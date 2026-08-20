"""
Multi-agent team coordination for FlowMind.

Enables collaborative problem-solving with multiple specialized agents.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import asyncio

from .agent import Agent, AgentResult, Role


@dataclass
class TeamConfig:
    """Configuration for an agent team."""
    name: str
    coordination_strategy: str = "sequential"  # sequential, parallel, hierarchical
    max_rounds: int = 5
    verbose: bool = False


@dataclass
class AgentTeam:
    """
    A team of agents working together on complex tasks.
    
    Teams enable multi-agent collaboration patterns that replace LangGraph's
    multi-agent workflows with simpler, more intuitive APIs.
    """
    id: str = field(default_factory=lambda: "team_" + str(hash(str(id())))[:8])
    config: TeamConfig = field(default_factory=lambda: TeamConfig(name=""))
    agents: Dict[str, Agent] = field(default_factory=dict)
    shared_context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.config.name == "":
            self.config.name = self.id
    
    @classmethod
    def create(cls, name: str, strategy: str = "sequential") -> 'AgentTeam':
        """Factory method to create a team."""
        config = TeamConfig(name=name, coordination_strategy=strategy)
        return cls(config=config)
    
    def add_agent(self, agent: Agent, role_name: Optional[str] = None) -> 'AgentTeam':
        """Add an agent to the team."""
        name = role_name or f"{agent.config.role.value}_{len(self.agents)}"
        self.agents[name] = agent
        return self
    
    def remove_agent(self, role_name: str) -> bool:
        """Remove an agent from the team."""
        if role_name in self.agents:
            del self.agents[role_name]
            return True
        return False
    
    async def run(self, task: str) -> TeamResult:
        """Execute a task with the team."""
        if not self.agents:
            return TeamResult.fail(error=ValueError("No agents in team"))
        
        results = []
        context = {"task": task, **self.shared_context}
        
        if self.config.coordination_strategy == "parallel":
            # Run all agents in parallel
            tasks = [
                agent.run(task, context={**context, "agent_role": name})
                for name, agent in self.agents.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        elif self.config.coordination_strategy == "hierarchical":
            # Manager coordinates other agents
            manager = self._get_manager()
            if manager:
                result = await manager.run(task, context=context)
                results.append(result)
            else:
                # Fallback to sequential
                results = await self._run_sequential(task, context)
        else:
            # Default: sequential execution
            results = await self._run_sequential(task, context)
        
        # Process results
        successful = [r for r in results if isinstance(r, AgentResult) and r.success]
        failed = [r for r in results if isinstance(r, AgentResult) and not r.success]
        errors = [r for r in results if isinstance(r, Exception)]
        
        return TeamResult(
            team_id=self.id,
            success=len(successful) > 0 and len(errors) == 0,
            results=successful,
            failures=failed,
            errors=errors,
            total_cost=sum(r.cost_usd for r in successful if isinstance(r, AgentResult)),
            total_tokens=sum(r.tokens_used for r in successful if isinstance(r, AgentResult))
        )
    
    async def _run_sequential(self, task: str, context: Dict[str, Any]) -> List[Union[AgentResult, Exception]]:
        """Run agents sequentially, passing context between them."""
        results = []
        current_task = task
        
        for name, agent in self.agents.items():
            try:
                result = await agent.run(current_task, context=context)
                results.append(result)
                
                if result.success:
                    # Update context with result for next agent
                    context[f"result_from_{name}"] = result.output
                    current_task = f"{current_task}\n\nPrevious work by {name}: {result.output}"
                    
            except Exception as e:
                results.append(e)
                if self.config.verbose:
                    print(f"Agent {name} failed: {e}")
        
        return results
    
    def _get_manager(self) -> Optional[Agent]:
        """Get the manager agent if one exists."""
        for name, agent in self.agents.items():
            if agent.config.role == Role.MANAGER:
                return agent
        return None
    
    def set_shared_context(self, **kwargs) -> None:
        """Set shared context for all agents."""
        self.shared_context.update(kwargs)
    
    def clear_shared_context(self) -> None:
        """Clear shared context."""
        self.shared_context.clear()
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get team statistics."""
        return {
            'id': self.id,
            'name': self.config.name,
            'strategy': self.config.coordination_strategy,
            'agent_count': len(self.agents),
            'agents': {name: agent.stats for name, agent in self.agents.items()},
        }


@dataclass
class TeamResult:
    """Result from team execution."""
    team_id: str
    success: bool
    results: List[AgentResult] = field(default_factory=list)
    failures: List[AgentResult] = field(default_factory=list)
    errors: List[Exception] = field(default_factory=list)
    total_cost: float = 0.0
    total_tokens: int = 0
    
    @classmethod
    def ok(cls, team_id: str, results: List[AgentResult], **kwargs) -> 'TeamResult':
        return cls(team_id=team_id, success=True, results=results, **kwargs)
    
    @classmethod
    def fail(cls, error: Exception, **kwargs) -> 'TeamResult':
        return cls(team_id="", success=False, errors=[error], **kwargs)
