"""
Agent system for FlowMind.

Provides intelligent agent capabilities with tool use, memory, and multi-agent coordination.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Awaitable, Union, Type
from enum import Enum
import asyncio
import uuid

from ..llm.provider import LLM, Message, ChatRole, LLMResponse, create_llm
from ..tools.tool import Tool
from ..memory.memory import Memory, ShortTermMemory, LongTermMemory
from ..core.state import FlowState


class Role(Enum):
    """Agent roles in a team."""
    MANAGER = "manager"
    RESEARCHER = "researcher"
    WRITER = "writer"
    CODER = "coder"
    REVIEWER = "reviewer"
    PLANNER = "planner"
    EXECUTOR = "executor"
    CRITIC = "critic"
    CUSTOM = "custom"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    role: Role = Role.CUSTOM
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_iterations: int = 10
    tools: List[Tool] = field(default_factory=list)
    system_prompt: Optional[str] = None
    memory: Optional[Memory] = None
    verbose: bool = False


@dataclass
class Agent:
    """
    An autonomous agent capable of using tools, maintaining memory, and completing tasks.
    
    Agents are the building blocks for complex AI systems, replacing LangChain's agents
    with a more flexible, type-safe implementation.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    config: AgentConfig = field(default_factory=lambda: AgentConfig(name=""))
    llm: Optional[LLM] = None
    is_running: bool = False
    
    # Execution stats
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    
    def __post_init__(self):
        if self.config.name == "":
            self.config.name = f"agent_{self.id}"
        if self.llm is None:
            self.llm = create_llm(
                model=self.config.model,
                temperature=self.config.temperature
            )
        if self.config.memory is None:
            self.config.memory = ShortTermMemory(max_messages=100)
    
    @classmethod
    def create(
        cls,
        name: str,
        role: Role = Role.CUSTOM,
        model: str = "gpt-4o",
        tools: Optional[List[Tool]] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> 'Agent':
        """Factory method to create an agent."""
        config = AgentConfig(
            name=name,
            role=role,
            model=model,
            tools=tools or [],
            system_prompt=system_prompt,
            **kwargs
        )
        return cls(config=config)
    
    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        state: Optional[FlowState] = None
    ) -> AgentResult:
        """Execute a task with the agent."""
        if self.is_running:
            raise RuntimeError("Agent is already running")
        
        self.is_running = True
        self.total_tasks += 1
        
        try:
            # Build messages
            messages = self._build_messages(task, context, state)
            
            # Execute with tool loop
            result = await self._execute_with_tools(messages, state)
            
            if result.success:
                self.successful_tasks += 1
            else:
                self.failed_tasks += 1
            
            return result
            
        finally:
            self.is_running = False
    
    def _build_messages(
        self,
        task: str,
        context: Optional[Dict[str, Any]],
        state: Optional[FlowState]
    ) -> List[Message]:
        """Build the message list for the agent."""
        messages = []
        
        # System prompt
        system_content = self.config.system_prompt or self._default_system_prompt()
        messages.append(Message.system(system_content))
        
        # Add memory if available
        if self.config.memory:
            memory_messages = self.config.memory.get_messages()
            messages.extend(memory_messages)
        
        # Add context
        if context:
            context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
            messages.append(Message.user(f"Context:\n{context_str}"))
        
        # Add task
        messages.append(Message.user(task))
        
        return messages
    
    def _default_system_prompt(self) -> str:
        """Generate default system prompt based on role."""
        role_prompts = {
            Role.MANAGER: "You are a project manager. Break down complex tasks and coordinate work.",
            Role.RESEARCHER: "You are a researcher. Find accurate information and cite sources.",
            Role.WRITER: "You are a writer. Create clear, engaging content.",
            Role.CODER: "You are a software engineer. Write clean, efficient, well-documented code.",
            Role.REVIEWER: "You are a reviewer. Critically analyze work and provide constructive feedback.",
            Role.PLANNER: "You are a planner. Create detailed, actionable plans.",
            Role.EXECUTOR: "You are an executor. Complete tasks efficiently and accurately.",
            Role.CRITIC: "You are a critic. Identify flaws and suggest improvements.",
        }
        
        base = role_prompts.get(self.config.role, "You are a helpful AI assistant.")
        
        if self.config.tools:
            tool_names = ", ".join(t.name for t in self.config.tools)
            base += f"\n\nYou have access to these tools: {tool_names}"
        
        return base
    
    async def _execute_with_tools(
        self,
        messages: List[Message],
        state: Optional[FlowState],
        iteration: int = 0
    ) -> AgentResult:
        """Execute the agent loop with tool calling."""
        if iteration >= self.config.max_iterations:
            return AgentResult.fail(
                agent_id=self.id,
                error=RuntimeError(f"Max iterations ({self.config.max_iterations}) exceeded"),
                iterations=iteration
            )
        
        # Get LLM response
        response = await self.llm.chat(messages)
        
        # Check for tool calls
        if response.tool_calls:
            tool_results = []
            
            for tool_call in response.tool_calls:
                tool_name = tool_call['function']['name']
                tool_args = tool_call['function']['arguments']
                
                # Find and execute tool
                tool = self._find_tool(tool_name)
                if tool:
                    try:
                        import json
                        args = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
                        result = await tool.execute(**args)
                        tool_results.append({
                            'tool_call_id': tool_call['id'],
                            'name': tool_name,
                            'result': result
                        })
                        
                        # Add tool response to messages
                        messages.append(Message.tool(
                            content=str(result),
                            tool_call_id=tool_call['id']
                        ))
                    except Exception as e:
                        tool_results.append({
                            'tool_call_id': tool_call['id'],
                            'name': tool_name,
                            'error': str(e)
                        })
                else:
                    tool_results.append({
                        'tool_call_id': tool_call['id'],
                        'name': tool_name,
                        'error': f"Tool '{tool_name}' not found"
                    })
            
            # Continue the loop with tool results
            return await self._execute_with_tools(messages, state, iteration + 1)
        
        # No tool calls, return final result
        # Store in memory
        if self.config.memory:
            self.config.memory.add_message(Message.user(messages[-1].content))
            self.config.memory.add_message(Message.assistant(response.content))
        
        return AgentResult.ok(
            agent_id=self.id,
            output=response.content,
            iterations=iteration + 1,
            tool_calls=len(response.tool_calls) if response.tool_calls else 0,
            tokens_used=response.total_tokens,
            cost_usd=response.cost_usd
        )
    
    def _find_tool(self, name: str) -> Optional[Tool]:
        """Find a tool by name."""
        for tool in self.config.tools:
            if tool.name == name:
                return tool
        return None
    
    def add_tool(self, tool: Tool) -> None:
        """Add a tool to the agent."""
        self.config.tools.append(tool)
    
    def remove_tool(self, name: str) -> bool:
        """Remove a tool by name."""
        for i, tool in enumerate(self.config.tools):
            if tool.name == name:
                self.config.tools.pop(i)
                return True
        return False
    
    def clear_memory(self) -> None:
        """Clear the agent's memory."""
        if self.config.memory:
            self.config.memory.clear()
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            'id': self.id,
            'name': self.config.name,
            'role': self.config.role.value,
            'total_tasks': self.total_tasks,
            'successful_tasks': self.successful_tasks,
            'failed_tasks': self.failed_tasks,
            'success_rate': self.successful_tasks / max(self.total_tasks, 1),
            'tools': [t.name for t in self.config.tools],
            'model': self.config.model,
        }


@dataclass
class AgentResult:
    """Result from agent execution."""
    agent_id: str
    success: bool
    output: Any
    error: Optional[Exception] = None
    iterations: int = 0
    tool_calls: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    
    @classmethod
    def ok(cls, agent_id: str, output: Any, **kwargs) -> 'AgentResult':
        return cls(agent_id=agent_id, success=True, output=output, **kwargs)
    
    @classmethod
    def fail(cls, agent_id: str, error: Exception, **kwargs) -> 'AgentResult':
        return cls(agent_id=agent_id, success=False, output=None, error=error, **kwargs)
