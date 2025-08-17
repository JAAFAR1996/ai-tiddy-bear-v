"""Abstract interfaces for dependency inversion.

This module defines all abstract base classes and interfaces that establish
contracts between layers without creating concrete dependencies.

Following the Dependency Inversion Principle:
- High-level modules should not depend on low-level modules
- Both should depend on abstractions
- Abstractions should not depend on details
- Details should depend on abstractions
"""

from .services import *
from .repositories import *
from .adapters import *

__all__ = [
    # Service interfaces
    "IAIService",
    "IAuthService", 
    "IChatService",
    "IConversationService",
    "IChildSafetyService",
    "IAudioService",
    "INotificationService",
    "IUserService",
    "IContentFilterService",
    "ISecurityService",
    "IEncryptionService",
    
    # Repository interfaces
    "IUserRepository",
    "IChildRepository", 
    "IConversationRepository",
    "IMessageRepository",
    "IAuditRepository",
    "ISessionRepository",
    
    # Adapter interfaces
    "IDatabaseAdapter",
    "IWebAdapter",
    "ICacheAdapter",
    "IEmailAdapter",
    "IStorageAdapter",
    "IExternalAPIAdapter",
]
