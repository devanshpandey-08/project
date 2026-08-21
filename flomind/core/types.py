"""Core type definitions with strict typing."""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypeVar, Generic
from datetime import datetime, timezone
import hashlib

T = TypeVar('T')
E = TypeVar('E', bound=Exception)


class ExecutionMode(Enum):
    """Execution strategy for nodes."""
    SEQUENTIAL = auto()
    PARALLEL = auto()
    CONDITIONAL = auto()


class NodeStatus(Enum):
    """Node execution status."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()
    INTERRUPTED = auto()


@dataclass(frozen=True)
class Result(Generic[T]):
    """Monadic result type for error handling."""
    success: bool
    value: Optional[T] = None
    error: Optional[str] = None
    
    @classmethod
    def ok(cls, value: T) -> 'Result[T]':
        return cls(success=True, value=value)
    
    @classmethod
    def fail(cls, error: str) -> 'Result[T]':
        return cls(success=False, error=error)
    
    def map(self, fn) -> 'Result':
        if self.success and self.value is not None:
            return Result.ok(fn(self.value))
        return self
    
    def bind(self, fn) -> 'Result':
        if self.success and self.value is not None:
            return fn(self.value)
        return self


@dataclass(frozen=True)
class NodeConfig:
    """Immutable node configuration."""
    retry_count: int = 3
    timeout_seconds: float = 30.0
    cache_enabled: bool = False
    cache_ttl_seconds: int = 3600
    circuit_breaker_threshold: int = 5
    rate_limit_per_minute: int = 60
    
    def __post_init__(self):
        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class ExecutionRecord:
    """Immutable execution record for audit trail."""
    node_id: str
    status: NodeStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    trace_id: str = field(default_factory=lambda: hashlib.md5(f"{datetime.now(timezone.utc)}".encode()).hexdigest()[:12])
    
    def __post_init__(self):
        if self.completed_at and self.started_at > self.completed_at:
            raise ValueError("started_at cannot be after completed_at")
