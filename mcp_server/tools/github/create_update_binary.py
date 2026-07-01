"""MCP tool: create_or_update_binary_file — создаёт/обновляет файл из base64."""

import base64
import json
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
    
    print(f"🔍 [create_or_update_binary_file] owner={owner}, repo={repo}, path={path}, branch={branch}")
    
    # 1. Декодируем base64
    try:
        decoded_content = base64.b64decode(content).decode('utf-8')
        print(f"✅ [create_or_update_binary_file] Base64 decoded, length={len(decoded_content)}")
    except Exception as e:
        print(f"❌ [create_or_update_binary_file] Base64 decode error: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Ошибка декодирования base64: {str(e)}"
            }]
        }
    
    # 2. Получаем инструмент create_or_update_file из реестра
    tool = registry.get("create_or_update_file")
    if not tool or not tool.handler:
        print(f"❌ [create_or_update_binary_file] Tool create_or_update_file not found")
        return {
            "content": [{
                "type": "text",
                "text": "❌ Ошибка: Инструмент create_or_update_file не найден"
            }]
        }
    
    print(f"✅ [create_or_update_binary_file] Found create_or_update_file, calling handler...")
    
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
        
        # ДИАГНОСТИКА
        print(f"📊 [create_or_update_binary_file] RESULT TYPE: {type(result)}")
        print(f"📊 [create_or_update_binary_file] RESULT: {result}")
        
        if isinstance(result, dict):
            print(f"📊 [create_or_update_binary_file] result keys: {list(result.keys())}")
            if "content" in result:
                print(f"📊 [create_or_update_binary_file] content: {result['content']}")
        
        # Просто возвращаем результат
        return result
        
    except Exception as e:
        print(f"❌ [create_or_update_binary_file] Exception: {e}")
        import traceback
        traceback.print_exc()
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Ошибка при сохранении: {str(e)}"
            }]
        }
