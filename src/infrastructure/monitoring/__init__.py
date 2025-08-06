"""
🧸 AI TEDDY BEAR V5 - MONITORING INFRASTRUCTURE
==============================================
COPPA compliance monitoring and audit systems.
"""

from .audit import (
    COPPAAuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    coppa_audit,
    get_user_context_from_request,
)


def get_metrics_collector():
    """Get metrics collector instance with lazy import to avoid circular imports."""
    from ..performance.monitoring import MetricsCollector
    return MetricsCollector()


__all__ = [
    "COPPAAuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditSeverity",
    "coppa_audit",
    "get_user_context_from_request",
    "get_metrics_collector",
]