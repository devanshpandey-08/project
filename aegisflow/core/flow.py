"""AegisFlow Core - Flow Engine & Builder"""
import asyncio
import json
from typing import Dict, List, Callable, Any, Optional
from aegisflow.core.state import FlowState, NodeConfig, ExecutionMode
from aegisflow.core.node import Node

class Flow:
    """Main Flow Executor"""
    def __init__(self, name: str, nodes: Dict[str, Node], edges: List[tuple], mode: str = ExecutionMode.SEQUENTIAL):
        self.name = name
        self.nodes = nodes
        self.edges = edges
        self.mode = mode
    
    async def execute(self, initial_data: dict) -> FlowState:
        # Initialize state with JSON-serialized data
        initial_json = json.dumps(initial_data, sort_keys=True)
        state = FlowState(_data_json=initial_json)
        
        # Simple sequential execution
        for node_id, node in self.nodes.items():
            result = await node.execute(state)
            if result.success:
                output_key = f"{node_id}_output"
                state = state.set(output_key, result.unwrap())
            else:
                raise RuntimeError(f"Node {node_id} failed: {result.error}")
        return state

class FlowBuilder:
    """Fluent Flow Builder"""
    def __init__(self, name: str):
        self.name = name
        self._nodes: Dict[str, Node] = {}
        self._edges: List[tuple] = []
    
    def add_node(self, node_id: str, func: Callable, inputs: Optional[List[str]] = None, 
                 outputs: Optional[List[str]] = None, config: Optional[dict] = None) -> 'FlowBuilder':
        node = Node(node_id=node_id, func=func, inputs=inputs or [], outputs=outputs or [], config=config)
        self._nodes[node_id] = node
        return self
    
    def connect(self, from_node: str, to_node: str) -> 'FlowBuilder':
        self._edges.append((from_node, to_node))
        return self
    
    def build(self) -> Flow:
        return Flow(name=self.name, nodes=self._nodes, edges=self._edges)
