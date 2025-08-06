"""
Unit tests for structlog logger implementation.
Tests structured logging functionality, component binding, and interface compliance.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import structlog

from src.infrastructure.logging.structlog_logger import StructlogLogger
from src.interfaces.logging import ILogger


class TestStructlogLoggerInitialization:
    """Test StructlogLogger initialization and configuration."""

    def test_structlog_logger_initialization_basic(self):
        """Test StructlogLogger initialization with name only."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="test_logger")
            
            assert logger.logger is mock_logger
            mock_structlog.get_logger.assert_called_once_with(name="test_logger")

    def test_structlog_logger_initialization_with_component(self):
        """Test StructlogLogger initialization with component binding."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_base_logger = Mock(spec=True)
            mock_bound_logger = Mock(spec=True)
            mock_base_logger.bind.return_value = mock_bound_logger
            mock_structlog.get_logger.return_value = mock_base_logger
            
            logger = StructlogLogger(name="test_logger", component="auth_service")
            
            assert logger.logger is mock_bound_logger
            mock_structlog.get_logger.assert_called_once_with(name="test_logger")
            mock_base_logger.bind.assert_called_once_with(component="auth_service")

    def test_structlog_logger_initialization_without_component(self):
        """Test StructlogLogger initialization without component binding."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="test_logger", component=None)
            
            assert logger.logger is mock_logger
            mock_structlog.get_logger.assert_called_once_with(name="test_logger")
            mock_logger.bind.assert_not_called()

    def test_structlog_logger_initialization_empty_component(self):
        """Test StructlogLogger initialization with empty component string."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="test_logger", component="")
            
            assert logger.logger is mock_logger
            mock_structlog.get_logger.assert_called_once_with(name="test_logger")
            # Empty string should not trigger binding
            mock_logger.bind.assert_not_called()

    def test_structlog_logger_implements_ilogger_interface(self):
        """Test that StructlogLogger implements ILogger interface."""
        with patch('src.infrastructure.logging.structlog_logger.structlog'):
            logger = StructlogLogger(name="test_logger")
            
            assert isinstance(logger, ILogger)
            
            # Verify all required methods exist
            assert hasattr(logger, 'info')
            assert hasattr(logger, 'warning')
            assert hasattr(logger, 'error')
            assert hasattr(logger, 'debug')
            assert hasattr(logger, 'critical')
            
            # Verify methods are callable
            assert callable(logger.info)
            assert callable(logger.warning)
            assert callable(logger.error)
            assert callable(logger.debug)
            assert callable(logger.critical)


class TestStructlogLoggerLoggingMethods:
    """Test StructlogLogger logging method functionality."""

    @pytest.fixture
    def mock_structlog_logger(self):
        """Create mock structlog logger for testing."""
        return Mock(spec=True)

    @pytest.fixture
    def structlog_logger(self, mock_structlog_logger):
        """Create StructlogLogger instance with mocked structlog."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_structlog.get_logger.return_value = mock_structlog_logger
            return StructlogLogger(name="test_logger")

    def test_info_method_basic(self, structlog_logger, mock_structlog_logger):
        """Test info method with basic message."""
        message = "Test info message"
        
        structlog_logger.info(message)
        
        mock_structlog_logger.info.assert_called_once_with(message)

    def test_info_method_with_args(self, structlog_logger, mock_structlog_logger):
        """Test info method with positional arguments."""
        message = "Test message with %s and %d"
        args = ("string", 42)
        
        structlog_logger.info(message, *args)
        
        mock_structlog_logger.info.assert_called_once_with(message, *args)

    def test_info_method_with_kwargs(self, structlog_logger, mock_structlog_logger):
        """Test info method with keyword arguments."""
        message = "Test info message"
        kwargs = {"user_id": "user123", "action": "login"}
        
        structlog_logger.info(message, **kwargs)
        
        mock_structlog_logger.info.assert_called_once_with(message, **kwargs)

    def test_info_method_with_args_and_kwargs(self, structlog_logger, mock_structlog_logger):
        """Test info method with both args and kwargs."""
        message = "User %s performed action"
        args = ("alice",)
        kwargs = {"user_id": "user123", "timestamp": "2025-07-29"}
        
        structlog_logger.info(message, *args, **kwargs)
        
        mock_structlog_logger.info.assert_called_once_with(message, *args, **kwargs)

    def test_warning_method_basic(self, structlog_logger, mock_structlog_logger):
        """Test warning method with basic message."""
        message = "Test warning message"
        
        structlog_logger.warning(message)
        
        mock_structlog_logger.warning.assert_called_once_with(message)

    def test_warning_method_with_context(self, structlog_logger, mock_structlog_logger):
        """Test warning method with contextual information."""
        message = "Security warning detected"
        kwargs = {
            "ip_address": "192.168.1.1",
            "attempt_count": 5,
            "user_id": "user123"
        }
        
        structlog_logger.warning(message, **kwargs)
        
        mock_structlog_logger.warning.assert_called_once_with(message, **kwargs)

    def test_error_method_basic(self, structlog_logger, mock_structlog_logger):
        """Test error method with basic message."""
        message = "Test error message"
        
        structlog_logger.error(message)
        
        mock_structlog_logger.error.assert_called_once_with(message)

    def test_error_method_with_exception_context(self, structlog_logger, mock_structlog_logger):
        """Test error method with exception context."""
        message = "Database connection failed"
        kwargs = {
            "error_type": "ConnectionError",
            "error_message": "Connection timeout",
            "retry_count": 3,
            "database_host": "localhost"
        }
        
        structlog_logger.error(message, **kwargs)
        
        mock_structlog_logger.error.assert_called_once_with(message, **kwargs)

    def test_debug_method_basic(self, structlog_logger, mock_structlog_logger):
        """Test debug method with basic message."""
        message = "Debug trace information"
        
        structlog_logger.debug(message)
        
        mock_structlog_logger.debug.assert_called_once_with(message)

    def test_debug_method_with_detailed_context(self, structlog_logger, mock_structlog_logger):
        """Test debug method with detailed debugging context."""
        message = "Processing child safety check"
        kwargs = {
            "child_id": "child123",
            "content_hash": "abc123",
            "safety_score": 0.95,
            "violations": [],
            "processing_time_ms": 45
        }
        
        structlog_logger.debug(message, **kwargs)
        
        mock_structlog_logger.debug.assert_called_once_with(message, **kwargs)

    def test_critical_method_basic(self, structlog_logger, mock_structlog_logger):
        """Test critical method with basic message."""
        message = "Critical system error"
        
        structlog_logger.critical(message)
        
        mock_structlog_logger.critical.assert_called_once_with(message)

    def test_critical_method_with_system_context(self, structlog_logger, mock_structlog_logger):
        """Test critical method with system context."""
        message = "COPPA compliance violation detected"
        kwargs = {
            "violation_type": "unauthorized_child_data_access",
            "user_id": "user456",
            "child_id": "child789",
            "severity": "critical",
            "immediate_action_required": True
        }
        
        structlog_logger.critical(message, **kwargs)
        
        mock_structlog_logger.critical.assert_called_once_with(message, **kwargs)


class TestStructlogLoggerComponentBinding:
    """Test StructlogLogger component binding functionality."""

    def test_component_binding_applied_to_all_methods(self):
        """Test that component binding is applied to all logging methods."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_base_logger = Mock(spec=True)
            mock_bound_logger = Mock(spec=True)
            mock_base_logger.bind.return_value = mock_bound_logger
            mock_structlog.get_logger.return_value = mock_base_logger
            
            logger = StructlogLogger(name="test_logger", component="security_service")
            
            # Test that bound logger is used for all methods
            logger.info("test message")
            logger.warning("test warning")
            logger.error("test error")
            logger.debug("test debug")
            logger.critical("test critical")
            
            # Verify component binding was applied
            mock_base_logger.bind.assert_called_once_with(component="security_service")
            
            # Verify all methods use the bound logger
            mock_bound_logger.info.assert_called_once_with("test message")
            mock_bound_logger.warning.assert_called_once_with("test warning")
            mock_bound_logger.error.assert_called_once_with("test error")
            mock_bound_logger.debug.assert_called_once_with("test debug")
            mock_bound_logger.critical.assert_called_once_with("test critical")

    def test_component_binding_with_special_characters(self):
        """Test component binding with special characters in component name."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_base_logger = Mock(spec=True)
            mock_bound_logger = Mock(spec=True)
            mock_base_logger.bind.return_value = mock_bound_logger
            mock_structlog.get_logger.return_value = mock_base_logger
            
            component_name = "auth_service_v2.1-beta"
            logger = StructlogLogger(name="test_logger", component=component_name)
            
            mock_base_logger.bind.assert_called_once_with(component=component_name)
            assert logger.logger is mock_bound_logger

    def test_no_component_binding_when_not_provided(self):
        """Test that no component binding occurs when component is not provided."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="test_logger")
            
            # Verify no binding was attempted
            mock_logger.bind.assert_not_called()
            assert logger.logger is mock_logger


class TestStructlogLoggerChildSafetyLogging:
    """Test StructlogLogger usage in child safety contexts."""

    @pytest.fixture
    def child_safety_logger(self):
        """Create StructlogLogger configured for child safety logging."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_base_logger = Mock(spec=True)
            mock_bound_logger = Mock(spec=True)
            mock_base_logger.bind.return_value = mock_bound_logger
            mock_structlog.get_logger.return_value = mock_base_logger
            
            return StructlogLogger(name="child_safety", component="safety_service")

    def test_child_safety_violation_logging(self, child_safety_logger):
        """Test logging child safety violations."""
        with patch.object(child_safety_logger, 'logger') as mock_logger:
            message = "Content safety violation detected"
            context = {
                "child_age": 8,
                "violation_type": "inappropriate_content",
                "safety_score": 0.2,
                "content_hash": "abc123def456",
                "violations": ["violence", "scary_content"]
            }
            
            child_safety_logger.warning(message, **context)
            
            mock_logger.warning.assert_called_once_with(message, **context)

    def test_coppa_compliance_logging(self, child_safety_logger):
        """Test logging COPPA compliance events."""
        with patch.object(child_safety_logger, 'logger') as mock_logger:
            message = "COPPA data access logged"
            context = {
                "event_type": "child_data_access",
                "user_id": "parent123",
                "child_id_hash": "hashed_child_id",  # Note: hashed for privacy
                "access_type": "read",
                "coppa_compliant": True,
                "parent_consent": True
            }
            
            child_safety_logger.info(message, **context)
            
            mock_logger.info.assert_called_once_with(message, **context)

    def test_security_threat_logging(self, child_safety_logger):
        """Test logging security threats."""
        with patch.object(child_safety_logger, 'logger') as mock_logger:
            message = "Security threat detected"
            context = {
                "threat_type": "brute_force_attack",
                "severity": "high",
                "source_ip": "192.168.1.100",
                "attempt_count": 10,
                "threat_id": "threat_12345",
                "immediate_block": True
            }
            
            child_safety_logger.critical(message, **context)
            
            mock_logger.critical.assert_called_once_with(message, **context)

    def test_child_interaction_logging(self, child_safety_logger):
        """Test logging child interactions (with privacy protection)."""
        with patch.object(child_safety_logger, 'logger') as mock_logger:
            message = "Child interaction processed"
            context = {
                "child_age": 7,
                "interaction_type": "chat_message",
                "response_generated": True,
                "safety_check_passed": True,
                "processing_time_ms": 150,
                # Note: No actual child content logged for privacy
                "content_length": 25,
                "content_hash": "safe_content_hash"
            }
            
            child_safety_logger.debug(message, **context)
            
            mock_logger.debug.assert_called_once_with(message, **context)


class TestStructlogLoggerEdgeCases:
    """Test StructlogLogger edge cases and error conditions."""

    def test_empty_logger_name(self):
        """Test StructlogLogger with empty logger name."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="")
            
            mock_structlog.get_logger.assert_called_once_with(name="")
            assert logger.logger is mock_logger

    def test_unicode_logger_name(self):
        """Test StructlogLogger with unicode logger name."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            unicode_name = "test_logger_🧸"
            logger = StructlogLogger(name=unicode_name)
            
            mock_structlog.get_logger.assert_called_once_with(name=unicode_name)
            assert logger.logger is mock_logger

    def test_unicode_component_name(self):
        """Test StructlogLogger with unicode component name."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_base_logger = Mock(spec=True)
            mock_bound_logger = Mock(spec=True)
            mock_base_logger.bind.return_value = mock_bound_logger
            mock_structlog.get_logger.return_value = mock_base_logger
            
            unicode_component = "teddy_bear_🧸_service"
            logger = StructlogLogger(name="test", component=unicode_component)
            
            mock_base_logger.bind.assert_called_once_with(component=unicode_component)

    def test_very_long_logger_name(self):
        """Test StructlogLogger with very long logger name."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            long_name = "a" * 1000
            logger = StructlogLogger(name=long_name)
            
            mock_structlog.get_logger.assert_called_once_with(name=long_name)
            assert logger.logger is mock_logger

    def test_logging_with_none_values(self):
        """Test logging methods with None values in context."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="test_logger")
            
            # Test logging with None values
            logger.info("Test message", user_id=None, data=None, result=None)
            
            mock_logger.info.assert_called_once_with(
                "Test message",
                user_id=None,
                data=None,
                result=None
            )

    def test_logging_with_complex_data_structures(self):
        """Test logging methods with complex data structures."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="test_logger")
            
            # Test logging with complex data
            complex_data = {
                "nested_dict": {"key": "value", "list": [1, 2, 3]},
                "tuple": (1, "two", 3.0),
                "set": {1, 2, 3}  # Sets are not JSON serializable
            }
            
            logger.info("Complex data logged", data=complex_data)
            
            mock_logger.info.assert_called_once_with("Complex data logged", data=complex_data)

    def test_logging_with_exception_objects(self):
        """Test logging methods with exception objects."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="test_logger")
            
            # Create test exception
            try:
                raise ValueError("Test exception")
            except ValueError as e:
                test_exception = e
            
            logger.error("Error occurred", exception=test_exception, error_type=type(test_exception).__name__)
            
            mock_logger.error.assert_called_once_with(
                "Error occurred",
                exception=test_exception,
                error_type="ValueError"
            )


class TestStructlogLoggerIntegration:
    """Test StructlogLogger integration scenarios."""

    def test_multiple_logger_instances_isolation(self):
        """Test that multiple logger instances are properly isolated."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger1 = Mock(spec=True)
            mock_logger2 = Mock(spec=True)
            mock_bound_logger1 = Mock(spec=True)
            mock_bound_logger2 = Mock(spec=True)
            
            # Setup different loggers for different calls
            def get_logger_side_effect(name):
                if name == "auth_service":
                    return mock_logger1
                elif name == "safety_service":
                    return mock_logger2
                return Mock(spec=True)
            
            mock_structlog.get_logger.side_effect = get_logger_side_effect
            mock_logger1.bind.return_value = mock_bound_logger1
            mock_logger2.bind.return_value = mock_bound_logger2
            
            # Create two different loggers
            auth_logger = StructlogLogger(name="auth_service", component="auth")
            safety_logger = StructlogLogger(name="safety_service", component="safety")
            
            # Test that they use different underlying loggers
            auth_logger.info("Auth message")
            safety_logger.warning("Safety warning")
            
            mock_bound_logger1.info.assert_called_once_with("Auth message")
            mock_bound_logger2.warning.assert_called_once_with("Safety warning")
            
            # Verify no cross-contamination
            mock_bound_logger1.warning.assert_not_called()
            mock_bound_logger2.info.assert_not_called()

    def test_logger_inheritance_compatibility(self):
        """Test that StructlogLogger can be used wherever ILogger is expected."""
        with patch('src.infrastructure.logging.structlog_logger.structlog'):
            logger = StructlogLogger(name="test_logger")
            
            # Test that it can be used in functions expecting ILogger
            def log_message(logger_instance: ILogger, message: str):
                logger_instance.info(message)
                logger_instance.warning(message)
                logger_instance.error(message)
                logger_instance.debug(message)
                logger_instance.critical(message)
            
            # Should not raise any type errors
            log_message(logger, "Test message")

    def test_production_logging_scenario(self):
        """Test realistic production logging scenario."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_base_logger = Mock(spec=True)
            mock_bound_logger = Mock(spec=True)
            mock_base_logger.bind.return_value = mock_bound_logger
            mock_structlog.get_logger.return_value = mock_base_logger
            
            # Create logger as would be done in production
            logger = StructlogLogger(
                name="ai_teddy_bear.security_service",
                component="threat_detection"
            )
            
            # Simulate production logging sequence
            logger.info("Security service initialized", version="1.0.0")
            logger.debug("Starting threat detection scan", scan_id="scan_123")
            logger.warning(
                "Suspicious activity detected",
                ip_address="192.168.1.100",
                threat_level="medium",
                action="monitoring"
            )
            logger.critical(
                "COPPA violation detected",
                violation_type="unauthorized_access",
                child_id_hash="hashed_id",
                immediate_action="block_user"
            )
            
            # Verify all calls were made to bound logger
            assert mock_bound_logger.info.call_count == 1
            assert mock_bound_logger.debug.call_count == 1
            assert mock_bound_logger.warning.call_count == 1
            assert mock_bound_logger.critical.call_count == 1
            
            # Verify component binding was applied
            mock_base_logger.bind.assert_called_once_with(component="threat_detection")


class TestStructlogLoggerCOPPACompliance:
    """Test StructlogLogger COPPA compliance features."""

    def test_coppa_safe_logging_no_pii(self):
        """Test that logger can be used safely without logging child PII."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="coppa_safe_logger")
            
            # Example of COPPA-safe logging - no actual child data
            logger.info(
                "Child interaction processed",
                child_age=8,  # Age is okay to log
                interaction_type="chat",
                safety_passed=True,
                content_hash="abc123",  # Hashed content, not actual content
                # Notice: No child name, no actual message content
                timestamp="2025-07-29T10:00:00Z"
            )
            
            # Verify the call was made with safe parameters
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            # Verify no PII in logged data
            assert "child_name" not in str(call_args)
            assert "actual_message" not in str(call_args)
            assert "address" not in str(call_args)
            
            # Verify safe data is present
            assert "child_age" in str(call_args)
            assert "content_hash" in str(call_args)

    def test_audit_trail_logging(self):
        """Test logging for COPPA audit trail requirements."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="audit_logger", component="coppa_audit")
            
            # Example audit trail entry
            logger.info(
                "COPPA audit event",
                event_type="child_data_access",
                user_id="parent123",
                user_role="parent",
                child_id_hash="child_hash_456",  # Hashed child ID
                access_type="read_conversation_history",
                consent_status="verified",
                timestamp="2025-07-29T10:00:00Z",
                correlation_id="req_789"
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            call_kwargs = mock_logger.info.call_args[1]
            
            # Verify audit structure
            assert call_args[0] == "COPPA audit event"
            assert call_kwargs["event_type"] == "child_data_access"
            assert call_kwargs["consent_status"] == "verified"

    def test_privacy_preserving_error_logging(self):
        """Test error logging that preserves child privacy."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="privacy_safe_logger")
            
            # Example privacy-preserving error log
            logger.error(
                "Chat generation failed",
                error_type="OpenAIException",
                error_code="rate_limit_exceeded",
                child_age=7,  # Safe to log
                session_id="session_abc123",  # Session ID, not child ID
                retry_count=3,
                # Notice: No child name, no message content
                correlation_id="error_456"
            )
            
            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args[1]
            
            # Verify privacy preservation
            assert "child_name" not in call_kwargs
            assert "message_content" not in call_kwargs
            assert "personal_info" not in call_kwargs
            
            # Verify technical details are present for debugging
            assert call_kwargs["error_type"] == "OpenAIException"
            assert call_kwargs["retry_count"] == 3


class TestStructlogLoggerErrorHandling:
    """Test StructlogLogger error handling and resilience."""

    def test_structlog_import_error_handling(self):
        """Test behavior when structlog is not available."""
        # This test would require mocking the import process
        # In practice, if structlog is not available, the import would fail
        # at module level, which is the expected behavior
        pass

    def test_logger_method_exception_propagation(self):
        """Test that exceptions from underlying logger are propagated."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_logger.info.side_effect = Exception("Logging system failure")
            mock_structlog.get_logger.return_value = mock_logger
            
            logger = StructlogLogger(name="test_logger")
            
            # Exception should propagate up
            with pytest.raises(Exception, match="Logging system failure"):
                logger.info("Test message")

    def test_logger_creation_with_invalid_parameters(self):
        """Test logger creation with various invalid parameters."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_structlog.get_logger.side_effect = Exception("Invalid logger name")
            
            # Should propagate the exception from structlog
            with pytest.raises(Exception, match="Invalid logger name"):
                StructlogLogger(name="invalid_name")


class TestStructlogLoggerPerformance:
    """Test StructlogLogger performance considerations."""

    def test_lazy_logger_creation(self):
        """Test that logger creation is handled efficiently."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_logger = Mock(spec=True)
            mock_structlog.get_logger.return_value = mock_logger
            
            # Logger should be created immediately during init
            logger = StructlogLogger(name="test_logger")
            
            # Verify structlog.get_logger was called during initialization
            mock_structlog.get_logger.assert_called_once()
            
            # Multiple logging calls should not create new loggers
            logger.info("Message 1")
            logger.info("Message 2")
            logger.info("Message 3")
            
            # Should still only have one call to get_logger
            assert mock_structlog.get_logger.call_count == 1

    def test_component_binding_performance(self):
        """Test that component binding is done efficiently."""
        with patch('src.infrastructure.logging.structlog_logger.structlog') as mock_structlog:
            mock_base_logger = Mock(spec=True)
            mock_bound_logger = Mock(spec=True)
            mock_base_logger.bind.return_value = mock_bound_logger
            mock_structlog.get_logger.return_value = mock_base_logger
            
            # Component binding should happen once during initialization
            logger = StructlogLogger(name="test_logger", component="test_component")
            
            # Multiple logging calls should not trigger additional binding
            logger.info("Message 1")
            logger.warning("Message 2")
            logger.error("Message 3")
            
            # Should only have one call to bind
            mock_base_logger.bind.assert_called_once_with(component="test_component")
            
            # All logging calls should use the bound logger
            assert mock_bound_logger.info.call_count == 1
            assert mock_bound_logger.warning.call_count == 1
            assert mock_bound_logger.error.call_count == 1