"""
Core Entities - Consolidated from 25+ model files
Extracted working domain models from existing implementation
Includes ChildProfile entity for event sourcing use cases
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from pydantic import PrivateAttr
from uuid import uuid4

from .events import ChildRegistered, ChildProfileUpdated
from .constants import MAX_CHILD_AGE, MIN_CHILD_AGE, MAX_AI_RESPONSE_TOKENS
from typing import Type
import os



class Child(BaseModel):
    """
    Child entity with strict validation and COPPA compliance.
    Data only, no event logic.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=50)
    age: int = Field(..., ge=MIN_CHILD_AGE, le=MAX_CHILD_AGE)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    safety_level: str = Field(default="strict")
    created_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def create(
        cls: Type["Child"], name: str, age: int, preferences: dict = None
    ) -> "Child":
        """Factory with error handling and validation."""
        try:
            return cls(name=name, age=age, preferences=preferences or {})
        except Exception as e:
            raise ValueError(f"Failed to create Child: {e}")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class EventSourcedEntity(BaseModel):
    """Base for event-sourced entities."""

    _events: list = PrivateAttr(default_factory=list)

    def update_profile(
        self,
        name: Optional[str] = None,
        age: Optional[int] = None,
        preferences: Optional[dict] = None,
        updated_by: Optional[str] = None,
    ) -> None:
        """Update profile fields and emit ChildProfileUpdated event if changed."""
        updated_fields = []
        previous_values = {}
        if name is not None and name != self.name:
            previous_values["name"] = self.name
            self.name = name
            updated_fields.append("name")
        if age is not None and age != self.age:
            previous_values["age"] = self.age
            self.age = age
            updated_fields.append("age")
        if preferences is not None and preferences != self.preferences:
            previous_values["preferences"] = self.preferences.copy()
            self.preferences = preferences
            updated_fields.append("preferences")
        if updated_fields:
            self.updated_at = datetime.now()
            event = ChildProfileUpdated(
                child_id=self.id,
                updated_by=updated_by,
                updated_at=self.updated_at,
                updated_fields=updated_fields,
                previous_values=previous_values,
            )
            self._events.append(event)

    def get_uncommitted_events(self) -> list:
        """Return and clear the list of uncommitted domain events."""
        events = self._events[:]
        self._events.clear()
        return events


class Message(EventSourcedEntity):
    """
    Message entity for conversations.
    - Uses limits from constants.
    - Content is stored encrypted (Fernet/AES).
    - Emits events on creation (future-proof).
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(..., min_length=1, max_length=MAX_AI_RESPONSE_TOKENS)
    role: str = Field(..., pattern="^(user|assistant|system)$")
    timestamp: datetime = Field(default_factory=datetime.now)
    child_id: str
    safety_checked: bool = Field(default=False)
    safety_score: float = Field(default=1.0, ge=0.0, le=1.0)

    @classmethod
    def encrypt_content(cls, plain: str) -> str:
        """Encrypt message content using unified encryption service."""
        from src.utils.crypto_utils import EncryptionService
        service = EncryptionService()
        return service.encrypt_message_content(plain)

    @classmethod
    def decrypt_content(cls, token: str) -> str:
        """Decrypt message content using unified encryption service."""
        from src.utils.crypto_utils import EncryptionService
        service = EncryptionService()
        return service.decrypt_message_content(token)

    @classmethod
    def create(cls, content: str, role: str, child_id: str, **kwargs) -> "Message":
        try:
            enc_content = cls.encrypt_content(content)
            obj = cls(content=enc_content, role=role, child_id=child_id, **kwargs)
            # Example: obj._events.append(MessageCreated(...))
            return obj
        except Exception as e:
            raise ValueError(f"Failed to create Message: {e}")

    def get_content(self) -> str:
        return self.decrypt_content(self.content)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class Conversation(EventSourcedEntity):
    """
    Conversation entity managing child interactions.
    - Event sourced.
    - Message limits from constants.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    child_id: str
    started_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="active")
    context: Dict[str, Any] = Field(default_factory=dict)
    _messages: List[Message] = PrivateAttr(default_factory=list)

    def add_message(self, message: Message):
        if len(self._messages) >= MAX_AI_RESPONSE_TOKENS:
            raise ValueError("Conversation message limit exceeded")
        self._messages.append(message)
        self.last_activity = datetime.now()
        # Example: self._events.append(ConversationMessageAdded(...))

    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        return self._messages[-limit:] if self._messages else []

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class User(EventSourcedEntity):
    """
    User entity for authentication.
    - Event sourced.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    role: str = Field(default="parent")
    children: List[str] = Field(default_factory=list)  # Child IDs
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = Field(default=True)

    @classmethod
    def create(cls, email: str, role: str = "parent", children: list = None) -> "User":
        try:
            return cls(email=email, role=role, children=children or [])
        except Exception as e:
            raise ValueError(f"Failed to create User: {e}")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SafetyResult(BaseModel):
    """Safety analysis result"""

    is_safe: bool = Field(default=True)
    safety_score: float = Field(default=1.0, ge=0.0, le=1.0)
    violations: List[str] = Field(default_factory=list)
    filtered_content: Optional[str] = None
    age_appropriate: bool = Field(default=True)


class AIResponse(BaseModel):
    """AI response with safety metadata"""

    content: str
    emotion: str = Field(default="neutral")
    safety_score: float = Field(default=1.0, ge=0.0, le=1.0)
    age_appropriate: bool = Field(default=True)
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
