"""Exception interfaces for clean architecture.

Defines interface contracts for exceptions to maintain clean architecture principles.
All custom exceptions should implement these interfaces to avoid layer violations.

Interfaces provide:
- Consistent exception structure across layers
- Type safety for exception handling
- Decoupling between architectural layers
"""

from typing import Optional, Any, Dict


# IDatabaseError is now an alias for DatabaseError for unified exception handling
from src.infrastructure.exceptions import DatabaseError

IDatabaseError = DatabaseError


class IValidationError(Exception):
    """
    Interface for validation errors.

    Handles:
    - Input format validation
    - Business rule violations
    - Data type mismatches
    - Required field validation

    Args:
        message: Validation error description
        field: Name of the field that failed validation
        value: The invalid value that caused the error
    """

    def __init__(
        self, message: str, field: Optional[str] = None, value: Optional[Any] = None
    ):
        super().__init__(message)
        self.field = field
        self.value = value


class IAuthenticationError(Exception):
    """Interface for authentication errors."""

    def __init__(self, message: str, reason: Optional[str] = None):
        super().__init__(message)
        self.reason = reason


class IAuthorizationError(Exception):
    """Interface for authorization errors."""

    def __init__(
        self, message: str, resource: Optional[str] = None, action: Optional[str] = None
    ):
        super().__init__(message)
        self.resource = resource
        self.action = action


class IServiceError(Exception):
    """
    Interface for service-level errors.

    Covers:
    - External service failures
    - Internal service communication errors
    - Service unavailability
    - API integration issues

    Args:
        message: Service error description
        service_name: Name of the failing service
        error_code: Service-specific error code
    """

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        super().__init__(message)
        self.service_name = service_name
        self.error_code = error_code


class IConfigurationError(Exception):
    """Interface for configuration errors."""

    def __init__(self, message: str, key: Optional[str] = None):
        super().__init__(message)
        self.key = key


# Use the interface names as the actual exceptions for simplicity
DatabaseError = IDatabaseError
ValidationError = IValidationError
AuthenticationError = IAuthenticationError
AuthorizationError = IAuthorizationError
ServiceError = IServiceError
ConfigurationError = IConfigurationError
