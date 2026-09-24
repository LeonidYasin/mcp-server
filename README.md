# MCP GitHub Server

Расширяемый MCP HTTP-сервер с модульной архитектурой и автоматическим обнаружением инструментов. Изначально вырос из обёртки над GitHub API, сейчас — универсальный набор инструментов для агента.

Сервер реализует **MCP Streamable HTTP transport** (JSON-RPC 2.0 поверх `POST /mcp`). Актуальная версия — **0.4.2**.

---

## Возможности

Инструменты разложены по подпакетам `mcp_server/tools/`. Каждый подпакет — независимая категория, которую можно включать и отключать отдельно.

### 🐙 `github/` — GitHub API

Файлы, коммиты, ветки, PR, issues, releases, tags, gists, Actions, security-алерты, workflow/сборки.

| Группа | Инструменты |
|--------|-------------|
| Файлы | `get_file_contents`, `create_or_update_file`, `create_or_update_binary_file`, `create_or_update_file_with_sha`, `delete_file`, `read_file_chunk`, `read_full_file`, `grep_file`, `list_directory`, `get_file_blame` |
| Коммиты | `list_commits`, `get_commit_status`, `get_commit_diff` |
| Ветки / сравнение | `list_branches`, `get_branch`, `create_branch`, `delete_branch`, `compare_branches`, `merge_branches` |
| PR / Issues | `create_pull_request`, `list_pull_requests`, `get_pull_request`, `merge_pull_request`, `close_pull_request`, `add_pr_comment`, `request_pr_review`, `create_issue`, `list_issues`, `get_issue`, `close_issue`, `add_issue_comment`, `add_labels` |
| Releases / Tags | `list_releases`, `create_release`, `get_latest_release`, `list_tags`, `create_tag` |
| Gists | `create_gist`, `list_gists`, `get_gist`, `update_gist` |
| Actions | `dispatch_workflow`, `rerun_workflow`, `cancel_workflow`, `list_workflows`, `list_artifacts` |
| Security | `list_dependabot_alerts`, `list_code_scanning_alerts`, `list_secret_scanning_alerts` |
| Repo info | `get_repo_info`, `get_repo_languages`, `get_repo_topics`, `list_repo_contributors` |
| Batch | `push_multiple_files` |

> **Большие файлы.** `get_file_contents` отдаёт файл целиком — для больших файлов клиент может обрезать ответ (`[truncated]`). Используйте `read_file_chunk(owner, repo, path, ref, offset, limit)`: он возвращает жёстко ограниченный кусок строк (≤ 32 KB) с заголовком `[строки N-M из K]` и подсказкой следующего `offset`. Для поиска по файлу без чтения всего тела — `grep_file(owner, repo, path, pattern, ref, regex, case_sensitive, max_matches)`.
>
> Если нужно получить файл **целиком** и не угадывать чанки — используйте `read_full_file(owner, repo, path, ref, max_bytes, include_line_numbers)`. Он сам подбирает безопасный размер куска (по средней длине строки, бюджет ~24 KB на срез), склеивает все части и в конце ставит `(конец файла)` либо предупреждение о достижении защитного бюджета `max_bytes`.

### 🏗️ `build/` — сборка и отладка

`watch_build`, `auto_fix_build`, `get_android_build_error`, `get_ios_build_error`, `get_run_logs_by_step`, `get_step_logs_via_checks`, `get_latest_workflow_error`, `get_workflow_run_logs`, `get_full_workflow_logs`, `get_workflow_by_file`, `list_workflow_runs`, `get_latest_run_id`, `get_workflow_run_steps`.

### 🌐 `web/` — веб

`web_fetch`, `web_search` (DuckDuckGo HTML, без API-ключа), `rss_read`, `html_to_markdown`.

### 🧰 `utils/` — утилиты и данные

`base64_encode`, `base64_decode`, `hash_text`, `json_format`, `json_query`, `uuid_generate`, `timestamp_now`, `date_convert`, `regex_test`, `text_diff`, `csv_parse`, `csv_generate`, `yaml_to_json`, `json_to_yaml`, `markdown_to_html`.

### 🧭 `meta/` — мета-инструменты

`list_my_tools` (список всех зарегистрированных инструментов), `describe_tool` (JSON-схема конкретного инструмента).

### 🔒 `localfs/` — локальные файлы (по умолчанию выключено)

`read_local_file`, `write_local_file`, `list_local_dir`, `search_in_files`.

Регистрируются только при `ENABLE_LOCAL_TOOLS=1`. Все пути ограничены `LOCAL_TOOLS_ROOT` (по умолчанию `~/workspace`). См. `SANDBOX.md`.

### 🔒 `localgit/` — git в workspace (по умолчанию выключено)

`git_status`, `git_log`, `git_diff`, `git_commit`, `git_push`, `git_pull`.

Тот же флаг `ENABLE_LOCAL_TOOLS` и тот же `LOCAL_TOOLS_ROOT`. Репозитории должны лежать внутри корня.

---

## Установка

```bash
git clone https://github.com/LeonidYasin/mcp-server.git
cd mcp-server
pip install flask httpx python-dotenv flask-cors
```

Либо через пакет:

```bash
pip install -e .
```

## Запуск

```bash
python -m mcp_server.server
```

Сервер слушает `http://0.0.0.0:3001`, MCP-эндпоинт — `POST /mcp`. Health-check — `GET /health` (показывает `tool_count`, список инструментов и диагностику последнего запроса).

Токен GitHub передаётся заголовком `Authorization: Bearer <token>`.

### Включение локальных инструментов

```bash
export ENABLE_LOCAL_TOOLS=1          # включает localfs + localgit
export LOCAL_TOOLS_ROOT=/workspace   # whitelist-корень (по умолчанию ~/workspace)
python -m mcp_server.server
```

## Подключение к DeepSeek++

В настройках плагина:

- **URL:** `http://127.0.0.1:3001/mcp`
- **Тип:** HTTP
- **Заголовок:** `Authorization: Bearer <ваш_github_token>`

---

## Структура проекта

```
mcp-server/
├── pyproject.toml
├── README.md
├── ROADMAP.md
├── SANDBOX.md
└── mcp_server/
    ├── __init__.py
    ├── server.py              # Flask HTTP-сервер (MCP transport, token handling, нормализация content)
    ├── core/
    │   ├── __init__.py
    │   ├── tool.py            # Tool dataclass
    │   └── registry.py        # ToolRegistry + канонический декоратор @mcp_tool
    └── tools/
        ├── __init__.py        # импорт подпакетов для авто-обнаружения
        ├── build/             # сборка и отладка
        ├── github/            # GitHub API
        ├── localfs/           # локальные файлы (ENABLE_LOCAL_TOOLS)
        ├── localgit/          # git в workspace (ENABLE_LOCAL_TOOLS)
        ├── meta/              # list_my_tools, describe_tool
        ├── utils/             # утилиты и данные
        └── web/               # web_fetch, web_search, rss, html
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
    ref_resp = client._request(
        "GET", f"/repos/{owner}/{repo}/git/ref/heads/{from_branch}"
    )
    sha = ref_resp.json()["object"]["sha"]

    client._request(
        "POST",
        f"/repos/{owner}/{repo}/git/refs",
        json={"ref": f"refs/heads/{branch}", "sha": sha},
    )

    return {
        "content": [{
            "type": "text",
            "text": f"✅ Ветка '{branch}' создана из '{from_branch}'"
        }]
    }
```

### Шаг 2. Экспортируйте инструмент

В `mcp_server/tools/<подпакет>/__init__.py` добавьте строку:

```python
from mcp_server.tools.github.create_branch import create_branch
```

### Шаг 3. Перезапустите сервер

```bash
# Ctrl+C, затем:
python -m mcp_server.server
```

Инструмент появится в `tools/list` автоматически.

---

## Как работает авто-обнаружение

`ToolRegistry` (в `mcp_server/core/registry.py`) при старте:

1. Сканирует подпакеты `mcp_server/tools/` через `pkgutil.iter_modules`.
2. Импортирует каждый подпакет.
3. Ищет функции с атрибутом `_mcp_tool` — его ставит декоратор `@mcp_tool` из `core/registry.py`.
4. Регистрирует найденные `Tool` в реестре.
