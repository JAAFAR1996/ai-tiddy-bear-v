"""
Tests for OpenAI TTS Provider
=============================

Tests for OpenAI Text-to-Speech provider.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import hashlib

from src.infrastructure.audio.openai_tts_provider import OpenAITTSProvider
from src.interfaces.providers.tts_provider import (
    TTSRequest,
    TTSResult,
    VoiceProfile,
    ChildSafetyContext,
    TTSProviderError,
    TTSUnsafeContentError,
    TTSConfigurationError
)
from src.shared.audio_types import AudioFormat, VoiceGender


class TestOpenAITTSProvider:
    """Test OpenAI TTS provider."""

    @pytest.fixture
    def provider(self):
        """Create OpenAI TTS provider."""
        return OpenAITTSProvider(api_key="test-key")

    @pytest.fixture
    def mock_tts_request(self):
        """Create mock TTS request."""
        voice_profile = VoiceProfile(
            voice_id="alloy",
            name="Alloy",
            language="en-US",
            gender=VoiceGender.NEUTRAL
        )
        
        config = Mock()
        config.voice_profile = voice_profile
        config.audio_format = AudioFormat.MP3
        config.speed = 1.0
        
        return TTSRequest(
            text="Hello world",
            config=config,
            request_id="test-123"
        )

    def test_initialization_valid(self):
        """Test valid provider initialization."""
        provider = OpenAITTSProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.model == "tts-1"
        assert provider.timeout == 30

    def test_initialization_no_api_key(self):
        """Test initialization without API key."""
        with pytest.raises(TTSConfigurationError, match="OpenAI API key is required"):
            OpenAITTSProvider(api_key="")

    def test_map_voice_profile_by_id(self, provider):
        """Test voice profile mapping by ID."""
        profile = VoiceProfile(voice_id="nova", name="Nova", language="en-US")
        
        voice = provider._map_voice_profile(profile)
        
        assert voice == "nova"

    def test_map_voice_profile_by_gender(self, provider):
        """Test voice profile mapping by gender."""
        profile = VoiceProfile(
            voice_id="unknown",
            name="Test",
            language="en-US",
            gender=VoiceGender.FEMALE
        )
        
        voice = provider._map_voice_profile(profile)
        
        assert voice == "shimmer"

    def test_calculate_cost_standard_model(self, provider):
        """Test cost calculation for standard model."""
        cost = provider._calculate_cost(1000)  # 1000 characters
        
        assert cost == 0.015  # $0.015 per 1K chars

    def test_calculate_cost_hd_model(self):
        """Test cost calculation for HD model."""
        provider = OpenAITTSProvider(api_key="test-key", model="tts-1-hd")
        
        cost = provider._calculate_cost(1000)
        
        assert cost == 0.030  # $0.030 per 1K chars

    def test_estimate_duration(self, provider):
        """Test audio duration estimation."""
        duration = provider._estimate_duration(16000)  # 16KB
        
        assert duration == 1.0  # 1 second

    @pytest.mark.asyncio
    async def test_get_available_voices(self, provider):
        """Test getting available voices."""
        voices = await provider.get_available_voices()
        
        assert len(voices) == 6
        assert all(voice.is_child_safe for voice in voices)
        assert any(voice.voice_id == "alloy" for voice in voices)

    @pytest.mark.asyncio
    async def test_get_available_voices_filtered(self, provider):
        """Test getting filtered voices."""
        voices = await provider.get_available_voices(language="en-US")
        
        assert len(voices) == 6
        assert all(voice.language == "en-US" for voice in voices)

    @pytest.mark.asyncio
    async def test_validate_content_safety_safe(self, provider):
        """Test content safety validation for safe content."""
        safety_context = ChildSafetyContext(child_age=8)
        
        is_safe, warnings = await provider.validate_content_safety(
            "Hello, how are you today?", safety_context
        )
        
        assert is_safe is True
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_validate_content_safety_blocked_words(self, provider):
        """Test content safety with blocked words."""
        safety_context = ChildSafetyContext(
            child_age=8,
            blocked_words=["violence", "scary"]
        )
        
        is_safe, warnings = await provider.validate_content_safety(
            "This is a violent story", safety_context
        )
        
        assert is_safe is False
        assert len(warnings) > 0
        assert any("blocked word" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_validate_content_safety_inappropriate_patterns(self, provider):
        """Test content safety with inappropriate patterns."""
        safety_context = ChildSafetyContext(child_age=8)
        
        is_safe, warnings = await provider.validate_content_safety(
            "This story has violence and death", safety_context
        )
        
        assert is_safe is False
        assert len(warnings) > 0

    @pytest.mark.asyncio
    async def test_validate_content_safety_urls(self, provider):
        """Test content safety with URLs."""
        safety_context = ChildSafetyContext(child_age=8)
        
        is_safe, warnings = await provider.validate_content_safety(
            "Visit https://example.com for more", safety_context
        )
        
        assert is_safe is False
        assert any("URL" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_validate_content_safety_complexity(self, provider):
        """Test content safety with complex text for young children."""
        safety_context = ChildSafetyContext(child_age=5)
        
        is_safe, warnings = await provider.validate_content_safety(
            "The extraordinary phenomenon demonstrates unprecedented capabilities.", 
            safety_context
        )
        
        assert is_safe is False
        assert any("complex" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_estimate_cost(self, provider, mock_tts_request):
        """Test cost estimation."""
        estimate = await provider.estimate_cost(mock_tts_request)
        
        assert estimate["provider"] == "openai"
        assert estimate["model"] == "tts-1"
        assert estimate["character_count"] == len(mock_tts_request.text)
        assert "estimated_cost_usd" in estimate

    def test_generate_cache_key(self, provider, mock_tts_request):
        """Test cache key generation."""
        key = provider._generate_cache_key(mock_tts_request)
        
        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 hex digest length

    def test_get_provider_info(self, provider):
        """Test getting provider information."""
        info = provider.get_provider_info()
        
        assert info["name"] == "OpenAI Text-to-Speech"
        assert info["provider_id"] == "openai_tts"
        assert info["model"] == "tts-1"
        assert "mp3" in info["supported_formats"]

    def test_get_metrics(self, provider):
        """Test getting provider metrics."""
        metrics = provider.get_metrics()
        
        assert metrics["provider"] == "openai"
        assert metrics["total_requests"] == 0
        assert metrics["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_clone_voice_not_supported(self, provider):
        """Test voice cloning not supported."""
        safety_context = ChildSafetyContext(child_age=8)
        
        with pytest.raises(TTSProviderError, match="Voice cloning is not supported"):
            await provider.clone_voice("test", [b"audio"], safety_context)

    @pytest.mark.asyncio
    async def test_synthesize_speech_unsafe_content(self, provider, mock_tts_request):
        """Test synthesis with unsafe content."""
        mock_tts_request.text = "This is violent content"
        mock_tts_request.safety_context = ChildSafetyContext(child_age=8)
        
        with pytest.raises(TTSUnsafeContentError):
            await provider.synthesize_speech(mock_tts_request)

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        """Test successful health check."""
        mock_response = Mock()
        mock_response.content = b"test audio"
        
        with patch.object(provider, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.audio.speech.create.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            health = await provider.health_check()
            
            assert health["status"] == "healthy"
            assert health["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        """Test failed health check."""
        with patch.object(provider, '_get_client') as mock_get_client:
            mock_get_client.side_effect = Exception("API Error")
            
            health = await provider.health_check()
            
            assert health["status"] == "unhealthy"
            assert "error" in health