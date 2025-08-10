"""
🧸 AI TEDDY BEAR V5 - COPPA COMPLIANCE AUDIT SYSTEM
==================================================
Comprehensive audit logging for COPPA compliance and child safety.
"""

import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path
import hashlib
from dataclasses import dataclass, asdict
from enum import Enum

from ..logging.production_logger import AuditLogger


class AuditEventType(Enum):
    """Types of audit events for COPPA compliance."""

    # Child data events
    CHILD_REGISTRATION = "child_registration"
    CHILD_DATA_ACCESS = "child_data_access"
    CHILD_DATA_MODIFICATION = "child_data_modification"
    CHILD_DATA_DELETION = "child_data_deletion"

    # Parental consent events
    PARENTAL_CONSENT_REQUEST = "parental_consent_request"
    PARENTAL_CONSENT_GRANTED = "parental_consent_granted"
    PARENTAL_CONSENT_REVOKED = "parental_consent_revoked"
    PARENTAL_CONSENT_EXPIRED = "parental_consent_expired"

    # Safety events
    CONTENT_FILTER_TRIGGERED = "content_filter_triggered"
    INAPPROPRIATE_CONTENT_BLOCKED = "inappropriate_content_blocked"
    SAFETY_VIOLATION = "safety_violation"

    # Security events
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

    # System events
    DATA_EXPORT_REQUEST = "data_export_request"
    DATA_RETENTION_CLEANUP = "data_retention_cleanup"
    SYSTEM_ERROR = "system_error"


class AuditSeverity(Enum):
    """Severity levels for audit events."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Structured audit event for COPPA compliance."""

    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: str
    description: str

    # User context (anonymized for children)
    user_id: Optional[str] = None
    user_type: Optional[str] = None  # 'child', 'parent', 'admin'
    session_id: Optional[str] = None

    # Child context (always anonymized)
    child_id_hash: Optional[str] = None
    child_age_group: Optional[str] = None  # '3-5', '6-8', '9-12', '13+'

    # Request context
    ip_address_hash: Optional[str] = None
    user_agent_hash: Optional[str] = None
    request_id: Optional[str] = None

    # Event-specific data
    metadata: Optional[Dict[str, Any]] = None

    # Compliance flags
    coppa_relevant: bool = True
    requires_parental_notification: bool = False
    data_subject_rights_impact: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return asdict(self)


class COPPAAuditLogger:
    """COPPA-compliant audit logging system."""

    def __init__(self):
        self.audit_logger = AuditLogger("coppa_compliance")
        self.events_cache: List[AuditEvent] = []
        self.cache_size = 1000

    def log_event(self, event_data: Dict[str, Any]) -> str:
        """Log a COPPA compliance audit event."""

        # Create structured audit event
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type=AuditEventType(event_data.get("event_type", "system_error")),
            severity=AuditSeverity(event_data.get("severity", "info")),
            timestamp=datetime.utcnow().isoformat() + "Z",
            description=event_data.get("description", "Audit event"),
            user_id=self._anonymize_user_id(event_data.get("user_id")),
            user_type=event_data.get("user_type"),
            session_id=event_data.get("session_id"),
            child_id_hash=self._hash_child_id(event_data.get("child_id")),
            child_age_group=self._categorize_age(event_data.get("child_age")),
            ip_address_hash=self._hash_ip_address(event_data.get("ip_address")),
            user_agent_hash=self._hash_user_agent(event_data.get("user_agent")),
            request_id=event_data.get("request_id"),
            metadata=self._sanitize_metadata(event_data.get("metadata", {})),
            coppa_relevant=event_data.get("coppa_relevant", True),
            requires_parental_notification=event_data.get(
                "requires_parental_notification", False
            ),
            data_subject_rights_impact=event_data.get(
                "data_subject_rights_impact", False
            ),
        )

        # Log the event
        self.audit_logger.log_event(event.to_dict())

        # Cache for analysis
        self._cache_event(event)

        # Check for critical events requiring immediate action
        if event.severity == AuditSeverity.CRITICAL:
            self._handle_critical_event(event)

        return event.event_id

    def log_child_data_access(
        self,
        child_id: str,
        accessed_by: str,
        access_type: str,
        data_fields: List[str],
        purpose: str,
        request_id: str = None,
    ) -> str:
        """Log child data access for COPPA compliance."""

        return self.log_event(
            {
                "event_type": "child_data_access",
                "severity": "info",
                "description": f"Child data accessed: {access_type}",
                "child_id": child_id,
                "user_id": accessed_by,
                "request_id": request_id,
                "metadata": {
                    "access_type": access_type,
                    "data_fields": data_fields,
                    "purpose": purpose,
                    "field_count": len(data_fields),
                },
                "coppa_relevant": True,
                "data_subject_rights_impact": True,
            }
        )

    def log_parental_consent_event(
        self,
        child_id: str,
        parent_id: str,
        consent_type: str,
        action: str,
        request_id: str = None,
    ) -> str:
        """Log parental consent events."""

        event_type_map = {
            "request": "parental_consent_request",
            "grant": "parental_consent_granted",
            "revoke": "parental_consent_revoked",
            "expire": "parental_consent_expired",
        }

        return self.log_event(
            {
                "event_type": event_type_map.get(action, "parental_consent_request"),
                "severity": "warning" if action == "revoke" else "info",
                "description": f"Parental consent {action}: {consent_type}",
                "child_id": child_id,
                "user_id": parent_id,
                "user_type": "parent",
                "request_id": request_id,
                "metadata": {"consent_type": consent_type, "action": action},
                "coppa_relevant": True,
                "requires_parental_notification": action in ["grant", "revoke"],
            }
        )

    def log_safety_violation(
        self,
        child_id: str,
        violation_type: str,
        content: str,
        severity: str = "warning",
        request_id: str = None,
    ) -> str:
        """Log child safety violations."""

        return self.log_event(
            {
                "event_type": "safety_violation",
                "severity": severity,
                "description": f"Safety violation detected: {violation_type}",
                "child_id": child_id,
                "request_id": request_id,
                "metadata": {
                    "violation_type": violation_type,
                    "content_hash": self._hash_content(content),
                    "content_length": len(content),
                },
                "coppa_relevant": True,
                "requires_parental_notification": severity in ["error", "critical"],
            }
        )

    def log_data_retention_event(
        self, child_id: str, action: str, data_types: List[str], reason: str
    ) -> str:
        """Log data retention and deletion events."""

        return self.log_event(
            {
                "event_type": "data_retention_cleanup",
                "severity": "info",
                "description": f"Data retention action: {action}",
                "child_id": child_id,
                "metadata": {
                    "action": action,
                    "data_types": data_types,
                    "reason": reason,
                    "data_type_count": len(data_types),
                },
                "coppa_relevant": True,
                "data_subject_rights_impact": True,
            }
        )

    def get_child_audit_trail(
        self, child_id: str, start_date: datetime = None, end_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a specific child (for parental requests)."""

        child_hash = self._hash_child_id(child_id)

        # Filter cached events
        filtered_events = []
        for event in self.events_cache:
            if event.child_id_hash == child_hash:
                if (
                    start_date
                    and datetime.fromisoformat(event.timestamp.replace("Z", ""))
                    < start_date
                ):
                    continue
                if (
                    end_date
                    and datetime.fromisoformat(event.timestamp.replace("Z", ""))
                    > end_date
                ):
                    continue
                filtered_events.append(event.to_dict())

        return filtered_events

    def generate_compliance_report(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Generate COPPA compliance report."""

        # Filter events by date range
        period_events = []
        for event in self.events_cache:
            event_time = datetime.fromisoformat(event.timestamp.replace("Z", ""))
            if start_date <= event_time <= end_date:
                period_events.append(event)

        # Analyze events
        report = {
            "report_id": str(uuid4()),
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "summary": {
                "total_events": len(period_events),
                "coppa_relevant_events": len(
                    [e for e in period_events if e.coppa_relevant]
                ),
                "critical_events": len(
                    [e for e in period_events if e.severity == AuditSeverity.CRITICAL]
                ),
                "safety_violations": len(
                    [
                        e
                        for e in period_events
                        if e.event_type == AuditEventType.SAFETY_VIOLATION
                    ]
                ),
            },
            "event_breakdown": {},
            "compliance_metrics": {
                "parental_consent_requests": 0,
                "data_access_events": 0,
                "safety_violations": 0,
                "data_retention_actions": 0,
            },
        }

        # Count events by type
        for event in period_events:
            event_type = event.event_type.value
            report["event_breakdown"][event_type] = (
                report["event_breakdown"].get(event_type, 0) + 1
            )

            # Update compliance metrics
            if event.event_type == AuditEventType.PARENTAL_CONSENT_REQUEST:
                report["compliance_metrics"]["parental_consent_requests"] += 1
            elif event.event_type == AuditEventType.CHILD_DATA_ACCESS:
                report["compliance_metrics"]["data_access_events"] += 1
            elif event.event_type == AuditEventType.SAFETY_VIOLATION:
                report["compliance_metrics"]["safety_violations"] += 1
            elif event.event_type == AuditEventType.DATA_RETENTION_CLEANUP:
                report["compliance_metrics"]["data_retention_actions"] += 1

        return report

    def _anonymize_user_id(self, user_id: str) -> Optional[str]:
        """Anonymize user ID for logging."""
        if not user_id:
            return None
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    def _hash_child_id(self, child_id: str) -> Optional[str]:
        """Hash child ID for COPPA compliance."""
        if not child_id:
            return None
        return hashlib.sha256(f"child_{child_id}".encode()).hexdigest()[:16]

    def _categorize_age(self, age: int) -> Optional[str]:
        """Categorize age into groups for privacy."""
        if age is None:
            return None

        if age <= 5:
            return "3-5"
        elif age <= 8:
            return "6-8"
        elif age <= 12:
            return "9-12"
        else:
            return "13+"

    def _hash_ip_address(self, ip_address: str) -> Optional[str]:
        """Hash IP address for privacy."""
        if not ip_address:
            return None
        return hashlib.sha256(ip_address.encode()).hexdigest()[:12]

    def _hash_user_agent(self, user_agent: str) -> Optional[str]:
        """Hash user agent for privacy."""
        if not user_agent:
            return None
        return hashlib.sha256(user_agent.encode()).hexdigest()[:12]

    def _hash_content(self, content: str) -> str:
        """Hash content for audit trail without storing actual content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from metadata."""
        sensitive_keys = {
            "password",
            "secret",
            "key",
            "token",
            "api_key",
            "email",
            "phone",
            "address",
            "ssn",
            "credit_card",
        }

        sanitized = {}
        for key, value in metadata.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***SANITIZED***"
            else:
                sanitized[key] = value

        return sanitized

    def _cache_event(self, event: AuditEvent):
        """Cache event for analysis and reporting."""
        self.events_cache.append(event)

        # Maintain cache size
        if len(self.events_cache) > self.cache_size:
            self.events_cache.pop(0)

    def _handle_critical_event(self, event: AuditEvent):
        """Handle critical events requiring immediate action."""
        # Log critical event to separate file
        critical_log_path = Path("logs/critical_events.log")
        critical_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(critical_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), default=str) + "\n")

        # إرسال تنبيه فوري عبر البريد الإلكتروني للمسؤول
        try:
            import asyncio
            from src.services.service_registry import get_notification_service
            from src.infrastructure.config.config_provider import get_config

            async def send_admin_alert():
                notification_service = await get_notification_service()
                config = get_config()
                admin_email = getattr(config, "PARENT_NOTIFICATION_EMAIL", None)
                if not admin_email:
                    return
                subject = f"[CRITICAL AUDIT EVENT] {event.event_type.value}"
                body = (
                    f"A critical audit event occurred at {event.timestamp}:\n\n"
                    f"Type: {event.event_type.value}\n"
                    f"Description: {event.description}\n"
                    f"Severity: {event.severity.value}\n"
                    f"Event ID: {event.event_id}\n"
                    f"User Type: {event.user_type or 'N/A'}\n"
                    f"Session ID: {event.session_id or 'N/A'}\n"
                    f"Metadata: {json.dumps(event.metadata, ensure_ascii=False)}\n"
                )
                try:
                    await notification_service.send_email(
                        to=admin_email, subject=subject, body=body
                    )
                except Exception as e:
                    # Log but do not raise
                    print(f"[Audit Alert] Failed to send admin alert: {e}")

            # Run async alert in background (non-blocking)
            asyncio.create_task(send_admin_alert())
        except Exception as e:
            print(f"[Audit Alert] Failed to schedule admin alert: {e}")


def get_user_context_from_request(request) -> Dict[str, Any]:
    """Extract user context from request for audit logging."""

    context = {
        "ip_address": (
            getattr(request.client, "host", None)
            if hasattr(request, "client")
            else None
        ),
        "user_agent": (
            request.headers.get("user-agent") if hasattr(request, "headers") else None
        ),
        "request_id": (
            getattr(request.state, "request_id", None)
            if hasattr(request, "state")
            else None
        ),
    }

    # Extract user info from request state if available
    if hasattr(request, "state"):
        context.update(
            {
                "user_id": getattr(request.state, "user_id", None),
                "user_type": getattr(request.state, "user_type", None),
                "session_id": getattr(request.state, "session_id", None),
            }
        )

    return context


# Global COPPA audit logger instance
coppa_audit = COPPAAuditLogger()
