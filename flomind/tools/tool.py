"""Tool system with type-safe decorators."""
import asyncio
from typing import Any, Callable, Dict, List, Optional, TypeVar
from dataclasses import dataclass, field
from functools import wraps

T = TypeVar('T')


@dataclass
class Tool:
    """Type-safe tool definition."""
    name: str
    description: str
    func: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.parameters.keys())
                }
            }
        }
    
    async def execute(self, **kwargs) -> Any:
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        else:
            return await asyncio.to_thread(self.func, **kwargs)


def tool(name: str, description: str, parameters: Optional[Dict[str, Any]] = None):
    """Decorator to create a tool from a function."""
    def decorator(func: Callable) -> Tool:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return await asyncio.to_thread(func, *args, **kwargs)
        
        return Tool(
            name=name,
            description=description,
            func=wrapper,
            parameters=parameters or {}
        )
    
    return decorator
