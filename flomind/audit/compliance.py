"""Audit module re-exports."""
from flomind.audit.logger import AuditLogger, AuditEvent, AuditEventType

# ComplianceChecker is an alias for AuditLogger
ComplianceChecker = AuditLogger

__all__ = ["AuditLogger", "AuditEvent", "AuditEventType", "ComplianceChecker"]
