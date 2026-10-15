# ROADMAP — расширение MCP-сервера

Дорожная карта развития **mcp-server**. Цель — превратить сервер из GitHub-обёртки в универсальный «швейцарский нож» для агента.

> **Source of truth:** версия — `mcp_server/__init__.py` (dynamic version в `pyproject.toml`); список инструментов — рантайм `list_my_tools` + [`TOOLS.md`](TOOLS.md).
> **Ревизия документации: 9 · 2026-10-15** (см. README → Source of truth).

Легенда приоритетов:
- 🔴 высокий — блокирует базовые сценарии, делать первым
- 🟡 средний — ощутимо расширяет возможности
- 🟢 низкий — нишевое / требует осторожности

---

## Актуальный срез — 2026-10-15

Исходный triage: 19 issues (12 open / 7 closed). После него PR #70 слит в `main` как `b78b209cf5e8927c2c4bb9771d6ff0bafcad0cf6`; этот SHA отдельно развёрнут в production. Из предыдущих PR открыт Draft #87. Учтены новые комментарии #88/#89; оба issue остаются open. Предложения API ниже — **backlog**, не новые зарегистрированные инструменты. [Карта проекта](docs/project-map.md) и [подробный файловый план](docs/binary-transfer-plan.md) синхронизированы с этим срезом.

| Область | Текущий статус / следующий gate |
| --- | --- |
| #60, #61, #62, #63, #65, #67, #79 | Закрыты; соответствующие fixes в main, подробная история проверок ниже. Rollout закреплённого SHA подтверждён отдельно в [снимке окружений](docs/deployment-status.md); это не закрывает остальные acceptance gates. |
| #69 / #83 | Attempts, bounded logs, combined-step segmentation и diagnostic adapters в main через #81/#82/#84/#85. Оба issue ещё open; не закрывать по одному наличию кода. |
| PR #87 / #69 | Draft HEAD `ef7993b87e8d6ed6598065e46203dc6145f9286d`, CI 4/4 success. TEST checkout совпадает с HEAD; специализированный authenticated deployed gate artifact identity ещё pending. Нельзя выводить attempt по имени/времени/общему SHA. |
| #58 / #86 | Android/Kotlin диагностика и безопасный repo-specific auto-fix остаются open. Опасный template-to-main autofix отключён в main; замена не реализована. |
| #53 / #59 | Диагностика доступа и неопределённый post-effect persistence остаются open; не повторять потенциально успешную мутацию вслепую. |
| #64 | Lifecycle tags/releases остаётся open. Получение release IDs и asset API согласовать с #89, не делать два конкурирующих контракта. |
| **#88 → #89 — открыты** | Реальная передача bytes клиент → staging → приватный Release asset → Actions → проверяемый результат. Малый synthetic client→TEST probe прошёл; Добавлен opt-in кандидат chunk/staging API с verified owner/allowlist, quotas/TTL и integrity; deployed acceptance и #89 E2E ещё pending. [Контракт](docs/file-uploads.md). #89 зависит от #88. Приоритет P1 предлагается для нового пользовательского сценария, не означает реализацию. |
| #66 / #68 | Actions secrets и verified repo/Pages configuration остаются open. Никаких настоящих secrets или изменения Pages в этом docs PR. |
| #77 | Сквозной аудит всех методов: schemas + args + results + turns; отдельно измерить большой бинарный маршрут без base64 в контексте модели. |
| Production / TEST | Production `b78b209…`, 113 tools; TEST отдельно `ef7993b…`, 119 tools (shell/process только TEST). Зависимости, TEST и Caddy при rollout не менялись. [Подробности](docs/deployment-status.md). |
| Документация / сайт | PR #70 merged; Pages deployment success и HTTP 200 подтверждены. Mermaid в опубликованной странице визуально не принят. Ревизия 8 зафиксировала rollout/feasibility и опубликована после #90; ревизия 9 добавляет кандидат #88, не его live acceptance. #89 не реализован. |

### Ближайшие зависимости

1. Завершить отдельный live gate PR #87; merge только после review и явного согласования. #69/#83 закрываются только по полным критериям.
2. Для нового файлового сценария малый feasibility probe выполнен; выбран bounded MCP chunk transport и добавлен opt-in staging-кандидат; далее regression/native TEST и реальный клиентский acceptance нового API; только после этого #89. Объекты для mutating smoke tests и прогон ~41 МБ требуют отдельного разрешения.
3. #89 согласовать с #64 (release lookup/IDs/assets), #59 (неопределённый POST), #53 (доступ), #77 (token/memory budgets). Actions artifact, Release asset и staging `file_id` — разные сущности.
4. #58/#86, доступ, lifecycle, secrets и Pages сохраняются отдельными PR; будущие docs/site gates и deployments требуют отдельной проверки и разрешения. Уже выполненный rollout не означает принятия #87/#88/#89.

## План надёжности GitHub — 2026-10-11

Исходный triage: 2026-10-11. Актуальный срез после новых #88/#89 — в разделе выше; #56/#57 уже слиты. Это план разработки через небольшие PR, **не разрешение менять production, сливать PR, публиковать releases или менять настройки чужих репозиториев**. Предыдущие функциональные батчи ниже сохранены как долгосрочный backlog.

### Порядок реализации

| Шаг | Приоритет | Issue / область | Отдельный PR и критерий завершения |
| --- | --- | --- | --- |
| 1 | Быстрое исправление | [#65](https://github.com/LeonidYasin/mcp-server/issues/65) — compare bounds | Единый max_files для summary/patch; 0 допустим, неверные лимиты отклоняются до API; SHA снимка, total/returned/truncated, ограничения patch bytes/lines, честная неполнота upstream; three-dot документирован. |
| 2 | P0 — сохранность данных | [#60](https://github.com/LeonidYasin/mcp-server/issues/60) — batch push | Сохранение executable/symlink modes одним tree-read, whitelist явных modes, expected_head_sha и отказ при конкурентном изменении. Не обходить ограничения force-push. |
| 3 | P0 — честный статус | [#61](https://github.com/LeonidYasin/mcp-server/issues/61) — statuses + checks | Пагинация обоих источников; success/failure/pending/no_checks/unknown; cancelled/timed_out не success, пустые legacy statuses не pending сами по себе. Branch protection отдельно. |
| 4 | P0 — безопасный merge | [#62](https://github.com/LeonidYasin/mcp-server/issues/62) — PR preflight | Полные SHA/draft/mergeable metadata; expected_head_sha передаётся как sha; disallowed method и изменившийся HEAD завершаются без merge. Зависит от достоверного чтения checks, но не обещает protection eligibility. |
| 5 | P0 — ложный success | [#67](https://github.com/LeonidYasin/mcp-server/issues/67) — draft transitions | GraphQL ready/draft mutations, ошибки permissions/closed/merged, идемпотентность и read-after-write. Согласовать с #57, не дублировать его проверку required args. |
| 6 | P0 — скачивание | [#63](https://github.com/LeonidYasin/mcp-server/issues/63) — artifacts | Получать 302 Location на сервере; HTTPS/host validation; Authorization не уходит на CDN; signed URL не попадает в persistent logs. Проверять 401/403/expired. |
| 6a | Regression blocker | [#79](https://github.com/LeonidYasin/mcp-server/issues/79) — process exit race | Отдельный fix PR: ESRCH при чтении /proc и противоречивый double-read после zombie reap. Детерминированные regression tests + повторные native group checks под теми же TEST limits; не ослаблять identity guards, не смешивать с artifact implementation. Устранить до объявления полного VPS gate #78 зелёным. |
| 7a | P1 — Actions identity | [#69](https://github.com/LeonidYasin/mcp-server/issues/69) — run attempts | run_attempt и SHA/time metadata; attempt-specific endpoints/cache; точные artifact ID, duplicate names. Не смешивать старую и новую попытки. |
| 7b | P1 — Actions diagnostics | [#69](https://github.com/LeonidYasin/mcp-server/issues/69), [#58](https://github.com/LeonidYasin/mcp-server/issues/58) — logs / Android | Fixtures per-step и combined-job ZIP, границы job/step или явный unsupported fallback. Затем compiler errors Kotlin/Java/Rust выше warnings, failed run не success. |
| 8a | P1 — диагностика доступа | [#53](https://github.com/LeonidYasin/mcp-server/issues/53) — HTTP errors | 403 может означать permissions, policy или rate limit; 404 — not found либо скрытый доступ. Подсказки без утверждения единственной причины и без раскрытия токена; никаких скрытых fallback. |
| 8b | P1 — диагностика протокола | [#59](https://github.com/LeonidYasin/mcp-server/issues/59) — create_issue persistence | Разделить GitHub effect и сохранение истории клиента. В main уже есть _normalize_content: сначала regression tests и проверка причины; не объявлять labels виноватыми без репро и не делать автоматический повтор потенциально успешного POST. |
| 9 | P1 — lifecycle releases | [#64](https://github.com/LeonidYasin/mcp-server/issues/64) — tags/releases | Сначала atomic update_tag + expected_old_sha и explicit force; затем get/update release и согласованный с #89 контракт assets (одна реализация, не дубликаты). Stable tags не перезаписывать неявно; сохранить assets, без delete/create обхода permissions. |
| 10 | P2 — новые возможности | [#68](https://github.com/LeonidYasin/mcp-server/issues/68) — repo features / Pages | Сначала only-supplied has_issues/has_discussions + read-back; затем Pages GET/POST/PUT с проверкой branch/path и deployment status. Configured, deployed и HTTP verified — разные состояния. |
| 11 | P2 — secrets boundary | [#66](https://github.com/LeonidYasin/mcp-server/issues/66) — Actions secrets | Public key + metadata listing; encrypted_value/key_id mutation. Plaintext только через реальную secure-input capability; без неё только заранее зашифрованный payload. Delete — отдельно и явно; values читать невозможно. |
| 12 | Сквозной — performance | [#77](https://github.com/LeonidYasin/mcp-server/issues/77) — token efficiency audit | Аудит ВСЕХ registry/runtime методов и схем; end-to-end baseline (schemas+args+results+turns), компактные/fields/summary/full контракты, bounded batches и объединённые read-only snapshots. Отдельные экономичные аналоги только при измеренном выигрыше; safety/completeness не сокращать. Инвентаризация, benchmarks и небольшие PR до финальной синхронизации docs/site. |
| 13 | P1 — binary ingress, новый план | [#88](https://github.com/LeonidYasin/mcp-server/issues/88) — клиент → staging | Сначала доказать доступный клиентский transport (stream upload ticket ИЛИ bounded chunks), не server-local path. Bytes/size/SHA-256 → scoped opaque file_id; quotas/TTL/cleanup/offset+idempotency и no traversal/symlink/SSRF. Реальный client→server ZIP/XLSX/non-UTF-8 gate, отдельно разрешённый synthetic ~41 МБ. |
| 14 | P1 — end-to-end files, зависит от 13 | [#89](https://github.com/LeonidYasin/mcp-server/issues/89) — Release assets → Actions | Согласовать с #64: release lookup/IDs, paginated assets, streaming upload из проверенного file_id, authenticated download в staging, size/hash verification. Name conflict явный; timeout POST → reconcile, не blind retry. Разрешённый private-release smoke ZIP → Actions → output artifact → bytes/size/hash read-back. |

P0 — приоритет по риску; шаг 1 выбран как маленькое изолированное исправление для запуска PR-процесса. Шаги 7a/7b и 8a/8b намеренно разделены, чтобы не объединять несколько независимых подсистем в один PR.

### Исторически пересекавшиеся PR (уже слиты)

- [#57](https://github.com/LeonidYasin/mcp-server/pull/57): required args в update_pull_request. Нужны regression tests и актуальный CI; не заменяет #67 и #62.
- [#56](https://github.com/LeonidYasin/mcp-server/pull/56): background process manager. Отдельный security review: PID reuse, process-group ownership, cwd/env, logs и восстановление bookkeeping. Не дублировать ветку; не считать безопасность доказанной описанием PR.

### Gate для каждого шага

1. Прочитать issue, комментарии, актуальный код и пересекающиеся PR.
2. Отдельная feature/fix ветка от актуального main; regression test сначала, затем минимальное изменение и schema/docs в том же PR.
3. Локально весь pytest + smoke import; CI Python 3.10–3.13 и wheel build. В PR различать фактически выполненные проверки и запланированные.
4. Проверка tool schema/runtime discovery; negative cases, bounds, redaction, no incidental mutation. Mocked тесты не заменяют live-тесты.
5. Изменяющий GitHub integration test — только на явно разрешённом disposable объекте, без настоящих секретов и production deployment. Если не выполнен, явно указать это.
6. Ревью и зелёный CI до merge; issue закрывается только после merge и выполнения критериев. Невыполненные части — явные follow-ups, не ложный «готово».

### Финальная синхронизация документации и сайта

PR #70 слит: добавлены карта проекта и файловый план, проверены 640 pytest, inventory 113/143 и сборка. После merge отдельно подтверждены Pages deployment/HTTP и production rollout. Ревизия 8 фиксирует эти результаты в [снимке окружений](docs/deployment-status.md). Это не приёмка будущего файлового API; Mermaid на Pages и реальные examples после реализации остаются отдельными gates.

После согласованного этапа кодовых исправлений — отдельный documentation/site PR:

- README, TOOLS, SANDBOX, инструкции запуска и тестирования, примеры вызовов и schema contracts сверить с кодом, runtime discovery и feature flags. Обновить версии/счётчики без неподтверждённых чисел.
- ROADMAP актуализировать по merged PR и фактически закрытым acceptance criteria; оставшиеся issues не выдавать за выполненные.
- Майндмэп: найти существующий источник; если его нет, добавить версионируемый источник в репозиторий. Разделить архитектуру, инструменты, безопасность и этапы развития; согласовать его с ROADMAP.
- GitHub Pages: сначала проверить текущую конфигурацию/источник сайта. Подготовить согласованную документацию, проверить относительные ссылки, сборку и отсутствие секретов; настроить deployment только с нужными правами, без обхода ограничений.
- Проверить реальный deployment URL, commit/status и опубликованное HTTP-содержимое. «Файлы загружены» не означает «сайт опубликован». GitHub Pages — статическая документация, не хостинг MCP runtime.
- Не публиковать токены, Caddy secrets, приватные данные и неподтверждённые результаты; создать redacted примеры production/test конфигураций.
- Финальный review: ссылки, примеры, установка с чистого окружения, матрица CI и отметки live/mock проверки. Отдельно согласовать rollout боевого сервера и rollback.

Это финальный gate выбранного этапа, а не обещание закрыть весь backlog одним PR.

Дополнительный запрос пользователя: [#77](https://github.com/LeonidYasin/mcp-server/issues/77) — аудит всех методов на экономию токенов. Аудит можно вести параллельно reliability fixes; экономию внедрять по измерениям, учитывать в финальных schemas/TOOLS/README/экономичных recipes/mindmap/Pages, не ценой защит и фактов.

### Кандидат #88 — реализация отдельно от rollout

- Выбран bounded MCP chunk transport; шесть opt-in tools, default OFF, отдельный private root и explicit GitHub-user allowlist. Никакого shell, произвольного server path или URL-fetch.
- Auth на каждом вызове через `/user`, SQLite transactional chunks/progress, idempotent begin/chunk/finish, verified opaque file_id, quotas/TTL/cleanup; [полный контракт](docs/file-uploads.md).
- Unit/in-process Flask tests включают synthetic ZIP/XLSX/non-UTF-8; это не live deployed acceptance. #88 остаётся open до точного TEST/client gate и отдельно разрешённого ~41 МБ прогона. #89 implementation/E2E отдельно.

### Завершено после документационного аудита — 2026-10-15

- [x] PR #70: reviewed HEAD `602b6e9ffa8eb1f31d54db5610c56f9cc436e2ad`; VPS под `mcp-test`: 640 pytest, smoke import, wheel/sdist. Squash merge в `b78b209cf5e8927c2c4bb9771d6ff0bafcad0cf6`; CI success.
- [x] Production rollout этого SHA с guarded preflight и механизмом rollback (откат не потребовался); localhost и внешний MCP smoke passed. TEST, Caddy, зависимости и reboot не затронуты. [Evidence](https://github.com/LeonidYasin/mcp-server/pull/70#issuecomment-6202583914).
- [x] Существующий Pages workflow автоматически отработал после merge #70; root/roadmap/map/plan/HTTP/validation HTTP 200. [Evidence](https://github.com/LeonidYasin/mcp-server/pull/70#issuecomment-6200111705).
- [x] #88: малый synthetic non-UTF-8/ZIP client→TEST probe, size/SHA-256 совпали. [Evidence и ограничения](docs/binary-transfer-plan.md#предварительная-feasibility--2026-10-15).
- [ ] #88: принять opt-in chunk/staging кандидат (synthetic XLSX теперь покрыт unit/HTTP tests), выполнить deployed real-client и отдельно разрешённый ~41 МБ gate; затем #89 private-release/Actions E2E.
- [ ] PR #87 authenticated deployed artifact gate; визуальная проверка Mermaid на опубликованном Pages.

### Статус выполнения — исторический журнал

Записи ниже фиксируют проверки и ограничения **на момент каждого PR**. Старые формулировки pending/unsupported не переопределяют актуальный срез выше: wrappers уже мигрированы #85, artifact candidate #87 ещё не принят.

- [x] Выполнен triage открытых issues и учтены #56/#57.
- [x] PR #57 слит: `5b7c2dd74715bdef32834102d423726bc2eac8a9`; 50 pytest + 28 live HTTP negative checks на тестовом VPS, CI Python 3.10–3.13 success. Production не обновлён.
- [x] Шаг 1 / #65: [PR #71](https://github.com/LeonidYasin/mcp-server/pull/71) слит: `ccd1c6fb475c86dc9630d0b06cbf6527b721e150`; issue #65 закрыт. 92 pytest на VPS, live TEST MCP limits/patch/identical-SHA checks и CI Python 3.10–3.13 success. Production не обновлён.
- [x] PR #56 слит: `85b3b5091864f26bc329cbc4f3ecf39ee068a579`; 150 pytest на VPS, remote TEST MCP TERM/KILL/status/log/metadata checks и systemd control-group restart cleanup passed. Linux identity/no-follow/limits и ограничения документированы. Production не обновлён, shell в production не включён.
- [x] Шаг 2 / #60: [PR #72](https://github.com/LeonidYasin/mcp-server/pull/72) слит: `1dfd6ba98065ca8cc15261bb243b9a443e951641`; issue #60 закрыт. 206 pytest на VPS + native bare-Git fixture, live GitHub сохранение executable/symlink modes и stale-HEAD conflict на разрешённой отдельной test branch; CI Python 3.10–3.13 success. Production не обновлён.
- [x] Шаг 3 / #61: [PR #73](https://github.com/LeonidYasin/mcp-server/pull/73) слит: `21bbafc89b0f08df717e12682318ff303634eef7`; issue #61 закрыт. 270 pytest на VPS, wheel/sdist build и CI Python 3.10–3.13 success; deployed TEST schema + live GitHub success/no_checks/output-cap/unknown checks passed. Production не обновлён.
- [x] Шаг 4 / #62: [PR #74](https://github.com/LeonidYasin/mcp-server/pull/74) слит новым guarded TEST tool: `310e2f6110b116ddf2fddde27ba1af2b0d470f9b`; issue #62 закрыт. 333 pytest на VPS, builds и CI Python 3.10–3.13 success; deployed TEST schema/method discovery/stale guard/invalid method/already-merged checks passed, затем отдельно разрешённый живой squash merge с проверенным HEAD подтверждён. Production не обновлён.
- [x] Шаг 5 / #67: [PR #75](https://github.com/LeonidYasin/mcp-server/pull/75) слит guarded TEST tool: `74b86d2349a4caa86508cc064fa1bf9a40af5bed`; issue #67 закрыт. 390 pytest на VPS, builds и CI Python 3.10–3.13 success; оба живых GraphQL перехода с no-op повторами и независимым свежим REST read-back прошли на отдельно разрешённом #76. Title/body/head/base не изменились; #76 закрыт без merge, временная ветка удалена. Production не обновлён.
- [x] Шаг 6 / #63: [PR #78](https://github.com/LeonidYasin/mcp-server/pull/78) слит guarded TEST tool после разрешения пользователя, merge commit `050423603a0a061984254b8ae2380e081767e081`, exact reviewed synced HEAD `4bcbc37a61650c2947b2987a3fb972a920d86bda`: настоящий API 302 download URL, streaming headers-only/no follow/no CDN auth, bounded exact-name/run lookup и honest ambiguity/errors. После отдельного process-fix #80 весь VPS pytest прошёл дважды (464 passed, 10.41s / 10.39s), CI Python 3.10–3.13 success. Deployed TEST schema/negative gate + живое authenticated разрешение по artifact_id и name/run прошли; independent consumer без PAT скачал 260606 bytes, HTTP 200, valid ZIP без extraction/execution. Opaque signed URLs не опубликованы в GitHub. Первоначальные failures и fix сохранены в #79/комментариях #78. Issue #63 независимо прочитан как closed/completed; production не обновлён.
- [x] #79: [PR #80](https://github.com/LeonidYasin/mcp-server/pull/80) слит guarded TEST tool: `655df5a253cc6f0eb21f3795ce2e97fd07727b3c`; issue #79 закрыт. 13 deterministic regressions, 403 pytest дважды на VPS, 10 последовательных повторов двух native TERM/KILL cases (20 checks), builds/CI Python 3.10–3.13 success. Identity/signals/limits не ослаблены. #78 обновлён до `4bcbc37a61650c2947b2987a3fb972a920d86bda`, tree `f2601c8083318fc5198ff47676beafedc72170a3` совпадает с ранее проверенной локальной интеграцией; exact remote HEAD и deployed artifact gate проверяются отдельно. Production не обновлён.
- [x] Шаг 7a (snapshot part only) / #69: [PR #81](https://github.com/LeonidYasin/mcp-server/pull/81), separate branch `fix/workflow-attempt-snapshots-69`, exact HEAD `196d3209c80f5d602bef484b519563c1ca3ec2cb`. Attempt-pinned status/steps snapshots, identity validation, bounded pagination/output; list/latest expose attempt/time. 510 pytest locally и на VPS under mcp-test (11.62s); CI Python 3.10–3.13 success. Live read-only public TunXBox run 38102759021: attempts 1/2, latest pinned to 2, SHA identity и 40 steps per attempt passed. Слит после разрешения пользователя guarded TEST tool, merge commit `bd086bcb43ee8f9391f3a42319661af2f2871fc4`: deployed TEST schemas + authenticated MCP attempts 1/2 (distinct job IDs/timestamps), latest=2, capped failure-first output, zero caps, invalid bounds and nonexistent attempt refusal passed; pytest directly in deployed repo under mcp-test 510 passed (11.67s); issue #69 не закрывается, logs/combined-step/artifact attribution отдельно в part 2. Кэша workflow logs сейчас нет; future cache identity документирован, не реализован. Production не обновлён.
- [x] Шаг 7b / #69 primary log readers (intermediate part only): [PR #82](https://github.com/LeonidYasin/mcp-server/pull/82), new branch `fix/workflow-attempt-logs-69`, слит после явного разрешения guarded TEST tool: merge commit `17005838a7b827e99dd9193722aad86e12e064bc`, exact reviewed HEAD `257776b4ff0ce381e5fc1807d655e092ea1323a1`. Four primary readers pin run_attempt and exact logs endpoint, bounded ZIP/no CDN auth/no redirects; combined step filter explicitly unsupported with same-attempt bounded job-search suggestion (not guessed boundaries). Structured response migration documented. Local 572 pytest, VPS candidate under mcp-test 572 in 22.80s; Deployed TEST 572 pytest in 23.92s; CI Python 3.10–3.13 success. Real authenticated ZIPs TunXBox run 38102759021 attempts 1/2: 5917 vs 2768 selected lines and own timestamps; both current archives combined, step filter explicitly unsupported, bounded job grep labels step=null (not step-specific). Latest=2 offset cap, no-text/no-files distinction and invalid/nonexistent attempts passed; runtime schemas checked. Per-step behavior fixture-covered, not claimed live on this run. Legacy diagnostics/full/preview/checks and artifact attempt attribution remain pending, issue #69 open, production unchanged.
- [x] Primary combined-step continuation #69 / [#83](https://github.com/LeonidYasin/mcp-server/issues/83): убрать временный `step_filter_unsupported` для поддерживаемых completed combined ZIP. Проверяемая сегментация markers/timeline + attempt/SHA/job_id/step identity, no cross-step context; fixture/live TEST 4KB vs 16KB attempts1/2, same-name jobs, nested/repeated groups и ambiguous timestamps. Unsupported/unknown допустим только для конкретных недоказуемых случаев, не вечная реализация. Реализация [PR #84](https://github.com/LeonidYasin/mcp-server/pull/84), отдельная ветка `fix/combined-step-boundaries-83`, слит guarded TEST tool после разрешения: merge `73fe03fb3bb163df2a0a0b902b14326a2eb5132a`, reviewed HEAD `3ac49de7e404d1e36cb8d62f6b22e13eeb8ccc51` (initial `f510e7a...` live gate failed: both attempts unsupported from ordinary multiline input continuations outside target; failure recorded in #84). Fix allows those outside proven windows, still refuses untimestamped target content/control markers; +2 regressions, local605/VPS candidate605 (23.79s) passed; corrected deployed live re-test PASSED: exact repo605pytest/26.02s, CI3.10–3.13 success; real TunXBox step22 attempts1/2 combined_step lines4974–5768 (795)/1688–2621 (934) match independent broad markers+API times. Neighbor regex0 selected hits vs359/363 broad controls; head/tail/offset/context20/alias/latest2/source-lines/caps passed; production unchanged: проверенный non-overlap completed timeline + unique top-level runner Run markers, исходные номера строк, контекст внутри шага, отдельные identities same-file steps, mixed-copy deduplication. Local603/VPS candidate603 (25.68s) прошли; Первый live gate603 failed и сохранён в истории; после fix605 corrected deployed gate passed. Issue #83/69 не закрываются автоматически: legacy wrappers/artifact attribution остаются pending; primary segmentation PR #84 merged; production unchanged. До этого #69/финальные docs/mindmap/Pages не объявляются завершёнными; legacy wrappers/artifact attribution также pending.
- [x] Diagnostic wrappers continuation / #69/#83: [PR #85](https://github.com/LeonidYasin/mcp-server/pull/85), branch `fix/workflow-diagnostic-attempts-69`, слит guarded TEST tool после разрешения: merge `b9787e4f40fe8b62f62dbafa632b60722e44f439`, reviewed HEAD `c52e7f11c640904de20a692828bc865b8163252c`. Latest/watch/run/full/preview/checks names and canonical Android/iOS diagnostics use bounded attempt readers; unique exact-job identity recheck, no empty/no-match-as-success. Old SDK transports fail closed. Unsafe hardcoded autofix-to-main disabled in candidate (not deployed production); mandatory safe replacement [#86](https://github.com/LeonidYasin/mcp-server/issues/86) separately tracked. Local634 / VPS candidate634 (27.17s), CI3.10–3.13 success; Deployed gate passed: exact repo634pytest/28.86s; runtime all9 definitions; authenticated full/preview/Android old/new step windows/caps, no-match run failure, watch snapshot, checks deprecated attempt-log source, iOS missing job, latest CI metadata and verified disabled autofix writes=false. No real iOS build/root-cause diagnosis claimed. Registered code no longer uses old SDK transports; production still unchanged, #86 replacement/artifact attribution/#58 pending. No unsafe autofix executed, production untouched.
- [ ] Artifact attempt identity / #69: [PR #87](https://github.com/LeonidYasin/mcp-server/pull/87), branch `fix/artifact-attempt-identity-69`, draft HEAD `ef7993b87e8d6ed6598065e46203dc6145f9286d`. Run-context separately from artifact attempt-or-unknown; bounded IDs/SHA/time/digest/duplicates listing; explicit attempt unknown candidates separate, strict download refuses before redirect, ID-only legacy resolution preserves unknown. No timestamp/name/latest/SHA inference or invented attempt-artifacts endpoint. Local666 / VPS candidate666 (27.99s), CI3.10–3.13 success. Real public TunXBox attempt1/2 source gate:6 rows/3 duplicate names,6 unknown, strict ID11690225979 refuses and0 redirect calls; positive API-attempt metadata fixture-covered only. TEST checkout при подключении проверен на exact HEAD, CI 4/4 success; это только read-only connectivity/identity check. Deployed authenticated artifact acceptance gate pending. Producer attribution protocol would require separate review, no TunXBox workflow/production changes.
- [ ] Новые #88/#89: полные требования и зависимости внесены в roadmap/карту/README/TOOLS/SANDBOX; реализация и сквозные проверки не выполнены.
- [ ] Остальная часть шага 7b / #58 и шаги 8–14: запланированы, не реализованы этим обновлением.
- [x] Промежуточный docs audit #70: README/TOOLS/SANDBOX и карта сверены с кодом; пропуски каталога, bind/session claims и isolation overclaims исправлены. Добавлены offline registry/link/HTTP checks, versioned inventory и source-distribution inputs. Это не реализация открытых issues.
- [ ] Финальная синхронизация после будущих code PR, live examples и GitHub Pages: опубликованный сайт ещё не проверен.

---

## Экосистема проектов (карта)

Техническая архитектура, границы доверия и планируемый файловый маршрут: [версионируемая карта проекта](docs/project-map.md). Экосистемная таблица ниже описывает отдельные проекты, не готовую бинарную интеграцию между ними.

У автора несколько связанных репозиториев вокруг одной идеи: **находимость и обмен через ИИ-агента**.

| Репозиторий | Домен | Стек | Роль |
|-------------|-------|------|------|
| **NoKing** | Обмен ценностями, DAO | HTML+JS → Solidity/IPFS | Протокол-фундамент |
| **Civis** | Люди по ценностям + маркетплейс | Python, SQLite, Telegram | Первый рабочий матчинг |
| **synapse** (старый) | Соцсеть на ИИ-чатах | концепция | Идейный предок |
| **synapse2** | ИИ-платформа поиска связей | FastAPI, DeepSeek | Веб-версия |
| **agora-mcp** | offers/wants, сетевой | TypeScript, Postgres+pgvector | Сетевой протокол |
| **mcp-server** | GitHub/MCP-инструменты + Synapse | Python, Flask | MCP-интерфейс |

**Стратегия (вариант A):** не сливать репозитории, а унифицировать протокол. Общая спека `synapse-protocol` — JSON-схема для item (offer/want), profile, contact, exchange. На неё ссылаются и Synapse, и Agora, и NoKing.

---

## Текущее состояние

Точный набор зарегистрированных инструментов зависит от feature flags и проверяется `list_my_tools` на выбранной сборке; старые статические счётчики не подтверждают runtime-каталог. Реализовано (смержено в `main`):

- **Батч 1** — PR / Issues / Releases / Tags / batch-push, meta (`list_my_tools`, `describe_tool`), web (`web_fetch`, `web_search`), утилиты (base64/hash/json/uuid/date/regex/diff).
- **Батч 2** — branches, gists, Actions control, security alerts, repo info.
- **Батч 3** — web (`rss_read`, `html_to_markdown`), данные (`csv_*`, `yaml/json` конвертеры, `markdown_to_html`), commits (`get_commit_diff`, `list_directory`, `get_file_blame`).
- **Батч 4** — sandboxed local filesystem (`localfs/`, 4 инструмента). По умолчанию **выключено** (`ENABLE_LOCAL_TOOLS=1`). См. `SANDBOX.md`.
- **Батч 5** — sandboxed local git (`localgit/`, 6 инструментов). Тот же флаг.
- **Батч 6** — sandboxed shell / python (`shell/`, `run_command`, `run_python`). Флаг `ENABLE_LOCAL_SHELL=1`.
- **Батч 7a** — каркас Synapse без эмбеддингов: `publish_profile`, `search_people` (keyword-MVP), `propose_contact`, `save_note`, `search_notes`, `index_github`. Флаг `ENABLE_SYNAPSE=1`, данные в `SYNAPSE_DATA_DIR`.
- **Repo admin** — `update_repo_info`; плюс `move_file`, `read_multiple_files`, `get_repo_tree`, `read_run_logs_offset`, review-threads (resolve/unresolve), search-* и др. — см. [`TOOLS.md`](TOOLS.md).

---

## Единый sandbox-пул инструментов

Батчи 4–6 готовы: localfs + git + shell объединяются в **один изолированный workspace**:

- один `LOCAL_TOOLS_ROOT` (= `/workspace`) — общий whitelist;
- раздельные флаги `ENABLE_LOCAL_TOOLS` (fs + git) и `ENABLE_LOCAL_SHELL` (shell);
- всё выполняется под одним `mcp-sandbox` (Linux) / внутри WSL2 без automount;
- cwd shell и расположение local-git repo ограничены `LOCAL_TOOLS_ROOT`; исполняемый shell/Python имеет все OS-права пользователя и не заперт этим cwd. Для OS-изоляции нужна отдельная policy.

Дальнейшее усиление — bwrap/Docker (уровни 2–3 в `SANDBOX.md`).

---

## Батч 7b — Synapse item/matching (код в main, provider gate отдельно)

> Статус: 8 item/matching tools уже регистрируются вместе с 6 базовыми при `ENABLE_SYNAPSE=1` (14 всего). Это проверено локальным discovery и [inventory](docs/tool-inventory.json), без вызова provider/реального matching. Embeddings/provider availability и качество — отдельные gates; без provider используется keyword fallback.

### Ключевой архитектурный урок (из agora-mcp)

**Item-модель, а не user-модель.** Одна эмбеддинг на **item** (offer | want), а не на пользователя. Матчинг **асимметричный**: offer ↔ чужие want.

**Instruction-aware эмбеддинги.** Разные префиксы для offer- и want-роли. Multilingual (RU+EN): BGE-M3 / multilingual-e5-large.

**Hybrid search.** Vector + structured filters (category, tags, geography).

**Freshness.** Items имеют `updated_at` и `active`; stale offers decay out.

**Outcome feedback.** Capturing (состоялся ли обмен) — задел для behavioral ranking.

### Выбор модели эмбеддингов — три опции

| Опция | Как работает | Плюсы | Минусы | Когда выбирать |
|-------|--------------|-------|--------|----------------|
| **A. OpenAI `text-embedding-3-small`** | облачные эмбеддинги (`OPENAI_API_KEY`) | лучшее качество, 1536 dim | платно, данные уходят в OpenAI | нужен максимум качества |
| **B. Локальная `sentence-transformers`** | модель локально (`all-MiniLM-L6-v2`, 384 dim) | бесплатно, приватно, офлайн | CPU/GPU, качество ниже | приоритет приватности |
| **C. Ollama `nomic-embed-text`** | локальный Ollama (`localhost:11434`) | бесплатно, легко менять модели | держать Ollama запущенным | уже используешь Ollama |

### Конфигурация (env)

```bash
export SYNAPSE_EMBEDDING_PROVIDER=ollama   # выбрать ОДИН: openai, local или ollama; без значения keyword fallback

# A
OPENAI_API_KEY=...
SYNAPSE_EMBEDDING_MODEL=text-embedding-3-small
# B
SYNAPSE_EMBEDDING_MODEL=all-MiniLM-L6-v2
# C
SYNAPSE_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

### Код батча 7b (наличие не означает acceptance качества)

- Векторное хранилище: SQLite + numpy.
- Item-модель: `submit_offer`, `submit_want`, `list_my_items`, `deactivate_item`.
- `model_me(text)`, `find_my_match(query, limit)`.
- `draft_profile_from_dialog`.
- `search_people`/`search_notes` → эмбеддинги при заданном провайдере, иначе keyword-MVP (graceful fallback).
- Freshness: `updated_at` + `active` + decay.
- Outcome feedback: `report_match_outcome`.

---

## Батч 20 — Token economy (экономия токенов, план)

**Зачем:** ИИ-агенту легче работать, когда «дешёвые» по токенам вызовы отдают короткий ответ. Сейчас часть инструментов возвращает «простыни» (полные файлы, полные логи, длинные списки) — это дорого по контексту.

> **Принцип: не дублировать весь каталог.** Массовые `*_slim` раздуют `tools/list` и запутают выбор. Предпочитать измеренные format/fields/snapshot контракты; отдельные экономичные аналоги — только при подтверждённой выгоде (#77). Дефолты и миграцию определять для каждого существующего контракта, не обещать несуществующий общий `full`.

### Что сделать

1. **`format: "full" | "compact"`** для «дорогих» list-методов:
   - `list_commits`, `list_branches`, `list_pull_requests`, `list_issues`, `list_releases`, `list_tags`, `list_workflow_runs`, `list_repo_contributors`.
   - `compact` → одна строка на элемент (`id | date | title`), без вложенных объектов.
2. **Подсказки в `description`** «дорогих» методов (`read_full_file`, `get_file_contents`, `get_full_workflow_logs`, `get_workflow_run_logs`): явно писать «для больших файлов/логов предпочитай `grep_file` / `read_file_chunk` / `grep_workflow_logs`».
3. **`fields=` (опционально)** — вернуть только запрошенные поля у list-методов.

### Как делать осторожно (не сломать)

- Дефолт остаётся `full` → существующие вызовы не меняются.
- `compact` — **новый** код-путь; покрыть быстрым тестом (smoke: `format=compact` возвращает строки, `format=full` — как раньше).
- Менять **по одному методу за PR**, после каждого — проверка, что `full` не сломан.
- Проверка после правки: `describe_tool(name)` показывает новый параметр; вызов с `format=compact` и без него даёт ожидаемое.

### Метрика

- До/после: размер ответа (байты) на типовом вызове `list_commits(format=compact)` vs `full`.
- Цель: −70…90% на листингах при сохранении `full` по запросу.

---

## Батч 8 — Авторизация и безопасность для публичного IP

⚠️ **Критично до любого публичного развёртывания.** В текущем `main` сервер по умолчанию слушает `127.0.0.1:3001` (можно явно переопределить `MCP_HOST`), не проверяет отдельный собственный токен, CORS открыт. Loopback не заменяет аутентификацию при публикации через reverse proxy.

Это **предложения**, не реализованные environment flags. Не подменять GitHub PAT другим Bearer в текущем сервере. Сейчас доступ защищает reverse proxy (`X-API-Key` в примере README).

1. **Отдельная MCP authentication policy** — выбрать и реализовать отдельно от GitHub token gate, с миграцией клиентов.
2. **Разделить credentials:** отдельный MCP access credential, а `Authorization: Bearer <github_token>` сохранить для GitHub до явно согласованного изменения протокола.
3. **CORS white-list** — вместо `CORS(app)`.
4. **Rate limit** — счётчик на IP + окно.
5. **TLS** — reverse-proxy (nginx / caddy) или Cloudflare Tunnel.
