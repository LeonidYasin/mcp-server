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
from .workflow_attempt_logs import PARAMETERS as LOG_PARAMETERS


def _safe_utf8(text: str) -> str:
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


@mcp_tool(
    name="grep_workflow_logs",
    description=(
        "Фильтрует логи workflow run по regex и возвращает только совпавшие строки "
        "с ±context строк контекста. Ограниченный ответ с output_truncated и run_attempt. "
        "Распаковывает ZIP-архив логов. Идеально для больших CI-логов (1000+ строк)."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        **LOG_PARAMETERS,
        "job_name": {"type":"string"}, "step_name": {"type":"string"},
        "pattern": {"type": "string", "description": "Regex (по умолчанию error|FAILED|Exception|error:)"},
        "context": {"type": "integer", "description": "Строк контекста до/после совпадения (по умолчанию 3)"},
        "max_matches": {"type": "integer", "description": "Максимум совпадений (по умолчанию 50, максимум 500)"},
        "case_sensitive": {"type": "boolean", "description": "Учитывать регистр (по умолчанию false)"},
        "file_filter": {"type": "string", "description": "Искать только в файлах логов, чьё имя содержит эту подстроку (напр. имя job)"},
    },
    required=["owner", "repo", "run_id"],
)
def grep_workflow_logs(client: GitHubClient, **kwargs):
    """Compatibility alias for the bounded attempt-aware grep reader."""
    from .workflow_attempt_logs import query
    kwargs.setdefault('pattern', r'error|FAILED|Exception|error:')
    return query(client, 'grep', **kwargs)
