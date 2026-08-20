"""Enterprise-grade AES-256-GCM encryption for FlowMind."""

import os
import base64
import hashlib
from typing import Optional, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


class Encryptor:
    """
    AES-256-GCM authenticated encryption.
    
    Features:
    - 256-bit encryption keys
    - Authenticated encryption (GCM mode)
    - Key derivation from passwords
    - Secure random IV generation
    - Base64 encoding for storage
    """
    
    def __init__(self, key: Optional[bytes] = None, password: Optional[str] = None):
        """
        Initialize encryptor with key or password.
        
        Args:
            key: Raw 32-byte encryption key
            password: Password to derive key from (uses PBKDF2)
        """
        if key and password:
            raise ValueError("Provide either key or password, not both")
            
        if password:
            self.key = self._derive_key(password)
        elif key:
            if len(key) != 32:
                raise ValueError("Key must be 32 bytes for AES-256")
            self.key = key
        else:
            # Generate random key
            self.key = os.urandom(32)
            
        self.aesgcm = AESGCM(self.key)
        
    def _derive_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        if salt is None:
            salt = os.urandom(16)
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode())
        return key
        
    def encrypt(self, plaintext: Union[str, bytes], associated_data: Optional[bytes] = None) -> str:
        """
        Encrypt data using AES-256-GCM.
        
        Args:
            plaintext: Data to encrypt
            associated_data: Additional authenticated data (optional)
            
        Returns:
            Base64-encoded ciphertext (IV + ciphertext + tag)
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
            
        # Generate random 12-byte IV
        iv = os.urandom(12)
        
        # Encrypt
        ciphertext = self.aesgcm.encrypt(iv, plaintext, associated_data)
        
        # Combine IV + ciphertext (tag is included in ciphertext)
        encrypted_data = iv + ciphertext
        
        return base64.b64encode(encrypted_data).decode('utf-8')
        
    def decrypt(self, ciphertext_b64: str, associated_data: Optional[bytes] = None) -> str:
        """
        Decrypt data using AES-256-GCM.
        
        Args:
            ciphertext_b64: Base64-encoded ciphertext
            associated_data: Additional authenticated data (must match encryption)
            
        Returns:
            Decrypted plaintext string
        """
        try:
            encrypted_data = base64.b64decode(ciphertext_b64)
            
            # Extract IV and ciphertext
            iv = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            # Decrypt
            plaintext = self.aesgcm.decrypt(iv, ciphertext, associated_data)
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
            
    def encrypt_dict(self, data: dict, associated_data: Optional[bytes] = None) -> str:
        """Encrypt a dictionary as JSON."""
        import json
        plaintext = json.dumps(data, sort_keys=True)
        return self.encrypt(plaintext, associated_data)
        
    def decrypt_dict(self, ciphertext_b64: str, associated_data: Optional[bytes] = None) -> dict:
        """Decrypt to a dictionary."""
        import json
        plaintext = self.decrypt(ciphertext_b64, associated_data)
        return json.loads(plaintext)
        
    def get_key_hex(self) -> str:
        """Get key as hex string for storage."""
        return self.key.hex()
        
    @classmethod
    def from_hex_key(cls, hex_key: str) -> 'Encryptor':
        """Create encryptor from hex-encoded key."""
        key = bytes.fromhex(hex_key)
        return cls(key=key)
