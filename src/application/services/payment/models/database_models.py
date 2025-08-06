"""
Production-Grade Payment Database Models
=======================================
Real database models for Iraqi payment system with full audit trail,
security, and compliance requirements.
"""

from sqlalchemy import (
    Column,
    String,
    Decimal,
    DateTime,
    Boolean,
    Text,
    Integer,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from datetime import datetime
from enum import Enum
import uuid

Base = declarative_base()


# PostgreSQL Enums
class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethodEnum(str, Enum):
    ZAIN_CASH = "zain_cash"
    FAST_PAY = "fast_pay"
    SWITCH = "switch"
    ASIACELL_CASH = "asiacell_cash"
    KOREK_PAY = "korek_pay"
    BANK_TRANSFER = "bank_transfer"
    CREDIT_CARD = "credit_card"


class TransactionTypeEnum(str, Enum):
    PAYMENT = "payment"
    REFUND = "refund"
    SUBSCRIPTION = "subscription"
    REVERSAL = "reversal"


class PaymentTransaction(Base):
    """
    Main payment transaction table with full audit trail.
    Stores all payment attempts and their complete lifecycle.
    """

    __tablename__ = "payment_transactions"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(100), unique=True, nullable=False, index=True)
    provider_transaction_id = Column(String(200), index=True)

    # Payment details
    amount = Column(Decimal(precision=15, scale=2), nullable=False)
    currency = Column(String(3), nullable=False, default="IQD")
    payment_method = Column(ENUM(PaymentMethodEnum), nullable=False, index=True)
    status = Column(
        ENUM(PaymentStatusEnum),
        nullable=False,
        default=PaymentStatusEnum.PENDING,
        index=True,
    )

    # Customer information (encrypted)
    customer_id = Column(String(100), index=True)
    customer_phone_encrypted = Column(Text, nullable=False)
    customer_name_encrypted = Column(Text, nullable=False)

    # Transaction metadata
    description = Column(Text)
    reference_id = Column(String(200), index=True)
    callback_url = Column(Text)

    # Provider-specific data
    provider_name = Column(String(50), nullable=False, index=True)
    provider_response = Column(JSONB)
    provider_fees = Column(Decimal(precision=15, scale=2), default=0)

    # Payment URLs/Codes
    payment_url = Column(Text)
    qr_code = Column(Text)
    payment_code = Column(String(50))

    # Timing
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    expires_at = Column(DateTime, index=True)
    completed_at = Column(DateTime, index=True)

    # Audit and security
    ip_address = Column(String(45))
    user_agent = Column(Text)
    session_id = Column(String(100))

    # Relationships
    refunds = relationship("RefundTransaction", back_populates="original_payment")
    audit_logs = relationship("PaymentAuditLog", back_populates="transaction")
    webhooks = relationship("WebhookEvent", back_populates="transaction")

    # Constraints
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("provider_fees >= 0", name="non_negative_fees"),
        Index("idx_payment_status_date", "status", "created_at"),
        Index("idx_payment_method_date", "payment_method", "created_at"),
        Index("idx_customer_payments", "customer_id", "created_at"),
    )


class RefundTransaction(Base):
    """
    Refund transactions with full traceability to original payment.
    """

    __tablename__ = "refund_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    refund_id = Column(String(100), unique=True, nullable=False, index=True)

    # Link to original payment
    original_payment_id = Column(
        UUID(as_uuid=True), ForeignKey("payment_transactions.id"), nullable=False
    )

    # Refund details
    amount = Column(Decimal(precision=15, scale=2), nullable=False)
    currency = Column(String(3), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(
        ENUM(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.PENDING
    )

    # Provider response
    provider_refund_id = Column(String(200))
    provider_response = Column(JSONB)
    provider_fees = Column(Decimal(precision=15, scale=2), default=0)

    # Timing
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Audit
    requested_by = Column(String(100), nullable=False)
    approved_by = Column(String(100))

    # Relationships
    original_payment = relationship("PaymentTransaction", back_populates="refunds")

    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_refund_amount"),
        Index("idx_refund_status_date", "status", "created_at"),
    )


class SubscriptionPayment(Base):
    """
    Recurring subscription payments with billing cycle management.
    """

    __tablename__ = "subscription_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(String(100), unique=True, nullable=False, index=True)

    # Customer and plan
    customer_id = Column(String(100), nullable=False, index=True)
    plan_id = Column(String(100), nullable=False)

    # Payment details
    amount = Column(Decimal(precision=15, scale=2), nullable=False)
    currency = Column(String(3), nullable=False, default="IQD")
    payment_method = Column(ENUM(PaymentMethodEnum), nullable=False)

    # Billing cycle
    billing_cycle = Column(String(20), nullable=False)  # monthly, yearly
    next_billing_date = Column(DateTime, nullable=False, index=True)
    billing_day = Column(Integer)  # Day of month for monthly billing

    # Status and control
    status = Column(String(20), nullable=False, default="active", index=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Metadata
    customer_phone_encrypted = Column(Text, nullable=False)
    customer_name_encrypted = Column(Text, nullable=False)

    # Timing
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    cancelled_at = Column(DateTime)

    # Relationships
    payment_attempts = relationship(
        "SubscriptionPaymentAttempt", back_populates="subscription"
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_subscription_amount"),
        Index("idx_next_billing", "next_billing_date", "is_active"),
    )


class SubscriptionPaymentAttempt(Base):
    """
    Individual payment attempts for subscriptions.
    """

    __tablename__ = "subscription_payment_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(
        UUID(as_uuid=True), ForeignKey("subscription_payments.id"), nullable=False
    )
    payment_transaction_id = Column(
        UUID(as_uuid=True), ForeignKey("payment_transactions.id")
    )

    # Attempt details
    attempt_number = Column(Integer, nullable=False, default=1)
    billing_period_start = Column(DateTime, nullable=False)
    billing_period_end = Column(DateTime, nullable=False)

    # Status
    status = Column(
        ENUM(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.PENDING
    )
    error_message = Column(Text)

    # Timing
    attempted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    next_retry_at = Column(DateTime)

    # Relationships
    subscription = relationship(
        "SubscriptionPayment", back_populates="payment_attempts"
    )
    payment_transaction = relationship("PaymentTransaction")

    __table_args__ = (
        Index("idx_subscription_attempts", "subscription_id", "attempted_at"),
    )


class PaymentAuditLog(Base):
    """
    Comprehensive audit log for all payment operations.
    Immutable log for compliance and forensic analysis.
    """

    __tablename__ = "payment_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(
        UUID(as_uuid=True), ForeignKey("payment_transactions.id"), index=True
    )

    # Event details
    event_type = Column(String(50), nullable=False, index=True)
    event_description = Column(Text, nullable=False)

    # State changes
    old_status = Column(String(50))
    new_status = Column(String(50))
    changes = Column(JSONB)

    # Context
    user_id = Column(String(100))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    api_endpoint = Column(String(200))

    # Provider details
    provider_name = Column(String(50))
    provider_request = Column(JSONB)
    provider_response = Column(JSONB)

    # Timing (immutable)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    transaction = relationship("PaymentTransaction", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_event_date", "event_type", "created_at"),
        Index("idx_audit_user_date", "user_id", "created_at"),
    )


class WebhookEvent(Base):
    """
    Webhook events from payment providers with signature verification.
    """

    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id"),
        nullable=True,
        index=True,
    )

    # Webhook details
    provider_name = Column(String(50), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    webhook_id = Column(String(200))  # Provider's webhook ID

    # Security
    signature = Column(Text, nullable=False)
    signature_verified = Column(Boolean, nullable=False, default=False)

    # Content
    raw_payload = Column(Text, nullable=False)
    parsed_payload = Column(JSONB)

    # Processing
    processed = Column(Boolean, nullable=False, default=False, index=True)
    processing_attempts = Column(Integer, nullable=False, default=0)
    processing_error = Column(Text)

    # Timing
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime)

    # HTTP context
    ip_address = Column(String(45))
    user_agent = Column(Text)
    headers = Column(JSONB)

    # Relationships
    transaction = relationship("PaymentTransaction", back_populates="webhooks")

    __table_args__ = (
        Index("idx_webhook_provider_date", "provider_name", "received_at"),
        Index("idx_webhook_processing", "processed", "processing_attempts"),
    )


class PaymentProvider(Base):
    """
    Payment provider configuration and status tracking.
    """

    __tablename__ = "payment_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)

    # Configuration
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_sandbox = Column(Boolean, nullable=False, default=True)
    api_url = Column(Text, nullable=False)

    # Limits
    min_amount = Column(Decimal(precision=15, scale=2), nullable=False)
    max_amount = Column(Decimal(precision=15, scale=2), nullable=False)
    supported_currencies = Column(JSONB, default=["IQD"])

    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_hour = Column(Integer, default=1000)

    # Health monitoring
    last_health_check = Column(DateTime)
    is_healthy = Column(Boolean, default=True, index=True)
    consecutive_failures = Column(Integer, default=0)

    # Statistics
    total_transactions = Column(Integer, default=0)
    successful_transactions = Column(Integer, default=0)
    failed_transactions = Column(Integer, default=0)
    total_volume = Column(Decimal(precision=20, scale=2), default=0)

    # Timing
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint("min_amount > 0", name="positive_min_amount"),
        CheckConstraint("max_amount > min_amount", name="valid_amount_range"),
        Index("idx_provider_health", "is_enabled", "is_healthy"),
    )


class PaymentFraudCheck(Base):
    """
    Fraud detection and risk assessment for payments.
    """

    __tablename__ = "payment_fraud_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id"),
        nullable=False,
        unique=True,
    )

    # Risk assessment
    risk_score = Column(Integer, nullable=False, default=0)  # 0-100
    risk_level = Column(
        String(20), nullable=False, default="low"
    )  # low, medium, high, critical

    # Fraud indicators
    velocity_check = Column(Boolean, default=False)
    amount_check = Column(Boolean, default=False)
    geo_check = Column(Boolean, default=False)
    device_check = Column(Boolean, default=False)
    pattern_check = Column(Boolean, default=False)

    # Decision
    is_approved = Column(Boolean, nullable=False, default=True)
    decline_reason = Column(Text)

    # Context
    customer_transaction_count_24h = Column(Integer, default=0)
    customer_volume_24h = Column(Decimal(precision=15, scale=2), default=0)
    ip_transaction_count_1h = Column(Integer, default=0)

    # External checks
    blacklist_check = Column(Boolean, default=False)
    whitelist_check = Column(Boolean, default=False)

    # Timing
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Raw data for analysis
    check_details = Column(JSONB)

    __table_args__ = (
        Index("idx_fraud_risk_level", "risk_level", "checked_at"),
        Index("idx_fraud_approved", "is_approved", "risk_score"),
    )
