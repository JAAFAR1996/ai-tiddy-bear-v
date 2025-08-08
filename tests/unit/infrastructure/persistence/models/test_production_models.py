"""
Unit tests for Production Database Models
Tests SQLAlchemy models with multi-database support and COPPA compliance
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from src.infrastructure.persistence.models.production_models import (
    Base,
    ConsentModel,
    UserModel,
    ChildModel,
    ConversationModel
)


class TestProductionModels:
    """Test production database models."""

    @pytest.fixture
    def engine(self):
        """Create in-memory SQLite engine for testing."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def session(self, engine):
        """Create database session for testing."""
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    @pytest.fixture
    def sample_user(self, session):
        """Create sample user for testing."""
        user = UserModel(
            email="test@example.com",
            password_hash="hashed_password",
            role="parent",
            first_name="John",
            last_name="Doe",
            is_active=True,
            email_verified=True
        )
        session.add(user)
        session.commit()
        return user

    @pytest.fixture
    def sample_child(self, session, sample_user):
        """Create sample child for testing."""
        child = ChildModel(
            parent_id=sample_user.id,
            name="Alice",
            age=8,
            safety_settings={"content_filter": "strict"},
            preferences={"theme": "colorful"},
            data_collection_consent=True
        )
        session.add(child)
        session.commit()
        return child


class TestConsentModel:
    """Test ConsentModel functionality."""

    def test_consent_model_creation(self, session, sample_child):
        """Test consent model creation."""
        consent = ConsentModel(
            parent_email="parent@example.com",
            child_id=sample_child.id,
            ip_address="192.168.1.1",
            extra={"browser": "Chrome", "version": "90.0"}
        )
        
        session.add(consent)
        session.commit()
        
        assert consent.id is not None
        assert consent.parent_email == "parent@example.com"
        assert consent.child_id == sample_child.id
        assert consent.consent_timestamp is not None
        assert consent.created_at is not None

    def test_consent_model_relationships(self, session, sample_child):
        """Test consent model relationships."""
        consent = ConsentModel(
            parent_email="parent@example.com",
            child_id=sample_child.id
        )
        
        session.add(consent)
        session.commit()
        
        # Test relationship to child
        assert consent.child == sample_child

    def test_consent_model_json_extra_field(self, session, sample_child):
        """Test JSON extra field functionality."""
        extra_data = {
            "browser": "Firefox",
            "os": "Windows 10",
            "consent_method": "digital_signature"
        }
        
        consent = ConsentModel(
            parent_email="parent@example.com",
            child_id=sample_child.id,
            extra=extra_data
        )
        
        session.add(consent)
        session.commit()
        
        # Retrieve and verify JSON data
        retrieved_consent = session.query(ConsentModel).filter_by(id=consent.id).first()
        assert retrieved_consent.extra == extra_data


class TestUserModel:
    """Test UserModel functionality."""

    def test_user_model_creation(self, session):
        """Test user model creation with required fields."""
        user = UserModel(
            email="test@example.com",
            password_hash="hashed_password",
            role="parent"
        )
        
        session.add(user)
        session.commit()
        
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.role == "parent"
        assert user.is_active is True
        assert user.email_verified is False
        assert user.failed_login_attempts == 0
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_user_model_full_profile(self, session):
        """Test user model with full profile information."""
        user = UserModel(
            email="john.doe@example.com",
            password_hash="secure_hash",
            role="parent",
            first_name="John",
            last_name="Doe",
            phone_number="+1234567890",
            date_of_birth=datetime(1985, 5, 15),
            parental_consent_given=True,
            parental_consent_date=datetime.now()
        )
        
        session.add(user)
        session.commit()
        
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.phone_number == "+1234567890"
        assert user.parental_consent_given is True

    def test_user_model_preferences_json(self, session):
        """Test user preferences JSON field."""
        preferences = {
            "language": "en",
            "notifications": {
                "email": True,
                "push": False
            },
            "privacy": {
                "data_sharing": False,
                "analytics": True
            }
        }
        
        user = UserModel(
            email="test@example.com",
            password_hash="hashed_password",
            role="parent",
            preferences=preferences
        )
        
        session.add(user)
        session.commit()
        
        retrieved_user = session.query(UserModel).filter_by(id=user.id).first()
        assert retrieved_user.preferences == preferences

    def test_user_model_security_fields(self, session):
        """Test user security-related fields."""
        user = UserModel(
            email="test@example.com",
            password_hash="hashed_password",
            role="parent",
            failed_login_attempts=3,
            account_locked_until=datetime.now() + timedelta(hours=1),
            last_password_change=datetime.now() - timedelta(days=30)
        )
        
        session.add(user)
        session.commit()
        
        assert user.failed_login_attempts == 3
        assert user.account_locked_until is not None
        assert user.last_password_change is not None

    def test_user_model_email_uniqueness(self, session):
        """Test email uniqueness constraint."""
        # Create first user
        user1 = UserModel(
            email="test@example.com",
            password_hash="hash1",
            role="parent"
        )
        session.add(user1)
        session.commit()
        
        # Try to create user with same email
        user2 = UserModel(
            email="test@example.com",
            password_hash="hash2",
            role="parent"
        )
        session.add(user2)
        
        with pytest.raises(IntegrityError):
            session.commit()

    def test_user_model_children_relationship(self, session, sample_user):
        """Test user-children relationship."""
        child1 = ChildModel(
            parent_id=sample_user.id,
            name="Alice",
            age=8
        )
        child2 = ChildModel(
            parent_id=sample_user.id,
            name="Bob",
            age=10
        )
        
        session.add_all([child1, child2])
        session.commit()
        
        assert len(sample_user.children) == 2
        assert child1 in sample_user.children
        assert child2 in sample_user.children


class TestChildModel:
    """Test ChildModel functionality."""

    def test_child_model_creation(self, session, sample_user):
        """Test child model creation."""
        child = ChildModel(
            parent_id=sample_user.id,
            name="Alice",
            age=8
        )
        
        session.add(child)
        session.commit()
        
        assert child.id is not None
        assert child.parent_id == sample_user.id
        assert child.name == "Alice"
        assert child.age == 8
        assert child.data_collection_consent is False
        assert child.data_retention_days == 365
        assert child.created_at is not None

    def test_child_model_safety_settings(self, session, sample_user):
        """Test child safety settings JSON field."""
        safety_settings = {
            "content_filter": "strict",
            "time_limits": {
                "daily_minutes": 60,
                "bedtime": "20:00"
            },
            "blocked_words": ["inappropriate", "dangerous"],
            "allowed_contacts": ["parent", "teacher"]
        }
        
        child = ChildModel(
            parent_id=sample_user.id,
            name="Alice",
            age=8,
            safety_settings=safety_settings
        )
        
        session.add(child)
        session.commit()
        
        retrieved_child = session.query(ChildModel).filter_by(id=child.id).first()
        assert retrieved_child.safety_settings == safety_settings

    def test_child_model_preferences(self, session, sample_user):
        """Test child preferences JSON field."""
        preferences = {
            "theme": "colorful",
            "avatar": "teddy_bear",
            "favorite_activities": ["stories", "games", "music"],
            "difficulty_level": "beginner"
        }
        
        child = ChildModel(
            parent_id=sample_user.id,
            name="Bob",
            age=10,
            preferences=preferences
        )
        
        session.add(child)
        session.commit()
        
        retrieved_child = session.query(ChildModel).filter_by(id=child.id).first()
        assert retrieved_child.preferences == preferences

    def test_child_model_parent_relationship(self, session, sample_user):
        """Test child-parent relationship."""
        child = ChildModel(
            parent_id=sample_user.id,
            name="Alice",
            age=8
        )
        
        session.add(child)
        session.commit()
        
        assert child.parent == sample_user
        assert child in sample_user.children

    def test_child_model_data_retention(self, session, sample_user):
        """Test data retention settings."""
        child = ChildModel(
            parent_id=sample_user.id,
            name="Alice",
            age=8,
            data_collection_consent=True,
            data_retention_days=180
        )
        
        session.add(child)
        session.commit()
        
        assert child.data_collection_consent is True
        assert child.data_retention_days == 180


class TestConversationModel:
    """Test ConversationModel functionality."""

    def test_conversation_model_creation(self, session, sample_child):
        """Test conversation model creation."""
        conversation = ConversationModel(
            child_id=sample_child.id,
            title="Morning Chat",
            summary="A friendly morning conversation",
            emotion_analysis="happy",
            sentiment_score=0.8,
            safety_score=1.0
        )
        
        session.add(conversation)
        session.commit()
        
        assert conversation.id is not None
        assert conversation.child_id == sample_child.id
        assert conversation.title == "Morning Chat"
        assert conversation.emotion_analysis == "happy"
        assert conversation.sentiment_score == 0.8
        assert conversation.safety_score == 1.0
        assert conversation.message_count == 0
        assert conversation.start_time is not None

    def test_conversation_model_child_relationship(self, session, sample_child):
        """Test conversation-child relationship."""
        conversation = ConversationModel(
            child_id=sample_child.id,
            title="Test Chat"
        )
        
        session.add(conversation)
        session.commit()
        
        assert conversation.child == sample_child
        assert conversation in sample_child.conversations

    def test_conversation_model_session_tracking(self, session, sample_child):
        """Test conversation session tracking."""
        conversation = ConversationModel(
            child_id=sample_child.id,
            title="Session Test",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(minutes=30)
        )
        
        session.add(conversation)
        session.commit()
        
        assert conversation.start_time is not None
        assert conversation.end_time is not None
        assert conversation.end_time > conversation.start_time

    def test_conversation_model_safety_metrics(self, session, sample_child):
        """Test conversation safety metrics."""
        conversation = ConversationModel(
            child_id=sample_child.id,
            title="Safety Test",
            emotion_analysis="neutral",
            sentiment_score=0.5,
            safety_score=0.9,
            engagement_level="medium"
        )
        
        session.add(conversation)
        session.commit()
        
        assert conversation.emotion_analysis == "neutral"
        assert conversation.sentiment_score == 0.5
        assert conversation.safety_score == 0.9
        assert conversation.engagement_level == "medium"


class TestModelIndexes:
    """Test database indexes for performance."""

    def test_user_email_index(self, session):
        """Test user email index exists."""
        users = []
        for i in range(10):
            user = UserModel(
                email=f"user{i}@example.com",
                password_hash="hash",
                role="parent"
            )
            users.append(user)
        
        session.add_all(users)
        session.commit()
        
        # Query by email should work efficiently
        found_user = session.query(UserModel).filter_by(email="user5@example.com").first()
        assert found_user is not None
        assert found_user.email == "user5@example.com"

    def test_child_parent_index(self, session, sample_user):
        """Test child parent_id index."""
        children = []
        for i in range(5):
            child = ChildModel(
                parent_id=sample_user.id,
                name=f"Child{i}",
                age=8 + i
            )
            children.append(child)
        
        session.add_all(children)
        session.commit()
        
        # Query by parent_id should work efficiently
        found_children = session.query(ChildModel).filter_by(parent_id=sample_user.id).all()
        assert len(found_children) == 5

    def test_conversation_child_index(self, session, sample_child):
        """Test conversation child_id index."""
        conversations = []
        for i in range(3):
            conv = ConversationModel(
                child_id=sample_child.id,
                title=f"Chat {i}"
            )
            conversations.append(conv)
        
        session.add_all(conversations)
        session.commit()
        
        # Query by child_id should work efficiently
        found_convs = session.query(ConversationModel).filter_by(child_id=sample_child.id).all()
        assert len(found_convs) == 3


class TestModelTimestamps:
    """Test automatic timestamp handling."""

    def test_user_timestamps(self, session):
        """Test user creation and update timestamps."""
        user = UserModel(
            email="test@example.com",
            password_hash="hash",
            role="parent"
        )
        
        session.add(user)
        session.commit()
        
        created_at = user.created_at
        updated_at = user.updated_at
        
        assert created_at is not None
        assert updated_at is not None

    def test_child_timestamps(self, session, sample_user):
        """Test child creation and update timestamps."""
        child = ChildModel(
            parent_id=sample_user.id,
            name="Alice",
            age=8
        )
        
        session.add(child)
        session.commit()
        
        created_at = child.created_at
        updated_at = child.updated_at
        
        assert created_at is not None
        assert updated_at is not None

    def test_conversation_timestamps(self, session, sample_child):
        """Test conversation timestamps."""
        conversation = ConversationModel(
            child_id=sample_child.id,
            title="Test Chat"
        )
        
        session.add(conversation)
        session.commit()
        
        assert conversation.created_at is not None
        assert conversation.updated_at is not None
        assert conversation.start_time is not None