# TOOLS — полный каталог инструментов mcp-server

> **Read-only кандидат #64/#89:** добавлены `get_release` и `list_release_assets`; без asset bytes, writes/publish, Actions и deployment. [Контракт и ограничения](docs/release-reads.md). PR #91 (upload) остаётся отдельным кандидатом; это не его merge или приёмка полного маршрута.

> **Source of truth:** рантайм-реестр сервера. Актуальный список всегда можно получить вызовом MCP-инструмента `list_my_tools`; схему любого инструмента — `describe_tool`.
>
> **Ревизия:** 9 · **Дата:** 2026-10-15 · **Состав:** проверять `list_my_tools` на выбранной сборке и feature flags

Инструменты сгруппированы по подпакетам `mcp_server/tools/`. Каждый подпакет — независимая категория, которую можно включать/отключать отдельно.

---

[Снимок окружений на 2026-10-15](docs/deployment-status.md): production 113 tools на `b78b209…`; TEST 119 на кандидате #87, shell/process только TEST. Это не меняет inventory профилей ниже; upload API #88 не включён в эту ветку; два read-only метода #89 доступны только на данном кандидате, не на production.

## Проверяемый профиль реестра

Snapshot [tool-inventory.json](docs/tool-inventory.json) получен локальным discovery без вызова handlers/сети и сверяется `python scripts/check_docs.py`. Для этой кодовой базы: **115 default**, **145 при всех трёх feature flags**. Это не счётчик deployed production/TEST: их revision/env надо читать отдельно.

| Категория handler (уникальные registry names) | Default | All enabled |
| --- | --- | --- |
| github | 92 | 92 |
| build | 2 | 2 |
| utils / meta / web | 15 / 2 / 4 | 15 / 2 / 4 |
| localfs / localgit | 0 / 0 | 4 / 6 |
| shell / process | 0 / 0 | 2 / 4 |
| synapse | 0 | 14 |

Списки ниже — **логические группы**; некоторые Actions/build names повторяются, поэтому их подзаголовки нельзя складывать для получения общего числа. Handler category в snapshot отражает реальное место зарегистрированной функции, не старый план батчей. Process names обнаруживаются при флаге, но управление требует Linux `/proc`. [Token gate](docs/http-transport.md) имеет отдельные ограничения, а `auto_fix_build` зарегистрирован, но отключён.

---

## Планируемые файловые API — не зарегистрированы

[#88](https://github.com/LeonidYasin/mcp-server/issues/88) → [#89](https://github.com/LeonidYasin/mcp-server/issues/89): client upload → scoped staging `file_id` → Release asset → Actions → verified bytes. `begin_file_upload` / `append_file_chunk` / `finish_file_upload` — лишь один из вариантов дизайна, как и будущие `upload_release_asset`, `download_release_asset`; не вызывать их как готовые tools. Основной транспорт выбирается после проверки реального клиента. [План](docs/binary-transfer-plan.md) · [Карта](docs/project-map.md) · [Roadmap](ROADMAP.md).

---

## 🐙 `github/` — GitHub API

### Файлы (12)
`get_file_contents`, `get_file_sha`, `create_or_update_file`, `create_or_update_file_with_sha`, `create_or_update_binary_file`, `delete_file`, `move_file`, `replace_in_file`, `read_file_chunk`, `read_full_file`, `grep_file`, `list_directory`

`create_or_update_binary_file` несмотря на имя декодирует base64 через UTF-8 и записывает в Git. Не подходит для произвольных бинарных ZIP/XLSX, staging и передачи клиентских файлов (#88). `read_multiple_files` — чтение файлов GitHub, не загрузка вложений клиента.

### Коммиты (4)
`list_commits`, `get_commit_status`, `get_commit_diff`, `get_file_blame`

`get_commit_status`: агрегирует legacy statuses и Check Runs по resolved SHA; `success/failure/pending/no_checks/unknown`, постраничные лимиты `max_pages` и лимит вывода `max_rows`. JSON-строка `metadata:` содержит sources/completeness/counts; не определяет merge eligibility. [Контракт и neutral/skipped policy](docs/commit-status.md).

### Ветки / сравнение (6)
`list_branches`, `get_branch`, `create_branch`, `delete_branch`, `compare_branches`, `merge_branches`

`create_branch`: `from_branch` принимает ветку/ref/SHA; `from_sha` — точный полный SHA, включая доступный fork network. Без merge и перезаписи ref; no-op только при совпадении SHA, обязательный read-back. [Контракт копирования ветки](docs/create-branch.md).

`compare_branches`: `max_files` (0–300, default 10) ограничивает summary и patches; `max_patch_bytes` / `max_patch_lines` ограничивают общий patch. SHA и completeness/truncation — в JSON-строке `metadata:`. Three-dot, не diff двух деревьев. [Подробный контракт](docs/compare-branches.md).

### Pull Requests (11)
`create_pull_request`, `list_pull_requests`, `get_pull_request`, `update_pull_request`, `merge_pull_request`, `close_pull_request`, `add_pr_comment`, `request_pr_review`, `get_review_threads`, `resolve_review_thread`, `unresolve_review_thread`

`get_pull_request`: structured SHA/draft/mergeability/timestamps и repo method flags в `metadata:`. `merge_pull_request`: обязательно `expected_head_sha`, enum метода, checks/preflight и один guarded PUT; нет автоматического retry/fallback или обхода protection. [Контракт и safety change](docs/pr-preflight.md).

`update_pull_request`: `draft` меняется через GraphQL с независимым REST read-back; bool-only, already-target no-op, закрытый/merged PR отклоняется. `metadata:` различает requested/actual/applied и partial/unconfirmed. Draft-only не отправляет REST PATCH и не меняет прочие поля. [Контракт draft/ready](docs/pr-draft.md).

### Issues (5)
`create_issue`, `list_issues`, `get_issue`, `close_issue`, `add_issue_comment`

### Метки (1)
`add_labels`

### Releases / Tags
`list_releases`, `create_release`, `get_latest_release`, `get_release`, `list_release_assets`, `list_tags`, `create_tag`, `delete_tag`

В main нет полного Release assets upload/list/download lifecycle. #64 — tags/releases; новый #89 — assets и Actions после #88. `get_release`/`list_release_assets` — read-only кандидат; upload/download assets всё ещё план. Не путать Release assets с `download_artifact` (Actions artifacts). [Зависимости и acceptance](docs/binary-transfer-plan.md).

### Gists (4)
`create_gist`, `list_gists`, `get_gist`, `update_gist`

### Actions / Workflows (17)
`dispatch_workflow`, `rerun_workflow`, `rerun_failed_jobs`, `cancel_workflow`, `list_workflows`, `list_workflow_runs`, `get_workflow_by_file`, `list_artifacts`, `download_artifact`, `get_workflow_run_status`, `get_workflow_run_steps`, `get_workflow_logs_preview`, `get_run_logs_by_step`, `get_step_logs_via_checks`, `read_run_logs_offset`, `grep_run_logs`, `grep_workflow_logs`

`download_artifact`: разрешает настоящий 302 Location без follow/CDN-запроса и передачи PAT; `artifact_id` или точное `name` + `run_id`, bounded lookup `max_pages`, отказ при неоднозначности/неполноте. Компактный `metadata:` содержит чувствительный short-lived download_url только при resolved; не путать с API URL/retention expiry. [Контракт и credential boundary](docs/artifact-download.md).

### Security (3)
`list_dependabot_alerts`, `list_code_scanning_alerts`, `list_secret_scanning_alerts`

### Repo info / admin (6)
`get_repo_info`, `get_repo_languages`, `get_repo_topics`, `list_repo_contributors`, `update_repo_info`, `get_repo_tree`

### Repo management (3)
`create_repo`, `list_my_repos`, `update_repo`

### Batch / multiple (2)
`push_multiple_files`, `read_multiple_files`

`push_multiple_files`: existing blob modes сохраняются; explicit `files[].mode`, optional `expected_head_sha`, один complete tree read и non-force ref update. [Modes/concurrency contract](docs/batch-push.md).

### Search (4)
`search_code`, `search_commits`, `search_issues`, `search_repositories`

---

## 🏗️ `build/` — сборка и отладка (13)

`watch_build`, `auto_fix_build`, `get_android_build_error`, `get_ios_build_error`, `get_run_logs_by_step`, `get_step_logs_via_checks`, `get_latest_workflow_error`, `get_workflow_run_logs`, `get_full_workflow_logs`, `get_workflow_by_file`, `list_workflow_runs`, `get_latest_run_id`, `get_workflow_run_steps`

`get_workflow_run_status`, `get_workflow_run_steps`: optional `run_attempt`, `max_pages` (1–20, default 5), `max_jobs` (0–100, default 20), `max_steps` (0–500, default 100). Attempt identity, source completeness and output truncation are separate. [Attempt snapshot contract](docs/workflow-attempts.md). Attempt-aware log readers: `read_run_logs_offset`, `grep_run_logs`, `get_run_logs_by_step`, `grep_workflow_logs`; structured responses; combined-step filtering via exact timeline + unique runner markers, case-specific ambiguity fallback. [Combined step boundaries](docs/workflow-step-boundaries.md). [Logs contract/migration](docs/workflow-attempt-logs.md). Legacy diagnostic/full/preview/watch/checks names now use bounded attempt adapters with explicit contract changes. [Adapter migration](docs/workflow-diagnostic-adapters.md). Unsafe template-to-main `auto_fix_build` is disabled pending reviewed replacement.

> Часть инструментов `build/` функционально пересекается с группой Actions в `github/` — это исторически сложившееся разделение (build-специфичные обёртки).

---

## 🌐 `web/` — веб (4)

`web_fetch`, `web_search` (DuckDuckGo HTML, без API-ключа), `rss_read`, `html_to_markdown`

---

## 🧰 `utils/` — утилиты и данные (15)

`base64_encode`, `base64_decode`, `hash_text`, `json_format`, `json_query`, `uuid_generate`, `timestamp_now`, `date_convert`, `regex_test`, `text_diff`, `csv_parse`, `csv_generate`, `yaml_to_json`, `json_to_yaml`, `markdown_to_html`

---

## 🧭 `meta/` — мета-инструменты (2)

`list_my_tools` (список всех зарегистрированных инструментов), `describe_tool` (JSON-схема конкретного инструмента)

---

## 🔒 `localfs/` — локальные файлы (4, по умолчанию выключено)

`read_local_file`, `write_local_file`, `list_local_dir`, `search_in_files`

Регистрируются только при `ENABLE_LOCAL_TOOLS=1`. Все пути ограничены `LOCAL_TOOLS_ROOT` (по умолчанию `~/workspace`). См. `SANDBOX.md`.

---

## 🔒 `localgit/` — git в workspace (6, по умолчанию выключено)

`git_status`, `git_log`, `git_diff`, `git_commit`, `git_push`, `git_pull`

Тот же флаг `ENABLE_LOCAL_TOOLS` и тот же `LOCAL_TOOLS_ROOT`. Репозитории должны лежать внутри корня.

---

## 🔒 `shell/` — sandboxed shell / python (2, по умолчанию выключено)

`run_command`, `run_python`

Флаг `ENABLE_LOCAL_SHELL=1`. Только **cwd** ограничен `LOCAL_TOOLS_ROOT`; filesystem/network-доступ исполняемого кода определяется OS policy, не этим флагом. См. `SANDBOX.md`.

---

## 🔒 `process/` — фоновые процессы (4, по умолчанию выключено)

`start_background`, `stop_process`, `process_status`, `tail_log`

Linux-only, opt-in `ENABLE_LOCAL_SHELL`; identity guard до сигналов, no-follow bookkeeping, bounded log reads. [Lifecycle и safety contract](docs/process-manager.md).

Тот же флаг `ENABLE_LOCAL_SHELL=1`, что и у `shell/` — это дополнение к нему для
долгоживущих процессов, которые `run_command` не может запустить (он
блокирующий и убивает по таймауту). См. `SANDBOX.md`.

---

## 🧠 `synapse/` — находимость людей (14, флаг `ENABLE_SYNAPSE=1`)

`publish_profile`, `search_people`, `propose_contact`, `save_note`, `search_notes`, `index_github`, `submit_offer`, `submit_want`, `list_my_items`, `deactivate_item`, `model_me`, `find_my_match`, `draft_profile_from_dialog`, `report_match_outcome`

Батч 7a — keyword-MVP; 8 дополнительных item/matching tools уже регистрируются из main при включённом флаге. Провайдер задаётся отдельно, без него keyword fallback. Provider availability/качество не подтверждаются одной регистрацией. Данные в `SYNAPSE_DATA_DIR`. Протокол — `docs/synapse-protocol.md`.

---

_Ревизия 9 · 2026-10-15. При изменении инструментов сверять каталог с runtime, учитывать feature flags и инкрементировать ревизию; планируемые API не включать в число доступных._
