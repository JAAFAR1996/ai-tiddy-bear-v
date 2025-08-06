"""
🧸 AI TEDDY BEAR V5 - ERROR RECOVERY TESTS
=========================================
Comprehensive tests for ESP32 error recovery system.

Tests cover:
- Basic recovery functionality
- Retry strategies with exponential backoff
- Circuit breaker patterns
- Fallback mechanisms
- Error classification and handling
- Metrics and monitoring
- Event handling
- Edge cases and error conditions
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Any, Dict

from src.infrastructure.device.error_recovery import (
    ErrorRecovery,
    ErrorContext,
    RecoveryRule,
    RecoveryStrategy,
    ErrorSeverity,
    CircuitBreaker,
    CircuitBreakerState,
    error_recovery
)
from src.infrastructure.exceptions import (
    AITeddyBearException,
    ServiceUnavailableError,
    DatabaseConnectionError,
    DatabaseTimeoutError,
    AIServiceError,
    RateLimitExceeded,
    ThrottlingError,
    ConfigurationError
)


class TestErrorContext:
    """Test ErrorContext functionality."""
    
    def test_error_context_creation(self):
        """Test creating error context."""
        error = ValueError("Test error")
        context = ErrorContext(
            error=error,
            device_id="device123",
            operation="test_operation",
            metadata={"key": "value"}
        )
        
        assert context.error == error
        assert context.device_id == "device123"
        assert context.operation == "test_operation"
        assert context.metadata == {"key": "value"}
        assert context.attempt_count == 0
        assert context.correlation_id is not None
    
    def test_error_context_to_dict(self):
        """Test converting error context to dictionary."""
        error = ValueError("Test error")
        context = ErrorContext(
            error=error,
            device_id="device123",
            operation="test_operation",
            attempt_count=2,
            metadata={"key": "value"}
        )
        
        result = context.to_dict()
        
        assert result["error_type"] == "ValueError"
        assert result["error_message"] == "Test error"
        assert result["device_id"] == "device123"
        assert result["operation"] == "test_operation"
        assert result["attempt_count"] == 2
        assert result["correlation_id"] == context.correlation_id
        assert result["metadata"] == {"key": "value"}


class TestCircuitBreaker:
    """Test CircuitBreaker functionality."""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker initial state."""
        breaker = CircuitBreaker(name="test")
        
        assert breaker.name == "test"
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.should_allow_request()
    
    def test_circuit_breaker_failure_tracking(self):
        """Test circuit breaker failure tracking."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)
        
        # Record failures
        for i in range(2):
            breaker.record_failure()
            assert breaker.state == CircuitBreakerState.CLOSED
            assert breaker.failure_count == i + 1
        
        # Third failure should open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.failure_count == 3
        assert not breaker.should_allow_request()
    
    def test_circuit_breaker_success_reset(self):
        """Test circuit breaker success reset."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)
        
        # Record failures to open circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Record success should reset
        breaker.record_success()
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.should_allow_request()
    
    def test_circuit_breaker_half_open_transition(self):
        """Test circuit breaker half-open transition."""
        breaker = CircuitBreaker(
            name="test", 
            failure_threshold=2, 
            recovery_timeout=0.1
        )
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Should transition to half-open
        assert breaker.should_allow_request()
        # Note: The transition happens in should_allow_request()
        # We can't directly check the state without triggering the transition


class TestErrorRecovery:
    """Test ErrorRecovery system functionality."""
    
    @pytest.fixture
    def recovery_system(self):
        """Create error recovery system for testing."""
        return ErrorRecovery(
            max_concurrent_recoveries=5,
            default_retry_count=2,
            enable_circuit_breaker=True,
            enable_metrics=True
        )
    
    def test_error_recovery_initialization(self, recovery_system):
        """Test error recovery system initialization."""
        assert recovery_system.max_concurrent_recoveries == 5
        assert recovery_system.default_retry_count == 2
        assert recovery_system.enable_circuit_breaker is True
        assert recovery_system.enable_metrics is True
        assert len(recovery_system._recovery_rules) > 0  # Default rules loaded
    
    def test_add_recovery_rule(self, recovery_system):
        """Test adding custom recovery rules."""
        rule = RecoveryRule(
            error_types=[ValueError],
            strategy=RecoveryStrategy.RETRY,
            max_retries=5
        )
        
        initial_count = len(recovery_system._recovery_rules)
        recovery_system.add_recovery_rule(rule)
        
        assert len(recovery_system._recovery_rules) == initial_count + 1
        assert recovery_system._recovery_rules[0] == rule  # Custom rules have priority
    
    def test_find_recovery_rule(self, recovery_system):
        """Test finding recovery rules for errors."""
        # Test with known error type
        rule = recovery_system._find_recovery_rule(ConnectionError("test"))
        assert rule is not None
        assert RecoveryStrategy.RECONNECT == rule.strategy
        
        # Test with database error
        rule = recovery_system._find_recovery_rule(DatabaseConnectionError("test"))
        assert rule is not None
        assert RecoveryStrategy.RETRY == rule.strategy
        
        # Test with unknown error type (should get fallback rule)
        rule = recovery_system._find_recovery_rule(RuntimeError("test"))
        assert rule is not None
        assert RecoveryStrategy.RETRY == rule.strategy
    
    @pytest.mark.asyncio
    async def test_basic_recovery(self, recovery_system):
        """Test basic error recovery functionality."""
        error = ConnectionError("Connection failed")
        
        result = await recovery_system.recover(
            error=error,
            device_id="device123",
            operation="test_operation"
        )
        
        assert result is True  # Recovery should succeed for connection errors
        
        # Check metrics were updated
        stats = recovery_system.get_recovery_statistics()
        assert stats['total_errors'] == 1
        assert 'ConnectionError' in stats['errors_by_type']
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocking(self, recovery_system):
        """Test circuit breaker blocking functionality."""
        # Get circuit breaker and force it open
        breaker = recovery_system._get_circuit_breaker("device123")
        breaker.state = CircuitBreakerState.OPEN
        breaker.last_failure_time = datetime.utcnow()
        
        error = AIServiceError("Service failed")
        
        result = await recovery_system.recover(
            error=error,
            device_id="device123",
            operation="test_operation"
        )
        
        assert result is False  # Should be blocked by circuit breaker
    
    @pytest.mark.asyncio
    async def test_recover_with_retry_success(self, recovery_system):
        """Test recover_with_retry with successful operation."""
        mock_operation = AsyncMock(return_value="success")
        
        result = await recovery_system.recover_with_retry(
            operation=mock_operation,
            device_id="device123",
            operation_name="test_op"
        )
        
        assert result == "success"
        assert mock_operation.call_count == 1
    
    @pytest.mark.asyncio
    async def test_recover_with_retry_eventual_success(self, recovery_system):
        """Test recover_with_retry with eventual success after failures."""
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock):  # Speed up test
            result = await recovery_system.recover_with_retry(
                operation=failing_operation,
                device_id="device123",
                max_retries=3,
                operation_name="test_op"
            )
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_recover_with_retry_final_failure(self, recovery_system):
        """Test recover_with_retry with final failure after all retries."""
        mock_operation = AsyncMock(side_effect=ConnectionError("Persistent failure"))
        
        with patch('asyncio.sleep', new_callable=AsyncMock):  # Speed up test
            with pytest.raises(ConnectionError, match="Persistent failure"):
                await recovery_system.recover_with_retry(
                    operation=mock_operation,
                    device_id="device123",
                    max_retries=2,
                    operation_name="test_op"
                )
        
        assert mock_operation.call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_recovery_context_success(self, recovery_system):
        """Test recovery context manager with successful operation."""
        async with recovery_system.recovery_context(
            device_id="device123",
            operation="test_op"
        ):
            # No exception should be raised
            pass
    
    @pytest.mark.asyncio
    async def test_recovery_context_with_recoverable_error(self, recovery_system):
        """Test recovery context manager with recoverable error."""
        with patch.object(recovery_system, 'recover', return_value=True):
            async with recovery_system.recovery_context(
                device_id="device123",
                operation="test_op"
            ):
                raise ConnectionError("Recoverable error")
    
    @pytest.mark.asyncio
    async def test_recovery_context_with_unrecoverable_error(self, recovery_system):
        """Test recovery context manager with unrecoverable error."""
        with patch.object(recovery_system, 'recover', return_value=False):
            with pytest.raises(ConnectionError):
                async with recovery_system.recovery_context(
                    device_id="device123",
                    operation="test_op"
                ):
                    raise ConnectionError("Unrecoverable error")
    
    def test_circuit_breaker_status(self, recovery_system):
        """Test getting circuit breaker status."""
        # Get status for non-existent breaker
        status = recovery_system.get_circuit_breaker_status("nonexistent")
        assert status['state'] == 'not_found'
        
        # Create a breaker and get its status
        breaker = recovery_system._get_circuit_breaker("device123")
        breaker.record_failure()
        
        status = recovery_system.get_circuit_breaker_status("device123")
        assert status['name'] == "device123"
        assert status['state'] == CircuitBreakerState.CLOSED.value
        assert status['failure_count'] == 1
    
    def test_reset_circuit_breaker(self, recovery_system):
        """Test manually resetting circuit breaker."""
        # Create and break circuit
        breaker = recovery_system._get_circuit_breaker("device123")
        breaker.state = CircuitBreakerState.OPEN
        breaker.failure_count = 5
        
        # Reset it
        recovery_system.reset_circuit_breaker("device123")
        
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0
    
    def test_recovery_statistics(self, recovery_system):
        """Test getting comprehensive recovery statistics."""
        stats = recovery_system.get_recovery_statistics()
        
        assert 'total_errors' in stats
        assert 'successful_recoveries' in stats
        assert 'failed_recoveries' in stats
        assert 'errors_by_type' in stats
        assert 'recoveries_by_strategy' in stats
        assert 'active_recoveries' in stats
        assert 'circuit_breakers' in stats
        assert 'recovery_rules_count' in stats
    
    def test_backoff_delay_calculation(self, recovery_system):
        """Test exponential backoff delay calculation."""
        # Test delay progression
        delay0 = recovery_system._calculate_backoff_delay(0, 2.0)
        delay1 = recovery_system._calculate_backoff_delay(1, 2.0)
        delay2 = recovery_system._calculate_backoff_delay(2, 2.0)
        
        # Should be roughly exponential (with jitter)
        assert 0.5 <= delay0 <= 2.0
        assert 1.5 <= delay1 <= 4.0
        assert 3.0 <= delay2 <= 8.0
        
        # Test cap at 60 seconds
        delay_large = recovery_system._calculate_backoff_delay(10, 2.0)
        assert delay_large <= 60.0
    
    @pytest.mark.asyncio
    async def test_event_handlers(self, recovery_system):
        """Test event handler functionality."""
        error_events = []
        recovery_events = []
        
        async def error_handler(context):
            error_events.append(context)
        
        async def recovery_handler(context):
            recovery_events.append(context)
        
        recovery_system.add_error_handler('test_event', error_handler)
        recovery_system.add_recovery_handler('test_event', recovery_handler)
        
        # Emit test event
        context = ErrorContext(error=ValueError("test"))
        await recovery_system._emit_event('test_event', context)
        
        assert len(error_events) == 1
        assert len(recovery_events) == 1
        assert error_events[0] == context
        assert recovery_events[0] == context
    
    @pytest.mark.asyncio
    async def test_concurrent_recovery_limit(self, recovery_system):
        """Test concurrent recovery operation limits."""
        # Set a low limit for testing
        recovery_system._recovery_semaphore = asyncio.Semaphore(2)
        
        recovery_calls = []
        
        async def slow_recovery(context, rule):
            recovery_calls.append(context)
            await asyncio.sleep(0.1)
            return True
        
        # Add custom rule with slow handler
        rule = RecoveryRule(
            error_types=[ValueError],
            strategy=RecoveryStrategy.RETRY,
            custom_handler=slow_recovery
        )
        recovery_system.add_recovery_rule(rule)
        
        # Start multiple concurrent recoveries
        tasks = []
        for i in range(5):
            task = asyncio.create_task(
                recovery_system.recover(
                    error=ValueError(f"error_{i}"),
                    device_id=f"device_{i}"
                )
            )
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(results)
        assert len(recovery_calls) == 5


class TestRecoveryStrategies:
    """Test specific recovery strategy implementations."""
    
    @pytest.fixture
    def recovery_system(self):
        """Create error recovery system for testing."""
        return ErrorRecovery(enable_metrics=True)
    
    @pytest.mark.asyncio
    async def test_retry_strategy(self, recovery_system):
        """Test retry strategy implementation."""
        context = ErrorContext(
            error=ConnectionError("test"),
            device_id="device123",
            operation="test_op"
        )
        rule = RecoveryRule(
            error_types=[ConnectionError],
            strategy=RecoveryStrategy.RETRY,
            max_retries=3
        )
        
        result = await recovery_system._handle_retry_strategy(context, rule)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_reconnect_strategy(self, recovery_system):
        """Test reconnect strategy implementation."""
        context = ErrorContext(
            error=ConnectionError("test"),
            device_id="device123",
            operation="test_op"
        )
        rule = RecoveryRule(
            error_types=[ConnectionError],
            strategy=RecoveryStrategy.RECONNECT,
            initial_delay=0.01  # Speed up test
        )
        
        result = await recovery_system._handle_reconnect_strategy(context, rule)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_reconnect_strategy_no_device_id(self, recovery_system):
        """Test reconnect strategy without device ID."""
        context = ErrorContext(
            error=ConnectionError("test"),
            device_id=None,  # No device ID
            operation="test_op"
        )
        rule = RecoveryRule(
            error_types=[ConnectionError],
            strategy=RecoveryStrategy.RECONNECT
        )
        
        result = await recovery_system._handle_reconnect_strategy(context, rule)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_strategy(self, recovery_system):
        """Test circuit breaker strategy implementation."""
        context = ErrorContext(
            error=AIServiceError("test"),
            device_id="device123",
            operation="test_op"
        )
        rule = RecoveryRule(
            error_types=[AIServiceError],
            strategy=RecoveryStrategy.CIRCUIT_BREAKER,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=60.0
        )
        
        result = await recovery_system._handle_circuit_breaker_strategy(context, rule)
        assert result is True
        
        # Check breaker was configured
        breaker = recovery_system._get_circuit_breaker("device123")
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 60.0
    
    @pytest.mark.asyncio
    async def test_fallback_strategy_with_action(self, recovery_system):
        """Test fallback strategy with fallback action."""
        fallback_called = False
        
        async def fallback_action(context):
            nonlocal fallback_called
            fallback_called = True
        
        context = ErrorContext(
            error=ValueError("test"),
            device_id="device123",
            operation="test_op"
        )
        rule = RecoveryRule(
            error_types=[ValueError],
            strategy=RecoveryStrategy.FALLBACK,
            fallback_action=fallback_action
        )
        
        result = await recovery_system._handle_fallback_strategy(context, rule)
        assert result is True
        assert fallback_called is True
    
    @pytest.mark.asyncio
    async def test_fallback_strategy_no_action(self, recovery_system):
        """Test fallback strategy without fallback action."""
        context = ErrorContext(
            error=ValueError("test"),
            device_id="device123",
            operation="test_op"
        )
        rule = RecoveryRule(
            error_types=[ValueError],
            strategy=RecoveryStrategy.FALLBACK,
            fallback_action=None
        )
        
        result = await recovery_system._handle_fallback_strategy(context, rule)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_escalate_strategy(self, recovery_system):
        """Test escalate strategy implementation."""
        context = ErrorContext(
            error=ConfigurationError("test"),
            device_id="device123",
            operation="test_op"
        )
        rule = RecoveryRule(
            error_types=[ConfigurationError],
            strategy=RecoveryStrategy.ESCALATE
        )
        
        result = await recovery_system._handle_escalate_strategy(context, rule)
        assert result is False  # Escalation should fail fast


class TestDefaultRecoveryRules:
    """Test default recovery rules configuration."""
    
    @pytest.fixture
    def recovery_system(self):
        """Create error recovery system for testing."""
        return ErrorRecovery()
    
    def test_connection_error_rule(self, recovery_system):
        """Test connection error recovery rule."""
        rule = recovery_system._find_recovery_rule(ConnectionError("test"))
        assert rule.strategy == RecoveryStrategy.RECONNECT
        assert rule.severity == ErrorSeverity.HIGH
    
    def test_database_error_rule(self, recovery_system):
        """Test database error recovery rule."""
        rule = recovery_system._find_recovery_rule(DatabaseConnectionError("test"))
        assert rule.strategy == RecoveryStrategy.RETRY
        assert rule.max_retries == 5
        assert rule.backoff_multiplier == 1.5
    
    def test_rate_limit_rule(self, recovery_system):
        """Test rate limit recovery rule."""
        rule = recovery_system._find_recovery_rule(RateLimitExceeded("test"))
        assert rule.strategy == RecoveryStrategy.RETRY
        assert rule.backoff_multiplier == 3.0
        assert rule.initial_delay == 5.0
    
    def test_ai_service_error_rule(self, recovery_system):
        """Test AI service error recovery rule."""
        rule = recovery_system._find_recovery_rule(AIServiceError("test"))
        assert rule.strategy == RecoveryStrategy.CIRCUIT_BREAKER
        assert rule.circuit_breaker_threshold == 3
    
    def test_configuration_error_rule(self, recovery_system):
        """Test configuration error recovery rule."""
        rule = recovery_system._find_recovery_rule(ConfigurationError("test"))
        assert rule.strategy == RecoveryStrategy.ESCALATE
        assert rule.severity == ErrorSeverity.CRITICAL
        assert rule.max_retries == 0
    
    def test_service_unavailable_rule(self, recovery_system):
        """Test service unavailable recovery rule."""
        rule = recovery_system._find_recovery_rule(ServiceUnavailableError("test"))
        assert rule.strategy == RecoveryStrategy.CIRCUIT_BREAKER
        assert rule.circuit_breaker_threshold == 5


class TestGlobalInstance:
    """Test global error recovery instance."""
    
    def test_global_instance_exists(self):
        """Test that global instance exists and is properly configured."""
        assert error_recovery is not None
        assert isinstance(error_recovery, ErrorRecovery)
        assert len(error_recovery._recovery_rules) > 0
    
    @pytest.mark.asyncio
    async def test_global_instance_functionality(self):
        """Test that global instance works correctly."""
        error = ConnectionError("Test error")
        
        result = await error_recovery.recover(
            error=error,
            device_id="test_device",
            operation="test_operation"
        )
        
        assert result is True


@pytest.mark.asyncio
async def test_integration_with_connection_pool():
    """Test integration scenario with connection pool."""
    recovery_system = ErrorRecovery()
    
    # Simulate connection pool operations with recovery
    operations_completed = 0
    
    async def mock_connection_operation():
        nonlocal operations_completed
        operations_completed += 1
        if operations_completed <= 2:
            raise ConnectionError("Connection lost")
        return "success"
    
    with patch('asyncio.sleep', new_callable=AsyncMock):
        result = await recovery_system.recover_with_retry(
            operation=mock_connection_operation,
            device_id="esp32_device_1",
            max_retries=3,
            operation_name="send_command"
        )
    
    assert result == "success"
    assert operations_completed == 3
    
    # Check that circuit breaker was used
    stats = recovery_system.get_recovery_statistics()
    assert stats['total_errors'] == 2  # Two failures before success


if __name__ == "__main__":
    pytest.main([__file__])