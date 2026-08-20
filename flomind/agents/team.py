"""Team orchestration for multi-agent collaboration."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal
from enum import Enum

from flomind.agents.agent import Agent, AgentConfig
from flomind.core.flow import FlowState, FlowContext
from flomind.core.node import Node


class TeamMode(Enum):
    """Mode of team collaboration."""
    SEQUENTIAL = "sequential"  # Agents work one after another
    PARALLEL = "parallel"  # Agents work simultaneously
    HIERARCHICAL = "hierarchical"  # Manager delegates to workers
    CONSENSUS = "consensus"  # All agents must agree


@dataclass
class TeamConfig:
    """Configuration for a team."""
    name: str
    mode: TeamMode = TeamMode.SEQUENTIAL
    verbose: bool = True
    max_rounds: int = 5


class Team:
    """
    Multi-agent team for collaborative task completion.
    
    Teams enable multiple agents to work together using different
    collaboration patterns:
    
    - Sequential: Each agent builds on previous work
    - Parallel: Agents work independently, results combined
    - Hierarchical: Manager delegates to specialized workers
    - Consensus: All agents discuss and reach agreement
    
    Usage:
        team = Team("ResearchTeam")
            .add_agent(researcher)
            .add_agent(writer)
            .add_agent(reviewer)
        
        result = await team.run("Write a report on AI trends")
    """
    
    def __init__(
        self,
        name: str,
        manager: Optional[Agent] = None,
        config: Optional[TeamConfig] = None,
    ):
        self.name = name
        self.manager = manager
        self.agents: List[Agent] = []
        self.config = config or TeamConfig(name=name)
        self._agent_registry: Dict[str, Agent] = {}
    
    def add_agent(self, agent: Agent) -> "Team":
        """Add an agent to the team."""
        self.agents.append(agent)
        self._agent_registry[agent.name] = agent
        return self
    
    def remove_agent(self, agent_name: str) -> "Team":
        """Remove an agent from the team."""
        if agent_name in self._agent_registry:
            del self._agent_registry[agent_name]
            self.agents = [a for a in self.agents if a.name != agent_name]
        return self
    
    async def _run_sequential(
        self,
        task: str,
        context: Optional[FlowContext] = None,
    ) -> Any:
        """Run agents sequentially, each building on previous work."""
        current_result = task
        
        for agent in self.agents:
            if context and context.is_cancelled():
                break
            
            # Pass previous result as context
            agent_task = f"{current_result}\n\nYour contribution:"
            current_result = await agent.run(agent_task, context)
        
        return current_result
    
    async def _run_parallel(
        self,
        task: str,
        context: Optional[FlowContext] = None,
    ) -> Any:
        """Run all agents in parallel and combine results."""
        async def run_agent(agent: Agent) -> tuple:
            result = await agent.run(task, context)
            return (agent.name, result)
        
        tasks = [run_agent(agent) for agent in self.agents]
        results = await asyncio.gather(*tasks)
        
        # Combine results
        combined = "\n\n".join([f"### {name}\n{result}" for name, result in results])
        return combined
    
    async def _run_hierarchical(
        self,
        task: str,
        context: Optional[FlowContext] = None,
    ) -> Any:
        """Manager delegates tasks to worker agents."""
        if not self.manager:
            # Use first agent as de facto manager
            return await self._run_sequential(task, context)
        
        # Manager plans and delegates
        plan = await self.manager.run(f"Plan how to accomplish: {task}", context)
        
        # Execute plan with workers
        results = []
        for agent in self.agents:
            if context and context.is_cancelled():
                break
            
            agent_task = f"Based on this plan: {plan}\n\nYour specific task:"
            result = await agent.run(agent_task, context)
            results.append((agent.name, result))
        
        # Manager synthesizes final result
        synthesis_input = "\n\n".join([f"### {name}\n{result}" for name, result in results])
        final = await self.manager.run(
            f"Synthesize these results into a coherent output:\n{synthesis_input}",
            context
        )
        
        return final
    
    async def _run_consensus(
        self,
        task: str,
        context: Optional[FlowContext] = None,
    ) -> Any:
        """All agents discuss and reach consensus."""
        if not self.agents:
            return ""
        
        # Round 1: Each agent provides initial thoughts
        initial_thoughts = []
        for agent in self.agents:
            thought = await agent.run(f"Initial thoughts on: {task}", context)
            initial_thoughts.append(f"{agent.name}: {thought}")
        
        discussion = "\n\n".join(initial_thoughts)
        
        # Round 2+: Agents refine based on others' input
        for round_num in range(1, self.config.max_rounds):
            refined = []
            for agent in self.agents:
                if context and context.is_cancelled():
                    break
                
                prompt = f"""Previous discussion:
{discussion}

Refine your position considering others' viewpoints:"""
                refined_thought = await agent.run(prompt, context)
                refined.append(f"{agent.name} (round {round_num}): {refined_thought}")
            
            discussion = "\n\n".join(refined)
        
        return f"Final consensus after {self.config.max_rounds} rounds:\n{discussion}"
    
    async def run(
        self,
        task: str,
        context: Optional[FlowContext] = None,
    ) -> Any:
        """
        Run the team on a task.
        
        Args:
            task: The task to accomplish
            context: Optional flow context
        
        Returns:
            Combined result from all agents
        """
        if self.config.mode == TeamMode.SEQUENTIAL:
            return await self._run_sequential(task, context)
        elif self.config.mode == TeamMode.PARALLEL:
            return await self._run_parallel(task, context)
        elif self.config.mode == TeamMode.HIERARCHICAL:
            return await self._run_hierarchical(task, context)
        elif self.config.mode == TeamMode.CONSENSUS:
            return await self._run_consensus(task, context)
        else:
            return await self._run_sequential(task, context)
    
    def run_sync(self, task: str, context: Optional[FlowContext] = None) -> Any:
        """Run the team synchronously."""
        return asyncio.run(self.run(task, context))
    
    def to_node(self) -> Node:
        """Convert team to a Flow node."""
        async def team_action(ctx: FlowContext) -> Any:
            task = ctx.state.get("task", ctx.state.get("input", ""))
            return await self.run(task, ctx)
        
        return Node(
            id=f"team_{self.name.lower().replace(' ', '_')}",
            action=team_action,
            name=self.name,
            description=f"Team ({self.config.mode.value}): {len(self.agents)} agents",
        )
    
    def __repr__(self) -> str:
        return f"Team(name={self.name}, mode={self.config.mode.value}, agents={len(self.agents)})"
