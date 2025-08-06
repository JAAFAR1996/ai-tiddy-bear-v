# type annotation imports for DI providers
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, List
import logging
import os
from enum import Enum

# Import services outside TYPE_CHECKING for runtime use
from src.infrastructure.caching.production_tts_cache_service import (
    ProductionTTSCacheService,
)
from src.infrastructure.database.repository import UserRepository

if TYPE_CHECKING:
    # Adapters & repositories
    from src.adapters.database_production import (
        ProductionDatabaseAdapter,
        ProductionChildRepository,
        ProductionUserRepository,
        ProductionConversationRepository,
        ProductionEventRepository,
        ProductionMessageRepository,
    )

    # AI/Child Safety consolidated services
    from src.application.services.ai_service import ConsolidatedAIService
    from src.application.services.child_safety_service import ChildSafetyService

    # Audio service
    from src.application.services.audio_service import AudioService

    # Use case classes
    from src.application.use_cases.manage_child_profile import ManageChildProfileUseCase
    from src.application.use_cases.process_esp32_audio import ProcessESP32AudioUseCase
    from src.application.use_cases.generate_ai_response import GenerateAIResponseUseCase

    # خدمات/Adapters غير موجودة فعلياً في المشروع (تأكد من وجودها أو حذفها)
    # from src.application.services.caching.cache_service import CacheService
    # from src.application.services.security.rate_limiting_service import RateLimitingService
    # from src.application.services.events.event_bus_service import EventBusService
    # from src.application.services.communication.notification_service import NotificationService
    # from src.application.services.auth.authentication_service import AuthenticationService
    # from src.infrastructure.caching.redis_adapter import RedisAdapter
    # from src.infrastructure.communication.email_adapter import SMTPEmailAdapter
    # from src.infrastructure.communication.push_adapter import FCMPushAdapter
    # from src.infrastructure.audio.speech_to_text_adapter import WhisperAdapter
    # from src.infrastructure.audio.text_to_speech_adapter import ElevenLabsAdapter
    # from src.infrastructure.messaging.rabbitmq_adapter import RabbitMQAdapter
    # from src.infrastructure.storage.s3_adapter import S3StorageAdapter
    # from src.infrastructure.websocket.websocket_adapter import FastAPIWebSocketAdapter
    # Services moved to unified implementations
    # ChatService remains in core.services but uses unified components
    # ConversationService moved to services.conversation_service

"""
Professional Dependency Injection Container using Injector

Implements a comprehensive DI container following SOLID principles
and Clean Architecture patterns. All dependencies are injected through
interfaces to eliminate circular dependencies.
"""

from injector import Injector, singleton, provider, Module

from src.interfaces.services import (
    IAIService,
    IChildSafetyService,
    IAuthService,
    IChatService,
    IConversationService,
    IAudioService,
    INotificationService,
    IUserService,
    ICacheService,
    IRateLimitingService,
    IEventBusService,
    IEncryptionService,
)
from src.interfaces.repositories import (
    IUserRepository,
    IChildRepository,
    IConversationRepository,
    IMessageRepository,
)
from src.interfaces.config import IConfiguration
from src.interfaces.providers.tts_provider import (
    ITTSService,
    TTSRequest,
    TTSResult,
    VoiceProfile,
    TTSConfiguration,
    ChildSafetyContext,
    TTSError,
    TTSProviderError,
    TTSConfigurationError,
    TTSUnsafeContentError,
    TTSRateLimitError,
    TTSProviderUnavailableError,
)
from src.shared.audio_types import AudioFormat, AudioQuality, VoiceEmotion, VoiceGender


class ApplicationModule(Module):
    """Main application module with all service bindings."""

    def configure(self, binder):
        """Configure all service bindings."""
        # ========================= CONFIGURATION ============================
        binder.bind(IConfiguration, to=self._get_configuration_service, scope=singleton)
        binder.bind("AppSettings", to=self._get_app_settings, scope=singleton)

        # ================ INFRASTRUCTURE SERVICES ===========================
        binder.bind("DatabaseAdapter", to=self._get_database_adapter, scope=singleton)
        binder.bind("ChildRepository", to=self._get_child_repository)
        binder.bind("UserRepository", to=self._get_user_repository)
        binder.bind("ConversationRepository", to=self._get_conversation_repository)
        binder.bind("EventRepository", to=self._get_event_repository)
        binder.bind("MessageRepository", to=self._get_message_repository)
        binder.bind("AIProvider", to=self._get_ai_provider, scope=singleton)
        binder.bind("TTSProvider", to=self._get_tts_provider, scope=singleton)
        binder.bind(ITTSService, to=self._get_tts_service, scope=singleton)
        binder.bind("SpeechProvider", to=self._get_speech_provider, scope=singleton)
        binder.bind("CacheAdapter", to=self._get_cache_adapter, scope=singleton)

        # ===================== APPLICATION SERVICES =========================
        binder.bind(IAIService, to=self._get_ai_service)
        binder.bind(IChildSafetyService, to=self._get_child_safety_service)
        binder.bind(IAuthService, to=self._get_authentication_service)
        binder.bind(IAudioService, to=self._get_audio_service)
        binder.bind(INotificationService, to=self._get_notification_service)
        binder.bind(IUserService, to=self._get_user_service)
        binder.bind(IChatService, to=self._get_chat_service)
        binder.bind(IConversationService, to=self._get_conversation_service)
        binder.bind(ICacheService, to=self._get_cache_service)
        binder.bind(IRateLimitingService, to=self._get_rate_limiting_service)
        binder.bind(IEventBusService, to=self._get_event_bus_service)
        binder.bind(IEncryptionService, to=self._get_encryption_service)

        # ===================== REPOSITORY BINDINGS =========================
        binder.bind(IUserRepository, to=self._get_user_repository)
        binder.bind(IChildRepository, to=self._get_child_repository)
        binder.bind(IConversationRepository, to=self._get_conversation_repository)
        binder.bind(IMessageRepository, to=self._get_message_repository)

        # =========================== USE CASES =============================
        self._bind_use_cases(binder)

        # ===================== ADDITIONAL ADAPTERS =========================
        self._bind_adapters(binder)

    @provider
    @singleton
    def _get_app_settings(self) -> object:
        # Example: load from config loader
        def _provider(config=None):
            from src.infrastructure.config.production_config import get_config

            return config or get_config()

        return _provider

    @provider
    @singleton
    def _get_ai_provider(self, AppSettings) -> object:
        import os
        from src.infrastructure.external.ai_providers.ai_factory import (
            AIProviderFactory,
        )

        provider_name = getattr(AppSettings, "ai_provider", None) or os.getenv(
            "AI_PROVIDER", "openai"
        )
        api_key = getattr(AppSettings, "openai_api_key", None) or os.getenv(
            "OPENAI_API_KEY"
        )
        return AIProviderFactory.get_provider(provider_name, api_key)

    @provider
    @singleton
    def _get_tts_provider(self, AppSettings) -> object:
        """DEPRECATED: Use _get_tts_service instead."""
        return self._get_tts_service(AppSettings)

    @provider
    @singleton
    def _get_tts_service(self, AppSettings) -> ITTSService:
        """Get production-ready TTS service with factory and caching."""
        env_config = {
            "TTS_PROVIDER": getattr(AppSettings, "tts_provider", None)
            or os.getenv("TTS_PROVIDER", "openai"),
            "OPENAI_API_KEY": getattr(AppSettings, "openai_api_key", None)
            or os.getenv("OPENAI_API_KEY"),
            "OPENAI_TTS_MODEL": os.getenv("OPENAI_TTS_MODEL", "tts-1"),
            "TTS_ENABLE_CACHING": os.getenv("TTS_ENABLE_CACHING", "true"),
            "TTS_CACHE_TTL": os.getenv("TTS_CACHE_TTL", "3600"),
            "TTS_CHILD_SAFETY": os.getenv("TTS_CHILD_SAFETY", "true"),
        }

        # Add TTSProviderFactory implementation at end of container.py
        return self._create_tts_service_directly(env_config)

    @provider
    @singleton
    def _get_tts_cache_service(self, AppSettings) -> "ProductionTTSCacheService":
        """Get Production Redis-based TTS caching service."""
        from src.infrastructure.caching.production_tts_cache_service import (
            ProductionTTSCacheService,
            CompressionLevel,
            CacheStrategy,
        )

        cache_enabled = os.getenv("TTS_CACHE_ENABLED", "true").lower() == "true"
        cache_ttl = int(os.getenv("TTS_CACHE_TTL", "3600"))
        max_cache_size_mb = int(os.getenv("TTS_CACHE_MAX_SIZE_MB", "1024"))
        compression_level = CompressionLevel(
            int(os.getenv("TTS_CACHE_COMPRESSION", "2"))
        )
        cache_strategy = CacheStrategy(os.getenv("TTS_CACHE_STRATEGY", "cost_aware"))

        return ProductionTTSCacheService(
            enabled=cache_enabled,
            default_ttl_seconds=cache_ttl,
            max_cache_size_mb=max_cache_size_mb,
            compression_level=compression_level,
            cache_strategy=cache_strategy,
        )

    @provider
    @singleton
    def _get_speech_provider(self, AppSettings) -> object:
        """Get Whisper STT provider for real-time processing."""
        import os
        from src.infrastructure.audio.whisper_stt_provider import WhisperSTTProvider

        # Use Whisper by default for real-time performance
        provider_name = getattr(AppSettings, "speech_provider", None) or os.getenv(
            "SPEECH_PROVIDER", "whisper"
        )

        if provider_name.lower() == "whisper":
            model_size = getattr(AppSettings, "whisper_model_size", None) or os.getenv(
                "WHISPER_MODEL_SIZE", "base"
            )

            return WhisperSTTProvider(
                model_size=model_size,
                device="auto",  # Auto-detect CUDA/CPU
                language=None,  # Auto-detect Arabic/English
                enable_vad=True,  # Voice Activity Detection
            )
        else:
            # Fallback to factory for other providers
            from src.infrastructure.external.speech_services.speech_provider_factory import (
                SpeechProviderFactory,
            )

            api_key = getattr(AppSettings, "speech_api_key", None) or os.getenv(
                "SPEECH_API_KEY"
            )
            return SpeechProviderFactory.get_provider(provider_name, api_key)

    @provider
    @singleton
    def _get_esp32_realtime_streamer(self) -> object:
        """Get ESP32 real-time audio streamer with optimized settings."""
        from src.infrastructure.streaming.esp32_realtime_streamer import (
            ESP32AudioStreamer,
        )

        return ESP32AudioStreamer(
            buffer_duration=2.0,  # 2-second circular buffer as specified
            chunk_size=1024,  # Optimized chunk size for 300ms latency
            target_latency=0.3,  # 300ms target latency requirement
            auto_reconnect=True,  # Auto-reconnection for reliability
        )

    def _bind_use_cases(self, binder):
        """Bind use case dependencies."""
        binder.bind(
            "ManageChildProfileUseCase", to=self._get_manage_child_profile_use_case
        )
        binder.bind("ProcessESP32AudioUseCase", to=self._get_process_audio_use_case)
        binder.bind(
            "GenerateAIResponseUseCase", to=self._get_generate_ai_response_use_case
        )

    def _bind_adapters(self, binder):
        """Bind adapter dependencies."""
        binder.bind("EmailAdapter", to=self._get_email_adapter)
        binder.bind("PushAdapter", to=self._get_push_adapter)
        binder.bind("SpeechAdapter", to=self._get_speech_adapter)
        binder.bind("TTSAdapter", to=self._get_tts_adapter)
        binder.bind("MessageQueueAdapter", to=self._get_message_queue_adapter)
        binder.bind("FileStorageAdapter", to=self._get_file_storage_adapter)
        binder.bind("WebSocketAdapter", to=self._get_websocket_adapter)

    # ====================== PROVIDER METHODS ======================

    @provider
    @singleton
    def _get_configuration_service(self) -> IConfiguration:
        """Get configuration service instance."""
        from src.infrastructure.config.configuration_adapter import ConfigurationAdapter

        return ConfigurationAdapter()

    @provider
    @singleton
    def _get_database_adapter(self) -> object:
        from src.adapters.database_production import ProductionDatabaseAdapter

        return ProductionDatabaseAdapter()

    @provider
    def _get_child_repository(self, database_adapter) -> object:
        """
        Provides ProductionChildRepository with full DI (session via transactional_session inside repository).
        """
        from src.adapters.database_production import ProductionChildRepository

        return ProductionChildRepository()

    @provider
    def _get_user_repository(self, database_adapter) -> object:
        """
        Provides ProductionUserRepository with full DI (session via transactional_session inside repository).
        """
        from src.adapters.database_production import ProductionUserRepository

        return ProductionUserRepository()

    @provider
    def _get_conversation_repository(self, database_adapter) -> object:
        """
        Provides ProductionConversationRepository with full DI (session via transactional_session inside repository).
        """
        from src.adapters.database_production import ProductionConversationRepository

        return ProductionConversationRepository()

    @provider
    def _get_event_repository(self, database_adapter) -> object:
        """
        Provides ProductionEventRepository with full DI (session via transactional_session inside repository).
        """
        from src.adapters.database_production import ProductionEventRepository

        return ProductionEventRepository()

    @provider
    def _get_message_repository(self, database_adapter) -> object:
        """
        Provides ProductionMessageRepository with full DI (session via transactional_session inside repository).
        """
        from src.adapters.database_production import ProductionMessageRepository

        return ProductionMessageRepository()

    # No longer needed: _get_ai_api_adapter

    @provider
    @singleton
    def _get_cache_adapter(self) -> object:
        """Get production Redis cache adapter."""
        from src.infrastructure.caching.production_redis_cache import ProductionRedisCache
        import os
        
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        return ProductionRedisCache(redis_url=redis_url)

    @provider
    @singleton
    def _get_ai_service(
        self,
        AIProvider,
        child_safety_service: IChildSafetyService,
        AppSettings,
    ) -> object:
        from src.application.services.ai_service import ConsolidatedAIService
        import logging
        import os

        logger = logging.getLogger("ai_teddy_bear.ai_service")

        # Create proper redis_url from settings
        redis_url = getattr(AppSettings, "redis_url", None) or os.getenv(
            "REDIS_URL", "redis://localhost:6379"
        )

        return ConsolidatedAIService(
            ai_provider=AIProvider,
            safety_monitor=child_safety_service,
            logger=logger,
            redis_url=redis_url,
        )

    @provider
    def _get_child_safety_service(
        self, event_repository, cache_service
    ) -> IChildSafetyService:
        from src.application.services.child_safety_service import ChildSafetyService

        return ChildSafetyService()

    @provider
    def _get_authentication_service(
        self, user_repository, encryption_service, cache_service
    ) -> IAuthService:
        """Get authentication service using unified JWT infrastructure."""
        try:
            # Use unified auth infrastructure with advanced JWT features
            from src.infrastructure.security.auth import (
                get_user_authenticator,
                get_authorization_manager,
                get_token_manager,
            )

            # Create wrapper that implements IAuthService interface with enhanced features
            class UnifiedAuthService:
                def __init__(self):
                    self.authenticator = get_user_authenticator()
                    self.authorizer = get_authorization_manager()
                    self.token_manager = get_token_manager()

                async def authenticate_user(
                    self, credentials: Dict[str, Any]
                ) -> Dict[str, Any]:
                    """Authenticate user with credentials and enhanced security tracking."""
                    email = credentials.get("email")
                    password = credentials.get("password")
                    device_info = credentials.get("device_info")
                    ip_address = credentials.get("ip_address")

                    return await self.authenticator.authenticate_user(
                        email, password, device_info, ip_address
                    )

                async def authorize_action(
                    self, user_id: str, action: str, resource: str
                ) -> bool:
                    """Authorize user action on resource."""
                    # Enhanced authorization using token validation
                    # Fetch user role from production database
                    try:
                        import uuid
                        user_repo = UserRepository()
                        user = await user_repo.get_by_id(uuid.UUID(user_id))
                        if user and hasattr(user, 'role'):
                            # Check permissions based on role
                            if str(user.role) == 'admin':
                                return True
                            elif str(user.role) == 'parent':
                                # Parents can access their own resources
                                return resource.startswith(f"user_{user_id}")
                            elif str(user.role) == 'child':
                                # Children have limited access
                                return action in ['read', 'view'] and resource.startswith(f"child_{user_id}")
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch user role: {e}")
                    
                    # Default to denying access if we can't verify
                    return False

                async def generate_token(
                    self, user_id: str, permissions: List[str], **kwargs
                ) -> str:
                    """Generate authentication token with advanced features."""
                    from src.infrastructure.security.jwt_advanced import TokenType

                    token_data = {
                        "sub": user_id,
                        "permissions": permissions,
                        "email": kwargs.get("email", ""),
                        "role": kwargs.get("role", "parent"),
                        "user_type": kwargs.get("user_type", "parent"),
                        "device_info": kwargs.get("device_info"),
                        "ip_address": kwargs.get("ip_address"),
                    }

                    # Use advanced JWT manager for token creation
                    return await self.token_manager.advanced_jwt.create_token(
                        user_id=user_id,
                        email=kwargs.get("email", ""),
                        role=kwargs.get("role", "parent"),
                        user_type=kwargs.get("user_type", "parent"),
                        token_type=TokenType.ACCESS,
                        device_info=kwargs.get("device_info"),
                        ip_address=kwargs.get("ip_address"),
                        permissions=permissions,
                    )

                async def validate_token(self, token: str, **kwargs) -> Dict[str, Any]:
                    """Validate and decode authentication token with enhanced security."""
                    device_info = kwargs.get("device_info")
                    ip_address = kwargs.get("ip_address")

                    # Use advanced JWT verification
                    claims = await self.token_manager.advanced_jwt.verify_token(
                        token,
                        verify_device=True,
                        current_device_info=device_info,
                        current_ip=ip_address,
                    )

                    # Convert to dict for backward compatibility
                    return {
                        "sub": claims.sub,
                        "email": claims.email,
                        "role": claims.role,
                        "user_type": claims.user_type,
                        "permissions": claims.permissions,
                        "jti": claims.jti,
                    }

                async def refresh_token(self, refresh_token: str, **kwargs) -> str:
                    """Refresh authentication token with enhanced security."""
                    device_info = kwargs.get("device_info")
                    ip_address = kwargs.get("ip_address")

                    # Use advanced JWT refresh with device/IP tracking
                    new_access_token, _ = (
                        await self.token_manager.advanced_jwt.refresh_token(
                            refresh_token, device_info, ip_address
                        )
                    )
                    return new_access_token

                async def revoke_token(
                    self, jti: str, reason: str = "manual_revocation"
                ):
                    """Revoke token with audit trail."""
                    await self.token_manager.revoke_token(jti, reason)

                async def revoke_all_user_tokens(
                    self, user_id: str, reason: str = "security_reset"
                ):
                    """Revoke all user tokens for security."""
                    await self.token_manager.revoke_all_user_tokens(user_id, reason)

            return UnifiedAuthService()

        except ImportError as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Unified AuthService not available: {e}")
            raise RuntimeError(f"Authentication service implementation not found: {e}")

    @provider
    @singleton
    def _get_encryption_service(self) -> IEncryptionService:
        """Get unified encryption service instance."""
        try:
            from src.utils.crypto_utils import EncryptionService

            return EncryptionService()
        except ImportError as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to import EncryptionService: {e}")
            raise RuntimeError(f"EncryptionService implementation not available: {e}")

    @provider
    def _get_notification_service(
        self, email_adapter, push_adapter
    ) -> INotificationService:
        """Get production notification service."""
        from src.infrastructure.communication.production_notification_service import (
            ProductionNotificationService,
        )

        return ProductionNotificationService(
            email_adapter=email_adapter, push_adapter=push_adapter
        )

    @provider
    def _get_audio_service(
        self, SpeechProvider, TTSService: ITTSService
    ) -> IAudioService:
        from src.application.services.audio_service import AudioService
        from src.application.services.audio_validation_service import (
            AudioValidationService,
        )
        from src.application.services.audio_streaming_service import (
            AudioStreamingService,
        )
        from src.application.services.audio_safety_service import AudioSafetyService
        import logging

        logger = logging.getLogger("ai_teddy_bear.audio_service")

        # Create required service instances - NO NONE VALUES
        validation_service = AudioValidationService(logger=logger)
        streaming_service = AudioStreamingService(buffer_size=4096, logger=logger)
        safety_service = AudioSafetyService(logger=logger)
        cache_service = self._get_tts_cache_service(self._get_app_settings())

        return AudioService(
            stt_provider=SpeechProvider,
            tts_service=TTSService,
            validation_service=validation_service,
            streaming_service=streaming_service,
            safety_service=safety_service,
            cache_service=cache_service,
            logger=logger,
        )

    @provider
    @singleton
    def _get_cache_service(self) -> ICacheService:
        """Get production Redis cache service."""
        from src.infrastructure.caching.production_redis_cache import (
            ProductionRedisCache,
        )

        return ProductionRedisCache()

    @provider
    def _get_rate_limiting_service(self) -> IRateLimitingService:
        from src.infrastructure.rate_limiting.rate_limiter import (
            create_rate_limiting_service,
        )

        return create_rate_limiting_service()

    @provider
    def _get_event_bus_service(self, message_queue_adapter) -> IEventBusService:
        """Get production event bus service."""
        from src.infrastructure.messaging.production_event_bus import ProductionEventBus

        return ProductionEventBus(message_queue_adapter=message_queue_adapter)

    @provider
    def _get_chat_service(
        self,
        child_safety_service: IChildSafetyService,
        rate_limiting_service: IRateLimitingService,
    ) -> IChatService:
        from src.core.services import ChatService
        from src.infrastructure.rate_limiting.rate_limiter import (
            create_rate_limiting_service,
        )
        import os

        openai_api_key = os.getenv("OPENAI_API_KEY")
        rate_limiter = create_rate_limiting_service()
        return ChatService(
            ai_provider=self._get_ai_provider(self._get_app_settings()),
            safety_service=child_safety_service,
            rate_limiter=rate_limiter,
        )

    @provider
    def _get_conversation_service(
        self, conversation_repository, message_repository
    ) -> IConversationService:
        from src.services.conversation_service import ConsolidatedConversationService
        import logging

        logger = logging.getLogger("ai_teddy_bear.conversation_service")
        return ConsolidatedConversationService(
            conversation_repository=conversation_repository,
            message_repository=message_repository,
            logger=logger,
        )

    @provider
    def _get_user_service(self, user_repository, child_repository) -> IUserService:
        from src.application.services.user_service import UserService
        import logging

        logger = logging.getLogger("ai_teddy_bear.user_service")
        return UserService(user_repository, child_repository, logger)

    @provider
    def _get_manage_child_profile_use_case(
        self,
        child_repository,
        child_safety_service: IChildSafetyService,
        event_bus_service,
    ) -> object:
        """Get manage child profile use case."""
        try:
            from src.application.use_cases.manage_child_profile import (
                ManageChildProfileUseCase,
            )

            return ManageChildProfileUseCase(
                child_repository, child_safety_service, event_bus_service
            )
        except ImportError as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"ManageChildProfileUseCase not available: {e}")
            raise RuntimeError(
                f"ManageChildProfileUseCase implementation not found: {e}"
            )

    @provider
    def _get_process_audio_use_case(
        self,
        audio_service,
        ai_service: IAIService,
        child_safety_service: IChildSafetyService,
        conversation_repository,
    ) -> object:
        """Get process ESP32 audio use case."""
        try:
            from src.application.use_cases.process_esp32_audio import (
                ProcessESP32AudioUseCase,
            )

            return ProcessESP32AudioUseCase(
                audio_service, ai_service, child_safety_service, conversation_repository
            )
        except ImportError as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"ProcessESP32AudioUseCase not available: {e}")
            raise RuntimeError(
                f"ProcessESP32AudioUseCase implementation not found: {e}"
            )

    @provider
    def _get_generate_ai_response_use_case(
        self,
        ai_service: IAIService,
        child_safety_service: IChildSafetyService,
        conversation_repository,
    ) -> object:
        """Get generate AI response use case."""
        try:
            from src.application.use_cases.generate_ai_response import (
                GenerateAIResponseUseCase,
            )

            return GenerateAIResponseUseCase(
                ai_service, child_safety_service, conversation_repository
            )
        except ImportError as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"GenerateAIResponseUseCase not available: {e}")
            raise RuntimeError(
                f"GenerateAIResponseUseCase implementation not found: {e}"
            )

    @provider
    def _get_email_adapter(self) -> object:
        """Get production email adapter."""
        from src.infrastructure.communication.production_email_adapter import (
            ProductionEmailAdapter,
        )

        return ProductionEmailAdapter()

    @provider
    def _get_push_adapter(self) -> object:
        """Get production push notification adapter."""
        from src.infrastructure.communication.production_push_adapter import (
            ProductionPushAdapter,
        )

        return ProductionPushAdapter()

    @provider
    def _get_speech_adapter(self) -> object:
        """Get speech adapter - uses existing speech provider."""
        try:
            return self._get_speech_provider(self._get_app_settings())
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Speech adapter not available: {e}")
            raise RuntimeError(f"Speech adapter implementation not found: {e}")

    @provider
    def _get_tts_adapter(self) -> object:
        """Get TTS adapter - uses existing TTS provider."""
        try:
            return self._get_tts_provider(self._get_app_settings())
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"TTS adapter not available: {e}")
            raise RuntimeError(f"TTS adapter implementation not found: {e}")

    @provider
    def _get_message_queue_adapter(self) -> object:
        """Get production message queue adapter."""
        from src.infrastructure.messaging.production_message_queue_adapter import (
            ProductionMessageQueueAdapter,
        )

        return ProductionMessageQueueAdapter()

    def _create_tts_service_directly(self, env_config: dict) -> ITTSService:
        """Create TTS service directly - production only supports OpenAI."""
        provider_type = env_config.get("TTS_PROVIDER", "openai").lower()

        if provider_type == "openai":
            return self._create_openai_tts_provider(env_config)
        else:
            raise TTSConfigurationError(
                f"Unsupported TTS provider: {provider_type}. "
                f"Only 'openai' is supported in production. "
                f"Set TTS_PROVIDER=openai in your configuration."
            )

    def _create_openai_tts_provider(self, env_config: dict) -> ITTSService:
        """Create OpenAI TTS provider implementation."""
        from src.infrastructure.audio.openai_tts_provider import OpenAITTSProvider

        api_key = env_config.get("OPENAI_API_KEY")
        if not api_key:
            raise TTSConfigurationError("OPENAI_API_KEY is required for OpenAI TTS")

        cache_service = self._get_tts_cache_service(self._get_app_settings())
        model = env_config.get("OPENAI_TTS_MODEL", "tts-1")

        return OpenAITTSProvider(
            api_key=api_key, cache_service=cache_service, model=model
        )

    @provider
    def _get_file_storage_adapter(self) -> object:
        """Get production file storage adapter."""
        from src.infrastructure.storage.production_file_storage_adapter import (
            ProductionFileStorageAdapter,
        )

        return ProductionFileStorageAdapter()

    @provider
    def _get_websocket_adapter(self) -> object:
        """Get production WebSocket adapter."""
        from src.infrastructure.websocket.production_websocket_adapter import (
            ProductionWebSocketAdapter,
        )

        return ProductionWebSocketAdapter()

    @provider
    @singleton
    def _get_esp32_realtime_streamer(self) -> object:
        """Get ESP32 real-time audio streamer with optimized settings."""
        from src.infrastructure.streaming.esp32_realtime_streamer import (
            ESP32AudioStreamer,
        )

        return ESP32AudioStreamer(
            buffer_duration=2.0,  # 2-second circular buffer as specified
            chunk_size=1024,  # Optimized chunk size for 300ms latency
            target_latency=0.3,  # 300ms target latency requirement
            auto_reconnect=True,  # Auto-reconnection for reliability
        )


# Global injector instance
injector_instance = Injector([ApplicationModule()])


def get_ai_service() -> IAIService:
    """Get AI service instance."""
    return injector_instance.get(IAIService)


def get_child_safety_service() -> IChildSafetyService:
    """Get child safety service instance."""
    return injector_instance.get(IChildSafetyService)


def get_authentication_service() -> IAuthService:
    """Get authentication service instance."""
    return injector_instance.get(IAuthService)


def get_injector() -> Injector:
    """Get the global injector instance."""
    return injector_instance
