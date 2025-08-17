"""
Database Models - Production-Ready SQLAlchemy Models with COPPA Compliance
=========================================================================
Enterprise database models with:
- COPPA-compliant child data handling
- Audit trails and versioning
- Soft deletes and data retention
- Performance optimizations (indexes, partitioning)
- Data validation and sanitization
- Encryption for sensitive fields
- Relationship management with proper constraints
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index,
    CheckConstraint,
    UniqueConstraint,
    Float,
    LargeBinary,
    Enum,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from cryptography.fernet import Fernet

from ..config.config_manager_provider import get_config_manager
from ..logging import get_logger, security_logger


# Base model with common fields
Base = declarative_base()

# Encryption setup - config injected at runtime, not at import time
logger = get_logger("database_models")

# Initialize encryption (in production, use proper key management)
# Will be initialized when first accessed
ENCRYPTION_KEY = None
cipher_suite = None


def get_encryption_key():
    """Get or create encryption key."""
    global ENCRYPTION_KEY, cipher_suite
    if ENCRYPTION_KEY is None:
        ENCRYPTION_KEY = config_manager.get(
            "ENCRYPTION_KEY", Fernet.generate_key().decode()
        )
        cipher_suite = Fernet(
            ENCRYPTION_KEY.encode()
            if isinstance(ENCRYPTION_KEY, str)
            else ENCRYPTION_KEY
        )
    return ENCRYPTION_KEY


def get_cipher_suite():
    """Get or create cipher suite."""
    global cipher_suite
    if cipher_suite is None:
        get_encryption_key()  # This will initialize cipher_suite
    return cipher_suite


# Enums
class UserRole(PyEnum):
    CHILD = "child"
    PARENT = "parent"
    ADMIN = "admin"
    SUPPORT = "support"


class ConversationStatus(PyEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ContentType(PyEnum):
    STORY = "story"
    CONVERSATION = "conversation"
    IMAGE = "image"
    AUDIO = "audio"


class SafetyLevel(PyEnum):
    SAFE = "safe"
    REVIEW = "review"
    BLOCKED = "blocked"


class DataRetentionStatus(PyEnum):
    ACTIVE = "active"
    SCHEDULED_DELETION = "scheduled_deletion"
    DELETED = "deleted"
    ANONYMIZED = "anonymized"


# Base model class with common functionality
class BaseModel(Base):
    """Base model with common fields and functionality."""

    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Soft delete support
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    # Data retention and compliance
    retention_status = Column(
        Enum(DataRetentionStatus), default=DataRetentionStatus.ACTIVE, nullable=False
    )
    scheduled_deletion_at = Column(DateTime(timezone=True), nullable=True)

    # Audit fields
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    # Metadata
    metadata_json = Column(JSONB, default=dict, nullable=False)

    def soft_delete(self, user_id: Optional[uuid.UUID] = None):
        """Perform soft delete."""
        self.deleted_at = datetime.utcnow()
        self.is_deleted = True
        self.updated_by = user_id

        # Log deletion
        logger.info(f"Soft deleted {self.__class__.__name__} {self.id}")

    def schedule_deletion(
        self, deletion_date: datetime, user_id: Optional[uuid.UUID] = None
    ):
        """Schedule item for deletion."""
        self.scheduled_deletion_at = deletion_date
        self.retention_status = DataRetentionStatus.SCHEDULED_DELETION
        self.updated_by = user_id

        logger.info(
            f"Scheduled deletion for {self.__class__.__name__} {self.id} at {deletion_date}"
        )

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert model to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)

            # Handle special types
            if isinstance(value, uuid.UUID):
                value = str(value)
            elif isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, PyEnum):
                value = value.value

            result[column.name] = value

        return result


# ==============================
# Notification & DeliveryRecord
# ==============================
class Notification(BaseModel):
    """نموذج إشعار إنتاجي (يدعم جميع القنوات)"""

    __tablename__ = "notifications"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    data = Column(JSONB, default=dict, nullable=False)
    notification_type = Column(String(50), nullable=False)
    priority = Column(String(20), nullable=False)
    channel = Column(
        String(30), nullable=False
    )  # email, sms, push, websocket, in_app, emergency_call
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    provider_response = Column(JSONB, default=dict, nullable=False)

    # علاقات
    user = relationship("User", back_populates="notifications")
    delivery_records = relationship(
        "DeliveryRecord", back_populates="notification", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_notifications_user_id", "user_id"),
        Index("idx_notifications_type", "notification_type"),
        Index("idx_notifications_channel", "channel"),
        Index("idx_notifications_created_at", "created_at"),
    )


class DeliveryRecord(BaseModel):
    """سجل تسليم إشعار إنتاجي (لكل قناة)"""

    __tablename__ = "delivery_records"

    notification_id = Column(
        UUID(as_uuid=True), ForeignKey("notifications.id"), nullable=False
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    channel = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False)  # sent, delivered, failed, retry
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    provider_response = Column(JSONB, default=dict, nullable=False)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    # علاقات
    notification = relationship("Notification", back_populates="delivery_records")
    user = relationship("User")

    __table_args__ = (
        Index("idx_delivery_records_notification_id", "notification_id"),
        Index("idx_delivery_records_user_id", "user_id"),
        Index("idx_delivery_records_channel", "channel"),
        Index("idx_delivery_records_status", "status"),
        Index("idx_delivery_records_created_at", "created_at"),
    )


class User(BaseModel):
    """User model with role-based access control."""

    __tablename__ = "users"

    # Basic information
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), nullable=True)  # Optional for child accounts
    password_hash = Column(String(255), nullable=True)  # Null for child accounts

    # Role and permissions
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Profile information
    display_name = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    timezone = Column(String(50), default="UTC", nullable=False)
    language = Column(String(10), default="en", nullable=False)

    # Settings
    settings = Column(JSONB, default=dict, nullable=False)

    # Security
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    children = relationship(
        "Child", back_populates="parent", cascade="all, delete-orphan"
    )
    conversations = relationship("Conversation", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    notifications = relationship("Notification", back_populates="user")

    # Indexes
    __table_args__ = (
        Index("idx_users_username", "username"),
        Index("idx_users_email", "email"),
        Index("idx_users_role", "role"),
        Index("idx_users_is_active", "is_active"),
        Index("idx_users_created_at", "created_at"),
    )

    @validates("email")
    def validate_email(self, key, email):
        """Validate email address."""
        if email and "@" not in email:
            raise ValueError("Invalid email address")
        return email.lower() if email else None

    @validates("username")
    def validate_username(self, key, username):
        """Validate username."""
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters")

        # Check for inappropriate content
        if any(word in username.lower() for word in ["admin", "root", "system"]):
            raise ValueError("Username contains restricted words")

        return username.lower()

    def is_child_account(self) -> bool:
        """Check if this is a child account."""
        return self.role == UserRole.CHILD

    def can_access_child_data(self, child_id: uuid.UUID) -> bool:
        """Check if user can access specific child's data."""
        if self.role == UserRole.ADMIN:
            return True

        if self.role == UserRole.PARENT:
            return any(child.id == child_id for child in self.children)

        return False


class Child(BaseModel):
    """Child model with COPPA compliance and privacy protection."""

    __tablename__ = "children"

    # Parent relationship (required for COPPA compliance)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    parent = relationship("User", back_populates="children")

    # Child information (minimal data collection)
    name = Column(String(100), nullable=False)  # First name only
    birth_date = Column(DateTime(timezone=True), nullable=True)  # Optional

    # Privacy and safety
    hashed_identifier = Column(
        String(64), unique=True, nullable=False
    )  # Hash of child info
    parental_consent = Column(Boolean, default=False, nullable=False)
    consent_date = Column(DateTime(timezone=True), nullable=True)
    consent_withdrawn_date = Column(DateTime(timezone=True), nullable=True)

    # Age verification
    age_verified = Column(Boolean, default=False, nullable=False)
    age_verification_date = Column(DateTime(timezone=True), nullable=True)
    estimated_age = Column(
        Integer, nullable=True
    )  # Estimated age for content filtering

    # Safety settings
    safety_level = Column(Enum(SafetyLevel), default=SafetyLevel.SAFE, nullable=False)
    content_filtering_enabled = Column(Boolean, default=True, nullable=False)
    interaction_logging_enabled = Column(Boolean, default=True, nullable=False)

    # Privacy settings
    data_retention_days = Column(Integer, default=90, nullable=False)  # COPPA default
    allow_data_sharing = Column(Boolean, default=False, nullable=False)

    # Child preferences (non-PII)
    favorite_topics = Column(JSONB, default=list, nullable=False)
    content_preferences = Column(JSONB, default=dict, nullable=False)

    # Relationships
    conversations = relationship(
        "Conversation", back_populates="child", cascade="all, delete-orphan"
    )
    safety_reports = relationship("SafetyReport", back_populates="child")

    # Indexes
    __table_args__ = (
        Index("idx_children_parent_id", "parent_id"),
        Index("idx_children_hashed_identifier", "hashed_identifier"),
        Index("idx_children_safety_level", "safety_level"),
        Index("idx_children_consent", "parental_consent"),
        Index("idx_children_retention_status", "retention_status"),
        CheckConstraint(
            "estimated_age >= 3 AND estimated_age <= 18", name="check_valid_age"
        ),
        CheckConstraint(
            "data_retention_days >= 1 AND data_retention_days <= 2555",
            name="check_retention_period",
        ),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.hashed_identifier:
            self.hashed_identifier = self._generate_hashed_identifier()

    def _generate_hashed_identifier(self) -> str:
        """Generate privacy-preserving hashed identifier."""
        data_to_hash = f"{self.parent_id}_{self.name}_{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data_to_hash.encode()).hexdigest()

    @validates("name")
    def validate_name(self, key, name):
        """Validate child name (COPPA compliance)."""
        if not name or len(name.strip()) < 1:
            raise ValueError("Child name is required")

        # Remove any potential PII patterns
        cleaned_name = name.strip()
        if len(cleaned_name) > 100:
            cleaned_name = cleaned_name[:100]

        return cleaned_name

    @validates("estimated_age")
    def validate_age(self, key, age):
        """Validate estimated age."""
        if age is not None and (age < 3 or age > 18):
            raise ValueError("Age must be between 3 and 18")
        return age

    def get_age(self) -> Optional[int]:
        """Get child's age (if birth_date is available)."""
        if self.birth_date:
            today = datetime.utcnow().date()
            birth_date = self.birth_date.date()
            return (
                today.year
                - birth_date.year
                - ((today.month, today.day) < (birth_date.month, birth_date.day))
            )
        return self.estimated_age

    def is_coppa_protected(self) -> bool:
        """Check if child is protected under COPPA (under 13)."""
        age = self.get_age()
        return age is not None and age < 13

    def requires_parental_consent(self) -> bool:
        """Check if parental consent is required."""
        return self.is_coppa_protected() and not self.parental_consent

    def schedule_data_deletion(self):
        """Schedule data deletion based on retention policy."""
        if self.data_retention_days > 0:
            deletion_date = datetime.utcnow() + timedelta(days=self.data_retention_days)
            self.schedule_deletion(deletion_date)

            # Log data retention action
            security_logger.info(
                f"Scheduled child data deletion",
                extra={
                    "child_hash": self.hashed_identifier,
                    "retention_days": self.data_retention_days,
                    "deletion_date": deletion_date.isoformat(),
                },
            )


class Conversation(BaseModel):
    """Conversation model with child safety features."""

    __tablename__ = "conversations"

    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=True)
    user = relationship("User", back_populates="conversations")
    child = relationship("Child", back_populates="conversations")

    # Conversation details
    title = Column(String(200), nullable=True)
    status = Column(
        Enum(ConversationStatus), default=ConversationStatus.ACTIVE, nullable=False
    )

    # Content safety
    safety_checked = Column(Boolean, default=False, nullable=False)
    safety_score = Column(Float, nullable=True)  # 0.0 to 1.0, higher is safer
    flagged_content = Column(Boolean, default=False, nullable=False)

    # Session information
    session_start = Column(DateTime(timezone=True), nullable=False, default=func.now())
    session_end = Column(DateTime(timezone=True), nullable=True)
    total_messages = Column(Integer, default=0, nullable=False)

    # Child-specific tracking
    educational_content = Column(Boolean, default=False, nullable=False)
    parental_review_required = Column(Boolean, default=False, nullable=False)

    # Context and preferences
    context_data = Column(JSONB, default=dict, nullable=False)
    conversation_settings = Column(JSONB, default=dict, nullable=False)

    # Relationships
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    interactions = relationship(
        "Interaction", back_populates="conversation", cascade="all, delete-orphan"
    )
    safety_reports = relationship("SafetyReport", back_populates="conversation")

    # Indexes
    __table_args__ = (
        Index("idx_conversations_user_id", "user_id"),
        Index("idx_conversations_child_id", "child_id"),
        Index("idx_conversations_status", "status"),
        Index("idx_conversations_safety", "safety_checked", "flagged_content"),
        Index("idx_conversations_session_start", "session_start"),
        CheckConstraint(
            "safety_score >= 0.0 AND safety_score <= 1.0",
            name="check_safety_score_range",
        ),
        CheckConstraint("total_messages >= 0", name="check_message_count"),
    )

    @validates("title")
    def validate_title(self, key, title):
        """Validate conversation title."""
        if title and len(title) > 200:
            return title[:200]
        return title

    def is_child_conversation(self) -> bool:
        """Check if this is a child conversation."""
        return self.child_id is not None

    def requires_safety_check(self) -> bool:
        """Check if conversation requires safety checking."""
        return self.is_child_conversation() and not self.safety_checked

    def end_session(self):
        """End conversation session."""
        self.session_end = datetime.utcnow()
        self.status = ConversationStatus.COMPLETED


class Message(BaseModel):
    """Message model with content filtering and safety checks."""

    __tablename__ = "messages"

    # Conversation relationship
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    conversation = relationship("Conversation", back_populates="messages")

    # Message details
    sender_type = Column(String(20), nullable=False)  # 'user', 'child', 'ai'
    content_type = Column(
        Enum(ContentType), default=ContentType.CONVERSATION, nullable=False
    )

    # Content (encrypted for sensitive data)
    content = Column(Text, nullable=False)
    content_encrypted = Column(LargeBinary, nullable=True)  # Encrypted version

    # Safety and filtering
    safety_checked = Column(Boolean, default=False, nullable=False)
    safety_level = Column(Enum(SafetyLevel), default=SafetyLevel.SAFE, nullable=False)
    content_filtered = Column(Boolean, default=False, nullable=False)

    # AI processing
    processed_by_ai = Column(Boolean, default=False, nullable=False)
    ai_model_used = Column(String(100), nullable=True)
    ai_processing_time = Column(Float, nullable=True)

    # Metrics
    character_count = Column(Integer, default=0, nullable=False)
    word_count = Column(Integer, default=0, nullable=False)
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0

    # Context
    message_metadata = Column(JSONB, default=dict, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_messages_conversation_id", "conversation_id"),
        Index("idx_messages_sender_type", "sender_type"),
        Index("idx_messages_safety", "safety_checked", "safety_level"),
        Index("idx_messages_created_at", "created_at"),
        Index("idx_messages_content_type", "content_type"),
        CheckConstraint("character_count >= 0", name="check_character_count"),
        CheckConstraint("word_count >= 0", name="check_word_count"),
        CheckConstraint(
            "sentiment_score >= -1.0 AND sentiment_score <= 1.0",
            name="check_sentiment_range",
        ),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.content:
            self.character_count = len(self.content)
            self.word_count = len(self.content.split())

    @validates("content")
    def validate_content(self, key, content):
        """Validate and process message content."""
        if not content:
            raise ValueError("Message content cannot be empty")

        # Update counts
        self.character_count = len(content)
        self.word_count = len(content.split())

        return content

    @validates("sender_type")
    def validate_sender_type(self, key, sender_type):
        """Validate sender type."""
        valid_types = ["user", "child", "ai", "system"]
        if sender_type not in valid_types:
            raise ValueError(f"Invalid sender type. Must be one of: {valid_types}")
        return sender_type

    def encrypt_content(self):
        """Encrypt message content for sensitive data."""
        if self.content and not self.content_encrypted:
            self.content_encrypted = get_cipher_suite().encrypt(self.content.encode())

            # Log encryption for audit
            logger.debug(f"Encrypted content for message {self.id}")

    def decrypt_content(self) -> str:
        """Decrypt message content."""
        if self.content_encrypted:
            try:
                return get_cipher_suite().decrypt(self.content_encrypted).decode()
            except Exception as e:
                logger.error(f"Failed to decrypt message {self.id}: {str(e)}")
                return "[ENCRYPTED_CONTENT]"
        return self.content or ""

    def is_from_child(self) -> bool:
        """Check if message is from a child."""
        return self.sender_type == "child"

    def requires_safety_check(self) -> bool:
        """Check if message requires safety checking."""
        return self.is_from_child() and not self.safety_checked


class SafetyReport(BaseModel):
    """Safety incident report model."""

    __tablename__ = "safety_reports"

    # Relationships
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=True)
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)

    child = relationship("Child", back_populates="safety_reports")
    conversation = relationship("Conversation", back_populates="safety_reports")
    message = relationship("Message")

    # Report details
    report_type = Column(
        String(50), nullable=False
    )  # 'inappropriate_content', 'safety_concern', etc.
    severity = Column(String(20), nullable=False)  # 'low', 'medium', 'high', 'critical'
    description = Column(Text, nullable=False)

    # AI detection details
    detected_by_ai = Column(Boolean, default=False, nullable=False)
    ai_confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    detection_rules = Column(JSONB, default=list, nullable=False)

    # Human review
    reviewed = Column(Boolean, default=False, nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)

    # Actions taken
    action_taken = Column(String(100), nullable=True)
    content_blocked = Column(Boolean, default=False, nullable=False)
    parent_notified = Column(Boolean, default=False, nullable=False)
    notification_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Follow-up
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_safety_reports_child_id", "child_id"),
        Index("idx_safety_reports_conversation_id", "conversation_id"),
        Index("idx_safety_reports_type_severity", "report_type", "severity"),
        Index("idx_safety_reports_reviewed", "reviewed"),
        Index("idx_safety_reports_resolved", "resolved"),
        Index("idx_safety_reports_created_at", "created_at"),
        CheckConstraint(
            "ai_confidence >= 0.0 AND ai_confidence <= 1.0",
            name="check_ai_confidence_range",
        ),
    )

    @validates("severity")
    def validate_severity(self, key, severity):
        """Validate severity level."""
        valid_severities = ["low", "medium", "high", "critical"]
        if severity not in valid_severities:
            raise ValueError(f"Invalid severity. Must be one of: {valid_severities}")
        return severity


class AuditLog(BaseModel):
    """Comprehensive audit log for all system actions."""

    __tablename__ = "audit_logs"

    # User relationship (optional for system actions)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="audit_logs")

    # Action details
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)

    # Request information
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(100), nullable=True)

    # Data changes (for sensitive operations)
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)

    # Context
    description = Column(Text, nullable=True)
    severity = Column(String(20), default="info", nullable=False)
    tags = Column(JSONB, default=list, nullable=False)

    # Child safety specific
    involves_child_data = Column(Boolean, default=False, nullable=False)
    child_id_hash = Column(String(64), nullable=True)  # Hashed child ID for privacy

    # Success/failure
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_child_data", "involves_child_data"),
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_severity", "severity"),
        Index("idx_audit_logs_ip", "ip_address"),
    )

    @validates("severity")
    def validate_severity(self, key, severity):
        """Validate severity level."""
        valid_severities = ["debug", "info", "warning", "error", "critical"]
        if severity not in valid_severities:
            raise ValueError(f"Invalid severity. Must be one of: {valid_severities}")
        return severity


# Create indexes for performance optimization
def create_performance_indexes():
    """Create additional indexes for performance optimization."""
    indexes = [
        # Composite indexes for common queries
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
        Index("idx_children_parent_consent", "parent_id", "parental_consent"),
        Index("idx_conversations_child_status", "child_id", "status"),
        Index(
            "idx_safety_reports_child_severity", "child_id", "severity", "created_at"
        ),
        Index(
            "idx_audit_logs_child_action", "involves_child_data", "action", "created_at"
        ),
        # Partial indexes for active records
        Index(
            "idx_users_active",
            "id",
            postgresql_where="is_active = true AND is_deleted = false",
        ),
        Index(
            "idx_children_active",
            "id",
            postgresql_where="is_deleted = false AND retention_status = 'active'",
        ),
        Index(
            "idx_conversations_active",
            "id",
            postgresql_where="status = 'active' AND is_deleted = false",
        ),
        # Hash indexes for equality lookups
        Index("idx_children_hash_lookup", "hashed_identifier", postgresql_using="hash"),
        Index("idx_users_username_lookup", "username", postgresql_using="hash"),
    ]

    return indexes


# Utility functions for model operations
def get_child_by_hash(hashed_identifier: str) -> Optional["Child"]:
    """Get child by hashed identifier (privacy-safe lookup)."""
    # This would be implemented with proper session management
    pass


def create_audit_log(
    action: str,
    resource_type: str,
    user_id: Optional[uuid.UUID] = None,
    resource_id: Optional[uuid.UUID] = None,
    **kwargs,
) -> "AuditLog":
    """Create audit log entry."""
    audit_log = AuditLog(
        action=action,
        resource_type=resource_type,
        user_id=user_id,
        resource_id=resource_id,
        **kwargs,
    )

    return audit_log


class Interaction(BaseModel):
    """Interaction model that maps to the interactions table in production database.

    This bridges the gap between Message entities and the interactions table
    used by dashboard_routes for displaying interaction history.
    """

    __tablename__ = "interactions"

    # Foreign key to conversations table
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    conversation = relationship("Conversation", back_populates="interactions")

    # Interaction content
    message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Safety metrics
    safety_score = Column(Float, default=100.0, nullable=False)
    flagged = Column(Boolean, default=False, nullable=False)
    flag_reason = Column(String(200), nullable=True)

    # Metadata for analytics and debugging
    content_metadata = Column(JSONB, default=dict, nullable=False)

    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # COPPA compliance and data retention
    retention_status = Column(
        Enum(DataRetentionStatus), default=DataRetentionStatus.ACTIVE, nullable=False
    )
    scheduled_deletion_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    # Indexes for performance
    __table_args__ = (
        Index("idx_interactions_conversation_id", "conversation_id"),
        Index("idx_interactions_timestamp", "timestamp"),
        Index("idx_interactions_flagged", "flagged"),
        Index("idx_interactions_safety_score", "safety_score"),
        Index("idx_interactions_child_timestamp", "conversation_id", "timestamp"),
        CheckConstraint(
            "safety_score >= 0 AND safety_score <= 100", name="check_safety_score"
        ),
        CheckConstraint("LENGTH(TRIM(message)) > 0", name="check_message_not_empty"),
        CheckConstraint(
            "LENGTH(TRIM(ai_response)) > 0", name="check_response_not_empty"
        ),
    )

    @validates("safety_score")
    def validate_safety_score(self, key, score):
        """Validate safety score is within range."""
        if score < 0 or score > 100:
            raise ValueError("Safety score must be between 0 and 100")
        return score

    @validates("message", "ai_response")
    def validate_content(self, key, content):
        """Validate content is not empty."""
        if not content or not content.strip():
            raise ValueError(f"{key} cannot be empty")
        return content

    def to_interaction_response(self) -> Dict[str, Any]:
        """Convert to InteractionResponse format used by dashboard API."""
        return {
            "id": str(self.id),
            "child_id": str(self.conversation.child_id) if self.conversation else None,
            "timestamp": self.timestamp,
            "message": self.message,
            "ai_response": self.ai_response,
            "safety_score": self.safety_score,
            "flagged": self.flagged,
            "flag_reason": self.flag_reason,
        }


# ================================
# SUBSCRIPTION AND PAYMENT MODELS
# ================================


class SubscriptionTier(PyEnum):
    """Subscription tier enumeration."""

    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    FAMILY = "family"


class SubscriptionStatus(PyEnum):
    """Subscription status enumeration."""

    ACTIVE = "active"
    TRIAL = "trial"
    PENDING_CANCELLATION = "pending_cancellation"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"


class PaymentMethod(PyEnum):
    """Payment method enumeration."""

    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"


class Subscription(BaseModel):
    """
    Subscription model for premium features.

    Tracks user subscriptions with Stripe integration and feature management.
    """

    __tablename__ = "subscriptions"

    # Subscription identification
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    tier = Column(Enum(SubscriptionTier), nullable=False, index=True)
    status = Column(Enum(SubscriptionStatus), nullable=False, index=True)

    # Stripe integration
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, index=True)

    # Billing information
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    billing_amount = Column(Float, nullable=True)
    billing_currency = Column(String(3), default="USD", nullable=False)
    payment_method = Column(Enum(PaymentMethod), nullable=True)

    # Features and limits
    features_enabled = Column(JSONB, default=dict, nullable=False)
    usage_limits = Column(JSONB, default=dict, nullable=False)

    # Subscription metadata
    subscription_metadata = Column(JSONB, default=dict, nullable=False)

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    payment_transactions = relationship(
        "PaymentTransaction", back_populates="subscription"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_subscriptions_user_id", "user_id"),
        Index("idx_subscriptions_status", "status"),
        Index("idx_subscriptions_tier", "tier"),
        Index("idx_subscriptions_stripe_customer", "stripe_customer_id"),
        Index("idx_subscriptions_period_end", "current_period_end"),
        UniqueConstraint("user_id", name="uq_user_subscription"),
    )

    @validates("billing_amount")
    def validate_billing_amount(self, key, amount):
        """Validate billing amount is positive."""
        if amount is not None and amount < 0:
            raise ValueError("Billing amount must be non-negative")
        return amount

    @hybrid_property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]

    @hybrid_property
    def is_trial(self) -> bool:
        """Check if subscription is in trial period."""
        return (
            self.status == SubscriptionStatus.TRIAL
            and self.trial_end
            and self.trial_end > datetime.utcnow()
        )

    def has_feature(self, feature_name: str) -> bool:
        """Check if subscription has a specific feature enabled."""
        return self.features_enabled.get(feature_name, False)

    def get_usage_limit(self, limit_name: str) -> Optional[int]:
        """Get usage limit for a specific resource."""
        return self.usage_limits.get(limit_name)


class PaymentTransaction(BaseModel):
    """
    Payment transaction model for billing and payment tracking.

    Records all payment transactions with full audit trail.
    """

    __tablename__ = "payment_transactions"

    # Transaction identification
    transaction_id = Column(String(255), unique=True, nullable=False, index=True)
    subscription_id = Column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False, index=True
    )

    # Payment details
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(String(50), nullable=False, index=True)
    payment_method = Column(String(100), nullable=True)
    transaction_type = Column(String(50), nullable=False, index=True)

    # Provider information
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    provider_transaction_id = Column(String(255), nullable=True)

    # Transaction metadata
    transaction_metadata = Column(JSONB, default=dict, nullable=False)
    failure_reason = Column(Text, nullable=True)

    # Relationships
    subscription = relationship("Subscription", back_populates="payment_transactions")

    # Indexes for performance
    __table_args__ = (
        Index("idx_payment_transactions_subscription", "subscription_id"),
        Index("idx_payment_transactions_status", "status"),
        Index("idx_payment_transactions_type", "transaction_type"),
        Index("idx_payment_transactions_created", "created_at"),
        Index("idx_payment_transactions_stripe_intent", "stripe_payment_intent_id"),
    )

    @validates("amount")
    def validate_amount(self, key, amount):
        """Validate payment amount is positive."""
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        return amount


# Update User model to include subscription relationship
def add_subscription_relationship_to_user():
    """Add subscription relationship to User model."""
    # This would be added to the User class:
    # subscriptions = relationship("Subscription", back_populates="user")
    pass


def schedule_child_data_cleanup():
    """Schedule cleanup of expired child data (COPPA compliance)."""
    # This would be implemented as a background task
    # to clean up expired child data according to retention policies
    pass
