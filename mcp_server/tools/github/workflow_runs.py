"""GitHub Actions workflow runs tools."""

import re

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient
from .workflow_attempts import PARAMETERS as ATTEMPT_PARAMETERS, snapshot
from .workflow_attempt_logs import PARAMETERS as LOG_PARAMETERS, query as query_logs


def _safe_utf8(text: str) -> str:
    """Безопасно преобразует строку в UTF-8, заменяя проблемные символы."""
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


def _decode_logs(raw) -> str:
    """Приводит логи к str, если это plain text (не ZIP)."""
    if isinstance(raw, bytes):
        return raw.decode('utf-8', errors='replace')
    return raw if isinstance(raw, str) else str(raw)


def _match_log_files(files: dict, job_name: str = None, step_name: str = None) -> dict:
    """Отбирает файлы логов по job_name/step_name (подстроки имени файла).

    Файлы в архиве называются как "<job>/<N>_<step>.txt".
    """
    job_needle = (job_name or "").strip().lower()
    step_needle = (step_name or "").strip().lower()
    out = {}
    for name, text in files.items():
        low = name.lower()
        if job_needle and job_needle not in low:
            continue
        if step_needle and step_needle not in low:
            continue
        out[name] = text
    return out


def _collect_lines(files: dict, job_name: str = None, step_name: str = None):
    """Собирает строки выбранных файлов, вставляя заголовки. Возвращает (lines, matched)."""
    matched = _match_log_files(files, job_name, step_name)
    lines = []
    for name, text in matched.items():
        lines.append(f"===== {name} =====")
        lines.extend(text.split("\n"))
    return lines, matched


@mcp_tool(
    name="list_workflow_runs",
    description="Получает список запусков workflow с run_id, статусами и временем (с пагинацией и фильтром status).",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "limit": {"type": "integer", "description": "Количество запусков на странице (по умолчанию 10, максимум 100)"},
        "page": {"type": "integer", "description": "Номер страницы (по умолчанию 1)"},
        "status": {"type": "string", "description": "Фильтр: completed|in_progress|queued|success|failure|cancelled и т.д."},
    },
    required=["owner", "repo"],
)
def list_workflow_runs(client: GitHubClient, owner: str, repo: str, limit: int = 10,
                       page: int = 1, status: str = None):
    """Получает список запусков workflow с пагинацией."""
    try:
        per_page = max(1, min(int(limit), 100))
        page = max(1, int(page))
        runs = client.get_workflow_runs(
            owner, repo, per_page=per_page, page=page, status=status
        )

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
                "head_sha": run.get("head_sha"),
                "run_attempt": run.get("run_attempt"),
                "run_started_at": run.get("run_started_at"),
                "completed_at": run.get("completed_at")
            })

        return {
            "owner": owner,
            "repo": repo,
            "page": page,
            "status_filter": status,
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
            "head_sha": run.get("head_sha"),
                "run_attempt": run.get("run_attempt"),
                "run_started_at": run.get("run_started_at"),
                "completed_at": run.get("completed_at")
        }
    except Exception as e:
        return {"error": _safe_utf8(str(e))}


@mcp_tool(
    name="get_workflow_run_status",
    description="Снимок выбранной попытки workflow; latest фиксируется при чтении, bounded jobs/steps, complete показывает полноту.",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        **ATTEMPT_PARAMETERS,
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_run_status(client: GitHubClient, owner: str, repo: str, run_id: int,
                           run_attempt: int = None, max_pages: int = 5,
                           max_jobs: int = 20, max_steps: int = 100):
    """Return an attempt-pinned, non-transactional snapshot; no polling."""
    return snapshot(client, owner, repo, run_id, run_attempt, max_pages,
                    max_jobs, max_steps, flat=False)

@mcp_tool(
    name="get_workflow_run_steps",
    description="Снимок выбранной попытки workflow; latest фиксируется при чтении, bounded jobs/steps, complete показывает полноту.",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        **ATTEMPT_PARAMETERS,
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_run_steps(client: GitHubClient, owner: str, repo: str, run_id: int,
                           run_attempt: int = None, max_pages: int = 5,
                           max_jobs: int = 20, max_steps: int = 100):
    """Return an attempt-pinned, non-transactional snapshot; no polling."""
    return snapshot(client, owner, repo, run_id, run_attempt, max_pages,
                    max_jobs, max_steps, flat=True)

@mcp_tool(
    name="read_run_logs_offset",
    description="Логи выбранной попытки: bounded ZIP/ответ; combined step filter по доказанным timeline/markers, ambiguous явно; без смешивания reruns.",
    parameters={
        "owner": {"type":"string"}, "repo": {"type":"string"}, "run_id": {"type":"integer"},
        "job_name": {"type":"string","description":"Фильтр только имени job (подстрока)"},
        "step_name": {"type":"string","description":"Фильтр шага; combined timeline/markers или явный ambiguous/unsupported"},
        **LOG_PARAMETERS,
        "offset": {"type":"integer","description":"0-based offset 0–100000"}, "limit": {"type":"integer","description":"Лимит строк 1–1000; alias max_lines"},
    },
    required=['owner', 'repo', 'run_id'],
)
def read_run_logs_offset(client: GitHubClient, **kwargs):
    """Attempt-aware reader; source errors are not successful empty searches."""
    if "limit" in kwargs:
        kwargs["max_lines"] = kwargs.pop("limit")
    return query_logs(client, "offset", **kwargs)

@mcp_tool(
    name="grep_run_logs",
    description="Логи выбранной попытки: bounded ZIP/ответ; combined step filter по доказанным timeline/markers, ambiguous явно; без смешивания reruns.",
    parameters={
        "owner": {"type":"string"}, "repo": {"type":"string"}, "run_id": {"type":"integer"},
        "job_name": {"type":"string","description":"Фильтр только имени job (подстрока)"},
        "step_name": {"type":"string","description":"Фильтр шага; combined timeline/markers или явный ambiguous/unsupported"},
        **LOG_PARAMETERS,
        "pattern": {"type":"string","description":"Regex до 256 символов; worker timeout 3s"}, "context": {"type":"integer","description":"Контекст 0–20, default 3"}, "max_matches": {"type":"integer","description":"Совпадения 1–500, default 50"}, "case_sensitive": {"type":"boolean"},
    },
    required=['owner', 'repo', 'run_id', 'pattern'],
)
def grep_run_logs(client: GitHubClient, **kwargs):
    """Attempt-aware reader; source errors are not successful empty searches."""
    return query_logs(client, "grep", **kwargs)

@mcp_tool(
    name="get_run_logs_by_step",
    description="Логи выбранной попытки: bounded ZIP/ответ; combined step filter по доказанным timeline/markers, ambiguous явно; без смешивания reruns.",
    parameters={
        "owner": {"type":"string"}, "repo": {"type":"string"}, "run_id": {"type":"integer"},
        "job_name": {"type":"string","description":"Фильтр только имени job (подстрока)"},
        "step_name": {"type":"string","description":"Фильтр шага; combined timeline/markers или явный ambiguous/unsupported"},
        **LOG_PARAMETERS,
        "direction": {"type":"string","description":"head|tail, default head"}, "start_time": {"type":"string","description":"Строка-маркер начала; не найдено => start_time_not_found"},
    },
    required=['owner', 'repo', 'run_id', 'step_name'],
)
def get_run_logs_by_step(client: GitHubClient, **kwargs):
    """Attempt-aware reader; source errors are not successful empty searches."""
    return query_logs(client, "step", **kwargs)

@mcp_tool(name="get_step_logs_via_checks",
    description="Deprecated checks name: bounded attempt step logs; НЕ SHA-wide Check Runs.",
    parameters={"owner":{"type":"string"},"repo":{"type":"string"},"run_id":{"type":"integer"},
        "step_name":{"type":"string"},"job_name":{"type":"string"},**LOG_PARAMETERS},
    required=["owner","repo","run_id","step_name"])
def get_step_logs_via_checks(client,owner,repo,run_id,step_name,run_attempt=None,max_pages=5,
        max_lines=200,max_chars=16000,job_name=None):
    result=query_logs(client,"step",owner=owner,repo=repo,run_id=run_id,step_name=step_name,
        run_attempt=run_attempt,max_pages=max_pages,max_lines=max_lines,max_chars=max_chars,job_name=job_name)
    result['source']='attempt_step_logs_not_checks'
    result['deprecated_alias']=True
    return result
