"""
Core exceptions for AI Teddy Bear application.
Comprehensive exception hierarchy with detailed error codes and context.
All exceptions inherit from AITeddyBearException for consistent handling.
"""

import traceback
from typing import Optional, Dict, List, Any
from datetime import datetime


class AITeddyBearException(Exception):
    """
    Base exception for all application exceptions in AI Teddy Bear.

    Provides:
    - Standard error_code for API responses
    - Context dictionary for additional error details
    - Structured error information for logging and debugging
    - Error severity levels for appropriate handling
    - Correlation ID for request tracking

    Args:
        message: Human-readable error message
        context: Additional context information (dict)
        severity: Error severity (low, medium, high, critical)
        correlation_id: Request correlation ID for tracking
    """

    error_code = "ai_teddybear_error"
    default_severity = "medium"

    def __init__(
        self,
        message: str = None,
        *,
        context: Optional[Dict[str, Any]] = None,
        severity: str = None,
        correlation_id: str = None,
    ):
        super().__init__(message or self.__class__.__doc__)
        self.context = context or {}
        self.severity = severity or self.default_severity
        self.correlation_id = correlation_id
        self.timestamp = datetime.utcnow().isoformat()

        # Add stack trace for debugging (exclude in production API responses)
        self.stack_trace = (
            traceback.format_exc()
            if traceback.format_exc() != "NoneType: None\n"
            else None
        )

    def to_dict(self, include_stack_trace: bool = False) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        result = {
            "error_code": self.error_code,
            "message": str(self),
            "severity": self.severity,
            "timestamp": self.timestamp,
            "context": self.context,
        }

        if self.correlation_id:
            result["correlation_id"] = self.correlation_id

        if include_stack_trace and self.stack_trace:
            result["stack_trace"] = self.stack_trace

        return result

    def get_safe_message(self) -> str:
        """Get sanitized message safe for user display (no sensitive data)."""
        return str(self)


# ====================
# AUTHENTICATION & AUTHORIZATION EXCEPTIONS
# ====================


class AuthenticationError(AITeddyBearException):
    """Raised when authentication fails."""

    error_code = "auth_failed"
    default_severity = "high"


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid or expired."""

    error_code = "invalid_token"


class AuthorizationError(AITeddyBearException):
    """Raised when user lacks required permissions."""

    error_code = "not_authorized"
    default_severity = "high"


class PermissionDeniedError(AuthorizationError):
    """Raised when specific permission is denied."""

    error_code = "permission_denied"

    def __init__(self, permission: str, resource: str = None, **kwargs):
        message = f"Permission '{permission}' denied"
        if resource:
            message += f" for resource '{resource}'"
        context = kwargs.get("context", {})
        context.update({"permission": permission, "resource": resource})
        super().__init__(message, context=context, **kwargs)


# ====================
# CHILD SAFETY & COPPA EXCEPTIONS
# ====================


class SafetyViolationError(AITeddyBearException):
    """
    Raised when content violates child safety rules.

    This exception is triggered when:
    - Inappropriate content is detected in user input
    - AI response contains unsafe material for children
    - Content filtering systems flag potential violations
    """

    error_code = "safety_violation"
    default_severity = "critical"

    def __init__(
        self,
        message: str = None,
        violations: Optional[List[str]] = None,
        confidence_score: float = None,
        **kwargs,
    ):
        super().__init__(message or "Content violates child safety rules", **kwargs)
        self.violations = violations or []
        self.confidence_score = confidence_score

        if self.violations:
            self.context["violations"] = self.violations
        if self.confidence_score is not None:
            self.context["confidence_score"] = self.confidence_score


class COPPAViolationError(AITeddyBearException):
    """Raised when COPPA compliance rules are violated."""

    error_code = "coppa_violation"
    default_severity = "critical"

    def __init__(self, child_age: int = None, required_action: str = None, **kwargs):
        message = "COPPA compliance violation detected"
        if child_age is not None:
            message += f" for child age {child_age}"
        context = kwargs.get("context", {})
        context.update(
            {
                "child_age": child_age,
                "required_action": required_action,
                "compliance_rule": "COPPA",
            }
        )
        super().__init__(message, context=context, **kwargs)


class ParentalConsentRequiredError(COPPAViolationError):
    """Raised when parental consent is required but missing."""

    error_code = "parental_consent_required"

    def __init__(self, child_id: str = None, **kwargs):
        message = "Parental consent required for this action"
        context = kwargs.get("context", {})
        context.update({"child_id": child_id})
        super().__init__(message, context=context, **kwargs)


# ====================
# DATA & RESOURCE EXCEPTIONS
# ====================


class ResourceNotFoundError(AITeddyBearException):
    """Raised when a requested resource is not found."""

    error_code = "resource_not_found"
    default_severity = "low"

    def __init__(self, resource_type: str, resource_id: str = None, **kwargs):
        message = f"{resource_type.title()} not found"
        if resource_id:
            message += f" (ID: {resource_id})"
        context = kwargs.get("context", {})
        context.update({"resource_type": resource_type, "resource_id": resource_id})
        super().__init__(message, context=context, **kwargs)


class ConversationNotFoundError(ResourceNotFoundError):
    """Raised when requested conversation does not exist."""

    error_code = "conversation_not_found"

    def __init__(self, conversation_id: str = None, **kwargs):
        super().__init__("conversation", conversation_id, **kwargs)


class ChildNotFoundError(ResourceNotFoundError):
    """Raised when requested child profile does not exist."""

    error_code = "child_not_found"

    def __init__(self, child_id: str = None, **kwargs):
        super().__init__("child", child_id, **kwargs)


class ValidationError(AITeddyBearException):
    """
    Raised when data validation fails.

    Common scenarios:
    - Invalid input format (email, phone, etc.)
    - Missing required fields
    - Data type mismatches
    - Business rule violations
    """

    error_code = "validation_error"
    default_severity = "medium"

    def __init__(
        self,
        message: str = None,
        field_errors: Optional[Dict[str, List[str]]] = None,
        **kwargs,
    ):
        super().__init__(message or "Data validation failed", **kwargs)
        self.field_errors = field_errors or {}
        if self.field_errors:
            self.context["field_errors"] = self.field_errors


# ====================
# EXTERNAL SERVICE EXCEPTIONS
# ====================


class ExternalServiceError(AITeddyBearException):
    """Raised when external service call fails."""

    error_code = "external_service_error"
    default_severity = "high"

    def __init__(
        self,
        service_name: str,
        status_code: int = None,
        response_data: str = None,
        **kwargs,
    ):
        message = f"External service '{service_name}' failed"
        if status_code:
            message += f" (HTTP {status_code})"
        context = kwargs.get("context", {})
        context.update(
            {
                "service_name": service_name,
                "status_code": status_code,
                "response_data": (
                    response_data[:200] if response_data else None
                ),  # Truncate for safety
            }
        )
        super().__init__(message, context=context, **kwargs)


class OpenAIServiceError(ExternalServiceError):
    """Raised when OpenAI API calls fail."""

    error_code = "openai_service_error"

    def __init__(self, error_type: str = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"error_type": error_type})
        super().__init__("OpenAI", context=context, **kwargs)


# ====================
# SYSTEM & CONFIGURATION EXCEPTIONS
# ====================


class ConfigurationError(AITeddyBearException):
    """Raised when configuration is invalid or missing."""

    error_code = "configuration_error"
    default_severity = "critical"

    def __init__(self, config_key: str = None, **kwargs):
        message = "Configuration error"
        if config_key:
            message += f" for key '{config_key}'"
        context = kwargs.get("context", {})
        context.update({"config_key": config_key})
        super().__init__(message, context=context, **kwargs)


class DatabaseError(AITeddyBearException):
    """Raised when database operations fail."""

    error_code = "database_error"
    default_severity = "high"

    def __init__(self, operation: str = None, table: str = None, **kwargs):
        message = "Database operation failed"
        if operation:
            message += f" ({operation})"
        if table:
            message += f" on table '{table}'"
        context = kwargs.get("context", {})
        context.update({"operation": operation, "table": table})
        super().__init__(message, context=context, **kwargs)


class RateLimitExceeded(AITeddyBearException):
    """Raised when rate limits are exceeded."""

    error_code = "rate_limit_exceeded"
    default_severity = "medium"

    def __init__(
        self, limit: int = None, window: str = None, retry_after: int = None, **kwargs
    ):
        message = "Rate limit exceeded"
        if limit and window:
            message += f" ({limit} requests per {window})"
        context = kwargs.get("context", {})
        context.update({"limit": limit, "window": window, "retry_after": retry_after})
        super().__init__(message, context=context, **kwargs)


# ====================
# BUSINESS LOGIC EXCEPTIONS
# ====================


class BusinessLogicError(AITeddyBearException):
    """Raised when business logic constraints are violated."""

    error_code = "business_logic_error"
    default_severity = "medium"

    def __init__(self, rule: str = None, **kwargs):
        message = "Business logic constraint violated"
        if rule:
            message += f": {rule}"
        context = kwargs.get("context", {})
        context.update({"violated_rule": rule})
        super().__init__(message, context=context, **kwargs)


class SubscriptionError(BusinessLogicError):
    """Raised when subscription-related operations fail."""

    error_code = "subscription_error"

    def __init__(self, subscription_status: str = None, **kwargs):
        message = "Subscription operation failed"
        context = kwargs.get("context", {})
        context.update({"subscription_status": subscription_status})
        super().__init__(message, context=context, **kwargs)


# =============================
# Additional Core Exceptions (موثقة وموحدة)
# =============================


class AITimeoutError(AITeddyBearException):
    """
    Raised when operation times out.
    """

    error_code = "timeout"


class InvalidInputError(ValidationError):
    """
    Raised when input data is invalid.
    """

    error_code = "invalid_input"


class UserNotFoundError(AITeddyBearException):
    """
    Raised when user is not found.
    """

    error_code = "user_not_found"


class SessionExpiredError(AuthenticationError):
    """
    Raised when session has expired.
    """

    error_code = "session_expired"


class ServiceUnavailableError(AITeddyBearException):
    """
    Raised when a service is unavailable.
    service: اسم الخدمة الخارجية أو الداخلية.
    """

    error_code = "service_unavailable"

    def __init__(
        self, message: str = None, service: str = None, *, context: dict = None
    ):
        ctx = context or {}
        if service:
            ctx["service"] = service
        super().__init__(message or self.__doc__, context=ctx)
        self.service = service


class ChildSafetyViolation(SafetyViolationError):
    """
    Raised for child safety violations (alias for SafetyViolationError).
    """

    error_code = "child_safety_violation"


class COPPAViolation(AITeddyBearException):
    """
    Raised for COPPA compliance violations.
    """

    error_code = "coppa_violation"


class SecurityViolation(AITeddyBearException):
    """
    Raised for security violations.
    """

    error_code = "security_violation"


class CacheError(AITeddyBearException):
    """
    Raised when cache operations fail.
    """

    error_code = "cache_error"


class MonitoringError(AITeddyBearException):
    """
    Raised when monitoring operations fail.
    """

    error_code = "monitoring_error"


class TestError(AITeddyBearException):
    """
    Raised when test operations fail.
    """

    error_code = "test_error"


class OptimizationError(AITeddyBearException):
    """
    Raised when optimization operations fail.
    """

    error_code = "optimization_error"


# ====================
# EXCEPTION UTILITIES & HANDLERS
# ====================


class ExceptionHandler:
    """
    Centralized exception handling utility.

    Provides consistent error formatting, logging, and sanitization.
    """

    @staticmethod
    def format_for_api(
        exception: Exception, include_debug: bool = False
    ) -> Dict[str, Any]:
        """Format exception for API response with security considerations."""
        if isinstance(exception, AITeddyBearException):
            return exception.to_dict(include_stack_trace=include_debug)

        # Handle generic exceptions with sanitization
        return {
            "error_code": "internal_error",
            "message": "An internal error occurred",
            "severity": "high",
            "timestamp": datetime.utcnow().isoformat(),
            "context": (
                {"exception_type": type(exception).__name__} if include_debug else {}
            ),
        }

    @staticmethod
    def get_error_hierarchy() -> Dict[str, List[str]]:
        """Get exception hierarchy for documentation and debugging."""
        return {
            "AITeddyBearException": [
                "AuthenticationError",
                "AuthorizationError",
                "SafetyViolationError",
                "COPPAViolationError",
                "ApplicationError",
                "ExternalServiceError",
                "DatabaseError",
                "RateLimitExceeded",
            ],
            "ApplicationError": [
                "ValidationError",
                "BusinessLogicError",
                "ConfigurationError",
            ],
            "AuthenticationError": ["InvalidTokenError"],
            "AuthorizationError": ["PermissionDeniedError"],
            "ValidationError": ["InvalidInputError"],
        }


# ====================
# EXCEPTION REGISTRY
# ====================

EXCEPTION_REGISTRY = {
    exc.__name__: exc
    for exc in [
        AITeddyBearException,
        AuthenticationError,
        InvalidTokenError,
        AuthorizationError,
        PermissionDeniedError,
        SafetyViolationError,
        COPPAViolationError,
        ValidationError,
        InvalidInputError,
        ConfigurationError,
        ExternalServiceError,
        DatabaseError,
        RateLimitExceeded,
    ]
}


def get_exception_by_name(name: str) -> Optional[type]:
    """Get exception class by name for dynamic error handling."""
    return EXCEPTION_REGISTRY.get(name)
