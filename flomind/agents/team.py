"""
FlowMind Agents - Team Module

Multi-agent team coordination for complex tasks.
"""

from typing import List, Dict, Any
import asyncio


class TeamMode:
    """Team execution modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"


class Team:
    """
    A team of agents working together on complex tasks.
    
    Unlike single agents, teams can:
    - Divide work among specialists (Researcher, Writer, Reviewer)
    - Execute in sequence or parallel
    - Share context and results
    """
    
    def __init__(self, agents: List[Any], mode: str = TeamMode.SEQUENTIAL):
        self.agents = {agent.config.name: agent for agent in agents}
        self.mode = mode
        self.results: Dict[str, Any] = {}
    
    async def execute(self, task: str) -> Dict[str, Any]:
        """Execute a task with the team."""
        if self.mode == TeamMode.SEQUENTIAL:
            return await self._execute_sequential(task)
        elif self.mode == TeamMode.PARALLEL:
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
        async def run_agent(name: str, agent):
            result = await agent.execute(task)
            return name, result
        
        tasks = [run_agent(name, agent) for name, agent in self.agents.items()]
        results = await asyncio.gather(*tasks)
        
        self.results = dict(results)
        return self.results
    
    def add_agent(self, agent):
        """Add an agent to the team."""
        self.agents[agent.config.name] = agent
    
    def remove_agent(self, name: str):
        """Remove an agent from the team."""
        if name in self.agents:
            del self.agents[name]
    
    def list_agents(self) -> List[str]:
        """List all agent names in the team."""
        return list(self.agents.keys())
