"""
Unit tests for ChildData DTO.
Tests COPPA compliance, data validation, and security features.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID

from src.shared.dto.child_data import ChildData


class TestChildDataCreation:
    """Test ChildData creation and basic functionality."""

    def test_create_valid_child_data(self):
        """Test creating valid ChildData with all required fields."""
        child_id = uuid4()
        parent_id = uuid4()
        consent_date = datetime.utcnow()
        
        child = ChildData(
            id=child_id,
            name="Alice Smith",
            age=8,
            parent_id=parent_id,
            consent_granted=True,
            consent_date=consent_date
        )
        
        assert child.id == child_id
        assert child.name == "Alice Smith"
        assert child.age == 8
        assert child.parent_id == parent_id
        assert child.consent_granted is True
        assert child.consent_date == consent_date
        assert isinstance(child.data_created, datetime)
        assert child.last_interaction is None
        assert child.encrypted_data is False
        assert child.preferences == {}

    def test_create_child_with_preferences(self):
        """Test creating child with custom preferences."""
        preferences = {
            "favorite_color": "blue",
            "interests": ["dinosaurs", "space"],
            "safety_level": "strict"
        }
        
        child = ChildData(
            id=uuid4(),
            name="Bob",
            age=7,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow(),
            preferences=preferences
        )
        
        assert child.preferences == preferences
        assert child.preferences["favorite_color"] == "blue"
        assert len(child.preferences["interests"]) == 2


class TestCOPPAAgeValidation:
    """Test COPPA age compliance (3-13 years)."""

    @pytest.mark.parametrize("age", [3, 5, 8, 10, 13])
    def test_valid_ages(self, age):
        """Test all valid COPPA ages."""
        child = ChildData(
            id=uuid4(),
            name="Test Child",
            age=age,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow()
        )
        assert child.age == age

    @pytest.mark.parametrize("invalid_age", [2, 14, 0, -1, 18, 25])
    def test_invalid_ages(self, invalid_age):
        """Test ages outside COPPA range are rejected."""
        with pytest.raises(ValueError, match="COPPA Violation: Child age must be between 3-13 years"):
            ChildData(
                id=uuid4(),
                name="Test Child",
                age=invalid_age,
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=datetime.utcnow()
            )

    def test_non_integer_age(self):
        """Test that non-integer ages are rejected."""
        with pytest.raises(ValueError, match="COPPA Violation: Child age must be between 3-13 years"):
            ChildData(
                id=uuid4(),
                name="Test Child",
                age="eight",  # String instead of int
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=datetime.utcnow()
            )

    def test_float_age(self):
        """Test that float ages are rejected."""
        with pytest.raises(ValueError, match="COPPA Violation: Child age must be between 3-13 years"):
            ChildData(
                id=uuid4(),
                name="Test Child",
                age=8.5,  # Float instead of int
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=datetime.utcnow()
            )


class TestNameValidation:
    """Test child name validation."""

    def test_valid_names(self):
        """Test various valid name formats."""
        valid_names = [
            "Alice",
            "Bob Smith",
            "María García",
            "李小明",
            "أحمد محمد",
            "Jean-Pierre",
            "O'Connor",
            "A",  # Single character
            "A" * 100  # Exactly 100 characters
        ]
        
        for name in valid_names:
            child = ChildData(
                id=uuid4(),
                name=name,
                age=8,
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=datetime.utcnow()
            )
            assert child.name == name

    def test_empty_name_rejected(self):
        """Test empty names are rejected."""
        with pytest.raises(ValueError, match="Child name cannot be empty"):
            ChildData(
                id=uuid4(),
                name="",
                age=8,
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=datetime.utcnow()
            )

    def test_whitespace_only_name_rejected(self):
        """Test names with only whitespace are rejected."""
        with pytest.raises(ValueError, match="Child name cannot be empty"):
            ChildData(
                id=uuid4(),
                name="   ",
                age=8,
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=datetime.utcnow()
            )

    def test_name_too_long_rejected(self):
        """Test names over 100 characters are rejected."""
        long_name = "A" * 101
        with pytest.raises(ValueError, match="Child name too long"):
            ChildData(
                id=uuid4(),
                name=long_name,
                age=8,
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=datetime.utcnow()
            )


class TestParentalConsentValidation:
    """Test COPPA parental consent requirements."""

    def test_consent_required_for_under_13(self):
        """Test parental consent is required for children under 13."""
        # All ages 3-12 require consent
        for age in range(3, 13):
            with pytest.raises(ValueError, match="COPPA Compliance: Parental consent required"):
                ChildData(
                    id=uuid4(),
                    name="Test Child",
                    age=age,
                    parent_id=uuid4(),
                    consent_granted=False  # No consent
                )

    def test_parent_id_required_for_under_13(self):
        """Test parent ID is required for children under 13."""
        with pytest.raises(ValueError, match="COPPA Compliance: Parent ID required"):
            ChildData(
                id=uuid4(),
                name="Test Child",
                age=8,
                parent_id=None,  # No parent ID
                consent_granted=True,
                consent_date=datetime.utcnow()
            )

    def test_consent_date_required_when_granted(self):
        """Test consent date is required when consent is granted."""
        with pytest.raises(ValueError, match="COPPA Compliance: Consent date required"):
            ChildData(
                id=uuid4(),
                name="Test Child",
                age=8,
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=None  # No consent date
            )

    def test_valid_consent_configuration(self):
        """Test valid consent configuration works."""
        child = ChildData(
            id=uuid4(),
            name="Test Child",
            age=10,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow()
        )
        
        assert child.consent_granted is True
        assert child.parent_id is not None
        assert child.consent_date is not None

    def test_13_year_old_edge_case(self):
        """Test 13-year-old still requires consent (under 13 rule)."""
        with pytest.raises(ValueError, match="COPPA Compliance: Parental consent required"):
            ChildData(
                id=uuid4(),
                name="Teen",
                age=13,
                parent_id=uuid4(),
                consent_granted=False
            )


class TestDataRetentionValidation:
    """Test COPPA data retention limits (90 days)."""

    def test_fresh_data_accepted(self):
        """Test recently created data is accepted."""
        recent_date = datetime.utcnow() - timedelta(days=30)
        
        child = ChildData(
            id=uuid4(),
            name="Test Child",
            age=8,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow(),
            data_created=recent_date
        )
        
        assert child.data_created == recent_date

    def test_data_at_90_day_limit_accepted(self):
        """Test data exactly at 90-day limit is still accepted."""
        limit_date = datetime.utcnow() - timedelta(days=90)
        
        child = ChildData(
            id=uuid4(),
            name="Test Child",
            age=8,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow(),
            data_created=limit_date
        )
        
        assert child.data_created == limit_date

    def test_expired_data_rejected(self):
        """Test data older than 90 days is rejected."""
        expired_date = datetime.utcnow() - timedelta(days=91)
        
        with pytest.raises(ValueError, match="COPPA Compliance: Child data expired after 90 days"):
            ChildData(
                id=uuid4(),
                name="Test Child",
                age=8,
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=datetime.utcnow(),
                data_created=expired_date
            )

    def test_should_purge_data_method(self):
        """Test should_purge_data method logic."""
        # Fresh data should not be purged
        fresh_child = ChildData(
            id=uuid4(),
            name="Fresh Child",
            age=8,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow(),
            data_created=datetime.utcnow() - timedelta(days=30)
        )
        assert fresh_child.should_purge_data() is False
        
        # Data at 90 days should be purged
        old_child = ChildData(
            id=uuid4(),
            name="Old Child",
            age=8,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow(),
            data_created=datetime.utcnow() - timedelta(days=90)
        )
        assert old_child.should_purge_data() is True

    def test_should_purge_data_no_creation_date(self):
        """Test should_purge_data when no creation date is set."""
        child = ChildData(
            id=uuid4(),
            name="Test Child",
            age=8,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow()
        )
        # Manually set to None to test edge case
        child.data_created = None
        
        assert child.should_purge_data() is False


class TestChildDataEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_unicode_names(self):
        """Test names with unicode characters."""
        unicode_names = [
            "José María",
            "北京小明",
            "محمد أحمد",
            "Владимир",
            "🌟 Star Child 🌟"
        ]
        
        for name in unicode_names:
            child = ChildData(
                id=uuid4(),
                name=name,
                age=8,
                parent_id=uuid4(),
                consent_granted=True,
                consent_date=datetime.utcnow()
            )
            assert child.name == name

    def test_complex_preferences(self):
        """Test complex preference data structures."""
        complex_prefs = {
            "safety": {
                "content_filter": "strict",
                "blocked_topics": ["violence", "scary"]
            },
            "learning": {
                "subjects": ["math", "science"],
                "difficulty": "beginner"
            },
            "schedule": {
                "active_hours": [9, 10, 11, 14, 15, 16],
                "timezone": "UTC-5"
            }
        }
        
        child = ChildData(
            id=uuid4(),
            name="Test Child",
            age=9,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow(),
            preferences=complex_prefs
        )
        
        assert child.preferences["safety"]["content_filter"] == "strict"
        assert len(child.preferences["learning"]["subjects"]) == 2
        assert child.preferences["schedule"]["timezone"] == "UTC-5"

    def test_timestamp_precision(self):
        """Test timestamp precision and timezone handling."""
        specific_time = datetime(2024, 1, 15, 10, 30, 45, 123456)
        
        child = ChildData(
            id=uuid4(),
            name="Time Test",
            age=7,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=specific_time,
            data_created=specific_time
        )
        
        assert child.consent_date == specific_time
        assert child.data_created == specific_time


class TestChildDataSecurity:
    """Test security-related features."""

    def test_encryption_status_tracking(self):
        """Test encryption status is tracked."""
        child = ChildData(
            id=uuid4(),
            name="Encrypted Child",
            age=8,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow(),
            encrypted_data=True
        )
        
        assert child.encrypted_data is True

    def test_last_interaction_tracking(self):
        """Test last interaction timestamp tracking."""
        interaction_time = datetime.utcnow() - timedelta(hours=2)
        
        child = ChildData(
            id=uuid4(),
            name="Active Child",
            age=9,
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow(),
            last_interaction=interaction_time
        )
        
        assert child.last_interaction == interaction_time

    def test_uuid_field_types(self):
        """Test UUID field type validation."""
        child_uuid = uuid4()
        parent_uuid = uuid4()
        
        child = ChildData(
            id=child_uuid,
            name="UUID Test",
            age=8,
            parent_id=parent_uuid,
            consent_granted=True,
            consent_date=datetime.utcnow()
        )
        
        assert isinstance(child.id, UUID)
        assert isinstance(child.parent_id, UUID)
        assert child.id == child_uuid
        assert child.parent_id == parent_uuid