"""AI Agent system for FlowMind."""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
import asyncio
import uuid
from enum import Enum

from flomind.tools.tool import Tool, ToolRegistry, ToolResult


class AgentRole(Enum):
    """Pre-defined agent roles."""
    ASSISTANT = "assistant"
    RESEARCHER = "researcher"
    WRITER = "writer"
    CODER = "coder"
    REVIEWER = "reviewer"
    MANAGER = "manager"
    CRITIC = "critic"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    role: AgentRole = AgentRole.ASSISTANT
    system_prompt: str = ""
    tools: List[Tool] = field(default_factory=list)
    max_iterations: int = 10
    temperature: float = 0.7
    model: str = "gpt-4"
    

class Agent:
    """
    Autonomous AI Agent with tool usage capabilities.
    
    Features:
    - Tool-based reasoning
    - Multi-step task execution
    - Self-correction
    - Memory integration
    """
    
    def __init__(
        self,
        name: str,
        role: str = "assistant",
        system_prompt: str = "",
        tools: Optional[List[Tool]] = None,
        model: str = "gpt-4",
        **kwargs
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.role = role
        self.system_prompt = system_prompt or f"You are a {role} assistant."
        self.model = model
        self.tools = tools or []
        self.tool_registry = ToolRegistry()
        
        # Register tools
        for tool in self.tools:
            self.tool_registry.register(tool)
            
        self._memory: List[Dict[str, Any]] = []
        self._iteration_count = 0
        
    def add_tool(self, tool: Tool) -> 'Agent':
        """Add a tool to the agent."""
        self.tools.append(tool)
        self.tool_registry.register(tool)
        return self
        
    def remove_tool(self, name: str) -> bool:
        """Remove a tool from the agent."""
        result = self.tool_registry.unregister(name)
        if result:
            self.tools = [t for t in self.tools if t.name != name]
        return result
        
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get tools in OpenAI function format."""
        return self.tool_registry.to_openai_functions()
        
    async def think(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Think about the task and decide on actions.
        
        In production, this would call an LLM. Here we simulate the behavior.
        """
        self._iteration_count += 1
        
        if self._iteration_count > 10:
            return {
                "action": "final_answer",
                "content": "Max iterations reached.",
                "tool_calls": []
            }
            
        # Simulate LLM decision making
        # In real implementation, this calls the LLM with tools schema
        available_tools = self.get_available_tools()
        
        # Simple heuristic: if task mentions tool names, use them
        tool_calls = []
        for tool in available_tools:
            if tool["name"].lower() in task.lower():
                tool_calls.append({
                    "id": str(uuid.uuid4()),
                    "name": tool["name"],
                    "arguments": {"query": task}
                })
                
        if tool_calls:
            return {
                "action": "use_tools",
                "tool_calls": tool_calls
            }
        else:
            return {
                "action": "final_answer",
                "content": f"I've analyzed: {task}",
                "tool_calls": []
            }
            
    async def execute_tool_call(self, tool_call: Dict[str, Any]) -> ToolResult:
        """Execute a single tool call."""
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})
        
        result = self.tool_registry.execute(tool_name, **arguments)
        
        # Store in memory
        self._memory.append({
            "type": "tool_call",
            "tool": tool_name,
            "arguments": arguments,
            "result": result.output if result.success else None,
            "error": result.error
        })
        
        return result
        
    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run the agent on a task.
        
        Returns final answer after potentially multiple tool uses.
        """
        self._iteration_count = 0
        self._memory.append({"type": "task", "content": task})
        
        while self._iteration_count < 10:
            # Think
            thought = await self.think(task, context)
            
            if thought["action"] == "final_answer":
                return {
                    "success": True,
                    "answer": thought["content"],
                    "iterations": self._iteration_count,
                    "memory": self._memory.copy()
                }
                
            elif thought["action"] == "use_tools":
                for tool_call in thought.get("tool_calls", []):
                    result = await self.execute_tool_call(tool_call)
                    if not result.success:
                        # Handle error
                        pass
                        
                task = f"Continue with: {task}"
                
        return {
            "success": False,
            "answer": "Max iterations exceeded",
            "iterations": self._iteration_count,
            "memory": self._memory.copy()
        }
        
    def run_sync(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run agent synchronously."""
        return asyncio.run(self.run(task, context))
        
    def clear_memory(self) -> None:
        """Clear agent memory."""
        self._memory = []
        
    def get_memory(self) -> List[Dict[str, Any]]:
        """Get agent memory."""
        return self._memory.copy()
