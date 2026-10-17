# Выпуск комнат в production: закрытый доверенный контур

Это release checklist, а не разрешение на production deployment. PR #116 остаётся
отдельным кандидатом. Общедоступный multi-tenant рынок требует другого access review:
rooms allowlist НЕ ограничивает остальные инструменты существующего MCP.

## Подтверждённый TEST baseline

Оператор сообщил установленный composite `a323a67f13ecb175a91e8f9726c76c11497483af`
на основе TEST `65ddae12bfaf6d117bb8f472ba396016db36610a` + rooms source
`9f93eb0d1091bf3eca0f60d6be7c6bbe6c45cfc8`. Состав 120 → 128 инструментов,
production PID не изменился. Это отдельная локальная сборка, НЕ HEAD этой ветки.

Обнаруженная регрессия: `ProtectSystem=strict` и `ProtectHome=read-only`;
ReadWritePaths первоначально включал лишь `/home/mcp-test/workspace` и
`/home/mcp-test/data`. Вызов rooms_list вернул room_storage_unavailable.
Оператор отдельно добавил только `/home/mcp-test/agent-rooms-115` в ReadWritePaths,
перезапустил только TEST и сообщил неизменные production/Caddy PID.

После исправления реальные MCP вызовы подтвердили:
- rooms_list, создание общей комнаты, отправку и чтение сообщения;
- повтор с тем же ключом: replayed=true, исходный ID, без второго сообщения;
- два чата с одним owner `github:79429232`: A → B → A, nonce из MCP и точный reply_to.

Evidence IDs: room `8c7e2c26-63cc-43bf-9e6d-d1a0195012a3`, A message
`e841b76b-6f74-4575-9075-ebe321709ab8`, B reply
`a3b59318-5ccb-4f9c-9a96-d8a4a64da443`. Текст и nonce не являются секретами,
но здесь не нужны. Сообщения TTL 24h; IDs — отчёт о проверке, не вечная ссылка.

Эти результаты НЕ доказывают live разных владельцев, reboot/power-loss,
production readiness новой hardening-ревизии или backup действующего VPS.

## Hardening в исходниках; не считать уже установленным

- Канонический абсолютный путь, приватный каталог service owner, файл 0600;
  отказ при symlink/alias, другом владельце файла/каталога и hardlink БД.
- SQLite synchronous=FULL, page_size=4096, max_page_count=16384 (64 MiB DB pages).
  WAL autocheckpoint 256 pages; journal_size_limit 1 MiB только после reset, НЕ
  жёсткий лимит активного WAL. Долгие readers/backup увеличивают WAL.
- Busy/locked: room_storage_busy, retryable=true, retry_after_ms=250.
  Повтор только по отдельному шагу и с исходным ключом, не бесконечный цикл.
  SQLite FULL: room_storage_capacity. Python без numeric error code возвращает
  generic room_storage_unavailable. В логах только numeric code/errno, не payload.
- Consistent backup через SQLite backup API; verify integrity/schema/FK;
  restore только в НОВЫЙ путь, без overwrite работающей БД.
- Установщик исторического TEST учитывает точный ReadWritePaths и проверяет
  SQLite внутри mount namespace активного TEST с последующим drop privileges.
  Это storage gate, не authenticated MCP gate. Этот root-скрипт запускает только
  оператор после отдельного согласования; агент его не исполняет.

## Gates до production

1. **CI exact SHA**: Python 3.10–3.13, полный pytest, docs/inventory, build wheel/sdist.
   Временные БД/fake identities не заменяют пункты ниже.
2. **Release assembly**: снять актуальный production SHA, clean status, dependency
   versions и tool baseline; учесть параллельные TEST доработки. Нельзя подменять
   production старой веткой комнат или переносить весь TEST без review.
   Закрепить immutable SHA и состав diff. Нужен отдельный утверждённый rollout.
3. **TEST новой ревизии**: разрешённое обновление без потери текущих изменений;
   registry=baseline+8, storage probe в systemd sandbox, authenticated list/send/read.
4. **Live владельцы**: два разных GitHub numeric IDs, индивидуальные Bearer и
   согласованный allowlist. B не читает/не пишет до join, затем A→B→A; B не удаляет
   сообщение A и не закрывает комнату A; после leave B не читает. Третий неразрешённый
   owner получает principal_not_allowed. Не просить токены в чате и не использовать
   общий proxy key как доказательство независимой личности. Это ещё не выполнено.
5. **Restart**: в отдельной тестовой комнате записать ID/cursor/key; оператор
   перезапускает только TEST; после этого authenticated read сохраняет сообщение,
   retry возвращает тот же ID, cadence не сбрасывается. Не рестартовать production
   ради проверки. CI fresh-process reopen не является live systemd evidence.
6. **Backup/restore drill**: оператор делает consistent snapshot, восстанавливает
   в новый приватный TEST-путь; проверяет IDs, membership, tombstone, cadence и
   idempotency. Исходная работающая БД не заменяется. Snapshot содержит сообщения
   и owner IDs; 0600, ограниченная retention, защищённая off-host копия по политике
   владельца. Пока нет расписания и проверенного off-host восстановления — gate открыт.
7. **Capacity/operations**: оператор назначает бюджет filesystem (DB+WAL+backups),
   мониторинг свободного места и growth, алерт на storage errors и on-call владельца.
   Начальный порог: алерт при свободном месте <256 MiB ИЛИ <10%, с последующей
   корректировкой по измерениям. Квоты SQL не заменяют filesystem quota.
   Измерить p95/errors на целевом числе workers и реальном диске; не обещать SLA
   по threaded unit tests. Нагрузку на VPS отдельно согласовать.
8. **Rollout/rollback**: согласовать downtime, backup и pinned version; добавить
   только нужный write path и env, не отключать sandbox. После запуска проверить
   authenticated MCP и прежние tools. Rollback к прежнему коду/config; оставить
   данные и snapshots, не удалять существующие drop-ins и не сбрасывать main.
   Не считать успешный registry/health подтверждением SQLite или auth.

Production включается только после явного решения владельца о закрытии gates.
До этого PR остаётся draft; production, Caddy и Agora этой работой не меняются.

## Команды утилиты: шаблоны, не автоматическое выполнение

Новая утилита входит в hardening-исходники. Выполнять **от service OS user** из
проверенного checkout/venv, не от root и не через инструмент run_python агента.
Ниже placeholders; пути и unit согласуются отдельно для TEST/production.

```text
<VENV_PYTHON> -m mcp_server.tools.rooms.maintenance verify <ABSOLUTE_DB_PATH>
<VENV_PYTHON> -m mcp_server.tools.rooms.maintenance backup <ABSOLUTE_DB_PATH> <NEW_SNAPSHOT_PATH>
```

Оба каталога приватные, canonical, принадлежат запускающему пользователю. Выход —
только ok/counts/error. Snapshot не перезаписывается. Для restore выполнить backup
от snapshot в ЕЩЁ ОДИН новый путь, verify, затем отдельно согласовать остановку
нужного сервиса и переключение AGENT_ROOMS_DB. Не копировать один .db от активной
WAL БД, не удалять -wal/-shm и не менять user_version вручную. После restore вернутся
состояния на момент snapshot, включая снятые позже сообщения/закрытые комнаты;
соблюдать retention и повторно проверять права. Сообщения всё равно недоверенные.
