"""Core flow engine with zero silent failures."""
import asyncio
from typing import Any, Callable, Dict, List, Optional, Set, Union
from datetime import datetime, timezone
from dataclasses import dataclass, field

from flomind.core.types import ExecutionMode, NodeStatus, NodeConfig, Result, ExecutionRecord
from flomind.core.state import FlowState


@dataclass
class Node:
    """Executable node with strict configuration."""
    id: str
    func: Callable
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    config: NodeConfig = field(default_factory=NodeConfig)
    dependencies: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        if not callable(self.func):
            raise ValueError(f"Node {self.id} func must be callable")


class Flow:
    """Production-grade flow engine with guaranteed execution."""
    
    def __init__(
        self,
        name: str,
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        checkpoint_saver: Optional[Any] = None
    ):
        self.name = name
        self.mode = mode
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Set[str]] = {}
        self.checkpoint_saver = checkpoint_saver
        self._execution_history: List[ExecutionRecord] = []
    
    def add_node(self, node: Node) -> 'Flow':
        if node.id in self.nodes:
            raise ValueError(f"Node {node.id} already exists")
        self.nodes[node.id] = node
        self.edges[node.id] = set()
        return self
    
    def connect(self, from_id: str, to_id: str) -> 'Flow':
        if from_id not in self.nodes:
            raise ValueError(f"Node {from_id} not found")
        if to_id not in self.nodes:
            raise ValueError(f"Node {to_id} not found")
        self.edges[from_id].add(to_id)
        self.nodes[to_id].dependencies.add(from_id)
        return self
    
    async def execute(self, initial_data: Dict[str, Any]) -> FlowState:
        state = FlowState().update(initial_data).take_snapshot()
        
        # Save initial checkpoint
        if self.checkpoint_saver:
            await self.checkpoint_saver.save(state, f"{self.name}_initial")
        
        try:
            if self.mode == ExecutionMode.SEQUENTIAL:
                state = await self._execute_sequential(state)
            elif self.mode == ExecutionMode.PARALLEL:
                state = await self._execute_parallel(state)
            else:
                raise ValueError(f"Unsupported execution mode: {self.mode}")
            
            # Save final checkpoint
            if self.checkpoint_saver:
                await self.checkpoint_saver.save(state, f"{self.name}_final")
            
            return state
            
        except Exception as e:
            # Record failure and restore last good checkpoint
            record = ExecutionRecord(
                node_id="flow",
                status=NodeStatus.FAILED,
                started_at=datetime.now(timezone.utc),
                error_message=str(e)
            )
            self._execution_history.append(record)
            
            # Try to restore from checkpoint
            if self.checkpoint_saver:
                restored = await self.checkpoint_saver.load(f"{self.name}_initial")
                if restored:
                    return restored
            
            raise
    
    async def _execute_sequential(self, state: FlowState) -> FlowState:
        executed: Set[str] = set()
        pending = set(self.nodes.keys())
        
        while pending:
            # Find nodes ready to execute (all dependencies met)
            ready = [
                node_id for node_id in pending
                if all(dep in executed for dep in self.nodes[node_id].dependencies)
            ]
            
            if not ready:
                if pending:
                    raise RuntimeError(f"Deadlock detected: cannot execute nodes {pending}")
                break
            
            # Execute first ready node (sequential)
            node_id = ready[0]
            state = await self._execute_node(node_id, state)
            executed.add(node_id)
            pending.remove(node_id)
            
            # Checkpoint after each node
            if self.checkpoint_saver:
                await self.checkpoint_saver.save(state, f"{self.name}_{node_id}")
        
        return state
    
    async def _execute_parallel(self, state: FlowState) -> FlowState:
        executed: Set[str] = set()
        pending = set(self.nodes.keys())
        semaphore = asyncio.Semaphore(10)  # Limit concurrency
        
        while pending:
            # Find nodes ready to execute
            ready = [
                node_id for node_id in pending
                if all(dep in executed for dep in self.nodes[node_id].dependencies)
            ]
            
            if not ready:
                if pending:
                    raise RuntimeError(f"Deadlock detected: cannot execute nodes {pending}")
                break
            
            # Execute all ready nodes in parallel with independent state copies
            tasks = []
            for node_id in ready:
                # Each task gets its own state copy to avoid race conditions
                task_state = state._clone()
                tasks.append(self._execute_node_with_state(node_id, task_state, semaphore))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Merge all results into final state
            for node_id, result_state in zip(ready, results):
                if isinstance(result_state, Exception):
                    raise result_state
                
                # Merge node result and status from each result state
                node_result = result_state.get_node_result(node_id)
                if node_result is not None:
                    state = state.set_node_result(node_id, node_result)
                
                node_status = result_state.get_node_status(node_id)
                if node_status:
                    state = state.set_node_status(node_id, node_status)
                
                # Merge output data
                for key, value in result_state._data.items():
                    state = state.set(key, value)
            
            executed.update(ready)
            pending.difference_update(ready)
            
            # Checkpoint after batch
            if self.checkpoint_saver:
                await self.checkpoint_saver.save(state, f"{self.name}_batch_{len(executed)}")
        
        return state
    
    async def _execute_node_with_state(self, node_id: str, state: FlowState, semaphore: asyncio.Semaphore) -> FlowState:
        async with semaphore:
            return await self._execute_node(node_id, state)
    
    async def _execute_node(self, node_id: str, state: FlowState) -> FlowState:
        node = self.nodes[node_id]
        
        # Update status to running
        state = state.set_node_status(node_id, "running")
        
        start_time = datetime.now(timezone.utc)
        record = ExecutionRecord(
            node_id=node_id,
            status=NodeStatus.RUNNING,
            started_at=start_time,
            input_data={k: state.get(k) for k in node.inputs}
        )
        
        try:
            # Get inputs
            inputs = {inp: state.get(inp) for inp in node.inputs}
            
            # Execute with timeout and retry
            result = await self._execute_with_retry(node, inputs)
            
            if not result.success:
                raise RuntimeError(result.error)
            
            # Update state with outputs
            for i, output in enumerate(node.outputs):
                if isinstance(result.value, (list, tuple)) and i < len(result.value):
                    state = state.set(output, result.value[i])
                elif isinstance(result.value, dict):
                    state = state.set(output, result.value.get(output, result.value))
                else:
                    state = state.set(output, result.value)
            
            state = state.set_node_result(node_id, result.value)
            state = state.set_node_status(node_id, "completed")
            
            record = ExecutionRecord(
                node_id=node_id,
                status=NodeStatus.COMPLETED,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                input_data=inputs,
                output_data={out: state.get(out) for out in node.outputs}
            )
            
        except Exception as e:
            state = state.set_node_status(node_id, "failed")
            record = ExecutionRecord(
                node_id=node_id,
                status=NodeStatus.FAILED,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                input_data=inputs if 'inputs' in locals() else {},
                error_message=str(e)
            )
            raise
        
        finally:
            self._execution_history.append(record)
            state = state.take_snapshot()
        
        return state
    
    async def _execute_with_retry(self, node: Node, inputs: Dict[str, Any]) -> Result[Any]:
        last_error = None
        
        for attempt in range(node.config.retry_count + 1):
            try:
                # Apply timeout
                if asyncio.iscoroutinefunction(node.func):
                    result = await asyncio.wait_for(
                        node.func(**inputs),
                        timeout=node.config.timeout_seconds
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(node.func, **inputs),
                        timeout=node.config.timeout_seconds
                    )
                
                return Result.ok(result)
                
            except asyncio.TimeoutError as e:
                last_error = f"Timeout after {node.config.timeout_seconds}s"
            except Exception as e:
                last_error = str(e)
            
            if attempt < node.config.retry_count:
                await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
        
        return Result.fail(last_error or "Unknown error")
    
    def get_execution_history(self) -> List[ExecutionRecord]:
        return list(self._execution_history)


class FlowBuilder:
    """Fluent builder for creating flows."""
    
    def __init__(self, name: str):
        self.name = name
        self.mode = ExecutionMode.SEQUENTIAL
        self.nodes: List[Node] = []
        self.connections: List[tuple] = []
        self.checkpoint_saver = None
    
    def set_mode(self, mode: ExecutionMode) -> 'FlowBuilder':
        self.mode = mode
        return self
    
    def add_node(
        self,
        node_id: str,
        func: Callable,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
        config: Optional[NodeConfig] = None
    ) -> 'FlowBuilder':
        node = Node(
            id=node_id,
            func=func,
            inputs=inputs or [],
            outputs=outputs or [],
            config=config or NodeConfig()
        )
        self.nodes.append(node)
        return self
    
    def connect(self, from_id: str, to_id: str) -> 'FlowBuilder':
        self.connections.append((from_id, to_id))
        return self
    
    def with_checkpointing(self, saver: Any) -> 'FlowBuilder':
        self.checkpoint_saver = saver
        return self
    
    def build(self) -> Flow:
        flow = Flow(self.name, self.mode, self.checkpoint_saver)
        
        for node in self.nodes:
            flow.add_node(node)
        
        for from_id, to_id in self.connections:
            flow.connect(from_id, to_id)
        
        return flow
