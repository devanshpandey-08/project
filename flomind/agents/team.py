"""Multi-Agent Team orchestration."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from flomind.agents.agent import Agent


class TeamStrategy(Enum):
    """Strategies for team execution."""
    SEQUENTIAL = "sequential"  # Agents work one after another
    PARALLEL = "parallel"  # Agents work simultaneously
    HIERARCHICAL = "hierarchical"  # Manager delegates to workers
    DEBATE = "debate"  # Agents debate and reach consensus


@dataclass
class TeamConfig:
    """Configuration for a team."""
    name: str
    strategy: TeamStrategy = TeamStrategy.SEQUENTIAL
    agents: List[Agent] = field(default_factory=list)
    max_rounds: int = 3
    

class Team:
    """
    Multi-Agent Team for complex task orchestration.
    
    Features:
    - Multiple execution strategies
    - Agent coordination
    - Result aggregation
    - Conflict resolution
    """
    
    def __init__(
        self,
        name: str,
        strategy: str = "sequential",
        agents: Optional[List[Agent]] = None,
        **kwargs
    ):
        self.name = name
        self.strategy = TeamStrategy(strategy.lower())
        self.agents = agents or []
        self.max_rounds = kwargs.get("max_rounds", 3)
        self._results: List[Dict[str, Any]] = []
        
    def add_agent(self, agent: Agent) -> 'Team':
        """Add an agent to the team."""
        self.agents.append(agent)
        return self
        
    def remove_agent(self, agent_name: str) -> bool:
        """Remove an agent from the team."""
        for i, agent in enumerate(self.agents):
            if agent.name == agent_name:
                self.agents.pop(i)
                return True
        return False
        
    async def _run_sequential(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run agents sequentially, passing results between them."""
        current_task = task
        results = []
        
        for agent in self.agents:
            result = await agent.run(current_task, context)
            results.append({
                "agent": agent.name,
                "result": result
            })
            
            if result.get("answer"):
                current_task = f"Previous result: {result['answer']}. Continue: {task}"
                
        # Aggregate results
        final_answer = results[-1]["result"].get("answer", "") if results else ""
        
        return {
            "success": all(r["result"].get("success", False) for r in results),
            "answer": final_answer,
            "agent_results": results,
            "strategy": "sequential"
        }
        
    async def _run_parallel(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run all agents in parallel."""
        tasks = [agent.run(task, context) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        agent_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                agent_results.append({
                    "agent": self.agents[i].name,
                    "error": str(result)
                })
            else:
                agent_results.append({
                    "agent": self.agents[i].name,
                    "result": result
                })
                
        # Simple aggregation: take first successful answer
        final_answer = ""
        for ar in agent_results:
            if "result" in ar and ar["result"].get("answer"):
                final_answer = ar["result"]["answer"]
                break
                
        return {
            "success": True,
            "answer": final_answer,
            "agent_results": agent_results,
            "strategy": "parallel"
        }
        
    async def _run_hierarchical(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run with manager delegating to workers."""
        if not self.agents:
            return {"success": False, "answer": "No agents in team"}
            
        # First agent is manager
        manager = self.agents[0]
        workers = self.agents[1:] if len(self.agents) > 1 else []
        
        # Manager analyzes task
        manager_result = await manager.run(
            f"As manager, analyze and delegate: {task}",
            context
        )
        
        if not workers:
            return {
                "success": manager_result.get("success", False),
                "answer": manager_result.get("answer", ""),
                "agent_results": [{"agent": manager.name, "result": manager_result}],
                "strategy": "hierarchical"
            }
            
        # Delegate to workers
        worker_tasks = []
        for worker in workers:
            worker_task = f"As {worker.role}, help with: {task}"
            worker_tasks.append(worker.run(worker_task, context))
            
        worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)
        
        # Manager synthesizes
        synthesis_task = f"Synthesize these results: {[r for r in worker_results]}"
        final_result = await manager.run(synthesis_task, context)
        
        return {
            "success": final_result.get("success", False),
            "answer": final_result.get("answer", ""),
            "manager_result": manager_result,
            "worker_results": list(worker_results),
            "strategy": "hierarchical"
        }
        
    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the team on a task using configured strategy."""
        if self.strategy == TeamStrategy.SEQUENTIAL:
            return await self._run_sequential(task, context)
        elif self.strategy == TeamStrategy.PARALLEL:
            return await self._run_parallel(task, context)
        elif self.strategy == TeamStrategy.HIERARCHICAL:
            return await self._run_hierarchical(task, context)
        else:
            # Default to sequential for unknown strategies
            return await self._run_sequential(task, context)
            
    def run_sync(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run team synchronously."""
        return asyncio.run(self.run(task, context))
        
    def get_agents_info(self) -> List[Dict[str, Any]]:
        """Get information about all agents."""
        return [
            {"name": a.name, "role": a.role, "tools_count": len(a.tools)}
            for a in self.agents
        ]
