"""MCP tool: create_or_update_binary_file — создаёт/обновляет файл из base64."""

import base64
import json
from mcp_server.core.registry import mcp_tool, registry
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="create_or_update_binary_file",
    description="Creates or updates a file in the repository from base64 string (no escaping issues).",
    parameters={
        "owner": {"type": "string", "description": "Repository owner"},
        "repo": {"type": "string", "description": "Repository name"},
        "path": {"type": "string", "description": "Path to the file in the repository"},
        "content": {"type": "string", "description": "File content in base64 format"},
        "message": {"type": "string", "description": "Commit message"},
        "branch": {"type": "string", "description": "Branch (default: main)"}
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
    """Create or update a file from base64."""
    
    print(f"[create_or_update_binary_file] owner={owner}, repo={repo}, path={path}, branch={branch}")
    
    # 1. Декодируем base64
    try:
        decoded_content = base64.b64decode(content).decode('utf-8')
        print(f"[create_or_update_binary_file] Base64 decoded OK")
    except Exception as e:
        print(f"[create_or_update_binary_file] Base64 decode error: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error decoding base64: {str(e)}"
            }]
        }
    
    # 2. Получаем инструмент create_or_update_file из реестра
    tool = registry.get("create_or_update_file")
    if not tool or not tool.handler:
        print(f"[create_or_update_binary_file] Tool create_or_update_file not found")
        return {
            "content": [{
                "type": "text",
                "text": "Error: Tool create_or_update_file not found"
            }]
        }
    
    print(f"[create_or_update_binary_file] Calling create_or_update_file...")
    
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
        
        # Диагностика
        print(f"[create_or_update_binary_file] result type: {type(result)}")
        
        # Возвращаем результат
        return result
        
    except Exception as e:
        print(f"[create_or_update_binary_file] Exception: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error: {str(e)}"
            }]
        }
