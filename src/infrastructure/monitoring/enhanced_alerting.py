"""
>� AI TEDDY BEAR V5 - ENHANCED ALERTING SYSTEM
===============================================
Production-ready alerting system with multiple notification channels,
Sentry integration, and child safety specific alerts.
"""

import asyncio
import json
import os
import smtplib
import time
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from urllib.parse import urljoin
import hashlib
from uuid import uuid4

try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.asyncio import AsyncioIntegration

    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        CollectorRegistry,
        push_to_gateway,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class AlertSeverity(Enum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    CHILD_SAFETY_CRITICAL = "child_safety_critical"


class AlertCategory(Enum):
    """Alert categories for better organization."""

    SYSTEM = "system"
    SECURITY = "security"
    CHILD_SAFETY = "child_safety"
    COPPA_COMPLIANCE = "coppa_compliance"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    API = "api"
    AUTHENTICATION = "authentication"
    CONTENT_MODERATION = "content_moderation"


class NotificationChannel(Enum):
    """Available notification channels."""

    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"
    SMS = "sms"
    DISCORD = "discord"
    MICROSOFT_TEAMS = "microsoft_teams"


@dataclass
class Alert:
    """Structured alert data."""

    id: str
    timestamp: str
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    source: str
    environment: str
    correlation_id: Optional[str] = None
    child_id: Optional[str] = None
    parent_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    tags: Optional[List[str]] = None
    fingerprint: Optional[str] = None
    count: int = 1
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    def __post_init__(self):
        """Generate fingerprint for alert deduplication."""
        if not self.fingerprint:
            data = f"{self.category.value}:{self.title}:{self.source}"
            self.fingerprint = hashlib.md5(data.encode()).hexdigest()

        if not self.first_seen:
            self.first_seen = self.timestamp
        self.last_seen = self.timestamp


@dataclass
class NotificationConfig:
    """Configuration for notification channels."""

    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = None
    severity_filter: List[AlertSeverity] = None
    category_filter: List[AlertCategory] = None
    rate_limit_seconds: int = 300  # 5 minutes default
    max_alerts_per_hour: int = 20


class AlertManager:
    """Main alert management system."""

    def __init__(self, environment: str = "production"):
        self.environment = environment
        self.logger = logging.getLogger(__name__)

        # Alert storage and tracking
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.last_notification_times: Dict[str, Dict[str, float]] = {}
        self.notification_counts: Dict[str, Dict[str, int]] = {}

        # Notification channels
        self.notification_configs: Dict[NotificationChannel, NotificationConfig] = {}

        # Metrics (if Prometheus available)
        if PROMETHEUS_AVAILABLE:
            from src.infrastructure.monitoring.metrics_registry import (
                get_metrics_registry,
            )

            self.registry = get_metrics_registry()
            self.alert_counter = self.registry.get_counter(
                "alert_total",
                "Total number of alerts triggered",
            )
            self.alert_duration = self.registry.get_histogram(
                "alert_duration_seconds",
                "Duration of alert processing in seconds",
                buckets=[0.1, 0.5, 1, 2.5, 5, 10],
            )
            self.active_alert_gauge = self.registry.get_gauge(
                "active_alerts", "Current number of active alerts"
            )

        # Initialize Sentry if available
        self._setup_sentry()

        # Load configuration
        self._load_configuration()

        # Start background tasks
        self._start_background_tasks()

    def _setup_sentry(self):
        """Initialize Sentry integration."""
        if not SENTRY_AVAILABLE:
            self.logger.warning("Sentry not available for enhanced error tracking")
            return

        sentry_dsn = os.getenv("SENTRY_DSN")
        if not sentry_dsn:
            self.logger.warning("SENTRY_DSN not configured")
            return

        # Configure Sentry with production settings
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=self.environment,
            traces_sample_rate=1.0 if self.environment == "development" else 0.1,
            profiles_sample_rate=1.0 if self.environment == "development" else 0.1,
            integrations=[
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                AsyncioIntegration(),
            ],
            # Child safety specific configuration
            before_send=self._sentry_before_send,
            before_send_transaction=self._sentry_before_send_transaction,
            max_breadcrumbs=50,
            attach_stacktrace=True,
            send_default_pii=False,  # Critical for child safety compliance
            in_app_include=["src"],
            release=os.getenv("APP_VERSION", "unknown"),
            server_name=os.getenv("INSTANCE_ID", "unknown"),
        )

        self.logger.info("Sentry integration initialized")

    def _sentry_before_send(self, event, hint):
        """Filter sensitive data before sending to Sentry."""
        # Remove any child-related PII
        sensitive_keys = {
            "child_name",
            "child_id",
            "child_age",
            "parent_name",
            "parent_email",
            "guardian_email",
            "phone",
            "address",
            "school",
            "location",
            "ip_address",
            "device_id",
            "session_token",
        }

        def clean_data(data):
            if isinstance(data, dict):
                return {
                    key: (
                        "[REDACTED]"
                        if any(sensitive in key.lower() for sensitive in sensitive_keys)
                        else clean_data(value)
                    )
                    for key, value in data.items()
                }
            elif isinstance(data, (list, tuple)):
                return [clean_data(item) for item in data]
            return data

        # Clean event data
        if "extra" in event:
            event["extra"] = clean_data(event["extra"])
        if "contexts" in event:
            event["contexts"] = clean_data(event["contexts"])

        return event

    def _sentry_before_send_transaction(self, event, hint):
        """Filter transaction data for Sentry."""
        return self._sentry_before_send(event, hint)

    def _load_configuration(self):
        """Load notification channel configurations."""
        # Email configuration
        if os.getenv("SMTP_HOST"):
            self.notification_configs[NotificationChannel.EMAIL] = NotificationConfig(
                channel=NotificationChannel.EMAIL,
                config={
                    "smtp_host": os.getenv("SMTP_HOST"),
                    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
                    "smtp_username": os.getenv("SMTP_USERNAME"),
                    "smtp_password": os.getenv("SMTP_PASSWORD"),
                    "from_email": os.getenv(
                        "ALERT_FROM_EMAIL", "alerts@aiteddybear.com"
                    ),
                    "to_emails": os.getenv("ALERT_TO_EMAILS", "").split(","),
                    "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
                },
                severity_filter=[
                    AlertSeverity.HIGH,
                    AlertSeverity.CRITICAL,
                    AlertSeverity.CHILD_SAFETY_CRITICAL,
                ],
            )

        # Slack configuration
        if os.getenv("SLACK_WEBHOOK_URL"):
            self.notification_configs[NotificationChannel.SLACK] = NotificationConfig(
                channel=NotificationChannel.SLACK,
                config={
                    "webhook_url": os.getenv("SLACK_WEBHOOK_URL"),
                    "channel": os.getenv("SLACK_CHANNEL", "#alerts"),
                    "username": os.getenv("SLACK_USERNAME", "AI Teddy Bear Alerts"),
                },
                severity_filter=[
                    AlertSeverity.MEDIUM,
                    AlertSeverity.HIGH,
                    AlertSeverity.CRITICAL,
                    AlertSeverity.CHILD_SAFETY_CRITICAL,
                ],
            )

        # PagerDuty configuration
        if os.getenv("PAGERDUTY_INTEGRATION_KEY"):
            self.notification_configs[NotificationChannel.PAGERDUTY] = (
                NotificationConfig(
                    channel=NotificationChannel.PAGERDUTY,
                    config={
                        "integration_key": os.getenv("PAGERDUTY_INTEGRATION_KEY"),
                        "service_name": os.getenv(
                            "PAGERDUTY_SERVICE_NAME", "AI Teddy Bear"
                        ),
                    },
                    severity_filter=[
                        AlertSeverity.CRITICAL,
                        AlertSeverity.CHILD_SAFETY_CRITICAL,
                    ],
                )
            )

        # Discord configuration
        if os.getenv("DISCORD_WEBHOOK_URL"):
            self.notification_configs[NotificationChannel.DISCORD] = NotificationConfig(
                channel=NotificationChannel.DISCORD,
                config={
                    "webhook_url": os.getenv("DISCORD_WEBHOOK_URL"),
                    "username": os.getenv("DISCORD_USERNAME", "AI Teddy Bear Alerts"),
                },
                severity_filter=[
                    AlertSeverity.HIGH,
                    AlertSeverity.CRITICAL,
                    AlertSeverity.CHILD_SAFETY_CRITICAL,
                ],
            )

        # Microsoft Teams configuration
        if os.getenv("TEAMS_WEBHOOK_URL"):
            self.notification_configs[NotificationChannel.MICROSOFT_TEAMS] = (
                NotificationConfig(
                    channel=NotificationChannel.MICROSOFT_TEAMS,
                    config={"webhook_url": os.getenv("TEAMS_WEBHOOK_URL")},
                    severity_filter=[
                        AlertSeverity.HIGH,
                        AlertSeverity.CRITICAL,
                        AlertSeverity.CHILD_SAFETY_CRITICAL,
                    ],
                )
            )

    def _start_background_tasks(self):
        """Start background maintenance tasks."""
        # Start alert cleanup task
        asyncio.create_task(self._cleanup_old_alerts())

        # Start metrics reporting task
        if PROMETHEUS_AVAILABLE:
            asyncio.create_task(self._report_metrics())

    async def _cleanup_old_alerts(self):
        """Clean up old resolved alerts."""
        while True:
            try:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                cutoff_str = cutoff_time.isoformat()

                # Remove old resolved alerts from history
                self.alert_history = [
                    alert
                    for alert in self.alert_history
                    if not alert.resolved
                    or (alert.resolved_at and alert.resolved_at > cutoff_str)
                ]

                # Clean up notification tracking
                current_time = time.time()
                for fingerprint in list(self.last_notification_times.keys()):
                    for channel in list(
                        self.last_notification_times[fingerprint].keys()
                    ):
                        if (
                            current_time
                            - self.last_notification_times[fingerprint][channel]
                            > 3600
                        ):  # 1 hour
                            del self.last_notification_times[fingerprint][channel]

                    if not self.last_notification_times[fingerprint]:
                        del self.last_notification_times[fingerprint]

                # Reset hourly notification counts
                for fingerprint in list(self.notification_counts.keys()):
                    for channel in list(self.notification_counts[fingerprint].keys()):
                        if (
                            current_time
                            - self.last_notification_times.get(fingerprint, {}).get(
                                channel, 0
                            )
                            > 3600
                        ):
                            self.notification_counts[fingerprint][channel] = 0

                await asyncio.sleep(300)  # Run every 5 minutes

            except Exception as e:
                self.logger.error(f"Error in alert cleanup: {e}")
                await asyncio.sleep(300)

    async def _report_metrics(self):
        """Report metrics to Prometheus if configured."""
        if not PROMETHEUS_AVAILABLE:
            return

        prometheus_gateway = os.getenv("PROMETHEUS_PUSHGATEWAY")
        if not prometheus_gateway:
            return

        while True:
            try:
                # Update active alert gauge
                self.active_alert_gauge.clear()
                for alert in self.active_alerts.values():
                    if not alert.resolved:
                        self.active_alert_gauge.labels(
                            severity=alert.severity.value, category=alert.category.value
                        ).inc()

                # Push metrics to gateway
                push_to_gateway(
                    prometheus_gateway,
                    job="ai-teddy-bear-alerts",
                    registry=self.registry,
                )

                await asyncio.sleep(60)  # Report every minute

            except Exception as e:
                self.logger.error(f"Error reporting metrics: {e}")
                await asyncio.sleep(60)

    async def create_alert(
        self,
        severity: AlertSeverity,
        category: AlertCategory,
        title: str,
        message: str,
        source: str,
        correlation_id: Optional[str] = None,
        child_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Alert:
        """Create and process a new alert."""

        alert = Alert(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            severity=severity,
            category=category,
            title=title,
            message=message,
            source=source,
            environment=self.environment,
            correlation_id=correlation_id,
            child_id=child_id,
            parent_id=parent_id,
            session_id=session_id,
            metadata=metadata or {},
            tags=tags or [],
        )

        # Check for existing alert with same fingerprint
        existing_alert = self.active_alerts.get(alert.fingerprint)
        if existing_alert and not existing_alert.resolved:
            # Update existing alert
            existing_alert.count += 1
            existing_alert.last_seen = alert.timestamp
            existing_alert.metadata.update(alert.metadata)
            alert = existing_alert
        else:
            # New alert
            self.active_alerts[alert.fingerprint] = alert
            self.alert_history.append(alert)

        # Log alert
        self.logger.log(
            (
                logging.CRITICAL
                if severity
                in [AlertSeverity.CRITICAL, AlertSeverity.CHILD_SAFETY_CRITICAL]
                else (
                    logging.ERROR if severity == AlertSeverity.HIGH else logging.WARNING
                )
            ),
            f"Alert created: {title}",
            extra={
                "alert_id": alert.id,
                "severity": severity.value,
                "category": category.value,
                "fingerprint": alert.fingerprint,
                "correlation_id": correlation_id,
                "metadata": metadata,
            },
        )

        # Update metrics
        if PROMETHEUS_AVAILABLE:
            self.alert_counter.labels(
                severity=severity.value,
                category=category.value,
                environment=self.environment,
            ).inc()

        # Send to Sentry for critical alerts
        if SENTRY_AVAILABLE and severity in [
            AlertSeverity.CRITICAL,
            AlertSeverity.CHILD_SAFETY_CRITICAL,
        ]:
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("alert_category", category.value)
                scope.set_tag("alert_severity", severity.value)
                scope.set_context("alert", asdict(alert))
                if correlation_id:
                    scope.set_tag("correlation_id", correlation_id)

                sentry_sdk.capture_message(
                    f"Critical Alert: {title}",
                    level="error" if severity == AlertSeverity.CRITICAL else "fatal",
                )

        # Send notifications
        await self._send_notifications(alert)

        return alert

    async def resolve_alert(
        self, fingerprint: str, resolved_by: str = "system"
    ) -> bool:
        """Resolve an active alert."""
        alert = self.active_alerts.get(fingerprint)
        if not alert or alert.resolved:
            return False

        alert.resolved = True
        alert.resolved_at = datetime.now(timezone.utc).isoformat()
        alert.resolved_by = resolved_by

        # Update metrics
        if PROMETHEUS_AVAILABLE:
            # Calculate resolution time
            start_time = datetime.fromisoformat(alert.timestamp.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(alert.resolved_at.replace("Z", "+00:00"))
            duration = (end_time - start_time).total_seconds()

            self.alert_duration.labels(
                severity=alert.severity.value, category=alert.category.value
            ).observe(duration)

        # Log resolution
        self.logger.info(
            f"Alert resolved: {alert.title}",
            extra={
                "alert_id": alert.id,
                "fingerprint": fingerprint,
                "resolved_by": resolved_by,
                "duration_seconds": duration if PROMETHEUS_AVAILABLE else None,
            },
        )

        # Send resolution notification for critical alerts
        if alert.severity in [
            AlertSeverity.CRITICAL,
            AlertSeverity.CHILD_SAFETY_CRITICAL,
        ]:
            await self._send_resolution_notification(alert)

        return True

    async def _send_notifications(self, alert: Alert):
        """Send alert notifications through configured channels."""
        tasks = []

        for channel, config in self.notification_configs.items():
            if not config.enabled:
                continue

            # Check severity filter
            if config.severity_filter and alert.severity not in config.severity_filter:
                continue

            # Check category filter
            if config.category_filter and alert.category not in config.category_filter:
                continue

            # Check rate limiting
            if self._is_rate_limited(alert.fingerprint, channel, config):
                continue

            # Create notification task
            task = asyncio.create_task(self._send_notification(alert, channel, config))
            tasks.append(task)

        # Wait for all notifications to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _is_rate_limited(
        self, fingerprint: str, channel: NotificationChannel, config: NotificationConfig
    ) -> bool:
        """Check if notifications are rate limited."""
        current_time = time.time()

        # Check time-based rate limiting
        if fingerprint in self.last_notification_times:
            if channel.value in self.last_notification_times[fingerprint]:
                last_time = self.last_notification_times[fingerprint][channel.value]
                if current_time - last_time < config.rate_limit_seconds:
                    return True

        # Check count-based rate limiting
        if fingerprint in self.notification_counts:
            if channel.value in self.notification_counts[fingerprint]:
                count = self.notification_counts[fingerprint][channel.value]
                if count >= config.max_alerts_per_hour:
                    return True

        return False

    def _update_rate_limit_tracking(
        self, fingerprint: str, channel: NotificationChannel
    ):
        """Update rate limiting tracking."""
        current_time = time.time()

        # Update last notification time
        if fingerprint not in self.last_notification_times:
            self.last_notification_times[fingerprint] = {}
        self.last_notification_times[fingerprint][channel.value] = current_time

        # Update notification count
        if fingerprint not in self.notification_counts:
            self.notification_counts[fingerprint] = {}
        if channel.value not in self.notification_counts[fingerprint]:
            self.notification_counts[fingerprint][channel.value] = 0
        self.notification_counts[fingerprint][channel.value] += 1

    async def _send_notification(
        self, alert: Alert, channel: NotificationChannel, config: NotificationConfig
    ):
        """Send notification through specific channel."""
        try:
            if channel == NotificationChannel.EMAIL:
                await self._send_email_notification(alert, config)
            elif channel == NotificationChannel.SLACK:
                await self._send_slack_notification(alert, config)
            elif channel == NotificationChannel.PAGERDUTY:
                await self._send_pagerduty_notification(alert, config)
            elif channel == NotificationChannel.DISCORD:
                await self._send_discord_notification(alert, config)
            elif channel == NotificationChannel.MICROSOFT_TEAMS:
                await self._send_teams_notification(alert, config)

            # Update rate limiting
            self._update_rate_limit_tracking(alert.fingerprint, channel)

            self.logger.info(
                f"Notification sent via {channel.value}",
                extra={"alert_id": alert.id, "channel": channel.value},
            )

        except Exception as e:
            self.logger.error(
                f"Failed to send notification via {channel.value}: {e}",
                extra={"alert_id": alert.id, "channel": channel.value, "error": str(e)},
            )

    async def _send_email_notification(self, alert: Alert, config: NotificationConfig):
        """Send email notification."""
        if not config.config.get("to_emails"):
            return

        # Create email message
        msg = MIMEMultipart()
        msg["From"] = config.config["from_email"]
        msg["To"] = ", ".join(config.config["to_emails"])
        msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"

        # Email body
        body = f"""
        Alert Details:
        
        Severity: {alert.severity.value.upper()}
        Category: {alert.category.value}
        Environment: {alert.environment}
        Time: {alert.timestamp}
        Source: {alert.source}
        
        Message:
        {alert.message}
        
        Correlation ID: {alert.correlation_id or 'N/A'}
        Alert Count: {alert.count}
        
        Metadata:
        {json.dumps(alert.metadata, indent=2) if alert.metadata else 'None'}
        
        ---
        AI Teddy Bear Alert System
        """

        msg.attach(MIMEText(body, "plain"))

        # Send email
        with smtplib.SMTP(
            config.config["smtp_host"], config.config["smtp_port"]
        ) as server:
            if config.config.get("use_tls", True):
                server.starttls()
            if config.config.get("smtp_username"):
                server.login(
                    config.config["smtp_username"], config.config["smtp_password"]
                )

            server.send_message(msg)

    async def _send_slack_notification(self, alert: Alert, config: NotificationConfig):
        """Send Slack notification."""
        if not REQUESTS_AVAILABLE:
            raise Exception("requests library not available")

        # Color coding based on severity
        color_map = {
            AlertSeverity.LOW: "#36a64f",
            AlertSeverity.MEDIUM: "#ff9500",
            AlertSeverity.HIGH: "#ff0000",
            AlertSeverity.CRITICAL: "#8B0000",
            AlertSeverity.CHILD_SAFETY_CRITICAL: "#FF1493",
        }

        payload = {
            "channel": config.config.get("channel", "#alerts"),
            "username": config.config.get("username", "AI Teddy Bear Alerts"),
            "attachments": [
                {
                    "color": color_map.get(alert.severity, "#ff0000"),
                    "title": f"{alert.severity.value.upper()}: {alert.title}",
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Environment",
                            "value": alert.environment,
                            "short": True,
                        },
                        {
                            "title": "Category",
                            "value": alert.category.value,
                            "short": True,
                        },
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Count", "value": str(alert.count), "short": True},
                        {
                            "title": "Correlation ID",
                            "value": alert.correlation_id or "N/A",
                            "short": True,
                        },
                        {"title": "Time", "value": alert.timestamp, "short": True},
                    ],
                    "footer": "AI Teddy Bear Alert System",
                    "ts": int(
                        datetime.fromisoformat(
                            alert.timestamp.replace("Z", "+00:00")
                        ).timestamp()
                    ),
                }
            ],
        }

        response = requests.post(config.config["webhook_url"], json=payload, timeout=10)
        response.raise_for_status()

    async def _send_pagerduty_notification(
        self, alert: Alert, config: NotificationConfig
    ):
        """Send PagerDuty notification."""
        if not REQUESTS_AVAILABLE:
            raise Exception("requests library not available")

        payload = {
            "routing_key": config.config["integration_key"],
            "event_action": "trigger",
            "dedup_key": alert.fingerprint,
            "payload": {
                "summary": f"{alert.severity.value.upper()}: {alert.title}",
                "source": alert.source,
                "severity": (
                    "critical"
                    if alert.severity
                    in [AlertSeverity.CRITICAL, AlertSeverity.CHILD_SAFETY_CRITICAL]
                    else "error"
                ),
                "component": alert.category.value,
                "group": alert.environment,
                "class": "alert",
                "custom_details": {
                    "message": alert.message,
                    "correlation_id": alert.correlation_id,
                    "count": alert.count,
                    "metadata": alert.metadata,
                },
            },
        }

        response = requests.post(
            "https://events.pagerduty.com/v2/enqueue", json=payload, timeout=10
        )
        response.raise_for_status()

    async def _send_discord_notification(
        self, alert: Alert, config: NotificationConfig
    ):
        """Send Discord notification."""
        if not REQUESTS_AVAILABLE:
            raise Exception("requests library not available")

        # Color coding based on severity
        color_map = {
            AlertSeverity.LOW: 0x36A64F,
            AlertSeverity.MEDIUM: 0xFF9500,
            AlertSeverity.HIGH: 0xFF0000,
            AlertSeverity.CRITICAL: 0x8B0000,
            AlertSeverity.CHILD_SAFETY_CRITICAL: 0xFF1493,
        }

        payload = {
            "username": config.config.get("username", "AI Teddy Bear Alerts"),
            "embeds": [
                {
                    "title": f"{alert.severity.value.upper()}: {alert.title}",
                    "description": alert.message,
                    "color": color_map.get(alert.severity, 0xFF0000),
                    "fields": [
                        {
                            "name": "Environment",
                            "value": alert.environment,
                            "inline": True,
                        },
                        {
                            "name": "Category",
                            "value": alert.category.value,
                            "inline": True,
                        },
                        {"name": "Source", "value": alert.source, "inline": True},
                        {"name": "Count", "value": str(alert.count), "inline": True},
                        {
                            "name": "Correlation ID",
                            "value": alert.correlation_id or "N/A",
                            "inline": True,
                        },
                    ],
                    "timestamp": alert.timestamp,
                    "footer": {"text": "AI Teddy Bear Alert System"},
                }
            ],
        }

        response = requests.post(config.config["webhook_url"], json=payload, timeout=10)
        response.raise_for_status()

    async def _send_teams_notification(self, alert: Alert, config: NotificationConfig):
        """Send Microsoft Teams notification."""
        if not REQUESTS_AVAILABLE:
            raise Exception("requests library not available")

        # Color coding based on severity
        color_map = {
            AlertSeverity.LOW: "Good",
            AlertSeverity.MEDIUM: "Warning",
            AlertSeverity.HIGH: "Attention",
            AlertSeverity.CRITICAL: "Attention",
            AlertSeverity.CHILD_SAFETY_CRITICAL: "Attention",
        }

        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"{alert.severity.value.upper()}: {alert.title}",
            "themeColor": color_map.get(alert.severity, "Attention"),
            "sections": [
                {
                    "activityTitle": f"{alert.severity.value.upper()}: {alert.title}",
                    "activitySubtitle": alert.message,
                    "facts": [
                        {"name": "Environment", "value": alert.environment},
                        {"name": "Category", "value": alert.category.value},
                        {"name": "Source", "value": alert.source},
                        {"name": "Count", "value": str(alert.count)},
                        {
                            "name": "Correlation ID",
                            "value": alert.correlation_id or "N/A",
                        },
                        {"name": "Time", "value": alert.timestamp},
                    ],
                }
            ],
        }

        response = requests.post(config.config["webhook_url"], json=payload, timeout=10)
        response.raise_for_status()

    async def _send_resolution_notification(self, alert: Alert):
        """Send alert resolution notification."""
        resolution_alert = Alert(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            severity=AlertSeverity.LOW,
            category=alert.category,
            title=f"RESOLVED: {alert.title}",
            message=f"Alert has been resolved by {alert.resolved_by}",
            source=alert.source,
            environment=alert.environment,
            correlation_id=alert.correlation_id,
            metadata={"original_alert_id": alert.id, "resolved_by": alert.resolved_by},
        )

        await self._send_notifications(resolution_alert)

    def get_active_alerts(
        self,
        category: Optional[AlertCategory] = None,
        severity: Optional[AlertSeverity] = None,
    ) -> List[Alert]:
        """Get active alerts with optional filtering."""
        alerts = [alert for alert in self.active_alerts.values() if not alert.resolved]

        if category:
            alerts = [alert for alert in alerts if alert.category == category]

        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]

        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)

    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        active_alerts = [
            alert for alert in self.active_alerts.values() if not alert.resolved
        ]

        stats = {
            "active_alerts": len(active_alerts),
            "total_alerts_24h": len(
                [
                    alert
                    for alert in self.alert_history
                    if datetime.fromisoformat(alert.timestamp.replace("Z", "+00:00"))
                    > datetime.now(timezone.utc) - timedelta(hours=24)
                ]
            ),
            "by_severity": {},
            "by_category": {},
            "top_sources": {},
        }

        # Count by severity
        for severity in AlertSeverity:
            count = len(
                [alert for alert in active_alerts if alert.severity == severity]
            )
            if count > 0:
                stats["by_severity"][severity.value] = count

        # Count by category
        for category in AlertCategory:
            count = len(
                [alert for alert in active_alerts if alert.category == category]
            )
            if count > 0:
                stats["by_category"][category.value] = count

        # Top sources
        source_counts = {}
        for alert in active_alerts:
            source_counts[alert.source] = source_counts.get(alert.source, 0) + 1

        stats["top_sources"] = dict(
            sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        return stats


# Global alert manager instance
alert_manager = AlertManager(environment=os.getenv("ENVIRONMENT", "production"))


# Convenience functions for common alert types
async def alert_child_safety_violation(
    title: str,
    message: str,
    child_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    violation_type: Optional[str] = None,
    content: Optional[str] = None,
    **kwargs,
) -> Alert:
    """Create child safety violation alert."""
    metadata = kwargs.get("metadata", {})
    metadata.update(
        {
            "violation_type": violation_type,
            "content_flagged": (
                content[:100] if content else None
            ),  # First 100 chars only
        }
    )

    return await alert_manager.create_alert(
        severity=AlertSeverity.CHILD_SAFETY_CRITICAL,
        category=AlertCategory.CHILD_SAFETY,
        title=title,
        message=message,
        source="child_safety_monitor",
        child_id=child_id,
        parent_id=parent_id,
        session_id=session_id,
        metadata=metadata,
        tags=["child_safety", "violation"],
        **kwargs,
    )


async def alert_coppa_violation(
    title: str,
    message: str,
    child_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    violation_details: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Alert:
    """Create COPPA compliance violation alert."""
    metadata = kwargs.get("metadata", {})
    metadata.update(
        {"compliance_framework": "COPPA", "violation_details": violation_details}
    )

    return await alert_manager.create_alert(
        severity=AlertSeverity.CRITICAL,
        category=AlertCategory.COPPA_COMPLIANCE,
        title=title,
        message=message,
        source="coppa_monitor",
        child_id=child_id,
        parent_id=parent_id,
        metadata=metadata,
        tags=["coppa", "compliance", "violation"],
        **kwargs,
    )


async def alert_security_incident(
    title: str,
    message: str,
    incident_type: str,
    severity: AlertSeverity = AlertSeverity.HIGH,
    source_ip: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs,
) -> Alert:
    """Create security incident alert."""
    metadata = kwargs.get("metadata", {})
    metadata.update(
        {"incident_type": incident_type, "source_ip": source_ip, "user_id": user_id}
    )

    return await alert_manager.create_alert(
        severity=severity,
        category=AlertCategory.SECURITY,
        title=title,
        message=message,
        source="security_monitor",
        metadata=metadata,
        tags=["security", "incident", incident_type],
        **kwargs,
    )


async def alert_system_error(
    title: str,
    message: str,
    error: Optional[Exception] = None,
    component: Optional[str] = None,
    **kwargs,
) -> Alert:
    """Create system error alert."""
    metadata = kwargs.get("metadata", {})
    if error:
        metadata.update(
            {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "component": component,
            }
        )

    return await alert_manager.create_alert(
        severity=AlertSeverity.HIGH,
        category=AlertCategory.SYSTEM,
        title=title,
        message=message,
        source=component or "system",
        metadata=metadata,
        tags=["system", "error"],
        **kwargs,
    )


async def alert_performance_issue(
    title: str,
    message: str,
    metric_name: str,
    metric_value: float,
    threshold: float,
    **kwargs,
) -> Alert:
    """Create performance issue alert."""
    metadata = kwargs.get("metadata", {})
    metadata.update(
        {
            "metric_name": metric_name,
            "metric_value": metric_value,
            "threshold": threshold,
            "deviation_percent": ((metric_value - threshold) / threshold) * 100,
        }
    )

    severity = (
        AlertSeverity.CRITICAL if metric_value > threshold * 2 else AlertSeverity.HIGH
    )

    return await alert_manager.create_alert(
        severity=severity,
        category=AlertCategory.PERFORMANCE,
        title=title,
        message=message,
        source="performance_monitor",
        metadata=metadata,
        tags=["performance", metric_name],
        **kwargs,
    )
