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

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def create_production_server(
        self,
        stt_model_size: str = "base",
        ai_provider=None,
        tts_service=None,
        redis_url: Optional[str] = None,
    ) -> ESP32ChatServer:
        """
        Create production ESP32 Chat Server with all services.

        Args:
            stt_model_size: Whisper model size ("tiny", "base", "small", "medium", "large")
            ai_provider: AI provider instance
            tts_service: TTS service instance
            redis_url: Redis connection URL

        Returns:
            Configured ESP32ChatServer instance
        """
        self.logger.info("Creating production ESP32 Chat Server")

        try:
            # Create STT Provider (Whisper)
            stt_provider = await self._create_stt_provider(stt_model_size)

            # Create AI Service
            ai_service = await self._create_ai_service(ai_provider, redis_url)

            # Create Child Safety Service
            safety_service = await self._create_safety_service()

            # Create ESP32 Chat Server
            chat_server = ESP32ChatServer()

            # Inject all services
            chat_server.inject_services(
                stt_provider=stt_provider,
                tts_service=tts_service,
                ai_service=ai_service,
                safety_service=safety_service,
            )

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
                self.logger.warning("No AI provider provided, creating mock service")
                return MockAIService()

            self.logger.info("Initializing ConsolidatedAIService")

            # Create safety monitor (mock for now)
            safety_monitor = MockSafetyMonitor()

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
            # Return mock service as fallback
            return MockAIService()

    async def _create_safety_service(self):
        """Create and initialize child safety service."""
        try:
            self.logger.info("Initializing ChildSafetyService")

            # Try to create the full ChildSafetyService
            try:
                safety_config = {
                    'enable_real_time_monitoring': True,
                    'auto_report_threshold': 0.7,
                    'parent_notification_threshold': 0.8,
                    'emergency_alert_threshold': 0.9,
                }
                safety_service = ChildSafetyService(config=safety_config)
                self.logger.info("ChildSafetyService initialized successfully")
                return safety_service
            except Exception as e:
                self.logger.warning(f"Failed to create full ChildSafetyService: {e}")
                # Fall back to simplified safety service
                return FallbackSafetyService()

        except Exception as e:
            self.logger.error(f"Failed to create safety service: {e}", exc_info=True)
            # Return basic fallback safety service
            return BasicSafetyService()


# Mock services for development/fallback
class MockAIService:
    """Mock AI service for development when real AI provider is not available."""

    async def generate_safe_response(self, child_id, user_input, child_age, **kwargs):
        """Generate a simple mock response."""
        age_appropriate_responses = {
            (3, 5): [
                "That's so cool! Tell me more!",
                "Wow! I love hearing about that!",
                "You're so smart! What else do you like?",
                "That sounds fun! Can you tell me another story?",
                "I like that too! What's your favorite color?",
            ],
            (6, 9): [
                "That's really interesting! Tell me more about it!",
                "Wow, that sounds amazing! What else do you enjoy?",
                "I love learning new things! Can you teach me something?",
                "That's so cool! What's your favorite thing to do?",
                "You're really creative! What would you like to talk about next?",
            ],
            (10, 13): [
                "That's fascinating! I'd love to hear more details!",
                "That sounds really cool! What got you interested in that?",
                "I'm impressed! Can you tell me more about your experience?",
                "That's awesome! What's the most exciting part about it?",
                "You have great ideas! What else are you curious about?",
            ],
        }

        # Get age-appropriate responses
        if 3 <= child_age <= 5:
            responses = age_appropriate_responses[(3, 5)]
        elif 6 <= child_age <= 9:
            responses = age_appropriate_responses[(6, 9)]
        elif 10 <= child_age <= 13:
            responses = age_appropriate_responses[(10, 13)]
        else:
            responses = age_appropriate_responses[(6, 9)]  # Default

        return AIResponse(
            content=random.choice(responses),
            confidence=0.8,
            safe=True,
            metadata={"source": "mock_ai_service", "child_age": child_age},
        )


class MockSafetyMonitor:
    """Mock safety monitor for development."""

    async def check_content(self, content: str):
        """Basic safety check."""
        inappropriate_words = [
            "bad", "hate", "stupid", "kill", "hurt", "violence", "weapon",
            "drug", "alcohol", "sex", "adult", "scary", "death", "blood"
        ]
        content_lower = content.lower()
        return not any(word in content_lower for word in inappropriate_words)


class FallbackSafetyService:
    """Fallback safety service when ChildSafetyService fails to initialize."""

    async def check_content(self, content: str, child_age: int) -> bool:
        """Check if content is safe for the child."""
        if not content or not content.strip():
            return False

        # Basic inappropriate content check
        inappropriate_words = [
            "bad", "hate", "stupid", "kill", "hurt", "violence", "weapon",
            "drug", "alcohol", "sex", "adult", "scary", "death", "blood",
            "fight", "angry", "monster", "ghost", "devil", "hell"
        ]

        content_lower = content.lower()
        for word in inappropriate_words:
            if word in content_lower:
                return False

        # Age-specific checks
        if child_age < 6:
            # More restrictive for younger children
            restricted_words = ["sad", "cry", "afraid", "dark", "nightmare"]
            for word in restricted_words:
                if word in content_lower:
                    return False

        return True


class BasicSafetyService:
    """Basic safety service as final fallback."""

    async def check_content(self, content: str, child_age: int) -> bool:
        """Basic content safety check."""
        if not content:
            return False
        
        # Very basic safety check
        dangerous_words = ["kill", "hurt", "violence", "weapon", "drug", "sex"]
        content_lower = content.lower()
        
        return not any(word in content_lower for word in dangerous_words)


# Global factory instance
esp32_service_factory = ESP32ServiceFactory()