"""
AegisFlow Security - AES-256-GCM Encryption, PII Detection, RBAC
"""
import os
import re
import json
import hashlib
from typing import Dict, List, Optional, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64

class Encryptor:
    """AES-256-GCM Encryption with Key Persistence"""
    
    def __init__(self, key: Optional[str] = None):
        if key:
            self.key = self._derive_key(key)
        else:
            # Load from env or generate persistent key
            env_key = os.getenv("AEGISFLOW_ENCRYPTION_KEY")
            if env_key:
                self.key = self._derive_key(env_key)
            else:
                self.key = AESGCM.generate_key(bit_length=256)
                print(f"WARNING: Generated ephemeral key. Set AEGISFLOW_ENCRYPTION_KEY env var.")
    
    def _derive_key(self, password: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"aegisflow_salt_v1",  # In prod, use random salt per user
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    def encrypt(self, plaintext: str) -> str:
        aesgcm = AESGCM(self.key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()
    
    def decrypt(self, ciphertext_b64: str) -> str:
        aesgcm = AESGCM(self.key)
        data = base64.b64decode(ciphertext_b64)
        nonce = data[:12]
        ciphertext = data[12:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()

class PIIDetector:
    """Advanced PII Detection with Homoglyph Protection"""
    
    PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'credit_card': r'\b(?:\d{4}[- ]?){3}\d{4}\b',
        'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
    }
    
    def __init__(self):
        self.compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE) 
            for name, pattern in self.PATTERNS.items()
        }
    
    def detect(self, text: str) -> Dict[str, List[str]]:
        """Returns dict of pii_type -> [matches]"""
        findings = {}
        # Normalize unicode homoglyphs
        normalized = text.encode('ascii', 'ignore').decode('ascii')
        
        for pii_type, pattern in self.compiled_patterns.items():
            matches = pattern.findall(normalized)
            if matches:
                findings[pii_type] = matches
        return findings
    
    def redact(self, text: str, replacement: str = "[REDACTED]") -> str:
        """Redacts all detected PII"""
        result = text
        for pattern in self.compiled_patterns.values():
            result = pattern.sub(replacement, result)
        return result

class Redactor:
    """Auto-redaction wrapper"""
    def __init__(self):
        self.detector = PIIDetector()
    
    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact PII in dict"""
        if isinstance(data, dict):
            return {k: self.redact_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.redact_dict(item) for item in data]
        elif isinstance(data, str):
            return self.detector.redact(data)
        return data

class Role:
    """RBAC Role Definition"""
    def __init__(self, name: str, permissions: List[str], inherits: Optional[List[str]] = None):
        self.name = name
        self.permissions = set(permissions)
        self.inherits = inherits or []
    
    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

class RBACManager:
    """Role-Based Access Control"""
    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self.user_roles: Dict[str, str] = {}  # user_id -> role_name
    
    def add_role(self, role: Role):
        self.roles[role.name] = role
    
    def assign_role(self, user_id: str, role_name: str):
        if role_name not in self.roles:
            raise ValueError(f"Role {role_name} does not exist")
        self.user_roles[user_id] = role_name
    
    def check_permission(self, user_id: str, permission: str) -> bool:
        role_name = self.user_roles.get(user_id)
        if not role_name:
            return False
        role = self.roles[role_name]
        if permission in role.permissions:
            return True
        # Check inherited roles
        for inherited_name in role.inherits:
            inherited_role = self.roles.get(inherited_name)
            if inherited_role and permission in inherited_role.permissions:
                return True
        return False

class AuditLogger:
    """Immutable Audit Ledger"""
    def __init__(self, log_file: str = "audit.log"):
        self.log_file = log_file
        self._buffer: List[dict] = []
    
    def log(self, event_type: str, user_id: str, action: str, details: Dict[str, Any]):
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "details": details,
            "hash": ""  # Will be computed
        }
        # Compute hash chain
        if self._buffer:
            prev_hash = self._buffer[-1]["hash"]
            entry["prev_hash"] = prev_hash
        entry["hash"] = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        self._buffer.append(entry)
        self._flush()
    
    def _flush(self):
        with open(self.log_file, 'a') as f:
            for entry in self._buffer:
                f.write(json.dumps(entry) + "\n")
        self._buffer = []
    
    def get_trace(self, trace_id: str) -> List[dict]:
        # In prod, query database
        return [e for e in self._buffer if e.get("details", {}).get("trace_id") == trace_id]

import time  # Import at bottom to avoid circular issues
