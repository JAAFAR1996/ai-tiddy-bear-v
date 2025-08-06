"""
AI Teddy Bear API Models with Enhanced Validation
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator, EmailStr
from datetime import datetime
from enum import Enum
from src.core.value_objects.value_objects import SafetyLevel
import re
import html
from urllib.parse import quote
from .config import (
    ALLOWED_INTERESTS,
    SUPPORTED_LANGUAGES,
    INAPPROPRIATE_WORDS,
    PHONE_PATTERN,
    PASSWORD_PATTERN,
    XSS_PATTERNS,
    MIN_CHILD_AGE,
    MAX_CHILD_AGE,
    MIN_CONVERSATION_TIME_LIMIT,
    MAX_CONVERSATION_TIME_LIMIT,
    CONTENT_FILTER_LEVELS,
    MIN_SAFETY_SCORE,
    MAX_SAFETY_SCORE,
)


class UserRole(str, Enum):
    PARENT = "parent"
    GUARDIAN = "guardian"
    ADMIN = "admin"


class ConversationMode(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    MIXED = "mixed"


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    COPPA_VIOLATION = "COPPA_VIOLATION"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ParentRegistrationRequest(BaseModel):
    email: EmailStr = Field(..., description="Parent's email address")
    password: str = Field(..., min_length=8, description="Strong password (8+ chars)")
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., description="Phone number for 2FA")
    consent_to_coppa: bool = Field(..., description="Required COPPA consent")
    terms_accepted: bool = Field(..., description="Required Terms acceptance")
    marketing_consent: bool = Field(False)

    @validator("password")
    def validate_password(cls, v):
        if not re.match(PASSWORD_PATTERN, v):
            raise ValueError(
                "Password must be at least 8 characters and contain uppercase, lowercase, digit, and special character (@$!%*?&)"
            )
        return v

    @validator("phone")
    def validate_phone(cls, v):
        # Clean phone number and validate
        cleaned = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not re.match(PHONE_PATTERN, cleaned):
            raise ValueError(
                "Phone number must be in international format (e.g., +1234567890)"
            )
        return cleaned

    @validator("consent_to_coppa", "terms_accepted")
    def validate_required_consent(cls, v):
        if not v:
            raise ValueError("This consent is required")
        return v


class LoginRequest(BaseModel):
    email: EmailStr = Field(...)
    password: str = Field(...)
    remember_me: bool = Field(False)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: Dict[str, Any]


class ChildProfileRequest(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=30, description="Child's first name only"
    )
    age: int = Field(
        ...,
        ge=MIN_CHILD_AGE,
        le=MAX_CHILD_AGE,
        description=f"Child's age ({MIN_CHILD_AGE}-{MAX_CHILD_AGE} years for COPPA)",
    )
    interests: List[str] = Field(..., min_items=1, max_items=10)
    safety_level: SafetyLevel = Field(SafetyLevel.HIGH)
    language_preference: str = Field("en")
    parental_controls: Dict[str, Any] = Field(
        default_factory=dict,
        description="Controls: conversation_time_limit(mins), daily_interaction_limit(mins), content_filtering(strict/moderate/basic), voice_enabled(bool)",
    )

    @validator("interests")
    def validate_interests(cls, v):
        if not v:
            raise ValueError("At least one interest is required")
        cleaned_interests = []
        for interest in v:
            cleaned = interest.lower().strip()
            if cleaned not in ALLOWED_INTERESTS:
                raise ValueError(
                    f'Interest "{interest}" is not allowed. Valid interests: {sorted(ALLOWED_INTERESTS)}'
                )
            cleaned_interests.append(cleaned)
        return cleaned_interests

    @validator("language_preference")
    def validate_language(cls, v):
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f'Language "{v}" is not supported. Supported languages: {SUPPORTED_LANGUAGES}'
            )
        return v

    @validator("parental_controls")
    def validate_parental_controls(cls, v):
        if "conversation_time_limit" in v:
            limit = v["conversation_time_limit"]
            if (
                not isinstance(limit, int)
                or limit < MIN_CONVERSATION_TIME_LIMIT
                or limit > MAX_CONVERSATION_TIME_LIMIT
            ):
                raise ValueError(
                    f"conversation_time_limit must be between {MIN_CONVERSATION_TIME_LIMIT}-{MAX_CONVERSATION_TIME_LIMIT} minutes"
                )
        if (
            "content_filtering" in v
            and v["content_filtering"] not in CONTENT_FILTER_LEVELS
        ):
            raise ValueError(
                f"content_filtering must be one of: {CONTENT_FILTER_LEVELS}"
            )
        return v


class ChildProfileResponse(BaseModel):
    id: str
    name: str
    age: int
    interests: List[str]
    safety_level: str
    created_at: datetime
    last_interaction: Optional[datetime] = None
    total_conversations: int = 0


class ConversationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    conversation_id: Optional[str] = None
    mode: ConversationMode = ConversationMode.TEXT
    voice_enabled: bool = False
    context: Optional[Dict[str, Any]] = None

    @validator("message")
    def validate_message(cls, v):
        # Sanitize input
        v = v.strip()
        v_lower = v.lower()

        # Check for inappropriate content
        for word in INAPPROPRIATE_WORDS:
            if word in v_lower:
                raise ValueError(
                    f"Message contains inappropriate content: personal or sensitive information"
                )

        # XSS protection
        for pattern in XSS_PATTERNS:
            if pattern in v_lower:
                raise ValueError("Message contains potentially unsafe content")

        # HTML escape for additional safety
        return html.escape(v)


class ConversationResponse(BaseModel):
    conversation_id: str
    message: str
    audio_url: Optional[str] = None
    safety_score: float = Field(..., ge=MIN_SAFETY_SCORE, le=MAX_SAFETY_SCORE)
    educational_value: Optional[str] = None
    suggested_followups: List[str] = Field(default_factory=list)
    interaction_metadata: Dict[str, Any] = Field(default_factory=dict)


class SafetyReport(BaseModel):
    incident_type: str
    severity: str = Field(..., pattern=r"^(low|medium|high|critical)$")
    description: str
    action_taken: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthStatus(BaseModel):
    status: str = Field(..., pattern=r"^(healthy|degraded|unhealthy)$")
    version: str
    uptime: int = Field(..., ge=0)
    active_conversations: int = Field(..., ge=0)
    safety_checks_passed: int = Field(..., ge=0)


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    field: Optional[str] = None
    correlation_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail

    @classmethod
    def create(
        cls,
        code: ErrorCode,
        message: str,
        field: str = None,
        correlation_id: str = None,
    ):
        return cls(
            error=ErrorDetail(
                code=code,
                message=message,
                field=field,
                correlation_id=correlation_id or f"req_{datetime.utcnow().timestamp()}",
            )
        )


# =============================================================================
# RATE LIMITING MODELS
# =============================================================================


class RateLimitInfo(BaseModel):
    """Rate limit information for API responses"""

    limit: int = Field(..., description="Maximum requests allowed in window")
    remaining: int = Field(
        ..., ge=0, description="Requests remaining in current window"
    )
    reset: datetime = Field(..., description="When the rate limit window resets")
    retry_after: Optional[int] = Field(
        None, description="Seconds to wait before retry (when limited)"
    )


class RateLimitExceeded(BaseModel):
    """Rate limit exceeded error response"""

    error: str = "Rate limit exceeded"
    rate_limit: RateLimitInfo
    message: str = Field(..., description="Human-readable error message")


# =============================================================================
# AUDIT TRAIL MODELS
# =============================================================================


class AuditEventType(str, Enum):
    """Types of audit events for COPPA compliance"""

    PARENT_REGISTRATION = "parent_registration"
    PARENT_LOGIN = "parent_login"
    CHILD_PROFILE_CREATED = "child_profile_created"
    CHILD_PROFILE_UPDATED = "child_profile_updated"
    CHILD_PROFILE_DELETED = "child_profile_deleted"
    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_ENDED = "conversation_ended"
    SAFETY_INCIDENT = "safety_incident"
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"
    CONSENT_GIVEN = "consent_given"
    CONSENT_WITHDRAWN = "consent_withdrawn"


class AuditEvent(BaseModel):
    """Audit event for compliance tracking"""

    event_id: str = Field(..., description="Unique event identifier")
    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = Field(None, description="Parent/user ID if applicable")
    child_id: Optional[str] = Field(None, description="Child ID if applicable")
    ip_address: str = Field(..., description="Client IP address")
    user_agent: str = Field(..., description="Client user agent")
    action: str = Field(..., description="Specific action taken")
    result: str = Field(..., pattern=r"^(success|failure|error)$")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional event context"
    )


class AuditTrail(BaseModel):
    """Collection of audit events for a specific entity"""

    entity_type: str = Field(..., pattern=r"^(parent|child|conversation)$")
    entity_id: str = Field(..., description="ID of the entity")
    events: List[AuditEvent] = Field(
        ..., description="Chronological list of audit events"
    )
    total_events: int = Field(..., ge=0)
    date_range: Dict[str, datetime] = Field(
        ..., description="Start and end dates of events"
    )


# =============================================================================
# TOKEN MODELS
# =============================================================================


class TokenResponse(BaseModel):
    """JWT token response with metadata"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="Seconds until token expires")
    scope: str = Field("parent", description="Token scope/permissions")
    issued_at: datetime = Field(default_factory=datetime.utcnow)


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token"""

    refresh_token: str = Field(..., description="Valid refresh token")


# =============================================================================
# PAGINATION MODELS
# =============================================================================


class PaginationParams(BaseModel):
    """Standard pagination parameters"""

    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: str = Field("desc", pattern=r"^(asc|desc)$")


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper"""

    items: List[Any] = Field(..., description="Page items")
    total: int = Field(..., ge=0, description="Total items across all pages")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")
    pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there's a next page")
    has_prev: bool = Field(..., description="Whether there's a previous page")
