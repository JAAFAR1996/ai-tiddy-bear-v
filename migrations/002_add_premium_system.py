"""
🧸 AI TEDDY BEAR V5 - PREMIUM SUBSCRIPTION DATABASE MIGRATION
============================================================
Migration script to add premium subscription and WebSocket tables.

CRITICAL: This migration adds:
1. Premium subscription tables
2. Payment transaction tables
3. WebSocket connection tracking tables
4. Real-time notification tables

Execute only once in production!
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Enum as SQLEnum,
    Index,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Import existing base if available, otherwise create new one
try:
    from src.infrastructure.database.base import Base
except ImportError:
    Base = declarative_base()


# ===========================================
# PREMIUM SUBSCRIPTION TABLES
# ===========================================


class SubscriptionTier(Base):
    """Premium subscription tiers configuration table."""

    __tablename__ = "subscription_tiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tier_name = Column(
        String(50), unique=True, nullable=False
    )  # FREE, BASIC, PREMIUM, ENTERPRISE
    monthly_price = Column(Float, nullable=False, default=0.0)
    children_limit = Column(Integer, nullable=False, default=1)  # -1 for unlimited
    history_days = Column(Integer, nullable=False, default=7)  # -1 for unlimited
    reports_per_month = Column(Integer, nullable=False, default=1)  # -1 for unlimited
    features_json = Column(Text, nullable=True)  # JSON array of feature names
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_subscription_tier_name", "tier_name"),
        Index("idx_subscription_tier_active", "is_active"),
    )


class UserSubscription(Base):
    """User premium subscription records."""

    __tablename__ = "user_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)  # Reference to user table
    tier_id = Column(Integer, ForeignKey("subscription_tiers.id"), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)

    # Subscription status
    status = Column(
        SQLEnum(
            "ACTIVE",
            "CANCELLED",
            "EXPIRED",
            "TRIAL",
            "PAST_DUE",
            name="subscription_status",
        ),
        nullable=False,
        default="TRIAL",
    )

    # Subscription dates
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    next_billing_date = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    # Billing information
    billing_cycle_days = Column(Integer, nullable=False, default=30)
    last_payment_amount = Column(Float, nullable=True)
    last_payment_date = Column(DateTime, nullable=True)

    # Metadata
    subscription_metadata = Column(Text, nullable=True)  # JSON metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_user_subscription_user_id", "user_id"),
        Index("idx_user_subscription_status", "status"),
        Index("idx_user_subscription_stripe_id", "stripe_subscription_id"),
        Index("idx_user_subscription_end_date", "end_date"),
        UniqueConstraint("user_id", name="uq_user_subscription_user_id"),
    )


class PaymentTransaction(Base):
    """Payment transaction records for audit and billing."""

    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(
        UUID(as_uuid=True), ForeignKey("user_subscriptions.id"), nullable=False
    )
    user_id = Column(String(255), nullable=False)

    # Transaction details
    transaction_type = Column(
        SQLEnum(
            "SUBSCRIPTION",
            "UPGRADE",
            "DOWNGRADE",
            "CANCELLATION",
            "REFUND",
            name="transaction_type",
        ),
        nullable=False,
    )

    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")

    # Payment provider details
    provider = Column(String(50), nullable=False, default="stripe")
    provider_transaction_id = Column(String(255), nullable=True)
    provider_customer_id = Column(String(255), nullable=True)

    # Transaction status
    status = Column(
        SQLEnum(
            "PENDING",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "REFUNDED",
            name="payment_status",
        ),
        nullable=False,
        default="PENDING",
    )

    # Dates
    transaction_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_date = Column(DateTime, nullable=True)

    # Additional information
    description = Column(Text, nullable=True)
    metadata = Column(Text, nullable=True)  # JSON metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_payment_transaction_subscription", "subscription_id"),
        Index("idx_payment_transaction_user", "user_id"),
        Index("idx_payment_transaction_status", "status"),
        Index("idx_payment_transaction_date", "transaction_date"),
        Index("idx_payment_transaction_provider_id", "provider_transaction_id"),
    )


# ===========================================
# WEBSOCKET CONNECTION TRACKING
# ===========================================


class WebSocketConnection(Base):
    """Active WebSocket connection tracking."""

    __tablename__ = "websocket_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)
    connection_id = Column(String(255), unique=True, nullable=False)

    # Connection details
    client_ip = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)
    room_id = Column(String(255), nullable=True)  # For grouping connections

    # Connection status
    status = Column(
        SQLEnum(
            "CONNECTING", "CONNECTED", "DISCONNECTED", "ERROR", name="websocket_status"
        ),
        nullable=False,
        default="CONNECTING",
    )

    # Connection timestamps
    connected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_activity_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)

    # Activity counters
    messages_sent = Column(Integer, default=0, nullable=False)
    messages_received = Column(Integer, default=0, nullable=False)

    # Metadata
    connection_metadata = Column(Text, nullable=True)  # JSON metadata

    __table_args__ = (
        Index("idx_websocket_user_id", "user_id"),
        Index("idx_websocket_connection_id", "connection_id"),
        Index("idx_websocket_status", "status"),
        Index("idx_websocket_room_id", "room_id"),
        Index("idx_websocket_last_activity", "last_activity_at"),
    )


# ===========================================
# REAL-TIME NOTIFICATION TRACKING
# ===========================================


class NotificationDelivery(Base):
    """Real-time notification delivery tracking."""

    __tablename__ = "notification_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)

    # Notification details
    notification_type = Column(
        SQLEnum(
            "SAFETY_ALERT",
            "BEHAVIOR_CONCERN",
            "USAGE_LIMIT",
            "PREMIUM_FEATURE",
            "EMERGENCY",
            name="notification_type",
        ),
        nullable=False,
    )

    priority = Column(
        SQLEnum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="notification_priority"),
        nullable=False,
        default="MEDIUM",
    )

    # Message content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    action_url = Column(String(500), nullable=True)

    # Delivery channels
    websocket_delivered = Column(Boolean, default=False, nullable=False)
    email_delivered = Column(Boolean, default=False, nullable=False)
    sms_delivered = Column(Boolean, default=False, nullable=False)
    push_delivered = Column(Boolean, default=False, nullable=False)

    # Delivery timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    websocket_sent_at = Column(DateTime, nullable=True)
    email_sent_at = Column(DateTime, nullable=True)
    sms_sent_at = Column(DateTime, nullable=True)
    push_sent_at = Column(DateTime, nullable=True)

    # Delivery attempts
    websocket_attempts = Column(Integer, default=0, nullable=False)
    email_attempts = Column(Integer, default=0, nullable=False)
    sms_attempts = Column(Integer, default=0, nullable=False)
    push_attempts = Column(Integer, default=0, nullable=False)

    # Status tracking
    overall_status = Column(
        SQLEnum("PENDING", "PARTIAL", "DELIVERED", "FAILED", name="delivery_status"),
        nullable=False,
        default="PENDING",
    )

    # Error tracking
    last_error = Column(Text, nullable=True)
    retry_after = Column(DateTime, nullable=True)

    # Related data
    related_child_id = Column(String(255), nullable=True)
    safety_score = Column(Integer, nullable=True)
    metadata = Column(Text, nullable=True)  # JSON metadata

    __table_args__ = (
        Index("idx_notification_user_id", "user_id"),
        Index("idx_notification_type", "notification_type"),
        Index("idx_notification_priority", "priority"),
        Index("idx_notification_status", "overall_status"),
        Index("idx_notification_created", "created_at"),
        Index("idx_notification_child_id", "related_child_id"),
    )


# ===========================================
# PREMIUM FEATURE USAGE TRACKING
# ===========================================


class FeatureUsage(Base):
    """Track premium feature usage for billing and analytics."""

    __tablename__ = "feature_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)
    subscription_id = Column(
        UUID(as_uuid=True), ForeignKey("user_subscriptions.id"), nullable=True
    )

    # Feature details
    feature_name = Column(
        String(100), nullable=False
    )  # e.g., 'custom_reports', 'ai_insights'
    feature_category = Column(
        String(50), nullable=False
    )  # e.g., 'reports', 'analytics', 'alerts'

    # Usage details
    usage_count = Column(Integer, default=1, nullable=False)
    usage_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    usage_month = Column(String(7), nullable=False)  # YYYY-MM for monthly limits

    # Billing information
    is_billable = Column(Boolean, default=True, nullable=False)
    tier_required = Column(String(50), nullable=False)  # Minimum tier required

    # Metadata
    usage_metadata = Column(Text, nullable=True)  # JSON metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_feature_usage_user_id", "user_id"),
        Index("idx_feature_usage_feature", "feature_name"),
        Index("idx_feature_usage_month", "usage_month"),
        Index("idx_feature_usage_date", "usage_date"),
        Index("idx_feature_usage_subscription", "subscription_id"),
        UniqueConstraint(
            "user_id", "feature_name", "usage_date", name="uq_daily_feature_usage"
        ),
    )


# ===========================================
# MIGRATION SCRIPT EXECUTION
# ===========================================


def get_migration_sql():
    """Generate SQL statements for this migration."""

    return """
-- ===========================================
-- AI TEDDY BEAR V5 - PREMIUM SYSTEM MIGRATION
-- ===========================================

-- Create subscription tier enumeration
CREATE TYPE subscription_status AS ENUM ('ACTIVE', 'CANCELLED', 'EXPIRED', 'TRIAL', 'PAST_DUE');
CREATE TYPE transaction_type AS ENUM ('SUBSCRIPTION', 'UPGRADE', 'DOWNGRADE', 'CANCELLATION', 'REFUND');
CREATE TYPE payment_status AS ENUM ('PENDING', 'COMPLETED', 'FAILED', 'CANCELLED', 'REFUNDED');
CREATE TYPE websocket_status AS ENUM ('CONNECTING', 'CONNECTED', 'DISCONNECTED', 'ERROR');
CREATE TYPE notification_type AS ENUM ('SAFETY_ALERT', 'BEHAVIOR_CONCERN', 'USAGE_LIMIT', 'PREMIUM_FEATURE', 'EMERGENCY');
CREATE TYPE notification_priority AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE delivery_status AS ENUM ('PENDING', 'PARTIAL', 'DELIVERED', 'FAILED');

-- Insert default subscription tiers
INSERT INTO subscription_tiers (tier_name, monthly_price, children_limit, history_days, reports_per_month, features_json) VALUES 
('FREE', 0.0, 1, 7, 1, '["basic_monitoring"]'),
('BASIC', 9.99, 3, 90, 5, '["advanced_analytics", "export_data", "real_time_alerts", "extended_history"]'),
('PREMIUM', 19.99, -1, -1, -1, '["custom_reports", "priority_support", "unlimited_children", "ai_insights"]'),
('ENTERPRISE', 49.99, -1, -1, -1, '["all_premium_features", "custom_integrations", "dedicated_support"]');

-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_user_subscriptions_active ON user_subscriptions (user_id) WHERE status = 'ACTIVE';
CREATE INDEX CONCURRENTLY idx_payment_transactions_recent ON payment_transactions (transaction_date) WHERE transaction_date > NOW() - INTERVAL '1 year';
CREATE INDEX CONCURRENTLY idx_websocket_connections_active ON websocket_connections (user_id) WHERE status = 'CONNECTED';
CREATE INDEX CONCURRENTLY idx_notification_deliveries_pending ON notification_deliveries (created_at) WHERE overall_status IN ('PENDING', 'PARTIAL');

-- Add constraints for data integrity
ALTER TABLE user_subscriptions ADD CONSTRAINT chk_subscription_dates CHECK (end_date IS NULL OR end_date > start_date);
ALTER TABLE payment_transactions ADD CONSTRAINT chk_payment_amount CHECK (amount >= 0);
ALTER TABLE feature_usage ADD CONSTRAINT chk_usage_count CHECK (usage_count > 0);

COMMENT ON TABLE subscription_tiers IS 'Premium subscription tier configuration';
COMMENT ON TABLE user_subscriptions IS 'User premium subscription records with Stripe integration';
COMMENT ON TABLE payment_transactions IS 'Payment transaction audit trail';
COMMENT ON TABLE websocket_connections IS 'Active WebSocket connection tracking';
COMMENT ON TABLE notification_deliveries IS 'Real-time notification delivery tracking';
COMMENT ON TABLE feature_usage IS 'Premium feature usage tracking for billing';
"""


if __name__ == "__main__":
    print("🧸 AI TEDDY BEAR V5 - PREMIUM SYSTEM MIGRATION")
    print("=" * 50)
    print("This script generates SQL for premium subscription system.")
    print("Execute the SQL output in your PostgreSQL database.")
    print()
    print(get_migration_sql())
