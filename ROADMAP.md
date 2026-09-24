# ROADMAP — расширение MCP-сервера

Дорожная карта развития `mcp-github-server`. Цель — превратить сервер из GitHub-обёртки в универсальный «швейцарский нож» для агента.

Легенда приоритетов:
- 🔴 высокий — блокирует базовые сценарии, делать первым
- 🟡 средний — ощутимо расширяет возможности
- 🟢 низкий — нишевое / требует осторожности

---

## Текущее состояние (baseline)

21 инструмент: GitHub files / commits / workflows / builds.

---

## Батч 1 — реализовано в этой ветке

### 🔴 GitHub: Pull Requests, Issues, Releases, Tags

Файлы: `mcp_server/tools/github/pull_requests.py`, `issues.py`, `releases.py`, `tags.py`

- PR: `create_pull_request`, `list_pull_requests`, `get_pull_request`, `merge_pull_request`, `close_pull_request`, `add_pr_comment`, `request_pr_review`
- Issues: `create_issue`, `list_issues`, `get_issue`, `close_issue`, `add_issue_comment`, `add_labels`
- Releases: `list_releases`, `create_release`, `get_latest_release`
- Tags: `list_tags`, `create_tag`

### 🔴 MCP meta

Файл: `mcp_server/tools/meta/meta_tools.py`

- `list_my_tools` — список всех зарегистрированных инструментов
- `describe_tool` — JSON-схема конкретного инструмента

### 🟡 Web

Файл: `mcp_server/tools/web/web_tools.py`

- `web_fetch` — получить HTML/текст страницы
- `web_search` — поиск через DuckDuckGo HTML (без API-ключа)

### 🟡 Утилиты

Файл: `mcp_server/tools/utils/utils_tools.py`

- `base64_encode`, `base64_decode`
- `hash_text` (md5/sha1/sha256)
- `json_format`, `json_query`
- `uuid_generate`
- `timestamp_now`, `date_convert`
- `regex_test`
- `text_diff`

### 🟡 GitHub: batch-операции

Файл: `mcp_server/tools/github/batch.py`

- `push_multiple_files` — несколько файлов одним коммитом

---

## Батч 2 — GitHub доведение до полноты

### 🔴 Ветки и рефы
- `delete_branch`, `get_branch`, `merge_branches`, `compare_branches`

### 🟡 Gists
- `create_gist`, `list_gists`, `get_gist`, `update_gist`

### 🟡 Repository
- `get_repo_info`, `get_repo_stats`, `list_repo_topics`, `update_repo`

### 🟡 Actions
- `dispatch_workflow`, `rerun_workflow`, `cancel_workflow`, `list_workflows`
- `list_artifacts`, `download_artifact`

### 🟡 Commits / files
- `get_commit_diff`, `list_directory`, `get_file_blame`

---

## Батч 3 — Безопасность и поиск

### 🟡 Security
- `list_dependabot_alerts`
- `list_code_scanning_alerts`
- `list_secret_scanning_alerts`

### 🟡 Search (расширить)
- уже есть `search_code`/`repos`/`users`/`issues`/`commits` у Copilot MCP;
  для локального сервера — добавить аналоги

---

## Батч 4 — Веб и данные

### 🟡 Web
- `rss_read` — парсинг RSS/Atom
- `html_to_markdown`
- `screenshot_url` (через headless browser)

### 🟡 Данные
- `csv_parse`, `csv_generate`
- `yaml_to_json`, `json_to_yaml`
- `markdown_to_html`

---

## Батч 5 — Локальная машина (осторожно)

⚠️ Требует whitelist путей и env-флаг `ENABLE_LOCAL_TOOLS=1`.

- `read_local_file`, `write_local_file`, `list_local_dir`, `search_in_files` (grep)
- `git_status`, `git_log`, `git_diff`, `git_commit`, `git_push`, `git_pull`

---

## Батч 6 — Shell / код (опасно)

⚠️ Требует подтверждения на опасные команды и таймаут.

- `run_command(cmd, cwd, timeout)`
- `run_python(code)` в песочнице

---

## Батч 7 — Память и Synapse

Стратегическая линия проекта.

- `model_me` — эмбеддинг-слепок пользователя из диалога
- `find_my_match` — поиск похожих людей по смыслу
- `publish_profile`, `search_people`, `propose_contact`
- `index_github` — индексировать публичные GitHub-профили
- `save_note`, `search_notes` — личная база знаний

---

## Технические заметки

- Инструменты возвращают `str`; обёртка в MCP-контент — на стороне `server.py`.
- Новый файл с инструментами нужно импортировать в `__init__.py` соответствующего подпакета.
- `ToolRegistry.discover()` сканирует подпакеты в `mcp_server/tools/`; внутри подпакета нужен `__init__.py` с импортами.
- Опасные категории (shell, local fs) держать отдельными подпакетами, чтобы отключать одной строкой.
