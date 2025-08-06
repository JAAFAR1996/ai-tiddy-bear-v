"""
Unit tests for consent models.
Tests COPPA consent tracking, enum validation, and consent lifecycle.
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
import uuid

from src.shared.dto.consent_models import (
    ConsentType, ConsentStatus, ConsentRecord
)


class TestConsentEnums:
    """Test consent enumeration types."""

    def test_consent_type_values(self):
        """Test ConsentType enum values."""
        assert ConsentType.DATA_COLLECTION == "data_collection"
        assert ConsentType.VOICE_RECORDING == "voice_recording"
        assert ConsentType.MARKETING_EMAILS == "marketing_emails"
        
        # Test all enum members exist
        expected_types = {"data_collection", "voice_recording", "marketing_emails"}
        actual_types = {member.value for member in ConsentType}
        assert actual_types == expected_types

    def test_consent_status_values(self):
        """Test ConsentStatus enum values."""
        assert ConsentStatus.PENDING == "pending"
        assert ConsentStatus.GRANTED == "granted"
        assert ConsentStatus.REVOKED == "revoked"
        assert ConsentStatus.EXPIRED == "expired"
        
        # Test all enum members exist
        expected_statuses = {"pending", "granted", "revoked", "expired"}
        actual_statuses = {member.value for member in ConsentStatus}
        assert actual_statuses == expected_statuses

    def test_enum_string_inheritance(self):
        """Test that enums inherit from str for JSON serialization."""
        assert isinstance(ConsentType.DATA_COLLECTION, str)
        assert isinstance(ConsentStatus.PENDING, str)


class TestConsentRecordCreation:
    """Test ConsentRecord creation and validation."""

    def test_create_minimal_consent_record(self):
        """Test creating consent record with minimal required fields."""
        record = ConsentRecord(
            child_id="child-123",
            parent_id="parent-456",
            consent_type=ConsentType.DATA_COLLECTION
        )
        
        assert record.child_id == "child-123"
        assert record.parent_id == "parent-456"
        assert record.consent_type == ConsentType.DATA_COLLECTION
        assert record.status == ConsentStatus.PENDING  # Default
        assert record.version == "1.0"  # Default
        assert record.id is not None
        assert len(record.id) == 36  # UUID4 length
        
        # Optional fields should be None
        assert record.granted_at is None
        assert record.revoked_at is None
        assert record.expires_at is None

    def test_create_complete_consent_record(self):
        """Test creating consent record with all fields."""
        consent_id = str(uuid.uuid4())
        granted_time = datetime.now()
        expires_time = granted_time + timedelta(days=365)
        
        record = ConsentRecord(
            id=consent_id,
            child_id="child-789",
            parent_id="parent-012",
            consent_type=ConsentType.VOICE_RECORDING,
            status=ConsentStatus.GRANTED,
            granted_at=granted_time,
            expires_at=expires_time,
            version="2.0"
        )
        
        assert record.id == consent_id
        assert record.child_id == "child-789"
        assert record.parent_id == "parent-012"
        assert record.consent_type == ConsentType.VOICE_RECORDING
        assert record.status == ConsentStatus.GRANTED
        assert record.granted_at == granted_time
        assert record.expires_at == expires_time
        assert record.version == "2.0"

    def test_auto_generated_id(self):
        """Test that ID is auto-generated if not provided."""
        record1 = ConsentRecord(
            child_id="child-1",
            parent_id="parent-1",
            consent_type=ConsentType.DATA_COLLECTION
        )
        
        record2 = ConsentRecord(
            child_id="child-2",
            parent_id="parent-2",
            consent_type=ConsentType.DATA_COLLECTION
        )
        
        # IDs should be different
        assert record1.id != record2.id
        # Both should be valid UUIDs
        uuid.UUID(record1.id)  # Should not raise
        uuid.UUID(record2.id)  # Should not raise


class TestConsentTypeValidation:
    """Test consent type validation."""

    def test_valid_consent_types(self):
        """Test all valid consent types are accepted."""
        for consent_type in ConsentType:
            record = ConsentRecord(
                child_id="child-test",
                parent_id="parent-test",
                consent_type=consent_type
            )
            assert record.consent_type == consent_type

    def test_string_consent_type_accepted(self):
        """Test string values for consent types are accepted."""
        record = ConsentRecord(
            child_id="child-test",
            parent_id="parent-test",
            consent_type="data_collection"  # String instead of enum
        )
        assert record.consent_type == ConsentType.DATA_COLLECTION

    def test_invalid_consent_type_rejected(self):
        """Test invalid consent types are rejected."""
        with pytest.raises(ValidationError):
            ConsentRecord(
                child_id="child-test",
                parent_id="parent-test",
                consent_type="invalid_type"
            )


class TestConsentStatusValidation:
    """Test consent status validation."""

    def test_valid_consent_statuses(self):
        """Test all valid consent statuses are accepted."""
        for status in ConsentStatus:
            record = ConsentRecord(
                child_id="child-test",
                parent_id="parent-test",
                consent_type=ConsentType.DATA_COLLECTION,
                status=status
            )
            assert record.status == status

    def test_string_consent_status_accepted(self):
        """Test string values for consent status are accepted."""
        record = ConsentRecord(
            child_id="child-test",
            parent_id="parent-test",
            consent_type=ConsentType.DATA_COLLECTION,
            status="granted"  # String instead of enum
        )
        assert record.status == ConsentStatus.GRANTED

    def test_invalid_consent_status_rejected(self):
        """Test invalid consent statuses are rejected."""
        with pytest.raises(ValidationError):
            ConsentRecord(
                child_id="child-test",
                parent_id="parent-test",
                consent_type=ConsentType.DATA_COLLECTION,
                status="invalid_status"
            )


class TestConsentRecordFieldValidation:
    """Test field validation for ConsentRecord."""

    def test_required_fields_validation(self):
        """Test required fields must be provided."""
        # Missing child_id
        with pytest.raises(ValidationError):
            ConsentRecord(
                parent_id="parent-test",
                consent_type=ConsentType.DATA_COLLECTION
            )
        
        # Missing parent_id
        with pytest.raises(ValidationError):
            ConsentRecord(
                child_id="child-test",
                consent_type=ConsentType.DATA_COLLECTION
            )
        
        # Missing consent_type
        with pytest.raises(ValidationError):
            ConsentRecord(
                child_id="child-test",
                parent_id="parent-test"
            )

    def test_empty_string_fields_rejected(self):
        """Test empty string fields are rejected."""
        with pytest.raises(ValidationError):
            ConsentRecord(
                child_id="",  # Empty string
                parent_id="parent-test",
                consent_type=ConsentType.DATA_COLLECTION
            )
        
        with pytest.raises(ValidationError):
            ConsentRecord(
                child_id="child-test",
                parent_id="",  # Empty string
                consent_type=ConsentType.DATA_COLLECTION
            )

    def test_datetime_field_validation(self):
        """Test datetime fields accept valid datetime objects."""
        now = datetime.now()
        
        record = ConsentRecord(
            child_id="child-test",
            parent_id="parent-test",
            consent_type=ConsentType.DATA_COLLECTION,
            granted_at=now,
            revoked_at=now,
            expires_at=now
        )
        
        assert record.granted_at == now
        assert record.revoked_at == now
        assert record.expires_at == now


class TestConsentRecordLifecycle:
    """Test consent record lifecycle scenarios."""

    def test_pending_to_granted_workflow(self):
        """Test typical workflow from pending to granted."""
        # Create pending record
        record = ConsentRecord(
            child_id="child-workflow",
            parent_id="parent-workflow",
            consent_type=ConsentType.DATA_COLLECTION,
            status=ConsentStatus.PENDING
        )
        
        assert record.status == ConsentStatus.PENDING
        assert record.granted_at is None
        
        # Grant consent
        granted_time = datetime.now()
        record.status = ConsentStatus.GRANTED
        record.granted_at = granted_time
        record.expires_at = granted_time + timedelta(days=365)
        
        assert record.status == ConsentStatus.GRANTED
        assert record.granted_at == granted_time
        assert record.expires_at is not None

    def test_revoke_consent_workflow(self):
        """Test revoking previously granted consent."""
        granted_time = datetime.now()
        
        record = ConsentRecord(
            child_id="child-revoke",
            parent_id="parent-revoke",
            consent_type=ConsentType.VOICE_RECORDING,
            status=ConsentStatus.GRANTED,
            granted_at=granted_time
        )
        
        # Revoke consent
        revoked_time = datetime.now()
        record.status = ConsentStatus.REVOKED
        record.revoked_at = revoked_time
        
        assert record.status == ConsentStatus.REVOKED
        assert record.revoked_at == revoked_time
        assert record.granted_at == granted_time  # Should preserve original grant time

    def test_expired_consent_scenario(self):
        """Test expired consent scenario."""
        past_time = datetime.now() - timedelta(days=400)
        
        record = ConsentRecord(
            child_id="child-expired",
            parent_id="parent-expired",
            consent_type=ConsentType.MARKETING_EMAILS,
            status=ConsentStatus.EXPIRED,
            granted_at=past_time,
            expires_at=past_time + timedelta(days=365)
        )
        
        assert record.status == ConsentStatus.EXPIRED
        assert record.expires_at < datetime.now()


class TestConsentRecordSerialization:
    """Test JSON serialization and Pydantic features."""

    def test_json_serialization(self):
        """Test consent record can be serialized to JSON."""
        record = ConsentRecord(
            child_id="child-json",
            parent_id="parent-json",
            consent_type=ConsentType.DATA_COLLECTION,
            status=ConsentStatus.GRANTED
        )
        
        # Should serialize without error
        json_data = record.model_dump_json()
        assert isinstance(json_data, str)
        assert "child-json" in json_data
        assert "data_collection" in json_data
        assert "granted" in json_data

    def test_dict_conversion(self):
        """Test consent record can be converted to dictionary."""
        record = ConsentRecord(
            child_id="child-dict",
            parent_id="parent-dict",
            consent_type=ConsentType.VOICE_RECORDING
        )
        
        data_dict = record.model_dump()
        assert isinstance(data_dict, dict)
        assert data_dict["child_id"] == "child-dict"
        assert data_dict["consent_type"] == "voice_recording"  # Enum value
        assert data_dict["status"] == "pending"  # Default status

    def test_from_dict_creation(self):
        """Test creating consent record from dictionary."""
        data = {
            "child_id": "child-from-dict",
            "parent_id": "parent-from-dict",
            "consent_type": "marketing_emails",
            "status": "granted",
            "version": "1.5"
        }
        
        record = ConsentRecord(**data)
        assert record.child_id == "child-from-dict"
        assert record.consent_type == ConsentType.MARKETING_EMAILS
        assert record.status == ConsentStatus.GRANTED
        assert record.version == "1.5"


class TestConsentRecordEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_ids(self):
        """Test handling of very long ID strings."""
        long_id = "a" * 1000
        
        record = ConsentRecord(
            child_id=long_id,
            parent_id=long_id,
            consent_type=ConsentType.DATA_COLLECTION
        )
        
        assert record.child_id == long_id
        assert record.parent_id == long_id

    def test_unicode_ids(self):
        """Test handling of unicode characters in IDs."""
        unicode_child_id = "child-测试-123"
        unicode_parent_id = "parent-тест-456"
        
        record = ConsentRecord(
            child_id=unicode_child_id,
            parent_id=unicode_parent_id,
            consent_type=ConsentType.DATA_COLLECTION
        )
        
        assert record.child_id == unicode_child_id
        assert record.parent_id == unicode_parent_id

    def test_version_field_flexibility(self):
        """Test version field accepts various formats."""
        versions = ["1.0", "2.1.3", "v1.0-beta", "latest"]
        
        for version in versions:
            record = ConsentRecord(
                child_id="child-version",
                parent_id="parent-version",
                consent_type=ConsentType.DATA_COLLECTION,
                version=version
            )
            assert record.version == version

    def test_datetime_precision(self):
        """Test datetime field precision handling."""
        precise_time = datetime(2024, 1, 15, 10, 30, 45, 123456)
        
        record = ConsentRecord(
            child_id="child-time",
            parent_id="parent-time",
            consent_type=ConsentType.DATA_COLLECTION,
            granted_at=precise_time,
            expires_at=precise_time
        )
        
        assert record.granted_at == precise_time
        assert record.expires_at == precise_time