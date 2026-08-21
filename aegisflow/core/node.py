"""AegisFlow Core - Node Definition"""
import asyncio
from typing import Callable, Any, List, Optional
from aegisflow.core.state import FlowState, Result, NodeConfig

class Node:
    """Executable Node in a Flow"""
    def __init__(self, node_id: str, func: Callable, inputs: List[str], outputs: List[str], config: Optional[dict] = None):
        self.node_id = node_id
        self.func = func
        self.inputs = inputs
        self.outputs = outputs
        self.config = NodeConfig(**config) if config else NodeConfig()
    
    async def execute(self, state: FlowState) -> Result:
        try:
            # Gather inputs from state
            input_values = {}
            for inp in self.inputs:
                val = state.get(inp)
                if val is not None:
                    input_values[inp] = val
            
            # Execute function (sync or async)
            if asyncio.iscoroutinefunction(self.func):
                output = await self.func(**input_values)
            else:
                output = self.func(**input_values)
            
            return Result.ok(output)
        except Exception as e:
            return Result.fail(str(e))
