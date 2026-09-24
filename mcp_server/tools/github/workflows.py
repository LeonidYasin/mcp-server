"""Workflow tools: get_latest_workflow_error, get_workflow_run_logs, get_full_workflow_logs, get_workflow_by_file."""

import re
import hashlib

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    """Безопасно преобразует строку в UTF-8, заменяя проблемные символы."""
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


def _grep_with_context(text_lines, rx, ctx: int, max_hits: int = 200):
    """Возвращает список (start, end) блоков вокруг совпадений, схлопывая перекрытия."""
    hits = [i for i, ln in enumerate(text_lines) if rx.search(ln)]
    if not hits:
        return [], 0
    blocks = []
    last_end = -1
    for idx in hits[:max_hits]:
        start = max(0, idx - ctx)
        end = min(len(text_lines), idx + ctx + 1)
        if start <= last_end and blocks:
            blocks[-1][1] = max(blocks[-1][1], end)
        else:
            blocks.append([start, end])
        last_end = end
    return blocks, len(hits)


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
    description=(
        "Логи и причина падения workflow run: список упавших шагов + хвост их логов "
        "(распаковывает ZIP). "
        "grep_pattern — regex, ищется по ВСЕМ файлам архива; grep_context — строк "
        "контекста вокруг совпадения (по умолчанию 1, как grep -C1); "
        "одинаковые совпадения из разных файлов помечаются '(same as ...)'. "
        "tail_lines=0 — отдавать только результат grep (без хвоста). "
        "Примеры pattern: 'e: file', 'error:', 'Unresolved reference', 'Caused by'."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "tail_lines": {"type": "integer", "description": "Сколько последних строк логов показать на упавший job (по умолчанию 15; 0 = без хвоста)"},
        "context_before": {"type": "integer", "description": "Сколько строк выше хвоста показать (по умолчанию 0)"},
        "grep_pattern": {"type": "string", "description": "Regex: вывести совпавшие строки из всех файлов (напр. 'e: file|Unresolved|error:')"},
        "grep_context": {"type": "integer", "description": "Строк контекста вокруг каждого совпадения (по умолчанию 1)"},
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_run_logs(client: GitHubClient, owner: str, repo: str, run_id: int,
                          tail_lines: int = 15, context_before: int = 0,
                          grep_pattern: str = None, grep_context: int = 1) -> str:
    """Get workflow run logs (tail + context + grep over all files with dedup)."""
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

        if not failed:
            lines.append("✅ Все проверки прошли успешно!")
            return _safe_utf8("\n".join(lines))

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

        try:
            files = client.get_workflow_run_logs_files(owner, repo, run_id)
            tail_n = max(0, min(int(tail_lines), 100))
            before_n = max(0, min(int(context_before), 200))

            # Хвост логов упавших job'ов (пропускаем, если tail_lines=0)
            if tail_n > 0:
                for job in failed:
                    job_name = (job.get('name') or '').strip()
                    if not job_name:
                        continue
                    matched = [(n, t) for n, t in files.items() if job_name.lower() in n.lower()]
                    if not matched:
                        continue
                    lines.append(f"\n   📄 Текст ошибки ({job_name}, последние {tail_n} строк"
                                 + (f" + {before_n} выше" if before_n else "") + "):")
                    for name, text in matched:
                        all_lines = [ln for ln in text.strip().split("\n") if ln.strip()]
                        if before_n:
                            block = all_lines[-(tail_n + before_n):]
                        else:
                            block = all_lines[-tail_n:]
                        lines.append(f"     ── {name} ──")
                        for tl in block:
                            lines.append(f"     {_safe_utf8(tl)}")

            # grep по всем файлам, с контекстом и дедупликацией
            gp = (grep_pattern or "").strip()
            if gp:
                rx = None
                try:
                    rx = re.compile(gp, re.IGNORECASE)
                except re.error as exc:
                    lines.append(f"   ⚠️ Некорректный grep_pattern '{gp}': {exc}")
                if rx:
                    ctx = max(0, min(int(grep_context), 10))
                    total_hits = 0
                    scanned_files = 0
                    seen_blocks = {}   # hash -> первый файл
                    per_file_out = []
                    for name, text in files.items():
                        scanned_files += 1
                        text_lines = text.split("\n")
                        blocks, hits_n = _grep_with_context(text_lines, rx, ctx)
                        if not blocks:
                            continue
                        total_hits += hits_n
                        # Сигнатура набора совпавших строк — для дедупликации
                        matched_text = "\n".join(
                            text_lines[i].strip()
                            for b in blocks for i in range(b[0], b[1])
                            if rx.search(text_lines[i])
                        )
                        sig = hashlib.md5(matched_text.encode("utf-8", errors="replace")).hexdigest()
                        if sig in seen_blocks:
                            per_file_out.append((name, None, seen_blocks[sig], hits_n))
                        else:
                            seen_blocks[sig] = name
                            rendered = []
                            for b in blocks:
                                for i in range(b[0], b[1]):
                                    mark = ">>" if rx.search(text_lines[i]) else "  "
                                    rendered.append(f"{mark} {i + 1}: {_safe_utf8(text_lines[i])}")
                            per_file_out.append((name, rendered, None, hits_n))

                    lines.append(
                        f"\n   🔎 grep '{gp}' (context={ctx}): файлов проверено {scanned_files}, "
                        f"совпадений {total_hits}"
                    )
                    if total_hits == 0:
                        lines.append(
                            "     (совпадений нет — примеры паттернов: "
                            "'e: file', 'error:', 'Unresolved reference', 'Caused by')"
                        )
                    else:
                        for name, rendered, dup_of, hits_n in per_file_out[:15]:
                            if rendered is None:
                                lines.append(f"     ── {name} ({hits_n}) — (same as in {dup_of}) ──")
                            else:
                                lines.append(f"     ── {name} ({hits_n}) ──")
                                for r in rendered:
                                    lines.append(f"       {r}")
        except Exception as e:
            lines.append(f"   ⚠️ Не удалось получить текст логов: {e}")

        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_full_workflow_logs",
    description="Получает ПОЛНЫЕ логи всех jobs для конкретного workflow run (без обрезания)",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
    },
    required=["owner", "repo", "run_id"],
)
def get_full_workflow_logs(client: GitHubClient, owner: str, repo: str, run_id: int) -> str:
    """Get full workflow logs without truncation."""
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
                    lines.append(f"\n   📄 ЛОГИ (все {len(log_lines)} строк):")
                    lines.append("   " + "-" * 40)
                    for line in log_lines:
                        lines.append(f"   {_safe_utf8(line)}")
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
    name="get_workflow_logs_preview",
    description="Получает первые N строк логов для конкретного workflow run (по умолчанию 50)",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "limit": {"type": "integer", "description": "Количество строк для вывода (по умолчанию 50)"},
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_logs_preview(client: GitHubClient, owner: str, repo: str, run_id: int, limit: int = 50) -> str:
    """Get first N lines of workflow logs."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)

        lines = [f"📋 ПРЕВЬЮ ЛОГОВ для запуска #{run_id} (первые {limit} строк)", f"Всего jobs: {len(jobs)}", "=" * 60, ""]

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
                    preview = log_lines[:limit]
                    lines.append(f"\n   📄 ЛОГИ (первые {len(preview)} из {len(log_lines)} строк):")
                    lines.append("   " + "-" * 40)
                    for line in preview:
                        lines.append(f"   {_safe_utf8(line)}")
                    if len(log_lines) > limit:
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
