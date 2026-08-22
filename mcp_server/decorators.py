"""
Декоратор для регистрации MCP-инструментов.
"""

import functools
from typing import Callable, Any


# Глобальный реестр для хранения зарегистрированных инструментов
_TOOL_REGISTRY = {}


def mcp_tool(func: Callable) -> Callable:
    """
    Декоратор для регистрации функции как MCP-инструмента.
    
    Помечает функцию как MCP-инструмент и добавляет её в глобальный реестр.
    Используется для автоматического обнаружения инструментов в папке tools.
    
    Пример:
        @mcp_tool
        def my_tool(param: str) -> dict:
            '''Описание инструмента.'''
            return {"result": param}
    """
    # Регистрируем функцию в глобальном реестре
    _TOOL_REGISTRY[func.__name__] = func
    
    # Добавляем атрибут для обнаружения декоратором
    func._is_mcp_tool = True
    func._tool_name = func.__name__
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    
    # Копируем атрибуты на wrapper
    wrapper._is_mcp_tool = True
    wrapper._tool_name = func.__name__
    
    return wrapper


def get_registered_tools() -> dict:
    """Возвращает словарь всех зарегистрированных инструментов."""
    return _TOOL_REGISTRY.copy()


def clear_registry() -> None:
    """Очищает реестр инструментов (используется в тестах)."""
    _TOOL_REGISTRY.clear()
