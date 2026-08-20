"""Type-safe state management for FlowMind flows."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Generic, TypeVar, get_type_hints
from copy import deepcopy
import json

T = TypeVar("T")


@dataclass
class FlowState:
    """
    Strongly-typed state container for flow execution.
    
    Replaces LangChain's dictionary-based state with type-safe access.
    Supports nested state, validation, and automatic serialization.
    """
    _data: Dict[str, Any] = field(default_factory=dict)
    _schema: Dict[str, type] = field(default_factory=dict)
    _readonly: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self._data:
            self._data = {}
        if not self._schema:
            self._schema = {}
        if not self._readonly:
            self._readonly = []
    
    def define_schema(self, **kwargs) -> "FlowState":
        """Define the schema for type-safe state access."""
        self._schema.update(kwargs)
        return self
    
    def set_readonly(self, *keys: str) -> "FlowState":
        """Mark keys as readonly (cannot be modified after initial set)."""
        self._readonly.extend(keys)
        return self
    
    def __setitem__(self, key: str, value: Any) -> None:
        # Validate against schema if defined
        if key in self._schema:
            expected_type = self._schema[key]
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"Key '{key}' expects type {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )
        
        # Check readonly
        if key in self._readonly and key in self._data:
            raise ValueError(f"Key '{key}' is readonly and cannot be modified")
        
        self._data[key] = deepcopy(value)
    
    def __getitem__(self, key: str) -> Any:
        if key not in self._data:
            raise KeyError(f"Key '{key}' not found in state")
        return deepcopy(self._data[key])
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state with optional default."""
        try:
            return self[key]
        except KeyError:
            return default
    
    def __contains__(self, key: str) -> bool:
        return key in self._data
    
    def __delitem__(self, key: str) -> None:
        if key in self._readonly:
            raise ValueError(f"Key '{key}' is readonly and cannot be deleted")
        del self._data[key]
    
    def update(self, data: Dict[str, Any], validate: bool = True) -> "FlowState":
        """Update state with multiple values."""
        for key, value in data.items():
            if validate:
                self[key] = value
            else:
                self._data[key] = deepcopy(value)
        return self
    
    def merge(self, other: "FlowState") -> "FlowState":
        """Merge another state into this one."""
        self._data.update(deepcopy(other._data))
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Export state as a dictionary."""
        return deepcopy(self._data)
    
    def to_json(self, indent: int = 2) -> str:
        """Export state as JSON string."""
        return json.dumps(self._data, indent=indent, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], schema: Optional[Dict[str, type]] = None) -> "FlowState":
        """Create a FlowState from a dictionary."""
        state = cls(_data=data, _schema=schema or {})
        return state
    
    @classmethod
    def from_json(cls, json_str: str, schema: Optional[Dict[str, type]] = None) -> "FlowState":
        """Create a FlowState from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data, schema)
    
    def keys(self) -> List[str]:
        """Get all keys in state."""
        return list(self._data.keys())
    
    def clear(self) -> "FlowState":
        """Clear all non-readonly state."""
        self._data = {k: v for k, v in self._data.items() if k in self._readonly}
        return self
    
    def snapshot(self) -> "FlowState":
        """Create a snapshot of current state."""
        return FlowState(
            _data=deepcopy(self._data),
            _schema=deepcopy(self._schema),
            _readonly=self._readonly.copy()
        )
    
    def __repr__(self) -> str:
        return f"FlowState({self._data})"
    
    def __len__(self) -> int:
        return len(self._data)


@dataclass
class FlowContext:
    """
    Execution context passed through flow nodes.
    
    Contains state plus execution metadata like trace IDs, 
    retry counts, and cancellation signals.
    """
    state: FlowState = field(default_factory=FlowState)
    trace_id: Optional[str] = None
    parent_trace_id: Optional[str] = None
    node_id: Optional[str] = None
    attempt: int = 0
    cancelled: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def cancel(self) -> None:
        """Signal cancellation of the flow."""
        self.cancelled = True
    
    def is_cancelled(self) -> bool:
        """Check if flow has been cancelled."""
        return self.cancelled
    
    def child_context(self, node_id: str) -> "FlowContext":
        """Create a child context for a specific node."""
        return FlowContext(
            state=self.state,
            trace_id=self.trace_id,
            parent_trace_id=self.trace_id,
            node_id=node_id,
            attempt=0,
            cancelled=self.cancelled,
            metadata={**self.metadata, "parent_node": self.node_id}
        )
    
    def increment_attempt(self) -> None:
        """Increment retry attempt counter."""
        self.attempt += 1
