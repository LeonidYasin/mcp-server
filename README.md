```markdown
# MCP GitHub Server

Расширяемый MCP HTTP-сервер для GitHub API с модульной архитектурой и автоматическим обнаружением инструментов.

## Возможности

| Инструмент | Описание |
|-----------|----------|
| `get_file_contents` | Чтение содержимого файлов из репозитория |
| `create_or_update_file` | Создание и обновление текстовых файлов |
| `create_or_update_binary_file` | Создание и обновление бинарных файлов (base64) |
| `delete_file` | Удаление файлов (автоматически получает SHA) |
| `list_commits` | Список последних коммитов |
| `get_latest_workflow_error` | Ошибка последней сборки |
| `get_workflow_run_logs` | Логи конкретного запуска workflow |
| `get_full_workflow_logs` | Полные логи всех jobs запуска |
| `get_workflow_by_file` | Запуски workflow по имени YAML-файла |
| `get_commit_status` | Статус проверок для коммита |

## Установка

```bash
git clone https://github.com/LeonidYasin/mcp-server.git
cd mcp-server
pip install flask httpx python-dotenv
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
            ├── __init__.py    # Экспорт инструментов
            ├── client.py      # GitHub API HTTP-клиент
            ├── files.py       # get_file_contents
            ├── create_update.py # create_or_update_file / _binary_file
            ├── delete_file.py # delete_file
            └── workflows.py   # workflow-инструменты
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
async def create_branch(
    client: GitHubClient,
    owner: str,
    repo: str,
    branch: str,
    from_branch: str = "main",
) -> dict:
    """Создать новую ветку."""
    # 1. Получаем SHA родительской ветки
    ref_resp = await client._request(
        "GET", f"/repos/{owner}/{repo}/git/ref/heads/{from_branch}"
    )
    sha = ref_resp["object"]["sha"]

    # 2. Создаём ветку
    await client._request(
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

1. **Функция должна быть `async`** и принимать `client: GitHubClient` первым аргументом
2. **Декоратор `@mcp_tool`** задаёт:
   - `name` — имя инструмента (как будет вызываться)
   - `description` — описание для AI-ассистента
   - `parameters` — словарь параметров в формате JSON Schema
   - `required` — список обязательных параметров
3. **Возвращать нужно `dict`** с ключом `content` — списком объектов `{"type": "text", "text": "..."}`
4. **Для запросов к GitHub API** используйте `await client._request(method, path, ...)`

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
async def имя_инструмента(client: GitHubClient, owner: str, repo: str) -> dict:
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
```
