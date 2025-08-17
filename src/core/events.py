"""
Core domain events for AI Teddy Bear application.
All events here must be COPPA-compliant and safe for child data.
Includes versioning, correlation_id, and event store integration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid


@dataclass(frozen=True)
class ChildProfileUpdated:
    """Event: A child's profile was updated (PII encrypted)."""

    child_id: str
    updated_fields: List[str]
    updated_at: datetime
    parent_id: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"

    def __post_init__(self):
        if not self.updated_fields or not all(
            isinstance(f, str) for f in self.updated_fields
        ):
            raise ValueError("updated_fields must be a non-empty list of strings.")


@dataclass(frozen=True)
class ChildRegistered:
    """
    Event: A new child was registered (PII encrypted).
    COPPA: Age is required and must be between 3 and 13 (inclusive).
    """

    child_id: str
    age: int  # Child's age (COPPA: must be 3-13)
    registered_at: datetime
    parent_id: Optional[str] = None
    consent_granted: bool = False
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"

    def __post_init__(self):
        if not (3 <= self.age <= 13):
            raise ValueError("Child age must be between 3 and 13 for COPPA compliance.")


# --- New Events ---


@dataclass(frozen=True)
class MessageCreated:
    """Event: A message was created (content encrypted)."""

    message_id: str
    child_id: str
    content: str
    created_at: datetime
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"


@dataclass(frozen=True)
class MessageViolation:
    """Event: Message violated safety or policy rules."""

    message_id: str
    child_id: str
    violation_type: str
    detected_at: datetime
    details: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"


@dataclass(frozen=True)
class AuthEvent:
    """Event: Authentication or authorization action."""

    user_id: str
    event_type: str  # e.g. 'login', 'logout', 'failed_login'
    timestamp: datetime
    ip_address: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"


@dataclass(frozen=True)
class SensitiveOperation:
    """Event: Sensitive operation (e.g. data export, deletion, admin action)."""

    operation: str
    performed_by: str
    performed_at: datetime
    target_id: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"


# --- Event Store Integration (stub) ---
class EventStore:
    """Simple event store stub for demonstration."""

    def __init__(self):
        self._events = []

    def append(self, event):
        self._events.append(event)

    def get_all(self):
        return list(self._events)
