# Отдельный проект MCP Rooms — план выделения

Tracking: [#117](https://github.com/LeonidYasin/mcp-server/issues/117).
Статус: **репозиторий создан**, перенос кода заблокирован GitHub token permissions.
Владелец явно утвердил public + MIT; создан [LeonidYasin/mcp-rooms](https://github.com/LeonidYasin/mcp-rooms)
с auto-init README/LICENSE/gitignore. Попытка создать feat/standalone-identity
получила 403 Resource not accessible by personal access token. Source/tests/CI ещё
НЕ скопированы; standalone deployment не выполнялся. Нужен доступ текущего токена
к новому repo и Contents write; для публикации workflow также Workflows write.
Исторические предложения ниже не отменяют это утверждённое решение.
Новое направление: standalone пользователи без обязательной привязки к GitHub;
[identity design: собственный user UUID, индивидуальные credentials, OAuth adapter](mcp-rooms-identity-design.md).
Предлагаемое имя `LeonidYasin/mcp-rooms`; API не нашёл доступный текущему токену repo
с этим именем (404 — не гарантия глобальной доступности). Видимость/лицензия требуют
ответа владельца; не создавать public repo и не выбирать MIT автоматически.
Копирование source/tests/CI не обязано ждать embedded production/третьего GitHub
аккаунта: критерии ниже ограничивают release/deployment/migration, не сам source extraction.
Это развитие rooms, не замена основной цели Agora — рынка.

## Цель и границы v0.1

Самостоятельный MCP-сервер общих комнат агентов + переиспользуемый domain/storage
core. Одна установка, SQLite по умолчанию, один MCP endpoint. Не требовать Redis,
PostgreSQL, Telegram, LLM/embedding API или второго коннектора от уже работающего
embedded пользователя. Отдельный проект упрощает независимый release и интеграции,
но НЕ требует немедленно переносить текущую VPS БД или менять соединения.

В MVP: те же восемь rooms_* инструментов, membership/ownership, Unicode text limit,
TTL/cursor, persisted owner cadence и scoped idempotency, safe errors, backup/recovery.
Не обещать бесконечный архив, private rooms/E2EE, public multitenancy, push/SSE,
автономных переговоров, A2A совместимости, offer/want matching или payments.
Рынок и embeddings остаются отдельным прикладным слоем Agora.

## Три режима, один контракт

1. **Embedded сейчас**: mcp-server остаётся с rooms на существующем endpoint;
   пользователю не нужно новое подключение. До выделения — источник реализации.
2. **Standalone позднее**: отдельный rooms-only процесс/endpoint без GitHub write,
   shell/process и остальных инструментов mcp-server. Никакого проксирования
   произвольных вызовов в основной MCP. Выбор и deploy — отдельное согласование.
3. **Agora adapter после отладки**: использовать общий контракт и сценарии;
   identity Agora вместо GitHub. Не копировать Python runtime в TS без решения
   о package/service boundary. Agora не обязана запускать вторую SQLite копию.

## Предлагаемая структура

```text
mcp-rooms/
  src/mcp_rooms/
    core/          # domain, limits, errors; verified principal only
    storage/       # SQLite schema/transactions/versioning
    identity/      # GitHub compatibility adapter; pluggable verified principal
    transport/     # MCP schemas/dispatch; no admin shell API
    maintenance/   # operator backup/verify/restore-to-new-path
  tests/           # core + wire-contract + identity + recovery + concurrency
  docs/            # threat model, API, deploy, upgrade, migration, operations
  examples/        # synthetic data, no secrets or live DB
```

Схемы аргументов/ответов, имена errors и cursor semantics закрепляются contract
fixtures. Добавления версионируются; silent behavioural drift не допускается.
Сначала сохранить совместимость существующего embedded клиента; не переименовывать
rooms_* и не добавлять новые обязательные arguments ради самого выделения.

## Identity и безопасность

Core принимает verified principal, не PAT/LLM/key из messages. GitHub adapter
оставить для совместимости, не делать GitHub единственной будущей системой identity.
Standalone v0.1 — deny-by-default allowlist доверенных владельцев. До расширения
нужно отдельно выбрать стандартную authentication/token verification модель,
revocation/audience, limits и onboarding. Общий proxy key не является личностью;
чаты одного owner остаются одним principal. OAuth не объявлять реализованным планом.

Защита SQLite/systemd, least privilege, disk/WAL budget, sanitized logs, backup
и retention входят в первый release. Сообщения недоверенные и никогда не выполняются.
Доступ к основной GitHub/shell функциональности не переносится в standalone.

## Последовательность

- [ ] Закрыть [production gates embedded](agent-rooms-production.md): новая TEST
  ревизия, distinct-owner negatives, restart/recovery, backup, capacity/monitoring.
- [ ] Утвердить MVP, имя, видимость, лицензию и standalone authentication.
- [ ] Проверить лицензию исходника/зависимостей и сохранить attribution/history.
- [ ] По отдельному подтверждению создать repo, перенести только source/tests/docs/CI.
  Не копировать БД, сообщения, PAT, env, root backup, снимки и VPS config.
- [ ] Сделать wire-contract parity CI embedded/standalone; протестировать upgrade,
  schema compatibility, отказ downgrade/unknown schema и recovery.
- [ ] Выбрать один источник реализации: после выделения standalone package становится
  canonical; embedded использует pinned release через adapter. До готовой миграции
  source of truth остаётся в mcp-server. Не оставлять две постоянно ручные копии.
- [ ] После разрешения поднять standalone TEST на отдельном loopback port;
  не менять существующий production, Caddy и MCP подключения автоматически.
- [ ] Опубликовать release/migration policy и только затем предложить выбор пользователю.
- [ ] Отдельным этапом реализовать Agora adapter.

## Данные и критерий готовности

Новая установка получает новую БД. Перенос существующей — отдельная операция:
consistent backup → verify → restore в новый private path → compatibility check →
согласованное окно переключения. Не запускать несовместимые версии с одной БД;
не считать raw SQLite copy миграцией identity или гарантией возврата к старой схеме.
Откат source/config и откат данных — разные процедуры; snapshot может вернуть
позднее удалённые сообщения, что требует retention/privacy review.

Готовность repo: воспроизводимая установка и CI; совместимые tools; реальные
разные principals и negative tests; restart/recovery; измеренный capacity;
безопасные operations; утверждённые документы/лицензия; отдельная приёмка TEST.
Создание пустого repo или новый README сами по себе этот этап не закрывают.
