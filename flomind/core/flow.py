"""
Core flow primitives for FlowMind.

Provides the fundamental building blocks: Flow, Node, Edge, and State management.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Dict, List, Optional, Generic, TypeVar, Union, Literal
from enum import Enum
import asyncio
import uuid
import time
from datetime import datetime

from .state import FlowState, NodeResult, StateSnapshot

T = TypeVar('T')
S = TypeVar('S', bound=FlowState)


class NodeType(Enum):
    """Types of nodes in a flow."""
    ACTION = "action"
    DECISION = "decision"
    TRANSFORM = "transform"
    AGENT = "agent"
    TOOL = "tool"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    CUSTOM = "custom"


class EdgeCondition(Enum):
    """Conditions for edge traversal."""
    ALWAYS = "always"
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    CUSTOM = "custom"


# Backwards compatible alias
State = FlowState


@dataclass
class NodeConfig:
    """Configuration for a node."""
    name: str
    node_type: NodeType = NodeType.CUSTOM
    timeout_seconds: float = 60.0
    retry_count: int = 3
    cache_enabled: bool = False
    cache_ttl_seconds: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Node(Generic[S]):
    """
    A node in a flow graph.

    Nodes are the fundamental execution units in FlowMind.
    Each node receives state, performs computation, and returns updated state.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    config: NodeConfig = field(default_factory=lambda: NodeConfig(name=""))
    handler: Optional[Callable[[S], Awaitable[Any]]] = None
    sync_handler: Optional[Callable[[S], Any]] = None

    # Execution tracking
    executions: int = 0
    last_execution: Optional[datetime] = None
    avg_duration_ms: float = 0.0

    # Cache
    _cache: Dict[str, Any] = field(default_factory=dict)
    _cache_timestamps: Dict[str, datetime] = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            self.name = f"node_{self.id}"
        if self.config.name == "":
            self.config.name = self.name

    async def execute(self, state: S) -> NodeResult:
        """Execute the node with given state."""
        start_time = time.time()
        self.executions += 1
        self.last_execution = datetime.now()

        try:
            # Check cache
            if self.config.cache_enabled:
                cache_key = self._compute_cache_key(state)
                if cache_key in self._cache:
                    cached_time = self._cache_timestamps.get(cache_key)
                    if cached_time:
                        age = (datetime.now() - cached_time).total_seconds()
                        if age < self.config.cache_ttl_seconds:
                            return NodeResult.ok(
                                node_id=self.id,
                                output=self._cache[cache_key],
                                metadata={'cached': True}
                            )

            # Execute handler
            if self.handler:
                result = await self.handler(state)
            elif self.sync_handler:
                result = self.sync_handler(state)
                if asyncio.iscoroutine(result):
                    result = await result
            else:
                raise ValueError(f"Node {self.name} has no handler")

            duration_ms = (time.time() - start_time) * 1000
            self._update_avg_duration(duration_ms)

            node_result = NodeResult.ok(
                node_id=self.id,
                output=result,
                duration_ms=duration_ms
            )

            # Cache result if enabled
            if self.config.cache_enabled:
                cache_key = self._compute_cache_key(state)
                self._cache[cache_key] = result
                self._cache_timestamps[cache_key] = datetime.now()

            return node_result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._update_avg_duration(duration_ms)
            return NodeResult.fail(node_id=self.id, error=e, duration_ms=duration_ms)

    def _compute_cache_key(self, state: S) -> str:
        """Compute cache key from state."""
        import hashlib
        import json
        state_str = json.dumps(state.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(f"{self.id}:{state_str}".encode()).hexdigest()[:16]

    def _update_avg_duration(self, duration_ms: float) -> None:
        """Update average duration using exponential moving average."""
        alpha = 0.3
        self.avg_duration_ms = alpha * duration_ms + (1 - alpha) * self.avg_duration_ms

    def clear_cache(self) -> None:
        """Clear the node's cache."""
        self._cache.clear()
        self._cache_timestamps.clear()

    def __repr__(self) -> str:
        return f"Node(id={self.id}, name={self.name}, type={self.config.node_type.value})"


@dataclass
class Edge:
    """
    An edge connecting two nodes in a flow.

    Edges define the flow of execution and can have conditions.
    """
    source: str  # Node ID
    target: str  # Node ID
    condition: EdgeCondition = EdgeCondition.ALWAYS
    condition_fn: Optional[Callable[[FlowState], bool]] = None
    label: str = ""
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def should_traverse(self, state: FlowState, last_result: Optional[NodeResult] = None) -> bool:
        """Determine if this edge should be traversed."""
        if self.condition == EdgeCondition.ALWAYS:
            return True

        if self.condition == EdgeCondition.ON_SUCCESS:
            return last_result is not None and last_result.success

        if self.condition == EdgeCondition.ON_FAILURE:
            return last_result is not None and not last_result.success

        if self.condition == EdgeCondition.CUSTOM and self.condition_fn:
            return self.condition_fn(state)

        return False

    def __repr__(self) -> str:
        label = f" [{self.label}]" if self.label else ""
        return f"Edge({self.source} -> {self.target}{label})"


@dataclass
class FlowMetadata:
    """Metadata for a flow."""
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Flow(Generic[S]):
    """
    A flow is a directed graph of nodes that defines an execution workflow.

    Flows are the primary abstraction in FlowMind, replacing both Chains and Graphs
    from LangChain/LangGraph with a unified, more powerful primitive.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    metadata: FlowMetadata = field(default_factory=lambda: FlowMetadata(name=""))
    nodes: Dict[str, Node[S]] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    entry_node: Optional[str] = None
    exit_nodes: List[str] = field(default_factory=list)

    # Execution state
    is_running: bool = False
    execution_count: int = 0
    last_execution: Optional[datetime] = None

    # Observability
    tracer: Optional[Any] = None

    def __post_init__(self):
        if not self.name:
            self.name = f"flow_{self.id}"
        if self.metadata.name == "":
            self.metadata.name = self.name

    def add_node(
        self,
        name: str,
        handler: Optional[Callable[[S], Awaitable[Any]]] = None,
        sync_handler: Optional[Callable[[S], Any]] = None,
        node_type: NodeType = NodeType.CUSTOM,
        **config_kwargs
    ) -> Node[S]:
        """Add a node to the flow."""
        config = NodeConfig(name=name, node_type=node_type, **config_kwargs)
        node = Node(name=name, config=config, handler=handler, sync_handler=sync_handler)
        self.nodes[node.id] = node

        # Set as entry node if first node
        if len(self.nodes) == 1:
            self.entry_node = node.id

        return node

    def add_edge(
        self,
        source: Union[str, Node],
        target: Union[str, Node],
        condition: EdgeCondition = EdgeCondition.ALWAYS,
        condition_fn: Optional[Callable[[FlowState], bool]] = None,
        label: str = ""
    ) -> Edge:
        """Add an edge between two nodes."""
        source_id = source if isinstance(source, str) else source.id
        target_id = target if isinstance(target, str) else target.id

        edge = Edge(
            source=source_id,
            target=target_id,
            condition=condition,
            condition_fn=condition_fn,
            label=label
        )
        self.edges.append(edge)
        return edge

    def add_conditional_edges(
        self,
        source: Union[str, Node],
        targets: Dict[str, Union[str, Node]],
        condition_fn: Callable[[FlowState], str]
    ) -> List[Edge]:
        """
        Add conditional edges from a source to multiple targets.

        The condition_fn should return the key of the target to use.
        """
        edges = []
        for label, target in targets.items():
            target_id = target if isinstance(target, str) else target.id

            def make_condition(label: str, cond_fn: Callable) -> Callable[[FlowState], bool]:
                return lambda state: cond_fn(state) == label

            edge = self.add_edge(
                source=source,
                target=target_id,
                condition=EdgeCondition.CUSTOM,
                condition_fn=make_condition(label, condition_fn),
                label=label
            )
            edges.append(edge)

        return edges

    def set_entry_point(self, node: Union[str, Node]) -> None:
        """Set the entry point of the flow."""
        node_id = node if isinstance(node, str) else node.id
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found in flow")
        self.entry_node = node_id

    def set_exit_points(self, *nodes: Union[str, Node]) -> None:
        """Set the exit points of the flow."""
        self.exit_nodes = [n if isinstance(n, str) else n.id for n in nodes]

    async def run(
        self,
        initial_state: Optional[S] = None,
        entry_point: Optional[str] = None,
        max_iterations: int = 100
    ) -> S:
        """
        Execute the flow from entry point to exit.

        Args:
            initial_state: Starting state (created if not provided)
            entry_point: Override the default entry point
            max_iterations: Maximum number of node executions to prevent infinite loops

        Returns:
            Final state after flow execution
        """
        if self.is_running:
            raise RuntimeError("Flow is already running")

        self.is_running = True
        self.execution_count += 1
        self.last_execution = datetime.now()

        try:
            state = initial_state or FlowState()
            current_node_id = entry_point or self.entry_node

            if not current_node_id:
                raise ValueError("No entry point defined for flow")

            iterations = 0
            last_result: Optional[NodeResult] = None

            while current_node_id and iterations < max_iterations:
                iterations += 1

                # Get current node
                node = self.nodes.get(current_node_id)
                if not node:
                    raise ValueError(f"Node {current_node_id} not found")

                # Execute node
                result = await node.execute(state)
                last_result = result

                # Update state with result
                if result.success:
                    state.outputs[current_node_id] = result.output

                # Find next node
                current_node_id = self._find_next_node(current_node_id, state, result)

            if iterations >= max_iterations:
                state.add_error(RuntimeError(f"Flow exceeded maximum iterations ({max_iterations})"))

            return state

        finally:
            self.is_running = False

    def _find_next_node(
        self,
        current_node_id: str,
        state: FlowState,
        last_result: Optional[NodeResult]
    ) -> Optional[str]:
        """Find the next node to execute."""
        # Check if current node is an exit node
        if current_node_id in self.exit_nodes:
            return None

        # Find outgoing edges
        outgoing_edges = [e for e in self.edges if e.source == current_node_id]

        if not outgoing_edges:
            return None

        # Find first traversable edge
        for edge in outgoing_edges:
            if edge.should_traverse(state, last_result):
                return edge.target

        # If no edge condition matched, return None
        return None

    def compile(self) -> 'CompiledFlow':
        """Compile the flow for optimized execution."""
        return CompiledFlow(self)

    def visualize(self) -> str:
        """Generate a text visualization of the flow."""
        lines = [f"Flow: {self.name}", "=" * 40]

        # List nodes
        lines.append("\nNodes:")
        for node_id, node in self.nodes.items():
            marker = " [ENTRY]" if node_id == self.entry_node else ""
            marker += " [EXIT]" if node_id in self.exit_nodes else ""
            lines.append(f"  {node_id}: {node.name} ({node.config.node_type.value}){marker}")

        # List edges
        lines.append("\nEdges:")
        for edge in self.edges:
            lines.append(f"  {edge}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Flow(id={self.id}, name={self.name}, nodes={len(self.nodes)}, edges={len(self.edges)})"


@dataclass
class CompiledFlow:
    """A compiled, optimized version of a flow."""
    flow: Flow
    execution_plan: List[List[str]] = field(default_factory=list)

    def __post_init__(self):
        self._generate_execution_plan()

    def _generate_execution_plan(self) -> None:
        """Generate an optimized execution plan."""
        # Topological sort and parallelization opportunities
        # This is a simplified version - production would be more sophisticated
        visited = set()
        plan = []

        def visit(node_id: str, path: List[str]) -> None:
            if node_id in path:
                raise ValueError(f"Cycle detected involving node {node_id}")
            if node_id in visited:
                return

            path.append(node_id)
            visited.add(node_id)

            # Find all targets from this node
            node = self.flow.nodes.get(node_id)
            if node:
                outgoing = [e.target for e in self.flow.edges if e.source == node_id]
                for target in outgoing:
                    visit(target, path.copy())

        if self.flow.entry_node:
            visit(self.flow.entry_node, [])

        # For now, just create a simple sequential plan
        # Production would identify parallel branches
        self.execution_plan = [[node_id] for node_id in visited]

    async def run(self, initial_state: Optional[FlowState] = None) -> FlowState:
        """Run the compiled flow."""
        return await self.flow.run(initial_state)


# Convenience function for creating flows
def create_flow(name: str, **kwargs) -> Flow:
    """Create a new flow with the given name."""
    metadata = FlowMetadata(name=name, **{k: v for k, v in kwargs.items() if k in FlowMetadata.__dataclass_fields__})
    return Flow(name=name, metadata=metadata)
