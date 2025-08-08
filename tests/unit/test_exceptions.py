"""
Comprehensive tests for exception handling across all layers.
"""

import pytest
from unittest.mock import Mock
from src.core.exceptions import (
    AITeddyBearException,
    ValidationError,
    SafetyViolationError,
    ConfigurationError,
    ResourceNotFoundError,
)
from src.infrastructure.exceptions import (
    get_exception_info,
    create_error_response,
    map_exception,
    DatabaseError,
    AIServiceError,
)
from src.interfaces.exceptions import (
    IDatabaseError,
    IValidationError,
    IServiceError,
)


class TestCoreExceptions:
    """Test core exception functionality."""

    def test_base_exception_structure(self):
        """Test AITeddyBearException basic structure."""
        exc = AITeddyBearException("Test error", context={"key": "value"})
        
        assert str(exc) == "Test error"
        assert exc.error_code == "ai_teddybear_error"
        assert exc.context == {"key": "value"}
        
        # Test to_dict method
        result = exc.to_dict()
        expected = {
            "error_code": "ai_teddybear_error",
            "message": "Test error",
            "context": {"key": "value"}
        }
        assert result == expected

    def test_validation_error_with_field_errors(self):
        """Test ValidationError with field-specific errors."""
        errors = {"email": "Invalid format", "age": "Must be positive"}
        exc = ValidationError("Validation failed", errors=errors)
        
        assert exc.error_code == "validation_error"
        assert exc.errors == errors
        assert exc.context["field_errors"] == errors

    def test_safety_violation_with_violations(self):
        """Test SafetyViolationError with violation details."""
        violations = ["inappropriate_language", "adult_content"]
        exc = SafetyViolationError("Content unsafe", violations=violations)
        
        assert exc.error_code == "safety_violation"
        assert exc.violations == violations
        assert exc.context["violations"] == violations

    def test_resource_not_found_with_details(self):
        """Test ResourceNotFoundError with resource details."""
        exc = ResourceNotFoundError(
            "Resource missing",
            resource_type="user",
            resource_id="123"
        )
        
        assert exc.error_code == "resource_not_found"
        assert exc.context["resource_type"] == "user"
        assert exc.context["resource_id"] == "123"
        assert "[user:123]" in str(exc)


class TestInfrastructureExceptions:
    """Test infrastructure exception utilities."""

    def test_exception_mapping(self):
        """Test mapping of standard Python exceptions."""
        # Test ValueError mapping
        original = ValueError("Invalid value")
        mapped = map_exception(original)
        
        assert isinstance(mapped, ValidationError)
        assert str(mapped) == "Invalid value"
        assert mapped.context["original_exception"] == "ValueError"

    def test_exception_mapping_with_custom_message(self):
        """Test exception mapping with custom message."""
        original = KeyError("missing_key")
        mapped = map_exception(original, "Configuration key missing")
        
        assert isinstance(mapped, ConfigurationError)
        assert str(mapped) == "Configuration key missing"

    def test_get_exception_info_custom(self):
        """Test get_exception_info with custom exception."""
        exc = ValidationError("Test error", context={"field": "email"})
        info = get_exception_info(exc)
        
        expected = {
            "error_code": "validation_error",
            "message": "Test error",
            "context": {"field": "email"}
        }
        assert info == expected

    def test_get_exception_info_standard(self):
        """Test get_exception_info with standard Python exception."""
        exc = ValueError("Standard error")
        info = get_exception_info(exc)
        
        assert info["error_code"] == "UNHANDLED_ERROR"
        assert info["message"] == "An unexpected error occurred"
        assert info["context"]["exception_type"] == "ValueError"
        assert info["context"]["original_message"] == "Standard error"

    def test_create_error_response(self):
        """Test error response creation."""
        exc = ValidationError("Test validation error")
        response = create_error_response(exc)
        
        assert "error" in response
        assert response["error"]["error_code"] == "validation_error"
        assert response["error"]["message"] == "Test validation error"

    def test_create_error_response_with_debug(self):
        """Test error response with debug information."""
        exc = ValueError("Standard error")
        response = create_error_response(exc, include_debug=True)
        
        assert "error" in response
        assert "debug" in response["error"]["context"]
        assert "traceback" in response["error"]["context"]["debug"]


class TestInterfaceExceptions:
    """Test interface exception contracts."""

    def test_database_error_interface(self):
        """Test IDatabaseError interface."""
        details = {"query": "SELECT * FROM users", "error_code": "23505"}
        exc = IDatabaseError(
            "Database constraint violation",
            operation="INSERT",
            details=details
        )
        
        assert str(exc) == "Database constraint violation"
        assert exc.operation == "INSERT"
        assert exc.details == details

    def test_validation_error_interface(self):
        """Test IValidationError interface."""
        exc = IValidationError(
            "Invalid email format",
            field="email",
            value="invalid-email"
        )
        
        assert str(exc) == "Invalid email format"
        assert exc.field == "email"
        assert exc.value == "invalid-email"

    def test_service_error_interface(self):
        """Test IServiceError interface."""
        exc = IServiceError(
            "AI service unavailable",
            service_name="openai",
            error_code="503"
        )
        
        assert str(exc) == "AI service unavailable"
        assert exc.service_name == "openai"
        assert exc.error_code == "503"


class TestExceptionIntegration:
    """Test exception handling across layers."""

    def test_exception_chain_handling(self):
        """Test handling of chained exceptions."""
        try:
            # Simulate a chain of exceptions
            try:
                raise ValueError("Original error")
            except ValueError as e:
                mapped = map_exception(e, "Mapped error message")
                raise mapped from e
        except AITeddyBearException as exc:
            assert isinstance(exc, ValidationError)
            assert str(exc) == "Mapped error message"
            assert exc.__cause__ is not None
            assert isinstance(exc.__cause__, ValueError)

    def test_error_context_preservation(self):
        """Test that error context is preserved through mapping."""
        original = ConnectionError("Network timeout")
        mapped = map_exception(original)
        
        info = get_exception_info(mapped)
        assert info["context"]["original_exception"] == "ConnectionError"

    def test_comprehensive_error_response(self):
        """Test complete error response flow."""
        # Create a complex exception with context
        exc = SafetyViolationError(
            "Content contains inappropriate material",
            violations=["profanity", "violence"],
            context={"content_id": "msg_123", "severity": "high"}
        )
        
        # Create error response
        response = create_error_response(exc)
        
        # Verify complete structure
        error = response["error"]
        assert error["error_code"] == "safety_violation"
        assert error["message"] == "Content contains inappropriate material"
        assert error["context"]["violations"] == ["profanity", "violence"]
        assert error["context"]["content_id"] == "msg_123"
        assert error["context"]["severity"] == "high"


if __name__ == "__main__":
    pytest.main([__file__])