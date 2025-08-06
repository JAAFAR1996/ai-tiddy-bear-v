"""
Unit tests for interface exceptions module.
Tests custom exception classes and their behavior for clean architecture compliance.
"""

import pytest
from unittest.mock import Mock, patch

from src.interfaces.exceptions import (
    IDatabaseError,
    IValidationError,
    IAuthenticationError,
    IAuthorizationError,
    IServiceError,
    IConfigurationError,
    DatabaseError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ServiceError,
    ConfigurationError,
)


class TestIDatabaseError:
    """Test IDatabaseError interface exception."""

    def test_database_error_basic_initialization(self):
        """Test IDatabaseError initialization with basic message."""
        message = "Database connection failed"
        error = IDatabaseError(message)
        
        assert str(error) == message
        assert error.operation is None
        assert error.details == {}

    def test_database_error_with_operation(self):
        """Test IDatabaseError initialization with operation."""
        message = "Query execution failed"
        operation = "SELECT"
        error = IDatabaseError(message, operation=operation)
        
        assert str(error) == message
        assert error.operation == operation
        assert error.details == {}

    def test_database_error_with_details(self):
        """Test IDatabaseError initialization with details."""
        message = "Transaction rollback failed"
        details = {
            "table": "conversations",
            "timeout": 30,
            "retry_count": 3
        }
        error = IDatabaseError(message, details=details)
        
        assert str(error) == message
        assert error.operation is None
        assert error.details == details

    def test_database_error_with_all_parameters(self):
        """Test IDatabaseError initialization with all parameters."""
        message = "Constraint violation"
        operation = "INSERT"
        details = {
            "constraint": "unique_child_id",
            "table": "children",
            "value": "child123"
        }
        error = IDatabaseError(message, operation=operation, details=details)
        
        assert str(error) == message
        assert error.operation == operation
        assert error.details == details

    def test_database_error_empty_details_default(self):
        """Test IDatabaseError provides empty dict as default for details."""
        error = IDatabaseError("Test error", details=None)
        
        assert error.details == {}
        assert isinstance(error.details, dict)

    def test_database_error_inheritance(self):
        """Test IDatabaseError inherits from Exception."""
        error = IDatabaseError("Test error")
        
        assert isinstance(error, Exception)
        assert isinstance(error, IDatabaseError)

    def test_database_error_can_be_raised(self):
        """Test IDatabaseError can be raised and caught."""
        with pytest.raises(IDatabaseError) as exc_info:
            raise IDatabaseError("Database error", operation="CONNECT")
        
        assert str(exc_info.value) == "Database error"
        assert exc_info.value.operation == "CONNECT"

    def test_database_error_with_unicode_message(self):
        """Test IDatabaseError with unicode characters in message."""
        message = "数据库错误 - Database error"
        error = IDatabaseError(message)
        
        assert str(error) == message

    def test_database_error_with_complex_details(self):
        """Test IDatabaseError with complex details structure."""
        details = {
            "connection_info": {
                "host": "localhost",
                "port": 5432,
                "database": "teddy_bear_db"
            },
            "query_params": ["child123", "parent456"],
            "timing": {
                "start_time": "2025-07-29T10:00:00Z",
                "duration_ms": 5000
            }
        }
        error = IDatabaseError("Complex query failed", details=details)
        
        assert error.details == details
        assert error.details["connection_info"]["host"] == "localhost"


class TestIValidationError:
    """Test IValidationError interface exception."""

    def test_validation_error_basic_initialization(self):
        """Test IValidationError initialization with basic message."""
        message = "Validation failed"
        error = IValidationError(message)
        
        assert str(error) == message
        assert error.field is None
        assert error.value is None

    def test_validation_error_with_field(self):
        """Test IValidationError initialization with field."""
        message = "Invalid email format"
        field = "email"
        error = IValidationError(message, field=field)
        
        assert str(error) == message
        assert error.field == field
        assert error.value is None

    def test_validation_error_with_value(self):
        """Test IValidationError initialization with value."""
        message = "Age must be between 3 and 13"
        value = 15
        error = IValidationError(message, value=value)
        
        assert str(error) == message
        assert error.field is None
        assert error.value == value

    def test_validation_error_with_all_parameters(self):
        """Test IValidationError initialization with all parameters."""
        message = "Invalid child age for COPPA compliance"
        field = "child_age"
        value = 2
        error = IValidationError(message, field=field, value=value)
        
        assert str(error) == message
        assert error.field == field
        assert error.value == value

    def test_validation_error_inheritance(self):
        """Test IValidationError inherits from Exception."""
        error = IValidationError("Test error")
        
        assert isinstance(error, Exception)
        assert isinstance(error, IValidationError)

    def test_validation_error_can_be_raised(self):
        """Test IValidationError can be raised and caught."""
        with pytest.raises(IValidationError) as exc_info:
            raise IValidationError("Invalid input", field="username", value="")
        
        assert str(exc_info.value) == "Invalid input"
        assert exc_info.value.field == "username"
        assert exc_info.value.value == ""

    def test_validation_error_with_none_value(self):
        """Test IValidationError with None value."""
        error = IValidationError("Required field missing", field="name", value=None)
        
        assert error.field == "name"
        assert error.value is None

    def test_validation_error_with_complex_value(self):
        """Test IValidationError with complex value types."""
        complex_value = {"nested": {"data": [1, 2, 3]}}
        error = IValidationError("Invalid structure", field="config", value=complex_value)
        
        assert error.field == "config"
        assert error.value == complex_value

    def test_validation_error_coppa_scenario(self):
        """Test IValidationError in COPPA compliance scenario."""
        message = "Child data validation failed"
        field = "child_birth_date"
        value = "2024-01-01"  # Too young for COPPA
        error = IValidationError(message, field=field, value=value)
        
        assert str(error) == message
        assert error.field == field
        assert error.value == value


class TestIAuthenticationError:
    """Test IAuthenticationError interface exception."""

    def test_authentication_error_basic_initialization(self):
        """Test IAuthenticationError initialization with basic message."""
        message = "Authentication failed"
        error = IAuthenticationError(message)
        
        assert str(error) == message
        assert error.reason is None

    def test_authentication_error_with_reason(self):
        """Test IAuthenticationError initialization with reason."""
        message = "Login failed"
        reason = "invalid_credentials"
        error = IAuthenticationError(message, reason=reason)
        
        assert str(error) == message
        assert error.reason == reason

    def test_authentication_error_inheritance(self):
        """Test IAuthenticationError inherits from Exception."""
        error = IAuthenticationError("Test error")
        
        assert isinstance(error, Exception)
        assert isinstance(error, IAuthenticationError)

    def test_authentication_error_can_be_raised(self):
        """Test IAuthenticationError can be raised and caught."""
        with pytest.raises(IAuthenticationError) as exc_info:
            raise IAuthenticationError("Token expired", reason="token_expired")
        
        assert str(exc_info.value) == "Token expired"
        assert exc_info.value.reason == "token_expired"

    def test_authentication_error_common_reasons(self):
        """Test IAuthenticationError with common authentication failure reasons."""
        reasons = [
            "invalid_password",
            "user_not_found",
            "account_locked",
            "token_expired",
            "insufficient_privileges",
            "mfa_required"
        ]
        
        for reason in reasons:
            error = IAuthenticationError("Authentication failed", reason=reason)
            assert error.reason == reason

    def test_authentication_error_empty_reason(self):
        """Test IAuthenticationError with empty reason."""
        error = IAuthenticationError("Auth failed", reason="")
        
        assert error.reason == ""

    def test_authentication_error_parent_child_scenario(self):
        """Test IAuthenticationError in parent-child access scenario."""
        message = "Parent authentication required for child data access"
        reason = "parent_consent_verification_failed"
        error = IAuthenticationError(message, reason=reason)
        
        assert str(error) == message
        assert error.reason == reason


class TestIAuthorizationError:
    """Test IAuthorizationError interface exception."""

    def test_authorization_error_basic_initialization(self):
        """Test IAuthorizationError initialization with basic message."""
        message = "Access denied"
        error = IAuthorizationError(message)
        
        assert str(error) == message
        assert error.resource is None
        assert error.action is None

    def test_authorization_error_with_resource(self):
        """Test IAuthorizationError initialization with resource."""
        message = "Insufficient permissions"
        resource = "child_data"
        error = IAuthorizationError(message, resource=resource)
        
        assert str(error) == message
        assert error.resource == resource
        assert error.action is None

    def test_authorization_error_with_action(self):
        """Test IAuthorizationError initialization with action."""
        message = "Operation not allowed"
        action = "delete"
        error = IAuthorizationError(message, action=action)
        
        assert str(error) == message
        assert error.resource is None
        assert error.action == action

    def test_authorization_error_with_all_parameters(self):
        """Test IAuthorizationError initialization with all parameters."""
        message = "Cannot delete child conversation data"
        resource = "conversation"
        action = "delete"
        error = IAuthorizationError(message, resource=resource, action=action)
        
        assert str(error) == message
        assert error.resource == resource
        assert error.action == action

    def test_authorization_error_inheritance(self):
        """Test IAuthorizationError inherits from Exception."""
        error = IAuthorizationError("Test error")
        
        assert isinstance(error, Exception)
        assert isinstance(error, IAuthorizationError)

    def test_authorization_error_can_be_raised(self):
        """Test IAuthorizationError can be raised and caught."""
        with pytest.raises(IAuthorizationError) as exc_info:
            raise IAuthorizationError("Access denied", resource="admin_panel", action="read")
        
        assert str(exc_info.value) == "Access denied"
        assert exc_info.value.resource == "admin_panel"
        assert exc_info.value.action == "read"

    def test_authorization_error_coppa_scenario(self):
        """Test IAuthorizationError in COPPA compliance scenario."""
        message = "Child cannot access other child's data"
        resource = "other_child_conversation"
        action = "read"
        error = IAuthorizationError(message, resource=resource, action=action)
        
        assert str(error) == message
        assert error.resource == resource
        assert error.action == action

    def test_authorization_error_parent_scenario(self):
        """Test IAuthorizationError in parent access scenario."""
        message = "Parent not authorized to access this child's data"
        resource = "child_messages"
        action = "view"
        error = IAuthorizationError(message, resource=resource, action=action)
        
        assert str(error) == message
        assert error.resource == resource
        assert error.action == action


class TestIServiceError:
    """Test IServiceError interface exception."""

    def test_service_error_basic_initialization(self):
        """Test IServiceError initialization with basic message."""
        message = "Service unavailable"
        error = IServiceError(message)
        
        assert str(error) == message
        assert error.service_name is None
        assert error.error_code is None

    def test_service_error_with_service_name(self):
        """Test IServiceError initialization with service name."""
        message = "OpenAI API call failed"
        service_name = "openai_chat_service"
        error = IServiceError(message, service_name=service_name)
        
        assert str(error) == message
        assert error.service_name == service_name
        assert error.error_code is None

    def test_service_error_with_error_code(self):
        """Test IServiceError initialization with error code."""
        message = "Rate limit exceeded"
        error_code = "RATE_LIMIT_429"
        error = IServiceError(message, error_code=error_code)
        
        assert str(error) == message
        assert error.service_name is None
        assert error.error_code == error_code

    def test_service_error_with_all_parameters(self):
        """Test IServiceError initialization with all parameters."""
        message = "Safety service validation failed"
        service_name = "child_safety_service"
        error_code = "SAFETY_VIOLATION_001"
        error = IServiceError(message, service_name=service_name, error_code=error_code)
        
        assert str(error) == message
        assert error.service_name == service_name
        assert error.error_code == error_code

    def test_service_error_inheritance(self):
        """Test IServiceError inherits from Exception."""
        error = IServiceError("Test error")
        
        assert isinstance(error, Exception)
        assert isinstance(error, IServiceError)

    def test_service_error_can_be_raised(self):
        """Test IServiceError can be raised and caught."""
        with pytest.raises(IServiceError) as exc_info:
            raise IServiceError("Service down", service_name="auth_service", error_code="SVC_001")
        
        assert str(exc_info.value) == "Service down"
        assert exc_info.value.service_name == "auth_service"
        assert exc_info.value.error_code == "SVC_001"

    def test_service_error_ai_service_scenario(self):
        """Test IServiceError in AI service scenario."""
        message = "AI response generation failed"
        service_name = "chat_completion_service"
        error_code = "AI_GEN_TIMEOUT"
        error = IServiceError(message, service_name=service_name, error_code=error_code)
        
        assert str(error) == message
        assert error.service_name == service_name
        assert error.error_code == error_code

    def test_service_error_security_service_scenario(self):
        """Test IServiceError in security service scenario."""
        message = "Security threat detection service failed"
        service_name = "threat_detection_service"
        error_code = "SEC_SCAN_FAILED"
        error = IServiceError(message, service_name=service_name, error_code=error_code)
        
        assert str(error) == message
        assert error.service_name == service_name
        assert error.error_code == error_code


class TestIConfigurationError:
    """Test IConfigurationError interface exception."""

    def test_configuration_error_basic_initialization(self):
        """Test IConfigurationError initialization with basic message."""
        message = "Configuration error"
        error = IConfigurationError(message)
        
        assert str(error) == message
        assert error.key is None

    def test_configuration_error_with_key(self):
        """Test IConfigurationError initialization with key."""
        message = "Missing required configuration"
        key = "OPENAI_API_KEY"
        error = IConfigurationError(message, key=key)
        
        assert str(error) == message
        assert error.key == key

    def test_configuration_error_inheritance(self):
        """Test IConfigurationError inherits from Exception."""
        error = IConfigurationError("Test error")
        
        assert isinstance(error, Exception)
        assert isinstance(error, IConfigurationError)

    def test_configuration_error_can_be_raised(self):
        """Test IConfigurationError can be raised and caught."""
        with pytest.raises(IConfigurationError) as exc_info:
            raise IConfigurationError("Invalid config value", key="JWT_SECRET_KEY")
        
        assert str(exc_info.value) == "Invalid config value"
        assert exc_info.value.key == "JWT_SECRET_KEY"

    def test_configuration_error_common_keys(self):
        """Test IConfigurationError with common configuration keys."""
        common_keys = [
            "DATABASE_URL",
            "REDIS_URL",
            "SECRET_KEY",
            "JWT_SECRET_KEY",
            "OPENAI_API_KEY",
            "COPPA_ENCRYPTION_KEY"
        ]
        
        for key in common_keys:
            error = IConfigurationError("Missing configuration", key=key)
            assert error.key == key

    def test_configuration_error_empty_key(self):
        """Test IConfigurationError with empty key."""
        error = IConfigurationError("Config error", key="")
        
        assert error.key == ""

    def test_configuration_error_coppa_scenario(self):
        """Test IConfigurationError in COPPA compliance scenario."""
        message = "COPPA encryption key not configured properly"
        key = "COPPA_ENCRYPTION_KEY"
        error = IConfigurationError(message, key=key)
        
        assert str(error) == message
        assert error.key == key


class TestExceptionAliases:
    """Test exception aliases for simplified usage."""

    def test_database_error_alias(self):
        """Test DatabaseError is alias for IDatabaseError."""
        assert DatabaseError is IDatabaseError
        
        error = DatabaseError("Test error")
        assert isinstance(error, IDatabaseError)

    def test_validation_error_alias(self):
        """Test ValidationError is alias for IValidationError."""
        assert ValidationError is IValidationError
        
        error = ValidationError("Test error")
        assert isinstance(error, IValidationError)

    def test_authentication_error_alias(self):
        """Test AuthenticationError is alias for IAuthenticationError."""
        assert AuthenticationError is IAuthenticationError
        
        error = AuthenticationError("Test error")
        assert isinstance(error, IAuthenticationError)

    def test_authorization_error_alias(self):
        """Test AuthorizationError is alias for IAuthorizationError."""
        assert AuthorizationError is IAuthorizationError
        
        error = AuthorizationError("Test error")
        assert isinstance(error, IAuthorizationError)

    def test_service_error_alias(self):
        """Test ServiceError is alias for IServiceError."""
        assert ServiceError is IServiceError
        
        error = ServiceError("Test error")
        assert isinstance(error, IServiceError)

    def test_configuration_error_alias(self):
        """Test ConfigurationError is alias for IConfigurationError."""
        assert ConfigurationError is IConfigurationError
        
        error = ConfigurationError("Test error")
        assert isinstance(error, IConfigurationError)

    def test_aliases_can_be_raised(self):
        """Test that aliases can be raised and caught as expected."""
        # Test raising and catching with alias
        with pytest.raises(DatabaseError):
            raise DatabaseError("DB error")
        
        with pytest.raises(ValidationError):
            raise ValidationError("Validation error")
        
        # Test that aliases catch the interface types
        with pytest.raises(DatabaseError):
            raise IDatabaseError("DB error")


class TestExceptionIntegration:
    """Test exception integration scenarios."""

    def test_exception_hierarchy_polymorphism(self):
        """Test exception hierarchy supports polymorphism."""
        errors = [
            IDatabaseError("DB error"),
            IValidationError("Validation error"),
            IAuthenticationError("Auth error"),
            IAuthorizationError("Authz error"),
            IServiceError("Service error"),
            IConfigurationError("Config error")
        ]
        
        # All should be instances of Exception
        for error in errors:
            assert isinstance(error, Exception)
        
        # Test that they can be caught as generic exceptions
        for error in errors:
            try:
                raise error
            except Exception as e:
                assert e is error

    def test_exception_chaining(self):
        """Test exception chaining scenarios."""
        # Test exception chaining
        try:
            try:
                raise IDatabaseError("Original DB error", operation="SELECT")
            except IDatabaseError as db_error:
                raise IServiceError("Service failed due to database") from db_error
        except IServiceError as service_error:
            assert service_error.__cause__ is not None
            assert isinstance(service_error.__cause__, IDatabaseError)
            assert service_error.__cause__.operation == "SELECT"

    def test_exception_context_preservation(self):
        """Test that exception context is preserved."""
        # Database error with full context
        db_error = IDatabaseError(
            "Connection timeout",
            operation="CONNECT",
            details={"host": "localhost", "timeout": 30}
        )
        
        # Validation error with full context
        val_error = IValidationError(
            "Invalid age",
            field="child_age",
            value=15
        )
        
        # Authorization error with full context
        auth_error = IAuthorizationError(
            "Access denied",
            resource="child_data",
            action="delete"
        )
        
        # Test that all context is preserved when raised and caught
        try:
            raise db_error
        except IDatabaseError as e:
            assert e.operation == "CONNECT"
            assert e.details["host"] == "localhost"
        
        try:
            raise val_error
        except IValidationError as e:
            assert e.field == "child_age"
            assert e.value == 15
        
        try:
            raise auth_error
        except IAuthorizationError as e:
            assert e.resource == "child_data"
            assert e.action == "delete"


class TestExceptionChildSafetyScenarios:
    """Test exceptions in child safety and COPPA compliance scenarios."""

    def test_coppa_validation_error(self):
        """Test validation error for COPPA compliance."""
        error = ValidationError(
            "Child age does not meet COPPA requirements",
            field="birth_date",
            value="2023-01-01"  # Too young
        )
        
        assert "COPPA" in str(error)
        assert error.field == "birth_date"
        assert error.value == "2023-01-01"

    def test_child_data_authorization_error(self):
        """Test authorization error for child data access."""
        error = AuthorizationError(
            "Child cannot access other child's conversation data",
            resource="conversation_history",
            action="read"
        )
        
        assert "child" in str(error).lower()
        assert error.resource == "conversation_history"
        assert error.action == "read"

    def test_parent_authentication_error(self):
        """Test authentication error for parent verification."""
        error = AuthenticationError(
            "Parent identity verification failed for child data access",
            reason="invalid_parent_token"
        )
        
        assert "parent" in str(error).lower()
        assert error.reason == "invalid_parent_token"

    def test_safety_service_error(self):
        """Test service error for child safety service."""
        error = ServiceError(
            "Content safety check failed - blocking unsafe content",
            service_name="child_safety_service",
            error_code="UNSAFE_CONTENT_DETECTED"
        )
        
        assert "safety" in str(error).lower()
        assert error.service_name == "child_safety_service"
        assert error.error_code == "UNSAFE_CONTENT_DETECTED"

    def test_security_configuration_error(self):
        """Test configuration error for security settings."""
        error = ConfigurationError(
            "Child data encryption key not properly configured",
            key="COPPA_ENCRYPTION_KEY"
        )
        
        assert "encryption" in str(error).lower()
        assert error.key == "COPPA_ENCRYPTION_KEY"

    def test_database_error_child_data_scenario(self):
        """Test database error in child data scenario."""
        error = DatabaseError(
            "Failed to store child conversation with privacy encryption",
            operation="INSERT",
            details={
                "table": "child_conversations",
                "encryption": "AES-256",
                "privacy_level": "high"
            }
        )
        
        assert "child conversation" in str(error).lower()
        assert error.operation == "INSERT"
        assert error.details["encryption"] == "AES-256"


class TestExceptionEdgeCases:
    """Test exception edge cases and error conditions."""

    def test_exceptions_with_none_parameters(self):
        """Test exceptions with None parameters."""
        # All exceptions should handle None gracefully
        db_error = IDatabaseError("Error", operation=None, details=None)
        val_error = IValidationError("Error", field=None, value=None)
        auth_error = IAuthenticationError("Error", reason=None)
        authz_error = IAuthorizationError("Error", resource=None, action=None)
        svc_error = IServiceError("Error", service_name=None, error_code=None)
        cfg_error = IConfigurationError("Error", key=None)
        
        assert db_error.operation is None
        assert db_error.details == {}
        assert val_error.field is None
        assert val_error.value is None
        assert auth_error.reason is None
        assert authz_error.resource is None
        assert authz_error.action is None
        assert svc_error.service_name is None
        assert svc_error.error_code is None
        assert cfg_error.key is None

    def test_exceptions_with_empty_strings(self):
        """Test exceptions with empty string parameters."""
        errors = [
            IDatabaseError("", operation="", details={}),
            IValidationError("", field="", value=""),
            IAuthenticationError("", reason=""),
            IAuthorizationError("", resource="", action=""),
            IServiceError("", service_name="", error_code=""),
            IConfigurationError("", key="")
        ]
        
        for error in errors:
            assert str(error) == ""

    def test_exceptions_with_unicode_parameters(self):
        """Test exceptions with unicode parameters."""
        db_error = IDatabaseError("数据库错误", operation="查询")
        val_error = IValidationError("验证错误", field="年龄")
        
        assert "数据库错误" in str(db_error)
        assert db_error.operation == "查询"
        assert val_error.field == "年龄"

    def test_exception_repr_methods(self):
        """Test exception string representations."""
        error = IDatabaseError("Test error", operation="SELECT", details={"table": "test"})
        
        # Should be able to represent as string
        str_repr = str(error)
        assert "Test error" in str_repr
        
        # Should be able to represent via repr
        repr_str = repr(error)
        assert isinstance(repr_str, str)

    def test_exception_with_very_long_messages(self):
        """Test exceptions with very long messages."""
        long_message = "A" * 10000
        error = IDatabaseError(long_message)
        
        assert str(error) == long_message
        assert len(str(error)) == 10000


class TestExceptionDocumentationCompliance:
    """Test that exceptions comply with clean architecture principles."""

    def test_all_exceptions_documented(self):
        """Test that all exception classes have docstrings."""
        exception_classes = [
            IDatabaseError,
            IValidationError,
            IAuthenticationError,
            IAuthorizationError,
            IServiceError,
            IConfigurationError
        ]
        
        for exc_class in exception_classes:
            assert exc_class.__doc__ is not None
            assert len(exc_class.__doc__.strip()) > 0
            assert "Interface for" in exc_class.__doc__

    def test_exception_interface_naming(self):
        """Test that exception interfaces follow naming convention."""
        interface_exceptions = [
            IDatabaseError,
            IValidationError,
            IAuthenticationError,
            IAuthorizationError,
            IServiceError,
            IConfigurationError
        ]
        
        for exc_class in interface_exceptions:
            assert exc_class.__name__.startswith("I")
            assert exc_class.__name__.endswith("Error")

    def test_exception_aliases_correct(self):
        """Test that exception aliases are correctly mapped."""
        alias_mappings = [
            (DatabaseError, IDatabaseError),
            (ValidationError, IValidationError),
            (AuthenticationError, IAuthenticationError),
            (AuthorizationError, IAuthorizationError),
            (ServiceError, IServiceError),
            (ConfigurationError, IConfigurationError)
        ]
        
        for alias, interface in alias_mappings:
            assert alias is interface
            assert alias.__name__ == interface.__name__.replace("I", "", 1)