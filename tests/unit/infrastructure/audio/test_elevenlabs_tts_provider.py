"""
Unit tests for ElevenLabsTTSProvider
Tests ElevenLabs TTS integration with child safety features
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.infrastructure.audio.elevenlabs_tts_provider import ElevenLabsTTSProvider
from src.interfaces.providers.tts_provider import (
    TTSRequest,
    TTSResult,
    VoiceProfile,
    ChildSafetyContext,
    AudioFormat,
    AudioQuality,
    VoiceEmotion,
    VoiceGender,
    TTSProviderError,
    TTSUnsafeContentError,
    TTSConfigurationError
)


class TestElevenLabsTTSProvider:
    """Test ElevenLabsTTSProvider functionality."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx client."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"mock_audio_data"
        mock_response.headers = {}
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        return mock_client

    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service."""
        mock_cache = Mock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        return mock_cache

    @pytest.fixture
    def tts_provider(self, mock_cache_service):
        """Create ElevenLabsTTSProvider instance."""
        with patch('src.infrastructure.audio.elevenlabs_tts_provider.HTTPX_AVAILABLE', True):
            return ElevenLabsTTSProvider(
                api_key="test_api_key",
                cache_service=mock_cache_service
            )

    @pytest.fixture
    def basic_tts_request(self):
        """Basic TTS request for testing."""
        return TTSRequest(
            text="Hello, this is a test message for children.",
            config=Mock(
                voice_profile=Mock(voice_id="alloy"),
                emotion=VoiceEmotion.NEUTRAL,
                speed=1.0,
                audio_format=AudioFormat.MP3,
                quality=AudioQuality.STANDARD
            ),
            safety_context=ChildSafetyContext(
                child_age=8,
                content_filter_level="moderate"
            )
        )

    def test_initialization_success(self):
        """Test successful provider initialization."""
        with patch('src.infrastructure.audio.elevenlabs_tts_provider.HTTPX_AVAILABLE', True):
            provider = ElevenLabsTTSProvider(api_key="test_key")
            
            assert provider.api_key == "test_key"
            assert provider.model == "eleven_monolingual_v1"
            assert provider.timeout == 30.0
            assert provider.max_retries == 3

    def test_initialization_no_httpx(self):
        """Test initialization fails without httpx."""
        with patch('src.infrastructure.audio.elevenlabs_tts_provider.HTTPX_AVAILABLE', False):
            with pytest.raises(TTSConfigurationError, match="httpx is required"):
                ElevenLabsTTSProvider(api_key="test_key")

    def test_initialization_no_api_key(self):
        """Test initialization fails without API key."""
        with patch('src.infrastructure.audio.elevenlabs_tts_provider.HTTPX_AVAILABLE', True):
            with pytest.raises(TTSConfigurationError, match="API key is required"):
                ElevenLabsTTSProvider(api_key="")

    @pytest.mark.asyncio
    async def test_synthesize_speech_success(self, tts_provider, basic_tts_request, mock_httpx_client):
        """Test successful speech synthesis."""
        with patch.object(tts_provider, '_get_client', return_value=mock_httpx_client):
            result = await tts_provider.synthesize_speech(basic_tts_request)
            
            assert isinstance(result, TTSResult)
            assert result.audio_data == b"mock_audio_data"
            assert result.provider_name == "elevenlabs"
            assert result.cached is False

    @pytest.mark.asyncio
    async def test_synthesize_speech_with_cache_hit(self, tts_provider, basic_tts_request, mock_cache_service):
        """Test speech synthesis with cache hit."""
        cached_result = TTSResult(
            audio_data=b"cached_audio",
            provider_name="elevenlabs",
            request_id="cached_id"
        )
        mock_cache_service.get.return_value = cached_result
        
        result = await tts_provider.synthesize_speech(basic_tts_request)
        
        assert result.audio_data == b"cached_audio"
        assert result.cached is True
        mock_cache_service.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_speech_unsafe_content(self, tts_provider):
        """Test synthesis fails with unsafe content."""
        unsafe_request = TTSRequest(
            text="This is scary and violent content with weapons.",
            config=Mock(
                voice_profile=Mock(voice_id="alloy"),
                emotion=VoiceEmotion.NEUTRAL,
                speed=1.0,
                audio_format=AudioFormat.MP3,
                quality=AudioQuality.STANDARD
            ),
            safety_context=ChildSafetyContext(
                child_age=8,
                content_filter_level="strict"
            )
        )
        
        with pytest.raises(TTSUnsafeContentError):
            await tts_provider.synthesize_speech(unsafe_request)

    @pytest.mark.asyncio
    async def test_validate_content_safety_safe_content(self, tts_provider):
        """Test content safety validation with safe content."""
        safe_text = "Hello! Let's read a nice story about animals."
        safety_context = ChildSafetyContext(child_age=8)
        
        is_safe, warnings = await tts_provider.validate_content_safety(safe_text, safety_context)
        
        assert is_safe is True
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_validate_content_safety_unsafe_content(self, tts_provider):
        """Test content safety validation with unsafe content."""
        unsafe_text = "This scary story has violence and weapons."
        safety_context = ChildSafetyContext(child_age=8, content_filter_level="strict")
        
        is_safe, warnings = await tts_provider.validate_content_safety(unsafe_text, safety_context)
        
        assert is_safe is False
        assert len(warnings) > 0
        assert any("inappropriate" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_validate_content_safety_blocked_words(self, tts_provider):
        """Test content safety with blocked words."""
        text = "This story mentions a custom blocked word."
        safety_context = ChildSafetyContext(
            child_age=8,
            blocked_words=["custom", "blocked"],
            content_filter_level="strict"
        )
        
        is_safe, warnings = await tts_provider.validate_content_safety(text, safety_context)
        
        assert is_safe is False
        assert any("blocked word" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_child_safety_validation_age_limits(self, tts_provider):
        """Test child safety validation with age limits."""
        request = TTSRequest(
            text="Test content",
            config=Mock(voice_profile=Mock(voice_id="alloy")),
            safety_context=ChildSafetyContext(child_age=2)  # Too young
        )
        
        with pytest.raises(TTSUnsafeContentError, match="COPPA compliance violation"):
            await tts_provider._validate_child_safety(request)

    @pytest.mark.asyncio
    async def test_child_safety_validation_text_length(self, tts_provider):
        """Test child safety validation with text length limits."""
        long_text = "A" * 1000  # Very long text
        request = TTSRequest(
            text=long_text,
            config=Mock(voice_profile=Mock(voice_id="alloy")),
            safety_context=ChildSafetyContext(child_age=6)
        )
        
        with pytest.raises(TTSUnsafeContentError, match="Text too long"):
            await tts_provider._validate_child_safety(request)

    @pytest.mark.asyncio
    async def test_child_safety_validation_unsafe_voice(self, tts_provider):
        """Test child safety validation with unsafe voice."""
        request = TTSRequest(
            text="Test content",
            config=Mock(voice_profile=Mock(voice_id="unsafe_voice")),
            safety_context=ChildSafetyContext(child_age=8)
        )
        
        with pytest.raises(TTSUnsafeContentError, match="not approved for child use"):
            await tts_provider._validate_child_safety(request)

    @pytest.mark.asyncio
    async def test_get_available_voices(self, tts_provider):
        """Test getting available child-safe voices."""
        voices = await tts_provider.get_available_voices(child_safe_only=True)
        
        assert len(voices) > 0
        assert all(isinstance(voice, VoiceProfile) for voice in voices)
        assert all(voice.is_child_safe for voice in voices)
        assert all(voice.language == "en-US" for voice in voices)

    @pytest.mark.asyncio
    async def test_get_available_voices_language_filter(self, tts_provider):
        """Test getting voices with language filter."""
        voices = await tts_provider.get_available_voices(language="en-US")
        
        assert len(voices) > 0
        assert all(voice.language == "en-US" for voice in voices)

    @pytest.mark.asyncio
    async def test_estimate_cost(self, tts_provider, basic_tts_request):
        """Test cost estimation."""
        cost_info = await tts_provider.estimate_cost(basic_tts_request)
        
        assert cost_info["provider"] == "elevenlabs"
        assert "character_count" in cost_info
        assert "estimated_cost_usd" in cost_info
        assert cost_info["pricing_model"] == "per_character"
        assert cost_info["character_count"] == len(basic_tts_request.text)

    @pytest.mark.asyncio
    async def test_health_check_success(self, tts_provider, mock_httpx_client):
        """Test successful health check."""
        with patch.object(tts_provider, '_get_client', return_value=mock_httpx_client):
            health = await tts_provider.health_check()
            
            assert health["provider"] == "elevenlabs"
            assert health["status"] in ["healthy", "degraded", "unhealthy"]
            assert "metrics" in health
            assert "configuration" in health

    @pytest.mark.asyncio
    async def test_health_check_failure(self, tts_provider):
        """Test health check with API failure."""
        mock_client = Mock()
        mock_client.get = AsyncMock(side_effect=Exception("API Error"))
        
        with patch.object(tts_provider, '_get_client', return_value=mock_client):
            health = await tts_provider.health_check()
            
            assert health["provider"] == "elevenlabs"
            assert health["status"] == "unhealthy"
            assert "error" in health

    def test_get_provider_info(self, tts_provider):
        """Test getting provider information."""
        info = tts_provider.get_provider_info()
        
        assert info["provider"] == "elevenlabs"
        assert info["name"] == "ElevenLabs TTS"
        assert "capabilities" in info
        assert info["capabilities"]["child_safety"] is True
        assert info["capabilities"]["coppa_compliant"] is True
        assert "child_safe_voices" in info

    @pytest.mark.asyncio
    async def test_clone_voice_disabled(self, tts_provider):
        """Test that voice cloning is disabled for child safety."""
        with pytest.raises(TTSConfigurationError, match="Voice cloning is disabled"):
            await tts_provider.clone_voice(
                name="test_voice",
                audio_samples=[b"sample"],
                safety_context=ChildSafetyContext()
            )

    def test_voice_info_fallback(self, tts_provider):
        """Test voice info fallback to safe voice."""
        voice_info = tts_provider._get_voice_info("unknown_voice")
        
        # Should fallback to alloy (default safe voice)
        assert voice_info == tts_provider.CHILD_SAFE_VOICES["alloy"]

    def test_cache_key_generation(self, tts_provider, basic_tts_request):
        """Test cache key generation."""
        cache_key = tts_provider._generate_cache_key(basic_tts_request)
        
        assert cache_key.startswith("tts_elevenlabs_")
        assert len(cache_key) > 20  # Should be a hash

    def test_audio_duration_estimation(self, tts_provider):
        """Test audio duration estimation."""
        # Test with typical audio size
        duration = tts_provider._estimate_audio_duration(32000)  # ~2 seconds
        assert duration > 1.0
        assert duration < 3.0
        
        # Test with very small audio
        duration_small = tts_provider._estimate_audio_duration(100)
        assert duration_small == 0.1  # Minimum duration

    @pytest.mark.asyncio
    async def test_prepare_voice_settings_emotions(self, tts_provider, basic_tts_request):
        """Test voice settings preparation with different emotions."""
        # Test happy emotion
        basic_tts_request.config.emotion = VoiceEmotion.HAPPY
        settings = await tts_provider._prepare_voice_settings(basic_tts_request)
        
        assert "stability" in settings
        assert "similarity_boost" in settings
        assert settings["style"] == 0.0  # Always 0 for child safety
        assert settings["use_speaker_boost"] is True
        
        # Values should be within valid range
        assert 0.0 <= settings["stability"] <= 1.0
        assert 0.0 <= settings["similarity_boost"] <= 1.0

    @pytest.mark.asyncio
    async def test_prepare_voice_settings_quality(self, tts_provider, basic_tts_request):
        """Test voice settings with different quality levels."""
        # Test high quality
        basic_tts_request.config.quality = AudioQuality.HIGH
        settings_high = await tts_provider._prepare_voice_settings(basic_tts_request)
        
        # Test low quality
        basic_tts_request.config.quality = AudioQuality.LOW
        settings_low = await tts_provider._prepare_voice_settings(basic_tts_request)
        
        # High quality should have higher values
        assert settings_high["stability"] >= settings_low["stability"]
        assert settings_high["similarity_boost"] >= settings_low["similarity_boost"]

    @pytest.mark.asyncio
    async def test_close_cleanup(self, tts_provider, mock_httpx_client):
        """Test resource cleanup on close."""
        tts_provider._client = mock_httpx_client
        
        await tts_provider.close()
        
        mock_httpx_client.aclose.assert_called_once()
        assert tts_provider._client is None

    def test_child_safe_voices_configuration(self, tts_provider):
        """Test that child-safe voices are properly configured."""
        assert len(tts_provider.CHILD_SAFE_VOICES) > 0
        
        for voice_id, voice_info in tts_provider.CHILD_SAFE_VOICES.items():
            assert "voice_id" in voice_info
            assert "name" in voice_info
            assert "gender" in voice_info
            assert "age_appropriate" in voice_info
            assert voice_info["age_appropriate"] is True
            assert "emotions" in voice_info
            assert len(voice_info["emotions"]) > 0

    def test_metrics_tracking(self, tts_provider):
        """Test that metrics are properly initialized and tracked."""
        metrics = tts_provider._metrics
        
        assert "total_requests" in metrics
        assert "successful_requests" in metrics
        assert "failed_requests" in metrics
        assert "cache_hits" in metrics
        assert "total_characters" in metrics
        assert "total_cost_usd" in metrics
        assert "safety_blocks" in metrics
        
        # All should start at 0
        assert metrics["total_requests"] == 0
        assert metrics["successful_requests"] == 0
        assert metrics["failed_requests"] == 0