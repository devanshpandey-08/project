"""
FlowMind Tools System

Type-safe tool definitions with automatic schema generation.
Tools are the building blocks agents use to interact with the world.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, get_type_hints
import inspect
import json
from functools import wraps

T = TypeVar('T')


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type_hint: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    """
    A tool that can be used by agents.
    
    Key Features:
    - Automatic schema generation from function signatures
    - Type validation
    - Rich descriptions for LLM understanding
    - Sync and async support
    """
    name: str
    description: str
    func: Callable
    parameters: List[ToolParameter] = field(default_factory=list)
    return_type: str = "Any"
    
    @classmethod
    def from_function(cls, func: Callable, 
                      name: Optional[str] = None,
                      description: Optional[str] = None) -> 'Tool':
        """Create a Tool from a function with automatic schema inference."""
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        # Get docstring for description
        doc = inspect.getdoc(func) or ""
        
        tool_name = name or func.__name__
        tool_desc = description or doc.split('\n')[0] if doc else f"Tool: {tool_name}"
        
        # Extract parameters
        params = []
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            type_hint = type_hints.get(param_name, Any)
            type_str = getattr(type_hint, '__name__', str(type_hint))
            
            # Check if required
            required = param.default == inspect.Parameter.empty
            
            params.append(ToolParameter(
                name=param_name,
                type_hint=type_str,
                description="",  # Could extract from docstring
                required=required,
                default=None if required else param.default
            ))
        
        # Return type
        return_hint = type_hints.get('return', Any)
        return_str = getattr(return_hint, '__name__', str(return_hint))
        
        return cls(
            name=tool_name,
            description=tool_desc,
            func=func,
            parameters=params,
            return_type=return_str
        )
    
    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": self._map_type_to_json_schema(param.type_hint),
                "description": param.description
            }
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    def _map_type_to_json_schema(self, type_str: str) -> str:
        """Map Python type to JSON Schema type."""
        type_map = {
            'str': 'string',
            'int': 'integer',
            'float': 'number',
            'bool': 'boolean',
            'list': 'array',
            'dict': 'object',
            'List': 'array',
            'Dict': 'object',
        }
        return type_map.get(type_str, 'string')
    
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given arguments."""
        import asyncio
        
        # Validate required parameters
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                raise ValueError(f"Missing required parameter: {param.name}")
        
        # Execute
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        else:
            return self.func(**kwargs)


def tool(name: Optional[str] = None, 
         description: Optional[str] = None):
    """
    Decorator to define a tool.
    
    Usage:
        @tool(description="Search the web")
        def search(query: str) -> str:
            '''Search for information online.'''
            return f"Results for {query}"
    """
    def decorator(func: Callable) -> Tool:
        return Tool.from_function(func, name=name, description=description)
    return decorator


class ToolRegistry:
    """
    Registry for managing available tools.
    
    Features:
    - Tool lookup by name
    - Schema aggregation for multiple tools
    - Validation
    """
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        """Register a tool."""
        self.tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self.tools.keys())
    
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get OpenAI schemas for all tools."""
        return [tool.to_openai_schema() for tool in self.tools.values()]
    
    async def execute(self, tool_name: str, **kwargs) -> Any:
        """Execute a tool by name."""
        tool = self.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        return await tool.execute(**kwargs)
