"""
Production API Models for Iraqi Payment System
============================================
Pydantic models for request/response validation with comprehensive
Arabic error handling and Iraqi market specifications.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, validator, root_validator
from decimal import Decimal
from datetime import datetime
from enum import Enum
import re


class PaymentProvider(str, Enum):
    """Supported Iraqi payment providers."""

    ZAINCASH = "zaincash"
    FASTPAY = "fastpay"
    SWITCH = "switch"
    ASIACELL_CASH = "asiacell_cash"
    KOREK_PAY = "korek_pay"


class PaymentStatus(str, Enum):
    """Payment processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class Currency(str, Enum):
    """Supported currencies."""

    IQD = "IQD"
    USD = "USD"
    EUR = "EUR"


class RefundReason(str, Enum):
    """Refund request reasons."""

    CUSTOMER_REQUEST = "customer_request"
    DUPLICATE_PAYMENT = "duplicate_payment"
    FRAUDULENT_TRANSACTION = "fraudulent_transaction"
    SERVICE_NOT_DELIVERED = "service_not_delivered"
    TECHNICAL_ERROR = "technical_error"
    CHARGEBACK = "chargeback"


# Request Models


class PaymentInitiationRequest(BaseModel):
    """Request model for initiating a payment."""

    # Required fields
    amount: Decimal = Field(..., description="Payment amount in the specified currency")
    currency: Currency = Field(default=Currency.IQD, description="Payment currency")
    provider: PaymentProvider = Field(..., description="Preferred payment provider")

    # Customer information
    customer_phone: str = Field(..., description="Customer phone number (Iraqi format)")
    customer_email: Optional[str] = Field(None, description="Customer email address")
    customer_name: Optional[str] = Field(None, description="Customer full name")

    # Order information
    order_id: str = Field(..., description="Unique order identifier")
    description: str = Field(..., description="Payment description in Arabic/English")

    # Optional fields
    redirect_url: Optional[str] = Field(None, description="Redirect URL after payment")
    webhook_url: Optional[str] = Field(
        None, description="Webhook URL for notifications"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )

    # Subscription fields
    is_subscription: bool = Field(
        default=False, description="Is this a subscription payment"
    )
    subscription_plan_id: Optional[str] = Field(
        None, description="Subscription plan identifier"
    )

    class Config:
        schema_extra = {
            "example": {
                "amount": "50000",
                "currency": "IQD",
                "provider": "zaincash",
                "customer_phone": "+9647901234567",
                "customer_email": "customer@example.com",
                "customer_name": "أحمد محمد علي",
                "order_id": "ORD-2025-001",
                "description": "اشتراك شهري في تطبيق الدب الذكي",
                "redirect_url": "https://app.example.com/payment/success",
                "is_subscription": True,
                "subscription_plan_id": "monthly_plan",
            }
        }

    @validator("amount")
    def validate_amount(cls, v):
        """Validate payment amount."""
        if v <= 0:
            raise ValueError("المبلغ يجب أن يكون أكبر من صفر")

        if v < Decimal("1000"):
            raise ValueError("الحد الأدنى للدفع هو 1000 دينار عراقي")

        if v > Decimal("50000000"):
            raise ValueError("الحد الأقصى للدفع هو 50 مليون دينار عراقي")

        return v

    @validator("customer_phone")
    def validate_phone(cls, v):
        """Validate Iraqi phone number format."""
        # Iraqi phone number patterns
        patterns = [
            r"^\+964[0-9]{10}$",  # +964XXXXXXXXXX
            r"^964[0-9]{10}$",  # 964XXXXXXXXXX
            r"^07[0-9]{8}$",  # 07XXXXXXXX
            r"^75[0-9]{7}$",  # 75XXXXXXX (Zain)
            r"^77[0-9]{7}$",  # 77XXXXXXX (Korek)
            r"^78[0-9]{7}$",  # 78XXXXXXX (AsiaCell)
        ]

        if not any(re.match(pattern, v) for pattern in patterns):
            raise ValueError("رقم الهاتف غير صحيح. يجب أن يكون رقم عراقي صالح")

        return v

    @validator("customer_email")
    def validate_email(cls, v):
        """Validate email format."""
        if v and not re.match(r"^[^@]+@[^@]+\.[^@]+$", v):
            raise ValueError("عنوان البريد الإلكتروني غير صحيح")
        return v

    @validator("order_id")
    def validate_order_id(cls, v):
        """Validate order ID format."""
        if not re.match(r"^[A-Za-z0-9_-]{3,50}$", v):
            raise ValueError("معرف الطلب يجب أن يتكون من 3-50 حرف أو رقم")
        return v

    @root_validator
    def validate_subscription_fields(cls, values):
        """Validate subscription-related fields."""
        is_subscription = values.get("is_subscription", False)
        subscription_plan_id = values.get("subscription_plan_id")

        if is_subscription and not subscription_plan_id:
            raise ValueError("معرف خطة الاشتراك مطلوب للدفعات الاشتراكية")

        return values


class PaymentStatusRequest(BaseModel):
    """Request model for checking payment status."""

    payment_id: str = Field(..., description="Payment transaction ID")
    provider: Optional[PaymentProvider] = Field(None, description="Payment provider")

    @validator("payment_id")
    def validate_payment_id(cls, v):
        """Validate payment ID format."""
        if not v.strip():
            raise ValueError("معرف الدفعة مطلوب")
        return v


class RefundRequest(BaseModel):
    """Request model for payment refund."""

    payment_id: str = Field(..., description="Original payment transaction ID")
    amount: Optional[Decimal] = Field(
        None, description="Refund amount (partial refund)"
    )
    reason: RefundReason = Field(..., description="Reason for refund")
    notes: Optional[str] = Field(None, description="Additional notes for refund")

    @validator("amount")
    def validate_refund_amount(cls, v):
        """Validate refund amount."""
        if v is not None and v <= 0:
            raise ValueError("مبلغ الاسترداد يجب أن يكون أكبر من صفر")
        return v


class WebhookVerificationRequest(BaseModel):
    """Request model for webhook verification."""

    signature: str = Field(..., description="Webhook signature")
    payload: Dict[str, Any] = Field(..., description="Webhook payload")
    timestamp: datetime = Field(..., description="Webhook timestamp")
    provider: PaymentProvider = Field(..., description="Payment provider")


# Response Models


class PaymentInitiationResponse(BaseModel):
    """Response model for payment initiation."""

    success: bool = Field(..., description="Operation success status")
    payment_id: str = Field(..., description="Unique payment transaction ID")
    payment_url: Optional[str] = Field(None, description="Payment URL for redirection")
    qr_code: Optional[str] = Field(None, description="QR code for mobile payments")
    expires_at: datetime = Field(..., description="Payment URL expiration time")

    # Provider-specific response
    provider_response: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific data"
    )

    # Status information
    status: PaymentStatus = Field(
        default=PaymentStatus.PENDING, description="Current payment status"
    )
    message: str = Field(..., description="Response message in Arabic")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "payment_id": "PAY_2025_001_ZC",
                "payment_url": "https://zaincash.iq/pay/12345",
                "expires_at": "2025-08-04T15:30:00Z",
                "status": "pending",
                "message": "تم إنشاء رابط الدفع بنجاح",
            }
        }


class PaymentStatusResponse(BaseModel):
    """Response model for payment status."""

    success: bool = Field(..., description="Operation success status")
    payment_id: str = Field(..., description="Payment transaction ID")
    status: PaymentStatus = Field(..., description="Current payment status")
    amount: Decimal = Field(..., description="Payment amount")
    currency: Currency = Field(..., description="Payment currency")
    provider: PaymentProvider = Field(..., description="Payment provider")

    # Transaction details
    transaction_id: Optional[str] = Field(None, description="Provider transaction ID")
    created_at: datetime = Field(..., description="Payment creation time")
    updated_at: datetime = Field(..., description="Last update time")
    completed_at: Optional[datetime] = Field(
        None, description="Payment completion time"
    )

    # Customer information
    customer_phone: str = Field(..., description="Customer phone number")
    order_id: str = Field(..., description="Order identifier")

    # Additional information
    failure_reason: Optional[str] = Field(
        None, description="Failure reason if payment failed"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "payment_id": "PAY_2025_001_ZC",
                "status": "completed",
                "amount": "50000",
                "currency": "IQD",
                "provider": "zaincash",
                "transaction_id": "ZC_TX_12345",
                "created_at": "2025-08-04T14:30:00Z",
                "completed_at": "2025-08-04T14:35:00Z",
                "customer_phone": "+9647901234567",
                "order_id": "ORD-2025-001",
            }
        }


class RefundResponse(BaseModel):
    """Response model for refund request."""

    success: bool = Field(..., description="Operation success status")
    refund_id: str = Field(..., description="Unique refund transaction ID")
    payment_id: str = Field(..., description="Original payment transaction ID")
    amount: Decimal = Field(..., description="Refund amount")
    status: str = Field(..., description="Refund status")
    message: str = Field(..., description="Response message in Arabic")

    # Processing information
    processed_at: Optional[datetime] = Field(None, description="Refund processing time")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "refund_id": "REF_2025_001",
                "payment_id": "PAY_2025_001_ZC",
                "amount": "50000",
                "status": "processing",
                "message": "تم تقديم طلب الاسترداد بنجاح",
                "estimated_completion": "2025-08-07T14:30:00Z",
            }
        }


class ErrorResponse(BaseModel):
    """Response model for errors."""

    success: bool = Field(default=False, description="Operation success status")
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message in Arabic")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error_code": "PAYMENT_001",
                "message": "فشل في معالجة الدفعة",
                "details": {
                    "provider_error": "Insufficient funds",
                    "retry_allowed": True,
                },
                "timestamp": "2025-08-04T14:30:00Z",
            }
        }


class ProviderStatusResponse(BaseModel):
    """Response model for provider health status."""

    provider: PaymentProvider = Field(..., description="Payment provider")
    status: str = Field(..., description="Provider status (online/offline/maintenance)")
    response_time: float = Field(..., description="Average response time in seconds")
    last_check: datetime = Field(..., description="Last health check time")
    available_methods: List[str] = Field(..., description="Available payment methods")

    class Config:
        schema_extra = {
            "example": {
                "provider": "zaincash",
                "status": "online",
                "response_time": 1.2,
                "last_check": "2025-08-04T14:30:00Z",
                "available_methods": ["wallet", "card"],
            }
        }


class SystemHealthResponse(BaseModel):
    """Response model for system health check."""

    status: str = Field(..., description="Overall system status")
    version: str = Field(..., description="System version")
    uptime: int = Field(..., description="System uptime in seconds")

    # Service statuses
    database_status: str = Field(..., description="Database connection status")
    redis_status: str = Field(..., description="Redis connection status")
    providers_status: Dict[str, str] = Field(
        ..., description="Payment providers status"
    )

    # Performance metrics
    active_connections: int = Field(..., description="Number of active connections")
    memory_usage: float = Field(..., description="Memory usage percentage")
    cpu_usage: float = Field(..., description="CPU usage percentage")

    # Transaction statistics
    total_transactions_today: int = Field(..., description="Total transactions today")
    successful_transactions_today: int = Field(
        ..., description="Successful transactions today"
    )
    failed_transactions_today: int = Field(..., description="Failed transactions today")

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "uptime": 86400,
                "database_status": "connected",
                "redis_status": "connected",
                "providers_status": {
                    "zaincash": "online",
                    "fastpay": "online",
                    "switch": "maintenance",
                },
                "active_connections": 25,
                "memory_usage": 45.2,
                "cpu_usage": 12.8,
                "total_transactions_today": 1250,
                "successful_transactions_today": 1198,
                "failed_transactions_today": 52,
            }
        }


# Subscription Models


class SubscriptionPlan(BaseModel):
    """Subscription plan model."""

    plan_id: str = Field(..., description="Unique plan identifier")
    name: str = Field(..., description="Plan name in Arabic")
    description: str = Field(..., description="Plan description")
    price: Decimal = Field(..., description="Plan price")
    currency: Currency = Field(default=Currency.IQD, description="Plan currency")
    duration_days: int = Field(..., description="Plan duration in days")
    features: List[str] = Field(..., description="Plan features list")

    class Config:
        schema_extra = {
            "example": {
                "plan_id": "monthly_premium",
                "name": "خطة شهرية مميزة",
                "description": "خطة شهرية تتضمن جميع الميزات المتقدمة",
                "price": "50000",
                "currency": "IQD",
                "duration_days": 30,
                "features": [
                    "محادثات غير محدودة",
                    "قصص مخصصة",
                    "ألعاب تعليمية",
                    "دعم فني متقدم",
                ],
            }
        }


class SubscriptionCreateRequest(BaseModel):
    """Request model for creating subscription."""

    plan_id: str = Field(..., description="Subscription plan identifier")
    customer_phone: str = Field(..., description="Customer phone number")
    customer_email: Optional[str] = Field(None, description="Customer email")
    payment_provider: PaymentProvider = Field(
        ..., description="Preferred payment provider"
    )
    auto_renewal: bool = Field(default=True, description="Enable auto-renewal")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )


class SubscriptionResponse(BaseModel):
    """Response model for subscription operations."""

    success: bool = Field(..., description="Operation success status")
    subscription_id: str = Field(..., description="Unique subscription identifier")
    plan_id: str = Field(..., description="Subscription plan identifier")
    status: str = Field(..., description="Subscription status")
    next_billing_date: datetime = Field(..., description="Next billing date")
    amount: Decimal = Field(..., description="Subscription amount")
    message: str = Field(..., description="Response message in Arabic")


# Error Codes and Messages

ERROR_MESSAGES = {
    "PAYMENT_001": "فشل في معالجة الدفعة",
    "PAYMENT_002": "مزود الدفع غير متاح حالياً",
    "PAYMENT_003": "مبلغ الدفعة غير صحيح",
    "PAYMENT_004": "معلومات العميل غير مكتملة",
    "PAYMENT_005": "انتهت صلاحية رابط الدفع",
    "PAYMENT_006": "الدفعة قيد المعالجة بالفعل",
    "PAYMENT_007": "فشل في التحقق من الدفعة",
    "PAYMENT_008": "رصيد غير كافي",
    "PAYMENT_009": "تم رفض الدفعة من البنك",
    "PAYMENT_010": "خطأ تقني في النظام",
    "REFUND_001": "فشل في معالجة الاسترداد",
    "REFUND_002": "مبلغ الاسترداد أكبر من المبلغ الأصلي",
    "REFUND_003": "لا يمكن استرداد هذه الدفعة",
    "REFUND_004": "تم تجاوز المدة المسموحة للاسترداد",
    "AUTH_001": "غير مصرح بهذه العملية",
    "AUTH_002": "انتهت صلاحية الرمز المميز",
    "AUTH_003": "رمز التحقق غير صحيح",
    "SYSTEM_001": "خطأ في قاعدة البيانات",
    "SYSTEM_002": "خدمة التخزين المؤقت غير متاحة",
    "SYSTEM_003": "تم تجاوز حد المعاملات المسموح",
}


def get_error_message(error_code: str) -> str:
    """Get Arabic error message for error code."""
    return ERROR_MESSAGES.get(error_code, "حدث خطأ غير متوقع")
