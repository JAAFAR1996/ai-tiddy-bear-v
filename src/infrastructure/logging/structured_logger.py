"""
Structured Logger - Production Logging Infrastructure
===================================================
Enterprise-grade structured logging system for AI Teddy Bear:
  * ELK Stack integration (Elasticsearch, Logstash, Kibana)
  * CloudWatch Logs integration
  * Structured JSON logging with proper correlation IDs
  * Log level management and filtering
  * Performance monitoring and log buffering
  * Security-aware logging (no secrets/PII)
  * Child safety specific logging categories
"""

import json
import logging
import logging.handlers
import os
import re
import sys
import time
import traceback
import threading
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class LoggingConfigurationError(Exception):
    """Critical logging configuration error that prevents production deployment."""
    pass


try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from pythonjsonlogger import jsonlogger
    JSON_LOGGER_AVAILABLE = True
except ImportError:
    JSON_LOGGER_AVAILABLE = False

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False


class LogLevel(Enum):
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SECURITY = "SECURITY"
    AUDIT = "AUDIT"
    CHILD_SAFETY = "CHILD_SAFETY"
    COMPLIANCE = "COMPLIANCE"


class LogCategory(Enum):
    APPLICATION = "application"
    HTTP = "http"
    DATABASE = "database"
    CACHE = "cache"
    PROVIDER = "provider"
    SECURITY = "security"
    CHILD_SAFETY = "child_safety"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    SYSTEM = "system"
    AUDIT = "audit"


@dataclass
class LogContext:
    correlation_id: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    child_id: Optional[str] = None
    parent_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    operation: Optional[str] = None
    component: Optional[str] = None
    version: Optional[str] = None
    environment: Optional[str] = None
    region: Optional[str] = None
    instance_id: Optional[str] = None


@dataclass
class LogEntry:
    timestamp: str
    level: str
    category: str
    message: str
    logger_name: str
    context: LogContext
    metadata: Dict[str, Any]
    duration_ms: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    child_safety_flags: Optional[Dict[str, Any]] = None
    compliance_tags: Optional[List[str]] = None


log_context: ContextVar[Optional[LogContext]] = ContextVar("log_context", default=None)


def set_log_context(context: Optional[LogContext]) -> None:
    """Set the current logging context for the active request or operation."""
    if context is not None and not isinstance(context, LogContext):
        raise TypeError(f"context must be LogContext or None, got {type(context)}")
    log_context.set(context)


def get_log_context() -> Optional[LogContext]:
    """Get the current logging context for the active request or operation."""
    return log_context.get()


class SecurityFilter(logging.Filter):
    SENSITIVE_KEYS = {
        "password", "token", "secret", "key", "authorization", "cookie",
        "credit_card", "ssn", "phone", "email", "address", "birth_date",
        "child_name", "parent_name", "real_name", "location", "ip_address",
    }
    PII_PATTERNS = [
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        r"sk-[A-Za-z0-9]{32,}",
        r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}",
        r"(?i)password\s*[:=]\s*[^\s,;]+",
        r"(?i)secret\s*[:=]\s*[^\s,;]+",
        r"(?i)token\s*[:=]\s*[^\s,;]+",
        r"(?i)api[_-]?key\s*[:=]\s*[^\s,;]+",
    ]
    _audit_log: list = []

    def filter(self, record):
        original = str(record.getMessage())
        redacted = self._sanitize_string(original, None)
        if original != redacted:
            SecurityFilter._audit_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "original": original,
                "redacted": redacted,
            })
        record.msg = redacted
        return True

    @classmethod
    def sanitize_data(cls, data: Any, _parent_stack=None) -> Any:
        if _parent_stack is None:
            _parent_stack = traceback.format_stack()
        if isinstance(data, dict):
            return {key: cls._sanitize_value(key, value, _parent_stack) for key, value in data.items()}
        elif isinstance(data, (list, tuple)):
            return [cls.sanitize_data(item, _parent_stack) for item in data]
        elif isinstance(data, str):
            return cls._sanitize_string(data, _parent_stack)
        else:
            return data

    @classmethod
    def _sanitize_value(cls, key: str, value: Any, _parent_stack) -> Any:
        if isinstance(key, str) and key.lower() in cls.SENSITIVE_KEYS:
            cls._audit_log.append({
                "event": "sensitive_value_redacted",
                "key": key,
                "stack": _parent_stack,
                "timestamp": time.time(),
            })
            return "[REDACTED]"
        return cls.sanitize_data(value, _parent_stack)

    @classmethod
    def _sanitize_string(cls, text: str, _parent_stack) -> str:
        redacted = text
        for pattern in cls.PII_PATTERNS:
            if re.search(pattern, redacted):
                cls._audit_log.append({
                    "event": "pii_pattern_redacted",
                    "pattern": pattern,
                    "stack": _parent_stack,
                    "timestamp": time.time(),
                })
                redacted = re.sub(pattern, "[REDACTED]", redacted)
        return redacted

    @classmethod
    def validate_environment_security(cls):
        """Validate environment for credential leaks."""
        sensitive_env_vars = ["AWS_SECRET_ACCESS_KEY", "DATABASE_PASSWORD", "API_KEY"]
        for var in sensitive_env_vars:
            if var in os.environ:
                value = os.environ[var]
                if len(value) < 10 or value in ["test", "dev", "password"]:
                    if os.getenv("ENVIRONMENT") == "production":
                        raise LoggingConfigurationError(f"Weak credential detected: {var}")
    
    @classmethod
    def get_audit_log(cls) -> list:
        return list(cls._audit_log)


class CloudWatchHandler(logging.Handler):
    def __init__(self, log_group: str, log_stream: str, region: str = "us-east-1"):
        super().__init__()
        self.log_group = log_group
        self.log_stream = log_stream
        self.region = region
        self.client = None
        self.sequence_token = None
        self.buffer = []
        self.buffer_size = 100
        self.flush_interval = 5.0
        self.last_flush = time.time()
        self._buffer_lock = threading.Lock()
        if BOTO3_AVAILABLE:
            try:
                self.client = boto3.client("logs", region_name=region)
                self._ensure_log_group_exists()
                self._ensure_log_stream_exists()
            except (ClientError, NoCredentialsError) as e:
                error_msg = f"CloudWatch logging disabled: {e}"
                logging.getLogger(__name__).warning(error_msg)
                if os.getenv("ENVIRONMENT") == "production":
                    StructuredLogger._critical_failures.append(f"CloudWatch: {error_msg}")
                self.client = None

    def _ensure_log_group_exists(self):
        try:
            self.client.describe_log_groups(logGroupNamePrefix=self.log_group)
        except ClientError:
            try:
                self.client.create_log_group(logGroupName=self.log_group)
                retention_days = int(os.getenv("LOG_RETENTION_DAYS", "30"))
                self.client.put_retention_policy(logGroupName=self.log_group, retentionInDays=retention_days)
            except ClientError as e:
                logging.getLogger(__name__).error(f"Failed to create log group: {e}")

    def _ensure_log_stream_exists(self):
        try:
            response = self.client.describe_log_streams(logGroupName=self.log_group, logStreamNamePrefix=self.log_stream)
            streams = response.get("logStreams", [])
            if streams:
                self.sequence_token = streams[0].get("uploadSequenceToken")
        except ClientError:
            try:
                self.client.create_log_stream(logGroupName=self.log_group, logStreamName=self.log_stream)
            except ClientError as e:
                logging.getLogger(__name__).error(f"Failed to create log stream: {e}")

    def emit(self, record):
        if not self.client:
            return
        try:
            log_entry = {"timestamp": int(record.created * 1000), "message": self.format(record)}
            with self._buffer_lock:
                self.buffer.append(log_entry)
                if len(self.buffer) >= self.buffer_size or time.time() - self.last_flush >= self.flush_interval:
                    self._flush_buffer()
        except Exception as e:
            logging.getLogger(__name__).error(f"CloudWatch logging error: {e}")

    def _flush_buffer(self):
        if not self.client:
            return
        with self._buffer_lock:
            if not self.buffer:
                return
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    kwargs = {"logGroupName": self.log_group, "logStreamName": self.log_stream, "logEvents": self.buffer}
                    if self.sequence_token:
                        kwargs["sequenceToken"] = self.sequence_token
                    response = self.client.put_log_events(**kwargs)
                    self.sequence_token = response.get("nextSequenceToken")
                    self.buffer.clear()
                    self.last_flush = time.time()
                    break
                except ClientError as e:
                    logging.getLogger(__name__).warning(f"CloudWatch log delivery failed (attempt {attempt}): {e}")
                    if attempt == max_retries:
                        logging.getLogger(__name__).error(f"CloudWatch log delivery failed after {max_retries} attempts: {e}")
                    else:
                        time.sleep(2**attempt)


class ElasticsearchHandler(logging.Handler):
    def __init__(self, hosts: List[str], index_name: str = "ai-teddy-bear-logs", username: Optional[str] = None, password: Optional[str] = None):
        super().__init__()
        self.index_name = index_name
        self.client = None
        self.buffer = []
        self.buffer_size = 100
        self.flush_interval = 5.0
        self.last_flush = time.time()
        self._buffer_lock = threading.Lock()
        if ELASTICSEARCH_AVAILABLE:
            try:
                self.client = Elasticsearch(hosts, timeout=10, retry_on_timeout=True)
                if not self.client.ping():
                    logging.getLogger(__name__).warning("Elasticsearch connection failed")
                    self.client = None
                else:
                    self._ensure_index_exists()
            except Exception as e:
                error_msg = f"Elasticsearch logging disabled: {e}"
                logging.getLogger(__name__).warning(error_msg)
                if os.getenv("ENVIRONMENT") == "production":
                    StructuredLogger._critical_failures.append(f"Elasticsearch: {error_msg}")
                self.client = None

    def _ensure_index_exists(self):
        if not self.client:
            return
        index_mapping = {
            "mappings": {
                "properties": {
                    "timestamp": {"type": "date"},
                    "level": {"type": "keyword"},
                    "category": {"type": "keyword"},
                    "message": {"type": "text"},
                    "logger_name": {"type": "keyword"},
                    "context": {
                        "properties": {
                            "correlation_id": {"type": "keyword"},
                            "trace_id": {"type": "keyword"},
                            "user_id": {"type": "keyword"},
                            "child_id": {"type": "keyword"},
                            "session_id": {"type": "keyword"},
                            "operation": {"type": "keyword"},
                            "component": {"type": "keyword"},
                            "environment": {"type": "keyword"},
                            "region": {"type": "keyword"},
                        }
                    },
                    "duration_ms": {"type": "float"},
                    "error_details": {"type": "object"},
                    "performance_metrics": {"type": "object"},
                    "child_safety_flags": {"type": "object"},
                    "compliance_tags": {"type": "keyword"},
                }
            },
            "settings": {
                "number_of_shards": 2,
                "number_of_replicas": 1,
                "index.lifecycle.name": "ai-teddy-bear-logs-policy",
                "index.lifecycle.rollover_alias": self.index_name,
                "index.lifecycle.policy": {
                    "policy": {
                        "phases": {
                            "delete": {
                                "min_age": f"{os.getenv('LOG_RETENTION_DAYS', '30')}d"
                            }
                        }
                    }
                }
            },
        }
        try:
            if not self.client.indices.exists(index=self.index_name):
                self.client.indices.create(index=self.index_name, body=index_mapping)
        except Exception as e:
            logging.getLogger(__name__).error(f"Elasticsearch logging error: {e}")

    def emit(self, record):
        """Emit a log record to Elasticsearch."""
        if not self.client:
            return
        try:
            log_entry = {
                "_index": self.index_name,
                "_source": json.loads(self.format(record)) if self.format(record).startswith('{') else {"message": self.format(record), "timestamp": datetime.now(timezone.utc).isoformat()}
            }
            with self._buffer_lock:
                self.buffer.append(log_entry)
                if len(self.buffer) >= self.buffer_size or time.time() - self.last_flush >= self.flush_interval:
                    self._flush_buffer()
        except Exception as e:
            logging.getLogger(__name__).error(f"Elasticsearch logging error: {e}")

    def _flush_buffer(self):
        if not self.client:
            return
        with self._buffer_lock:
            if not self.buffer:
                return
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    bulk(self.client, self.buffer)
                    self.buffer.clear()
                    self.last_flush = time.time()
                    break
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Elasticsearch log delivery failed (attempt {attempt}): {e}")
                    if attempt == max_retries:
                        logging.getLogger(__name__).error(f"Elasticsearch log delivery failed after {max_retries} attempts: {e}")
                    else:
                        time.sleep(2**attempt)


class StructuredLogger:
    _production_handlers_required = []
    _critical_failures = []
    
    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self.name = name
        self.level = level
        self.logger = logging.getLogger(name)
        if not any(isinstance(f, SecurityFilter) for f in self.logger.filters):
            self.logger.addFilter(SecurityFilter())
        if not hasattr(self.logger, "_frozen_level"):
            self.logger.setLevel(getattr(logging, level.value))
            self.logger._frozen_level = level.value
        self.logger.handlers.clear()
        self._setup_console_handler()
        self._setup_file_handler()
        self._setup_cloudwatch_handler()
        self._setup_elasticsearch_handler()
        self._operation_start_times = {}
        self._validate_production_readiness()

    def _validate_production_readiness(self):
        """Validate critical logging infrastructure in production."""
        if os.getenv("ENVIRONMENT") == "production":
            if os.getenv("MULTIPROCESS_LOGGING") == "true" and not os.getenv("CENTRALIZED_LOGGING_AGENT"):
                self._critical_failures.append("Multi-process logging without centralized agent")
            SecurityFilter.validate_environment_security()
            if self._critical_failures:
                raise LoggingConfigurationError(f"Critical logging failures: {self._critical_failures}")
    
    @staticmethod
    def get_health_status() -> Dict[str, Any]:
        """Get health status of logging system."""
        is_healthy = len(StructuredLogger._critical_failures) == 0
        return {
            "healthy": is_healthy,
            "critical_failures": StructuredLogger._critical_failures,
            "security_filter_audit_count": len(SecurityFilter.get_audit_log()),
            "logger_registry_count": len(_LOGGER_REGISTRY),
            "available_integrations": {
                "boto3": BOTO3_AVAILABLE,
                "json_logger": JSON_LOGGER_AVAILABLE,
                "elasticsearch": ELASTICSEARCH_AVAILABLE,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    @staticmethod
    def is_production_ready() -> bool:
        """Check if logging system is ready for production."""
        return len(StructuredLogger._critical_failures) == 0

    def set_level(self, new_level: LogLevel):
        self.level = new_level
        self.logger.setLevel(getattr(logging, new_level.value))
        self.logger._frozen_level = new_level.value

    def _setup_console_handler(self):
        if not JSON_LOGGER_AVAILABLE:
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        else:
            formatter = jsonlogger.JsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def _setup_file_handler(self):
        log_dir = Path(os.getenv("LOG_DIR", "./logs"))
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{self.name}.log"
        file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=50 * 1024 * 1024, backupCount=10)
        if JSON_LOGGER_AVAILABLE:
            formatter = jsonlogger.JsonFormatter()
        else:
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _setup_cloudwatch_handler(self):
        log_group = os.getenv("CLOUDWATCH_LOG_GROUP")
        if log_group and BOTO3_AVAILABLE:
            log_stream = os.getenv("CLOUDWATCH_LOG_STREAM", f"{self.name}-{datetime.now().strftime('%Y-%m-%d')}")
            region = os.getenv("AWS_REGION", "us-east-1")
            cloudwatch_handler = CloudWatchHandler(log_group, log_stream, region)
            if JSON_LOGGER_AVAILABLE:
                formatter = jsonlogger.JsonFormatter()
            else:
                formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            cloudwatch_handler.setFormatter(formatter)
            self.logger.addHandler(cloudwatch_handler)

    def _setup_elasticsearch_handler(self):
        """Setup Elasticsearch handler if configured."""
        es_hosts = os.getenv("ELASTICSEARCH_HOSTS")
        if es_hosts and ELASTICSEARCH_AVAILABLE:
            hosts = es_hosts.split(",")
            username = os.getenv("ELASTICSEARCH_USERNAME")
            password = os.getenv("ELASTICSEARCH_PASSWORD")
            index_name = os.getenv("ELASTICSEARCH_INDEX", "ai-teddy-bear-logs")
            es_handler = ElasticsearchHandler(hosts, index_name, username, password)
            if JSON_LOGGER_AVAILABLE:
                formatter = jsonlogger.JsonFormatter()
            else:
                formatter = logging.Formatter("%(message)s")
            es_handler.setFormatter(formatter)
            self.logger.addHandler(es_handler)

    def _create_log_entry(self, level: LogLevel, category: LogCategory, message: str, **kwargs) -> LogEntry:
        """Create a structured log entry."""
        context = log_context.get() or LogContext(correlation_id=str(uuid4()))
        metadata = kwargs.pop("metadata", {})
        duration_ms = kwargs.pop("duration_ms", None)
        error_details = kwargs.pop("error_details", None)
        performance_metrics = kwargs.pop("performance_metrics", None)
        child_safety_flags = kwargs.pop("child_safety_flags", None)
        compliance_tags = kwargs.pop("compliance_tags", None)
        metadata.update(kwargs)
        metadata = SecurityFilter.sanitize_data(metadata)
        if error_details:
            error_details = SecurityFilter.sanitize_data(error_details)
        return LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level.value,
            category=category.value,
            message=SecurityFilter.sanitize_data(message),
            logger_name=self.name,
            context=context,
            metadata=metadata,
            duration_ms=duration_ms,
            error_details=error_details,
            performance_metrics=performance_metrics,
            child_safety_flags=child_safety_flags,
            compliance_tags=compliance_tags,
        )

    def _log(self, level: LogLevel, category: LogCategory, message: str, **kwargs):
        """Internal logging method."""
        log_entry = self._create_log_entry(level, category, message, **kwargs)
        log_data = asdict(log_entry)
        if level == LogLevel.TRACE:
            self.logger.debug(json.dumps(log_data))
        elif level == LogLevel.DEBUG:
            self.logger.debug(json.dumps(log_data))
        elif level == LogLevel.INFO:
            self.logger.info(json.dumps(log_data))
        elif level == LogLevel.WARNING:
            self.logger.warning(json.dumps(log_data))
        elif level == LogLevel.ERROR:
            self.logger.error(json.dumps(log_data))
        elif level == LogLevel.CRITICAL:
            self.logger.critical(json.dumps(log_data))
        elif level in [LogLevel.SECURITY, LogLevel.AUDIT, LogLevel.CHILD_SAFETY, LogLevel.COMPLIANCE]:
            self.logger.critical(json.dumps(log_data))

    def trace(self, message: str, category: LogCategory = LogCategory.APPLICATION, **kwargs):
        """Log trace message."""
        self._log(LogLevel.TRACE, category, message, **kwargs)

    def debug(self, message: str, category: LogCategory = LogCategory.APPLICATION, **kwargs):
        """Log debug message."""
        self._log(LogLevel.DEBUG, category, message, **kwargs)

    def info(self, message: str, category: LogCategory = LogCategory.APPLICATION, **kwargs):
        """Log info message."""
        self._log(LogLevel.INFO, category, message, **kwargs)

    def warning(self, message: str, category: LogCategory = LogCategory.APPLICATION, **kwargs):
        """Log warning message."""
        self._log(LogLevel.WARNING, category, message, **kwargs)

    def error(self, message: str, category: LogCategory = LogCategory.APPLICATION, error: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception details."""
        if error:
            kwargs["error_details"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
        self._log(LogLevel.ERROR, category, message, **kwargs)

    def critical(self, message: str, category: LogCategory = LogCategory.APPLICATION, error: Optional[Exception] = None, **kwargs):
        """Log critical message."""
        if error:
            kwargs["error_details"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
        self._log(LogLevel.CRITICAL, category, message, **kwargs)

    def security(self, message: str, **kwargs):
        """Log security-related message."""
        self._log(LogLevel.SECURITY, LogCategory.SECURITY, message, **kwargs)

    def audit(self, message: str, **kwargs):
        """Log audit message."""
        self._log(LogLevel.AUDIT, LogCategory.AUDIT, message, **kwargs)

    def child_safety(self, message: str, child_id: Optional[str] = None, safety_flags: Optional[Dict[str, Any]] = None, **kwargs):
        """Log child safety message."""
        if child_id:
            kwargs["child_id"] = child_id
        if safety_flags:
            kwargs["child_safety_flags"] = safety_flags
        self._log(LogLevel.CHILD_SAFETY, LogCategory.CHILD_SAFETY, message, **kwargs)

    def compliance(self, message: str, compliance_type: Optional[str] = None, tags: Optional[List[str]] = None, **kwargs):
        """Log compliance message."""
        if compliance_type:
            kwargs["compliance_type"] = compliance_type
        if tags:
            kwargs["compliance_tags"] = tags
        self._log(LogLevel.COMPLIANCE, LogCategory.COMPLIANCE, message, **kwargs)

    def start_operation(self, operation_name: str, **kwargs) -> str:
        """Start timing an operation."""
        operation_id = str(uuid4())
        self._operation_start_times[operation_id] = time.time()
        self.info(f"Operation started: {operation_name}", category=LogCategory.PERFORMANCE, operation=operation_name, operation_id=operation_id, **kwargs)
        return operation_id

    def end_operation(self, operation_id: str, operation_name: str, success: bool = True, **kwargs):
        """End timing an operation."""
        start_time = self._operation_start_times.pop(operation_id, None)
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
            level = LogLevel.INFO if success else LogLevel.WARNING
            self._log(level, LogCategory.PERFORMANCE, f"Operation {'completed' if success else 'failed'}: {operation_name}", operation=operation_name, operation_id=operation_id, duration_ms=duration_ms, success=success, **kwargs)


class LoggingContextManager:
    """Context manager for logging with correlation tracking."""

    def __init__(self, logger: StructuredLogger, operation: str, **context_kwargs):
        self.logger = logger
        self.operation = operation
        self.context_kwargs = context_kwargs
        self.operation_id = None
        self.start_time = None

    def __enter__(self):
        """Enter the context manager."""
        self.operation_id = self.logger.start_operation(self.operation, **self.context_kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        success = exc_type is None
        if self.operation_id:
            self.logger.end_operation(self.operation_id, self.operation, success=success)
        return False


# Thread-safe singleton logger registry
_LOGGER_REGISTRY = {}
_LOGGER_REGISTRY_LOCK = threading.Lock()


def get_logger(name: str, level: LogLevel = LogLevel.INFO) -> StructuredLogger:
    """Get or create a singleton structured logger by name."""
    with _LOGGER_REGISTRY_LOCK:
        if name in _LOGGER_REGISTRY:
            return _LOGGER_REGISTRY[name]
        logger = StructuredLogger(name, level)
        _LOGGER_REGISTRY[name] = logger
        return logger


# Pre-configured loggers for common components
http_logger = get_logger("http", LogLevel.INFO)
database_logger = get_logger("database", LogLevel.INFO)
cache_logger = get_logger("cache", LogLevel.INFO)
provider_logger = get_logger("provider", LogLevel.INFO)
security_logger = get_logger("security", LogLevel.WARNING)
child_safety_logger = get_logger("child_safety", LogLevel.INFO)
compliance_logger = get_logger("compliance", LogLevel.INFO)
performance_logger = get_logger("performance", LogLevel.INFO)
business_logger = get_logger("business", LogLevel.INFO)
system_logger = get_logger("system", LogLevel.INFO)
audit_logger = get_logger("audit", LogLevel.INFO)


def send_critical_alert(message: str, alert_type: str = "SECURITY"):
    """Send critical alert to external systems."""
    alert_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": alert_type,
        "message": message,
        "environment": os.getenv("ENVIRONMENT", "unknown")
    }
    logging.getLogger(__name__).critical(json.dumps(alert_data))
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if webhook_url:
        try:
            import requests
            requests.post(webhook_url, json=alert_data, timeout=5)
        except Exception:
            pass


def print_logging_health():
    import pprint
    pprint.pprint(StructuredLogger.get_health_status())


def export_security_audit_log(filepath=None):
    """Export SecurityFilter audit log to file or return as list."""
    audit_log = SecurityFilter.get_audit_log()
    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            for entry in audit_log:
                f.write(json.dumps(entry) + "\n")
    return audit_log


def check_audit_log_alert(threshold=100):
    """Alert if redaction/PII detection exceeds threshold."""
    count = len(SecurityFilter.get_audit_log())
    if count >= threshold:
        send_critical_alert(f"SecurityFilter redaction events exceeded threshold: {count}", "SECURITY_BREACH")
    return count
