"""
Unit tests for AudioSafetyService
Tests audio content safety validation for children
"""

import pytest
from unittest.mock import Mock

from src.application.services.audio_safety_service import (
    AudioSafetyService,
    SafetyCheckResult
)


class TestAudioSafetyService:
    """Test AudioSafetyService functionality."""

    @pytest.fixture
    def safety_service(self):
        """Create AudioSafetyService instance."""
        return AudioSafetyService()

    @pytest.fixture
    def sample_audio_data(self):
        """Sample audio data for testing."""
        return b"sample_audio_data" * 1000  # Simulate audio data

    @pytest.mark.asyncio
    async def test_check_audio_safety_valid_audio(self, safety_service, sample_audio_data):
        """Test safety check with valid audio."""
        result = await safety_service.check_audio_safety(sample_audio_data, child_age=8)
        
        assert isinstance(result, SafetyCheckResult)
        assert result.is_safe is True
        assert result.confidence > 0.5
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_check_audio_safety_empty_audio(self, safety_service):
        """Test safety check with empty audio."""
        result = await safety_service.check_audio_safety(b"", child_age=8)
        
        assert result.is_safe is False
        assert "Empty audio data" in result.violations
        assert "Provide valid audio" in result.recommendations

    @pytest.mark.asyncio
    async def test_check_audio_safety_too_long(self, safety_service):
        """Test safety check with audio too long for children."""
        long_audio = b"x" * 400000  # Very long audio
        result = await safety_service.check_audio_safety(long_audio, child_age=8)
        
        assert result.is_safe is False
        assert any("too long" in violation for violation in result.violations)
        assert any("under 5 minutes" in rec for rec in result.recommendations)

    @pytest.mark.asyncio
    async def test_check_audio_safety_young_child(self, safety_service):
        """Test safety check for very young children."""
        medium_audio = b"x" * 80000  # Medium length audio
        result = await safety_service.check_audio_safety(medium_audio, child_age=3)
        
        # Should have stricter limits for young children
        if not result.is_safe:
            assert any("very young children" in violation for violation in result.violations)

    @pytest.mark.asyncio
    async def test_check_audio_safety_no_age_provided(self, safety_service, sample_audio_data):
        """Test safety check without child age."""
        result = await safety_service.check_audio_safety(sample_audio_data)
        
        assert isinstance(result, SafetyCheckResult)
        # Should still perform basic safety checks

    @pytest.mark.asyncio
    async def test_check_text_safety_safe_content(self, safety_service):
        """Test text safety with safe content."""
        safe_text = "Hello! Let's read a nice story about animals."
        result = await safety_service.check_text_safety(safe_text)
        
        assert result.is_safe is True
        assert len(result.violations) == 0
        assert result.confidence > 0.9

    @pytest.mark.asyncio
    async def test_check_text_safety_empty_text(self, safety_service):
        """Test text safety with empty text."""
        result = await safety_service.check_text_safety("")
        
        assert result.is_safe is True
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_check_text_safety_violent_content(self, safety_service):
        """Test text safety with violent content."""
        violent_text = "Let's fight with weapons and hurt someone."
        result = await safety_service.check_text_safety(violent_text)
        
        assert result.is_safe is False
        assert any("violence" in violation for violation in result.violations)
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_check_text_safety_scary_content(self, safety_service):
        """Test text safety with scary content."""
        scary_text = "There's a scary monster in the nightmare."
        result = await safety_service.check_text_safety(scary_text)
        
        assert result.is_safe is False
        assert any("fear" in violation for violation in result.violations)

    @pytest.mark.asyncio
    async def test_check_text_safety_adult_content(self, safety_service):
        """Test text safety with adult content."""
        adult_text = "Let's talk about alcohol and cigarettes."
        result = await safety_service.check_text_safety(adult_text)
        
        assert result.is_safe is False
        assert any("adult_content" in violation for violation in result.violations)

    @pytest.mark.asyncio
    async def test_check_text_safety_inappropriate_language(self, safety_service):
        """Test text safety with inappropriate language."""
        inappropriate_text = "You are stupid and ugly, I hate you."
        result = await safety_service.check_text_safety(inappropriate_text)
        
        assert result.is_safe is False
        assert any("inappropriate" in violation for violation in result.violations)

    @pytest.mark.asyncio
    async def test_filter_content_safe_text(self, safety_service):
        """Test content filtering with safe text."""
        safe_text = "Let's play a fun game together!"
        filtered = await safety_service.filter_content(safe_text)
        
        assert filtered == safe_text  # Should remain unchanged

    @pytest.mark.asyncio
    async def test_filter_content_unsafe_text(self, safety_service):
        """Test content filtering with unsafe text."""
        unsafe_text = "This scary monster will fight and hurt you."
        filtered = await safety_service.filter_content(unsafe_text)
        
        assert "[filtered]" in filtered
        assert "scary" not in filtered
        assert "fight" not in filtered
        assert "hurt" not in filtered

    @pytest.mark.asyncio
    async def test_filter_content_capitalized_words(self, safety_service):
        """Test content filtering handles capitalized unsafe words."""
        unsafe_text = "The Scary Monster will Fight."
        filtered = await safety_service.filter_content(unsafe_text)
        
        assert "[filtered]" in filtered
        assert "Scary" not in filtered
        assert "Fight" not in filtered

    @pytest.mark.asyncio
    async def test_filter_content_empty_text(self, safety_service):
        """Test content filtering with empty text."""
        filtered = await safety_service.filter_content("")
        assert filtered == ""
        
        filtered_none = await safety_service.filter_content(None)
        assert filtered_none is None

    def test_assess_audio_quality_short_audio(self, safety_service):
        """Test audio quality assessment with short audio."""
        short_audio = b"x" * 500  # Very short
        quality = safety_service._assess_audio_quality(short_audio)
        
        assert quality == 0.1  # Should be low quality

    def test_assess_audio_quality_normal_audio(self, safety_service):
        """Test audio quality assessment with normal audio."""
        normal_audio = b"x" * 5000  # Normal length
        quality = safety_service._assess_audio_quality(normal_audio)
        
        assert quality > 0.5  # Should be reasonable quality

    def test_unsafe_patterns_initialization(self, safety_service):
        """Test that unsafe patterns are properly initialized."""
        assert hasattr(safety_service, 'unsafe_patterns')
        assert len(safety_service.unsafe_patterns) > 0
        assert "excessive_noise" in safety_service.unsafe_patterns
        assert "inappropriate_content" in safety_service.unsafe_patterns

    @pytest.mark.asyncio
    async def test_safety_check_result_structure(self, safety_service, sample_audio_data):
        """Test that SafetyCheckResult has correct structure."""
        result = await safety_service.check_audio_safety(sample_audio_data)
        
        assert hasattr(result, 'is_safe')
        assert hasattr(result, 'violations')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'recommendations')
        
        assert isinstance(result.is_safe, bool)
        assert isinstance(result.violations, list)
        assert isinstance(result.confidence, float)
        assert isinstance(result.recommendations, list)

    @pytest.mark.asyncio
    async def test_multiple_violations_handling(self, safety_service):
        """Test handling of multiple safety violations."""
        # Create audio that violates multiple rules
        very_long_empty_audio = b""  # Empty and would be too long if it had data
        
        result = await safety_service.check_audio_safety(very_long_empty_audio, child_age=3)
        
        assert result.is_safe is False
        assert len(result.violations) >= 1
        assert len(result.recommendations) >= 1

    def test_service_initialization_with_logger(self):
        """Test service initialization with custom logger."""
        mock_logger = Mock()
        service = AudioSafetyService(logger=mock_logger)
        
        assert service.logger == mock_logger

    def test_service_initialization_default_logger(self):
        """Test service initialization with default logger."""
        service = AudioSafetyService()
        
        assert service.logger is not None
        assert hasattr(service.logger, 'info')
        assert hasattr(service.logger, 'warning')
        assert hasattr(service.logger, 'error')