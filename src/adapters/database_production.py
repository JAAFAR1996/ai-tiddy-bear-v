"""
🧸 AI TEDDY BEAR V5 - PRODUCTION DATABASE ADAPTER
===============================================
Enterprise-grade PostgreSQL database adapter with:
- Complete async/await implementation
- Comprehensive error handling and rollback
- Standardized transaction management
- UUID type safety and validation
- COPPA compliance features
- Connection pooling and monitoring
- Audit logging and security
"""

# Standard library imports
import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

# Third-party imports
from sqlalchemy import (
    create_engine,
    select,
    delete,
    and_,
    Column,
    String,
    DateTime,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session

# Internal imports
from src.infrastructure.persistence.models.production_models import (
    UserModel,
    ChildModel,
    ConversationModel,
    MessageModel,
    ConsentModel,
    Base,
)
from src.interfaces.repositories import (
    IUserRepository,
    IChildRepository,
    IConversationRepository,
    IMessageRepository,
    IEventRepository,
)
from src.interfaces.adapters import IDatabaseAdapter
from src.interfaces.exceptions import DatabaseError, ValidationError
from src.infrastructure.config.production_config import get_config, load_config

# Ensure config is loaded at startup
load_config()

# Configure logging
logger = logging.getLogger(__name__)


# ================================
# UTILITY FUNCTIONS
# ================================


def _validate_uuid(value: Union[str, uuid.UUID], field_name: str) -> uuid.UUID:
    """Validate and convert UUID with proper error handling."""
    if value is None:
        raise ValidationError(f"{field_name} cannot be None")

    if isinstance(value, uuid.UUID):
        return value

    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError as e:
            raise ValidationError(
                f"Invalid UUID format for {field_name}: {value}"
            ) from e

    raise ValidationError(f"{field_name} must be UUID or string, got {type(value)}")


def _validate_age(age: int) -> int:
    """Validate age for COPPA compliance."""
    if not isinstance(age, int):
        raise ValidationError(f"Age must be integer, got {type(age)}")

    if age < 3 or age > 13:
        raise ValidationError("Age must be between 3 and 13 for COPPA compliance")
    return age


def _validate_email(email: str) -> str:
    if not isinstance(email, str) or not email.strip():
        raise ValidationError("Email must be non-empty string")
    if "@" not in email or "." not in email:
        raise ValidationError(f"Invalid email format: {email}")
    return email.strip().lower()


def _validate_string(value: str, field_name: str, max_length: int = 255) -> str:
    """Validate string input."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be string, got {type(value)}")

    value = value.strip()
    if not value:
        raise ValidationError(f"{field_name} cannot be empty")

    if len(value) > max_length:
        raise ValidationError(f"{field_name} exceeds maximum length ({max_length})")

    return value


# ================================
# DATABASE CONNECTION MANAGER
# ================================


class DatabaseConnectionManager:
    """Manages database connections with connection pooling and health monitoring."""

    def __init__(self, config=None):

        self.config = config or get_config()
        self.async_engine = None
        self.sync_engine = None
        self.async_session_factory = None
        self.sync_session_factory = None
        self._initialized = False

    async def initialize(self):
        """Initialize database connections and session factories."""
        if self._initialized:
            return

        try:
            # Debug: Print DATABASE_URL to verify format
            print(f"🔍 DATABASE_URL: {self.config.DATABASE_URL}")

            # Create async engine
            self.async_engine = create_async_engine(
                self.config.DATABASE_URL,
                pool_size=self.config.DATABASE_POOL_SIZE,
                max_overflow=self.config.DATABASE_MAX_OVERFLOW,
                pool_timeout=self.config.DATABASE_POOL_TIMEOUT,
                pool_recycle=3600,
                echo=self.config.DEBUG,
                future=True,
            )

            # Create sync engine for migrations and compatibility
            sync_url = self.config.DATABASE_URL.replace(
                "+asyncpg", "+psycopg2"
            ).replace("postgresql://", "postgresql://")
            self.sync_engine = create_engine(
                sync_url,
                pool_size=self.config.DATABASE_POOL_SIZE,
                max_overflow=self.config.DATABASE_MAX_OVERFLOW,
                pool_timeout=self.config.DATABASE_POOL_TIMEOUT,
                pool_recycle=3600,
                echo=self.config.DEBUG,
            )

            # Create session factories
            self.async_session_factory = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )

            self.sync_session_factory = sessionmaker(
                self.sync_engine,
                class_=Session,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )

            self._initialized = True
            logger.info("Database connection manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database connections: {e}")
            raise DatabaseError(f"Database initialization failed: {e}") from e

    @asynccontextmanager
    async def get_async_session(self):
        """Get async database session with automatic cleanup."""
        if not self._initialized:
            await self.initialize()

        session = self.async_session_factory()
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error, rolled back: {e}")
            raise
        finally:
            await session.close()

    def get_sync_session(self):
        """Get sync database session."""
        if not self._initialized:
            raise DatabaseError("Database not initialized. Call initialize() first.")

        return self.sync_session_factory()

    async def health_check(self) -> bool:
        """Check database health."""
        try:
            async with self.get_async_session() as session:
                result = await session.execute(select(1))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def close(self):
        """Close all database connections."""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.sync_engine:
            self.sync_engine.dispose()

        self._initialized = False
        logger.info("Database connections closed")


# Global connection manager instance
_connection_manager = DatabaseConnectionManager()


async def get_database_session():
    """Get async database session for dependency injection."""
    async with _connection_manager.get_async_session() as session:
        yield session


# ================================
# BASE REPOSITORY CLASS
# ================================


class BaseRepository:
    """Base repository with common database operations and error handling."""

    def __init__(self, model_class):
        self.model_class = model_class
        self.connection_manager = _connection_manager

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute database operation with retry logic."""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                return await operation(*args, **kwargs)
            except OperationalError as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(
                        f"Database operation failed after {max_retries} retries: {e}"
                    )
                    raise DatabaseError(f"Database operation failed: {e}") from e

                # Wait before retry (exponential backoff)
                await asyncio.sleep(2**retry_count)
                logger.warning(
                    f"Database operation retry {retry_count}/{max_retries}: {e}"
                )
            except Exception as e:
                logger.error(f"Database operation failed: {e}")
                raise DatabaseError(f"Database operation failed: {e}") from e

    async def _validate_foreign_key(
        self, session: AsyncSession, model_class, key_value: uuid.UUID
    ):
        """Validate that foreign key reference exists."""
        result = await session.execute(
            select(model_class.id).where(model_class.id == key_value)
        )
        if not result.scalar_one_or_none():
            raise ValidationError(
                f"{model_class.__name__} with ID {key_value} not found"
            )


# ================================
# CONSENT REPOSITORY
# ================================


# ConsentModel is imported from production_models


class ProductionConsentRepository(BaseRepository):
    """Production repository for managing parental consents (COPPA compliance)."""

    def __init__(self):
        super().__init__(ConsentModel)

    async def create_consent(
        self,
        parent_email: str,
        child_id: str,
        consent_timestamp: datetime,
        ip_address: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ConsentModel:
        """Create a new parental consent record with full validation."""
        # Validate inputs
        parent_email = _validate_email(parent_email)
        child_id = _validate_uuid(child_id, "child_id")
        ip_address = _validate_string(ip_address, "ip_address", 45)  # IPv6 max length

        if not isinstance(consent_timestamp, datetime):
            raise ValidationError("consent_timestamp must be datetime object")

        async def _create_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    # Validate child exists
                    await self._validate_foreign_key(session, ChildModel, child_id)

                    consent_data = {
                        "parent_email": parent_email,
                        "child_id": child_id,
                        "consent_timestamp": consent_timestamp,
                        "ip_address": ip_address,
                        "extra": extra or {},
                        "created_at": datetime.utcnow(),
                    }

                    consent = ConsentModel(**consent_data)
                    session.add(consent)
                    await session.commit()
                    await session.refresh(consent)

                    logger.info(f"Created consent record for child {child_id}")
                    return consent

                except IntegrityError as e:
                    await session.rollback()
                    logger.error(f"Consent creation failed - integrity error: {e}")
                    raise ValidationError(
                        "Consent record already exists or violates constraints"
                    ) from e

        return await self._execute_with_retry(_create_operation)

    async def get_consent_by_child(self, child_id: str) -> Optional[ConsentModel]:
        """Get consent record by child ID."""
        child_id = _validate_uuid(child_id, "child_id")

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(ConsentModel).where(ConsentModel.child_id == child_id)
                )
                return result.scalar_one_or_none()

        return await self._execute_with_retry(_get_operation)

    async def get_consents_by_parent(self, parent_email: str) -> List[ConsentModel]:
        """Get all consents for a parent email."""
        parent_email = _validate_email(parent_email)

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(ConsentModel).where(
                        ConsentModel.parent_email == parent_email
                    )
                )
                return list(result.scalars().all())

        return await self._execute_with_retry(_get_operation)

    async def revoke_consent(self, consent_id: uuid.UUID) -> bool:
        """Revoke (delete) a consent record by its ID."""
        consent_id = _validate_uuid(consent_id, "consent_id")

        async def _revoke_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    result = await session.execute(
                        select(ConsentModel).where(ConsentModel.id == consent_id)
                    )
                    consent = result.scalar_one_or_none()

                    if consent:
                        await session.delete(consent)
                        await session.commit()
                        logger.info(f"Revoked consent {consent_id}")
                        return True

                    return False

                except Exception as e:
                    await session.rollback()
                    logger.error(f"Failed to revoke consent {consent_id}: {e}")
                    raise

        return await self._execute_with_retry(_revoke_operation)


# ================================
# EVENT REPOSITORY
# ================================


class EventModel(Base):
    """Event model for audit logging."""

    __tablename__ = "audit_events"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    description = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    correlation_id = Column(String(255), nullable=True)


class ProductionEventRepository(BaseRepository, IEventRepository):
    """Production event repository for audit and safety events."""

    def __init__(self):
        super().__init__(EventModel)

    async def log_event(self, event_data: Dict[str, Any]) -> EventModel:
        """Log audit event with validation."""
        # Validate required fields
        if not isinstance(event_data, dict):
            raise ValidationError("event_data must be dictionary")

        required_fields = ["event_type", "user_id", "description"]
        for field in required_fields:
            if field not in event_data:
                raise ValidationError(f"Missing required field: {field}")

        async def _log_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    event_data.update(
                        {
                            "id": uuid.uuid4(),
                            "timestamp": datetime.utcnow(),
                            "correlation_id": event_data.get(
                                "correlation_id", str(uuid.uuid4())
                            ),
                        }
                    )

                    event = EventModel(**event_data)
                    session.add(event)
                    await session.commit()
                    await session.refresh(event)

                    return event

                except Exception as e:
                    await session.rollback()
                    logger.error(f"Failed to log event: {e}")
                    raise

        return await self._execute_with_retry(_log_operation)

    async def get_events(self, **filters) -> List[EventModel]:
        """Get audit events with filtering."""

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                query = select(EventModel)

                # Apply filters
                conditions = []
                if "event_type" in filters:
                    conditions.append(EventModel.event_type == filters["event_type"])
                if "user_id" in filters:
                    user_id = _validate_uuid(filters["user_id"], "user_id")
                    conditions.append(EventModel.user_id == user_id)
                if "start_date" in filters:
                    conditions.append(EventModel.timestamp >= filters["start_date"])
                if "end_date" in filters:
                    conditions.append(EventModel.timestamp <= filters["end_date"])

                if conditions:
                    query = query.where(and_(*conditions))

                query = query.order_by(EventModel.timestamp.desc())
                query = query.limit(filters.get("limit", 100))

                result = await session.execute(query)
                return list(result.scalars().all())

        return await self._execute_with_retry(_get_operation)

    async def cleanup_old_events(self, days_old: int) -> int:
        """Clean up old audit events."""
        if not isinstance(days_old, int) or days_old < 1:
            raise ValidationError("days_old must be positive integer")

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        async def _cleanup_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    result = await session.execute(
                        delete(EventModel).where(EventModel.timestamp < cutoff_date)
                    )
                    deleted_count = result.rowcount
                    await session.commit()

                    logger.info(
                        f"Cleaned up {deleted_count} old events (older than {days_old} days)"
                    )
                    return deleted_count

                except Exception as e:
                    await session.rollback()
                    logger.error(f"Failed to cleanup old events: {e}")
                    raise

        return await self._execute_with_retry(_cleanup_operation)

    async def find_by_type(self, event_type: str) -> List[EventModel]:
        """Find events by type."""
        event_type = _validate_string(event_type, "event_type")
        return await self.get_events(event_type=event_type)

    async def find_by_child(self, child_id: str) -> List[EventModel]:
        """Find events for a specific child."""
        child_id = _validate_uuid(child_id, "child_id")
        return await self.get_events(user_id=child_id)


# ================================
# USER REPOSITORY
# ================================


class ProductionUserRepository(BaseRepository, IUserRepository):
    """Production user repository with UUID support and JSONB preferences."""

    def __init__(self):
        super().__init__(UserModel)

    async def create_user(
        self, email: str, password_hash: str, role: str = "parent", **kwargs
    ) -> UserModel:
        """Create new user with UUID primary key and full validation."""
        # Validate inputs
        email = _validate_email(email)
        password_hash = _validate_string(password_hash, "password_hash")
        role = _validate_string(role, "role", 50)

        if role not in ["parent", "admin", "moderator"]:
            raise ValidationError(f"Invalid role: {role}")

        async def _create_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    # Check if user already exists
                    existing = await session.execute(
                        select(UserModel).where(UserModel.email == email)
                    )
                    if existing.scalar_one_or_none():
                        raise ValidationError(f"User with email {email} already exists")

                    user_data = {
                        "id": uuid.uuid4(),
                        "email": email,
                        "password_hash": password_hash,
                        "role": role,
                        "preferences": kwargs.get("preferences", {}),
                        "first_name": kwargs.get("first_name"),
                        "last_name": kwargs.get("last_name"),
                        "phone_number": kwargs.get("phone_number"),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "is_active": True,
                    }

                    user = UserModel(**user_data)
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)

                    logger.info(f"Created user {email} with role {role}")
                    return user

                except IntegrityError as e:
                    await session.rollback()
                    logger.error(f"User creation failed - integrity error: {e}")
                    raise ValidationError(
                        "User already exists or violates constraints"
                    ) from e

        return await self._execute_with_retry(_create_operation)

    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """Get user by email with validation."""
        email = _validate_email(email)

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(UserModel).where(UserModel.email == email)
                )
                return result.scalar_one_or_none()

        return await self._execute_with_retry(_get_operation)

    async def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        """Get user by UUID with proper type conversion."""
        user_id = _validate_uuid(user_id, "user_id")

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(UserModel).where(UserModel.id == user_id)
                )
                return result.scalar_one_or_none()

        return await self._execute_with_retry(_get_operation)

    async def update_user(self, user_id: str, **updates) -> Optional[UserModel]:
        """Update user with validation."""
        user_id = _validate_uuid(user_id, "user_id")

        async def _update_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    user = await session.get(UserModel, user_id)
                    if not user:
                        return None

                    # Validate and apply updates
                    for key, value in updates.items():
                        if hasattr(user, key):
                            setattr(user, key, value)
                        else:
                            logger.warning(f"Ignoring unknown field: {key}")

                    user.updated_at = datetime.utcnow()
                    await session.commit()
                    await session.refresh(user)

                    logger.info(f"Updated user {user_id}")
                    return user

                except Exception as e:
                    await session.rollback()
                    logger.error(f"Failed to update user {user_id}: {e}")
                    raise

        return await self._execute_with_retry(_update_operation)

    async def delete_user(self, user_id: str) -> bool:
        """Delete user by ID."""
        user_id = _validate_uuid(user_id, "user_id")

        async def _delete_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    user = await session.get(UserModel, user_id)
                    if user:
                        await session.delete(user)
                        await session.commit()
                        logger.info(f"Deleted user {user_id}")
                        return True
                    return False

                except Exception as e:
                    await session.rollback()
                    logger.error(f"Failed to delete user {user_id}: {e}")
                    raise

        return await self._execute_with_retry(_delete_operation)


# ================================
# CHILD REPOSITORY
# ================================


class ProductionChildRepository(BaseRepository, IChildRepository):
    """Production child repository with COPPA compliance and JSONB settings."""

    def __init__(self):
        super().__init__(ChildModel)

    async def create_child(
        self,
        name: str,
        age: int,
        parent_id: str,
        safety_settings: Optional[Dict] = None,
        **kwargs,
    ) -> ChildModel:
        """Create child with age validation and COPPA compliance."""
        # Validate inputs
        name = _validate_string(name, "name", 100)
        age = _validate_age(age)
        parent_id = _validate_uuid(parent_id, "parent_id")

        async def _create_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    # Validate parent exists
                    await self._validate_foreign_key(session, UserModel, parent_id)

                    child_data = {
                        "id": uuid.uuid4(),
                        "name": name,
                        "age": age,
                        "parent_id": parent_id,
                        "safety_settings": safety_settings or {},
                        "preferences": kwargs.get("preferences", {}),
                        "data_collection_consent": kwargs.get(
                            "data_collection_consent", False
                        ),
                        "data_retention_days": kwargs.get("data_retention_days", 365),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "is_active": True,
                    }

                    child = ChildModel(**child_data)
                    session.add(child)
                    await session.commit()
                    await session.refresh(child)

                    logger.info(
                        f"Created child {name} (age {age}) for parent {parent_id}"
                    )
                    return child

                except IntegrityError as e:
                    await session.rollback()
                    logger.error(f"Child creation failed - integrity error: {e}")
                    raise ValidationError("Child creation violates constraints") from e

        return await self._execute_with_retry(_create_operation)

    async def get_child_by_id(self, child_id: str) -> Optional[ChildModel]:
        """Get child by UUID."""
        child_id = _validate_uuid(child_id, "child_id")

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(ChildModel).where(ChildModel.id == child_id)
                )
                return result.scalar_one_or_none()

        return await self._execute_with_retry(_get_operation)

    async def get_children_by_parent(self, parent_id: str) -> List[ChildModel]:
        """Get all children for a parent with relationship loading."""
        parent_id = _validate_uuid(parent_id, "parent_id")

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(ChildModel)
                    .where(ChildModel.parent_id == parent_id)
                    .where(ChildModel.is_active)
                    .order_by(ChildModel.created_at)
                )
                return list(result.scalars().all())

        return await self._execute_with_retry(_get_operation)

    async def update_child(self, child_id: str, **updates) -> Optional[ChildModel]:
        """Update child with validation."""
        child_id = _validate_uuid(child_id, "child_id")

        # Validate age if being updated
        if "age" in updates:
            updates["age"] = _validate_age(updates["age"])

        async def _update_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    child = await session.get(ChildModel, child_id)
                    if not child:
                        return None

                    # Apply updates
                    for key, value in updates.items():
                        if hasattr(child, key):
                            setattr(child, key, value)
                        else:
                            logger.warning(f"Ignoring unknown field: {key}")

                    child.updated_at = datetime.utcnow()
                    await session.commit()
                    await session.refresh(child)

                    logger.info(f"Updated child {child_id}")
                    return child

                except Exception as e:
                    await session.rollback()
                    logger.error(f"Failed to update child {child_id}: {e}")
                    raise

        return await self._execute_with_retry(_update_operation)

    async def delete_child(self, child_id: str) -> bool:
        """Soft delete child (COPPA compliance - retain data as required)."""
        child_id = _validate_uuid(child_id, "child_id")

        async def _delete_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    child = await session.get(ChildModel, child_id)
                    if child:
                        # Soft delete - mark as inactive
                        child.is_active = False
                        child.updated_at = datetime.utcnow()
                        await session.commit()
                        logger.info(f"Soft deleted child {child_id}")
                        return True
                    return False

                except Exception as e:
                    await session.rollback()
                    logger.error(f"Failed to delete child {child_id}: {e}")
                    raise

        return await self._execute_with_retry(_delete_operation)


# ================================
# CONVERSATION REPOSITORY
# ================================


class ProductionConversationRepository(BaseRepository, IConversationRepository):
    """Production conversation repository with JSONB metadata and performance indexes."""

    def __init__(self):
        super().__init__(ConversationModel)

    async def create_conversation(
        self, child_id: str, title: str = "Chat Session", **kwargs
    ) -> ConversationModel:
        """Create conversation with UUID foreign key."""
        # Validate inputs
        child_id = _validate_uuid(child_id, "child_id")
        title = _validate_string(title, "title", 255)

        async def _create_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    # Validate child exists
                    await self._validate_foreign_key(session, ChildModel, child_id)

                    conversation_data = {
                        "id": uuid.uuid4(),
                        "child_id": child_id,
                        "title": title,
                        "session_id": kwargs.get("session_id", uuid.uuid4()),
                        "summary": kwargs.get("summary", ""),
                        "sentiment_score": kwargs.get("sentiment_score", 0.0),
                        "safety_score": kwargs.get("safety_score", 1.0),
                        "engagement_level": kwargs.get("engagement_level", "medium"),
                        "metadata": kwargs.get("metadata", {}),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "is_active": True,
                    }

                    conversation = ConversationModel(**conversation_data)
                    session.add(conversation)
                    await session.commit()
                    await session.refresh(conversation)

                    logger.info(f"Created conversation {title} for child {child_id}")
                    return conversation

                except IntegrityError as e:
                    await session.rollback()
                    logger.error(f"Conversation creation failed - integrity error: {e}")
                    raise ValidationError(
                        "Conversation creation violates constraints"
                    ) from e

        return await self._execute_with_retry(_create_operation)

    async def get_conversation_by_id(
        self, conversation_id: str
    ) -> Optional[ConversationModel]:
        """Get conversation by UUID."""
        conversation_id = _validate_uuid(conversation_id, "conversation_id")

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(ConversationModel).where(
                        ConversationModel.id == conversation_id
                    )
                )
                return result.scalar_one_or_none()

        return await self._execute_with_retry(_get_operation)

    async def get_conversations_by_child(
        self, child_id: str, limit: int = 50
    ) -> List[ConversationModel]:
        """Get conversations for a child."""
        child_id = _validate_uuid(child_id, "child_id")

        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit must be positive integer")

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(ConversationModel)
                    .where(ConversationModel.child_id == child_id)
                    .where(ConversationModel.is_active)
                    .order_by(ConversationModel.created_at.desc())
                    .limit(limit)
                )
                return list(result.scalars().all())

        return await self._execute_with_retry(_get_operation)

    async def update_conversation(
        self, conversation_id: str, **updates
    ) -> Optional[ConversationModel]:
        """Update conversation."""
        conversation_id = _validate_uuid(conversation_id, "conversation_id")

        async def _update_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    conversation = await session.get(ConversationModel, conversation_id)
                    if not conversation:
                        return None

                    # Apply updates
                    for key, value in updates.items():
                        if hasattr(conversation, key):
                            setattr(conversation, key, value)
                        else:
                            logger.warning(f"Ignoring unknown field: {key}")

                    conversation.updated_at = datetime.utcnow()
                    await session.commit()
                    await session.refresh(conversation)

                    logger.info(f"Updated conversation {conversation_id}")
                    return conversation

                except Exception as e:
                    await session.rollback()
                    logger.error(
                        f"Failed to update conversation {conversation_id}: {e}"
                    )
                    raise

        return await self._execute_with_retry(_update_operation)


# ================================
# MESSAGE REPOSITORY
# ================================


class ProductionMessageRepository(BaseRepository, IMessageRepository):
    """Production message repository with sequence ordering and JSONB metadata."""

    def __init__(self):
        super().__init__(MessageModel)

    async def create_message(
        self,
        conversation_id: str,
        child_id: str,
        content: str,
        role: str,
        safety_score: float = 1.0,
        sequence_number: int = 0,
        **kwargs,
    ) -> MessageModel:
        """Create message with proper foreign keys and validation."""
        # Validate inputs
        conversation_id = _validate_uuid(conversation_id, "conversation_id")
        child_id = _validate_uuid(child_id, "child_id")
        content = _validate_string(content, "content", 4000)
        role = _validate_string(role, "role", 50)

        if not (0.0 <= safety_score <= 1.0):
            raise ValidationError("safety_score must be between 0.0 and 1.0")

        if not isinstance(sequence_number, int) or sequence_number < 0:
            raise ValidationError("sequence_number must be non-negative integer")

        async def _create_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    # Validate foreign keys
                    await self._validate_foreign_key(
                        session, ConversationModel, conversation_id
                    )
                    await self._validate_foreign_key(session, ChildModel, child_id)

                    message_data = {
                        "id": uuid.uuid4(),
                        "conversation_id": conversation_id,
                        "child_id": child_id,
                        "content": content,
                        "role": role,
                        "safety_score": safety_score,
                        "sequence_number": sequence_number,
                        "content_type": kwargs.get("content_type", "text"),
                        "emotion": kwargs.get("emotion", "neutral"),
                        "sentiment": kwargs.get("sentiment", 0.0),
                        "message_metadata": kwargs.get("metadata", {}),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "is_active": True,
                    }

                    message = MessageModel(**message_data)
                    session.add(message)
                    await session.commit()
                    await session.refresh(message)

                    logger.info(f"Created message in conversation {conversation_id}")
                    return message

                except IntegrityError as e:
                    await session.rollback()
                    logger.error(f"Message creation failed - integrity error: {e}")
                    raise ValidationError(
                        "Message creation violates constraints"
                    ) from e

        return await self._execute_with_retry(_create_operation)

    async def get_messages_by_conversation(
        self, conversation_id: str, limit: int = 50, offset: int = 0
    ) -> List[MessageModel]:
        """Get messages ordered by sequence number."""
        conversation_id = _validate_uuid(conversation_id, "conversation_id")

        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit must be positive integer")

        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be non-negative integer")

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(MessageModel)
                    .where(MessageModel.conversation_id == conversation_id)
                    .where(MessageModel.is_active)
                    .order_by(MessageModel.sequence_number)
                    .offset(offset)
                    .limit(limit)
                )
                return list(result.scalars().all())

        return await self._execute_with_retry(_get_operation)

    async def get_message_by_id(self, message_id: str) -> Optional[MessageModel]:
        """Get message by ID."""
        message_id = _validate_uuid(message_id, "message_id")

        async def _get_operation():
            async with self.connection_manager.get_async_session() as session:
                result = await session.execute(
                    select(MessageModel).where(MessageModel.id == message_id)
                )
                return result.scalar_one_or_none()

        return await self._execute_with_retry(_get_operation)

    async def update_message(
        self, message_id: str, **updates
    ) -> Optional[MessageModel]:
        """Update message."""
        message_id = _validate_uuid(message_id, "message_id")

        async def _update_operation():
            async with self.connection_manager.get_async_session() as session:
                try:
                    message = await session.get(MessageModel, message_id)
                    if not message:
                        return None

                    # Apply updates
                    for key, value in updates.items():
                        if hasattr(message, key):
                            setattr(message, key, value)
                        else:
                            logger.warning(f"Ignoring unknown field: {key}")

                    message.updated_at = datetime.utcnow()
                    await session.commit()
                    await session.refresh(message)

                    logger.info(f"Updated message {message_id}")
                    return message

                except Exception as e:
                    await session.rollback()
                    logger.error(f"Failed to update message {message_id}: {e}")
                    raise

        return await self._execute_with_retry(_update_operation)


# ================================
# DATABASE ADAPTER
# ================================


class ProductionDatabaseAdapter(IDatabaseAdapter):
    """Production database adapter with async support and connection pooling."""

    def __init__(self):
        self.connection_manager = _connection_manager
        self._initialized = False

    async def initialize(self):
        """Initialize database connections."""
        if not self._initialized:
            await self.connection_manager.initialize()
            self._initialized = True

    async def create_tables(self):
        """Create all database tables."""
        await self.initialize()

        async with self.connection_manager.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created successfully")

    async def health_check(self) -> bool:
        """Check database health."""
        return await self.connection_manager.health_check()

    async def connect(self, connection_string: str) -> bool:
        """Connect to database."""
        try:
            # Set connection string if provided
            if connection_string:
                # Update connection manager with new string if needed
                pass
            await self.initialize()
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from database."""
        try:
            await self.close()
            return True
        except Exception as e:
            logger.error(f"Database disconnection failed: {e}")
            return False

    async def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> Any:
        """Execute database query with basic security validation."""
        await self.initialize()

        # Basic security check - prevent dangerous operations
        query_upper = query.strip().upper()
        dangerous_keywords = ["DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
        if any(keyword in query_upper for keyword in dangerous_keywords):
            raise ValidationError(f"Query contains restricted operations")

        async with self.connection_manager.get_async_session() as session:
            try:
                if parameters:
                    result = await session.execute(text(query), parameters)
                else:
                    result = await session.execute(text(query))
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise DatabaseError(f"Query execution failed: {e}")

    async def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """Execute multiple queries in transaction with security validation."""
        try:
            await self.initialize()

            # Validate all queries before execution
            dangerous_keywords = [
                "DROP",
                "TRUNCATE",
                "ALTER",
                "CREATE",
                "GRANT",
                "REVOKE",
            ]
            for query_data in queries:
                query = query_data.get("query", "")
                query_upper = query.strip().upper()
                if any(keyword in query_upper for keyword in dangerous_keywords):
                    raise ValidationError(f"Transaction contains restricted operations")

            async with self.connection_manager.get_async_session() as session:
                async with session.begin():
                    for query_data in queries:
                        query = query_data.get("query", "")
                        parameters = query_data.get("parameters", {})
                        if parameters:
                            await session.execute(text(query), parameters)
                        else:
                            await session.execute(text(query))
                    await session.commit()
            return True
        except Exception as e:
            logger.error(f"Transaction execution failed: {e}")
            return False

    async def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status."""
        try:
            health = await self.health_check()
            return {
                "connected": health,
                "initialized": self._initialized,
                "pool_size": (
                    getattr(self.connection_manager.async_engine.pool, "size", 0)
                    if hasattr(self.connection_manager, "async_engine")
                    else 0
                ),
                "checked_out": (
                    getattr(self.connection_manager.async_engine.pool, "checked_out", 0)
                    if hasattr(self.connection_manager, "async_engine")
                    else 0
                ),
            }
        except Exception as e:
            return {
                "connected": False,
                "initialized": self._initialized,
                "error": str(e),
            }

    async def close(self):
        """Close database connections."""
        await self.connection_manager.close()
        self._initialized = False

    def get_user_repository(self) -> ProductionUserRepository:
        """Get user repository instance."""
        return ProductionUserRepository()

    def get_child_repository(self) -> ProductionChildRepository:
        """Get child repository instance."""
        return ProductionChildRepository()

    def get_conversation_repository(self) -> ProductionConversationRepository:
        """Get conversation repository instance."""
        return ProductionConversationRepository()

    def get_message_repository(self) -> ProductionMessageRepository:
        """Get message repository instance."""
        return ProductionMessageRepository()

    def get_event_repository(self) -> ProductionEventRepository:
        """Get event repository instance."""
        return ProductionEventRepository()

    def get_consent_repository(self) -> ProductionConsentRepository:
        """Get consent repository instance."""
        return ProductionConsentRepository()


# ================================
# INITIALIZATION FUNCTIONS
# ================================


async def initialize_production_database() -> ProductionDatabaseAdapter:
    """Initialize production database with comprehensive setup."""
    logger.info("🚀 Initializing production database...")

    try:
        adapter = ProductionDatabaseAdapter()
        await adapter.initialize()
        await adapter.create_tables()

        # Verify health
        if await adapter.health_check():
            logger.info("✅ Production database initialized successfully")
            logger.info(
                "Database features configured: UUID PKs, JSONB columns, Connection pooling, Async operations"
            )
            return adapter
        else:
            raise DatabaseError("Database health check failed after initialization")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise DatabaseError(f"Database initialization failed: {e}") from e


# Global adapter instance
_database_adapter: Optional[ProductionDatabaseAdapter] = None


async def get_database_adapter() -> ProductionDatabaseAdapter:
    """Get global database adapter instance."""
    global _database_adapter

    if _database_adapter is None:
        _database_adapter = await initialize_production_database()

    return _database_adapter


# Backward compatibility functions
def get_database():
    """Backward compatibility: Get sync database session."""
    if not _connection_manager._initialized:
        raise DatabaseError("Database not initialized")

    session = _connection_manager.get_sync_session()
    try:
        yield session
    finally:
        session.close()


# Entry point for CLI usage
if __name__ == "__main__":
    asyncio.run(initialize_production_database())
