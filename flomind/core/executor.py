"""Flow executor with resilience patterns and async execution."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, AsyncIterator

from flomind.core.flow import FlowState, FlowContext
from flomind.core.node import Node, NodeResult, NodeType
from flomind.core.edge import Edge, ConditionalEdge
from flomind.core.types import (
    FlowResult, 
    FlowStatus, 
    FlowMetadata,
    RetryConfig, 
    TimeoutConfig,
    CircuitBreakerConfig,
    StreamChunk,
)


@dataclass
class CircuitBreaker:
    """Circuit breaker for fault tolerance."""
    config: CircuitBreakerConfig
    failures: int = 0
    last_failure_time: float = 0
    state: str = "closed"  # closed, open, half-open
    success_count: int = 0
    
    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        elif self.state == "open":
            if (time.time() - self.last_failure_time) * 1000 >= self.config.recovery_timeout_ms:
                self.state = "half-open"
                self.success_count = 0
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self) -> None:
        if self.state == "half-open":
            self.success_count += 1
            if self.success_count >= self.config.half_open_requests:
                self.state = "closed"
                self.failures = 0
        else:
            self.failures = max(0, self.failures - 1)
    
    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.config.failure_threshold:
            self.state = "open"


class FlowExecutor:
    """
    Executes FlowMind flows with full resilience support.
    
    Features:
    - Async execution
    - Retry with exponential backoff
    - Timeout handling
    - Circuit breaker pattern
    - Parallel node execution
    - Streaming support
    - Cancellation
    """
    
    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        timeout_config: Optional[TimeoutConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.default_retry = retry_config or RetryConfig()
        self.default_timeout = timeout_config or TimeoutConfig()
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def _get_circuit_breaker(self, node_id: str) -> CircuitBreaker:
        if node_id not in self._circuit_breakers:
            self._circuit_breakers[node_id] = CircuitBreaker(self.circuit_breaker_config)
        return self._circuit_breakers[node_id]
    
    async def execute_with_retry(
        self,
        node: Node,
        context: FlowContext,
    ) -> NodeResult:
        """Execute a node with retry logic."""
        retry_config = node.retry_config or self.default_retry
        last_error = None
        
        for attempt in range(retry_config.max_retries + 1):
            context.attempt = attempt
            
            # Check circuit breaker
            cb = self._get_circuit_breaker(node.id)
            if not cb.can_execute():
                return NodeResult(
                    success=False,
                    error=f"Circuit breaker open for node {node.id}",
                    metadata={"circuit_breaker": True}
                )
            
            try:
                result = await node.execute(context)
                
                if result.success:
                    cb.record_success()
                    return result
                else:
                    last_error = result.error
                    
            except Exception as e:
                last_error = str(e)
                if not isinstance(e, retry_config.retryable_exceptions):
                    cb.record_failure()
                    return NodeResult(success=False, error=last_error)
            
            cb.record_failure()
            
            # Don't delay on last attempt
            if attempt < retry_config.max_retries:
                delay = min(
                    retry_config.base_delay_ms * (retry_config.exponential_base ** attempt),
                    retry_config.max_delay_ms
                )
                if retry_config.jitter:
                    import random
                    delay *= (0.5 + random.random())
                await asyncio.sleep(delay / 1000)
        
        return NodeResult(
            success=False,
            error=f"Max retries exceeded. Last error: {last_error}",
            metadata={"max_retries": retry_config.max_retries}
        )
    
    async def execute_with_timeout(
        self,
        node: Node,
        context: FlowContext,
    ) -> NodeResult:
        """Execute a node with timeout handling."""
        timeout_config = node.timeout_config or self.default_timeout
        
        if timeout_config.node_timeout_ms is None:
            return await self.execute_with_retry(node, context)
        
        try:
            result = await asyncio.wait_for(
                self.execute_with_retry(node, context),
                timeout=timeout_config.node_timeout_ms / 1000
            )
            return result
        except asyncio.TimeoutError:
            return NodeResult(
                success=False,
                error=f"Node {node.id} timed out after {timeout_config.node_timeout_ms}ms",
                metadata={"timeout": True}
            )
    
    def _get_next_nodes(
        self,
        current_node_id: str,
        context: FlowContext,
        nodes: Dict[str, Node],
        edges: List[ConditionalEdge],
    ) -> List[str]:
        """Determine which nodes to execute next."""
        next_nodes = []
        
        for edge in edges:
            if edge.source != current_node_id:
                continue
            
            # Check condition
            if edge.condition:
                try:
                    result = edge.condition(context)
                    if asyncio.iscoroutine(result):
                        # For async conditions, we'll evaluate during execution
                        pass
                    if not result:
                        continue
                except Exception:
                    continue
            
            if edge.target not in next_nodes:
                next_nodes.append(edge.target)
        
        return next_nodes
    
    async def execute(
        self,
        nodes: Dict[str, Node],
        edges: List[ConditionalEdge],
        initial_state: Optional[FlowState] = None,
        start_node: str = "start",
        metadata: Optional[FlowMetadata] = None,
    ) -> FlowResult[Any]:
        """
        Execute a flow graph.
        
        Args:
            nodes: Dictionary of node_id -> Node
            edges: List of edges connecting nodes
            initial_state: Initial flow state
            start_node: ID of the starting node
            metadata: Execution metadata
        
        Returns:
            FlowResult with execution outcome
        """
        start_time = time.time()
        meta = metadata or FlowMetadata()
        
        context = FlowContext(
            state=initial_state or FlowState(),
            trace_id=meta.run_id,
        )
        
        executed_nodes: List[str] = []
        queue = deque([start_node])
        visited: Set[str] = set()
        
        while queue and not context.is_cancelled():
            current_id = queue.popleft()
            
            if current_id in visited:
                continue
            
            if current_id not in nodes:
                if current_id == "end":
                    break
                continue
            
            visited.add(current_id)
            node = nodes[current_id]
            context.node_id = current_id
            
            # Execute node with resilience
            result = await self.execute_with_timeout(node, context)
            
            executed_nodes.append(current_id)
            
            if not result.success:
                return FlowResult(
                    success=False,
                    error=result.error,
                    state=context.state.to_dict(),
                    execution_time_ms=(time.time() - start_time) * 1000,
                    nodes_executed=executed_nodes,
                    trace_id=meta.run_id,
                )
            
            # Update state with node output
            if result.output is not None:
                context.state["last_output"] = result.output
                if node.id not in ("start", "end"):
                    context.state[node.id] = result.output
            
            # Get next nodes
            next_ids = self._get_next_nodes(current_id, context, nodes, edges)
            queue.extend(next_ids)
        
        if context.is_cancelled():
            return FlowResult(
                success=False,
                error="Flow was cancelled",
                state=context.state.to_dict(),
                execution_time_ms=(time.time() - start_time) * 1000,
                nodes_executed=executed_nodes,
                trace_id=meta.run_id,
            )
        
        return FlowResult(
            success=True,
            data=context.state.get("last_output"),
            state=context.state.to_dict(),
            execution_time_ms=(time.time() - start_time) * 1000,
            nodes_executed=executed_nodes,
            trace_id=meta.run_id,
        )
    
    async def execute_streaming(
        self,
        nodes: Dict[str, Node],
        edges: List[ConditionalEdge],
        initial_state: Optional[FlowState] = None,
        start_node: str = "start",
    ) -> AsyncIterator[StreamChunk]:
        """Execute flow and stream intermediate results."""
        start_time = time.time()
        context = FlowContext(state=initial_state or FlowState())
        
        queue = deque([start_node])
        visited: Set[str] = set()
        
        while queue and not context.is_cancelled():
            current_id = queue.popleft()
            
            if current_id in visited or current_id not in nodes:
                continue
            
            visited.add(current_id)
            node = nodes[current_id]
            context.node_id = current_id
            
            # Yield start chunk
            yield StreamChunk(
                content=f"[START] Node: {current_id}",
                node_id=current_id,
                metadata={"event": "node_start"}
            )
            
            result = await self.execute_with_timeout(node, context)
            
            # Yield result chunk
            if result.output:
                yield StreamChunk(
                    content=str(result.output),
                    node_id=current_id,
                    metadata={"event": "node_result"}
                )
            
            if not result.success:
                yield StreamChunk(
                    content=f"[ERROR] {result.error}",
                    node_id=current_id,
                    metadata={"event": "error"}
                )
                break
            
            # Update state
            if result.output is not None:
                context.state["last_output"] = result.output
            
            next_ids = self._get_next_nodes(current_id, context, nodes, edges)
            queue.extend(next_ids)
        
        yield StreamChunk(
            content="[END] Flow completed",
            metadata={"event": "flow_end", "duration_ms": (time.time() - start_time) * 1000}
        )
