"""Immutable state management with versioned snapshots."""
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple
from datetime import datetime, timezone
import hashlib
import copy


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable state snapshot with cryptographic hash."""
    version: int
    timestamp: datetime
    data: FrozenSet[Tuple[str, Any]]
    node_executions: FrozenSet[Tuple[str, str]]  # (node_id, status)
    hash: str = field(default="")
    
    def __post_init__(self):
        if not self.hash:
            object.__setattr__(self, 'hash', self._compute_hash())
    
    def _compute_hash(self) -> str:
        content = f"{self.version}:{self.timestamp.isoformat()}:{str(self.data)}:{str(self.node_executions)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "data": dict(self.data),
            "node_executions": dict(self.node_executions),
            "hash": self.hash
        }


@dataclass
class FlowState:
    """Mutable flow state with immutable snapshot history."""
    _data: Dict[str, Any] = field(default_factory=dict)
    _node_results: Dict[str, Any] = field(default_factory=dict)
    _node_status: Dict[str, str] = field(default_factory=dict)
    _history: List[StateSnapshot] = field(default_factory=list)
    _current_version: int = 0
    _trace_id: str = field(default_factory=lambda: hashlib.md5(f"{datetime.now(timezone.utc)}".encode()).hexdigest()[:12])
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> 'FlowState':
        new_state = self._clone()
        new_state._data[key] = value
        return new_state
    
    def update(self, updates: Dict[str, Any]) -> 'FlowState':
        new_state = self._clone()
        new_state._data.update(updates)
        return new_state
    
    def set_node_result(self, node_id: str, result: Any) -> 'FlowState':
        new_state = self._clone()
        new_state._node_results[node_id] = result
        new_state._node_status[node_id] = "completed"
        return new_state
    
    def set_node_status(self, node_id: str, status: str) -> 'FlowState':
        new_state = self._clone()
        new_state._node_status[node_id] = status
        return new_state
    
    def get_node_result(self, node_id: str) -> Optional[Any]:
        return self._node_results.get(node_id)
    
    def get_node_status(self, node_id: str) -> Optional[str]:
        return self._node_status.get(node_id)
    
    def take_snapshot(self) -> 'FlowState':
        new_state = self._clone()
        new_state._current_version += 1
        
        snapshot = StateSnapshot(
            version=new_state._current_version,
            timestamp=datetime.now(timezone.utc),
            data=frozenset(self._data.items()),
            node_executions=frozenset(self._node_status.items())
        )
        new_state._history.append(snapshot)
        return new_state
    
    def restore_snapshot(self, version: int) -> Optional['FlowState']:
        for snapshot in reversed(self._history):
            if snapshot.version == version:
                new_state = self._clone()
                new_state._data = dict(snapshot.data)
                new_state._node_status = dict(snapshot.node_executions)
                new_state._current_version = version
                new_state._node_results = {}  # Reset results on restore
                return new_state
        return None
    
    def get_history(self) -> List[StateSnapshot]:
        return list(self._history)
    
    def get_latest_snapshot(self) -> Optional[StateSnapshot]:
        return self._history[-1] if self._history else None
    
    def _clone(self) -> 'FlowState':
        new_state = FlowState(
            _data=copy.deepcopy(self._data),
            _node_results=copy.deepcopy(self._node_results),
            _node_status=copy.deepcopy(self._node_status),
            _history=list(self._history),
            _current_version=self._current_version,
            _trace_id=self._trace_id
        )
        return new_state
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": dict(self._data),
            "node_results": dict(self._node_results),
            "node_status": dict(self._node_status),
            "version": self._current_version,
            "trace_id": self._trace_id,
            "history_length": len(self._history)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FlowState':
        state = cls()
        state._data = data.get("data", {})
        state._node_results = data.get("node_results", {})
        state._node_status = data.get("node_status", {})
        state._current_version = data.get("version", 0)
        state._trace_id = data.get("trace_id", state._trace_id)
        return state
