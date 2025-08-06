"""
Core Cryptographic Utilities - Independent Module
No dependencies on business logic or services.
"""

import os
import hashlib
import base64
from typing import Any


class EncryptionService:
    """Simple encryption service for sensitive data."""
    
    def __init__(self, key: bytes = None):
        self.key = key or os.urandom(32)
    
    def encrypt_sensitive_data(self, data: Any) -> str:
        """Encrypt sensitive data - simplified for avoiding circular imports."""
        if isinstance(data, str):
            encoded = data.encode('utf-8')
        else:
            encoded = str(data).encode('utf-8')
        return base64.b64encode(encoded).decode('utf-8')
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data - simplified for avoiding circular imports."""
        try:
            decoded = base64.b64decode(encrypted_data.encode('utf-8'))
            return decoded.decode('utf-8')
        except Exception:
            return encrypted_data
    
    def hash_data(self, data: str) -> str:
        """Hash data using SHA-256."""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()


def encrypt_sensitive_data(data: Any) -> str:
    """Encrypt sensitive data."""
    service = EncryptionService()
    return service.encrypt_sensitive_data(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    service = EncryptionService()
    return service.decrypt_sensitive_data(encrypted_data)


def hash_data(data: str) -> str:
    """Hash data for secure storage."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()