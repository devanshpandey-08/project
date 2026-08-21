# RBAC logic is now in crypto.py - this file re-exports for compatibility
from aegisflow.security.crypto import Role, RBACManager
__all__ = ["Role", "RBACManager"]
