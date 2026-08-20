"""
Role-Based Access Control (RBAC) for FlowMind
==============================================
Enterprise-grade permission management with:
- Fine-grained permissions (resource:action format)
- Role hierarchy with inheritance
- Multi-tenancy support
- Custom validators
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable
from enum import Enum
import fnmatch


class PermissionAction(Enum):
    """Standard permission actions."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    CREATE = "create"
    UPDATE = "update"


@dataclass
class Permission:
    """
    Represents a fine-grained permission.
    
    Format: "resource:action" or "*" for wildcard
    Examples:
        - "flow:read"
        - "agent:execute"
        - "memory:*"
        - "*" (all permissions)
    """
    pattern: str
    
    def __post_init__(self):
        if not self.pattern:
            raise ValueError("Permission pattern cannot be empty")
    
    def matches(self, other: "Permission") -> bool:
        """Check if this permission matches another (supports wildcards)."""
        if self.pattern == "*":
            return True
        if other.pattern == "*":
            return True
        return fnmatch.fnmatch(other.pattern, self.pattern)
    
    def __str__(self) -> str:
        return self.pattern
    
    def __hash__(self) -> int:
        return hash(self.pattern)
    
    def __eq__(self, other) -> bool:
        if isinstance(other, Permission):
            return self.pattern == other.pattern
        return False


@dataclass
class Role:
    """
    Represents a role with associated permissions.
    
    Attributes:
        name: Unique role identifier
        permissions: List of permissions granted to this role
        inherits: List of parent role names for inheritance
        description: Human-readable description
    """
    name: str
    permissions: List[Permission] = field(default_factory=list)
    inherits: List[str] = field(default_factory=list)
    description: str = ""
    
    def add_permission(self, permission: Permission) -> None:
        """Add a permission to this role."""
        if permission not in self.permissions:
            self.permissions.append(permission)
    
    def remove_permission(self, permission: Permission) -> bool:
        """Remove a permission from this role."""
        if permission in self.permissions:
            self.permissions.remove(permission)
            return True
        return False
    
    def get_all_permissions(self, role_registry: Dict[str, "Role"]) -> Set[Permission]:
        """Get all permissions including inherited ones."""
        all_perms: Set[Permission] = set(self.permissions)
        
        for parent_name in self.inherits:
            if parent_name in role_registry:
                parent_role = role_registry[parent_name]
                all_perms.update(parent_role.get_all_permissions(role_registry))
        
        return all_perms


@dataclass
class UserContext:
    """Context information about the current user."""
    user_id: str
    tenant_id: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


class RBACManager:
    """
    Enterprise Role-Based Access Control Manager.
    
    Features:
    - Role definition and management
    - Permission assignment
    - Role hierarchy with inheritance
    - Multi-tenancy support
    - Custom permission validators
    - Audit-ready permission checks
    """
    
    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, List[str]] = {}  # user_id -> [role_names]
        self._tenant_user_roles: Dict[str, Dict[str, List[str]]] = {}  # tenant_id -> user_id -> [roles]
        self._validators: Dict[str, Callable[[UserContext, Permission], bool]] = {}
        
        # Create default system roles
        self._create_default_roles()
    
    def _create_default_roles(self) -> None:
        """Create default system roles."""
        # Admin role - full access
        admin = Role(
            name="admin",
            permissions=[Permission("*")],
            description="Full system access"
        )
        self.add_role(admin)
        
        # Developer role - can create and modify flows
        developer = Role(
            name="developer",
            permissions=[
                Permission("flow:*"),
                Permission("agent:*"),
                Permission("tool:*"),
                Permission("memory:read"),
                Permission("memory:write"),
            ],
            inherits=[],
            description="Can create and modify flows and agents"
        )
        self.add_role(developer)
        
        # Executor role - can only run flows
        executor = Role(
            name="executor",
            permissions=[
                Permission("flow:read"),
                Permission("flow:execute"),
                Permission("agent:execute"),
            ],
            inherits=[],
            description="Can only execute existing flows"
        )
        self.add_role(executor)
        
        # Viewer role - read-only access
        viewer = Role(
            name="viewer",
            permissions=[
                Permission("flow:read"),
                Permission("agent:read"),
                Permission("tool:read"),
            ],
            inherits=[],
            description="Read-only access"
        )
        self.add_role(viewer)
    
    def add_role(self, role: Role) -> None:
        """Register a new role."""
        if role.name in self._roles:
            raise ValueError(f"Role '{role.name}' already exists")
        self._roles[role.name] = role
    
    def get_role(self, name: str) -> Optional[Role]:
        """Get a role by name."""
        return self._roles.get(name)
    
    def remove_role(self, name: str) -> bool:
        """Remove a role."""
        if name in self._roles:
            del self._roles[name]
            # Remove from user assignments
            for user_id in list(self._user_roles.keys()):
                if name in self._user_roles[user_id]:
                    self._user_roles[user_id].remove(name)
            return True
        return False
    
    def assign_role(self, user_id: str, role_name: str, tenant_id: Optional[str] = None) -> None:
        """Assign a role to a user."""
        if role_name not in self._roles:
            raise ValueError(f"Role '{role_name}' does not exist")
        
        if tenant_id:
            if tenant_id not in self._tenant_user_roles:
                self._tenant_user_roles[tenant_id] = {}
            if user_id not in self._tenant_user_roles[tenant_id]:
                self._tenant_user_roles[tenant_id][user_id] = []
            if role_name not in self._tenant_user_roles[tenant_id][user_id]:
                self._tenant_user_roles[tenant_id][user_id].append(role_name)
        else:
            if user_id not in self._user_roles:
                self._user_roles[user_id] = []
            if role_name not in self._user_roles[user_id]:
                self._user_roles[user_id].append(role_name)
    
    def revoke_role(self, user_id: str, role_name: str, tenant_id: Optional[str] = None) -> bool:
        """Revoke a role from a user."""
        if tenant_id:
            if tenant_id in self._tenant_user_roles and user_id in self._tenant_user_roles[tenant_id]:
                if role_name in self._tenant_user_roles[tenant_id][user_id]:
                    self._tenant_user_roles[tenant_id][user_id].remove(role_name)
                    return True
        else:
            if user_id in self._user_roles and role_name in self._user_roles[user_id]:
                self._user_roles[user_id].remove(role_name)
                return True
        return False
    
    def get_user_roles(self, user_id: str, tenant_id: Optional[str] = None) -> List[str]:
        """Get all roles assigned to a user."""
        if tenant_id and tenant_id in self._tenant_user_roles:
            return self._tenant_user_roles[tenant_id].get(user_id, [])
        return self._user_roles.get(user_id, [])
    
    def check_permission(
        self,
        user_id: str,
        permission_pattern: str,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        Check if a user has a specific permission.
        
        Args:
            user_id: The user identifier
            permission_pattern: Permission to check (e.g., "flow:read")
            tenant_id: Optional tenant ID for multi-tenancy
            
        Returns:
            True if the user has the permission, False otherwise
        """
        requested_perm = Permission(permission_pattern)
        roles = self.get_user_roles(user_id, tenant_id)
        
        # Collect all permissions from all roles (including inherited)
        all_permissions: Set[Permission] = set()
        for role_name in roles:
            role = self._roles.get(role_name)
            if role:
                all_permissions.update(role.get_all_permissions(self._roles))
        
        # Check if any permission matches
        for perm in all_permissions:
            if perm.matches(requested_perm):
                return True
        
        # Check custom validators
        context = UserContext(user_id=user_id, tenant_id=tenant_id, roles=roles)
        for validator_perm, validator_func in self._validators.items():
            if requested_perm.matches(Permission(validator_perm)):
                if validator_func(context, requested_perm):
                    return True
        
        return False
    
    def register_validator(
        self,
        permission_pattern: str,
        validator: Callable[[UserContext, Permission], bool]
    ) -> None:
        """
        Register a custom permission validator.
        
        Useful for dynamic permissions based on resource ownership, etc.
        """
        self._validators[permission_pattern] = validator
    
    def has_any_permission(
        self,
        user_id: str,
        permissions: List[str],
        tenant_id: Optional[str] = None
    ) -> bool:
        """Check if user has any of the specified permissions."""
        for perm in permissions:
            if self.check_permission(user_id, perm, tenant_id):
                return True
        return False
    
    def has_all_permissions(
        self,
        user_id: str,
        permissions: List[str],
        tenant_id: Optional[str] = None
    ) -> bool:
        """Check if user has all of the specified permissions."""
        for perm in permissions:
            if not self.check_permission(user_id, perm, tenant_id):
                return False
        return True
    
    def list_roles(self) -> List[Role]:
        """List all registered roles."""
        return list(self._roles.values())
    
    def clear(self) -> None:
        """Clear all roles and assignments (except defaults)."""
        self._roles.clear()
        self._user_roles.clear()
        self._tenant_user_roles.clear()
        self._validators.clear()
        self._create_default_roles()
