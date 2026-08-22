# MCP GitHub Server

Расширяемый MCP HTTP-сервер для GitHub API с модульной архитектурой и автоматическим обнаружением инструментов.

## Возможности

Сервер предоставляет **19 инструментов** для работы с GitHub:

### 📁 Работа с файлами (4)
| Инструмент | Описание |
|-----------|----------|
| `get_file_contents` | Чтение содержимого файлов из репозитория |
| `create_or_update_file` | Создание и обновление текстовых файлов |
| `create_or_update_binary_file` | Создание и обновление бинарных файлов (base64) |
| `delete_file` | Удаление файлов (автоматически получает SHA) |

### 📝 Коммиты (2)
| Инструмент | Описание |
|-----------|----------|
| `list_commits` | Список последних коммитов |
| `get_commit_status` | Статус проверок для коммита |

### ⚙️ Workflow (7)
| Инструмент | Описание |
|-----------|----------|
| `get_latest_workflow_error` | Ошибка последней сборки |
| `get_workflow_run_logs` | Логи конкретного запуска workflow |
| `get_full_workflow_logs` | Полные логи всех jobs запуска |
| `get_workflow_by_file` | Запуски workflow по имени YAML-файла |
| `list_workflow_runs` | Список запусков с run_id и статусами |
| `get_latest_run_id` | run_id последнего запуска |
| `get_workflow_run_steps` | Список всех шагов в запуске с их статусами |

### 🏗️ Сборка и отладка (6)
| Инструмент | Описание |
|-----------|----------|
| `watch_build` | Мониторинг сборки |
| `auto_fix_build` | Авто-исправление ошибок сборки (Android/iOS) |
| `get_android_build_error` | Детальная ошибка Android сборки |
| `get_ios_build_error` | Детальная ошибка iOS сборки |
| `get_run_logs_by_step` | Логи конкретного шага по имени |
| `create_or_update_file_with_sha` | Создание/обновление с авто-получением SHA |

## Установка

```bash
git clone https://github.com/LeonidYasin/mcp-server.git
cd mcp-server
pip install flask httpx python-dotenv flask-cors
```

## Запуск

```bash
python -m mcp_server.server
```

Сервер запускается на `http://0.0.0.0:3001`, эндпоинт MCP: `POST /mcp`.

Токен GitHub передаётся через заголовок `Authorization: Bearer <token>`.

## Подключение к DeepSeek++

В настройках плагина DeepSeek++:
- **URL:** `http://127.0.0.1:3001/mcp`
- **Тип:** HTTP
- **Заголовок:** `Authorization: Bearer <ваш_github_token>`

## Структура проекта

```
mcp-server/
├── pyproject.toml
├── README.md
└── mcp_server/
    ├── __init__.py
    ├── server.py              # Flask HTTP-сервер
    ├── core/
    │   ├── __init__.py
    │   ├── tool.py            # Tool dataclass
    │   └── registry.py        # ToolRegistry с авто-обнаружением
    └── tools/
        ├── __init__.py
        └── github/
            ├── __init__.py            # Экспорт инструментов
            ├── client.py              # GitHub API HTTP-клиент
            ├── file_ops.py            # get_file_contents, create_or_update_file, delete_file
            ├── file_sha_ops.py        # create_or_update_file_with_sha
            ├── create_update_binary.py # create_or_update_binary_file
            ├── commits.py             # list_commits, get_commit_status
            ├── workflows.py           # workflow-инструменты (4 шт)
            ├── workflow_runs.py       # list_workflow_runs, get_latest_run_id, get_workflow_run_steps, get_run_logs_by_step
            ├── build_logs.py          # watch_build
            ├── build_logs_loader.py   # auto_fix_build, get_android_build_error, get_ios_build_error
            └── build_logs_tools.py    # вспомогательные функции для сборки
```

## Как добавить новый инструмент

### Шаг 1: Создайте файл в `mcp_server/tools/github/`

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
    # 1. Получаем SHA родительской ветки
    ref_resp = client._request(
        "GET", f"/repos/{owner}/{repo}/git/ref/heads/{from_branch}"
    )
    sha = ref_resp.json()["object"]["sha"]

    # 2. Создаём ветку
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

### Шаг 2: Экспортируйте инструмент

В `mcp_server/tools/github/__init__.py` добавьте строку:

```python
from mcp_server.tools.github.create_branch import create_branch
```

### Шаг 3: Перезапустите сервер

```bash
# Остановите Ctrl+C и снова запустите
python -m mcp_server.server
```

Инструмент автоматически появится в списке. Никакой другой настройки не требуется.

## Как работает авто-обнаружение

`ToolRegistry` (в `mcp_server/core/registry.py`) при запуске:

1. Сканирует `mcp_server/tools/`
2. Находит все подпакеты (директории с `__init__.py`)
3. Импортирует их и ищет функции с декоратором `@mcp_tool`
4. Регистрирует найденные инструменты

## Правила написания инструментов

1. **Функция должна быть синхронной** и принимать `client: GitHubClient` первым аргументом
2. **Декоратор `@mcp_tool`** задаёт:
   - `name` — имя инструмента (как будет вызываться)
   - `description` — описание для AI-ассистента
   - `parameters` — словарь параметров в формате JSON Schema
   - `required` — список обязательных параметров
3. **Возвращать нужно `dict`** с ключом `content` — списком объектов `{"type": "text", "text": "..."}`
4. **Для запросов к GitHub API** используйте `client._request(method, path, ...)`

## Шаблон для копирования

```python
"""MCP tool: имя_инструмента - краткое описание."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="имя_инструмента",
    description="Что делает инструмент",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
    },
    required=["owner", "repo"],
)
def имя_инструмента(client: GitHubClient, owner: str, repo: str) -> dict:
    # Ваш код здесь
    return {
        "content": [{"type": "text", "text": "Результат работы"}]
    }
```

## Требования к GitHub токену

Токен должен иметь следующие разрешения (scopes):
- `repo` (или `Contents: Read and write`) — для работы с файлами
- `Actions: Read` — для просмотра workflow
- `Metadata: Read` — для базовой информации (обычно по умолчанию)

## Тестирование сервера через curl

```bash
# Проверка списка инструментов
curl -X POST http://127.0.0.1:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <токен>" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list","params":{}}'

# Чтение файла
curl -X POST http://127.0.0.1:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <токен>" \
  -d '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"get_file_contents","arguments":{"owner":"LeonidYasin","repo":"mcp-server","path":"README.md"}}}'
```

## Версионирование

- **v0.1.0** — stdio-транспорт, базовая модульная архитектура
- **v0.2.0** — Flask HTTP-транспорт, 10 инструментов, авто-обнаружение, инструкция для разработчиков
- **v0.3.0** — Добавлены 9 новых инструментов: всего 19, включая работу с workflow, сборкой и отладкой
