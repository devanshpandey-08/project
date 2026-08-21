from typing import Callable, Dict, Any
def Tool(name: str = "", description: str = "", parameters: Dict[str, Any] = None):
    def decorator(func: Callable) -> Callable:
        func._tool_name = name or func.__name__
        func._tool_description = description
        func._tool_parameters = parameters or {}
        return func
    return decorator
