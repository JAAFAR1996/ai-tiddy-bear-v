"""
Comprehensive tests for Audio Service.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from dataclasses import dataclass

from src.application.services.audio_service import (
    AudioService,
    TTSMetrics,
    TTSCacheService
)
from src.shared.audio_types import AudioProcessingError
from src.interfaces.providers.tts_provider import TTSResult, TTSError, TTSProviderError


class TestTTSMetrics:
    """Test TTS metrics data class."""

    def test_metrics_initialization(self):
        """Test metrics initialization with defaults."""
        metrics = TTSMetrics()
        
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.cache_hit_rate == 0.0
        assert metrics.provider_errors == {}
        assert metrics.cache_stats == {}

    def test_metrics_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = TTSMetrics(total_requests=10, successful_requests=8)
        assert metrics.success_rate == 80.0
        
        # Test with zero requests
        empty_metrics = TTSMetrics()
        assert empty_metrics.success_rate == 0.0

    def test_metrics_average_cost_calculation(self):
        """Test average cost per request calculation."""
        metrics = TTSMetrics(total_requests=5, estimated_cost_usd=10.0)
        assert metrics.average_cost_per_request == 2.0
        
        # Test with zero requests
        empty_metrics = TTSMetrics()
        assert empty_metrics.average_cost_per_request == 0.0

    def test_metrics_to_dict(self):
        """Test metrics dictionary conversion."""
        metrics = TTSMetrics(
            total_requests=10,
            successful_requests=8,
            estimated_cost_usd=5.0
        )
        
        result = metrics.to_dict()
        
        assert isinstance(result, dict)
        assert result["total_requests"] == 10
        assert result["successful_requests"] == 8
        assert result["success_rate"] == 80.0
        assert result["estimated_cost_usd"] == 5.0
        assert result["average_cost_per_request"] == 0.5


class TestTTSCacheService:
    """Test TTS caching service."""

    @pytest.fixture
    def cache_service(self):
        """Create cache service instance."""
        return TTSCacheService(enabled=True, ttl_seconds=3600, max_cache_size=100)

    @pytest.mark.asyncio
    async def test_cache_enabled_get_miss(self, cache_service):
        """Test cache miss when enabled."""
        result = await cache_service.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_and_get_hit(self, cache_service):
        """Test cache set and subsequent hit."""
        mock_result = Mock(spec=TTSResult)
        mock_result.cached = False
        
        await cache_service.set("test_key", mock_result)
        retrieved = await cache_service.get("test_key")
        
        assert retrieved is not None
        assert retrieved.cached is True

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """Test cache when disabled."""
        disabled_cache = TTSCacheService(enabled=False)
        mock_result = Mock(spec=TTSResult)
        
        await disabled_cache.set("test_key", mock_result)
        result = await disabled_cache.get("test_key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_size_limit(self, cache_service):
        """Test cache size limit enforcement."""
        cache_service.max_cache_size = 2
        
        # Add items up to limit
        for i in range(3):
            mock_result = Mock(spec=TTSResult)
            await cache_service.set(f"key_{i}", mock_result)
        
        # Should only have 2 items (oldest removed)
        assert len(cache_service._cache) == 2

    @pytest.mark.asyncio
    async def test_cache_ttl_expiry(self, cache_service):
        """Test cache TTL expiry."""
        cache_service.ttl_seconds = 1  # Very short TTL
        mock_result = Mock(spec=TTSResult)
        
        await cache_service.set("test_key", mock_result)
        
        # Mock time to simulate expiry
        with patch('src.application.services.audio_service.datetime') as mock_datetime:
            future_time = datetime.now(timezone.utc)
            mock_datetime.now.return_value = future_time
            
            result = await cache_service.get("test_key")
            # Should still be there if not enough time passed
            assert result is not None

    @pytest.mark.asyncio
    async def test_cache_invalidate(self, cache_service):
        """Test cache invalidation."""
        mock_result = Mock(spec=TTSResult)
        await cache_service.set("test_key", mock_result)
        
        await cache_service.invalidate("test_key")
        result = await cache_service.get("test_key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_clear(self, cache_service):
        """Test cache clearing."""
        # Add multiple items
        for i in range(3):
            mock_result = Mock(spec=TTSResult)
            await cache_service.set(f"key_{i}", mock_result)
        
        await cache_service.clear()
        
        assert len(cache_service._cache) == 0

    def test_cache_stats(self, cache_service):
        """Test cache statistics."""
        stats = cache_service.get_stats()
        
        assert isinstance(stats, dict)
        assert stats["enabled"] is True
        assert stats["size"] == 0
        assert stats["max_size"] == 100
        assert stats["ttl_seconds"] == 3600


class TestAudioService:
    """Test Audio Service functionality."""

    @pytest.fixture
    def audio_service(self):
        """Create audio service with mocked dependencies."""
        mock_stt = AsyncMock()
        mock_tts = AsyncMock()
        mock_validation = AsyncMock()
        mock_streaming = AsyncMock()
        mock_safety = AsyncMock()
        mock_cache = AsyncMock()
        
        return AudioService(
            stt_provider=mock_stt,
            tts_service=mock_tts,
            validation_service=mock_validation,
            streaming_service=mock_streaming,
            safety_service=mock_safety,
            cache_service=mock_cache
        )

    @pytest.mark.asyncio
    async def test_process_audio_success(self, audio_service):
        """Test successful audio processing."""
        # Setup mocks
        mock_audio_data = b"fake_audio_data"
        mock_stream = AsyncMock()
        
        audio_service.streaming_service.process_stream.return_value = mock_audio_data
        audio_service.validation_service.validate_audio.return_value = Mock(is_valid=True)
        audio_service.safety_service.check_audio_safety.return_value = Mock(is_safe=True)
        audio_service.safety_service.check_text_safety.return_value = Mock(is_safe=True, recommendations=[])
        
        # Mock STT result
        mock_stt_result = Mock()
        mock_stt_result.text = "Hello world"
        audio_service.stt_provider.transcribe.return_value = mock_stt_result
        
        # Mock TTS result
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"tts_audio_data"
        mock_tts_result.provider_name = "openai"
        mock_tts_result.cached = False
        mock_tts_result.duration_seconds = 2.5
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        result = await audio_service.process_audio(mock_stream)
        
        assert result["success"] is True
        assert result["text"] == "Hello world"
        assert result["tts_audio"] == b"tts_audio_data"
        assert result["child_safe"] is True
        assert "processing_time_ms" in result
        assert "tts_metadata" in result

    @pytest.mark.asyncio
    async def test_process_audio_validation_failure(self, audio_service):
        """Test audio processing with validation failure."""
        mock_stream = AsyncMock()
        mock_audio_data = b"invalid_audio"
        
        audio_service.streaming_service.process_stream.return_value = mock_audio_data
        audio_service.validation_service.validate_audio.return_value = Mock(
            is_valid=False, 
            issues=["invalid_format"]
        )
        
        with pytest.raises(AudioProcessingError, match="Validation failed"):
            await audio_service.process_audio(mock_stream)

    @pytest.mark.asyncio
    async def test_process_audio_safety_failure(self, audio_service):
        """Test audio processing with safety failure."""
        mock_stream = AsyncMock()
        mock_audio_data = b"unsafe_audio"
        
        audio_service.streaming_service.process_stream.return_value = mock_audio_data
        audio_service.validation_service.validate_audio.return_value = Mock(is_valid=True)
        audio_service.safety_service.check_audio_safety.return_value = Mock(
            is_safe=False,
            violations=["inappropriate_content"]
        )
        
        with pytest.raises(AudioProcessingError, match="Safety check failed"):
            await audio_service.process_audio(mock_stream)

    @pytest.mark.asyncio
    async def test_convert_text_to_speech_success(self, audio_service):
        """Test successful text-to-speech conversion."""
        text = "Hello world"
        
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"tts_audio_data"
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        result = await audio_service.convert_text_to_speech(text)
        
        assert result == b"tts_audio_data"
        audio_service.tts_service.synthesize_speech.assert_called_once()

    @pytest.mark.asyncio
    async def test_convert_text_to_speech_with_voice_settings(self, audio_service):
        """Test TTS conversion with voice settings."""
        text = "Hello world"
        voice_settings = {"voice_id": "alloy", "speed": 1.2}
        
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"tts_audio_data"
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        result = await audio_service.convert_text_to_speech(text, voice_settings)
        
        assert result == b"tts_audio_data"

    @pytest.mark.asyncio
    async def test_convert_text_to_speech_tts_error(self, audio_service):
        """Test TTS conversion with TTS service error."""
        text = "Hello world"
        
        audio_service.tts_service.synthesize_speech.side_effect = TTSError("TTS failed")
        
        with pytest.raises(AudioProcessingError, match="TTS service error"):
            await audio_service.convert_text_to_speech(text)

    @pytest.mark.asyncio
    async def test_convert_text_to_speech_provider_error(self, audio_service):
        """Test TTS conversion with provider error."""
        text = "Hello world"
        
        audio_service.tts_service.synthesize_speech.side_effect = TTSProviderError("Provider failed")
        
        with pytest.raises(AudioProcessingError, match="TTS provider error"):
            await audio_service.convert_text_to_speech(text)

    @pytest.mark.asyncio
    async def test_convert_speech_to_text(self, audio_service):
        """Test speech-to-text conversion."""
        audio_data = b"audio_data"
        
        mock_stt_result = Mock()
        mock_stt_result.text = "Transcribed text"
        audio_service.stt_provider.transcribe.return_value = mock_stt_result
        
        result = await audio_service.convert_speech_to_text(audio_data)
        
        assert result == "Transcribed text"
        audio_service.stt_provider.transcribe.assert_called_once_with(audio_data)

    @pytest.mark.asyncio
    async def test_process_stream(self, audio_service):
        """Test stream processing."""
        mock_stream = AsyncMock()
        mock_audio_data = b"stream_audio"
        
        audio_service.streaming_service.process_stream.return_value = mock_audio_data
        
        mock_stt_result = Mock()
        mock_stt_result.text = "Stream text"
        audio_service.stt_provider.transcribe.return_value = mock_stt_result
        
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"stream_tts"
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        text, audio = await audio_service.process_stream(mock_stream)
        
        assert text == "Stream text"
        assert audio == b"stream_tts"

    @pytest.mark.asyncio
    async def test_validate_audio_safety(self, audio_service):
        """Test audio safety validation."""
        audio_data = b"audio_data"
        
        audio_service.safety_service.check_audio_safety.return_value = Mock(is_safe=True)
        
        result = await audio_service.validate_audio_safety(audio_data)
        
        assert result is True
        audio_service.safety_service.check_audio_safety.assert_called_once_with(audio_data)

    @pytest.mark.asyncio
    async def test_get_service_health(self, audio_service):
        """Test service health check."""
        # Setup service state
        audio_service._request_count = 100
        audio_service._success_count = 95
        audio_service._tts_request_count = 50
        audio_service._cache_hits = 20
        
        # Mock TTS service health
        audio_service.tts_service.health_check.return_value = {"status": "healthy"}
        
        # Mock cache service health
        audio_service.cache_service.get_comprehensive_stats.return_value = {"cache_size": 10}
        
        health = await audio_service.get_service_health()
        
        assert isinstance(health, dict)
        assert health["status"] in ["healthy", "degraded"]
        assert "audio_processing" in health
        assert "tts_service" in health
        assert "production_cache" in health
        assert health["audio_processing"]["success_rate"] == 0.95

    @pytest.mark.asyncio
    async def test_get_available_voices(self, audio_service):
        """Test getting available voices."""
        mock_voices = [Mock(), Mock()]
        audio_service.tts_service.get_available_voices.return_value = mock_voices
        
        voices = await audio_service.get_available_voices(language="en", child_safe_only=True)
        
        assert voices == mock_voices
        audio_service.tts_service.get_available_voices.assert_called_once_with("en", True)

    @pytest.mark.asyncio
    async def test_estimate_tts_cost(self, audio_service):
        """Test TTS cost estimation."""
        text = "Hello world"
        expected_cost = {"estimated_cost": 0.05, "character_count": 11}
        
        audio_service.tts_service.estimate_cost.return_value = expected_cost
        
        result = await audio_service.estimate_tts_cost(text)
        
        assert result == expected_cost
        audio_service.tts_service.estimate_cost.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tts_metrics(self, audio_service):
        """Test TTS metrics retrieval."""
        # Setup metrics
        audio_service._metrics = TTSMetrics(total_requests=10, successful_requests=8)
        audio_service._request_count = 100
        audio_service._tts_request_count = 50
        audio_service._cache_hits = 20
        
        # Mock cache service
        audio_service.cache_service.health_check.return_value = {"status": "healthy"}
        audio_service.cache_service.get_comprehensive_stats.return_value = {"cache_size": 10}
        
        metrics = await audio_service.get_tts_metrics()
        
        assert isinstance(metrics, dict)
        assert "tts_metrics" in metrics
        assert "timestamp" in metrics
        assert "uptime_info" in metrics
        assert "production_cache_metrics" in metrics
        assert metrics["uptime_info"]["total_audio_requests"] == 100
        assert metrics["uptime_info"]["cache_hits"] == 20

    def test_generate_cache_key(self, audio_service):
        """Test cache key generation."""
        from src.interfaces.providers.tts_provider import TTSRequest, TTSConfiguration, VoiceProfile
        from src.shared.audio_types import VoiceGender, VoiceEmotion, AudioFormat, AudioQuality
        
        voice_profile = VoiceProfile(
            voice_id="alloy",
            name="Alloy",
            language="en-US",
            gender=VoiceGender.NEUTRAL,
            age_range="adult",
            description="Test voice"
        )
        
        config = TTSConfiguration(
            voice_profile=voice_profile,
            emotion=VoiceEmotion.NEUTRAL,
            speed=1.0,
            audio_format=AudioFormat.MP3,
            quality=AudioQuality.STANDARD
        )
        
        request = TTSRequest(text="Hello world", config=config)
        
        key = audio_service._generate_cache_key(request)
        
        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 hash length

    def test_update_error_metrics(self, audio_service):
        """Test error metrics updating."""
        initial_failed = audio_service._metrics.failed_requests
        
        audio_service._update_error_metrics("test_error")
        
        assert audio_service._metrics.failed_requests == initial_failed + 1
        assert "test_error" in audio_service._metrics.provider_errors
        assert audio_service._metrics.provider_errors["test_error"] == 1


class TestAudioServiceErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def audio_service(self):
        """Create audio service with mocked dependencies."""
        mock_stt = AsyncMock()
        mock_tts = AsyncMock()
        mock_validation = AsyncMock()
        mock_streaming = AsyncMock()
        mock_safety = AsyncMock()
        
        return AudioService(
            stt_provider=mock_stt,
            tts_service=mock_tts,
            validation_service=mock_validation,
            streaming_service=mock_streaming,
            safety_service=mock_safety
        )

    @pytest.mark.asyncio
    async def test_process_audio_streaming_error(self, audio_service):
        """Test audio processing with streaming error."""
        mock_stream = AsyncMock()
        
        audio_service.streaming_service.process_stream.side_effect = Exception("Stream error")
        
        with pytest.raises(AudioProcessingError, match="Processing failed"):
            await audio_service.process_audio(mock_stream)

    @pytest.mark.asyncio
    async def test_process_audio_stt_error(self, audio_service):
        """Test audio processing with STT error."""
        mock_stream = AsyncMock()
        mock_audio_data = b"audio_data"
        
        audio_service.streaming_service.process_stream.return_value = mock_audio_data
        audio_service.validation_service.validate_audio.return_value = Mock(is_valid=True)
        audio_service.safety_service.check_audio_safety.return_value = Mock(is_safe=True)
        audio_service.stt_provider.transcribe.side_effect = Exception("STT error")
        
        with pytest.raises(AudioProcessingError, match="Processing failed"):
            await audio_service.process_audio(mock_stream)

    @pytest.mark.asyncio
    async def test_get_available_voices_error(self, audio_service):
        """Test error handling when getting available voices."""
        audio_service.tts_service.get_available_voices.side_effect = Exception("TTS error")
        
        voices = await audio_service.get_available_voices()
        
        assert voices == []

    @pytest.mark.asyncio
    async def test_estimate_tts_cost_error(self, audio_service):
        """Test error handling in cost estimation."""
        audio_service.tts_service.estimate_cost.side_effect = Exception("Cost error")
        
        result = await audio_service.estimate_tts_cost("test")
        
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_service_health_cache_error(self, audio_service):
        """Test service health with cache service error."""
        audio_service._request_count = 10
        audio_service._success_count = 8
        audio_service.tts_service.health_check.return_value = {"status": "healthy"}
        audio_service.cache_service = Mock()
        audio_service.cache_service.get_comprehensive_stats.side_effect = Exception("Cache error")
        
        health = await audio_service.get_service_health()
        
        assert "production_cache" in health
        assert "error" in health["production_cache"]


class TestAudioServiceIntegration:
    """Integration tests for AudioService workflows."""

    @pytest.fixture
    def audio_service(self):
        """Create audio service with mocked dependencies."""
        mock_stt = AsyncMock()
        mock_tts = AsyncMock()
        mock_validation = AsyncMock()
        mock_streaming = AsyncMock()
        mock_safety = AsyncMock()
        mock_cache = AsyncMock()
        
        return AudioService(
            stt_provider=mock_stt,
            tts_service=mock_tts,
            validation_service=mock_validation,
            streaming_service=mock_streaming,
            safety_service=mock_safety,
            cache_service=mock_cache
        )

    @pytest.mark.asyncio
    async def test_complete_audio_workflow(self, audio_service):
        """Test complete audio processing workflow."""
        # Mock input stream
        mock_stream = AsyncMock()
        mock_audio_data = b"complete_audio_data"
        
        # Setup service responses
        audio_service.streaming_service.process_stream.return_value = mock_audio_data
        audio_service.validation_service.validate_audio.return_value = Mock(is_valid=True)
        audio_service.safety_service.check_audio_safety.return_value = Mock(
            is_safe=True, child_age=6
        )
        audio_service.safety_service.check_text_safety.return_value = Mock(
            is_safe=True, recommendations=[]
        )
        
        # Mock STT
        mock_stt_result = Mock()
        mock_stt_result.text = "Hello, how are you today?"
        audio_service.stt_provider.transcribe.return_value = mock_stt_result
        
        # Mock TTS with cache miss
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"synthesized_speech"
        mock_tts_result.provider_name = "openai"
        mock_tts_result.cached = False
        mock_tts_result.duration_seconds = 3.2
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        audio_service.cache_service.get.return_value = None  # Cache miss
        
        result = await audio_service.process_audio(mock_stream)
        
        # Verify complete workflow
        assert result["success"] is True
        assert result["text"] == "Hello, how are you today?"
        assert result["tts_audio"] == b"synthesized_speech"
        assert result["child_safe"] is True
        assert result["tts_metadata"]["provider"] == "openai"
        assert result["tts_metadata"]["cached"] is False
        assert result["tts_metadata"]["duration_seconds"] == 3.2
        
        # Verify all services were called
        audio_service.streaming_service.process_stream.assert_called_once()
        audio_service.validation_service.validate_audio.assert_called_once()
        audio_service.safety_service.check_audio_safety.assert_called_once()
        audio_service.stt_provider.transcribe.assert_called_once()
        audio_service.tts_service.synthesize_speech.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_with_text_filtering(self, audio_service):
        """Test workflow with unsafe text that needs filtering."""
        mock_stream = AsyncMock()
        mock_audio_data = b"audio_with_unsafe_text"
        
        # Setup services
        audio_service.streaming_service.process_stream.return_value = mock_audio_data
        audio_service.validation_service.validate_audio.return_value = Mock(is_valid=True)
        audio_service.safety_service.check_audio_safety.return_value = Mock(is_safe=True)
        
        # Mock unsafe text detection and filtering
        audio_service.safety_service.check_text_safety.return_value = Mock(
            is_safe=False, recommendations=["filter_content"]
        )
        audio_service.safety_service.filter_content.return_value = "Hello, let's play!"
        
        # Mock STT with unsafe content
        mock_stt_result = Mock()
        mock_stt_result.text = "Hello, let's fight!"
        audio_service.stt_provider.transcribe.return_value = mock_stt_result
        
        # Mock TTS
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"filtered_speech"
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        result = await audio_service.process_audio(mock_stream)
        
        # Verify filtering was applied
        audio_service.safety_service.filter_content.assert_called_once_with("Hello, let's fight!")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_workflow_with_cache_hit(self, audio_service):
        """Test workflow with TTS cache hit."""
        mock_stream = AsyncMock()
        mock_audio_data = b"cached_audio_data"
        
        # Setup services
        audio_service.streaming_service.process_stream.return_value = mock_audio_data
        audio_service.validation_service.validate_audio.return_value = Mock(is_valid=True)
        audio_service.safety_service.check_audio_safety.return_value = Mock(is_safe=True)
        audio_service.safety_service.check_text_safety.return_value = Mock(
            is_safe=True, recommendations=[]
        )
        
        # Mock STT
        mock_stt_result = Mock()
        mock_stt_result.text = "Cached text"
        audio_service.stt_provider.transcribe.return_value = mock_stt_result
        
        # Mock cache hit
        cached_tts_result = Mock(spec=TTSResult)
        cached_tts_result.audio_data = b"cached_speech"
        cached_tts_result.cached = True
        cached_tts_result.provider_name = "openai"
        cached_tts_result.duration_seconds = 2.1
        audio_service.cache_service.get.return_value = cached_tts_result
        
        result = await audio_service.process_audio(mock_stream)
        
        # Verify cache was used
        assert result["tts_metadata"]["cached"] is True
        audio_service.tts_service.synthesize_speech.assert_not_called()  # Should skip TTS call

    @pytest.mark.asyncio
    async def test_workflow_with_child_age_context(self, audio_service):
        """Test workflow with child age for safety context."""
        mock_stream = AsyncMock()
        mock_audio_data = b"child_audio_data"
        
        # Setup services with child age
        audio_service.streaming_service.process_stream.return_value = mock_audio_data
        audio_service.validation_service.validate_audio.return_value = Mock(is_valid=True)
        
        # Mock safety result with child age
        safety_result = Mock(is_safe=True)
        safety_result.child_age = 7
        audio_service.safety_service.check_audio_safety.return_value = safety_result
        audio_service.safety_service.check_text_safety.return_value = Mock(
            is_safe=True, recommendations=[]
        )
        
        # Mock STT
        mock_stt_result = Mock()
        mock_stt_result.text = "Child-appropriate content"
        audio_service.stt_provider.transcribe.return_value = mock_stt_result
        
        # Mock TTS
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"child_speech"
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        result = await audio_service.process_audio(mock_stream)
        
        # Verify child age was passed to TTS
        call_args = audio_service.tts_service.synthesize_speech.call_args
        tts_request = call_args[0][0]
        assert tts_request.safety_context is not None
        assert tts_request.safety_context.child_age == 7

    @pytest.mark.asyncio
    async def test_concurrent_audio_processing(self, audio_service):
        """Test concurrent audio processing requests."""
        import asyncio
        
        # Setup mock responses
        audio_service.streaming_service.process_stream.return_value = b"concurrent_audio"
        audio_service.validation_service.validate_audio.return_value = Mock(is_valid=True)
        audio_service.safety_service.check_audio_safety.return_value = Mock(is_safe=True)
        audio_service.safety_service.check_text_safety.return_value = Mock(
            is_safe=True, recommendations=[]
        )
        
        # Mock STT with different results for each request
        def mock_transcribe(audio_data):
            result = Mock()
            result.text = f"Transcribed {len(audio_data)} bytes"
            return result
        
        audio_service.stt_provider.transcribe.side_effect = mock_transcribe
        
        # Mock TTS
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"concurrent_speech"
        mock_tts_result.cached = False
        mock_tts_result.provider_name = "openai"
        mock_tts_result.duration_seconds = 1.5
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        # Create multiple concurrent requests
        streams = [AsyncMock() for _ in range(5)]
        tasks = [audio_service.process_audio(stream) for stream in streams]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all requests completed successfully
        assert len(results) == 5
        for result in results:
            assert result["success"] is True
            assert "Transcribed" in result["text"]

    @pytest.mark.asyncio
    async def test_metrics_tracking_workflow(self, audio_service):
        """Test that metrics are properly tracked during workflow."""
        mock_stream = AsyncMock()
        
        # Setup successful workflow
        audio_service.streaming_service.process_stream.return_value = b"metrics_audio"
        audio_service.validation_service.validate_audio.return_value = Mock(is_valid=True)
        audio_service.safety_service.check_audio_safety.return_value = Mock(is_safe=True)
        audio_service.safety_service.check_text_safety.return_value = Mock(
            is_safe=True, recommendations=[]
        )
        
        mock_stt_result = Mock()
        mock_stt_result.text = "Metrics test"
        audio_service.stt_provider.transcribe.return_value = mock_stt_result
        
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"metrics_speech"
        mock_tts_result.cached = False
        mock_tts_result.estimated_cost = 0.02
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        # Check initial metrics
        initial_requests = audio_service._request_count
        initial_tts_requests = audio_service._tts_request_count
        
        await audio_service.process_audio(mock_stream)
        
        # Verify metrics were updated
        assert audio_service._request_count == initial_requests + 1
        assert audio_service._success_count > 0
        assert audio_service._tts_request_count == initial_tts_requests + 1
        assert audio_service._metrics.total_requests > 0
        assert audio_service._metrics.successful_requests > 0


class TestAudioServicePerformance:
    """Performance and load testing for AudioService."""

    @pytest.fixture
    def audio_service(self):
        """Create audio service for performance testing."""
        mock_stt = AsyncMock()
        mock_tts = AsyncMock()
        mock_validation = AsyncMock()
        mock_streaming = AsyncMock()
        mock_safety = AsyncMock()
        
        return AudioService(
            stt_provider=mock_stt,
            tts_service=mock_tts,
            validation_service=mock_validation,
            streaming_service=mock_streaming,
            safety_service=mock_safety
        )

    @pytest.mark.asyncio
    async def test_high_volume_tts_requests(self, audio_service):
        """Test handling high volume of TTS requests."""
        import time
        
        # Setup fast mock responses
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"fast_tts"
        mock_tts_result.cached = False
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        # Measure performance
        start_time = time.time()
        
        tasks = []
        for i in range(50):  # 50 concurrent requests
            task = audio_service.convert_text_to_speech(f"Test text {i}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify all requests completed
        assert len(results) == 50
        for result in results:
            assert result == b"fast_tts"
        
        # Performance should be reasonable (less than 5 seconds for 50 requests)
        assert processing_time < 5.0
        
        # Verify metrics were updated
        assert audio_service._metrics.total_requests == 50
        assert audio_service._metrics.successful_requests == 50

    @pytest.mark.asyncio
    async def test_memory_efficiency_large_text(self, audio_service):
        """Test memory efficiency with large text inputs."""
        # Create large text (10KB)
        large_text = "This is a test sentence. " * 400  # ~10KB
        
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"large_text_tts" * 1000  # ~15KB response
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        result = await audio_service.convert_text_to_speech(large_text)
        
        # Should handle large text without issues
        assert len(result) > 10000
        assert audio_service._metrics.total_characters_processed >= len(large_text)

    def test_cache_key_consistency(self, audio_service):
        """Test cache key generation consistency."""
        from src.interfaces.providers.tts_provider import TTSRequest, TTSConfiguration, VoiceProfile
        from src.shared.audio_types import VoiceGender, VoiceEmotion, AudioFormat, AudioQuality
        
        # Create identical requests
        voice_profile = VoiceProfile(
            voice_id="alloy",
            name="Alloy",
            language="en-US",
            gender=VoiceGender.NEUTRAL,
            age_range="adult",
            description="Test voice"
        )
        
        config = TTSConfiguration(
            voice_profile=voice_profile,
            emotion=VoiceEmotion.NEUTRAL,
            speed=1.0,
            audio_format=AudioFormat.MP3,
            quality=AudioQuality.STANDARD
        )
        
        request1 = TTSRequest(text="Hello world", config=config)
        request2 = TTSRequest(text="Hello world", config=config)
        
        key1 = audio_service._generate_cache_key(request1)
        key2 = audio_service._generate_cache_key(request2)
        
        # Should generate identical keys for identical requests
        assert key1 == key2
        
        # Different text should generate different keys
        request3 = TTSRequest(text="Different text", config=config)
        key3 = audio_service._generate_cache_key(request3)
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_error_recovery_performance(self, audio_service):
        """Test performance under error conditions."""
        import time
        
        # Setup intermittent failures
        call_count = 0
        def mock_tts_with_failures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd call
                raise TTSError("Intermittent failure")
            
            result = Mock(spec=TTSResult)
            result.audio_data = b"recovered_tts"
            return result
        
        audio_service.tts_service.synthesize_speech.side_effect = mock_tts_with_failures
        
        start_time = time.time()
        
        # Execute requests with expected failures
        successful_requests = 0
        failed_requests = 0
        
        for i in range(15):
            try:
                await audio_service.convert_text_to_speech(f"Test {i}")
                successful_requests += 1
            except AudioProcessingError:
                failed_requests += 1
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should have appropriate success/failure ratio
        assert successful_requests > 0
        assert failed_requests > 0
        assert successful_requests + failed_requests == 15
        
        # Error handling shouldn't significantly impact performance
        assert processing_time < 3.0
        
        # Metrics should reflect errors
        assert audio_service._metrics.failed_requests > 0
        assert audio_service._metrics.error_rate > 0


class TestAudioServiceEdgeCases:
    """Edge case testing for AudioService."""

    @pytest.fixture
    def audio_service(self):
        """Create audio service for edge case testing."""
        mock_stt = AsyncMock()
        mock_tts = AsyncMock()
        mock_validation = AsyncMock()
        mock_streaming = AsyncMock()
        mock_safety = AsyncMock()
        
        return AudioService(
            stt_provider=mock_stt,
            tts_service=mock_tts,
            validation_service=mock_validation,
            streaming_service=mock_streaming,
            safety_service=mock_safety
        )

    @pytest.mark.asyncio
    async def test_empty_text_tts(self, audio_service):
        """Test TTS with empty text."""
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b""
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        result = await audio_service.convert_text_to_speech("")
        
        assert result == b""

    @pytest.mark.asyncio
    async def test_unicode_text_tts(self, audio_service):
        """Test TTS with Unicode text."""
        unicode_text = "Hello 世界! 🎵 Émojis and ñoños"
        
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"unicode_tts"
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        result = await audio_service.convert_text_to_speech(unicode_text)
        
        assert result == b"unicode_tts"
        # Verify character count includes Unicode properly
        assert audio_service._metrics.total_characters_processed >= len(unicode_text)

    @pytest.mark.asyncio
    async def test_very_long_text_tts(self, audio_service):
        """Test TTS with very long text."""
        # Create 50KB text
        long_text = "A" * 50000
        
        mock_tts_result = Mock(spec=TTSResult)
        mock_tts_result.audio_data = b"long_text_tts"
        audio_service.tts_service.synthesize_speech.return_value = mock_tts_result
        
        result = await audio_service.convert_text_to_speech(long_text)
        
        assert result == b"long_text_tts"
        assert audio_service._metrics.total_characters_processed >= 50000

    @pytest.mark.asyncio
    async def test_special_characters_in_cache_key(self, audio_service):
        """Test cache key generation with special characters."""
        from src.interfaces.providers.tts_provider import TTSRequest, TTSConfiguration, VoiceProfile
        from src.shared.audio_types import VoiceGender, VoiceEmotion, AudioFormat, AudioQuality
        
        voice_profile = VoiceProfile(
            voice_id="special|voice",
            name="Special Voice",
            language="en-US",
            gender=VoiceGender.NEUTRAL,
            age_range="adult",
            description="Voice with special chars"
        )
        
        config = TTSConfiguration(
            voice_profile=voice_profile,
            emotion=VoiceEmotion.NEUTRAL,
            speed=1.0,
            audio_format=AudioFormat.MP3,
            quality=AudioQuality.STANDARD
        )
        
        # Text with special characters that could break cache key generation
        special_text = "Hello|World!@#$%^&*()+={}[]\\|;:'\",.<>?/~`"
        request = TTSRequest(text=special_text, config=config)
        
        # Should not raise exception
        key = audio_service._generate_cache_key(request)
        assert isinstance(key, str)
        assert len(key) == 64

    @pytest.mark.asyncio
    async def test_service_health_with_no_requests(self, audio_service):
        """Test service health when no requests have been made."""
        audio_service.tts_service.health_check.return_value = {"status": "healthy"}
        
        health = await audio_service.get_service_health()
        
        assert health["status"] in ["healthy", "degraded"]
        assert health["audio_processing"]["total_requests"] == 0
        assert health["audio_processing"]["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_tts_timeout_handling(self, audio_service):
        """Test handling of TTS timeout errors."""
        audio_service.tts_service.synthesize_speech.side_effect = TimeoutError("TTS timeout")
        
        with pytest.raises(AudioProcessingError, match="TTS request timeout"):
            await audio_service.convert_text_to_speech("Test timeout")
        
        # Verify timeout error was recorded
        assert "timeout_error" in audio_service._metrics.provider_errors
        assert audio_service._metrics.provider_errors["timeout_error"] == 1

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, audio_service):
        """Test handling of validation errors in TTS."""
        audio_service.tts_service.synthesize_speech.side_effect = ValueError("Invalid parameters")
        
        with pytest.raises(AudioProcessingError, match="Invalid TTS parameters"):
            await audio_service.convert_text_to_speech("Test validation")
        
        # Verify validation error was recorded
        assert "validation_error" in audio_service._metrics.provider_errors

    def test_safe_logging_with_malicious_input(self, audio_service):
        """Test safe logging prevents injection attacks."""
        # Test with potential log injection characters
        malicious_message = "Test\nINJECTED_LOG_ENTRY\rMALICIOUS\t\x00NULL"
        
        # Should not raise exception and should sanitize
        audio_service._safe_log(malicious_message)
        
        # Test with extremely long message
        long_message = "A" * 2000
        audio_service._safe_log(long_message)
        
        # Should handle without issues (would be truncated internally)