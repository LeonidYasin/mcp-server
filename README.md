# MCP GitHub Server

[![version](https://img.shields.io/badge/version-0.4.3-blue)](pyproject.toml)
[![tools](https://img.shields.io/badge/tools-110-brightgreen)](TOOLS.md)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

Расширяемый MCP HTTP-сервер с модульной архитектурой и автоматическим обнаружением инструментов. Изначально вырос из обёртки над GitHub API, сейчас — универсальный набор инструментов для агента.

Сервер реализует **MCP Streamable HTTP transport** (JSON-RPC 2.0 поверх `POST /mcp`).

---

## 📌 Source of truth

| Что | Где источник правды |
|-----|---------------------|
| **Версия** | `pyproject.toml` (single-source; читается динамически в коде) — **0.4.3** |
| **Список инструментов** | рантайм-реестр: `list_my_tools`; полный каталог — [`TOOLS.md`](TOOLS.md) — **110** |
| **Схема инструмента** | `describe_tool(name)` |
| **Документация** | ревизия **3** от **2026-09-26** |

> **Ревизия документации: 3 · 2026-09-26.** Инкрементируется при каждом значимом изменении README/ROADMAP/TOOLS/SANDBOX. При расхождении доков и рантайма — прав рантайм (код), доки приводим к нему.

---

## Возможности

**Всего инструментов: 110** (полный каталог — [`TOOLS.md`](TOOLS.md)). Инструменты разложены по подпакетам `mcp_server/tools/`. Каждый подпакет — независимая категория, которую можно включать и отключать отдельно.

### 🐙 `github/` — GitHub API (82)

Файлы, коммиты, ветки, PR (включая review-threads), issues, releases, tags, gists, Actions/workflows, search, security-алерты.

| Группа | Инструменты |
|--------|-------------|
| Файлы | `get_file_contents`, `create_or_update_file`, `create_or_update_file_with_sha`, `create_or_update_binary_file`, `delete_file`, `move_file`, `replace_in_file`, `read_file_chunk`, `read_full_file`, `grep_file`, `list_directory` |
| Коммиты | `list_commits`, `get_commit_status`, `get_commit_diff`, `get_file_blame` |
| Ветки / сравнение | `list_branches`, `get_branch`, `create_branch`, `delete_branch`, `compare_branches`, `merge_branches` |
| PR | `create_pull_request`, `list_pull_requests`, `get_pull_request`, `update_pull_request`, `merge_pull_request`, `close_pull_request`, `add_pr_comment`, `request_pr_review`, `get_review_threads`, `resolve_review_thread`, `unresolve_review_thread` |
| Issues / метки | `create_issue`, `list_issues`, `get_issue`, `close_issue`, `add_issue_comment`, `add_labels` |
| Releases / Tags | `list_releases`, `create_release`, `get_latest_release`, `list_tags`, `create_tag`, `delete_tag` |
| Gists | `create_gist`, `list_gists`, `get_gist`, `update_gist` |
| Actions / Workflows | `dispatch_workflow`, `rerun_workflow`, `rerun_failed_jobs`, `cancel_workflow`, `list_workflows`, `list_workflow_runs`, `get_workflow_by_file`, `list_artifacts`, `download_artifact`, `get_workflow_run_status`, `get_workflow_run_steps`, `get_workflow_logs_preview`, `get_run_logs_by_step`, `get_step_logs_via_checks`, `read_run_logs_offset`, `grep_run_logs`, `grep_workflow_logs` |
| Search | `search_code`, `search_commits`, `search_issues`, `search_repositories` |
| Security | `list_dependabot_alerts`, `list_code_scanning_alerts`, `list_secret_scanning_alerts` |
| Repo info / admin | `get_repo_info`, `get_repo_languages`, `get_repo_topics`, `list_repo_contributors`, `update_repo_info`, `get_repo_tree` |
| Batch | `push_multiple_files`, `read_multiple_files` |

> **Большие файлы.** `get_file_contents` отдаёт файл целиком — для больших файлов клиент может обрезать ответ (`[truncated]`). Используйте `read_file_chunk(owner, repo, path, ref, offset, limit)`: жёстко ограниченный кусок строк (≤ 32 KB). Поиск по файлу — `grep_file(...)`. Файл целиком без угадывания чанков — `read_full_file(...)` (сам подбирает размер, склеивает части, ставит `(конец файла)` либо предупреждение о бюджете `max_bytes`).
>
> **Прямые ссылки на файл.** `get_file_contents`/`read_full_file` в начале ответа возвращают `🔗` (blob) и `📄` (raw) ссылки.

### 🏗️ `build/` — сборка и отладка (13)

`watch_build`, `auto_fix_build`, `get_android_build_error`, `get_ios_build_error`, `get_run_logs_by_step`, `get_step_logs_via_checks`, `get_latest_workflow_error`, `get_workflow_run_logs`, `get_full_workflow_logs`, `get_workflow_by_file`, `list_workflow_runs`, `get_latest_run_id`, `get_workflow_run_steps`

### 🌐 `web/` — веб (4)

`web_fetch`, `web_search` (DuckDuckGo HTML, без API-ключа), `rss_read`, `html_to_markdown`

### 🧰 `utils/` — утилиты и данные (15)

`base64_encode`, `base64_decode`, `hash_text`, `json_format`, `json_query`, `uuid_generate`, `timestamp_now`, `date_convert`, `regex_test`, `text_diff`, `csv_parse`, `csv_generate`, `yaml_to_json`, `json_to_yaml`, `markdown_to_html`

### 🧭 `meta/` — мета-инструменты (2)

`list_my_tools`, `describe_tool`

### 🧠 `synapse/` — находимость людей (`ENABLE_SYNAPSE=1`)

`publish_profile`, `search_people`, `propose_contact`, `save_note`, `search_notes`, `index_github`. Батч 7a — keyword-MVP; батч 7b (эмбеддинг-матчинг, item-модель offer/want) — в работе. Протокол — [`docs/synapse-protocol.md`](docs/synapse-protocol.md).

### 🔒 `localfs/` — локальные файлы (4, по умолчанию выключено)

`read_local_file`, `write_local_file`, `list_local_dir`, `search_in_files`. Флаг `ENABLE_LOCAL_TOOLS=1`, корень `LOCAL_TOOLS_ROOT`. См. [`SANDBOX.md`](SANDBOX.md).

### 🔒 `localgit/` — git в workspace (6, по умолчанию выключено)

`git_status`, `git_log`, `git_diff`, `git_commit`, `git_push`, `git_pull`. Тот же флаг.

### 🔒 `shell/` — sandboxed shell / python (2, по умолчанию выключено)

`run_command`, `run_python`. Флаг `ENABLE_LOCAL_SHELL=1`, выполнение только внутри `LOCAL_TOOLS_ROOT`. См. [`SANDBOX.md`](SANDBOX.md).

---

## Установка

```bash
git clone https://github.com/LeonidYasin/mcp-server.git
cd mcp-server
pip install -e .
```

Либо вручную: `pip install flask httpx python-dotenv flask-cors`.

## Запуск

```bash
python -m mcp_server.server
```

Сервер слушает `http://0.0.0.0:3001`, MCP-эндпоинт — `POST /mcp`. Health-check — `GET /health` (показывает `tool_count`, список инструментов и диагностику последнего запроса).

Токен GitHub передаётся заголовком `Authorization: Bearer <token>`.

### Включение локальных инструментов

```bash
export ENABLE_LOCAL_TOOLS=1          # localfs + localgit
export ENABLE_LOCAL_SHELL=1          # shell (run_command, run_python)
export ENABLE_SYNAPSE=1              # synapse
export LOCAL_TOOLS_ROOT=/workspace   # whitelist-корень (по умолчанию ~/workspace)
python -m mcp_server.server
```

## Подключение к DeepSeek++

- **URL:** `http://127.0.0.1:3001/mcp`
- **Тип:** HTTP
- **Заголовок:** `Authorization: Bearer <ваш_github_token>`

---

## Структура проекта

```
mcp-server/
├── pyproject.toml           # source of truth для версии
├── README.md
├── ROADMAP.md
├── SANDBOX.md
├── TOOLS.md                 # полный каталог инструментов
├── docs/
│   ├── synapse-protocol.md   # JSON-схема item/profile/contact/exchange
│   └── skills/               # Skills для ИИ-агентов (см. ниже)
└── mcp_server/
    ├── server.py            # Flask HTTP-сервер (MCP transport, token handling)
    ├── core/
    │   ├── tool.py          # Tool dataclass
    │   └── registry.py      # ToolRegistry + @mcp_tool
    └── tools/
        ├── build/           # сборка и отладка
        ├── github/          # GitHub API
        ├── localfs/         # локальные файлы (ENABLE_LOCAL_TOOLS)
        ├── localgit/        # git в workspace (ENABLE_LOCAL_TOOLS)
        ├── meta/            # list_my_tools, describe_tool
        ├── shell/           # shell/python (ENABLE_LOCAL_SHELL)
        ├── synapse/         # находимость людей (ENABLE_SYNAPSE)
        ├── utils/           # утилиты и данные
        └── web/             # web_fetch, web_search, rss, html
```

---

## Как добавить новый инструмент

### Шаг 1. Создайте файл в нужном подпакете

Пример: `mcp_server/tools/github/create_branch.py`

```python
"""MCP tool: create_branch - создаёт новую ветку."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="create_branch",
    description="Создаёт новую ветку в репозитории",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "branch": {"type": "string", "description": "Имя новой ветки"},
        "from_branch": {"type": "string", "description": "Источник (по умолчанию main)"},
    },
    required=["owner", "repo", "branch"],
)
def create_branch(client: GitHubClient, owner: str, repo: str, branch: str, from_branch: str = "main") -> dict:
    """Создать новую ветку."""
    ...
```

### Шаг 2. Подключите файл в `__init__.py` подпакета

Реестр (`mcp_server/core/registry.py`) регистрирует **только то, что явно импортировано** в `mcp_server/tools/<подпакет>/__init__.py`. Без импорта функция не станет инструментом.

### Шаг 3. Обновите доки

Добавьте инструмент в [`TOOLS.md`](TOOLS.md) и, если нужно, в этот README. Инкрементируйте **ревизию документации** в блоке Source of truth.
