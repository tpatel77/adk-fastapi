"""
Registry for custom lifecycle callbacks.
Allows users to register Python functions that can be invoked during agent/model/tool execution.
"""

from typing import Callable, Any, Dict

# Callback function signature: (context_data: dict, *args, **kwargs) -> Any
CallbackFunc = Callable[..., Any]

class CallbackRegistry:
    """Registry for managing callback functions."""
    
    _callbacks: Dict[str, CallbackFunc] = {}
    
    @classmethod
    def register(cls, name: str, func: CallbackFunc):
        """Register a callback function."""
        if name in cls._callbacks:
            # We allow overwriting, but logging a warning might be good in complex apps
            pass
        cls._callbacks[name] = func
        
    @classmethod
    def get(cls, name: str) -> CallbackFunc | None:
        """Get a callback function by name."""
        return cls._callbacks.get(name)
    
    @classmethod
    def clear(cls):
        """Clear all registered callbacks (mostly for testing)."""
        cls._callbacks.clear()

def register_callback(name: str):
    """Decorator to register a function as a callback."""
    def decorator(func: CallbackFunc):
        CallbackRegistry.register(name, func)
        return func
    return decorator


def callback_origin(name: str) -> str:
    return "default" if isinstance(name, str) and name.startswith("default_") else "workflow_custom"


def split_callback_names(names: list[str]) -> dict[str, list[str]]:
    defaults: list[str] = []
    customs: list[str] = []
    for n in names or []:
        if callback_origin(n) == "default":
            defaults.append(n)
        else:
            customs.append(n)
    return {"default": defaults, "workflow_custom": customs}


import adk.core.callbacks.defaults
