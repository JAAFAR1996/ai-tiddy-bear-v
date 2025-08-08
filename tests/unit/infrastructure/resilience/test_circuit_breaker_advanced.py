"""
Advanced Circuit Breaker Tests
==============================
Tests for advanced circuit breaker with adaptive thresholds and child safety.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class FailureType(Enum):
    """Types of failures that can trigger circuit breaker."""
    TIMEOUT = "timeout"
    ERROR = "error"
    RATE_LIMIT = "rate_limit"
    CHILD_SAFETY = "child_safety"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    timeout_duration: float = 30.0
    
    # Adaptive settings
    adaptive_threshold: bool = True
    min_failure_threshold: int = 3
    max_failure_threshold: int = 20
    
    # Child safety settings
    child_safety_mode: bool = True
    child_safety_threshold: int = 2  # Lower threshold for child safety
    
    # Monitoring
    enable_metrics: bool = True
    sliding_window_size: int = 100


@dataclass
class CircuitMetrics:
    """Circuit breaker metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeouts: int = 0
    circuit_opens: int = 0
    circuit_closes: int = 0
    current_failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    average_response_time: float = 0.0
    failure_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "timeouts": self.timeouts,
            "circuit_opens": self.circuit_opens,
            "circuit_closes": self.circuit_closes,
            "current_failure_count": self.current_failure_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "average_response_time": self.average_response_time,
            "failure_rate": self.failure_rate
        }


class AdvancedCircuitBreaker:
    """Advanced circuit breaker with adaptive thresholds and child safety features."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        
        # Sliding window for adaptive behavior
        self.request_history: List[Dict[str, Any]] = []
        self.response_times: List[float] = []
        
        # State management
        self.last_state_change = datetime.now()
        self.half_open_attempts = 0
        
        # Callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_failure: Optional[Callable] = None
        self.on_success: Optional[Callable] = None
        
        # Child safety tracking
        self.child_safety_violations: List[Dict[str, Any]] = []
        
        # Adaptive threshold tracking
        self.recent_failure_rates: List[float] = []
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")
        
        # Execute the function
        start_time = time.time()
        
        try:
            # Apply timeout if configured
            if self.config.timeout_duration > 0:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.timeout_duration
                )
            else:
                result = await func(*args, **kwargs)
            
            # Record success
            response_time = time.time() - start_time
            await self._record_success(response_time)
            
            return result
            
        except asyncio.TimeoutError:
            await self._record_failure(FailureType.TIMEOUT)
            raise CircuitBreakerTimeoutError(f"Function timed out after {self.config.timeout_duration}s")
            
        except ChildSafetyViolationError as e:
            await self._record_child_safety_violation(str(e))
            raise
            
        except Exception as e:
            await self._record_failure(FailureType.ERROR, str(e))
            raise
    
    async def _record_success(self, response_time: float):
        """Record successful request."""
        self.metrics.total_requests += 1
        self.metrics.successful_requests += 1
        self.metrics.current_failure_count = 0
        
        # Update response time metrics
        self.response_times.append(response_time)
        if len(self.response_times) > self.config.sliding_window_size:
            self.response_times.pop(0)
        
        self.metrics.average_response_time = sum(self.response_times) / len(self.response_times)
        
        # Update request history
        self._add_to_history("success", response_time=response_time)
        
        # Handle half-open state
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.config.success_threshold:
                self._transition_to_closed()
        
        # Update failure rate
        self._update_failure_rate()
        
        # Callback
        if self.on_success:
            await self.on_success(self.name, response_time)
    
    async def _record_failure(self, failure_type: FailureType, error_message: str = ""):
        """Record failed request."""
        self.metrics.total_requests += 1
        self.metrics.failed_requests += 1
        self.metrics.current_failure_count += 1
        self.metrics.last_failure_time = datetime.now()
        
        if failure_type == FailureType.TIMEOUT:
            self.metrics.timeouts += 1
        
        # Update request history
        self._add_to_history("failure", failure_type=failure_type.value, error=error_message)
        
        # Check if circuit should open
        if self._should_open_circuit(failure_type):
            self._transition_to_open()
        
        # Update failure rate
        self._update_failure_rate()
        
        # Callback
        if self.on_failure:
            await self.on_failure(self.name, failure_type, error_message)
    
    async def _record_child_safety_violation(self, violation_details: str):
        """Record child safety violation."""
        violation = {
            "timestamp": datetime.now(),
            "details": violation_details,
            "circuit_name": self.name
        }
        
        self.child_safety_violations.append(violation)
        
        # Keep only recent violations
        if len(self.child_safety_violations) > 50:
            self.child_safety_violations = self.child_safety_violations[-50:]
        
        # Child safety violations trigger immediate circuit opening
        await self._record_failure(FailureType.CHILD_SAFETY, violation_details)
    
    def _should_open_circuit(self, failure_type: FailureType) -> bool:
        """Determine if circuit should open based on failure."""
        # Child safety violations have lower threshold
        if failure_type == FailureType.CHILD_SAFETY and self.config.child_safety_mode:
            child_safety_failures = len([
                h for h in self.request_history[-10:]  # Last 10 requests
                if h.get("failure_type") == FailureType.CHILD_SAFETY.value
            ])
            return child_safety_failures >= self.config.child_safety_threshold
        
        # Use adaptive threshold if enabled
        threshold = self._get_adaptive_threshold()
        
        return self.metrics.current_failure_count >= threshold
    
    def _get_adaptive_threshold(self) -> int:
        """Get adaptive failure threshold based on recent performance."""
        if not self.config.adaptive_threshold:
            return self.config.failure_threshold
        
        # Calculate adaptive threshold based on recent failure rates
        if len(self.recent_failure_rates) < 5:
            return self.config.failure_threshold
        
        avg_failure_rate = sum(self.recent_failure_rates) / len(self.recent_failure_rates)
        
        if avg_failure_rate > 0.5:  # High failure rate
            return max(self.config.min_failure_threshold, self.config.failure_threshold - 2)
        elif avg_failure_rate < 0.1:  # Low failure rate
            return min(self.config.max_failure_threshold, self.config.failure_threshold + 2)
        else:
            return self.config.failure_threshold
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset from open state."""
        time_since_open = datetime.now() - self.last_state_change
        return time_since_open.total_seconds() >= self.config.recovery_timeout
    
    def _transition_to_open(self):
        """Transition circuit to open state."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.now()
            self.metrics.circuit_opens += 1
            
            if self.on_state_change:
                asyncio.create_task(self.on_state_change(self.name, CircuitState.OPEN))
    
    def _transition_to_half_open(self):
        """Transition circuit to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self.last_state_change = datetime.now()
        self.half_open_attempts = 0
        
        if self.on_state_change:
            asyncio.create_task(self.on_state_change(self.name, CircuitState.HALF_OPEN))
    
    def _transition_to_closed(self):
        """Transition circuit to closed state."""
        self.state = CircuitState.CLOSED
        self.last_state_change = datetime.now()
        self.metrics.circuit_closes += 1
        self.metrics.current_failure_count = 0
        
        if self.on_state_change:
            asyncio.create_task(self.on_state_change(self.name, CircuitState.CLOSED))
    
    def _add_to_history(self, result: str, **metadata):
        """Add request to history."""
        entry = {
            "timestamp": datetime.now(),
            "result": result,
            **metadata
        }
        
        self.request_history.append(entry)
        
        # Keep sliding window
        if len(self.request_history) > self.config.sliding_window_size:
            self.request_history.pop(0)
    
    def _update_failure_rate(self):
        """Update current failure rate."""
        if self.metrics.total_requests == 0:
            self.metrics.failure_rate = 0.0
        else:
            self.metrics.failure_rate = self.metrics.failed_requests / self.metrics.total_requests
        
        # Update recent failure rates for adaptive behavior
        self.recent_failure_rates.append(self.metrics.failure_rate)
        if len(self.recent_failure_rates) > 20:
            self.recent_failure_rates.pop(0)
    
    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        return self.metrics.to_dict()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of circuit breaker."""
        return {
            "name": self.name,
            "state": self.state.value,
            "healthy": self.state == CircuitState.CLOSED,
            "failure_rate": self.metrics.failure_rate,
            "current_failures": self.metrics.current_failure_count,
            "child_safety_violations": len(self.child_safety_violations),
            "last_state_change": self.last_state_change.isoformat(),
            "adaptive_threshold": self._get_adaptive_threshold()
        }
    
    def reset(self):
        """Manually reset circuit breaker."""
        self.state = CircuitState.CLOSED
        self.metrics.current_failure_count = 0
        self.last_state_change = datetime.now()
        self.half_open_attempts = 0
    
    def force_open(self, reason: str = "Manual"):
        """Manually force circuit open."""
        self._transition_to_open()
        self._add_to_history("forced_open", reason=reason)


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerTimeoutError(Exception):
    """Exception raised when function times out."""
    pass


class ChildSafetyViolationError(Exception):
    """Exception raised for child safety violations."""
    pass


@pytest.fixture
def circuit_config():
    """Create circuit breaker configuration for testing."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=1.0,  # Short for testing
        success_threshold=2,
        timeout_duration=0.5,
        child_safety_threshold=1
    )


@pytest.fixture
def circuit_breaker(circuit_config):
    """Create circuit breaker for testing."""
    return AdvancedCircuitBreaker("test_circuit", circuit_config)


@pytest.mark.asyncio
class TestAdvancedCircuitBreaker:
    """Test advanced circuit breaker functionality."""
    
    async def test_circuit_breaker_initialization(self, circuit_breaker):
        """Test circuit breaker initialization."""
        assert circuit_breaker.name == "test_circuit"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.total_requests == 0
        assert circuit_breaker.metrics.current_failure_count == 0
    
    async def test_successful_function_execution(self, circuit_breaker):
        """Test successful function execution through circuit breaker."""
        async def successful_function():
            return "success"
        
        # Execute function
        result = await circuit_breaker.call(successful_function)
        
        # Verify result and metrics
        assert result == "success"
        assert circuit_breaker.metrics.total_requests == 1
        assert circuit_breaker.metrics.successful_requests == 1
        assert circuit_breaker.metrics.failed_requests == 0
        assert circuit_breaker.state == CircuitState.CLOSED
    
    async def test_function_failure_handling(self, circuit_breaker):
        """Test function failure handling."""
        async def failing_function():
            raise Exception("Function failed")
        
        # Execute failing function
        with pytest.raises(Exception, match="Function failed"):
            await circuit_breaker.call(failing_function)
        
        # Verify metrics
        assert circuit_breaker.metrics.total_requests == 1
        assert circuit_breaker.metrics.successful_requests == 0
        assert circuit_breaker.metrics.failed_requests == 1
        assert circuit_breaker.metrics.current_failure_count == 1
    
    async def test_circuit_opening_on_failures(self, circuit_breaker):
        """Test circuit opening after threshold failures."""
        async def failing_function():
            raise Exception("Function failed")
        
        # Execute failing function multiple times
        for i in range(3):  # Threshold is 3
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_function)
        
        # Circuit should be open now
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.metrics.circuit_opens == 1
        
        # Next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await circuit_breaker.call(failing_function)
    
    async def test_timeout_handling(self, circuit_breaker):
        """Test function timeout handling."""
        async def slow_function():
            await asyncio.sleep(1.0)  # Longer than timeout
            return "slow result"
        
        # Execute slow function
        with pytest.raises(CircuitBreakerTimeoutError):
            await circuit_breaker.call(slow_function)
        
        # Verify timeout recorded
        assert circuit_breaker.metrics.timeouts == 1
        assert circuit_breaker.metrics.failed_requests == 1
    
    async def test_half_open_state_recovery(self, circuit_breaker):
        """Test circuit recovery through half-open state."""
        async def failing_function():
            raise Exception("Function failed")
        
        async def successful_function():
            return "success"
        
        # Open the circuit
        for i in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Next call should transition to half-open
        result = await circuit_breaker.call(successful_function)
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Another successful call should close the circuit
        result = await circuit_breaker.call(successful_function)
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.circuit_closes == 1
    
    async def test_child_safety_violation_handling(self, circuit_breaker):
        """Test child safety violation handling."""
        async def unsafe_function():
            raise ChildSafetyViolationError("Inappropriate content detected")
        
        # Execute unsafe function
        with pytest.raises(ChildSafetyViolationError):
            await circuit_breaker.call(unsafe_function)
        
        # Circuit should open immediately due to child safety (threshold = 1)
        assert circuit_breaker.state == CircuitState.OPEN
        assert len(circuit_breaker.child_safety_violations) == 1
        
        # Verify violation details
        violation = circuit_breaker.child_safety_violations[0]
        assert "Inappropriate content detected" in violation["details"]
        assert violation["circuit_name"] == "test_circuit"
    
    async def test_adaptive_threshold_behavior(self, circuit_breaker):
        """Test adaptive threshold adjustment."""
        # Enable adaptive threshold
        circuit_breaker.config.adaptive_threshold = True
        circuit_breaker.config.min_failure_threshold = 2
        circuit_breaker.config.max_failure_threshold = 6
        
        async def failing_function():
            raise Exception("Function failed")
        
        # Simulate high failure rate scenario
        for i in range(10):
            try:
                await circuit_breaker.call(failing_function)
            except:
                pass
        
        # Adaptive threshold should be lower due to high failure rate
        adaptive_threshold = circuit_breaker._get_adaptive_threshold()
        assert adaptive_threshold <= circuit_breaker.config.failure_threshold
    
    async def test_metrics_collection(self, circuit_breaker):
        """Test comprehensive metrics collection."""
        async def mixed_function(should_fail: bool):
            if should_fail:
                raise Exception("Function failed")
            await asyncio.sleep(0.1)  # Simulate processing time
            return "success"
        
        # Execute mixed success/failure calls
        for i in range(10):
            try:
                await circuit_breaker.call(mixed_function, i % 3 == 0)  # Fail every 3rd call
            except:
                pass
        
        # Verify metrics
        metrics = circuit_breaker.get_metrics()
        assert metrics["total_requests"] == 10
        assert metrics["successful_requests"] > 0
        assert metrics["failed_requests"] > 0
        assert metrics["average_response_time"] > 0
        assert 0 <= metrics["failure_rate"] <= 1
    
    async def test_state_change_callbacks(self, circuit_breaker):
        """Test state change callback functionality."""
        state_changes = []
        
        async def state_change_callback(name: str, new_state: CircuitState):
            state_changes.append((name, new_state))
        
        circuit_breaker.on_state_change = state_change_callback
        
        async def failing_function():
            raise Exception("Function failed")
        
        # Trigger state changes
        for i in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_function)
        
        # Wait for callback
        await asyncio.sleep(0.1)
        
        # Verify callback called
        assert len(state_changes) == 1
        assert state_changes[0] == ("test_circuit", CircuitState.OPEN)
    
    async def test_manual_circuit_control(self, circuit_breaker):
        """Test manual circuit breaker control."""
        # Force circuit open
        circuit_breaker.force_open("Testing")
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Reset circuit
        circuit_breaker.reset()
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.current_failure_count == 0
    
    async def test_health_status_reporting(self, circuit_breaker):
        """Test health status reporting."""
        # Get initial health status
        health = circuit_breaker.get_health_status()
        
        assert health["name"] == "test_circuit"
        assert health["state"] == "closed"
        assert health["healthy"] is True
        assert health["failure_rate"] == 0.0
        assert health["current_failures"] == 0
        assert health["child_safety_violations"] == 0
        
        # Trigger some failures
        async def failing_function():
            raise Exception("Function failed")
        
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_function)
        
        # Check updated health status
        health = circuit_breaker.get_health_status()
        assert health["current_failures"] == 1
        assert health["failure_rate"] > 0
    
    async def test_sliding_window_behavior(self, circuit_breaker):
        """Test sliding window for request history."""
        # Set small sliding window for testing
        circuit_breaker.config.sliding_window_size = 5
        
        async def test_function(value: int):
            if value % 2 == 0:
                raise Exception(f"Failed for {value}")
            return f"Success {value}"
        
        # Execute more requests than window size
        for i in range(10):
            try:
                await circuit_breaker.call(test_function, i)
            except:
                pass
        
        # Verify sliding window maintained
        assert len(circuit_breaker.request_history) == 5
        assert len(circuit_breaker.response_times) <= 5
    
    async def test_concurrent_requests(self, circuit_breaker):
        """Test circuit breaker with concurrent requests."""
        async def concurrent_function(delay: float):
            await asyncio.sleep(delay)
            return f"Result after {delay}s"
        
        # Execute concurrent requests
        tasks = [
            circuit_breaker.call(concurrent_function, 0.1),
            circuit_breaker.call(concurrent_function, 0.2),
            circuit_breaker.call(concurrent_function, 0.1),
            circuit_breaker.call(concurrent_function, 0.3)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all requests completed
        assert len(results) == 4
        assert circuit_breaker.metrics.total_requests == 4
        assert circuit_breaker.metrics.successful_requests == 4
    
    async def test_coppa_compliance_features(self, circuit_breaker):
        """Test COPPA compliance features in circuit breaker."""
        # Enable child safety mode
        circuit_breaker.config.child_safety_mode = True
        
        async def child_unsafe_function():
            raise ChildSafetyViolationError("Content not suitable for children under 13")
        
        # Execute unsafe function
        with pytest.raises(ChildSafetyViolationError):
            await circuit_breaker.call(child_unsafe_function)
        
        # Verify immediate circuit opening for child safety
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Verify child safety violation recorded
        violations = circuit_breaker.child_safety_violations
        assert len(violations) == 1
        assert "children under 13" in violations[0]["details"]
        
        # Verify health status includes child safety info
        health = circuit_breaker.get_health_status()
        assert health["child_safety_violations"] == 1
    
    async def test_esp32_device_resilience(self, circuit_breaker):
        """Test circuit breaker for ESP32 device communication."""
        # Configure for ESP32 device communication
        circuit_breaker.config.timeout_duration = 5.0  # ESP32 can be slower
        circuit_breaker.config.failure_threshold = 5   # More tolerant for hardware
        
        async def esp32_communication():
            # Simulate ESP32 communication
            await asyncio.sleep(0.1)
            return {"status": "ok", "battery": 85, "temperature": 42.5}
        
        async def esp32_timeout():
            # Simulate ESP32 timeout
            await asyncio.sleep(6.0)  # Longer than timeout
            return {"status": "timeout"}
        
        # Test successful communication
        result = await circuit_breaker.call(esp32_communication)
        assert result["status"] == "ok"
        
        # Test timeout handling
        with pytest.raises(CircuitBreakerTimeoutError):
            await circuit_breaker.call(esp32_timeout)
        
        # Verify ESP32-specific metrics
        assert circuit_breaker.metrics.timeouts == 1
        assert circuit_breaker.state == CircuitState.CLOSED  # Still closed due to higher threshold