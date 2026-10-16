# Состояние deployment и проверок

> **Обновление приёмки #88:** file-backed ZIP и XLSX, live count quota 8/9 и освобождение ёмкости после cancel — PASS. Полная приёмка ещё открыта. [Матрица доказательств и оставшиеся gates](upload-acceptance.md) · [XLSX/quota evidence](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204702804).

Ревизия документации 9 · снимок на 2026-10-15. Это исторически закреплённое состояние, не обещание, что каждый будущий commit main уже развёрнут. [README](../README.md) · [Roadmap](../ROADMAP.md) · [Карта](project-map.md) · [Validation](validation.md) · [Файловый план](binary-transfer-plan.md).

## Production и TEST — отдельные состояния

| Окружение | Проверенная ревизия / профиль | Статус |
| --- | --- | --- |
| Production | `b78b209cf5e8927c2c4bb9771d6ff0bafcad0cf6`, detached HEAD, версия 0.4.3, 113 tools | Rollout и внешний MCP smoke passed; localfs/localgit, shell/process, Synapse выключены |
| TEST | `ef7993b87e8d6ed6598065e46203dc6145f9286d`, кандидат Draft PR #87, 119 tools | Shell/process включены только TEST; localfs/localgit/Synapse выключены. Специализированный authenticated deployed artifact gate pending |
| main после merge #70 | `b78b209cf5e8927c2c4bb9771d6ff0bafcad0cf6` | Документационный merge; будущие docs commits не меняют закреплённую production revision автоматически |

Production: `mcp-server.service`, Unix user/group `mcp`, checkout `/home/mcp/mcp-server`, venv `.venv`, Gunicorn, локальный порт 3001. TEST: `mcp-test.service`, user `mcp-test`, checkout `/home/mcp-test/mcp-server`, отдельный venv `/home/mcp-test/venv`, порт 3002; внешний путь `/test/mcp`.

## Что реально выполнено

1. До rollout проверен точный HEAD PR #70 `602b6e9ffa8eb1f31d54db5610c56f9cc436e2ad` в отдельном checkout/venv под `mcp-test`: **640 pytest**, inventory **113/143**, 74 локальные ссылки, smoke import, wheel/sdist. [VPS evidence](https://github.com/LeonidYasin/mcp-server/pull/70#issuecomment-6200030171).
2. PR #70 squash merged; дерево reviewed HEAD и merge SHA одинаково. CI main: [run 38790796983](https://github.com/LeonidYasin/mcp-server/actions/runs/38790796983). Проверка кода не подменяет отдельную приёмку каждого backlog issue.
3. Пользователь запустил guarded root-скрипт: preflight service/user/path/old HEAD/target SHA/dependencies, приватный backup, переключение только production и автоматический rollback при ошибке. Git/import выполнялись от `mcp`, systemd orchestration — от root. Итог **ROLLOUT PASS**, откат не потребовался, новый process, 113 tools, зависимости не менялись. Незатреканный файл `To` оставлен на месте и скопирован в закрытый root backup; содержимое не публиковалось.
4. Независимые проверки после rollout: localhost health production/TEST; внешний production MCP `hash_text`; schema `merge_pull_request` требует `expected_head_sha`; target combined checks success (7), источник полон. Внешний smoke — ограниченная проверка доступности/схем, не исчерпывающий acceptance всех API. [Rollout и external evidence](https://github.com/LeonidYasin/mcp-server/pull/70#issuecomment-6202583914).

TEST, Caddy, system packages и VPS reboot **не затронуты**. `pip install`/обновление зависимостей не выполнялись. Старый production SHA: `dbefdad1ec84e723a95cb1219aa631557cd72ad4`. Реальный root backup сохраняется у оператора (`/root/mcp-rollout-<id>`); удалять его или `To` этой актуализацией не предлагается.

## Статическая документация / Pages

После merge #70 существующий workflow автоматически завершился успешно: [Pages run 38790795808](https://github.com/LeonidYasin/mcp-server/actions/runs/38790795808). Проверены HTTP 200 и ожидаемый текст на [корне сайта](https://leonidyasin.github.io/mcp-server/), ROADMAP.html, docs/project-map.html, docs/binary-transfer-plan.html, docs/http-transport.html и docs/validation.html. [Evidence](https://github.com/LeonidYasin/mcp-server/pull/70#issuecomment-6200111705).

Исходно проверена ревизия 7. После guarded merge [PR #90](https://github.com/LeonidYasin/mcp-server/pull/90#issuecomment-6202906007) опубликована ревизия 8: CI+Pages 7/7 success, семь страниц HTTP 200 с текстом rev8. Кандидат ревизии 9 этим ещё не опубликован и не развёрнут в runtime. На странице карты найден Mermaid code block; визуальное отображение диаграммы на самом Pages ещё не принято. Локальная визуальная проверка не заменяет этот gate. Настройки Pages не менялись; Pages — статическая документация, не MCP runtime.

## Следующие gates

- **#88:** малый synthetic non-UTF-8/ZIP client→TEST probe passed; это feasibility через file-backed MCP arguments, не upload API. Добавлен opt-in [chunk/staging кандидат](file-uploads.md) без shell; synthetic XLSX покрыт unit/in-process tests. Отдельный временный upload TEST установлен на runtime `f39ee020324240833fb008f5c0fc19ad665bc9ca`, loopback3004, 119 tools (113 default + 6 upload; shell/local/Synapse OFF). Оператор подтвердил защищённый `/upload-test/mcp`, 401 без/с неверным key, старые pings и неизменность protected master PIDs/Caddyfile. Это runtime-конфигурация Caddy, не отсутствие её изменений. Первый маршрут удалён оператором ([cleanup evidence](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204369596)). Для file-backed ZIP gate оператор повторно открыл временный маршрут с новым state и новой попыткой cleanup через45 минут; второй маршрут тоже удалён оператором ([evidence](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204595072)). Для XLSX/count-quota gate открыт третий временный маршрут с новой45-минутной cleanup-попыткой; его удаление пока не подтверждено. Малый authenticated upload smoke через новое MCP-подключение прошёл: 50 bytes / два чанка, size/hash, retries, incomplete refusal и удаление записи. [Evidence и ограничения](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204289526). Позднее прошёл file-backed ZIP client-sandbox gate (110 124 bytes / 3 чанка, size/hash, cancel; [evidence](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204515365)). XLSX и live count quota 8/9 также PASS. Полная приёмка #88 (live cross-owner, byte/global quotas/expiry, retention) и ~41 МБ ещё pending; большой прогон — отдельно разрешённый. [Результат и ограничения](binary-transfer-plan.md#предварительная-feasibility--2026-10-15).
- **#89:** зависит от #88; согласовать release lookup/IDs с #64. Private Release assets, Actions dispatch и обратный bytes/hash E2E ещё не выполнены. [Статус #89](https://github.com/LeonidYasin/mcp-server/issues/89#issuecomment-6200184998).
- **#87:** отдельный artifact attempt identity gate остаётся pending; установленный TEST-кандидат не означает acceptance, merge или production deploy.
- **Docs/site:** после принятия документационного PR проверить опубликованную ревизию и визуальный Mermaid. После реализации API — реальные schemas/examples, без proposed tools в runtime inventory.

## Правила следующего rollout

Новый deployment — только по отдельному разрешению, на проверенный полный SHA, с preflight фактического unit/checkout/venv, backup, rollback и post-start localhost/external checks. Не выполнять blind pull/reset, не удалять незнакомые файлы и не включать shell в production ради upload. Системные обновления/reboot — отдельное окно обслуживания. Текущий документационный PR не запускает rollout, не сливает #87 и не закрывает #88/#89.
