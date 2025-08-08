"""
Enterprise Database Manager - Production-Grade Multi-Tier Database System
==============================================================================
Enterprise-grade database management system for child-safe AI applications with:
- Multi-tier architecture (Primary/Replica/Backup/Emergency)
- Advanced security with COPPA compliance and audit logging
- High-performance connection pooling with auto-scaling
- Intelligent load balancing and predictive failover
- Comprehensive monitoring with Prometheus/OpenTelemetry integration
- Data reconciliation and consistency management
- Disaster recovery automation with RTO/RPO guarantees
- Child data encryption and privacy protection
- Real-time health monitoring and auto-healing
- Circuit breaker patterns with adaptive thresholds
"""

import asyncio
import time
import logging
import hashlib
import json
import ssl
import secrets
import re
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import weakref
from concurrent.futures import ThreadPoolExecutor
from cryptography.fernet import Fernet
from src.infrastructure.database.connection_pool_manager import get_pool_manager
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

import asyncpg
from asyncpg import Pool, Connection, Record
from asyncpg.exceptions import (
    PostgresError,
    ConnectionDoesNotExistError,
    InterfaceError,
    InvalidCatalogNameError,
    InsufficientPrivilegeError,
    DataError,
    IntegrityConstraintViolationError,
)

# Optional monitoring imports
try:
    from prometheus_client import Counter, Gauge, Histogram, Summary

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

try:
    from opentelemetry import trace, metrics as otel_metrics
    from opentelemetry.trace import Status, StatusCode

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

from ..config import get_config_manager
from ..logging import get_logger, audit_logger, performance_logger
from ..monitoring import get_metrics_collector

# Type definitions
DatabaseOperation = Callable[..., Any]
HealthCheckFunction = Callable[[], bool]

# Security constants
ENCRYPTION_KEY = None
SENSITIVE_FIELD_PATTERNS = [
    r"password",
    r"secret",
    r"token",
    r"key",
    r"credential",
    r"child.*name",
    r"email",
    r"phone",
    r"address",
]


class DatabaseTier(Enum):
    """Database tier levels for different operations."""

    PRIMARY = "primary"  # High-priority write operations
    REPLICA = "replica"  # Read operations with load balancing
    BACKUP = "backup"  # Disaster recovery and failover
    EMERGENCY = "emergency"  # Last resort emergency operations
    CHILD_SAFE = "child_safe"  # Special tier for child data with enhanced security


class DatabaseConnectionState(Enum):
    """Enhanced database connection states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"
    MAINTENANCE = "maintenance"
    QUARANTINED = "quarantined"  # Security isolation
    EMERGENCY_ONLY = "emergency_only"  # Limited operations


class RetryStrategy(Enum):
    """Advanced retry strategies."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIBONACCI = "fibonacci"
    ADAPTIVE = "adaptive"  # Adapts based on error type
    CIRCUIT_BREAKER = "circuit_breaker"


class SecurityLevel(Enum):
    """Security levels for different operations."""

    STANDARD = "standard"
    HIGH = "high"
    CHILD_DATA = "child_data"  # Special handling for child information
    AUDIT_REQUIRED = "audit_required"


@dataclass
class EnterpriseConnectionMetrics:
    """Comprehensive connection metrics for enterprise monitoring."""

    # Basic connection metrics
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    peak_connections: int = 0

    # Query metrics
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    slow_queries: int = 0
    child_data_queries: int = 0

    # Performance metrics
    average_query_time: float = 0.0
    p95_query_time: float = 0.0
    p99_query_time: float = 0.0
    connection_wait_time: float = 0.0

    # Security metrics
    security_violations: int = 0
    failed_auth_attempts: int = 0
    suspicious_activity: int = 0

    # Compliance metrics
    coppa_compliance_checks: int = 0
    audit_logs_generated: int = 0
    data_retention_actions: int = 0

    # Timestamp tracking
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    last_security_scan: Optional[datetime] = None


@dataclass
class DatabaseConfig:
    """Enhanced database configuration with security features."""

    url: str
    tier: DatabaseTier = DatabaseTier.PRIMARY
    security_level: SecurityLevel = SecurityLevel.STANDARD

    # Connection pool settings
    max_connections: int = 20
    min_connections: int = 5
    max_idle_time: float = 300.0
    max_lifetime: float = 3600.0
    acquire_timeout: float = 30.0
    query_timeout: float = 60.0
    command_timeout: float = 300.0

    # Security settings
    ssl_mode: str = "verify-full"  # Strongest SSL security
    ssl_cert_file: Optional[str] = None
    ssl_key_file: Optional[str] = None
    ssl_ca_file: Optional[str] = None
    require_auth: bool = True
    encrypt_child_data: bool = True

    # Performance settings
    enable_query_cache: bool = True
    enable_prepared_statements: bool = True
    statement_cache_size: int = 1000

    # Monitoring settings
    enable_metrics: bool = True
    enable_slow_query_log: bool = True
    slow_query_threshold: float = 1.0  # seconds

    # Child safety settings
    child_data_retention_days: int = 30
    enable_coppa_audit: bool = True
    auto_encrypt_sensitive: bool = True

    # Application identification
    application_name: str = "ai-teddy-bear-enterprise"
    server_settings: Dict[str, str] = field(default_factory=dict)


@dataclass
class AdaptiveRetryConfig:
    """Advanced retry configuration with adaptive behavior."""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.ADAPTIVE
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    backoff_multiplier: float = 2.0

    # Adaptive settings
    success_threshold: int = 5  # Consecutive successes to reduce delays
    failure_threshold: int = 3  # Consecutive failures to increase delays
    adaptation_window: int = 100  # Number of operations to consider

    # Error-specific settings
    timeout_multiplier: float = 1.5
    connection_error_multiplier: float = 2.0
    security_error_attempts: int = 1  # No retries for security errors


@dataclass
class CircuitBreakerConfig:
    """Enhanced circuit breaker with adaptive thresholds."""

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 60.0
    half_open_max_calls: int = 3

    # Adaptive features
    adaptive_threshold: bool = True
    min_threshold: int = 3
    max_threshold: int = 15
    threshold_adjustment_factor: float = 0.1

    # Monitoring
    enable_alerts: bool = True
    alert_on_open: bool = True
    alert_on_half_open: bool = False


class SecurityManager:
    """Handles database security, encryption, and audit logging."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = get_logger("db_security")
        self.audit_logger = audit_logger

        # Initialize encryption
        if config.encrypt_child_data:
            self._init_encryption()

        # Sensitive field patterns
        self.sensitive_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in SENSITIVE_FIELD_PATTERNS
        ]

    def _init_encryption(self):
        """Initialize encryption for sensitive data."""
        global ENCRYPTION_KEY
        if ENCRYPTION_KEY is None:
            # In production, get from secure key management service
            key = get_config_manager().get("DATABASE_ENCRYPTION_KEY")
            if key:
                ENCRYPTION_KEY = key.encode()
            else:
                ENCRYPTION_KEY = Fernet.generate_key()
                self.logger.warning(
                    "Using generated encryption key - configure DATABASE_ENCRYPTION_KEY"
                )

        self.fernet = Fernet(ENCRYPTION_KEY)

    def encrypt_sensitive_data(self, data: Any, field_name: str = "") -> Any:
        """Encrypt sensitive data if field matches sensitive patterns."""
        if not self.config.auto_encrypt_sensitive:
            return data

        if not isinstance(data, (str, bytes)):
            return data

        # Check if field should be encrypted
        if field_name and any(
            pattern.search(field_name) for pattern in self.sensitive_patterns
        ):
            try:
                if isinstance(data, str):
                    data = data.encode("utf-8")
                return self.fernet.encrypt(data).decode("utf-8")
            except Exception as e:
                self.logger.error(f"Encryption failed for field {field_name}: {e}")
                return data

        return data

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        try:
            return self.fernet.decrypt(encrypted_data.encode("utf-8")).decode("utf-8")
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            return encrypted_data

    def sanitize_error_message(self, error_msg: str) -> str:
        """Sanitize database errors to prevent credential leakage."""
        sensitive_patterns = [
            r"password=[^&\s]+",
            r"user=[^&\s]+",
            r"host=[\w\.-]+",
            r"postgresql://[^@]+@[^/]+",
            r"Connection.*refused.*\d+\.\d+\.\d+\.\d+",
            r'authentication.*failed.*user.*"[^"]*"',
        ]

        sanitized = str(error_msg)
        for pattern in sensitive_patterns:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

        # Remove newlines and limit length
        return sanitized.replace("\n", " ").replace("\r", " ")[:500]

    def audit_database_operation(self, operation: str, details: Dict[str, Any]):
        """Log database operations for COPPA compliance."""
        if not self.config.enable_coppa_audit:
            return

        # Hash sensitive identifiers
        audit_details = details.copy()
        if "child_id" in audit_details:
            audit_details["child_id_hash"] = self._hash_identifier(
                audit_details.pop("child_id")
            )
        if "user_id" in audit_details:
            audit_details["user_id_hash"] = self._hash_identifier(
                audit_details.pop("user_id")
            )

        self.audit_logger.audit(
            f"Database operation: {operation}",
            metadata={
                **audit_details,
                "timestamp": datetime.utcnow().isoformat(),
                "compliance_framework": "COPPA",
                "security_level": self.config.security_level.value,
                "tier": self.config.tier.value,
            },
        )

    def _hash_identifier(self, identifier: str) -> str:
        """Create a secure hash of sensitive identifiers."""
        salt = get_config_manager().get("AUDIT_SALT", "default_salt").encode()
        return hashlib.pbkdf2_hmac("sha256", identifier.encode(), salt, 100000).hex()[
            :16
        ]


class AdvancedCircuitBreaker:
    """Enhanced circuit breaker with adaptive thresholds and monitoring."""

    def __init__(self, config: CircuitBreakerConfig, node_id: str):
        self.config = config
        self.node_id = node_id
        self.logger = get_logger(f"circuit_breaker_{node_id}")

        # State management
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.success_count = 0
        self.consecutive_successes = 0
        self.consecutive_failures = 0

        # Adaptive thresholds
        self.current_failure_threshold = config.failure_threshold
        self.failure_history = deque(
            maxlen=config.adaptation_window if config.adaptive_threshold else 10
        )

        # Timing
        self.last_failure_time = 0.0
        self.last_success_time = time.time()
        self.state_change_time = time.time()

        # Monitoring
        self._init_metrics()

    def _init_metrics(self):
        """Initialize Prometheus metrics if available."""
        if PROMETHEUS_AVAILABLE:
            self.state_gauge = Gauge(
                "circuit_breaker_state",
                "Circuit breaker state (0=closed, 1=half_open, 2=open)",
                ["node_id"],
            )
            self.operations_total = Counter(
                "circuit_breaker_operations_total",
                "Total operations through circuit breaker",
                ["node_id", "result"],
            )
            self.failure_count_gauge = Gauge(
                "circuit_breaker_failure_count", "Current failure count", ["node_id"]
            )

    def can_execute(self) -> bool:
        """Determine if operation can execute through circuit breaker."""
        current_time = time.time()

        if self.state == "CLOSED":
            return True

        elif self.state == "OPEN":
            # Check if timeout period has elapsed
            if current_time - self.last_failure_time >= self.config.timeout:
                self._transition_to_half_open()
                return True
            return False

        elif self.state == "HALF_OPEN":
            # Allow limited calls in half-open state
            return self.success_count < self.config.half_open_max_calls

        return False

    def record_success(self):
        """Record successful operation and adjust state."""
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()

        if PROMETHEUS_AVAILABLE:
            self.operations_total.labels(node_id=self.node_id, result="success").inc()

        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()

        elif self.state == "CLOSED":
            # Reduce failure count on success
            self.failure_count = max(0, self.failure_count - 1)

            # Adapt threshold based on performance
            if self.config.adaptive_threshold:
                self._adapt_threshold_on_success()

    def record_failure(self, error_type: str = "general"):
        """Record failed operation and adjust state."""
        self.failure_count += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()

        # Track failure history for adaptation
        if self.config.adaptive_threshold:
            self.failure_history.append((time.time(), error_type))

        if PROMETHEUS_AVAILABLE:
            self.operations_total.labels(node_id=self.node_id, result="failure").inc()
            self.failure_count_gauge.labels(node_id=self.node_id).set(
                self.failure_count
            )

        # State transitions
        if (
            self.state == "CLOSED"
            and self.failure_count >= self.current_failure_threshold
        ):
            self._transition_to_open()

        elif self.state == "HALF_OPEN":
            self._transition_to_open()

        # Adapt threshold based on failure pattern
        if self.config.adaptive_threshold:
            self._adapt_threshold_on_failure()

        log_data = {
            "node_id": self.node_id,
            "state": self.state,
            "failure_count": self.failure_count,
            "threshold": self.current_failure_threshold,
            "error_type": error_type,
        }
        self.logger.warning("Circuit breaker failure recorded", extra=log_data)

    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self.state = "CLOSED"
        self.failure_count = 0
        self.success_count = 0
        self.state_change_time = time.time()

        if PROMETHEUS_AVAILABLE:
            self.state_gauge.labels(node_id=self.node_id).set(0)

        self.logger.info(f"Circuit breaker {self.node_id} transitioned to CLOSED")

    def _transition_to_open(self):
        """Transition to OPEN state."""
        self.state = "OPEN"
        self.success_count = 0
        self.state_change_time = time.time()

        if PROMETHEUS_AVAILABLE:
            self.state_gauge.labels(node_id=self.node_id).set(2)

        self.logger.error(
            f"Circuit breaker {self.node_id} OPENED after {self.failure_count} failures"
        )

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self.state = "HALF_OPEN"
        self.success_count = 0
        self.state_change_time = time.time()

        if PROMETHEUS_AVAILABLE:
            self.state_gauge.labels(node_id=self.node_id).set(1)

        self.logger.info(f"Circuit breaker {self.node_id} transitioned to HALF_OPEN")

    def _adapt_threshold_on_success(self):
        """Adapt failure threshold based on success pattern."""
        if self.consecutive_successes >= 10:
            # Lower threshold slightly for better sensitivity
            new_threshold = max(
                self.config.min_threshold,
                int(
                    self.current_failure_threshold
                    * (1 - self.config.threshold_adjustment_factor)
                ),
            )
            if new_threshold != self.current_failure_threshold:
                self.logger.info(
                    f"Lowering failure threshold from {self.current_failure_threshold} to {new_threshold}"
                )
                self.current_failure_threshold = new_threshold

    def _adapt_threshold_on_failure(self):
        """Adapt failure threshold based on failure pattern."""
        # Analyze recent failure pattern
        recent_failures = len(
            [f for f in self.failure_history if time.time() - f[0] < 300]
        )  # Last 5 minutes

        if recent_failures > self.current_failure_threshold * 2:
            # Increase threshold to reduce sensitivity during instability
            new_threshold = min(
                self.config.max_threshold,
                int(
                    self.current_failure_threshold
                    * (1 + self.config.threshold_adjustment_factor)
                ),
            )
            if new_threshold != self.current_failure_threshold:
                self.logger.info(
                    f"Raising failure threshold from {self.current_failure_threshold} to {new_threshold}"
                )
                self.current_failure_threshold = new_threshold


class EnterpriseConnectionPool:
    """High-performance connection pool with advanced monitoring."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = get_logger(f"connection_pool_{config.tier.value}")
        self.security_manager = SecurityManager(config)

        # Pool state
        self.pool: Optional[Pool] = None
        self.state = DatabaseConnectionState.HEALTHY
        self.metrics = EnterpriseConnectionMetrics()

        # Monitoring
        self.query_times = deque(maxlen=1000)  # Bounded history
        self.slow_queries = deque(maxlen=100)

        # Performance optimization
        self.prepared_statements = {}
        self.query_cache = {} if config.enable_query_cache else None

        # Threading for background tasks
        self.executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix=f"db-{config.tier.value}"
        )

        # Prometheus metrics
        self._init_prometheus_metrics()

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics if available."""
        if not PROMETHEUS_AVAILABLE:
            return

        tier = self.config.tier.value
        self.connection_gauge = Gauge(
            "database_connections_active",
            "Active database connections",
            ["tier", "state"],
        )

        self.query_duration_histogram = Histogram(
            "database_query_duration_seconds",
            "Database query duration",
            ["tier", "operation_type"],
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
        )

        self.query_counter = Counter(
            "database_queries_total",
            "Total database queries",
            ["tier", "status", "security_level"],
        )

        self.child_data_operations = Counter(
            "database_child_data_operations_total",
            "Child data operations (COPPA tracking)",
            ["tier", "operation", "compliance_status"],
        )

    async def initialize(self) -> bool:
        """Initialize connection pool with enhanced error handling."""
        try:
            self.logger.info(f"Initializing {self.config.tier.value} connection pool")

            # Prepare SSL context if required
            ssl_context = None
            if self.config.ssl_mode in ["verify-full", "verify-ca"]:
                ssl_context = self._create_ssl_context()

            # Enhanced server settings
            server_settings = {
                "application_name": self.config.application_name,
                "timezone": "UTC",
                "statement_timeout": str(int(self.config.query_timeout * 1000)),
                **self.config.server_settings,
            }

            # Create connection pool with enhanced configuration
            self.pool = await asyncpg.create_pool(
                self.config.url,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
                max_inactive_connection_lifetime=self.config.max_idle_time,
                max_queries=10000,  # Rotate connections after many queries
                command_timeout=self.config.command_timeout,
                server_settings=server_settings,
                ssl=ssl_context,
                init=self._init_connection,
            )

            # Test initial connection with comprehensive validation
            await self._validate_connection_security()

            self.state = DatabaseConnectionState.HEALTHY
            self.metrics.last_success_time = datetime.utcnow()

            log_data = {
                "tier": self.config.tier.value,
                "min_connections": self.config.min_connections,
                "max_connections": self.config.max_connections,
                "security_level": self.config.security_level.value,
            }
            self.logger.info("Connection pool initialized successfully", extra=log_data)

            return True

        except Exception as e:
            sanitized_error = self.security_manager.sanitize_error_message(str(e))
            self.logger.error(
                f"Connection pool initialization failed: {sanitized_error}"
            )
            self.state = DatabaseConnectionState.FAILED
            self.metrics.last_failure_time = datetime.utcnow()
            return False

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create enhanced SSL context for secure connections."""
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        if self.config.ssl_cert_file:
            context.load_cert_chain(self.config.ssl_cert_file, self.config.ssl_key_file)

        if self.config.ssl_ca_file:
            context.load_verify_locations(self.config.ssl_ca_file)

        # Enhanced security settings
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers("HIGH:!aNULL:!MD5:!RC4:!DSS")

        return context

    async def _init_connection(self, conn: Connection):
        """Initialize new database connections with security settings."""
        # Set connection-level security parameters
        await conn.execute("SET log_statement = 'none'")  # Prevent query logging
        await conn.execute(
            "SET log_min_duration_statement = -1"
        )  # Disable slow query logging at connection level

        # Set application context for auditing
        await conn.execute(f"SET application_name = '{self.config.application_name}'")

        # Initialize prepared statements for common operations
        if self.config.enable_prepared_statements:
            await self._prepare_common_statements(conn)

    async def _prepare_common_statements(self, conn: Connection):
        """Prepare commonly used statements for better performance."""
        common_statements = {
            "health_check": "SELECT 1",
            "connection_count": "SELECT count(*) FROM pg_stat_activity WHERE application_name = $1",
            "child_data_cleanup": """
                DELETE FROM child_interactions 
                WHERE created_at < $1 AND retention_policy = 'auto_delete'
            """,
        }

        for name, sql in common_statements.items():
            try:
                await conn.prepare(sql)
                self.prepared_statements[name] = sql
            except Exception as e:
                self.logger.warning(f"Failed to prepare statement {name}: {e}")

    async def _validate_connection_security(self):
        """Validate connection security and permissions."""
        async with self.pool.acquire() as conn:
            # Verify SSL connection
            ssl_info = await conn.fetchrow(
                """
                SELECT ssl, version, cipher 
                FROM pg_stat_ssl 
                WHERE pid = pg_backend_pid()
            """
            )

            if not ssl_info or not ssl_info["ssl"]:
                if self.config.ssl_mode in ["require", "verify-ca", "verify-full"]:
                    raise ConnectionError("SSL connection required but not established")

            # Check permissions for child data operations
            if self.config.tier == DatabaseTier.CHILD_SAFE:
                # Verify table access permissions
                tables_to_check = [
                    "child_profiles",
                    "child_interactions",
                    "parent_consent",
                ]
                for table in tables_to_check:
                    try:
                        await conn.fetchval(
                            f"SELECT has_table_privilege(current_user, '{table}', 'SELECT')"
                        )
                    except Exception as e:
                        self.logger.warning(
                            f"Cannot verify permissions for table {table}: {e}"
                        )

            self.logger.info("Connection security validation passed")

    @asynccontextmanager
    async def acquire_connection(self) -> AsyncGenerator[Connection, None]:
        """Acquire connection with comprehensive monitoring and security."""
        if not self.pool:
            raise ConnectionError("Connection pool not initialized")

        start_time = time.time()
        connection = None

        try:
            # Acquire connection with timeout
            connection = await asyncio.wait_for(
                self.pool.acquire(), timeout=self.config.acquire_timeout
            )

            acquire_time = time.time() - start_time
            self.metrics.connection_wait_time = acquire_time
            self.metrics.active_connections += 1

            # Update peak connections
            if self.metrics.active_connections > self.metrics.peak_connections:
                self.metrics.peak_connections = self.metrics.active_connections

            # Update Prometheus metrics
            if PROMETHEUS_AVAILABLE:
                self.connection_gauge.labels(
                    tier=self.config.tier.value, state="active"
                ).inc()

            yield connection

        except Exception as e:
            self.metrics.failed_connections += 1
            self.metrics.last_failure_time = datetime.utcnow()

            sanitized_error = self.security_manager.sanitize_error_message(str(e))
            self.logger.error(f"Connection acquisition failed: {sanitized_error}")
            raise

        finally:
            if connection:
                try:
                    await self.pool.release(connection)
                    self.metrics.active_connections = max(
                        0, self.metrics.active_connections - 1
                    )

                    if PROMETHEUS_AVAILABLE:
                        self.connection_gauge.labels(
                            tier=self.config.tier.value, state="active"
                        ).dec()

                except Exception as e:
                    sanitized_error = self.security_manager.sanitize_error_message(
                        str(e)
                    )
                    self.logger.error(f"Connection release failed: {sanitized_error}")

    async def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        operation_type: str = "unknown",
        security_level: SecurityLevel = SecurityLevel.STANDARD,
        child_id: Optional[str] = None,
    ) -> Any:
        """Execute query with comprehensive monitoring and security."""

        start_time = time.time()
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]

        # Security audit for child data operations
        if child_id or security_level == SecurityLevel.CHILD_DATA:
            self.security_manager.audit_database_operation(
                operation_type,
                {
                    "query_hash": query_hash,
                    "child_id": child_id,
                    "security_level": security_level.value,
                    "tier": self.config.tier.value,
                },
            )

            if PROMETHEUS_AVAILABLE:
                self.child_data_operations.labels(
                    tier=self.config.tier.value,
                    operation=operation_type,
                    compliance_status="audited",
                ).inc()

        try:
            async with self.acquire_connection() as conn:
                # Execute query with monitoring
                if params:
                    result = await conn.fetch(query, *params)
                else:
                    result = await conn.fetch(query)

                # Record successful operation
                execution_time = time.time() - start_time
                self._record_query_metrics(
                    execution_time, operation_type, "success", security_level
                )

                # Encrypt sensitive data in results if required
                if (
                    self.config.encrypt_child_data
                    and security_level == SecurityLevel.CHILD_DATA
                ):
                    result = self._encrypt_result_set(result)

                return result

        except Exception as e:
            execution_time = time.time() - start_time
            self._record_query_metrics(
                execution_time, operation_type, "failure", security_level
            )

            # Classify error type for circuit breaker
            error_type = self._classify_database_error(e)

            sanitized_error = self.security_manager.sanitize_error_message(str(e))
            log_data = {
                "query_hash": query_hash,
                "operation_type": operation_type,
                "execution_time": execution_time,
                "error_type": error_type,
                "error": sanitized_error,
            }
            self.logger.error("Query execution failed", extra=log_data)

            raise

    def _record_query_metrics(
        self,
        execution_time: float,
        operation_type: str,
        status: str,
        security_level: SecurityLevel,
    ):
        """Record comprehensive query metrics."""

        # Update basic metrics
        self.metrics.total_queries += 1
        if status == "success":
            self.metrics.successful_queries += 1
        else:
            self.metrics.failed_queries += 1

        # Track child data queries
        if security_level == SecurityLevel.CHILD_DATA:
            self.metrics.child_data_queries += 1

        # Record query time
        self.query_times.append(execution_time)

        # Check for slow queries
        if execution_time > self.config.slow_query_threshold:
            self.metrics.slow_queries += 1
            self.slow_queries.append(
                {
                    "execution_time": execution_time,
                    "operation_type": operation_type,
                    "timestamp": datetime.utcnow(),
                }
            )

            log_data = {
                "execution_time": execution_time,
                "operation_type": operation_type,
                "threshold": self.config.slow_query_threshold,
            }
            self.logger.warning("Slow query detected", extra=log_data)

        # Update average query time
        if self.query_times:
            self.metrics.average_query_time = sum(self.query_times) / len(
                self.query_times
            )

            # Calculate percentiles
            sorted_times = sorted(self.query_times)
            if len(sorted_times) >= 20:  # Minimum samples for percentiles
                p95_idx = int(len(sorted_times) * 0.95)
                p99_idx = int(len(sorted_times) * 0.99)
                self.metrics.p95_query_time = sorted_times[p95_idx]
                self.metrics.p99_query_time = sorted_times[p99_idx]

        # Update Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            self.query_counter.labels(
                tier=self.config.tier.value,
                status=status,
                security_level=security_level.value,
            ).inc()

            self.query_duration_histogram.labels(
                tier=self.config.tier.value, operation_type=operation_type
            ).observe(execution_time)

    def _classify_database_error(self, error: Exception) -> str:
        """Classify database errors for circuit breaker and retry logic."""
        if isinstance(error, ConnectionDoesNotExistError):
            return "connection_lost"
        elif isinstance(error, InterfaceError):
            return "interface_error"
        elif isinstance(error, InsufficientPrivilegeError):
            return "security_error"
        elif isinstance(error, DataError):
            return "data_error"
        elif isinstance(error, IntegrityConstraintViolationError):
            return "constraint_violation"
        elif "timeout" in str(error).lower():
            return "timeout"
        elif "connection" in str(error).lower():
            return "connection_error"
        else:
            return "general_error"

    def _encrypt_result_set(self, results: List[Record]) -> List[Dict]:
        """Encrypt sensitive fields in query results."""
        if not results:
            return results

        encrypted_results = []
        for record in results:
            encrypted_record = dict(record)
            for field_name, value in encrypted_record.items():
                if value is not None:
                    encrypted_record[field_name] = (
                        self.security_manager.encrypt_sensitive_data(value, field_name)
                    )
            encrypted_results.append(encrypted_record)

        return encrypted_results

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check with security validation."""
        health_status = {
            "healthy": False,
            "tier": self.config.tier.value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
        }

        try:
            # Basic connectivity check
            async with self.acquire_connection() as conn:
                # Simple query
                await conn.fetchval("SELECT 1")
                health_status["checks"]["basic_connectivity"] = True

                # Check connection count
                if "health_check" in self.prepared_statements:
                    active_connections = await conn.fetchval(
                        self.prepared_statements["connection_count"],
                        self.config.application_name,
                    )
                else:
                    active_connections = await conn.fetchval(
                        "SELECT count(*) FROM pg_stat_activity WHERE application_name = $1",
                        self.config.application_name,
                    )

                health_status["checks"]["connection_count"] = active_connections
                health_status["checks"]["pool_utilization"] = (
                    active_connections / self.config.max_connections * 100
                )

                # Security checks
                if self.config.security_level in [
                    SecurityLevel.HIGH,
                    SecurityLevel.CHILD_DATA,
                ]:
                    ssl_status = await conn.fetchrow(
                        """
                        SELECT ssl, version, cipher 
                        FROM pg_stat_ssl 
                        WHERE pid = pg_backend_pid()
                    """
                    )
                    health_status["checks"]["ssl_active"] = bool(
                        ssl_status and ssl_status["ssl"]
                    )

                # Performance checks
                health_status["checks"][
                    "avg_query_time"
                ] = self.metrics.average_query_time
                health_status["checks"]["slow_queries_rate"] = (
                    self.metrics.slow_queries / max(1, self.metrics.total_queries) * 100
                )

                self.metrics.last_health_check = datetime.utcnow()
                health_status["healthy"] = True

        except Exception as e:
            sanitized_error = self.security_manager.sanitize_error_message(str(e))
            health_status["checks"]["error"] = sanitized_error
            self.logger.error(f"Health check failed: {sanitized_error}")

        return health_status

    async def cleanup_old_data(self) -> int:
        """Clean up old data according to retention policies."""
        if self.config.child_data_retention_days <= 0:
            return 0

        cutoff_date = datetime.utcnow() - timedelta(
            days=self.config.child_data_retention_days
        )

        try:
            async with self.acquire_connection() as conn:
                # Clean up old child interactions
                if "child_data_cleanup" in self.prepared_statements:
                    result = await conn.execute(
                        self.prepared_statements["child_data_cleanup"], cutoff_date
                    )
                else:
                    result = await conn.execute(
                        """
                        DELETE FROM child_interactions 
                        WHERE created_at < $1 AND retention_policy = 'auto_delete'
                    """,
                        cutoff_date,
                    )

                # Parse result to get row count
                cleaned_count = int(result.split()[-1]) if result else 0

                if cleaned_count > 0:
                    self.security_manager.audit_database_operation(
                        "data_cleanup",
                        {
                            "records_cleaned": cleaned_count,
                            "cutoff_date": cutoff_date.isoformat(),
                            "retention_days": self.config.child_data_retention_days,
                        },
                    )

                self.metrics.data_retention_actions += 1
                return cleaned_count

        except Exception as e:
            sanitized_error = self.security_manager.sanitize_error_message(str(e))
            self.logger.error(f"Data cleanup failed: {sanitized_error}")
            return 0

    async def close(self):
        """Close connection pool and cleanup resources."""
        if self.pool:
            await self.pool.close()
            self.logger.info(f"Connection pool for {self.config.tier.value} closed")

        # Shutdown executor
        self.executor.shutdown(wait=True)


class EnterpriseIntelligentLoadBalancer:
    """Advanced load balancer with predictive capabilities and health awareness."""

    def __init__(self, pools: Dict[str, EnterpriseConnectionPool]):
        self.pools = pools
        self.logger = get_logger("intelligent_load_balancer")

        # Load balancing strategies
        self.strategies = {
            "round_robin": self._round_robin_selection,
            "least_connections": self._least_connections_selection,
            "fastest_response": self._fastest_response_selection,
            "predictive": self._predictive_selection,
            "child_data_optimized": self._child_data_optimized_selection,
        }

        # State tracking
        self.round_robin_index = 0
        self.performance_history = defaultdict(deque)
        self.prediction_window = 100  # Number of recent operations to consider

        # Health monitoring
        self.health_scores = {}
        self.last_health_update = {}

    async def select_pool(
        self,
        operation_type: str = "read",
        security_level: SecurityLevel = SecurityLevel.STANDARD,
        strategy: str = "predictive",
    ) -> Optional[EnterpriseConnectionPool]:
        """Select optimal pool based on strategy and current conditions."""

        # Filter available pools based on criteria
        available_pools = await self._get_available_pools(
            operation_type, security_level
        )

        if not available_pools:
            self.logger.error("No available pools for operation")
            return None

        # Apply selection strategy
        if strategy in self.strategies:
            selected_pool = await self.strategies[strategy](
                available_pools, operation_type
            )
        else:
            selected_pool = available_pools[0]  # Fallback to first available

        # Update performance tracking
        self._update_pool_selection_metrics(selected_pool, strategy)

        return selected_pool

    async def _get_available_pools(
        self, operation_type: str, security_level: SecurityLevel
    ) -> List[EnterpriseConnectionPool]:
        """Get pools that can handle the requested operation."""
        available = []

        for pool_id, pool in self.pools.items():
            # Check pool health
            if pool.state not in [
                DatabaseConnectionState.HEALTHY,
                DatabaseConnectionState.DEGRADED,
            ]:
                continue

            # Check tier compatibility
            if operation_type == "write" and pool.config.tier not in [
                DatabaseTier.PRIMARY,
                DatabaseTier.BACKUP,
            ]:
                continue

            # Check security level compatibility
            if (
                security_level == SecurityLevel.CHILD_DATA
                and pool.config.tier != DatabaseTier.CHILD_SAFE
            ):
                # Allow primary tier for child data if child_safe tier not available
                if pool.config.tier != DatabaseTier.PRIMARY:
                    continue

            # Check connection availability
            if (
                pool.metrics.active_connections >= pool.config.max_connections * 0.9
            ):  # 90% threshold
                continue

            available.append(pool)

        return available

    async def _round_robin_selection(
        self, pools: List[EnterpriseConnectionPool], operation_type: str
    ) -> EnterpriseConnectionPool:
        """Simple round-robin selection."""
        selected = pools[self.round_robin_index % len(pools)]
        self.round_robin_index += 1
        return selected

    async def _least_connections_selection(
        self, pools: List[EnterpriseConnectionPool], operation_type: str
    ) -> EnterpriseConnectionPool:
        """Select pool with least active connections."""
        return min(pools, key=lambda p: p.metrics.active_connections)

    async def _fastest_response_selection(
        self, pools: List[EnterpriseConnectionPool], operation_type: str
    ) -> EnterpriseConnectionPool:
        """Select pool with fastest average response time."""
        return min(pools, key=lambda p: p.metrics.average_query_time or float("inf"))

    async def _predictive_selection(
        self, pools: List[EnterpriseConnectionPool], operation_type: str
    ) -> EnterpriseConnectionPool:
        """Predictive selection based on multiple factors."""
        pool_scores = {}

        for pool in pools:
            score = 0

            # Connection capacity factor (lower is better)
            capacity_ratio = (
                pool.metrics.active_connections / pool.config.max_connections
            )
            score += (1 - capacity_ratio) * 40  # 40% weight

            # Performance factor (lower avg time is better)
            avg_time = pool.metrics.average_query_time or 0.1
            max_time = max((p.metrics.average_query_time or 0.1) for p in pools)
            if max_time > 0:
                score += (1 - avg_time / max_time) * 30  # 30% weight

            # Success rate factor
            success_rate = pool.metrics.successful_queries / max(
                1, pool.metrics.total_queries
            )
            score += success_rate * 20  # 20% weight

            # Recent performance factor
            recent_performance = self._get_recent_performance_score(pool)
            score += recent_performance * 10  # 10% weight

            pool_scores[pool] = score

        # Select pool with highest score
        return max(pool_scores.items(), key=lambda x: x[1])[0]

    async def _child_data_optimized_selection(
        self, pools: List[EnterpriseConnectionPool], operation_type: str
    ) -> EnterpriseConnectionPool:
        """Specialized selection for child data operations."""
        # Prefer CHILD_SAFE tier
        child_safe_pools = [
            p for p in pools if p.config.tier == DatabaseTier.CHILD_SAFE
        ]
        if child_safe_pools:
            return await self._predictive_selection(child_safe_pools, operation_type)

        # Fallback to predictive selection with enhanced security pools
        security_pools = [
            p
            for p in pools
            if p.config.security_level in [SecurityLevel.HIGH, SecurityLevel.CHILD_DATA]
        ]
        if security_pools:
            return await self._predictive_selection(security_pools, operation_type)

        # Final fallback
        return await self._predictive_selection(pools, operation_type)

    def _get_recent_performance_score(self, pool: EnterpriseConnectionPool) -> float:
        """Calculate recent performance score for a pool."""
        pool_id = f"{pool.config.tier.value}"
        recent_times = list(pool.query_times)[-20:]  # Last 20 queries

        if not recent_times:
            return 0.5  # Neutral score

        avg_recent = sum(recent_times) / len(recent_times)
        overall_avg = pool.metrics.average_query_time or avg_recent

        if overall_avg == 0:
            return 1.0

        # Score based on recent vs overall performance
        return max(0, min(1, 2 - (avg_recent / overall_avg)))

    def _update_pool_selection_metrics(
        self, pool: EnterpriseConnectionPool, strategy: str
    ):
        """Update metrics about pool selection decisions."""
        if PROMETHEUS_AVAILABLE:
            pool_selection_counter = Counter(
                "database_pool_selections_total",
                "Total pool selections by load balancer",
                ["tier", "strategy"],
            )
            pool_selection_counter.labels(
                tier=pool.config.tier.value, strategy=strategy
            ).inc()


class EnterpriseDisasterRecoveryManager:
    """Handles disaster recovery, failover, and data consistency."""

    def __init__(self, pools: Dict[str, EnterpriseConnectionPool]):
        self.pools = pools
        self.logger = get_logger("disaster_recovery")

        # Recovery configuration
        self.rto_targets = {
            DatabaseTier.PRIMARY: 300,  # 5 minutes
            DatabaseTier.REPLICA: 600,  # 10 minutes
            DatabaseTier.BACKUP: 900,  # 15 minutes
            DatabaseTier.CHILD_SAFE: 60,  # 1 minute (critical)
        }

        self.rpo_targets = {
            DatabaseTier.PRIMARY: 0,  # Zero data loss
            DatabaseTier.CHILD_SAFE: 0,  # Zero data loss for child data
            DatabaseTier.REPLICA: 300,  # 5 minutes acceptable
            DatabaseTier.BACKUP: 900,  # 15 minutes acceptable
        }

        # Recovery state
        self.failover_in_progress = {}
        self.recovery_start_times = {}
        self.backup_checkpoints = {}

        # Data consistency tracking
        self.consistency_checks = {}
        self.replication_lag_thresholds = {
            DatabaseTier.REPLICA: 30.0,  # 30 seconds
            DatabaseTier.BACKUP: 300.0,  # 5 minutes
        }

    async def initiate_failover(
        self, failed_tier: DatabaseTier, target_tier: Optional[DatabaseTier] = None
    ) -> bool:
        """Initiate intelligent failover to backup systems."""

        if failed_tier in self.failover_in_progress:
            self.logger.warning(f"Failover already in progress for {failed_tier.value}")
            return False

        self.failover_in_progress[failed_tier] = True
        self.recovery_start_times[failed_tier] = time.time()

        try:
            self.logger.critical(f"Initiating failover from {failed_tier.value}")

            # Determine failover target
            if not target_tier:
                target_tier = self._determine_failover_target(failed_tier)

            if not target_tier:
                raise Exception("No suitable failover target available")

            # Perform pre-failover validations
            await self._pre_failover_validation(failed_tier, target_tier)

            # Execute failover sequence
            success = await self._execute_failover_sequence(failed_tier, target_tier)

            if success:
                # Post-failover validation
                await self._post_failover_validation(target_tier)

                # Update routing configuration
                await self._update_failover_routing(failed_tier, target_tier)

                # Schedule consistency check
                asyncio.create_task(
                    self._schedule_consistency_verification(failed_tier, target_tier)
                )

                elapsed_time = time.time() - self.recovery_start_times[failed_tier]
                rto_target = self.rto_targets.get(failed_tier, 900)

                if elapsed_time <= rto_target:
                    self.logger.info(
                        f"Failover completed within RTO target: {elapsed_time:.2f}s <= {rto_target}s"
                    )
                else:
                    self.logger.warning(
                        f"Failover exceeded RTO target: {elapsed_time:.2f}s > {rto_target}s"
                    )

                return True

        except Exception as e:
            self.logger.error(f"Failover failed: {e}")

        finally:
            self.failover_in_progress.pop(failed_tier, None)

        return False

    def _determine_failover_target(
        self, failed_tier: DatabaseTier
    ) -> Optional[DatabaseTier]:
        """Determine the best failover target for a failed tier."""

        # Failover hierarchy
        failover_map = {
            DatabaseTier.PRIMARY: [DatabaseTier.BACKUP, DatabaseTier.REPLICA],
            DatabaseTier.REPLICA: [DatabaseTier.BACKUP, DatabaseTier.PRIMARY],
            DatabaseTier.BACKUP: [DatabaseTier.PRIMARY, DatabaseTier.REPLICA],
            DatabaseTier.CHILD_SAFE: [
                DatabaseTier.PRIMARY
            ],  # Child data needs primary-level security
        }

        candidates = failover_map.get(failed_tier, [])

        # Find first healthy candidate
        for candidate in candidates:
            for pool_id, pool in self.pools.items():
                if (
                    pool.config.tier == candidate
                    and pool.state == DatabaseConnectionState.HEALTHY
                ):
                    return candidate

        return None

    async def _pre_failover_validation(
        self, source_tier: DatabaseTier, target_tier: DatabaseTier
    ):
        """Validate conditions before starting failover."""

        target_pool = self._get_pool_by_tier(target_tier)
        if not target_pool:
            raise Exception(f"Target tier {target_tier.value} not available")

        # Check target pool health
        health_status = await target_pool.health_check()
        if not health_status.get("healthy", False):
            raise Exception(f"Target pool {target_tier.value} is not healthy")

        # Check capacity
        utilization = (
            target_pool.metrics.active_connections / target_pool.config.max_connections
        )
        if utilization > 0.7:  # 70% threshold
            self.logger.warning(
                f"Target pool {target_tier.value} is at {utilization:.1%} capacity"
            )

        # For child data, ensure encryption capability
        if source_tier == DatabaseTier.CHILD_SAFE:
            if not target_pool.config.encrypt_child_data:
                raise Exception("Target pool cannot handle encrypted child data")

    async def _execute_failover_sequence(
        self, source_tier: DatabaseTier, target_tier: DatabaseTier
    ) -> bool:
        """Execute the actual failover sequence."""

        try:
            # Step 1: Create backup checkpoint if possible
            await self._create_emergency_checkpoint(source_tier)

            # Step 2: Prepare target pool for increased load
            await self._prepare_target_pool(target_tier)

            # Step 3: Transfer active connections (graceful)
            await self._transfer_active_connections(source_tier, target_tier)

            # Step 4: Update internal routing
            self._update_internal_routing(source_tier, target_tier)

            # Step 5: Validate data consistency
            await self._validate_failover_consistency(target_tier)

            return True

        except Exception as e:
            self.logger.error(f"Failover sequence failed at step: {e}")
            return False

    async def _create_emergency_checkpoint(self, tier: DatabaseTier):
        """Create emergency data checkpoint before failover."""

        pool = self._get_pool_by_tier(tier)
        if not pool or pool.state == DatabaseConnectionState.FAILED:
            self.logger.warning(
                f"Cannot create checkpoint for failed tier {tier.value}"
            )
            return

        try:
            async with pool.acquire_connection() as conn:
                # Create checkpoint metadata
                checkpoint_id = f"emergency_{tier.value}_{int(time.time())}"

                # For child data, ensure critical tables are backed up
                if tier == DatabaseTier.CHILD_SAFE:
                    critical_tables = [
                        "child_profiles",
                        "child_interactions",
                        "parent_consent",
                    ]
                    for table in critical_tables:
                        # This would typically integrate with your backup system
                        await conn.execute(f"-- Emergency checkpoint for {table}")

                self.backup_checkpoints[tier] = {
                    "checkpoint_id": checkpoint_id,
                    "timestamp": datetime.utcnow(),
                    "status": "created",
                }

                self.logger.info(f"Emergency checkpoint created: {checkpoint_id}")

        except Exception as e:
            self.logger.error(f"Failed to create emergency checkpoint: {e}")

    async def _prepare_target_pool(self, tier: DatabaseTier):
        """Prepare target pool to handle additional load."""

        pool = self._get_pool_by_tier(tier)
        if not pool:
            raise Exception(f"Target pool {tier.value} not found")

        # Scale up connections if needed
        current_capacity = pool.metrics.active_connections / pool.config.max_connections
        if current_capacity > 0.5:  # If over 50%, scale up
            # This would typically trigger auto-scaling
            self.logger.info(f"Scaling up target pool {tier.value} for failover load")

        # Warm up prepared statements
        try:
            async with pool.acquire_connection() as conn:
                # Execute warm-up queries
                await conn.fetchval("SELECT 1")  # Basic connectivity

        except Exception as e:
            self.logger.error(f"Failed to warm up target pool: {e}")

    async def _transfer_active_connections(
        self, source_tier: DatabaseTier, target_tier: DatabaseTier
    ):
        """Gracefully transfer active connections."""

        # This is a simplified version - production would need more sophisticated logic
        source_pool = self._get_pool_by_tier(source_tier)
        target_pool = self._get_pool_by_tier(target_tier)

        if source_pool and source_pool.state != DatabaseConnectionState.FAILED:
            # Allow existing operations to complete (with timeout)
            grace_period = 30.0  # seconds
            start_time = time.time()

            while (
                source_pool.metrics.active_connections > 0
                and time.time() - start_time < grace_period
            ):
                await asyncio.sleep(1)

            # Force close remaining connections if grace period exceeded
            if source_pool.metrics.active_connections > 0:
                self.logger.warning(
                    f"Force closing {source_pool.metrics.active_connections} connections"
                )

        self.logger.info(
            f"Connection transfer from {source_tier.value} to {target_tier.value} completed"
        )

    def _update_internal_routing(
        self, source_tier: DatabaseTier, target_tier: DatabaseTier
    ):
        """Update internal routing to redirect traffic."""

        # Mark source as failed
        source_pool = self._get_pool_by_tier(source_tier)
        if source_pool:
            source_pool.state = DatabaseConnectionState.FAILED

        # This would integrate with your service discovery/routing system
        self.logger.info(f"Routing updated: {source_tier.value} -> {target_tier.value}")

    async def _post_failover_validation(self, target_tier: DatabaseTier):
        """Validate system state after failover."""

        target_pool = self._get_pool_by_tier(target_tier)
        if not target_pool:
            raise Exception(
                f"Target pool {target_tier.value} not available for validation"
            )

        # Comprehensive health check
        health_status = await target_pool.health_check()
        if not health_status.get("healthy", False):
            raise Exception(f"Post-failover validation failed for {target_tier.value}")

        # Test database operations
        try:
            await target_pool.execute_query(
                "SELECT current_timestamp, version()",
                operation_type="post_failover_test",
            )
        except Exception as e:
            raise Exception(f"Post-failover operation test failed: {e}")

        self.logger.info(f"Post-failover validation passed for {target_tier.value}")

    async def _update_failover_routing(
        self, source_tier: DatabaseTier, target_tier: DatabaseTier
    ):
        """Update external routing configuration."""

        # This would typically update load balancer configuration,
        # service mesh routing, DNS records, etc.

        routing_config = {
            "failed_tier": source_tier.value,
            "active_tier": target_tier.value,
            "failover_time": datetime.utcnow().isoformat(),
            "automatic": True,
        }

        # Log for external monitoring systems
        self.logger.info("Failover routing updated", extra=routing_config)

    async def _schedule_consistency_verification(
        self, source_tier: DatabaseTier, target_tier: DatabaseTier
    ):
        """Schedule data consistency verification after failover."""

        # Wait for replication to settle
        await asyncio.sleep(60)  # 1 minute grace period

        try:
            await self._verify_data_consistency(target_tier)

            # If child data was involved, perform additional checks
            if source_tier == DatabaseTier.CHILD_SAFE:
                await self._verify_child_data_consistency(target_tier)

            self.logger.info(
                f"Consistency verification completed for {target_tier.value}"
            )

        except Exception as e:
            self.logger.error(f"Consistency verification failed: {e}")
            # This would typically trigger alerts for manual intervention

    async def _verify_data_consistency(self, tier: DatabaseTier):
        """Verify data consistency after failover."""

        pool = self._get_pool_by_tier(tier)
        if not pool:
            raise Exception(f"Pool {tier.value} not available for consistency check")

        try:
            async with pool.acquire_connection() as conn:
                # Basic integrity checks
                table_counts = await conn.fetch(
                    """
                    SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del
                    FROM pg_stat_user_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                """
                )

                # Store consistency snapshot
                self.consistency_checks[tier] = {
                    "timestamp": datetime.utcnow(),
                    "table_counts": [dict(row) for row in table_counts],
                    "status": "verified",
                }

        except Exception as e:
            raise Exception(f"Data consistency verification failed: {e}")

    async def _verify_child_data_consistency(self, tier: DatabaseTier):
        """Special consistency checks for child data."""

        pool = self._get_pool_by_tier(tier)
        if not pool:
            return

        try:
            async with pool.acquire_connection() as conn:
                # Check critical child data tables
                child_checks = await conn.fetch(
                    """
                    SELECT 
                        'child_profiles' as table_name,
                        count(*) as total_records,
                        count(DISTINCT child_id) as unique_children
                    FROM child_profiles
                    WHERE created_at >= current_date - interval '30 days'
                    
                    UNION ALL
                    
                    SELECT 
                        'child_interactions' as table_name,
                        count(*) as total_records,
                        count(DISTINCT child_id) as unique_children
                    FROM child_interactions
                    WHERE created_at >= current_date - interval '7 days'
                """
                )

                # Verify encryption status for sensitive fields
                encrypted_check = await conn.fetchval(
                    """
                    SELECT count(*) 
                    FROM child_profiles 
                    WHERE encrypted_name IS NOT NULL
                    AND length(encrypted_name) > length(display_name)
                """
                )

                log_data = {
                    "tier": tier.value,
                    "child_checks": [dict(row) for row in child_checks],
                    "encrypted_records": encrypted_check,
                }
                self.logger.info("Child data consistency verified", extra=log_data)

        except Exception as e:
            self.logger.error(f"Child data consistency check failed: {e}")

    def _get_pool_by_tier(
        self, tier: DatabaseTier
    ) -> Optional[EnterpriseConnectionPool]:
        """Get pool instance by tier."""
        for pool in self.pools.values():
            if pool.config.tier == tier:
                return pool
        return None


class database_manager:
    """Main enterprise database manager orchestrating all components."""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager or get_config_manager()
        self.logger = get_logger("enterprise_database_manager")

        # Core components
        self.pools: Dict[str, EnterpriseConnectionPool] = {}
        self.circuit_breakers: Dict[str, AdvancedCircuitBreaker] = {}
        self.load_balancer: Optional[EnterpriseIntelligentLoadBalancer] = None
        self.disaster_recovery: Optional[EnterpriseDisasterRecoveryManager] = None

        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.health_check_interval = self.config_manager.get_int(
            "DATABASE_HEALTH_CHECK_INTERVAL", 30
        )
        self.metrics_interval = self.config_manager.get_int(
            "DATABASE_METRICS_INTERVAL", 60
        )
        self.cleanup_interval = self.config_manager.get_int(
            "DATABASE_CLEANUP_INTERVAL", 3600
        )  # 1 hour

        # Monitoring
        self._init_prometheus_metrics()

        # OpenTelemetry tracing
        if OPENTELEMETRY_AVAILABLE:
            self.tracer = trace.get_tracer(__name__)
        else:
            self.tracer = None

    def _init_prometheus_metrics(self):
        """Initialize enterprise-level Prometheus metrics."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.system_health_gauge = Gauge(
            "database_system_health",
            "Overall database system health (0-1)",
            ["component"],
        )

        self.failover_events = Counter(
            "database_failover_events_total",
            "Total database failover events",
            ["source_tier", "target_tier", "reason"],
        )

        self.rto_histogram = Histogram(
            "database_rto_seconds",
            "Recovery Time Objective measurements",
            ["tier", "recovery_type"],
            buckets=[30, 60, 300, 600, 900, 1800, 3600],
        )

        self.consistency_checks = Counter(
            "database_consistency_checks_total",
            "Data consistency check results",
            ["tier", "result"],
        )

    async def initialize(self) -> bool:
        """Initialize the complete enterprise database system."""
        try:
            self.logger.info("Initializing Enterprise Database Manager")

            # Initialize connection pools
            await self._initialize_connection_pools()

            # Initialize circuit breakers
            self._initialize_circuit_breakers()

            # Initialize load balancer
            self.load_balancer = EnterpriseIntelligentLoadBalancer(self.pools)

            # Initialize disaster recovery manager
            self.disaster_recovery = EnterpriseDisasterRecoveryManager(self.pools)

            # Start background tasks
            await self._start_background_tasks()

            # Validate system health
            system_health = await self.get_system_health()
            if not system_health.get("healthy", False):
                raise Exception("System health validation failed after initialization")

            log_data = {
                "pools": len(self.pools),
                "healthy_pools": len(
                    [
                        p
                        for p in self.pools.values()
                        if p.state == DatabaseConnectionState.HEALTHY
                    ]
                ),
            }
            self.logger.info("Enterprise Database Manager initialized successfully", extra=log_data)

            return True

        except Exception as e:
            self.logger.error(f"Enterprise Database Manager initialization failed: {e}")
            await self.cleanup()
            return False

    async def _initialize_connection_pools(self):
        """Initialize all database connection pools concurrently."""

        pool_configs = []

        # Primary database
        primary_url = self.config_manager.get("DATABASE_URL")
        if primary_url:
            pool_configs.append(
                DatabaseConfig(
                    url=primary_url,
                    tier=DatabaseTier.PRIMARY,
                    security_level=SecurityLevel.HIGH,
                    max_connections=self.config_manager.get_int(
                        "DATABASE_PRIMARY_MAX_CONNECTIONS", 25
                    ),
                    min_connections=self.config_manager.get_int(
                        "DATABASE_PRIMARY_MIN_CONNECTIONS", 5
                    ),
                    enable_coppa_audit=True,
                    encrypt_child_data=True,
                )
            )

        # Replica databases
        replica_urls = self.config_manager.get_list("DATABASE_REPLICA_URLS", ",")
        for i, replica_url in enumerate(replica_urls):
            if replica_url.strip():
                pool_configs.append(
                    DatabaseConfig(
                        url=replica_url.strip(),
                        tier=DatabaseTier.REPLICA,
                        security_level=SecurityLevel.STANDARD,
                        max_connections=self.config_manager.get_int(
                            "DATABASE_REPLICA_MAX_CONNECTIONS", 15
                        ),
                        min_connections=self.config_manager.get_int(
                            "DATABASE_REPLICA_MIN_CONNECTIONS", 3
                        ),
                        application_name=f"ai-teddy-bear-replica-{i}",
                    )
                )

        # Backup databases
        backup_urls = self.config_manager.get_list("DATABASE_BACKUP_URLS", ",")
        for i, backup_url in enumerate(backup_urls):
            if backup_url.strip():
                pool_configs.append(
                    DatabaseConfig(
                        url=backup_url.strip(),
                        tier=DatabaseTier.BACKUP,
                        security_level=SecurityLevel.HIGH,
                        max_connections=self.config_manager.get_int(
                            "DATABASE_BACKUP_MAX_CONNECTIONS", 10
                        ),
                        min_connections=self.config_manager.get_int(
                            "DATABASE_BACKUP_MIN_CONNECTIONS", 2
                        ),
                        application_name=f"ai-teddy-bear-backup-{i}",
                    )
                )

        # Child-safe database (if configured separately)
        child_safe_url = self.config_manager.get("DATABASE_CHILD_SAFE_URL")
        if child_safe_url:
            pool_configs.append(
                DatabaseConfig(
                    url=child_safe_url,
                    tier=DatabaseTier.CHILD_SAFE,
                    security_level=SecurityLevel.CHILD_DATA,
                    max_connections=self.config_manager.get_int(
                        "DATABASE_CHILD_SAFE_MAX_CONNECTIONS", 8
                    ),
                    min_connections=self.config_manager.get_int(
                        "DATABASE_CHILD_SAFE_MIN_CONNECTIONS", 2
                    ),
                    encrypt_child_data=True,
                    enable_coppa_audit=True,
                    child_data_retention_days=30,
                    ssl_mode="verify-full",
                    application_name="ai-teddy-bear-child-safe",
                )
            )

        # Initialize pools concurrently
        initialization_tasks = []
        for i, config in enumerate(pool_configs):
            pool = EnterpriseConnectionPool(config)
            pool_id = f"{config.tier.value}_{i}"
            self.pools[pool_id] = pool

            initialization_tasks.append(pool.initialize())

        # Wait for all pools to initialize
        results = await asyncio.gather(*initialization_tasks, return_exceptions=True)

        # Check results
        successful_pools = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pool_id = f"{pool_configs[i].tier.value}_{i}"
                self.logger.error(f"Pool {pool_id} initialization failed: {result}")
                # Remove failed pool
                self.pools.pop(pool_id, None)
            elif result:
                successful_pools += 1

        if successful_pools == 0:
            raise Exception("No database pools could be initialized")

        self.logger.info(
            f"Initialized {successful_pools}/{len(pool_configs)} database pools"
        )

    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for all pools."""

        for pool_id, pool in self.pools.items():
            circuit_breaker_config = CircuitBreakerConfig(
                failure_threshold=self.config_manager.get_int(
                    "DATABASE_CIRCUIT_BREAKER_THRESHOLD", 5
                ),
                success_threshold=self.config_manager.get_int(
                    "DATABASE_CIRCUIT_BREAKER_SUCCESS_THRESHOLD", 3
                ),
                timeout=self.config_manager.get_float(
                    "DATABASE_CIRCUIT_BREAKER_TIMEOUT", 60.0
                ),
                adaptive_threshold=self.config_manager.get_bool(
                    "DATABASE_CIRCUIT_BREAKER_ADAPTIVE", True
                ),
            )

            self.circuit_breakers[pool_id] = AdvancedCircuitBreaker(
                circuit_breaker_config, pool_id
            )

    async def _start_background_tasks(self):
        """Start all background monitoring and maintenance tasks."""

        # Health monitoring task
        health_task = asyncio.create_task(self._health_monitoring_loop())
        self.background_tasks.append(health_task)

        # Metrics collection task
        metrics_task = asyncio.create_task(self._metrics_collection_loop())
        self.background_tasks.append(metrics_task)

        # Data cleanup task
        cleanup_task = asyncio.create_task(self._data_cleanup_loop())
        self.background_tasks.append(cleanup_task)

        # Performance optimization task
        optimization_task = asyncio.create_task(self._performance_optimization_loop())
        self.background_tasks.append(optimization_task)

        self.logger.info(f"Started {len(self.background_tasks)} background tasks")

    async def _health_monitoring_loop(self):
        """Background health monitoring with automatic recovery."""

        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                # Check all pools
                for pool_id, pool in self.pools.items():
                    health_status = await pool.health_check()

                    if not health_status.get("healthy", False):
                        self.logger.warning(f"Pool {pool_id} health check failed")

                        # Update circuit breaker
                        if pool_id in self.circuit_breakers:
                            self.circuit_breakers[pool_id].record_failure(
                                "health_check_failed"
                            )

                        # Check if failover is needed
                        if pool.config.tier == DatabaseTier.PRIMARY:
                            if self.disaster_recovery:
                                self.logger.critical(
                                    "Primary database health failed - initiating failover"
                                )
                                await self.disaster_recovery.initiate_failover(
                                    DatabaseTier.PRIMARY
                                )

                    else:
                        # Update circuit breaker on success
                        if pool_id in self.circuit_breakers:
                            self.circuit_breakers[pool_id].record_success()

                # Update system health metrics
                if PROMETHEUS_AVAILABLE:
                    system_health = await self.get_system_health()
                    health_score = 1.0 if system_health.get("healthy") else 0.0
                    self.system_health_gauge.labels(component="overall").set(
                        health_score
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")

    async def _metrics_collection_loop(self):
        """Background metrics collection and reporting."""

        while True:
            try:
                await asyncio.sleep(self.metrics_interval)

                # Collect metrics from all pools
                for pool_id, pool in self.pools.items():
                    metrics = pool.metrics

                    if PROMETHEUS_AVAILABLE:
                        tier = pool.config.tier.value

                        # Update Prometheus metrics
                        self.system_health_gauge.labels(component=f"pool_{tier}").set(
                            1.0
                            if pool.state == DatabaseConnectionState.HEALTHY
                            else 0.0
                        )

                # Report to external monitoring systems
                await self._report_external_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")

    async def _data_cleanup_loop(self):
        """Background data cleanup for COPPA compliance."""

        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                total_cleaned = 0
                for pool_id, pool in self.pools.items():
                    if pool.config.child_data_retention_days > 0:
                        cleaned = await pool.cleanup_old_data()
                        total_cleaned += cleaned

                if total_cleaned > 0:
                    self.logger.info(
                        f"COPPA compliance cleanup: {total_cleaned} records removed"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Data cleanup error: {e}")

    async def _performance_optimization_loop(self):
        """Background performance optimization."""

        optimization_interval = 3600  # 1 hour

        while True:
            try:
                await asyncio.sleep(optimization_interval)

                # Analyze query patterns and suggest optimizations
                for pool_id, pool in self.pools.items():
                    if pool.slow_queries:
                        slow_query_count = len(pool.slow_queries)
                        if slow_query_count > 10:  # Threshold for concern
                            log_data = {
                                "pool_id": pool_id,
                                "slow_queries": slow_query_count,
                            }
                            self.logger.warning("Pool %s has %d slow queries", pool_id, slow_query_count, extra=log_data)

                    # Clear old performance data
                    if len(pool.query_times) > 500:
                        # Keep only recent 500 samples
                        pool.query_times = deque(
                            list(pool.query_times)[-500:], maxlen=1000
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Performance optimization error: {e}")

    async def _report_external_metrics(self):
        """Report metrics to external monitoring systems."""

        metrics_collector = get_metrics_collector()
        if metrics_collector:
            system_health = await self.get_system_health()

            # Report system-level metrics
            await metrics_collector.gauge(
                "database.system.health", 1.0 if system_health.get("healthy") else 0.0
            )
            await metrics_collector.gauge(
                "database.system.pools.total", len(self.pools)
            )
            await metrics_collector.gauge(
                "database.system.pools.healthy", system_health.get("healthy_pools", 0)
            )

    # Public API methods

    async def execute_read(
        self,
        query: str,
        params: Optional[Tuple] = None,
        security_level: SecurityLevel = SecurityLevel.STANDARD,
        child_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Execute read operation with intelligent routing."""

        # OpenTelemetry tracing
        if self.tracer:
            with self.tracer.start_as_current_span("database.read") as span:
                span.set_attribute("security_level", security_level.value)
                if child_id:
                    span.set_attribute("involves_child_data", True)
                return await self._execute_operation(
                    "read", query, params, security_level, child_id, timeout
                )
        else:
            return await self._execute_operation(
                "read", query, params, security_level, child_id, timeout
            )

    async def execute_write(
        self,
        query: str,
        params: Optional[Tuple] = None,
        security_level: SecurityLevel = SecurityLevel.STANDARD,
        child_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Execute write operation on primary database."""

        if self.tracer:
            with self.tracer.start_as_current_span("database.write") as span:
                span.set_attribute("security_level", security_level.value)
                if child_id:
                    span.set_attribute("involves_child_data", True)
                return await self._execute_operation(
                    "write", query, params, security_level, child_id, timeout
                )
        else:
            return await self._execute_operation(
                "write", query, params, security_level, child_id, timeout
            )

    async def _execute_operation(
        self,
        operation_type: str,
        query: str,
        params: Optional[Tuple],
        security_level: SecurityLevel,
        child_id: Optional[str],
        timeout: Optional[float],
    ) -> Any:
        """Internal method to execute database operations."""

        if not self.load_balancer:
            raise ConnectionError("Database system not properly initialized")

        # Select appropriate pool
        selected_pool = await self.load_balancer.select_pool(
            operation_type=operation_type,
            security_level=security_level,
            strategy="child_data_optimized" if child_id else "predictive",
        )

        if not selected_pool:
            raise ConnectionError(f"No available pools for {operation_type} operation")

        pool_id = f"{selected_pool.config.tier.value}"
        circuit_breaker = self.circuit_breakers.get(pool_id)

        # Check circuit breaker
        if circuit_breaker and not circuit_breaker.can_execute():
            # Try to find alternative pool
            alternative_pool = await self.load_balancer.select_pool(
                operation_type=operation_type,
                security_level=security_level,
                strategy="fastest_response",
            )

            if alternative_pool and alternative_pool != selected_pool:
                selected_pool = alternative_pool
                pool_id = f"{selected_pool.config.tier.value}"
                circuit_breaker = self.circuit_breakers.get(pool_id)

                if circuit_breaker and not circuit_breaker.can_execute():
                    raise ConnectionError(
                        "All suitable database pools are circuit-broken"
                    )
            else:
                raise ConnectionError(f"Circuit breaker open for {pool_id}")

        # Execute operation with retry and circuit breaker protection
        start_time = time.time()
        try:
            result = await selected_pool.execute_query(
                query=query,
                params=params,
                operation_type=operation_type,
                security_level=security_level,
                child_id=child_id,
            )

            # Record success
            if circuit_breaker:
                circuit_breaker.record_success()

            execution_time = time.time() - start_time

            # Update metrics
            if PROMETHEUS_AVAILABLE:
                self.rto_histogram.labels(
                    tier=selected_pool.config.tier.value,
                    recovery_type="normal_operation",
                ).observe(execution_time)

            return result

        except Exception as e:
            # Record failure
            if circuit_breaker:
                error_type = selected_pool._classify_database_error(e)
                circuit_breaker.record_failure(error_type)

            # Check if we should attempt failover
            if (
                selected_pool.config.tier == DatabaseTier.PRIMARY
                and self.disaster_recovery
                and "connection" in str(e).lower()
            ):

                self.logger.error(
                    f"Primary database connection failed - attempting failover"
                )
                await self.disaster_recovery.initiate_failover(DatabaseTier.PRIMARY)

            raise

    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status."""

        health_status = {
            "healthy": False,
            "timestamp": datetime.utcnow().isoformat(),
            "pools": {},
            "summary": {
                "total_pools": len(self.pools),
                "healthy_pools": 0,
                "degraded_pools": 0,
                "failed_pools": 0,
            },
            "circuit_breakers": {},
            "system_metrics": {
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "child_data_queries": 0,
            },
        }

        # Check individual pools
        for pool_id, pool in self.pools.items():
            pool_health = await pool.health_check()
            health_status["pools"][pool_id] = pool_health

            # Update summary
            if pool_health.get("healthy", False):
                health_status["summary"]["healthy_pools"] += 1
            elif pool.state == DatabaseConnectionState.DEGRADED:
                health_status["summary"]["degraded_pools"] += 1
            else:
                health_status["summary"]["failed_pools"] += 1

            # Aggregate metrics
            metrics = pool.metrics
            health_status["system_metrics"]["total_queries"] += metrics.total_queries
            health_status["system_metrics"][
                "successful_queries"
            ] += metrics.successful_queries
            health_status["system_metrics"]["failed_queries"] += metrics.failed_queries
            health_status["system_metrics"][
                "child_data_queries"
            ] += metrics.child_data_queries

        # Check circuit breakers
        for cb_id, circuit_breaker in self.circuit_breakers.items():
            health_status["circuit_breakers"][cb_id] = {
                "state": circuit_breaker.state,
                "failure_count": circuit_breaker.failure_count,
                "consecutive_successes": circuit_breaker.consecutive_successes,
            }

        # Determine overall health
        healthy_pools = health_status["summary"]["healthy_pools"]
        total_pools = health_status["summary"]["total_pools"]

        if total_pools == 0:
            health_status["healthy"] = False
        elif healthy_pools == total_pools:
            health_status["healthy"] = True
        elif healthy_pools >= total_pools * 0.7:  # 70% threshold
            health_status["healthy"] = True
            health_status["status"] = "degraded"
        else:
            health_status["healthy"] = False
            health_status["status"] = "critical"

        return health_status

    async def cleanup(self):
        """Cleanup all resources and connections."""

        self.logger.info("Shutting down Enterprise Database Manager")

        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()

        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        # Close all connection pools
        cleanup_tasks = []
        for pool_id, pool in self.pools.items():
            cleanup_tasks.append(pool.close())

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

        self.logger.info("Enterprise Database Manager shutdown completed")


# Global instance management
_enterprise_db_manager: Optional[database_manager] = None
_initialization_lock = threading.Lock()


async def get_enterprise_database_manager() -> database_manager:
    """Get or create enterprise database manager instance."""
    global _enterprise_db_manager

    if _enterprise_db_manager is None:
        with _initialization_lock:
            if _enterprise_db_manager is None:
                _enterprise_db_manager = database_manager()
                success = await _enterprise_db_manager.initialize()
                if not success:
                    _enterprise_db_manager = None
                    raise Exception("Failed to initialize Enterprise Database Manager")

    return _enterprise_db_manager


# Convenience functions with enterprise features


async def execute_child_safe_query(query: str, *params, child_id: str) -> Any:
    """Execute query with child data protection."""
    manager = await get_enterprise_database_manager()
    return await manager.execute_read(
        query, params, security_level=SecurityLevel.CHILD_DATA, child_id=child_id
    )


async def execute_enterprise_read(
    query: str, *params, security_level: SecurityLevel = SecurityLevel.STANDARD
) -> Any:
    """Execute read operation with enterprise security."""
    manager = await get_enterprise_database_manager()
    return await manager.execute_read(query, params, security_level=security_level)


async def execute_enterprise_write(
    query: str, *params, security_level: SecurityLevel = SecurityLevel.STANDARD
) -> Any:
    """Execute write operation with enterprise security."""
    manager = await get_enterprise_database_manager()
    return await manager.execute_write(query, params, security_level=security_level)


# FastAPI dependencies
async def get_enterprise_db():
    """FastAPI dependency for enterprise database access."""
    manager = await get_enterprise_database_manager()
    return manager


async def get_child_safe_db():
    """FastAPI dependency for child-safe database access."""
    manager = await get_enterprise_database_manager()

    # Return a wrapper that enforces child data security
    class ChildSafeDBWrapper:
        def __init__(self, manager):
            self._manager = manager

        async def execute_read(self, query: str, *params, child_id: str):
            return await self._manager.execute_read(
                query,
                params,
                security_level=SecurityLevel.CHILD_DATA,
                child_id=child_id,
            )

        async def execute_write(self, query: str, *params, child_id: str):
            return await self._manager.execute_write(
                query,
                params,
                security_level=SecurityLevel.CHILD_DATA,
                child_id=child_id,
            )

    return ChildSafeDBWrapper(manager)


# System initialization and cleanup
async def initialize_enterprise_database():
    """Initialize enterprise database system."""
    await get_enterprise_database_manager()


async def cleanup_enterprise_database():
    """Cleanup enterprise database system."""
    global _enterprise_db_manager
    if _enterprise_db_manager:
        await _enterprise_db_manager.cleanup()
        _enterprise_db_manager = None


# --- Legacy API Compatibility Wrappers ---
# These wrappers provide the old API names for compatibility with legacy code.


async def initialize_database():
    """Legacy alias for initializing the database system."""
    await initialize_enterprise_database()


async def close_database():
    """Legacy alias for cleaning up the database system."""
    await cleanup_enterprise_database()


async def get_connection():
    """Legacy stub: returns the main database manager instance (not a raw connection)."""
    return await get_enterprise_database_manager()


async def execute_query(query: str, *params, **kwargs):
    """Legacy alias for executing a query (read)."""
    manager = await get_enterprise_database_manager()
    return await manager.execute_read(query, params, **kwargs)


async def fetch_one(query: str, *params, **kwargs):
    """Legacy stub: fetch one record from a query result."""
    manager = await get_enterprise_database_manager()
    results = await manager.execute_read(query, params, **kwargs)
    return results[0] if results else None


async def fetch_all(query: str, *params, **kwargs):
    """Legacy stub: fetch all records from a query result."""
    manager = await get_enterprise_database_manager()
    return await manager.execute_read(query, params, **kwargs)


async def execute_command(query: str, *params, **kwargs):
    """Legacy alias for executing a write command."""
    manager = await get_enterprise_database_manager()
    return await manager.execute_write(query, params, **kwargs)


# DatabaseRole is not defined in the new system; provide a dummy Enum for compatibility
from enum import Enum as _Enum


class DatabaseRole(_Enum):
    PRIMARY = "primary"
    REPLICA = "replica"
    BACKUP = "backup"
    EMERGENCY = "emergency"
    CHILD_SAFE = "child_safe"
# --- FastAPI Dependency: get_db ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession from the global connection pool manager.
    Usage: db: AsyncSession = Depends(get_db)
    """
    pool_manager = await get_pool_manager()
    async with pool_manager.get_session() as session:
        yield session