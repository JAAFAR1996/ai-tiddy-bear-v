"""
Core Database Repositories - Production ORM Implementation

Provides production-ready database repositories for the AI Teddy Bear platform:
- ConversationRepository: Async CRUD operations using SQLAlchemy ORM
- MessageRepository: Async CRUD operations using SQLAlchemy ORM
- PostgreSQL-based implementation with connection pooling
- Full error handling and transaction support
- COPPA compliance with data retention policies
- Performance optimization with proper ORM patterns
"""

import json
import structlog
from datetime import datetime, UTC, timedelta
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod

# SQLAlchemy imports
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func
from sqlalchemy.orm import selectinload

# Domain models and database models
from .models import ConversationEntity, MessageEntity
from ..infrastructure.database.models import Conversation as ConversationModel, Message as MessageModel
from .exceptions import ConversationNotFoundError

# Configure logging (unified)
logger = structlog.get_logger(__name__)
AUDIT_LOG_CHANNEL = structlog.get_logger("audit")




class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""


class MessageNotFoundError(Exception):
    """Raised when message is not found."""


# ================================
# REPOSITORY INTERFACES
# ================================


class IConversationRepository(ABC):
    """Abstract repository interface for conversation operations."""

    @abstractmethod
    async def save(self, conversation: ConversationEntity) -> ConversationEntity:
        """Save or update a conversation."""

    @abstractmethod
    async def get_by_id(self, conversation_id: str) -> Optional[ConversationEntity]:
        """Get conversation by ID."""

    @abstractmethod
    async def get_by_child_id(self, child_id: str) -> List[ConversationEntity]:
        """Get all conversations for a specific child."""

    @abstractmethod
    async def delete(self, conversation_id: str) -> None:
        """Delete conversation by ID."""

    @abstractmethod
    async def create_tables(self) -> None:
        """Create database tables if they don't exist."""


class IMessageRepository(ABC):
    """Abstract repository interface for message operations."""

    @abstractmethod
    async def save_message(self, message: MessageEntity) -> MessageEntity:
        """Save a message to the database."""

    @abstractmethod
    async def get_conversation_messages(
        self, conversation_id: str, limit: int = 50, offset: int = 0
    ) -> List[MessageEntity]:
        """Get messages for a conversation."""

    @abstractmethod
    async def delete_conversation_messages(self, conversation_id: str) -> int:
        """Delete all messages for a conversation."""

    @abstractmethod
    async def create_tables(self) -> None:
        """Create database tables if they don't exist."""


# ORM IMPLEMENTATIONS


class ConversationRepository(IConversationRepository):
    """
    SQLAlchemy ORM-based conversation repository with async support.

    Provides production-ready conversation persistence with:
    - Full async/await support using SQLAlchemy async
    - ORM-based queries instead of raw SQL
    - ACID transaction support
    - Connection pooling via AsyncSession
    - COPPA-compliant data retention
    - Performance-optimized queries with proper relationships
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with async database session.

        Args:
            session: SQLAlchemy AsyncSession instance
        """
        self.session = session
        logger.info("ConversationRepository initialized with ORM session")

    async def create_tables(self) -> None:
        """Create database tables - handled by SQLAlchemy migrations in production."""
        logger.info("Table creation handled by SQLAlchemy migrations")

    async def save(self, conversation: ConversationEntity) -> ConversationEntity:
        """
        Save or update a conversation using SQLAlchemy ORM.
        """
        try:
            # Update timestamp
            conversation.updated_at = datetime.now(UTC)
            
            # Convert domain entity to database model
            db_conversation = await self._entity_to_model(conversation)
            
            # Check if conversation exists
            existing = await self.session.get(ConversationModel, conversation.id)
            
            if existing:
                # Update existing conversation
                for key, value in self._model_to_dict(db_conversation).items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                db_conversation = existing
            else:
                # Add new conversation 
                self.session.add(db_conversation)
            
            await self.session.commit()
            
            # Audit logging with sanitized IDs
            safe_conv_id = str(conversation.id).replace('\n', '').replace('\r', '')[:50]
            safe_child_id = str(conversation.child_id).replace('\n', '').replace('\r', '')[:50]
            
            logger.info(
                f"Conversation {safe_conv_id} saved via ORM",
                conversation_id=safe_conv_id,
            )
            AUDIT_LOG_CHANNEL.info(
                "AUDIT: Conversation saved via ORM",
                conversation_id=safe_conv_id,
                child_id=safe_child_id,
            )
            
            return conversation

        except Exception as e:
            await self.session.rollback()
            
            # Sanitized error logging
            safe_conv_id = str(conversation.id).replace('\n', '').replace('\r', '')[:50]
            safe_error = str(e).replace('\n', '').replace('\r', '')[:200]
            
            logger.error(
                f"Failed to save conversation {safe_conv_id}: {safe_error}",
                conversation_id=safe_conv_id,
            )
            AUDIT_LOG_CHANNEL.error(
                "AUDIT: Conversation save failed via ORM",
                conversation_id=safe_conv_id,
                error=safe_error,
            )
            raise DatabaseConnectionError(f"Save operation failed: {e}") from e

    async def get_by_id(self, conversation_id: str) -> Optional[ConversationEntity]:
        """
        Get conversation by ID using SQLAlchemy ORM.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            ConversationEntity if found, None otherwise
        """
        try:
            # Use ORM select instead of raw SQL
            stmt = select(ConversationModel).where(ConversationModel.id == conversation_id)
            result = await self.session.execute(stmt)
            db_conversation = result.scalar_one_or_none()

            if not db_conversation:
                return None

            return await self._model_to_entity(db_conversation)

        except Exception as e:
            safe_conv_id = str(conversation_id).replace('\n', '').replace('\r', '')[:50]
            safe_error = str(e).replace('\n', '').replace('\r', '')[:200]
            logger.error(f"Failed to get conversation {safe_conv_id}: {safe_error}")
            raise DatabaseConnectionError(f"Get operation failed: {e}") from e

    async def get_by_child_id(self, child_id: str) -> List[ConversationEntity]:
        """
        Get all conversations for a specific child using SQLAlchemy ORM.

        Args:
            child_id: Child's unique identifier

        Returns:
            List of ConversationEntity objects
        """
        try:
            # Use ORM select with ordering instead of raw SQL
            stmt = (
                select(ConversationModel)
                .where(ConversationModel.child_id == child_id)
                .order_by(ConversationModel.session_start.desc())
            )
            result = await self.session.execute(stmt)
            db_conversations = result.scalars().all()

            # Convert database models to domain entities
            entities = []
            for db_conversation in db_conversations:
                entity = await self._model_to_entity(db_conversation)
                entities.append(entity)

            return entities

        except Exception as e:
            safe_child_id = str(child_id).replace('\n', '').replace('\r', '')[:50]
            safe_error = str(e).replace('\n', '').replace('\r', '')[:200]
            logger.error(f"Failed to get conversations for child {safe_child_id}: {safe_error}")
            raise DatabaseConnectionError(f"Get operation failed: {e}") from e

    async def delete(self, conversation_id: str) -> None:
        """
        Delete conversation by ID using SQLAlchemy ORM.

        Args:
            conversation_id: Unique conversation identifier

        Raises:
            ConversationNotFoundError: If conversation doesn't exist
            DatabaseConnectionError: If database operation fails
        """
        try:
            # Use ORM delete instead of raw SQL
            stmt = delete(ConversationModel).where(ConversationModel.id == conversation_id)
            result = await self.session.execute(stmt)
            
            if result.rowcount == 0:
                AUDIT_LOG_CHANNEL.warning(
                    "AUDIT: Conversation delete not found via ORM",
                    conversation_id=conversation_id,
                )
                raise ConversationNotFoundError(f"Conversation {conversation_id} not found")
            
            await self.session.commit()
            
            logger.info(
                f"Conversation {conversation_id} deleted via ORM",
                conversation_id=conversation_id,
            )
            AUDIT_LOG_CHANNEL.info(
                "AUDIT: Conversation deleted via ORM", 
                conversation_id=conversation_id
            )
            
        except ConversationNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Failed to delete conversation {conversation_id}: {e}",
                conversation_id=conversation_id,
            )
            AUDIT_LOG_CHANNEL.error(
                "AUDIT: Conversation delete failed via ORM",
                conversation_id=conversation_id,
                error=str(e),
            )
            raise DatabaseConnectionError(f"Delete operation failed: {e}") from e

    async def cleanup_old_conversations(self, retention_days: int = 90) -> int:
        """
        Clean up old conversations using SQLAlchemy ORM.

        Args:
            retention_days: Number of days to retain conversations

        Returns:
            Number of conversations deleted
        """
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
            
            # Use ORM delete instead of raw SQL
            stmt = delete(ConversationModel).where(
                ConversationModel.session_start < cutoff_date
            )
            result = await self.session.execute(stmt)
            deleted_count = result.rowcount
            
            await self.session.commit()
            
            logger.info(
                f"Cleaned up {deleted_count} old conversations via ORM",
                retention_days=retention_days,
            )
            AUDIT_LOG_CHANNEL.info(
                "AUDIT: COPPA cleanup via ORM",
                deleted_count=deleted_count,
                retention_days=retention_days,
            )
            
            return deleted_count
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to cleanup old conversations: {e}")
            AUDIT_LOG_CHANNEL.error("AUDIT: COPPA cleanup failed via ORM", error=str(e))
            raise DatabaseConnectionError(f"Cleanup operation failed: {e}") from e

    async def _entity_to_model(self, entity: ConversationEntity) -> ConversationModel:
        """Convert domain entity to database model."""
        return ConversationModel(
            id=entity.id,
            child_id=entity.child_id,
            title=entity.summary[:200] if entity.summary else None,  # Map summary to title
            session_start=entity.start_time,
            session_end=entity.end_time,
            total_messages=entity.message_count,
            safety_score=entity.safety_score,
            context_data=entity.metadata or {},
            created_at=entity.created_at or datetime.now(UTC),
            updated_at=entity.updated_at or datetime.now(UTC),
        )

    async def _model_to_entity(self, model: ConversationModel) -> ConversationEntity:
        """Convert database model to domain entity."""
        return ConversationEntity(
            id=str(model.id),
            child_id=str(model.child_id) if model.child_id else "",
            session_id=str(model.id),  # Use conversation ID as session ID
            start_time=model.session_start,
            end_time=model.session_end,
            summary=model.title or "",
            emotion_analysis="neutral",  # Default value
            sentiment_score=0.0,  # Default value  
            message_count=model.total_messages,
            safety_score=model.safety_score or 1.0,
            engagement_level="medium",  # Default value
            created_at=model.created_at,
            updated_at=model.updated_at,
            metadata=model.context_data or {},
        )

    def _model_to_dict(self, model: ConversationModel) -> Dict[str, Any]:
        """Convert model to dictionary for updates."""
        return {
            'title': model.title,
            'session_start': model.session_start,
            'session_end': model.session_end,
            'total_messages': model.total_messages,
            'safety_score': model.safety_score,
            'context_data': model.context_data,
            'updated_at': model.updated_at,
        }


class MessageRepository(IMessageRepository):
    """
    SQLAlchemy ORM-based message repository.

    Provides production-ready message persistence with:
    - Full async/await support using SQLAlchemy async
    - ORM-based queries instead of raw SQL
    - COPPA-compliant data handling
    - Performance optimization with proper relationships
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize message repository with async session.
        """
        self.session = session
        logger.info("MessageRepository initialized with ORM session")


    async def create_tables(self) -> None:
        """Create database tables - handled by SQLAlchemy migrations."""
        logger.info("Table creation handled by SQLAlchemy migrations")

    async def save_message(self, message: MessageEntity) -> MessageEntity:
        """
        Save a message using SQLAlchemy ORM.

        Args:
            message: MessageEntity to save

        Returns:
            Saved MessageEntity
        """
        try:
            # Convert domain entity to database model
            db_message = await self._entity_to_model(message)
            
            # Check if message exists
            existing = await self.session.get(MessageModel, message.id)
            
            if existing:
                # Update existing message
                for key, value in self._model_to_dict(db_message).items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                db_message = existing
            else:
                # Add new message
                self.session.add(db_message)
            
            await self.session.commit()
            
            logger.info(f"Message {message.id} saved via ORM", message_id=message.id)
            AUDIT_LOG_CHANNEL.info(
                "AUDIT: Message saved via ORM",
                message_id=message.id,
                conversation_id=message.conversation_id,
            )
            
            return message
            
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Failed to save message {message.id}: {e}", 
                message_id=message.id
            )
            AUDIT_LOG_CHANNEL.error(
                "AUDIT: Message save failed via ORM", 
                message_id=message.id, 
                error=str(e)
            )
            raise DatabaseConnectionError(f"Save operation failed: {e}") from e

    async def get_conversation_messages(
        self, conversation_id: str, limit: int = 50, offset: int = 0
    ) -> List[MessageEntity]:
        """
        Get messages for a conversation using SQLAlchemy ORM.

        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages to retrieve
            offset: Number of messages to skip

        Returns:
            List of MessageEntity objects
        """
        try:
            # Use ORM select with pagination instead of raw SQL
            stmt = (
                select(MessageModel)
                .where(MessageModel.conversation_id == conversation_id)
                .order_by(MessageModel.created_at.asc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(stmt)
            db_messages = result.scalars().all()

            logger.info(
                f"Fetched {len(db_messages)} messages for conversation {conversation_id} via ORM",
                conversation_id=conversation_id,
            )

            # Convert database models to domain entities
            entities = []
            for db_message in db_messages:
                entity = await self._model_to_entity(db_message)
                entities.append(entity)

            return entities
            
        except Exception as e:
            logger.error(
                f"Failed to get messages for conversation {conversation_id}: {e}",
                conversation_id=conversation_id,
            )
            raise DatabaseConnectionError(f"Get operation failed: {e}") from e

    async def delete_conversation_messages(self, conversation_id: str) -> int:
        """
        Delete all messages for a conversation using SQLAlchemy ORM.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Number of messages deleted
        """
        try:
            # Use ORM delete instead of raw SQL
            stmt = delete(MessageModel).where(
                MessageModel.conversation_id == conversation_id
            )
            result = await self.session.execute(stmt)
            deleted_count = result.rowcount
            
            await self.session.commit()
            
            logger.info(
                f"Deleted {deleted_count} messages for conversation {conversation_id} via ORM",
                conversation_id=conversation_id,
            )
            AUDIT_LOG_CHANNEL.info(
                "AUDIT: Messages deleted via ORM",
                conversation_id=conversation_id,
                deleted_count=deleted_count,
            )
            
            return deleted_count
            
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Failed to delete messages for conversation {conversation_id}: {e}",
                conversation_id=conversation_id,
            )
            AUDIT_LOG_CHANNEL.error(
                "AUDIT: Message delete failed via ORM",
                conversation_id=conversation_id,
                error=str(e),
            )
            raise DatabaseConnectionError(f"Delete operation failed: {e}") from e

    async def _entity_to_model(self, entity: MessageEntity) -> MessageModel:
        """Convert domain entity to database model."""
        return MessageModel(
            id=entity.id,
            conversation_id=entity.conversation_id,
            sender_type=entity.sender,
            content=entity.content_encrypted,  # Store encrypted content
            timestamp=entity.timestamp,
            safety_score=entity.safety_score,
            created_at=entity.created_at or datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def _model_to_entity(self, model: MessageModel) -> MessageEntity:
        """Convert database model to domain entity."""
        return MessageEntity(
            id=str(model.id),
            conversation_id=str(model.conversation_id),
            sender=model.sender_type,
            content_encrypted=model.content or "",  # Handle encrypted content
            timestamp=model.timestamp,
            emotion="neutral",  # Default value
            sentiment=0.0,  # Default value
            content_type="text",  # Default value
            sequence_number=0,  # Default value, could be enhanced
            safety_score=model.safety_score or 1.0,
            created_at=model.created_at,
            metadata={},  # Default empty metadata
        )

    def _model_to_dict(self, model: MessageModel) -> Dict[str, Any]:
        """Convert model to dictionary for updates."""
        return {
            'sender_type': model.sender_type,
            'content': model.content,
            'timestamp': model.timestamp,
            'safety_score': model.safety_score,
            'updated_at': model.updated_at,
        }


# FACTORY FUNCTIONS


def create_conversation_repository(session: AsyncSession) -> ConversationRepository:
    """Create an ORM-based conversation repository instance."""
    return ConversationRepository(session)


def create_message_repository(session: AsyncSession) -> MessageRepository:
    """Create an ORM-based message repository instance."""
    return MessageRepository(session)


# Export all repository classes and interfaces
__all__ = [
    "IConversationRepository",
    "IMessageRepository",
    "ConversationRepository",
    "MessageRepository",
    "create_conversation_repository",
    "create_message_repository",
    "DatabaseConnectionError",
    "ConversationNotFoundError",
    "MessageNotFoundError",
]
