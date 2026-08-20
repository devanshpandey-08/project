"""
FlowMind Agents

Autonomous agents that can use tools, maintain memory, and collaborate.
Unlike LangChain's complex agent setup, FlowMind agents are simple yet powerful.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
import asyncio
import json

from flomind.tools.tool import Tool, ToolRegistry
from flomind.memory.short_term import ShortTermMemory


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str = "Agent"
    role: str = "Assistant"
    system_prompt: str = "You are a helpful assistant."
    max_iterations: int = 10
    temperature: float = 0.7
    model: str = "gpt-4o"


@dataclass
class Agent:
    """
    An autonomous agent that can use tools to accomplish tasks.
    
    Key Features:
    - Tool usage with automatic schema generation
    - Short-term memory for conversation context
    - Iterative reasoning (thought → action → observation)
    - Simple API for complex behavior
    """
    config: AgentConfig = field(default_factory=AgentConfig)
    tools: List[Tool] = field(default_factory=list)
    memory: ShortTermMemory = field(default_factory=ShortTermMemory)
    
    def __post_init__(self):
        self.tool_registry = ToolRegistry()
        for tool in self.tools:
            self.tool_registry.register(tool)
    
    async def execute(self, task: str, 
                     context: Optional[Dict[str, Any]] = None) -> str:
        """
        Execute a task using tools and reasoning.
        
        This is a simplified agent loop - in production, this would
        integrate with actual LLM providers.
        """
        self.memory.add_message("user", task)
        
        iteration = 0
        while iteration < self.config.max_iterations:
            iteration += 1
            
            # Build prompt with context
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                *self.memory.get_messages(),
            ]
            
            # In production: call LLM here
            # For now, simulate agent behavior
            if not self.tools:
                # No tools, just return a simple response
                response = f"Completed: {task}"
                self.memory.add_message("assistant", response)
                return response
            
            # Simulate tool usage (in production, LLM decides which tool)
            # This is placeholder logic
            tool_results = []
            for tool in self.tools:
                try:
                    # Try to extract parameters from task (simplified)
                    result = await tool.execute(query=task)
                    tool_results.append(f"{tool.name}: {result}")
                except Exception:
                    pass
            
            if tool_results:
                response = "\n".join(tool_results)
            else:
                response = f"Task completed: {task}"
            
            self.memory.add_message("assistant", response)
            return response
        
        return "Max iterations reached"
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible schemas for all tools."""
        return self.tool_registry.get_all_schemas()


class Team:
    """
    A team of agents working together.
    
    Unlike single agents, teams can:
    - Divide work among specialists
    - Review each other's output
    - Handle complex multi-step tasks
    """
    
    def __init__(self, agents: List[Agent], mode: str = "sequential"):
        self.agents = {agent.config.name: agent for agent in agents}
        self.mode = mode  # sequential, parallel, hierarchical
        self.results: Dict[str, Any] = {}
    
    async def execute(self, task: str) -> Dict[str, Any]:
        """Execute a task with the team."""
        if self.mode == "sequential":
            return await self._execute_sequential(task)
        elif self.mode == "parallel":
            return await self._execute_parallel(task)
        else:
            raise ValueError(f"Unknown team mode: {self.mode}")
    
    async def _execute_sequential(self, task: str) -> Dict[str, Any]:
        """Execute agents one after another, passing results."""
        current_task = task
        
        for name, agent in self.agents.items():
            result = await agent.execute(current_task)
            self.results[name] = result
            current_task = f"Previous result: {result}\n\nContinue with: {task}"
        
        return self.results
    
    async def _execute_parallel(self, task: str) -> Dict[str, Any]:
        """Execute all agents in parallel."""
        async def run_agent(name: str, agent: Agent):
            result = await agent.execute(task)
            return name, result
        
        tasks = [run_agent(name, agent) for name, agent in self.agents.items()]
        results = await asyncio.gather(*tasks)
        
        self.results = dict(results)
        return self.results
    
    def add_agent(self, agent: Agent):
        """Add an agent to the team."""
        self.agents[agent.config.name] = agent
    
    def remove_agent(self, name: str):
        """Remove an agent from the team."""
        if name in self.agents:
            del self.agents[name]
