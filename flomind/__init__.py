"""
FlowMind - The Next Generation AI Orchestration Framework

FlowMind replaces LangChain and LangGraph with a unified, type-safe,
and performant framework for building AI applications.

Key Features:
- Flow-based programming model (replaces Chains and Graphs)
- Type-safe state management
- Built-in agent system with tool support
- Multi-agent team coordination
- Comprehensive observability (tracing, metrics)
- Streaming support
- Vector store abstraction
- Resilience policies (retry, timeout, circuit breaker)

Quick Start:
    from flomind import Flow, Agent, Tool, create_flow
    
    # Create a simple flow
    flow = create_flow("my_flow")
    
    @flow.node
    async def process(state):
        return {"result": "hello"}
    
    result = await flow.run()
"""

__version__ = "1.0.0"
__author__ = "FlowMind Team"

# Core primitives
from .core.flow import Flow, Node, Edge, NodeType, EdgeCondition, create_flow
from .core.state import FlowState, NodeResult

# Agents
from .agents.agent import Agent, Role, AgentConfig
from .agents.team import AgentTeam, TeamConfig

# Tools
from .tools.tool import Tool, Action, tool, ToolError

# Memory
from .memory.memory import Memory, ShortTermMemory, LongTermMemory, ContextWindow

# Workflows
from .workflows.workflow import Workflow, Sequential, Parallel, Conditional, Loop

# Policies
from .policies import RetryPolicy, TimeoutPolicy, CircuitBreaker

# Streaming
from .streaming.stream import Stream, EventBus, EventType, StreamChunk

# Observability
from .observability.tracer import Tracer, Trace, Span, Metrics

# Vector Store
from .vector.store import VectorStore, InMemoryVectorStore, Document

# Configuration (NEW - Production Ready)
from .config import (
    FlowMindConfig,
    ConfigManager,
    get_config,
    load_config,
    load_config_from_env,
)

# Convenience exports
__all__ = [
    # Core
    'Flow',
    'Node',
    'Edge',
    'NodeType',
    'EdgeCondition',
    'create_flow',
    'FlowState',
    'NodeResult',
    
    # Agents
    'Agent',
    'Role',
    'AgentConfig',
    'AgentTeam',
    'TeamConfig',
    
    # Tools
    'Tool',
    'Action',
    'tool',
    'ToolError',
    
    # Memory
    'Memory',
    'ShortTermMemory',
    'LongTermMemory',
    'ContextWindow',
    
    # Workflows
    'Workflow',
    'Sequential',
    'Parallel',
    'Conditional',
    'Loop',
    
    # Policies
    'RetryPolicy',
    'TimeoutPolicy',
    'CircuitBreaker',
    
    # Streaming
    'Stream',
    'EventBus',
    'EventType',
    'StreamChunk',
    
    # Observability
    'Tracer',
    'Trace',
    'Span',
    'Metrics',
    
    # Vector
    'VectorStore',
    'InMemoryVectorStore',
    'Document',
    
    # Configuration (Production Ready)
    'FlowMindConfig',
    'ConfigManager',
    'get_config',
    'load_config',
    'load_config_from_env',
]


def __getattr__(name):
    """Lazy loading for backwards compatibility."""
    if name == 'State':
        from .core.state import FlowState
        return FlowState
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
