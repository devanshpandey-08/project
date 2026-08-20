"""
State management for FlowMind.

Provides type-safe state handling for flows and workflows.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class NodeResult:
    """Result from executing a node."""
    node_id: str
    success: bool
    output: Any = None
    error: Optional[Exception] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def ok(cls, node_id: str, output: Any, **kwargs) -> 'NodeResult':
        return cls(node_id=node_id, success=True, output=output, **kwargs)
    
    @classmethod
    def fail(cls, node_id: str, error: Exception, **kwargs) -> 'NodeResult':
        return cls(node_id=node_id, success=False, error=error, **kwargs)


@dataclass
class StateSnapshot:
    """A snapshot of state at a point in time."""
    timestamp: datetime
    data: Dict[str, Any]
    version: int = 0


@dataclass
class FlowState:
    """
    The state that flows through the execution graph.
    
    Provides a type-safe container for data passing between nodes.
    """
    
    # Input data
    inputs: Dict[str, Any] = field(default_factory=dict)
    
    # Output from each node
    outputs: Dict[str, Any] = field(default_factory=dict)
    
    # Errors encountered
    errors: List[Exception] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Execution history
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Snapshots for debugging/replay
    snapshots: List[StateSnapshot] = field(default_factory=list)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from inputs or outputs."""
        if key in self.inputs:
            return self.inputs[key]
        return self.outputs.get(key, default)
    
    def set(self, key: str, value: Any) -> 'FlowState':
        """Set a value in outputs."""
        self.outputs[key] = value
        return self
    
    def add_input(self, key: str, value: Any) -> 'FlowState':
        """Add an input value."""
        self.inputs[key] = value
        return self
    
    def add_error(self, error: Exception) -> 'FlowState':
        """Record an error."""
        self.errors.append(error)
        return self
    
    def record_history(self, node_id: str, action: str, data: Any) -> 'FlowState':
        """Record an action in history."""
        self.history.append({
            'node_id': node_id,
            'action': action,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
        return self
    
    def take_snapshot(self, version: Optional[int] = None) -> 'FlowState':
        """Take a snapshot of current state."""
        if version is None:
            version = len(self.snapshots)
        
        snapshot = StateSnapshot(
            timestamp=datetime.now(),
            data=self.to_dict(),
            version=version
        )
        self.snapshots.append(snapshot)
        return self
    
    def restore_snapshot(self, version: int) -> bool:
        """Restore state from a snapshot."""
        for snapshot in self.snapshots:
            if snapshot.version == version:
                self._from_dict(snapshot.data)
                return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            'inputs': self.inputs,
            'outputs': self.outputs,
            'errors': [str(e) for e in self.errors],
            'metadata': self.metadata,
            'history': self.history,
        }
    
    def _from_dict(self, data: Dict[str, Any]) -> None:
        """Restore state from dictionary."""
        self.inputs = data.get('inputs', {})
        self.outputs = data.get('outputs', {})
        self.errors = [Exception(e) for e in data.get('errors', [])]
        self.metadata = data.get('metadata', {})
        self.history = data.get('history', [])
    
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0
    
    def clear(self) -> 'FlowState':
        """Clear all state."""
        self.inputs.clear()
        self.outputs.clear()
        self.errors.clear()
        self.metadata.clear()
        self.history.clear()
        return self
    
    def copy(self) -> 'FlowState':
        """Create a copy of this state."""
        return FlowState(
            inputs=self.inputs.copy(),
            outputs=self.outputs.copy(),
            errors=self.errors.copy(),
            metadata=self.metadata.copy(),
            history=self.history.copy(),
        )
