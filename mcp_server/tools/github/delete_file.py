"""MCP tool: delete_file - delete a file from a GitHub repository."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="delete_file",
    description="Удаляет файл из GitHub репозитория. Требует SHA файла (получи через get_file_contents).",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу в репозитории"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "branch": {"type": "string", "description": "Ветка"},
        "sha": {"type": "string", "description": "SHA файла для удаления"},
    },
)
async def delete_file(
    client: GitHubClient,
    owner: str,
    repo: str,
    path: str,
    message: str,
    branch: str,
    sha: str,
) -> dict:
    """Delete a file from a GitHub repository."""
    result = await client.delete_file(
        owner=owner,
        repo=repo,
        path=path,
        message=message,
        branch=branch,
        sha=sha,
    )
    return {
        "content": [
            {
                "type": "text",
                "text": f"File '{path}' deleted successfully from {owner}/{repo} on branch {branch}.",
            }
        ]
    }
