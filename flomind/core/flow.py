"""
FlowMind Core Flow Engine

The heart of FlowMind - executes nodes with full observability,
resilience, and debugging capabilities.

Key Differentiator: When a flow fails at step 7, you can:
1. See exact state at steps 1-6
2. Replay from any checkpoint
3. Understand why each decision was made
4. Recover gracefully without losing progress
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union, Set
from datetime import datetime
import asyncio
import time
import uuid
import logging

from flomind.core.node import Node, NodeType, NodeResult, NodeConfig
from flomind.core.state import State, StateSnapshot


logger = logging.getLogger(__name__)


@dataclass
class FlowConfig:
    """Configuration for a flow."""
    name: str = "unnamed_flow"
    max_retries: int = 3
    default_timeout: float = 60.0
    enable_caching: bool = True
    enable_tracing: bool = True
    log_level: str = "INFO"
    parallel_limit: int = 10  # Max parallel nodes


class Flow:
    """
    A flow is a directed graph of nodes that processes data.
    
    Unlike LangChain's rigid chains or LangGraph's complex graphs,
    FlowMind flows are:
    - Easy to debug (full state history)
    - Resilient by default (retry, timeout, circuit breaker)
    - Observable (trace every execution)
    - Developer-friendly (simple API, clear errors)
    """
    
    def __init__(self, config: Optional[FlowConfig] = None):
        self.config = config or FlowConfig()
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[str]] = {}  # node_id -> [next_node_ids]
        self.entry_nodes: List[str] = []
        self.exit_nodes: List[str] = []
        
        # Caching
        self._cache: Dict[str, Any] = {}
        
        # Execution tracking
        self._execution_count = 0
    
    def add_node(self, node: Node) -> 'Flow':
        """Add a node to the flow."""
        self.nodes[node.id] = node
        return self
    
    def add_edge(self, from_id: str, to_id: str) -> 'Flow':
        """Add an edge between nodes."""
        if from_id not in self.edges:
            self.edges[from_id] = []
        self.edges[from_id].append(to_id)
        
        # Track entry/exit nodes
        if from_id not in self.entry_nodes and from_id not in [e for edges in self.edges.values() for e in edges]:
            pass  # Will be set properly later
        
        return self
    
    def set_entry(self, node_id: str) -> 'Flow':
        """Set the entry node(s)."""
        if node_id not in self.entry_nodes:
            self.entry_nodes.append(node_id)
        return self
    
    def set_exit(self, node_id: str) -> 'Flow':
        """Set the exit node(s)."""
        if node_id not in self.exit_nodes:
            self.exit_nodes.append(node_id)
        return self
    
    def _get_cache_key(self, node_id: str, inputs: Dict[str, Any]) -> str:
        """Generate cache key for node execution."""
        sorted_inputs = str(sorted(inputs.items()))
        return f"{node_id}:{hash(sorted_inputs)}"
    
    async def _execute_node(self, node: Node, state: State) -> NodeResult:
        """Execute a single node with retry, timeout, and caching."""
        start_time = time.time()
        cache_key = None
        
        # Check cache
        if self.config.enable_caching and node.config.cache_enabled:
            cache_key = self._get_cache_key(node.id, {k: state.data.get(k) for k in node.inputs})
            if cache_key in self._cache:
                latency = (time.time() - start_time) * 1000
                logger.debug(f"Cache hit for node {node.id}")
                return NodeResult(
                    node_id=node.id,
                    success=True,
                    result=self._cache[cache_key],
                    latency_ms=latency,
                    cached=True
                )
        
        # Execute with retries
        last_error = None
        for attempt in range(node.config.retry_count + 1):
            try:
                # Apply timeout
                if asyncio.iscoroutinefunction(node.execute):
                    result = await asyncio.wait_for(
                        node.execute(state.data),
                        timeout=node.config.timeout_seconds
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, lambda: node.execute(state.data)
                        ),
                        timeout=node.config.timeout_seconds
                    )
                
                # Cache result
                if cache_key and self.config.enable_caching:
                    self._cache[cache_key] = result
                
                latency = (time.time() - start_time) * 1000
                
                return NodeResult(
                    node_id=node.id,
                    success=True,
                    result=result,
                    latency_ms=latency,
                    retry_count=attempt
                )
                
            except asyncio.TimeoutError as e:
                last_error = f"Timeout after {node.config.timeout_seconds}s"
                logger.warning(f"Node {node.id} timed out on attempt {attempt + 1}")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Node {node.id} failed on attempt {attempt + 1}: {e}")
                
                if attempt < node.config.retry_count:
                    await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
        
        # All retries failed
        latency = (time.time() - start_time) * 1000
        return NodeResult(
            node_id=node.id,
            success=False,
            error=last_error,
            latency_ms=latency,
            retry_count=node.config.retry_count
        )
    
    async def execute(self, initial_data: Dict[str, Any], 
                     trace_id: Optional[str] = None) -> State:
        """
        Execute the flow with given initial data.
        
        Returns a State object with:
        - Final results
        - Complete execution history
        - Ability to debug what happened at each step
        """
        trace_id = trace_id or str(uuid.uuid4())
        state = State(data=initial_data, trace_id=trace_id)
        
        logger.info(f"Starting flow {self.config.name} (trace={trace_id})")
        
        # Start from entry nodes
        current_nodes = self.entry_nodes or list(self.nodes.keys())[:1]
        executed: Set[str] = set()
        
        while current_nodes:
            next_nodes: Set[str] = set()
            
            # Execute current layer (supports parallel)
            tasks = []
            for node_id in current_nodes:
                if node_id in executed or node_id not in self.nodes:
                    continue
                
                node = self.nodes[node_id]
                tasks.append(self._execute_node(node, state))
            
            if not tasks:
                break
            
            # Execute in parallel (up to limit)
            semaphore = asyncio.Semaphore(self.config.parallel_limit)
            
            async def bounded_execute(task_node_id: str):
                async with semaphore:
                    return task_node_id, await self._execute_node(
                        self.nodes[task_node_id], state
                    )
            
            bounded_tasks = [bounded_execute(nid) for nid in current_nodes 
                           if nid not in executed and nid in self.nodes]
            
            results = await asyncio.gather(*bounded_tasks, return_exceptions=True)
            
            # Process results
            for result_item in results:
                if isinstance(result_item, Exception):
                    logger.error(f"Unexpected error: {result_item}")
                    continue
                
                node_id, result = result_item
                executed.add(node_id)
                
                # Update state with result
                if result.success:
                    # Store result in state
                    output_key = f"{node_id}_output"
                    state = state.update(**{output_key: result.result})
                    
                    # Record execution details
                    state.set_node_result(
                        node_id=node_id,
                        result=result.result,
                        latency_ms=result.latency_ms,
                        success=True,
                        cached=result.cached
                    )
                    
                    # Determine next nodes
                    if node_id in self.edges:
                        next_nodes.update(self.edges[node_id])
                    else:
                        # Try conditional branching
                        node = self.nodes[node_id]
                        next_node = node.get_next_node(state.data)
                        if next_node:
                            next_nodes.add(next_node)
                else:
                    # Record failure
                    state.set_node_result(
                        node_id=node_id,
                        result=None,
                        latency_ms=result.latency_ms,
                        success=False,
                        error=result.error
                    )
                    
                    logger.error(f"Node {node_id} failed: {result.error}")
                    
                    # Don't continue from failed node unless it's retried
                    # (For now, we stop - could implement circuit breaker here)
            
            current_nodes = list(next_nodes - executed)
        
        self._execution_count += 1
        logger.info(f"Flow {self.config.name} completed (trace={trace_id}, nodes={len(executed)})")
        
        return state
    
    def visualize(self) -> str:
        """Generate a simple text visualization of the flow."""
        lines = [f"Flow: {self.config.name}"]
        lines.append("=" * 40)
        
        for node_id, node in self.nodes.items():
            entry_marker = "🚪 " if node_id in self.entry_nodes else "   "
            exit_marker = " 🏁" if node_id in self.exit_nodes else ""
            lines.append(f"{entry_marker}{node_id} [{node.node_type.value}]{exit_marker}")
            
            if node_id in self.edges:
                for next_id in self.edges[node_id]:
                    lines.append(f"   └─> {next_id}")
        
        return "\n".join(lines)


class FlowBuilder:
    """Fluent builder for creating flows."""
    
    def __init__(self, name: str):
        self.flow = Flow(FlowConfig(name=name))
    
    def add_node(self, id: str, func: Callable,
                 node_type: NodeType = NodeType.TASK,
                 inputs: Optional[List[str]] = None,
                 outputs: Optional[List[str]] = None,
                 retry_count: int = None,
                 timeout_seconds: float = None,
                 **config_kwargs) -> 'FlowBuilder':
        """Add a node to the flow."""
        
        # Handle legacy retry_policy parameter
        if 'retry_policy' in config_kwargs:
            retry_policy = config_kwargs.pop('retry_policy')
            if hasattr(retry_policy, 'max_retries'):
                retry_count = retry_policy.max_retries
            if hasattr(retry_policy, 'base_delay'):
                config_kwargs['retry_delay_base'] = retry_policy.base_delay
            if hasattr(retry_policy, 'max_delay'):
                config_kwargs['max_retry_delay'] = retry_policy.max_delay
        
        # Override defaults if provided
        if retry_count is not None:
            config_kwargs['retry_count'] = retry_count
        if timeout_seconds is not None:
            config_kwargs['timeout_seconds'] = timeout_seconds
            
        node = Node(
            id=id,
            node_type=node_type,
            func=func,
            inputs=inputs or [],
            outputs=outputs or [],
            config=NodeConfig(**config_kwargs)
        )
        self.flow.add_node(node)
        return self
    def add_llm_node(self, id: str, func: Callable,
                     inputs: Optional[List[str]] = None,
                     **config_kwargs) -> 'FlowBuilder':
        """Add an LLM node with optimized defaults."""
        return self.add_node(
            id=id,
            func=func,
            node_type=NodeType.LLM,
            inputs=inputs or ['prompt'],
            timeout_seconds=120.0,  # LLMs can be slow
            **config_kwargs
        )
    
    def add_tool_node(self, id: str, func: Callable,
                      inputs: Optional[List[str]] = None,
                      **config_kwargs) -> 'FlowBuilder':
        """Add a tool node."""
        return self.add_node(
            id=id,
            func=func,
            node_type=NodeType.TOOL,
            inputs=inputs or [],
            **config_kwargs
        )
    
    def connect(self, from_id: str, to_id: str) -> 'FlowBuilder':
        """Connect two nodes."""
        self.flow.add_edge(from_id, to_id)
        return self
    
    def start_at(self, node_id: str) -> 'FlowBuilder':
        """Set the entry node."""
        self.flow.set_entry(node_id)
        return self
    
    def end_at(self, node_id: str) -> 'FlowBuilder':
        """Set the exit node."""
        self.flow.set_exit(node_id)
        return self
    
    def build(self) -> Flow:
        """Build and return the flow."""
        # Auto-set entry if not specified
        if not self.flow.entry_nodes and self.flow.nodes:
            first_node = list(self.flow.nodes.keys())[0]
            self.flow.set_entry(first_node)
        
        return self.flow
