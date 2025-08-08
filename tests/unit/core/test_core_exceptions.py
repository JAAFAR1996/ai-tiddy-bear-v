"""
Unit tests for core exceptions with 100% coverage.
Tests custom exception behavior, error messages, and exception hierarchy.
"""

import pytest
from src.core.exceptions import (
    AITeddyBearException,
    AuthenticationError,
    InvalidTokenError,
    AuthorizationError,
    SafetyViolationError,
    ConversationNotFoundError,
    ChildNotFoundError,
    ValidationError,
    ExternalServiceError,
    ResourceNotFoundError,
    RateLimitError,
    AITimeoutError,
    InvalidInputError,
    UserNotFoundError,
    SessionExpiredError,
    RateLimitExceeded,
    ConfigurationError,
    ServiceUnavailableError,
    ChildSafetyViolation,
    COPPAViolation,
    SecurityViolation
)


class TestExceptionHierarchy:
    """Test exception inheritance and hierarchy."""

    def test_base_exception(self):
        """Test base AITeddyBearException."""
        exc = AITeddyBearException("Base error")
        assert str(exc) == "Base error"
        assert isinstance(exc, Exception)

    def test_authentication_exceptions_inherit_correctly(self):
        """Test authentication-related exceptions inherit from correct base."""
        auth_error = AuthenticationError("Auth failed")
        token_error = InvalidTokenError("Invalid token")
        session_error = SessionExpiredError("Session expired")
        
        assert isinstance(auth_error, AITeddyBearException)
        assert isinstance(token_error, AuthenticationError)
        assert isinstance(token_error, AITeddyBearException)
        assert isinstance(session_error, AuthenticationError)

    def test_validation_exceptions_inherit_correctly(self):
        """Test validation exceptions inherit correctly."""
        validation_error = ValidationError("Validation failed")
        input_error = InvalidInputError("Invalid input")
        
        assert isinstance(validation_error, AITeddyBearException)
        assert isinstance(input_error, ValidationError)
        assert isinstance(input_error, AITeddyBearException)


class TestSafetyViolationError:
    """Test SafetyViolationError with violations list."""

    def test_safety_violation_with_violations(self):
        """Test SafetyViolationError stores violations."""
        violations = ["violence", "inappropriate_language", "adult_content"]
        exc = SafetyViolationError("Content unsafe", violations=violations)
        
        assert str(exc) == "Content unsafe"
        assert exc.violations == violations
        assert len(exc.violations) == 3

    def test_safety_violation_without_violations(self):
        """Test SafetyViolationError with no violations list."""
        exc = SafetyViolationError("General safety violation")
        
        assert str(exc) == "General safety violation"
        assert exc.violations == []
        assert len(exc.violations) == 0

    def test_safety_violation_empty_list(self):
        """Test SafetyViolationError with explicit empty list."""
        exc = SafetyViolationError("Safety check failed", violations=[])
        
        assert exc.violations == []


class TestValidationError:
    """Test ValidationError with error details."""

    def test_validation_error_with_details(self):
        """Test ValidationError stores error details."""
        errors = {
            "age": "Must be between 3 and 13",
            "name": "Cannot be empty",
            "email": "Invalid format"
        }
        exc = ValidationError("Multiple validation errors", errors=errors)
        
        assert str(exc) == "Multiple validation errors"
        assert exc.errors == errors
        assert exc.errors["age"] == "Must be between 3 and 13"

    def test_validation_error_without_details(self):
        """Test ValidationError without error details."""
        exc = ValidationError("Validation failed")
        
        assert str(exc) == "Validation failed"
        assert exc.errors == {}

    def test_validation_error_access_missing_key(self):
        """Test accessing non-existent error key."""
        exc = ValidationError("Error", errors={"field1": "error1"})
        
        assert "field2" not in exc.errors
        assert exc.errors.get("field2") is None


class TestResourceNotFoundError:
    """Test ResourceNotFoundError with resource details."""

    def test_resource_not_found_with_details(self):
        """Test ResourceNotFoundError with type and ID."""
        exc = ResourceNotFoundError(
            message="Child profile not found",
            resource_type="ChildProfile",
            resource_id="child-123"
        )
        
        expected_msg = "Child profile not found [ChildProfile:child-123]"
        assert str(exc) == expected_msg
        assert exc.resource_type == "ChildProfile"
        assert exc.resource_id == "child-123"

    def test_resource_not_found_default_message(self):
        """Test ResourceNotFoundError with default message."""
        exc = ResourceNotFoundError(
            resource_type="User",
            resource_id="user-456"
        )
        
        expected_msg = "Resource not found [User:user-456]"
        assert str(exc) == expected_msg

    def test_resource_not_found_no_details(self):
        """Test ResourceNotFoundError without details."""
        exc = ResourceNotFoundError()
        
        assert str(exc) == "Resource not found"
        assert exc.resource_type is None
        assert exc.resource_id is None

    def test_resource_not_found_partial_details(self):
        """Test ResourceNotFoundError with only type."""
        exc = ResourceNotFoundError(
            message="Not found",
            resource_type="Conversation"
        )
        
        assert str(exc) == "Not found"
        assert exc.resource_type == "Conversation"
        assert exc.resource_id is None


class TestRateLimitErrors:
    """Test rate limit exception variants."""

    def test_rate_limit_error_with_retry(self):
        """Test RateLimitError with retry_after."""
        exc = RateLimitError("Rate limit exceeded", retry_after=60)
        
        assert str(exc) == "Rate limit exceeded"
        assert exc.retry_after == 60

    def test_rate_limit_error_without_retry(self):
        """Test RateLimitError without retry_after."""
        exc = RateLimitError("Too many requests")
        
        assert str(exc) == "Too many requests"
        assert exc.retry_after is None

    def test_rate_limit_exceeded_duplicate(self):
        """Test RateLimitExceeded (duplicate class)."""
        exc = RateLimitExceeded("Limit hit", retry_after=120)
        
        assert str(exc) == "Limit hit"
        assert exc.retry_after == 120
        assert isinstance(exc, AITeddyBearException)


class TestConfigurationError:
    """Test ConfigurationError with config key."""

    def test_configuration_error_with_key(self):
        """Test ConfigurationError with specific config key."""
        exc = ConfigurationError(
            "Invalid configuration value",
            config_key="DATABASE_URL"
        )
        
        assert str(exc) == "Invalid configuration value"
        assert exc.config_key == "DATABASE_URL"

    def test_configuration_error_without_key(self):
        """Test ConfigurationError without key."""
        exc = ConfigurationError("General config error")
        
        assert str(exc) == "General config error"
        assert exc.config_key is None


class TestServiceUnavailableError:
    """Test ServiceUnavailableError with service name."""

    def test_service_unavailable_with_name(self):
        """Test ServiceUnavailableError with service name."""
        exc = ServiceUnavailableError(
            "AI service is down",
            service="OpenAI"
        )
        
        assert str(exc) == "AI service is down"
        assert exc.service == "OpenAI"

    def test_service_unavailable_without_name(self):
        """Test ServiceUnavailableError without service name."""
        exc = ServiceUnavailableError("Service error")
        
        assert str(exc) == "Service error"
        assert exc.service is None


class TestSpecificDomainExceptions:
    """Test specific domain exceptions."""

    def test_child_not_found(self):
        """Test ChildNotFoundError."""
        exc = ChildNotFoundError()
        assert isinstance(exc, AITeddyBearException)

    def test_conversation_not_found(self):
        """Test ConversationNotFoundError."""
        exc = ConversationNotFoundError()
        assert isinstance(exc, AITeddyBearException)

    def test_user_not_found(self):
        """Test UserNotFoundError."""
        exc = UserNotFoundError()
        assert isinstance(exc, AITeddyBearException)

    def test_external_service_error(self):
        """Test ExternalServiceError."""
        exc = ExternalServiceError("API call failed")
        assert str(exc) == "API call failed"
        assert isinstance(exc, AITeddyBearException)

    def test_ai_timeout_error(self):
        """Test AITimeoutError."""
        exc = AITimeoutError("Operation timed out")
        assert str(exc) == "Operation timed out"
        assert isinstance(exc, AITeddyBearException)

    def test_authorization_error(self):
        """Test AuthorizationError."""
        exc = AuthorizationError("Insufficient permissions")
        assert str(exc) == "Insufficient permissions"
        assert isinstance(exc, AITeddyBearException)


class TestSafetyAndComplianceExceptions:
    """Test safety and compliance-related exceptions."""

    def test_child_safety_violation(self):
        """Test ChildSafetyViolation."""
        exc = ChildSafetyViolation()
        assert isinstance(exc, AITeddyBearException)

    def test_coppa_violation(self):
        """Test COPPAViolation."""
        exc = COPPAViolation()
        assert isinstance(exc, AITeddyBearException)

    def test_security_violation(self):
        """Test SecurityViolation."""
        exc = SecurityViolation()
        assert isinstance(exc, AITeddyBearException)
    
    def test_child_safety_violation_with_message(self):
        """Test ChildSafetyViolation with message."""
        exc = ChildSafetyViolation("Inappropriate content detected")
        assert str(exc) == "Inappropriate content detected"
    
    def test_coppa_violation_with_message(self):
        """Test COPPAViolation with message."""
        exc = COPPAViolation("Age requirement not met")
        assert str(exc) == "Age requirement not met"
    
    def test_security_violation_with_message(self):
        """Test SecurityViolation with message."""
        exc = SecurityViolation("Unauthorized access attempt")
        assert str(exc) == "Unauthorized access attempt"


class TestExceptionUsagePatterns:
    """Test common exception usage patterns."""

    def test_exception_chaining(self):
        """Test exception chaining for debugging."""
        try:
            # Simulate database error
            raise ConnectionError("Database connection failed")
        except ConnectionError as e:
            # Wrap in domain exception
            try:
                raise ExternalServiceError("Could not fetch user data") from e
            except ExternalServiceError as exc:
                assert exc.__cause__ is not None
                assert isinstance(exc.__cause__, ConnectionError)
                assert str(exc.__cause__) == "Database connection failed"

    def test_exception_with_context(self):
        """Test adding context to exceptions."""
        violations = ["violence", "adult_content"]
        exc = SafetyViolationError(
            f"Content violates {len(violations)} safety rules",
            violations=violations
        )
        
        assert "2 safety rules" in str(exc)
        assert exc.violations == violations

    def test_validation_error_aggregation(self):
        """Test aggregating multiple validation errors."""
        errors = {}
        
        # Simulate field validation
        if not "test@example.com".endswith(".com"):
            errors["email"] = "Must be a .com email"
        
        if len("ab") < 3:
            errors["username"] = "Must be at least 3 characters"
        
        if 15 > 13:
            errors["age"] = "Must be 13 or younger"
        
        if errors:
            exc = ValidationError("Profile validation failed", errors=errors)
            assert len(exc.errors) == 2  # email check passes
            assert "username" in exc.errors
            assert "age" in exc.errors


class TestAllExceptionsWithMessages:
    """Test all exceptions can be instantiated with messages."""
    
    def test_child_not_found_with_message(self):
        """Test ChildNotFoundError with custom message."""
        exc = ChildNotFoundError("Child with ID 123 not found")
        assert str(exc) == "Child with ID 123 not found"
    
    def test_conversation_not_found_with_message(self):
        """Test ConversationNotFoundError with custom message."""
        exc = ConversationNotFoundError("Conversation expired")
        assert str(exc) == "Conversation expired"
    
    def test_user_not_found_with_message(self):
        """Test UserNotFoundError with custom message."""
        exc = UserNotFoundError("User account deleted")
        assert str(exc) == "User account deleted"
    
    def test_ai_timeout_error_as_base_exception(self):
        """Test AITimeoutError behavior."""
        exc = AITimeoutError()
        assert isinstance(exc, AITeddyBearException)
        assert isinstance(exc, Exception)
        
        # With custom message
        exc2 = AITimeoutError("Request took too long")
        assert str(exc2) == "Request took too long"
    
    def test_invalid_token_error_with_message(self):
        """Test InvalidTokenError with message."""
        exc = InvalidTokenError("Token signature invalid")
        assert str(exc) == "Token signature invalid"
        assert isinstance(exc, AuthenticationError)
    
    def test_rate_limit_zero_retry(self):
        """Test RateLimitError with zero retry_after."""
        exc = RateLimitError("Immediate retry", retry_after=0)
        assert exc.retry_after == 0
    
    def test_rate_limit_exceeded_zero_retry(self):
        """Test RateLimitExceeded with zero retry_after."""
        exc = RateLimitExceeded("No wait", retry_after=0)
        assert exc.retry_after == 0
    
    def test_resource_not_found_only_resource_id(self):
        """Test ResourceNotFoundError with only resource_id."""
        exc = ResourceNotFoundError(
            message="Missing resource",
            resource_id="res-123"
        )
        # Should not append details if resource_type is missing
        assert str(exc) == "Missing resource"
        assert exc.resource_id == "res-123"
        assert exc.resource_type is None


class TestExceptionEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_validation_error_none_errors_explicit(self):
        """Test ValidationError with None errors parameter."""
        exc = ValidationError("Validation failed", errors=None)
        assert exc.errors == {}
    
    def test_safety_violation_none_violations_explicit(self):
        """Test SafetyViolationError with None violations parameter."""
        exc = SafetyViolationError("Safety check", violations=None)
        assert exc.violations == []
    
    def test_empty_resource_details(self):
        """Test ResourceNotFoundError with empty strings."""
        exc = ResourceNotFoundError(
            message="Not found",
            resource_type="",
            resource_id=""
        )
        # Empty strings should not append details
        assert str(exc) == "Not found"
    
    def test_exception_repr(self):
        """Test exception string representation."""
        exc = AITeddyBearException("Test error")
        repr_str = repr(exc)
        assert "AITeddyBearException" in repr_str
        assert "Test error" in repr_str
    
    def test_exception_inheritance_chain(self):
        """Test complete inheritance chain."""
        exc = InvalidInputError("Bad input")
        
        # Check full inheritance chain
        assert isinstance(exc, InvalidInputError)
        assert isinstance(exc, ValidationError)
        assert isinstance(exc, AITeddyBearException)
        assert isinstance(exc, Exception)
        assert isinstance(exc, BaseException)
    
    def test_configuration_error_empty_key(self):
        """Test ConfigurationError with empty key."""
        exc = ConfigurationError("Config missing", config_key="")
        assert exc.config_key == ""
    
    def test_service_unavailable_empty_service(self):
        """Test ServiceUnavailableError with empty service."""
        exc = ServiceUnavailableError("Down", service="")
        assert exc.service == ""


class TestExceptionComparison:
    """Test exception comparison and equality."""
    
    def test_same_exception_different_instances(self):
        """Test that same exception type with same message are different objects."""
        exc1 = AITeddyBearException("Error")
        exc2 = AITeddyBearException("Error")
        
        assert exc1 is not exc2
        assert str(exc1) == str(exc2)
        assert type(exc1) == type(exc2)
    
    def test_exception_in_collections(self):
        """Test exceptions can be used in collections."""
        exc1 = ValidationError("Error 1")
        exc2 = SafetyViolationError("Error 2")
        exc3 = RateLimitError("Error 3")
        
        # Can be stored in list
        errors = [exc1, exc2, exc3]
        assert len(errors) == 3
        
        # Can be used as dict values
        error_map = {
            "validation": exc1,
            "safety": exc2,
            "rate_limit": exc3
        }
        assert error_map["validation"] is exc1
    
    def test_exception_truthiness(self):
        """Test exception objects are truthy."""
        exc = AITeddyBearException("Any error")
        assert bool(exc) is True
        
        if exc:
            pass  # Should execute
        else:
            pytest.fail("Exception should be truthy")