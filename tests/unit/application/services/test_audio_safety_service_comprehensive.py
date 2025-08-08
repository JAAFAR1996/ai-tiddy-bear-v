"""
Comprehensive unit tests for audio_safety_service module.
Production-grade child safety testing for audio content and transcription.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import logging

from src.application.services.audio_safety_service import (
    AudioSafetyService,
    SafetyCheckResult
)


class TestSafetyCheckResult:
    """Test SafetyCheckResult dataclass."""

    def test_safety_check_result_creation(self):
        """Test SafetyCheckResult creation with all fields."""
        result = SafetyCheckResult(
            is_safe=True,
            violations=["test violation"],
            confidence=0.95,
            recommendations=["test recommendation"]
        )
        
        assert result.is_safe is True
        assert result.violations == ["test violation"]
        assert result.confidence == 0.95
        assert result.recommendations == ["test recommendation"]

    def test_safety_check_result_safe(self):
        """Test SafetyCheckResult for safe content."""
        result = SafetyCheckResult(
            is_safe=True,
            violations=[],
            confidence=1.0,
            recommendations=[]
        )
        
        assert result.is_safe is True
        assert len(result.violations) == 0
        assert result.confidence == 1.0
        assert len(result.recommendations) == 0

    def test_safety_check_result_unsafe(self):
        """Test SafetyCheckResult for unsafe content."""
        violations = ["inappropriate_content", "excessive_noise"]
        recommendations = ["Filter content", "Reduce volume"]
        
        result = SafetyCheckResult(
            is_safe=False,
            violations=violations,
            confidence=0.2,
            recommendations=recommendations
        )
        
        assert result.is_safe is False
        assert result.violations == violations
        assert result.confidence == 0.2
        assert result.recommendations == recommendations


class TestAudioSafetyService:
    """Test AudioSafetyService functionality."""

    @pytest.fixture
    def audio_safety_service(self):
        """Create AudioSafetyService instance for testing."""
        return AudioSafetyService()

    @pytest.fixture
    def custom_logger(self):
        """Create custom logger for testing."""
        return Mock(spec=logging.Logger)

    @pytest.fixture
    def audio_safety_service_with_logger(self, custom_logger):
        """Create AudioSafetyService with custom logger."""
        return AudioSafetyService(logger=custom_logger)

    def test_initialization_default_logger(self, audio_safety_service):
        """Test AudioSafetyService initialization with default logger."""
        assert audio_safety_service.logger is not None
        assert isinstance(audio_safety_service.unsafe_patterns, list)
        assert len(audio_safety_service.unsafe_patterns) > 0

    def test_initialization_custom_logger(self, audio_safety_service_with_logger, custom_logger):
        """Test AudioSafetyService initialization with custom logger."""
        assert audio_safety_service_with_logger.logger == custom_logger
        assert isinstance(audio_safety_service_with_logger.unsafe_patterns, list)

    def test_unsafe_patterns_content(self, audio_safety_service):
        """Test unsafe patterns contain expected categories."""
        expected_patterns = [
            "excessive_noise",
            "distorted_speech", 
            "inappropriate_content",
            "adult_conversation",
            "multiple_speakers"
        ]
        
        for pattern in expected_patterns:
            assert pattern in audio_safety_service.unsafe_patterns

    @pytest.mark.asyncio
    async def test_check_audio_safety_empty_data(self, audio_safety_service):
        """Test audio safety check with empty data."""
        audio_data = b""
        
        result = await audio_safety_service.check_audio_safety(audio_data)
        
        assert isinstance(result, SafetyCheckResult)
        assert result.is_safe is False
        assert "Empty audio data" in result.violations
        assert "Provide valid audio" in result.recommendations
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_check_audio_safety_valid_short_audio(self, audio_safety_service):
        """Test audio safety check with valid short audio."""
        # Create valid short audio data (simulated)
        audio_data = b"A" * 10000  # Short audio
        
        with patch.object(audio_safety_service, '_assess_audio_quality', return_value=0.8):
            result = await audio_safety_service.check_audio_safety(audio_data)
        
        assert isinstance(result, SafetyCheckResult)
        assert result.is_safe is True
        assert len(result.violations) == 0
        assert len(result.recommendations) == 0
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_check_audio_safety_too_long_general(self, audio_safety_service):
        """Test audio safety check with too long audio (general)."""
        # Create audio that's too long (over 5 minutes)
        audio_data = b"A" * 5000000  # ~5+ minutes estimated
        
        result = await audio_safety_service.check_audio_safety(audio_data)
        
        assert result.is_safe is False
        assert "Audio too long for child attention span" in result.violations
        assert "Keep audio under 5 minutes" in result.recommendations

    @pytest.mark.asyncio
    async def test_check_audio_safety_too_long_young_child(self, audio_safety_service):
        """Test audio safety check with too long audio for young child."""
        # Create audio that's too long for young children (over 1 minute)
        audio_data = b"A" * 100000  # ~1+ minute estimated
        child_age = 3  # Very young child
        
        result = await audio_safety_service.check_audio_safety(audio_data, child_age)
        
        assert result.is_safe is False
        assert "Audio too long for very young children" in result.violations
        assert "Keep under 1 minute for children under 5" in result.recommendations

    @pytest.mark.asyncio
    async def test_check_audio_safety_age_appropriate_young_child(self, audio_safety_service):
        """Test audio safety check with age-appropriate audio for young child."""
        # Create short audio appropriate for young children
        audio_data = b"A" * 50000  # Under 1 minute estimated
        child_age = 4
        
        with patch.object(audio_safety_service, '_assess_audio_quality', return_value=0.8):
            result = await audio_safety_service.check_audio_safety(audio_data, child_age)
        
        assert result.is_safe is True
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_check_audio_safety_poor_quality(self, audio_safety_service):
        """Test audio safety check with poor quality audio."""
        audio_data = b"A" * 10000
        
        with patch.object(audio_safety_service, '_assess_audio_quality', return_value=0.3):
            result = await audio_safety_service.check_audio_safety(audio_data)
        
        assert result.is_safe is False
        assert "Audio quality insufficient for children" in result.violations
        assert "Improve audio clarity" in result.recommendations

    @pytest.mark.asyncio
    async def test_check_audio_safety_multiple_violations(self, audio_safety_service):
        """Test audio safety check with multiple violations."""
        # Empty, poor quality audio
        audio_data = b""
        
        result = await audio_safety_service.check_audio_safety(audio_data)
        
        assert result.is_safe is False
        assert len(result.violations) >= 1
        assert len(result.recommendations) >= 1
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_check_audio_safety_older_child(self, audio_safety_service):
        """Test audio safety check for older child (more lenient duration)."""
        # Audio that would be too long for young children but OK for older
        audio_data = b"A" * 80000  # ~1+ minute
        child_age = 8  # Older child
        
        with patch.object(audio_safety_service, '_assess_audio_quality', return_value=0.8):
            result = await audio_safety_service.check_audio_safety(audio_data, child_age)
        
        assert result.is_safe is True
        # Should not have young child duration violation
        violations_text = " ".join(result.violations)
        assert "very young children" not in violations_text

    @pytest.mark.asyncio
    async def test_check_text_safety_empty_text(self, audio_safety_service):
        """Test text safety check with empty text."""
        result = await audio_safety_service.check_text_safety("")
        
        assert result.is_safe is True
        assert len(result.violations) == 0
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_check_text_safety_whitespace_only(self, audio_safety_service):
        """Test text safety check with whitespace-only text."""
        result = await audio_safety_service.check_text_safety("   \n\t  ")
        
        assert result.is_safe is True
        assert len(result.violations) == 0
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_check_text_safety_safe_content(self, audio_safety_service):
        """Test text safety check with safe content."""
        safe_texts = [
            "Hello, how are you today?",
            "Let's play a fun game together!",
            "What's your favorite color?",
            "I love reading books about animals.",
            "Can you count to ten?"
        ]
        
        for text in safe_texts:
            result = await audio_safety_service.check_text_safety(text)
            assert result.is_safe is True, f"Text should be safe: {text}"
            assert len(result.violations) == 0
            assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_check_text_safety_violence_content(self, audio_safety_service):
        """Test text safety check with violence-related content."""
        violence_texts = [
            "Don't fight with your brother",
            "The character got hit by a ball",
            "This will hurt a little bit", 
            "There's a weapon in the story",
            "The toy gun is broken"
        ]
        
        for text in violence_texts:
            result = await audio_safety_service.check_text_safety(text)
            assert result.is_safe is False, f"Text should be unsafe: {text}"
            assert any("violence" in violation for violation in result.violations)
            assert any("Replace violence content" in rec for rec in result.recommendations)
            assert result.confidence == 0.2

    @pytest.mark.asyncio
    async def test_check_text_safety_fear_content(self, audio_safety_service):
        """Test text safety check with fear-inducing content."""
        fear_texts = [
            "That looks scary to me",
            "It's quite frightening outside", 
            "There's a monster under the bed",
            "I had a nightmare last night"
        ]
        
        for text in fear_texts:
            result = await audio_safety_service.check_text_safety(text)
            assert result.is_safe is False, f"Text should be unsafe: {text}"
            assert any("fear" in violation for violation in result.violations)
            assert any("Replace fear content" in rec for rec in result.recommendations)

    @pytest.mark.asyncio
    async def test_check_text_safety_adult_content(self, audio_safety_service):
        """Test text safety check with adult content."""
        adult_texts = [
            "I don't like drug stores",
            "Dad drinks alcohol sometimes",
            "Mom quit cigarette smoking"
        ]
        
        for text in adult_texts:
            result = await audio_safety_service.check_text_safety(text)
            assert result.is_safe is False, f"Text should be unsafe: {text}"
            assert any("adult_content" in violation for violation in result.violations)
            assert any("Replace adult_content content" in rec for rec in result.recommendations)

    @pytest.mark.asyncio
    async def test_check_text_safety_inappropriate_content(self, audio_safety_service):
        """Test text safety check with inappropriate language."""
        inappropriate_texts = [
            "That's really stupid",
            "I hate vegetables",
            "You look ugly today"
        ]
        
        for text in inappropriate_texts:
            result = await audio_safety_service.check_text_safety(text)
            assert result.is_safe is False, f"Text should be unsafe: {text}"
            assert any("inappropriate" in violation for violation in result.violations)
            assert any("Replace inappropriate content" in rec for rec in result.recommendations)

    @pytest.mark.asyncio
    async def test_check_text_safety_case_insensitive(self, audio_safety_service):
        """Test text safety check is case insensitive."""
        test_cases = [
            "That's SCARY",
            "Don't FIGHT",
            "I HATE this",
            "MONSTER under bed"
        ]
        
        for text in test_cases:
            result = await audio_safety_service.check_text_safety(text)
            assert result.is_safe is False, f"Text should be detected as unsafe: {text}"

    @pytest.mark.asyncio
    async def test_check_text_safety_multiple_violations(self, audio_safety_service):
        """Test text safety check with multiple violations in one text."""
        text = "Don't fight the scary monster with weapons, I hate it!"
        
        result = await audio_safety_service.check_text_safety(text)
        
        assert result.is_safe is False
        # Should detect multiple categories but break after first in each category
        assert len(result.violations) >= 1  # At least one violation per category
        assert result.confidence == 0.2

    @pytest.mark.asyncio
    async def test_check_text_safety_boundary_cases(self, audio_safety_service):
        """Test text safety check with boundary cases."""
        boundary_cases = [
            None,  # None input
            "",    # Empty string
            "a",   # Single character
            "fight fight fight",  # Repeated unsafe word
            "fighty",  # Contains but not exact match
            "fighting spirit"  # Context matters
        ]
        
        for text in boundary_cases:
            # Should not raise exceptions
            if text is None:
                continue  # Skip None as it's handled in the function
            result = await audio_safety_service.check_text_safety(text)
            assert isinstance(result, SafetyCheckResult)

    @pytest.mark.asyncio
    async def test_filter_content_empty_input(self, audio_safety_service):
        """Test content filtering with empty input."""
        assert await audio_safety_service.filter_content("") == ""
        assert await audio_safety_service.filter_content(None) is None

    @pytest.mark.asyncio
    async def test_filter_content_safe_text(self, audio_safety_service):
        """Test content filtering with safe text."""
        safe_text = "Hello, let's play a fun game together!"
        result = await audio_safety_service.filter_content(safe_text)
        
        assert result == safe_text  # Should remain unchanged

    @pytest.mark.asyncio
    async def test_filter_content_unsafe_words(self, audio_safety_service):
        """Test content filtering removes unsafe words."""
        test_cases = [
            ("This is scary content", "This is [filtered] content"),
            ("Something frightening happened", "Something [filtered] happened"),
            ("Violence is not good", "[filtered] is not good"),  
            ("No weapons allowed", "No [filtered] allowed"),
            ("Don't fight with others", "Don't [filtered] with others"),
            ("That will hurt you", "That will [filtered] you"),
            ("There's a monster here", "There's a [filtered] here")
        ]
        
        for input_text, expected_output in test_cases:
            result = await audio_safety_service.filter_content(input_text)
            assert result == expected_output, f"Failed for: {input_text}"

    @pytest.mark.asyncio
    async def test_filter_content_capitalized_words(self, audio_safety_service):
        """Test content filtering handles capitalized unsafe words."""
        test_cases = [
            ("This is Scary content", "This is [filtered] content"),
            ("Something Frightening happened", "Something [filtered] happened"),
            ("Violence is bad", "[filtered] is bad"),
            ("No Weapons here", "No [filtered] here"),
            ("Don't Fight anyone", "Don't [filtered] anyone"),
            ("That will Hurt", "That will [filtered]"),
            ("Big Monster outside", "Big [filtered] outside")
        ]
        
        for input_text, expected_output in test_cases:
            result = await audio_safety_service.filter_content(input_text)
            assert result == expected_output, f"Failed for: {input_text}"

    @pytest.mark.asyncio
    async def test_filter_content_multiple_unsafe_words(self, audio_safety_service):
        """Test content filtering with multiple unsafe words."""
        input_text = "The scary monster will fight and hurt everyone with weapons"
        result = await audio_safety_service.filter_content(input_text)
        
        # All unsafe words should be filtered
        expected_filtered_words = ["scary", "monster", "fight", "hurt", "weapons"]
        for word in expected_filtered_words:
            assert word not in result
            assert "[filtered]" in result

    @pytest.mark.asyncio
    async def test_filter_content_preserves_structure(self, audio_safety_service):
        """Test content filtering preserves text structure."""
        input_text = "Hello! This scary story has violence. Don't fight!"
        result = await audio_safety_service.filter_content(input_text)
        
        # Should preserve punctuation and structure
        assert result.startswith("Hello!")
        assert result.endswith("!")
        assert "[filtered]" in result
        assert "Don't [filtered]" in result

    def test_assess_audio_quality_too_short(self, audio_safety_service):
        """Test audio quality assessment with too short audio."""
        short_audio = b"A" * 500  # Less than 1000 bytes
        
        quality = audio_safety_service._assess_audio_quality(short_audio)
        
        assert quality == 0.1

    def test_assess_audio_quality_sufficient_length(self, audio_safety_service):
        """Test audio quality assessment with sufficient length."""
        sufficient_audio = b"A" * 5000  # More than 1000 bytes
        
        quality = audio_safety_service._assess_audio_quality(sufficient_audio)
        
        assert quality == 0.7  # Default quality score

    def test_assess_audio_quality_boundary_cases(self, audio_safety_service):
        """Test audio quality assessment boundary cases."""
        # Exactly 1000 bytes
        boundary_audio = b"A" * 1000
        quality = audio_safety_service._assess_audio_quality(boundary_audio)
        assert quality == 0.7
        
        # Just under threshold
        under_threshold = b"A" * 999
        quality = audio_safety_service._assess_audio_quality(under_threshold)
        assert quality == 0.1
        
        # Empty audio
        empty_audio = b""
        quality = audio_safety_service._assess_audio_quality(empty_audio)
        assert quality == 0.1


class TestAudioSafetyServiceIntegration:
    """Integration tests for AudioSafetyService workflows."""

    @pytest.fixture
    def audio_safety_service(self):
        """Create AudioSafetyService for integration testing."""
        return AudioSafetyService()

    @pytest.mark.asyncio
    async def test_complete_safety_workflow(self, audio_safety_service):
        """Test complete safety validation workflow."""
        # Simulate complete workflow: audio -> transcription -> safety check -> filtering
        
        # Step 1: Check audio safety
        audio_data = b"A" * 20000  # Valid length audio
        child_age = 6
        
        with patch.object(audio_safety_service, '_assess_audio_quality', return_value=0.8):
            audio_result = await audio_safety_service.check_audio_safety(audio_data, child_age)
        
        assert audio_result.is_safe is True
        
        # Step 2: Check transcribed text safety
        transcribed_text = "Hello there! Let's play a game together."
        text_result = await audio_safety_service.check_text_safety(transcribed_text)
        
        assert text_result.is_safe is True
        
        # Step 3: Filter content (should remain unchanged for safe content)
        filtered_content = await audio_safety_service.filter_content(transcribed_text)
        
        assert filtered_content == transcribed_text

    @pytest.mark.asyncio
    async def test_unsafe_content_workflow(self, audio_safety_service):
        """Test workflow with unsafe content requiring filtering."""
        # Step 1: Audio check (assume passes)
        audio_data = b"A" * 15000
        
        with patch.object(audio_safety_service, '_assess_audio_quality', return_value=0.7):
            audio_result = await audio_safety_service.check_audio_safety(audio_data)
        
        assert audio_result.is_safe is True
        
        # Step 2: Unsafe transcribed text
        unsafe_text = "There's a scary monster that wants to fight!"
        text_result = await audio_safety_service.check_text_safety(unsafe_text)
        
        assert text_result.is_safe is False
        assert len(text_result.violations) > 0
        
        # Step 3: Filter the unsafe content
        filtered_content = await audio_safety_service.filter_content(unsafe_text)
        
        assert filtered_content != unsafe_text
        assert "[filtered]" in filtered_content
        assert "scary" not in filtered_content
        assert "monster" not in filtered_content
        assert "fight" not in filtered_content

    @pytest.mark.asyncio
    async def test_age_specific_safety_workflow(self, audio_safety_service):
        """Test age-specific safety workflow."""
        # Test with very young child (stricter rules)
        young_child_age = 3
        
        # Audio that's too long for young children
        long_audio_for_young = b"A" * 80000  # Over 1 minute
        
        with patch.object(audio_safety_service, '_assess_audio_quality', return_value=0.8):
            young_result = await audio_safety_service.check_audio_safety(
                long_audio_for_young, young_child_age
            )
        
        assert young_result.is_safe is False
        assert "very young children" in " ".join(young_result.violations)
        
        # Same audio with older child (should be fine)
        older_child_age = 8
        
        with patch.object(audio_safety_service, '_assess_audio_quality', return_value=0.8):
            older_result = await audio_safety_service.check_audio_safety(
                long_audio_for_young, older_child_age
            )
        
        assert older_result.is_safe is True

    @pytest.mark.asyncio
    async def test_progressive_filtering_workflow(self, audio_safety_service):
        """Test progressive content filtering workflow."""
        # Start with heavily contaminated content
        original_text = "The scary monster will fight and hurt you with weapons in a frightening way!"
        
        # Check initial safety
        initial_result = await audio_safety_service.check_text_safety(original_text)
        assert initial_result.is_safe is False
        
        # Apply filtering
        filtered_text = await audio_safety_service.filter_content(original_text)
        
        # Check if filtering improved safety
        filtered_result = await audio_safety_service.check_text_safety(filtered_text)
        
        # After filtering, text should have fewer violations
        # (though may still be unsafe due to overall context)
        assert len(filtered_result.violations) <= len(initial_result.violations)
        assert "[filtered]" in filtered_text

    @pytest.mark.asyncio
    async def test_edge_case_handling_workflow(self, audio_safety_service):
        """Test workflow handles edge cases gracefully."""
        edge_cases = [
            (b"", ""),  # Empty audio and text
            (b"A" * 10, "a"),  # Minimal content
            (b"A" * 100000, "word " * 1000),  # Large content
        ]
        
        for audio_data, text_content in edge_cases:
            # Should not raise exceptions
            audio_result = await audio_safety_service.check_audio_safety(audio_data)
            text_result = await audio_safety_service.check_text_safety(text_content)
            filtered_result = await audio_safety_service.filter_content(text_content)
            
            # All should return valid results
            assert isinstance(audio_result, SafetyCheckResult)
            assert isinstance(text_result, SafetyCheckResult)
            assert isinstance(filtered_result, str)


class TestAudioSafetyServiceErrorHandling:
    """Test error handling and robustness."""

    @pytest.fixture
    def audio_safety_service(self):
        """Create AudioSafetyService for error testing."""
        return AudioSafetyService()

    @pytest.mark.asyncio
    async def test_invalid_child_age_handling(self, audio_safety_service):
        """Test handling of invalid child ages."""
        audio_data = b"A" * 10000
        
        # Test with negative age
        result = await audio_safety_service.check_audio_safety(audio_data, -1)
        assert isinstance(result, SafetyCheckResult)
        
        # Test with extremely high age
        result = await audio_safety_service.check_audio_safety(audio_data, 150)
        assert isinstance(result, SafetyCheckResult)
        
        # Test with None age (should work)
        result = await audio_safety_service.check_audio_safety(audio_data, None)
        assert isinstance(result, SafetyCheckResult)

    @pytest.mark.asyncio
    async def test_concurrent_safety_checks(self, audio_safety_service):
        """Test concurrent safety checks don't interfere."""
        import asyncio
        
        # Create multiple concurrent checks
        audio_data = b"A" * 10000
        text_data = "Hello world"
        
        tasks = []
        for i in range(10):
            tasks.append(audio_safety_service.check_audio_safety(audio_data, 5 + i))
            tasks.append(audio_safety_service.check_text_safety(f"{text_data} {i}"))
            tasks.append(audio_safety_service.filter_content(f"scary {text_data} {i}"))
        
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 30
        for result in results:
            assert result is not None

    def test_memory_efficiency_large_audio(self, audio_safety_service):
        """Test memory efficiency with large audio data."""
        # Test with large audio data
        large_audio = b"A" * 1000000  # 1MB
        
        # Should handle without memory issues
        quality = audio_safety_service._assess_audio_quality(large_audio)
        assert isinstance(quality, float)
        assert 0.0 <= quality <= 1.0

    @pytest.mark.asyncio
    async def test_unicode_text_handling(self, audio_safety_service):
        """Test handling of Unicode text in safety checks."""
        unicode_texts = [
            "Hello 世界",  # Mixed languages
            "émojis 🎵🎶",  # Accents and emojis
            "Здравствуй мир",  # Cyrillic
            "مرحبا بالعالم",  # Arabic
            "🔥🌟⭐💫",  # Only emojis
        ]
        
        for text in unicode_texts:
            # Should handle without errors
            result = await audio_safety_service.check_text_safety(text)
            assert isinstance(result, SafetyCheckResult)
            
            filtered = await audio_safety_service.filter_content(text)
            assert isinstance(filtered, str)

    @pytest.mark.asyncio
    async def test_performance_with_long_text(self, audio_safety_service):
        """Test performance with very long text content."""
        # Create very long text
        long_text = "This is a test sentence. " * 1000  # ~25k characters
        
        import time
        start_time = time.time()
        
        result = await audio_safety_service.check_text_safety(long_text)
        filtered = await audio_safety_service.filter_content(long_text)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete in reasonable time (less than 1 second)
        assert processing_time < 1.0
        assert isinstance(result, SafetyCheckResult)
        assert isinstance(filtered, str)

    @pytest.mark.asyncio  
    async def test_pattern_matching_edge_cases(self, audio_safety_service):
        """Test pattern matching edge cases."""
        edge_case_texts = [
            "scarycat",  # Unsafe word as part of compound word
            "scary-looking",  # Unsafe word with hyphen
            "scary!",  # Unsafe word with punctuation
            "SCARY",  # All caps
            "s c a r y",  # Spaced out
            "scaryyy",  # Extended word
        ]
        
        for text in edge_case_texts:
            result = await audio_safety_service.check_text_safety(text)
            assert isinstance(result, SafetyCheckResult)
            
            # Only exact word matches should be caught
            if text == "scary!":
                assert result.is_safe is False
            elif text == "SCARY":
                assert result.is_safe is False
            else:
                # Compound words, spaced words etc. might not match exactly
                assert isinstance(result.is_safe, bool)