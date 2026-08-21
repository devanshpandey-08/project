"""
AegisFlow v1.0.0 - Production-Grade AI Orchestration
Secure, Compliant, and Dual-Mode (Creative/Compliance)
"""

__version__ = "1.0.0"
__author__ = "AegisFlow Team"

# Core Exports
from aegisflow.core.flow import Flow, FlowBuilder
from aegisflow.core.state import FlowState
from aegisflow.core.node import Node, NodeConfig
from aegisflow.core.types import Result, ExecutionMode

# Security Exports
from aegisflow.security.crypto import Encryptor
from aegisflow.security.pii import PIIDetector, Redactor
from aegisflow.security.rbac import RBACManager, Role
from aegisflow.security.audit import AuditLogger

# Resilience Exports
from aegisflow.resilience.retry import RetryPolicy
from aegisflow.resilience.circuit_breaker import CircuitBreaker
from aegisflow.resilience.timeout import TimeoutPolicy

# Persistence Exports
from aegisflow.persistence.base import Checkpointer
from aegisflow.persistence.memory import MemorySaver
from aegisflow.persistence.sqlite import SQLiteSaver

# HITL Exports
from aegisflow.hitl.interrupt import HumanInterrupt, ApprovalPattern

# Agent Exports
from aegisflow.agents.dynamic import DynamicAgent, AgentMode

# Tool Exports
from aegisflow.tools.base import Tool

# Integrations
from aegisflow.integrations.llm import OpenAIClient, AnthropicClient

__all__ = [
    # Core
    "Flow", "FlowBuilder", "FlowState", "Node", "NodeConfig", "Result", "ExecutionMode",
    # Security
    "Encryptor", "PIIDetector", "Redactor", "RBACManager", "Role", "AuditLogger",
    # Resilience
    "RetryPolicy", "CircuitBreaker", "TimeoutPolicy",
    # Persistence
    "Checkpointer", "MemorySaver", "SQLiteSaver",
    # HITL
    "HumanInterrupt", "ApprovalPattern",
    # Agents
    "DynamicAgent", "AgentMode",
    # Tools
    "Tool",
    # Integrations
    "OpenAIClient", "AnthropicClient",
]
