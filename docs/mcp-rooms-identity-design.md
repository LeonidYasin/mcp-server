# MCP Rooms: identity без обязательного GitHub

Статус: предлагаемый дизайн по новому запросу владельца. Public + MIT утверждены;
[репозиторий создан](https://github.com/LeonidYasin/mcp-rooms); token permissions
исправлены и module/tests/docs/CI перенесены в [draft PR #1](https://github.com/LeonidYasin/mcp-rooms/pull/1).
Реализована alpha local UUID/Bearer adapter + официальный SDK; OAuth остаётся planned,
deployment/live client acceptance не выполнены. Предложения
о необходимости выбора visibility/license ниже — исторический контекст до решения.
Это не реализованный standalone auth и не разрешение deployment. Tracking: #117.

## Изменение последовательности

Владелец запросил вынести/скопировать модуль в отдельный repo уже сейчас и убрать
обязательную GitHub identity. Выделение исходников и CI можно выполнять ДО закрытия
всех embedded production gates; публичный rollout и миграция данных по-прежнему
требуют отдельной приёмки. Не ждать третьего GitHub аккаунта ради разработки:
standalone CI использует собственные principals, затем отдельный live pilot.

Предлагаемое имя LeonidYasin/mcp-rooms; public/private и лицензия требуют решения
владельца до создания/публикации. В проверенном root tree mcp-server нет LICENSE,
а pyproject.toml не объявляет license. Public source не означает разрешение на
произвольное relicensing. До выбора владельца не добавлять MIT автоматически;
проверить авторство/права исходников и notices зависимостей.

## Решение для первого закрытого пилота

Один rooms-only процесс, Streamable HTTP MCP, SQLite, TLS через existing reverse
proxy после отдельного согласования. Никаких GitHub API/PAT, shell, web/GitHub
write tools в standalone. Сохраняются восемь rooms_* методов и лимиты/ошибки.
Существующий embedded TEST и его GitHub adapter остаются без изменений.

Локальный invite-only identity provider с индивидуальными opaque Bearer tokens.
Это практический private pilot mode, НЕ реализация стандартного OAuth flow и
НЕ гарантия совместимости со всеми MCP клиентами. Клиент должен уметь безопасно
настроить Authorization header; фактический Notion/other-client gate отдельный.
Официальная справка Notion описывает header auth (API key/Bearer) у custom MCP.

- user_id: server-generated UUID, неизменный после rotation/provider change.
- owner в core: строго `user:<canonical-UUID>`, не email/display_name/token.
- credential_id: отдельный ID каждого подключения/агента. Два ключа одного user
  дают одного owner, общие права и per-user cadence/quota; rotation не сбрасывает
  лимиты и не лишает истории/членства.
- display_name не уникальный идентификатор и не доказательство identity.
- В первом релизе агент действует от имени user; это не независимая autonomous
  agent identity/delegation. Отдельные agent ACL — последующее версионируемое решение.

Никаких user_id/owner в tool arguments или доверия X-User-ID от клиента. Verified
principal создаёт только auth adapter. Наличие UUID в запросе не даёт полномочий.
Общий proxy key может быть дополнительным барьером, но не заменяет user credential.

## Выдача и жизненный цикл ключей

1. Оператор создаёт пользователя через local maintenance CLI с правами service
   owner; CLI НЕ MCP tool и НЕ публичный endpoint регистрации. Нужны audited
   create-user, issue-token, revoke-token, disable-user. Агент их на VPS не запускает.
2. У каждого подключения свой cryptographically random secret >=32 bytes.
   Публичный token_id используется только для bounded lookup, не для авторизации.
3. В базе сохраняются token_id, digest секрета, user_id, service/resource binding,
   scopes, expires_at, revoked_at; raw secret не хранится. Для равномерного
   256-bit secret допустим SHA-256 digest и constant-time comparison; password
   hashing к этому не приравнивать. Если появятся пароли — отдельный reviewed flow.
4. Секрет выдаётся один раз в приватный 0600 файл в canonical каталоге service
   owner, без overwrite/symlink/hardlink, не в общий лог, Git, URL или tool response.
   Пользователь переносит его в защищённую форму подключения; не просить в чате.
5. Auth каждого HTTP запроса проверяет digest, expiry, revoked/disabled status,
   разрешённый resource и scopes. По умолчанию reject unknown/malformed token.
   Токен только Authorization: Bearer, никогда query/path/message.
6. Rotation выдаёт новый credential того же user; старый явно отзывается после
   проверки подключения. Отзыв после commit блокирует новые запросы; не обещать
   отмену уже выполняющегося запроса. Long-lived identity cache не применять.
7. Потеря всех ключей в пилоте: операторский recovery, не самозахват аккаунта по
   имени/email. Disable user закрывает доступ, не удаляет историю автоматически.

Bearer — переносимое полномочие: кто украл токен, действует как владелец. Нельзя
доказать уникального человека или конкретный чат одним токеном. Invite-only плюс
per-user quotas не предотвращают Sybil в открытой саморегистрации. Для public
market нужны отдельные moderation/onboarding/abuse/storage budgets.

## Authorization и данные

Предлагаемые таблицы identity schema: users(id,status,display_name,created_at),
credentials(id,user_id,digest,resource,scopes,expires_at,revoked_at), а в будущем
external_identities(issuer,subject,user_id) с unique(issuer,subject). Scopes whitelist
rooms:read/rooms:write; delete/close всё равно требуют domain ownership. Management
scope не принимается на публичном MCP. Приватный auth/store может быть одним
SQLite файлом с versioned migrations и согласованным backup; не второй DB daemon.

Существующие комнаты остаются public_to_enrolled_users: допущенный пользователь
видит каталог и может join; read/send требуют membership. Это НЕ private rooms.
No-auth 401; valid credential без нужного scope 403; membership/ownership domain
errors сохраняют wire contract. tools/list может показывать только rooms registry;
не переносить discovery остальных 120 tools или registry auto-import всего сервера.

## OAuth/OIDC: следующий adapter, не самописный auth server

Для клиентов с browser sign-in использовать поддерживаемую OAuth 2.1 реализацию/
authorization server, а не собственный grant/token/password протокол. MCP resource
server проверяет выданный ДЛЯ НЕГО access token. Нужны Protected Resource Metadata,
discovery, Authorization Code + PKCE, корректный issuer/audience/resource/scopes,
expiry и refresh/revocation policy. ID token не принимать вместо access token,
GitHub/Google tokens не пересылать в room tools; клиент не задаёт trusted issuer.

Пользователь rooms не равен external subject: mapping по проверенной паре
(issuer,subject), не по email. Привязка к существующему user только с доказательством
владения обоими входами или audited recovery; не объединять аккаунты автоматически.
GitHub может быть необязательным provider позднее, никогда prerequisite.
OAuth service может быть self-hosted; платный IdP не обязателен. Выбор конкретного
готового компонента после проверки лицензии, ресурсов VPS и реального клиента.
Notion compatibility зависит также от client registration/discovery; не объявлять
любой OIDC provider готовым MCP authorization server без интеграционного теста.

Нормативные/продуктовые источники:
- https://modelcontextprotocol.io/specification/latest/basic/authorization
- https://www.notion.so/help/mcp-connections-for-custom-agents
Latest спецификация меняется: при реализации закрепить поддерживаемую revision.
Static Bearer pilot не объявлять OAuth-conformant только из-за наличия header.

## Что переносим и что изменяем

Source snapshot: mcp-server PR #116 at 5290a940b77d60924a9d4d53b76b7de8af9c4e83.
Копировать только reviewed room store/maintenance + focused tests и документацию
с provenance path/blob/commit. Ops transport adapter и registry переписать узко:
не импортировать GitHubClient и mcp_server auto-discovery. Core сейчас содержит
regex github:<numeric-id> в RoomStore._actor — это реальная связность, её нужно
заменить явно, а не просто переименовать папку. Сохранить все storage guards,
transactions/TTL/retry/cadence/backup/schema protections и тестировать их перенос.

Новая standalone установка — НОВАЯ БД. Embedded owners github:* не переписывать
автоматически в user:*; live messages/PAT/env/root backups не копировать. Будущая
миграция требует доказанного identity mapping, consistent snapshot/new-path restore
и отдельного согласования. Wire shape owner остаётся строкой, namespace changing
документируется: клиенты не должны считать её обязательным GitHub profile URL.

До standalone contract parity source of truth остаётся embedded. Затем canonical
versioned core package в mcp-rooms; embedded использует pinned compatibility adapter
с GitHub principal namespace, не две расходящиеся ручные копии. Перенос namespace
не должен ломать существующую embedded БД или подменять владельцев.

## Проверки до standalone TEST

- Все восемь room contracts + storage/concurrency/crash/backup tests перенесены;
  package install/build и CI exact SHA. Generic principals вместо fake GitHub API.
- Два credentials одного user: общая identity/cadence; разные users: ownership
  isolation; третий disabled/unknown user denied; no-auth/expiry/revoke/scope cases.
- Rotation сохраняет membership/history/idempotency/rate limits. Подделка UUID,
  X-User-ID, token_id без секрета и токен другого resource не дают доступ.
- Выдача/recovery не доступны через MCP; secrets redacted из access/error logs,
  headers не попадают в health/diagnostics. Auth DB guards и backup privacy проверены.
- Реальные MCP clients, restart/recovery, disk/WAL/load и scoped rollback отдельно.
- После operator-approved standalone TEST на новом loopback port — отдельная
  приёмка; никаких автоматических production/Caddy/старых connection изменений.
