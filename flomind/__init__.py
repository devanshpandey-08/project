"""
FlowMind - Next-Generation AI Orchestration Framework

A lightweight, type-safe, async-native framework designed to replace LangChain and LangGraph.
Built for August 2026 and beyond.

Key Features:
- Zero abstraction overhead with direct Python typing
- Native async/await from the ground up
- Type-safe state management with full IDE support
- Declarative + Imperative hybrid programming model
- Built-in observability and tracing
- Memory-efficient true streaming
- Hot-reload workflow capabilities
- Multi-agent coordination built-in
- Vector store agnostic with unified interface
- Cost tracking and optimization
"""

__version__ = "1.0.0"
__author__ = "FlowMind Team"
__all__ = [
    # Core primitives
    "Flow",
    "Node",
    "Edge",
    "State",
    
    # Agent system
    "Agent",
    "AgentTeam",
    "Role",
    
    # Tools and actions
    "Tool",
    "Action",
    "tool",
    
    # Memory and context
    "Memory",
    "ShortTermMemory",
    "LongTermMemory",
    "ContextWindow",
    
    # Streaming and events
    "Stream",
    "EventBus",
    "EventType",
    
    # Observability
    "Tracer",
    "Metrics",
    "ObservabilityConfig",
    
    # LLM providers
    "LLM",
    "Provider",
    "Message",
    "ChatRole",
    
    # Vector stores
    "VectorStore",
    "EmbeddingModel",
    "Document",
    
    # Workflows
    "Workflow",
    "Parallel",
    "Sequential",
    "Conditional",
    "Loop",
    
    # Utilities
    "RetryPolicy",
    "TimeoutPolicy",
    "CircuitBreaker",
    
    # Types
    "FlowState",
    "NodeResult",
    "StreamChunk",
]

from .core.flow import Flow, Node, Edge, State
from .core.state import FlowState, NodeResult
from .agents.agent import Agent, Role
from .agents.team import AgentTeam
from .tools.tool import Tool, Action, tool
from .memory.memory import Memory, ShortTermMemory, LongTermMemory, ContextWindow
from .streaming.stream import Stream, EventBus, EventType, StreamChunk
from .observability.tracer import Tracer, Metrics, ObservabilityConfig
from .llm.provider import LLM, Provider, Message, ChatRole
from .vector.store import VectorStore, EmbeddingModel, Document
from .workflows.workflow import Workflow
from .workflows.composition import Parallel, Sequential, Conditional, Loop
from .policies.retry import RetryPolicy
from .policies.timeout import TimeoutPolicy
from .policies.circuit_breaker import CircuitBreaker

# Convenience imports
from .decorators import flow, node, agent, tool as tool_decorator
