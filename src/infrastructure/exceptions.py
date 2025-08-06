"""
Infrastructure-specific exceptions for AI Teddy Bear (production-grade).
All exceptions here must inherit from core AITeddyBearException.
"""

from src.core.exceptions import ChildSafetyViolation, COPPAViolation
from typing import Dict, Any
from uuid import uuid4
import time
from src.core.exceptions import (
    ValidationError,
    AuthorizationError,
    AITeddyBearException,
)
from src.interfaces.exceptions import IServiceError as ServiceError

# =============================
# INFRASTRUCTURE EXCEPTIONS
# =============================


class ParentalConsentRequired(AITeddyBearException):
    """
    Parental consent required for this action.
    
    Raised when:
    - Child under 13 attempts restricted action (COPPA compliance)
    - Feature requires explicit parental permission
    - Consent has expired or been revoked
    """
    
    error_code = "parental_consent_required"


class AgeVerificationError(AITeddyBearException):
    """
    Age verification failed or required.
    
    Occurs when:
    - Unable to verify user's age
    - Age verification documents are invalid
    - User age doesn't meet minimum requirements
    """
    
    error_code = "age_verification_failed"


class ConsentError(AITeddyBearException):
    """Consent-related error."""
    
    error_code = "consent_error"


class AIServiceError(AITeddyBearException):
    """
    AI service unavailable or error.
    
    Common causes:
    - External AI API is down
    - Authentication with AI service failed
    - AI service returned unexpected response
    - Model loading or inference errors
    """
    
    error_code = "ai_service_error"


class AIQuotaExceeded(AITeddyBearException):
    """AI service quota or rate limit exceeded."""
    
    error_code = "ai_quota_exceeded"


class AIContentFilterError(AITeddyBearException):
    """AI service blocked content due to safety filters."""
    
    error_code = "ai_content_filtered"


class DatabaseError(AITeddyBearException):
    """
    Database operation failed.
    
    Includes:
    - Connection failures
    - Query execution errors
    - Transaction rollbacks
    - Constraint violations
    """
    
    error_code = "database_error"


class DatabaseConnectionError(DatabaseError):
    """Database connection failed."""

    pass


class DatabaseTimeoutError(DatabaseError):
    """Database operation timed out."""

    pass


class RateLimitExceeded(AITeddyBearException):
    """Rate limit exceeded."""

    pass


class ThrottlingError(AITeddyBearException):
    """Service throttling due to high load."""

    pass


class ConfigurationError(AITeddyBearException):
    """Configuration error that prevents operation."""

    pass


class ServiceUnavailableError(AITeddyBearException):
    """Service temporarily unavailable."""

    pass


class MaintenanceModeError(AITeddyBearException):
    """Service in maintenance mode."""

    pass


class FileProcessingError(AITeddyBearException):
    """File processing failed."""

    pass


class FileSizeExceeded(FileProcessingError):
    """File size exceeds maximum allowed."""

    pass


class UnsupportedFileType(FileProcessingError):
    """Unsupported file type."""

    pass


# =============================
# EXCEPTION UTILITIES
# =============================


def get_exception_info(exc: Exception) -> Dict[str, Any]:
    """
    Extract standardized information from any exception.
    
    Args:
        exc: Exception to extract information from
        
    Returns:
        Dict containing structured error information
    """
    if isinstance(exc, AITeddyBearException):
        return exc.to_dict()
    
    # Handle standard Python exceptions
    correlation_id = str(uuid4())
    return {
        "error_code": "UNHANDLED_ERROR",
        "message": "An unexpected error occurred",
        "context": {
            "correlation_id": correlation_id,
            "timestamp": time.time(),
            "exception_type": type(exc).__name__,
            "original_message": str(exc),
        }
    }


def create_error_response(
    exc: Exception, include_debug: bool = False
) -> Dict[str, Any]:
    """
    Create a standardized error response for API endpoints.
    
    Args:
        exc: Exception to create response for
        include_debug: Whether to include debug information
        
    Returns:
        Dict containing standardized error response
    """
    error_info = get_exception_info(exc)
    
    if include_debug and not isinstance(exc, AITeddyBearException):
        import traceback
        if "context" not in error_info:
            error_info["context"] = {}
        error_info["context"]["debug"] = {
            "traceback": traceback.format_exc(),
            "exception_args": list(exc.args) if exc.args else [],
        }
    
    return {"error": error_info}


# Comprehensive exception mapping
EXCEPTION_MAPPING = {
    ValueError: ValidationError,
    TypeError: ValidationError,
    PermissionError: AuthorizationError,
    OSError: ServiceUnavailableError,
    ImportError: ConfigurationError,
}


def map_exception(exc: Exception, default_message: str = None) -> AITeddyBearException:
    """
    Map standard Python exceptions to our custom exception hierarchy.
    
    Args:
        exc: The original exception to map
        default_message: Override message for the mapped exception
        
    Returns:
        AITeddyBearException: Mapped custom exception
    """
    exc_type = type(exc)
    if exc_type in EXCEPTION_MAPPING:
        custom_exc_class = EXCEPTION_MAPPING[exc_type]
        message = default_message or str(exc) or "Operation failed"
        context = {"original_exception": exc_type.__name__}
        return custom_exc_class(message, context=context)
    
    # For unmapped exceptions, create generic exception with details
    context = {
        "original_exception": exc_type.__name__,
        "original_message": str(exc)
    }
    return AITeddyBearException(
        default_message or "An unexpected error occurred", 
        context=context
    )
