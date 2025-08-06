"""
🧸 AI TEDDY BEAR V5 - CORE ENTITIES MODULE
=========================================
Core domain entities and value objects for the AI Teddy Bear application.
"""

from .subscription import (
    Subscription,
    PremiumFeature,
    PaymentTransaction,
    SubscriptionTier,
    SubscriptionStatus,
    NotificationType,
    NotificationPriority,
    PaymentStatus,
    TransactionType,
)

# Import core entities directly to avoid circular imports
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from entities import (
        Child,
        Message,
        Conversation,
        User,
        SafetyResult,
        AIResponse,
        EventSourcedEntity,
    )
except ImportError:
    # Fallback: define minimal entities here
    from datetime import datetime
    from typing import Optional, List, Dict, Any
    from pydantic import BaseModel, Field
    from uuid import uuid4

    class Child(BaseModel):
        id: str = Field(default_factory=lambda: str(uuid4()))
        name: str = Field(..., min_length=1, max_length=50)
        age: int = Field(..., ge=3, le=13)
        preferences: Dict[str, Any] = Field(default_factory=dict)
        safety_level: str = Field(default="strict")
        created_at: datetime = Field(default_factory=datetime.now)

    class Message(BaseModel):
        id: str = Field(default_factory=lambda: str(uuid4()))
        content: str = Field(..., min_length=1, max_length=1000)
        role: str = Field(..., pattern="^(user|assistant|system)$")
        timestamp: datetime = Field(default_factory=datetime.now)
        child_id: str
        safety_checked: bool = Field(default=False)
        safety_score: float = Field(default=1.0, ge=0.0, le=1.0)

    class Conversation(BaseModel):
        id: str = Field(default_factory=lambda: str(uuid4()))
        child_id: str
        started_at: datetime = Field(default_factory=datetime.now)
        last_activity: datetime = Field(default_factory=datetime.now)
        status: str = Field(default="active")
        context: Dict[str, Any] = Field(default_factory=dict)

    class User(BaseModel):
        id: str = Field(default_factory=lambda: str(uuid4()))
        email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
        role: str = Field(default="parent")
        children: List[str] = Field(default_factory=list)
        created_at: datetime = Field(default_factory=datetime.now)
        is_active: bool = Field(default=True)

    class SafetyResult(BaseModel):
        is_safe: bool = Field(default=True)
        safety_score: float = Field(default=1.0, ge=0.0, le=1.0)
        violations: List[str] = Field(default_factory=list)
        filtered_content: Optional[str] = None
        age_appropriate: bool = Field(default=True)

    class AIResponse(BaseModel):
        content: str
        emotion: str = Field(default="neutral")
        safety_score: float = Field(default=1.0, ge=0.0, le=1.0)
        age_appropriate: bool = Field(default=True)
        timestamp: datetime = Field(default_factory=datetime.now)

    class EventSourcedEntity(BaseModel):
        pass


__all__ = [
    "Subscription",
    "PremiumFeature",
    "PaymentTransaction",
    "SubscriptionTier",
    "SubscriptionStatus",
    "NotificationType",
    "NotificationPriority",
    "PaymentStatus",
    "TransactionType",
    "Child",
    "Message",
    "Conversation",
    "User",
    "SafetyResult",
    "AIResponse",
    "EventSourcedEntity",
]
