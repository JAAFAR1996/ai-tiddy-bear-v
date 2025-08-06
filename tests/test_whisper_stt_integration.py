"""🧸 AI TEDDY BEAR V5 - Whisper STT Integration Tests
Test suite for Whisper STT provider with real-time performance validation.
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, patch

from src.infrastructure.audio.whisper_stt_provider import WhisperSTTProvider
from src.interfaces.providers.stt_provider import STTResult


class TestWhisperSTTProvider:
    """Test suite for Whisper STT provider implementation."""

    @pytest.fixture
    def mock_whisper_model(self):
        """Mock Whisper model for testing."""
        from src.infrastructure.audio.whisper_stt_provider import WhisperSTTProvider

        model = Mock(spec=WhisperSTTProvider)
        model.transcribe.return_value = {
            "text": "مرحبا، كيف حالك؟",
            "language": "ar",
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.5,
                    "text": "مرحبا، كيف حالك؟",
                    "confidence": 0.95,
                }
            ],
        }
        return model

    @pytest.fixture
    def whisper_provider(self, mock_whisper_model):
        """Create WhisperSTTProvider instance with mocked dependencies."""
        with patch("whisper.load_model", return_value=mock_whisper_model):
            provider = WhisperSTTProvider(
                model_size="base", device="cpu", language=None, enable_vad=True
            )
            return provider

    def test_provider_initialization(self):
        """Test proper initialization of Whisper STT provider."""
        with patch("whisper.load_model", autospec=True) as mock_load:
            mock_load.return_value = Mock(spec=WhisperSTTProvider)

            provider = WhisperSTTProvider(
                model_size="base", device="auto", language="ar", enable_vad=True
            )

            assert provider.model_size == "base"
            assert provider.device == "cpu"  # Should fallback to CPU if no CUDA
            assert provider.language == "ar"
            assert provider.enable_vad is True
            mock_load.assert_called_once_with("base", device="cpu")

    def test_audio_preprocessing(self, whisper_provider):
        """Test audio preprocessing functionality."""
        # Create sample audio data (16kHz, mono)
        sample_rate = 16000
        duration = 2.0
        audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32)

        processed_audio = whisper_provider._preprocess_audio(
            audio_data, original_sr=sample_rate
        )

        # Should be normalized and in correct format
        assert isinstance(processed_audio, np.ndarray)
        assert processed_audio.dtype == np.float32
        assert len(processed_audio.shape) == 1  # Mono audio
        assert np.max(np.abs(processed_audio)) <= 1.0  # Normalized

    @pytest.mark.asyncio
    async def test_transcribe_arabic_audio(self, whisper_provider, mock_whisper_model):
        """Test Arabic audio transcription."""
        # Sample Arabic audio data
        audio_data = np.random.randn(32000).astype(np.float32)  # 2 seconds at 16kHz

        result = await whisper_provider.transcribe(audio_data)

        assert isinstance(result, STTResult)
        assert result.text == "مرحبا، كيف حالك؟"
        assert result.language == "ar"
        assert result.confidence >= 0.9
        assert result.processing_time_ms > 0
        mock_whisper_model.transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_english_audio(self, whisper_provider, mock_whisper_model):
        """Test English audio transcription."""
        # Configure mock for English
        mock_whisper_model.transcribe.return_value = {
            "text": "Hello, how are you?",
            "language": "en",
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Hello, how are you?",
                    "confidence": 0.98,
                }
            ],
        }

        audio_data = np.random.randn(32000).astype(np.float32)
        result = await whisper_provider.transcribe(audio_data)

        assert result.text == "Hello, how are you?"
        assert result.language == "en"
        assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_real_time_performance(self, whisper_provider):
        """Test real-time performance requirements."""
        # Test with 1-second audio chunk (real-time scenario)
        audio_data = np.random.randn(16000).astype(np.float32)  # 1 second

        start_time = asyncio.get_event_loop().time()
        result = await whisper_provider.transcribe(audio_data)
        end_time = asyncio.get_event_loop().time()

        processing_time = (end_time - start_time) * 1000  # Convert to ms

        # Should process faster than real-time (< 1000ms for 1s audio)
        assert processing_time < 1000
        assert result.processing_time_ms < 1000

    @pytest.mark.asyncio
    async def test_empty_audio_handling(self, whisper_provider):
        """Test handling of empty or silent audio."""
        # Empty audio
        empty_audio = np.zeros(16000, dtype=np.float32)

        result = await whisper_provider.transcribe(empty_audio)

        assert isinstance(result, STTResult)
        assert result.text == ""  # Should return empty text for silence
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_audio_format_validation(self, whisper_provider):
        """Test audio format validation."""
        # Invalid audio format (wrong dtype)
        invalid_audio = np.random.randint(0, 100, 16000)  # Integer array

        with pytest.raises(ValueError, match="Audio data must be float32"):
            await whisper_provider.transcribe(invalid_audio)

    @pytest.mark.asyncio
    async def test_transcribe_with_segments(self, whisper_provider, mock_whisper_model):
        """Test transcription with segment information."""
        # Configure mock with multiple segments
        mock_whisper_model.transcribe.return_value = {
            "text": "مرحبا. كيف حالك اليوم؟",
            "language": "ar",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "مرحبا.", "confidence": 0.95},
                {
                    "start": 1.0,
                    "end": 3.0,
                    "text": "كيف حالك اليوم؟",
                    "confidence": 0.92,
                },
            ],
        }

        audio_data = np.random.randn(48000).astype(np.float32)  # 3 seconds
        result = await whisper_provider.transcribe(audio_data)

        assert result.text == "مرحبا. كيف حالك اليوم؟"
        assert len(result.segments) == 2
        assert result.segments[0]["text"] == "مرحبا."
        assert result.segments[1]["text"] == "كيف حالك اليوم؟"

    @pytest.mark.asyncio
    async def test_concurrent_transcription(self, whisper_provider):
        """Test concurrent transcription requests."""
        audio_data = np.random.randn(16000).astype(np.float32)

        # Create multiple concurrent transcription tasks
        tasks = [whisper_provider.transcribe(audio_data) for _ in range(3)]

        results = await asyncio.gather(*tasks)

        # All should complete successfully
        assert len(results) == 3
        for result in results:
            assert isinstance(result, STTResult)

    def test_health_check(self, whisper_provider):
        """Test health check functionality."""
        health_status = whisper_provider.health_check()

        assert health_status["status"] == "healthy"
        assert health_status["model_size"] == "base"
        assert health_status["device"] == "cpu"
        assert "model_loaded" in health_status
        assert "supported_languages" in health_status

    @pytest.mark.asyncio
    async def test_error_handling(self, whisper_provider, mock_whisper_model):
        """Test error handling in transcription."""
        # Configure mock to raise exception
        mock_whisper_model.transcribe.side_effect = Exception("Model error")

        audio_data = np.random.randn(16000).astype(np.float32)

        with pytest.raises(Exception, match="Model error"):
            await whisper_provider.transcribe(audio_data)

    @pytest.mark.performance
    async def test_latency_requirements(self, whisper_provider):
        """Test latency requirements for ESP32 integration."""
        # Test with different audio chunk sizes
        chunk_sizes = [0.5, 1.0, 2.0]  # seconds

        for duration in chunk_sizes:
            audio_size = int(16000 * duration)
            audio_data = np.random.randn(audio_size).astype(np.float32)

            start_time = asyncio.get_event_loop().time()
            result = await whisper_provider.transcribe(audio_data)
            end_time = asyncio.get_event_loop().time()

            processing_time = (end_time - start_time) * 1000

            # Should meet 300ms latency target for short audio
            if duration <= 1.0:
                assert (
                    processing_time < 300
                ), f"Latency {processing_time}ms exceeds 300ms target"

            assert result.processing_time_ms == pytest.approx(processing_time, abs=50)


@pytest.mark.integration
class TestWhisperSTTIntegration:
    """Integration tests for Whisper STT with audio service."""

    @pytest.mark.asyncio
    async def test_audio_service_integration(self):
        """Test integration with AudioService."""
        from src.application.services.audio_service import AudioService
        from unittest.mock import Mock

        # Mock dependencies
        mock_tts = Mock(spec="TTSService")
        mock_validation = Mock(spec="ValidationService")
        mock_streaming = Mock(spec="StreamingService")
        mock_safety = Mock(spec="SafetyService")
        mock_cache = Mock(spec="CacheService")
        mock_logger = Mock(spec="Logger")

        # Create WhisperSTTProvider
        with patch("whisper.load_model", autospec=True) as mock_load:
            mock_model = Mock(spec=WhisperSTTProvider)
            mock_model.transcribe.return_value = {
                "text": "test transcription",
                "language": "en",
                "segments": [],
            }
            mock_load.return_value = mock_model

            whisper_stt = WhisperSTTProvider(model_size="base")

            # Create AudioService with Whisper STT
            audio_service = AudioService(
                stt_provider=whisper_stt,
                tts_service=mock_tts,
                validation_service=mock_validation,
                streaming_service=mock_streaming,
                safety_service=mock_safety,
                cache_service=mock_cache,
                logger=mock_logger,
            )

            # Test audio processing
            audio_data = np.random.randn(16000).astype(np.float32)
            result = await audio_service.process_audio(
                audio_data=audio_data, child_id="test_child", language_code="auto"
            )

            # Should use Whisper for STT
            assert result is not None
            mock_model.transcribe.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
