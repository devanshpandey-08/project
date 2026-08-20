"""Agent system for FlowMind - autonomous AI agents with tool usage."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union, Awaitable

from flomind.core.flow import FlowState, FlowContext
from flomind.core.node import Node, NodeType
from flomind.tools.tool import Tool
from flomind.memory.short_term import ShortTermMemory


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    role: str = ""
    goal: str = ""
    backstory: str = ""
    temperature: float = 0.7
    max_iterations: int = 10
    verbose: bool = True


class Agent:
    """
    Autonomous AI agent that can use tools and make decisions.
    
    Agents are self-contained units that:
    - Have a specific role and goal
    - Can use tools to accomplish tasks
    - Maintain short-term memory of conversations
    - Can work independently or in teams
    
    Usage:
        agent = Agent(
            name="Researcher",
            role="Research specialist",
            goal="Find accurate information",
            tools=[search_tool, read_tool],
        )
        
        result = await agent.run("Research quantum computing")
    """
    
    def __init__(
        self,
        name: str,
        role: str = "Assistant",
        goal: str = "Help the user",
        backstory: str = "",
        tools: Optional[List[Tool]] = None,
        config: Optional[AgentConfig] = None,
        llm_provider: Optional[Any] = None,
    ):
        self.name = name
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.config = config or AgentConfig(name=name, role=role, goal=goal, backstory=backstory)
        self.llm_provider = llm_provider
        self.memory = ShortTermMemory(max_messages=20)
        self._tool_registry: Dict[str, Tool] = {t.name: t for t in self.tools}
    
    def add_tool(self, tool: Tool) -> "Agent":
        """Add a tool to the agent."""
        self.tools.append(tool)
        self._tool_registry[tool.name] = tool
        return self
    
    def remove_tool(self, tool_name: str) -> "Agent":
        """Remove a tool from the agent."""
        if tool_name in self._tool_registry:
            del self._tool_registry[tool_name]
            self.tools = [t for t in self.tools if t.name != tool_name]
        return self
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        parts = [
            f"You are {self.name}.",
            f"Role: {self.role}",
            f"Goal: {self.goal}",
        ]
        
        if self.backstory:
            parts.append(f"Backstory: {self.backstory}")
        
        if self.tools:
            tool_descriptions = "\n".join([f"- {t.name}: {t.description}" for t in self.tools])
            parts.append(f"\nYou have access to these tools:\n{tool_descriptions}")
        
        parts.append("\nThink step by step and use tools when needed.")
        
        return "\n".join(parts)
    
    async def run(
        self,
        task: str,
        context: Optional[FlowContext] = None,
        stream: bool = False,
    ) -> Any:
        """
        Run the agent on a task.
        
        Args:
            task: The task to accomplish
            context: Optional flow context for state sharing
            stream: Whether to stream intermediate results
        
        Returns:
            The final result of the agent's work
        """
        # Add task to memory
        self.memory.add_user_message(task)
        
        system_prompt = self._build_system_prompt()
        iterations = 0
        final_result = None
        
        while iterations < self.config.max_iterations:
            iterations += 1
            
            # Get conversation history
            messages = self.memory.get_messages()
            
            # Call LLM (placeholder - would use actual provider)
            if self.llm_provider:
                response = await self.llm_provider.chat(
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=self.tools,
                )
            else:
                # Simulated response for demo
                response = {
                    "content": f"Completed task: {task}",
                    "tool_calls": []
                }
            
            # Handle tool calls
            if response.get("tool_calls"):
                for tool_call in response["tool_calls"]:
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("arguments", {})
                    
                    if tool_name in self._tool_registry:
                        tool = self._tool_registry[tool_name]
                        try:
                            result = await tool.execute(**tool_args)
                            self.memory.add_tool_result(tool_name, result)
                        except Exception as e:
                            self.memory.add_tool_result(tool_name, f"Error: {e}")
                    else:
                        self.memory.add_tool_result(tool_name, f"Tool not found: {tool_name}")
            else:
                # No tool calls, we have our final answer
                final_result = response.get("content", "")
                self.memory.add_assistant_message(final_result)
                break
        
        return final_result
    
    def run_sync(self, task: str, context: Optional[FlowContext] = None) -> Any:
        """Run the agent synchronously."""
        return asyncio.run(self.run(task, context))
    
    def to_node(self) -> Node:
        """Convert agent to a Flow node."""
        async def agent_action(ctx: FlowContext) -> Any:
            task = ctx.state.get("task", ctx.state.get("input", ""))
            return await self.run(task, ctx)
        
        return Node(
            id=f"agent_{self.name.lower().replace(' ', '_')}",
            node_type=NodeType.AGENT,
            action=agent_action,
            name=self.name,
            description=f"Agent: {self.role}",
        )
    
    def __repr__(self) -> str:
        return f"Agent(name={self.name}, role={self.role}, tools={len(self.tools)})"
