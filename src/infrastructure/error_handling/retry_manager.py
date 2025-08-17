"""
Enhanced Error Handling with Intelligent Retry Logic
===================================================
Production-grade retry system with exponential backoff, circuit breaker,
and comprehensive error categorization for the AI Teddy Bear platform.
"""

import asyncio
import time
import random
import logging
from typing import Any, Callable, Dict, List, Optional, Type, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import functools
from contextlib import asynccontextmanager

# Third-party imports
import httpx
import redis.asyncio as redis
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError

# Use existing exceptions
from ..exceptions import (
    AITeddyBearException,
    DatabaseError,
    DatabaseTimeoutError,
    AIServiceError,
    RateLimitExceeded,
    ServiceUnavailableError
)
from src.core.exceptions import (
    AuthenticationError,
    SafetyViolationError,
    COPPAViolation
)
from ..error_handler import CircuitBreaker


class ErrorSeverity(Enum):
    """Error severity levels for categorization."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for intelligent handling."""
    NETWORK = "network"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    EXTERNAL_API = "external_api"
    SYSTEM = "system"
    CHILD_SAFETY = "child_safety"
    COPPA_COMPLIANCE = "coppa_compliance"


class RetryStrategy(Enum):
    """Retry strategies for different error types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"
    NO_RETRY = "no_retry"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    
    # Error type specific settings
    retryable_exceptions: List[Type[Exception]] = field(default_factory=lambda: [
        ConnectionError,
        TimeoutError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        OperationalError,  # Database connection issues
        redis.ConnectionError,
    ])
    
    non_retryable_exceptions: List[Type[Exception]] = field(default_factory=lambda: [
        ValueError,
        TypeError,
        KeyError,
        IntegrityError,  # Database constraint violations
        PermissionError,
        AuthenticationError,
    ])


@dataclass
class ErrorContext:
    """Context information for error handling."""
    correlation_id: str
    user_id: Optional[str] = None
    child_id: Optional[str] = None
    operation: Optional[str] = None
    service: Optional[str] = None
    endpoint: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    attempt_number: int
    delay: float
    exception: Exception
    timestamp: datetime = field(default_factory=datetime.now)
    
    
@dataclass
class ErrorReport:
    """Comprehensive error report."""
    correlation_id: str
    error_category: ErrorCategory
    severity: ErrorSeverity
    exception: Exception
    context: ErrorContext
    retry_attempts: List[RetryAttempt] = field(default_factory=list)
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    total_retry_duration: float = 0.0


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


# Using existing CircuitBreaker from error_handler.py instead of duplicating


class EnhancedRetryManager:
    """
    Enhanced retry manager with intelligent error handling.
    
    Features:
    - Exponential backoff with jitter
    - Circuit breaker pattern
    - Error categorization and reporting
    - COPPA compliance logging
    - Child safety specific handling
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ai_teddy_bear.retry_manager")
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_reports: List[ErrorReport] = []
        self.redis_client: Optional[redis.Redis] = None
        
        # Default configurations for different services
        self.service_configs = {
            "database": RetryConfig(
                max_attempts=3,
                initial_delay=0.5,
                max_delay=10.0,
                retryable_exceptions=[OperationalError, ConnectionError]
            ),
            "external_api": RetryConfig(
                max_attempts=5,
                initial_delay=1.0,
                max_delay=30.0,
                retryable_exceptions=[httpx.ConnectTimeout, httpx.ReadTimeout, ConnectionError]
            ),
            "redis": RetryConfig(
                max_attempts=3,
                initial_delay=0.2,
                max_delay=5.0,
                retryable_exceptions=[redis.ConnectionError, ConnectionError]
            ),
            "child_safety": RetryConfig(
                max_attempts=2,  # Fewer retries for safety-critical operations
                initial_delay=0.1,
                max_delay=2.0,
                strategy=RetryStrategy.FIXED_DELAY
            )
        }
    
    def set_redis_client(self, redis_client: redis.Redis):
        """Set Redis client for error reporting."""
        self.redis_client = redis_client
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60,
                success_threshold=3,
                service_name=service_name
            )
        return self.circuit_breakers[service_name]
    
    def categorize_error(self, exception: Exception) -> Tuple[ErrorCategory, ErrorSeverity]:
        """Categorize error and determine severity."""
        # Database errors
        if isinstance(exception, (SQLAlchemyError, OperationalError)):
            severity = ErrorSeverity.HIGH if isinstance(exception, OperationalError) else ErrorSeverity.MEDIUM
            return ErrorCategory.DATABASE, severity
        
        # Network errors
        if isinstance(exception, (ConnectionError, TimeoutError, httpx.ConnectTimeout, httpx.ReadTimeout)):
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
        
        # Authentication/Authorization
        if "auth" in str(exception).lower() or "permission" in str(exception).lower():
            return ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH
        
        # Child safety (critical priority)
        if "child" in str(exception).lower() or "safety" in str(exception).lower():
            return ErrorCategory.CHILD_SAFETY, ErrorSeverity.CRITICAL
        
        # COPPA compliance
        if "coppa" in str(exception).lower() or "compliance" in str(exception).lower():
            return ErrorCategory.COPPA_COMPLIANCE, ErrorSeverity.CRITICAL
        
        # Rate limiting
        if "rate" in str(exception).lower() and "limit" in str(exception).lower():
            return ErrorCategory.RATE_LIMIT, ErrorSeverity.MEDIUM
        
        # Validation errors
        if isinstance(exception, (ValueError, TypeError, KeyError)):
            return ErrorCategory.VALIDATION, ErrorSeverity.LOW
        
        # Default to system error
        return ErrorCategory.SYSTEM, ErrorSeverity.MEDIUM
    
    def calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for retry attempt."""
        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.initial_delay * (config.exponential_base ** (attempt - 1))
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.initial_delay * attempt
        elif config.strategy == RetryStrategy.FIXED_DELAY:
            delay = config.initial_delay
        elif config.strategy == RetryStrategy.IMMEDIATE:
            delay = 0.0
        else:  # NO_RETRY
            return 0.0
        
        # Apply maximum delay limit
        delay = min(delay, config.max_delay)
        
        # Add jitter to prevent thundering herd
        if config.jitter:
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    def should_retry(self, exception: Exception, attempt: int, config: RetryConfig) -> bool:
        """Determine if operation should be retried."""
        if attempt >= config.max_attempts:
            return False
        
        if config.strategy == RetryStrategy.NO_RETRY:
            return False
        
        # Check if exception type is retryable
        if any(isinstance(exception, exc_type) for exc_type in config.non_retryable_exceptions):
            return False
        
        if any(isinstance(exception, exc_type) for exc_type in config.retryable_exceptions):
            return True
        
        # Default: retry for most exceptions except validation errors
        return not isinstance(exception, (ValueError, TypeError, KeyError))
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        service_name: str = "default",
        context: Optional[ErrorContext] = None,
        config: Optional[RetryConfig] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with intelligent retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            service_name: Service identifier for circuit breaker
            context: Error context for logging
            config: Retry configuration
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries fail
        """
        # Use service-specific config or default
        if config is None:
            config = self.service_configs.get(service_name, RetryConfig())
        
        if context is None:
            context = ErrorContext(correlation_id=f"retry_{int(time.time())}")
        
        # Check circuit breaker
        circuit_breaker = self.get_circuit_breaker(service_name)
        if not circuit_breaker.should_allow_request():
            raise Exception(f"Circuit breaker OPEN for service: {service_name}")
        
        # Initialize error report
        error_report = None
        last_exception = None
        start_time = time.time()
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Record success
                circuit_breaker.record_success()
                
                # Mark error as resolved if we had retries
                if error_report:
                    error_report.resolved = True
                    error_report.resolution_time = datetime.now()
                    error_report.total_retry_duration = time.time() - start_time
                
                self.logger.info(
                    f"Operation succeeded",
                    extra={
                        "service": service_name,
                        "correlation_id": context.correlation_id,
                        "attempt": attempt,
                        "total_attempts": config.max_attempts
                    }
                )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Categorize error
                error_category, severity = self.categorize_error(e)
                
                # Create error report on first failure
                if error_report is None:
                    error_report = ErrorReport(
                        correlation_id=context.correlation_id,
                        error_category=error_category,
                        severity=severity,
                        exception=e,
                        context=context
                    )
                    self.error_reports.append(error_report)
                
                # Record retry attempt
                if attempt < config.max_attempts and self.should_retry(e, attempt, config):
                    delay = self.calculate_delay(attempt, config)
                    
                    retry_attempt = RetryAttempt(
                        attempt_number=attempt,
                        delay=delay,
                        exception=e
                    )
                    error_report.retry_attempts.append(retry_attempt)
                    
                    self.logger.warning(
                        f"Operation failed, retrying in {delay:.2f}s",
                        extra={
                            "service": service_name,
                            "correlation_id": context.correlation_id,
                            "attempt": attempt,
                            "total_attempts": config.max_attempts,
                            "error": str(e),
                            "error_category": error_category.value,
                            "severity": severity.value,
                            "delay": delay
                        }
                    )
                    
                    # Log critical errors immediately
                    if severity == ErrorSeverity.CRITICAL:
                        await self._log_critical_error(error_report)
                    
                    # Wait before retry
                    if delay > 0:
                        await asyncio.sleep(delay)
                
                else:
                    # No more retries or non-retryable error
                    circuit_breaker.record_failure()
                    error_report.total_retry_duration = time.time() - start_time
                    
                    self.logger.error(
                        f"Operation failed after {attempt} attempts",
                        extra={
                            "service": service_name,
                            "correlation_id": context.correlation_id,
                            "total_attempts": attempt,
                            "error": str(e),
                            "error_category": error_category.value,
                            "severity": severity.value,
                            "total_duration": error_report.total_retry_duration
                        },
                        exc_info=True
                    )
                    
                    # Log to Redis for monitoring
                    await self._store_error_report(error_report)
                    
                    raise e
    
    async def _log_critical_error(self, error_report: ErrorReport):
        """Log critical errors for immediate attention."""
        critical_log = {
            "event_type": "critical_error",
            "correlation_id": error_report.correlation_id,
            "error_category": error_report.error_category.value,
            "severity": error_report.severity.value,
            "exception": str(error_report.exception),
            "context": {
                "user_id": error_report.context.user_id,
                "child_id": error_report.context.child_id,
                "operation": error_report.context.operation,
                "service": error_report.context.service
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Log to application logs
        self.logger.critical(
            "CRITICAL ERROR DETECTED",
            extra=critical_log
        )
        
        # Store in Redis for real-time monitoring
        if self.redis_client:
            try:
                await self.redis_client.lpush(
                    "critical_errors",
                    str(critical_log)
                )
                await self.redis_client.expire("critical_errors", 86400)  # 24 hours
            except Exception as e:
                self.logger.error(f"Failed to store critical error in Redis: {e}")
    
    async def _store_error_report(self, error_report: ErrorReport):
        """Store error report in Redis for monitoring."""
        if not self.redis_client:
            return
        
        try:
            report_data = {
                "correlation_id": error_report.correlation_id,
                "error_category": error_report.error_category.value,
                "severity": error_report.severity.value,
                "exception": str(error_report.exception),
                "retry_attempts": len(error_report.retry_attempts),
                "resolved": error_report.resolved,
                "total_duration": error_report.total_retry_duration,
                "timestamp": datetime.now().isoformat()
            }
            
            # Store in Redis with TTL
            key = f"error_report:{error_report.correlation_id}"
            await self.redis_client.setex(key, 86400, str(report_data))  # 24 hours
            
            # Add to error metrics
            await self.redis_client.hincrby("error_metrics", error_report.error_category.value, 1)
            await self.redis_client.hincrby("error_severity", error_report.severity.value, 1)
            
        except Exception as e:
            self.logger.error(f"Failed to store error report in Redis: {e}")
    
    async def get_error_metrics(self) -> Dict[str, Any]:
        """Get error metrics for monitoring."""
        if not self.redis_client:
            return {}
        
        try:
            # Get error counts by category and severity
            category_metrics = await self.redis_client.hgetall("error_metrics")
            severity_metrics = await self.redis_client.hgetall("error_severity")
            
            # Get circuit breaker states
            circuit_states = {
                name: breaker.state.value 
                for name, breaker in self.circuit_breakers.items()
            }
            
            return {
                "error_categories": {k.decode(): int(v) for k, v in category_metrics.items()},
                "error_severities": {k.decode(): int(v) for k, v in severity_metrics.items()},
                "circuit_breakers": circuit_states,
                "total_reports": len(self.error_reports),
                "resolved_reports": sum(1 for r in self.error_reports if r.resolved)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get error metrics: {e}")
            return {}
    
    def with_retry(
        self, 
        service_name: str = "default",
        config: Optional[RetryConfig] = None
    ):
        """Decorator for adding retry logic to functions."""
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                context = ErrorContext(
                    correlation_id=f"decorated_{int(time.time())}",
                    operation=func.__name__
                )
                
                return await self.execute_with_retry(
                    func, *args,
                    service_name=service_name,
                    context=context,
                    config=config,
                    **kwargs
                )
            return wrapper
        return decorator


# Global retry manager instance
retry_manager = EnhancedRetryManager()


# Convenience decorators
def with_database_retry(func):
    """Decorator for database operations with retry logic."""
    return retry_manager.with_retry(service_name="database")(func)


def with_api_retry(func):
    """Decorator for external API operations with retry logic."""
    return retry_manager.with_retry(service_name="external_api")(func)


def with_child_safety_retry(func):
    """Decorator for child safety operations with careful retry logic."""
    return retry_manager.with_retry(service_name="child_safety")(func)


# Context manager for manual retry handling
@asynccontextmanager
async def retry_context(
    service_name: str = "default",
    context: Optional[ErrorContext] = None,
    config: Optional[RetryConfig] = None
):
    """Context manager for manual retry handling."""
    if context is None:
        context = ErrorContext(correlation_id=f"context_{int(time.time())}")
    
    try:
        yield retry_manager
    except Exception as e:
        # Log error but don't retry in context manager
        category, severity = retry_manager.categorize_error(e)
        retry_manager.logger.error(
            f"Error in retry context: {e}",
            extra={
                "correlation_id": context.correlation_id,
                "service": service_name,
                "error_category": category.value,
                "severity": severity.value
            }
        )
        raise
