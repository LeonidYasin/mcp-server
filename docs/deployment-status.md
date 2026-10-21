# Состояние deployment и проверок

Ревизия документации 9 · снимок на 2026-10-21. Это исторически закреплённое состояние, не обещание, что каждый будущий commit main уже развёрнут. [README](../README.md) · [Roadmap](../ROADMAP.md) · [Карта](project-map.md) · [Validation](validation.md) · [Файловый план](binary-transfer-plan.md).

## Production и TEST — отдельные состояния

| Окружение | Проверенная ревизия / профиль | Статус |
| --- | --- | --- |
| Production | `a0dc3286a05f774bdf321de05f695b7d4c755f61` (main после squash PR #119), detached HEAD, 114 tools | Rollout 2026-10-21 PASS, внешний MCP smoke passed; rooms, localfs/localgit, shell/process, Synapse выключены |
| TEST | `ef7993b87e8d6ed6598065e46203dc6145f9286d`, кандидат Draft PR #87, 119 tools | Shell/process включены только TEST; localfs/localgit/Synapse выключены. Специализированный authenticated deployed artifact gate pending |
| main после squash #119 | `a0dc3286a05f774bdf321de05f695b7d4c755f61` | CI main 3.10–3.13 success; будущие docs commits не меняют закреплённую production revision автоматически |

Production: `mcp-server.service`, Unix user/group `mcp`, checkout `/home/mcp/mcp-server`, venv `.venv`, Gunicorn, локальный порт 3001. TEST: `mcp-test.service`, user `mcp-test`, checkout `/home/mcp-test/mcp-server`, отдельный venv `/home/mcp-test/venv`, порт 3002; внешний путь `/test/mcp`.

## Rollout 2026-10-21 — PR #119

- Merge: PR #119 squash → `main` `a0dc3286a05f774bdf321de05f695b7d4c755f61` (parent `8c2aa3ac6972e680cd9df7af982e66731d21f2ce`), 51 файл, +15748/−9 — совпадает с PR. Исходные ветки `release/research-prod-candidate` и `feat/idea-analog-workflow` сохранены.
- CI: [run 39635233318](https://github.com/LeonidYasin/mcp-server/actions/runs/39635233318), Python 3.10–3.13 success; combined status 7/7 success.
- Операторский guarded root-скрипт (inline paste): preflight, флаги `ENABLE_AGENT_ROOMS/LOCAL_SHELL/LOCAL_TOOLS/SYNAPSE` выключены, зависимости не менялись, приватный backup, detached checkout точного SHA, import check, restart, health. Итог `RESULT=ROLLOUT_PASS old=8c2aa3ac… new=a0dc3286… pid=392628`, backup `/root/mcp-rollout-20261021-164229`. Откат не потребовался. TEST, Caddy, системные пакеты не затронуты.
- Внешняя проверка через production MCP: `list_my_tools` = **114**; `find_repository_analogs` зарегистрирован и выполнил bounded read-only поиск (2 запроса GitHub Search, 5 кандидатов, без записи); `search_repositories` с `mode=public`, `get_repo_info` с `mode=public_evidence`, `create_branch` с `from_sha`; ни одного `rooms_*` и ни одного из `run_command`, `run_python`, `start_background`, `stop_process`, `process_status`, `tail_log`.
- Отдельная TEST-приёмка этого точного SHA в production-профиле не выполнялась — решение владельца; компенсировано CI, неизменными зависимостями, автоматическим откатом и внешним smoke.

## Что реально выполнено (rollout 2026-10-15)

1. До rollout проверен точный HEAD PR #70 `602b6e9ffa8eb1f31d54db5610c56f9cc436e2ad` в отдельном checkout/venv под `mcp-test`: **640 pytest**, inventory **113/143**, 74 локальные ссылки, smoke import, wheel/sdist. [VPS evidence](https://github.com/LeonidYasin/mcp-server/pull/70#issuecomment-6200030171).
2. PR #70 squash merged; дерево reviewed HEAD и merge SHA одинаково. CI main: [run 38790796983](https://github.com/LeonidYasin/mcp-server/actions/runs/38790796983). Проверка кода не подменяет отдельную приёмку каждого backlog issue.
3. Пользователь запустил guarded root-скрипт: preflight service/user/path/old HEAD/target SHA/dependencies, приватный backup, переключение только production и автоматический rollback при ошибке. Git/import выполнялись от `mcp`, systemd orchestration — от root. Итог **ROLLOUT PASS**, откат не потребовался, новый process, 113 tools, зависимости не менялись. Незатреканный файл `To` оставлен на месте и скопирован в закрытый root backup; содержимое не публиковалось.
4. Независимые проверки после rollout: localhost health production/TEST; внешний production MCP `hash_text`; schema `merge_pull_request` требует `expected_head_sha`; target combined checks success (7), источник полон. Внешний smoke — ограниченная проверка доступности/схем, не исчерпывающий acceptance всех API. [Rollout и external evidence](https://github.com/LeonidYasin/mcp-server/pull/70#issuecomment-6202583914).

TEST, Caddy, system packages и VPS reboot **не затронуты**. `pip install`/обновление зависимостей не выполнялись. Старый production SHA: `dbefdad1ec84e723a95cb1219aa631557cd72ad4`. Реальный root backup сохраняется у оператора (`/root/mcp-rollout-<id>`); удалять его или `To` этой актуализацией не предлагается.

## Статическая документация / Pages

После merge #70 существующий workflow автоматически завершился успешно: [Pages run 38790795808](https://github.com/LeonidYasin/mcp-server/actions/runs/38790795808). Проверены HTTP 200 и ожидаемый текст на [корне сайта](https://leonidyasin.github.io/mcp-server/), ROADMAP.html, docs/project-map.html, docs/binary-transfer-plan.html, docs/http-transport.html и docs/validation.html. [Evidence](https://github.com/LeonidYasin/mcp-server/pull/70#issuecomment-6200111705).

Это проверка опубликованной **ревизии 7**, не будущих изменений ревизии 8. На странице карты найден Mermaid code block; визуальное отображение диаграммы на самом Pages ещё не принято. Локальная визуальная проверка не заменяет этот gate. Настройки Pages не менялись; Pages — статическая документация, не MCP runtime.

## Следующие gates

- **#88:** малый synthetic non-UTF-8/ZIP client→TEST probe passed; это feasibility через file-backed MCP arguments, не upload API. Выбор поддерживаемого transport без shell → scoped staging → integrity/isolation/quotas/TTL/cleanup → реальный client acceptance. XLSX и ~41 МБ ещё не проверены; большой прогон — отдельно разрешённый. [Результат и ограничения](binary-transfer-plan.md#предварительная-feasibility--2026-10-15).
- **#89:** зависит от #88; согласовать release lookup/IDs с #64. Private Release assets, Actions dispatch и обратный bytes/hash E2E ещё не выполнены. [Статус #89](https://github.com/LeonidYasin/mcp-server/issues/89#issuecomment-6200184998).
- **#87:** отдельный artifact attempt identity gate остаётся pending; установленный TEST-кандидат не означает acceptance, merge или production deploy.
- **Docs/site:** после принятия документационного PR проверить опубликованную ревизию и визуальный Mermaid. После реализации API — реальные schemas/examples, без proposed tools в runtime inventory.

## Правила следующего rollout

Новый deployment — только по отдельному разрешению, на проверенный полный SHA, с preflight фактического unit/checkout/venv, backup, rollback и post-start localhost/external checks. Не выполнять blind pull/reset, не удалять незнакомые файлы и не включать shell в production ради upload. Системные обновления/reboot — отдельное окно обслуживания. Текущий документационный PR не запускает rollout, не сливает #87 и не закрывает #88/#89.
