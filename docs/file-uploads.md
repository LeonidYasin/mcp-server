# Бинарный staging API — кандидат #88

Ревизия документации 9 · 2026-10-15. **Реализация в отдельном PR, по умолчанию выключена; не production/live acceptance.** [План #88 → #89](binary-transfer-plan.md) · [TOOLS](../TOOLS.md) · [Sandbox](../SANDBOX.md) · [Deployment snapshot](deployment-status.md).

## Выбранный транспорт и клиентская граница

Один основной транспорт: **bounded MCP chunks через существующий `POST /mcp`**, без нового HTTP upload endpoint/ticket и без shell в целевом API. Chunk — canonical base64 **не более 48 KiB decoded / 65536 encoded characters**; целый файл никогда не должен попадать в модельный текст. Сервер сохраняет bytes как SQLite BLOB, не декодирует их как UTF-8 и не записывает их в Git.

Текущая агентная среда умеет передавать JSON-аргументы из файла (`arguments_file_path` у tool runner). В ней ранее проверен малый synthetic client→TEST probe; новая реализация отдельно требует live acceptance на точном TEST HEAD. Это **не обещание поддержки всеми Notion/MCP-клиентами**: без способности программно прочитать исходный файл и передать аргументы вне модельного текста автоматический канал недоступен. Сервер не видит клиентский `/data/...`.

Helper `scripts/prepare_file_upload.py` читает **локальный клиентский** файл, готовит один JSON аргументов с mode 0600 и печатает только факт подготовки/размер аргументов. Сам helper не делает сеть, не знает токен и не вызывает MCP. Оркестратор передаёт файл аргументов, читает bounded ответ и повторяет по `received`; ручная перезагрузка исходника, `gh` и base64 в чате не нужны. Не печатать/не загружать JSON чанка обратно в контекст модели. Capability runner, транспортные логи и история MCP host находятся вне контроля сервера: отсутствие payload retention там пока не доказано.

## Включение только в отдельном окружении

Все шесть инструментов отсутствуют в default discovery. Для отдельного TEST-кандидата оператор заранее создаёт приватный каталог mode **0700**, принадлежащий service user, и задаёт:

```dotenv
ENABLE_FILE_UPLOADS=1
FILE_UPLOAD_ROOT=/absolute/private/staging-directory
FILE_UPLOAD_ALLOWED_USERS=<comma-separated-positive-GitHub-user-IDs>
```

Это шаблон, не готовая команда для production. Не использовать общий каталог TEST/production, workspace shell tools, source checkout, symlink или каталог, доступный другим OS users. Только POSIX; runtime отказывает при неподдерживаемом/небезопасном root. Имена пользователя/ID проверяются оператором перед включением; `*`, пустая allowlist и невалидные ID запрещены. Ни shell/localfs, ни расширенные GitHub repo permissions не требуются. OS user root либо другой процесс того же UID уже может читать/изменять staging — этот API не заменяет OS sandbox. Каталог не должен попадать в public backup/артефакты CI; encryption at rest и filesystem quotas — отдельная policy оператора.

На **каждом вызове** сервер проверяет Bearer через фиксированный `GET https://api.github.com/user`, без redirect. Наличие заголовка, client-supplied owner и `initialize` не являются аутентификацией. Только проверенный numeric GitHub user ID из ответа 200 и явная allowlist дают доступ. Ошибки/401/403/redirect/невалидный ответ — fail closed, без staging mutation. Principal — **GitHub user**, не Notion user/сессия: два PAT одного GitHub пользователя разделяют его uploads, разные GitHub users изолированы. GitHub App installation tokens, не поддерживающие `/user`, не поддерживаются этим контрактом. Rate-limit/network failure не обходятся; запрос к GitHub выполняется для каждого chunk и входит в бюджет #77. PAT не сохраняется в БД и не включается в ответы/логи API.

## Схемы и ответы

Ответ каждого handler — MCP `content[0].text` с JSON. Успех содержит `ok: true`, отказ — `ok: false, error: <fixed_code>`; не полагаться на HTTP 200 как признак успеха. Отсутствующий Bearer ловится существующим JSON-RPC gate. У неожиданной ошибки upload handler нет traceback/body/path в серверном логе или ответе; upload request ID в request log редактируется.

| Инструмент | Обязательные аргументы | Успех / правило |
| --- | --- | --- |
| `begin_file_upload` | `name`, `size`, `sha256`, `request_key` | Непрозрачный `upload_id`, expected_size, received=0, expires, chunk_bytes/max_chunks. Имя — display basename, не путь; lower-case 64-hex SHA/key. Один случайный key + одинаковая metadata возвращают ту же запись до expiry/cancel; конфликт metadata отвергается |
| `append_file_chunk` | `upload_id`, `offset`, `data`, `chunk_sha256` | Offset — текущий received; строгий canonical base64 и SHA-256 bytes чанка. Exact повтор **того же chunk boundary/bytes** идемпотентен, в том числе после finish; gap/overlap/rechunk/conflict отвергаются. Payload никогда не отражается |
| `finish_file_upload` | `upload_id` | Проверены все chunks, contiguous offsets, полный size/SHA-256; только затем выдаётся `file_id` вида `file_<64hex>`, фактический size и hash. Повтор возвращает тот же file_id; file_id не является path |
| `get_file_upload_status` | `upload_id` | Только owner-visible bounded metadata, без bytes и filesystem path. Для uploading file_id отсутствует |
| `cancel_file_upload` | `upload_id` | Удаляет собственную pending/finalized запись и chunks, file_id инвалидируется. Повтор после удаления — `not_found_or_expired`, не ложный success |
| `cleanup_file_uploads` | нет | Удаляет только expired записи всех owners, без раскрытия их количества/IDs/metadata; не удаляет активные uploads |

`name`: NFC, 1–128 символов/≤255 UTF-8 bytes, без leading dot/edge whitespace, slash/backslash/colon и управляющих/format символов. Size/offset — неотрицательные integer, bool/float отвергаются. IDs — случайные 32 bytes hex, разные namespace upload_id/file_id. Незавершённый upload не разрешается через внутреннюю границу `verified_chunks(owner, file_id)`; она заново проверяет hash/size и owner. Её bounded iterator — задел для #89, **не готовый Release upload API**. Внутри этой транзакции запрещены network calls; будущий consumer должен копировать в отдельно авторизованный bounded stream/spool.

## Лимиты, атомарность и cleanup

- Файл ≤ **64 MiB**, чанков ≤ **2048**, chunk ≤ **48 KiB**. Использовать полные chunks, кроме последнего; слишком мелкие chunks могут исчерпать count limit. Пустой файл допустим: begin → finish с SHA-256 пустых bytes.
- **8 uploads / 128 MiB reserved** на GitHub user; **32 uploads / 256 MiB reserved** на staging root. Pending и finalized учитываются одинаково; резервируется весь expected_size при begin, не только уже записанные bytes.
- TTL **3600 секунд от begin**, не продлевается status/retry/finalize. Данные нельзя читать после expiry. Cleanup выполняется лениво при следующем вызове либо явно `cleanup_file_uploads`; при простое данные могут оставаться на диске до такого вызова. Это не background scheduler.
- SQLite `BEGIN IMMEDIATE` сериализует workers; chunk BLOB и received фиксируются **одной транзакцией**, без промежуточного file/DB split. До commit сбой откатывает оба; после потерянного ответа использовать status/тот же key/chunk/finish, а не новый begin вслепую. Lock timeout → `staging_unavailable`, безопасный retry/reconcile, не ложный success.
- БД — фиксированное `staging.sqlite3`, mode 0600; имена/ID никогда не подставляются в filesystem path. Symlink ancestors/root/database/sidecars, hardlinked/non-regular БД и широкие permissions отвергаются. Параллельные процессы того же UID/root не входят в threat model.
- Foreign-key cascade удаляет chunks; `secure_delete=ON` затирает SQLite freed cells. Это не cryptographic erase, не управление snapshots/backups/SSD. SQLite index/journal/page overhead не входит в logical reserved quota, DB не обязана уменьшаться после cleanup; storage-level budget/monitoring остаётся оператору.
- Сервер не делает URL fetch, ZIP extract, Git/Release/Actions mutation; не логирует chunks/токены/IDs upload-вызовов. Reverse proxy/WSGI/MCP host нужно отдельно настроить без body/Authorization tracing и с разумным request-body/rate limit. Когда `ENABLE_FILE_UPLOADS=1`, **все POST /mcp** (включая старые tools) дополнительно ограничены envelope **1 MiB до JSON parsing**, сверх лимита — HTTP 413. При выключенном flag поведение старых text API не меняется. Это opt-in operational constraint, не универсальный transport change; слишком большой batch следует разбить либо использовать другой deployment. Proxy/rate limits по-прежнему обязательны.

Ошибки: `uploads_disabled`, `upload_allowlist_not_configured`, `owner_not_allowed`, `authentication_required/failed/unavailable`, `staging_not_configured/unavailable`, `unsafe_staging_root/database`, `invalid_name/integer/id/sha256/base64`, `file_size_limit`, `chunk_size_limit`, `quota_exceeded`, `request_key_conflict`, `chunk_hash_mismatch`, `offset_conflict`, `chunk_conflict`, `size_mismatch`, `chunk_count_limit`, `already_finalized`, `incomplete_upload`, `file_hash_mismatch`, `integrity_mismatch`, `not_found_or_expired`.

## Воспроизводимый клиентский шаг

В **клиентской** среде, где уже доступен synthetic файл и tool runner поддерживает file-backed arguments:

```bash
mkdir -m 700 client-upload-args
python scripts/prepare_file_upload.py begin synthetic.zip client-upload-args/begin.json
# Runner: begin_file_upload(arguments_file_path=.../begin.json), проверить ok=true.
# Сохранить upload_id из bounded ответа, не печатая его в публичные логи.
python scripts/prepare_file_upload.py chunk synthetic.zip client-upload-args/chunk-0.json --upload-id "$UPLOAD_ID" --offset 0
# Runner: append_file_chunk(arguments_file_path=.../chunk-0.json).
# Продолжать от received, полными 49152-byte chunks, пока received == expected_size.
# Runner: finish_file_upload(upload_id=...), проверить ok, size и SHA-256.
```

Это pseudocode оркестратора, не обещание CLI-команды `arguments_file_path` для любого MCP client. При потере ответа повторять существующий файл аргументов, не генерировать новый request_key; helper EXCL не перезаписывает существующий output. Удалить локальные JSON с chunks после разрешённой проверки по policy клиента. Исходный файл в процессе upload должен оставаться неизменным; finish обнаружит изменение bytes по ожидаемому hash.

## Что доказано и что pending

Автоматические tests: arbitrary non-UTF-8 bytes, ZIP и минимальный synthetic XLSX; byte/size/SHA-256 сохранность, strict decode/bounds, incomplete/incorrect hash, offsets/exact retries/conflicts, quotas, owner isolation, TTL/cancel/cleanup, parallel connections, rollback и filesystem guards. Flask HTTP dispatch проверяет schema/нормализацию, Bearer gate и mocked `/user` verification; helper проверен через локальные JSON-файлы. Это **mocked/unit/in-process**, не deployed authenticated клиентский gate.

Дополнительно выполнен **малый authenticated deployed smoke** через отдельное MCP-подключение `/upload-test/mcp`, runtime `f39ee020324240833fb008f5c0fc19ad665bc9ca`: 50 synthetic bytes двумя чанками, exact chunk retry без дублирования, premature finish → `incomplete_upload`, финальные size/SHA-256 и opaque `file_id`, повтор finish с тем же ID, status, cancel и последующий `not_found_or_expired`. [Evidence](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204289526). Данные/hash/base64 сгенерированы программно существующим TEST Python tool; передача выполнена внешними MCP tool calls. Это **не** новый file-backed перенос исходного файла из sandbox клиента и не deployed binary/XLSX/большой прогон. Synthetic запись удалена; Release/Actions не вызывались.

**Новый deployed gate PASS:** настоящий ZIP из sandbox клиента передан через file-backed MCP arguments: **110 124 bytes / 3 чанка**, итоговые size/SHA-256 совпали, получен opaque file_id; запись удалена, status после cancel — not_found_or_expired. Base64 не выводился в контекст модели. [Evidence](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204515365). Это не server-side ZIP parsing, обратный download, XLSX, большой прогон или полная приёмка #88.

Pending: полная приёмка #88, включая deployed XLSX и дополнительные форматные проверки, live owner isolation/limits/expiry, проверку клиентской retention/log policy; отдельно разрешённый synthetic ~41 МБ и измерения #77. Успешный smoke не доказывает эти gates. #88 не закрывается по одним unit tests. Private inputs, Release assets/Actions E2E (#89), production deployment и reboot этим PR не разрешены.
