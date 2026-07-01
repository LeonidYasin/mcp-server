"""MCP tool: create_or_update_binary_file — создаёт/обновляет файл из base64."""

import base64
from mcp_server.core.registry import mcp_tool, registry
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
def create_or_update_binary_file(
    client: GitHubClient,
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str = "main"
) -> dict:
    """Создать или обновить файл из base64."""
    
    # 1. Декодируем base64
    try:
        decoded_content = base64.b64decode(content).decode('utf-8')
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Ошибка декодирования base64: {str(e)}"
            }]
        }
    
    # 2. Получаем инструмент create_or_update_file из реестра
    tool = registry.get("create_or_update_file")
    if not tool or not tool.handler:
        return {
            "content": [{
                "type": "text",
                "text": "❌ Ошибка: Инструмент create_or_update_file не найден"
            }]
        }
    
    # 3. Вызываем create_or_update_file
    try:
        result = tool.handler(
            client=client,
            owner=owner,
            repo=repo,
            path=path,
            content=decoded_content,
            message=message,
            branch=branch
        )
        
        # result — это dict вида {"content": [{"type": "text", "text": "..."}]}
        # Извлекаем текст из результата
        if isinstance(result, dict) and "content" in result:
            result_text = result["content"][0]["text"] if result["content"] else "✅ Файл сохранён"
        else:
            result_text = f"✅ Файл {path} успешно создан/обновлён в {owner}/{repo} (ветка: {branch})"
        
        return {
            "content": [{
                "type": "text",
                "text": result_text
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Ошибка при сохранении: {str(e)}"
            }]
        }
