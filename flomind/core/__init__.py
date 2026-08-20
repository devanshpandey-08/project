"""Core module exports."""
from .state import FlowState, NodeResult, StateSnapshot
from .flow import (
    Flow,
    Node,
    Edge,
    NodeType,
    EdgeCondition,
    NodeConfig,
    FlowMetadata,
    CompiledFlow,
    create_flow,
    State,  # Backwards compatible alias
)

__all__ = [
    'Flow',
    'Node',
    'Edge',
    'NodeType',
    'EdgeCondition',
    'NodeConfig',
    'FlowMetadata',
    'CompiledFlow',
    'create_flow',
    'FlowState',
    'NodeResult',
    'StateSnapshot',
    'State',
]
