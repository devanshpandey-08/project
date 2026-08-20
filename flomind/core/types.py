"""Core types for FlowMind framework."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Generic, TypeVar
from enum import Enum
import time
import uuid


T = TypeVar("T")


class FlowStatus(Enum):
    """Status of a flow execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StreamChunk:
    """A chunk of streamed output."""
    content: str
    node_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return self.content


@dataclass
class FlowResult(Generic[T]):
    """Result of a flow execution with full context."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    state: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    nodes_executed: List[str] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0
    trace_id: Optional[str] = None
    
    def raise_if_error(self) -> "FlowResult[T]":
        """Raise an exception if the flow failed."""
        if not self.success and self.error:
            raise FlowExecutionError(self.error)
        return self
    
    def get_data(self, default: Optional[T] = None) -> Optional[T]:
        """Get the result data or default."""
        return self.data if self.success else default


class FlowExecutionError(Exception):
    """Exception raised when a flow execution fails."""
    
    def __init__(self, message: str, node_id: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(message)
        self.node_id = node_id
        self.cause = cause


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay_ms: int = 100
    max_delay_ms: int = 10000
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior."""
    total_timeout_ms: Optional[int] = None
    node_timeout_ms: Optional[int] = None


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""
    failure_threshold: int = 5
    recovery_timeout_ms: int = 60000
    half_open_requests: int = 3


@dataclass
class FlowMetadata:
    """Metadata for flow execution tracking."""
    flow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_run_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
