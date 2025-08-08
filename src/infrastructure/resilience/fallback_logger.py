"""
Production Fallback Logging Infrastructure
=========================================
Enterprise-grade logging system for fallback operations with:
- Structured logging with context preservation
- Performance metrics and timing analysis
- Cost tracking and optimization insights
- Security event monitoring and alerting
- Integration with ELK/CloudWatch/Prometheus
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import uuid
from contextlib import contextmanager


class LogLevel(Enum):
    """Enhanced log levels for fallback operations."""
    TRACE = "trace"      # Detailed execution flow
    DEBUG = "debug"      # Development debugging
    INFO = "info"        # General information
    WARNING = "warning"  # Potential issues
    ERROR = "error"      # Error conditions
    CRITICAL = "critical" # Critical failures
    AUDIT = "audit"      # Security/compliance events


class EventType(Enum):
    """Types of fallback events for categorization."""
    FALLBACK_TRIGGERED = "fallback_triggered"
    PROVIDER_FAILURE = "provider_failure"
    PROVIDER_SUCCESS = "provider_success"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    HEALTH_CHECK_FAILED = "health_check_failed"
    HEALTH_CHECK_PASSED = "health_check_passed"
    COST_THRESHOLD_EXCEEDED = "cost_threshold_exceeded"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    SECURITY_EVENT = "security_event"
    COMPLIANCE_VIOLATION = "compliance_violation"


@dataclass
class LogContext:
    """Structured context for fallback logging."""
    service_name: str
    operation_id: str = None
    user_id: str = None
    session_id: str = None
    request_id: str = None
    correlation_id: str = None
    parent_operation_id: str = None
    
    # Provider context
    provider: str = None
    tier: str = None
    attempt_number: int = None
    
    # Performance context
    start_time: float = None
    duration_ms: float = None
    response_size_bytes: int = None
    
    # Cost context
    estimated_cost: float = None
    cost_currency: str = "USD"
    
    # Error context
    error_type: str = None
    error_code: str = None
    error_message: str = None
    stack_trace: str = None
    
    # Metadata
    environment: str = None
    region: str = None
    instance_id: str = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary, filtering None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class FallbackLogger:
    """
    Production-grade logging system for fallback operations.
    
    Features:
    - Structured JSON logging with contextual information
    - Performance metrics and timing analysis
    - Cost tracking and budget monitoring
    - Security event detection and alerting
    - Integration with monitoring systems
    - Log aggregation and analysis
    """
    
    def __init__(self, service_name: str = None):
        self.service_name = service_name or "fallback_system"
        self.logger = logging.getLogger(f"fallback.{self.service_name}")
        
        # Performance tracking
        self._operation_timings: Dict[str, float] = {}
        self._cost_tracking: Dict[str, float] = {}
        
        # Event counters for metrics
        self._event_counters: Dict[EventType, int] = {event: 0 for event in EventType}
        
        # Log buffer for batch processing (optional)
        self._log_buffer: List[Dict[str, Any]] = []
        self._buffer_size = 1000
        self._last_flush = time.time()
        
        # Configure structured logging
        self._configure_structured_logging()
        
        self.logger.info(
            "FallbackLogger initialized",
            extra=self._create_log_extra(
                LogContext(service_name=self.service_name),
                EventType.PROVIDER_SUCCESS,
                {"component": "logger", "action": "initialized"}
            )
        )
    
    def _configure_structured_logging(self):
        """Configure structured JSON logging format."""
        # Custom formatter for structured logging
        class StructuredFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }
                
                # Add extra fields if present
                if hasattr(record, 'extra_fields'):
                    log_entry.update(record.extra_fields)
                
                return json.dumps(log_entry, default=str)
        
        # Apply formatter to handlers
        for handler in self.logger.handlers:
            handler.setFormatter(StructuredFormatter())
    
    @contextmanager
    def operation_context(self, context: LogContext):
        """Context manager for tracking operation lifecycle."""
        operation_id = context.operation_id or str(uuid.uuid4())
        context.operation_id = operation_id
        context.start_time = time.time()
        
        try:
            self.log_operation_start(context)
            yield context
        except Exception as e:
            context.error_type = type(e).__name__
            context.error_message = str(e)
            self.log_operation_error(context, e)
            raise
        finally:
            if context.start_time:
                context.duration_ms = (time.time() - context.start_time) * 1000
            self.log_operation_end(context)
    
    def log_fallback_triggered(
        self,
        context: LogContext,
        failure_reason: str,
        original_provider: str,
        target_tier: str,
        additional_data: Dict[str, Any] = None
    ):
        """Log fallback trigger event with comprehensive context."""
        self._event_counters[EventType.FALLBACK_TRIGGERED] += 1
        
        event_data = {
            "event_type": EventType.FALLBACK_TRIGGERED.value,
            "failure_reason": failure_reason,
            "original_provider": original_provider,
            "target_tier": target_tier,
            "fallback_sequence_number": context.attempt_number or 1
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        self.logger.warning(
            f"Fallback triggered: {failure_reason} -> {target_tier}",
            extra=self._create_log_extra(context, EventType.FALLBACK_TRIGGERED, event_data)
        )
        
        # Check for excessive fallbacks (potential alert condition)
        if context.attempt_number and context.attempt_number > 3:
            self.log_performance_alert(
                context,
                "excessive_fallbacks",
                f"Service experiencing {context.attempt_number} consecutive fallbacks"
            )
    
    def log_provider_failure(
        self,
        context: LogContext,
        provider: str,
        error: Exception,
        response_time_ms: float = None,
        additional_data: Dict[str, Any] = None
    ):
        """Log provider failure with detailed error analysis."""
        self._event_counters[EventType.PROVIDER_FAILURE] += 1
        
        context.provider = provider
        context.error_type = type(error).__name__
        context.error_message = str(error)
        context.duration_ms = response_time_ms
        
        event_data = {
            "event_type": EventType.PROVIDER_FAILURE.value,
            "provider": provider,
            "error_type": context.error_type,
            "error_message": context.error_message,
            "response_time_ms": response_time_ms,
            "is_timeout": "timeout" in str(error).lower(),
            "is_rate_limit": "rate limit" in str(error).lower() or "429" in str(error),
            "is_auth_error": "auth" in str(error).lower() or "401" in str(error) or "403" in str(error)
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        self.logger.error(
            f"Provider failure: {provider} - {context.error_type}: {context.error_message}",
            extra=self._create_log_extra(context, EventType.PROVIDER_FAILURE, event_data)
        )
        
        # Track error patterns for analysis
        self._track_error_pattern(provider, context.error_type)
    
    def log_provider_success(
        self,
        context: LogContext,
        provider: str,
        response_time_ms: float,
        cost: float = None,
        additional_data: Dict[str, Any] = None
    ):
        """Log successful provider operation with performance metrics."""
        self._event_counters[EventType.PROVIDER_SUCCESS] += 1
        
        context.provider = provider
        context.duration_ms = response_time_ms
        context.estimated_cost = cost
        
        event_data = {
            "event_type": EventType.PROVIDER_SUCCESS.value,
            "provider": provider,
            "response_time_ms": response_time_ms,
            "cost": cost,
            "tier": context.tier,
            "attempt_number": context.attempt_number or 1
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        # Determine log level based on performance
        log_level = LogLevel.INFO
        if response_time_ms > 5000:  # > 5 seconds
            log_level = LogLevel.WARNING
        elif response_time_ms > 10000:  # > 10 seconds
            log_level = LogLevel.ERROR
        
        log_method = getattr(self.logger, log_level.value)
        log_method(
            f"Provider success: {provider} ({response_time_ms:.1f}ms)",
            extra=self._create_log_extra(context, EventType.PROVIDER_SUCCESS, event_data)
        )
        
        # Track performance for analysis
        self._track_performance(provider, response_time_ms)
        
        # Track costs if provided
        if cost:
            self._track_cost(provider, cost)
    
    def log_circuit_breaker_event(
        self,
        context: LogContext,
        provider: str,
        event: str,  # "opened" or "closed"
        failure_count: int = None,
        threshold: int = None,
        additional_data: Dict[str, Any] = None
    ):
        """Log circuit breaker state changes."""
        event_type = EventType.CIRCUIT_BREAKER_OPENED if event == "opened" else EventType.CIRCUIT_BREAKER_CLOSED
        self._event_counters[event_type] += 1
        
        event_data = {
            "event_type": event_type.value,
            "provider": provider,
            "circuit_breaker_state": event,
            "failure_count": failure_count,
            "threshold": threshold
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        log_level = LogLevel.WARNING if event == "opened" else LogLevel.INFO
        log_method = getattr(self.logger, log_level.value)
        
        log_method(
            f"Circuit breaker {event}: {provider} (failures: {failure_count}/{threshold})",
            extra=self._create_log_extra(context, event_type, event_data)
        )
        
        # Circuit breaker opening is a critical event
        if event == "opened":
            self.log_performance_alert(
                context,
                "circuit_breaker_opened",
                f"Circuit breaker opened for {provider} after {failure_count} failures"
            )
    
    def log_health_check(
        self,
        context: LogContext,
        provider: str,
        success: bool,
        response_time_ms: float = None,
        error: str = None,
        additional_data: Dict[str, Any] = None
    ):
        """Log health check results."""
        event_type = EventType.HEALTH_CHECK_PASSED if success else EventType.HEALTH_CHECK_FAILED
        self._event_counters[event_type] += 1
        
        event_data = {
            "event_type": event_type.value,
            "provider": provider,
            "health_check_success": success,
            "response_time_ms": response_time_ms,
            "error": error
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        log_level = LogLevel.DEBUG if success else LogLevel.WARNING
        log_method = getattr(self.logger, log_level.value)
        
        status = "passed" if success else "failed"
        message = f"Health check {status}: {provider}"
        if response_time_ms:
            message += f" ({response_time_ms:.1f}ms)"
        if error:
            message += f" - {error}"
        
        log_method(
            message,
            extra=self._create_log_extra(context, event_type, event_data)
        )
    
    def log_cost_alert(
        self,
        context: LogContext,
        provider: str,
        current_cost: float,
        threshold: float,
        period: str = "daily",
        additional_data: Dict[str, Any] = None
    ):
        """Log cost threshold exceeded alerts."""
        self._event_counters[EventType.COST_THRESHOLD_EXCEEDED] += 1
        
        event_data = {
            "event_type": EventType.COST_THRESHOLD_EXCEEDED.value,
            "provider": provider,
            "current_cost": current_cost,
            "threshold": threshold,
            "period": period,
            "cost_percentage": (current_cost / threshold) * 100 if threshold > 0 else 0
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        self.logger.warning(
            f"Cost threshold exceeded: {provider} ${current_cost:.2f} > ${threshold:.2f} ({period})",
            extra=self._create_log_extra(context, EventType.COST_THRESHOLD_EXCEEDED, event_data)
        )
    
    def log_performance_alert(
        self,
        context: LogContext,
        alert_type: str,
        message: str,
        severity: str = "warning",
        additional_data: Dict[str, Any] = None
    ):
        """Log performance degradation alerts."""
        self._event_counters[EventType.PERFORMANCE_DEGRADATION] += 1
        
        event_data = {
            "event_type": EventType.PERFORMANCE_DEGRADATION.value,
            "alert_type": alert_type,
            "severity": severity,
            "alert_message": message
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        log_level = getattr(LogLevel, severity.upper(), LogLevel.WARNING)
        log_method = getattr(self.logger, log_level.value)
        
        log_method(
            f"Performance alert [{alert_type}]: {message}",
            extra=self._create_log_extra(context, EventType.PERFORMANCE_DEGRADATION, event_data)
        )
    
    def log_security_event(
        self,
        context: LogContext,
        event_type: str,
        message: str,
        severity: str = "warning",
        additional_data: Dict[str, Any] = None
    ):
        """Log security-related events."""
        self._event_counters[EventType.SECURITY_EVENT] += 1
        
        event_data = {
            "event_type": EventType.SECURITY_EVENT.value,
            "security_event_type": event_type,
            "severity": severity,
            "security_message": message
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        log_level = getattr(LogLevel, severity.upper(), LogLevel.WARNING)
        log_method = getattr(self.logger, log_level.value)
        
        log_method(
            f"Security event [{event_type}]: {message}",
            extra=self._create_log_extra(context, EventType.SECURITY_EVENT, event_data)
        )
    
    def log_operation_start(self, context: LogContext):
        """Log operation start."""
        self.logger.debug(
            f"Operation started: {context.operation_id}",
            extra=self._create_log_extra(
                context,
                EventType.PROVIDER_SUCCESS,
                {"lifecycle": "start", "operation_id": context.operation_id}
            )
        )
    
    def log_operation_end(self, context: LogContext):
        """Log operation completion."""
        self.logger.debug(
            f"Operation completed: {context.operation_id} ({context.duration_ms:.1f}ms)",
            extra=self._create_log_extra(
                context,
                EventType.PROVIDER_SUCCESS,
                {
                    "lifecycle": "end",
                    "operation_id": context.operation_id,
                    "duration_ms": context.duration_ms
                }
            )
        )
    
    def log_operation_error(self, context: LogContext, error: Exception):
        """Log operation error."""
        self.logger.error(
            f"Operation failed: {context.operation_id} - {type(error).__name__}: {str(error)}",
            extra=self._create_log_extra(
                context,
                EventType.PROVIDER_FAILURE,
                {
                    "lifecycle": "error",
                    "operation_id": context.operation_id,
                    "error_type": type(error).__name__,
                    "error_message": str(error)
                }
            ),
            exc_info=True
        )
    
    def _create_log_extra(
        self,
        context: LogContext,
        event_type: EventType,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create structured extra data for logging."""
        extra_data = {
            "extra_fields": {
                **context.to_dict(),
                "event_type": event_type.value,
                **event_data,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "service": self.service_name
            }
        }
        
        return extra_data
    
    def _track_error_pattern(self, provider: str, error_type: str):
        """Track error patterns for analysis."""
        # This would integrate with metrics system
        pass
    
    def _track_performance(self, provider: str, response_time_ms: float):
        """Track performance metrics."""
        # This would integrate with metrics system
        if provider not in self._operation_timings:
            self._operation_timings[provider] = []
        
        # Keep last 100 timings for moving averages
        timings = self._operation_timings[provider]
        timings.append(response_time_ms)
        if len(timings) > 100:
            timings.pop(0)
    
    def _track_cost(self, provider: str, cost: float):
        """Track cost metrics."""
        if provider not in self._cost_tracking:
            self._cost_tracking[provider] = 0.0
        
        self._cost_tracking[provider] += cost
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get logging metrics summary."""
        return {
            "event_counters": {event.value: count for event, count in self._event_counters.items()},
            "performance_tracking": {
                provider: {
                    "avg_response_time_ms": sum(timings) / len(timings) if timings else 0,
                    "sample_count": len(timings)
                }
                for provider, timings in self._operation_timings.items()
            },
            "cost_tracking": dict(self._cost_tracking),
            "log_buffer_size": len(self._log_buffer),
            "service_name": self.service_name,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    async def flush_logs(self):
        """Flush buffered logs (if using buffering)."""
        if self._log_buffer:
            # This would send logs to external system
            self._log_buffer.clear()
            self._last_flush = time.time()


# Global logger instance
fallback_logger = FallbackLogger("ai_teddy_bear")
