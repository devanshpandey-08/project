"""
Workflow composition for FlowMind.

High-level workflow primitives for building complex AI applications.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Awaitable, Union
import asyncio

from ..core.flow import Flow, Node, Edge, FlowState, NodeType, EdgeCondition


@dataclass
class Workflow(Flow):
    """
    A high-level workflow built on top of Flow.
    
    Workflows provide a more declarative API for common patterns.
    """
    
    @classmethod
    def create(cls, name: str) -> 'Workflow':
        """Create a new workflow."""
        return cls(name=name)
    
    def add_step(self, name: str, handler: Callable, **kwargs) -> Node:
        """Add a step to the workflow."""
        return self.add_node(name=name, handler=handler, **kwargs)
    
    def chain(self, *steps: Union[str, Node]) -> 'Workflow':
        """Chain steps together sequentially."""
        for i in range(len(steps) - 1):
            self.add_edge(steps[i], steps[i + 1])
        return self
    
    def branch(
        self,
        source: Union[str, Node],
        targets: Dict[str, Union[str, Node]],
        condition: Callable[[FlowState], str]
    ) -> 'Workflow':
        """Add conditional branching."""
        self.add_conditional_edges(source, targets, condition)
        return self
    
    def parallel(self, *steps: Union[str, Node]) -> 'Workflow':
        """Run steps in parallel (conceptually - actual parallelism depends on execution)."""
        # Create a virtual parallel node
        parallel_id = f"parallel_{len(self.nodes)}"
        
        async def parallel_handler(state: FlowState) -> Dict[str, Any]:
            results = {}
            for step in steps:
                step_id = step if isinstance(step, str) else step.id
                if step_id in self.outputs:
                    results[step_id] = self.outputs[step_id]
            return results
        
        self.add_node(parallel_id, handler=parallel_handler, node_type=NodeType.PARALLEL)
        
        for step in steps:
            step_id = step if isinstance(step, str) else step.id
            self.add_edge(parallel_id, step_id)
        
        return self


# Composition operators
class Sequential:
    """Sequential composition of workflows."""
    
    def __init__(self, *workflows: Union[Workflow, Callable]):
        self.workflows = workflows
    
    async def execute(self, state: FlowState) -> Any:
        result = None
        for wf in self.workflows:
            if callable(wf):
                result = await wf(state)
            else:
                state = await wf.run(state)
                result = state
        return result


class Parallel:
    """Parallel composition of workflows."""
    
    def __init__(self, *workflows: Union[Workflow, Callable]):
        self.workflows = workflows
    
    async def execute(self, state: FlowState) -> Dict[str, Any]:
        async def run_wf(wf, name):
            if callable(wf):
                return await wf(state)
            else:
                result = await wf.run(state)
                return result
        
        tasks = [run_wf(wf, f"wf_{i}") for i, wf in enumerate(self.workflows)]
        results = await asyncio.gather(*tasks)
        
        return {f"result_{i}": r for i, r in enumerate(results)}


class Conditional:
    """Conditional execution based on state."""
    
    def __init__(
        self,
        condition: Callable[[FlowState], bool],
        then_branch: Union[Workflow, Callable],
        else_branch: Optional[Union[Workflow, Callable]] = None
    ):
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch
    
    async def execute(self, state: FlowState) -> Any:
        if self.condition(state):
            branch = self.then_branch
        elif self.else_branch:
            branch = self.else_branch
        else:
            return None
        
        if callable(branch):
            return await branch(state)
        else:
            result = await branch.run(state)
            return result


class Loop:
    """Loop execution until condition is met."""
    
    def __init__(
        self,
        body: Union[Workflow, Callable],
        until: Callable[[FlowState], bool],
        max_iterations: int = 10
    ):
        self.body = body
        self.until = until
        self.max_iterations = max_iterations
    
    async def execute(self, state: FlowState) -> Any:
        iterations = 0
        result = None
        
        while iterations < self.max_iterations and not self.until(state):
            if callable(self.body):
                result = await self.body(state)
            else:
                state = await self.body.run(state)
                result = state
            iterations += 1
        
        return result
