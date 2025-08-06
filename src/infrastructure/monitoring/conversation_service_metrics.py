"""Production Monitoring and Metrics for ConsolidatedConversationService

This module provides comprehensive monitoring capabilities for the conversation service:
- Real-time metrics collection using Prometheus
- Performance monitoring and alerting
- Child safety metrics and incident tracking
- Resource utilization monitoring
- Business metrics and analytics
- Health checks and service status monitoring
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, asdict

import prometheus_client
from prometheus_client import Counter, Histogram, Gauge, Info, Enum as PrometheusEnum


class MetricLevel(Enum):
    """Metric collection levels."""

    BASIC = "basic"
    DETAILED = "detailed"
    DEBUG = "debug"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ConversationMetrics:
    """Conversation-specific metrics data."""

    conversation_id: str
    child_id: str
    message_count: int
    duration_seconds: float
    interaction_type: str
    status: str
    safety_incidents: int
    created_at: datetime
    updated_at: datetime


@dataclass
class PerformanceMetrics:
    """Performance metrics data."""

    operation: str
    duration_ms: float
    success: bool
    error_type: Optional[str] = None
    resource_usage: Optional[Dict[str, Any]] = None


class ConversationServiceMetrics:
    """Production-grade metrics collection for ConversationService.

    Provides comprehensive monitoring including:
    - Conversation lifecycle metrics
    - Message processing metrics
    - Safety and security metrics
    - Performance and resource metrics
    - Business intelligence metrics
    """

    def __init__(
        self,
        service_name: str = "conversation_service",
        metric_level: MetricLevel = MetricLevel.DETAILED,
    ):
        """Initialize metrics collection.

        Args:
            service_name: Name of the service for metric labeling
            metric_level: Level of metrics to collect
        """
        self.service_name = service_name
        self.metric_level = metric_level

        # Initialize Prometheus metrics
        from src.infrastructure.monitoring.metrics_registry import get_metrics_registry

        self.registry = get_metrics_registry()
        self.conversation_counter = self.registry.get_counter(
            "conversation_total", "Total number of conversations started"
        )
        self.message_counter = self.registry.get_counter(
            "message_total", "Total number of messages sent"
        )
        self.response_latency = self.registry.get_histogram(
            "response_latency_seconds",
            "Response latency in seconds",
            buckets=[0.1, 0.5, 1, 2.5, 5, 10],
        )

        # Internal tracking
        self._active_conversations: Dict[str, ConversationMetrics] = {}
        self._performance_history: List[PerformanceMetrics] = []
        self._alert_thresholds = self._init_alert_thresholds()

        # Background monitoring (started via start() method)
        self._monitoring_task = None
        self._started = False

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics collectors."""

        # === CONVERSATION LIFECYCLE METRICS ===
        self.conversations_total = Counter(
            "conversation_service_conversations_total",
            "Total number of conversations created",
            ["interaction_type", "child_age_group"],
        )

        self.conversations_active = Gauge(
            "conversation_service_conversations_active",
            "Number of currently active conversations",
        )

        self.conversation_duration = Histogram(
            "conversation_service_conversation_duration_seconds",
            "Duration of completed conversations",
            ["interaction_type", "completion_reason"],
            buckets=[60, 300, 600, 1800, 3600, 7200],  # 1min to 2hours
        )

        # === MESSAGE PROCESSING METRICS ===
        self.messages_total = Counter(
            "conversation_service_messages_total",
            "Total number of messages processed",
            ["message_type", "safety_status"],
        )

        self.message_processing_duration = Histogram(
            "conversation_service_message_processing_duration_ms",
            "Time taken to process messages",
            ["message_type"],
            buckets=[10, 50, 100, 500, 1000, 5000],  # 10ms to 5s
        )

        self.message_safety_violations = Counter(
            "conversation_service_safety_violations_total",
            "Number of safety violations detected",
            ["violation_type", "severity"],
        )

        # === PERFORMANCE METRICS ===
        self.operation_duration = Histogram(
            "conversation_service_operation_duration_ms",
            "Duration of service operations",
            ["operation", "status"],
            buckets=[1, 10, 50, 100, 500, 1000, 5000],
        )

        self.database_operations = Counter(
            "conversation_service_database_operations_total",
            "Number of database operations",
            ["operation", "table", "status"],
        )

        self.cache_operations = Counter(
            "conversation_service_cache_operations_total",
            "Number of cache operations",
            ["operation", "hit_miss"],
        )

        # === ERROR AND HEALTH METRICS ===
        self.errors_total = Counter(
            "conversation_service_errors_total",
            "Total number of errors",
            ["error_type", "operation"],
        )

        self.service_health = Gauge(
            "conversation_service_health_status",
            "Service health status (1=healthy, 0=unhealthy)",
        )

        self.dependency_health = Gauge(
            "conversation_service_dependency_health",
            "Health status of dependencies",
            ["dependency"],
        )

        # === BUSINESS METRICS ===
        self.child_engagement = Histogram(
            "conversation_service_child_engagement_messages",
            "Number of messages per conversation",
            ["age_group", "interaction_type"],
            buckets=[1, 5, 10, 20, 50, 100],
        )

        self.session_quality = Gauge(
            "conversation_service_session_quality_score",
            "Quality score of conversations (0-1)",
            ["interaction_type"],
        )

        # === RESOURCE UTILIZATION ===
        self.memory_usage = Gauge(
            "conversation_service_memory_usage_bytes", "Memory usage of the service"
        )

        self.active_locks = Gauge(
            "conversation_service_active_locks", "Number of active conversation locks"
        )

        # Service info
        self.service_info = Info(
            "conversation_service_info", "Service information and configuration"
        )

        # Set initial service info
        self.service_info.info(
            {
                "service_name": self.service_name,
                "metric_level": self.metric_level.value,
                "version": "1.0.0",
                "start_time": datetime.now().isoformat(),
            }
        )

    def _init_alert_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """Initialize alert thresholds for monitoring."""
        return {
            "conversation_duration": {
                "warning_seconds": 3600,  # 1 hour
                "critical_seconds": 7200,  # 2 hours
            },
            "message_processing": {
                "warning_ms": 1000,  # 1 second
                "critical_ms": 5000,  # 5 seconds
            },
            "safety_violations": {
                "warning_per_hour": 10,
                "critical_per_hour": 50,
            },
            "error_rate": {
                "warning_percent": 5.0,
                "critical_percent": 10.0,
            },
            "active_conversations": {
                "warning_count": 1000,
                "critical_count": 5000,
            },
        }

    async def start(self):
        """Start the metrics monitoring service - must be called from async context."""
        if self._started:
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._started = True
        logger.info("ConversationServiceMetrics monitoring started")

    async def stop(self):
        """Stop the metrics monitoring service."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        self._started = False
        logger.info("ConversationServiceMetrics monitoring stopped")

    # === CONVERSATION LIFECYCLE TRACKING ===

    def conversation_started(
        self,
        conversation_id: str,
        child_id: str,
        interaction_type: str,
        child_age: Optional[int] = None,
    ):
        """Track conversation start."""
        age_group = self._get_age_group(child_age) if child_age else "unknown"

        # Update Prometheus metrics
        self.conversations_total.labels(
            interaction_type=interaction_type, child_age_group=age_group
        ).inc()

        self.conversations_active.inc()

        # Track internally
        self._active_conversations[conversation_id] = ConversationMetrics(
            conversation_id=conversation_id,
            child_id=child_id,
            message_count=0,
            duration_seconds=0.0,
            interaction_type=interaction_type,
            status="active",
            safety_incidents=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        if self.metric_level in [MetricLevel.DETAILED, MetricLevel.DEBUG]:
            self._log_metric_event(
                "conversation_started",
                {
                    "conversation_id": conversation_id,
                    "interaction_type": interaction_type,
                    "child_age_group": age_group,
                },
            )

    def conversation_ended(
        self,
        conversation_id: str,
        reason: str = "unknown",
        final_message_count: int = 0,
    ):
        """Track conversation end."""
        if conversation_id not in self._active_conversations:
            return

        metrics = self._active_conversations[conversation_id]
        duration = (datetime.now() - metrics.created_at).total_seconds()

        # Update Prometheus metrics
        self.conversation_duration.labels(
            interaction_type=metrics.interaction_type, completion_reason=reason
        ).observe(duration)

        self.conversations_active.dec()

        self.child_engagement.labels(
            age_group="unknown",  # Would need to track age
            interaction_type=metrics.interaction_type,
        ).observe(final_message_count or metrics.message_count)

        # Remove from active tracking
        del self._active_conversations[conversation_id]

        # Check for alerts
        self._check_conversation_duration_alert(duration, conversation_id)

        if self.metric_level in [MetricLevel.DETAILED, MetricLevel.DEBUG]:
            self._log_metric_event(
                "conversation_ended",
                {
                    "conversation_id": conversation_id,
                    "duration_seconds": duration,
                    "message_count": final_message_count,
                    "reason": reason,
                },
            )

    # === MESSAGE PROCESSING TRACKING ===

    def message_processed(
        self,
        conversation_id: str,
        message_type: str,
        processing_time_ms: float,
        safety_status: str = "safe",
        success: bool = True,
    ):
        """Track message processing."""
        # Update Prometheus metrics
        self.messages_total.labels(
            message_type=message_type, safety_status=safety_status
        ).inc()

        self.message_processing_duration.labels(message_type=message_type).observe(
            processing_time_ms
        )

        # Update conversation metrics
        if conversation_id in self._active_conversations:
            self._active_conversations[conversation_id].message_count += 1
            self._active_conversations[conversation_id].updated_at = datetime.now()

        # Check for performance alerts
        self._check_message_processing_alert(processing_time_ms, message_type)

        if not success:
            self.errors_total.labels(
                error_type="message_processing_failed", operation="add_message"
            ).inc()

    def safety_violation_detected(
        self, conversation_id: str, violation_type: str, severity: str = "medium"
    ):
        """Track safety violations."""
        self.message_safety_violations.labels(
            violation_type=violation_type, severity=severity
        ).inc()

        # Update conversation metrics
        if conversation_id in self._active_conversations:
            self._active_conversations[conversation_id].safety_incidents += 1

        # Check for safety alerts
        self._check_safety_violation_alert(violation_type, severity)

        if self.metric_level in [MetricLevel.DETAILED, MetricLevel.DEBUG]:
            self._log_metric_event(
                "safety_violation",
                {
                    "conversation_id": conversation_id,
                    "violation_type": violation_type,
                    "severity": severity,
                },
            )

    # === PERFORMANCE AND OPERATION TRACKING ===

    def operation_completed(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        error_type: Optional[str] = None,
    ):
        """Track service operation completion."""
        status = "success" if success else "error"

        self.operation_duration.labels(operation=operation, status=status).observe(
            duration_ms
        )

        if not success and error_type:
            self.errors_total.labels(error_type=error_type, operation=operation).inc()

        # Store performance history
        if self.metric_level == MetricLevel.DEBUG:
            self._performance_history.append(
                PerformanceMetrics(
                    operation=operation,
                    duration_ms=duration_ms,
                    success=success,
                    error_type=error_type,
                )
            )

            # Keep only recent history
            if len(self._performance_history) > 1000:
                self._performance_history = self._performance_history[-500:]

    def database_operation(self, operation: str, table: str, success: bool = True):
        """Track database operations."""
        status = "success" if success else "error"

        self.database_operations.labels(
            operation=operation, table=table, status=status
        ).inc()

    def cache_operation(self, operation: str, hit: bool = True):
        """Track cache operations."""
        hit_miss = "hit" if hit else "miss"

        self.cache_operations.labels(operation=operation, hit_miss=hit_miss).inc()

    # === HEALTH AND STATUS MONITORING ===

    def update_service_health(
        self, healthy: bool, dependencies: Optional[Dict[str, bool]] = None
    ):
        """Update service health status."""
        self.service_health.set(1 if healthy else 0)

        if dependencies:
            for dep_name, dep_healthy in dependencies.items():
                self.dependency_health.labels(dependency=dep_name).set(
                    1 if dep_healthy else 0
                )

    def update_resource_usage(self, memory_bytes: int, active_locks: int):
        """Update resource usage metrics."""
        self.memory_usage.set(memory_bytes)
        self.active_locks.set(active_locks)

    # === BUSINESS INTELLIGENCE ===

    def update_session_quality(self, interaction_type: str, quality_score: float):
        """Update session quality metrics."""
        self.session_quality.labels(interaction_type=interaction_type).set(
            quality_score
        )

    def get_conversation_analytics(self) -> Dict[str, Any]:
        """Get current conversation analytics."""
        active_count = len(self._active_conversations)

        # Calculate average metrics
        if active_count > 0:
            total_messages = sum(
                conv.message_count for conv in self._active_conversations.values()
            )
            total_incidents = sum(
                conv.safety_incidents for conv in self._active_conversations.values()
            )
            avg_messages = total_messages / active_count
            avg_incidents = total_incidents / active_count
        else:
            avg_messages = avg_incidents = 0

        return {
            "active_conversations": active_count,
            "average_messages_per_conversation": avg_messages,
            "average_safety_incidents": avg_incidents,
            "total_conversations_today": self._get_daily_conversation_count(),
            "conversation_types": self._get_conversation_type_distribution(),
            "performance_summary": self._get_performance_summary(),
        }

    # === ALERT SYSTEM ===

    def _check_conversation_duration_alert(
        self, duration_seconds: float, conversation_id: str
    ):
        """Check if conversation duration exceeds thresholds."""
        thresholds = self._alert_thresholds["conversation_duration"]

        if duration_seconds > thresholds["critical_seconds"]:
            self._trigger_alert(
                AlertSeverity.CRITICAL,
                "conversation_duration_critical",
                f"Conversation {conversation_id} exceeded critical duration: {duration_seconds:.0f}s",
            )
        elif duration_seconds > thresholds["warning_seconds"]:
            self._trigger_alert(
                AlertSeverity.WARNING,
                "conversation_duration_warning",
                f"Conversation {conversation_id} exceeded warning duration: {duration_seconds:.0f}s",
            )

    def _check_message_processing_alert(
        self, processing_time_ms: float, message_type: str
    ):
        """Check if message processing time exceeds thresholds."""
        thresholds = self._alert_thresholds["message_processing"]

        if processing_time_ms > thresholds["critical_ms"]:
            self._trigger_alert(
                AlertSeverity.CRITICAL,
                "message_processing_critical",
                f"{message_type} message processing exceeded critical time: {processing_time_ms:.0f}ms",
            )
        elif processing_time_ms > thresholds["warning_ms"]:
            self._trigger_alert(
                AlertSeverity.WARNING,
                "message_processing_warning",
                f"{message_type} message processing exceeded warning time: {processing_time_ms:.0f}ms",
            )

    def _check_safety_violation_alert(self, violation_type: str, severity: str):
        """Check if safety violations exceed thresholds."""
        # This would implement rate-based alerting
        # For now, just trigger immediate alerts for high severity
        if severity in ["high", "critical"]:
            self._trigger_alert(
                AlertSeverity.ERROR,
                "safety_violation_detected",
                f"High severity safety violation detected: {violation_type}",
            )

    def _trigger_alert(self, severity: AlertSeverity, alert_type: str, message: str):
        """Trigger an alert."""
        alert_data = {
            "timestamp": datetime.now().isoformat(),
            "service": self.service_name,
            "severity": severity.value,
            "type": alert_type,
            "message": message,
        }

        # Log alert
        print(f"ALERT [{severity.value.upper()}] {alert_type}: {message}")

        # In production, this would integrate with alerting systems like:
        # - Prometheus Alertmanager
        # - PagerDuty
        # - Slack notifications
        # - Email alerts

        if self.metric_level == MetricLevel.DEBUG:
            self._log_metric_event("alert_triggered", alert_data)

    # === BACKGROUND MONITORING ===

    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute

                # Update health metrics
                self._update_health_metrics()

                # Check alert conditions
                self._check_system_alerts()

                # Cleanup old data
                self._cleanup_old_data()

            except Exception as e:
                print(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)

    def _update_health_metrics(self):
        """Update system health metrics."""
        # Update active conversation count
        active_count = len(self._active_conversations)

        # Check if system is healthy
        healthy = (
            active_count
            < self._alert_thresholds["active_conversations"]["critical_count"]
        )

        self.update_service_health(healthy)

    def _check_system_alerts(self):
        """Check system-wide alert conditions."""
        active_count = len(self._active_conversations)
        thresholds = self._alert_thresholds["active_conversations"]

        if active_count > thresholds["critical_count"]:
            self._trigger_alert(
                AlertSeverity.CRITICAL,
                "active_conversations_critical",
                f"Critical number of active conversations: {active_count}",
            )
        elif active_count > thresholds["warning_count"]:
            self._trigger_alert(
                AlertSeverity.WARNING,
                "active_conversations_warning",
                f"High number of active conversations: {active_count}",
            )

    def _cleanup_old_data(self):
        """Clean up old tracking data."""
        cutoff_time = datetime.now() - timedelta(hours=24)

        # Clean up old conversations (shouldn't happen in normal operation)
        old_conversations = [
            conv_id
            for conv_id, metrics in self._active_conversations.items()
            if metrics.created_at < cutoff_time
        ]

        for conv_id in old_conversations:
            self.conversation_ended(conv_id, "cleanup_timeout")

    # === UTILITY METHODS ===

    def _get_age_group(self, age: int) -> str:
        """Get age group classification."""
        if age < 5:
            return "toddler"
        elif age < 8:
            return "young_child"
        elif age < 13:
            return "child"
        else:
            return "teen"

    def _get_daily_conversation_count(self) -> int:
        """Get count of conversations started today."""
        # This would query actual metrics
        # For now, return current active count as approximation
        return len(self._active_conversations)

    def _get_conversation_type_distribution(self) -> Dict[str, int]:
        """Get distribution of conversation types."""
        distribution = {}
        for metrics in self._active_conversations.values():
            interaction_type = metrics.interaction_type
            distribution[interaction_type] = distribution.get(interaction_type, 0) + 1
        return distribution

    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self._performance_history:
            return {"operations": 0}

        recent_history = self._performance_history[-100:]  # Last 100 operations

        total_ops = len(recent_history)
        successful_ops = sum(1 for op in recent_history if op.success)
        avg_duration = sum(op.duration_ms for op in recent_history) / total_ops

        return {
            "operations": total_ops,
            "success_rate": successful_ops / total_ops if total_ops > 0 else 0,
            "average_duration_ms": avg_duration,
        }

    def _log_metric_event(self, event_type: str, data: Dict[str, Any]):
        """Log metric events for debugging."""
        if self.metric_level == MetricLevel.DEBUG:
            print(f"METRIC EVENT [{event_type}]: {data}")

    # === CLEANUP ===

    async def shutdown(self):
        """Shutdown monitoring (alias for stop)."""
        await self.stop()

    def export_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        return prometheus_client.generate_latest().decode("utf-8")


# === METRICS MIDDLEWARE ===


class ConversationMetricsMiddleware:
    """Middleware to automatically collect metrics from ConversationService operations."""

    def __init__(self, metrics: ConversationServiceMetrics):
        self.metrics = metrics

    def __call__(self, func):
        """Decorator to wrap service methods with metrics collection."""
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            operation_name = func.__name__
            start_time = time.time()
            success = True
            error_type = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                self.metrics.operation_completed(
                    operation=operation_name,
                    duration_ms=duration_ms,
                    success=success,
                    error_type=error_type,
                )

        return wrapper


# === FACTORY FUNCTION ===


def create_conversation_metrics(
    service_name: str = "conversation_service",
    metric_level: MetricLevel = MetricLevel.DETAILED,
) -> ConversationServiceMetrics:
    """Create and configure conversation service metrics.

    Args:
        service_name: Name of the service
        metric_level: Level of metrics to collect

    Returns:
        Configured metrics instance
    """
    return ConversationServiceMetrics(service_name, metric_level)


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def example_usage():
        # Create metrics instance
        metrics = create_conversation_metrics()

        # Simulate conversation lifecycle
        conv_id = "test-conversation-123"
        child_id = "child-456"

        # Start conversation
        metrics.conversation_started(conv_id, child_id, "chat", child_age=7)

        # Process some messages
        for i in range(5):
            metrics.message_processed(
                conv_id,
                "user_input",
                processing_time_ms=50.0 + i * 10,
                safety_status="safe",
            )

        # End conversation
        metrics.conversation_ended(conv_id, "completed", 5)

        # Get analytics
        analytics = metrics.get_conversation_analytics()
        print("Analytics:", analytics)

        # Export metrics
        print("Metrics export sample:")
        print(metrics.export_metrics()[:500] + "...")

        # Cleanup
        await metrics.shutdown()

    asyncio.run(example_usage())
