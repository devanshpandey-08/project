"""AES-256-GCM encryption for sensitive data."""

import os
import base64
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


class Encryptor:
    """
    Enterprise-grade encryption using AES-256-GCM.
    
    Features:
    - Authenticated encryption (AEAD)
    - Secure key derivation (PBKDF2)
    - Random IV generation
    - Base64 encoding for storage
    
    Usage:
        encryptor = Encryptor(secret_key="my-secret-key")
        encrypted = encryptor.encrypt("sensitive data")
        decrypted = encryptor.decrypt(encrypted)
    """
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        key_bytes: Optional[bytes] = None,
        salt: Optional[bytes] = None,
        iterations: int = 100000,
    ):
        """
        Initialize encryptor with a secret key.
        
        Args:
            secret_key: String secret key (will be derived to 256-bit key)
            key_bytes: Raw 32-byte key (alternative to secret_key)
            salt: Salt for key derivation (random if not provided)
            iterations: PBKDF2 iterations
        """
        self.iterations = iterations
        
        if key_bytes:
            if len(key_bytes) != 32:
                raise ValueError("key_bytes must be 32 bytes for AES-256")
            self.key = key_bytes
            self.salt = salt or os.urandom(16)
        elif secret_key:
            self.salt = salt or os.urandom(16)
            self.key = self._derive_key(secret_key, self.salt, iterations)
        else:
            # Generate random key (not recommended for production)
            self.key = os.urandom(32)
            self.salt = os.urandom(16)
        
        self.aesgcm = AESGCM(self.key)
    
    def _derive_key(self, password: str, salt: bytes, iterations: int) -> bytes:
        """Derive a 256-bit key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
            backend=default_backend(),
        )
        return kdf.derive(password.encode())
    
    def encrypt(self, plaintext: str, associated_data: Optional[bytes] = None) -> str:
        """
        Encrypt plaintext string.
        
        Args:
            plaintext: The text to encrypt
            associated_data: Optional authenticated data (not encrypted but authenticated)
        
        Returns:
            Base64-encoded ciphertext (salt + iv + ciphertext + tag)
        """
        iv = os.urandom(12)  # 96-bit IV for GCM
        plaintext_bytes = plaintext.encode('utf-8')
        
        ciphertext = self.aesgcm.encrypt(iv, plaintext_bytes, associated_data)
        
        # Combine salt + iv + ciphertext for storage
        # Format: salt (16) + iv (12) + ciphertext + tag (16)
        combined = self.salt + iv + ciphertext
        
        return base64.b64encode(combined).decode('ascii')
    
    def decrypt(self, ciphertext_b64: str, associated_data: Optional[bytes] = None) -> str:
        """
        Decrypt ciphertext.
        
        Args:
            ciphertext_b64: Base64-encoded ciphertext
            associated_data: Same associated data used during encryption
        
        Returns:
            Decrypted plaintext string
        
        Raises:
            ValueError: If decryption fails (wrong key or tampered data)
        """
        try:
            combined = base64.b64decode(ciphertext_b64.encode('ascii'))
            
            # Extract components
            salt = combined[:16]
            iv = combined[16:28]
            ciphertext_with_tag = combined[28:]
            
            # Verify salt matches
            if salt != self.salt:
                raise ValueError("Salt mismatch - wrong key or corrupted data")
            
            plaintext_bytes = self.aesgcm.decrypt(iv, ciphertext_with_tag, associated_data)
            
            return plaintext_bytes.decode('utf-8')
            
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
    
    def encrypt_bytes(self, data: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Encrypt raw bytes."""
        iv = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(iv, data, associated_data)
        return self.salt + iv + ciphertext
    
    def decrypt_bytes(self, data: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Decrypt raw bytes."""
        salt = data[:16]
        iv = data[16:28]
        ciphertext = data[28:]
        
        if salt != self.salt:
            raise ValueError("Salt mismatch")
        
        return self.aesgcm.decrypt(iv, ciphertext, associated_data)
    
    def get_key_info(self) -> dict:
        """Get information about the current key configuration."""
        return {
            "key_length": len(self.key) * 8,  # bits
            "salt_length": len(self.salt),
            "iterations": self.iterations,
            "algorithm": "AES-256-GCM",
        }
    
    @classmethod
    def from_base64_key(cls, key_b64: str) -> "Encryptor":
        """Create encryptor from base64-encoded key."""
        key_bytes = base64.b64decode(key_b64)
        return cls(key_bytes=key_bytes)
    
    def to_base64_key(self) -> str:
        """Export key as base64 string."""
        return base64.b64encode(self.key).decode('ascii')
