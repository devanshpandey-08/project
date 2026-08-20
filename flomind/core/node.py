"""Node definitions for FlowMind flows."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union, Awaitable
from enum import Enum
import asyncio
import time

from flomind.core.flow import FlowState, FlowContext
from flomind.core.types import RetryConfig, TimeoutConfig


class NodeType(Enum):
    """Type of node in a flow."""
    ACTION = "action"  # Executes a function
    LLM = "llm"  # Calls an LLM
    CONDITION = "condition"  # Branching logic
    PARALLEL = "parallel"  # Parallel execution
    AGENT = "agent"  # Agent execution
    TOOL = "tool"  # Tool execution
    MEMORY_READ = "memory_read"  # Read from memory
    MEMORY_WRITE = "memory_write"  # Write to memory


@dataclass
class NodeResult:
    """Result of executing a node."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class Node:
    """
    A node in a FlowMind flow graph.
    
    Nodes are the building blocks of flows. Each node:
    - Has a unique ID
    - Performs a specific action
    - Can have retry/timeout configurations
    - Produces output that updates the flow state
    """
    
    def __init__(
        self,
        id: str,
        node_type: NodeType = NodeType.ACTION,
        action: Optional[Callable[[FlowContext], Union[Any, Awaitable[Any]]]] = None,
        name: Optional[str] = None,
        description: str = "",
        retry_config: Optional[RetryConfig] = None,
        timeout_config: Optional[TimeoutConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.node_type = node_type
        self.action = action
        self.name = name or id
        self.description = description
        self.retry_config = retry_config or RetryConfig()
        self.timeout_config = timeout_config or TimeoutConfig()
        self.metadata = metadata or {}
        self._pre_hooks: List[Callable[[FlowContext], None]] = []
        self._post_hooks: List[Callable[[FlowContext, NodeResult], None]] = []
    
    def pre_hook(self, fn: Callable[[FlowContext], None]) -> "Node":
        """Add a pre-execution hook."""
        self._pre_hooks.append(fn)
        return self
    
    def post_hook(self, fn: Callable[[FlowContext, NodeResult], None]) -> "Node":
        """Add a post-execution hook."""
        self._post_hooks.append(fn)
        return self
    
    async def execute(self, context: FlowContext) -> NodeResult:
        """Execute the node with the given context."""
        start_time = time.time()
        
        try:
            # Run pre-hooks
            for hook in self._pre_hooks:
                hook(context)
            
            # Check if cancelled
            if context.is_cancelled():
                return NodeResult(
                    success=False,
                    error="Flow was cancelled",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Execute action if defined
            if self.action is None:
                return NodeResult(
                    success=True,
                    output=None,
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            result = self.action(context)
            
            # Handle async results
            if asyncio.iscoroutine(result):
                result = await result
            
            execution_time = (time.time() - start_time) * 1000
            
            node_result = NodeResult(
                success=True,
                output=result,
                execution_time_ms=execution_time,
                metadata={"node_type": self.node_type.value}
            )
            
            # Run post-hooks
            for hook in self._post_hooks:
                hook(context, node_result)
            
            return node_result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return NodeResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                metadata={"exception_type": type(e).__name__}
            )
    
    def __repr__(self) -> str:
        return f"Node(id={self.id}, type={self.node_type.value}, name={self.name})"


def node(
    id: Optional[str] = None,
    node_type: NodeType = NodeType.ACTION,
    name: Optional[str] = None,
    description: str = "",
    retry: Optional[RetryConfig] = None,
    timeout: Optional[TimeoutConfig] = None,
) -> Callable[[Callable], Node]:
    """
    Decorator to create a Node from a function.
    
    Usage:
        @node(id="summarize", node_type=NodeType.LLM)
        def summarize_node(ctx: FlowContext) -> str:
            text = ctx.state["input"]
            return f"Summary of: {text[:50]}..."
    """
    def decorator(func: Callable) -> Node:
        node_id = id or func.__name__
        return Node(
            id=node_id,
            node_type=node_type,
            action=func,
            name=name or func.__name__,
            description=description,
            retry_config=retry,
            timeout_config=timeout,
        )
    return decorator
