# MCP GitHub Server

Расширяемый MCP HTTP-сервер для GitHub API с модульной архитектурой и автоматическим обнаружением инструментов.

## Возможности

| Инструмент | Описание |
|-----------|----------|
| `get_file_contents` | Чтение содержимого файлов из репозитория |
| `create_or_update_file` | Создание и обновление текстовых файлов |
| `create_or_update_file_with_sha` | Создание/обновление с авто-получением SHA |
| `create_or_update_binary_file` | Создание и обновление бинарных файлов (base64) |
| `delete_file` | Удаление файлов (автоматически получает SHA) |
| `list_commits` | Список последних коммитов |
| `get_commit_status` | Статус проверок для коммита |
| `get_latest_workflow_error` | Ошибка последней сборки |
| `get_workflow_run_logs` | Логи конкретного запуска workflow |
| `get_full_workflow_logs` | Полные логи всех jobs запуска |
| `get_workflow_by_file` | Запуски workflow по имени YAML-файла |
| `list_workflow_runs` | Список последних запусков workflow с run_id и статусами |
| `get_latest_run_id` | run_id последнего запуска workflow |
| `get_run_logs_by_step` | Логи конкретного шага по имени (с фильтрацией) |

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

## Структура проекта (реальная)

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
        ├── build/             # Инструменты для сборки (Android/iOS)
        │   ├── build_logs.py
        │   ├── build_logs_loader.py
        │   ├── build_logs_tools.py
        │   └── ...
        └── github/
            ├── __init__.py         # Экспорт всех инструментов
            ├── client.py           # GitHub API HTTP-клиент
            ├── commits.py          # list_commits, get_commit_status
            ├── file_ops.py         # get_file_contents, create_or_update_file, delete_file
            ├── file_sha_ops.py     # create_or_update_file_with_sha
            ├── create_update_binary.py  # create_or_update_binary_file
            ├── workflows.py        # get_latest_workflow_error, get_workflow_run_logs,
            │                       # get_full_workflow_logs, get_workflow_by_file
            └── workflow_runs.py    # list_workflow_runs, get_latest_run_id,
                                    # get_run_logs_by_step
```

### Примечание о структуре

В отличие от подхода «один инструмент = один файл», этот проект использует **тематическую группировку**:
- файлы группируют связанные инструменты
- `@mcp_tool` регистрирует каждый инструмент отдельно
- авто-дискавери работает через импорт в `__init__.py`

## Как добавить новый инструмент

### Шаг 1: Создайте или дополните файл в `mcp_server/tools/github/`

Пример добавления в существующий файл:

```python
# mcp_server/tools/github/workflow_runs.py

@mcp_tool(
    name="my_new_tool",
    description="Краткое описание",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
    },
    required=["owner", "repo"],
)
def my_new_tool(client: GitHubClient, owner: str, repo: str) -> str:
    # Ваш код здесь
    return _safe_utf8("Результат")
```

Или создайте новый файл, если группа инструментов новая.

### Шаг 2: Экспортируйте инструмент

В `mcp_server/tools/github/__init__.py` добавьте строку:

```python
from mcp_server.tools.github.workflow_runs import my_new_tool
```

### Шаг 3: Перезапустите сервер

```bash
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

1. **Функция должна быть синхронной** (не `async`) и принимать `client: GitHubClient` первым аргументом
2. **Декоратор `@mcp_tool`** задаёт:
   - `name` — имя инструмента (как будет вызываться)
   - `description` — описание для AI-ассистента
   - `parameters` — словарь параметров в формате JSON Schema
   - `required` — список обязательных параметров
3. **Возвращать нужно `str`** — текст ответа (используйте `_safe_utf8()` для безопасности)
4. **Для запросов к GitHub API** используйте методы `client.get_*` или `client._request()`

## Шаблон для копирования

```python
"""MCP tool: имя_инструмента - краткое описание."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    """Безопасно преобразует строку в UTF-8."""
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


@mcp_tool(
    name="имя_инструмента",
    description="Что делает инструмент",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
    },
    required=["owner", "repo"],
)
def имя_инструмента(client: GitHubClient, owner: str, repo: str) -> str:
    try:
        # Ваш код здесь
        result = "Результат работы"
        return _safe_utf8(result)
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")
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
- **v0.2.0** — Flask HTTP-транспорт, авто-обнаружение
- **v0.3.0** — Добавлены `list_workflow_runs`, `get_latest_run_id`, `get_run_logs_by_step`
