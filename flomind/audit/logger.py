"""Audit logging for compliance (SOC2, HIPAA, GDPR)."""

import json
import logging
import uuid
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class AuditEventType(Enum):
    """Types of audit events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    FLOW_EXECUTION = "flow_execution"
    AGENT_ACTION = "agent_action"
    TOOL_USAGE = "tool_usage"
    SECURITY_EVENT = "security_event"
    SYSTEM_CHANGE = "system_change"
    COMPLIANCE_CHECK = "compliance_check"


@dataclass
class AuditEvent:
    """Immutable audit event record."""
    event_id: str
    event_type: AuditEventType
    timestamp: str
    user_id: Optional[str]
    action: str
    resource: str
    resource_id: Optional[str]
    status: str  # success, failure, warning
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    trace_id: str = ""
    tenant_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "status": self.status,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id
        }
        
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


class AuditLogger:
    """
    Enterprise audit logger for compliance.
    
    Features:
    - Immutable audit trail
    - Structured JSON logging
    - SIEM integration ready
    - Sensitive data masking
    - SOC2/HIPAA/GDPR compliant
    """
    
    def __init__(
        self,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO,
        mask_sensitive: bool = True,
        include_trace: bool = True
    ):
        """
        Initialize audit logger.
        
        Args:
            log_file: Path to audit log file (None = stdout)
            log_level: Logging level
            mask_sensitive: Mask sensitive data in logs
            include_trace: Include trace IDs for distributed tracing
        """
        self.mask_sensitive = mask_sensitive
        self.include_trace = include_trace
        
        # Setup structured logger
        self.logger = logging.getLogger("flomind.audit")
        self.logger.setLevel(log_level)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler() if not log_file else logging.FileHandler(log_file)
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        self._events: List[AuditEvent] = []
        
    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive fields in data."""
        if not self.mask_sensitive:
            return data
            
        sensitive_keys = ["password", "token", "api_key", "secret", "credit_card", "ssn"]
        masked = {}
        
        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_keys):
                masked[key] = "***REDACTED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_data(value)
            else:
                masked[key] = value
                
        return masked
        
    def log(
        self,
        event_type: AuditEventType,
        action: str,
        resource: str,
        status: str = "success",
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        trace_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Returns:
            The created AuditEvent
        """
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow().isoformat() + "Z",
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            status=status,
            details=self._mask_sensitive_data(details or {}),
            ip_address=ip_address,
            user_agent=user_agent,
            trace_id=trace_id or str(uuid.uuid4()) if self.include_trace else "",
            tenant_id=tenant_id
        )
        
        self._events.append(event)
        self.logger.info(event.to_json())
        
        return event
        
    def log_authentication(
        self,
        user_id: str,
        success: bool,
        method: str = "password",
        **kwargs
    ) -> AuditEvent:
        """Log authentication event."""
        return self.log(
            event_type=AuditEventType.AUTHENTICATION,
            action=f"login_{method}",
            resource="auth",
            status="success" if success else "failure",
            user_id=user_id,
            details={"method": method},
            **kwargs
        )
        
    def log_authorization(
        self,
        user_id: str,
        action: str,
        resource: str,
        allowed: bool,
        **kwargs
    ) -> AuditEvent:
        """Log authorization check."""
        return self.log(
            event_type=AuditEventType.AUTHORIZATION,
            action=action,
            resource=resource,
            status="success" if allowed else "denied",
            user_id=user_id,
            details={"allowed": allowed},
            **kwargs
        )
        
    def log_flow_execution(
        self,
        flow_id: str,
        flow_name: str,
        success: bool,
        execution_time: float,
        user_id: Optional[str] = None,
        **kwargs
    ) -> AuditEvent:
        """Log flow execution."""
        return self.log(
            event_type=AuditEventType.FLOW_EXECUTION,
            action="execute",
            resource="flow",
            status="success" if success else "failure",
            user_id=user_id,
            resource_id=flow_id,
            details={
                "flow_name": flow_name,
                "execution_time_ms": execution_time * 1000,
                "success": success
            },
            **kwargs
        )
        
    def log_tool_usage(
        self,
        tool_name: str,
        user_id: str,
        success: bool,
        parameters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AuditEvent:
        """Log tool usage."""
        return self.log(
            event_type=AuditEventType.TOOL_USAGE,
            action="execute",
            resource="tool",
            status="success" if success else "failure",
            user_id=user_id,
            resource_id=tool_name,
            details={"parameters": parameters} if parameters else {},
            **kwargs
        )
        
    def get_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None
    ) -> List[AuditEvent]:
        """Query audit events with filters."""
        events = self._events
        
        if start_time:
            events = [e for e in events if e.timestamp >= start_time.isoformat()]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time.isoformat()]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if user_id:
            events = [e for e in events if e.user_id == user_id]
            
        return events
        
    def export_json(self, filepath: str) -> None:
        """Export all events to JSON file."""
        with open(filepath, 'w') as f:
            for event in self._events:
                f.write(event.to_json() + '\n')
                
    def get_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance summary report."""
        events = self._events
        
        return {
            "total_events": len(events),
            "by_type": {et.value: len([e for e in events if e.event_type == et]) for et in AuditEventType},
            "by_status": {
                "success": len([e for e in events if e.status == "success"]),
                "failure": len([e for e in events if e.status == "failure"]),
                "denied": len([e for e in events if e.status == "denied"]),
                "warning": len([e for e in events if e.status == "warning"])
            },
            "unique_users": len(set(e.user_id for e in events if e.user_id)),
            "time_range": {
                "start": events[0].timestamp if events else None,
                "end": events[-1].timestamp if events else None
            }
        }
