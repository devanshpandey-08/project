"""
FlowMind Core Node Types

Defines the building blocks of flows with clear semantics.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
import asyncio


class NodeType(Enum):
    """Types of nodes in a flow."""
    TASK = "task"  # Regular computation
    LLM = "llm"  # LLM call with token tracking
    TOOL = "tool"  # External tool/API call
    CONDITIONAL = "conditional"  # Branching logic
    PARALLEL = "parallel"  # Parallel execution group
    AGENT = "agent"  # Autonomous agent
    MEMORY_READ = "memory_read"  # Read from memory
    MEMORY_WRITE = "memory_write"  # Write to memory


@dataclass
class NodeConfig:
    """Configuration for a node."""
    retry_count: int = 3
    timeout_seconds: float = 30.0
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    log_level: str = "INFO"


@dataclass
class Node:
    """
    A node in a flow - the fundamental unit of execution.
    
    Each node has:
    - Clear inputs/outputs (type-safe)
    - Execution metadata (latency, success/failure)
    - Caching capability
    - Retry logic
    """
    id: str
    node_type: NodeType
    func: Optional[Callable] = None
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    config: NodeConfig = field(default_factory=NodeConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # For conditional nodes
    condition: Optional[Callable[[Dict[str, Any]], str]] = None
    branches: Dict[str, str] = field(default_factory=dict)  # branch_name -> next_node_id
    
    async def execute(self, input_data: Dict[str, Any]) -> Any:
        """Execute the node with given inputs."""
        if not self.func:
            raise ValueError(f"Node {self.id} has no function to execute")
        
        # Extract only the inputs this node needs
        node_inputs = {k: input_data.get(k) for k in self.inputs}
        
        # Check if function is async
        if asyncio.iscoroutinefunction(self.func):
            result = await self.func(**node_inputs)
        else:
            result = self.func(**node_inputs)
        
        return result
    
    def get_next_node(self, state: Dict[str, Any]) -> Optional[str]:
        """For conditional nodes, determine which branch to take."""
        if self.node_type != NodeType.CONDITIONAL or not self.condition:
            return None
        
        branch = self.condition(state)
        return self.branches.get(branch)
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class NodeResult:
    """Result of executing a node."""
    node_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    cached: bool = False
    retry_count: int = 0
    tokens_used: Optional[int] = None  # For LLM nodes
    cost_usd: Optional[float] = None  # For paid APIs
