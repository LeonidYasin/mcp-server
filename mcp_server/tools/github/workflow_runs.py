"""Workflow runs tools: list_workflow_runs, get_latest_run_id."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    """Безопасно преобразует строку в UTF-8, заменяя проблемные символы."""
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


@mcp_tool(
    name="list_workflow_runs",
    description="Получает список последних запусков workflow с run_id, статусами и временем",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "limit": {"type": "integer", "description": "Количество запусков (по умолчанию 10)"},
    },
    required=["owner", "repo"],
)
def list_workflow_runs(client: GitHubClient, owner: str, repo: str, limit: int = 10) -> str:
    """List recent workflow runs with run_id and status."""
    try:
        runs = client.get_workflow_runs(owner, repo, per_page=limit)
        if not runs:
            return _safe_utf8("Нет запусков workflow")

        lines = [
            f"📋 Последние {len(runs)} запусков workflow:",
            "",
        ]

        for run in runs:
            run_id = run.get("id")
            status = run.get("status", "unknown")
            conclusion = run.get("conclusion", "pending")
            created_at = run.get("created_at", "")[:16].replace("T", " ")
            head_sha = (run.get("head_sha") or "")[:7]
            branch = run.get("head_branch", "unknown")
            name = run.get("name", "unknown")

            icon = {"success": "✅", "failure": "❌", "cancelled": "⚠️"}.get(conclusion, "⏳")

            lines.append(
                f"  {icon} #{run_id} [{name}] - {status}/{conclusion} - "
                f"{branch} @ {head_sha} - {created_at}"
            )

        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_latest_run_id",
    description="Получает run_id последнего запуска workflow (успешного или нет)",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
    },
    required=["owner", "repo"],
)
def get_latest_run_id(client: GitHubClient, owner: str, repo: str) -> str:
    """Get the latest workflow run ID."""
    try:
        runs = client.get_workflow_runs(owner, repo, per_page=1)
        if not runs:
            return _safe_utf8("Нет запусков workflow")

        run = runs[0]
        lines = [
            f"🏃 Последний запуск:",
            f"  run_id: {run.get('id')}",
            f"  статус: {run.get('status')}",
            f"  результат: {run.get('conclusion')}",
            f"  ветка: {run.get('head_branch')}",
            f"  коммит: {(run.get('head_sha') or '')[:7]}",
            f"  время: {(run.get('created_at') or '')[:16].replace('T', ' ')}",
        ]
        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")
