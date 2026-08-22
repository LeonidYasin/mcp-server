"""GitHub Actions workflow runs tools."""

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
    description="Получает список последних запусков workflow с run_id, статусами и временем.",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "limit": {"type": "integer", "description": "Количество запусков (по умолчанию 10)"},
    },
    required=["owner", "repo"],
)
def list_workflow_runs(client: GitHubClient, owner: str, repo: str, limit: int = 10):
    """Получает список последних запусков workflow."""
    try:
        runs = client.get_workflow_runs(owner, repo, per_page=limit)
        
        result = []
        for run in runs:
            result.append({
                "run_id": run.get("id"),
                "name": run.get("name"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "event": run.get("event"),
                "created_at": run.get("created_at"),
                "updated_at": run.get("updated_at"),
                "workflow_id": run.get("workflow_id"),
                "head_branch": run.get("head_branch"),
                "head_sha": run.get("head_sha")
            })
        
        return {
            "owner": owner,
            "repo": repo,
            "total": len(result),
            "runs": result
        }
    except Exception as e:
        return {"error": _safe_utf8(str(e))}


@mcp_tool(
    name="get_latest_run_id",
    description="Получает run_id последнего запуска workflow (успешного или нет).",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
    },
    required=["owner", "repo"],
)
def get_latest_run_id(client: GitHubClient, owner: str, repo: str):
    """Получает run_id последнего запуска workflow."""
    try:
        runs = client.get_workflow_runs(owner, repo, per_page=1)
        if not runs:
            return {"error": "No workflow runs found"}
        
        run = runs[0]
        return {
            "run_id": run.get("id"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "created_at": run.get("created_at"),
            "head_sha": run.get("head_sha")
        }
    except Exception as e:
        return {"error": _safe_utf8(str(e))}


@mcp_tool(
    name="get_workflow_run_steps",
    description="Получает список всех шагов для указанного запуска workflow с их статусами.",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_run_steps(client: GitHubClient, owner: str, repo: str, run_id: int):
    """Получает список всех шагов для указанного запуска workflow."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        if not jobs:
            return {"error": "No jobs found for this run"}
        
        result = []
        for job in jobs:
            job_name = job.get("name", "")
            job_id = job.get("id")
            for step in job.get("steps", []):
                result.append({
                    "job": job_name,
                    "job_id": job_id,
                    "step": step.get("name", ""),
                    "number": step.get("number"),
                    "status": step.get("status"),
                    "conclusion": step.get("conclusion"),
                    "started_at": step.get("started_at"),
                    "completed_at": step.get("completed_at")
                })
        
        return {
            "owner": owner,
            "repo": repo,
            "run_id": run_id,
            "total_steps": len(result),
            "steps": result
        }
    except Exception as e:
        return {"error": _safe_utf8(str(e))}


@mcp_tool(
    name="get_run_logs_by_step",
    description="Получает логи конкретного шага workflow по имени шага.",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "step_name": {"type": "string", "description": "Название шага (часть имени, регистр не важен)"},
        "max_lines": {"type": "integer", "description": "Максимум строк для вывода (по умолчанию 200)"},
        "start_time": {"type": "string", "description": "ISO 8601 время начала (например 2026-08-22T10:30:00Z)"},
    },
    required=["owner", "repo", "run_id", "step_name"],
)
def get_run_logs_by_step(
    client: GitHubClient,
    owner: str,
    repo: str,
    run_id: int,
    step_name: str,
    max_lines: int = 200,
    start_time: str = None
):
    """Получает логи конкретного шага workflow по имени шага."""
    try:
        # Получаем логи через client
        logs = client.get_workflow_run_logs(owner, repo, run_id)
        
        # Ищем нужный шаг в логах
        log_lines = logs.split('\n')
        
        # Если указано время начала, фильтруем логи после этого времени
        if start_time:
            filtered_lines = []
            found_start = False
            for line in log_lines:
                if start_time in line:
                    found_start = True
                if found_start:
                    filtered_lines.append(line)
            log_lines = filtered_lines
        
        # Ищем шаг по имени
        step_lines = []
        in_step = False
        for line in log_lines:
            if step_name.lower() in line.lower():
                in_step = True
            if in_step:
                step_lines.append(line)
                # Останавливаемся после max_lines строк
                if len(step_lines) >= max_lines:
                    break
        
        if not step_lines:
            return {"error": f"No logs found for step: {step_name}"}
        
        return {
            "run_id": run_id,
            "step_name": step_name,
            "total_lines": len(step_lines),
            "returned_lines": min(max_lines, len(step_lines)),
            "start_time": start_time,
            "logs": step_lines[:max_lines]
        }
    except Exception as e:
        return {"error": _safe_utf8(str(e))}


@mcp_tool(
    name="get_step_logs_via_checks",
    description="Получает логи шага через GitHub Checks API.",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "step_name": {"type": "string", "description": "Название шага (часть имени, регистр не важен)"},
    },
    required=["owner", "repo", "run_id", "step_name"],
)
def get_step_logs_via_checks(client: GitHubClient, owner: str, repo: str, run_id: int, step_name: str):
    """Получает логи шага через GitHub Checks API."""
    try:
        # Получаем информацию о запуске
        run = client.get_workflow_run(owner, repo, run_id)
        commit_sha = run.get("head_sha")
        if not commit_sha:
            return {"error": "No commit SHA found"}
        
        # Получаем check-runs для коммита
        check_runs = client.get_check_runs(owner, repo, commit_sha)
        
        # Ищем check-run с нужным именем шага
        found_check = None
        for check in check_runs:
            check_name = check.get("name", "").lower()
            if step_name.lower() in check_name:
                found_check = check
                break
        
        if not found_check:
            return {
                "error": f"No check-run found for step: {step_name}",
                "available_checks": [c.get("name") for c in check_runs[:10]]
            }
        
        return {
            "run_id": run_id,
            "step_name": step_name,
            "commit_sha": commit_sha,
            "check_run": {
                "name": found_check.get("name"),
                "status": found_check.get("status"),
                "conclusion": found_check.get("conclusion"),
                "started_at": found_check.get("started_at"),
                "completed_at": found_check.get("completed_at"),
                "output": {
                    "title": found_check.get("output", {}).get("title"),
                    "summary": found_check.get("output", {}).get("summary"),
                    "text": found_check.get("output", {}).get("text"),
                    "annotations_count": len(found_check.get("output", {}).get("annotations", []))
                }
            },
            "note": "Checks API returns truncated output (up to 65535 characters). For full logs, use get_run_logs_by_step."
        }
    except Exception as e:
        return {"error": _safe_utf8(str(e))}
