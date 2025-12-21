"""Tool registry for managing custom and built-in tools."""

import importlib
from typing import Any, Callable
from functools import wraps


class ToolRegistry:
    """Singleton registry for managing tools available to agents."""
    
    _instance: "ToolRegistry | None" = None
    _tools: dict[str, Callable[..., Any]]
    
    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance
    
    def register(self, name: str, func: Callable[..., Any]) -> None:
        """Register a tool function with the given name."""
        self._tools[name] = func
    
    def get(self, name: str) -> Callable[..., Any] | None:
        """Get a registered tool by name."""
        return self._tools.get(name)
    
    def get_all(self) -> dict[str, Callable[..., Any]]:
        """Get all registered tools."""
        return self._tools.copy()
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
    
    def load_tool_from_module(self, module_path: str, function_name: str, tool_name: str | None = None) -> Callable[..., Any]:
        """
        Load a tool function from a Python module.
        
        Args:
            module_path: Dotted path to the module (e.g., 'adk.tools.custom')
            function_name: Name of the function in the module
            tool_name: Optional name to register the tool under (defaults to function_name)
        
        Returns:
            The loaded tool function
        """
        module = importlib.import_module(module_path)
        func = getattr(module, function_name)
        
        name = tool_name or function_name
        self.register(name, func)
        
        return func


def register_tool(name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to register a function as a tool.
    
    Usage:
        @register_tool("my_tool")
        def my_tool_function(arg1: str) -> str:
            '''Tool description for the LLM.'''
            return f"Result: {arg1}"
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or func.__name__
        registry = ToolRegistry()
        registry.register(tool_name, func)
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return _registry
