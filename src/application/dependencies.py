"""Dependency injection helpers for the application layer.

This module provides dependency injection decorators and helpers
that can be used by adapters and presentation layers without
directly importing from infrastructure.

All functions return concrete interface types for strong type checking
and proper dependency inversion.
"""

from typing import TypeVar, Type, TYPE_CHECKING
from fastapi import Depends, Request

# Import the injector instance
from src.infrastructure.container import get_injector

# Import interfaces for strong typing
from src.interfaces.services import (
    IChatService,
    IAuthService,
    IConversationService,
    IChildSafetyService,
    IAIService,
    IAudioService,
    INotificationService,
    IUserService,
)
from src.interfaces.repositories import (
    IUserRepository,
    IChildRepository,
    IConversationRepository,
    IMessageRepository,
)

T = TypeVar("T")


# ========================= SERVICE DEPENDENCIES =========================


def get_chat_service() -> IChatService:
    """Get chat service instance with strong type checking."""
    injector = get_injector()
    return injector.get(IChatService)


def get_auth_service() -> IAuthService:
    """Get authentication service instance with strong type checking."""
    injector = get_injector()
    return injector.get(IAuthService)


def get_conversation_service() -> IConversationService:
    """Get conversation service instance with strong type checking."""
    injector = get_injector()
    return injector.get(IConversationService)


def get_child_safety_service() -> IChildSafetyService:
    """Get child safety service instance with strong type checking."""
    injector = get_injector()
    return injector.get(IChildSafetyService)


def get_ai_service() -> IAIService:
    """Get AI service instance with strong type checking."""
    injector = get_injector()
    return injector.get(IAIService)


def get_audio_service() -> IAudioService:
    """Get audio service instance with strong type checking."""
    injector = get_injector()
    return injector.get(IAudioService)


def get_notification_service() -> INotificationService:
    """Get notification service instance with strong type checking."""
    injector = get_injector()
    return injector.get(INotificationService)


def get_user_service() -> IUserService:
    """Get user service instance with strong type checking."""
    injector = get_injector()
    return injector.get(IUserService)


def get_whisper_stt_provider():
    """Get Whisper STT provider instance for real-time processing."""
    injector = get_injector()
    return injector.get(object)  # Will resolve to WhisperSTTProvider


def get_esp32_realtime_streamer():
    """Get ESP32 real-time streamer instance for optimized streaming."""
    injector = get_injector()
    return injector.get(object)  # Will resolve to ESP32AudioStreamer


# ========================= REPOSITORY DEPENDENCIES =========================


def get_user_repository() -> IUserRepository:
    """Get user repository instance with strong type checking."""
    injector = get_injector()
    return injector.get(IUserRepository)


def get_child_repository() -> IChildRepository:
    """Get child repository instance with strong type checking."""
    injector = get_injector()
    return injector.get(IChildRepository)


def get_conversation_repository() -> IConversationRepository:
    """Get conversation repository instance with strong type checking."""
    injector = get_injector()
    return injector.get(IConversationRepository)


def get_message_repository() -> IMessageRepository:
    """Get message repository instance with strong type checking."""
    injector = get_injector()
    return injector.get(IMessageRepository)


# ========================= FASTAPI DEPENDENCY ANNOTATIONS =========================

# Service dependency annotations with proper typing
ChatServiceDep = Depends(get_chat_service)
AuthServiceDep = Depends(get_auth_service)
ConversationServiceDep = Depends(get_conversation_service)
ChildSafetyServiceDep = Depends(get_child_safety_service)
AIServiceDep = Depends(get_ai_service)
AudioServiceDep = Depends(get_audio_service)
NotificationServiceDep = Depends(get_notification_service)
UserServiceDep = Depends(get_user_service)

# Repository dependency annotations with proper typing
UserRepositoryDep = Depends(get_user_repository)
ChildRepositoryDep = Depends(get_child_repository)
ConversationRepositoryDep = Depends(get_conversation_repository)
MessageRepositoryDep = Depends(get_message_repository)


# ========================= PRODUCTION CONFIG & AUTH DEPENDENCIES =========================

def get_config_from_state(request: Request) -> "ProductionConfig":
    """Get configuration from app.state (production-grade)"""
    from fastapi import HTTPException
    import logging, os
    
    # DIAGNOSTIC LOG
    diag = {
        "has_app_state_config": hasattr(request.app.state, "config"),
        "config_is_none": getattr(request.app.state, "config", None) is None,
        "config_type": type(getattr(request.app.state, "config", None)).__name__,
        "config_ready_flag": getattr(request.app.state, "config_ready", None),
        "ready_flag": getattr(request.app.state, "ready", None),
        "pid": os.getpid(),
    }
    logging.getLogger("diag.config_dep").warning("CFG_DEP %s", diag)
    
    config = getattr(request.app.state, "config", None)
    if config is None:
        # Service is still initializing - return 503 instead of 500
        raise HTTPException(
            status_code=503, 
            detail="Service initializing - configuration not ready",
            headers={"Retry-After": "5"}
        )
    return config

def get_token_manager_from_state(request: Request) -> "TokenManager":
    """Get TokenManager from app.state (production-grade)"""
    from fastapi import Request, HTTPException
    token_manager = getattr(request.app.state, "token_manager", None)
    if token_manager is None:
        raise HTTPException(status_code=503, detail="Token manager not ready")
    return token_manager

def get_security_service_from_state(request: Request) -> "SecurityService":
    """Get SecurityService from app.state (production-grade)"""
    from fastapi import Request, HTTPException
    security_service = getattr(request.app.state, "security_service", None)
    if security_service is None:
        raise HTTPException(status_code=503, detail="Security service not ready")
    return security_service

def get_advanced_jwt_from_state(request: Request) -> "AdvancedJWTManager":
    """Get AdvancedJWTManager from app.state (production-grade)"""
    from fastapi import Request, HTTPException
    advanced_jwt = getattr(request.app.state, "advanced_jwt", None)
    if advanced_jwt is None:
        raise HTTPException(status_code=503, detail="Advanced JWT manager not ready")
    return advanced_jwt

def get_db_adapter_from_state(request: Request) -> "ProductionDatabaseAdapter":
    """Get ProductionDatabaseAdapter from app.state (production-grade)"""
    from fastapi import Request, HTTPException
    db_adapter = getattr(request.app.state, "db_adapter", None)
    if db_adapter is None:
        raise HTTPException(status_code=503, detail="Database adapter not ready")
    return db_adapter

def get_payment_system_from_state(request: Request) -> "PaymentSystemIntegration":
    """Get PaymentSystemIntegration from app.state (production-grade)"""
    from fastapi import Request, HTTPException
    payment_system = getattr(request.app.state, "payment_system", None)
    if payment_system is None:
        raise HTTPException(status_code=503, detail="Payment system not ready")
    return payment_system

# FastAPI dependency annotations for production services
ConfigDep = Depends(get_config_from_state)
TokenManagerDep = Depends(get_token_manager_from_state)
SecurityServiceDep = Depends(get_security_service_from_state)
AdvancedJWTDep = Depends(get_advanced_jwt_from_state)
DBAdapterDep = Depends(get_db_adapter_from_state)
PaymentDep = Depends(get_payment_system_from_state)

def get_admin_security_manager(token_manager: "TokenManager" = TokenManagerDep) -> "AdminSecurityManager":
    """Get AdminSecurityManager with proper TokenManager injection (production-grade)"""
    from src.infrastructure.security.admin_security import AdminSecurityManager
    return AdminSecurityManager(token_manager=token_manager)

AdminSecurityDep = Depends(get_admin_security_manager)

def get_admin_security_manager_from_state(app) -> "AdminSecurityManager":
    """Build AdminSecurityManager at startup using services already in app.state."""
    from src.infrastructure.security.admin_security import AdminSecurityManager
    token_manager = getattr(app.state, "token_manager", None)
    if token_manager is None:
        raise RuntimeError("Token manager not ready")
    return AdminSecurityManager(token_manager=token_manager)

# ========================= DATABASE DEPENDENCY (PRODUCTION-GRADE) =========================

async def get_database_connection_from_state(request: Request):
    """Get database connection using config from app.state (production-grade)"""
    from fastapi import HTTPException
    
    # Get db_adapter from app.state (set during startup)
    db_adapter = getattr(request.app.state, "db_adapter", None)
    if db_adapter is None:
        raise HTTPException(
            status_code=503,
            detail="Database adapter not ready - service initializing",
            headers={"Retry-After": "5"}
        )
    
    # Use the production database adapter's async session method
    async for session in db_adapter.get_async_session():
        yield session

# FastAPI dependency annotation
DatabaseConnectionDep = Depends(get_database_connection_from_state)

# ========================= ENTERPRISE DATABASE & TRANSACTION DEPENDENCIES =========================

async def get_enterprise_db_manager_from_state(request: Request):
    """Get enterprise database manager from app.state (production-grade)"""
    from fastapi import Request, HTTPException
    
    ent_db = getattr(request.app.state, "ent_db", None)
    if ent_db is None:
        raise HTTPException(
            status_code=503,
            detail="Enterprise database manager not ready - service initializing",
            headers={"Retry-After": "10"}
        )
    return ent_db

async def get_transaction_manager_from_state(request: Request):
    """Get transaction manager from app.state (production-grade)"""
    from fastapi import Request, HTTPException
    
    tx_manager = getattr(request.app.state, "tx_manager", None)
    if tx_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Transaction manager not ready - service initializing",
            headers={"Retry-After": "10"}
        )
    return tx_manager

# FastAPI dependency annotations
EnterpriseDbDep = Depends(get_enterprise_db_manager_from_state)
TransactionManagerDep = Depends(get_transaction_manager_from_state)

# ========================= GENERIC DEPENDENCY HELPER =========================


def get_service(service_type: Type[T]) -> T:
    """Generic service getter with strong type checking.

    Args:
        service_type: The interface type to resolve

    Returns:
        Concrete implementation of the requested service type

    Example:
        service = get_service(IAIService)
    """
    injector = get_injector()
    return injector.get(service_type)


# ========================= CONVENIENCE TYPE ALIASES =========================

# Type aliases for easier usage in endpoint signatures
ChatService = IChatService
AuthService = IAuthService
ConversationService = IConversationService
AIService = IAIService
AudioService = IAudioService
NotificationService = INotificationService
UserService = IUserService

# Repository type aliases
UserRepository = IUserRepository
ChildRepository = IChildRepository
ConversationRepository = IConversationRepository
MessageRepository = IMessageRepository
