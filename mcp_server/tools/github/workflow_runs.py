"""Workflow runs tools: list_workflow_runs, get_latest_run_id, get_run_logs_by_step, get_workflow_run_steps."""

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


@mcp_tool(
    name="get_workflow_run_steps",
    description="Получает список всех шагов для указанного запуска workflow с их статусами",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_run_steps(client: GitHubClient, owner: str, repo: str, run_id: int) -> str:
    """Get list of all steps for a workflow run with their statuses."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        if not jobs:
            return _safe_utf8(f"❌ Нет jobs для запуска #{run_id}")

        lines = [
            f"📋 Шаги для запуска #{run_id}:",
            "",
        ]

        for job in jobs:
            job_name = job.get("name", "unknown")
            job_status = job.get("status", "unknown")
            job_conclusion = job.get("conclusion", "pending")
            lines.append(f"📦 Job: {job_name} ({job_status}/{job_conclusion})")

            for step in job.get("steps", []):
                step_name = step.get("name", "unknown")
                step_status = step.get("status", "unknown")
                step_conclusion = step.get("conclusion", "pending")
                step_number = step.get("number", "?")
                icon = {"success": "✅", "failure": "❌", "cancelled": "⚠️"}.get(step_conclusion, "⏳")
                lines.append(f"  {icon} [{step_number}] {step_name} - {step_status}/{step_conclusion}")

            lines.append("")

        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_run_logs_by_step",
    description="Получает логи конкретного шага workflow по имени шага",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "step_name": {"type": "string", "description": "Название шага (часть имени, регистр не важен)"},
        "max_lines": {"type": "integer", "description": "Максимум строк для вывода (по умолчанию 200)"},
    },
    required=["owner", "repo", "run_id", "step_name"],
)
def get_run_logs_by_step(client: GitHubClient, owner: str, repo: str, run_id: int, step_name: str, max_lines: int = 200) -> str:
    """Get logs for a specific step by name using ##[group] and ##[endgroup] markers."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        target_step = None
        target_job = None
        target_job_id = None

        # Находим нужный шаг
        for job in jobs:
            for step in job.get("steps", []):
                if step_name.lower() in step.get("name", "").lower():
                    target_step = step
                    target_job = job
                    target_job_id = job.get("id")
                    break
            if target_step:
                break

        if not target_step or not target_job_id:
            return _safe_utf8(f"❌ Шаг '{step_name}' не найден в запуске #{run_id}")

        # Получаем полные логи job
        logs = client.get_job_logs(owner, repo, target_job_id)
        log_lines = logs.split("\n")

        step_name_clean = target_step.get("name", "")
        
        # Ищем логи шага по маркерам ##[group] и ##[endgroup]
        step_logs = []
        in_step = False
        found_step = False
        
        for line in log_lines:
            # Проверяем начало группы шага
            if "##[group]" in line and step_name_clean.lower() in line.lower():
                in_step = True
                found_step = True
                step_logs.append(line)
                continue
            elif in_step and "##[endgroup]" in line:
                step_logs.append(line)
                in_step = False
                break
            elif in_step:
                step_logs.append(line)

        # Если не нашли по маркерам, пробуем найти по имени в логе
        if not found_step:
            in_step = False
            for line in log_lines:
                if step_name_clean.lower() in line.lower():
                    in_step = True
                    found_step = True
                    step_logs.append(line)
                    continue
                elif in_step and line.strip() and not line.startswith(" "):
                    break
                elif in_step:
                    step_logs.append(line)

        # Если всё равно не нашли, возвращаем все логи с предупреждением
        if not found_step or not step_logs:
            step_logs = log_lines
            step_logs.append("\n⚠️ Не удалось выделить конкретный шаг, показаны все логи job")

        # Обрезаем до max_lines
        total_lines = len(step_logs)
        if total_lines > max_lines:
            step_logs = step_logs[:max_lines]
            step_logs.append(f"\n... (обрезано, всего {total_lines} строк, показано {max_lines})")

        lines = [
            f"📋 Логи шага '{target_step.get('name')}' (job: {target_job.get('name')})",
            f"📦 Job ID: {target_job_id}",
            f"📊 Статус шага: {target_step.get('conclusion')}",
            f"🔢 Номер шага: {target_step.get('number', '?')}",
            f"📄 Всего строк в логе шага: {total_lines}",
            "",
            "---",
            "",
        ]
        lines.extend(step_logs)

        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")
