"""
FlowMind Tools Registry

Central registry for managing tools across agents and flows.
"""

from typing import Dict, List, Optional, Any
from flomind.tools.tool import Tool


class ToolRegistry:
    """
    Central registry for tools.
    
    Features:
    - Register/unregister tools
    - Get tools by name
    - Get all schemas for LLM function calling
    - Execute tools by name
    """
    
    _instance: Optional['ToolRegistry'] = None
    
    def __new__(cls) -> 'ToolRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tools = {}
        return cls._instance
    
    def register(self, tool: Tool):
        """Register a tool."""
        self.tools[tool.name] = tool
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        if name in self.tools:
            del self.tools[name]
            return True
        return False
    
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
    
    def clear(self):
        """Clear all registered tools."""
        self.tools.clear()
