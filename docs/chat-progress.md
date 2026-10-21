# Прогресс чата: доказательства, исходники и незавершённые gates

Назначение — не дамп переписки, а навигация без повторной реализации. Текущая
основа docs-ветки main `8c2aa3ac6972e680cd9df7af982e66731d21f2ce`; ниже независимые exact-SHA candidates, не merged
runtime. Существующие исторические документы не переписываются задним числом.
Ссылки на ветки/PR могут изменяться; ссылки blob/full SHA закрепляют источник.
[Handoff](ai-handoff.md) · [state](work-state.json) · [AGENTS](../AGENTS.md).

## 1. GitHub, Actions, transport и безопасность

В main уже сохранены: [transport](http-transport.md), [validation](validation.md),
[инвентарь](tool-inventory.json), [batch CAS/modes](batch-push.md),
[commit statuses](commit-status.md), [guarded PR](pr-preflight.md),
[draft/read-back](pr-draft.md), [create branch](create-branch.md),
[compare bounds](compare-branches.md), [attempt snapshots](workflow-attempts.md),
[attempt readers](workflow-attempt-logs.md), [step boundaries](workflow-step-boundaries.md),
[diagnostic adapters](workflow-diagnostic-adapters.md), [process identity/races](process-manager.md),
[artifact resolver](artifact-download.md), [safe workflow skill](skills/github-mcp-safe-workflow/SKILL.md).
Все имеют source/tests в repo. Общая codebase не равна приёмке всех backlog issues.
#87 остаётся open: attempt-or-unknown, identity не выводить из имени/времени/SHA.
Диагностика не должна объявлять success по отсутствию error lines; unsafe auto-fix
на main отключён. Permission refusal не обходить сменой аккаунта/выключением guards.

## 2. Binary #88 → #89 (PR #91, #114)

Source/docs candidate `4edf84e3c67809122ec41d6b3de98970bb840f34`:
[API](https://github.com/LeonidYasin/mcp-server/blob/4edf84e3c67809122ec41d6b3de98970bb840f34/docs/file-uploads.md),
[acceptance](https://github.com/LeonidYasin/mcp-server/blob/4edf84e3c67809122ec41d6b3de98970bb840f34/docs/upload-acceptance.md),
[loopback](https://github.com/LeonidYasin/mcp-server/blob/4edf84e3c67809122ec41d6b3de98970bb840f34/docs/upload-test-deployment.md),
[proxy](https://github.com/LeonidYasin/mcp-server/blob/4edf84e3c67809122ec41d6b3de98970bb840f34/docs/upload-test-proxy.md).
Исторический установленный runtime `f39ee020324240833fb008f5c0fc19ad665bc9ca`.

Подтверждено: малый authenticated upload50bytes/2chunks, retry/incomplete refusal/
stable opaque file_id/cancel; клиентский ZIP110124bytes/3chunks; synthetic XLSX5300bytes,
client-side reopen/typed values/ZIP audit + server finish size/SHA256; count quota8,
девятый rejected и после cancel принят. XLSX hash
`df51352f21fb6c7c47a01dcc8741b0c35575a52dca2345aedf7507c987d5f3e1`.
Это не серверное чтение spreadsheet и не обратный download. Ещё не закрыты:
cross-owner, live byte/global quotas/expiry, host history retention, ~41MiB/resource
probe и private Release→Actions→output verified bytes E2E.

В исходном acceptance третье temporary-route cleanup было pending. Позднее в
этом чате оператор сообщил `UPLOAD ROUTE CLEANUP state=removed` для XLSX окна.
Это **operator report**, не новый live probe; не доказывает остановку loopback,
отзыв credentials, удаление connector или всех будущих маршрутов.
PR #114 `feat/release-readonly-64-89` — отдельный read-only release lookup/assets
candidate; не выдавать за complete upload/download/Actions #89.

Публичные helper исходники:
[prepare_file_upload.py](https://github.com/LeonidYasin/mcp-server/blob/4edf84e3c67809122ec41d6b3de98970bb840f34/scripts/prepare_file_upload.py),
[deploy_upload_test.py](https://github.com/LeonidYasin/mcp-server/blob/4edf84e3c67809122ec41d6b3de98970bb840f34/scripts/deploy_upload_test.py),
[upload_test_proxy.py](https://github.com/LeonidYasin/mcp-server/blob/4edf84e3c67809122ec41d6b3de98970bb840f34/scripts/upload_test_proxy.py).
Это archive/runbook, НЕ команда повторного запуска: старые source/current SHA,
пути/порты/таймеры и systemd assumptions требуют нового review/preflight.

## 3. Research / коммерческие идеи / аналоги репозиториев

Основная product-задача сервера, не отвлекаться от неё только на инфраструктуру.
Open цепочка: #108 author analytics (#99), #109 priority CI/research scenarios,
#110 search observations (#100), #111 public evidence, #112 idea analog composition;
#107 read-only discoverability (#103). #101/web research, #102 composition,
#104 preview/catalog и #105 real pilot остаются отдельными целями/approval gates,
не автоматически закрыты наличием GitHub Search.

Source/docs aggregate research candidate `10aa6909b2e945b42dd48740bad5ef1f0056301e`:
[контракт analog workflow](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/docs/repository-analogs.md),
[search observations](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/docs/repository-search-observations.md),
[pinned evidence](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/docs/repository-evidence.md),
[external acceptance](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/docs/idea-analog-external-acceptance.md),
[quality audit](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/docs/scenarios/analog-quality-audit.md),
[reviewed cases JSON](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/docs/examples/repository-analog-reviewed-cases.json),
[Agora MCP-only research](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/docs/scenarios/agora-mcp-only-research.md),
[commerce follow-up](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/docs/scenarios/agora-commerce-followup.md),
[rollout archive](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/docs/test-pr112-rollout.md),
[operator helper](https://github.com/LeonidYasin/mcp-server/blob/10aa6909b2e945b42dd48740bad5ef1f0056301e/scripts/deploy_test_pr112.py).
Не запускать чужой repo для исследования: чтение evidence не разрешает code execution.

### Что реально проверено

Tool `find_repository_analogs`: caller problem/mechanism formulations; broad,
zero-star и forks-only first-page lanes; stateless batch continuation/fingerprint;
source exclusion; quota stop без sleep/credential fallback; provenance по каждой
строке. Четыре external кейса: Tablebot-pipe-Advanced, agora-mcp, ConstruBot,
plain duplicate-issue idea.24 first-page Search observations с caller-side merge,
не полный corpus и не все страницы. Дополнительные8 narrower probes — другие
незавершённые plans, не добавлять их к завершённым six-probe coverage.

Проверять отдельно: product problem, механизм, deployment/license, активность,
экономическая полезность. Stars не фильтр качества. Fork с одинаковым head/parent
не новая независимая идея. Awesome list/spec/dataset/demo не full runtime analog.
API totals — индексированные результаты запроса и ограниченное окно (обычно1000),
не исчерпывающий census всех доступных/частных/удалённых repo или их смысла.
Finite corpus не означает searchable complete semantic enumeration.

Полезные уже inspected pointers (НЕ universal replacements):
- `buidanhhuong/can-co`: offer/want и attribute/trust subset ranking; не доказан
  Agora-equivalent pgvector cosine retrieval.
- `agentcommercekit/ack`: MIT identity/payment demos, не готовая Agora или escrow;
  SDK trust/revocation/replay требуют отдельного review.
- `agentic-commerce-protocol/agentic-commerce-protocol`: checkout specification/MCP
  binding, не marketplace matching implementation.
- `gramster/dedupper`: SQLite/TF-IDF pairwise threshold + LLM triage, не embedding
  ANN/pre-creation UI; `pelikhan/action-genai-issue-dedup` — другой компонент.
- `Giakomogcs/ai-parametric-house-3d`: geometry/visualization adjacent; наблюдён
  identical parent/head, не отдельная новая реализация и не material estimator.
- `eusoff-hackers/eusoff_meal_bot`: spreadsheet reads/hardcoded dispatch, не
  table-authored workflow engine. Другие pointers/лицензии — в pinned reports.

### Не терять незавершённый live evidence gate

Path-walk source/runtime `65ddae12bfaf6d117bb8f472ba396016db36610a` установлен в
TEST по operator report; CI1060 tests на3.12 исторически записан в source report.
ConstruBot pinned `ee3d69e0f6c721207ab66ceef2d830a316d80d52`, explicit path
`backend/app/main.py`,start_line21,max_lines20. Рекурсивное дерево превысило256KiB;
новый bounded non-recursive pinned path-walk достигнут, но GitHub quota стала0.
Результат `unavailable/observed_rate_budget`,4requests; НЕ accepted lines21–40.
Повтор после reset только через обычный MCP reader, фиксировать linked tree/blob
integrity и returned lines либо честный отказ. Source report ниже старого заголовка
содержит historical «not installed»; верхний follow-up и этот ledger уточняют
хронологию, а не дают свежую гарантию availability.

Auto file selection остаётся эвристикой: namespace collisions/focus basename vs
path correction сохранены, но полезность выбора и semantic recall не доказаны.
Не писать алгоритм заново: сначала изучить examples/regression tests, затем
quality benchmark/coverage ledger и конкретные informative source follow-ups.

## 4. Embedded rooms #115/#116 → standalone #117

Pinned embedded source/docs `3f3002aaa065f85175e799ec3522c574f685ee7b`:
[API](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/docs/agent-rooms.md),
[production gaps](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/docs/agent-rooms-production.md),
[hardening](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/docs/agent-rooms-test-hardening-evidence.md),
[distinct owners](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/docs/agent-rooms-distinct-owner-evidence.md),
[two chats](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/docs/agent-rooms-two-chats.md),
[identity design](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/docs/mcp-rooms-identity-design.md),
[extraction plan](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/docs/mcp-rooms-standalone-plan.md).

8 methods: rooms_create/list/join/leave/read/send/delete_message/close. SQLite;
verified GitHub numeric principal, membership/ownership, <=500 Unicode text,
10s owner cadence,24h TTL, cursor/reply_to, persistent scoped idempotency.
One endpoint, no need another connector for embedded user. Rooms shared by
allowed participants, not private negotiation/E2EE or arbitrary code instructions.

Operator historical installation:65ddae1→a323a67 (120→128tools), source9f93eb0;
strict systemd initially blocked SQLite writes despite file ownership because
ReadWritePaths omitted room directory. Operator added ONLY TEST room path;
not fixed by chmod777/weakening production. Hardening composite
3c4eb8405c413a49374a17b73c973dbb9aeda9a6, source75555c3e; test count not asserted here: use exact evidence, not guessed totals. Initial upgrade failure
was retained and corrected before reported successful install.

Confirmed: old messages/idempotency/cursor survived restart; same-owner A→B→A;
then independent github:79429232 and github:340767429 credentials, before-join
read/send denial, join/exchange/retry, foreign-delete/close denial and after-leave
denial. One agent controlled two connections; later second-chat reply observed.
No autonomous polling/push delivery proof. Third owner not available, so denied
third owner gate remains open, as do cadence short-restart/full live restore/
off-host/WAL/disk/load/monitoring/release assembly/production approval.

Archived helpers: [enable](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/scripts/enable_test_agent_rooms.py),
[upgrade](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/scripts/upgrade_test_agent_rooms.py),
[temporary alias](https://github.com/LeonidYasin/mcp-server/blob/3f3002aaa065f85175e799ec3522c574f685ee7b/scripts/rooms_test_alias.py).
Two aliases can target same process/DB; alias is client connection workaround,
not a separate identity or a need for one server per chat. Shared proxy API key
is not verified personal principal. Do not replay old helpers on a changed TEST.

## 5. Что уже вынесено и НЕ нужно создавать заново

[Standalone repo](https://github.com/LeonidYasin/mcp-rooms), public MIT, PR #1,
branch feat/standalone-identity, docs source `c92d5036c7dc6c8686d31cbb14dc72c1f7369798`.
[AI entry](https://github.com/LeonidYasin/mcp-rooms/blob/c92d5036c7dc6c8686d31cbb14dc72c1f7369798/AGENTS.md),
[state](https://github.com/LeonidYasin/mcp-rooms/blob/c92d5036c7dc6c8686d31cbb14dc72c1f7369798/docs/work-state.json),
[historical live acceptance](https://github.com/LeonidYasin/mcp-rooms/blob/c92d5036c7dc6c8686d31cbb14dc72c1f7369798/docs/acceptance-2026-10-19.md),
[Qwen proxy + instructions](https://github.com/LeonidYasin/mcp-rooms/blob/c92d5036c7dc6c8686d31cbb14dc72c1f7369798/docs/qwen-client.md),
[proxy source](https://github.com/LeonidYasin/mcp-rooms/blob/c92d5036c7dc6c8686d31cbb14dc72c1f7369798/clients/qwen/mcp_proxy_v2.py),
[proxy diagnostics](https://github.com/LeonidYasin/mcp-rooms/blob/c92d5036c7dc6c8686d31cbb14dc72c1f7369798/clients/qwen/check_rooms_proxy.py),
[current F3c.1 evidence](https://github.com/LeonidYasin/mcp-rooms/blob/c92d5036c7dc6c8686d31cbb14dc72c1f7369798/docs/ci-f3c1.md).
Не копировать код прокси второй ручной копией в server; canonical files уже там.

В отличие от embedded: собственный UUID principal, индивидуальный digest-only key,
expiry/scopes/resource/revoke/disable, GitHub/email/phone не обязательны. Телефон/
email+свой UUID был промежуточным предложением, не текущим обязательным контрактом.
Был one-click signup/двое principals/rotation live pilot, затем signup отключали
на extended test. Qwen Desktop1.0.3.44 observed initialize без Authorization;
local debug proxy показал auth.present=false. Тот же key local+HTTPS curl прошёл.
Причина конкретной ошибки не Caddy при успешном том же HTTPS request: proxy
добавляет auth локально, masked debugging; не выводить full headers/bodies/keys.

Подтверждён Qwen→Rooms→Notion и обратный read с reply_to; cross-owner ACL;
restart persistence, consistent DB restore drill и disposable revoke/disable drill.
Restore старого snapshot может вернуть старые revocations/disabled users: это
наблюдённый риск, не устранённый одним checksum. Real keys не отзывались drill-ом.
Temporary HTTPS route удалён, standalone Rooms TEST stopped по operator report.
Никакой current public availability/production не обещается.

После пилота в Rooms принят собственный Python/SQLite marketplace domain (ADR001),
не обязательные PostgreSQL/Telegram/Cloudflare/готовый monolith. Web+MCP общие objects:
private draft→real photos→preview→explicit consent→public card→withdraw. Geographic
access не ограничен деревней/городом, geography — filter. Broad future: товары/
услуги/работа/люди/проекты/стартапы/инвесторы; поездки/доставка позднее. Реальная
продажа/спрос не выдумываются; снятый/помытый унитаз — технический тест, не PR-бренд.
Public web docs/prototype ≠ marketplace running. Админ MCP отдельный credential/
audience/scopes; private replies/browser writes/onboarding/search остаются gates.

Accepted Rooms source `fc96fe641092b1cfc07c6fa25cc2d3a65d0a88ac`:789 tests3.12,
Landlock/seccomp native child, consistent quarantined recovery с current original
authority,30 runtime hash pins/offline clean venv+native smoke. Recovery не
compose-ready, не full DR при утрате current authority. Следующий этап F3c.2
operator install/stop/rollback/resources. Промежуточные raw rooms installation/
proxy/root backup state — НЕ публичные portable deployment configs.

## 6. Честные неизвестные и правила продолжения

- Repo inventory/branch/PR state выше реально прочитаны через GitHub; это не fresh
  VPS/readiness acceptance. Sources pinned, runtime facts attributed to operator/
  historical authenticated evidence. Main deployment docs2026-10-15 устарели для
  последующих TEST candidates, но сохранены как история production.
- Другой чат https://app.notion.com/chat?t=3fc8b3cc846c8088a35300a97e20e65a упомянут
  владельцем. Его содержимое не прочитано; новые изменения сверять с current
  branch diffs/оператором, не заявлять, что все параллельные работы интегрированы.
- Старый binary feasibility использовал TEST run_python. Владелец затем явно
  запретил такие операции без отдельного подтверждения+пароля каждый раз.
  Исторический probe не создаёт разрешения повторять его или запускать scripts.
- Здесь НЕ публикуется полный chat dump: только отобранные публичные исходники,
  тесты, contracts, sanitized outcomes, решения/ошибки/неизвестные. Private payloads,
  root logs, keys, snapshots и live DB намеренно исключены.
- Не закрывать issues/PRs bulk, не мигрировать embedded DB в standalone, не
  объявлять полный coverage/производительность/лицензионную чистоту по snippet.
  Если immutable URL недоступен, это blocker: не восстанавливать source догадкой.
