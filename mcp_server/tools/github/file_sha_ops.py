"""File operations with automatic SHA handling."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


@mcp_tool(
    name="create_or_update_file_with_sha",
    description="Создаёт или обновляет файл, автоматически получая SHA для обновления",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "content": {"type": "string", "description": "Содержимое файла"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "branch": {"type": "string", "description": "Ветка (по умолчанию main)"},
    },
    required=["owner", "repo", "path", "content", "message", "branch"],
)
def create_or_update_file_with_sha(client: GitHubClient, owner: str, repo: str, path: str, content: str, message: str, branch: str = "main") -> str:
    """Create or update a file, automatically getting SHA if needed."""
    try:
        existing_sha = None
        action = "created"
        
        # Try to get existing file SHA
        try:
            existing = client.get_file(owner, repo, path, branch)
            if existing and existing.get('sha'):
                existing_sha = existing.get('sha')
                action = "updated"
        except Exception:
            pass
        
        # Create or update file
        result = client.create_or_update_file(owner, repo, path, content, message, branch, existing_sha)
        
        lines = [
            f"✅ File processed: {path}",
            f"📦 Repository: {owner}/{repo}",
            f"🌿 Branch: {branch}",
            f"📝 Action: {action}",
        ]
        
        if action == "updated":
            lines.append(f"🔄 Updated existing file (SHA: {existing_sha[:7]}...)")
        else:
            lines.append("✨ Created new file")
        
        if result and result.get('content', {}).get('sha'):
            new_sha = result['content']['sha']
            lines.append(f"🔑 New SHA: {new_sha[:7]}...")
        
        return _safe_utf8('\n'.join(lines))
        
    except Exception as e:
        return _safe_utf8(f"❌ Error: {e}")
