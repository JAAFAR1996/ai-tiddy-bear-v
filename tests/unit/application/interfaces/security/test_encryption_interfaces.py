"""
Tests for Encryption Interfaces - Child Data Protection
======================================================

Critical security tests for child data encryption interfaces.
These tests ensure COPPA compliance and data protection.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.application.interfaces.security.encryption_interfaces import (
    IChildDataEncryption,
    IFieldLevelEncryption,
    ISecureStorageEncryption,
    IEncryptionKeyManager,
    EncryptionStrength,
    DataClassification,
    EncryptionResult,
    DecryptionResult
)


class TestEncryptionInterfaces:
    """Test encryption interface contracts."""

    def test_encryption_strength_enum(self):
        """Test encryption strength levels."""
        assert EncryptionStrength.STANDARD.value == "standard"
        assert EncryptionStrength.HIGH.value == "high"
        assert EncryptionStrength.MAXIMUM.value == "maximum"

    def test_data_classification_enum(self):
        """Test data classification levels."""
        assert DataClassification.PUBLIC.value == "public"
        assert DataClassification.PII.value == "pii"
        assert DataClassification.SENSITIVE_PII.value == "sensitive_pii"

    def test_encryption_result_structure(self):
        """Test encryption result data structure."""
        result = EncryptionResult(
            encrypted_data=b"encrypted",
            encryption_method="AES-256",
            key_id="key123",
            data_classification=DataClassification.PII,
            created_at=1234567890.0,
            metadata={"test": "data"}
        )
        
        assert result.encrypted_data == b"encrypted"
        assert result.encryption_method == "AES-256"
        assert result.key_id == "key123"
        assert result.data_classification == DataClassification.PII
        assert result.created_at == 1234567890.0
        assert result.metadata == {"test": "data"}


class TestIChildDataEncryption:
    """Test child data encryption interface."""

    @pytest.fixture
    def mock_encryption_service(self):
        """Create mock encryption service."""
        service = Mock(spec=IChildDataEncryption)
        service.encrypt_child_pii = AsyncMock()
        service.decrypt_child_pii = AsyncMock()
        service.encrypt_conversation_history = AsyncMock()
        service.decrypt_conversation_history = AsyncMock()
        service.encrypt_child_preferences = AsyncMock()
        service.anonymize_child_data = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_encrypt_child_pii_interface(self, mock_encryption_service):
        """Test child PII encryption interface."""
        child_id = "child123"
        pii_data = {"name": "Test Child", "age": 8}
        expected_result = EncryptionResult(
            encrypted_data=b"encrypted_pii",
            encryption_method="AES-256",
            key_id="key123",
            data_classification=DataClassification.PII,
            created_at=datetime.now().timestamp(),
            metadata={"child_id": child_id}
        )
        mock_encryption_service.encrypt_child_pii.return_value = expected_result
        
        result = await mock_encryption_service.encrypt_child_pii(
            child_id, pii_data, DataClassification.PII
        )
        
        mock_encryption_service.encrypt_child_pii.assert_called_once_with(
            child_id, pii_data, DataClassification.PII
        )
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_anonymize_child_data_interface(self, mock_encryption_service):
        """Test child data anonymization interface."""
        child_data = {
            "name": "Test Child",
            "age": 8,
            "preferences": ["stories", "games"]
        }
        expected_result = {
            "name": "Child_ABC123",
            "age_group": "6-9",
            "preferences": ["stories", "games"]
        }
        mock_encryption_service.anonymize_child_data.return_value = expected_result
        
        result = await mock_encryption_service.anonymize_child_data(
            child_data, "standard"
        )
        
        mock_encryption_service.anonymize_child_data.assert_called_once_with(
            child_data, "standard"
        )
        assert result == expected_result


class TestIEncryptionKeyManager:
    """Test encryption key management interface."""

    @pytest.fixture
    def mock_key_manager(self):
        """Create mock key manager service."""
        service = Mock(spec=IEncryptionKeyManager)
        service.generate_child_keys = AsyncMock()
        service.get_child_key = AsyncMock()
        service.delete_child_keys = AsyncMock()
        service.backup_child_keys = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_generate_child_keys_interface(self, mock_key_manager):
        """Test child key generation interface."""
        child_id = "child123"
        expected_keys = {
            "encryption_key": "key123",
            "signing_key": "sign456",
            "backup_key": "backup789"
        }
        mock_key_manager.generate_child_keys.return_value = expected_keys
        
        result = await mock_key_manager.generate_child_keys(
            child_id, EncryptionStrength.HIGH
        )
        
        mock_key_manager.generate_child_keys.assert_called_once_with(
            child_id, EncryptionStrength.HIGH
        )
        assert result == expected_keys

    @pytest.mark.asyncio
    async def test_delete_child_keys_interface(self, mock_key_manager):
        """Test child key deletion interface (COPPA compliance)."""
        child_id = "child123"
        mock_key_manager.delete_child_keys.return_value = True
        
        result = await mock_key_manager.delete_child_keys(
            child_id, secure_deletion=True
        )
        
        mock_key_manager.delete_child_keys.assert_called_once_with(
            child_id, secure_deletion=True
        )
        assert result is True