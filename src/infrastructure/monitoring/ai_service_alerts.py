"""
AI Service Monitoring and Alerting System
=========================================
Production-ready monitoring and alerting for AI Service with:
- Real-time performance monitoring
- Automatic alert generation
- Integration with external monitoring systems
- SRE-ready metrics and dashboards
"""

import asyncio
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from collections import defaultdict, deque
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import redis.asyncio as aioredis
from prometheus_client import Counter, Histogram, Gauge, Summary
import httpx


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Types of metrics to monitor."""

    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    SAFETY_SCORE = "safety_score"
    RATE_LIMIT_VIOLATIONS = "rate_limit_violations"
    REDIS_PERFORMANCE = "redis_performance"
    CONCURRENT_REQUESTS = "concurrent_requests"
    
    # Enhanced metrics for new features
    RETRY_RATE = "retry_rate"
    CIRCUIT_BREAKER_TRIPS = "circuit_breaker_trips"
    JWT_TOKEN_FAILURES = "jwt_token_failures"
    DEVICE_TRACKING_ANOMALIES = "device_tracking_anomalies"
    AUDIO_PROCESSING_LATENCY = "audio_processing_latency"
    FALLBACK_USAGE = "fallback_usage"
    SESSION_SECURITY_VIOLATIONS = "session_security_violations"


@dataclass
class Alert:
    """Alert data structure."""

    id: str
    severity: AlertSeverity
    metric_type: MetricType
    message: str
    value: float
    threshold: float
    timestamp: datetime
    service: str = "ai_service"
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["severity"] = self.severity.value
        data["metric_type"] = self.metric_type.value
        return data


@dataclass
class MetricThreshold:
    """Metric threshold configuration."""

    metric_type: MetricType
    warning_threshold: float
    error_threshold: float
    critical_threshold: float
    comparison: str = "greater_than"  # greater_than, less_than, equals
    window_seconds: int = 300  # 5 minutes
    min_samples: int = 5


class AlertChannel(ABC):
    """Abstract base class for alert channels."""

    @abstractmethod
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert through this channel."""
        pass


class SlackAlertChannel(AlertChannel):
    """Slack alert channel integration."""

    def __init__(self, webhook_url: str, channel: str = "#ai-alerts"):
        self.webhook_url = webhook_url
        self.channel = channel
        self.logger = logging.getLogger(__name__)

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        try:
            import aiohttp

            color_map = {
                AlertSeverity.INFO: "#36a64f",  # green
                AlertSeverity.WARNING: "#ff9900",  # orange
                AlertSeverity.ERROR: "#ff0000",  # red
                AlertSeverity.CRITICAL: "#8B0000",  # dark red
            }

            emoji_map = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.ERROR: "🚨",
                AlertSeverity.CRITICAL: "🔥",
            }

            payload = {
                "channel": self.channel,
                "username": "AI Service Monitor",
                "text": f"{emoji_map[alert.severity]} *{alert.severity.value.upper()}* Alert",
                "attachments": [
                    {
                        "color": color_map[alert.severity],
                        "fields": [
                            {"title": "Service", "value": alert.service, "short": True},
                            {
                                "title": "Metric",
                                "value": alert.metric_type.value,
                                "short": True,
                            },
                            {
                                "title": "Message",
                                "value": alert.message,
                                "short": False,
                            },
                            {
                                "title": "Value",
                                "value": f"{alert.value:.2f}",
                                "short": True,
                            },
                            {
                                "title": "Threshold",
                                "value": f"{alert.threshold:.2f}",
                                "short": True,
                            },
                            {
                                "title": "Time",
                                "value": alert.timestamp.strftime(
                                    "%Y-%m-%d %H:%M:%S UTC"
                                ),
                                "short": False,
                            },
                        ],
                    }
                ],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 200:
                        self.logger.info(f"Slack alert sent: {alert.id}")
                        return True
                    else:
                        self.logger.error(
                            f"Failed to send Slack alert: {response.status}"
                        )
                        return False

        except Exception as e:
            self.logger.error(f"Error sending Slack alert: {e}")
            return False


class EmailAlertChannel(AlertChannel):
    """Email alert channel integration."""

    def __init__(self, smtp_config: Dict[str, Any], recipients: List[str]):
        self.smtp_config = smtp_config
        self.recipients = recipients
        self.logger = logging.getLogger(__name__)

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            import aiosmtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["From"] = self.smtp_config["from_email"]
            msg["To"] = ", ".join(self.recipients)
            msg["Subject"] = (
                f"[{alert.severity.value.upper()}] AI Service Alert - {alert.message}"
            )

            # HTML email content
            html_content = f"""
            <html>
            <body>
                <h2>🤖 AI Service Alert</h2>
                <p><strong>Severity:</strong> <span style="color: {'red' if alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL] else 'orange' if alert.severity == AlertSeverity.WARNING else 'green'}">{alert.severity.value.upper()}</span></p>
                <p><strong>Service:</strong> {alert.service}</p>
                <p><strong>Metric:</strong> {alert.metric_type.value}</p>
                <p><strong>Message:</strong> {alert.message}</p>
                <p><strong>Value:</strong> {alert.value:.2f}</p>
                <p><strong>Threshold:</strong> {alert.threshold:.2f}</p>
                <p><strong>Time:</strong> {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
                {f'<p><strong>Metadata:</strong> {json.dumps(alert.metadata, indent=2)}</p>' if alert.metadata else ''}
            </body>
            </html>
            """

            msg.set_content(html_content, subtype="html")

            await aiosmtplib.send(
                msg,
                hostname=self.smtp_config["hostname"],
                port=self.smtp_config["port"],
                username=self.smtp_config["username"],
                password=self.smtp_config["password"],
                use_tls=self.smtp_config.get("use_tls", True),
            )

            self.logger.info(f"Email alert sent: {alert.id}")
            return True

        except Exception as e:
            self.logger.error(f"Error sending email alert: {e}")
            return False


class PagerDutyAlertChannel(AlertChannel):
    """PagerDuty alert channel for critical incidents."""

    def __init__(self, integration_key: str):
        self.integration_key = integration_key
        self.logger = logging.getLogger(__name__)

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to PagerDuty."""
        try:
            import aiohttp

            # Only send ERROR and CRITICAL alerts to PagerDuty
            if alert.severity not in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
                return True

            payload = {
                "routing_key": self.integration_key,
                "event_action": "trigger",
                "dedup_key": f"ai_service_{alert.metric_type.value}_{alert.timestamp.strftime('%Y%m%d%H')}",
                "payload": {
                    "summary": f"AI Service {alert.severity.value.upper()}: {alert.message}",
                    "source": "ai_service_monitor",
                    "severity": (
                        "critical"
                        if alert.severity == AlertSeverity.CRITICAL
                        else "error"
                    ),
                    "component": "ai_service",
                    "group": "teddy_bear_platform",
                    "class": alert.metric_type.value,
                    "custom_details": {
                        "metric_value": alert.value,
                        "threshold": alert.threshold,
                        "service": alert.service,
                        "metadata": alert.metadata or {},
                    },
                },
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 202:
                        self.logger.info(f"PagerDuty alert sent: {alert.id}")
                        return True
                    else:
                        self.logger.error(
                            f"Failed to send PagerDuty alert: {response.status}"
                        )
                        return False

        except Exception as e:
            self.logger.error(f"Error sending PagerDuty alert: {e}")
            return False


class AIServiceMonitor:
    """Comprehensive AI Service monitoring and alerting system."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        alert_channels: List[AlertChannel] = None,
        thresholds: List[MetricThreshold] = None,
    ):
        self.redis_url = redis_url
        self.alert_channels = alert_channels or []
        self.thresholds = thresholds or self._default_thresholds()
        self.logger = logging.getLogger(__name__)
        self.redis_pool = None

        # Prometheus metrics
        self.response_time_histogram = Histogram(
            "ai_service_response_time_seconds",
            "AI service response time",
            ["method", "status"],
        )

        self.error_counter = Counter(
            "ai_service_errors_total",
            "Total AI service errors",
            ["error_type", "severity"],
        )

        self.throughput_gauge = Gauge(
            "ai_service_throughput_requests_per_second", "AI service throughput"
        )

        self.safety_score_histogram = Histogram(
            "ai_service_safety_score", "AI service safety scores", ["age_group"]
        )

        self.concurrent_requests_gauge = Gauge(
            "ai_service_concurrent_requests", "Current concurrent requests"
        )

        self.redis_performance_histogram = Histogram(
            "ai_service_redis_operation_seconds",
            "Redis operation performance",
            ["operation"],
        )

        # Alert state tracking
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []

        # Monitoring task
        self.monitoring_task = None
        self.is_monitoring = False

    def _default_thresholds(self) -> List[MetricThreshold]:
        """Default metric thresholds for alerting."""
        return [
            MetricThreshold(
                metric_type=MetricType.RESPONSE_TIME,
                warning_threshold=5.0,  # 5 seconds
                error_threshold=10.0,  # 10 seconds
                critical_threshold=20.0,  # 20 seconds
                comparison="greater_than",
            ),
            MetricThreshold(
                metric_type=MetricType.ERROR_RATE,
                warning_threshold=0.05,  # 5% error rate
                error_threshold=0.10,  # 10% error rate
                critical_threshold=0.25,  # 25% error rate
                comparison="greater_than",
            ),
            MetricThreshold(
                metric_type=MetricType.THROUGHPUT,
                warning_threshold=10.0,  # < 10 req/s
                error_threshold=5.0,  # < 5 req/s
                critical_threshold=1.0,  # < 1 req/s
                comparison="less_than",
            ),
            MetricThreshold(
                metric_type=MetricType.SAFETY_SCORE,
                warning_threshold=0.8,  # Safety score < 0.8
                error_threshold=0.6,  # Safety score < 0.6
                critical_threshold=0.4,  # Safety score < 0.4
                comparison="less_than",
            ),
            MetricThreshold(
                metric_type=MetricType.RATE_LIMIT_VIOLATIONS,
                warning_threshold=10.0,  # 10 violations/hour
                error_threshold=50.0,  # 50 violations/hour
                critical_threshold=100.0,  # 100 violations/hour
                comparison="greater_than",
            ),
            MetricThreshold(
                metric_type=MetricType.REDIS_PERFORMANCE,
                warning_threshold=0.1,  # 100ms Redis ops
                error_threshold=0.5,  # 500ms Redis ops
                critical_threshold=2.0,  # 2s Redis ops
                comparison="greater_than",
            ),
        ]

    async def start_monitoring(self):
        """Start the monitoring system."""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.redis_pool = aioredis.ConnectionPool.from_url(
            self.redis_url, max_connections=10
        )

        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("AI Service monitoring started")

    async def stop_monitoring(self):
        """Stop the monitoring system."""
        self.is_monitoring = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        if self.redis_pool:
            await self.redis_pool.disconnect()

        self.logger.info("AI Service monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                await self._check_metrics()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _check_metrics(self):
        """Check all metrics against thresholds."""
        redis = aioredis.Redis(connection_pool=self.redis_pool)

        try:
            # Check each metric type
            for threshold in self.thresholds:
                try:
                    metric_value = await self._get_metric_value(
                        redis, threshold.metric_type
                    )
                    if metric_value is not None:
                        await self._evaluate_threshold(threshold, metric_value)
                except Exception as e:
                    self.logger.error(f"Error checking {threshold.metric_type}: {e}")

        finally:
            await redis.aclose()  # Changed from close() to aclose() for redis.asyncio

    async def _get_metric_value(
        self, redis: aioredis.Redis, metric_type: MetricType
    ) -> Optional[float]:
        """Get current value for a metric type."""
        try:
            current_time = time.time()
            window_start = current_time - 300  # 5 minute window

            if metric_type == MetricType.RESPONSE_TIME:
                # Get average response time from recent requests
                response_times = await redis.zrangebyscore(
                    "ai:metrics:response_times",
                    window_start,
                    current_time,
                    withscores=True,
                )
                if response_times:
                    times = [float(score) for _, score in response_times]
                    return sum(times) / len(times)

            elif metric_type == MetricType.ERROR_RATE:
                # Calculate error rate
                total_requests = await redis.zcount(
                    "ai:metrics:requests", window_start, current_time
                )
                error_requests = await redis.zcount(
                    "ai:metrics:errors", window_start, current_time
                )
                if total_requests > 0:
                    return error_requests / total_requests

            elif metric_type == MetricType.THROUGHPUT:
                # Calculate requests per second
                total_requests = await redis.zcount(
                    "ai:metrics:requests", window_start, current_time
                )
                return total_requests / 300  # requests per second over 5 minutes

            elif metric_type == MetricType.SAFETY_SCORE:
                # Get average safety score
                safety_scores = await redis.zrangebyscore(
                    "ai:metrics:safety_scores",
                    window_start,
                    current_time,
                    withscores=True,
                )
                if safety_scores:
                    scores = [float(score) for _, score in safety_scores]
                    return sum(scores) / len(scores)

            elif metric_type == MetricType.RATE_LIMIT_VIOLATIONS:
                # Count rate limit violations per hour
                hour_start = current_time - 3600
                violations = await redis.zcount(
                    "ai:metrics:rate_limit_violations", hour_start, current_time
                )
                return float(violations)

            elif metric_type == MetricType.REDIS_PERFORMANCE:
                # Get average Redis operation time
                redis_times = await redis.zrangebyscore(
                    "ai:metrics:redis_times",
                    window_start,
                    current_time,
                    withscores=True,
                )
                if redis_times:
                    times = [float(score) for _, score in redis_times]
                    return sum(times) / len(times)

            return None

        except Exception as e:
            self.logger.error(f"Error getting metric value for {metric_type}: {e}")
            return None

    async def _evaluate_threshold(self, threshold: MetricThreshold, value: float):
        """Evaluate a metric value against its threshold."""
        alert_key = f"{threshold.metric_type.value}"

        # Determine severity
        severity = None
        threshold_value = None

        if threshold.comparison == "greater_than":
            if value >= threshold.critical_threshold:
                severity = AlertSeverity.CRITICAL
                threshold_value = threshold.critical_threshold
            elif value >= threshold.error_threshold:
                severity = AlertSeverity.ERROR
                threshold_value = threshold.error_threshold
            elif value >= threshold.warning_threshold:
                severity = AlertSeverity.WARNING
                threshold_value = threshold.warning_threshold

        elif threshold.comparison == "less_than":
            if value <= threshold.critical_threshold:
                severity = AlertSeverity.CRITICAL
                threshold_value = threshold.critical_threshold
            elif value <= threshold.error_threshold:
                severity = AlertSeverity.ERROR
                threshold_value = threshold.error_threshold
            elif value <= threshold.warning_threshold:
                severity = AlertSeverity.WARNING
                threshold_value = threshold.warning_threshold

        # Handle alert state
        if severity:
            # Create or update alert
            if (
                alert_key not in self.active_alerts
                or self.active_alerts[alert_key].severity != severity
            ):
                alert = Alert(
                    id=f"{alert_key}_{int(time.time())}",
                    severity=severity,
                    metric_type=threshold.metric_type,
                    message=f"{threshold.metric_type.value} {threshold.comparison.replace('_', ' ')} {threshold_value:.2f}",
                    value=value,
                    threshold=threshold_value,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "comparison": threshold.comparison,
                        "window_seconds": threshold.window_seconds,
                    },
                )

                self.active_alerts[alert_key] = alert
                self.alert_history.append(alert)

                # Send alert through all channels
                await self._send_alert(alert)

        else:
            # Clear alert if it exists
            if alert_key in self.active_alerts:
                resolved_alert = self.active_alerts.pop(alert_key)
                self.logger.info(f"Alert resolved: {alert_key}")

                # Optionally send resolution notification
                await self._send_resolution(resolved_alert, value)

    async def _send_alert(self, alert: Alert):
        """Send alert through all configured channels."""
        self.logger.warning(f"ALERT: {alert.message} (value: {alert.value:.2f})")

        # Send through all alert channels
        for channel in self.alert_channels:
            try:
                await channel.send_alert(alert)
            except Exception as e:
                self.logger.error(
                    f"Failed to send alert through {type(channel).__name__}: {e}"
                )

    async def _send_resolution(self, alert: Alert, current_value: float):
        """Send alert resolution notification."""
        resolution_message = (
            f"RESOLVED: {alert.message} (current value: {current_value:.2f})"
        )
        self.logger.info(resolution_message)

        # Create resolution alert
        resolution_alert = Alert(
            id=f"resolved_{alert.id}",
            severity=AlertSeverity.INFO,
            metric_type=alert.metric_type,
            message=f"RESOLVED: {alert.message}",
            value=current_value,
            threshold=alert.threshold,
            timestamp=datetime.utcnow(),
            metadata={"resolved_alert_id": alert.id},
        )

        # Send resolution through channels that support it
        for channel in self.alert_channels:
            if hasattr(channel, "send_resolution"):
                try:
                    await channel.send_resolution(resolution_alert)
                except Exception as e:
                    self.logger.error(
                        f"Failed to send resolution through {type(channel).__name__}: {e}"
                    )

    # Public methods for recording metrics
    async def record_request(
        self, response_time: float, error: bool = False, safety_score: float = None
    ):
        """Record a request for monitoring."""
        current_time = time.time()

        redis = aioredis.Redis(connection_pool=self.redis_pool)

        try:
            # Record request
            await redis.zadd("ai:metrics:requests", {str(current_time): current_time})

            # Record response time
            await redis.zadd(
                "ai:metrics:response_times", {str(current_time): response_time}
            )

            # Record error if applicable
            if error:
                await redis.zadd("ai:metrics:errors", {str(current_time): current_time})

            # Record safety score if provided
            if safety_score is not None:
                await redis.zadd(
                    "ai:metrics:safety_scores", {str(current_time): safety_score}
                )

            # Clean up old data (keep last 24 hours)
            cleanup_time = current_time - 86400
            await redis.zremrangebyscore("ai:metrics:requests", 0, cleanup_time)
            await redis.zremrangebyscore("ai:metrics:response_times", 0, cleanup_time)
            await redis.zremrangebyscore("ai:metrics:errors", 0, cleanup_time)
            await redis.zremrangebyscore("ai:metrics:safety_scores", 0, cleanup_time)

        finally:
            await redis.aclose()  # Changed from close() to aclose() for redis.asyncio

    async def record_rate_limit_violation(self, child_id: str, violation_type: str):
        """Record a rate limit violation."""
        current_time = time.time()

        redis = aioredis.Redis(connection_pool=self.redis_pool)

        try:
            await redis.zadd(
                "ai:metrics:rate_limit_violations",
                {f"{child_id}:{violation_type}:{current_time}": current_time},
            )

            # Clean up old violations (keep last 24 hours)
            cleanup_time = current_time - 86400
            await redis.zremrangebyscore(
                "ai:metrics:rate_limit_violations", 0, cleanup_time
            )

        finally:
            await redis.aclose()  # Changed from close() to aclose() for redis.asyncio

    async def record_redis_operation(self, operation: str, duration: float):
        """Record Redis operation performance."""
        current_time = time.time()

        redis = aioredis.Redis(connection_pool=self.redis_pool)

        try:
            await redis.zadd(
                "ai:metrics:redis_times", {f"{operation}:{current_time}": duration}
            )

            # Clean up old data
            cleanup_time = current_time - 86400
            await redis.zremrangebyscore("ai:metrics:redis_times", 0, cleanup_time)

        finally:
            await redis.aclose()  # Changed from close() to aclose() for redis.asyncio

    def get_active_alerts(self) -> List[Alert]:
        """Get list of currently active alerts."""
        return list(self.active_alerts.values())

    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for specified number of hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [alert for alert in self.alert_history if alert.timestamp >= cutoff_time]


# Factory function for easy setup
def create_ai_service_monitor(
    redis_url: str = "redis://localhost:6379",
    slack_webhook_url: str = None,
    email_config: Dict[str, Any] = None,
    pagerduty_key: str = None,
    custom_thresholds: List[MetricThreshold] = None,
) -> AIServiceMonitor:
    """Factory function to create AI service monitor with common configurations."""

    alert_channels = []

    # Add Slack channel if configured
    if slack_webhook_url:
        alert_channels.append(SlackAlertChannel(slack_webhook_url))

    # Add email channel if configured
    if email_config:
        alert_channels.append(
            EmailAlertChannel(
                smtp_config=email_config["smtp"], recipients=email_config["recipients"]
            )
        )

    # Add PagerDuty channel if configured
    if pagerduty_key:
        alert_channels.append(PagerDutyAlertChannel(pagerduty_key))

    return AIServiceMonitor(
        redis_url=redis_url, alert_channels=alert_channels, thresholds=custom_thresholds
    )


# =============================================================================
# ENHANCED ALERTING SYSTEM INTEGRATION
# =============================================================================


class AlertCategory(Enum):
    """Extended alert categories for enhanced monitoring."""

    # Original categories
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"

    # Enhanced categories
    SAFETY = "safety"
    SECURITY = "security"
    COPPA_COMPLIANCE = "coppa_compliance"
    DATA_INTEGRITY = "data_integrity"
    EXTERNAL_SERVICES = "external_services"


class ErrorPattern:
    """Enhanced error pattern detection for advanced monitoring."""

    def __init__(
        self,
        name: str,
        pattern: str,
        severity: AlertSeverity,
        category: AlertCategory,
        threshold_count: int = 1,
        time_window_minutes: int = 5,
        description: str = "",
    ):
        self.name = name
        self.pattern = pattern
        self.severity = severity
        self.category = category
        self.threshold_count = threshold_count
        self.time_window_minutes = time_window_minutes
        self.description = description
        self.occurrences = deque()

    def add_occurrence(self):
        """Add an occurrence of this pattern."""
        self.occurrences.append(datetime.utcnow())

    def check_threshold(self) -> bool:
        """Check if error pattern threshold is exceeded."""
        now = datetime.utcnow()
        cutoff_time = now - timedelta(minutes=self.time_window_minutes)

        # Remove old occurrences
        while self.occurrences and self.occurrences[0] < cutoff_time:
            self.occurrences.popleft()

        return len(self.occurrences) >= self.threshold_count

    def matches_message(self, message: str) -> bool:
        """Check if message matches this pattern."""
        return bool(re.search(self.pattern, message.lower(), re.IGNORECASE))


@dataclass
class EnhancedAlertEvent:
    """Enhanced alert event with additional metadata."""

    id: str
    timestamp: datetime
    severity: AlertSeverity
    category: AlertCategory
    title: str
    description: str
    source_service: str
    affected_component: str
    metadata: Dict[str, Any]
    context: Dict[str, Any]
    correlation_id: Optional[str] = None
    parent_alert_id: Optional[str] = None

    # AI Service compatibility
    metric_type: Optional[MetricType] = None
    value: Optional[float] = None
    threshold: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["severity"] = self.severity.value
        data["category"] = self.category.value
        if self.metric_type:
            data["metric_type"] = self.metric_type.value
        return data

    def to_alert(self) -> Alert:
        """Convert to standard Alert format for compatibility."""
        return Alert(
            id=self.id,
            severity=self.severity,
            metric_type=self.metric_type or MetricType.ERROR_RATE,
            message=f"{self.title}: {self.description}",
            value=self.value or 0.0,
            threshold=self.threshold or 0.0,
            timestamp=self.timestamp,
            service=self.source_service,
            metadata=self.metadata,
        )


class EnhancedAlertChannel(AlertChannel):
    """Enhanced alert channel with webhook support."""

    def __init__(self, webhook_url: str, channel_type: str = "webhook"):
        self.webhook_url = webhook_url
        self.channel_type = channel_type
        self.logger = logging.getLogger(__name__)

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "alert": alert.to_dict(),
                    "channel_type": self.channel_type,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                response = await client.post(
                    self.webhook_url, json=payload, timeout=10.0
                )

                if response.status_code == 200:
                    self.logger.info(f"Successfully sent alert {alert.id} via webhook")
                    return True
                else:
                    self.logger.error(
                        f"Failed to send webhook alert: {response.status_code}"
                    )
                    return False

        except Exception as e:
            self.logger.error(f"Error sending webhook alert: {e}")
            return False

    async def send_enhanced_alert(self, alert: EnhancedAlertEvent) -> bool:
        """Send enhanced alert event."""
        return await self.send_alert(alert.to_alert())


class EnhancedAIServiceMonitor(AIServiceMonitor):
    """Enhanced AI Service Monitor with advanced error detection."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        alert_channels: List[AlertChannel] = None,
        thresholds: List[MetricThreshold] = None,
        error_patterns: List[ErrorPattern] = None,
    ):
        super().__init__(redis_url, alert_channels, thresholds)

        # Enhanced alerting features
        self.error_patterns = {}
        self.alert_correlation = defaultdict(list)
        self.notification_handlers = {}

        # Setup enhanced features
        self._setup_error_patterns(error_patterns or [])
        self._setup_notification_handlers()

    def _setup_error_patterns(self, custom_patterns: List[ErrorPattern]):
        """Setup comprehensive error patterns for monitoring."""
        # Standard error patterns
        default_patterns = [
            # Safety patterns
            ErrorPattern(
                name="inappropriate_content_detected",
                pattern="inappropriate.*content|unsafe.*message|content.*filter.*triggered",
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.SAFETY,
                threshold_count=1,
                time_window_minutes=1,
                description="Inappropriate content detected in child interaction",
            ),
            ErrorPattern(
                name="child_safety_violation",
                pattern="child.*safety.*violation|age.*verification.*failed",
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.SAFETY,
                threshold_count=1,
                time_window_minutes=1,
                description="Child safety violation detected",
            ),
            # Performance patterns
            ErrorPattern(
                name="high_response_time",
                pattern="response.*time.*exceeded|slow.*response|timeout.*warning",
                severity=AlertSeverity.WARNING,
                category=AlertCategory.PERFORMANCE,
                threshold_count=5,
                time_window_minutes=5,
                description="High response times detected",
            ),
            # Security patterns
            ErrorPattern(
                name="unauthorized_access_attempt",
                pattern="unauthorized.*access|invalid.*token|authentication.*failed",
                severity=AlertSeverity.ERROR,
                category=AlertCategory.SECURITY,
                threshold_count=10,
                time_window_minutes=5,
                description="Multiple unauthorized access attempts",
            ),
            # COPPA Compliance patterns
            ErrorPattern(
                name="coppa_data_violation",
                pattern="coppa.*violation|child.*data.*exposed|pii.*leaked",
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.COPPA_COMPLIANCE,
                threshold_count=1,
                time_window_minutes=1,
                description="COPPA compliance violation detected",
            ),
            # External Services patterns
            ErrorPattern(
                name="openai_api_failure",
                pattern="openai.*api.*failed|ai.*service.*timeout|openai.*rate.*limit",
                severity=AlertSeverity.WARNING,
                category=AlertCategory.EXTERNAL_SERVICES,
                threshold_count=5,
                time_window_minutes=10,
                description="OpenAI API service issues",
            ),
        ]

        # Combine default and custom patterns
        all_patterns = default_patterns + custom_patterns
        for pattern in all_patterns:
            self.error_patterns[pattern.name] = pattern

    def _setup_notification_handlers(self):
        """Setup notification handlers for different channels."""
        self.notification_handlers = {
            "email": self._send_email_notification,
            "slack": self._send_slack_notification,
            "webhook": self._send_webhook_notification,
            "pagerduty": self._send_pagerduty_notification,
        }

    async def process_log_entry(
        self, log_entry: Dict[str, Any]
    ) -> List[EnhancedAlertEvent]:
        """Process a log entry and generate enhanced alerts if patterns match."""
        alerts_generated = []

        try:
            log_message = log_entry.get("message", "").lower()
            timestamp = datetime.fromisoformat(
                log_entry.get("timestamp", datetime.utcnow().isoformat())
            )

            # Check against all error patterns
            for pattern_name, pattern in self.error_patterns.items():
                if pattern.matches_message(log_message):
                    pattern.add_occurrence()

                    if pattern.check_threshold():
                        alert = await self._create_enhanced_alert(
                            pattern=pattern, log_entry=log_entry, timestamp=timestamp
                        )

                        if await self._should_send_enhanced_alert(alert):
                            alerts_generated.append(alert)
                            await self._send_enhanced_alert(alert)

        except Exception as e:
            self.logger.error(f"Error processing log entry: {e}", log_entry=log_entry)

        return alerts_generated

    async def _create_enhanced_alert(
        self, pattern: ErrorPattern, log_entry: Dict[str, Any], timestamp: datetime
    ) -> EnhancedAlertEvent:
        """Create enhanced alert event from pattern match."""
        import uuid

        alert = EnhancedAlertEvent(
            id=str(uuid.uuid4()),
            timestamp=timestamp,
            severity=pattern.severity,
            category=pattern.category,
            title=f"Pattern Detected: {pattern.name}",
            description=pattern.description,
            source_service=log_entry.get("service", "ai_service"),
            affected_component=log_entry.get("component", "unknown"),
            metadata={
                "pattern_name": pattern.name,
                "pattern_threshold": pattern.threshold_count,
                "occurrences_count": len(pattern.occurrences),
                "log_level": log_entry.get("level", "unknown"),
            },
            context={
                "original_message": log_entry.get("message", ""),
                "log_entry": log_entry,
                "pattern_details": {
                    "pattern": pattern.pattern,
                    "time_window_minutes": pattern.time_window_minutes,
                },
            },
        )

        return alert

    async def _should_send_enhanced_alert(self, alert: EnhancedAlertEvent) -> bool:
        """Determine if enhanced alert should be sent."""
        # Always send critical alerts
        if alert.severity == AlertSeverity.CRITICAL:
            return True

        # Check for alert correlation and deduplication
        similar_alerts = self.alert_correlation.get(alert.category.value, [])
        recent_cutoff = datetime.utcnow() - timedelta(minutes=15)

        recent_similar = [
            a
            for a in similar_alerts
            if a.timestamp >= recent_cutoff and a.title == alert.title
        ]

        # Don't spam similar alerts
        if len(recent_similar) >= 3:
            return False

        return True

    async def _send_enhanced_alert(self, alert: EnhancedAlertEvent):
        """Send enhanced alert through all configured channels."""
        # Convert to standard alert for compatibility
        standard_alert = alert.to_alert()

        # Send through all channels
        for channel in self.alert_channels:
            try:
                if hasattr(channel, "send_enhanced_alert"):
                    await channel.send_enhanced_alert(alert)
                else:
                    await channel.send_alert(standard_alert)
            except Exception as e:
                self.logger.error(f"Failed to send alert through channel: {e}")

        # Store in correlation tracking
        self.alert_correlation[alert.category.value].append(alert)

        # Clean up old correlation data
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        for category in self.alert_correlation:
            self.alert_correlation[category] = [
                a
                for a in self.alert_correlation[category]
                if a.timestamp >= cutoff_time
            ]

    async def _send_email_notification(self, alert: EnhancedAlertEvent):
        """Send email notification for enhanced alert."""
        # Implementation for email notifications
        pass

    async def _send_slack_notification(self, alert: EnhancedAlertEvent):
        """Send Slack notification for enhanced alert."""
        # Implementation for Slack notifications
        pass

    async def _send_webhook_notification(self, alert: EnhancedAlertEvent):
        """Send webhook notification for enhanced alert."""
        # Implementation for webhook notifications
        pass

    async def _send_pagerduty_notification(self, alert: EnhancedAlertEvent):
        """Send PagerDuty notification for enhanced alert."""
        # Implementation for PagerDuty notifications
        pass

    def get_enhanced_alert_history(self, hours: int = 24) -> List[EnhancedAlertEvent]:
        """Get enhanced alert history."""
        all_alerts = []
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        for category_alerts in self.alert_correlation.values():
            all_alerts.extend(
                [alert for alert in category_alerts if alert.timestamp >= cutoff_time]
            )

        return sorted(all_alerts, key=lambda x: x.timestamp, reverse=True)


# Enhanced factory function
def create_enhanced_ai_service_monitor(
    redis_url: str = "redis://localhost:6379",
    slack_webhook_url: str = None,
    email_config: Dict[str, Any] = None,
    pagerduty_key: str = None,
    webhook_url: str = None,
    custom_thresholds: List[MetricThreshold] = None,
    custom_error_patterns: List[ErrorPattern] = None,
) -> EnhancedAIServiceMonitor:
    """Factory function to create enhanced AI service monitor."""

    alert_channels = []

    # Add Slack channel if configured
    if slack_webhook_url:
        alert_channels.append(SlackAlertChannel(slack_webhook_url))

    # Add email channel if configured
    if email_config:
        alert_channels.append(
            EmailAlertChannel(
                smtp_config=email_config["smtp"], recipients=email_config["recipients"]
            )
        )

    # Add PagerDuty channel if configured
    if pagerduty_key:
        alert_channels.append(PagerDutyAlertChannel(pagerduty_key))

    # Add webhook channel if configured
    if webhook_url:
        alert_channels.append(EnhancedAlertChannel(webhook_url))

    return EnhancedAIServiceMonitor(
        redis_url=redis_url,
        alert_channels=alert_channels,
        thresholds=custom_thresholds,
        error_patterns=custom_error_patterns,
    )


# Smart Monitoring for Enhanced Features
class SmartFeatureMonitor:
    """Smart monitoring for enhanced authentication, retry logic, and circuit breakers."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.logger = logging.getLogger(__name__)
        self.redis_pool = None
        
        # Metrics for enhanced features
        self.retry_metrics = Counter(
            "ai_teddy_retry_attempts_total",
            "Total retry attempts",
            ["service", "endpoint", "attempt_number"]
        )
        
        self.circuit_breaker_metrics = Gauge(
            "ai_teddy_circuit_breaker_state",
            "Circuit breaker states (0=closed, 1=open, 2=half_open)",
            ["service", "provider"]
        )
        
        self.jwt_security_metrics = Counter(
            "ai_teddy_jwt_security_events_total",
            "JWT security events",
            ["event_type", "severity"]
        )
        
        self.device_tracking_metrics = Counter(
            "ai_teddy_device_tracking_events_total",
            "Device tracking events",
            ["event_type", "anomaly_type"]
        )
        
        self.audio_latency_metrics = Histogram(
            "ai_teddy_audio_processing_seconds",
            "Audio processing latency",
            ["provider", "retry_attempt"],
            buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        self.fallback_metrics = Counter(
            "ai_teddy_fallback_usage_total",
            "Fallback mechanism usage",
            ["service", "fallback_tier", "reason"]
        )
    
    async def monitor_retry_patterns(self, service: str, endpoint: str, attempts: int, success: bool):
        """Monitor retry patterns and detect anomalies."""
        self.retry_metrics.labels(
            service=service,
            endpoint=endpoint,
            attempt_number=str(attempts)
        ).inc()
        
        # Alert if retry rate is too high
        if attempts > 2:
            await self._alert_high_retry_rate(service, endpoint, attempts)
    
    async def monitor_circuit_breaker_state(self, service: str, provider: str, state: str):
        """Monitor circuit breaker state changes."""
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        self.circuit_breaker_metrics.labels(service=service, provider=provider).set(state_value)
        
        # Alert on circuit breaker trips
        if state == "open":
            await self._alert_circuit_breaker_trip(service, provider)
    
    async def monitor_jwt_security_event(self, event_type: str, severity: str, metadata: Dict[str, Any]):
        """Monitor JWT security events."""
        self.jwt_security_metrics.labels(event_type=event_type, severity=severity).inc()
        
        # Alert on security violations
        if severity in ["error", "critical"]:
            await self._alert_jwt_security_violation(event_type, severity, metadata)
    
    async def monitor_device_anomaly(self, anomaly_type: str, metadata: Dict[str, Any]):
        """Monitor device tracking anomalies."""
        self.device_tracking_metrics.labels(
            event_type="anomaly",
            anomaly_type=anomaly_type
        ).inc()
        
        # Alert on suspicious device behavior
        await self._alert_device_anomaly(anomaly_type, metadata)
    
    async def monitor_audio_latency(self, provider: str, retry_attempt: int, latency: float):
        """Monitor audio processing latency."""
        self.audio_latency_metrics.labels(
            provider=provider,
            retry_attempt=str(retry_attempt)
        ).observe(latency)
        
        # Alert if latency is too high
        if latency > 2.0:  # 2 seconds threshold
            await self._alert_high_audio_latency(provider, retry_attempt, latency)
    
    async def monitor_fallback_usage(self, service: str, fallback_tier: str, reason: str):
        """Monitor fallback mechanism usage."""
        self.fallback_metrics.labels(
            service=service,
            fallback_tier=fallback_tier,
            reason=reason
        ).inc()
        
        # Alert on emergency fallback usage
        if fallback_tier == "emergency":
            await self._alert_emergency_fallback_used(service, reason)
    
    async def _alert_high_retry_rate(self, service: str, endpoint: str, attempts: int):
        """Alert when retry rate is high."""
        alert = Alert(
            id=f"high_retry_{service}_{endpoint}_{int(time.time())}",
            severity=AlertSeverity.WARNING,
            metric_type=MetricType.RETRY_RATE,
            message=f"High retry rate detected: {service}/{endpoint} with {attempts} attempts",
            value=float(attempts),
            threshold=2.0,
            timestamp=datetime.utcnow(),
            service=service,
            metadata={
                "endpoint": endpoint,
                "attempts": attempts,
                "recommendation": "Check service health and network connectivity"
            }
        )
        
        # This would be sent through configured alert channels
        self.logger.warning(f"High retry rate alert: {alert.to_dict()}")
    
    async def _alert_circuit_breaker_trip(self, service: str, provider: str):
        """Alert when circuit breaker trips."""
        alert = Alert(
            id=f"circuit_breaker_trip_{service}_{provider}_{int(time.time())}",
            severity=AlertSeverity.ERROR,
            metric_type=MetricType.CIRCUIT_BREAKER_TRIPS,
            message=f"Circuit breaker OPEN: {service}/{provider}",
            value=1.0,
            threshold=1.0,
            timestamp=datetime.utcnow(),
            service=service,
            metadata={
                "provider": provider,
                "impact": "Service degradation possible",
                "recommendation": "Check provider health and consider manual intervention"
            }
        )
        
        self.logger.error(f"Circuit breaker trip alert: {alert.to_dict()}")
    
    async def _alert_jwt_security_violation(self, event_type: str, severity: str, metadata: Dict[str, Any]):
        """Alert on JWT security violations."""
        alert = Alert(
            id=f"jwt_security_{event_type}_{int(time.time())}",
            severity=AlertSeverity.CRITICAL if severity == "critical" else AlertSeverity.ERROR,
            metric_type=MetricType.JWT_TOKEN_FAILURES,
            message=f"JWT security violation: {event_type}",
            value=1.0,
            threshold=1.0,
            timestamp=datetime.utcnow(),
            service="authentication",
            metadata={
                "event_type": event_type,
                "severity": severity,
                "details": metadata,
                "recommendation": "Investigate for potential security breach"
            }
        )
        
        self.logger.critical(f"JWT security violation: {alert.to_dict()}")
    
    async def _alert_device_anomaly(self, anomaly_type: str, metadata: Dict[str, Any]):
        """Alert on device tracking anomalies."""
        alert = Alert(
            id=f"device_anomaly_{anomaly_type}_{int(time.time())}",
            severity=AlertSeverity.WARNING,
            metric_type=MetricType.DEVICE_TRACKING_ANOMALIES,
            message=f"Device tracking anomaly: {anomaly_type}",
            value=1.0,
            threshold=1.0,
            timestamp=datetime.utcnow(),
            service="device_tracking",
            metadata={
                "anomaly_type": anomaly_type,
                "details": metadata,
                "recommendation": "Review device behavior patterns"
            }
        )
        
        self.logger.warning(f"Device anomaly alert: {alert.to_dict()}")
    
    async def _alert_high_audio_latency(self, provider: str, retry_attempt: int, latency: float):
        """Alert on high audio processing latency."""
        alert = Alert(
            id=f"audio_latency_{provider}_{int(time.time())}",
            severity=AlertSeverity.WARNING,
            metric_type=MetricType.AUDIO_PROCESSING_LATENCY,
            message=f"High audio latency: {provider} took {latency:.2f}s",
            value=latency,
            threshold=2.0,
            timestamp=datetime.utcnow(),
            service="audio_processing",
            metadata={
                "provider": provider,
                "retry_attempt": retry_attempt,
                "latency": latency,
                "recommendation": "Check audio provider performance"
            }
        )
        
        self.logger.warning(f"High audio latency alert: {alert.to_dict()}")
    
    async def _alert_emergency_fallback_used(self, service: str, reason: str):
        """Alert when emergency fallback is used."""
        alert = Alert(
            id=f"emergency_fallback_{service}_{int(time.time())}",
            severity=AlertSeverity.CRITICAL,
            metric_type=MetricType.FALLBACK_USAGE,
            message=f"Emergency fallback used: {service}",
            value=1.0,
            threshold=1.0,
            timestamp=datetime.utcnow(),
            service=service,
            metadata={
                "reason": reason,
                "impact": "Service running on emergency fallback",
                "recommendation": "Immediate attention required - restore primary service"
            }
        )
        
        self.logger.critical(f"Emergency fallback alert: {alert.to_dict()}")
    
    async def get_smart_monitoring_dashboard(self) -> Dict[str, Any]:
        """Get smart monitoring dashboard data."""
        return {
            "retry_patterns": {
                "total_retries_last_hour": await self._get_retry_count_last_hour(),
                "high_retry_services": await self._get_high_retry_services(),
            },
            "circuit_breakers": {
                "open_breakers": await self._get_open_circuit_breakers(),
                "trip_count_today": await self._get_circuit_breaker_trips_today(),
            },
            "security": {
                "jwt_violations_today": await self._get_jwt_violations_today(),
                "device_anomalies_today": await self._get_device_anomalies_today(),
            },
            "audio_performance": {
                "p95_latency": await self._get_audio_p95_latency(),
                "provider_comparison": await self._get_audio_provider_comparison(),
            },
            "fallback_usage": {
                "emergency_fallbacks_today": await self._get_emergency_fallbacks_today(),
                "fallback_by_tier": await self._get_fallback_usage_by_tier(),
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _get_retry_count_last_hour(self) -> int:
        """Get retry count for last hour."""
        # Implementation would query Prometheus/Redis
        return 0
    
    async def _get_high_retry_services(self) -> List[str]:
        """Get services with high retry rates."""
        return []
    
    async def _get_open_circuit_breakers(self) -> List[Dict[str, str]]:
        """Get currently open circuit breakers."""
        return []
    
    async def _get_circuit_breaker_trips_today(self) -> int:
        """Get circuit breaker trips today."""
        return 0
    
    async def _get_jwt_violations_today(self) -> int:
        """Get JWT violations today."""
        return 0
    
    async def _get_device_anomalies_today(self) -> int:
        """Get device anomalies today."""
        return 0
    
    async def _get_audio_p95_latency(self) -> float:
        """Get P95 audio latency."""
        return 0.0
    
    async def _get_audio_provider_comparison(self) -> Dict[str, float]:
        """Get audio provider performance comparison."""
        return {}
    
    async def _get_emergency_fallbacks_today(self) -> int:
        """Get emergency fallback usage today."""
        return 0
    
    async def _get_fallback_usage_by_tier(self) -> Dict[str, int]:
        """Get fallback usage by tier."""
        return {}


# Global smart feature monitor instance
smart_monitor = SmartFeatureMonitor()
