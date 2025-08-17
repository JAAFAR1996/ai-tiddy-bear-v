"""Repository interfaces for dependency inversion.

All repository contracts are defined here to eliminate circular dependencies
and ensure proper data access layer separation.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, TypeVar, Generic
from uuid import UUID
from datetime import datetime


class IUserRepository(ABC):
    """Interface for user data persistence."""

    @abstractmethod
    async def create(self, user_data: Dict[str, Any]) -> str:
        """Create new user record."""
        pass

    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        pass

    @abstractmethod
    async def update(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user record."""
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        """Delete user record."""
        pass

    @abstractmethod
    async def list_users(self, filters: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
        """List users with filtering."""
        pass

    @abstractmethod
    async def exists(self, user_id: str) -> bool:
        """Check if user exists."""
        pass


class IChildRepository(ABC):
    """Interface for child profile data persistence."""

    @abstractmethod
    async def create(self, child_data: Dict[str, Any]) -> str:
        """Create new child record."""
        pass

    @abstractmethod
    async def get_by_id(self, child_id: str) -> Optional[Dict[str, Any]]:
        """Get child by ID."""
        pass

    @abstractmethod
    async def get_by_parent_id(self, parent_id: str) -> List[Dict[str, Any]]:
        """Get children by parent ID."""
        pass

    @abstractmethod
    async def update(self, child_id: str, updates: Dict[str, Any]) -> bool:
        """Update child record."""
        pass

    @abstractmethod
    async def delete(self, child_id: str) -> bool:
        """Delete child record."""
        pass

    @abstractmethod
    async def update_safety_settings(self, child_id: str, settings: Dict[str, Any]) -> bool:
        """Update child safety settings."""
        pass

    @abstractmethod
    async def get_safety_settings(self, child_id: str) -> Dict[str, Any]:
        """Get child safety settings."""
        pass

    @abstractmethod
    async def verify_parental_access(self, parent_id: str, child_id: str) -> bool:
        """Verify parent has access to child."""
        pass


class IConversationRepository(ABC):
    """Interface for conversation data persistence."""

    @abstractmethod
    async def create(self, conversation_data: Dict[str, Any]) -> str:
        """Create new conversation."""
        pass

    @abstractmethod
    async def get_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation by ID."""
        pass

    @abstractmethod
    async def get_by_child_id(self, child_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversations for child."""
        pass

    @abstractmethod
    async def add_message(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """Add message to conversation."""
        pass

    @abstractmethod
    async def update_status(self, conversation_id: str, status: str) -> bool:
        """Update conversation status."""
        pass

    @abstractmethod
    async def archive(self, conversation_id: str) -> bool:
        """Archive conversation."""
        pass

    @abstractmethod
    async def delete(self, conversation_id: str) -> bool:
        """Delete conversation."""
        pass

    @abstractmethod
    async def get_active_conversations(self, child_id: str) -> List[Dict[str, Any]]:
        """Get active conversations for child."""
        pass


class IMessageRepository(ABC):
    """Interface for message data persistence."""

    @abstractmethod
    async def create(self, message_data: Dict[str, Any]) -> str:
        """Create new message."""
        pass

    @abstractmethod
    async def get_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get message by ID."""
        pass

    @abstractmethod
    async def get_by_conversation_id(
        self, 
        conversation_id: str, 
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages for conversation."""
        pass

    @abstractmethod
    async def update(self, message_id: str, updates: Dict[str, Any]) -> bool:
        """Update message."""
        pass

    @abstractmethod
    async def delete(self, message_id: str) -> bool:
        """Delete message."""
        pass

    @abstractmethod
    async def mark_as_read(self, message_id: str) -> bool:
        """Mark message as read."""
        pass

    @abstractmethod
    async def get_unread_count(self, conversation_id: str) -> int:
        """Get unread message count."""
        pass


class IAuditRepository(ABC):
    """Interface for audit log data persistence."""

    @abstractmethod
    async def log_event(self, event_data: Dict[str, Any]) -> str:
        """Log audit event."""
        pass

    @abstractmethod
    async def get_events(
        self, 
        filters: Dict[str, Any], 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit events with filtering."""
        pass

    @abstractmethod
    async def get_user_activity(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user activity log."""
        pass

    @abstractmethod
    async def get_child_activity(self, child_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get child activity log."""
        pass

    @abstractmethod
    async def cleanup_old_events(self, days_old: int) -> int:
        """Clean up old audit events."""
        pass


class ISessionRepository(ABC):
    """Interface for session data persistence."""

    @abstractmethod
    async def create_session(self, session_data: Dict[str, Any]) -> str:
        """Create new session."""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        pass

    @abstractmethod
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data."""
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        pass

    @abstractmethod
    async def get_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active sessions for user."""
        pass

    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        pass


# Protocol for repository factory
class RepositoryFactory(Protocol):
    """Protocol for repository factory implementations."""

    def create_user_repository(self) -> IUserRepository:
        """Create user repository instance."""
        ...

    def create_child_repository(self) -> IChildRepository:
        """Create child repository instance."""
        ...

    def create_conversation_repository(self) -> IConversationRepository:
        """Create conversation repository instance."""
        ...

    def create_message_repository(self) -> IMessageRepository:
        """Create message repository instance."""
        ...

    def create_audit_repository(self) -> IAuditRepository:
        """Create audit repository instance."""
        ...

    def create_session_repository(self) -> ISessionRepository:
        """Create session repository instance."""
        ...


T = TypeVar('T')
ID = TypeVar('ID')


class IRepository(ABC, Generic[T, ID]):
    """Generic repository interface for CRUD operations."""

    @abstractmethod
    async def get(self, entity_id: ID) -> Optional[T]:
        """Retrieve entity by ID."""
        pass

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Save entity and return updated version."""
        pass

    @abstractmethod
    async def delete(self, entity_id: ID) -> bool:
        """Delete entity by ID. Returns True if successful."""
        pass

    @abstractmethod
    async def list(self, limit: int = 100, offset: int = 0) -> List[T]:
        """List entities with pagination."""
        pass


class IGenericChildRepository(IRepository[Any, UUID]):
    """Generic interface for child data persistence."""

    @abstractmethod
    async def find_by_parent(self, parent_id: UUID) -> List[Any]:
        """Find children by parent ID."""
        pass

    @abstractmethod
    async def update_safety_settings(self, child_id: UUID, settings: Dict[str, Any]) -> bool:
        """Update child safety settings."""
        pass


class IGenericUserRepository(IRepository[Any, UUID]):
    """Generic interface for user data persistence."""

    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[Any]:
        """Find user by email address."""
        pass

    @abstractmethod
    async def find_by_username(self, username: str) -> Optional[Any]:
        """Find user by username."""
        pass


class IGenericConversationRepository(IRepository[Any, UUID]):
    """Generic interface for conversation data persistence."""

    @abstractmethod
    async def find_by_child(self, child_id: UUID) -> List[Any]:
        """Find conversations by child ID."""
        pass

    @abstractmethod
    async def find_recent(self, child_id: UUID, limit: int = 10) -> List[Any]:
        """Find recent conversations for a child."""
        pass


class IEventRepository(IRepository[Any, UUID]):
    """Interface for event storage (audit, safety, etc.)."""

    @abstractmethod
    async def find_by_type(self, event_type: str) -> List[Any]:
        """Find events by type."""
        pass

    @abstractmethod
    async def find_by_child(self, child_id: UUID) -> List[Any]:
        """Find events for a specific child."""
        pass
