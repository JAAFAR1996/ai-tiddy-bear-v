"""
Tests for core events module.
"""

import pytest
from datetime import datetime
from src.core.events import (
    ChildRegistered,
    ChildProfileUpdated,
    MessageCreated,
    MessageViolation,
    AuthEvent,
    SensitiveOperation,
    EventStore
)


def test_child_registered_valid():
    """Test valid child registration event."""
    event = ChildRegistered(
        child_id="child123",
        age=8,
        registered_at=datetime.now(),
        parent_id="parent123",
        consent_granted=True
    )
    assert event.child_id == "child123"
    assert event.age == 8
    assert event.consent_granted is True
    assert event.version == "1.0.0"


def test_child_registered_invalid_age():
    """Test child registration with invalid age (COPPA violation)."""
    with pytest.raises(ValueError, match="Child age must be between 3 and 13"):
        ChildRegistered(
            child_id="child123",
            age=2,  # Too young
            registered_at=datetime.now()
        )
    
    with pytest.raises(ValueError, match="Child age must be between 3 and 13"):
        ChildRegistered(
            child_id="child123",
            age=14,  # Too old
            registered_at=datetime.now()
        )


def test_child_profile_updated_valid():
    """Test valid child profile update event."""
    event = ChildProfileUpdated(
        child_id="child123",
        updated_fields=["name", "age"],
        updated_at=datetime.now(),
        parent_id="parent123"
    )
    assert event.child_id == "child123"
    assert event.updated_fields == ["name", "age"]
    assert event.version == "1.0.0"


def test_child_profile_updated_invalid_fields():
    """Test child profile update with invalid fields."""
    with pytest.raises(ValueError, match="updated_fields must be a non-empty list"):
        ChildProfileUpdated(
            child_id="child123",
            updated_fields=[],  # Empty list
            updated_at=datetime.now()
        )


def test_message_created():
    """Test message created event."""
    event = MessageCreated(
        message_id="msg123",
        child_id="child123",
        content="Hello!",
        created_at=datetime.now()
    )
    assert event.message_id == "msg123"
    assert event.child_id == "child123"
    assert event.content == "Hello!"
    assert event.version == "1.0.0"


def test_message_violation():
    """Test message violation event."""
    event = MessageViolation(
        message_id="msg123",
        child_id="child123",
        violation_type="inappropriate_content",
        detected_at=datetime.now(),
        details="Contains forbidden words"
    )
    assert event.violation_type == "inappropriate_content"
    assert event.details == "Contains forbidden words"


def test_auth_event():
    """Test authentication event."""
    event = AuthEvent(
        user_id="user123",
        event_type="login",
        timestamp=datetime.now(),
        ip_address="192.168.1.1"
    )
    assert event.user_id == "user123"
    assert event.event_type == "login"
    assert event.ip_address == "192.168.1.1"


def test_sensitive_operation():
    """Test sensitive operation event."""
    event = SensitiveOperation(
        operation="data_export",
        performed_by="admin123",
        performed_at=datetime.now(),
        target_id="child123"
    )
    assert event.operation == "data_export"
    assert event.performed_by == "admin123"
    assert event.target_id == "child123"


def test_event_store():
    """Test event store functionality."""
    store = EventStore()
    
    # Test empty store
    assert store.get_all() == []
    
    # Add events
    event1 = MessageCreated(
        message_id="msg1",
        child_id="child1",
        content="Hello",
        created_at=datetime.now()
    )
    event2 = AuthEvent(
        user_id="user1",
        event_type="login",
        timestamp=datetime.now()
    )
    
    store.append(event1)
    store.append(event2)
    
    # Test retrieval
    events = store.get_all()
    assert len(events) == 2
    assert events[0] == event1
    assert events[1] == event2


def test_event_correlation_ids():
    """Test that events have unique correlation IDs."""
    event1 = MessageCreated(
        message_id="msg1",
        child_id="child1",
        content="Hello",
        created_at=datetime.now()
    )
    event2 = MessageCreated(
        message_id="msg2",
        child_id="child1",
        content="Hi",
        created_at=datetime.now()
    )
    
    # Correlation IDs should be different
    assert event1.correlation_id != event2.correlation_id
    assert len(event1.correlation_id) > 0
    assert len(event2.correlation_id) > 0


def test_events_are_immutable():
    """Test that events are immutable (frozen dataclasses)."""
    event = MessageCreated(
        message_id="msg1",
        child_id="child1",
        content="Hello",
        created_at=datetime.now()
    )
    
    # Should not be able to modify
    with pytest.raises(AttributeError):
        event.content = "Modified"