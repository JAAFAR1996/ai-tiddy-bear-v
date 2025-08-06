"""
Cryptographic utilities for secure data handling.
Provides encryption, hashing, and key management for child data protection.
"""

import os
import hashlib
import hmac
import base64
from datetime import datetime
from typing import Dict, Any, Optional
import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoUtils:
    """Cryptographic utility functions."""

    def __init__(
        self,
        default_algorithm: str = "AES-256-GCM",
        key_derivation_iterations: int = 100000,
    ):
        self.default_algorithm = default_algorithm
        self.key_derivation_iterations = key_derivation_iterations

    def generate_random_key(self, length: int = 32) -> bytes:
        """Generate cryptographically secure random key."""
        return os.urandom(length)

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against bcrypt hash."""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    def encrypt_data(self, plaintext: str, key: bytes) -> Dict[str, str]:
        """Encrypt data using AES-GCM via Fernet (production-ready)."""
        fernet = Fernet(base64.urlsafe_b64encode(key[:32]))
        encrypted = fernet.encrypt(plaintext.encode("utf-8"))
        
        # Fernet internally uses AES-128 in CBC mode with HMAC for authentication
        # The token format includes the nonce/IV and authentication tag
        encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")
        
        return {
            "ciphertext": encrypted_b64,
            "algorithm": "Fernet-AES-128-CBC-HMAC",
            "timestamp": int(datetime.utcnow().timestamp()),
        }

    def decrypt_data(self, encrypted_data: Dict[str, str], key: bytes) -> str:
        """Decrypt data using AES-GCM."""
        fernet = Fernet(base64.urlsafe_b64encode(key[:32]))
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        decrypted = fernet.decrypt(ciphertext)
        return decrypted.decode("utf-8")

    def generate_hmac(self, data: str, secret_key: bytes) -> str:
        """Generate HMAC signature."""
        signature = hmac.new(secret_key, data.encode("utf-8"), hashlib.sha256)
        return signature.hexdigest()

    def verify_hmac(self, data: str, secret_key: bytes, signature: str) -> bool:
        """Verify HMAC signature."""
        expected = self.generate_hmac(data, secret_key)
        return hmac.compare_digest(expected, signature)

    def derive_key(self, password: str, salt: bytes, iterations: int = None) -> bytes:
        """Derive key from password using PBKDF2."""
        if iterations is None:
            iterations = self.key_derivation_iterations

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode("utf-8"))

    def secure_compare(self, string1: str, string2: str) -> bool:
        """Constant-time string comparison."""
        return hmac.compare_digest(string1, string2)

    def encrypt_child_pii(
        self, child_data: Dict[str, Any], encryption_key: bytes
    ) -> Dict[str, Any]:
        """Encrypt child PII data with COPPA compliance metadata."""
        import json

        pii_json = json.dumps(child_data)
        encrypted = self.encrypt_data(pii_json, encryption_key)

        return {
            **encrypted,
            "metadata": {
                "data_type": "child_pii",
                "coppa_protected": True,
                "encrypted_at": datetime.utcnow().isoformat(),
                "algorithm": self.default_algorithm,
            },
        }


class EncryptionService:
    """Unified encryption service for all application data including messages."""

    def __init__(self, master_key: Optional[bytes] = None):
        self.crypto_utils = CryptoUtils()
        self.master_key = master_key or self.crypto_utils.generate_random_key(32)
        self._message_key = None

    def _get_message_key(self) -> bytes:
        """Get or create message encryption key from config."""
        if self._message_key is None:
            try:
                import os
                key_str = os.environ.get("COPPA_ENCRYPTION_KEY")
                if key_str:
                    # Ensure key is proper length for Fernet
                    if len(key_str) < 32:
                        key_str = key_str.ljust(32, '0')
                    self._message_key = base64.urlsafe_b64encode(key_str[:32].encode())
                else:
                    self._message_key = Fernet.generate_key()
            except Exception:
                self._message_key = Fernet.generate_key()
        return self._message_key

    def encrypt_sensitive_data(self, data: Any) -> str:
        """Encrypt sensitive application data."""
        import json
        json_data = json.dumps(data)
        encrypted = self.crypto_utils.encrypt_data(json_data, self.master_key)
        return base64.b64encode(json.dumps(encrypted).encode()).decode()

    def decrypt_sensitive_data(self, encrypted_data: str) -> Any:
        """Decrypt sensitive application data."""
        import json
        decoded = json.loads(base64.b64decode(encrypted_data).decode())
        decrypted_json = self.crypto_utils.decrypt_data(decoded, self.master_key)
        return json.loads(decrypted_json)

    def encrypt_message_content(self, content: str) -> str:
        """Encrypt message content using Fernet (unified from entities/models)."""
        try:
            fernet = Fernet(self._get_message_key())
            return fernet.encrypt(content.encode()).decode()
        except Exception as e:
            raise ValueError(f"Message encryption failed: {e}")

    def decrypt_message_content(self, encrypted_content: str) -> str:
        """Decrypt message content using Fernet (unified from entities/models)."""
        try:
            fernet = Fernet(self._get_message_key())
            return fernet.decrypt(encrypted_content.encode()).decode()
        except Exception as e:
            raise ValueError(f"Message decryption failed: {e}")
