"""
Comprehensive Tests for ElevenLabs TTS Provider
==============================================
Production-ready test suite covering all aspects of the ElevenLabs TTS provider
with focus on child safety, COPPA compliance, and production reliability.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.infrastructure.audio.elevenlabs_tts_provider import ElevenLabsTTSProvider
from src.infrastructure.caching.production_tts_cache_service import ProductionTTSCacheService
from src.interfaces.providers.tts_provider import (
    TTSRequest,
    TTSResult,
    TTSConfiguration,
    VoiceProfile,
    ChildSafetyContext,
    AudioFormat,
    AudioQuality,
    VoiceEmotion,
    VoiceGender,
    TTSProviderError,
    TTSConfigurationError,
    TTSUnsafeContentError,
    TTSRateLimitError,
    TTSProviderUnavailableError,
)


class TestElevenLabsTTSProvider:
    """Comprehensive test suite for ElevenLabs TTS Provider."""

    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service for testing."""
        cache = AsyncMock(spec=ProductionTTSCacheService)
        cache.get.return_value = None  # No cache hit by default
        cache.set = AsyncMock(spec=ProductionTTSCacheService.set)
        return cache

    @pytest.fixture
    def provider(self, mock_cache_service):
        """Create provider instance with mocked dependencies."""
        return ElevenLabsTTSProvider(
            api_key="test_api_key_123",
            cache_service=mock_cache_service,
            model="eleven_monolingual_v1",
            timeout=30.0,
            max_retries=3,
        )

    @pytest.fixture
    def child_safety_context(self):
        """Standard child safety context for testing."""
        return ChildSafetyContext(
            child_age=8,
            parental_controls=True,
            content_filter_level="strict",
            blocked_words=["badword", "inappropriate"],
        )

    @pytest.fixture
    def sample_tts_request(self, child_safety_context):
        """Sample TTS request for testing."""
        voice_profile = VoiceProfile(
            voice_id="alloy",
            name="Adam",
            language="en-US",
            gender=VoiceGender.MALE,
            age_range="adult",
            description="Calm and friendly male voice",
            is_child_safe=True,
            supported_emotions=[VoiceEmotion.NEUTRAL, VoiceEmotion.HAPPY],
        )

        config = TTSConfiguration(
            voice_profile=voice_profile,
            emotion=VoiceEmotion.HAPPY,
            speed=1.0,
            audio_format=AudioFormat.MP3,
            quality=AudioQuality.STANDARD,
        )

        return TTSRequest(
            text="Hello there! I'm your friendly AI teddy bear.",
            config=config,
            safety_context=child_safety_context,
        )

    # =====================================================================
    # INITIALIZATION TESTS
    # =====================================================================

    def test_provider_initialization_success(self):
        """Test successful provider initialization."""
        provider = ElevenLabsTTSProvider(
            api_key="test_key", model="eleven_monolingual_v1"
        )

        assert provider.api_key == "test_key"
        assert provider.model == "eleven_monolingual_v1"
        assert provider.timeout == 30.0
        assert provider.max_retries == 3
        assert len(provider.CHILD_SAFE_VOICES) == 5

    def test_provider_initialization_missing_httpx(self):
        """Test initialization failure when httpx not available."""
        with patch(
            "src.infrastructure.audio.elevenlabs_tts_provider.HTTPX_AVAILABLE", False
        ):
            with pytest.raises(TTSConfigurationError, match="httpx is required"):
                ElevenLabsTTSProvider(api_key="test_key")

    def test_provider_initialization_missing_api_key(self):
        """Test initialization failure with missing API key."""
        with pytest.raises(TTSConfigurationError, match="API key is required"):
            ElevenLabsTTSProvider(api_key="")

    # =====================================================================
    # CHILD SAFETY VALIDATION TESTS
    # =====================================================================

    async def test_child_safety_validation_valid_age(
        self, provider, sample_tts_request
    ):
        """Test child safety validation with valid age."""
        # Should not raise any exception
        await provider._validate_child_safety(sample_tts_request)

    async def test_child_safety_validation_invalid_age_too_young(
        self, provider, sample_tts_request
    ):
        """Test child safety validation with age too young."""
        sample_tts_request.safety_context.child_age = 2  # Too young for COPPA

        with pytest.raises(TTSUnsafeContentError, match="COPPA compliance violation"):
            await provider._validate_child_safety(sample_tts_request)

    async def test_child_safety_validation_invalid_age_too_old(
        self, provider, sample_tts_request
    ):
        """Test child safety validation with age too old."""
        sample_tts_request.safety_context.child_age = 15  # Too old for COPPA

        with pytest.raises(TTSUnsafeContentError, match="COPPA compliance violation"):
            await provider._validate_child_safety(sample_tts_request)

    async def test_child_safety_validation_text_too_long_young_child(
        self, provider, sample_tts_request
    ):
        """Test text length limit for young children."""
        sample_tts_request.safety_context.child_age = 6
        sample_tts_request.text = "x" * 501  # Too long for young child

        with pytest.raises(TTSUnsafeContentError, match="Text too long"):
            await provider._validate_child_safety(sample_tts_request)

    async def test_child_safety_validation_text_too_long_older_child(
        self, provider, sample_tts_request
    ):
        """Test text length limit for older children."""
        sample_tts_request.safety_context.child_age = 10
        sample_tts_request.text = "x" * 751  # Too long for older child

        with pytest.raises(TTSUnsafeContentError, match="Text too long"):
            await provider._validate_child_safety(sample_tts_request)

    async def test_child_safety_validation_blocked_words(
        self, provider, sample_tts_request
    ):
        """Test blocked words enforcement."""
        sample_tts_request.text = "This contains a badword in the text"

        with pytest.raises(TTSUnsafeContentError, match="blocked word"):
            await provider._validate_child_safety(sample_tts_request)

    async def test_child_safety_validation_inappropriate_voice(
        self, provider, sample_tts_request
    ):
        """Test rejection of non-child-safe voices."""
        sample_tts_request.config.voice_profile.voice_id = "unsafe_voice_id"

        with pytest.raises(TTSUnsafeContentError, match="not approved for child use"):
            await provider._validate_child_safety(sample_tts_request)

    # =====================================================================
    # CONTENT SAFETY VALIDATION TESTS
    # =====================================================================

    async def test_validate_content_safety_safe_content(
        self, provider, child_safety_context
    ):
        """Test content safety validation with safe content."""
        text = "Once upon a time, there was a friendly teddy bear."

        is_safe, warnings = await provider.validate_content_safety(
            text, child_safety_context
        )

        assert is_safe is True
        assert len(warnings) == 0

    async def test_validate_content_safety_inappropriate_content(
        self, provider, child_safety_context
    ):
        """Test content safety validation with inappropriate content."""
        text = "This is a violent and scary story about death and blood."

        is_safe, warnings = await provider.validate_content_safety(
            text, child_safety_context
        )

        assert is_safe is False
        assert len(warnings) > 0
        assert any("inappropriate" in warning for warning in warnings)

    async def test_validate_content_safety_blocked_words(
        self, provider, child_safety_context
    ):
        """Test content safety validation with blocked words."""
        text = "This text contains a badword that should be blocked."

        is_safe, warnings = await provider.validate_content_safety(
            text, child_safety_context
        )

        assert is_safe is False
        assert any("blocked word" in warning for warning in warnings)

    async def test_validate_content_safety_complex_text_young_child(self, provider):
        """Test content safety validation with complex text for young child."""
        context = ChildSafetyContext(child_age=5, content_filter_level="strict")
        text = " ".join(["word"] * 60)  # 60 words - too complex for young child

        is_safe, warnings = await provider.validate_content_safety(text, context)

        assert len(warnings) > 0
        assert any("too complex" in warning for warning in warnings)

    async def test_validate_content_safety_filter_levels(self, provider):
        """Test different content filter levels."""
        text = "This contains violent content."

        # Strict filtering
        strict_context = ChildSafetyContext(content_filter_level="strict")
        is_safe_strict, _ = await provider.validate_content_safety(text, strict_context)

        # Moderate filtering
        moderate_context = ChildSafetyContext(content_filter_level="moderate")
        is_safe_moderate, _ = await provider.validate_content_safety(
            text, moderate_context
        )

        # Basic filtering
        basic_context = ChildSafetyContext(content_filter_level="basic")
        is_safe_basic, _ = await provider.validate_content_safety(text, basic_context)

        # Strict should be most restrictive
        assert is_safe_strict is False
        # Moderate and basic might be more permissive (depending on content)

    # =====================================================================
    # VOICE SETTINGS TESTS
    # =====================================================================

    async def test_prepare_voice_settings_default(self, provider, sample_tts_request):
        """Test voice settings preparation with default emotion."""
        sample_tts_request.config.emotion = VoiceEmotion.NEUTRAL

        settings = await provider._prepare_voice_settings(sample_tts_request)

        assert 0.0 <= settings["stability"] <= 1.0
        assert 0.0 <= settings["similarity_boost"] <= 1.0
        assert settings["style"] == 0.0  # Always 0 for child safety
        assert settings["use_speaker_boost"] is True

    async def test_prepare_voice_settings_emotions(self, provider, sample_tts_request):
        """Test voice settings preparation with different emotions."""
        emotions_to_test = [
            VoiceEmotion.HAPPY,
            VoiceEmotion.SAD,
            VoiceEmotion.EXCITED,
            VoiceEmotion.CALM,
            VoiceEmotion.CARING,
            VoiceEmotion.EDUCATIONAL,
        ]

        for emotion in emotions_to_test:
            sample_tts_request.config.emotion = emotion
            settings = await provider._prepare_voice_settings(sample_tts_request)

            assert 0.0 <= settings["stability"] <= 1.0
            assert 0.0 <= settings["similarity_boost"] <= 1.0
            assert settings["style"] == 0.0  # Always 0 for child safety

    async def test_prepare_voice_settings_quality_levels(
        self, provider, sample_tts_request
    ):
        """Test voice settings preparation with different quality levels."""
        qualities = [
            AudioQuality.LOW,
            AudioQuality.STANDARD,
            AudioQuality.HIGH,
            AudioQuality.PREMIUM,
        ]

        for quality in qualities:
            sample_tts_request.config.quality = quality
            settings = await provider._prepare_voice_settings(sample_tts_request)

            assert 0.0 <= settings["stability"] <= 1.0
            assert 0.0 <= settings["similarity_boost"] <= 1.0

    # =====================================================================
    # API CALL TESTS
    # =====================================================================

    async def test_call_elevenlabs_api_success(self, provider):
        """Test successful API call."""
        mock_audio_data = b"fake_audio_data_content"

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.content = mock_audio_data
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await provider._call_elevenlabs_api(
                voice_id="test_voice_id",
                text="test text",
                voice_settings={"stability": 0.5, "similarity_boost": 0.5},
                model_id="eleven_monolingual_v1",
            )

            assert result == mock_audio_data
            mock_client.post.assert_called_once()

    async def test_call_elevenlabs_api_invalid_auth(self, provider):
        """Test API call with invalid authentication."""
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 401
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(
                TTSConfigurationError, match="Invalid ElevenLabs API key"
            ):
                await provider._call_elevenlabs_api(
                    voice_id="test_voice_id",
                    text="test text",
                    voice_settings={},
                    model_id="eleven_monolingual_v1",
                )

    async def test_call_elevenlabs_api_rate_limit(self, provider):
        """Test API call with rate limiting."""
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 429
            mock_response.headers = {"retry-after": "2"}
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(TTSRateLimitError, match="rate limit exceeded"):
                await provider._call_elevenlabs_api(
                    voice_id="test_voice_id",
                    text="test text",
                    voice_settings={},
                    model_id="eleven_monolingual_v1",
                )

    async def test_call_elevenlabs_api_validation_error(self, provider):
        """Test API call with validation error."""
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 422
            mock_response.text = "Invalid voice settings"
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(
                TTSConfigurationError, match="Invalid request parameters"
            ):
                await provider._call_elevenlabs_api(
                    voice_id="test_voice_id",
                    text="test text",
                    voice_settings={},
                    model_id="eleven_monolingual_v1",
                )

    async def test_call_elevenlabs_api_server_error_with_retry(self, provider):
        """Test API call with server error and retry logic."""
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 500
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
                with pytest.raises(
                    TTSProviderUnavailableError, match="service unavailable"
                ):
                    await provider._call_elevenlabs_api(
                        voice_id="test_voice_id",
                        text="test text",
                        voice_settings={},
                        model_id="eleven_monolingual_v1",
                    )

            # Should have retried 3 times
            assert mock_client.post.call_count == 3

    async def test_call_elevenlabs_api_network_error(self, provider):
        """Test API call with network error."""
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.post.side_effect = httpx.RequestError("Network error")
            mock_get_client.return_value = mock_client

            with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
                with pytest.raises(TTSProviderUnavailableError, match="Network error"):
                    await provider._call_elevenlabs_api(
                        voice_id="test_voice_id",
                        text="test text",
                        voice_settings={},
                        model_id="eleven_monolingual_v1",
                    )

    # =====================================================================
    # FULL SYNTHESIS TESTS
    # =====================================================================

    async def test_synthesize_speech_success(
        self, provider, sample_tts_request, mock_cache_service
    ):
        """Test successful speech synthesis."""
        mock_audio_data = b"fake_audio_data_content"

        with patch.object(
            provider, "_call_elevenlabs_api", return_value=mock_audio_data
        ) as mock_api:
            result = await provider.synthesize_speech(sample_tts_request)

            # Verify result structure
            assert isinstance(result, TTSResult)
            assert result.audio_data == mock_audio_data
            assert result.provider_name == "elevenlabs"
            assert result.format == AudioFormat.MP3
            assert result.processing_time_ms > 0
            assert not result.cached
            assert result.file_size_bytes == len(mock_audio_data)

            # Verify API was called
            mock_api.assert_called_once()

            # Verify cache was updated
            mock_cache_service.set.assert_called_once()

            # Verify metrics were updated
            assert provider._metrics["total_requests"] > 0
            assert provider._metrics["successful_requests"] > 0

    async def test_synthesize_speech_cache_hit(
        self, provider, sample_tts_request, mock_cache_service
    ):
        """Test speech synthesis with cache hit."""
        # Setup cache hit
        cached_result = TTSResult(
            audio_data=b"cached_audio_data",
            request_id="cached_request",
            provider_name="elevenlabs",
            config=sample_tts_request.config,
            duration_seconds=2.0,
            sample_rate=22050,
            bit_rate=128000,
            file_size_bytes=100,
            format=AudioFormat.MP3,
            processing_time_ms=50.0,
            provider_latency_ms=40.0,
            cached=True,
        )
        mock_cache_service.get.return_value = cached_result

        result = await provider.synthesize_speech(sample_tts_request)

        assert result.cached is True
        assert result.audio_data == b"cached_audio_data"
        assert provider._metrics["cache_hits"] > 0

    async def test_synthesize_speech_unsafe_content(self, provider, sample_tts_request):
        """Test speech synthesis with unsafe content."""
        sample_tts_request.text = "This contains violent and scary content."

        with pytest.raises(TTSUnsafeContentError, match="safety validation"):
            await provider.synthesize_speech(sample_tts_request)

        assert provider._metrics["safety_blocks"] > 0

    async def test_synthesize_speech_provider_error(self, provider, sample_tts_request):
        """Test speech synthesis with provider error."""
        with patch.object(
            provider, "_call_elevenlabs_api", side_effect=TTSProviderError("API Error")
        ):
            with pytest.raises(TTSProviderError, match="API Error"):
                await provider.synthesize_speech(sample_tts_request)

            assert provider._metrics["failed_requests"] > 0

    # =====================================================================
    # VOICE MANAGEMENT TESTS
    # =====================================================================

    async def test_get_available_voices_default(self, provider):
        """Test getting available voices with default parameters."""
        voices = await provider.get_available_voices()

        assert len(voices) == 5  # All child-safe voices
        for voice in voices:
            assert isinstance(voice, VoiceProfile)
            assert voice.is_child_safe is True
            assert voice.language == "en-US"
            assert voice.voice_id in provider.CHILD_SAFE_VOICES

    async def test_get_available_voices_language_filter(self, provider):
        """Test getting available voices with language filter."""
        # English should return all voices
        voices_en = await provider.get_available_voices(language="en-US")
        assert len(voices_en) == 5

        # Non-English should return no voices
        voices_fr = await provider.get_available_voices(language="fr-FR")
        assert len(voices_fr) == 0

    def test_get_voice_info_valid_voice(self, provider):
        """Test getting voice info for valid voice."""
        voice_info = provider._get_voice_info("alloy")

        assert voice_info["name"] == "Adam"
        assert voice_info["gender"] == VoiceGender.MALE
        assert voice_info["age_appropriate"] is True

    def test_get_voice_info_invalid_voice(self, provider):
        """Test getting voice info for invalid voice (should default to safe voice)."""
        voice_info = provider._get_voice_info("unsafe_voice")

        # Should default to 'alloy'
        assert voice_info["name"] == "Adam"
        assert voice_info["gender"] == VoiceGender.MALE
        assert voice_info["age_appropriate"] is True

    # =====================================================================
    # COST ESTIMATION TESTS
    # =====================================================================

    async def test_estimate_cost(self, provider, sample_tts_request):
        """Test cost estimation."""
        cost_info = await provider.estimate_cost(sample_tts_request)

        assert cost_info["provider"] == "elevenlabs"
        assert cost_info["character_count"] == len(sample_tts_request.text)
        assert cost_info["estimated_cost_usd"] > 0
        assert cost_info["pricing_model"] == "per_character"
        assert cost_info["rate_per_character"] == provider.PRICING_PER_CHARACTER

    def test_estimate_audio_duration(self, provider):
        """Test audio duration estimation."""
        # Test normal audio size
        duration = provider._estimate_audio_duration(32000)  # ~2 seconds
        assert 1.8 <= duration <= 2.2

        # Test very small audio (should have minimum)
        duration_small = provider._estimate_audio_duration(100)
        assert duration_small >= 0.1

    # =====================================================================
    # HEALTH CHECK TESTS
    # =====================================================================

    async def test_health_check_healthy(self, provider):
        """Test health check when service is healthy."""
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            health = await provider.health_check()

            assert health["provider"] == "elevenlabs"
            assert health["status"] == "healthy"
            assert health["api_accessible"] is True
            assert health["child_safe_voices"] == 5
            assert "metrics" in health
            assert "configuration" in health

    async def test_health_check_unhealthy(self, provider):
        """Test health check when service is unhealthy."""
        with patch.object(
            provider, "_get_client", side_effect=Exception("Connection failed")
        ):
            health = await provider.health_check()

            assert health["provider"] == "elevenlabs"
            assert health["status"] == "unhealthy"
            assert health["api_accessible"] is False
            assert "error" in health

    # =====================================================================
    # PROVIDER INFO TESTS
    # =====================================================================

    def test_get_provider_info(self, provider):
        """Test getting provider information."""
        info = provider.get_provider_info()

        assert info["provider"] == "elevenlabs"
        assert info["name"] == "ElevenLabs TTS"
        assert "capabilities" in info
        assert info["capabilities"]["child_safety"] is True
        assert info["capabilities"]["coppa_compliant"] is True
        assert "supported_formats" in info
        assert "child_safe_voices" in info
        assert "pricing" in info
        assert "limits" in info

    # =====================================================================
    # VOICE CLONING TESTS
    # =====================================================================

    async def test_clone_voice_disabled_for_safety(
        self, provider, child_safety_context
    ):
        """Test that voice cloning is disabled for child safety."""
        with pytest.raises(TTSConfigurationError, match="Voice cloning is disabled"):
            await provider.clone_voice(
                name="test_voice",
                audio_samples=[b"sample_audio"],
                safety_context=child_safety_context,
            )

    # =====================================================================
    # CACHE KEY GENERATION TESTS
    # =====================================================================

    def test_generate_cache_key_consistency(self, provider, sample_tts_request):
        """Test cache key generation consistency."""
        key1 = provider._generate_cache_key(sample_tts_request)
        key2 = provider._generate_cache_key(sample_tts_request)

        assert key1 == key2
        assert key1.startswith("tts_elevenlabs_")
        assert len(key1) > 20  # Should be reasonably long hash

    def test_generate_cache_key_uniqueness(self, provider, sample_tts_request):
        """Test cache key uniqueness for different requests."""
        key1 = provider._generate_cache_key(sample_tts_request)

        # Change text
        sample_tts_request.text = "Different text content"
        key2 = provider._generate_cache_key(sample_tts_request)

        assert key1 != key2

    # =====================================================================
    # CLEANUP TESTS
    # =====================================================================

    async def test_close_cleanup(self, provider):
        """Test resource cleanup on close."""
        # Create a mock client
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_get_client.return_value = mock_client
            provider._client = mock_client

            await provider.close()

            mock_client.aclose.assert_called_once()
            assert provider._client is None


if __name__ == "__main__":
    pytest.main([__file__])
