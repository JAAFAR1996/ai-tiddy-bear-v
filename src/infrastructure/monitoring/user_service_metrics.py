"""
🎯 USER SERVICE METRICS - PROMETHEUS MONITORING
===============================================
Production-grade monitoring and metrics collection for User Service:
- Real-time performance metrics
- Session tracking and analytics
- Database operation monitoring
- Error rate and response time tracking
- Child safety compliance metrics
- Alert thresholds and triggers

COMPREHENSIVE MONITORING - NO BLIND SPOTS
"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from enum import Enum
import uuid
from fastapi import Request

# Prometheus metrics
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    start_http_server,
)

# Internal imports
from src.infrastructure.logging.structlog_logger import StructlogLogger

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics we collect."""

    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    SUMMARY = "summary"


class OperationStatus(str, Enum):
    """Operation status for metrics."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


class UserServiceMetrics:
    """
    Comprehensive metrics collection for User Service.

    Provides production-grade monitoring with:
    - Performance metrics (response time, throughput)
    - Business metrics (sessions, users, children)
    - Error tracking and analysis
    - Child safety compliance metrics
    - Resource utilization monitoring
    """

    def __init__(
        self,
        service_name: str = "user_service",
        enable_http_server: bool = True,
        metrics_port: int = 8001,
        registry: Optional[CollectorRegistry] = None,
    ):
        """
        Initialize metrics collection system.

        Args:
            service_name: Name of the service for metric labels
            enable_http_server: Whether to start HTTP metrics server
            metrics_port: Port for metrics HTTP server
            registry: Optional custom registry
        """
        self.service_name = service_name
        from src.infrastructure.monitoring.metrics_registry import get_metrics_registry

        self.registry = get_metrics_registry()
        self.logger = StructlogLogger("user_service_metrics", component="monitoring")

        # Initialize all metrics
        self._init_performance_metrics()
        self._init_business_metrics()
        self._init_error_metrics()
        self._init_safety_metrics()
        self._init_resource_metrics()

        # Start HTTP server for Prometheus scraping
        if enable_http_server:
            self._start_metrics_server(metrics_port)

        # Track service startup
        self.service_started_time = time.time()
        self.uptime_gauge.set_to_current_time()

        self.logger.info(f"User Service metrics initialized on port {metrics_port}")

    # ========================================================================
    # METRIC INITIALIZATION
    # ========================================================================

    def _init_performance_metrics(self):
        """Initialize performance monitoring metrics."""

        # Request duration tracking
        self.request_duration = Histogram(
            "user_service_request_duration_seconds",
            "Time spent processing requests",
            ["operation", "status"],
            registry=self.registry,
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

        # Request rate tracking
        self.request_rate = Counter(
            "user_service_requests_total",
            "Total number of requests processed",
            ["operation", "status"],
            registry=self.registry,
        )

        # Response time summary
        self.response_time_summary = Summary(
            "user_service_response_time_seconds",
            "Response time summary statistics",
            ["operation"],
            registry=self.registry,
        )

        # Database operation metrics
        self.db_operation_duration = Histogram(
            "user_service_db_operation_duration_seconds",
            "Database operation duration",
            ["operation", "table", "status"],
            registry=self.registry,
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
        )

        self.db_connection_pool = Gauge(
            "user_service_db_connections",
            "Database connection pool status",
            ["state"],  # active, idle, total
            registry=self.registry,
        )

        # Service uptime
        self.uptime_gauge = Gauge(
            "user_service_uptime_seconds",
            "Service uptime in seconds",
            registry=self.registry,
        )

    def _init_business_metrics(self):
        """Initialize business logic metrics."""

        # User management metrics
        self.users_total = Counter(
            "user_service_users_created_total",
            "Total number of users created",
            ["user_type"],  # parent, admin
            registry=self.registry,
        )

        self.users_active = Gauge(
            "user_service_users_active",
            "Number of currently active users",
            registry=self.registry,
        )

        # Child management metrics
        self.children_total = Counter(
            "user_service_children_created_total",
            "Total number of children created",
            ["age_group"],  # toddler, preschool, elementary, preteen
            registry=self.registry,
        )

        self.children_active = Gauge(
            "user_service_children_active",
            "Number of currently active children",
            registry=self.registry,
        )

        # Session management metrics
        self.sessions_created = Counter(
            "user_service_sessions_created_total",
            "Total number of sessions created",
            ["device_type"],
            registry=self.registry,
        )

        self.sessions_active = Gauge(
            "user_service_sessions_active",
            "Number of currently active sessions",
            registry=self.registry,
        )

        self.sessions_ended = Counter(
            "user_service_sessions_ended_total",
            "Total number of sessions ended",
            ["end_reason"],  # normal, timeout, error, force_close
            registry=self.registry,
        )

        self.session_duration = Histogram(
            "user_service_session_duration_seconds",
            "Duration of user sessions",
            ["age_group", "device_type"],
            registry=self.registry,
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400],  # 1min to 4hours
        )

        # Authentication metrics
        self.auth_attempts = Counter(
            "user_service_auth_attempts_total",
            "Authentication attempts",
            ["method", "result"],  # result: success, failure, rate_limited
            registry=self.registry,
        )

    def _init_error_metrics(self):
        """Initialize error tracking metrics."""

        # General error tracking
        self.errors_total = Counter(
            "user_service_errors_total",
            "Total number of errors",
            ["error_type", "operation", "severity"],
            registry=self.registry,
        )

        # Validation errors
        self.validation_errors = Counter(
            "user_service_validation_errors_total",
            "Input validation errors",
            ["field", "error_type"],
            registry=self.registry,
        )

        # Rate limiting metrics
        self.rate_limit_hits = Counter(
            "user_service_rate_limit_hits_total",
            "Rate limit violations",
            ["limit_type", "user_type"],
            registry=self.registry,
        )

        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            "user_service_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["operation"],
            registry=self.registry,
        )

    def _init_safety_metrics(self):
        """Initialize child safety and COPPA compliance metrics."""

        # Age verification metrics
        self.age_verifications = Counter(
            "user_service_age_verifications_total",
            "Age verification attempts",
            ["age_group", "result"],  # result: valid, invalid, missing
            registry=self.registry,
        )

        # COPPA compliance metrics
        self.coppa_compliance = Counter(
            "user_service_coppa_events_total",
            "COPPA compliance events",
            ["event_type", "compliance_status"],
            registry=self.registry,
        )

        # Parental consent tracking
        self.parental_consent = Counter(
            "user_service_parental_consent_total",
            "Parental consent events",
            ["consent_type", "action"],  # action: granted, revoked, updated
            registry=self.registry,
        )

        # Child safety violations
        self.safety_violations = Counter(
            "user_service_safety_violations_total",
            "Child safety policy violations",
            ["violation_type", "severity", "action_taken"],
            registry=self.registry,
        )

        # Session time limits compliance
        self.session_time_limits = Histogram(
            "user_service_session_time_limit_compliance",
            "Session time vs. recommended limits",
            ["age_group", "compliance_status"],
            registry=self.registry,
            buckets=[300, 600, 1200, 1800, 2700, 3600],  # 5min to 1hour
        )

    def _init_resource_metrics(self):
        """Initialize resource utilization metrics."""

        # Memory usage
        self.memory_usage = Gauge(
            "user_service_memory_usage_bytes",
            "Memory usage in bytes",
            ["type"],  # heap, non_heap, total
            registry=self.registry,
        )

        # CPU usage
        self.cpu_usage = Gauge(
            "user_service_cpu_usage_percent",
            "CPU usage percentage",
            registry=self.registry,
        )

        # Cache metrics
        self.cache_operations = Counter(
            "user_service_cache_operations_total",
            "Cache operations",
            [
                "operation",
                "result",
            ],  # operation: get, set, delete; result: hit, miss, error
            registry=self.registry,
        )

        self.cache_size = Gauge(
            "user_service_cache_size_bytes",
            "Cache size in bytes",
            ["cache_type"],
            registry=self.registry,
        )

    # ========================================================================
    # PERFORMANCE METRICS METHODS
    # ========================================================================

    @asynccontextmanager
    async def measure_request(self, operation: str):
        """Context manager to measure request duration and track status."""
        start_time = time.time()
        status = OperationStatus.SUCCESS

        try:
            yield
        except asyncio.TimeoutError:
            status = OperationStatus.TIMEOUT
            raise
        except Exception as e:
            status = OperationStatus.ERROR
            self.record_error(operation, type(e).__name__, str(e))
            raise
        finally:
            duration = time.time() - start_time
            self.request_duration.labels(operation=operation, status=status).observe(
                duration
            )
            self.request_rate.labels(operation=operation, status=status).inc()
            self.response_time_summary.labels(operation=operation).observe(duration)

    def measure_db_operation(self, operation: str, table: str):
        """Context manager for database operation timing."""
        return self._db_operation_context(operation, table)

    @asynccontextmanager
    async def _db_operation_context(self, operation: str, table: str):
        """Internal database operation measurement."""
        start_time = time.time()
        status = OperationStatus.SUCCESS

        try:
            yield
        except Exception as e:
            status = OperationStatus.ERROR
            self.record_error(
                f"db_{operation}", type(e).__name__, str(e), severity="high"
            )
            raise
        finally:
            duration = time.time() - start_time
            self.db_operation_duration.labels(
                operation=operation, table=table, status=status
            ).observe(duration)

    def update_db_connection_pool(self, active: int, idle: int, total: int):
        """Update database connection pool metrics."""
        self.db_connection_pool.labels(state="active").set(active)
        self.db_connection_pool.labels(state="idle").set(idle)
        self.db_connection_pool.labels(state="total").set(total)

    # ========================================================================
    # BUSINESS METRICS METHODS
    # ========================================================================

    def record_user_created(self, user_type: str = "parent"):
        """Record user creation."""
        self.users_total.labels(user_type=user_type).inc()
        self.logger.info(f"User created: {user_type}")

    def record_child_created(self, age: int):
        """Record child creation with age classification."""
        age_group = self._classify_age_group(age)
        self.children_total.labels(age_group=age_group).inc()
        self.logger.info(f"Child created: age {age}, group {age_group}")

    def record_session_created(self, device_type: str):
        """Record session creation."""
        self.sessions_created.labels(device_type=device_type).inc()
        self.sessions_active.inc()

    def record_session_ended(
        self, duration_seconds: float, end_reason: str, age_group: str, device_type: str
    ):
        """Record session end with comprehensive metrics."""
        self.sessions_ended.labels(end_reason=end_reason).inc()
        self.sessions_active.dec()
        self.session_duration.labels(
            age_group=age_group, device_type=device_type
        ).observe(duration_seconds)

    def record_auth_attempt(
        self, method: str, success: bool, rate_limited: bool = False
    ):
        """Record authentication attempt."""
        if rate_limited:
            result = "rate_limited"
        elif success:
            result = "success"
        else:
            result = "failure"

        self.auth_attempts.labels(method=method, result=result).inc()

    def update_active_counts(
        self, active_users: int, active_children: int, active_sessions: int
    ):
        """Update active entity counts."""
        self.users_active.set(active_users)
        self.children_active.set(active_children)
        self.sessions_active.set(active_sessions)

    # ========================================================================
    # ERROR TRACKING METHODS
    # ========================================================================

    def record_error(
        self,
        operation: str,
        error_type: str,
        error_message: str,
        severity: str = "medium",
    ):
        """Record error occurrence."""
        self.errors_total.labels(
            error_type=error_type, operation=operation, severity=severity
        ).inc()

        self.logger.error(
            f"Error in {operation}: {error_type} - {error_message}",
            extra={
                "operation": operation,
                "error_type": error_type,
                "severity": severity,
            },
        )

    def record_validation_error(self, field: str, error_type: str):
        """Record input validation error."""
        self.validation_errors.labels(field=field, error_type=error_type).inc()

    def record_rate_limit_hit(self, limit_type: str, user_type: str):
        """Record rate limit violation."""
        self.rate_limit_hits.labels(limit_type=limit_type, user_type=user_type).inc()
        self.logger.warning(f"Rate limit hit: {limit_type} for {user_type}")

    def update_circuit_breaker_state(self, operation: str, state: int):
        """Update circuit breaker state (0=closed, 1=open, 2=half-open)."""
        self.circuit_breaker_state.labels(operation=operation).set(state)

    # ========================================================================
    # SAFETY METRICS METHODS
    # ========================================================================

    def record_age_verification(self, age: int, is_valid: bool):
        """Record age verification attempt."""
        age_group = self._classify_age_group(age)
        result = "valid" if is_valid else "invalid"
        self.age_verifications.labels(age_group=age_group, result=result).inc()

    def record_coppa_event(self, event_type: str, is_compliant: bool):
        """Record COPPA compliance event."""
        compliance_status = "compliant" if is_compliant else "violation"
        self.coppa_compliance.labels(
            event_type=event_type, compliance_status=compliance_status
        ).inc()

        if not is_compliant:
            self.logger.warning(f"COPPA compliance violation: {event_type}")

    def record_parental_consent(self, consent_type: str, action: str):
        """Record parental consent event."""
        self.parental_consent.labels(consent_type=consent_type, action=action).inc()

    def record_safety_violation(
        self, violation_type: str, severity: str, action_taken: str
    ):
        """Record child safety violation."""
        self.safety_violations.labels(
            violation_type=violation_type, severity=severity, action_taken=action_taken
        ).inc()

        self.logger.error(
            f"Safety violation: {violation_type} (severity: {severity}, action: {action_taken})"
        )

    def record_session_time_compliance(
        self, age: int, session_duration: float, is_compliant: bool
    ):
        """Record session time limit compliance."""
        age_group = self._classify_age_group(age)
        compliance_status = "compliant" if is_compliant else "exceeded"

        self.session_time_limits.labels(
            age_group=age_group, compliance_status=compliance_status
        ).observe(session_duration)

    # ========================================================================
    # RESOURCE MONITORING METHODS
    # ========================================================================

    def update_memory_usage(
        self, heap_bytes: int, non_heap_bytes: int, total_bytes: int
    ):
        """Update memory usage metrics."""
        self.memory_usage.labels(type="heap").set(heap_bytes)
        self.memory_usage.labels(type="non_heap").set(non_heap_bytes)
        self.memory_usage.labels(type="total").set(total_bytes)

    def update_cpu_usage(self, cpu_percent: float):
        """Update CPU usage metric."""
        self.cpu_usage.set(cpu_percent)

    def record_cache_operation(self, operation: str, hit: bool):
        """Record cache operation."""
        result = "hit" if hit else "miss"
        self.cache_operations.labels(operation=operation, result=result).inc()

    def update_cache_size(self, cache_type: str, size_bytes: int):
        """Update cache size metric."""
        self.cache_size.labels(cache_type=cache_type).set(size_bytes)

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def _classify_age_group(self, age: int) -> str:
        """Classify age into appropriate group."""
        if age <= 3:
            return "toddler"
        elif age <= 5:
            return "preschool"
        elif age <= 11:
            return "elementary"
        elif age <= 13:
            return "preteen"
        else:
            return "teen"  # Edge case, should be filtered out in validation

    def _start_metrics_server(self, port: int):
        """Start HTTP server for Prometheus metrics."""
        try:
            start_http_server(port, registry=self.registry)
            self.logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            self.logger.error(f"Failed to start metrics server: {e}")

    def get_metrics_output(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry).decode("utf-8")

    def update_uptime(self):
        """Update service uptime metric."""
        uptime_seconds = time.time() - self.service_started_time
        self.uptime_gauge.set(uptime_seconds)

    def get_health_metrics(self) -> Dict[str, Any]:
        """Get health check metrics."""
        uptime_seconds = time.time() - self.service_started_time

        return {
            "service": self.service_name,
            "uptime_seconds": uptime_seconds,
            "metrics_collected": True,
            "prometheus_registry": len(self.registry._collector_to_names),
            "timestamp": datetime.utcnow().isoformat(),
        }


# ============================================================================
# METRICS DECORATOR AND CONTEXT MANAGERS
# ============================================================================


def track_user_service_operation(operation_name: str):
    """Decorator to automatically track User Service operations."""

    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            # Assume self has a metrics attribute
            if hasattr(self, "_metrics") and self._metrics:
                async with self._metrics.measure_request(operation_name):
                    return await func(self, *args, **kwargs)
            else:
                return await func(self, *args, **kwargs)

        return wrapper

    return decorator


class MetricsMiddleware:
    """Middleware for automatic metrics collection."""

    def __init__(self, metrics: UserServiceMetrics):
        self.metrics = metrics

    async def __call__(self, request: Request, call_next):
        """Process request with metrics collection."""
        operation = f"{request.method}_{request.url.path.replace('/', '_')}"

        async with self.metrics.measure_request(operation):
            response = await call_next(request)
            return response


# ============================================================================
# FACTORY FUNCTION
# ============================================================================


def create_user_service_metrics(
    service_name: str = "user_service",
    enable_http_server: bool = True,
    metrics_port: int = 8001,
) -> UserServiceMetrics:
    """
    Factory function to create User Service metrics instance.

    Args:
        service_name: Name of the service
        enable_http_server: Whether to start HTTP server
        metrics_port: Port for metrics server

    Returns:
        Configured UserServiceMetrics instance
    """
    return UserServiceMetrics(
        service_name=service_name,
        enable_http_server=enable_http_server,
        metrics_port=metrics_port,
    )


# Export for easy imports
__all__ = [
    "UserServiceMetrics",
    "MetricType",
    "OperationStatus",
    "track_user_service_operation",
    "MetricsMiddleware",
    "create_user_service_metrics",
]


if __name__ == "__main__":
    # Demo usage
    print("🎯 User Service Metrics - Prometheus Monitoring")
    print("Metrics server will start on http://localhost:8001/metrics")

    # Create metrics instance
    metrics = create_user_service_metrics()

    # Simulate some operations
    metrics.record_user_created("parent")
    metrics.record_child_created(8)
    metrics.record_session_created("tablet")

    print("Demo metrics recorded. Check http://localhost:8001/metrics")
