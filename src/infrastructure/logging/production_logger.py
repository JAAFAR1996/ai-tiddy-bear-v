"""
🧸 AI TEDDY BEAR V5 - PRODUCTION LOGGING SYSTEM
==============================================
Structured logging with security, audit, and compliance features.
"""

import logging
import logging.handlers
import json
import time
import os
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import structlog
from uuid import uuid4


class SecurityFilter(logging.Filter):
    """Filter to prevent logging of sensitive information."""

    SENSITIVE_KEYS = {
        "password",
        "secret",
        "key",
        "token",
        "api_key",
        "auth",
        "authorization",
        "cookie",
        "session",
        "csrf",
        "ssn",
        "credit_card",
        "card_number",
        "cvv",
        "pin",
    }

    def filter(self, record):
        """Filter out sensitive information from log records."""
        if hasattr(record, "msg") and isinstance(record.msg, str):
            # Check if message contains sensitive patterns
            msg_lower = record.msg.lower()
            for sensitive in self.SENSITIVE_KEYS:
                if sensitive in msg_lower:
                    # استخدام regex لإخفاء المعلومات الحساسة بدون تخريب الرسالة
                    import re

                    pattern = rf'({sensitive}[\s=:]*["\']?)([^"\'\s,}}\]]+)'
                    record.msg = re.sub(
                        pattern, r"\1***MASKED***", record.msg, flags=re.IGNORECASE
                    )

        # Filter sensitive data from extra fields
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                    setattr(record, key, "***MASKED***")

        return True


class COPPAComplianceFilter(logging.Filter):
    """Filter to ensure COPPA compliance in logs."""

    CHILD_DATA_KEYS = {
        "child_name",
        "child_id",
        "child_age",
        "child_email",
        "parent_email",
        "guardian_email",
        "school",
        "address",
        "phone",
        "location",
        "ip_address",
    }

    def filter(self, record):
        """Ensure child data is properly handled in logs."""
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if any(child_key in key.lower() for child_key in self.CHILD_DATA_KEYS):
                    # Hash or mask child-related data
                    if "id" in key.lower():
                        # Keep IDs but hash them for tracking
                        import hashlib

                        hashed = hashlib.sha256(str(value).encode()).hexdigest()[:8]
                        setattr(record, key, f"child_{hashed}")
                    else:
                        setattr(record, key, "***COPPA_PROTECTED***")

        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
            ]:
                log_entry[key] = value

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class AuditLogger:
    """Specialized logger for audit events."""

    def __init__(self, name: str = "audit"):
        self.logger = logging.getLogger(f"audit.{name}")
        self.logger.setLevel(logging.INFO)

        # Ensure audit logs go to separate file
        if not self.logger.handlers:
            self._setup_audit_handler()

    def _setup_audit_handler(self):
        """Setup audit log handler."""
        log_dir = Path("logs/audit")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Rotating file handler for audit logs
        handler = logging.handlers.TimedRotatingFileHandler(
            log_dir / "audit.log",
            when="midnight",
            interval=1,
            backupCount=365,  # Keep 1 year of audit logs
            encoding="utf-8",
        )

        handler.setFormatter(JSONFormatter())
        handler.addFilter(SecurityFilter())
        handler.addFilter(COPPAComplianceFilter())

        self.logger.addHandler(handler)
        self.logger.propagate = False  # Don't propagate to root logger

    def log_event(self, event_data: Dict[str, Any]):
        """Log an audit event."""
        event_data.update(
            {
                "event_id": str(uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "audit_type": "security_audit",
            }
        )

        self.logger.info("Audit event", extra=event_data)


class SecurityLogger:
    """Specialized logger for security events."""

    def __init__(self, name: str = "security"):
        self.logger = logging.getLogger(f"security.{name}")
        self.logger.setLevel(logging.WARNING)

        if not self.logger.handlers:
            self._setup_security_handler()

    def _setup_security_handler(self):
        """Setup security log handler."""
        log_dir = Path("logs/security")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Rotating file handler for security logs
        handler = logging.handlers.TimedRotatingFileHandler(
            log_dir / "security.log",
            when="midnight",
            interval=1,
            backupCount=90,  # Keep 90 days of security logs
            encoding="utf-8",
        )

        handler.setFormatter(JSONFormatter())
        handler.addFilter(SecurityFilter())

        self.logger.addHandler(handler)
        self.logger.propagate = False

    def warning(self, message: str, **kwargs):
        """Log security warning."""
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs):
        """Log security error."""
        self.logger.error(message, extra=kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical security event."""
        self.logger.critical(message, extra=kwargs)


def setup_production_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    enable_console: bool = True,
    enable_file: bool = True,
):
    """Setup production logging configuration."""

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JSONFormatter())
        console_handler.addFilter(SecurityFilter())
        console_handler.addFilter(COPPAComplianceFilter())
        root_logger.addHandler(console_handler)

    # File handler
    if enable_file:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_path / "application.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(SecurityFilter())
        file_handler.addFilter(COPPAComplianceFilter())
        root_logger.addHandler(file_handler)

    # Error file handler
    error_handler = logging.handlers.TimedRotatingFileHandler(
        log_path / "errors.log",
        when="midnight",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    error_handler.addFilter(SecurityFilter())
    root_logger.addHandler(error_handler)


def get_logger(name: str, context: str = None) -> logging.Logger:
    """Get a configured logger instance."""
    logger_name = f"{name}.{context}" if context else name
    return logging.getLogger(logger_name)


# Global instances
security_logger = SecurityLogger()
audit_logger = AuditLogger()

# Initialize logging on import
setup_production_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    enable_console=os.getenv("ENABLE_CONSOLE_LOGGING", "true").lower() == "true",
    enable_file=os.getenv("ENABLE_FILE_LOGGING", "true").lower() == "true",
)
