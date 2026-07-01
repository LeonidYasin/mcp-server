"""
Загрузчик для новых инструментов анализа сборок.
Этот файл явно импортирует все новые инструменты, чтобы они были зарегистрированы.
"""

# Явно импортируем новые инструменты, чтобы декораторы сработали
from mcp_server.tools.github.build_logs import get_android_build_error
from mcp_server.tools.github.build_logs import get_ios_build_error

# Экспортируем их для ToolRegistry
__all__ = [
    "get_android_build_error",
    "get_ios_build_error",
]
