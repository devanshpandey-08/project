"""Tool system for FlowMind - type-safe function wrapping for agents."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints, get_origin, get_args
from functools import wraps
import inspect


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type_hint: type
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class ToolResult:
    """Result of tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None


class Tool:
    """
    A tool that can be used by agents.
    
    Tools wrap Python functions with metadata for LLM function calling.
    They provide:
    - Type-safe parameter validation
    - Automatic schema generation
    - Async/sync execution support
    - Error handling
    
    Usage:
        @tool(name="search", description="Search the web")
        def search_tool(query: str, limit: int = 5) -> str:
            return f"Results for: {query}"
        
        # Or programmatically:
        tool = Tool(
            name="calculator",
            description="Perform calculations",
            fn=lambda x, y: x + y,
            parameters=[...]
        )
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        fn: Callable,
        parameters: Optional[List[ToolParameter]] = None,
        return_type: Optional[type] = None,
    ):
        self.name = name
        self.description = description
        self.fn = fn
        self.parameters = parameters or []
        self.return_type = return_type
        
        # Auto-extract parameters from function signature if not provided
        if not parameters:
            self._extract_parameters()
    
    def _extract_parameters(self) -> None:
        """Extract parameters from function signature."""
        try:
            sig = inspect.signature(self.fn)
            type_hints = get_type_hints(self.fn)
            
            self.parameters = []
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue
                
                param_type = type_hints.get(param_name, Any)
                is_required = param.default == inspect.Parameter.empty
                
                self.parameters.append(ToolParameter(
                    name=param_name,
                    type_hint=param_type,
                    description="",  # Would need docstring parsing
                    required=is_required,
                    default=None if is_required else param.default,
                ))
            
            # Extract return type
            if "return" in type_hints:
                self.return_type = type_hints["return"]
                
        except Exception:
            pass  # Keep empty parameters if extraction fails
    
    def _validate_params(self, **kwargs) -> None:
        """Validate input parameters."""
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                raise ValueError(f"Missing required parameter: {param.name}")
            
            if param.name in kwargs:
                value = kwargs[param.name]
                # Basic type checking
                if param.type_hint != Any and not isinstance(value, param.type_hint):
                    # Handle optional types
                    origin = get_origin(param.type_hint)
                    if origin is not None:
                        args = get_args(param.type_hint)
                        if origin is list and not isinstance(value, list):
                            raise TypeError(f"Parameter {param.name} must be a list")
                        elif origin is dict and not isinstance(value, dict):
                            raise TypeError(f"Parameter {param.name} must be a dict")
    
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        self._validate_params(**kwargs)
        
        try:
            result = self.fn(**kwargs)
            
            # Handle async functions
            if asyncio.iscoroutine(result):
                result = await result
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Tool execution failed: {e}")
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert tool to OpenAI function calling schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": self._type_to_json_schema(param.type_hint),
                "description": param.description,
            }
            properties[param.name] = prop
            
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
                    "required": required,
                },
            },
        }
    
    def _type_to_json_schema(self, t: type) -> str:
        """Convert Python type to JSON schema type."""
        if t == str:
            return "string"
        elif t == int:
            return "integer"
        elif t == float:
            return "number"
        elif t == bool:
            return "boolean"
        elif t == list or get_origin(t) == list:
            return "array"
        elif t == dict or get_origin(t) == dict:
            return "object"
        elif t == type(None):
            return "null"
        else:
            return "string"  # Default
    
    def __repr__(self) -> str:
        return f"Tool(name={self.name}, params={len(self.parameters)})"


def tool(
    name: Optional[str] = None,
    description: str = "",
) -> Callable[[Callable], Tool]:
    """
    Decorator to create a Tool from a function.
    
    Usage:
        @tool(name="web_search", description="Search the web")
        def search(query: str, limit: int = 10) -> str:
            return f"Search results for {query}"
    """
    def decorator(fn: Callable) -> Tool:
        tool_name = name or fn.__name__
        return Tool(
            name=tool_name,
            description=description,
            fn=fn,
        )
    return decorator


class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> "ToolRegistry":
        """Register a tool."""
        self._tools[tool.name] = tool
        return self
    
    def unregister(self, name: str) -> "ToolRegistry":
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]
        return self
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Tool]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def to_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all tools."""
        return [t.to_schema() for t in self._tools.values()]
    
    def execute(self, name: str, **kwargs) -> Any:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        return asyncio.run(tool.execute(**kwargs))
    
    async def execute_async(self, name: str, **kwargs) -> Any:
        """Execute a tool by name asynchronously."""
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        return await tool.execute(**kwargs)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __repr__(self) -> str:
        return f"ToolRegistry(tools={list(self._tools.keys())})"
