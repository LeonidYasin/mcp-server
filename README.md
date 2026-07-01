# MCP GitHub Server v0.2.0

HTTP MCP-сервер для GitHub API с полным набором инструментов, включая `delete_file`.

## Инструменты

| Инструмент | Описание |
|---|---|
| `create_or_update_file` | Создание/обновление текстовых файлов |
| `create_or_update_binary_file` | Создание/обновление бинарных файлов (base64) |
| `get_file_contents` | Чтение содержимого файлов |
| `delete_file` | 🆕 Удаление файлов |
| `list_commits` | Список коммитов |
| `get_latest_workflow_error` | Ошибка последней сборки |
| `get_workflow_run_logs` | Логи конкретного workflow run |
| `get_full_workflow_logs` | Полные логи всех jobs |
| `get_workflow_by_file` | Запуски workflow по имени YAML |
| `get_commit_status` | Статус проверок коммита |

## Аутентификация

Токен передаётся через заголовок `Authorization: Bearer <token>` при каждом запросе.
Никаких `.env` файлов на сервере не требуется.

## Установка и запуск

```bash
git clone https://github.com/LeonidYasin/mcp-server.git
cd mcp-server
pip install flask httpx
python -m mcp_server.server
```

Сервер запустится на `http://0.0.0.0:3001`.

### Переменные окружения (опционально)

- `PORT` — порт (по умолчанию 3001)
- `DEBUG` — режим отладки (`true`/`false`)

## Подключение к DeepSeek++ / Claude Desktop

В настройках MCP укажите:
- **URL:** `http://localhost:3001/mcp`
- **Headers:** `Authorization: Bearer ghp_your_github_token`

## Структура

```
mcp-server/
├── pyproject.toml
├── README.md
├── .gitignore
└── mcp_server/
    ├── __init__.py
    └── server.py          # HTTP MCP сервер (Flask)
```
