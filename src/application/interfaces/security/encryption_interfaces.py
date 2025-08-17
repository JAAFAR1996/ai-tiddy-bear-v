"""
Encryption Interfaces for Child Data Protection
==============================================

This module defines encryption interfaces for protecting child data
in the AI Teddy Bear system with COPPA compliance.

Note: All implementations are in src.core.security_service
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass


class EncryptionStrength(Enum):
    """Encryption strength levels for different data types."""
    STANDARD = "standard"  # For general child data
    HIGH = "high"         # For sensitive PII
    MAXIMUM = "maximum"   # For highly sensitive data


class DataClassification(Enum):
    """Classification of child data for appropriate encryption."""
    PUBLIC = "public"           # Non-sensitive data
    INTERNAL = "internal"       # App-internal data
    CONFIDENTIAL = "confidential"  # Child preferences, settings
    PII = "pii"                # Personally identifiable information
    SENSITIVE_PII = "sensitive_pii"  # Highly sensitive child data


@dataclass
class EncryptionResult:
    """Result of encryption operation."""
    encrypted_data: bytes
    encryption_method: str
    key_id: str
    data_classification: DataClassification
    created_at: float
    metadata: Dict[str, Any]


@dataclass
class DecryptionResult:
    """Result of decryption operation."""
    decrypted_data: Union[str, bytes, Dict[str, Any]]
    original_classification: DataClassification
    decrypted_at: float
    metadata: Dict[str, Any]


# ============================================================================
# CHILD DATA ENCRYPTION SERVICE
# ============================================================================

class IChildDataEncryption(ABC):
    """
    Practical encryption service for protecting child data.
    
    This service provides simple, reliable encryption specifically designed
    for child data protection and COPPA compliance. It focuses on real-world
    use cases rather than theoretical cryptographic operations.
    
    Use Cases:
    - Encrypting child names and personal information
    - Protecting conversation history
    - Securing child preferences and settings
    - Anonymizing child data for analytics
    
    COPPA Compliance:
    - Automatic classification of child data
    - Secure key management for child data
    - Audit logging for all encryption operations
    - Support for data deletion requirements
    """
    
    @abstractmethod
    async def encrypt_child_pii(
        self,
        child_id: str,
        pii_data: Dict[str, Any],
        classification: DataClassification = DataClassification.PII
    ) -> EncryptionResult:
        """Encrypt child personally identifiable information."""
        pass
    
    @abstractmethod
    async def decrypt_child_pii(
        self,
        child_id: str,
        encryption_result: EncryptionResult
    ) -> DecryptionResult:
        """Decrypt child personally identifiable information."""
        pass
    
    @abstractmethod
    async def encrypt_conversation_history(
        self,
        child_id: str,
        messages: List[Dict[str, Any]]
    ) -> EncryptionResult:
        """Encrypt child conversation history for storage."""
        pass
    
    @abstractmethod
    async def decrypt_conversation_history(
        self,
        child_id: str,
        encryption_result: EncryptionResult
    ) -> List[Dict[str, Any]]:
        """Decrypt child conversation history."""
        pass
    
    @abstractmethod
    async def encrypt_child_preferences(
        self,
        child_id: str,
        preferences: Dict[str, Any]
    ) -> EncryptionResult:
        """Encrypt child preferences and settings."""
        pass
    
    @abstractmethod
    async def anonymize_child_data(
        self,
        child_data: Dict[str, Any],
        anonymization_level: str = "standard"
    ) -> Dict[str, Any]:
        """Anonymize child data for analytics and reporting."""
        pass


# ============================================================================
# FIELD-LEVEL ENCRYPTION SERVICE
# ============================================================================

class IFieldLevelEncryption(ABC):
    """Field-level encryption for selective data protection."""
    
    @abstractmethod
    async def encrypt_fields(
        self,
        data: Dict[str, Any],
        fields_to_encrypt: List[str],
        child_id: str
    ) -> Dict[str, Any]:
        """Encrypt specific fields in a data dictionary."""
        pass
    
    @abstractmethod
    async def decrypt_fields(
        self,
        encrypted_data: Dict[str, Any],
        fields_to_decrypt: List[str],
        child_id: str
    ) -> Dict[str, Any]:
        """Decrypt specific fields in an encrypted data dictionary."""
        pass
    
    @abstractmethod
    async def is_field_encrypted(
        self,
        data: Dict[str, Any],
        field_name: str
    ) -> bool:
        """Check if a specific field is encrypted."""
        pass


# ============================================================================
# SECURE STORAGE ENCRYPTION
# ============================================================================

class ISecureStorageEncryption(ABC):
    """Encryption service for secure storage of child data."""
    
    @abstractmethod
    async def encrypt_for_storage(
        self,
        data: Union[str, bytes, Dict[str, Any]],
        storage_type: str,
        child_id: Optional[str] = None
    ) -> EncryptionResult:
        """Encrypt data for secure storage."""
        pass
    
    @abstractmethod
    async def decrypt_from_storage(
        self,
        encryption_result: EncryptionResult,
        child_id: Optional[str] = None
    ) -> DecryptionResult:
        """Decrypt data retrieved from storage."""
        pass
    
    @abstractmethod
    async def rotate_encryption_keys(
        self,
        child_id: str,
        backup_old_keys: bool = True
    ) -> bool:
        """Rotate encryption keys for a child's data."""
        pass


# ============================================================================
# ENCRYPTION KEY MANAGEMENT
# ============================================================================

class IEncryptionKeyManager(ABC):
    """Key management service for child data encryption."""
    
    @abstractmethod
    async def generate_child_keys(
        self,
        child_id: str,
        key_strength: EncryptionStrength = EncryptionStrength.HIGH
    ) -> Dict[str, str]:
        """Generate encryption keys for a child's data."""
        pass
    
    @abstractmethod
    async def get_child_key(
        self,
        child_id: str,
        key_type: str
    ) -> Optional[str]:
        """Retrieve encryption key for child data."""
        pass
    
    @abstractmethod
    async def delete_child_keys(
        self,
        child_id: str,
        secure_deletion: bool = True
    ) -> bool:
        """Delete all encryption keys for a child (COPPA compliance)."""
        pass
    
    @abstractmethod
    async def backup_child_keys(
        self,
        child_id: str,
        backup_location: str
    ) -> str:
        """Create secure backup of child's encryption keys."""
        pass


# Export practical encryption interfaces
__all__ = [
    # Enums
    "EncryptionStrength",
    "DataClassification",
    
    # Data Classes
    "EncryptionResult",
    "DecryptionResult",
    
    # Core Interfaces
    "IChildDataEncryption",
    "IFieldLevelEncryption", 
    "ISecureStorageEncryption",
    "IEncryptionKeyManager",
]
