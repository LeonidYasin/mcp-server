"""
Декоратор для регистрации MCP-инструментов.
"""

import sys
from typing import Callable

# Глобальный реестр для хранения зарегистрированных инструментов
_TOOL_REGISTRY = {}


def mcp_tool(func: Callable) -> Callable:
    """
    Декоратор для регистрации MCP-инструментов.
    Помечает функцию как MCP-инструмент и добавляет её в глобальный реестр.
    """
    func._is_mcp_tool = True
    
    # Регистрируем функцию в глобальном реестре
    module_name = func.__module__
    func_name = func.__name__
    
    if module_name not in _TOOL_REGISTRY:
        _TOOL_REGISTRY[module_name] = {}
    _TOOL_REGISTRY[module_name][func_name] = func
    
    return func


def get_registered_tools() -> dict:
    """Возвращает словарь всех зарегистрированных инструментов."""
    return _TOOL_REGISTRY


def get_tools_by_module(module_name: str) -> dict:
    """Возвращает инструменты для указанного модуля."""
    return _TOOL_REGISTRY.get(module_name, {})
