"""AegisFlow Core - Type-safe, Immutable State Management"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import time
import json

@dataclass(frozen=True)
class FlowState:
    """Immutable state with versioned snapshots using JSON serialization"""
    _data_json: str = "{}"
    version: int = 0
    checkpoint_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    
    def _get_data(self) -> dict:
        return json.loads(self._data_json)
    
    def get(self, key: str, default: Any = None) -> Any:
        data = self._get_data()
        return data.get(key, default)
    
    def set(self, key: str, value: Any) -> 'FlowState':
        """Returns new state instance (immutable)"""
        data = self._get_data()
        data[key] = value
        new_json = json.dumps(data, sort_keys=True)
        return FlowState(
            _data_json=new_json,
            version=self.version + 1,
            checkpoint_id=self.checkpoint_id
        )
    
    def take_snapshot(self) -> dict:
        return {
            "data": self._get_data(),
            "version": self.version,
            "checkpoint_id": self.checkpoint_id,
            "timestamp": self.created_at
        }
    
    def __hash__(self):
        return hash((self._data_json, self.version))

@dataclass
class NodeConfig:
    retry_count: int = 0
    timeout_seconds: float = 30.0
    cache_enabled: bool = False
    encrypt_state: bool = False
    required_role: Optional[str] = None

class Result:
    """Type-safe result wrapper"""
    def __init__(self, success: bool, value: Any = None, error: Optional[str] = None):
        self.success = success
        self._value = value
        self.error = error
    
    @classmethod
    def ok(cls, value: Any) -> 'Result':
        return cls(success=True, value=value)
    
    @classmethod
    def fail(cls, error: str) -> 'Result':
        return cls(success=False, error=error)
    
    def unwrap(self) -> Any:
        if not self.success:
            raise RuntimeError(f"Attempted to unwrap failed result: {self.error}")
        return self._value

class ExecutionMode:
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
