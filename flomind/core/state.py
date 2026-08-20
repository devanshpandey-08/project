"""
FlowMind Core State Management

Key Innovation: Immutable, versioned state with full history for debugging.
When a flow fails at step 7, you can inspect the exact state at steps 1-6.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypeVar, Generic
from datetime import datetime
import copy
import hashlib

T = TypeVar('T')


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable snapshot of state at a point in time."""
    version: int
    timestamp: datetime
    data: Dict[str, Any]
    node_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Create immutable hash for quick comparison
        object.__setattr__(self, '_hash', self._compute_hash())
    
    def _compute_hash(self) -> str:
        """Compute hash of state for change detection."""
        content = f"{self.version}:{self.timestamp.isoformat()}:{str(sorted(self.data.items()))}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    @property
    def hash(self) -> str:
        return self._hash
    
    def diff(self, other: 'StateSnapshot') -> Dict[str, Any]:
        """Show what changed between two snapshots."""
        if self.version >= other.version:
            return {}
        
        changes = {}
        all_keys = set(self.data.keys()) | set(other.data.keys())
        
        for key in all_keys:
            old_val = self.data.get(key, '<missing>')
            new_val = other.data.get(key, '<missing>')
            if old_val != new_val:
                changes[key] = {'old': old_val, 'new': new_val}
        
        return changes


@dataclass
class StateHistory:
    """Complete history of state changes for debugging."""
    snapshots: List[StateSnapshot] = field(default_factory=list)
    max_history: int = 100  # Keep last 100 snapshots
    
    def add(self, snapshot: StateSnapshot):
        """Add a new snapshot, maintaining max history."""
        self.snapshots.append(snapshot)
        if len(self.snapshots) > self.max_history:
            self.snapshots = self.snapshots[-self.max_history:]
    
    def get_at_version(self, version: int) -> Optional[StateSnapshot]:
        """Retrieve state at specific version (for debugging)."""
        for snapshot in self.snapshots:
            if snapshot.version == version:
                return snapshot
        return None
    
    def get_last_n(self, n: int) -> List[StateSnapshot]:
        """Get last N snapshots for inspection."""
        return self.snapshots[-n:]
    
    def replay_to(self, version: int) -> Optional[Dict[str, Any]]:
        """Replay state to a specific version (for recovery)."""
        snapshot = self.get_at_version(version)
        return snapshot.data if snapshot else None


@dataclass
class State:
    """
    Main state container with versioning and history.
    
    Production Reality: When your 10-node flow fails at step 7,
    you need to see exactly what happened at steps 1-6.
    """
    data: Dict[str, Any] = field(default_factory=dict)
    version: int = 0
    history: StateHistory = field(default_factory=StateHistory)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata for observability
    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    node_executions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def update(self, **kwargs) -> 'State':
        """
        Update state immutably - returns new State with incremented version.
        This prevents race conditions in parallel execution.
        """
        new_data = copy.deepcopy(self.data)
        new_data.update(kwargs)
        
        new_version = self.version + 1
        now = datetime.utcnow()
        
        # Create snapshot before updating
        snapshot = StateSnapshot(
            version=self.version,
            timestamp=self.updated_at,
            data=copy.deepcopy(self.data),
            metadata={'trace_id': self.trace_id}
        )
        self.history.add(snapshot)
        
        # Return new state (immutable pattern)
        new_state = State(
            data=new_data,
            version=new_version,
            history=self.history,
            created_at=self.created_at,
            updated_at=now,
            trace_id=self.trace_id,
            parent_span_id=self.parent_span_id,
            node_executions=copy.deepcopy(self.node_executions)
        )
        
        return new_state
    
    def set_node_result(self, node_id: str, result: Any, 
                        latency_ms: float, success: bool, 
                        error: Optional[str] = None,
                        cached: bool = False):
        """Record node execution details for observability."""
        self.node_executions[node_id] = {
            'result': result,
            'latency_ms': latency_ms,
            'success': success,
            'error': error,
            'timestamp': datetime.utcnow().isoformat(),
            'state_version': self.version,
            'cached': cached
        }
    
    def get_node_history(self, node_id: str) -> List[Dict[str, Any]]:
        """Get all executions of a specific node (for debugging retries)."""
        return [
            exec_record for nid, exec_record in self.node_executions.items()
            if nid == node_id or nid.startswith(f"{node_id}_")
        ]
    
    def get_failed_nodes(self) -> List[str]:
        """Quickly identify which nodes failed."""
        return [
            node_id for node_id, exec_record in self.node_executions.items()
            if not exec_record.get('success', True)
        ]
    
    def get_total_latency(self) -> float:
        """Calculate total flow latency."""
        return sum(
            exec_record.get('latency_ms', 0) 
            for exec_record in self.node_executions.values()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for logging/storage."""
        return {
            'version': self.version,
            'data': self.data,
            'trace_id': self.trace_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'node_count': len(self.node_executions),
            'failed_nodes': self.get_failed_nodes(),
            'total_latency_ms': self.get_total_latency()
        }
    
    def debug_string(self) -> str:
        """Human-readable debug output."""
        lines = [
            f"State(v{self.version}, trace={self.trace_id})",
            f"Data keys: {list(self.data.keys())}",
            f"Nodes executed: {len(self.node_executions)}",
        ]
        
        failed = self.get_failed_nodes()
        if failed:
            lines.append(f"❌ Failed nodes: {failed}")
        else:
            lines.append("✅ All nodes successful")
        
        lines.append(f"⏱️ Total latency: {self.get_total_latency():.2f}ms")
        
        return "\n".join(lines)
