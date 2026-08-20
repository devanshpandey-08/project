"""
FlowMind - The Last AI Orchestration Framework You'll Ever Need

FlowMind completely replaces LangChain and LangGraph with a unified,
type-safe, production-ready framework designed for enterprise scale.

Key Features:
- Single primitive: Flow (replaces Chains + Graphs)
- Type-safe state management
- Built-in security (encryption, PII detection, RBAC)
- Native observability (tracing, metrics, audit logs)
- Multi-agent orchestration
- Resilience patterns (retry, timeout, circuit breaker)
- Async-native execution
- Provider-agnostic LLM interface
"""

__version__ = "1.0.0"
__author__ = "FlowMind Team"

# Core Primitives
from flomind.core.flow import FlowState, FlowContext
from flomind.core.node import Node, NodeType
from flomind.core.edge import Edge, ConditionalEdge
from flomind.core.executor import FlowExecutor
from flomind.core import Flow, create_flow

# Agents & Teams
from flomind.agents.agent import Agent
from flomind.agents.team import Team
from flomind.agents.roles import (
    ManagerAgent,
    ResearcherAgent,
    WriterAgent,
    CoderAgent,
    ReviewerAgent,
)

# Tools System
from flomind.tools.tool import Tool, tool, ToolRegistry

# Memory Systems
from flomind.memory.short_term import ShortTermMemory
from flomind.memory.long_term import LongTermMemory
from flomind.memory.vector import VectorMemory

# Security
from flomind.security.encryptor import Encryptor
from flomind.security.pii import PIIDetector, RedactionLevel
from flomind.security.sanitizer import InputSanitizer

# Observability - placeholder imports (modules to be implemented)
# from flomind.observability.tracer import Tracer, Span
# from flomind.observability.metrics import MetricsCollector
# from flomind.observability.logger import StructuredLogger

# Configuration - placeholder imports
# from flomind.config.settings import FlowMindConfig, ConfigLoader

# Integrations - placeholder imports
# from flomind.integrations.llm import LLMProvider, OpenAIProvider, AnthropicProvider
# from flomind.integrations.vector import VectorStore, PineconeStore

# Utilities
from flomind.core.types import FlowResult, StreamChunk

__all__ = [
    # Core
    "Flow",
    "FlowState",
    "FlowContext",
    "Node",
    "NodeType",
    "Edge",
    "ConditionalEdge",
    "FlowExecutor",
    # Agents
    "Agent",
    "Team",
    "ManagerAgent",
    "ResearcherAgent",
    "WriterAgent",
    "CoderAgent",
    "ReviewerAgent",
    # Tools
    "Tool",
    "tool",
    "ToolRegistry",
    # Memory
    "ShortTermMemory",
    "LongTermMemory",
    "VectorMemory",
    # Security
    "Encryptor",
    "PIIDetector",
    "RedactionLevel",
    "InputSanitizer",
    "AuditLogger",
    "AuditEvent",
    "RBACManager",
    "Role",
    "Permission",
    "RateLimiter",
    "RateLimitPolicy",
    # Observability
    "Tracer",
    "Span",
    "MetricsCollector",
    "StructuredLogger",
    # Config
    "FlowMindConfig",
    "ConfigLoader",
    # Integrations
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "VectorStore",
    "PineconeStore",
    # Types
    "FlowResult",
    "StreamChunk",
]
