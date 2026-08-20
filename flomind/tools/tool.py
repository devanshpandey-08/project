"""
Tool system for FlowMind.

Provides a type-safe, composable way to define and execute tools/actions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Awaitable, TypeVar, Generic
import asyncio
import functools
import inspect


T = TypeVar('T')


@dataclass
class ToolParameter:
    """A parameter for a tool."""
    name: str
    type_hint: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolConfig:
    """Configuration for a tool."""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    timeout_seconds: float = 30.0
    retry_count: int = 0


@dataclass
class Tool(Generic[T]):
    """
    A tool that can be used by agents.
    
    Tools replace LangChain's tools with better type safety and async support.
    """
    config: ToolConfig
    handler: Callable[..., Awaitable[T]]
    
    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        handler: Callable[..., Awaitable[T]],
        parameters: Optional[List[ToolParameter]] = None,
        **kwargs
    ) -> 'Tool':
        """Factory method to create a tool."""
        config = ToolConfig(
            name=name,
            description=description,
            parameters=parameters or [],
            **kwargs
        )
        return cls(config=config, handler=handler)
    
    async def execute(self, **kwargs) -> T:
        """Execute the tool with given arguments."""
        try:
            if asyncio.iscoroutinefunction(self.handler):
                return await self.handler(**kwargs)
            else:
                return self.handler(**kwargs)
        except Exception as e:
            raise ToolError(f"Tool {self.config.name} failed: {e}") from e
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def description(self) -> str:
        return self.config.description
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []
        
        for param in self.config.parameters:
            properties[param.name] = {
                "type": param.type_hint,
                "description": param.description
            }
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.config.name,
                "description": self.config.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    def __repr__(self) -> str:
        return f"Tool(name={self.config.name}, description={self.config.description[:50]}...)"


@dataclass
class Action(Tool):
    """An action is a special type of tool that modifies state."""
    pass


class ToolError(Exception):
    """Exception raised when a tool fails."""
    pass


def tool(name: Optional[str] = None, description: Optional[str] = None):
    """
    Decorator to create a tool from a function.
    
    Usage:
        @tool
        async def search(query: str) -> str:
            '''Search for information.'''
            ...
    
        @tool(name="custom_name", description="Custom description")
        def calculator(expression: str) -> float:
            '''Calculate a mathematical expression.'''
            ...
    """
    def decorator(func: Callable) -> Tool:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "No description").strip()
        
        # Extract parameters from function signature
        sig = inspect.signature(func)
        params = []
        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls'):
                continue
            
            type_hint = getattr(param.annotation, '__name__', str(param.annotation))
            if type_hint == '<class \'str\'>':
                type_hint = 'string'
            elif type_hint == '<class \'int\'>':
                type_hint = 'integer'
            elif type_hint == '<class \'float\'>':
                type_hint = 'number'
            elif type_hint == '<class \'bool\'>':
                type_hint = 'boolean'
            
            params.append(ToolParameter(
                name=param_name,
                type_hint=type_hint,
                description="",
                required=param.default == inspect.Parameter.empty,
                default=None if param.default == inspect.Parameter.empty else param.default
            ))
        
        # Wrap sync functions in async
        if not asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(**kwargs):
                return func(**kwargs)
            handler = async_wrapper
        else:
            handler = func
        
        return Tool.create(
            name=tool_name,
            description=tool_desc,
            handler=handler,
            parameters=params
        )
    
    # Handle both @tool and @tool() syntax
    if callable(name):
        func = name
        name = None
        return decorator(func)
    
    return decorator
