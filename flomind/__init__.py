"""
FlowMind - The Last AI Orchestration Framework You'll Need

Designed for production reality: LLM latency dominates, debugging matters,
and developer experience wins.
"""

__version__ = "2.0.0"
__author__ = "FlowMind Team"

# Core Primitives
from flomind.core.flow import Flow, FlowBuilder
from flomind.core.state import State, StateSnapshot
from flomind.core.node import Node, NodeType

# Agents & Teams
from flomind.agents.agent import Agent
from flomind.agents.team import Team, TeamMode

# Tools
from flomind.tools.tool import Tool, tool
from flomind.tools.registry import ToolRegistry

# Memory
from flomind.memory.short_term import ShortTermMemory
from flomind.memory.long_term import LongTermMemory

# Observability (The Real Differentiator)
from flomind.observability.tracer import FlowTracer, Span
from flomind.observability.metrics import MetricsCollector
from flomind.observability.debugger import FlowDebugger

# Resilience (Production Ready)
from flomind.resilience.retry import RetryStrategy
from flomind.resilience.circuit_breaker import CircuitBreaker
from flomind.resilience.timeout import TimeoutPolicy

# Alias for convenience
RetryPolicy = RetryStrategy

# Integrations
from flomind.integrations.openai import OpenAIProvider
from flomind.integrations.anthropic import AnthropicProvider
from flomind.integrations.vector_store import VectorStore

# Types
from flomind.types.context import ExecutionContext
from flomind.types.result import Result, Success, Failure

__all__ = [
    # Core
    "Flow",
    "FlowBuilder",
    "State",
    "StateSnapshot",
    "Node",
    "NodeType",
    # Agents
    "Agent",
    "Team",
    "TeamMode",
    # Tools
    "Tool",
    "tool",
    "ToolRegistry",
    # Memory
    "ShortTermMemory",
    "LongTermMemory",
    # Observability
    "FlowTracer",
    "Span",
    "MetricsCollector",
    "FlowDebugger",
    # Resilience
    "RetryStrategy",
    "CircuitBreaker",
    "TimeoutPolicy",
    # Integrations
    "OpenAIProvider",
    "AnthropicProvider",
    "VectorStore",
    # Types
    "ExecutionContext",
    "Result",
    "Success",
    "Failure",
]
