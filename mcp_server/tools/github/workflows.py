"""Workflow tools: get_latest_workflow_error, get_workflow_run_logs, get_full_workflow_logs, get_workflow_by_file."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    """Безопасно преобразует строку в UTF-8, заменяя проблемные символы."""
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


@mcp_tool(
    name="get_latest_workflow_error",
    description="Получает ошибку последней сборки через GitHub API",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
    },
    required=["owner", "repo"],
)
def get_latest_workflow_error(client: GitHubClient, owner: str, repo: str) -> str:
    """Get latest workflow error."""
    try:
        runs = client.get_workflow_runs(owner, repo, per_page=1)
        if not runs:
            return "Нет запусков workflow"

        run = runs[0]
        run_id = run.get("id")
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        failed = [j for j in jobs if j.get("conclusion") == "failure"]

        lines = [
            f"🏃 Последний запуск: #{run_id}",
            f"📌 Статус: {run.get('status')}",
            f"📊 Результат: {run.get('conclusion')}",
            f"🌿 Ветка: {run.get('head_branch')}",
        ]

        if failed:
            lines.append(f"\n❌ Проваленные jobs ({len(failed)}):")
            for job in failed:
                job_name = job.get('name') or 'unknown'
                lines.append(f"  📦 {job_name}")
                for step in job.get("steps", []):
                    if step.get("conclusion") == "failure":
                        step_name = step.get('name') or 'unknown step'
                        lines.append(f"    ❌ {step_name}")
        else:
            lines.append("\n✅ Все проверки успешны")

        result = "\n".join(lines)
        return _safe_utf8(result)
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_workflow_run_logs",
    description="Получает логи и причину падения конкретного workflow run",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_run_logs(client: GitHubClient, owner: str, repo: str, run_id: int) -> str:
    """Get workflow run logs."""
    try:
        run = client.get_workflow_run(owner, repo, run_id)
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        failed = [j for j in jobs if j.get("conclusion") == "failure"]

        lines = [
            f"🏃 Запуск #{run_id}",
            f"📌 Статус: {run.get('status')}",
            f"📊 Результат: {run.get('conclusion')}",
            f"🌿 Ветка: {run.get('head_branch')}",
            f"🔖 Коммит: {(run.get('head_sha') or '')[:7]}",
            "",
        ]

        if failed:
            lines.append("❌ НАЙДЕНЫ ОШИБКИ:")
            for job in failed:
                job_name = job.get('name') or 'unknown'
                lines.append(f"\n📦 Job: {job_name}")
                lines.append(f"   Статус: {job.get('status')}")
                lines.append("   🔍 Проваленные шаги:")
                for step in job.get("steps", []):
                    if step.get("conclusion") == "failure":
                        step_name = step.get('name') or 'unknown step'
                        lines.append(f"   ❌ {step_name}")
        else:
            lines.append("✅ Все проверки прошли успешно!")

        result = "\n".join(lines)
        return _safe_utf8(result)
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


# Аналогично исправьте остальные функции (get_full_workflow_logs, get_workflow_by_file)
# Везде, где есть return, оберните в _safe_utf8()
