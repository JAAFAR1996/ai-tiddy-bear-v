"""
Backup Monitoring and Alerting Service for AI Teddy Bear Application

Provides comprehensive monitoring for:
- Backup success/failure notifications
- Storage usage monitoring
- COPPA compliance reporting
- Performance metrics tracking
- SLA monitoring (RTO/RPO)
- Automated alerting and escalation
"""

import asyncio
import logging
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from typing import Dict, List, Optional, Set, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import requests

from ..monitoring.prometheus_metrics import PrometheusMetricsCollector


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertChannel(Enum):
    """Alert delivery channels"""
    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"
    SMS = "sms"


class ComplianceStatus(Enum):
    """COPPA compliance status"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"
    UNKNOWN = "unknown"


@dataclass
class Alert:
    """Alert definition"""
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    timestamp: datetime
    component: str  # database, files, config, system
    metrics: Dict[str, Any]
    resolved: bool = False
    acknowledged: bool = False
    escalated: bool = False


@dataclass
class BackupMetrics:
    """Backup operation metrics"""
    backup_id: str
    backup_type: str
    component: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: float
    size_bytes: int
    success: bool
    throughput_mbps: float
    compression_ratio: float
    encryption_enabled: bool
    coppa_compliant: bool
    error_message: Optional[str] = None


@dataclass
class StorageMetrics:
    """Storage usage metrics"""
    provider: str
    total_space_bytes: int
    used_space_bytes: int
    available_space_bytes: int
    backup_count: int
    oldest_backup_date: datetime
    newest_backup_date: datetime
    growth_rate_mb_per_day: float
    projected_full_date: Optional[datetime]


@dataclass
class ComplianceReport:
    """COPPA compliance report"""
    report_id: str
    timestamp: datetime
    period_start: datetime
    period_end: datetime
    total_backups: int
    compliant_backups: int
    non_compliant_backups: int
    compliance_rate: float
    issues: List[str]
    recommendations: List[str]
    status: ComplianceStatus


@dataclass
class SLAMetrics:
    """Service Level Agreement metrics"""
    rto_target_minutes: int  # Recovery Time Objective
    rpo_target_minutes: int  # Recovery Point Objective
    rto_actual_minutes: Optional[int]
    rpo_actual_minutes: Optional[int]
    rto_breaches_count: int
    rpo_breaches_count: int
    availability_percentage: float
    mttr_minutes: float  # Mean Time To Recovery
    mtbf_hours: float   # Mean Time Between Failures


class BackupMonitoringService:
    """
    Comprehensive monitoring service for backup operations
    with alerting, compliance tracking, and performance monitoring.
    """

    def __init__(self,
                 metrics_collector: PrometheusMetricsCollector,
                 alert_config: Dict[str, Any],
                 notification_config: Dict[str, Any]):
        self.metrics_collector = metrics_collector
        self.alert_config = alert_config
        self.notification_config = notification_config
        
        self.logger = logging.getLogger(__name__)
        
        # Active alerts
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        
        # Metrics storage
        self.backup_metrics: List[BackupMetrics] = []
        self.storage_metrics: Dict[str, StorageMetrics] = {}
        
        # Compliance tracking
        self.compliance_reports: List[ComplianceReport] = []
        
        # SLA tracking
        self.sla_metrics = SLAMetrics(
            rto_target_minutes=120,  # 2 hours
            rpo_target_minutes=15,   # 15 minutes
            rto_actual_minutes=None,
            rpo_actual_minutes=None,
            rto_breaches_count=0,
            rpo_breaches_count=0,
            availability_percentage=99.9,
            mttr_minutes=0.0,
            mtbf_hours=0.0
        )
        
        # Initialize alert thresholds
        self.alert_thresholds = {
            'backup_failure_rate': 0.1,  # 10% failure rate
            'storage_usage_warning': 0.8,  # 80% usage
            'storage_usage_critical': 0.95,  # 95% usage
            'backup_duration_warning_minutes': 60,  # 1 hour
            'backup_duration_critical_minutes': 120,  # 2 hours
            'compliance_rate_warning': 0.95,  # 95% compliance
            'rto_breach_threshold_minutes': 150,  # 2.5 hours
            'rpo_breach_threshold_minutes': 30   # 30 minutes
        }

    async def track_backup_metrics(self, 
                                 backup_id: str,
                                 backup_type: str,
                                 component: str,
                                 start_time: datetime,
                                 end_time: Optional[datetime],
                                 size_bytes: int,
                                 success: bool,
                                 encryption_enabled: bool = True,
                                 coppa_compliant: bool = True,
                                 error_message: Optional[str] = None) -> None:
        """Track backup operation metrics"""
        
        duration_seconds = 0.0
        throughput_mbps = 0.0
        
        if end_time:
            duration_seconds = (end_time - start_time).total_seconds()
            if duration_seconds > 0:
                throughput_mbps = (size_bytes / (1024 * 1024)) / (duration_seconds / 60)
        
        metrics = BackupMetrics(
            backup_id=backup_id,
            backup_type=backup_type,
            component=component,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            size_bytes=size_bytes,
            success=success,
            throughput_mbps=throughput_mbps,
            compression_ratio=0.7,  # Placeholder
            encryption_enabled=encryption_enabled,
            coppa_compliant=coppa_compliant,
            error_message=error_message
        )
        
        self.backup_metrics.append(metrics)
        
        # Update Prometheus metrics
        self._update_prometheus_metrics(metrics)
        
        # Check for alerts
        await self._check_backup_alerts(metrics)
        
        self.logger.info(f"Tracked backup metrics: {backup_id} - Success: {success}")

    def _update_prometheus_metrics(self, metrics: BackupMetrics) -> None:
        """Update Prometheus metrics"""
        # Backup completion counter
        self.metrics_collector.increment_counter(
            "backup_operations_total",
            {
                "component": metrics.component,
                "type": metrics.backup_type,
                "status": "success" if metrics.success else "failure"
            }
        )
        
        # Backup duration histogram
        self.metrics_collector.observe_histogram(
            "backup_duration_seconds",
            metrics.duration_seconds,
            {
                "component": metrics.component,
                "type": metrics.backup_type
            }
        )
        
        # Backup size histogram
        self.metrics_collector.observe_histogram(
            "backup_size_bytes",
            metrics.size_bytes,
            {
                "component": metrics.component,
                "type": metrics.backup_type
            }
        )
        
        # Backup throughput gauge
        self.metrics_collector.set_gauge(
            "backup_throughput_mbps",
            metrics.throughput_mbps,
            {
                "component": metrics.component,
                "type": metrics.backup_type
            }
        )
        
        # COPPA compliance gauge
        self.metrics_collector.set_gauge(
            "backup_coppa_compliant",
            1.0 if metrics.coppa_compliant else 0.0,
            {"backup_id": metrics.backup_id}
        )

    async def _check_backup_alerts(self, metrics: BackupMetrics) -> None:
        """Check backup metrics against alert thresholds"""
        
        # Backup failure alert
        if not metrics.success:
            await self._create_alert(
                alert_id=f"backup_failure_{metrics.backup_id}",
                title=f"Backup Failed: {metrics.component}",
                message=f"Backup {metrics.backup_id} failed. Error: {metrics.error_message or 'Unknown error'}",
                severity=AlertSeverity.CRITICAL,
                component=metrics.component,
                metrics=asdict(metrics)
            )
        
        # Backup duration alerts
        duration_minutes = metrics.duration_seconds / 60
        
        if duration_minutes > self.alert_thresholds['backup_duration_critical_minutes']:
            await self._create_alert(
                alert_id=f"backup_duration_critical_{metrics.backup_id}",
                title=f"Backup Duration Critical: {metrics.component}",
                message=f"Backup {metrics.backup_id} took {duration_minutes:.1f} minutes (critical threshold: {self.alert_thresholds['backup_duration_critical_minutes']} minutes)",
                severity=AlertSeverity.CRITICAL,
                component=metrics.component,
                metrics={"duration_minutes": duration_minutes}
            )
        elif duration_minutes > self.alert_thresholds['backup_duration_warning_minutes']:
            await self._create_alert(
                alert_id=f"backup_duration_warning_{metrics.backup_id}",
                title=f"Backup Duration Warning: {metrics.component}",
                message=f"Backup {metrics.backup_id} took {duration_minutes:.1f} minutes (warning threshold: {self.alert_thresholds['backup_duration_warning_minutes']} minutes)",
                severity=AlertSeverity.WARNING,
                component=metrics.component,
                metrics={"duration_minutes": duration_minutes}
            )
        
        # COPPA compliance alert
        if not metrics.coppa_compliant:
            await self._create_alert(
                alert_id=f"coppa_non_compliant_{metrics.backup_id}",
                title=f"COPPA Non-Compliance: {metrics.component}",
                message=f"Backup {metrics.backup_id} is not COPPA compliant",
                severity=AlertSeverity.CRITICAL,
                component=metrics.component,
                metrics={"coppa_compliant": False}
            )

    async def track_storage_metrics(self,
                                  provider: str,
                                  total_space_bytes: int,
                                  used_space_bytes: int,
                                  backup_count: int,
                                  oldest_backup_date: datetime,
                                  newest_backup_date: datetime) -> None:
        """Track storage usage metrics"""
        
        available_space_bytes = total_space_bytes - used_space_bytes
        usage_percentage = used_space_bytes / total_space_bytes if total_space_bytes > 0 else 0
        
        # Calculate growth rate (simplified)
        days_span = (newest_backup_date - oldest_backup_date).days
        growth_rate_mb_per_day = 0.0
        projected_full_date = None
        
        if days_span > 0:
            growth_rate_mb_per_day = (used_space_bytes / (1024 * 1024)) / days_span
            
            if growth_rate_mb_per_day > 0:
                days_until_full = (available_space_bytes / (1024 * 1024)) / growth_rate_mb_per_day
                projected_full_date = datetime.utcnow() + timedelta(days=days_until_full)
        
        storage_metrics = StorageMetrics(
            provider=provider,
            total_space_bytes=total_space_bytes,
            used_space_bytes=used_space_bytes,
            available_space_bytes=available_space_bytes,
            backup_count=backup_count,
            oldest_backup_date=oldest_backup_date,
            newest_backup_date=newest_backup_date,
            growth_rate_mb_per_day=growth_rate_mb_per_day,
            projected_full_date=projected_full_date
        )
        
        self.storage_metrics[provider] = storage_metrics
        
        # Update Prometheus metrics
        self.metrics_collector.set_gauge(
            "storage_total_bytes",
            total_space_bytes,
            {"provider": provider}
        )
        
        self.metrics_collector.set_gauge(
            "storage_used_bytes",
            used_space_bytes,
            {"provider": provider}
        )
        
        self.metrics_collector.set_gauge(
            "storage_usage_percentage",
            usage_percentage,
            {"provider": provider}
        )
        
        self.metrics_collector.set_gauge(
            "storage_backup_count",
            backup_count,
            {"provider": provider}
        )
        
        # Check storage alerts
        await self._check_storage_alerts(storage_metrics, usage_percentage)

    async def _check_storage_alerts(self, storage_metrics: StorageMetrics, usage_percentage: float) -> None:
        """Check storage metrics against alert thresholds"""
        
        if usage_percentage >= self.alert_thresholds['storage_usage_critical']:
            await self._create_alert(
                alert_id=f"storage_critical_{storage_metrics.provider}",
                title=f"Storage Critical: {storage_metrics.provider}",
                message=f"Storage usage is {usage_percentage:.1%} (critical threshold: {self.alert_thresholds['storage_usage_critical']:.1%})",
                severity=AlertSeverity.CRITICAL,
                component="storage",
                metrics={
                    "provider": storage_metrics.provider,
                    "usage_percentage": usage_percentage,
                    "available_gb": storage_metrics.available_space_bytes / (1024**3)
                }
            )
        elif usage_percentage >= self.alert_thresholds['storage_usage_warning']:
            await self._create_alert(
                alert_id=f"storage_warning_{storage_metrics.provider}",
                title=f"Storage Warning: {storage_metrics.provider}",
                message=f"Storage usage is {usage_percentage:.1%} (warning threshold: {self.alert_thresholds['storage_usage_warning']:.1%})",
                severity=AlertSeverity.WARNING,
                component="storage",
                metrics={
                    "provider": storage_metrics.provider,
                    "usage_percentage": usage_percentage,
                    "projected_full_date": storage_metrics.projected_full_date.isoformat() if storage_metrics.projected_full_date else None
                }
            )

    async def generate_compliance_report(self, 
                                       period_start: datetime,
                                       period_end: datetime) -> ComplianceReport:
        """Generate COPPA compliance report"""
        
        report_id = f"compliance_{period_start.strftime('%Y%m%d')}_{period_end.strftime('%Y%m%d')}"
        
        # Filter backups in period
        period_backups = [
            m for m in self.backup_metrics
            if period_start <= m.start_time <= period_end
        ]
        
        total_backups = len(period_backups)
        compliant_backups = len([m for m in period_backups if m.coppa_compliant])
        non_compliant_backups = total_backups - compliant_backups
        
        compliance_rate = compliant_backups / total_backups if total_backups > 0 else 0.0
        
        # Identify issues
        issues = []
        recommendations = []
        
        if non_compliant_backups > 0:
            issues.append(f"{non_compliant_backups} non-compliant backups found")
            recommendations.append("Review backup encryption settings")
            recommendations.append("Audit child data handling procedures")
        
        # Check encryption coverage
        unencrypted_backups = len([m for m in period_backups if not m.encryption_enabled])
        if unencrypted_backups > 0:
            issues.append(f"{unencrypted_backups} unencrypted backups found")
            recommendations.append("Enable encryption for all backup operations")
        
        # Determine overall status
        if compliance_rate >= self.alert_thresholds['compliance_rate_warning']:
            status = ComplianceStatus.COMPLIANT
        elif compliance_rate >= 0.8:
            status = ComplianceStatus.PENDING_REVIEW
        else:
            status = ComplianceStatus.NON_COMPLIANT
        
        report = ComplianceReport(
            report_id=report_id,
            timestamp=datetime.utcnow(),
            period_start=period_start,
            period_end=period_end,
            total_backups=total_backups,
            compliant_backups=compliant_backups,
            non_compliant_backups=non_compliant_backups,
            compliance_rate=compliance_rate,
            issues=issues,
            recommendations=recommendations,
            status=status
        )
        
        self.compliance_reports.append(report)
        
        # Create alert if non-compliant
        if status != ComplianceStatus.COMPLIANT:
            await self._create_alert(
                alert_id=f"compliance_violation_{report_id}",
                title="COPPA Compliance Violation",
                message=f"Compliance rate is {compliance_rate:.1%} for period {period_start.date()} to {period_end.date()}",
                severity=AlertSeverity.CRITICAL if status == ComplianceStatus.NON_COMPLIANT else AlertSeverity.WARNING,
                component="compliance",
                metrics=asdict(report)
            )
        
        self.logger.info(f"Generated compliance report: {report_id} - Status: {status.value}")
        return report

    async def track_sla_metrics(self,
                              rto_actual_minutes: Optional[int] = None,
                              rpo_actual_minutes: Optional[int] = None) -> None:
        """Track SLA metrics (RTO/RPO)"""
        
        if rto_actual_minutes is not None:
            self.sla_metrics.rto_actual_minutes = rto_actual_minutes
            
            # Check RTO breach
            if rto_actual_minutes > self.alert_thresholds['rto_breach_threshold_minutes']:
                self.sla_metrics.rto_breaches_count += 1
                
                await self._create_alert(
                    alert_id=f"rto_breach_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    title="RTO Breach",
                    message=f"Recovery Time Objective breached: {rto_actual_minutes} minutes (target: {self.sla_metrics.rto_target_minutes} minutes)",
                    severity=AlertSeverity.CRITICAL,
                    component="sla",
                    metrics={
                        "rto_actual": rto_actual_minutes,
                        "rto_target": self.sla_metrics.rto_target_minutes,
                        "breach_count": self.sla_metrics.rto_breaches_count
                    }
                )
        
        if rpo_actual_minutes is not None:
            self.sla_metrics.rpo_actual_minutes = rpo_actual_minutes
            
            # Check RPO breach
            if rpo_actual_minutes > self.alert_thresholds['rpo_breach_threshold_minutes']:
                self.sla_metrics.rpo_breaches_count += 1
                
                await self._create_alert(
                    alert_id=f"rpo_breach_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    title="RPO Breach",
                    message=f"Recovery Point Objective breached: {rpo_actual_minutes} minutes (target: {self.sla_metrics.rpo_target_minutes} minutes)",
                    severity=AlertSeverity.CRITICAL,
                    component="sla",
                    metrics={
                        "rpo_actual": rpo_actual_minutes,
                        "rpo_target": self.sla_metrics.rpo_target_minutes,
                        "breach_count": self.sla_metrics.rpo_breaches_count
                    }
                )
        
        # Update Prometheus metrics
        if self.sla_metrics.rto_actual_minutes is not None:
            self.metrics_collector.set_gauge(
                "sla_rto_actual_minutes",
                self.sla_metrics.rto_actual_minutes
            )
        
        if self.sla_metrics.rpo_actual_minutes is not None:
            self.metrics_collector.set_gauge(
                "sla_rpo_actual_minutes",
                self.sla_metrics.rpo_actual_minutes
            )
        
        self.metrics_collector.set_gauge(
            "sla_rto_breaches_total",
            self.sla_metrics.rto_breaches_count
        )
        
        self.metrics_collector.set_gauge(
            "sla_rpo_breaches_total",
            self.sla_metrics.rpo_breaches_count
        )

    async def _create_alert(self,
                          alert_id: str,
                          title: str,
                          message: str,
                          severity: AlertSeverity,
                          component: str,
                          metrics: Dict[str, Any]) -> None:
        """Create and process alert"""
        
        # Check if alert already exists (avoid duplicates)
        if alert_id in self.active_alerts:
            return
        
        alert = Alert(
            alert_id=alert_id,
            title=title,
            message=message,
            severity=severity,
            timestamp=datetime.utcnow(),
            component=component,
            metrics=metrics
        )
        
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # Send notifications
        await self._send_alert_notifications(alert)
        
        # Update metrics
        self.metrics_collector.increment_counter(
            "backup_alerts_total",
            {
                "severity": severity.value,
                "component": component
            }
        )
        
        self.logger.warning(f"Alert created: {alert_id} - {title}")

    async def _send_alert_notifications(self, alert: Alert) -> None:
        """Send alert notifications through configured channels"""
        
        channels = self.notification_config.get('channels', [])
        
        for channel in channels:
            try:
                if channel['type'] == AlertChannel.EMAIL.value:
                    await self._send_email_alert(alert, channel['config'])
                elif channel['type'] == AlertChannel.SLACK.value:
                    await self._send_slack_alert(alert, channel['config'])
                elif channel['type'] == AlertChannel.PAGERDUTY.value:
                    await self._send_pagerduty_alert(alert, channel['config'])
                elif channel['type'] == AlertChannel.WEBHOOK.value:
                    await self._send_webhook_alert(alert, channel['config'])
                    
            except Exception as e:
                self.logger.error(f"Failed to send alert via {channel['type']}: {e}")

    async def _send_email_alert(self, alert: Alert, config: Dict[str, Any]) -> None:
        """Send email alert"""
        
        smtp_server = config.get('smtp_server', 'localhost')
        smtp_port = config.get('smtp_port', 587)
        username = config.get('username')
        password = config.get('password')
        from_email = config.get('from_email')
        to_emails = config.get('to_emails', [])
        
        if not all([from_email, to_emails]):
            return
        
        # Create message
        msg = MimeMultipart()
        msg['From'] = from_email
        msg['To'] = ', '.join(to_emails)
        msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
        
        # Create email body
        body = f"""
Alert: {alert.title}
Severity: {alert.severity.value.upper()}
Component: {alert.component}
Timestamp: {alert.timestamp.isoformat()}

Message:
{alert.message}

Metrics:
{json.dumps(alert.metrics, indent=2, default=str)}

Alert ID: {alert.alert_id}
        """
        
        msg.attach(MimeText(body, 'plain'))
        
        # Send email
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            if username and password:
                server.starttls()
                server.login(username, password)
            
            server.send_message(msg)
            server.quit()
            
            self.logger.info(f"Email alert sent: {alert.alert_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")

    async def _send_slack_alert(self, alert: Alert, config: Dict[str, Any]) -> None:
        """Send Slack alert"""
        
        webhook_url = config.get('webhook_url')
        if not webhook_url:
            return
        
        # Determine color based on severity
        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ffeb3b",
            AlertSeverity.CRITICAL: "#f44336",
            AlertSeverity.EMERGENCY: "#9c27b0"
        }
        
        color = color_map.get(alert.severity, "#36a64f")
        
        # Create Slack message
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert.severity.value.upper(),
                            "short": True
                        },
                        {
                            "title": "Component",
                            "value": alert.component,
                            "short": True
                        },
                        {
                            "title": "Timestamp",
                            "value": alert.timestamp.isoformat(),
                            "short": True
                        },
                        {
                            "title": "Alert ID",
                            "value": alert.alert_id,
                            "short": True
                        }
                    ],
                    "footer": "AI Teddy Bear Backup Monitoring",
                    "ts": int(alert.timestamp.timestamp())
                }
            ]
        }
        
        # Send to Slack
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        self.logger.info(f"Slack alert sent: {alert.alert_id}")
                    else:
                        self.logger.error(f"Slack alert failed: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")

    async def _send_pagerduty_alert(self, alert: Alert, config: Dict[str, Any]) -> None:
        """Send PagerDuty alert"""
        
        integration_key = config.get('integration_key')
        if not integration_key:
            return
        
        # Map severity to PagerDuty severity
        severity_map = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.CRITICAL: "error",
            AlertSeverity.EMERGENCY: "critical"
        }
        
        payload = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "dedup_key": alert.alert_id,
            "payload": {
                "summary": alert.title,
                "source": "ai-teddy-bear-backup",
                "severity": severity_map.get(alert.severity, "error"),
                "component": alert.component,
                "custom_details": alert.metrics
            }
        }
        
        # Send to PagerDuty
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload
                ) as response:
                    if response.status == 202:
                        self.logger.info(f"PagerDuty alert sent: {alert.alert_id}")
                    else:
                        self.logger.error(f"PagerDuty alert failed: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"Failed to send PagerDuty alert: {e}")

    async def _send_webhook_alert(self, alert: Alert, config: Dict[str, Any]) -> None:
        """Send webhook alert"""
        
        webhook_url = config.get('url')
        if not webhook_url:
            return
        
        payload = {
            "alert_id": alert.alert_id,
            "title": alert.title,
            "message": alert.message,
            "severity": alert.severity.value,
            "component": alert.component,
            "timestamp": alert.timestamp.isoformat(),
            "metrics": alert.metrics
        }
        
        headers = config.get('headers', {})
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers=headers
                ) as response:
                    if 200 <= response.status < 300:
                        self.logger.info(f"Webhook alert sent: {alert.alert_id}")
                    else:
                        self.logger.error(f"Webhook alert failed: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert"""
        
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            del self.active_alerts[alert_id]
            
            self.logger.info(f"Alert resolved: {alert_id}")
            return True
        
        return False

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an active alert"""
        
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.acknowledged = True
            
            self.logger.info(f"Alert acknowledged: {alert_id}")
            return True
        
        return False

    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get active alerts, optionally filtered by severity"""
        
        alerts = list(self.active_alerts.values())
        
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history"""
        
        return sorted(self.alert_history, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_backup_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of backup metrics for the last N hours"""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.backup_metrics
            if m.start_time >= cutoff_time
        ]
        
        if not recent_metrics:
            return {
                "total_backups": 0,
                "successful_backups": 0,
                "failed_backups": 0,
                "success_rate": 0.0,
                "total_size_gb": 0.0,
                "average_duration_minutes": 0.0,
                "coppa_compliance_rate": 0.0
            }
        
        successful = [m for m in recent_metrics if m.success]
        failed = [m for m in recent_metrics if not m.success]
        compliant = [m for m in recent_metrics if m.coppa_compliant]
        
        total_size_gb = sum(m.size_bytes for m in recent_metrics) / (1024**3)
        durations = [m.duration_seconds for m in recent_metrics if m.duration_seconds > 0]
        avg_duration_minutes = (sum(durations) / len(durations) / 60) if durations else 0
        
        return {
            "total_backups": len(recent_metrics),
            "successful_backups": len(successful),
            "failed_backups": len(failed),
            "success_rate": len(successful) / len(recent_metrics),
            "total_size_gb": total_size_gb,
            "average_duration_minutes": avg_duration_minutes,
            "coppa_compliance_rate": len(compliant) / len(recent_metrics)
        }

    def get_storage_summary(self) -> Dict[str, Any]:
        """Get storage usage summary across all providers"""
        
        if not self.storage_metrics:
            return {
                "total_providers": 0,
                "total_space_gb": 0.0,
                "total_used_gb": 0.0,
                "overall_usage_percentage": 0.0,
                "total_backups": 0
            }
        
        total_space = sum(m.total_space_bytes for m in self.storage_metrics.values())
        total_used = sum(m.used_space_bytes for m in self.storage_metrics.values())
        total_backups = sum(m.backup_count for m in self.storage_metrics.values())
        
        return {
            "total_providers": len(self.storage_metrics),
            "total_space_gb": total_space / (1024**3),
            "total_used_gb": total_used / (1024**3),
            "overall_usage_percentage": total_used / total_space if total_space > 0 else 0.0,
            "total_backups": total_backups,
            "providers": {
                provider: {
                    "usage_percentage": metrics.used_space_bytes / metrics.total_space_bytes if metrics.total_space_bytes > 0 else 0.0,
                    "backup_count": metrics.backup_count,
                    "growth_rate_mb_per_day": metrics.growth_rate_mb_per_day
                }
                for provider, metrics in self.storage_metrics.items()
            }
        }

    def get_sla_summary(self) -> Dict[str, Any]:
        """Get SLA metrics summary"""
        
        return {
            "rto_target_minutes": self.sla_metrics.rto_target_minutes,
            "rpo_target_minutes": self.sla_metrics.rpo_target_minutes,
            "rto_actual_minutes": self.sla_metrics.rto_actual_minutes,
            "rpo_actual_minutes": self.sla_metrics.rpo_actual_minutes,
            "rto_breaches_count": self.sla_metrics.rto_breaches_count,
            "rpo_breaches_count": self.sla_metrics.rpo_breaches_count,
            "availability_percentage": self.sla_metrics.availability_percentage,
            "mttr_minutes": self.sla_metrics.mttr_minutes,
            "mtbf_hours": self.sla_metrics.mtbf_hours
        }

    async def send_backup_notification(self,
                                     job_id: str,
                                     status: str,
                                     size_mb: float,
                                     duration_seconds: float,
                                     coppa_verified: bool = True) -> None:
        """Send backup completion notification"""
        
        if status == "completed":
            message = f"Backup {job_id} completed successfully in {duration_seconds/60:.1f} minutes ({size_mb:.1f} MB)"
            severity = AlertSeverity.INFO
        else:
            message = f"Backup {job_id} failed after {duration_seconds/60:.1f} minutes"
            severity = AlertSeverity.CRITICAL
        
        await self._create_alert(
            alert_id=f"backup_notification_{job_id}",
            title=f"Backup {status.title()}: {job_id}",
            message=message,
            severity=severity,
            component="backup",
            metrics={
                "job_id": job_id,
                "status": status,
                "size_mb": size_mb,
                "duration_seconds": duration_seconds,
                "coppa_verified": coppa_verified
            }
        )

    async def send_backup_alert(self,
                              job_id: str,
                              error: str,
                              failed_components: List[str]) -> None:
        """Send backup failure alert"""
        
        await self._create_alert(
            alert_id=f"backup_failure_{job_id}",
            title=f"Backup Failure: {job_id}",
            message=f"Backup failed with error: {error}. Failed components: {', '.join(failed_components)}",
            severity=AlertSeverity.CRITICAL,
            component="backup",
            metrics={
                "job_id": job_id,
                "error": error,
                "failed_components": failed_components
            }
        )

    async def start_monitoring(self) -> None:
        """Start background monitoring tasks"""
        
        self.logger.info("Starting backup monitoring service")
        
        # Start periodic tasks
        asyncio.create_task(self._periodic_compliance_check())
        asyncio.create_task(self._periodic_storage_check())
        asyncio.create_task(self._periodic_alert_cleanup())

    async def _periodic_compliance_check(self) -> None:
        """Periodic COPPA compliance check"""
        
        while True:
            try:
                # Generate daily compliance report
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=1)
                
                await self.generate_compliance_report(start_time, end_time)
                
                # Wait 24 hours
                await asyncio.sleep(24 * 3600)
                
            except Exception as e:
                self.logger.error(f"Periodic compliance check failed: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error

    async def _periodic_storage_check(self) -> None:
        """Periodic storage usage check"""
        
        while True:
            try:
                # Check storage usage for all providers
                for provider, metrics in self.storage_metrics.items():
                    usage_percentage = metrics.used_space_bytes / metrics.total_space_bytes if metrics.total_space_bytes > 0 else 0
                    
                    # Update storage metrics
                    await self.track_storage_metrics(
                        provider=provider,
                        total_space_bytes=metrics.total_space_bytes,
                        used_space_bytes=metrics.used_space_bytes,
                        backup_count=metrics.backup_count,
                        oldest_backup_date=metrics.oldest_backup_date,
                        newest_backup_date=metrics.newest_backup_date
                    )
                
                # Wait 1 hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"Periodic storage check failed: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes on error

    async def _periodic_alert_cleanup(self) -> None:
        """Periodic cleanup of resolved alerts"""
        
        while True:
            try:
                # Clean up old resolved alerts from history
                cutoff_time = datetime.utcnow() - timedelta(days=30)
                
                self.alert_history = [
                    alert for alert in self.alert_history
                    if alert.timestamp >= cutoff_time or not alert.resolved
                ]
                
                # Wait 24 hours
                await asyncio.sleep(24 * 3600)
                
            except Exception as e:
                self.logger.error(f"Alert cleanup failed: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error