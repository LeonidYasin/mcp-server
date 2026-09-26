# TOOLS — полный каталог инструментов mcp-server

> **Source of truth:** рантайм-реестр сервера. Актуальный список всегда можно получить вызовом MCP-инструмента `list_my_tools`; схему любого инструмента — `describe_tool`.
>
> **Ревизия:** 3 · **Дата:** 2026-09-26 · **Всего инструментов: 110**

Инструменты сгруппированы по подпакетам `mcp_server/tools/`. Каждый подпакет — независимая категория, которую можно включать/отключать отдельно.

---

## 🐙 `github/` — GitHub API (83)

### Файлы (11)
`get_file_contents`, `create_or_update_file`, `create_or_update_file_with_sha`, `create_or_update_binary_file`, `delete_file`, `move_file`, `read_file_chunk`, `read_full_file`, `grep_file`, `list_directory`

### Коммиты (4)
`list_commits`, `get_commit_status`, `get_commit_diff`, `get_file_blame`

### Ветки / сравнение (6)
`list_branches`, `get_branch`, `create_branch`, `delete_branch`, `compare_branches`, `merge_branches`

### Pull Requests (11)
`create_pull_request`, `list_pull_requests`, `get_pull_request`, `update_pull_request`, `merge_pull_request`, `close_pull_request`, `add_pr_comment`, `request_pr_review`, `get_review_threads`, `resolve_review_thread`, `unresolve_review_thread`

### Issues (5)
`create_issue`, `list_issues`, `get_issue`, `close_issue`, `add_issue_comment`

### Метки (1)
`add_labels`

### Releases / Tags (7)
`list_releases`, `create_release`, `get_latest_release`, `list_tags`, `create_tag`, `delete_tag`

### Gists (4)
`create_gist`, `list_gists`, `get_gist`, `update_gist`

### Actions / Workflows (17)
`dispatch_workflow`, `rerun_workflow`, `rerun_failed_jobs`, `cancel_workflow`, `list_workflows`, `list_workflow_runs`, `get_workflow_by_file`, `list_artifacts`, `download_artifact`, `get_workflow_run_status`, `get_workflow_run_steps`, `get_workflow_logs_preview`, `get_run_logs_by_step`, `get_step_logs_via_checks`, `read_run_logs_offset`, `grep_run_logs`, `grep_workflow_logs`

### Security (3)
`list_dependabot_alerts`, `list_code_scanning_alerts`, `list_secret_scanning_alerts`

### Repo info / admin (6)
`get_repo_info`, `get_repo_languages`, `get_repo_topics`, `list_repo_contributors`, `update_repo_info`, `get_repo_tree`

### Batch / multiple (3)
`push_multiple_files`, `read_multiple_files`

### Search (4)
`search_code`, `search_commits`, `search_issues`, `search_repositories`

---

## 🏗️ `build/` — сборка и отладка (13)

`watch_build`, `auto_fix_build`, `get_android_build_error`, `get_ios_build_error`, `get_run_logs_by_step`, `get_step_logs_via_checks`, `get_latest_workflow_error`, `get_workflow_run_logs`, `get_full_workflow_logs`, `get_workflow_by_file`, `list_workflow_runs`, `get_latest_run_id`, `get_workflow_run_steps`

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

Флаг `ENABLE_LOCAL_SHELL=1`. Команды выполняются только внутри `LOCAL_TOOLS_ROOT`. См. `SANDBOX.md`.

---

## 🧠 `synapse/` — находимость людей (6+, флаг `ENABLE_SYNAPSE=1`)

`publish_profile`, `search_people`, `propose_contact`, `save_note`, `search_notes`, `index_github`

Батч 7a — каркас без эмбеддингов (keyword-MVP). Батч 7b (эмбеддинг-матчинг, item-модель offer/want) — в работе. Данные в `SYNAPSE_DATA_DIR`. Протокол — `docs/synapse-protocol.md`.

---

_Ревизия 1 · 2026-09-26 · всего 109 инструментов. При добавлении/удалении инструмента — обновить этот файл, счётчик и инкрементировать ревизию._
