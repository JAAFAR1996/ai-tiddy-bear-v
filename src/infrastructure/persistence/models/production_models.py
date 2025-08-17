"""
Production Database Models - Multi-Database Support
Enterprise-grade SQLAlchemy models supporting both SQLite and PostgreSQL
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    Float,
    Integer,
    Boolean,
    ForeignKey,
    Index,
    CheckConstraint,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.sql import func

# Import database-specific types conditionally
try:
    from sqlalchemy.dialects.postgresql import UUID, JSONB

    HAS_POSTGRESQL = True
except ImportError:
    HAS_POSTGRESQL = False

# Define UUID type that works with both SQLite and PostgreSQL
import os

database_url = os.getenv("DATABASE_URL", "")
if "sqlite" in database_url.lower():
    UUID_TYPE = String
    JSON_TYPE = JSON  # SQLite uses JSON
else:
    if HAS_POSTGRESQL:
        UUID_TYPE = UUID
        JSON_TYPE = JSON  # Use JSON instead of JSONB for compatibility
    else:
        UUID_TYPE = String
        JSON_TYPE = JSON

Base = declarative_base()


# --- COPPA Parental Consent Model ---
class ConsentModel(Base):
    """Production model for parental consents (COPPA compliance)"""

    __tablename__ = "parental_consents"

    id: Column = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_email: Column = Column(String(255), nullable=False, index=True)
    child_id: Column = Column(
        String,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consent_timestamp: Column = Column(DateTime, default=func.now(), nullable=False)
    ip_address: Column = Column(String(45), nullable=True)
    extra: Column = Column(JSON_TYPE, nullable=True)
    created_at: Column = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    child: Mapped["ChildModel"] = relationship(
        "ChildModel", backref="parental_consents"
    )

    __table_args__ = (
        UniqueConstraint("parent_email", "child_id", name="uq_parent_child_consent"),
        Index("idx_consent_child", "child_id"),
        Index("idx_consent_email", "parent_email"),
        Index("idx_consent_timestamp", "consent_timestamp"),
    )


class UserModel(Base):
    """Production user model with full referential integrity"""

    __tablename__ = "users"

    # Primary key with proper UUID type
    id: Column = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # User authentication and profile
    email: Column = Column(String(255), unique=True, nullable=False, index=True)
    password_hash: Column = Column(String(255), nullable=False)
    role: Column = Column(String(50), nullable=False, default="parent")

    # User details
    first_name: Column = Column(String(100), nullable=True)
    last_name: Column = Column(String(100), nullable=True)
    phone_number: Column = Column(String(20), nullable=True)

    # Account status and security
    is_active: Column = Column(Boolean, default=True, nullable=False)
    email_verified: Column = Column(Boolean, default=False, nullable=False)
    phone_verified: Column = Column(Boolean, default=False, nullable=False)

    # Security tracking
    failed_login_attempts: Column = Column(Integer, default=0, nullable=False)
    account_locked_until: Column = Column(DateTime, nullable=True)
    last_password_change: Column = Column(DateTime, default=datetime.utcnow)

    # Timestamps
    created_at: Column = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Column = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login: Column = Column(DateTime, nullable=True)

    # COPPA compliance fields
    date_of_birth: Column = Column(DateTime, nullable=True)
    parental_consent_given: Column = Column(Boolean, default=False, nullable=False)
    parental_consent_date: Column = Column(DateTime, nullable=True)

    # Preferences stored as JSON for performance
    preferences: Column = Column(JSON_TYPE, nullable=False, default=dict)
    data_retention_preference: Column = Column(JSON_TYPE, nullable=True)

    # Relationships with cascade delete
    children: Mapped[List["ChildModel"]] = relationship(
        "ChildModel", back_populates="parent", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "failed_login_attempts >= 0", name="check_failed_login_attempts"
        ),
        CheckConstraint(
            "role IN ('parent', 'admin', 'support')", name="check_user_role"
        ),
        Index("idx_user_email", "email"),
        Index("idx_user_role", "role"),
        Index("idx_user_active", "is_active"),
        Index("idx_user_created", "created_at"),
    )


class ChildModel(Base):
    """Production child model with age validation and safety features"""

    __tablename__ = "children"

    # Primary key with proper UUID type
    id: Column = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to users with CASCADE delete
    parent_id: Column = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Child profile
    name: Column = Column(String(100), nullable=False)
    age: Column = Column(Integer, nullable=False)

    # Safety and preferences stored as JSON
    safety_settings: Column = Column(JSON_TYPE, nullable=False, default=dict)
    preferences: Column = Column(JSON_TYPE, nullable=False, default=dict)

    # COPPA compliance
    data_collection_consent: Column = Column(Boolean, default=False, nullable=False)
    data_retention_days: Column = Column(Integer, default=365, nullable=False)

    # Timestamps
    created_at: Column = Column(DateTime, default=func.now(), nullable=False)
    updated_at: Column = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    parent: Mapped["UserModel"] = relationship("UserModel", back_populates="children")
    conversations: Mapped[List["ConversationModel"]] = relationship(
        "ConversationModel", back_populates="child", cascade="all, delete-orphan"
    )
    messages: Mapped[List["MessageModel"]] = relationship(
        "MessageModel", back_populates="child", cascade="all, delete-orphan"
    )

    # Constraints for COPPA compliance
    __table_args__ = (
        CheckConstraint("age >= 0 AND age <= 18", name="check_child_age_coppa"),
        CheckConstraint(
            "data_retention_days > 0", name="check_data_retention_positive"
        ),
        Index("idx_child_parent", "parent_id"),
        Index("idx_child_age", "age"),
        Index("idx_child_created", "created_at"),
        Index("idx_child_name", "name"),
    )


class ConversationModel(Base):
    """Production conversation model with performance indexes"""

    __tablename__ = "conversations"

    # Primary key with proper UUID type
    id: Column = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to children with CASCADE delete
    child_id: Column = Column(
        String,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Conversation metadata
    title: Column = Column(String(200), default="Chat Session", nullable=False)
    session_id: Column = Column(
        String, default=lambda: str(uuid.uuid4()), nullable=False
    )

    # Conversation analysis stored as JSONB
    summary: Column = Column(Text, default="", nullable=False)
    emotion_analysis: Column = Column(String(50), default="neutral", nullable=False)
    sentiment_score: Column = Column(Float, default=0.0, nullable=False)
    safety_score: Column = Column(Float, default=1.0, nullable=False)
    engagement_level: Column = Column(String(20), default="medium", nullable=False)

    # Counters
    message_count: Column = Column(Integer, default=0, nullable=False)

    # Session timing
    start_time: Column = Column(DateTime, default=func.now(), nullable=False)
    end_time: Column = Column(DateTime, nullable=True)

    # Timestamps
    created_at: Column = Column(DateTime, default=func.now(), nullable=False)
    updated_at: Column = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Metadata stored as JSON for performance
    conversation_metadata: Column = Column(JSON_TYPE, nullable=False, default=dict)

    # Relationships
    child: Mapped["ChildModel"] = relationship(
        "ChildModel", back_populates="conversations"
    )
    messages: Mapped[List["MessageModel"]] = relationship(
        "MessageModel", back_populates="conversation", cascade="all, delete-orphan"
    )

    # Constraints and indexes for performance
    __table_args__ = (
        CheckConstraint(
            "sentiment_score >= -1.0 AND sentiment_score <= 1.0",
            name="check_sentiment_range",
        ),
        CheckConstraint(
            "safety_score >= 0.0 AND safety_score <= 1.0",
            name="check_safety_score_range",
        ),
        CheckConstraint("message_count >= 0", name="check_message_count_positive"),
        CheckConstraint(
            "engagement_level IN ('low', 'medium', 'high')",
            name="check_engagement_level",
        ),
        Index("idx_conv_child", "child_id"),
        Index("idx_conv_session", "session_id"),
        Index("idx_conv_created", "created_at"),
        Index("idx_conv_updated", "updated_at"),
        Index("idx_conv_safety", "safety_score"),
        Index("idx_conv_child_created", "child_id", "created_at"),  # Composite index
    )


class MessageModel(Base):
    """Production message model with encryption and safety tracking"""

    __tablename__ = "messages"

    # Primary key with proper UUID type
    id: Column = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign keys with CASCADE delete
    conversation_id: Column = Column(
        String,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    child_id: Column = Column(
        String,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Message content and metadata
    content: Column = Column(
        Text, nullable=False
    )  # Will be encrypted at application level
    role: Column = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content_type: Column = Column(String(20), default="text", nullable=False)

    # Sequence for proper ordering
    sequence_number: Column = Column(Integer, nullable=False, default=0)

    # Safety and analysis
    safety_checked: Column = Column(Boolean, default=True, nullable=False)
    safety_score: Column = Column(Float, default=1.0, nullable=False)
    emotion: Column = Column(String(50), default="neutral", nullable=False)
    sentiment: Column = Column(Float, default=0.0, nullable=False)

    # Timestamps
    created_at: Column = Column(DateTime, default=func.now(), nullable=False)
    timestamp: Column = Column(
        DateTime, default=func.now(), nullable=False
    )  # Message timestamp

    # Message metadata as JSON
    message_metadata: Column = Column(JSON_TYPE, nullable=False, default=dict)

    # Relationships
    conversation: Mapped["ConversationModel"] = relationship(
        "ConversationModel", back_populates="messages"
    )
    child: Mapped["ChildModel"] = relationship("ChildModel", back_populates="messages")

    # Constraints and indexes for performance
    __table_args__ = (
        CheckConstraint(
            "safety_score >= 0.0 AND safety_score <= 1.0", name="check_msg_safety_score"
        ),
        CheckConstraint(
            "sentiment >= -1.0 AND sentiment <= 1.0", name="check_msg_sentiment_range"
        ),
        CheckConstraint("sequence_number >= 0", name="check_sequence_positive"),
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')", name="check_message_role"
        ),
        CheckConstraint(
            "content_type IN ('text', 'audio', 'image')", name="check_content_type"
        ),
        UniqueConstraint(
            "conversation_id", "sequence_number", name="uq_conversation_sequence"
        ),
        Index("idx_msg_conversation", "conversation_id"),
        Index("idx_msg_child", "child_id"),
        Index("idx_msg_created", "created_at"),
        Index("idx_msg_safety", "safety_score"),
        Index("idx_msg_role", "role"),
        Index(
            "idx_msg_conv_seq", "conversation_id", "sequence_number"
        ),  # Composite for ordering
        Index(
            "idx_msg_child_created", "child_id", "created_at"
        ),  # Composite for recent messages
    )


# Additional production tables for comprehensive system


class SessionModel(Base):
    """Production session tracking with security features"""

    __tablename__ = "sessions"

    id: Column = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    child_id: Column = Column(
        String,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Session state and metadata
    status: Column = Column(String(20), default="active", nullable=False)
    interaction_count: Column = Column(Integer, default=0, nullable=False)
    session_data: Column = Column(JSON_TYPE, nullable=False, default=dict)

    # Session timing
    created_at: Column = Column(DateTime, default=func.now(), nullable=False)
    last_activity: Column = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
    ended_at: Column = Column(DateTime, nullable=True)
    end_reason: Column = Column(Text, nullable=True)

    # Relationships
    child: Mapped["ChildModel"] = relationship("ChildModel", backref="sessions")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'expired', 'terminated')",
            name="check_session_status",
        ),
        CheckConstraint("interaction_count >= 0", name="check_interaction_count"),
        Index("idx_session_child", "child_id"),
        Index("idx_session_status", "status"),
        Index("idx_session_activity", "last_activity"),
    )


class AuditLogModel(Base):
    """Production audit trail for compliance and security"""

    __tablename__ = "audit_logs"

    id: Column = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Audit metadata
    table_name: Column = Column(String(50), nullable=False)
    record_id: Column = Column(String, nullable=False)
    action: Column = Column(String(20), nullable=False)  # INSERT, UPDATE, DELETE

    # User context
    user_id: Column = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Change tracking
    old_values: Column = Column(JSON_TYPE, nullable=True)
    new_values: Column = Column(JSON_TYPE, nullable=True)

    # Request context
    ip_address: Column = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent: Column = Column(Text, nullable=True)

    # Timestamp
    created_at: Column = Column(DateTime, default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "action IN ('INSERT', 'UPDATE', 'DELETE')", name="check_audit_action"
        ),
        Index("idx_audit_table_record", "table_name", "record_id"),
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_created", "created_at"),
    )
