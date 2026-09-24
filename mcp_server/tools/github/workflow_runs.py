"""GitHub Actions workflow runs tools."""

import re

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


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
                "head_sha": run.get("head_sha")
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
            "head_sha": run.get("head_sha")
        }
    except Exception as e:
        return {"error": _safe_utf8(str(e))}


@mcp_tool(
    name="get_workflow_run_status",
    description=(
        "Мгновенный (неблокирующий) снимок статуса запуска workflow: "
        "status, conclusion, jobs[] со статусами/результатами и список "
        "проваленных шагов. Заменяет polling в watch_build."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_run_status(client: GitHubClient, owner: str, repo: str, run_id: int):
    """Мгновенный снимок статуса workflow run (без polling)."""
    try:
        run = client.get_workflow_run(owner, repo, run_id)
        jobs = client.get_workflow_jobs(owner, repo, run_id)

        job_list = []
        failed_steps = []
        for job in jobs:
            steps = []
            for step in job.get("steps", []):
                steps.append({
                    "name": step.get("name"),
                    "status": step.get("status"),
                    "conclusion": step.get("conclusion"),
                })
                if step.get("conclusion") == "failure":
                    failed_steps.append(f"{job.get('name')} / {step.get('name')}")
            job_list.append({
                "name": job.get("name"),
                "status": job.get("status"),
                "conclusion": job.get("conclusion"),
                "steps": steps,
            })

        return {
            "owner": owner,
            "repo": repo,
            "run_id": run_id,
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "head_branch": run.get("head_branch"),
            "head_sha": run.get("head_sha"),
            "html_url": run.get("html_url"),
            "total_jobs": len(job_list),
            "failed_steps": failed_steps,
            "jobs": job_list,
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
    name="read_run_logs_offset",
    description=(
        "Читает окно лога workflow run с произвольного смещения (offset/limit). "
        "Нужно, когда ошибка в середине/конце лога, а get_run_logs_by_step "
        "отдаёт только начало. job_name/step_name — необязательные фильтры "
        "по имени файла в архиве (<job>/<N>_<step>.txt)."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "job_name": {"type": "string", "description": "Фильтр по имени job (подстрока)"},
        "step_name": {"type": "string", "description": "Фильтр по имени шага (подстрока)"},
        "offset": {"type": "integer", "description": "С какой строки начать (0-based, по умолчанию 0)"},
        "limit": {"type": "integer", "description": "Сколько строк вернуть (по умолчанию 200, максимум 1000)"},
    },
    required=["owner", "repo", "run_id"],
)
def read_run_logs_offset(client: GitHubClient, **kwargs) -> str:
    """Читает окно лога run с произвольного смещения."""
    owner, repo, run_id = kwargs["owner"], kwargs["repo"], kwargs["run_id"]
    offset = max(0, int(kwargs.get("offset", 0)))
    limit = max(1, min(int(kwargs.get("limit", 200)), 1000))
    job_name = kwargs.get("job_name")
    step_name = kwargs.get("step_name")
    try:
        files = client.get_workflow_run_logs_files(owner, repo, run_id)
        if not files:
            return f"❌ В архиве логов run {run_id} нет файлов."
        lines, matched = _collect_lines(files, job_name, step_name)
        if not matched:
            return (
                f"❌ Нет файлов логов по фильтру job='{job_name or '-'}' "
                f"step='{step_name or '-'}'. Доступны: {sorted(files.keys())[:20]}"
            )
        total = len(lines)
        window = lines[offset:offset + limit]
        if not window:
            return f"❌ Пустое окно: offset={offset}, limit={limit}, всего строк={total}."
        header = (
            f"📄 Логи run {run_id}: строки {offset + 1}..{offset + len(window)} из {total} "
            f"(файлов: {len(matched)})"
        )
        return header + "\n" + "\n".join(_safe_utf8(l) for l in window)
    except Exception as e:
        return f"❌ Ошибка read_run_logs_offset: {e}"


@mcp_tool(
    name="grep_run_logs",
    description=(
        "Ищет regex в логах workflow run и возвращает совпадения ±context строк. "
        "Маленький ответ — идеально для больших логов. Можно ограничить "
        "job_name/step_name. Пример pattern='e: file|Unresolved|error:'."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "pattern": {"type": "string", "description": "Regex (обязателен)"},
        "context": {"type": "integer", "description": "Строк контекста до/после (по умолчанию 3)"},
        "max_matches": {"type": "integer", "description": "Максимум совпадений (по умолчанию 50, макс 500)"},
        "job_name": {"type": "string", "description": "Фильтр по имени job (подстрока)"},
        "step_name": {"type": "string", "description": "Фильтр по имени шага (подстрока)"},
        "case_sensitive": {"type": "boolean", "description": "Учитывать регистр (по умолчанию false)"},
    },
    required=["owner", "repo", "run_id", "pattern"],
)
def grep_run_logs(client: GitHubClient, **kwargs) -> str:
    """Ищет regex в логах run с контекстом (распаковывает ZIP)."""
    owner, repo, run_id = kwargs["owner"], kwargs["repo"], kwargs["run_id"]
    pattern = (kwargs.get("pattern") or "").strip()
    if not pattern:
        return "❌ Нужен непустой pattern."
    context = max(0, int(kwargs.get("context", 3)))
    max_matches = max(1, min(int(kwargs.get("max_matches", 50)), 500))
    flags = 0 if kwargs.get("case_sensitive") else re.IGNORECASE
    job_name = kwargs.get("job_name")
    step_name = kwargs.get("step_name")

    try:
        rx = re.compile(pattern, flags)
    except re.error as e:
        return f"❌ Некорректный regex '{pattern}': {e}"

    try:
        files = client.get_workflow_run_logs_files(owner, repo, run_id)
        if not files:
            return f"❌ В архиве логов run {run_id} нет файлов."
        lines, matched = _collect_lines(files, job_name, step_name)
        if not matched:
            return (
                f"❌ Нет файлов логов по фильтру job='{job_name or '-'}' "
                f"step='{step_name or '-'}'. Доступны: {sorted(files.keys())[:20]}"
            )

        hits = [i for i, ln in enumerate(lines) if rx.search(ln)]
        if not hits:
            return (
                f"🔍 По шаблону '{pattern}' ничего не найдено "
                f"(файлов: {len(matched)}, строк: {len(lines)})."
            )

        blocks = []
        last_end = -1
        for idx in hits[:max_matches]:
            start = max(0, idx - context)
            end = min(len(lines), idx + context + 1)
            if start <= last_end and blocks:
                blocks[-1][1] = max(blocks[-1][1], end)
            else:
                blocks.append([start, end])
            last_end = end

        out = [
            f"🔍 Шаблон: {pattern} | совпадений: {len(hits)} "
            f"(показаны первые {min(len(hits), max_matches)}), "
            f"файлов: {len(matched)}, строк: {len(lines)}"
        ]
        for start, end in blocks:
            out.append(f"--- строки {start + 1}..{end} ---")
            for i in range(start, end):
                mark = ">>" if rx.search(lines[i]) else "  "
                out.append(f"{mark} {i + 1}: {_safe_utf8(lines[i])}")
        return "\n".join(out)
    except Exception as e:
        return f"❌ Ошибка grep_run_logs: {e}"


@mcp_tool(
    name="get_run_logs_by_step",
    description=(
        "Получает логи конкретного шага workflow по имени шага (распаковывает ZIP). "
        "direction='head' — с начала (по умолчанию), 'tail' — с конца."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "step_name": {"type": "string", "description": "Название шага (часть имени, регистр не важен)"},
        "max_lines": {"type": "integer", "description": "Максимум строк для вывода (по умолчанию 200)"},
        "start_time": {"type": "string", "description": "ISO 8601 время начала (например 2026-08-22T10:30:00Z)"},
        "direction": {"type": "string", "description": "head (с начала, по умолчанию) | tail (с конца)"},
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
    start_time: str = None,
    direction: str = "head"
):
    """Получает логи конкретного шага workflow, распаковывая ZIP."""
    try:
        # Логи run'а — это ZIP с файлами вида "<job>/<N>_<step>.txt"
        files = client.get_workflow_run_logs_files(owner, repo, run_id)
        if not files:
            return {"error": "No log files found in run archive"}

        needle = step_name.lower()
        matched = {name: text for name, text in files.items() if needle in name.lower()}
        if not matched:
            return {
                "error": f"No log file matched step: {step_name}",
                "available_files": sorted(files.keys())[:30],
            }

        # Склеиваем совпавшие файлы
        logs = "\n".join(
            f"===== {name} =====\n{text}" for name, text in matched.items()
        )
        log_lines = logs.split('\n')

        if start_time:
            filtered_lines = []
            found_start = False
            for line in log_lines:
                if start_time in line:
                    found_start = True
                if found_start:
                    filtered_lines.append(line)
            log_lines = filtered_lines

        if not log_lines:
            return {"error": f"No logs found for step: {step_name}"}

        total = len(log_lines)
        if str(direction).lower() == "tail":
            shown = log_lines[-max_lines:]
        else:
            shown = log_lines[:max_lines]

        return {
            "run_id": run_id,
            "step_name": step_name,
            "matched_files": list(matched.keys()),
            "total_lines": total,
            "returned_lines": len(shown),
            "direction": str(direction).lower(),
            "start_time": start_time,
            "logs": shown
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
        run = client.get_workflow_run(owner, repo, run_id)
        commit_sha = run.get("head_sha")
        if not commit_sha:
            return {"error": "No commit SHA found"}

        check_runs = client.get_check_runs(owner, repo, commit_sha)

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
