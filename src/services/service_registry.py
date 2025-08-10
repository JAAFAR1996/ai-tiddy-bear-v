"""
Consolidated Service Registry - Clean Async Pattern
=================================================
هذا الملف مسؤول عن تعريف جميع الخدمات (Services) والـ repositories بشكل واضح وصريح.
جميع الخدمات الـ async يتم تهيئتها فقط عند الطلب، وليس في __init__.
كل خدمة تحتاج dependency تأخذها عبر injection صريح.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, TypeVar, List
from src.infrastructure.config.production_config import ProductionConfig
from src.infrastructure.config.validator import (
    validate_production_config,
    ConfigurationValidationError,
)

# Explicit imports: كل خدمة وكل repository يجب أن يكون معرف بوضوح
from src.application.services.ai_service import ConsolidatedAIService
from src.application.services.user_service import UserService
from src.application.services.child_safety_service import ConsolidatedChildSafetyService
from src.services.conversation_service import ConsolidatedConversationService
from src.infrastructure.logging.structured_logger import StructuredLogger
from src.application.services.child_safety_service import ChildSafetyService

from src.infrastructure.config.validator import COPPAValidator
from src.adapters.database_production import (
    ProductionUserRepository,
    ProductionChildRepository,
    ProductionConversationRepository,
    ProductionMessageRepository,
    ProductionConsentRepository,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceRegistry:
    def find_dead_registrations(self) -> dict:
        """
        Detect any registered factory or singleton that has never been instantiated (dead registration).
        Returns a dict with lists of dead singletons and factories.
        Logs the result in the audit log.
        """
        dead_singletons = []
        for name, entry in self._singletons.items():
            if entry.get("instance") is None:
                dead_singletons.append(name)
        # Factories: can't track instantiation directly, so check for usage counter
        # Optionally, you could add a counter in get_service if you want more granularity
        dead_factories = [name for name in self._factories.keys()]
        result = {"dead_singletons": dead_singletons, "dead_factories": dead_factories}
        self._audit("dead_registrations_check", result)
        return result

    """
    Centralized service registry for dependency injection, with strict config validation, readiness checks, and audit logging.
    جميع الخدمات الـ async يتم تهيئتها فقط عند الطلب via get_service().
    """

    def __init__(self, config: Optional[dict] = None) -> None:
        """
        Initialize registry, validate config, and register factories.
        Args:
            config: Application config (dict or ProductionConfig)
        """
        import os

        self._audit_log: list = []
        self._audit_logger = StructuredLogger("service_registry_audit")

        # Fail-fast: require config in production
        if config is None or not config:
            if os.getenv("ENVIRONMENT", "development") == "production":
                raise RuntimeError(
                    "[ServiceRegistry] Production config must be provided explicitly. No global/implicit config allowed."
                )
        # Accept either dict or ProductionConfig
        if isinstance(config, dict):
            self.config = ProductionConfig(**config)
        elif isinstance(config, ProductionConfig):
            self.config = config
        else:
            self.config = config or {}

        # Strict config validation (fail-fast)
        try:
            self._audit("config_validation_start", details={})
            if isinstance(self.config, ProductionConfig):
                import asyncio

                # Run async validation synchronously at startup
                loop = (
                    asyncio.get_event_loop()
                    if asyncio.get_event_loop().is_running()
                    else asyncio.new_event_loop()
                )
                result = loop.run_until_complete(
                    validate_production_config(self.config)
                )
                if not result["valid"]:
                    self._audit("config_validation_failed", details=result)
                    raise ConfigurationValidationError(result["errors"])
                self._audit("config_validation_passed", details=result)
        except Exception as e:
            self._audit("config_validation_exception", details={"error": str(e)})
            raise

        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, callable] = {}
        self._singletons: Dict[str, Dict[str, Any]] = {}
        self._instances: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

        self._register_all_factories()
        logger.info("Service Registry initialized with factories only")
        self._audit(
            "registry_initialized",
            details={
                "config_keys": (
                    list(self.config.__dict__.keys())
                    if hasattr(self.config, "__dict__")
                    else list(self.config.keys())
                )
            },
        )

    def _audit(self, event: str, details: dict):
        entry = {"event": event, "timestamp": time.time(), "details": details}
        self._audit_log.append(entry)
        self._audit_logger.info(f"AUDIT: {event}", **details)

    async def check_readiness(self) -> dict:
        """
        Check readiness of all critical dependencies: DB, Redis, OpenAI, etc. with retry and timeout.
        Returns a dict with status and details. Raises if not ready.
        """
        from tenacity import (
            AsyncRetrying,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type,
            RetryError,
        )

        status = {"db": False, "redis": False, "openai": False, "errors": []}
        logger = self._audit_logger

        async def db_check():
            session = await self._get_db_session()
            if not session:
                raise RuntimeError("DB session unavailable")
            return True

        async def redis_check():
            import aioredis

            redis_url = getattr(self.config, "REDIS_URL", None)
            if not redis_url:
                raise RuntimeError("REDIS_URL not set")
            redis = await aioredis.from_url(
                redis_url, encoding="utf-8", decode_responses=True
            )
            pong = await redis.ping()
            await redis.close()
            if not pong:
                raise RuntimeError("Redis ping failed")
            return True

        async def openai_check():
            import openai

            openai.api_key = getattr(self.config, "OPENAI_API_KEY", None)
            if not openai.api_key:
                raise RuntimeError("OPENAI_API_KEY not set")
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: openai.Model.list()
            )
            return True

        async def run_with_retry(fn, name):
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=8),
                    retry=retry_if_exception_type(Exception),
                    reraise=True,
                ):
                    with attempt:
                        logger.info(
                            f"Readiness check: {name} attempt {attempt.retry_state.attempt_number}"
                        )
                        return await asyncio.wait_for(fn(), timeout=5)
            except RetryError as re:
                logger.error(f"{name} readiness failed after retries: {re}")
                status["errors"].append(f"{name}: {re}")
                return False
            except Exception as e:
                logger.error(f"{name} readiness error: {e}")
                status["errors"].append(f"{name}: {e}")
                return False

        status["db"] = await run_with_retry(db_check, "DB")
        status["redis"] = await run_with_retry(redis_check, "Redis")
        status["openai"] = await run_with_retry(openai_check, "OpenAI")

        self._audit("readiness_check", details=status)
        if not all([status["db"], status["redis"], status["openai"]]):
            raise RuntimeError(f"Readiness check failed: {status}")
        return status

    def get_dependency_tree(self) -> dict:
        """
        Return a tree of all registered services and their dependencies.
        """
        tree = {}
        for name, entry in {**self._singletons, **self._factories}.items():
            tree[name] = list(entry.get("dependencies", []))
        self._audit("dependency_tree_requested", details=tree)
        return tree

    def _register_all_factories(self) -> None:
        """
        تسجيل جميع الخدمات كـ factories بدون تهيئة فورية.
        كل خدمة async سيتم تهيئتها فقط عند استدعاء get_service().
        """

        # Register repositories as factories
        self.register_factory("user_repository", self._create_user_repository)
        self.register_factory("child_repository", self._create_child_repository)
        self.register_factory(
            "conversation_repository", self._create_conversation_repository
        )
        self.register_factory("message_repository", self._create_message_repository)
        self.register_factory("consent_repository", self._create_consent_repository)
        self.register_factory(
            "notification_repository", self._create_notification_repository
        )
        self.register_factory(
            "delivery_record_repository", self._create_delivery_record_repository
        )

        # Register utility services as factories
        self.register_factory("coppa_validator", self._create_coppa_validator)
        self.register_factory("safety_monitor", self._create_safety_monitor)
        self.register_factory("ai_provider", self._create_ai_provider)

        # Register core services as factories
        self.register_factory("ai_service", self._create_ai_service)
        self.register_factory("user_service", self._create_user_service)
        self.register_factory("child_safety_service", self._create_child_safety_service)

        # Async services - تهيئة فقط عند الطلب
        self.register_factory("notification_service", self._create_notification_service)
        self.register_factory("conversation_service", self._create_conversation_service)

        # Audio services
        self.register_factory("tts_service", self._create_tts_service)
        self.register_factory("stt_provider", self._create_stt_provider)
        self.register_factory("audio_service", self._create_audio_service)

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

        # Register utility services
        self.register_singleton("coppa_validator", self._create_coppa_validator)
        self.register_singleton("safety_monitor", self._create_safety_monitor)
        self.register_singleton("ai_provider", self._create_ai_provider)

        # Register audio provider dependencies
        self.register_singleton("tts_service", self._create_tts_service)
        self.register_singleton("stt_provider", self._create_stt_provider)

    async def _create_notification_service(self, **dependencies):
        """Create ProductionNotificationService instance (production)."""
        from src.application.services.notification.notification_service_main import (
            NotificationService as ProductionNotificationService,
        )

        service = ProductionNotificationService()
        await service.initialize()
        return service

    async def _create_notification_repository(self) -> Any:
        """Create Notification repository instance (production)."""
        session = await self._get_db_session()
        from src.infrastructure.database.production_notification_repository import (
            ProductionNotificationRepository,
        )

        return ProductionNotificationRepository(session)

    async def _create_delivery_record_repository(self) -> Any:
        """Create DeliveryRecord repository instance (production)."""
        session = await self._get_db_session()
        from src.infrastructure.database.production_notification_repository import (
            ProductionDeliveryRecordRepository,
        )

        return ProductionDeliveryRecordRepository(session)

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

    async def get_service(
        self, service_name: str, dependencies: Optional[Dict[str, Any]] = None
    ) -> Any:
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
            # Always ensure config is injected in dependencies
            def ensure_config_in_deps(deps: Optional[Dict[str, Any]]) -> Dict[str, Any]:
                deps = deps.copy() if deps else {}
                if "config" not in deps and self.config:
                    deps["config"] = self.config
                return deps

            # Check singletons first
            if service_name in self._singletons:
                singleton_config = self._singletons[service_name]
                # Return existing instance if available
                if singleton_config["instance"] is not None:
                    return singleton_config["instance"]
                # Create new singleton instance
                resolved_deps = await self._resolve_dependencies(
                    singleton_config["dependencies"]
                )
                resolved_deps = ensure_config_in_deps(resolved_deps)
                instance = await self._create_service_instance(
                    singleton_config["factory"], resolved_deps
                )
                singleton_config["instance"] = instance
                return instance
            # Check factories
            if service_name in self._factories:
                factory_config = self._factories[service_name]
                resolved_deps = await self._resolve_dependencies(
                    factory_config["dependencies"]
                )
                resolved_deps = ensure_config_in_deps(resolved_deps)
                return await self._create_service_instance(
                    factory_config["factory"], resolved_deps
                )
            # Service not found
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
        config = dependencies.get("config")
        if config is None:
            raise ValueError("config must be provided explicitly to _create_ai_service")
        ai_provider = dependencies.get("ai_provider")
        safety_monitor = dependencies.get("safety_monitor")
        logger = StructuredLogger("ai_service")
        redis_url = getattr(config, "REDIS_URL", "redis://localhost:6379")
        return ConsolidatedAIService(
            ai_provider=ai_provider,
            safety_monitor=safety_monitor,
            logger=logger,
            redis_url=redis_url,
            config=config,
        )

    async def _create_user_service(self, **dependencies) -> UserService:
        """Create User service instance (production, consolidated)."""
        config = dependencies.get("config")
        if config is None:
            raise ValueError(
                "config must be provided explicitly to _create_user_service"
            )
        user_repository = dependencies.get("user_repository")
        child_repository = dependencies.get("child_repository")
        logger = StructuredLogger("user_service")
        session_timeout = getattr(config, "SESSION_TIMEOUT_MINUTES", 30)
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

        # Get required dependencies
        if conversation_repository is None:
            conversation_repository = await self.get_service("conversation_repository")
        if message_repository is None:
            message_repository = await self.get_service("message_repository")

        # Get notification service and logger
        notification_service = await self.get_service("notification_service")

        # Create logger
        import logging

        logger = logging.getLogger("conversation_service")

        return ConsolidatedConversationService(
            conversation_repository=conversation_repository,
            message_repository=message_repository,
            notification_service=notification_service,
            logger=logger,
        )

    # =============================================================================
    # REPOSITORY FACTORY METHODS
    # =============================================================================

    async def _create_user_repository(self) -> Any:
        """Create User repository instance (production)."""
        session = await self._get_db_session()
        config = self.config
        return ProductionUserRepository(session, config=config)

    async def _create_child_repository(self) -> Any:
        """Create Child repository instance (production)."""
        session = await self._get_db_session()
        config = self.config
        return ProductionChildRepository(session, config=config)

    async def _create_conversation_repository(self) -> Any:
        """Create Conversation repository instance (production)."""
        session = await self._get_db_session()
        config = self.config
        return ProductionConversationRepository(session, config=config)

    async def _create_message_repository(self) -> Any:
        """Create Message repository instance (production)."""
        session = await self._get_db_session()
        config = self.config
        return ProductionMessageRepository(session, config=config)

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

    async def _create_tts_service(self, **dependencies) -> Any:
        """Create production TTS service instance with multi-provider support."""
        config = dependencies.get("config")
        if config is None:
            raise ValueError(
                "config must be provided explicitly to _create_tts_service"
            )
        from src.infrastructure.audio.openai_tts_provider import OpenAITTSProvider
        from src.infrastructure.audio.elevenlabs_tts_provider import (
            ElevenLabsTTSProvider,
        )
        from src.infrastructure.caching.production_tts_cache_service import (
            ProductionTTSCacheService,
        )

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

    async def _create_stt_provider(self, **dependencies) -> Any:
        """Create production STT provider instance with local Whisper."""
        from src.infrastructure.audio.whisper_stt_provider import (
            WhisperSTTProviderFactory,
        )
        from src.infrastructure.logging.structured_logger import StructuredLogger

        config = dependencies.get("config")
        if config is None:
            raise ValueError(
                "config must be provided explicitly to _create_stt_service"
            )
        # Get STT configuration from config
        stt_config = {
            "whisper_model": getattr(config, "WHISPER_MODEL_SIZE", "base"),
            "device": getattr(config, "WHISPER_DEVICE", None),  # Auto-detect
            "default_language": getattr(config, "DEFAULT_STT_LANGUAGE", "auto"),
            "temperature": getattr(config, "WHISPER_TEMPERATURE", 0.0),
            "max_duration": getattr(config, "MAX_AUDIO_DURATION_SECONDS", 300),
            "cache_enabled": getattr(config, "STT_CACHE_ENABLED", True),
            "safety_filtering": getattr(config, "STT_SAFETY_FILTERING", True),
        }
        stt_logger = StructuredLogger("whisper_stt")
        stt_logger.info("Creating Whisper STT provider for production", **stt_config)
        # Create production-optimized Whisper STT provider
        stt_provider = WhisperSTTProviderFactory.create_production_provider(
            config=stt_config, logger=stt_logger
        )
        # Initialize the provider
        initialization_success = await stt_provider.initialize()
        if not initialization_success:
            stt_logger.error("Failed to initialize Whisper STT provider")
            raise RuntimeError("Whisper STT provider initialization failed")
        # Optimize for real-time performance
        await stt_provider.optimize_for_realtime()
        stt_logger.info("Whisper STT provider created and initialized successfully")
        return stt_provider

    async def _create_ai_provider(self, **dependencies) -> Any:
        """Create production AI provider instance."""
        from src.adapters.providers.openai_provider import ProductionOpenAIProvider

        config = dependencies.get("config")
        if config is None:
            raise ValueError(
                "config must be provided explicitly to _create_openai_provider"
            )
        api_key = getattr(config, "OPENAI_API_KEY", None)
        model = getattr(config, "OPENAI_MODEL", "gpt-3.5-turbo")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for AI provider")
        return ProductionOpenAIProvider(api_key=api_key, model=model, config=config)

    # UTILITY METHODS

    async def _resolve_dependencies(
        self, dependency_names: List[str]
    ) -> Dict[str, Any]:
        """Resolve all dependencies for a service, always injecting config if missing."""
        dependencies = {}
        for dep_name in dependency_names:
            try:
                dependencies[dep_name] = await self.get_service(dep_name)
            except KeyError:
                logger.error(f"Dependency not found: {dep_name}", exc_info=True)
                dependencies[dep_name] = None
            except Exception as e:
                logger.error(
                    f"Failed to resolve dependency {dep_name}: {e}", exc_info=True
                )
                dependencies[dep_name] = None
        # Always inject config if not present
        if "config" not in dependencies and self.config:
            dependencies["config"] = self.config
        return dependencies

    async def _create_service_instance(
        self,
        factory: callable,
        dependencies: Dict[str, Any],
    ) -> Any:
        """Create service instance using factory and dependencies. Ensure correct type or fail clearly.

        Args:
            factory: Factory function
            dependencies: Resolved dependencies

        Returns:
            Service instance
        """
        try:
            if asyncio.iscoroutinefunction(factory):
                instance = await factory(**dependencies)
            else:
                instance = factory(**dependencies)
        except TypeError as e:
            logger.error(
                f"Service creation failed due to type error: {e}", exc_info=True
            )
            self._audit(
                "service_factory_type_error", {"factory": str(factory), "error": str(e)}
            )
            raise
        except Exception as e:  # noqa: E722
            logger.error(f"Service creation failed: {e}", exc_info=True)
            self._audit(
                "service_factory_exception", {"factory": str(factory), "error": str(e)}
            )
            raise

        # Type check: ensure instance is not None and is an object
        if instance is None or not hasattr(instance, "__class__"):
            msg = f"Factory {factory} did not return a valid instance. Got: {instance}"
            logger.error(msg)
            self._audit(
                "service_factory_invalid_instance",
                {"factory": str(factory), "result": str(instance)},
            )
            raise RuntimeError(msg)
        return instance

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


# Convenience functions for notification repositories
async def get_notification_repository():
    """Convenience function to get Notification repository."""
    registry = await get_service_registry()
    return await registry.get_service("notification_repository")


async def get_delivery_record_repository():
    """Convenience function to get DeliveryRecord repository."""
    registry = await get_service_registry()
    return await registry.get_service("delivery_record_repository")
