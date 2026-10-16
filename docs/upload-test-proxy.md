# Временный защищённый маршрут upload-TEST

[API](file-uploads.md) · [Отдельный loopback TEST](upload-test-deployment.md).

`scripts/upload_test_proxy.py` выполняется оператором из root-консоли, после review/CI и проверки checksum скрипта. Код API работающего upload-TEST остаётся на отдельно закреплённом runtime SHA; добавление этого инструмента не переключает checkout или сервис.

Программа читает только локальный Caddy admin API и закрытый snapshot оператора. Конфигурация должна совпадать со snapshot. Единственный `/test/*` с upstream3002 должен быть вложен в положительную exact `X-API-Key` проверку и host matcher `leonid-mcp.duckdns.org`. Непонятная/иная политика, OR без key, wildcard, custom proxy/headers, другой rewrite или конфликт нового prefix приводят к STOP, не к ослаблению защиты.

Новый exact `/upload-test/mcp` клонируется рядом с `/test/*` ВНУТРИ ТОЙ ЖЕ key-защиты. Меняются только path, strip prefix и upstream3004, добавляется уникальный cleanup ID. Header/key не экспортируются и не задаются заново. PATCH изменяет только содержащий routes array с If-Match ROOT Etag, защищая и предков от конкурентной смены auth. HTTP412 — остановка, не blind retry применения. Caddyfile не меняется, Caddy process не перезапускается; runtime config reload всё же выполняется через admin API.

TLS gates идут напрямую на localhost443 с проверенным SNI/сертификатом публичного hostname, без DNS/proxy/redirect и без PAT: старые production/TEST ping до/после; новый route без/с неверным key должен дать401, с правильным key tools/list должен вернуть119 tools. Ключ остаётся в памяти root-процесса на VPS. Проверка fingerprints прежних master PID дополняет read-back конфигурации.

До изменения планируется отдельный transient cleanup timer на45 минут. Это АВТОМАТИЧЕСКАЯ ПОПЫТКА удаления, не обещание успеха при недоступном Caddy/изменении маршрута оператором. Cleanup удаляет только совпадающий ID И неизменённое содержимое нашего route, использует свежий root Etag, сохраняет чужие concurrent edits; уже отсутствующий route — no-op. При ошибке post-gates сразу выполняется такая же безопасная rollback-попытка. Закрытый state и код сохраняются в /root для ручной проверки/cleanup; не публиковать их содержимое. Выведенная cleanup_command удаляет только новый route, не останавливает сервисы и не восстанавливает старую конфигурацию целиком.

После PROTECTED UPLOAD ROUTE READY ещё нужны внешняя negative-auth проверка и отдельное MCP connection/реальное client→API acceptance с настоящим GitHub /user. Это не разрешение private inputs, ~41MiB, Release/Actions или production rollout. Текущие TEST #87, Agora и production не заменяются.

Caddy Etag/If-Match behavior: https://caddyserver.com/docs/api#concurrent-config-changes
