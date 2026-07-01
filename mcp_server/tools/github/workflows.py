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
            return _safe_utf8("Нет запусков workflow")

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

        return _safe_utf8("\n".join(lines))
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

        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_full_workflow_logs",
    description="Получает ПОЛНЫЕ логи всех jobs для конкретного workflow run",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
    },
    required=["owner", "repo", "run_id"],
)
def get_full_workflow_logs(client: GitHubClient, owner: str, repo: str, run_id: int) -> str:
    """Get full workflow logs."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)

        lines = [f"📋 ПОЛНЫЕ ЛОГИ для запуска #{run_id}", f"Всего jobs: {len(jobs)}", "=" * 60, ""]

        for job in jobs:
            job_name = job.get("name") or "unknown"
            lines.append(f"📦 JOB: {job_name}")
            lines.append(f"   Статус: {job.get('status')}")
            lines.append(f"   Результат: {job.get('conclusion')}")

            job_id = job.get("id")
            if job_id:
                try:
                    logs = client.get_job_logs(owner, repo, job_id)
                    log_lines = logs.split("\n")
                    lines.append(f"\n   📄 ЛОГИ (первые 50 строк из {len(log_lines)}):")
                    lines.append("   " + "-" * 40)
                    # Обрезаем логи до 50 строк и экранируем проблемные символы
                    for line in log_lines[:50]:
                        lines.append(f"   {_safe_utf8(line)}")
                    if len(log_lines) > 50:
                        lines.append(f"   ... (обрезано, всего {len(log_lines)} строк)")
                    lines.append("   " + "-" * 40)
                except Exception as e:
                    lines.append(f"   ⚠️ Не удалось получить логи: {e}")

            lines.append("")
            lines.append("-" * 40)
            lines.append("")

        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_workflow_by_file",
    description="Получает последние запуски workflow по имени YAML файла",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "filename": {"type": "string", "description": "Имя файла workflow (например build.yml)"},
    },
    required=["owner", "repo", "filename"],
)
def get_workflow_by_file(client: GitHubClient, owner: str, repo: str, filename: str) -> str:
    """Get workflow runs by filename."""
    try:
        workflows = client.get_workflows(owner, repo)
        target = None
        for wf in workflows:
            if wf.get("name") == filename or wf.get("path", "").endswith(filename):
                target = wf
                break

        if not target:
            return _safe_utf8(f"❌ Workflow '{filename}' не найден")

        runs = client.get_workflow_runs_by_id(owner, repo, target["id"])

        lines = [
            f"📄 Workflow: {target['name']}",
            f"📁 Файл: {target['path']}",
            "",
            f"📋 Последние {len(runs)} запусков:",
        ]

        for run in runs:
            conclusion = run.get("conclusion", "pending")
            icon = {"success": "✅", "failure": "❌"}.get(conclusion, "⏳")
            lines.append(
                f"  {icon} #{run['id']} - {(run.get('head_sha') or '')[:7]} "
                f"- {conclusion} - {run.get('created_at', '')[:10]}"
            )

        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")
