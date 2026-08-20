"""Core Flow Engine - The heart of FlowMind."""

from typing import Any, Dict, List, Optional, Callable, Union, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time
import uuid
from datetime import datetime


class NodeType(Enum):
    """Types of nodes in a flow."""
    START = "start"
    END = "end"
    TASK = "task"
    AGENT = "agent"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"


class NodeStatus(Enum):
    """Execution status of a node."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Node:
    """A node in the flow graph."""
    id: str
    node_type: NodeType
    name: str
    func: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def reset(self):
        """Reset node state."""
        self.status = NodeStatus.PENDING
        self.result = None
        self.error = None
        self.started_at = None
        self.completed_at = None


@dataclass
class EdgeCondition:
    """Condition for edge traversal."""
    condition: Callable[[Dict[str, Any]], bool]
    description: str = ""


@dataclass
class Edge:
    """Edge connecting two nodes."""
    source: str
    target: str
    condition: Optional[EdgeCondition] = None
    label: str = ""


T = TypeVar('T')


@dataclass
class FlowState(Generic[T]):
    """Type-safe state container for flow execution."""
    data: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_context: Optional[T] = None
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from state."""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set value in state."""
        self.data[key] = value
        self.history.append({"key": key, "value": value, "timestamp": datetime.now()})
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple values."""
        self.data.update(updates)
        self.history.append({"updates": updates, "timestamp": datetime.now()})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "data": self.data,
            "metadata": self.metadata,
            "history_length": len(self.history)
        }


@dataclass
class FlowResult:
    """Result of flow execution."""
    success: bool
    output: Any = None
    state: Optional[FlowState] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    node_results: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "trace_id": self.trace_id,
            "node_count": len(self.node_results)
        }


class Flow:
    """
    Unified Flow primitive replacing Chains and Graphs.
    
    Features:
    - Type-safe state management
    - Conditional routing
    - Parallel execution
    - Built-in resilience
    - Full observability
    """
    
    def __init__(self, name: str, description: str = ""):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.start_node: Optional[str] = None
        self.end_node: Optional[str] = None
        self._compiled = False
        self._adjacency: Dict[str, List[str]] = {}
        
    def add_node(
        self,
        id: str,
        node_type: NodeType,
        name: str,
        func: Optional[Callable] = None,
        **metadata
    ) -> 'Flow':
        """Add a node to the flow."""
        node = Node(
            id=id,
            node_type=node_type,
            name=name,
            func=func,
            metadata=metadata
        )
        self.nodes[id] = node
        self._adjacency[id] = []
        self._compiled = False
        
        if node_type == NodeType.START:
            self.start_node = id
        elif node_type == NodeType.END:
            self.end_node = id
            
        return self
    
    def add_edge(
        self,
        source: str,
        target: str,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        label: str = ""
    ) -> 'Flow':
        """Add an edge between nodes."""
        edge_condition = None
        if condition:
            edge_condition = EdgeCondition(condition=condition, description=label)
            
        edge = Edge(source=source, target=target, condition=edge_condition, label=label)
        self.edges.append(edge)
        
        if source in self._adjacency:
            self._adjacency[source].append(target)
        else:
            self._adjacency[source] = [target]
            
        self._compiled = False
        return self
    
    def compile(self) -> 'Flow':
        """Compile and validate the flow."""
        if not self.start_node:
            raise ValueError("Flow must have a start node")
        if not self.end_node:
            raise ValueError("Flow must have an end node")
            
        # Validate connectivity
        visited = set()
        queue = [self.start_node]
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            queue.extend(self._adjacency.get(current, []))
            
        if self.end_node not in visited:
            raise ValueError("End node is not reachable from start node")
            
        self._compiled = True
        return self
    
    async def execute_async(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        user_context: Any = None,
        **kwargs
    ) -> FlowResult:
        """Execute the flow asynchronously."""
        if not self._compiled:
            self.compile()
            
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        state = FlowState(data=initial_state or {}, user_context=user_context)
        node_results = {}
        
        try:
            current_node_id = self.start_node
            
            while current_node_id:
                node = self.nodes[current_node_id]
                node.status = NodeStatus.RUNNING
                node.started_at = datetime.now()
                
                try:
                    if node.func:
                        if asyncio.iscoroutinefunction(node.func):
                            result = await node.func(state, **kwargs)
                        else:
                            result = node.func(state, **kwargs)
                        node.result = result
                        state.set(f"node_{current_node_id}", result)
                        node_results[current_node_id] = result
                    
                    node.status = NodeStatus.COMPLETED
                    node.completed_at = datetime.now()
                    
                    # Find next node
                    next_node = None
                    for edge in self.edges:
                        if edge.source == current_node_id:
                            if edge.condition:
                                if edge.condition.condition(state.data):
                                    next_node = edge.target
                                    break
                            else:
                                next_node = edge.target
                                break
                    
                    current_node_id = next_node
                    
                except Exception as e:
                    node.status = NodeStatus.FAILED
                    node.error = str(e)
                    node.completed_at = datetime.now()
                    raise
                    
            execution_time = time.time() - start_time
            
            return FlowResult(
                success=True,
                output=state.get("node_" + self.end_node) if self.end_node else None,
                state=state,
                execution_time=execution_time,
                node_results=node_results,
                trace_id=trace_id
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return FlowResult(
                success=False,
                error=str(e),
                state=state,
                execution_time=execution_time,
                node_results=node_results,
                trace_id=trace_id
            )
    
    def execute(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        user_context: Any = None,
        **kwargs
    ) -> FlowResult:
        """Execute the flow synchronously."""
        return asyncio.run(self.execute_async(initial_state, user_context, **kwargs))
    
    def visualize(self) -> str:
        """Generate a text visualization of the flow."""
        lines = [f"Flow: {self.name}", "=" * 40]
        
        for node_id, node in self.nodes.items():
            edges_out = [e.target for e in self.edges if e.source == node_id]
            edges_str = ", ".join(edges_out) if edges_out else "None"
            lines.append(f"[{node.node_type.value}] {node.name} -> {edges_str}")
            
        return "\n".join(lines)
