"""
FlowMind Types - Execution Context

Type-safe context passing throughout flow execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid


@dataclass
class ExecutionContext:
    """
    Context passed through flow execution.
    
    Contains:
    - Trace information for observability
    - User/tenant information for multi-tenancy
    - Request metadata
    - Cancellation tokens
    """
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    
    # Multi-tenancy
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # Request info
    request_id: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    
    # Execution control
    timeout_seconds: Optional[float] = None
    cancel_requested: bool = False
    
    # Custom metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def should_cancel(self) -> bool:
        """Check if execution should be cancelled."""
        if self.cancel_requested:
            return True
        
        if self.timeout_seconds:
            elapsed = (datetime.utcnow() - self.started_at).total_seconds()
            if elapsed > self.timeout_seconds:
                return True
        
        return False
    
    def child_context(self, span_id: str) -> 'ExecutionContext':
        """Create a child context for a sub-operation."""
        return ExecutionContext(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=self.span_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            request_id=self.request_id,
            started_at=self.started_at,
            timeout_seconds=self.timeout_seconds,
            metadata={**self.metadata}
        )
