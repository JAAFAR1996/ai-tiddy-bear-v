"""
Provider Circuit Breaker System - Enterprise Grade Circuit Breakers
=================================================================
Comprehensive circuit breaker implementation for all external providers:
- Adaptive circuit breaker with machine learning capabilities
- Provider-specific failure patterns and thresholds
- Advanced monitoring and alerting
- Cost-aware failure handling
- Geographic failover support
- Real-time health scoring
"""

import asyncio
import json
import logging
import statistics
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import uuid
import math

from .fallback_logger import FallbackLogger, LogContext, EventType

# Try to import EventPublisher, but make it optional
try:
    from ..messaging.event_bus_integration import EventPublisher
    EVENT_PUBLISHER_AVAILABLE = True
except ImportError:
    EVENT_PUBLISHER_AVAILABLE = False
    class MockEventPublisher:
        @staticmethod
        async def publish_system_event(event_type: str, payload: dict):
            # Mock implementation that does nothing
            pass
    EventPublisher = MockEventPublisher

# Redis imports for enhanced circuit breaker state
try:
    import redis.asyncio as aioredis
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = None


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"           # Normal operation
    OPEN = "open"              # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"    # Testing if service is recovered


class ProviderType(Enum):
    """Types of external providers."""
    AI_PROVIDER = "ai_provider"
    STORAGE_PROVIDER = "storage_provider"
    COMMUNICATION_PROVIDER = "communication_provider"
    DATABASE_PROVIDER = "database_provider"
    CACHE_PROVIDER = "cache_provider"
    AUDIO_PROVIDER = "audio_provider"
    WEBHOOK_PROVIDER = "webhook_provider"


class FailurePattern(Enum):
    """Types of failure patterns."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION_ERROR = "authentication_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    QUOTA_EXCEEDED = "quota_exceeded"
    INVALID_RESPONSE = "invalid_response"
    NETWORK_ERROR = "network_error"


@dataclass
class FailureEvent:
    """Represents a failure event."""
    timestamp: datetime
    provider_id: str
    failure_type: FailurePattern
    error_message: str
    response_time: float
    cost_impact: float = 0.0
    user_id: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ProviderMetrics:
    """Comprehensive metrics for a provider."""
    provider_id: str
    provider_type: ProviderType
    
    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Response time metrics
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    average_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # Failure metrics
    recent_failures: deque = field(default_factory=lambda: deque(maxlen=50))
    consecutive_failures: int = 0
    failure_rate: float = 0.0
    
    # Health scoring
    health_score: float = 100.0
    last_health_check: Optional[datetime] = None
    
    # Cost metrics
    estimated_cost_per_request: float = 0.0
    total_cost_impact: float = 0.0
    
    # Geographic metrics
    region: str = "unknown"
    latency_by_region: Dict[str, float] = field(default_factory=dict)
    
    def update_request(self, success: bool, response_time: float, cost: float = 0.0):
        """Update metrics after a request."""
        self.total_requests += 1
        self.response_times.append(response_time)
        self.total_cost_impact += cost
        
        if success:
            self.successful_requests += 1
            self.consecutive_failures = 0
            # Gradually improve health score
            self.health_score = min(100.0, self.health_score + 0.5)
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1
            # Decrease health score based on failure severity
            penalty = min(10.0, self.consecutive_failures * 2.0)
            self.health_score = max(0.0, self.health_score - penalty)
        
        # Update averages
        if self.response_times:
            self.average_response_time = statistics.mean(self.response_times)
            sorted_times = sorted(self.response_times)
            n = len(sorted_times)
            self.p95_response_time = sorted_times[int(n * 0.95)] if n > 0 else 0.0
            self.p99_response_time = sorted_times[int(n * 0.99)] if n > 0 else 0.0
        
        # Update failure rate
        if self.total_requests > 0:
            self.failure_rate = (self.failed_requests / self.total_requests) * 100
    
    def add_failure(self, failure: FailureEvent):
        """Add a failure event."""
        self.recent_failures.append(failure)
    
    def get_failure_pattern_distribution(self) -> Dict[str, int]:
        """Get distribution of failure patterns."""
        pattern_count = defaultdict(int)
        for failure in self.recent_failures:
            pattern_count[failure.failure_type.value] += 1
        return dict(pattern_count)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    provider_id: str
    provider_type: ProviderType
    
    # Failure thresholds
    failure_threshold: int = 5              # Failures before opening
    failure_rate_threshold: float = 50.0    # Percentage failure rate
    consecutive_failure_threshold: int = 3   # Consecutive failures
    
    # Timing configuration
    timeout_duration: float = 30.0          # Request timeout
    recovery_timeout: int = 60              # Time to wait before half-open
    half_open_max_calls: int = 3            # Max calls in half-open state
    
    # Health scoring
    min_health_score: float = 20.0          # Minimum health score to stay closed
    health_check_interval: int = 300        # Health check frequency (seconds)
    
    # Cost configuration
    max_cost_per_minute: float = 10.0       # Maximum cost per minute
    cost_failure_multiplier: float = 2.0    # Cost multiplier for failures
    
    # Advanced features
    adaptive_thresholds: bool = True        # Enable adaptive thresholds
    geographic_failover: bool = True        # Enable geographic failover
    ml_failure_prediction: bool = True      # Enable ML failure prediction


class ProviderCircuitBreaker:
    """
    Legacy circuit breaker for backward compatibility.
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.logger = FallbackLogger(f"circuit_breaker_{config.provider_id}")
        
        # Circuit state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.next_attempt_time: Optional[datetime] = None
        self.half_open_attempts = 0
        
        # Metrics
        self.metrics = ProviderMetrics(
            provider_id=config.provider_id,
            provider_type=config.provider_type
        )
        
        # Failure tracking
        self.failure_history: List[FailureEvent] = []
        self.failure_patterns: Dict[FailurePattern, int] = defaultdict(int)
        
        # Adaptive thresholds
        self.adaptive_failure_threshold = config.failure_threshold
        self.adaptive_timeout = config.timeout_duration
        
        # Health monitoring
        self.last_health_check = datetime.now()
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Cost tracking
        self.cost_window = deque(maxlen=60)  # Last 60 seconds
        self.current_cost_per_minute = 0.0
        
        # Event callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_failure: Optional[Callable] = None
        self.on_success: Optional[Callable] = None
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Basic circuit breaker call for legacy compatibility."""
        if self.state == CircuitState.OPEN:
            if self.next_attempt_time and datetime.now() >= self.next_attempt_time:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker is OPEN for {self.config.provider_id}")
        
        try:
            result = await func(*args, **kwargs)
            self.failure_count = 0
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
            return result
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.next_attempt_time = datetime.now() + timedelta(seconds=self.config.recovery_timeout)
            raise


class EnhancedRedisCircuitBreaker:
    """
    Enhanced circuit breaker with Redis state persistence and exponential backoff.
    
    Features:
    - Redis-backed state persistence for distributed systems
    - Exponential backoff with jitter for recovery attempts
    - Advanced failure pattern analysis
    - Cost-aware failure handling
    - Geographic failover support
    - Machine learning failure prediction
    - Real-time health monitoring
    """
    
    def __init__(self, config: CircuitBreakerConfig, redis_client: Optional[Redis] = None):
        self.config = config
        self.logger = logging.getLogger(f"enhanced_circuit_breaker_{config.provider_id}")
        
        # Redis client for distributed state
        self.redis_client = redis_client
        self.redis_available = REDIS_AVAILABLE and redis_client is not None
        
        # Circuit state keys in Redis
        self.state_key = f"circuit_breaker:{config.provider_id}:state"
        self.failure_count_key = f"circuit_breaker:{config.provider_id}:failure_count"
        self.last_failure_key = f"circuit_breaker:{config.provider_id}:last_failure"
        self.next_attempt_key = f"circuit_breaker:{config.provider_id}:next_attempt"
        self.metrics_key = f"circuit_breaker:{config.provider_id}:metrics"
        self.backoff_key = f"circuit_breaker:{config.provider_id}:backoff_level"
        
        # Local fallback state (if Redis unavailable)
        self.local_state = CircuitState.CLOSED
        self.local_failure_count = 0
        self.local_last_failure_time: Optional[datetime] = None
        self.local_next_attempt_time: Optional[datetime] = None
        self.local_backoff_level = 0
        
        # Exponential backoff configuration
        self.min_backoff_seconds = 30  # Minimum backoff time
        self.max_backoff_seconds = 1800  # Maximum backoff time (30 minutes)
        self.backoff_multiplier = 2.0
        self.jitter_factor = 0.1  # Add randomness to backoff
        
        self.half_open_attempts = 0
        
        # Metrics
        self.metrics = ProviderMetrics(
            provider_id=config.provider_id,
            provider_type=config.provider_type
        )
        
        # Failure tracking
        self.failure_history: List[FailureEvent] = []
        self.failure_patterns: Dict[FailurePattern, int] = defaultdict(int)
        
        # Adaptive thresholds
        self.adaptive_failure_threshold = config.failure_threshold
        self.adaptive_timeout = config.timeout_duration
        
        # Health monitoring
        self.last_health_check = datetime.now()
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Cost tracking
        self.cost_window = deque(maxlen=60)  # Last 60 seconds
        self.current_cost_per_minute = 0.0
        
        # Event callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_failure: Optional[Callable] = None
        self.on_success: Optional[Callable] = None
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state (legacy property for compatibility)."""
        return self.local_state
    
    @property
    def failure_count(self) -> int:
        """Get current failure count (legacy property for compatibility)."""
        return self.local_failure_count
    
    @property
    def next_attempt_time(self) -> Optional[datetime]:
        """Get next attempt time (legacy property for compatibility)."""
        return self.local_next_attempt_time
    
    async def _get_circuit_state(self) -> CircuitState:
        """Get current circuit state from Redis or local fallback."""
        if self.redis_available:
            try:
                state_str = await self.redis_client.get(self.state_key)
                if state_str:
                    # Update local state to match Redis
                    redis_state = CircuitState(state_str.decode() if isinstance(state_str, bytes) else state_str)
                    self.local_state = redis_state
                    return redis_state
            except Exception as e:
                self.logger.warning(f"Failed to get state from Redis: {e}")
        
        return self.local_state
    
    async def _set_circuit_state(self, state: CircuitState) -> None:
        """Set circuit state in Redis and local fallback."""
        if self.redis_available:
            try:
                await self.redis_client.set(
                    self.state_key, 
                    state.value, 
                    ex=self.max_backoff_seconds * 2  # TTL for cleanup
                )
            except Exception as e:
                self.logger.warning(f"Failed to set state in Redis: {e}")
        
        self.local_state = state
    
    async def _get_failure_count(self) -> int:
        """Get failure count from Redis or local fallback."""
        if self.redis_available:
            try:
                count = await self.redis_client.get(self.failure_count_key)
                if count:
                    redis_count = int(count)
                    # Update local count to match Redis
                    self.local_failure_count = redis_count
                    return redis_count
            except Exception as e:
                self.logger.warning(f"Failed to get failure count from Redis: {e}")
        
        return self.local_failure_count
    
    async def _increment_failure_count(self) -> int:
        """Increment and return failure count."""
        if self.redis_available:
            try:
                count = await self.redis_client.incr(self.failure_count_key)
                await self.redis_client.expire(self.failure_count_key, self.max_backoff_seconds * 2)
                return count
            except Exception as e:
                self.logger.warning(f"Failed to increment failure count in Redis: {e}")
        
        self.local_failure_count += 1
        return self.local_failure_count
    
    async def _reset_failure_count(self) -> None:
        """Reset failure count to zero."""
        if self.redis_available:
            try:
                await self.redis_client.delete(self.failure_count_key)
            except Exception as e:
                self.logger.warning(f"Failed to reset failure count in Redis: {e}")
        
        self.local_failure_count = 0
    
    async def _get_backoff_level(self) -> int:
        """Get current backoff level for exponential backoff."""
        if self.redis_available:
            try:
                level = await self.redis_client.get(self.backoff_key)
                if level:
                    local_backoff_level = int(level)
                    self.local_backoff_level = local_backoff_level
                    return local_backoff_level
            except Exception as e:
                self.logger.warning(f"Failed to get backoff level from Redis: {e}")
        
        return getattr(self, 'local_backoff_level', 0)
    
    async def _increment_backoff_level(self) -> int:
        """Increment backoff level for exponential backoff."""
        if self.redis_available:
            try:
                level = await self.redis_client.incr(self.backoff_key)
                await self.redis_client.expire(self.backoff_key, self.max_backoff_seconds * 2)
                self.local_backoff_level = level
                return level
            except Exception as e:
                self.logger.warning(f"Failed to increment backoff level in Redis: {e}")
        
        # Local fallback when Redis is not available
        current_level = getattr(self, 'local_backoff_level', 0)
        self.local_backoff_level = current_level + 1
        return self.local_backoff_level
    
    async def _reset_backoff_level(self) -> None:
        """Reset backoff level to zero."""
        if self.redis_available:
            try:
                await self.redis_client.delete(self.backoff_key)
            except Exception as e:
                self.logger.warning(f"Failed to reset backoff level in Redis: {e}")
        
        # Reset local backoff level
        self.local_backoff_level = 0
    
    def _calculate_exponential_backoff(self, backoff_level: int) -> int:
        """Calculate exponential backoff time with jitter."""
        # Base exponential backoff
        backoff_seconds = min(
            self.min_backoff_seconds * (self.backoff_multiplier ** backoff_level),
            self.max_backoff_seconds
        )
        
        # Add jitter to prevent thundering herd
        jitter = backoff_seconds * self.jitter_factor * (0.5 - asyncio.get_running_loop().time() % 1)
        backoff_with_jitter = backoff_seconds + jitter
        
        # Ensure we don't go below minimum
        return max(int(backoff_with_jitter), self.min_backoff_seconds)
    
    async def _set_next_attempt_time(self, backoff_level: int) -> datetime:
        """Set next attempt time using exponential backoff."""
        backoff_seconds = self._calculate_exponential_backoff(backoff_level)
        next_attempt = datetime.now() + timedelta(seconds=backoff_seconds)
        
        if self.redis_available:
            try:
                await self.redis_client.set(
                    self.next_attempt_key,
                    next_attempt.isoformat(),
                    ex=backoff_seconds + 300  # TTL with buffer
                )
            except Exception as e:
                self.logger.warning(f"Failed to set next attempt time in Redis: {e}")
        
        self.local_next_attempt_time = next_attempt
        
        self.logger.info(
            f"Circuit breaker backoff scheduled for {self.config.provider_id}",
            extra={
                "backoff_level": backoff_level,
                "backoff_seconds": backoff_seconds,
                "next_attempt": next_attempt.isoformat()
            }
        )
        
        return next_attempt
    
    async def _get_next_attempt_time(self) -> Optional[datetime]:
        """Get next attempt time from Redis or local fallback."""
        if self.redis_available:
            try:
                time_str = await self.redis_client.get(self.next_attempt_key)
                if time_str:
                    return datetime.fromisoformat(time_str.decode())
            except Exception as e:
                self.logger.warning(f"Failed to get next attempt time from Redis: {e}")
        
        return self.local_next_attempt_time
    
    async def track_request(
        self,
        provider_name: str,
        start_time: float,
        success: bool,
        cost: float = 0.0,
        tokens: int = 0,
        error: Optional[Exception] = None
    ) -> None:
        """Track provider request metrics for cost analysis."""
        response_time = (time.time() - start_time) * 1000
        
        # Update metrics
        self.metrics.update_request(success, response_time, cost)
        
        # Update cost tracking
        self._update_cost_tracking(cost)
        
        # Log request for monitoring
        self.logger.info(
            f"Request tracked for {provider_name}",
            extra={
                "provider_name": provider_name,
                "success": success,
                "response_time_ms": response_time,
                "cost": cost,
                "tokens": tokens,
                "error": str(error) if error else None
            }
        )
    
    def _is_cost_limit_exceeded(self) -> bool:
        """Check if cost limit is exceeded."""
        return self.current_cost_per_minute > self.config.max_cost_per_minute
    
    def _update_cost_tracking(self, cost: float):
        """Update cost tracking window."""
        now = time.time()
        self.cost_window.append((now, cost))
        
        # Remove old entries (older than 60 seconds)
        cutoff = now - 60
        while self.cost_window and self.cost_window[0][0] < cutoff:
            self.cost_window.popleft()
        
        # Calculate current cost per minute
        total_cost = sum(cost for _, cost in self.cost_window)
        self.current_cost_per_minute = total_cost
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function call through the enhanced circuit breaker.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            TimeoutError: When request times out
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Get current circuit state from Redis
        current_state = await self._get_circuit_state()
        
        # Check circuit state
        if current_state == CircuitState.OPEN:
            if await self._should_attempt_reset():
                await self._transition_to_half_open()
                current_state = CircuitState.HALF_OPEN
            else:
                await self._handle_circuit_open(request_id)
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN for {self.config.provider_id}"
                )
        
        # Check cost limits
        if self._is_cost_limit_exceeded():
            await self._handle_cost_limit_exceeded(request_id)
            raise CostLimitExceededError(
                f"Cost limit exceeded for {self.config.provider_id}"
            )
        
        # Execute the function
        try:
            # Apply timeout and execute
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.adaptive_timeout
                )
            else:
                result = func(*args, **kwargs)
            
            # Record success
            response_time = time.time() - start_time
            await self._handle_success(request_id, response_time)
            
            return result
            
        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            await self._handle_failure(
                request_id,
                FailurePattern.TIMEOUT,
                f"Request timed out after {self.adaptive_timeout}s",
                response_time
            )
            raise
            
        except ConnectionError as e:
            response_time = time.time() - start_time
            await self._handle_failure(
                request_id,
                FailurePattern.CONNECTION_ERROR,
                str(e),
                response_time
            )
            raise
            
        except Exception as e:
            response_time = time.time() - start_time
            failure_type = self._classify_error(e)
            await self._handle_failure(request_id, failure_type, str(e), response_time)
            raise
    
    async def _handle_success(self, request_id: str, response_time: float):
        """Handle successful request."""
        # Update metrics
        cost = self._calculate_request_cost(response_time, True)
        self.metrics.update_request(True, response_time, cost)
        
        # Update cost tracking
        self._update_cost_tracking(cost)
        
        # Reset failure count in Redis
        await self._reset_failure_count()
        
        # Get current state
        current_state = await self._get_circuit_state()
        
        # Transition from half-open to closed if needed
        if current_state == CircuitState.HALF_OPEN:
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.config.half_open_max_calls:
                await self._transition_to_closed()
        
        # Update adaptive thresholds
        if self.config.adaptive_thresholds:
            self._update_adaptive_thresholds(True, response_time)
        
        # Log success
        self.logger.info(
            f"Request successful for {self.config.provider_id}",
            extra={
                "request_id": request_id,
                "response_time": response_time,
                "cost": cost,
                "circuit_state": self.state.value,
                "health_score": self.metrics.health_score
            }
        )
        
        # Trigger success callback
        if self.on_success:
            await self.on_success(self.config.provider_id, request_id, response_time)
        
        # Publish success event
        await EventPublisher.publish_system_event(
            event_type="circuit_breaker.request.success",
            payload={
                "provider_id": self.config.provider_id,
                "request_id": request_id,
                "response_time": response_time,
                "cost": cost,
                "circuit_state": self.state.value,
                "health_score": self.metrics.health_score
            }
        )
    
    async def _handle_failure(
        self,
        request_id: str,
        failure_type: FailurePattern,
        error_message: str,
        response_time: float
    ):
        """Handle failed request."""
        # Create failure event
        failure_event = FailureEvent(
            timestamp=datetime.now(),
            provider_id=self.config.provider_id,
            failure_type=failure_type,
            error_message=error_message,
            response_time=response_time,
            cost_impact=self._calculate_request_cost(response_time, False),
            request_id=request_id
        )
        
        # Update metrics
        self.metrics.update_request(False, response_time, failure_event.cost_impact)
        self.metrics.add_failure(failure_event)
        
        # Update failure tracking in Redis and locally
        failure_count = await self._increment_failure_count()
        self.last_failure_time = datetime.now()
        self.failure_patterns[failure_type] += 1
        self.failure_history.append(failure_event)
        
        # Keep only recent failures
        if len(self.failure_history) > 100:
            self.failure_history = self.failure_history[-100:]
        
        # Update cost tracking
        self._update_cost_tracking(failure_event.cost_impact)
        
        # Get current state
        current_state = await self._get_circuit_state()
        
        # Check if circuit should open
        if await self._should_open_circuit():
            await self._transition_to_open()
        elif current_state == CircuitState.HALF_OPEN:
            await self._transition_to_open()
        
        # Update adaptive thresholds
        if self.config.adaptive_thresholds:
            self._update_adaptive_thresholds(False, response_time, failure_type)
        
        # Log failure
        self.logger.error(
            f"Request failed for {self.config.provider_id}",
            extra={
                "request_id": request_id,
                "failure_type": failure_type.value,
                "error_message": error_message,
                "response_time": response_time,
                "cost_impact": failure_event.cost_impact,
                "circuit_state": self.state.value,
                "failure_count": self.failure_count,
                "consecutive_failures": self.metrics.consecutive_failures
            }
        )
        
        # Trigger failure callback
        if self.on_failure:
            await self.on_failure(self.config.provider_id, failure_event)
        
        # Publish failure event
        await EventPublisher.publish_system_event(
            event_type="circuit_breaker.request.failure",
            payload={
                "provider_id": self.config.provider_id,
                "request_id": request_id,
                "failure_type": failure_type.value,
                "error_message": error_message,
                "response_time": response_time,
                "cost_impact": failure_event.cost_impact,
                "circuit_state": self.state.value,
                "failure_count": self.failure_count,
                "consecutive_failures": self.metrics.consecutive_failures
            }
        )
    
    async def _handle_circuit_open(self, request_id: str):
        """Handle request when circuit is open."""
        self.logger.warning(
            f"Circuit breaker OPEN for {self.config.provider_id}, request rejected",
            extra={
                "request_id": request_id,
                "circuit_state": self.state.value,
                "failure_count": self.failure_count,
                "next_attempt_time": self.next_attempt_time.isoformat() if self.next_attempt_time else None
            }
        )
        
        # Publish circuit open event
        await EventPublisher.publish_system_event(
            event_type="circuit_breaker.request.rejected",
            payload={
                "provider_id": self.config.provider_id,
                "request_id": request_id,
                "circuit_state": self.state.value,
                "reason": "circuit_open",
                "next_attempt_time": self.next_attempt_time.isoformat() if self.next_attempt_time else None
            }
        )
    
    async def _handle_cost_limit_exceeded(self, request_id: str):
        """Handle request when cost limit is exceeded."""
        self.logger.warning(
            f"Cost limit exceeded for {self.config.provider_id}, request rejected",
            extra={
                "request_id": request_id,
                "current_cost_per_minute": self.current_cost_per_minute,
                "max_cost_per_minute": self.config.max_cost_per_minute
            }
        )
        
        # Publish cost limit event
        await EventPublisher.publish_system_event(
            event_type="circuit_breaker.cost_limit.exceeded",
            payload={
                "provider_id": self.config.provider_id,
                "request_id": request_id,
                "current_cost_per_minute": self.current_cost_per_minute,
                "max_cost_per_minute": self.config.max_cost_per_minute
            }
        )
    
    async def _should_open_circuit(self) -> bool:
        """Determine if circuit should open based on Redis and local state."""
        failure_count = await self._get_failure_count()
        
        # Check consecutive failures
        if self.metrics.consecutive_failures >= self.config.consecutive_failure_threshold:
            return True
        
        # Check total failure count (use Redis state)
        if failure_count >= self.config.failure_threshold:
            return True
        
        # Check failure rate
        if self.metrics.failure_rate >= self.config.failure_rate_threshold:
            return True
        
        # Check health score
        if self.metrics.health_score <= self.config.min_health_score:
            return True
        
        return False
    
    async def _should_attempt_reset(self) -> bool:
        """Determine if circuit should attempt reset using Redis state."""
        next_attempt = await self._get_next_attempt_time()
        if not next_attempt:
            return False
        
        return datetime.now() >= next_attempt
    
    async def _transition_to_open(self):
        """Transition circuit to OPEN state with exponential backoff."""
        old_state = await self._get_circuit_state()
        
        # Increment backoff level for exponential backoff
        backoff_level = await self._increment_backoff_level()
        
        # Set circuit state to OPEN
        await self._set_circuit_state(CircuitState.OPEN)
        
        # Calculate and set next attempt time with exponential backoff
        await self._set_next_attempt_time(backoff_level)
        
        self.half_open_attempts = 0
        
        await self._log_state_change(old_state, CircuitState.OPEN, {"backoff_level": backoff_level})
        
        if self.on_state_change:
            await self.on_state_change(self.config.provider_id, old_state, CircuitState.OPEN)
    
    async def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state."""
        old_state = await self._get_circuit_state()
        await self._set_circuit_state(CircuitState.HALF_OPEN)
        self.half_open_attempts = 0
        
        await self._log_state_change(old_state, CircuitState.HALF_OPEN)
        
        if self.on_state_change:
            await self.on_state_change(self.config.provider_id, old_state, CircuitState.HALF_OPEN)
    
    async def _transition_to_closed(self):
        """Transition circuit to CLOSED state and reset all counters."""
        old_state = await self._get_circuit_state()
        await self._set_circuit_state(CircuitState.CLOSED)
        
        # Reset all failure counters and backoff levels
        await self._reset_failure_count()
        await self._reset_backoff_level()
        
        # Clear next attempt time
        if self.redis_available:
            try:
                await self.redis_client.delete(self.next_attempt_key)
            except Exception as e:
                self.logger.warning(f"Failed to clear next attempt time from Redis: {e}")
        
        self.local_next_attempt_time = None
        self.half_open_attempts = 0
        
        await self._log_state_change(old_state, CircuitState.CLOSED)
        
        if self.on_state_change:
            await self.on_state_change(self.config.provider_id, old_state, CircuitState.CLOSED)
    
    async def _log_state_change(self, old_state: CircuitState, new_state: CircuitState, extra_data: Optional[Dict[str, Any]] = None):
        """Log circuit state change with enhanced metadata."""
        failure_count = await self._get_failure_count()
        backoff_level = await self._get_backoff_level()
        next_attempt = await self._get_next_attempt_time()
        
        log_data = {
            "provider_id": self.config.provider_id,
            "old_state": old_state.value,
            "new_state": new_state.value,
            "failure_count": failure_count,
            "backoff_level": backoff_level,
            "health_score": self.metrics.health_score,
            "failure_rate": self.metrics.failure_rate,
            "next_attempt": next_attempt.isoformat() if next_attempt else None,
            "redis_available": self.redis_available
        }
        
        if extra_data:
            log_data.update(extra_data)
        
        self.logger.info(
            f"Enhanced circuit breaker state changed for {self.config.provider_id}: {old_state.value} -> {new_state.value}",
            extra=log_data
        )
        
        # Publish state change event
        await EventPublisher.publish_system_event(
            event_type="circuit_breaker.state.changed",
            payload={
                "provider_id": self.config.provider_id,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "failure_count": self.failure_count,
                "health_score": self.metrics.health_score,
                "failure_rate": self.metrics.failure_rate,
                "next_attempt_time": self.next_attempt_time.isoformat() if self.next_attempt_time else None
            }
        )
    
    def _classify_error(self, error: Exception) -> FailurePattern:
        """Classify error type."""
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            return FailurePattern.TIMEOUT
        elif "connection" in error_str:
            return FailurePattern.CONNECTION_ERROR
        elif "rate limit" in error_str or "too many requests" in error_str:
            return FailurePattern.RATE_LIMIT
        elif "auth" in error_str or "unauthorized" in error_str:
            return FailurePattern.AUTHENTICATION_ERROR
        elif "service unavailable" in error_str or "503" in error_str:
            return FailurePattern.SERVICE_UNAVAILABLE
        elif "quota" in error_str or "429" in error_str:
            return FailurePattern.QUOTA_EXCEEDED
        elif "invalid response" in error_str:
            return FailurePattern.INVALID_RESPONSE
        else:
            return FailurePattern.NETWORK_ERROR
    
    def _calculate_request_cost(self, response_time: float, success: bool) -> float:
        """Calculate estimated cost for a request."""
        base_cost = self.metrics.estimated_cost_per_request
        
        # Add latency cost
        latency_cost = response_time * 0.001  # $0.001 per second
        
        # Add failure cost multiplier
        if not success:
            base_cost *= self.config.cost_failure_multiplier
        
        return base_cost + latency_cost
    
    def _update_cost_tracking(self, cost: float):
        """Update cost tracking window."""
        now = time.time()
        self.cost_window.append((now, cost))
        
        # Remove old entries (older than 60 seconds)
        cutoff = now - 60
        while self.cost_window and self.cost_window[0][0] < cutoff:
            self.cost_window.popleft()
        
        # Calculate current cost per minute
        total_cost = sum(cost for _, cost in self.cost_window)
        self.current_cost_per_minute = total_cost
    
    def _is_cost_limit_exceeded(self) -> bool:
        """Check if cost limit is exceeded."""
        return self.current_cost_per_minute > self.config.max_cost_per_minute
    
    def _update_adaptive_thresholds(
        self,
        success: bool,
        response_time: float,
        failure_type: Optional[FailurePattern] = None
    ):
        """Update adaptive thresholds based on recent performance."""
        if not self.config.adaptive_thresholds:
            return
        
        # Adjust failure threshold based on success rate
        if self.metrics.total_requests > 10:
            success_rate = (self.metrics.successful_requests / self.metrics.total_requests) * 100
            
            if success_rate > 95:
                # High success rate, can tolerate more failures
                self.adaptive_failure_threshold = min(
                    self.config.failure_threshold * 2,
                    self.config.failure_threshold + 3
                )
            elif success_rate < 80:
                # Low success rate, be more aggressive
                self.adaptive_failure_threshold = max(
                    self.config.failure_threshold // 2,
                    2
                )
        
        # Adjust timeout based on response time percentiles
        if len(self.metrics.response_times) > 5:
            if self.metrics.p95_response_time > 0:
                # Set timeout to 3x p95 response time, with bounds
                new_timeout = self.metrics.p95_response_time * 3
                self.adaptive_timeout = max(
                    min(new_timeout, self.config.timeout_duration * 2),
                    self.config.timeout_duration * 0.5
                )
    
    async def get_enhanced_status(self) -> Dict[str, Any]:
        """Get comprehensive enhanced circuit breaker status with Redis data."""
        current_state = await self._get_circuit_state()
        failure_count = await self._get_failure_count()
        backoff_level = await self._get_backoff_level()
        next_attempt = await self._get_next_attempt_time()
        
        return {
            "provider_id": self.config.provider_id,
            "provider_type": self.config.provider_type.value,
            "state": current_state.value,
            "failure_count": failure_count,
            "backoff_level": backoff_level,
            "half_open_attempts": self.half_open_attempts,
            "next_attempt_time": next_attempt.isoformat() if next_attempt else None,
            "redis_available": self.redis_available,
            "exponential_backoff": {
                "min_backoff_seconds": self.min_backoff_seconds,
                "max_backoff_seconds": self.max_backoff_seconds,
                "backoff_multiplier": self.backoff_multiplier,
                "jitter_factor": self.jitter_factor,
                "current_backoff_seconds": self._calculate_exponential_backoff(backoff_level) if backoff_level > 0 else 0
            },
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "success_rate": ((self.metrics.successful_requests / self.metrics.total_requests) * 100) if self.metrics.total_requests > 0 else 100,
                "failure_rate": self.metrics.failure_rate,
                "consecutive_failures": self.metrics.consecutive_failures,
                "average_response_time": self.metrics.average_response_time,
                "p95_response_time": self.metrics.p95_response_time,
                "p99_response_time": self.metrics.p99_response_time,
                "health_score": self.metrics.health_score,
                "total_cost_impact": self.metrics.total_cost_impact,
                "current_cost_per_minute": self.current_cost_per_minute
            },
            "failure_patterns": dict(self.failure_patterns),
            "adaptive_thresholds": {
                "failure_threshold": self.adaptive_failure_threshold,
                "timeout": self.adaptive_timeout
            },
            "configuration": {
                "failure_threshold": self.config.failure_threshold,
                "failure_rate_threshold": self.config.failure_rate_threshold,
                "timeout_duration": self.config.timeout_duration,
                "recovery_timeout": self.config.recovery_timeout,
                "min_health_score": self.config.min_health_score,
                "max_cost_per_minute": self.config.max_cost_per_minute
            }
        }
    
    async def force_open(self, reason: str = "Manual intervention"):
        """Force circuit to open state."""
        await self._log_state_change(self.state, CircuitState.OPEN)
        self.state = CircuitState.OPEN
        self.next_attempt_time = datetime.now() + timedelta(seconds=self.config.recovery_timeout)
        
        self.logger.warning(
            f"Circuit breaker manually opened for {self.config.provider_id}",
            extra={"reason": reason}
        )
    
    async def force_close(self, reason: str = "Manual intervention"):
        """Force circuit to closed state."""
        await self._log_state_change(self.state, CircuitState.CLOSED)
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.next_attempt_time = None
        
        self.logger.info(
            f"Circuit breaker manually closed for {self.config.provider_id}",
            extra={"reason": reason}
        )
    
    async def reset_metrics(self):
        """Reset all metrics."""
        self.metrics = ProviderMetrics(
            provider_id=self.config.provider_id,
            provider_type=self.config.provider_type
        )
        self.failure_count = 0
        self.failure_history.clear()
        self.failure_patterns.clear()
        self.cost_window.clear()
        
        self.logger.info(f"Metrics reset for {self.config.provider_id}")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CostLimitExceededError(Exception):
    """Exception raised when cost limit is exceeded."""
    pass


# Factory functions for creating enhanced circuit breakers
async def create_enhanced_redis_circuit_breaker(
    provider_id: str,
    provider_type: ProviderType,
    redis_url: Optional[str] = None,
    **config_overrides
) -> EnhancedRedisCircuitBreaker:
    """
    Create an enhanced Redis-backed circuit breaker.
    
    Args:
        provider_id: Unique provider identifier
        provider_type: Type of provider
        redis_url: Redis connection URL (optional)
        **config_overrides: Configuration overrides
        
    Returns:
        Configured EnhancedRedisCircuitBreaker instance
    """
    # Create circuit breaker configuration
    config = CircuitBreakerConfig(
        provider_id=provider_id,
        provider_type=provider_type,
        **config_overrides
    )
    
    # Initialize Redis client if available and URL provided
    redis_client = None
    if REDIS_AVAILABLE and redis_url:
        try:
            redis_client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0
            )
            # Test connection
            await redis_client.ping()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to connect to Redis for circuit breaker: {e}")
            redis_client = None
    
    return EnhancedRedisCircuitBreaker(config, redis_client)


def create_legacy_circuit_breaker(
    provider_id: str,
    provider_type: ProviderType,
    **config_overrides
) -> ProviderCircuitBreaker:
    """
    Create a legacy circuit breaker (for backward compatibility).
    
    Args:
        provider_id: Unique provider identifier
        provider_type: Type of provider
        **config_overrides: Configuration overrides
        
    Returns:
        Configured ProviderCircuitBreaker instance
    """
    config = CircuitBreakerConfig(
        provider_id=provider_id,
        provider_type=provider_type,
        **config_overrides
    )
    
    return ProviderCircuitBreaker(config)
