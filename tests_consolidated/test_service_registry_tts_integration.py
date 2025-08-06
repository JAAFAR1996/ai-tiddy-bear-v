"""
Test Service Registry TTS Integration
====================================
Tests for verifying TTS provider registration and dependency injection
"""

import pytest
from unittest.mock import Mock, patch, create_autospec

from src.services.service_registry import ServiceRegistry
from src.infrastructure.audio.openai_tts_provider import OpenAITTSProvider
from src.infrastructure.audio.elevenlabs_tts_provider import ElevenLabsTTSProvider
from src.infrastructure.config.production_config import ProductionConfig
from src.infrastructure.caching.production_tts_cache_service import ProductionTTSCacheService


class TestServiceRegistryTTSIntegration:
    """Test TTS provider integration with ServiceRegistry."""

    @pytest.fixture
    def mock_config_openai(self):
        """Mock configuration for OpenAI TTS."""
        config = Mock(spec=ProductionConfig)
        config.OPENAI_API_KEY = "sk-test-key-1234567890abcdef"
        config.TTS_PROVIDER = "openai"
        return config

    @pytest.fixture
    def mock_config_elevenlabs(self):
        """Mock configuration for ElevenLabs TTS."""
        config = Mock(spec=ProductionConfig)
        config.ELEVENLABS_API_KEY = "test-elevenlabs-key-1234567890"
        config.TTS_PROVIDER = "elevenlabs"
        return config

    @pytest.mark.asyncio
    async def test_openai_tts_provider_registration(self, mock_config_openai):
        """Test that OpenAI TTS provider is correctly registered and created."""
        registry = ServiceRegistry()

        with patch(
            "src.services.service_registry.get_config", return_value=mock_config_openai
        ):
            with patch(
                "src.infrastructure.caching.production_tts_cache_service.ProductionTTSCacheService"
            ) as mock_cache:
                mock_cache_instance = Mock(spec=ProductionTTSCacheService)
                mock_cache.return_value = mock_cache_instance

                # Get TTS service
                tts_service = await registry.get_service("tts_service")

                # Verify it's the correct type
                assert isinstance(tts_service, OpenAITTSProvider)

                # Verify cache was created
                mock_cache.assert_called_once_with(
                    enabled=True, default_ttl_seconds=3600, max_cache_size_mb=1024
                )

    @pytest.mark.asyncio
    async def test_elevenlabs_tts_provider_registration(self, mock_config_elevenlabs):
        """Test that ElevenLabs TTS provider is correctly registered and created."""
        registry = ServiceRegistry()

        with patch(
            "src.services.service_registry.get_config",
            return_value=mock_config_elevenlabs,
        ):
            with patch(
                "src.infrastructure.caching.production_tts_cache_service.ProductionTTSCacheService"
            ) as mock_cache:
                mock_cache_instance = Mock(spec=ProductionTTSCacheService)
                mock_cache.return_value = mock_cache_instance

                # Get TTS service
                tts_service = await registry.get_service("tts_service")

                # Verify it's the correct type
                assert isinstance(tts_service, ElevenLabsTTSProvider)

                # Verify cache was created
                mock_cache.assert_called_once_with(
                    enabled=True, default_ttl_seconds=3600, max_cache_size_mb=1024
                )

    @pytest.mark.asyncio
    async def test_missing_openai_api_key_raises_error(self):
        """Test that missing OpenAI API key raises RuntimeError."""
        config = Mock(spec=ProductionConfig)
        config.OPENAI_API_KEY = None
        config.TTS_PROVIDER = "openai"

        registry = ServiceRegistry()

        with patch("src.services.service_registry.get_config", return_value=config):
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
                await registry.get_service("tts_service")

    @pytest.mark.asyncio
    async def test_missing_elevenlabs_api_key_raises_error(self):
        """Test that missing ElevenLabs API key raises RuntimeError."""
        config = Mock(spec=ProductionConfig)
        config.ELEVENLABS_API_KEY = None
        config.TTS_PROVIDER = "elevenlabs"

        registry = ServiceRegistry()

        with patch("src.services.service_registry.get_config", return_value=config):
            with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY is required"):
                await registry.get_service("tts_service")

    @pytest.mark.asyncio
    async def test_unsupported_tts_provider_raises_error(self):
        """Test that unsupported TTS provider raises RuntimeError."""
        config = Mock(spec=ProductionConfig)
        config.TTS_PROVIDER = "unsupported_provider"

        registry = ServiceRegistry()

        with patch("src.services.service_registry.get_config", return_value=config):
            with pytest.raises(
                RuntimeError, match="Unsupported TTS provider: unsupported_provider"
            ):
                await registry.get_service("tts_service")

    @pytest.mark.asyncio
    async def test_tts_service_singleton_behavior(self, mock_config_openai):
        """Test that TTS service follows singleton pattern."""
        registry = ServiceRegistry()

        with patch(
            "src.services.service_registry.get_config", return_value=mock_config_openai
        ):
            with patch(
                "src.infrastructure.caching.production_tts_cache_service.ProductionTTSCacheService"
            ):
                # Get TTS service twice
                tts_service_1 = await registry.get_service("tts_service")
                tts_service_2 = await registry.get_service("tts_service")

                # Verify same instance is returned (singleton)
                assert tts_service_1 is tts_service_2

    @pytest.mark.asyncio
    async def test_tts_provider_switching(
        self, mock_config_openai, mock_config_elevenlabs
    ):
        """Test switching between TTS providers with different registries."""
        # Test OpenAI provider
        registry_openai = ServiceRegistry()

        with patch(
            "src.services.service_registry.get_config", return_value=mock_config_openai
        ):
            with patch(
                "src.infrastructure.caching.production_tts_cache_service.ProductionTTSCacheService"
            ):
                tts_openai = await registry_openai.get_service("tts_service")
                assert isinstance(tts_openai, OpenAITTSProvider)

        # Test ElevenLabs provider with new registry
        registry_elevenlabs = ServiceRegistry()

        with patch(
            "src.services.service_registry.get_config",
            return_value=mock_config_elevenlabs,
        ):
            with patch(
                "src.infrastructure.caching.production_tts_cache_service.ProductionTTSCacheService"
            ):
                tts_elevenlabs = await registry_elevenlabs.get_service("tts_service")
                assert isinstance(tts_elevenlabs, ElevenLabsTTSProvider)

    @pytest.mark.asyncio
    async def test_audio_service_tts_dependency(self, mock_config_openai):
        """Test that AudioService correctly receives TTS service dependency."""
        registry = ServiceRegistry()

        with patch(
            "src.services.service_registry.get_config", return_value=mock_config_openai
        ):
            with patch(
                "src.infrastructure.caching.production_tts_cache_service.ProductionTTSCacheService"
            ):
                with patch(
                    "src.application.services.audio_service.AudioService"
                ) as mock_audio_service:
                    from src.application.services.audio_service import AudioService
                    mock_audio_instance = create_autospec(AudioService, instance=True)
                    mock_audio_service.return_value = mock_audio_instance

                    # Get audio service (which depends on TTS service)
                    await registry.get_service("audio_service")

                    # Verify AudioService was created with TTS dependency
                    mock_audio_service.assert_called_once()
                    call_args = mock_audio_service.call_args

                    # Verify TTS service was passed as dependency
                    assert "tts_service" in call_args.kwargs
                    assert isinstance(
                        call_args.kwargs["tts_service"], OpenAITTSProvider
                    )


@pytest.mark.integration
class TestTTSProviderRealConfiguration:
    """Integration tests with real configuration."""

    def test_configuration_validation_openai(self):
        """Test that OpenAI configuration validates correctly."""
        from src.infrastructure.config.production_config import ProductionConfig

        # Test valid OpenAI configuration
        config_data = {
            "ENVIRONMENT": "test",
            "SECRET_KEY": "test_secret_key_12345678901234567890",
            "JWT_SECRET_KEY": "test_jwt_secret_key_12345678901234567890",
            "COPPA_ENCRYPTION_KEY": "test_coppa_key_12345678901234567890",
            "DATABASE_URL": "postgresql://user:pass@localhost/test",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test1234567890abcdef1234567890abcdef1234567890abcdef",
            "TTS_PROVIDER": "openai",
            "CORS_ALLOWED_ORIGINS": ["http://localhost:3000"],
            "PARENT_NOTIFICATION_EMAIL": "parent@example.com",
        }

        config = ProductionConfig(**config_data)
        assert config.TTS_PROVIDER == "openai"
        assert config.OPENAI_API_KEY.startswith("sk-")

    def test_configuration_validation_elevenlabs(self):
        """Test that ElevenLabs configuration validates correctly."""
        from src.infrastructure.config.production_config import ProductionConfig

        # Test valid ElevenLabs configuration
        config_data = {
            "ENVIRONMENT": "test",
            "SECRET_KEY": "test_secret_key_12345678901234567890",
            "JWT_SECRET_KEY": "test_jwt_secret_key_12345678901234567890",
            "COPPA_ENCRYPTION_KEY": "test_coppa_key_12345678901234567890",
            "DATABASE_URL": "postgresql://user:pass@localhost/test",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test1234567890abcdef1234567890abcdef1234567890abcdef",
            "ELEVENLABS_API_KEY": "test_elevenlabs_key_1234567890",
            "TTS_PROVIDER": "elevenlabs",
            "CORS_ALLOWED_ORIGINS": ["http://localhost:3000"],
            "PARENT_NOTIFICATION_EMAIL": "parent@example.com",
        }

        config = ProductionConfig(**config_data)
        assert config.TTS_PROVIDER == "elevenlabs"
        assert config.ELEVENLABS_API_KEY is not None

    def test_invalid_tts_provider_validation(self):
        """Test that invalid TTS provider raises validation error."""
        from src.infrastructure.config.production_config import ProductionConfig
        from pydantic import ValidationError

        config_data = {
            "ENVIRONMENT": "test",
            "SECRET_KEY": "test_secret_key_12345678901234567890",
            "JWT_SECRET_KEY": "test_jwt_secret_key_12345678901234567890",
            "COPPA_ENCRYPTION_KEY": "test_coppa_key_12345678901234567890",
            "DATABASE_URL": "postgresql://user:pass@localhost/test",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test1234567890abcdef1234567890abcdef1234567890abcdef",
            "TTS_PROVIDER": "invalid_provider",  # Invalid provider
            "CORS_ALLOWED_ORIGINS": ["http://localhost:3000"],
            "PARENT_NOTIFICATION_EMAIL": "parent@example.com",
        }

        with pytest.raises(ValidationError):
            ProductionConfig(**config_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])