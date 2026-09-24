"""
Загрузчик для новых инструментов анализа сборок.
Этот файл явно импортирует все новые инструменты, чтобы они были зарегистрированы.
"""

# Явно импортируем новые инструменты, чтобы декораторы сработали
from mcp_server.tools.github.build_logs import get_android_build_error
from mcp_server.tools.github.build_logs import get_ios_build_error
from mcp_server.tools.github.workflow_logs_grep import grep_workflow_logs
from mcp_server.tools.github.batch import move_file
from mcp_server.tools.github.workflow_runs import get_workflow_run_status
from mcp_server.tools.github.workflow_runs import read_run_logs_offset
from mcp_server.tools.github.workflow_runs import grep_run_logs
from mcp_server.tools.github.actions import rerun_failed_jobs

# Экспортируем их для ToolRegistry
__all__ = [
    "get_android_build_error",
    "get_ios_build_error",
    "grep_workflow_logs",
    "move_file",
    "get_workflow_run_status",
    "read_run_logs_offset",
    "grep_run_logs",
    "rerun_failed_jobs",
]
