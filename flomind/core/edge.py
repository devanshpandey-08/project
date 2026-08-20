"""Edge definitions for FlowMind flows."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union, Awaitable

from flomind.core.flow import FlowState, FlowContext


@dataclass
class Edge:
    """
    A directed edge connecting two nodes in a flow.
    
    Edges define the execution order and can optionally
    transform state between nodes.
    """
    source: str
    target: str
    condition: Optional[Callable[[FlowContext], bool]] = None
    transform: Optional[Callable[[FlowContext], FlowContext]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def should_traverse(self, context: FlowContext) -> bool:
        """Check if this edge should be traversed."""
        if self.condition is None:
            return True
        try:
            result = self.condition(context)
            if asyncio.iscoroutine(result):
                # Will be handled by async executor
                return True  # Default to true for sync check
            return result
        except Exception:
            return False
    
    def apply_transform(self, context: FlowContext) -> FlowContext:
        """Apply state transformation if defined."""
        if self.transform:
            return self.transform(context)
        return context


@dataclass
class ConditionalEdge(Edge):
    """
    An edge with conditional logic for branching.
    
    Usage:
        ConditionalEdge(
            source="decision",
            target="positive_path",
            condition=lambda ctx: ctx.state.get("sentiment") == "positive"
        )
    """
    label: str = ""
    priority: int = 0  # For resolving multiple matching conditions
    
    def __post_init__(self):
        self.metadata["edge_type"] = "conditional"
        self.metadata["label"] = self.label


def edge(
    source: str,
    target: str,
    condition: Optional[Callable[[FlowContext], bool]] = None,
    label: str = "",
) -> ConditionalEdge:
    """
    Create a conditional edge between nodes.
    
    Usage:
        @edge("decision", "approve", condition=lambda ctx: ctx.state["approved"])
        
    Or simply:
        edge("start", "end")  # Unconditional edge
    """
    return ConditionalEdge(
        source=source,
        target=target,
        condition=condition,
        label=label
    )


def conditional(
    condition: Callable[[FlowContext], bool],
    target: str,
    label: str = "",
) -> ConditionalEdge:
    """
    Create a conditional branch (used within node definitions).
    
    Usage:
        Node(
            id="check_status",
            edges=[
                conditional(lambda ctx: ctx.state["status"] == "ok", "success"),
                conditional(lambda ctx: ctx.state["status"] == "error", "failure"),
            ]
        )
    """
    return ConditionalEdge(
        source="",  # Will be set by parent node
        target=target,
        condition=condition,
        label=label
    )


class EdgeBuilder:
    """Fluent builder for creating complex edge configurations."""
    
    def __init__(self, source: str):
        self.source = source
        self._edges: List[ConditionalEdge] = []
    
    def to(self, target: str, condition: Optional[Callable[[FlowContext], bool]] = None, label: str = "") -> "EdgeBuilder":
        """Add an edge to a target node."""
        self._edges.append(ConditionalEdge(
            source=self.source,
            target=target,
            condition=condition,
            label=label
        ))
        return self
    
    def always(self, target: str) -> "EdgeBuilder":
        """Add an unconditional edge."""
        return self.to(target, condition=None)
    
    def when(self, condition: Callable[[FlowContext], bool], target: str, label: str = "") -> "EdgeBuilder":
        """Add a conditional edge."""
        return self.to(target, condition=condition, label=label)
    
    def when_true(self, condition_field: str, target: str) -> "EdgeBuilder":
        """Add edge when a state field is truthy."""
        return self.when(lambda ctx: bool(ctx.state.get(condition_field)), target, label=condition_field)
    
    def when_false(self, condition_field: str, target: str) -> "EdgeBuilder":
        """Add edge when a state field is falsy."""
        return self.when(lambda ctx: not ctx.state.get(condition_field), target, label=f"not_{condition_field}")
    
    def when_equals(self, field: str, value: Any, target: str) -> "EdgeBuilder":
        """Add edge when a state field equals a value."""
        return self.when(lambda ctx: ctx.state.get(field) == value, target, label=f"{field}=={value}")
    
    def build(self) -> List[ConditionalEdge]:
        """Build and return all edges."""
        return self._edges


def edges_from(source: str) -> EdgeBuilder:
    """Start building edges from a source node."""
    return EdgeBuilder(source)
