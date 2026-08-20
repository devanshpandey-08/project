"""
FlowMind - The Last AI Orchestration Framework You'll Ever Need.

Replaces LangChain & LangGraph with a unified, type-safe, secure, and 
enterprise-grade architecture designed for production at scale.
"""

__version__ = "2.0.0"
__author__ = "FlowMind Team"

# Core Primitives
from flomind.core.flow import Flow, FlowState, FlowResult
from flomind.core.node import Node, NodeType, NodeStatus
from flomind.core.edge import Edge, EdgeCondition
from flomind.core.executor import FlowExecutor

# Agents & Teams
from flomind.agents.agent import Agent, AgentRole
from flomind.agents.team import Team, TeamStrategy

# Tools System
from flomind.tools.tool import Tool, ToolResult, ToolError
from flomind.tools.registry import ToolRegistry

# Memory Systems
from flomind.memory.short_term import ShortTermMemory
from flomind.memory.long_term import LongTermMemory
from flomind.memory.vector_store import VectorStore

# Security Suite
from flomind.security.encryption import Encryptor
from flomind.security.pii import PIIDetector, PIIType
from flomind.security.sanitizer import InputSanitizer

# Audit & Compliance
from flomind.audit.logger import AuditLogger, AuditEvent, AuditEventType
from flomind.audit.compliance import ComplianceChecker

# Access Control
from flomind.rbac.manager import RBACManager
from flomind.rbac.role import Role, Permission

# Rate Limiting
from flomind.rate_limit.limiter import RateLimiter, RateLimitPolicy

# Resilience Patterns
from flomind.core.resilience import RetryPolicy, TimeoutPolicy, CircuitBreaker

# Observability
from flomind.observability.tracer import Tracer, Span
from flomind.observability.metrics import MetricsCollector

# Configuration
from flomind.config.settings import FlowMindConfig, Settings

# Integrations (Lazy loaded to avoid heavy deps)
def get_openai_client():
    from flomind.integrations.openai_client import OpenAIClient
    return OpenAIClient

def get_anthropic_client():
    from flomind.integrations.anthropic_client import AnthropicClient
    return AnthropicClient

def get_pinecone_client():
    from flomind.integrations.pinecone_client import PineconeClient
    return PineconeClient

# Factory Functions
from flomind.flows.factory import create_flow, create_agent, create_team

__all__ = [
    # Core
    "Flow", "FlowState", "FlowResult", "Node", "NodeType", "NodeStatus",
    "Edge", "EdgeCondition", "FlowExecutor",
    
    # Agents
    "Agent", "AgentRole", "Team", "TeamStrategy",
    
    # Tools
    "Tool", "ToolResult", "ToolError", "ToolRegistry",
    
    # Memory
    "ShortTermMemory", "LongTermMemory", "VectorStore",
    
    # Security
    "Encryptor", "PIIDetector", "PIIType", "InputSanitizer",
    
    # Audit
    "AuditLogger", "AuditEvent", "ComplianceChecker",
    
    # RBAC
    "RBACManager", "Role", "Permission",
    
    # Rate Limiting
    "RateLimiter", "RateLimitPolicy",
    
    # Resilience
    "RetryPolicy", "TimeoutPolicy", "CircuitBreaker",
    
    # Observability
    "Tracer", "Span", "MetricsCollector",
    
    # Config
    "FlowMindConfig", "Settings",
    
    # Factories
    "create_flow", "create_agent", "create_team",
    
    # Integrations
    "get_openai_client", "get_anthropic_client", "get_pinecone_client",
]
