"""Commit tools: list_commits, get_commit_status."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="list_commits",
    description="Получает список коммитов репозитория (с пагинацией)",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "sha": {"type": "string", "description": "Ветка или коммит (опционально)"},
        "limit": {"type": "integer", "description": "Сколько на странице (по умолчанию 10, максимум 100)"},
        "page": {"type": "integer", "description": "Номер страницы (по умолчанию 1)"},
    },
    required=["owner", "repo"],
)
def list_commits(client: GitHubClient, owner: str, repo: str, sha: str | None = None,
                 limit: int = 10, page: int = 1) -> str:
    """List commits with pagination."""
    try:
        per_page = max(1, min(int(limit), 100))
        page = max(1, int(page))
        commits = client.list_commits(owner, repo, sha, per_page=per_page, page=page)
        if not commits:
            return f"Нет коммитов (стр. {page})"
        lines = [f"Коммиты, стр. {page}, {len(commits)} шт:"]
        for c in commits:
            sha_short = c.get("sha", "")[:7]
            msg = c.get("commit", {}).get("message", "").splitlines()[0][:80]
            lines.append(f"{sha_short} - {msg}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Ошибка: {e}"


@mcp_tool(
    name="get_commit_status",
    description="Получает статус проверок для конкретного коммита",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "sha": {"type": "string", "description": "SHA коммита"},
    },
    required=["owner", "repo", "sha"],
)
def get_commit_status(client: GitHubClient, owner: str, repo: str, sha: str) -> str:
    """Get commit status."""
    try:
        status = client.get_commit_status(owner, repo, sha)
        checks = client.get_check_runs(owner, repo, sha)

        lines = [f"🔖 Коммит: {sha}", f"📊 Статус: {status.get('state', 'unknown')}", ""]

        if checks:
            failed = [c for c in checks if c.get("conclusion") == "failure"]
            pending = [c for c in checks if c.get("status") == "in_progress"]
            success = [c for c in checks if c.get("conclusion") == "success"]

            if failed:
                lines.append(f"❌ Провалено: {len(failed)}")
                for c in failed:
                    lines.append(f"   - {c.get('name')}")
            if pending:
                lines.append(f"⏳ В процессе: {len(pending)}")
            if success:
                lines.append(f"✅ Успешно: {len(success)}")
        else:
            lines.append("ℹ️ Нет проверок")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Ошибка: {e}"
