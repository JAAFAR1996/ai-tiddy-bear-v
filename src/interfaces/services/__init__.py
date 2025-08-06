"""Service interfaces for dependency inversion.

All service contracts are defined here to eliminate circular dependencies
and ensure proper layer separation according to hexagonal architecture.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, Union, TypeVar, Generic
from uuid import UUID
from datetime import datetime


class IAIService(ABC):
    """Interface for AI processing services."""

    @abstractmethod
    async def generate_response(
        self, 
        message: str, 
        context: Dict[str, Any], 
        child_id: str
    ) -> str:
        """Generate AI response for child interaction."""
        pass

    @abstractmethod
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment and emotional content."""
        pass

    @abstractmethod
    async def validate_content_safety(self, content: str) -> bool:
        """Validate content meets safety guidelines."""
        pass


class IAuthService(ABC):
    """Interface for authentication and authorization services."""

    @abstractmethod
    async def authenticate_user(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate user with credentials."""
        pass

    @abstractmethod
    async def authorize_action(self, user_id: str, action: str, resource: str) -> bool:
        """Authorize user action on resource."""
        pass

    @abstractmethod
    async def generate_token(self, user_id: str, permissions: List[str]) -> str:
        """Generate authentication token."""
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate and decode authentication token."""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> str:
        """Refresh authentication token."""
        pass


class IChatService(ABC):
    """Interface for chat functionality."""

    @abstractmethod
    async def process_message(
        self, 
        message: str, 
        user_id: str, 
        child_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """Process incoming chat message."""
        pass

    @abstractmethod
    async def get_conversation_history(
        self, 
        child_id: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get conversation history for child."""
        pass

    @abstractmethod
    async def start_conversation(self, child_id: str, parent_id: str) -> str:
        """Start new conversation session."""
        pass

    @abstractmethod
    async def end_conversation(self, session_id: str) -> bool:
        """End conversation session."""
        pass


class IConversationService(ABC):
    """Interface for conversation management."""

    @abstractmethod
    async def create_conversation(self, child_id: str, metadata: Dict[str, Any]) -> str:
        """Create new conversation."""
        pass

    @abstractmethod
    async def add_message(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """Add message to conversation."""
        pass

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation details."""
        pass

    @abstractmethod
    async def archive_conversation(self, conversation_id: str) -> bool:
        """Archive conversation."""
        pass

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete conversation permanently."""
        pass


class IChildSafetyService(ABC):
    """Interface for child safety and protection services."""

    @abstractmethod
    async def validate_content(self, content: str, child_age: int) -> Dict[str, Any]:
        """Validate content appropriateness for child."""
        pass

    @abstractmethod
    async def filter_content(self, content: str) -> str:
        """Filter inappropriate content."""
        pass

    @abstractmethod
    async def log_safety_event(self, event: Dict[str, Any]) -> bool:
        """Log safety-related event."""
        pass

    @abstractmethod
    async def get_safety_recommendations(self, child_id: str) -> List[Dict[str, Any]]:
        """Get safety recommendations for child."""
        pass

    @abstractmethod
    async def verify_parental_consent(self, child_id: str) -> bool:
        """Verify parental consent status."""
        pass


class IAudioService(ABC):
    """Interface for audio processing services."""

    @abstractmethod
    async def process_audio(self, audio_data: bytes) -> Dict[str, Any]:
        """Process audio input."""
        pass

    @abstractmethod
    async def convert_text_to_speech(self, text: str, voice_settings: Dict[str, Any]) -> bytes:
        """Convert text to speech audio."""
        pass

    @abstractmethod
    async def convert_speech_to_text(self, audio_data: bytes) -> str:
        """Convert speech audio to text."""
        pass

    @abstractmethod
    async def validate_audio_safety(self, audio_data: bytes) -> bool:
        """Validate audio content safety."""
        pass


class INotificationService(ABC):
    """Interface for notification services."""

    @abstractmethod
    async def send_notification(
        self, 
        recipient_id: str, 
        message: str, 
        notification_type: str
    ) -> bool:
        """Send notification to recipient."""
        pass

    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send email notification."""
        pass

    @abstractmethod
    async def send_push_notification(self, device_id: str, message: str) -> bool:
        """Send push notification."""
        pass

    @abstractmethod
    async def get_notification_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Get notification history for user."""
        pass


class IUserService(ABC):
    """Interface for user management services."""

    @abstractmethod
    async def create_user(self, user_data: Dict[str, Any]) -> str:
        """Create new user."""
        pass

    @abstractmethod
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get user by ID."""
        pass

    @abstractmethod
    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user information."""
        pass

    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete user account."""
        pass

    @abstractmethod
    async def verify_user_permissions(self, user_id: str, child_id: str) -> bool:
        """Verify user has permissions for child."""
        pass


class IContentFilterService(ABC):
    """Interface for content filtering services."""

    @abstractmethod
    async def filter_text(self, text: str, filter_level: str) -> str:
        """Filter inappropriate text content."""
        pass

    @abstractmethod
    async def check_content_safety(self, content: str) -> Dict[str, Any]:
        """Check content safety rating."""
        pass

    @abstractmethod
    async def add_blocked_word(self, word: str) -> bool:
        """Add word to blocked list."""
        pass

    @abstractmethod
    async def remove_blocked_word(self, word: str) -> bool:
        """Remove word from blocked list."""
        pass


class ISecurityService(ABC):
    """Interface for security services."""

    @abstractmethod
    async def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        pass

    @abstractmethod
    async def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        pass

    @abstractmethod
    async def generate_secure_token(self, length: int = 32) -> str:
        """Generate secure random token."""
        pass

    @abstractmethod
    async def hash_password(self, password: str) -> str:
        """Hash password securely."""
        pass

    @abstractmethod
    async def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        pass


class IEncryptionService(ABC):
    """Interface for encryption services."""

    @abstractmethod
    def encrypt(self, data: str) -> str:
        """Encrypt data."""
        pass

    @abstractmethod
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data."""
        pass

    @abstractmethod
    def generate_key(self) -> str:
        """Generate encryption key."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if encryption service is available."""
        pass


# Protocol for dependency injection
class ServiceProvider(Protocol):
    """Protocol for service provider implementations."""

    def get_service(self, service_type: type) -> Any:
        """Get service instance by type."""
        ...

    def register_service(self, service_type: type, instance: Any) -> None:
        """Register service instance."""
        ...


class IService(ABC):
    """Base service interface."""
    pass


class ICacheService(IService):
    """Interface for caching operations."""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get cached value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set cached value with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete cached value."""
        pass


class IRateLimitingService(IService):
    """Interface for rate limiting operations."""

    @abstractmethod
    async def check_limit(self, identifier: str, limit: int, window: int) -> bool:
        """Check if request is within rate limit."""
        pass

    @abstractmethod
    async def increment(self, identifier: str) -> None:
        """Increment counter for identifier."""
        pass


class IEventBusService(IService):
    """Interface for event publishing and subscription."""

    @abstractmethod
    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish event to event bus."""
        pass

    @abstractmethod
    async def subscribe(self, event_type: str, handler: callable) -> None:
        """Subscribe to event type with handler."""
        pass
