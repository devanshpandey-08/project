"""Tool system for FlowMind."""

from typing import Any, Dict, List, Optional, Callable, Type, get_type_hints
from dataclasses import dataclass, field
import inspect
import json


@dataclass
class ToolError(Exception):
    """Error raised by tool execution."""
    message: str
    code: str = "TOOL_ERROR"
    details: Optional[Dict[str, Any]] = None
    
    def __str__(self):
        return f"[{self.code}] {self.message}"


@dataclass
class ToolResult:
    """Result of tool execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata
        }


class Tool:
    """
    Type-safe tool definition with automatic schema generation.
    
    Features:
    - Automatic parameter validation
    - OpenAI function calling compatible
    - Async/sync support
    - Rich metadata
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        func: Optional[Callable] = None,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ):
        self.name = name
        self.description = description
        self.func = func
        self.tags = tags or []
        self._parameters = parameters
        self._type_hints = {}
        
        if func:
            self._infer_parameters_from_func()
            
    def _infer_parameters_from_func(self):
        """Infer parameters from function signature."""
        if not self.func:
            return
            
        sig = inspect.signature(self.func)
        type_hints = get_type_hints(self.func)
        self._type_hints = type_hints
        
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
                
            param_type = type_hints.get(param_name, Any)
            
            # Map Python types to JSON schema types
            type_map = {
                int: {"type": "integer"},
                float: {"type": "number"},
                str: {"type": "string"},
                bool: {"type": "boolean"},
                list: {"type": "array", "items": {"type": "string"}},
                dict: {"type": "object"},
                Any: {"type": "string"}
            }
            
            param_schema = type_map.get(param_type, {"type": "string"})
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
            else:
                param_schema["default"] = param.default
                
            properties[param_name] = param_schema
            
        self._parameters = {
            "type": "object",
            "properties": properties,
            "required": required
        }
        
    @property
    def parameters(self) -> Dict[str, Any]:
        """Get tool parameters schema."""
        return self._parameters or {}
    
    def to_openai_function(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
    
    async def execute_async(self, **kwargs) -> ToolResult:
        """Execute tool asynchronously."""
        import asyncio
        
        if not self.func:
            return ToolResult(
                success=False,
                error=f"Tool {self.name} has no function"
            )
            
        try:
            # Validate parameters
            if self._parameters and "properties" in self._parameters:
                required = self._parameters.get("required", [])
                for req in required:
                    if req not in kwargs:
                        raise ToolError(
                            f"Missing required parameter: {req}",
                            code="MISSING_PARAMETER"
                        )
            
            # Execute
            if asyncio.iscoroutinefunction(self.func):
                result = await self.func(**kwargs)
            else:
                result = self.func(**kwargs)
                
            return ToolResult(success=True, output=result)
            
        except ToolError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}"
            )
    
    def execute(self, **kwargs) -> ToolResult:
        """Execute tool synchronously."""
        import asyncio
        return asyncio.run(self.execute_async(**kwargs))
    
    def __call__(self, **kwargs) -> ToolResult:
        """Allow calling tool directly."""
        return self.execute(**kwargs)


class ToolRegistry:
    """Registry for managing tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        
    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
        
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
        
    def list_tools(self) -> List[Tool]:
        """List all registered tools."""
        return list(self._tools.values())
        
    def to_openai_functions(self) -> List[Dict[str, Any]]:
        """Convert all tools to OpenAI format."""
        return [tool.to_openai_function() for tool in self._tools.values()]
        
    def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {name}"
            )
        return tool.execute(**kwargs)


# Decorator for easy tool creation
def tool(
    name: Optional[str] = None,
    description: str = "",
    tags: Optional[List[str]] = None
):
    """Decorator to create a tool from a function."""
    def decorator(func: Callable) -> Tool:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip()
        return Tool(
            name=tool_name,
            description=tool_desc,
            func=func,
            tags=tags
        )
    return decorator
