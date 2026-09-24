"""MCP tool: фильтр логов workflow run по regex с контекстом.

Решает проблему пункта 9 отчёта: CI-лог 1000+ строк обрезается клиентом.
Этот инструмент возвращает только совпавшие строки ±контекст — маленький
ответ, который не режется.

Важно: GitHub отдаёт логи run'а как ZIP. Используем
client.get_workflow_run_logs_text(), который распаковывает архив.
"""

import re

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


@mcp_tool(
    name="grep_workflow_logs",
    description=(
        "Фильтрует логи workflow run по regex и возвращает только совпавшие строки "
        "с ±context строк контекста. Маленький ответ — не обрезается клиентом. "
        "Распаковывает ZIP-архив логов. Идеально для больших CI-логов (1000+ строк)."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "pattern": {"type": "string", "description": "Regex (по умолчанию error|FAILED|Exception|error:)"},
        "context": {"type": "integer", "description": "Строк контекста до/после совпадения (по умолчанию 3)"},
        "max_matches": {"type": "integer", "description": "Максимум совпадений (по умолчанию 50, максимум 500)"},
        "case_sensitive": {"type": "boolean", "description": "Учитывать регистр (по умолчанию false)"},
        "file_filter": {"type": "string", "description": "Искать только в файлах логов, чьё имя содержит эту подстроку (напр. имя job)"},
    },
    required=["owner", "repo", "run_id"],
)
def grep_workflow_logs(client: GitHubClient, **kwargs) -> str:
    """Фильтрует логи workflow run по regex с контекстом (распаковывает ZIP)."""
    owner, repo, run_id = kwargs["owner"], kwargs["repo"], kwargs["run_id"]
    pattern = (kwargs.get("pattern") or r"error|FAILED|Exception|error:").strip()
    context = max(0, int(kwargs.get("context", 3)))
    max_matches = max(1, min(int(kwargs.get("max_matches", 50)), 500))
    flags = 0 if kwargs.get("case_sensitive") else re.IGNORECASE
    file_filter = (kwargs.get("file_filter") or "").strip().lower()

    try:
        rx = re.compile(pattern, flags)
    except re.error as e:
        return f"❌ Некорректный regex '{pattern}': {e}"

    try:
        files = client.get_workflow_run_logs_files(owner, repo, run_id)
        if not files:
            return f"❌ В архиве логов run {run_id} нет файлов."

        if file_filter:
            files = {n: t for n, t in files.items() if file_filter in n.lower()}
            if not files:
                return f"❌ Нет файлов логов с '{file_filter}' в имени (run {run_id})."

        # Склеиваем выбранные файлы, сохраняя заголовки
        chunks = []
        for name, text in files.items():
            chunks.append(f"===== {name} =====")
            chunks.append(text)
        logs = "\n".join(chunks)
        lines = logs.split("\n")

        hits = [i for i, ln in enumerate(lines) if rx.search(ln)]
        if not hits:
            return (
                f"🔍 По шаблону '{pattern}' ничего не найдено в логах run {run_id} "
                f"(файлов: {len(files)}, строк: {len(lines)})."
            )

        # Собираем блоки [start, end) с контекстом, схлопывая перекрытия
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
            f"(показаны первые {min(len(hits), max_matches)}), файлов: {len(files)}, строк: {len(lines)}"
        ]
        for start, end in blocks:
            out.append(f"--- строки {start + 1}..{end} ---")
            for i in range(start, end):
                mark = ">>" if rx.search(lines[i]) else "  "
                out.append(f"{mark} {i + 1}: {_safe_utf8(lines[i])}")
        return "\n".join(out)
    except Exception as e:
        return f"❌ Ошибка grep_workflow_logs: {e}"
