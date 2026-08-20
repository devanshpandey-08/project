"""
Flow - The unified primitive that replaces Chains and Graphs.

FlowMind's core innovation: A single, intuitive API for all AI workflows.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Union, AsyncIterator
from dataclasses import dataclass, field

from flomind.core.flow import FlowState, FlowContext
from flomind.core.node import Node, NodeType
from flomind.core.edge import ConditionalEdge, edges_from
from flomind.core.executor import FlowExecutor
from flomind.core.types import FlowResult, RetryConfig, TimeoutConfig, CircuitBreakerConfig, FlowMetadata


@dataclass
class FlowBuilder:
    """Fluent builder for creating flows."""
    
    name: str
    description: str = ""
    _nodes: Dict[str, Node] = field(default_factory=dict)
    _edges: List[ConditionalEdge] = field(default_factory=list)
    _start_node: str = "start"
    _end_node: str = "end"
    _retry_config: Optional[RetryConfig] = None
    _timeout_config: Optional[TimeoutConfig] = None
    _circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    
    def add_node(self, node: Node) -> "FlowBuilder":
        """Add a node to the flow."""
        self._nodes[node.id] = node
        return self
    
    def add_edge(self, edge: ConditionalEdge) -> "FlowBuilder":
        """Add an edge to the flow."""
        # Update source if empty (for conditional edges)
        if not edge.source and self._edges:
            edge.source = self._edges[-1].target
        self._edges.append(edge)
        return self
    
    def add_edges(self, *edges: ConditionalEdge) -> "FlowBuilder":
        """Add multiple edges."""
        for edge in edges:
            self.add_edge(edge)
        return self
    
    def from_node(self, source: str) -> "FlowBuilder":
        """Start building edges from a node."""
        return self
    
    def chain(self, *node_ids: str) -> "FlowBuilder":
        """Create a simple chain of nodes."""
        if not node_ids:
            return self
        
        # Add start edge
        self._edges.append(ConditionalEdge(source=self._start_node, target=node_ids[0]))
        
        # Chain nodes
        for i in range(len(node_ids) - 1):
            self._edges.append(ConditionalEdge(source=node_ids[i], target=node_ids[i + 1]))
        
        # Add end edge
        self._edges.append(ConditionalEdge(source=node_ids[-1], target=self._end_node))
        
        return self
    
    def branch(
        self,
        from_node: str,
        conditions: List[tuple],  # [(condition_fn, target_node), ...]
        default: Optional[str] = None,
    ) -> "FlowBuilder":
        """Create branching logic from a node."""
        for condition, target in conditions:
            self._edges.append(ConditionalEdge(
                source=from_node,
                target=target,
                condition=condition
            ))
        
        if default:
            self._edges.append(ConditionalEdge(
                source=from_node,
                target=default,
                condition=None  # Default fallback
            ))
        
        return self
    
    def parallel(self, *node_ids: str) -> "FlowBuilder":
        """Mark nodes for parallel execution (future feature)."""
        # For now, just add them sequentially
        # Parallel execution will be implemented in executor
        return self
    
    def with_retry(self, config: RetryConfig) -> "FlowBuilder":
        """Set default retry configuration."""
        self._retry_config = config
        return self
    
    def with_timeout(self, config: TimeoutConfig) -> "FlowBuilder":
        """Set default timeout configuration."""
        self._timeout_config = config
        return self
    
    def with_circuit_breaker(self, config: CircuitBreakerConfig) -> "FlowBuilder":
        """Set circuit breaker configuration."""
        self._circuit_breaker_config = config
        return self
    
    def build(self) -> "Flow":
        """Build the flow."""
        # Ensure start and end nodes exist
        if self._start_node not in self._nodes:
            self._nodes[self._start_node] = Node(id=self._start_node, name="Start")
        if self._end_node not in self._nodes:
            self._nodes[self._end_node] = Node(id=self._end_node, name="End")
        
        return Flow(
            name=self.name,
            description=self.description,
            nodes=self._nodes,
            edges=self._edges,
            start_node=self._start_node,
            retry_config=self._retry_config,
            timeout_config=self._timeout_config,
            circuit_breaker_config=self._circuit_breaker_config,
        )


class Flow:
    """
    A Flow is the fundamental unit of work in FlowMind.
    
    Flows replace both LangChain's Chains and LangGraph's Graphs with a single,
    unified abstraction that handles:
    - Sequential chains
    - Directed graphs with cycles
    - Conditional branching
    - Parallel execution
    - Agent orchestration
    - Tool calling
    - Memory management
    
    Usage:
        # Simple chain
        flow = Flow("SimpleChain")
            .add_node(Node("step1", action=fn1))
            .add_node(Node("step2", action=fn2))
            .chain("step1", "step2")
            .build()
        
        # With conditions
        flow = Flow("DecisionFlow")
            .add_node(Node("check", action=check_fn))
            .add_node(Node("approve", action=approve_fn))
            .add_node(Node("reject", action=reject_fn))
            .branch("check", [
                (lambda ctx: ctx.state["approved"], "approve"),
                (lambda ctx: not ctx.state["approved"], "reject"),
            ])
            .build()
        
        # Execute
        result = await flow.run({"input": "data"})
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        nodes: Optional[Dict[str, Node]] = None,
        edges: Optional[List[ConditionalEdge]] = None,
        start_node: str = "start",
        end_node: str = "end",
        retry_config: Optional[RetryConfig] = None,
        timeout_config: Optional[TimeoutConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.name = name
        self.description = description
        self.nodes = nodes or {}
        self.edges = edges or []
        self.start_node = start_node
        self.end_node = end_node
        self.retry_config = retry_config
        self.timeout_config = timeout_config
        self.circuit_breaker_config = circuit_breaker_config
        self._executor = FlowExecutor(
            retry_config=retry_config,
            timeout_config=timeout_config,
            circuit_breaker_config=circuit_breaker_config,
        )
    
    @classmethod
    def create(cls, name: str, description: str = "") -> FlowBuilder:
        """Create a new flow using the fluent builder."""
        return FlowBuilder(name=name, description=description)
    
    async def run(
        self,
        input_data: Optional[Dict[str, Any]] = None,
        initial_state: Optional[FlowState] = None,
        metadata: Optional[FlowMetadata] = None,
    ) -> FlowResult[Any]:
        """
        Run the flow synchronously (async internally).
        
        Args:
            input_data: Initial input data
            initial_state: Pre-populated state (overrides input_data)
            metadata: Execution metadata
        
        Returns:
            FlowResult with execution outcome
        """
        # Prepare initial state
        if initial_state is None:
            initial_state = FlowState()
            if input_data:
                initial_state.update(input_data)
        
        return await self._executor.execute(
            nodes=self.nodes,
            edges=self.edges,
            initial_state=initial_state,
            start_node=self.start_node,
            metadata=metadata,
        )
    
    def run_sync(
        self,
        input_data: Optional[Dict[str, Any]] = None,
        initial_state: Optional[FlowState] = None,
        metadata: Optional[FlowMetadata] = None,
    ) -> FlowResult[Any]:
        """Run the flow synchronously (blocking)."""
        return asyncio.run(self.run(input_data, initial_state, metadata))
    
    async def stream(
        self,
        input_data: Optional[Dict[str, Any]] = None,
        initial_state: Optional[FlowState] = None,
    ) -> AsyncIterator[str]:
        """Stream flow execution results."""
        if initial_state is None:
            initial_state = FlowState()
            if input_data:
                initial_state.update(input_data)
        
        async for chunk in self._executor.execute_streaming(
            nodes=self.nodes,
            edges=self.edges,
            initial_state=initial_state,
            start_node=self.start_node,
        ):
            yield str(chunk)
    
    def add_node(self, node: Node) -> "Flow":
        """Add a node to the flow."""
        self.nodes[node.id] = node
        return self
    
    def add_edge(self, edge: ConditionalEdge) -> "Flow":
        """Add an edge to the flow."""
        self.edges.append(edge)
        return self
    
    def visualize(self) -> str:
        """Generate a text visualization of the flow."""
        lines = [f"Flow: {self.name}", "=" * 40]
        
        if self.description:
            lines.append(f"Description: {self.description}")
            lines.append("")
        
        lines.append("Nodes:")
        for node_id, node in self.nodes.items():
            lines.append(f"  - {node_id} ({node.node_type.value})")
        
        lines.append("")
        lines.append("Edges:")
        for edge in self.edges:
            condition = f" [{edge.label}]" if edge.label else ""
            lines.append(f"  {edge.source} --> {edge.target}{condition}")
        
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        return f"Flow(name={self.name}, nodes={len(self.nodes)}, edges={len(self.edges)})"


def create_flow(name: str, description: str = "") -> FlowBuilder:
    """Convenience function to create a flow."""
    return Flow.create(name, description)
