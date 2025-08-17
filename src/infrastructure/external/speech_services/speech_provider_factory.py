"""
Speech Provider Factory
======================
Factory for creating STT providers with Whisper as default.
"""

import logging
from typing import Optional, Dict, Any
from src.interfaces.providers.stt_provider import ISTTProvider


class SpeechProviderFactory:
    """Factory for creating speech-to-text providers."""

    @staticmethod
    def get_provider(
        provider_name: str, api_key: Optional[str] = None, **kwargs
    ) -> ISTTProvider:
        """
        Create STT provider based on configuration.

        Args:
            provider_name: Provider type ("whisper", "openai", "google")
            api_key: API key for external providers
            **kwargs: Additional provider-specific configuration

        Returns:
            ISTTProvider: Configured STT provider
        """
        logger = logging.getLogger(__name__)

        if provider_name.lower() == "whisper":
            from src.infrastructure.audio.whisper_stt_provider import WhisperSTTProvider

            model_size = kwargs.get("model_size", "base")
            device = kwargs.get("device", "auto")
            language = kwargs.get("language", None)  # Auto-detect

            logger.info(f"Creating Whisper STT provider with model: {model_size}")
            return WhisperSTTProvider(
                model_size=model_size, device=device, language=language
            )

        elif provider_name.lower() == "openai":
            from src.infrastructure.audio.openai_stt_provider import OpenAISTTProvider

            if not api_key:
                raise ValueError("OpenAI API key required for OpenAI STT provider")

            logger.info("Creating OpenAI STT provider")
            return OpenAISTTProvider(api_key=api_key)

        elif provider_name.lower() == "google":
            from src.infrastructure.audio.google_stt_provider import GoogleSTTProvider

            if not api_key:
                raise ValueError("Google API key required for Google STT provider")

            logger.info("Creating Google STT provider")
            return GoogleSTTProvider(api_key=api_key)

        else:
            raise ValueError(f"Unsupported STT provider: {provider_name}")

    @staticmethod
    def get_available_providers() -> Dict[str, Dict[str, Any]]:
        """Get information about available providers."""
        return {
            "whisper": {
                "name": "Local Whisper",
                "description": "Local OpenAI Whisper model for Arabic/English",
                "requires_api_key": False,
                "supports_realtime": True,
                "languages": ["ar", "en", "auto"],
                "latency": "low",
                "cost": "free",
            },
            "openai": {
                "name": "OpenAI Whisper API",
                "description": "OpenAI cloud-based Whisper API",
                "requires_api_key": True,
                "supports_realtime": False,
                "languages": ["ar", "en", "auto"],
                "latency": "medium",
                "cost": "paid",
            },
            "google": {
                "name": "Google Speech-to-Text",
                "description": "Google Cloud Speech-to-Text API",
                "requires_api_key": True,
                "supports_realtime": True,
                "languages": ["ar", "en", "auto"],
                "latency": "low",
                "cost": "paid",
            },
        }
