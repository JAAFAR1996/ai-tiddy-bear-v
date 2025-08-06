"""
Premium Subscription Entities - Core Domain Models
================================================
Enterprise subscription system for parent app premium features.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from uuid import UUID, uuid4


class SubscriptionTier(Enum):
    """Subscription tier levels."""

    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(Enum):
    """Subscription status states."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"
    SUSPENDED = "suspended"


class PaymentStatus(Enum):
    """Payment transaction status."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class TransactionType(Enum):
    """Payment transaction types."""

    SUBSCRIPTION = "subscription"
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    CANCELLATION = "cancellation"
    REFUND = "refund"


class NotificationType(Enum):
    """Real-time notification types."""

    SAFETY_ALERT = "safety_alert"
    BEHAVIOR_CONCERN = "behavior_concern"
    USAGE_LIMIT = "usage_limit"
    PREMIUM_FEATURE = "premium_feature"
    EMERGENCY = "emergency"


class NotificationPriority(Enum):
    """Notification priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PremiumFeature:
    """Premium feature definition."""

    feature_id: str
    name: str
    description: str
    required_tier: SubscriptionTier
    monthly_limit: Optional[int] = None  # None = unlimited
    enabled: bool = True

    def is_available_for_tier(self, tier: SubscriptionTier) -> bool:
        """Check if feature is available for given tier."""
        tier_hierarchy = {
            SubscriptionTier.FREE: 0,
            SubscriptionTier.BASIC: 1,
            SubscriptionTier.PREMIUM: 2,
            SubscriptionTier.ENTERPRISE: 3,
        }
        return tier_hierarchy.get(tier, 0) >= tier_hierarchy.get(self.required_tier, 0)


@dataclass
class UsageCounter:
    """Track feature usage for billing."""

    feature_id: str
    user_id: UUID
    month_year: str  # Format: "2025-08"
    usage_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

    def increment(self, amount: int = 1) -> None:
        """Increment usage counter."""
        self.usage_count += amount
        self.last_updated = datetime.now()

    def reset(self) -> None:
        """Reset counter for new billing period."""
        self.usage_count = 0
        self.last_updated = datetime.now()


@dataclass
class Subscription:
    """User subscription to premium features."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    tier: SubscriptionTier = SubscriptionTier.FREE
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE

    # Billing information
    created_at: datetime = field(default_factory=datetime.now)
    starts_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None

    # Payment details
    monthly_price: float = 0.0
    currency: str = "USD"
    payment_method_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

    # Feature limits and usage
    feature_limits: Dict[str, int] = field(default_factory=dict)
    usage_counters: Dict[str, int] = field(default_factory=dict)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        now = datetime.now()
        return self.status == SubscriptionStatus.ACTIVE and (
            self.expires_at is None or self.expires_at > now
        )

    def is_trial(self) -> bool:
        """Check if subscription is in trial period."""
        now = datetime.now()
        return (
            self.trial_ends_at is not None
            and self.trial_ends_at > now
            and self.is_active()
        )

    def days_until_expiry(self) -> Optional[int]:
        """Get days until subscription expires."""
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    def can_use_feature(self, feature_id: str, requested_amount: int = 1) -> bool:
        """Check if user can use a premium feature."""
        if not self.is_active():
            return False

        # Check feature limit
        limit = self.feature_limits.get(feature_id)
        if limit is None:
            return True  # Unlimited

        current_usage = self.usage_counters.get(feature_id, 0)
        return current_usage + requested_amount <= limit

    def use_feature(self, feature_id: str, amount: int = 1) -> bool:
        """Record feature usage."""
        if not self.can_use_feature(feature_id, amount):
            return False

        self.usage_counters[feature_id] = (
            self.usage_counters.get(feature_id, 0) + amount
        )
        return True


@dataclass
class PaymentTransaction:
    """Payment transaction record."""

    id: UUID = field(default_factory=uuid4)
    subscription_id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)

    # Transaction details
    amount: float = 0.0
    currency: str = "USD"
    description: str = ""

    # Status and timing
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None

    # External payment provider details
    stripe_payment_intent_id: Optional[str] = None
    paypal_transaction_id: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def mark_completed(self) -> None:
        """Mark transaction as completed."""
        self.status = PaymentStatus.COMPLETED
        self.processed_at = datetime.now()

    def mark_failed(self, reason: str = "") -> None:
        """Mark transaction as failed."""
        self.status = PaymentStatus.FAILED
        self.processed_at = datetime.now()
        if reason:
            self.metadata["failure_reason"] = reason


# Premium Feature Definitions
PREMIUM_FEATURES = [
    PremiumFeature(
        feature_id="advanced_analytics",
        name="Advanced Analytics",
        description="Detailed behavioral analysis and learning progress reports",
        required_tier=SubscriptionTier.BASIC,
        monthly_limit=None,
    ),
    PremiumFeature(
        feature_id="custom_reports",
        name="Custom Reports",
        description="Generate personalized safety and development reports",
        required_tier=SubscriptionTier.PREMIUM,
        monthly_limit=10,
    ),
    PremiumFeature(
        feature_id="export_data",
        name="Data Export",
        description="Export conversation history and analytics data",
        required_tier=SubscriptionTier.BASIC,
        monthly_limit=5,
    ),
    PremiumFeature(
        feature_id="priority_support",
        name="Priority Support",
        description="24/7 priority customer support",
        required_tier=SubscriptionTier.PREMIUM,
        monthly_limit=None,
    ),
    PremiumFeature(
        feature_id="unlimited_children",
        name="Unlimited Children",
        description="Manage unlimited child profiles",
        required_tier=SubscriptionTier.PREMIUM,
        monthly_limit=None,
    ),
    PremiumFeature(
        feature_id="real_time_alerts",
        name="Real-time Safety Alerts",
        description="Instant notifications for safety concerns",
        required_tier=SubscriptionTier.BASIC,
        monthly_limit=None,
    ),
    PremiumFeature(
        feature_id="ai_insights",
        name="AI Behavioral Insights",
        description="AI-powered analysis of child behavior patterns",
        required_tier=SubscriptionTier.PREMIUM,
        monthly_limit=20,
    ),
    PremiumFeature(
        feature_id="extended_history",
        name="Extended History",
        description="Access conversation history beyond 30 days",
        required_tier=SubscriptionTier.BASIC,
        monthly_limit=None,
    ),
]

# Pricing Tiers
SUBSCRIPTION_PRICING = {
    SubscriptionTier.FREE: {
        "monthly_price": 0.0,
        "features": ["basic_monitoring", "single_child"],
        "limits": {"children_count": 1, "history_days": 7, "reports_per_month": 1},
    },
    SubscriptionTier.BASIC: {
        "monthly_price": 9.99,
        "features": [
            "advanced_analytics",
            "export_data",
            "real_time_alerts",
            "extended_history",
        ],
        "limits": {
            "children_count": 3,
            "history_days": 90,
            "reports_per_month": 5,
            "export_data": 5,
        },
    },
    SubscriptionTier.PREMIUM: {
        "monthly_price": 19.99,
        "features": [
            "custom_reports",
            "priority_support",
            "unlimited_children",
            "ai_insights",
        ],
        "limits": {
            "children_count": -1,  # Unlimited
            "history_days": -1,  # Unlimited
            "reports_per_month": -1,
            "custom_reports": 10,
            "ai_insights": 20,
        },
    },
    SubscriptionTier.ENTERPRISE: {
        "monthly_price": 49.99,
        "features": [
            "all_premium_features",
            "custom_integrations",
            "dedicated_support",
        ],
        "limits": {
            "children_count": -1,
            "history_days": -1,
            "reports_per_month": -1,
            "custom_reports": -1,
            "ai_insights": -1,
        },
    },
}
