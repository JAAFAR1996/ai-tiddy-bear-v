"""
Comprehensive Performance Monitoring and Alerting System
Real-time metrics, Core Web Vitals, response time monitoring, and child-safety compliance tracking
"""

import asyncio
import time
import logging
import psutil
import os
import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
import weakref

import aiofiles
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
    generate_latest,
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.exceptions import MonitoringError, ConfigurationError
from src.utils.date_utils import get_current_timestamp
from .cache_manager import CacheManager
from .cdn_manager import CDNManager


logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MetricType(Enum):
    """Types of metrics collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class PerformanceThreshold:
    """Performance threshold configuration."""

    metric_name: str
    warning_threshold: float
    critical_threshold: float
    emergency_threshold: Optional[float] = None
    check_interval_seconds: int = 60
    consecutive_violations: int = 3
    child_safety_impact: bool = False


@dataclass
class Alert:
    """Performance alert."""

    id: str
    level: AlertLevel
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    child_safety_related: bool = False
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class CoreWebVitals:
    """Core Web Vitals metrics."""

    largest_contentful_paint_ms: Optional[float] = None  # LCP
    first_input_delay_ms: Optional[float] = None  # FID
    cumulative_layout_shift: Optional[float] = None  # CLS
    first_contentful_paint_ms: Optional[float] = None  # FCP
    time_to_interactive_ms: Optional[float] = None  # TTI
    total_blocking_time_ms: Optional[float] = None  # TBT


@dataclass
class SystemMetrics:
    """System performance metrics."""

    cpu_usage_percent: float
    memory_usage_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_received_mb: float
    active_connections: int
    load_average: List[float]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ApplicationMetrics:
    """Application-specific metrics."""

    total_requests: int = 0
    requests_per_second: float = 0.0
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    error_rate: float = 0.0
    active_sessions: int = 0
    cache_hit_ratio: float = 0.0
    database_connections: int = 0
    child_safety_violations: int = 0
    coppa_compliance_score: float = 100.0
    timestamp: datetime = field(default_factory=datetime.now)


class BaseAlertHandler(ABC):
    """Base class for alert handlers."""

    @abstractmethod
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert notification."""
        pass


class LogAlertHandler(BaseAlertHandler):
    """Log-based alert handler."""

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to logs."""
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.CRITICAL: logging.CRITICAL,
            AlertLevel.EMERGENCY: logging.CRITICAL,
        }[alert.level]

        logger.log(
            log_level,
            f"PERFORMANCE ALERT [{alert.level.value.upper()}]: {alert.message}",
            extra={
                "alert_id": alert.id,
                "metric": alert.metric_name,
                "current_value": alert.current_value,
                "threshold": alert.threshold_value,
                "child_safety_related": alert.child_safety_related,
                "tags": alert.tags,
            },
        )
        return True


class WebhookAlertHandler(BaseAlertHandler):
    """Webhook-based alert handler."""

    def __init__(self, webhook_url: str, timeout: int = 30):
        self.webhook_url = webhook_url
        self.timeout = timeout

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        import httpx

        payload = {
            "alert_id": alert.id,
            "level": alert.level.value,
            "metric": alert.metric_name,
            "current_value": alert.current_value,
            "threshold": alert.threshold_value,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat(),
            "child_safety_related": alert.child_safety_related,
            "tags": alert.tags,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code < 400
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


class MetricsCollector:
    """Collects various performance metrics."""

    def __init__(self):
        from src.infrastructure.monitoring.metrics_registry import get_metrics_registry
        self.registry = get_metrics_registry()

        # Prometheus metrics
        self.request_count = self.registry.get_counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"]
        )

        self.request_duration = self.registry.get_histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            ["method", "endpoint"]
        )

        self.active_connections = self.registry.get_gauge(
            "active_connections", "Number of active connections"
        )

        self.cache_hit_ratio = self.registry.get_gauge(
            "cache_hit_ratio", "Cache hit ratio", ["cache_name"]
        )

        self.child_safety_violations = self.registry.get_counter(
            "child_safety_violations_total",
            "Total child safety violations",
            ["violation_type"]
        )

        self.system_cpu_usage = self.registry.get_gauge(
            "system_cpu_usage_percent",
            "System CPU usage percentage"
        )

        self.system_memory_usage = self.registry.get_gauge(
            "system_memory_usage_percent",
            "System memory usage percentage"
        )

        # Response time tracking
        self.response_times = deque(maxlen=1000)
        self.response_times_lock = threading.Lock()

        # Child safety metrics
        self.coppa_compliance_events = deque(maxlen=100)
        self.safety_violations = defaultdict(int)

    async def collect_system_metrics(self) -> SystemMetrics:
        """Collect system performance metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)

            # Disk metrics
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent

            # Disk I/O
            disk_io = psutil.disk_io_counters()
            disk_read_mb = disk_io.read_bytes / (1024 * 1024) if disk_io else 0
            disk_write_mb = disk_io.write_bytes / (1024 * 1024) if disk_io else 0

            # Network I/O
            net_io = psutil.net_io_counters()
            net_sent_mb = net_io.bytes_sent / (1024 * 1024) if net_io else 0
            net_recv_mb = net_io.bytes_recv / (1024 * 1024) if net_io else 0

            # Network connections
            connections = len(psutil.net_connections())

            # Load average (Unix-like systems)
            try:
                load_avg = list(os.getloadavg())
            except (OSError, AttributeError):
                load_avg = [0.0, 0.0, 0.0]

            # Update Prometheus metrics
            self.system_cpu_usage.set(cpu_percent)
            self.system_memory_usage.set(memory_percent)
            self.active_connections.set(connections)

            return SystemMetrics(
                cpu_usage_percent=cpu_percent,
                memory_usage_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                disk_usage_percent=disk_percent,
                disk_io_read_mb=disk_read_mb,
                disk_io_write_mb=disk_write_mb,
                network_sent_mb=net_sent_mb,
                network_received_mb=net_recv_mb,
                active_connections=connections,
                load_average=load_avg,
            )

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            raise MonitoringError(f"System metrics collection failed: {e}")

    async def collect_application_metrics(
        self, cache_manager: Optional[CacheManager] = None
    ) -> ApplicationMetrics:
        """Collect application performance metrics."""
        try:
            # Calculate response time metrics
            with self.response_times_lock:
                if self.response_times:
                    sorted_times = sorted(self.response_times)
                    avg_response_time = sum(sorted_times) / len(sorted_times)
                    p95_response_time = sorted_times[int(0.95 * len(sorted_times))]
                    p99_response_time = sorted_times[int(0.99 * len(sorted_times))]
                else:
                    avg_response_time = p95_response_time = p99_response_time = 0.0

            # Cache hit ratio
            cache_hit_ratio = 0.0
            if cache_manager:
                try:
                    metrics = await cache_manager.get_comprehensive_metrics()
                    cache_hit_ratio = metrics.get("overall", {}).get(
                        "overall_hit_ratio", 0.0
                    )
                except Exception as e:
                    logger.warning(f"Failed to get cache metrics: {e}")

            # COPPA compliance score
            coppa_score = self._calculate_coppa_compliance_score()

            return ApplicationMetrics(
                avg_response_time_ms=avg_response_time,
                p95_response_time_ms=p95_response_time,
                p99_response_time_ms=p99_response_time,
                cache_hit_ratio=cache_hit_ratio,
                child_safety_violations=sum(self.safety_violations.values()),
                coppa_compliance_score=coppa_score,
            )

        except Exception as e:
            logger.error(f"Failed to collect application metrics: {e}")
            raise MonitoringError(f"Application metrics collection failed: {e}")

    def record_request(
        self, method: str, endpoint: str, status_code: int, duration_ms: float
    ) -> None:
        """Record HTTP request metrics."""
        self.request_count.labels(
            method=method, endpoint=endpoint, status_code=str(status_code)
        ).inc()
        self.request_duration.labels(method=method, endpoint=endpoint).observe(
            duration_ms / 1000.0
        )

        with self.response_times_lock:
            self.response_times.append(duration_ms)

    def record_child_safety_violation(self, violation_type: str) -> None:
        """Record child safety violation."""
        self.child_safety_violations.labels(violation_type=violation_type).inc()
        self.safety_violations[violation_type] += 1

        # Record for COPPA compliance tracking
        self.coppa_compliance_events.append(
            {
                "type": "violation",
                "violation_type": violation_type,
                "timestamp": get_current_timestamp(),
            }
        )

    def record_coppa_compliance_event(
        self, event_type: str, details: Dict[str, Any]
    ) -> None:
        """Record COPPA compliance event."""
        self.coppa_compliance_events.append(
            {
                "type": event_type,
                "details": details,
                "timestamp": get_current_timestamp(),
            }
        )

    def _calculate_coppa_compliance_score(self) -> float:
        """Calculate COPPA compliance score based on recent events."""
        if not self.coppa_compliance_events:
            return 100.0

        # Look at events from the last hour
        cutoff_time = get_current_timestamp() - 3600  # 1 hour ago
        recent_events = [
            event
            for event in self.coppa_compliance_events
            if event["timestamp"] > cutoff_time
        ]

        if not recent_events:
            return 100.0

        # Calculate score based on violations vs compliance events
        violations = sum(1 for event in recent_events if event["type"] == "violation")
        total_events = len(recent_events)

        if total_events == 0:
            return 100.0

        compliance_ratio = max(0, (total_events - violations) / total_events)
        return compliance_ratio * 100.0

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus-formatted metrics."""
        return generate_latest(self.registry).decode("utf-8")


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for performance monitoring."""

    def __init__(self, app, metrics_collector: MetricsCollector):
        super().__init__(app)
        self.metrics_collector = metrics_collector

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance."""
        start_time = time.time()

        # Extract request info
        method = request.method
        path = request.url.path

        # Sanitize endpoint for metrics (remove IDs, etc.)
        endpoint = self._sanitize_endpoint(path)

        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Record metrics
        self.metrics_collector.record_request(
            method=method,
            endpoint=endpoint,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        response.headers["X-Performance-Monitored"] = "true"

        # Check for child safety endpoints
        if self._is_child_safety_endpoint(path):
            response.headers["X-Child-Safe-Monitored"] = "true"

        return response

    def _sanitize_endpoint(self, path: str) -> str:
        """Sanitize endpoint path for metrics."""
        # Replace UUIDs, IDs, etc. with placeholders
        import re

        # Replace UUIDs
        path = re.sub(
            r"/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
            "/{uuid}",
            path,
        )

        # Replace numeric IDs
        path = re.sub(r"/\d+", "/{id}", path)

        # Replace child IDs for privacy
        path = re.sub(r"/children/[^/]+", "/children/{child_id}", path)

        return path

    def _is_child_safety_endpoint(self, path: str) -> bool:
        """Check if endpoint is related to child safety."""
        child_endpoints = ["/children/", "/safety/", "/coppa/", "/parental/"]
        return any(endpoint in path for endpoint in child_endpoints)


class AlertManager:
    """Manages performance alerts and notifications."""

    def __init__(self):
        self.thresholds: Dict[str, PerformanceThreshold] = {}
        self.handlers: List[BaseAlertHandler] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.violation_counts: Dict[str, int] = defaultdict(int)

    def add_threshold(self, threshold: PerformanceThreshold) -> None:
        """Add performance threshold."""
        self.thresholds[threshold.metric_name] = threshold

    def add_handler(self, handler: BaseAlertHandler) -> None:
        """Add alert handler."""
        self.handlers.append(handler)

    async def check_thresholds(self, metrics: Dict[str, float]) -> List[Alert]:
        """Check metrics against thresholds and generate alerts."""
        new_alerts = []

        for metric_name, value in metrics.items():
            if metric_name not in self.thresholds:
                continue

            threshold = self.thresholds[metric_name]
            alert_level = self._determine_alert_level(value, threshold)

            if alert_level:
                # Check for consecutive violations
                self.violation_counts[metric_name] += 1

                if (
                    self.violation_counts[metric_name]
                    >= threshold.consecutive_violations
                ):
                    alert = Alert(
                        id=f"{metric_name}_{int(time.time())}",
                        level=alert_level,
                        metric_name=metric_name,
                        current_value=value,
                        threshold_value=self._get_threshold_value(
                            alert_level, threshold
                        ),
                        message=self._generate_alert_message(
                            metric_name, value, alert_level, threshold
                        ),
                        timestamp=datetime.now(),
                        child_safety_related=threshold.child_safety_impact,
                    )

                    # Check if this is a new alert or escalation
                    existing_alert_key = f"{metric_name}_{alert_level.value}"
                    if existing_alert_key not in self.active_alerts:
                        self.active_alerts[existing_alert_key] = alert
                        self.alert_history.append(alert)
                        new_alerts.append(alert)

                        # Send notifications
                        await self._send_alert(alert)
            else:
                # Reset violation count if threshold is not exceeded
                self.violation_counts[metric_name] = 0

                # Check if we can resolve any active alerts for this metric
                await self._resolve_alerts_for_metric(metric_name, value)

        return new_alerts

    def _determine_alert_level(
        self, value: float, threshold: PerformanceThreshold
    ) -> Optional[AlertLevel]:
        """Determine alert level based on value and threshold."""
        if threshold.emergency_threshold and value >= threshold.emergency_threshold:
            return AlertLevel.EMERGENCY
        elif value >= threshold.critical_threshold:
            return AlertLevel.CRITICAL
        elif value >= threshold.warning_threshold:
            return AlertLevel.WARNING
        return None

    def _get_threshold_value(
        self, level: AlertLevel, threshold: PerformanceThreshold
    ) -> float:
        """Get threshold value for alert level."""
        if level == AlertLevel.EMERGENCY and threshold.emergency_threshold:
            return threshold.emergency_threshold
        elif level == AlertLevel.CRITICAL:
            return threshold.critical_threshold
        elif level == AlertLevel.WARNING:
            return threshold.warning_threshold
        return 0.0

    def _generate_alert_message(
        self,
        metric_name: str,
        value: float,
        level: AlertLevel,
        threshold: PerformanceThreshold,
    ) -> str:
        """Generate alert message."""
        threshold_value = self._get_threshold_value(level, threshold)

        base_message = f"{metric_name} is {value:.2f}, exceeding {level.value} threshold of {threshold_value:.2f}"

        if threshold.child_safety_impact:
            base_message += " - This may impact child safety and COPPA compliance"

        return base_message

    async def _send_alert(self, alert: Alert) -> None:
        """Send alert to all handlers."""
        for handler in self.handlers:
            try:
                await handler.send_alert(alert)
            except Exception as e:
                logger.error(f"Failed to send alert via {type(handler).__name__}: {e}")

    async def _resolve_alerts_for_metric(
        self, metric_name: str, current_value: float
    ) -> None:
        """Resolve active alerts for a metric if conditions are met."""
        to_resolve = []

        for alert_key, alert in self.active_alerts.items():
            if alert.metric_name == metric_name and not alert.resolved:
                threshold = self.thresholds[metric_name]

                # Check if value is now below warning threshold
                if current_value < threshold.warning_threshold:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    to_resolve.append(alert_key)

                    logger.info(f"Alert resolved: {alert.message}")

        # Remove resolved alerts from active alerts
        for key in to_resolve:
            del self.active_alerts[key]

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics."""
        active_by_level = defaultdict(int)
        for alert in self.active_alerts.values():
            active_by_level[alert.level.value] += 1

        child_safety_alerts = sum(
            1 for alert in self.active_alerts.values() if alert.child_safety_related
        )

        return {
            "total_active_alerts": len(self.active_alerts),
            "active_by_level": dict(active_by_level),
            "child_safety_alerts": child_safety_alerts,
            "total_historical_alerts": len(self.alert_history),
            "violation_counts": dict(self.violation_counts),
        }


class PerformanceMonitor:
    """Main performance monitoring system."""

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        cdn_manager: Optional[CDNManager] = None,
    ):
        self.cache_manager = cache_manager
        self.cdn_manager = cdn_manager

        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()

        # Background task for continuous monitoring
        self._monitoring_task = None
        self._running = False

        self._initialize_default_thresholds()
        self._initialize_default_handlers()

    def _initialize_default_thresholds(self) -> None:
        """Initialize default performance thresholds."""

        # Response time thresholds
        self.alert_manager.add_threshold(
            PerformanceThreshold(
                metric_name="avg_response_time_ms",
                warning_threshold=200.0,
                critical_threshold=500.0,
                emergency_threshold=1000.0,
                child_safety_impact=True,
            )
        )

        self.alert_manager.add_threshold(
            PerformanceThreshold(
                metric_name="p99_response_time_ms",
                warning_threshold=500.0,
                critical_threshold=1000.0,
                emergency_threshold=2000.0,
                child_safety_impact=True,
            )
        )

        # System resource thresholds
        self.alert_manager.add_threshold(
            PerformanceThreshold(
                metric_name="cpu_usage_percent",
                warning_threshold=70.0,
                critical_threshold=85.0,
                emergency_threshold=95.0,
            )
        )

        self.alert_manager.add_threshold(
            PerformanceThreshold(
                metric_name="memory_usage_percent",
                warning_threshold=80.0,
                critical_threshold=90.0,
                emergency_threshold=95.0,
            )
        )

        # Cache performance thresholds
        self.alert_manager.add_threshold(
            PerformanceThreshold(
                metric_name="cache_hit_ratio",
                warning_threshold=0.5,  # Below 50%
                critical_threshold=0.3,  # Below 30%
                emergency_threshold=0.1,  # Below 10%
            )
        )

        # Child safety thresholds
        self.alert_manager.add_threshold(
            PerformanceThreshold(
                metric_name="child_safety_violations",
                warning_threshold=1.0,
                critical_threshold=5.0,
                emergency_threshold=10.0,
                child_safety_impact=True,
            )
        )

        self.alert_manager.add_threshold(
            PerformanceThreshold(
                metric_name="coppa_compliance_score",
                warning_threshold=95.0,  # Below 95%
                critical_threshold=90.0,  # Below 90%
                emergency_threshold=80.0,  # Below 80%
                child_safety_impact=True,
            )
        )

    def _initialize_default_handlers(self) -> None:
        """Initialize default alert handlers."""
        # Add log handler by default
        self.alert_manager.add_handler(LogAlertHandler())

    def add_webhook_handler(self, webhook_url: str) -> None:
        """Add webhook alert handler."""
        self.alert_manager.add_handler(WebhookAlertHandler(webhook_url))

    async def start_monitoring(self, interval_seconds: int = 60) -> None:
        """Start continuous performance monitoring."""
        if self._running:
            return

        self._running = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )

        logger.info(f"Performance monitoring started with {interval_seconds}s interval")

    async def stop_monitoring(self) -> None:
        """Stop performance monitoring."""
        self._running = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Performance monitoring stopped")

    async def _monitoring_loop(self, interval_seconds: int) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Collect all metrics
                system_metrics = await self.metrics_collector.collect_system_metrics()
                app_metrics = await self.metrics_collector.collect_application_metrics(
                    self.cache_manager
                )

                # Prepare metrics dictionary for threshold checking
                metrics_dict = {
                    "cpu_usage_percent": system_metrics.cpu_usage_percent,
                    "memory_usage_percent": system_metrics.memory_usage_percent,
                    "avg_response_time_ms": app_metrics.avg_response_time_ms,
                    "p99_response_time_ms": app_metrics.p99_response_time_ms,
                    "cache_hit_ratio": app_metrics.cache_hit_ratio,
                    "child_safety_violations": float(
                        app_metrics.child_safety_violations
                    ),
                    "coppa_compliance_score": app_metrics.coppa_compliance_score,
                }

                # Check thresholds and generate alerts
                await self.alert_manager.check_thresholds(metrics_dict)

                # Log key metrics
                logger.info(
                    "Performance metrics collected",
                    extra={
                        "cpu_percent": system_metrics.cpu_usage_percent,
                        "memory_percent": system_metrics.memory_usage_percent,
                        "avg_response_time_ms": app_metrics.avg_response_time_ms,
                        "cache_hit_ratio": app_metrics.cache_hit_ratio,
                        "coppa_compliance": app_metrics.coppa_compliance_score,
                    },
                )

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # Wait for next interval
            await asyncio.sleep(interval_seconds)

    def get_middleware(self) -> PerformanceMonitoringMiddleware:
        """Get FastAPI middleware for request monitoring."""
        return PerformanceMonitoringMiddleware(None, self.metrics_collector)

    async def get_performance_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive performance data for dashboard."""
        try:
            system_metrics = await self.metrics_collector.collect_system_metrics()
            app_metrics = await self.metrics_collector.collect_application_metrics(
                self.cache_manager
            )
            alert_summary = self.alert_manager.get_alert_summary()

            # CDN metrics if available
            cdn_metrics = {}
            if self.cdn_manager:
                try:
                    cdn_data = await self.cdn_manager.get_performance_summary()
                    cdn_metrics = cdn_data
                except Exception as e:
                    logger.warning(f"Failed to get CDN metrics: {e}")

            return {
                "system": {
                    "cpu_usage_percent": system_metrics.cpu_usage_percent,
                    "memory_usage_percent": system_metrics.memory_usage_percent,
                    "memory_used_mb": system_metrics.memory_used_mb,
                    "disk_usage_percent": system_metrics.disk_usage_percent,
                    "active_connections": system_metrics.active_connections,
                    "load_average": system_metrics.load_average,
                },
                "application": {
                    "avg_response_time_ms": app_metrics.avg_response_time_ms,
                    "p95_response_time_ms": app_metrics.p95_response_time_ms,
                    "p99_response_time_ms": app_metrics.p99_response_time_ms,
                    "cache_hit_ratio": app_metrics.cache_hit_ratio,
                    "child_safety_violations": app_metrics.child_safety_violations,
                    "coppa_compliance_score": app_metrics.coppa_compliance_score,
                },
                "cdn": cdn_metrics,
                "alerts": alert_summary,
                "active_alerts": [
                    {
                        "id": alert.id,
                        "level": alert.level.value,
                        "metric": alert.metric_name,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "child_safety_related": alert.child_safety_related,
                    }
                    for alert in self.alert_manager.get_active_alerts()
                ],
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            raise MonitoringError(f"Dashboard data collection failed: {e}")

    async def export_metrics(self, format: str = "prometheus") -> str:
        """Export metrics in specified format."""
        if format == "prometheus":
            return self.metrics_collector.get_prometheus_metrics()
        elif format == "json":
            dashboard_data = await self.get_performance_dashboard_data()
            return json.dumps(dashboard_data, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for monitoring system."""
        health_status = {
            "monitoring_active": self._running,
            "metrics_collector_healthy": True,
            "alert_manager_healthy": True,
            "active_alerts_count": len(self.alert_manager.get_active_alerts()),
            "critical_alerts_count": 0,
            "child_safety_status": "compliant",
            "overall_status": "healthy",
        }

        try:
            # Check metrics collection
            await self.metrics_collector.collect_system_metrics()

            # Check alert levels
            critical_alerts = [
                alert
                for alert in self.alert_manager.get_active_alerts()
                if alert.level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]
            ]
            health_status["critical_alerts_count"] = len(critical_alerts)

            # Check child safety compliance
            app_metrics = await self.metrics_collector.collect_application_metrics()
            if app_metrics.coppa_compliance_score < 90.0:
                health_status["child_safety_status"] = "degraded"
            if app_metrics.coppa_compliance_score < 80.0:
                health_status["child_safety_status"] = "non_compliant"

            # Overall status
            if critical_alerts or app_metrics.coppa_compliance_score < 80.0:
                health_status["overall_status"] = "critical"
            elif (
                len(self.alert_manager.get_active_alerts()) > 0
                or app_metrics.coppa_compliance_score < 95.0
            ):
                health_status["overall_status"] = "degraded"

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["overall_status"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status


# Factory function for easy initialization
def create_performance_monitor(
    cache_manager: Optional[CacheManager] = None,
    cdn_manager: Optional[CDNManager] = None,
    webhook_url: Optional[str] = None,
) -> PerformanceMonitor:
    """Create performance monitor with optional integrations."""

    monitor = PerformanceMonitor(cache_manager, cdn_manager)

    if webhook_url:
        monitor.add_webhook_handler(webhook_url)

    return monitor
