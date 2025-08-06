"""
Unit tests for core entities with 100% coverage.
Tests domain models including Child, ChildProfile, Message, Conversation, User, and related value objects.
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
import json
import time
from unittest.mock import patch

from src.core.entities import (
    Child, ChildProfile, Message, Conversation, User, SafetyResult, AIResponse
)
from src.core.events import ChildRegistered, ChildProfileUpdated


class TestChildEntity:
    """Test suite for Child entity."""

    def test_create_valid_child(self):
        """Test creating a valid child entity."""
        child = Child(
            name="Alice",
            age=8,
            preferences={"favorite_color": "purple"},
            safety_level="strict"
        )
        
        assert child.name == "Alice"
        assert child.age == 8
        assert child.preferences["favorite_color"] == "purple"
        assert child.safety_level == "strict"
        assert child.id is not None
        assert isinstance(child.created_at, datetime)

    def test_child_age_validation_too_young(self):
        """Test that children under 3 are rejected (COPPA compliance)."""
        with pytest.raises(ValidationError) as exc_info:
            Child(name="Baby", age=2)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("age",) for error in errors)

    def test_child_age_validation_too_old(self):
        """Test that children over 13 are rejected (COPPA compliance)."""
        with pytest.raises(ValidationError) as exc_info:
            Child(name="Teen", age=14)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("age",) for error in errors)

    def test_child_name_validation_empty(self):
        """Test that empty names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Child(name="", age=8)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_child_name_validation_too_long(self):
        """Test that names over 50 characters are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Child(name="A" * 51, age=8)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    @pytest.mark.parametrize("age", [3, 5, 8, 10, 13])
    def test_valid_age_range(self, age):
        """Test all valid ages within COPPA range."""
        child = Child(name="Test", age=age)
        assert child.age == age

    def test_json_serialization(self):
        """Test JSON serialization of Child entity."""
        child = Child(name="Bob", age=7)
        json_data = child.model_dump_json()
        
        assert "Bob" in json_data
        assert "7" in json_data
        assert child.id in json_data
    
    def test_child_default_values(self):
        """Test default values for Child entity."""
        child = Child(name="Test", age=5)
        assert child.preferences == {}
        assert child.safety_level == "strict"
        assert child.id is not None
    
    def test_child_with_custom_preferences(self):
        """Test Child with custom preferences."""
        prefs = {"favorite_color": "blue", "interests": ["reading", "games"]}
        child = Child(name="Test", age=7, preferences=prefs)
        assert child.preferences == prefs
    
    def test_child_with_custom_safety_level(self):
        """Test Child with custom safety level."""
        child = Child(name="Test", age=10, safety_level="moderate")
        assert child.safety_level == "moderate"
    
    def test_child_datetime_json_encoding(self):
        """Test datetime encoding in JSON."""
        child = Child(name="Test", age=8)
        json_str = child.model_dump_json()
        data = json.loads(json_str)
        
        # Check that created_at is properly encoded
        assert "created_at" in data
        # Should be able to parse it back as datetime
        datetime.fromisoformat(data["created_at"])
    
    def test_child_model_dump(self):
        """Test model_dump method."""
        child = Child(name="Alice", age=9, preferences={"pet": "cat"})
        data = child.model_dump()
        
        assert data["name"] == "Alice"
        assert data["age"] == 9
        assert data["preferences"] == {"pet": "cat"}
        assert "id" in data
        assert "created_at" in data
        assert "safety_level" in data


class TestChildProfileEntity:
    """Test suite for ChildProfile entity with event sourcing."""

    def test_create_child_profile_factory(self):
        """Test creating child profile using factory method."""
        profile = ChildProfile.create(
            name="Emma",
            age=9,
            preferences={"interests": ["art", "music"]}
        )
        
        assert profile.name == "Emma"
        assert profile.age == 9
        assert profile.preferences["interests"] == ["art", "music"]
        assert profile.id is not None
        assert profile.created_at == profile.updated_at
        
        # Check event was created
        events = profile.get_uncommitted_events()
        assert len(events) == 1
        assert isinstance(events[0], ChildRegistered)
        assert events[0].child_id == profile.id
        assert events[0].age == 9

    def test_update_profile_name(self):
        """Test updating child profile name generates event."""
        profile = ChildProfile.create(name="John", age=6, preferences={})
        profile.get_uncommitted_events()  # Clear creation event
        
        profile.update_profile(name="Johnny", updated_by="parent-123")
        
        assert profile.name == "Johnny"
        assert profile.updated_at > profile.created_at
        
        events = profile.get_uncommitted_events()
        assert len(events) == 1
        assert isinstance(events[0], ChildProfileUpdated)
        assert events[0].updated_fields == ["name"]
        assert events[0].previous_values["name"] == "John"
        assert events[0].updated_by == "parent-123"

    def test_update_profile_multiple_fields(self):
        """Test updating multiple fields at once."""
        profile = ChildProfile.create(
            name="Sarah", 
            age=7, 
            preferences={"color": "red"}
        )
        profile.get_uncommitted_events()  # Clear
        
        profile.update_profile(
            name="Sara",
            age=8,
            preferences={"color": "blue", "animal": "cat"}
        )
        
        assert profile.name == "Sara"
        assert profile.age == 8
        assert profile.preferences == {"color": "blue", "animal": "cat"}
        
        events = profile.get_uncommitted_events()
        assert len(events) == 1
        event = events[0]
        assert set(event.updated_fields) == {"name", "age", "preferences"}
        assert event.previous_values["name"] == "Sarah"
        assert event.previous_values["age"] == 7
        assert event.previous_values["preferences"] == {"color": "red"}

    def test_no_update_when_values_unchanged(self):
        """Test no event generated when values don't change."""
        profile = ChildProfile(name="Test", age=10, preferences={})
        profile.get_uncommitted_events()  # Clear
        
        profile.update_profile(name="Test", age=10)
        
        events = profile.get_uncommitted_events()
        assert len(events) == 0

    def test_events_cleared_after_retrieval(self):
        """Test events are cleared after get_uncommitted_events."""
        profile = ChildProfile.create(name="Test", age=5, preferences={})
        
        events1 = profile.get_uncommitted_events()
        assert len(events1) == 1
        
        events2 = profile.get_uncommitted_events()
        assert len(events2) == 0
    
    def test_child_profile_direct_instantiation(self):
        """Test creating ChildProfile directly without factory."""
        profile = ChildProfile(name="Direct", age=11)
        assert profile.name == "Direct"
        assert profile.age == 11
        assert profile.preferences == {}
        assert profile.id is not None
        assert isinstance(profile.created_at, datetime)
        assert isinstance(profile.updated_at, datetime)
        assert profile._events == []
    
    def test_child_profile_validation_errors(self):
        """Test ChildProfile validation errors."""
        # Test age too young
        with pytest.raises(ValidationError) as exc_info:
            ChildProfile(name="Young", age=2)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("age",) for error in errors)
        
        # Test age too old
        with pytest.raises(ValidationError) as exc_info:
            ChildProfile(name="Old", age=14)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("age",) for error in errors)
        
        # Test empty name
        with pytest.raises(ValidationError) as exc_info:
            ChildProfile(name="", age=7)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)
        
        # Test name too long
        with pytest.raises(ValidationError) as exc_info:
            ChildProfile(name="A" * 51, age=7)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)
    
    def test_child_profile_update_with_none_values(self):
        """Test update_profile ignores None values."""
        profile = ChildProfile(name="Original", age=8, preferences={"key": "value"})
        original_updated_at = profile.updated_at
        
        # Small delay to ensure timestamp difference
        time.sleep(0.01)
        
        profile.update_profile(name=None, age=None, preferences=None)
        
        # Nothing should change except updated_at
        assert profile.name == "Original"
        assert profile.age == 8
        assert profile.preferences == {"key": "value"}
        assert profile.updated_at > original_updated_at
        
        # No events should be generated
        events = profile.get_uncommitted_events()
        assert len(events) == 0
    
    def test_child_profile_update_partial(self):
        """Test partial updates to profile."""
        profile = ChildProfile(name="Start", age=6, preferences={"a": 1})
        profile.get_uncommitted_events()  # Clear any initial events
        
        # Update only name
        profile.update_profile(name="End")
        events = profile.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].updated_fields == ["name"]
        
        # Update only age
        profile.update_profile(age=7)
        events = profile.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].updated_fields == ["age"]
        
        # Update only preferences
        profile.update_profile(preferences={"b": 2})
        events = profile.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].updated_fields == ["preferences"]
    
    def test_child_profile_create_with_empty_preferences(self):
        """Test create method with None preferences."""
        profile = ChildProfile.create(name="NoPref", age=9, preferences=None)
        assert profile.preferences == {}
        
        events = profile.get_uncommitted_events()
        assert len(events) == 1
        assert isinstance(events[0], ChildRegistered)
    
    def test_child_profile_json_serialization(self):
        """Test JSON serialization of ChildProfile."""
        profile = ChildProfile(
            name="JSON Test",
            age=10,
            preferences={"hobby": "coding"},
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 0, 0)
        )
        
        data = profile.model_dump()
        assert data["name"] == "JSON Test"
        assert data["age"] == 10
        assert data["preferences"] == {"hobby": "coding"}
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Test JSON string serialization
        json_str = profile.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "JSON Test"


class TestMessageEntity:
    """Test suite for Message entity."""

    def test_create_valid_message(self):
        """Test creating a valid message."""
        msg = Message(
            content="Hello AI friend!",
            role="user",
            child_id="child-123",
            safety_checked=True,
            safety_score=0.95
        )
        
        assert msg.content == "Hello AI friend!"
        assert msg.role == "user"
        assert msg.child_id == "child-123"
        assert msg.safety_checked is True
        assert msg.safety_score == 0.95
        assert msg.id is not None
        assert isinstance(msg.timestamp, datetime)

    def test_message_role_validation(self):
        """Test message role must be valid."""
        with pytest.raises(ValidationError):
            Message(
                content="Test",
                role="invalid_role",
                child_id="child-123"
            )

    @pytest.mark.parametrize("role", ["user", "assistant", "system"])
    def test_valid_message_roles(self, role):
        """Test all valid message roles."""
        msg = Message(content="Test", role=role, child_id="child-123")
        assert msg.role == role

    def test_message_content_validation_empty(self):
        """Test empty message content is rejected."""
        with pytest.raises(ValidationError):
            Message(content="", role="user", child_id="child-123")

    def test_message_content_validation_too_long(self):
        """Test message content over 1000 chars is rejected."""
        with pytest.raises(ValidationError):
            Message(
                content="A" * 1001,
                role="user",
                child_id="child-123"
            )

    def test_safety_score_validation(self):
        """Test safety score must be between 0 and 1."""
        with pytest.raises(ValidationError):
            Message(
                content="Test",
                role="user",
                child_id="child-123",
                safety_score=1.5
            )
        
        with pytest.raises(ValidationError):
            Message(
                content="Test",
                role="user",
                child_id="child-123",
                safety_score=-0.1
            )
    
    def test_message_defaults(self):
        """Test Message default values."""
        msg = Message(content="Test", role="user", child_id="123")
        assert msg.safety_checked is False
        assert msg.safety_score == 1.0
    
    def test_message_json_encoding(self):
        """Test Message JSON encoding with datetime."""
        msg = Message(
            content="Test message",
            role="assistant",
            child_id="child-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        json_str = msg.model_dump_json()
        data = json.loads(json_str)
        
        assert data["content"] == "Test message"
        assert data["timestamp"] == "2024-01-01T12:00:00"
        
        # Can parse back
        datetime.fromisoformat(data["timestamp"])


class TestConversationEntity:
    """Test suite for Conversation entity."""

    def test_create_conversation(self):
        """Test creating a new conversation."""
        conv = Conversation(
            child_id="child-456",
            context={"topic": "dinosaurs"}
        )
        
        assert conv.child_id == "child-456"
        assert conv.status == "active"
        assert conv.context["topic"] == "dinosaurs"
        assert conv.id is not None
        assert conv.started_at == conv.last_activity

    def test_add_message_to_conversation(self):
        """Test adding messages updates conversation."""
        conv = Conversation(child_id="child-789")
        initial_activity = conv.last_activity
        
        # Add a small delay to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        msg = Message(
            content="Tell me a story",
            role="user",
            child_id="child-789"
        )
        conv.add_message(msg)
        
        assert conv.last_activity > initial_activity
        messages = conv.get_recent_messages()
        assert len(messages) == 1
        assert messages[0] == msg

    def test_get_recent_messages_limit(self):
        """Test getting recent messages respects limit."""
        conv = Conversation(child_id="child-999")
        
        # Add 15 messages
        for i in range(15):
            msg = Message(
                content=f"Message {i}",
                role="user" if i % 2 == 0 else "assistant",
                child_id="child-999"
            )
            conv.add_message(msg)
        
        # Get last 10
        recent = conv.get_recent_messages(limit=10)
        assert len(recent) == 10
        assert recent[0].content == "Message 5"
        assert recent[-1].content == "Message 14"

    def test_get_recent_messages_empty(self):
        """Test getting messages from empty conversation."""
        conv = Conversation(child_id="child-empty")
        messages = conv.get_recent_messages()
        assert messages == []
    
    def test_conversation_defaults(self):
        """Test Conversation default values."""
        conv = Conversation(child_id="test-child")
        assert conv.status == "active"
        assert conv.context == {}
        assert conv.id is not None
    
    def test_conversation_with_custom_values(self):
        """Test Conversation with custom values."""
        context = {"theme": "space", "difficulty": "easy"}
        conv = Conversation(
            child_id="child-123",
            status="paused",
            context=context
        )
        assert conv.status == "paused"
        assert conv.context == context
    
    def test_conversation_json_encoding(self):
        """Test Conversation JSON encoding."""
        conv = Conversation(
            child_id="child-json",
            started_at=datetime(2024, 1, 1, 10, 0, 0),
            last_activity=datetime(2024, 1, 1, 11, 0, 0)
        )
        
        json_str = conv.model_dump_json()
        data = json.loads(json_str)
        
        assert data["started_at"] == "2024-01-01T10:00:00"
        assert data["last_activity"] == "2024-01-01T11:00:00"
    
    def test_conversation_messages_not_in_dump(self):
        """Test that private _messages field is not in model dump."""
        conv = Conversation(child_id="test")
        msg = Message(content="Test", role="user", child_id="test")
        conv.add_message(msg)
        
        data = conv.model_dump()
        assert "_messages" not in data
    
    def test_get_recent_messages_with_fewer_than_limit(self):
        """Test getting messages when fewer exist than limit."""
        conv = Conversation(child_id="child-few")
        
        # Add only 3 messages
        for i in range(3):
            msg = Message(
                content=f"Message {i}",
                role="user",
                child_id="child-few"
            )
            conv.add_message(msg)
        
        # Request 10 but should get only 3
        recent = conv.get_recent_messages(limit=10)
        assert len(recent) == 3


class TestUserEntity:
    """Test suite for User entity."""

    def test_create_valid_user(self):
        """Test creating a valid user."""
        user = User(
            email="parent@example.com",
            children=["child-1", "child-2"]
        )
        
        assert user.email == "parent@example.com"
        assert user.role == "parent"
        assert len(user.children) == 2
        assert user.is_active is True
        assert user.id is not None
        assert isinstance(user.created_at, datetime)

    def test_email_validation_invalid(self):
        """Test invalid email formats are rejected."""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user@.com",
            "user..name@example.com"
        ]
        
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                User(email=email)

    def test_email_validation_valid(self):
        """Test valid email formats are accepted."""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "user123@test-domain.org"
        ]
        
        for email in valid_emails:
            user = User(email=email)
            assert user.email == email
    
    def test_user_defaults(self):
        """Test User default values."""
        user = User(email="test@example.com")
        assert user.role == "parent"
        assert user.children == []
        assert user.is_active is True
        assert user.id is not None
    
    def test_user_with_custom_values(self):
        """Test User with custom values."""
        user = User(
            email="admin@example.com",
            role="admin",
            children=["child-1", "child-2", "child-3"],
            is_active=False
        )
        assert user.role == "admin"
        assert len(user.children) == 3
        assert user.is_active is False
    
    def test_user_json_encoding(self):
        """Test User JSON encoding."""
        user = User(
            email="user@test.com",
            created_at=datetime(2024, 1, 1, 9, 0, 0)
        )
        
        json_str = user.model_dump_json()
        data = json.loads(json_str)
        
        assert data["email"] == "user@test.com"
        assert data["created_at"] == "2024-01-01T09:00:00"


class TestSafetyResult:
    """Test suite for SafetyResult value object."""

    def test_create_safe_result(self):
        """Test creating a safe result."""
        result = SafetyResult(
            is_safe=True,
            safety_score=0.98,
            violations=[],
            age_appropriate=True
        )
        
        assert result.is_safe is True
        assert result.safety_score == 0.98
        assert result.violations == []
        assert result.filtered_content is None
        assert result.age_appropriate is True

    def test_create_unsafe_result(self):
        """Test creating an unsafe result with violations."""
        result = SafetyResult(
            is_safe=False,
            safety_score=0.2,
            violations=["violence", "inappropriate_language"],
            filtered_content="The [filtered] story about [filtered]...",
            age_appropriate=False
        )
        
        assert result.is_safe is False
        assert result.safety_score == 0.2
        assert len(result.violations) == 2
        assert "violence" in result.violations
        assert result.filtered_content is not None
        assert result.age_appropriate is False

    def test_safety_score_bounds(self):
        """Test safety score validation."""
        with pytest.raises(ValidationError):
            SafetyResult(safety_score=1.1)
        
        with pytest.raises(ValidationError):
            SafetyResult(safety_score=-0.1)
    
    def test_safety_result_defaults(self):
        """Test SafetyResult default values."""
        result = SafetyResult()
        assert result.is_safe is True
        assert result.safety_score == 1.0
        assert result.violations == []
        assert result.filtered_content is None
        assert result.age_appropriate is True
    
    def test_safety_result_json_serialization(self):
        """Test SafetyResult JSON serialization."""
        result = SafetyResult(
            is_safe=False,
            safety_score=0.3,
            violations=["test1", "test2"],
            filtered_content="filtered",
            age_appropriate=False
        )
        
        data = result.model_dump()
        assert data["is_safe"] is False
        assert data["safety_score"] == 0.3
        assert data["violations"] == ["test1", "test2"]
        assert data["filtered_content"] == "filtered"
        assert data["age_appropriate"] is False


class TestAIResponse:
    """Test suite for AIResponse value object."""

    def test_create_ai_response(self):
        """Test creating an AI response."""
        response = AIResponse(
            content="Once upon a time in a magical forest...",
            emotion="happy",
            safety_score=0.99,
            age_appropriate=True
        )
        
        assert response.content == "Once upon a time in a magical forest..."
        assert response.emotion == "happy"
        assert response.safety_score == 0.99
        assert response.age_appropriate is True
        assert isinstance(response.timestamp, datetime)

    def test_default_emotion(self):
        """Test default emotion is neutral."""
        response = AIResponse(content="Hello")
        assert response.emotion == "neutral"

    def test_json_encoding(self):
        """Test datetime is properly encoded in JSON."""
        response = AIResponse(content="Test")
        json_str = response.model_dump_json()
        
        # Should contain ISO format timestamp
        assert response.timestamp.isoformat() in json_str
    
    def test_ai_response_safety_score_bounds(self):
        """Test AIResponse safety score validation."""
        with pytest.raises(ValidationError):
            AIResponse(content="Test", safety_score=1.1)
        
        with pytest.raises(ValidationError):
            AIResponse(content="Test", safety_score=-0.1)
    
    def test_ai_response_all_fields(self):
        """Test AIResponse with all fields specified."""
        response = AIResponse(
            content="Full response",
            emotion="excited",
            safety_score=0.85,
            age_appropriate=False,
            timestamp=datetime(2024, 1, 1, 15, 30, 0)
        )
        
        assert response.content == "Full response"
        assert response.emotion == "excited"
        assert response.safety_score == 0.85
        assert response.age_appropriate is False
        assert response.timestamp == datetime(2024, 1, 1, 15, 30, 0)
    
    def test_ai_response_model_dump(self):
        """Test AIResponse model dump."""
        response = AIResponse(
            content="Test dump",
            emotion="sad",
            safety_score=0.7
        )
        
        data = response.model_dump()
        assert data["content"] == "Test dump"
        assert data["emotion"] == "sad"
        assert data["safety_score"] == 0.7
        assert data["age_appropriate"] is True
        assert "timestamp" in data


class TestEntityIntegration:
    """Integration tests for entity interactions."""
    
    def test_child_and_conversation_integration(self):
        """Test Child and Conversation entities work together."""
        child = Child(name="Integration Test", age=8)
        conv = Conversation(child_id=child.id)
        
        assert conv.child_id == child.id
        
        # Add messages
        msg1 = Message(
            content="Hello!",
            role="user",
            child_id=child.id
        )
        msg2 = Message(
            content="Hi there!",
            role="assistant",
            child_id=child.id
        )
        
        conv.add_message(msg1)
        conv.add_message(msg2)
        
        messages = conv.get_recent_messages()
        assert len(messages) == 2
        assert all(msg.child_id == child.id for msg in messages)
    
    def test_user_child_relationship(self):
        """Test User can have multiple children."""
        user = User(email="parent@test.com")
        
        # Create children
        child1 = Child(name="Child 1", age=6)
        child2 = Child(name="Child 2", age=9)
        
        # Update user's children list
        user.children = [child1.id, child2.id]
        
        assert len(user.children) == 2
        assert child1.id in user.children
        assert child2.id in user.children
    
    def test_message_safety_flow(self):
        """Test message safety checking flow."""
        msg = Message(
            content="Test message",
            role="user",
            child_id="test-child"
        )
        
        # Simulate safety check
        safety_result = SafetyResult(
            is_safe=True,
            safety_score=0.95,
            violations=[],
            age_appropriate=True
        )
        
        # Update message based on safety result
        msg.safety_checked = True
        msg.safety_score = safety_result.safety_score
        
        assert msg.safety_checked is True
        assert msg.safety_score == 0.95
    
    def test_ai_response_safety_integration(self):
        """Test AIResponse with safety checking."""
        # Generate AI response
        ai_response = AIResponse(
            content="Once upon a time...",
            emotion="happy"
        )
        
        # Check safety
        safety_result = SafetyResult(
            is_safe=True,
            safety_score=0.98,
            age_appropriate=True
        )
        
        # Update AI response based on safety
        ai_response.safety_score = safety_result.safety_score
        ai_response.age_appropriate = safety_result.age_appropriate
        
        assert ai_response.safety_score == 0.98
        assert ai_response.age_appropriate is True