"""
Consolidated Service Registry - Explicit Factory Pattern
=======================================================
هذا الملف مسؤول عن تعريف جميع الخدمات (Services) والـ repositories بشكل واضح وصريح.
كل خدمة يتم تعريفها مع توثيق dependencies الخاصة بها، ولا توجد أي dependencies غامضة أو غير موثقة.
يجب حذف أي تعليق أو استيراد غير مستخدم أو غير واضح.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, TypeVar, List


# Explicit imports: كل خدمة وكل repository يجب أن يكون معرف بوضوح
from src.application.services.ai_service import ConsolidatedAIService
from src.application.services.user_service import UserService
from src.application.services.child_safety_service import ConsolidatedChildSafetyService
from src.services.conversation_service import ConsolidatedConversationService

from src.infrastructure.config.validator import COPPAValidator
from src.adapters.database_production import (
    ProductionUserRepository,
    ProductionChildRepository,
    ProductionConversationRepository,
    ProductionMessageRepository,
    ProductionConsentRepository,
)

import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceRegistry:
    """
    Centralized service registry for dependency injection.
    كل خدمة يتم تعريفها بنمط Explicit Factory Pattern مع توثيق dependencies.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        تهيئة registry مع جميع الخدمات والـ repositories بشكل واضح.
        Args:
            config: إعدادات التطبيق (اختياري)
        """
        self.config = config or {}
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

        # تسجيل جميع الخدمات بشكل صريح
        self._register_consolidated_services()

        logger.info("Service Registry initialized")

    # SERVICE REGISTRATION METHODS

    def _register_consolidated_services(self) -> None:
        """
        تسجيل جميع الخدمات مع dependencies بشكل واضح وصريح.
        كل خدمة يتم تعريفها بنمط Explicit Factory Pattern.
        """

        # تعريف الـ repositories بشكل واضح
        user_repository = ProductionUserRepository()
        child_repository = ProductionChildRepository()
        conversation_repository = ProductionConversationRepository()
        message_repository = ProductionMessageRepository()
        consent_repository = ProductionConsentRepository()
        # Notification repositories
        from src.infrastructure.database.production_notification_repository import ProductionNotificationRepository, ProductionDeliveryRecordRepository
        notification_repository = ProductionNotificationRepository()
        delivery_record_repository = ProductionDeliveryRecordRepository()
        coppa_validator = COPPAValidator()

        # تعريف الخدمات مع dependencies بشكل صريح
        self._singletons["ai_service"] = ConsolidatedAIService()
        self._singletons["user_service"] = UserService(
            user_repository, child_repository
        )
        self._singletons["child_safety_service"] = ConsolidatedChildSafetyService(
            coppa_validator, consent_repository
        )
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        notification_service = loop.run_until_complete(self.get_service("notification_service"))
        self._singletons["conversation_service"] = ConsolidatedConversationService(
            conversation_repository,
            message_repository,
            notification_service=notification_service
        )


        # Register notification repositories as factories
        self.register_factory("notification_repository", self._create_notification_repository)
        self.register_factory("delivery_record_repository", self._create_delivery_record_repository)

        # Register production notification service as singleton
        self.register_singleton("notification_service", self._create_notification_service, dependencies=["notification_repository", "delivery_record_repository"])
    async def _create_notification_service(self, **dependencies):
        """Create ProductionNotificationService instance (production)."""
        from src.services.notification_service_production import ProductionNotificationService
        service = ProductionNotificationService()
        await service.initialize()
        return service
async def get_notification_service():
    """Convenience function to get ProductionNotificationService."""
    registry = await get_service_registry()
    return await registry.get_service("notification_service")

        # Register notification service (to be implemented in notification_service_production.py)
        # self.register_singleton("notification_service", self._create_notification_service, dependencies=["notification_repository", "delivery_record_repository"])

    async def _create_notification_repository(self) -> Any:
        """Create Notification repository instance (production)."""
        session = await self._get_db_session()
        from src.infrastructure.database.production_notification_repository import ProductionNotificationRepository
        return ProductionNotificationRepository(session)

    async def _create_delivery_record_repository(self) -> Any:
        """Create DeliveryRecord repository instance (production)."""
        session = await self._get_db_session()
        from src.infrastructure.database.production_notification_repository import ProductionDeliveryRecordRepository
        return ProductionDeliveryRecordRepository(session)

# Convenience functions for notification repositories (outside the class)
async def get_notification_repository():
    """Convenience function to get Notification repository."""
    registry = await get_service_registry()
    return await registry.get_service("notification_repository")

async def get_delivery_record_repository():
    """Convenience function to get DeliveryRecord repository."""
    registry = await get_service_registry()
    return await registry.get_service("delivery_record_repository")

        # توثيق dependencies لكل خدمة:
        # ai_service: لا يعتمد على repositories مباشرة (حسب الكود الحالي)
        # user_service: يعتمد على user_repository و child_repository
        # child_safety_service: يعتمد على coppa_validator و consent_repository
        # conversation_service: يعتمد على conversation_repository و message_repository
        self.register_singleton(
            service_name="conversation_service",
            factory=self._create_conversation_service,
            dependencies=["conversation_repository", "message_repository"],
        )

        # Register Audio Service (Singleton - manages audio processing pipeline)
        self.register_singleton(
            service_name="audio_service",
            factory=self._create_audio_service,
            dependencies=["tts_service", "stt_provider"],
        )

        # Register repository dependencies (would be actual implementations)
        self.register_factory("user_repository", self._create_user_repository)
        self.register_factory("child_repository", self._create_child_repository)
        self.register_factory(
            "conversation_repository", self._create_conversation_repository
        )
        self.register_factory("message_repository", self._create_message_repository)
        self.register_factory("consent_repository", self._create_consent_repository)

        # Register utility services
        self.register_singleton("coppa_validator", self._create_coppa_validator)
        self.register_singleton("safety_monitor", self._create_safety_monitor)
        self.register_singleton("ai_provider", self._create_ai_provider)

        # Register audio provider dependencies
        self.register_singleton("tts_service", self._create_tts_service)
        self.register_singleton("stt_provider", self._create_stt_provider)

    def register_singleton(
        self,
        service_name: str,
        factory: callable,
        dependencies: Optional[List[str]] = None,
    ) -> None:
        """Register a singleton service.

        Args:
            service_name: Name to register service under
            factory: Factory function to create service
            dependencies: List of dependency service names
        """
        self._singletons[service_name] = {
            "factory": factory,
            "dependencies": dependencies or [],
            "instance": None,
        }

        # Sanitize service name for logging
        safe_service_name = service_name.replace("\n", "").replace("\r", "")[:100]
        logger.debug(f"Registered singleton service: {safe_service_name}")

    def register_factory(
        self,
        service_name: str,
        factory: callable,
        dependencies: Optional[List[str]] = None,
    ) -> None:
        """Register a factory service (new instance each time).

        Args:
            service_name: Name to register service under
            factory: Factory function to create service
            dependencies: List of dependency service names
        """
        self._factories[service_name] = {
            "factory": factory,
            "dependencies": dependencies or [],
        }

        # Sanitize service name for logging
        safe_service_name = service_name.replace("\n", "").replace("\r", "")[:100]
        logger.debug(f"Registered factory service: {safe_service_name}")

    # =============================================================================
    # SERVICE RESOLUTION METHODS
    # =============================================================================

    async def get_service(self, service_name: str) -> Any:
        """Get service instance by name.

        Args:
            service_name: Name of service to resolve

        Returns:
            Service instance

        Raises:
            KeyError: If service not found
            Exception: If service creation fails
        """
        async with self._lock:
            # Check singletons first
            if service_name in self._singletons:
                singleton_config = self._singletons[service_name]

                # Return existing instance if available
                if singleton_config["instance"] is not None:
                    return singleton_config["instance"]

                # Create new singleton instance
                dependencies = await self._resolve_dependencies(
                    singleton_config["dependencies"]
                )
                instance = await self._create_service_instance(
                    singleton_config["factory"], dependencies
                )

                # Cache singleton instance
                singleton_config["instance"] = instance
                return instance

            # Check factories
            if service_name in self._factories:
                factory_config = self._factories[service_name]
                dependencies = await self._resolve_dependencies(
                    factory_config["dependencies"]
                )
                return await self._create_service_instance(
                    factory_config["factory"], dependencies
                )

            # Service not found
            # Sanitize service name for error message
            safe_service_name = service_name.replace("\n", "").replace("\r", "")[:100]
            raise KeyError(f"Service not registered: {safe_service_name}")

    async def get_ai_service(self) -> ConsolidatedAIService:
        """Get AI service instance."""
        return await self.get_service("ai_service")

    async def get_user_service(self) -> UserService:
        """Get User service instance."""
        return await self.get_service("user_service")

    async def get_child_safety_service(self) -> ConsolidatedChildSafetyService:
        """Get Child Safety service instance."""
        return await self.get_service("child_safety_service")

    async def get_conversation_service(self) -> ConsolidatedConversationService:
        """Get Conversation service instance."""
        return await self.get_service("conversation_service")

    async def get_audio_service(self):
        """Get Audio service instance."""
        return await self.get_service("audio_service")

    # SERVICE FACTORY METHODS

    async def _create_ai_service(self, **dependencies) -> ConsolidatedAIService:
        """Create AI service instance (production, consolidated)."""
        from src.infrastructure.config.production_config import get_config

        config = get_config()
        ai_provider = dependencies.get("ai_provider")
        safety_monitor = dependencies.get("safety_monitor")
        logger = StructuredLogger("ai_service")

        # Get Redis configuration
        redis_url = getattr(config, "REDIS_URL", "redis://localhost:6379")

        return ConsolidatedAIService(
            ai_provider=ai_provider,
            safety_monitor=safety_monitor,
            logger=logger,
            redis_url=redis_url,
        )

    async def _create_user_service(self, **dependencies) -> UserService:
        """Create User service instance (production, consolidated)."""
        user_repository = dependencies.get("user_repository")
        child_repository = dependencies.get("child_repository")
        logger = StructuredLogger("user_service")
        session_timeout = self.config.get("session_timeout_minutes", 30)
        return UserService(
            user_repository=user_repository,
            child_repository=child_repository,
            logger=logger,
            session_timeout_minutes=session_timeout,
        )

    async def _create_child_safety_service(
        self, **dependencies
    ) -> ConsolidatedChildSafetyService:
        """Create Child Safety service instance (production, consolidated)."""
        # Pass dependencies as config dict, matching the actual constructor
        config = {
            "coppa_validator": dependencies.get("coppa_validator"),
            "consent_repository": dependencies.get("consent_repository"),
        }
        return ChildSafetyService(config=config)

    async def _create_audio_service(self, **dependencies):
        """Create Audio service instance (production, consolidated)."""
        from src.application.services.audio_service import AudioService
        from src.application.services.audio_validation_service import (
            AudioValidationService,
        )
        from src.application.services.audio_streaming_service import (
            AudioStreamingService,
        )
        from src.application.services.audio_safety_service import AudioSafetyService
        from src.infrastructure.logging.structured_logger import StructuredLogger

        logger = StructuredLogger("audio_service")

        # Get dependencies
        tts_service = dependencies.get("tts_service")
        stt_provider = dependencies.get("stt_provider")

        # Create service dependencies - NO NONE VALUES
        validation_service = AudioValidationService(logger=logger)
        streaming_service = AudioStreamingService(buffer_size=4096, logger=logger)
        safety_service = AudioSafetyService(logger=logger)

        # Create production TTS cache service
        from src.infrastructure.caching.production_tts_cache_service import (
            ProductionTTSCacheService,
        )

        cache_service = ProductionTTSCacheService(
            enabled=True, default_ttl_seconds=3600, max_cache_size_mb=1024
        )

        return AudioService(
            stt_provider=stt_provider,
            tts_service=tts_service,
            validation_service=validation_service,
            streaming_service=streaming_service,
            safety_service=safety_service,
            cache_service=cache_service,
            logger=logger,
        )

    async def _create_conversation_service(
        self, **dependencies
    ) -> ConsolidatedConversationService:
        """Create Conversation service instance (production, consolidated)."""
        conversation_repository = dependencies.get("conversation_repository")
        message_repository = dependencies.get("message_repository")
        return ConsolidatedConversationService(
            conversation_repository=conversation_repository,
            message_repository=message_repository,
        )

    # =============================================================================
    # REPOSITORY FACTORY METHODS
    # =============================================================================

    async def _create_user_repository(self) -> Any:
        """Create User repository instance (production)."""
        session = await self._get_db_session()
        return ProductionUserRepository(session)

    async def _create_child_repository(self) -> Any:
        """Create Child repository instance (production)."""
        session = await self._get_db_session()
        return ProductionChildRepository(session)

    async def _create_conversation_repository(self) -> Any:
        """Create Conversation repository instance (production)."""
        session = await self._get_db_session()
        return ProductionConversationRepository(session)

    async def _create_message_repository(self) -> Any:
        """Create Message repository instance (production)."""
        session = await self._get_db_session()
        return ProductionMessageRepository(session)

    async def _create_consent_repository(self) -> Any:
        """Create Consent repository instance (production)."""
        session = await self._get_db_session()
        return ProductionConsentRepository(session)

    # Add a method to get the DB session (to be implemented according to your DB setup)
    async def _get_db_session(self):
        """Get async DB session from production database manager."""
        # أفضل حل إنتاجي: استخدم جلسة SQLAlchemy async session مباشرة
        from src.adapters.database_production import _connection_manager

        # تأكد من تهيئة الاتصال إذا لزم الأمر
        if not _connection_manager._initialized:
            await _connection_manager.initialize()
        return await _connection_manager.get_async_session()

    async def _create_coppa_validator(self) -> COPPAValidator:
        """Create COPPA validator instance."""
        return COPPAValidator()

    async def _create_safety_monitor(self) -> Any:
        """Create production SafetyMonitor instance."""
        from src.application.services.child_safety_service import ChildSafetyService

        logger.info("Creating Production SafetyMonitor instance")
        return ChildSafetyService()

    async def _create_tts_service(self) -> Any:
        """Create production TTS service instance with multi-provider support."""
        from src.infrastructure.audio.openai_tts_provider import OpenAITTSProvider
        from src.infrastructure.audio.elevenlabs_tts_provider import (
            ElevenLabsTTSProvider,
        )
        from src.infrastructure.caching.production_tts_cache_service import (
            ProductionTTSCacheService,
        )
        from src.infrastructure.config.production_config import get_config

        config = get_config()

        # Create shared cache service
        cache_service = ProductionTTSCacheService(
            enabled=True, default_ttl_seconds=3600, max_cache_size_mb=1024
        )

        # Determine which TTS provider to use based on configuration
        tts_provider = getattr(config, "TTS_PROVIDER", "openai").lower()

        if tts_provider == "elevenlabs":
            # Create ElevenLabs TTS provider
            api_key = getattr(config, "ELEVENLABS_API_KEY", None)
            if not api_key:
                raise RuntimeError(
                    "ELEVENLABS_API_KEY is required for ElevenLabs TTS service"
                )

            logger.info("Creating ElevenLabs TTS provider for production")
            return ElevenLabsTTSProvider(api_key=api_key, cache_service=cache_service)

        elif tts_provider == "openai":
            # Create OpenAI TTS provider (default)
            api_key = getattr(config, "OPENAI_API_KEY", None)
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is required for OpenAI TTS service")

            logger.info("Creating OpenAI TTS provider for production")
            return OpenAITTSProvider(
                api_key=api_key, cache_service=cache_service, model="tts-1"
            )

        else:
            raise RuntimeError(
                f"Unsupported TTS provider: {tts_provider}. Supported providers: openai, elevenlabs"
            )

    async def _create_stt_provider(self) -> Any:
        """Create production STT provider instance."""
        # For now, return a placeholder STT provider
        # This would be replaced with actual STT implementation
        logger.info("Creating placeholder STT provider (to be implemented)")

        class PlaceholderSTTProvider:
            """Placeholder STT provider for future implementation."""

            async def transcribe_audio(self, audio_data: bytes) -> str:
                """Placeholder transcription method."""
                return "STT not implemented yet"

            async def health_check(self) -> bool:
                """Health check placeholder."""
                return True

        return PlaceholderSTTProvider()

    async def _create_ai_provider(self) -> Any:
        """Create production AI provider instance."""
        from src.adapters.providers.openai_provider import ProductionOpenAIProvider
        from src.infrastructure.config.production_config import get_config

        config = get_config()
        api_key = getattr(config, "OPENAI_API_KEY", None)
        model = getattr(config, "OPENAI_MODEL", "gpt-3.5-turbo")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for AI provider")

        return ProductionOpenAIProvider(api_key=api_key, model=model, config=config)

    # UTILITY METHODS

    async def _resolve_dependencies(
        self, dependency_names: List[str]
    ) -> Dict[str, Any]:
        """Resolve all dependencies for a service.

        Args:
            dependency_names: List of dependency service names

        Returns:
            Dictionary mapping dependency names to instances
        """
        dependencies = {}

        for dep_name in dependency_names:
            try:
                dependencies[dep_name] = await self.get_service(dep_name)
            except KeyError:
                logger.error(f"Dependency not found: {dep_name}", exc_info=True)
                dependencies[dep_name] = None
            except Exception as e:  # noqa: E722
                logger.error(
                    f"Failed to resolve dependency {dep_name}: {e}", exc_info=True
                )
                dependencies[dep_name] = None

        return dependencies

    async def _create_service_instance(
        self,
        factory: callable,
        dependencies: Dict[str, Any],
    ) -> Any:
        """Create service instance using factory and dependencies.

        Args:
            factory: Factory function
            dependencies: Resolved dependencies

        Returns:
            Service instance
        """
        try:
            if asyncio.iscoroutinefunction(factory):
                return await factory(**dependencies)
            else:
                return factory(**dependencies)
        except TypeError as e:
            logger.error(
                f"Service creation failed due to type error: {e}", exc_info=True
            )
            raise
        except Exception as e:  # noqa: E722
            logger.error(f"Service creation failed: {e}", exc_info=True)
            raise

    async def shutdown(self) -> None:
        """Shutdown all services and clean up resources."""
        logger.info("Shutting down service registry...")

        # Shutdown singletons
        for service_name, config in self._singletons.items():
            instance = config.get("instance")
            if instance and hasattr(instance, "shutdown"):
                try:
                    await instance.shutdown()
                    logger.debug(f"Shutdown service: {service_name}")
                except Exception as e:  # noqa: E722
                    logger.error(
                        f"Error shutting down {service_name}: {e}", exc_info=True
                    )

        # Clear all registrations
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()

        logger.info("Service registry shutdown complete")

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all registered services."""
        return {
            "registry_status": "healthy",
            "registered_singletons": list(self._singletons.keys()),
            "registered_factories": list(self._factories.keys()),
            "active_singletons": [
                name
                for name, config in self._singletons.items()
                if config["instance"] is not None
            ],
            "total_services": len(self._singletons) + len(self._factories),
        }


# =============================================================================
# GLOBAL SERVICE REGISTRY INSTANCE
# =============================================================================

# Global registry instance (would be configured in application startup)
_registry: Optional[ServiceRegistry] = None


async def get_service_registry(
    config: Optional[Dict[str, Any]] = None,
) -> ServiceRegistry:
    """Get or create global service registry instance.

    Args:
        config: Optional configuration for new registry

    Returns:
        Service registry instance
    """
    global _registry

    if _registry is None:
        _registry = ServiceRegistry(config)

    return _registry


async def get_ai_service() -> ConsolidatedAIService:
    """Convenience function to get AI service."""
    registry = await get_service_registry()
    return await registry.get_ai_service()


async def get_user_service() -> UserService:
    """Convenience function to get User service."""
    registry = await get_service_registry()
    return await registry.get_user_service()


async def get_child_safety_service() -> ConsolidatedChildSafetyService:
    """Convenience function to get Child Safety service."""
    registry = await get_service_registry()
    return await registry.get_child_safety_service()


async def get_conversation_service() -> ConsolidatedConversationService:
    """Convenience function to get Conversation service."""
    registry = await get_service_registry()
    return await registry.get_conversation_service()


async def get_notification_service():
    """Get production notification service."""
    registry = await get_service_registry()
    return await registry.get_service("notification_service")


async def get_audio_service():
    """Convenience function to get Audio service."""
    registry = await get_service_registry()
    return await registry.get_audio_service()
