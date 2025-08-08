"""
Production Edge Case Tests
=========================
Test edge cases for production readiness.
"""

import pytest
from src.domain.audio import AudioFile, AudioValidationService
from src.application.services.audio_safety_service import AudioSafetyService
from src.shared.audio_types import AudioFormat


class TestAudioEdgeCases:
    """Test audio processing edge cases."""
    
    @pytest.fixture
    def validation_service(self):
        return AudioValidationService()
    
    @pytest.fixture
    def safety_service(self):
        return AudioSafetyService()
    
    def test_corrupted_audio_handling(self, validation_service):
        """Test handling of corrupted audio files."""
        corrupted_audio = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100
        
        result = validation_service.validate_audio(corrupted_audio)
        assert not result.is_valid
        assert len(result.issues) > 0
    
    def test_empty_audio_handling(self, validation_service):
        """Test handling of empty audio."""
        result = validation_service.validate_audio(b"")
        assert not result.is_valid
        assert "empty" in str(result.issues).lower()
    
    def test_oversized_audio_handling(self, validation_service):
        """Test handling of oversized audio files."""
        large_audio = b"RIFF" + b"\x00" * (60 * 1024 * 1024)
        
        result = validation_service.validate_audio(large_audio)
        assert not result.is_valid
    
    def test_very_short_audio(self):
        """Test handling of very short audio clips."""
        short_audio = AudioFile(
            data=b"test" * 10,
            format=AudioFormat.WAV,
            duration_ms=50,
            sample_rate=16000
        )
        
        assert not short_audio.is_valid_for_processing()
    
    @pytest.mark.asyncio
    async def test_inappropriate_content_detection(self, safety_service):
        """Test detection of inappropriate content."""
        test_cases = [
            ("This is scary monster", False),
            ("Hello friend", True),
            ("Violence is bad", False),
            ("Let's play together", True)
        ]
        
        for text, should_be_safe in test_cases:
            result = await safety_service.check_text_safety(text)
            assert result.is_safe == should_be_safe
    
    def test_error_handling_coverage(self):
        """Test that critical paths have error handling."""
        from src.application.services.audio_validation_service import AudioValidationService
        
        service = AudioValidationService()
        test_inputs = [b"", b"invalid", b"\x00" * 1000]
        
        for invalid_input in test_inputs:
            try:
                result = service.validate_audio(invalid_input)
                assert hasattr(result, 'is_valid')
            except Exception as e:
                pytest.fail(f"Unhandled exception: {e}")