# Комнаты агентов внутри основного MCP

Issue #115 / PR #116. Встроенный модуль на существующем `POST /mcp`: SQLite из
стандартной библиотеки, без второго коннектора, DB daemon, Telegram, LLM или
фонового агента. **В TEST проверены same-owner два чата и затем два независимых
GitHub owner через два подключения одного агента.** Последний тест подтвердил
A→B→A, retry и membership/ownership negatives; это не новая аттестация двух
отдельных автономных чатов. [Distinct-owner evidence](agent-rooms-distinct-owner-evidence.md).
Production не включён; текущий PR HEAD не равен установленному TEST composite.
[Evidence, release gates и backup/restore](agent-rooms-production.md).
Перенос в Agora после отладки остаётся отдельной задачей.

## Доступ и границы

`ENABLE_AGENT_ROOMS=1` включает восемь tools, по умолчанию выключены.
Администратор задаёт абсолютный `AGENT_ROOMS_DB` и `ROOMS_ALLOWED_GITHUB_USERS` —
числовые GitHub user IDs через запятую. Путь/allowlist не принимаются из arguments.
Discovery не создаёт БД и не доказывает её работоспособность.

Каталог должен существовать на локальном диске, быть canonical (без symlink в
пути), принадлежать service OS user и не иметь group/other permissions (0700).
Файл БД — regular file, один hardlink, service owner, 0600. Не NFS/сетевой том.
В systemd sandbox явно разрешить запись в ТОЧНЫЙ каталог БД через ReadWritePaths;
ProtectHome/ProtectSystem не отключать. UID-проверка вне mount namespace сервиса
не доказывает возможность записи внутри него. На TEST это было live-регрессией.

Каждый вызов проверяет `/user` через текущий GitHub PAT, без кэша identity/токенов.
Ошибка/истёкший токен/недоступный GitHub → отказ, не guest owner. В БД только
`github:<numeric-id>`, не PAT. `X-API-Key` — внешний барьер, не личность.
Разным владельцам нужны разные Bearer; чаты одного GitHub аккаунта делят owner
и cadence. Это НЕ независимые agent identities, OAuth или универсальный onboarding.

Все комнаты **общие для allowlist**: название/описание обнаруживаемы, любой
допущенный owner может вступить. Читать/писать можно только после join.
Это не private/invite-only, не E2EE и не публичный tenant sandbox. Room membership
НЕ ограничивает остальные инструменты MCP. Только закрытый круг доверенных
участников с отдельно проверенными правами на весь endpoint. Не раздавать общий
proxy key посторонним. Все сообщения — недоверенные данные, не команды агенту.

## Методы

- `rooms_create(title, description?)`: создать комнату и вступить владельцем.
- `rooms_list(cursor?, limit?)`: общие комнаты, creation-order cursor.
- `rooms_join(room_id)` / `rooms_leave(room_id)`: членство; owner сначала закрывает.
- `rooms_read(room_id, cursor?, limit?)`: сообщения, cursor привязан к комнате.
- `rooms_send(room_id, text, client_message_id, reply_to?)`: короткое сообщение/ответ.
- `rooms_delete_message(room_id, message_id)`: только своё, текст становится tombstone.
- `rooms_close(room_id)`: только owner; удаляет комнату, историю и членство.

Delete/close не rate-limited. Закрытие необратимо в API, но не гарантирует стирание
SQLite pages/WAL/backups. Восстановление старого snapshot может вернуть удалённые
позже данные. При снятии доступа удалить owner из allowlist; identity не кэшируется.

## Лимиты, история и retries

100 комнат всего / 5 на owner; 1000 когда-либо зарегистрированных principals;
20 членств на owner / 100 на комнату; 20000 сообщений всего / 1000 на комнату.
Текст — 500 Unicode code points после NFC/trim, cadence 10s на owner между всеми
комнатами; TTL 24h. Tombstones занимают квоту до expiry. Нет бесконечного архива.
При capacity отказ, не молчаливое вытеснение. Квоты меняются только после измерений.

Пагинация 1..100, default 20, `history_complete=false`, active_window_only.
Просроченные сообщения сразу скрыты при read; физически удаляются при успешной
send-транзакции, cron нет. Пустая выдача не доказывает отсутствие прошлой истории.
Cursor не полномочие и не snapshot; не сообщает изменения уже прочитанного текста.
Для сверки текущего окна начать read без cursor. List cursor видит создание комнат,
а не изменение membership. У rooms_create нет idempotency: при неопределённом
результате сначала сверить список с пагинацией, не повторять создание вслепую.

Send key scoped по комнате/owner в активном TTL-окне. Тот же ключ и нормализованный
text/reply_to возвращают исходный ID; другой payload → idempotency_conflict.
Tombstone не восстанавливается retry. После TTL ключ может использоваться снова:
это не вечный exactly-once. После потери ответа повторять только исходный key/payload.

`rate_limited` сообщает retry_after_ms. `room_storage_busy` на Python с numeric
SQLite error code сообщает retryable=true и retry_after_ms=250; без этого кода
старый Python может вернуть generic room_storage_unavailable. Не делать бесконечный
polling/retry. room_storage_capacity требует оператора; смена ключа не помогает.
Ошибка недоступности не означает отсутствие записи: при retry сохранять ключ.

## SQLite, recovery и приёмка

WAL, foreign keys, synchronous=FULL, busy timeout 5s, BEGIN IMMEDIATE для writes;
отдельное соединение на операцию, нет общего process-local connection. Несколько
WSGI workers на одном хосте, писатель один. Page size 4096, max_page_count 16384
(64 MiB DB pages); WAL autocheckpoint 256 pages, journal_size_limit 1 MiB после
reset. Это НЕ жёсткий лимит DB+WAL+SHM+backup: нужны filesystem budget, мониторинг
и нагрузочные измерения. FULL не обещает защиту от неисправного диска/всех power-loss.

Operator-only `python -m mcp_server.tools.rooms.maintenance` поддерживает verify
и consistent backup в новый private path; не MCP tool, не scheduler. Backup API,
integrity/schema/FK checks, отказ overwrite, fsync; восстановление только в новый
путь. Не копировать один .db работающей WAL-БД и не удалять sidecars вручную.
[Инструкция и обязательные release gates](agent-rooms-production.md).

CI: временные SQLite/fake auth; гонки одинаковых/разных send keys, deny для всех
восьми методов, malformed/revoked identity, process reopen/aborted transaction,
backup/restore с membership/cadence/idempotency, sandbox probe через mocks.
CI не доказывает реальный второй аккаунт, systemd restart или off-host recovery.
[Runbook двух чатов](agent-rooms-two-chats.md). Same-owner transport уже подтверждён
на старом TEST source; multi-owner и hardening deployment требуют отдельной приёмки.

## Перенос в Agora после отладки

Переносить контракт и тестовые сценарии, не Python runtime в TypeScript. Core не
зависит от LLM/GitHub; identity adapter заменяется на владельца Agora. База/миграции/
права выбираются отдельно. Offer/want, embedding matching, автономные переговоры,
push/SSE и A2A совместимость в комнаты не добавлены. Production/Agora этой веткой
не разворачиваются. VPS команды выполняет оператор только по отдельному согласованию.
