"""Role-Based Access Control (RBAC) for enterprise security."""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class PermissionAction(Enum):
    """Allowed actions in permissions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class Permission:
    """
    Fine-grained permission definition.
    
    Format: resource:action (e.g., "flow:read", "agent:execute")
    """
    resource: str
    action: PermissionAction
    
    def __str__(self) -> str:
        return f"{self.resource}:{self.action.value}"
        
    @classmethod
    def from_string(cls, perm_str: str) -> 'Permission':
        """Create permission from string like 'flow:read'."""
        parts = perm_str.split(':')
        if len(parts) != 2:
            raise ValueError(f"Invalid permission format: {perm_str}")
        resource, action = parts
        return cls(resource=resource, action=PermissionAction(action))


@dataclass
class Role:
    """Role with associated permissions."""
    name: str
    description: str = ""
    permissions: Set[str] = field(default_factory=set)
    inherits: List[str] = field(default_factory=list)  # Parent roles
    
    def add_permission(self, permission: str) -> None:
        """Add a permission to the role."""
        self.permissions.add(permission)
        
    def remove_permission(self, permission: str) -> bool:
        """Remove a permission from the role."""
        if permission in self.permissions:
            self.permissions.remove(permission)
            return True
        return False
        
    def has_permission(self, permission: str) -> bool:
        """Check if role has a specific permission."""
        return permission in self.permissions


class RBACManager:
    """
    Enterprise Role-Based Access Control Manager.
    
    Features:
    - Fine-grained permissions (resource:action)
    - Role hierarchy with inheritance
    - Multi-tenancy support
    - Custom validators
    - Audit integration ready
    """
    
    # Built-in system roles
    SYSTEM_ROLES = {
        "admin": Role(
            name="admin",
            description="Full system access",
            permissions={"*:*"}  # Wildcard for all permissions
        ),
        "developer": Role(
            name="developer",
            description="Development access",
            permissions={
                "flow:create", "flow:read", "flow:update", "flow:delete",
                "agent:create", "agent:read", "agent:update", "agent:execute",
                "tool:create", "tool:read", "tool:execute"
            }
        ),
        "executor": Role(
            name="executor",
            description="Execution only access",
            permissions={
                "flow:read", "flow:execute",
                "agent:read", "agent:execute"
            }
        ),
        "viewer": Role(
            name="viewer",
            description="Read-only access",
            permissions={
                "flow:read", "agent:read", "tool:read"
            }
        )
    }
    
    def __init__(self, tenant_id: Optional[str] = None):
        """
        Initialize RBAC manager.
        
        Args:
            tenant_id: Optional tenant ID for multi-tenancy
        """
        self.tenant_id = tenant_id
        self.roles: Dict[str, Role] = dict(self.SYSTEM_ROLES)
        self.user_roles: Dict[str, Set[str]] = {}  # user_id -> set of role names
        self.resource_permissions: Dict[str, Dict[str, Set[str]]] = {}  # resource_id -> user_id -> permissions
        
    def create_role(
        self,
        name: str,
        description: str = "",
        permissions: Optional[List[str]] = None,
        inherits: Optional[List[str]] = None
    ) -> Role:
        """Create a custom role."""
        if name in self.roles:
            raise ValueError(f"Role already exists: {name}")
            
        role = Role(
            name=name,
            description=description,
            permissions=set(permissions or []),
            inherits=inherits or []
        )
        
        # Expand inherited permissions
        for parent_name in role.inherits:
            if parent_name in self.roles:
                parent = self.roles[parent_name]
                role.permissions.update(parent.permissions)
                
        self.roles[name] = role
        return role
        
    def assign_role(self, user_id: str, role_name: str) -> None:
        """Assign a role to a user."""
        if role_name not in self.roles:
            raise ValueError(f"Role not found: {role_name}")
            
        if user_id not in self.user_roles:
            self.user_roles[user_id] = set()
            
        self.user_roles[user_id].add(role_name)
        
    def revoke_role(self, user_id: str, role_name: str) -> bool:
        """Revoke a role from a user."""
        if user_id in self.user_roles and role_name in self.user_roles[user_id]:
            self.user_roles[user_id].remove(role_name)
            return True
        return False
        
    def get_user_permissions(self, user_id: str) -> Set[str]:
        """Get all effective permissions for a user."""
        if user_id not in self.user_roles:
            return set()
            
        permissions = set()
        
        for role_name in self.user_roles[user_id]:
            if role_name in self.roles:
                role = self.roles[role_name]
                permissions.update(role.permissions)
                
        return permissions
        
    def has_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has a specific permission."""
        user_perms = self.get_user_permissions(user_id)
        
        # Check wildcard
        if "*:*" in user_perms:
            return True
            
        # Check exact match
        if permission in user_perms:
            return True
            
        # Check resource wildcard (e.g., flow:* matches flow:read)
        resource = permission.split(':')[0] if ':' in permission else permission
        if f"{resource}:*" in user_perms:
            return True
            
        return False
        
    def check_access(
        self,
        user_id: str,
        resource: str,
        action: str
    ) -> bool:
        """Check if user can perform action on resource."""
        permission = f"{resource}:{action}"
        return self.has_permission(user_id, permission)
        
    def grant_resource_permission(
        self,
        resource_id: str,
        user_id: str,
        permission: str
    ) -> None:
        """Grant specific permission on a resource to a user."""
        if resource_id not in self.resource_permissions:
            self.resource_permissions[resource_id] = {}
        if user_id not in self.resource_permissions[resource_id]:
            self.resource_permissions[resource_id][user_id] = set()
        self.resource_permissions[resource_id][user_id].add(permission)
        
    def check_resource_access(
        self,
        user_id: str,
        resource_id: str,
        action: str
    ) -> bool:
        """Check resource-level permission."""
        # First check global permission
        if self.check_access(user_id, "*", action):
            return True
            
        # Then check resource-specific permission
        if resource_id in self.resource_permissions:
            if user_id in self.resource_permissions[resource_id]:
                perms = self.resource_permissions[resource_id][user_id]
                if f"*:{action}" in perms or f"{resource_id}:{action}" in perms:
                    return True
                    
        return False
