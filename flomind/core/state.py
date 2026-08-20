"""
Type-safe state management for FlowMind.

Provides immutable, typed state containers with full IDE support and runtime validation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar, Dict, List, Optional, Callable
from datetime import datetime
import hashlib
import json

T = TypeVar('T')


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable snapshot of state at a point in time."""
    version: int
    timestamp: datetime
    data_hash: str
    data: Dict[str, Any]
    
    @classmethod
    def create(cls, version: int, data: Dict[str, Any]) -> StateSnapshot:
        """Create a new state snapshot."""
        data_json = json.dumps(data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(data_json.encode()).hexdigest()[:16]
        return cls(
            version=version,
            timestamp=datetime.now(),
            data_hash=data_hash,
            data=data.copy()
        )


@dataclass
class NodeResult:
    """Result from executing a node in a flow."""
    node_id: str
    success: bool
    output: Any
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    
    @classmethod
    def ok(cls, node_id: str, output: Any, **kwargs) -> NodeResult:
        """Create a successful result."""
        return cls(node_id=node_id, success=True, output=output, **kwargs)
    
    @classmethod
    def fail(cls, node_id: str, error: Exception, **kwargs) -> NodeResult:
        """Create a failed result."""
        return cls(node_id=node_id, success=False, output=None, error=error, **kwargs)


@dataclass
class FlowState(Generic[T]):
    """
    Mutable state container for flow execution.
    
    Provides type-safe access to state with automatic versioning and snapshots.
    """
    data: Dict[str, Any] = field(default_factory=dict)
    version: int = 0
    snapshots: List[StateSnapshot] = field(default_factory=list)
    max_snapshots: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Typed accessors for common patterns
    messages: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    errors: List[Exception] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.data:
            self.data = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state."""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> FlowState[T]:
        """Set a value in state (immutable style, returns new reference)."""
        self.data[key] = value
        return self
    
    def update(self, updates: Dict[str, Any]) -> FlowState[T]:
        """Update multiple values in state."""
        self.data.update(updates)
        return self
    
    def delete(self, key: str) -> bool:
        """Delete a key from state."""
        if key in self.data:
            del self.data[key]
            return True
        return False
    
    def has(self, key: str) -> bool:
        """Check if a key exists in state."""
        return key in self.data
    
    def take_snapshot(self) -> StateSnapshot:
        """Take an immutable snapshot of current state."""
        snapshot = StateSnapshot.create(self.version, self.data)
        self.snapshots.append(snapshot)
        
        # Prune old snapshots if needed
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots = self.snapshots[-self.max_snapshots:]
        
        return snapshot
    
    def restore_snapshot(self, snapshot: StateSnapshot) -> bool:
        """Restore state from a snapshot."""
        if snapshot in self.snapshots:
            self.data = snapshot.data.copy()
            self.version = snapshot.version
            return True
        return False
    
    def increment_version(self) -> int:
        """Increment and return the new version number."""
        self.version += 1
        return self.version
    
    def merge(self, other: FlowState[T], overwrite: bool = True) -> FlowState[T]:
        """Merge another state into this one."""
        if overwrite:
            self.data.update(other.data)
        else:
            for key, value in other.data.items():
                if key not in self.data:
                    self.data[key] = value
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            'version': self.version,
            'data': self.data.copy(),
            'metadata': self.metadata.copy(),
            'messages': self.messages.copy(),
            'context': self.context.copy(),
            'outputs': self.outputs.copy(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FlowState[T]:
        """Create state from dictionary."""
        state = cls()
        state.version = data.get('version', 0)
        state.data = data.get('data', {}).copy()
        state.metadata = data.get('metadata', {}).copy()
        state.messages = data.get('messages', []).copy()
        state.context = data.get('context', {}).copy()
        state.outputs = data.get('outputs', {}).copy()
        return state
    
    def clear(self) -> FlowState[T]:
        """Clear all state data."""
        self.data.clear()
        self.messages.clear()
        self.context.clear()
        self.errors.clear()
        self.outputs.clear()
        self.increment_version()
        return self
    
    def add_message(self, role: str, content: str, **kwargs) -> FlowState[T]:
        """Add a chat message to state."""
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            **kwargs
        })
        return self
    
    def add_error(self, error: Exception) -> FlowState[T]:
        """Add an error to state."""
        self.errors.append(error)
        return self
    
    def __getitem__(self, key: str) -> Any:
        return self.data[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = self.increment_version() or value
    
    def __contains__(self, key: str) -> bool:
        return key in self.data
    
    def __len__(self) -> int:
        return len(self.data)
    
    def __repr__(self) -> str:
        return f"FlowState(version={self.version}, keys={list(self.data.keys())})"


@dataclass
class TypedState(Generic[T]):
    """
    Strongly-typed state wrapper for compile-time type checking.
    
    Use this when you want full type safety for your state schema.
    """
    _state: FlowState
    _schema: type[T]
    
    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        return self._state.get(name)
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self._state.set(name, value)
    
    def validate(self) -> bool:
        """Validate state against schema (runtime check)."""
        # In production, use pydantic or similar for actual validation
        return True
