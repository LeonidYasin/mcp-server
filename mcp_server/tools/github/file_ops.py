"""File operations tools: get_file_contents, create_or_update_file, delete_file."""

import base64
import json

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="get_file_contents",
    description="Получает содержимое файла из репозитория",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу в репозитории"},
        "ref": {"type": "string", "description": "Ветка или коммит (опционально)"},
    },
    required=["owner", "repo", "path"],
)
def get_file_contents(client: GitHubClient, owner: str, repo: str, path: str, ref: str | None = None) -> str:
    """Get file contents from a GitHub repository."""
    try:
        data = client.get_file(owner, repo, path, ref)
        if "content" in data:
            decoded = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return decoded
        elif isinstance(data, list):
            # Directory listing
            items = [f"{'📁' if item['type'] == 'dir' else '📄'} {item['name']}" for item in data]
            return "\n".join(items)
        else:
            return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"❌ Ошибка: {e}"


@mcp_tool(
    name="create_or_update_file",
    description="Создаёт или обновляет ТЕКСТОВЫЙ файл в репозитории",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "content": {"type": "string", "description": "Содержимое файла"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "branch": {"type": "string", "description": "Ветка"},
        "sha": {"type": "string", "description": "SHA файла при обновлении"},
    },
    required=["owner", "repo", "path", "content", "message", "branch"],
)
def create_or_update_file(
    client: GitHubClient,
    owner: str, repo: str, path: str, content: str,
    message: str, branch: str, sha: str | None = None
) -> str:
    """Create or update a file."""
    try:
        client.create_or_update_file(owner, repo, path, content, message, branch, sha)
        return f"✅ Файл {path} успешно сохранён в {owner}/{repo} ({branch})"
    except Exception as e:
        return f"❌ Ошибка: {e}"


@mcp_tool(
    name="delete_file",
    description="Удаляет файл из GitHub репозитория (автоматически получает SHA)",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "branch": {"type": "string", "description": "Ветка"},
    },
    required=["owner", "repo", "path", "message", "branch"],
)
def delete_file(
    client: GitHubClient,
    owner: str, repo: str, path: str,
    message: str, branch: str
) -> str:
    """Delete a file, auto-fetching SHA."""
    try:
        sha = client.get_file_sha(owner, repo, path, branch)
        if not sha:
            return f"❌ Файл {path} не найден в {owner}/{repo}"
        client.delete_file(owner, repo, path, message, branch, sha)
        return f"✅ Файл {path} успешно удалён из {owner}/{repo} ({branch})"
    except Exception as e:
        return f"❌ Ошибка: {e}"
