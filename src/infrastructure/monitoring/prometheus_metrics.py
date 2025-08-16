"""
Prometheus Metrics - Comprehensive Metrics Collection (CONSOLIDATED)
===================================================================
🔄 CONSOLIDATED METRICS:
This file now contains all Prometheus metrics and replaces the legacy metrics.py.
Any new metrics or modifications must be implemented here.
All imports of metrics.py are deprecated and have been migrated.

Enterprise-grade Prometheus metrics for AI Teddy Bear system:
- HTTP request/response metrics for every endpoint
- Business metrics for child interactions and safety
- Provider performance and circuit breaker metrics
- Database and cache performance metrics
- Cost tracking and optimization metrics
- Custom metrics for ML model performance
- SLA and compliance monitoring metrics
- AI service metrics with collectors (migrated from metrics.py)
- Child safety metrics with collectors (migrated from metrics.py)
"""

import time
import functools
import asyncio
from typing import Optional, Callable
from enum import Enum

# Production deployment requires prometheus_client - NO FALLBACKS ALLOWED
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    Enum as PrometheusEnum,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..resilience.fallback_logger import FallbackLogger


class MetricType(Enum):
    """Types of metrics for categorization."""

    HTTP = "http"
    BUSINESS = "business"
    PROVIDER = "provider"
    DATABASE = "database"
    CACHE = "cache"
    SECURITY = "security"
    COST = "cost"
    PERFORMANCE = "performance"
    ML_MODEL = "ml_model"
    COMPLIANCE = "compliance"


class PrometheusMetrics:
    """
    Comprehensive Prometheus metrics collector for AI Teddy Bear system.

    Features:
    - HTTP request/response metrics with detailed labels
    - Business metrics for child interactions and safety
    - Provider performance monitoring
    - Database and cache metrics
    - Cost tracking and optimization
    - Custom metrics for ML models
    - SLA and compliance monitoring
    """

    def __init__(
        self,
        registry: Optional[CollectorRegistry] = None,
        service_name: str = "ai_teddy_bear",
    ):
        self.registry = registry or CollectorRegistry()
        self.service_name = service_name
        self.logger = FallbackLogger("prometheus_metrics")

        # Initialize all metrics
        self._init_http_metrics()
        self._init_business_metrics()
        self._init_provider_metrics()
        self._init_database_metrics()
        self._init_cache_metrics()
        self._init_security_metrics()
        self._init_cost_metrics()
        self._init_performance_metrics()
        self._init_ml_model_metrics()
        self._init_compliance_metrics()
        self._init_system_metrics()
        self._init_audio_metrics()

        self.logger.info("Prometheus metrics initialized - production grade")

    def _init_http_metrics(self):
        """Initialize HTTP-related metrics."""
        # HTTP request counter
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total number of HTTP requests",
            ["method", "endpoint", "status_code", "user_type", "region"],
            registry=self.registry,
        )

        # HTTP request duration
        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "Duration of HTTP requests in seconds",
            ["method", "endpoint", "status_code"],
            buckets=[
                0.001,
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
            ],
            registry=self.registry,
        )

        # HTTP request size
        self.http_request_size_bytes = Histogram(
            "http_request_size_bytes",
            "Size of HTTP requests in bytes",
            ["method", "endpoint"],
            buckets=[64, 256, 1024, 4096, 16384, 65536, 262144, 1048576],
            registry=self.registry,
        )

        # HTTP response size
        self.http_response_size_bytes = Histogram(
            "http_response_size_bytes",
            "Size of HTTP responses in bytes",
            ["method", "endpoint", "status_code"],
            buckets=[64, 256, 1024, 4096, 16384, 65536, 262144, 1048576],
            registry=self.registry,
        )

        # Active HTTP connections
        self.http_connections_active = Gauge(
            "http_connections_active",
            "Number of active HTTP connections",
            registry=self.registry,
        )

        # HTTP errors by type
        self.http_errors_total = Counter(
            "http_errors_total",
            "Total number of HTTP errors",
            ["error_type", "endpoint", "method"],
            registry=self.registry,
        )

    def _init_business_metrics(self):
        """Initialize business logic metrics."""
        # Child interactions
        self.child_interactions_total = Counter(
            "child_interactions_total",
            "Total number of child interactions",
            ["interaction_type", "age_group", "language", "safety_status"],
            registry=self.registry,
        )

        # Child messages processed
        self.child_messages_processed_total = Counter(
            "child_messages_processed_total",
            "Total child messages processed",
            ["message_type", "language", "sentiment", "safety_flag"],
            registry=self.registry,
        )

        # Stories generated
        self.stories_generated_total = Counter(
            "stories_generated_total",
            "Total stories generated",
            ["age_group", "category", "language", "personalization_level"],
            registry=self.registry,
        )

        # Safety violations detected
        self.safety_violations_total = Counter(
            "safety_violations_total",
            "Total safety violations detected",
            ["violation_type", "severity", "action_taken", "age_group"],
            registry=self.registry,
        )

        # Parent notifications sent
        self.parent_notifications_total = Counter(
            "parent_notifications_total",
            "Total parent notifications sent",
            ["notification_type", "channel", "urgency", "delivery_status"],
            registry=self.registry,
        )

        # Active child sessions
        self.child_sessions_active = Gauge(
            "child_sessions_active",
            "Number of active child sessions",
            ["age_group", "region"],
            registry=self.registry,
        )

        # Content moderation metrics
        self.content_moderation_checks_total = Counter(
            "content_moderation_checks_total",
            "Total content moderation checks",
            ["content_type", "check_result", "confidence_level"],
            registry=self.registry,
        )

        # User engagement metrics
        self.user_engagement_duration_seconds = Histogram(
            "user_engagement_duration_seconds",
            "Duration of user engagement sessions",
            ["age_group", "activity_type"],
            buckets=[30, 60, 120, 300, 600, 1200, 1800, 3600],
            registry=self.registry,
        )

    def _init_provider_metrics(self):
        """Initialize external provider metrics."""
        # Provider requests
        self.provider_requests_total = Counter(
            "provider_requests_total",
            "Total requests to external providers",
            ["provider_id", "provider_type", "operation", "status"],
            registry=self.registry,
        )

        # Provider response time
        self.provider_response_duration_seconds = Histogram(
            "provider_response_duration_seconds",
            "Response time from external providers",
            ["provider_id", "provider_type", "operation"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
            registry=self.registry,
        )

        # Circuit breaker status
        self.circuit_breaker_state = PrometheusEnum(
            "circuit_breaker_state",
            "Current state of circuit breakers",
            ["provider_id", "provider_type"],
            states=["closed", "open", "half_open"],
            registry=self.registry,
        )

        # Provider health score
        self.provider_health_score = Gauge(
            "provider_health_score",
            "Health score of external providers (0-100)",
            ["provider_id", "provider_type", "region"],
            registry=self.registry,
        )

        # Provider cost
        self.provider_cost_total = Counter(
            "provider_cost_total",
            "Total cost incurred by providers",
            ["provider_id", "provider_type", "operation"],
            registry=self.registry,
        )

        # Provider rate limits
        self.provider_rate_limit_hits_total = Counter(
            "provider_rate_limit_hits_total",
            "Total rate limit hits by provider",
            ["provider_id", "provider_type"],
            registry=self.registry,
        )

    def _init_database_metrics(self):
        """Initialize database metrics."""
        # Database connections
        self.database_connections_active = Gauge(
            "database_connections_active",
            "Number of active database connections",
            ["database_name", "connection_type"],
            registry=self.registry,
        )

        # Database query duration
        self.database_query_duration_seconds = Histogram(
            "database_query_duration_seconds",
            "Duration of database queries",
            ["database_name", "query_type", "table_name"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry,
        )

        # Database operations
        self.database_operations_total = Counter(
            "database_operations_total",
            "Total database operations",
            ["database_name", "operation", "table_name", "status"],
            registry=self.registry,
        )

        # Database pool metrics
        self.database_pool_size = Gauge(
            "database_pool_size",
            "Database connection pool size",
            ["database_name", "pool_type"],
            registry=self.registry,
        )

        # Database locks
        self.database_locks_total = Counter(
            "database_locks_total",
            "Total database lock events",
            ["database_name", "lock_type", "table_name"],
            registry=self.registry,
        )

    def _init_cache_metrics(self):
        """Initialize cache metrics."""
        # Cache operations
        self.cache_operations_total = Counter(
            "cache_operations_total",
            "Total cache operations",
            ["cache_name", "operation", "result"],
            registry=self.registry,
        )

        # Cache hit ratio
        self.cache_hit_ratio = Gauge(
            "cache_hit_ratio",
            "Cache hit ratio (0-1)",
            ["cache_name", "cache_type"],
            registry=self.registry,
        )

        # Cache response time
        self.cache_response_duration_seconds = Histogram(
            "cache_response_duration_seconds",
            "Cache operation response time",
            ["cache_name", "operation"],
            buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25],
            registry=self.registry,
        )

        # Cache memory usage
        self.cache_memory_bytes = Gauge(
            "cache_memory_bytes",
            "Cache memory usage in bytes",
            ["cache_name"],
            registry=self.registry,
        )

        # Cache key count
        self.cache_keys_count = Gauge(
            "cache_keys_count",
            "Number of keys in cache",
            ["cache_name"],
            registry=self.registry,
        )

    def _init_security_metrics(self):
        """Initialize security metrics."""
        # Authentication attempts
        self.auth_attempts_total = Counter(
            "auth_attempts_total",
            "Total authentication attempts",
            ["auth_type", "result", "user_type"],
            registry=self.registry,
        )

        # Rate limiting
        self.rate_limit_hits_total = Counter(
            "rate_limit_hits_total",
            "Total rate limit hits",
            ["endpoint", "limit_type", "user_type"],
            registry=self.registry,
        )

        # Security violations
        self.security_violations_total = Counter(
            "security_violations_total",
            "Total security violations",
            ["violation_type", "severity", "source_ip", "action_taken"],
            registry=self.registry,
        )

        # JWT token metrics
        self.jwt_tokens_issued_total = Counter(
            "jwt_tokens_issued_total",
            "Total JWT tokens issued",
            ["token_type", "user_type"],
            registry=self.registry,
        )

        # Failed login attempts
        self.failed_login_attempts_total = Counter(
            "failed_login_attempts_total",
            "Total failed login attempts",
            ["reason", "user_type", "source_ip"],
            registry=self.registry,
        )

    def _init_cost_metrics(self):
        """Initialize cost tracking metrics."""
        # Total cost by service
        self.service_cost_total = Counter(
            "service_cost_total",
            "Total cost by service in USD",
            ["service_name", "cost_type", "region"],
            registry=self.registry,
        )

        # Cost per user
        self.cost_per_user = Histogram(
            "cost_per_user",
            "Cost per user in USD",
            ["user_type", "time_period"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry,
        )

        # Resource usage cost
        self.resource_cost_total = Counter(
            "resource_cost_total",
            "Total resource cost",
            ["resource_type", "provider", "region"],
            registry=self.registry,
        )

        # Budget tracking
        self.budget_usage_ratio = Gauge(
            "budget_usage_ratio",
            "Budget usage ratio (0-1)",
            ["budget_category", "time_period"],
            registry=self.registry,
        )

    def _init_performance_metrics(self):
        """Initialize performance metrics."""
        # CPU usage
        self.cpu_usage_percent = Gauge(
            "cpu_usage_percent",
            "CPU usage percentage",
            ["instance_id", "cpu_type"],
            registry=self.registry,
        )

        # Memory usage
        self.memory_usage_bytes = Gauge(
            "memory_usage_bytes",
            "Memory usage in bytes",
            ["instance_id", "memory_type"],
            registry=self.registry,
        )

        # Disk I/O
        self.disk_io_operations_total = Counter(
            "disk_io_operations_total",
            "Total disk I/O operations",
            ["instance_id", "operation_type", "device"],
            registry=self.registry,
        )

        # Network I/O
        self.network_io_bytes_total = Counter(
            "network_io_bytes_total",
            "Total network I/O in bytes",
            ["instance_id", "direction", "interface"],
            registry=self.registry,
        )

        # Garbage collection
        self.gc_duration_seconds = Histogram(
            "gc_duration_seconds",
            "Garbage collection duration",
            ["gc_type"],
            registry=self.registry,
        )

    def _init_ml_model_metrics(self):
        """Initialize ML model performance metrics."""
        # Model inference time
        self.ml_inference_duration_seconds = Histogram(
            "ml_inference_duration_seconds",
            "ML model inference duration",
            ["model_name", "model_version", "input_type"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry,
        )

        # Model predictions
        self.ml_predictions_total = Counter(
            "ml_predictions_total",
            "Total ML predictions made",
            ["model_name", "model_version", "prediction_type", "confidence_level"],
            registry=self.registry,
        )

        # Model accuracy
        self.ml_model_accuracy = Gauge(
            "ml_model_accuracy",
            "ML model accuracy score",
            ["model_name", "model_version", "dataset"],
            registry=self.registry,
        )

        # Model drift detection
        self.ml_model_drift_score = Gauge(
            "ml_model_drift_score",
            "ML model drift detection score",
            ["model_name", "model_version", "drift_type"],
            registry=self.registry,
        )

    def _init_compliance_metrics(self):
        """Initialize compliance and audit metrics."""
        # COPPA compliance checks
        self.coppa_compliance_checks_total = Counter(
            "coppa_compliance_checks_total",
            "Total COPPA compliance checks",
            ["check_type", "result", "age_verification"],
            registry=self.registry,
        )

        # Data retention compliance
        self.data_retention_actions_total = Counter(
            "data_retention_actions_total",
            "Total data retention actions",
            ["action_type", "data_type", "retention_period"],
            registry=self.registry,
        )

        # Audit log entries
        self.audit_log_entries_total = Counter(
            "audit_log_entries_total",
            "Total audit log entries",
            ["event_type", "user_type", "severity"],
            registry=self.registry,
        )

        # Privacy policy compliance
        self.privacy_compliance_score = Gauge(
            "privacy_compliance_score",
            "Privacy compliance score (0-100)",
            ["compliance_type", "region"],
            registry=self.registry,
        )

    def _init_system_metrics(self):
        """Initialize system-wide metrics."""
        # Application info
        self.application_info = Info(
            "application_info", "Application information", registry=self.registry
        )

        # Uptime
        self.application_uptime_seconds = Gauge(
            "application_uptime_seconds",
            "Application uptime in seconds",
            registry=self.registry,
        )

        # Version info
        self.application_version_info = Info(
            "application_version_info",
            "Application version information",
            registry=self.registry,
        )

        # Health check status
        self.health_check_status = PrometheusEnum(
            "health_check_status",
            "Health check status",
            ["service_name"],
            states=["healthy", "warning", "critical", "unknown"],
            registry=self.registry,
        )

    def _init_audio_metrics(self):
        """Initialize audio pipeline metrics."""
        # TTS request metrics
        self.tts_requests_total = Counter(
            "tts_requests_total",
            "Total TTS requests",
            ["provider", "voice_id", "language", "status", "cached"],
            registry=self.registry,
        )

        # TTS processing duration
        self.tts_processing_duration_seconds = Histogram(
            "tts_processing_duration_seconds",
            "Duration of TTS processing",
            ["provider", "voice_id", "model"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry,
        )

        # TTS cache performance
        self.tts_cache_operations_total = Counter(
            "tts_cache_operations_total",
            "Total TTS cache operations",
            ["operation", "result"],
            registry=self.registry,
        )

        self.tts_cache_hit_ratio = Gauge(
            "tts_cache_hit_ratio",
            "TTS cache hit ratio (0-1)",
            registry=self.registry,
        )

        # TTS character count
        self.tts_characters_processed_total = Counter(
            "tts_characters_processed_total",
            "Total characters processed by TTS",
            ["provider", "language", "content_type"],
            registry=self.registry,
        )

        # TTS cost tracking
        self.tts_cost_total_usd = Counter(
            "tts_cost_total_usd",
            "Total TTS cost in USD",
            ["provider", "model"],
            registry=self.registry,
        )

        # Audio validation metrics
        self.audio_validation_checks_total = Counter(
            "audio_validation_checks_total",
            "Total audio validation checks",
            ["format", "result", "error_type"],
            registry=self.registry,
        )

        # Audio safety metrics
        self.audio_safety_checks_total = Counter(
            "audio_safety_checks_total",
            "Total audio safety checks",
            ["check_type", "result", "child_age_group"],
            registry=self.registry,
        )

        self.audio_safety_violations_total = Counter(
            "audio_safety_violations_total",
            "Total audio safety violations",
            ["violation_type", "severity", "action_taken"],
            registry=self.registry,
        )

        # Speech-to-text metrics
        self.stt_requests_total = Counter(
            "stt_requests_total",
            "Total STT requests",
            ["provider", "language", "status"],
            registry=self.registry,
        )

        self.stt_processing_duration_seconds = Histogram(
            "stt_processing_duration_seconds",
            "Duration of STT processing",
            ["provider", "language"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry,
        )

        # Audio streaming metrics
        self.audio_stream_connections_active = Gauge(
            "audio_stream_connections_active",
            "Number of active audio streaming connections",
            ["stream_type"],
            registry=self.registry,
        )

        self.audio_stream_bytes_processed_total = Counter(
            "audio_stream_bytes_processed_total",
            "Total bytes processed in audio streams",
            ["stream_type", "direction"],
            registry=self.registry,
        )

        # Audio quality metrics
        self.audio_quality_score = Histogram(
            "audio_quality_score",
            "Audio quality scores (0-1)",
            ["content_type", "age_group"],
            buckets=[0.0, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0],
            registry=self.registry,
        )

        # Child-specific audio metrics
        self.child_audio_sessions_total = Counter(
            "child_audio_sessions_total",
            "Total child audio sessions",
            ["age_group", "session_type", "duration_bucket"],
            registry=self.registry,
        )

        self.child_audio_engagement_duration_seconds = Histogram(
            "child_audio_engagement_duration_seconds",
            "Duration of child audio engagement",
            ["age_group", "content_type"],
            buckets=[30, 60, 120, 300, 600, 1200, 1800],
            registry=self.registry,
        )

        # Audio error metrics
        self.audio_errors_total = Counter(
            "audio_errors_total",
            "Total audio processing errors",
            ["error_type", "component", "severity"],
            registry=self.registry,
        )

        # TTS provider health
        self.tts_provider_health_score = Gauge(
            "tts_provider_health_score",
            "TTS provider health score (0-1)",
            ["provider", "region"],
            registry=self.registry,
        )

    # Convenience methods for recording metrics
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        request_size: int = 0,
        response_size: int = 0,
        user_type: str = "unknown",
        region: str = "unknown",
    ):
        """Record HTTP request metrics."""
        status_str = str(status_code)

        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_str,
            user_type=user_type,
            region=region,
        ).inc()

        self.http_request_duration_seconds.labels(
            method=method, endpoint=endpoint, status_code=status_str
        ).observe(duration)

        if request_size > 0:
            self.http_request_size_bytes.labels(
                method=method, endpoint=endpoint
            ).observe(request_size)

        if response_size > 0:
            self.http_response_size_bytes.labels(
                method=method, endpoint=endpoint, status_code=status_str
            ).observe(response_size)

    def record_child_interaction(
        self,
        interaction_type: str,
        age_group: str,
        language: str = "en",
        safety_status: str = "safe",
    ):
        """Record child interaction metrics."""
        self.child_interactions_total.labels(
            interaction_type=interaction_type,
            age_group=age_group,
            language=language,
            safety_status=safety_status,
        ).inc()

    def record_provider_request(
        self,
        provider_id: str,
        provider_type: str,
        operation: str,
        status: str,
        duration: float,
        cost: float = 0.0,
    ):
        """Record provider request metrics."""
        self.provider_requests_total.labels(
            provider_id=provider_id,
            provider_type=provider_type,
            operation=operation,
            status=status,
        ).inc()

        self.provider_response_duration_seconds.labels(
            provider_id=provider_id, provider_type=provider_type, operation=operation
        ).observe(duration)

        if cost > 0:
            self.provider_cost_total.labels(
                provider_id=provider_id,
                provider_type=provider_type,
                operation=operation,
            ).inc(cost)

    def update_circuit_breaker_state(
        self, provider_id: str, provider_type: str, state: str
    ):
        """Update circuit breaker state."""
        self.circuit_breaker_state.labels(
            provider_id=provider_id, provider_type=provider_type
        ).state(state)

    def update_provider_health(
        self, provider_id: str, provider_type: str, region: str, health_score: float
    ):
        """Update provider health score."""
        self.provider_health_score.labels(
            provider_id=provider_id, provider_type=provider_type, region=region
        ).set(health_score)

    def record_database_query(
        self,
        database_name: str,
        query_type: str,
        table_name: str,
        duration: float,
        status: str = "success",
    ):
        """Record database query metrics."""
        self.database_operations_total.labels(
            database_name=database_name,
            operation=query_type,
            table_name=table_name,
            status=status,
        ).inc()

        self.database_query_duration_seconds.labels(
            database_name=database_name, query_type=query_type, table_name=table_name
        ).observe(duration)

    def record_cache_operation(
        self, cache_name: str, operation: str, result: str, duration: float
    ):
        """Record cache operation metrics."""
        self.cache_operations_total.labels(
            cache_name=cache_name, operation=operation, result=result
        ).inc()

        self.cache_response_duration_seconds.labels(
            cache_name=cache_name, operation=operation
        ).observe(duration)

    def record_security_event(
        self,
        event_type: str,
        severity: str,
        action_taken: str,
        source_ip: str = "unknown",
    ):
        """Record security event metrics."""
        self.security_violations_total.labels(
            violation_type=event_type,
            severity=severity,
            source_ip=source_ip,
            action_taken=action_taken,
        ).inc()

    def record_ml_prediction(
        self,
        model_name: str,
        model_version: str,
        prediction_type: str,
        confidence_level: str,
        duration: float,
    ):
        """Record ML model prediction metrics."""
        self.ml_predictions_total.labels(
            model_name=model_name,
            model_version=model_version,
            prediction_type=prediction_type,
            confidence_level=confidence_level,
        ).inc()

        self.ml_inference_duration_seconds.labels(
            model_name=model_name,
            model_version=model_version,
            input_type=prediction_type,
        ).observe(duration)

    def record_compliance_check(
        self, check_type: str, result: str, data_type: str = "user_data"
    ):
        """Record compliance check metrics."""
        if check_type.startswith("coppa"):
            self.coppa_compliance_checks_total.labels(
                check_type=check_type,
                result=result,
                age_verification="true" if "age" in check_type else "false",
            ).inc()

        self.audit_log_entries_total.labels(
            event_type=check_type,
            user_type="system",
            severity="info" if result == "pass" else "warning",
        ).inc()

    def record_deployment_success(
        self,
        environment: str,
        execution_time: float,
        downtime: float = 0.0,
        version: str = "unknown",
        deployment_type: str = "standard",
    ):
        """Record successful deployment metrics."""
        # Record deployment success as a business metric
        self.child_interactions_total.labels(
            interaction_type="deployment_success",
            age_group="system",
            language="system",
            safety_status="safe",
        ).inc()
        
        # Record deployment duration
        self.http_request_duration_seconds.labels(
            method="DEPLOY",
            endpoint=f"/deployment/{environment}",
            status_code="200",
        ).observe(execution_time)
        
        # Record as audit log entry
        self.audit_log_entries_total.labels(
            event_type="deployment_success",
            user_type="system",
            severity="info",
        ).inc()
        
        self.logger.info(
            "Deployment success recorded",
            environment=environment,
            execution_time=execution_time,
            downtime=downtime,
            version=version,
            deployment_type=deployment_type,
        )

    def record_deployment_failure(
        self,
        environment: str,
        error_message: str,
        error_type: str = "deployment_error",
        severity: str = "high",
    ):
        """Record deployment failure metrics."""
        # Record deployment failure as security violation
        self.security_violations_total.labels(
            violation_type="deployment_failure",
            severity=severity,
            source_ip="system",
            action_taken="rollback",
        ).inc()
        
        # Record as HTTP error
        self.http_errors_total.labels(
            error_type=error_type,
            endpoint=f"/deployment/{environment}",
            method="DEPLOY",
        ).inc()
        
        # Record deployment failure as failed HTTP request
        self.http_requests_total.labels(
            method="DEPLOY",
            endpoint=f"/deployment/{environment}",
            status_code="500",
            user_type="system",
            region="local",
        ).inc()
        
        # Record as audit log entry
        self.audit_log_entries_total.labels(
            event_type="deployment_failure",
            user_type="system",
            severity="error",
        ).inc()
        
        self.logger.error(
            "Deployment failure recorded",
            environment=environment,
            error_message=error_message[:200],  # Truncate long error messages
            error_type=error_type,
            severity=severity,
        )

    def get_metrics(self) -> str:
        """Get all metrics in Prometheus format."""
        return generate_latest(self.registry).decode()

    def get_content_type(self) -> str:
        """Get content type for metrics endpoint."""
        return CONTENT_TYPE_LATEST


class PrometheusMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for automatic Prometheus metrics collection."""

    def __init__(self, app, metrics: PrometheusMetrics):
        super().__init__(app)
        self.metrics = metrics
        self.logger = FallbackLogger("prometheus_middleware")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process HTTP request and collect metrics."""
        start_time = time.time()

        # Extract request information
        method = request.method
        path = request.url.path

        # Normalize endpoint path (remove IDs and parameters)
        endpoint = self._normalize_endpoint(path)

        # Get request size
        request_size = int(request.headers.get("content-length", 0))

        # Extract user information from headers or auth
        user_type = self._extract_user_type(request)
        region = self._extract_region(request)

        # Increment active connections
        self.metrics.http_connections_active.inc()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Get response size
            response_size = int(response.headers.get("content-length", 0))

            # Record metrics
            self.metrics.record_http_request(
                method=method,
                endpoint=endpoint,
                status_code=response.status_code,
                duration=duration,
                request_size=request_size,
                response_size=response_size,
                user_type=user_type,
                region=region,
            )

            return response

        except Exception as e:
            # Record error
            duration = time.time() - start_time

            self.metrics.http_errors_total.labels(
                error_type=type(e).__name__, endpoint=endpoint, method=method
            ).inc()

            # Record as 500 error
            self.metrics.record_http_request(
                method=method,
                endpoint=endpoint,
                status_code=500,
                duration=duration,
                request_size=request_size,
                user_type=user_type,
                region=region,
            )

            raise

        finally:
            # Decrement active connections
            self.metrics.http_connections_active.dec()

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for consistent labeling."""
        # Replace UUID patterns
        import re

        path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{id}",
            path,
        )

        # Replace numeric IDs
        path = re.sub(r"/\d+", "/{id}", path)

        # Limit path length and normalize
        if len(path) > 100:
            path = path[:100] + "..."

        return path

    def _extract_user_type(self, request: Request) -> str:
        """Extract user type from request."""
        # Check for user type in headers
        user_type = request.headers.get("x-user-type", "unknown")

        # Check for JWT token and extract user type
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # This would typically decode JWT and extract user type
            # For now, return generic types
            if "parent" in auth_header.lower():
                return "parent"
            elif "child" in auth_header.lower():
                return "child"
            elif "admin" in auth_header.lower():
                return "admin"

        return user_type

    def _extract_region(self, request: Request) -> str:
        """Extract region from request."""
        # Check headers for region information
        region = request.headers.get("x-region", "unknown")

        # Check CloudFront or CDN headers
        cf_region = request.headers.get("cloudfront-viewer-country", "")
        if cf_region:
            return cf_region.lower()

        # Check X-Forwarded-For for IP-based region detection
        # This would typically use a GeoIP service
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            # Simple region mapping based on IP (would use proper GeoIP in production)
            ip = forwarded_for.split(",")[0].strip()
            if (
                ip.startswith("10.")
                or ip.startswith("192.168.")
                or ip.startswith("172.")
            ):
                return "local"

        return region


def metrics_decorator(
    metrics: PrometheusMetrics, metric_type: MetricType = MetricType.BUSINESS
):
    """Decorator for adding custom metrics to functions."""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = f"{func.__module__}.{func.__name__}"

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # Record success metric based on type
                if metric_type == MetricType.BUSINESS:
                    # Business function success
                    metrics.child_interactions_total.labels(
                        interaction_type=function_name,
                        age_group="unknown",
                        language="unknown",
                        safety_status="safe",
                    ).inc()

                return result

            except Exception as e:
                duration = time.time() - start_time

                # Record error metric
                metrics.http_errors_total.labels(
                    error_type=type(e).__name__,
                    endpoint=function_name,
                    method="function_call",
                ).inc()

                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = f"{func.__module__}.{func.__name__}"

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Record success metric
                if metric_type == MetricType.BUSINESS:
                    metrics.child_interactions_total.labels(
                        interaction_type=function_name,
                        age_group="unknown",
                        language="unknown",
                        safety_status="safe",
                    ).inc()

                return result

            except Exception as e:
                duration = time.time() - start_time

                # Record error metric
                metrics.http_errors_total.labels(
                    error_type=type(e).__name__,
                    endpoint=function_name,
                    method="function_call",
                ).inc()

                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Global metrics instance
prometheus_metrics = PrometheusMetrics()


class AIMetricsCollector:
    """Collector for AI service metrics (migrated from metrics.py)."""

    def __init__(self, metrics: PrometheusMetrics = None):
        self.metrics = metrics or prometheus_metrics
        self.logger = FallbackLogger("ai_metrics")

    def record_ai_request(
        self,
        model: str,
        provider: str = "openai",
        status: str = "success",
        duration: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_estimate: float = 0.0,
        child_age_group: str = "unknown",
    ):
        """Record AI request metrics."""

        # Record AI request using consolidated metrics
        self.metrics.provider_requests_total.labels(
            provider_id=provider,
            provider_type="ai_model",
            operation=f"generate_{model}",
            status=status,
        ).inc()

        if duration > 0:
            self.metrics.provider_response_duration_seconds.labels(
                provider_id=provider,
                provider_type="ai_model",
                operation=f"generate_{model}",
            ).observe(duration)

        # Record business metric for child interaction
        self.metrics.child_interactions_total.labels(
            interaction_type="ai_generation",
            age_group=child_age_group,
            language="unknown",
            safety_status="safe" if status == "success" else "unsafe",
        ).inc()

        if cost_estimate > 0:
            self.metrics.provider_cost_total.labels(
                provider_id=provider,
                provider_type="ai_model",
                operation=f"generate_{model}",
            ).inc(cost_estimate)

        # Record ML prediction metrics
        if prompt_tokens > 0 or completion_tokens > 0:
            confidence = "high" if status == "success" else "low"
            self.metrics.record_ml_prediction(
                model_name=model,
                model_version="latest",
                prediction_type="text_generation",
                confidence_level=confidence,
                duration=duration,
            )

        self.logger.info(
            "AI request recorded",
            model=model,
            provider=provider,
            status=status,
            duration=duration,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_estimate=cost_estimate,
        )

    def record_deployment_success(
        self,
        environment: str,
        execution_time: float,
        downtime: float = 0.0,
        version: str = "unknown",
        deployment_type: str = "standard",
    ):
        """Record successful deployment metrics."""
        # Record deployment success as a business metric
        self.metrics.child_interactions_total.labels(
            interaction_type="deployment_success",
            age_group="system",
            language="system",
            safety_status="safe",
        ).inc()
        
        # Record deployment duration
        self.metrics.http_request_duration_seconds.labels(
            method="DEPLOY",
            endpoint=f"/deployment/{environment}",
            status_code="200",
        ).observe(execution_time)
        
        # Record as audit log entry
        self.metrics.audit_log_entries_total.labels(
            event_type="deployment_success",
            user_type="system",
            severity="info",
        ).inc()
        
        self.logger.info(
            "Deployment success recorded",
            environment=environment,
            execution_time=execution_time,
            downtime=downtime,
            version=version,
            deployment_type=deployment_type,
        )

    def record_deployment_failure(
        self,
        environment: str,
        error_message: str,
        error_type: str = "deployment_error",
        severity: str = "high",
    ):
        """Record deployment failure metrics."""
        # Record deployment failure as security violation
        self.metrics.security_violations_total.labels(
            violation_type="deployment_failure",
            severity=severity,
            source_ip="system",
            action_taken="rollback",
        ).inc()
        
        # Record as HTTP error
        self.metrics.http_errors_total.labels(
            error_type=error_type,
            endpoint=f"/deployment/{environment}",
            method="DEPLOY",
        ).inc()
        
        # Record deployment failure as failed HTTP request
        self.metrics.http_requests_total.labels(
            method="DEPLOY",
            endpoint=f"/deployment/{environment}",
            status_code="500",
            user_type="system",
            region="local",
        ).inc()
        
        # Record as audit log entry
        self.metrics.audit_log_entries_total.labels(
            event_type="deployment_failure",
            user_type="system",
            severity="error",
        ).inc()
        
        self.logger.error(
            "Deployment failure recorded",
            environment=environment,
            error_message=error_message[:200],  # Truncate long error messages
            error_type=error_type,
            severity=severity,
        )

    def record_tts_request(
        self,
        provider: str,
        voice_id: str,
        language: str,
        status: str,
        duration: float,
        character_count: int,
        cost_usd: float = 0.0,
        cached: bool = False,
        model: str = "default",
        content_type: str = "conversation",
    ):
        """Record TTS request metrics."""
        cached_str = "cached" if cached else "fresh"
        
        # Record TTS request
        self.metrics.tts_requests_total.labels(
            provider=provider,
            voice_id=voice_id,
            language=language,
            status=status,
            cached=cached_str,
        ).inc()

        # Record processing duration
        self.metrics.tts_processing_duration_seconds.labels(
            provider=provider,
            voice_id=voice_id,
            model=model,
        ).observe(duration)

        # Record character count
        self.metrics.tts_characters_processed_total.labels(
            provider=provider,
            language=language,
            content_type=content_type,
        ).inc(character_count)

        # Record cost
        if cost_usd > 0:
            self.metrics.tts_cost_total_usd.labels(
                provider=provider,
                model=model,
            ).inc(cost_usd)

        # Record cache operation
        cache_result = "hit" if cached else "miss"
        self.metrics.tts_cache_operations_total.labels(
            operation="get",
            result=cache_result,
        ).inc()

        self.logger.info(
            "TTS request recorded",
            provider=provider,
            voice_id=voice_id,
            status=status,
            duration=duration,
            character_count=character_count,
            cost_usd=cost_usd,
            cached=cached,
        )

    def record_audio_validation(
        self,
        audio_format: str,
        result: str,
        error_type: str = "none",
        quality_score: float = 0.0,
        age_group: str = "unknown",
    ):
        """Record audio validation metrics."""
        # Record validation check
        self.metrics.audio_validation_checks_total.labels(
            format=audio_format,
            result=result,
            error_type=error_type,
        ).inc()

        # Record quality score if available
        if quality_score > 0:
            self.metrics.audio_quality_score.labels(
                content_type="user_input",
                age_group=age_group,
            ).observe(quality_score)

        self.logger.info(
            "Audio validation recorded",
            format=audio_format,
            result=result,
            error_type=error_type,
            quality_score=quality_score,
        )

    def record_audio_safety_check(
        self,
        check_type: str,
        result: str,
        child_age: int = 0,
        violations: list = None,
        action_taken: str = "none",
    ):
        """Record audio safety check metrics."""
        violations = violations or []
        age_group = self._get_age_group(child_age)

        # Record safety check
        self.metrics.audio_safety_checks_total.labels(
            check_type=check_type,
            result=result,
            child_age_group=age_group,
        ).inc()

        # Record violations
        for violation in violations:
            severity = "high" if "violent" in violation.lower() or "inappropriate" in violation.lower() else "medium"
            self.metrics.audio_safety_violations_total.labels(
                violation_type=violation[:50],  # Truncate long violation descriptions
                severity=severity,
                action_taken=action_taken,
            ).inc()

        self.logger.info(
            "Audio safety check recorded",
            check_type=check_type,
            result=result,
            child_age=child_age,
            violations_count=len(violations),
            action_taken=action_taken,
        )

    def record_stt_request(
        self,
        provider: str,
        language: str,
        status: str,
        duration: float,
        confidence: float = 0.0,
    ):
        """Record STT request metrics."""
        # Record STT request
        self.metrics.stt_requests_total.labels(
            provider=provider,
            language=language,
            status=status,
        ).inc()

        # Record processing duration
        self.metrics.stt_processing_duration_seconds.labels(
            provider=provider,
            language=language,
        ).observe(duration)

        self.logger.info(
            "STT request recorded",
            provider=provider,
            language=language,
            status=status,
            duration=duration,
            confidence=confidence,
        )

    def record_child_audio_session(
        self,
        child_age: int,
        session_type: str,
        duration_seconds: int,
        content_type: str = "conversation",
    ):
        """Record child audio session metrics."""
        age_group = self._get_age_group(child_age)
        
        # Determine duration bucket
        if duration_seconds < 60:
            duration_bucket = "short"
        elif duration_seconds < 300:
            duration_bucket = "medium"
        elif duration_seconds < 1200:
            duration_bucket = "long"
        else:
            duration_bucket = "extended"

        # Record session
        self.metrics.child_audio_sessions_total.labels(
            age_group=age_group,
            session_type=session_type,
            duration_bucket=duration_bucket,
        ).inc()

        # Record engagement duration
        self.metrics.child_audio_engagement_duration_seconds.labels(
            age_group=age_group,
            content_type=content_type,
        ).observe(duration_seconds)

        self.logger.info(
            "Child audio session recorded",
            child_age=child_age,
            session_type=session_type,
            duration_seconds=duration_seconds,
            content_type=content_type,
        )

    def record_audio_error(
        self,
        error_type: str,
        component: str,
        severity: str = "medium",
        error_message: str = "",
    ):
        """Record audio processing error."""
        self.metrics.audio_errors_total.labels(
            error_type=error_type,
            component=component,
            severity=severity,
        ).inc()

        self.logger.error(
            "Audio error recorded",
            error_type=error_type,
            component=component,
            severity=severity,
            error_message=error_message[:100],  # Truncate long error messages
        )

    def update_tts_provider_health(
        self,
        provider: str,
        health_score: float,
        region: str = "default",
    ):
        """Update TTS provider health score."""
        self.metrics.tts_provider_health_score.labels(
            provider=provider,
            region=region,
        ).set(health_score)

        self.logger.info(
            "TTS provider health updated",
            provider=provider,
            health_score=health_score,
            region=region,
        )

    def update_tts_cache_hit_ratio(self, hit_ratio: float):
        """Update TTS cache hit ratio."""
        self.metrics.tts_cache_hit_ratio.set(hit_ratio)

    def _get_age_group(self, age: int) -> str:
        """Get age group string from age."""
        if age <= 0:
            return "unknown"
        elif age <= 5:
            return "early_childhood"
        elif age <= 8:
            return "middle_childhood"
        elif age <= 12:
            return "late_childhood"
        else:
            return "adolescent"


class SafetyMetricsCollector:
    """Collector for child safety and COPPA metrics (migrated from metrics.py)."""

    def __init__(self, metrics: PrometheusMetrics = None):
        self.metrics = metrics or prometheus_metrics
        self.logger = FallbackLogger("safety_metrics")

    def record_safety_check(
        self,
        check_type: str,
        result: str,
        severity: str = "info",
        age_group: str = "unknown",
    ):
        """Record safety check metrics."""

        # Record safety violation if applicable
        if result == "violation":
            self.metrics.safety_violations_total.labels(
                violation_type=check_type,
                severity=severity,
                action_taken="blocked",
                age_group=age_group,
            ).inc()

        # Record content moderation check
        confidence = "high" if severity in ["high", "critical"] else "medium"
        self.metrics.content_moderation_checks_total.labels(
            content_type="text", check_result=result, confidence_level=confidence
        ).inc()

        self.logger.info(
            "Safety check performed",
            check_type=check_type,
            result=result,
            severity=severity,
            age_group=age_group,
        )

    def record_coppa_check(
        self, check_type: str, result: str, action_taken: str = "none"
    ):
        """Record COPPA compliance check."""

        # Use consolidated compliance metrics
        self.metrics.record_compliance_check(
            check_type=f"coppa_{check_type}", result=result
        )

        self.logger.info(
            "COPPA check performed",
            check_type=check_type,
            result=result,
            action_taken=action_taken,
        )

    def record_content_filter_action(
        self, action_type: str, content_type: str, severity: str = "medium"
    ):
        """Record content filtering action."""

        # Record security violation
        self.metrics.record_security_event(
            event_type=f"content_filter_{action_type}",
            severity=severity,
            action_taken=action_type,
        )

        # Record content moderation
        self.metrics.content_moderation_checks_total.labels(
            content_type=content_type,
            check_result="filtered",
            confidence_level=severity,
        ).inc()

        self.logger.warning(
            "Content filtered",
            action_type=action_type,
            content_type=content_type,
            severity=severity,
        )

    def record_parental_consent(self, event_type: str, status: str):
        """Record parental consent event."""

        # Record as compliance check
        self.metrics.record_compliance_check(
            check_type=f"parental_consent_{event_type}", result=status
        )

        # Record as notification if applicable
        if event_type in ["granted", "revoked"]:
            self.metrics.parent_notifications_total.labels(
                notification_type="consent_update",
                channel="system",
                urgency="normal",
                delivery_status="delivered",
            ).inc()

        self.logger.info("Parental consent event", event_type=event_type, status=status)


def get_metrics_response() -> Response:
    """Generate Prometheus metrics response (legacy compatibility)."""
    metrics_data = prometheus_metrics.get_metrics()
    return Response(
        content=metrics_data, media_type=prometheus_metrics.get_content_type()
    )


# Global metrics collectors (legacy compatibility)
ai_metrics = AIMetricsCollector()
safety_metrics = SafetyMetricsCollector()


# Legacy MetricsMiddleware for backward compatibility
class MetricsMiddleware(PrometheusMiddleware):
    """Legacy metrics middleware (wrapper around PrometheusMiddleware)."""

    def __init__(self, app):
        super().__init__(app, prometheus_metrics)
        self.logger = FallbackLogger("metrics_middleware")

    def _get_user_type(self, request: Request) -> str:
        """Determine user type for metrics (legacy compatibility)."""
        return self._extract_user_type(request)


class PrometheusMetricsCollector:
    """
    Legacy compatibility class for PrometheusMetricsCollector.
    Wrapper around PrometheusMetrics for backward compatibility.
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """Initialize with optional registry."""
        self.prometheus_metrics = PrometheusMetrics(registry=registry)
        self.logger = FallbackLogger("prometheus_metrics_collector")
        
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        self.prometheus_metrics.record_http_request(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration=duration
        )
        
    def record_provider_call(self, provider: str, operation: str, status: str, duration: float):
        """Record provider call metrics."""
        self.prometheus_metrics.record_provider_request(
            provider_id=provider,
            provider_type="external_api",
            operation=operation,
            status=status,
            duration=duration
        )
        
    def record_database_operation(self, operation: str, table: str, duration: float, status: str = "success"):
        """Record database operation metrics."""
        self.prometheus_metrics.record_database_query(
            database_name="main",
            query_type=operation,
            table_name=table,
            duration=duration,
            status=status
        )
        
    def record_cache_operation(self, cache_name: str, operation: str, result: str):
        """Record cache operation metrics."""
        self.prometheus_metrics.record_cache_operation(
            cache_name=cache_name,
            operation=operation,
            result=result,
            duration=0.001  # Default minimal duration
        )
        
    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return self.prometheus_metrics.get_metrics()
        
    def get_content_type(self) -> str:
        """Get content type for metrics."""
        return self.prometheus_metrics.get_content_type()


# Legacy global instance for backward compatibility
prometheus_metrics_collector = PrometheusMetricsCollector()
