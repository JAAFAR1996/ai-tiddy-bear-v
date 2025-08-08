"""
Unit tests for AIResponse DTO.
Tests data validation, safety enforcement, and field constraints.
"""

import pytest
from datetime import datetime
from dataclasses import FrozenInstanceError

from src.shared.dto.ai_response import AIResponse


class TestAIResponseCreation:
    """Test AIResponse creation and basic functionality."""

    def test_create_minimal_response(self):
        """Test creating AIResponse with minimal required fields."""
        response = AIResponse(content="Hello there!")
        
        assert response.content == "Hello there!"
        assert response.confidence == 1.0
        assert response.safe is True
        assert response.safety_score == 1.0
        assert response.age_appropriate is True
        assert response.model_used == "gpt-4-turbo-preview"
        assert isinstance(response.timestamp, datetime)
        assert response.moderation_flags == []

    def test_create_comprehensive_response(self):
        """Test creating AIResponse with all fields."""
        timestamp = datetime.now()
        metadata = {"processing_time": 0.5, "tokens_used": 150}
        
        response = AIResponse(
            content="Once upon a time...",
            confidence=0.95,
            timestamp=timestamp,
            model_used="gpt-4-custom",
            metadata=metadata,
            audio_url="https://example.com/audio.mp3",
            safe=True,
            safety_score=0.98,
            moderation_flags=["reviewed"],
            age_appropriate=True,
            conversation_id="conv-123",
            emotion="happy",
            sentiment=0.8,
            audio_response=b"audio_data"
        )
        
        assert response.content == "Once upon a time..."
        assert response.confidence == 0.95
        assert response.timestamp == timestamp
        assert response.model_used == "gpt-4-custom"
        assert response.metadata == metadata
        assert response.audio_url == "https://example.com/audio.mp3"
        assert response.safe is True
        assert response.safety_score == 0.98
        assert response.moderation_flags == ["reviewed"]
        assert response.age_appropriate is True
        assert response.conversation_id == "conv-123"
        assert response.emotion == "happy"
        assert response.sentiment == 0.8
        assert response.audio_response == b"audio_data"


class TestAIResponseValidation:
    """Test AIResponse field validation."""

    def test_empty_content_validation(self):
        """Test that empty content raises ValueError."""
        with pytest.raises(ValueError, match="Response content cannot be empty"):
            AIResponse(content="")
        
        with pytest.raises(ValueError, match="Response content cannot be empty"):
            AIResponse(content="   ")  # Only whitespace

    def test_confidence_bounds_validation(self):
        """Test confidence score validation."""
        # Valid confidence values
        AIResponse(content="test", confidence=0.0)
        AIResponse(content="test", confidence=0.5)
        AIResponse(content="test", confidence=1.0)
        
        # Invalid confidence values
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            AIResponse(content="test", confidence=-0.1)
        
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            AIResponse(content="test", confidence=1.1)

    def test_safety_score_bounds_validation(self):
        """Test safety score validation."""
        # Valid safety scores
        AIResponse(content="test", safety_score=0.0)
        AIResponse(content="test", safety_score=0.5)
        AIResponse(content="test", safety_score=1.0)
        
        # Invalid safety scores
        with pytest.raises(ValueError, match="Safety score must be between 0.0 and 1.0"):
            AIResponse(content="test", safety_score=-0.1)
        
        with pytest.raises(ValueError, match="Safety score must be between 0.0 and 1.0"):
            AIResponse(content="test", safety_score=1.5)

    def test_sentiment_bounds_validation(self):
        """Test sentiment score validation."""
        # Valid sentiment values
        AIResponse(content="test", sentiment=-1.0)
        AIResponse(content="test", sentiment=0.0)
        AIResponse(content="test", sentiment=1.0)
        AIResponse(content="test", sentiment=None)  # Optional field
        
        # Invalid sentiment values
        with pytest.raises(ValueError, match="Sentiment must be between -1.0 and 1.0"):
            AIResponse(content="test", sentiment=-1.1)
        
        with pytest.raises(ValueError, match="Sentiment must be between -1.0 and 1.0"):
            AIResponse(content="test", sentiment=1.1)


class TestAIResponseSafetyLogic:
    """Test safety enforcement logic in AIResponse."""

    def test_low_safety_score_enforcement(self):
        """Test that low safety scores automatically set safe=False."""
        response = AIResponse(
            content="test content",
            safety_score=0.7  # Below 0.8 threshold
        )
        
        assert response.safe is False
        assert "low_safety_score" in response.moderation_flags

    def test_age_inappropriate_enforcement(self):
        """Test that age_inappropriate automatically sets safe=False."""
        response = AIResponse(
            content="test content",
            age_appropriate=False
        )
        
        assert response.safe is False
        assert "not_age_appropriate" in response.moderation_flags

    def test_multiple_safety_violations(self):
        """Test handling multiple safety violations."""
        response = AIResponse(
            content="test content",
            safety_score=0.5,  # Low score
            age_appropriate=False  # Not age appropriate
        )
        
        assert response.safe is False
        assert "low_safety_score" in response.moderation_flags
        assert "not_age_appropriate" in response.moderation_flags
        assert len(response.moderation_flags) == 2

    def test_safe_content_remains_safe(self):
        """Test that safe content with good scores remains safe."""
        response = AIResponse(
            content="A friendly story about animals",
            safety_score=0.95,
            age_appropriate=True
        )
        
        assert response.safe is True
        assert response.moderation_flags == []

    def test_existing_moderation_flags_preserved(self):
        """Test that existing moderation flags are preserved."""
        response = AIResponse(
            content="test content",
            safety_score=0.6,  # Will trigger low_safety_score
            moderation_flags=["custom_flag", "reviewed"]
        )
        
        assert response.safe is False
        assert "custom_flag" in response.moderation_flags
        assert "reviewed" in response.moderation_flags
        assert "low_safety_score" in response.moderation_flags


class TestAIResponseEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_threshold_safety_score(self):
        """Test safety score exactly at threshold (0.8)."""
        response = AIResponse(
            content="test content",
            safety_score=0.8  # Exactly at threshold
        )
        
        # Should be safe since it's not < 0.8
        assert response.safe is True
        assert "low_safety_score" not in response.moderation_flags

    def test_unicode_content(self):
        """Test AIResponse handles unicode content correctly."""
        response = AIResponse(content="مرحبا! Hello! 你好! 🌟")
        
        assert response.content == "مرحبا! Hello! 你好! 🌟"
        assert response.safe is True

    def test_very_long_content(self):
        """Test AIResponse handles long content."""
        long_content = "A" * 10000
        response = AIResponse(content=long_content)
        
        assert len(response.content) == 10000
        assert response.safe is True

    def test_special_characters_in_content(self):
        """Test content with special characters."""
        special_content = "Content with \n\t special \r\n characters & symbols!"
        response = AIResponse(content=special_content)
        
        assert response.content == special_content
        assert response.safe is True

    def test_metadata_serialization(self):
        """Test metadata field handles complex data structures."""
        complex_metadata = {
            "processing_time": 1.5,
            "model_info": {
                "version": "4.0",
                "parameters": ["temperature", "max_tokens"]
            },
            "safety_checks": [
                {"type": "content", "passed": True},
                {"type": "age_appropriate", "passed": True}
            ]
        }
        
        response = AIResponse(
            content="test",
            metadata=complex_metadata
        )
        
        assert response.metadata == complex_metadata
        assert response.metadata["processing_time"] == 1.5
        assert response.metadata["model_info"]["version"] == "4.0"


class TestAIResponseDefaults:
    """Test default values and optional fields."""

    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        response = AIResponse(content="test")
        
        assert response.metadata is None
        assert response.audio_url is None
        assert response.conversation_id is None
        assert response.emotion is None
        assert response.sentiment is None
        assert response.audio_response is None

    def test_boolean_defaults(self):
        """Test boolean field defaults."""
        response = AIResponse(content="test")
        
        assert response.safe is True
        assert response.age_appropriate is True

    def test_list_defaults(self):
        """Test list field defaults."""
        response = AIResponse(content="test")
        
        assert response.moderation_flags == []
        assert isinstance(response.moderation_flags, list)

    def test_timestamp_default(self):
        """Test timestamp default is current time."""
        before = datetime.now()
        response = AIResponse(content="test")
        after = datetime.now()
        
        assert before <= response.timestamp <= after


class TestAIResponseImmutability:
    """Test dataclass behavior and field access."""

    def test_field_modification_allowed(self):
        """Test that fields can be modified (dataclass is not frozen)."""
        response = AIResponse(content="original")
        
        # Should be able to modify fields
        response.content = "modified"
        response.safe = False
        response.moderation_flags.append("new_flag")
        
        assert response.content == "modified"
        assert response.safe is False
        assert "new_flag" in response.moderation_flags

    def test_repr_contains_key_fields(self):
        """Test that string representation contains key information."""
        response = AIResponse(
            content="Test content",
            safe=True,
            safety_score=0.95
        )
        
        repr_str = repr(response)
        assert "Test content" in repr_str
        assert "safe" in repr_str.lower()
        assert "0.95" in repr_str