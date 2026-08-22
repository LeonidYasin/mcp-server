"""
Декоратор для регистрации MCP-инструментов.
Автоматически регистрирует функции в ToolRegistry.
"""

import functools
import inspect
from typing import Callable, Any

from mcp_server.core.tool import Tool


# Ленивый импорт, чтобы избежать циклических зависимостей
_TOOL_REGISTRY = None


def _get_registry():
    """Получить глобальный экземпляр ToolRegistry."""
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY is None:
        try:
            from mcp_server.core.registry import ToolRegistry
            _TOOL_REGISTRY = ToolRegistry()
        except ImportError:
            # Если реестр не доступен, создаем локальный
            class _DummyRegistry:
                def register(self, tool):
                    pass
                def discover(self):
                    pass
            _TOOL_REGISTRY = _DummyRegistry()
    return _TOOL_REGISTRY


def mcp_tool(func: Callable) -> Callable:
    """
    Декоратор для регистрации функции как MCP-инструмента.
    
    Автоматически регистрирует функцию в ToolRegistry с использованием
    её сигнатуры для генерации схемы параметров.
    
    Пример:
        @mcp_tool
        def my_tool(param: str) -> dict:
            '''Описание инструмента.'''
            return {"result": param}
    """
    # Добавляем атрибуты для обнаружения
    func._is_mcp_tool = True
    func._tool_name = func.__name__
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    
    # Копируем атрибуты на wrapper
    wrapper._is_mcp_tool = True
    wrapper._tool_name = func.__name__
    
    # Регистрируем в ToolRegistry
    try:
        registry = _get_registry()
        
        # Извлекаем описание из docstring
        doc = func.__doc__ or ""
        description = doc.strip().split('\n')[0] if doc else func.__name__
        
        # Генерируем схему параметров из сигнатуры
        sig = inspect.signature(func)
        parameters = {}
        required = []
        
        for name, param in sig.parameters.items():
            # Пропускаем client и другие служебные параметры
            if name in ('client', 'self', 'cls'):
                continue
            
            param_info = {
                "type": "string",
                "description": name
            }
            
            # Пытаемся определить тип из аннотации
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_info["type"] = "integer"
                elif param.annotation == bool:
                    param_info["type"] = "boolean"
                elif param.annotation == float:
                    param_info["type"] = "number"
                elif hasattr(param.annotation, "__origin__") and param.annotation.__origin__ == list:
                    param_info["type"] = "array"
                elif param.annotation == dict or (hasattr(param.annotation, "__origin__") and param.annotation.__origin__ == dict):
                    param_info["type"] = "object"
            
            # Если есть значение по умолчанию, параметр не обязательный
            if param.default == inspect.Parameter.empty:
                required.append(name)
            else:
                param_info["default"] = param.default
            
            parameters[name] = param_info
        
        # Создаем объект Tool
        tool = Tool(
            name=func.__name__,
            description=description,
            parameters=parameters,
            required=required,
            handler=func
        )
        
        # Добавляем атрибут для auto-discovery
        func._mcp_tool = tool
        wrapper._mcp_tool = tool
        
        # Регистрируем в реестре
        registry.register(tool)
        
    except Exception as e:
        # Если регистрация не удалась, просто логируем ошибку
        print(f"[WARN] Failed to register tool {func.__name__}: {e}")
    
    return wrapper


def get_registered_tools() -> dict:
    """Возвращает словарь всех зарегистрированных инструментов."""
    try:
        registry = _get_registry()
        return registry._tools if hasattr(registry, '_tools') else {}
    except Exception:
        return {}


def clear_registry() -> None:
    """Очищает реестр инструментов (используется в тестах)."""
    try:
        registry = _get_registry()
        if hasattr(registry, '_tools'):
            registry._tools.clear()
    except Exception:
        pass
