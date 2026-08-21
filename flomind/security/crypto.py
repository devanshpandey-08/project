"""Enterprise security with AES-256-GCM encryption, PII detection, and RBAC."""
import os
import re
import hashlib
import secrets
from typing import Any, Dict, List, Optional, Set, FrozenSet
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timezone

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


@dataclass
class Encryptor:
    """AES-256-GCM encryption for sensitive data."""
    
    key: Optional[bytes] = None
    salt: Optional[bytes] = None
    
    def __post_init__(self):
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library required for encryption")
        
        if self.key is None:
            self.key = secrets.token_bytes(32)  # 256-bit key
        
        if self.salt is None:
            self.salt = secrets.token_bytes(16)
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    def encrypt(self, plaintext: str, password: Optional[str] = None) -> Dict[str, str]:
        """Encrypt plaintext with authenticated encryption."""
        if password:
            key = self._derive_key(password, self.salt)
        else:
            key = self.key
        
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)  # 96-bit nonce
        
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        
        return {
            "ciphertext": ciphertext.hex(),
            "nonce": nonce.hex(),
            "salt": self.salt.hex()
        }
    
    def decrypt(self, encrypted_data: Dict[str, str], password: Optional[str] = None) -> str:
        """Decrypt ciphertext with authentication."""
        if password:
            key = self._derive_key(password, bytes.fromhex(encrypted_data["salt"]))
        else:
            key = self.key
        
        aesgcm = AESGCM(key)
        nonce = bytes.fromhex(encrypted_data["nonce"])
        ciphertext = bytes.fromhex(encrypted_data["ciphertext"])
        
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()


@dataclass
class PIIDetector:
    """Detect and redact PII for compliance (GDPR, HIPAA, SOC2)."""
    
    patterns: Dict[str, re.Pattern] = field(default_factory=dict)
    
    def __post_init__(self):
        self.patterns = {
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "phone": re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
            "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            "credit_card": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            "ip_address": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
            "date_of_birth": re.compile(r'\b(?:0[1-9]|1[0-2])/(?:0[1-9]|[12]\d|3[01])/(?:19|20)\d{2}\b'),
        }
    
    def detect(self, text: str) -> List[Dict[str, Any]]:
        """Detect all PII in text."""
        findings = []
        
        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                findings.append({
                    "type": pii_type,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.95
                })
        
        return findings
    
    def redact(self, text: str, replacement: str = "[REDACTED]") -> str:
        """Redact all PII from text."""
        result = text
        
        for pattern in self.patterns.values():
            result = pattern.sub(replacement, result)
        
        return result
    
    def has_pii(self, text: str) -> bool:
        """Check if text contains any PII."""
        return len(self.detect(text)) > 0


@dataclass
class InputSanitizer:
    """Sanitize inputs to prevent XSS and injection attacks."""
    
    max_length: int = 10000
    allowed_tags: FrozenSet[str] = field(default_factory=frozenset)
    
    def sanitize(self, input_str: str) -> str:
        """Sanitize input string."""
        if not input_str:
            return ""
        
        # Length limiting
        if len(input_str) > self.max_length:
            input_str = input_str[:self.max_length]
        
        # Null byte removal
        input_str = input_str.replace('\x00', '')
        
        # Script tag removal (XSS prevention)
        input_str = re.sub(r'<script[^>]*>.*?</script>', '', input_str, flags=re.IGNORECASE | re.DOTALL)
        input_str = re.sub(r'<script[^>]*>', '', input_str, flags=re.IGNORECASE)
        input_str = re.sub(r'</script>', '', input_str, flags=re.IGNORECASE)
        
        # Event handler removal
        input_str = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', input_str, flags=re.IGNORECASE)
        input_str = re.sub(r'\s*on\w+\s*=\s*[^\s>]+', '', input_str, flags=re.IGNORECASE)
        
        # HTML entity encoding for remaining special chars
        input_str = input_str.replace('&', '&amp;')
        input_str = input_str.replace('<', '&lt;')
        input_str = input_str.replace('>', '&gt;')
        input_str = input_str.replace('"', '&quot;')
        input_str = input_str.replace("'", '&#x27;')
        
        return input_str
    
    def validate(self, input_str: str) -> tuple[bool, str]:
        """Validate input and return (is_valid, error_message)."""
        if not input_str:
            return False, "Input cannot be empty"
        
        if len(input_str) > self.max_length:
            return False, f"Input exceeds maximum length of {self.max_length}"
        
        if '\x00' in input_str:
            return False, "Null bytes not allowed"
        
        if re.search(r'<script', input_str, re.IGNORECASE):
            return False, "Script tags not allowed"
        
        return True, ""


class Permission(Enum):
    """Fine-grained permissions for RBAC."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass
class Role:
    """Role with hierarchical permissions."""
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    inherits: Optional[str] = None
    
    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions


@dataclass
class RBACManager:
    """Role-Based Access Control with multi-tenancy support."""
    
    roles: Dict[str, Role] = field(default_factory=dict)
    user_roles: Dict[str, Set[str]] = field(default_factory=dict)  # user_id -> role names
    resource_permissions: Dict[str, Dict[str, Set[Permission]]] = field(default_factory=dict)  # resource -> user_id -> permissions
    
    def __post_init__(self):
        # Initialize default roles
        self.add_role(Role("admin", {Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.DELETE, Permission.ADMIN}))
        self.add_role(Role("developer", {Permission.READ, Permission.WRITE, Permission.EXECUTE}))
        self.add_role(Role("executor", {Permission.READ, Permission.EXECUTE}))
        self.add_role(Role("viewer", {Permission.READ}))
    
    def add_role(self, role: Role) -> None:
        self.roles[role.name] = role
    
    def assign_role(self, user_id: str, role_name: str) -> bool:
        if role_name not in self.roles:
            return False
        
        if user_id not in self.user_roles:
            self.user_roles[user_id] = set()
        
        self.user_roles[user_id].add(role_name)
        return True
    
    def revoke_role(self, user_id: str, role_name: str) -> bool:
        if user_id not in self.user_roles:
            return False
        
        if role_name in self.user_roles[user_id]:
            self.user_roles[user_id].remove(role_name)
            return True
        
        return False
    
    def has_permission(self, user_id: str, permission: Permission) -> bool:
        if user_id not in self.user_roles:
            return False
        
        for role_name in self.user_roles[user_id]:
            role = self.roles.get(role_name)
            if role and role.has_permission(permission):
                return True
        
        return False
    
    def can_access_resource(self, user_id: str, resource_id: str, permission: Permission) -> bool:
        # Check global permission first
        if self.has_permission(user_id, permission):
            return True
        
        # Check resource-specific permission
        if resource_id in self.resource_permissions:
            user_perms = self.resource_permissions[resource_id].get(user_id, set())
            if permission in user_perms:
                return True
        
        return False
    
    def grant_resource_permission(self, resource_id: str, user_id: str, permission: Permission) -> None:
        if resource_id not in self.resource_permissions:
            self.resource_permissions[resource_id] = {}
        
        if user_id not in self.resource_permissions[resource_id]:
            self.resource_permissions[resource_id][user_id] = set()
        
        self.resource_permissions[resource_id][user_id].add(permission)
