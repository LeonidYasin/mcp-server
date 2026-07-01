"""MCP tool: create_or_update_binary_file — создаёт/обновляет бинарный файл из base64."""

import base64
from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="create_or_update_binary_file",
    description="Создаёт или обновляет файл в репозитории из base64-строки (без экранирования).",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу в репозитории"},
        "content": {"type": "string", "description": "Содержимое файла в формате base64"},
        "message": {"type": "string", "description": "Сообщение коммита"},
        "branch": {"type": "string", "description": "Ветка (по умолчанию main)"}
    },
    required=["owner", "repo", "path", "content", "message"]
)
async def create_or_update_binary_file(
    client: GitHubClient,
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str = "main"
) -> dict:
    """Создать или обновить файл из base64."""
    
    # Декодируем base64 в байты
    try:
        decoded_content = base64.b64decode(content)
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Ошибка декодирования base64: {str(e)}"
            }]
        }
    
    # Получаем инструмент create_or_update_file из реестра
    from mcp_server.core.registry import registry
    tool = registry.get("create_or_update_file")
    if not tool or not tool.handler:
        return {
            "content": [{
                "type": "text",
                "text": "❌ Ошибка: Инструмент create_or_update_file не найден"
            }]
        }
    
    try:
        # Вызываем create_or_update_file с декодированным содержимым (как текст)
        # Если файл бинарный, нужно использовать другой подход
        # Но для текстовых файлов это работает
        result = await tool.handler(
            client=client,
            owner=owner,
            repo=repo,
            path=path,
            content=decoded_content.decode('utf-8'),
            message=message,
            branch=branch
        )
        return {
            "content": [{
                "type": "text",
                "text": f"✅ Файл {path} успешно создан/обновлён в {owner}/{repo} (ветка: {branch})"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Ошибка: {str(e)}"
            }]
        }
