# Временный TEST-алиас для второго GitHub владельца

Notion в текущем workspace отклонил повторное добавление `/test/mcp` с другим
именем: этот URL уже добавлен. Это observed UI constraint, не утверждение, что
Notion никогда не поддерживает per-user OAuth или два аккаунта любым способом.
Для проверки в этом workspace владелец разрешил временный защищённый alias.

## Scope

Планируемый адрес: https://leonid-mcp.duckdns.org/test-rooms-b/mcp.
Он НЕ активен от одного наличия файла в PR. Его включает только оператор после
pinned download/checksum и согласования. Это тот же TEST:3002 и SQLite, не новая
служба/БД. Основной endpoint и соединение не заменяются.

`scripts/rooms_test_alias.py add`: свежий GET Caddy config+ETag; требует единственный
точный host guard и exact X-API-Key matcher, внутри него `/test/*` → loopback3002.
Никакой header OR/weak wildcard key/Authorization override. Новый exact path route
перед TEST/fallback: rewrite `/mcp`, тот же reverse_proxy; Bearer не задаётся и
не подменяется. Добавление PUT с If-Match, post-check вне alias config не изменён.
Не редактирует Caddyfile и не рестартует службы; Caddy runtime config изменяется
через admin API и может быть автоматически сохранён самим Caddy по его политике.
Снимок исходного config приватный0600 и содержит секреты: не присылать в чат.

После добавления: без/с неверным proxy key ожидается401; с существующим key ping
и tools/list сравниваются с loopback TEST (128 tools/8rooms). До/после проверяются
production/test MCP pings, PID TEST/production/Caddy и hash Caddyfile. No redirects,
no environment HTTP proxy, bounded responses. GitHub PAT в скрипте нет.

## Cleanup и ограничения

Перед добавлением создаётся root transient systemd timer на90 минут, выполняющий
ОДНУ попытку cleanup (внутри до3 CAS retries). Это не гарантия удаления при outage,
конкурентной модификации самого route или недоступном admin API. Итог содержит
точную ручную cleanup_command и private state path. При ошибке добавления/проверки
script пытается удалить только собственный exact route. Никакого whole-config
restore: чужие параллельные изменения сохраняются. Изменённый route/duplicate IDs
→ отказ вместо удаления чужой конфигурации. После cleanup удалить тестовый профиль
подключения отдельно; не удалять основное соединение. Приватные snapshot/state
и timer не очищать вручную до подтверждённого удаления alias.

## Проверка владельцев

maranan-jpg numeric GitHub ID340767429 проверен через public `/users/maranan-jpg`.
Его ещё НЕТ в room allowlist (разрешён только79429232). Сначала подключить новый
URL с ИНДИВИДУАЛЬНЫМ Bearer maranan-jpg и существующим proxy key через защищённую
форму, без передачи токенов в чат/URL/repo. rooms_list ожидаемо principal_not_allowed.
Затем отдельное разрешённое добавление ID в TEST allowlist и рестарт TEST;
verify distinct owner в MCP, membership/ownership negatives и A→B→A.
Не считать tools/list/ping доказательством GitHub identity. Room allowlist НЕ
ограничивает прочие128 tools TEST; это только доверенный пользовательский аккаунт,
не onboarding посторонних и не публичная tenant boundary. Использовать минимальный
PAT без repo-write permissions для этой проверки. Не выполнять другие tools от B.

Состояние до операторского запуска: alias planned, allowlist unchanged, distinct-owner
gate pending. CI synthetic fixtures/mock HTTP — не доказательство live маршрута.
