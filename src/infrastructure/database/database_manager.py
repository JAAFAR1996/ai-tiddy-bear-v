"""
Database Manager - Production-Ready Database Connection Management
================================================================
Enterprise database management with connection pooling, retries, timeouts, and zero single points of failure:
- Advanced connection pooling with dynamic sizing
- Intelligent retry mechanisms with exponential backoff
- Circuit breaker patterns for database failures
- Read/write splitting for high availability
- Connection health monitoring and auto-recovery
- Database failover and disaster recovery
- Performance monitoring and optimization
- COPPA-compliant data operations
"""

import asyncio
import time
import logging
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import json


import asyncpg
from asyncpg import Pool, Connection
from asyncpg.exceptions import (
    PostgresError,
    ConnectionDoesNotExistError,
    InterfaceError,
    InvalidCatalogNameError,
)
from fastapi import Request

from ..config.config_manager_provider import get_config_manager
from ..logging import get_logger, audit_logger, performance_logger
from ..monitoring import get_metrics_collector
from ...core.exceptions import ConfigurationError

# Type definitions
DatabaseOperation = Callable[..., Any]
HealthCheckFunction = Callable[[], bool]


class DatabaseConnectionState(Enum):
    """Database connection states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"
    MAINTENANCE = "maintenance"


class DatabaseRole(Enum):
    """Database role types."""

    PRIMARY = "primary"
    REPLICA = "replica"
    BACKUP = "backup"


class RetryStrategy(Enum):
    """Retry strategy types."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_INTERVAL = "fixed_interval"
    FIBONACCI = "fibonacci"


@dataclass
class DatabaseConfig:
    """Database configuration."""

    url: str
    role: DatabaseRole = DatabaseRole.PRIMARY
    max_connections: int = 20
    min_connections: int = 5
    max_idle_time: float = 300.0  # 5 minutes
    max_lifetime: float = 3600.0  # 1 hour
    acquire_timeout: float = 30.0
    query_timeout: float = 60.0
    command_timeout: float = 300.0
    server_settings: Dict[str, str] = field(default_factory=dict)
    ssl_mode: str = "require"
    application_name: str = "ai-teddy-bear"


@dataclass
class RetryConfig:
    """Retry configuration."""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    backoff_multiplier: float = 2.0


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 60.0
    half_open_max_calls: int = 3


@dataclass
class ConnectionMetrics:
    """Connection pool metrics."""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    average_query_time: float = 0.0
    peak_connections: int = 0
    connection_wait_time: float = 0.0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None


class CircuitBreaker:
    """Circuit breaker for database operations."""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.logger = get_logger("circuit_breaker")

    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        now = datetime.now()

        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if (now - self.last_failure_time).total_seconds() >= self.config.timeout:
                self.state = "HALF_OPEN"
                self.success_count = 0
                self.logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            return False
        elif self.state == "HALF_OPEN":
            return self.success_count < self.config.half_open_max_calls

        return False

    def record_success(self):
        """Record successful operation."""
        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = "CLOSED"
                self.failure_count = 0
                self.logger.info("Circuit breaker reset to CLOSED")
        elif self.state == "CLOSED":
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if (
            self.state == "CLOSED"
            and self.failure_count >= self.config.failure_threshold
        ):
            self.state = "OPEN"
            self.logger.error(
                f"Circuit breaker opened after {self.failure_count} failures"
            )
        elif self.state == "HALF_OPEN":
            self.state = "OPEN"
            self.logger.warning("Circuit breaker reopened during half-open state")


class DatabaseNode:
    """Individual database node management."""

    def __init__(self, config: DatabaseConfig, retry_config: RetryConfig):
        self.config = config
        self.retry_config = retry_config
        self.pool: Optional[Pool] = None
        self.state = DatabaseConnectionState.HEALTHY
        self.metrics = ConnectionMetrics()
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        self.logger = get_logger(f"db_node_{config.role.value}")
        self.metrics_collector = get_metrics_collector()

        # Health monitoring
        self.last_health_check = datetime.now()
        self.health_check_interval = 30.0  # seconds
        self.consecutive_failures = 0

        # Performance tracking
        self.query_times: List[float] = []
        self.max_query_time_samples = 1000

    async def initialize(self):
        """Initialize database connection pool."""
        try:
            self.logger.info(f"Initializing database pool for {self.config.role.value}")

            # Create connection pool
            self.pool = await asyncpg.create_pool(
                self.config.url,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
                max_idle=self.config.max_idle_time,
                max_lifetime=self.config.max_lifetime,
                command_timeout=self.config.command_timeout,
                server_settings=self.config.server_settings,
            )

            # Test initial connection
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")

            self.state = DatabaseConnectionState.HEALTHY
            self.metrics.last_success_time = datetime.now()

            self.logger.info(
                f"Database pool initialized successfully",
                extra={
                    "role": self.config.role.value,
                    "min_connections": self.config.min_connections,
                    "max_connections": self.config.max_connections,
                },
            )

        except Exception as e:
            self.state = DatabaseConnectionState.FAILED
            self.metrics.last_failure_time = datetime.now()
            safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
            self.logger.error("Failed to initialize database pool: %s", safe_error)
            raise

    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            self.logger.info("Database pool closed")

    @asynccontextmanager
    async def acquire_connection(self) -> AsyncGenerator[Connection, None]:
        """Acquire database connection with circuit breaker protection."""
        if not self.circuit_breaker.can_execute():
            raise ConnectionError("Circuit breaker is open")

        if not self.pool:
            raise ConnectionError("Database pool not initialized")

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
            self.metrics.total_connections = max(
                self.metrics.total_connections, self.metrics.active_connections
            )

            # Update peak connections
            if self.metrics.active_connections > self.metrics.peak_connections:
                self.metrics.peak_connections = self.metrics.active_connections

            self.circuit_breaker.record_success()

            yield connection

        except Exception as e:
            self.circuit_breaker.record_failure()
            self.consecutive_failures += 1
            self.metrics.failed_connections += 1
            self.metrics.last_failure_time = datetime.now()

            safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
            self.logger.error("Failed to acquire connection: %s", safe_error)
            raise

        finally:
            if connection:
                try:
                    await self.pool.release(connection)
                    self.metrics.active_connections = max(
                        0, self.metrics.active_connections - 1
                    )
                except Exception as e:
                    safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                    self.logger.error("Failed to release connection: %s", safe_error)

    async def execute_with_retry(
        self, operation: DatabaseOperation, *args, **kwargs
    ) -> Any:
        """Execute database operation with retry logic."""
        last_exception = None

        for attempt in range(self.retry_config.max_attempts):
            try:
                start_time = time.time()

                async with self.acquire_connection() as conn:
                    result = await operation(conn, *args, **kwargs)

                # Record successful operation
                execution_time = time.time() - start_time
                self._record_query_time(execution_time)

                self.metrics.total_queries += 1
                self.metrics.successful_queries += 1
                self.metrics.last_success_time = datetime.now()
                self.consecutive_failures = 0

                # Update state if recovering
                if self.state == DatabaseConnectionState.RECOVERING:
                    self.state = DatabaseConnectionState.HEALTHY
                    self.logger.info("Database node recovered")

                return result

            except Exception as e:
                last_exception = e
                self.metrics.total_queries += 1
                self.metrics.failed_queries += 1
                self.consecutive_failures += 1

                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.warning(
                    "Database operation failed (attempt %d/%d): %s",
                    attempt + 1,
                    self.retry_config.max_attempts,
                    safe_error,
                )

                # Don't retry on certain errors
                if isinstance(e, (InvalidCatalogNameError, InterfaceError)):
                    break

                # Wait before retry (except last attempt)
                if attempt < self.retry_config.max_attempts - 1:
                    delay = self._calculate_retry_delay(attempt)
                    await asyncio.sleep(delay)

        # All retries failed
        self.state = DatabaseConnectionState.FAILED
        self.metrics.last_failure_time = datetime.now()

        safe_error = str(last_exception).replace("\n", "").replace("\r", "")[:200]
        self.logger.error(
            "Database operation failed after %d attempts: %s",
            self.retry_config.max_attempts,
            safe_error,
        )

        raise last_exception

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay based on strategy."""
        if self.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.retry_config.base_delay * (
                self.retry_config.backoff_multiplier**attempt
            )
        elif self.retry_config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.retry_config.base_delay * (attempt + 1)
        elif self.retry_config.strategy == RetryStrategy.FIBONACCI:
            fib = self._fibonacci(attempt + 1)
            delay = self.retry_config.base_delay * fib
        else:  # FIXED_INTERVAL
            delay = self.retry_config.base_delay

        # Apply jitter and max delay
        if self.retry_config.jitter:
            import random

            delay *= 0.5 + random.random() * 0.5

        return min(delay, self.retry_config.max_delay)

    def _fibonacci(self, n: int) -> int:
        """Calculate Fibonacci number."""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    def _record_query_time(self, execution_time: float):
        """Record query execution time."""
        self.query_times.append(execution_time)

        # Keep only recent samples
        if len(self.query_times) > self.max_query_time_samples:
            self.query_times = self.query_times[-self.max_query_time_samples :]

        # Update average
        if self.query_times:
            self.metrics.average_query_time = sum(self.query_times) / len(
                self.query_times
            )

    async def health_check(self) -> bool:
        """Perform health check on database node."""
        try:
            async with self.acquire_connection() as conn:
                # Simple health check query
                await conn.fetchval("SELECT 1")

                # Check connection count
                pool_size = await conn.fetchval(
                    "SELECT count(*) FROM pg_stat_activity WHERE application_name = $1",
                    self.config.application_name,
                )

                self.logger.debug(
                    f"Health check passed",
                    extra={
                        "role": self.config.role.value,
                        "active_connections": pool_size,
                    },
                )

                self.last_health_check = datetime.now()
                return True

        except Exception as e:
            safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
            self.logger.error("Health check failed: %s", safe_error)
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get current node metrics."""
        pool_info = {}
        if self.pool:
            pool_info = {
                "pool_size": self.pool.get_size(),
                "pool_max_size": self.pool.get_max_size(),
                "pool_min_size": self.pool.get_min_size(),
                "pool_idle": self.pool.get_idle_size(),
            }

        return {
            "role": self.config.role.value,
            "state": self.state.value,
            "circuit_breaker_state": self.circuit_breaker.state,
            "consecutive_failures": self.consecutive_failures,
            "last_health_check": self.last_health_check.isoformat(),
            "metrics": {
                "total_connections": self.metrics.total_connections,
                "active_connections": self.metrics.active_connections,
                "peak_connections": self.metrics.peak_connections,
                "total_queries": self.metrics.total_queries,
                "successful_queries": self.metrics.successful_queries,
                "failed_queries": self.metrics.failed_queries,
                "average_query_time": self.metrics.average_query_time,
                "connection_wait_time": self.metrics.connection_wait_time,
                "success_rate": (
                    self.metrics.successful_queries
                    / max(1, self.metrics.total_queries)
                    * 100
                ),
            },
            "pool_info": pool_info,
        }


class DatabaseManager:
    """Production database manager with high availability."""

    def __init__(self, *, config=None, sessionmaker=None, config_manager=None):
        """Initialize DatabaseManager with DI support.
        
        Args:
            config: ProductionConfig instance from app.state (preferred)
            sessionmaker: async_sessionmaker instance (preferred) 
            config_manager: Legacy config manager (fallback only)
        """
        self._config = config
        self._sessionmaker = sessionmaker
        # No fallback to global config manager - require explicit injection
        if not config:
            raise RuntimeError(
                "DatabaseManager requires injected ProductionConfig (no global config manager)"
            )
        self.logger = get_logger("database_manager")
        self.metrics_collector = get_metrics_collector()

        # Database nodes
        self.primary_node: Optional[DatabaseNode] = None
        self.replica_nodes: List[DatabaseNode] = []
        self.backup_nodes: List[DatabaseNode] = []

        # Configuration - use DI config if available
        self.retry_config = RetryConfig(
            max_attempts=self.get_config_value("DATABASE_MAX_RETRIES", 3),
            base_delay=self.get_config_value("DATABASE_RETRY_DELAY", 1.0),
            max_delay=self.get_config_value("DATABASE_MAX_RETRY_DELAY", 60.0),
        )

        # Health monitoring
        self.health_check_task: Optional[asyncio.Task] = None
        self.health_check_interval = self.get_config_value("DATABASE_HEALTH_CHECK_INTERVAL", 30)

        # Load balancing for read operations  
        self.read_strategy = self.get_config_value("DATABASE_READ_STRATEGY", "round_robin")

    def get_config(self):
        """Get configuration using DI (production-grade)."""
        if self._config is not None:
            return self._config
        # Fallback to legacy config manager
        if hasattr(self.config_manager, 'get_config'):
            return self.config_manager.get_config()
        raise ConfigurationError(
            "DatabaseManager requires injected ProductionConfig (no global config manager)",
            context={"component": "DatabaseManager"}
        )

    def get_config_value(self, key: str, default=None):
        """Get config value using DI or fallback."""
        if self._config is not None:
            return getattr(self._config, key, default)
        # Legacy fallback
        if hasattr(self.config_manager, 'get'):
            return self.config_manager.get(key, default)
        elif hasattr(self.config_manager, 'get_int') and isinstance(default, int):
            return self.config_manager.get_int(key, default)
        elif hasattr(self.config_manager, 'get_float') and isinstance(default, float):
            return self.config_manager.get_float(key, default)
        return default

    def _ensure_sessionmaker(self):
        """Ensure sessionmaker is available."""
        if self._sessionmaker is None:
            # Try to create one from config
            config = self.get_config()
            if hasattr(config, 'DATABASE_URL'):
                from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
                engine = create_async_engine(config.DATABASE_URL, pool_pre_ping=True)
                self._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
            else:
                raise ConfigurationError("No sessionmaker provided and cannot create from config")
        return self._sessionmaker

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection using DI sessionmaker (production-grade with session lifecycle)."""
        SessionLocal = self._ensure_sessionmaker()
        async with SessionLocal() as session:
            try:
                yield session
                # commit() عند النجاح
                await session.commit()
            except Exception:
                # rollback() عند الاستثناء
                await session.rollback()
                raise
            finally:
                # إغلاق الجلسة دائماً
                await session.close()

    # Legacy compatibility
    session = get_connection

    def _post_init_setup(self):
        """Complete initialization after DI setup."""
        # Replica management 
        self.current_replica_index = 0

        # Metrics reporting
        self.metrics_task: Optional[asyncio.Task] = None
        self.metrics_interval = 60  # seconds

    async def initialize(self):
        """Initialize database manager with all configured nodes."""
        try:
            self.logger.info("Initializing database manager")

            # Initialize primary database
            await self._initialize_primary_database()

            # Initialize replica databases
            await self._initialize_replica_databases()

            # Initialize backup databases
            await self._initialize_backup_databases()

            # Start health monitoring
            self.health_check_task = asyncio.create_task(self._health_check_loop())

            # Start metrics reporting
            self.metrics_task = asyncio.create_task(self._metrics_reporting_loop())

            self.logger.info(
                "Database manager initialized successfully",
                extra={
                    "primary_nodes": 1 if self.primary_node else 0,
                    "replica_nodes": len(self.replica_nodes),
                    "backup_nodes": len(self.backup_nodes),
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize database manager: {str(e)}")
            raise

    async def _initialize_primary_database(self):
        """Initialize primary database connection."""
        primary_url = self.config_manager.get("DATABASE_URL")
        if not primary_url:
            raise ValueError("PRIMARY_DATABASE_URL not configured")

        primary_config = DatabaseConfig(
            url=primary_url,
            role=DatabaseRole.PRIMARY,
            max_connections=self.config_manager.get_int("DATABASE_POOL_SIZE", 20),
            min_connections=self.config_manager.get_int("DATABASE_MIN_POOL_SIZE", 5),
            acquire_timeout=self.config_manager.get_float(
                "DATABASE_ACQUIRE_TIMEOUT", 30.0
            ),
            query_timeout=self.config_manager.get_float("DATABASE_QUERY_TIMEOUT", 60.0),
            command_timeout=self.config_manager.get_float(
                "DATABASE_COMMAND_TIMEOUT", 300.0
            ),
            application_name=self.config_manager.get("APP_NAME", "ai-teddy-bear"),
        )

        self.primary_node = DatabaseNode(primary_config, self.retry_config)
        await self.primary_node.initialize()

    async def _initialize_replica_databases(self):
        """Initialize replica database connections."""
        replica_urls = self.config_manager.get_list("DATABASE_REPLICA_URLS", ",")

        for i, replica_url in enumerate(replica_urls):
            if replica_url.strip():
                replica_config = DatabaseConfig(
                    url=replica_url.strip(),
                    role=DatabaseRole.REPLICA,
                    max_connections=self.config_manager.get_int(
                        "DATABASE_REPLICA_POOL_SIZE", 10
                    ),
                    min_connections=self.config_manager.get_int(
                        "DATABASE_REPLICA_MIN_POOL_SIZE", 2
                    ),
                    acquire_timeout=self.config_manager.get_float(
                        "DATABASE_ACQUIRE_TIMEOUT", 30.0
                    ),
                    query_timeout=self.config_manager.get_float(
                        "DATABASE_QUERY_TIMEOUT", 60.0
                    ),
                    application_name=f"{self.config_manager.get('APP_NAME', 'ai-teddy-bear')}-replica-{i}",
                )

                replica_node = DatabaseNode(replica_config, self.retry_config)
                await replica_node.initialize()
                self.replica_nodes.append(replica_node)

                self.logger.info(f"Replica database {i+1} initialized")

    async def _initialize_backup_databases(self):
        """Initialize backup database connections."""
        backup_urls = self.config_manager.get_list("DATABASE_BACKUP_URLS", ",")

        for i, backup_url in enumerate(backup_urls):
            if backup_url.strip():
                backup_config = DatabaseConfig(
                    url=backup_url.strip(),
                    role=DatabaseRole.BACKUP,
                    max_connections=self.config_manager.get_int(
                        "DATABASE_BACKUP_POOL_SIZE", 5
                    ),
                    min_connections=1,
                    application_name=f"{self.config_manager.get('APP_NAME', 'ai-teddy-bear')}-backup-{i}",
                )

                backup_node = DatabaseNode(backup_config, self.retry_config)
                await backup_node.initialize()
                self.backup_nodes.append(backup_node)

                self.logger.info(f"Backup database {i+1} initialized")

    async def close(self):
        """Close all database connections."""
        self.logger.info("Closing database manager")

        # Cancel background tasks
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        if self.metrics_task:
            self.metrics_task.cancel()
            try:
                await self.metrics_task
            except asyncio.CancelledError:
                pass

        # Close all database nodes
        tasks = []

        if self.primary_node:
            tasks.append(self.primary_node.close())

        for replica in self.replica_nodes:
            tasks.append(replica.close())

        for backup in self.backup_nodes:
            tasks.append(backup.close())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.logger.info("Database manager closed")

    async def execute_write(self, operation: DatabaseOperation, *args, **kwargs) -> Any:
        """Execute write operation on primary database."""
        if not self.primary_node:
            raise ConnectionError("No primary database available")

        self.logger.debug("Executing write operation on primary database")

        try:
            result = await self.primary_node.execute_with_retry(
                operation, *args, **kwargs
            )

            # Log successful write operation
            audit_logger.audit(
                "Database write operation completed",
                metadata={
                    "operation": (
                        operation.__name__
                        if hasattr(operation, "__name__")
                        else "unknown"
                    ),
                    "node_role": "primary",
                    "timestamp": datetime.now().isoformat(),
                },
            )

            return result

        except Exception as e:
            self.logger.error(f"Write operation failed on primary database: {str(e)}")

            # Try backup nodes if primary fails
            for backup_node in self.backup_nodes:
                if backup_node.state == DatabaseConnectionState.HEALTHY:
                    try:
                        self.logger.warning(
                            "Attempting write operation on backup database"
                        )
                        result = await backup_node.execute_with_retry(
                            operation, *args, **kwargs
                        )

                        audit_logger.audit(
                            "Database write operation completed on backup",
                            metadata={
                                "operation": (
                                    operation.__name__
                                    if hasattr(operation, "__name__")
                                    else "unknown"
                                ),
                                "node_role": "backup",
                                "primary_failed": True,
                                "timestamp": datetime.now().isoformat(),
                            },
                        )

                        return result

                    except Exception as backup_error:
                        self.logger.error(
                            f"Backup database also failed: {str(backup_error)}"
                        )
                        continue

            raise

    async def execute_read(self, operation: DatabaseOperation, *args, **kwargs) -> Any:
        """Execute read operation with load balancing across replicas."""
        # Try replicas first for read operations
        available_replicas = [
            replica
            for replica in self.replica_nodes
            if replica.state == DatabaseConnectionState.HEALTHY
        ]

        if available_replicas:
            replica_node = self._select_replica(available_replicas)

            try:
                self.logger.debug(f"Executing read operation on replica database")
                result = await replica_node.execute_with_retry(
                    operation, *args, **kwargs
                )

                performance_logger.info(
                    "Database read operation completed",
                    extra={
                        "node_role": "replica",
                        "operation": (
                            operation.__name__
                            if hasattr(operation, "__name__")
                            else "unknown"
                        ),
                    },
                )

                return result

            except Exception as e:
                self.logger.warning(f"Read operation failed on replica: {str(e)}")
                # Fall through to primary

        # Fall back to primary database
        if not self.primary_node:
            raise ConnectionError("No database available for read operation")

        self.logger.debug("Executing read operation on primary database (fallback)")

        try:
            result = await self.primary_node.execute_with_retry(
                operation, *args, **kwargs
            )

            performance_logger.info(
                "Database read operation completed",
                extra={
                    "node_role": "primary",
                    "operation": (
                        operation.__name__
                        if hasattr(operation, "__name__")
                        else "unknown"
                    ),
                    "fallback_from_replica": bool(available_replicas),
                },
            )

            return result

        except Exception as e:
            self.logger.error(f"Read operation failed on primary database: {str(e)}")
            raise

    def _select_replica(self, available_replicas: List[DatabaseNode]) -> DatabaseNode:
        """Select replica based on load balancing strategy."""
        if not available_replicas:
            raise ValueError("No available replicas")

        if self.read_strategy == "round_robin":
            replica = available_replicas[
                self.current_replica_index % len(available_replicas)
            ]
            self.current_replica_index += 1
            return replica

        elif self.read_strategy == "least_connections":
            return min(available_replicas, key=lambda r: r.metrics.active_connections)

        elif self.read_strategy == "fastest_response":
            return min(available_replicas, key=lambda r: r.metrics.average_query_time)

        else:  # Default to first available
            return available_replicas[0]

    async def _health_check_loop(self):
        """Background health check loop."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._perform_health_checks()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check loop error: {str(e)}")

    async def _perform_health_checks(self):
        """Perform health checks on all database nodes."""
        tasks = []

        # Health check all nodes
        if self.primary_node:
            tasks.append(self._check_node_health(self.primary_node))

        for replica in self.replica_nodes:
            tasks.append(self._check_node_health(replica))

        for backup in self.backup_nodes:
            tasks.append(self._check_node_health(backup))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_node_health(self, node: DatabaseNode):
        """Check health of individual database node."""
        try:
            is_healthy = await node.health_check()

            if is_healthy:
                if node.state == DatabaseConnectionState.FAILED:
                    node.state = DatabaseConnectionState.RECOVERING
                    self.logger.info(
                        f"Database node {node.config.role.value} is recovering"
                    )
                elif node.state == DatabaseConnectionState.RECOVERING:
                    node.state = DatabaseConnectionState.HEALTHY
                    self.logger.info(
                        f"Database node {node.config.role.value} has recovered"
                    )
            else:
                if node.state == DatabaseConnectionState.HEALTHY:
                    node.state = DatabaseConnectionState.DEGRADED
                    self.logger.warning(
                        f"Database node {node.config.role.value} is degraded"
                    )
                elif node.state == DatabaseConnectionState.DEGRADED:
                    node.state = DatabaseConnectionState.FAILED
                    self.logger.error(
                        f"Database node {node.config.role.value} has failed"
                    )

        except Exception as e:
            self.logger.error(
                f"Health check failed for {node.config.role.value}: {str(e)}"
            )
            node.state = DatabaseConnectionState.FAILED

    async def _metrics_reporting_loop(self):
        """Background metrics reporting loop."""
        while True:
            try:
                await asyncio.sleep(self.metrics_interval)
                await self._report_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics reporting error: {str(e)}")

    async def _report_metrics(self):
        """Report database metrics to monitoring system."""
        try:
            all_metrics = self.get_all_metrics()

            # Report to metrics collector
            if self.metrics_collector:
                for node_metrics in all_metrics["nodes"]:
                    role = node_metrics["role"]
                    metrics = node_metrics["metrics"]

                    self.metrics_collector.gauge(
                        f"database.connections.total.{role}",
                        metrics["total_connections"],
                    )
                    self.metrics_collector.gauge(
                        f"database.connections.active.{role}",
                        metrics["active_connections"],
                    )
                    self.metrics_collector.gauge(
                        f"database.connections.peak.{role}", metrics["peak_connections"]
                    )
                    self.metrics_collector.counter(
                        f"database.queries.total.{role}", metrics["total_queries"]
                    )
                    self.metrics_collector.counter(
                        f"database.queries.successful.{role}",
                        metrics["successful_queries"],
                    )
                    self.metrics_collector.counter(
                        f"database.queries.failed.{role}", metrics["failed_queries"]
                    )
                    self.metrics_collector.gauge(
                        f"database.query_time.avg.{role}", metrics["average_query_time"]
                    )
                    self.metrics_collector.gauge(
                        f"database.success_rate.{role}", metrics["success_rate"]
                    )

            self.logger.debug("Database metrics reported successfully")

        except Exception as e:
            self.logger.error(f"Failed to report metrics: {str(e)}")

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics from all database nodes."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "nodes": [],
            "summary": {
                "total_nodes": 0,
                "healthy_nodes": 0,
                "failed_nodes": 0,
                "total_connections": 0,
                "total_queries": 0,
            },
        }

        all_nodes = []
        if self.primary_node:
            all_nodes.append(self.primary_node)
        all_nodes.extend(self.replica_nodes)
        all_nodes.extend(self.backup_nodes)

        for node in all_nodes:
            node_metrics = node.get_metrics()
            metrics["nodes"].append(node_metrics)

            # Update summary
            metrics["summary"]["total_nodes"] += 1
            if node.state == DatabaseConnectionState.HEALTHY:
                metrics["summary"]["healthy_nodes"] += 1
            elif node.state == DatabaseConnectionState.FAILED:
                metrics["summary"]["failed_nodes"] += 1

            metrics["summary"]["total_connections"] += node_metrics["metrics"][
                "total_connections"
            ]
            metrics["summary"]["total_queries"] += node_metrics["metrics"][
                "total_queries"
            ]

        return metrics

    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of database system."""
        all_metrics = self.get_all_metrics()

        # Determine overall health
        total_nodes = all_metrics["summary"]["total_nodes"]
        healthy_nodes = all_metrics["summary"]["healthy_nodes"]
        failed_nodes = all_metrics["summary"]["failed_nodes"]

        if total_nodes == 0:
            overall_status = "no_databases"
        elif failed_nodes == 0:
            overall_status = "healthy"
        elif healthy_nodes > 0:
            overall_status = "degraded"
        else:
            overall_status = "failed"

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "summary": all_metrics["summary"],
            "primary_available": bool(
                self.primary_node
                and self.primary_node.state == DatabaseConnectionState.HEALTHY
            ),
            "replicas_available": len(
                [
                    r
                    for r in self.replica_nodes
                    if r.state == DatabaseConnectionState.HEALTHY
                ]
            ),
            "backups_available": len(
                [
                    b
                    for b in self.backup_nodes
                    if b.state == DatabaseConnectionState.HEALTHY
                ]
            ),
        }


# Global database manager instance (initialized later)
database_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get or create database manager instance."""
    global database_manager
    if database_manager is None:
        # In production, DatabaseManager should always be injected via DI
        # This fallback is only for development/testing
        raise RuntimeError(
            "DatabaseManager not initialized. Use dependency injection via "
            "app.state.db_adapter or DatabaseConnectionDep."
        )
    return database_manager


# Convenience functions for common database operations
async def execute_query(query: str, *args, read_only: bool = True) -> Any:
    """Execute a database query with automatic read/write routing."""

    async def operation(conn: Connection, q: str, *params):
        if read_only:
            return await conn.fetch(q, *params)
        else:
            return await conn.execute(q, *params)

    manager = get_database_manager()
    if read_only:
        return await manager.execute_read(operation, query, *args)
    else:
        return await manager.execute_write(operation, query, *args)


async def fetch_one(query: str, *args) -> Optional[Any]:
    """Fetch single row from database."""

    async def operation(conn: Connection, q: str, *params):
        return await conn.fetchrow(q, *params)

    manager = get_database_manager()
    return await manager.execute_read(operation, query, *args)


async def fetch_all(query: str, *args) -> List[Any]:
    """Fetch all rows from database."""

    async def operation(conn: Connection, q: str, *params):
        return await conn.fetch(q, *params)

    manager = get_database_manager()
    return await manager.execute_read(operation, query, *args)


async def execute_command(query: str, *args) -> str:
    """Execute database command (INSERT, UPDATE, DELETE)."""

    async def operation(conn: Connection, q: str, *params):
        return await conn.execute(q, *params)

    manager = get_database_manager()
    return await manager.execute_write(operation, query, *args)


@asynccontextmanager
async def get_connection(read_only: bool = True) -> AsyncGenerator[Connection, None]:
    """Get database connection for manual transaction management."""
    manager = get_database_manager()
    if read_only and manager.replica_nodes:
        # Use replica for read-only operations
        available_replicas = [
            r
            for r in manager.replica_nodes
            if r.state == DatabaseConnectionState.HEALTHY
        ]
        if available_replicas:
            replica = manager._select_replica(available_replicas)
            async with replica.acquire_connection() as conn:
                yield conn
                return

    # Use primary database
    if not manager.primary_node:
        raise ConnectionError("No primary database available")

    async with manager.primary_node.acquire_connection() as conn:
        yield conn


# Database initialization function
async def initialize_database():
    """Initialize database manager."""
    manager = get_database_manager()
    await manager.initialize()


# Database cleanup function
async def close_database():
    """Close database manager."""
    manager = get_database_manager()
    await manager.close()


# FastAPI dependency for DB connection
async def get_db():
    async with get_connection(read_only=True) as conn:
        yield conn
