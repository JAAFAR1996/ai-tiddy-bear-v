"""
ESP32 Service Factory - Production Service Injection
===================================================
Factory for creating and configuring ESP32 Chat Server with all required services.
"""

import logging
import os
import random
from typing import Optional

from src.services.esp32_chat_server import ESP32ChatServer
from src.infrastructure.audio.whisper_stt_provider import WhisperSTTProvider
from src.application.services.ai_service import ConsolidatedAIService
from src.application.services.child_safety_service import ChildSafetyService
from src.shared.dto.ai_response import AIResponse


class ESP32ServiceFactory:
    """Factory for creating production-ready ESP32 Chat Server."""

    def __init__(self, config):
        """Initialize factory with centralized config (production-grade DI)"""
        if config is None:
            raise RuntimeError("ESP32ServiceFactory requires config parameter - no fallback allowed in production")
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def create_production_server(
        self,
        ai_provider,  # Required - no default
        tts_service,  # Required - no default
        stt_model_size: str = "base",
        redis_url: Optional[str] = None,
    ) -> ESP32ChatServer:
        """
        Create production ESP32 Chat Server with all services.

        Args:
            ai_provider: AI provider instance (REQUIRED)
            tts_service: TTS service instance (REQUIRED)
            stt_model_size: Whisper model size ("tiny", "base", "small", "medium", "large")
            redis_url: Redis connection URL

        Returns:
            Configured ESP32ChatServer instance

        Raises:
            ValueError: If required dependencies are None
        """
        self.logger.info("Creating production ESP32 Chat Server")

        # Validate required dependencies
        if ai_provider is None:
            raise ValueError("ai_provider is required and cannot be None")
        if tts_service is None:
            raise ValueError("tts_service is required and cannot be None")

        try:
            # Create STT Provider (Whisper)
            stt_provider = await self._create_stt_provider(stt_model_size)

            # Create AI Service
            ai_service = await self._create_ai_service(ai_provider, redis_url)

            # Create Child Safety Service
            safety_service = await self._create_safety_service()

            # Create ESP32 Chat Server with centralized config
            chat_server = ESP32ChatServer(config=self.config)

            # Inject all services
            chat_server.inject_services(
                stt_provider=stt_provider,
                tts_service=tts_service,
                ai_service=ai_service,
                safety_service=safety_service,
            )

            # Inject instance into backward-compatibility proxy
            from src.services.esp32_chat_server import esp32_chat_server as _esp32_proxy
            _esp32_proxy.set(chat_server)
            
            self.logger.info("ESP32 Chat Server created successfully with all services")
            return chat_server

        except Exception as e:
            self.logger.error(f"Failed to create ESP32 Chat Server: {e}", exc_info=True)
            raise

    async def _create_stt_provider(self, model_size: str) -> WhisperSTTProvider:
        """Create and initialize Whisper STT provider."""
        try:
            self.logger.info(f"Initializing Whisper STT provider with model: {model_size}")

            # Determine device
            device = "cuda" if os.getenv("USE_GPU", "false").lower() == "true" else "cpu"

            # Create provider
            stt_provider = WhisperSTTProvider(
                model_size=model_size,
                device=device,
                language=None,  # Auto-detect
                enable_vad=True,
            )

            # Optimize for real-time performance
            await stt_provider.optimize_for_realtime()

            self.logger.info("Whisper STT provider initialized successfully")
            return stt_provider

        except Exception as e:
            self.logger.error(f"Failed to create STT provider: {e}", exc_info=True)
            raise

    async def _create_ai_service(
        self, ai_provider=None, redis_url: Optional[str] = None
    ):
        """Create and initialize AI service."""
        try:
            if not ai_provider:
                raise ValueError("AI provider is required for production - cannot create AI service without provider")

            self.logger.info("Initializing ConsolidatedAIService")

            # Create production safety monitor
            from src.application.services.child_safety_service import ChildSafetyService
            safety_monitor = ChildSafetyService(config={
                'enable_real_time_monitoring': True,
                'auto_report_threshold': 0.7,
                'parent_notification_threshold': 0.8,
                'emergency_alert_threshold': 0.9,
            })

            # Create logger
            logger = logging.getLogger("ai_service")

            # Create AI service
            ai_service = ConsolidatedAIService(
                ai_provider=ai_provider,
                safety_monitor=safety_monitor,
                logger=logger,
                tts_service=None,  # Will be provided separately
                redis_client=None,
                redis_url=redis_url or "redis://localhost:6379",
            )

            self.logger.info("ConsolidatedAIService initialized successfully")
            return ai_service

        except Exception as e:
            self.logger.error(f"Failed to create AI service: {e}", exc_info=True)
            raise

    async def _create_safety_service(self):
        """Create and initialize child safety service."""
        try:
            self.logger.info("Initializing production ChildSafetyService")

            safety_config = {
                'enable_real_time_monitoring': True,
                'auto_report_threshold': 0.7,
                'parent_notification_threshold': 0.8,
                'emergency_alert_threshold': 0.9,
            }
            safety_service = ChildSafetyService(config=safety_config)
            self.logger.info("Production ChildSafetyService initialized successfully")
            return safety_service

        except Exception as e:
            self.logger.error(f"Failed to create production safety service: {e}", exc_info=True)
            raise


# Production services only - no mock services in production environment




# NOTE: No global factory instance - use proper DI pattern with config injection
# For testing/development only:  
# from src.infrastructure.config.production_config import get_config
# esp32_service_factory = ESP32ServiceFactory(config=get_config())
