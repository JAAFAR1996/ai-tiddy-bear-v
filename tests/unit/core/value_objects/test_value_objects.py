"""
Tests for Core Value Objects
============================

Tests for core value objects and enums.
"""

import pytest

from src.core.value_objects.value_objects import (
    ContentFilterLevel,
    SafetyLevel,
    AgeGroup,
    SafetyScore,
    EmotionResult,
    ContentComplexity,
    ChildPreferences
)


class TestSafetyLevel:
    """Test safety level enum."""

    def test_from_score(self):
        """Test creating safety level from score."""
        assert SafetyLevel.from_score(0.95) == SafetyLevel.SAFE
        assert SafetyLevel.from_score(0.8) == SafetyLevel.LOW
        assert SafetyLevel.from_score(0.6) == SafetyLevel.MEDIUM
        assert SafetyLevel.from_score(0.4) == SafetyLevel.HIGH
        assert SafetyLevel.from_score(0.1) == SafetyLevel.CRITICAL


class TestAgeGroup:
    """Test age group enum."""

    def test_from_age_valid(self):
        """Test creating age group from valid ages."""
        assert AgeGroup.from_age(3) == AgeGroup.TODDLER
        assert AgeGroup.from_age(5) == AgeGroup.PRESCHOOL
        assert AgeGroup.from_age(7) == AgeGroup.EARLY_ELEMENTARY
        assert AgeGroup.from_age(13) == AgeGroup.PRETEEN

    def test_from_age_invalid(self):
        """Test creating age group from invalid ages."""
        with pytest.raises(ValueError, match="outside COPPA-compliant range"):
            AgeGroup.from_age(2)

    def test_validate_coppa_compliance(self):
        """Test COPPA compliance validation."""
        assert AgeGroup.validate_coppa_compliance(5) is True
        assert AgeGroup.validate_coppa_compliance(2) is False


class TestSafetyScore:
    """Test safety score value object."""

    def test_valid_safety_score(self):
        """Test creating valid safety score."""
        score = SafetyScore(0.8, 0.9, ("violation1",))
        
        assert score.score == 0.8
        assert score.confidence == 0.9
        assert score.violations == ("violation1",)

    def test_invalid_score_range(self):
        """Test invalid score range."""
        with pytest.raises(ValueError, match="score must be between 0.0 and 1.0"):
            SafetyScore(1.5, 0.9, ())

    def test_is_safe_property(self):
        """Test is_safe property."""
        safe_score = SafetyScore(0.9, 0.9, ())
        unsafe_score = SafetyScore(0.5, 0.9, ("violation",))
        
        assert safe_score.is_safe is True
        assert unsafe_score.is_safe is False


class TestChildPreferences:
    """Test child preferences value object."""

    def test_create_safe_defaults(self):
        """Test creating safe default preferences."""
        prefs = ChildPreferences.create_safe_defaults(8)
        
        assert prefs.learning_style == "visual"
        assert prefs.language_preference == "en"
        assert prefs.voice_speed == 1.0

    def test_create_safe_defaults_invalid_age(self):
        """Test creating defaults with invalid age."""
        with pytest.raises(ValueError, match="COPPA-compliant range"):
            ChildPreferences.create_safe_defaults(15)

    def test_invalid_learning_style(self):
        """Test invalid learning style."""
        with pytest.raises(ValueError, match="learning_style must be one of"):
            ChildPreferences(learning_style="invalid")