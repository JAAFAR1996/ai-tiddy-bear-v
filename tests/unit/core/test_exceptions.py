"""
Tests for Core Exceptions
=========================

Critical tests for application exception handling.
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
    RateLimitExceeded,
    ConfigurationError,
    ServiceUnavailableError,
    ChildSafetyViolation,
    COPPAViolation,
    SecurityViolation
)


class TestAITeddyBearException:
    """Test base exception class."""

    def test_base_exception_creation(self):
        """Test base exception creation."""
        exc = AITeddyBearException("Test error")
        
        assert str(exc) == "Test error"
        assert exc.error_code == "ai_teddybear_error"
        assert exc.context == {}

    def test_base_exception_with_context(self):
        """Test base exception with context."""
        context = {"user_id": "123", "action": "test"}
        exc = AITeddyBearException("Test error", context=context)
        
        assert exc.context == context

    def test_to_dict_method(self):
        """Test exception to dictionary conversion."""
        context = {"detail": "test"}
        exc = AITeddyBearException("Test error", context=context)
        
        result = exc.to_dict()
        
        assert result["error_code"] == "ai_teddybear_error"
        assert result["message"] == "Test error"
        assert result["context"] == context

    def test_default_message_from_docstring(self):
        """Test default message from class docstring."""
        exc = AITeddyBearException()
        
        # Should use class docstring as default message
        assert "Base exception" in str(exc)


class TestAuthenticationErrors:
    """Test authentication-related exceptions."""

    def test_authentication_error(self):
        """Test authentication error."""
        exc = AuthenticationError("Invalid credentials")
        
        assert exc.error_code == "auth_failed"
        assert str(exc) == "Invalid credentials"
        assert isinstance(exc, AITeddyBearException)

    def test_invalid_token_error(self):
        """Test invalid token error."""
        exc = InvalidTokenError("Token expired")
        
        assert exc.error_code == "invalid_token"
        assert isinstance(exc, AuthenticationError)

    def test_authorization_error(self):
        """Test authorization error."""
        exc = AuthorizationError("Access denied")
        
        assert exc.error_code == "not_authorized"
        assert str(exc) == "Access denied"


class TestSafetyViolationError:
    """Test safety violation exception."""

    def test_safety_violation_basic(self):
        """Test basic safety violation."""
        exc = SafetyViolationError("Inappropriate content")
        
        assert exc.error_code == "safety_violation"
        assert str(exc) == "Inappropriate content"
        assert exc.violations == []

    def test_safety_violation_with_violations(self):
        """Test safety violation with specific violations."""
        violations = ["violence", "inappropriate_language"]
        exc = SafetyViolationError(
            "Content blocked", 
            violations=violations,
            context={"severity": "high"}
        )
        
        assert exc.violations == violations
        assert exc.context["violations"] == violations
        assert exc.context["severity"] == "high"

    def test_safety_violation_default_message(self):
        """Test safety violation with default message."""
        exc = SafetyViolationError()
        
        assert "violates child safety rules" in str(exc)


class TestValidationError:
    """Test validation exception."""

    def test_validation_error_basic(self):
        """Test basic validation error."""
        exc = ValidationError("Invalid data")
        
        assert exc.error_code == "validation_error"
        assert str(exc) == "Invalid data"
        assert exc.errors == {}

    def test_validation_error_with_field_errors(self):
        """Test validation error with field-specific errors."""
        errors = {
            "email": "Invalid email format",
            "age": "Age must be between 3 and 13"
        }
        exc = ValidationError("Validation failed", errors=errors)
        
        assert exc.errors == errors
        assert exc.context["field_errors"] == errors

    def test_validation_error_default_message(self):
        """Test validation error with default message."""
        exc = ValidationError()
        
        assert "validation failed" in str(exc).lower()


class TestResourceNotFoundError:
    """Test resource not found exception."""

    def test_resource_not_found_basic(self):
        """Test basic resource not found."""
        exc = ResourceNotFoundError("Resource missing")
        
        assert exc.error_code == "resource_not_found"
        assert str(exc) == "Resource missing"

    def test_resource_not_found_with_details(self):
        """Test resource not found with type and ID."""
        exc = ResourceNotFoundError(
            "User not found",
            resource_type="user",
            resource_id="123"
        )
        
        assert "[user:123]" in str(exc)
        assert exc.context["resource_type"] == "user"
        assert exc.context["resource_id"] == "123"

    def test_resource_not_found_partial_details(self):
        """Test resource not found with only type."""
        exc = ResourceNotFoundError(
            resource_type="conversation"
        )
        
        assert exc.context["resource_type"] == "conversation"
        assert "resource_id" not in exc.context


class TestRateLimitExceeded:
    """Test rate limit exception."""

    def test_rate_limit_basic(self):
        """Test basic rate limit exceeded."""
        exc = RateLimitExceeded("Too many requests")
        
        assert exc.error_code == "rate_limit_exceeded"
        assert str(exc) == "Too many requests"
        assert exc.retry_after is None

    def test_rate_limit_with_retry_after(self):
        """Test rate limit with retry after."""
        exc = RateLimitExceeded("Rate limit exceeded", retry_after=60)
        
        assert exc.retry_after == 60
        assert exc.context["retry_after"] == 60

    def test_rate_limit_default_message(self):
        """Test rate limit with default message."""
        exc = RateLimitExceeded(retry_after=30)
        
        assert "rate limit" in str(exc).lower()
        assert exc.retry_after == 30


class TestConfigurationError:
    """Test configuration exception."""

    def test_configuration_error_basic(self):
        """Test basic configuration error."""
        exc = ConfigurationError("Missing config")
        
        assert exc.error_code == "configuration_error"
        assert str(exc) == "Missing config"
        assert exc.config_key is None

    def test_configuration_error_with_key(self):
        """Test configuration error with config key."""
        exc = ConfigurationError(
            "Invalid database URL",
            config_key="DATABASE_URL"
        )
        
        assert exc.config_key == "DATABASE_URL"
        assert exc.context["config_key"] == "DATABASE_URL"

    def test_configuration_error_default_message(self):
        """Test configuration error with default message."""
        exc = ConfigurationError(config_key="API_KEY")
        
        assert "configuration error" in str(exc).lower()
        assert exc.config_key == "API_KEY"


class TestServiceUnavailableError:
    """Test service unavailable exception."""

    def test_service_unavailable_basic(self):
        """Test basic service unavailable."""
        exc = ServiceUnavailableError("Service down")
        
        assert exc.error_code == "service_unavailable"
        assert str(exc) == "Service down"
        assert exc.service is None

    def test_service_unavailable_with_service(self):
        """Test service unavailable with service name."""
        exc = ServiceUnavailableError(
            "OpenAI API unavailable",
            service="openai"
        )
        
        assert exc.service == "openai"
        assert exc.context["service"] == "openai"


class TestSpecificExceptions:
    """Test specific domain exceptions."""

    def test_conversation_not_found(self):
        """Test conversation not found exception."""
        exc = ConversationNotFoundError("Conversation missing")
        
        assert exc.error_code == "conversation_not_found"
        assert isinstance(exc, AITeddyBearException)

    def test_child_not_found(self):
        """Test child not found exception."""
        exc = ChildNotFoundError("Child profile missing")
        
        assert exc.error_code == "child_not_found"
        assert isinstance(exc, AITeddyBearException)

    def test_external_service_error(self):
        """Test external service error."""
        exc = ExternalServiceError("API call failed")
        
        assert exc.error_code == "external_service_error"
        assert isinstance(exc, AITeddyBearException)

    def test_child_safety_violation(self):
        """Test child safety violation (alias)."""
        exc = ChildSafetyViolation("Unsafe content")
        
        assert exc.error_code == "child_safety_violation"
        assert isinstance(exc, SafetyViolationError)

    def test_coppa_violation(self):
        """Test COPPA violation."""
        exc = COPPAViolation("COPPA compliance issue")
        
        assert exc.error_code == "coppa_violation"
        assert isinstance(exc, AITeddyBearException)

    def test_security_violation(self):
        """Test security violation."""
        exc = SecurityViolation("Security breach detected")
        
        assert exc.error_code == "security_violation"
        assert isinstance(exc, AITeddyBearException)


class TestExceptionInheritance:
    """Test exception inheritance hierarchy."""

    def test_all_inherit_from_base(self):
        """Test all exceptions inherit from base."""
        exceptions = [
            AuthenticationError,
            InvalidTokenError,
            AuthorizationError,
            SafetyViolationError,
            ValidationError,
            ResourceNotFoundError,
            RateLimitExceeded,
            ConfigurationError,
            ServiceUnavailableError,
            COPPAViolation,
            SecurityViolation
        ]
        
        for exc_class in exceptions:
            exc = exc_class("test")
            assert isinstance(exc, AITeddyBearException)

    def test_authentication_hierarchy(self):
        """Test authentication exception hierarchy."""
        exc = InvalidTokenError("test")
        
        assert isinstance(exc, InvalidTokenError)
        assert isinstance(exc, AuthenticationError)
        assert isinstance(exc, AITeddyBearException)

    def test_safety_hierarchy(self):
        """Test safety exception hierarchy."""
        exc = ChildSafetyViolation("test")
        
        assert isinstance(exc, ChildSafetyViolation)
        assert isinstance(exc, SafetyViolationError)
        assert isinstance(exc, AITeddyBearException)


class TestExceptionSerialization:
    """Test exception serialization for API responses."""

    def test_simple_exception_to_dict(self):
        """Test simple exception serialization."""
        exc = AuthenticationError("Login failed")
        result = exc.to_dict()
        
        expected = {
            "error_code": "auth_failed",
            "message": "Login failed",
            "context": {}
        }
        assert result == expected

    def test_complex_exception_to_dict(self):
        """Test complex exception serialization."""
        violations = ["violence", "inappropriate"]
        context = {"severity": "high", "user_id": "123"}
        
        exc = SafetyViolationError(
            "Content blocked",
            violations=violations,
            context=context
        )
        result = exc.to_dict()
        
        assert result["error_code"] == "safety_violation"
        assert result["message"] == "Content blocked"
        assert result["context"]["violations"] == violations
        assert result["context"]["severity"] == "high"
        assert result["context"]["user_id"] == "123"

    def test_validation_error_to_dict(self):
        """Test validation error serialization."""
        errors = {"email": "Invalid format", "age": "Too young"}
        exc = ValidationError("Invalid input", errors=errors)
        result = exc.to_dict()
        
        assert result["error_code"] == "validation_error"
        assert result["context"]["field_errors"] == errors