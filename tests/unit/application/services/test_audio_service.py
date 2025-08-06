"""
Tests for AudioService - real audio processing functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
import io
from datetime import datetime

from src.application.services.audio_service import AudioService, TTSCacheService
from src.interfaces.providers.tts_provider import (
    ITTSService, TTSRequest, TTSResult, TTSConfiguration, VoiceProfile, 
    VoiceGender, AudioFormat, AudioQuality
)


class TestAudioService:
    @pytest.fixture
    def mock_stt_provider(self):
        provider = Mock()
        provider.transcribe = AsyncMock()
        return provider

    @pytest.fixture
    def mock_tts_service(self):
        """Mock unified TTS service."""
        service = Mock(spec=ITTSService)
        service.synthesize_speech = AsyncMock()
        service.get_available_voices = AsyncMock()
        service.health_check = AsyncMock()
        service.estimate_cost = AsyncMock()
        return service

    @pytest.fixture
    def mock_cache_service(self):
        return Mock(spec=TTSCacheService)

    @pytest.fixture
    def audio_service(self, mock_stt_provider, mock_tts_service, mock_cache_service):
        return AudioService(
            stt_provider=mock_stt_provider,
            tts_service=mock_tts_service,
            validation_service=None,
            streaming_service=None, 
            safety_service=None,
            cache_service=mock_cache_service
        )

    @pytest.mark.asyncio
    async def test_convert_text_to_speech_success(self, audio_service, mock_tts_service):
        """Test successful TTS conversion using unified interface."""
        # Setup
        mock_result = TTSResult(
            audio_data=b"fake_audio_data",
            request_id="test_123",
            provider_name="openai",
            config=TTSConfiguration(
                voice_profile=VoiceProfile("alloy", "Alloy", "en-US", VoiceGender.NEUTRAL, "adult", "Test voice")
            ),
            duration_seconds=2.5,
            sample_rate=22050,
            bit_rate=128000,
            file_size_bytes=1024,
            format=AudioFormat.MP3,
            processing_time_ms=150.0,
            provider_latency_ms=120.0,
            created_at=datetime.now()
        )
        mock_tts_service.synthesize_speech.return_value = mock_result
        
        # Execute
        text = "Hello, this is a test message"
        voice_settings = {"voice_id": "alloy", "speed": 1.0}
        result = await audio_service.convert_text_to_speech(text, voice_settings)
        
        # Verify
        assert result == b"fake_audio_data"
        mock_tts_service.synthesize_speech.assert_called_once()
        
        # Verify the request structure
        call_args = mock_tts_service.synthesize_speech.call_args[0][0]
        assert isinstance(call_args, TTSRequest)
        assert call_args.text == text
        assert call_args.config.voice_profile.voice_id == "alloy"
        assert call_args.config.speed == 1.0

    @pytest.mark.asyncio
    async def test_generate_speech_empty_text(self, audio_service):
        """Test speech generation with empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            await audio_service.generate_speech("", uuid4())

    @pytest.mark.asyncio
    async def test_generate_speech_text_too_long(self, audio_service):
        """Test speech generation with text too long."""
        long_text = "a" * 5001  # Exceeds limit
        
        with pytest.raises(ValueError, match="Text too long"):
            await audio_service.generate_speech(long_text, uuid4())

    @pytest.mark.asyncio
    async def test_process_audio_input_success(self, audio_service, mock_speech_processor):
        """Test successful audio input processing."""
        audio_data = b"fake_audio_data"
        child_id = uuid4()
        
        mock_speech_processor.process_audio.return_value = {
            "text": "Hello AI teddy",
            "confidence": 0.95,
            "language": "en"
        }
        
        result = await audio_service.process_audio_input(audio_data, child_id)
        
        assert result["text"] == "Hello AI teddy"
        assert result["confidence"] == 0.95
        mock_speech_processor.process_audio.assert_called_once_with(audio_data, child_id)

    @pytest.mark.asyncio
    async def test_process_audio_input_empty_data(self, audio_service):
        """Test audio processing with empty data."""
        with pytest.raises(ValueError, match="Audio data cannot be empty"):
            await audio_service.process_audio_input(b"", uuid4())

    @pytest.mark.asyncio
    async def test_process_audio_input_invalid_format(self, audio_service, mock_speech_processor):
        """Test audio processing with invalid format."""
        audio_data = b"invalid_audio_format"
        child_id = uuid4()
        
        mock_speech_processor.process_audio.side_effect = Exception("Invalid audio format")
        
        with pytest.raises(Exception, match="Invalid audio format"):
            await audio_service.process_audio_input(audio_data, child_id)


class TestTTSCacheService:
    """Test TTS caching functionality."""
    
    @pytest.fixture
    def cache_service(self):
        return TTSCacheService(enabled=True, ttl_seconds=60, max_cache_size=10)
    
    @pytest.fixture
    def sample_tts_result(self):
        return TTSResult(
            audio_data=b"cached_audio",
            request_id="cache_test",
            provider_name="test_provider",
            config=TTSConfiguration(
                voice_profile=VoiceProfile("test", "Test", "en-US", VoiceGender.NEUTRAL, "adult", "Test voice")
            ),
            duration_seconds=1.0,
            sample_rate=22050,
            bit_rate=128000,
            file_size_bytes=512,
            format=AudioFormat.MP3,
            processing_time_ms=100.0,
            provider_latency_ms=80.0,
            created_at=datetime.now()
        )
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache_service, sample_tts_result):
        """Test caching and retrieving TTS results."""
        cache_key = "test_cache_key"
        
        # Set cache
        await cache_service.set(cache_key, sample_tts_result)
        
        # Get from cache
        cached_result = await cache_service.get(cache_key)
        
        assert cached_result is not None
        assert cached_result.audio_data == b"cached_audio"
        assert cached_result.cached is True
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_service):
        """Test cache miss scenario."""
        result = await cache_service.get("nonexistent_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_service):
        """Test cache statistics."""
        stats = cache_service.get_stats()
        
        assert stats["enabled"] is True
        assert stats["size"] == 0
        assert stats["max_size"] == 10
        assert stats["ttl_seconds"] == 60

    @pytest.mark.asyncio
    async def test_validate_audio_format_valid(self, audio_service):
        """Test audio format validation with valid formats."""
        valid_formats = [b"RIFF", b"OggS", b"ID3"]
        
        for format_header in valid_formats:
            audio_data = format_header + b"rest_of_audio_data"
            result = await audio_service._validate_audio_format(audio_data)
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_audio_format_invalid(self, audio_service):
        """Test audio format validation with invalid format."""
        invalid_audio = b"INVALID_FORMAT_HEADER"
        
        result = await audio_service._validate_audio_format(invalid_audio)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_supported_voices(self, audio_service, mock_tts_provider):
        """Test getting supported voices."""
        mock_voices = [
            {"id": "child_friendly", "name": "Child Friendly", "language": "en"},
            {"id": "storyteller", "name": "Story Teller", "language": "en"}
        ]
        mock_tts_provider.get_supported_voices.return_value = mock_voices
        
        result = await audio_service.get_supported_voices()
        
        assert result == mock_voices
        mock_tts_provider.get_supported_voices.assert_called_once()

    @pytest.mark.asyncio
    async def test_adjust_voice_for_age_young_child(self, audio_service):
        """Test voice adjustment for young child."""
        voice_settings = {"voice": "default", "speed": 1.0, "pitch": 1.0}
        child_age = 4
        
        result = await audio_service._adjust_voice_for_age(voice_settings, child_age)
        
        assert result["speed"] == 0.8  # Slower for young children
        assert result["pitch"] == 1.2  # Higher pitch

    @pytest.mark.asyncio
    async def test_adjust_voice_for_age_older_child(self, audio_service):
        """Test voice adjustment for older child."""
        voice_settings = {"voice": "default", "speed": 1.0, "pitch": 1.0}
        child_age = 12
        
        result = await audio_service._adjust_voice_for_age(voice_settings, child_age)
        
        assert result["speed"] == 1.0  # Normal speed
        assert result["pitch"] == 1.0  # Normal pitch

    @pytest.mark.asyncio
    async def test_generate_audio_response_with_emotion(self, audio_service, mock_tts_provider):
        """Test generating audio response with emotion."""
        text = "I'm so happy to talk with you!"
        child_id = uuid4()
        emotion = "happy"
        
        mock_tts_provider.generate_speech.return_value = "https://example.com/happy_audio.mp3"
        
        result = await audio_service.generate_audio_response(text, child_id, emotion)
        
        assert result == "https://example.com/happy_audio.mp3"
        # Verify emotion was applied to voice settings
        call_args = mock_tts_provider.generate_speech.call_args
        voice_settings = call_args[0][2]
        assert "emotion" in voice_settings
        assert voice_settings["emotion"] == "happy"

    @pytest.mark.asyncio
    async def test_cleanup_old_audio_files(self, audio_service):
        """Test cleanup of old audio files."""
        with patch('os.listdir') as mock_listdir:
            with patch('os.path.getmtime') as mock_getmtime:
                with patch('os.remove') as mock_remove:
                    # Mock old files
                    mock_listdir.return_value = ["old_audio.mp3", "recent_audio.mp3"]
                    mock_getmtime.side_effect = [1000000, 9999999999]  # Old and recent timestamps
                    
                    cleaned_count = await audio_service.cleanup_old_audio_files()
                    
                    assert cleaned_count == 1
                    mock_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_audio_stats(self, audio_service):
        """Test getting audio service statistics."""
        # Simulate some usage
        audio_service._speech_requests = 100
        audio_service._processing_requests = 50
        audio_service._total_audio_duration = 3600  # 1 hour
        
        stats = await audio_service.get_audio_stats()
        
        assert stats["speech_requests"] == 100
        assert stats["processing_requests"] == 50
        assert stats["total_duration_seconds"] == 3600
        assert "average_duration" in stats

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, audio_service, mock_tts_provider, mock_speech_processor):
        """Test health check when all services are healthy."""
        mock_tts_provider.health_check.return_value = {"status": "healthy"}
        mock_speech_processor.health_check.return_value = {"status": "healthy"}
        
        result = await audio_service.health_check()
        
        assert result["status"] == "healthy"
        assert result["tts_provider"]["status"] == "healthy"
        assert result["speech_processor"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, audio_service, mock_tts_provider, mock_speech_processor):
        """Test health check when one service is degraded."""
        mock_tts_provider.health_check.return_value = {"status": "degraded"}
        mock_speech_processor.health_check.return_value = {"status": "healthy"}
        
        result = await audio_service.health_check()
        
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_convert_audio_format(self, audio_service):
        """Test audio format conversion."""
        input_audio = b"fake_wav_data"
        target_format = "mp3"
        
        with patch('src.application.services.audio_service.convert_audio') as mock_convert:
            mock_convert.return_value = b"fake_mp3_data"
            
            result = await audio_service.convert_audio_format(input_audio, target_format)
            
            assert result == b"fake_mp3_data"
            mock_convert.assert_called_once_with(input_audio, target_format)

    @pytest.mark.asyncio
    async def test_apply_audio_filters_child_safe(self, audio_service):
        """Test applying child-safe audio filters."""
        audio_data = b"raw_audio_data"
        child_age = 6
        
        with patch('src.application.services.audio_service.apply_child_filters') as mock_filter:
            mock_filter.return_value = b"filtered_audio_data"
            
            result = await audio_service._apply_audio_filters(audio_data, child_age)
            
            assert result == b"filtered_audio_data"
            mock_filter.assert_called_once_with(audio_data, child_age)