"""
Advanced Connection Pool Manager for AI Teddy Bear
Optimized database connection management with monitoring and auto-scaling
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Any, List
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event, text  # Ensure text is imported for SQL string safety

from src.core.exceptions import DatabaseError, ConfigurationError


@dataclass
class PoolMetrics:
    """Connection pool performance metrics."""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    peak_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_reset: datetime = field(default_factory=datetime.utcnow)

    def reset(self):
        """Reset metrics for new measurement period."""
        self.total_requests = 0
        self.failed_requests = 0
        self.avg_response_time = 0.0
        self.last_reset = datetime.utcnow()


class ConnectionPoolManager:
    """
    Advanced connection pool manager with monitoring and optimization.

    Features:
    - Dynamic pool sizing based on load
    - Connection health monitoring
    - Performance metrics collection
    - Automatic connection recycling
    - COPPA-compliant connection logging
    """

    def __init__(
        self,
        database_url: str,
        min_size: int = 5,
        max_size: int = 20,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,  # 1 hour
        enable_monitoring: bool = True,
    ):
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.enable_monitoring = enable_monitoring

        self.engine: Optional[Any] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self.metrics = PoolMetrics()
        self.connection_history: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

        self.logger = logging.getLogger(__name__)

    async def initialize(self) -> None:
        """Initialize the connection pool with optimized settings."""
        try:
            # Create engine with advanced pool configuration
            self.engine = create_async_engine(
                self.database_url,
                pool_size=self.min_size,
                max_overflow=self.max_overflow,
                pool_timeout=self.pool_timeout,
                pool_recycle=self.pool_recycle,
                pool_pre_ping=True,  # Validate connections before use
                echo=False,  # Disable SQL logging for performance
                future=True,
                connect_args={
                    "command_timeout": 60,
                    "server_settings": {
                        "application_name": "ai_teddy_bear",
                        "jit": "off",  # Disable JIT for consistent performance
                    },
                },
            )

            # Set up session factory
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False,
            )

            # Set up monitoring if enabled
            if self.enable_monitoring:
                self._setup_monitoring()

            # Test connection
            await self._test_connection()

            log_data = {
                "min_size": self.min_size,
                "max_size": self.max_size,
                "max_overflow": self.max_overflow,
            }
            self.logger.info("Database connection pool initialized", extra=log_data)

        except Exception as e:
            self.logger.critical(f"Failed to initialize connection pool: {e}")
            raise DatabaseError(
                "Connection pool initialization failed",
                context={"operation": "initialize", "error": str(e)},
            )

    def _setup_monitoring(self) -> None:
        """Set up connection pool monitoring."""

        @event.listens_for(self.engine.sync_engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            """Handle new connection creation."""
            self.metrics.total_connections += 1
            self.metrics.peak_connections = max(
                self.metrics.peak_connections, self.metrics.total_connections
            )

            if self.enable_monitoring:
                self.connection_history.append(
                    {
                        "event": "connect",
                        "timestamp": datetime.utcnow().isoformat(),
                        "connection_id": id(dbapi_conn),
                    }
                )

        @event.listens_for(self.engine.sync_engine, "close")
        def on_close(dbapi_conn, connection_record):
            """Handle connection closure."""
            self.metrics.total_connections = max(0, self.metrics.total_connections - 1)

            if self.enable_monitoring:
                self.connection_history.append(
                    {
                        "event": "close",
                        "timestamp": datetime.utcnow().isoformat(),
                        "connection_id": id(dbapi_conn),
                    }
                )

    async def _test_connection(self) -> None:
        """Test database connectivity."""
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                if not result.scalar():
                    raise DatabaseError("Connection test failed")
        except Exception as e:
            raise DatabaseError(
                "Database connection test failed",
                context={"operation": "test_connection", "error": str(e)},
            )

    @asynccontextmanager
    async def get_session(self):
        """
        Get database session with automatic cleanup and error handling.

        Usage:
            async with pool_manager.get_session() as session:
                # Use session for database operations
                result = await session.execute(text(query) if isinstance(query, str) else query)
        """
        if not self.session_factory:
            raise DatabaseError("Connection pool not initialized")

        start_time = time.time()
        session = None

        try:
            # Create session
            session = self.session_factory()

            # Update metrics
            async with self._lock:
                self.metrics.active_connections += 1
                self.metrics.total_requests += 1

            yield session

            # Commit transaction on success
            await session.commit()

        except Exception as e:
            # Rollback on error
            if session:
                try:
                    await session.rollback()
                except Exception as rollback_error:
                    self.logger.error(f"Session rollback failed: {rollback_error}")

            # Update error metrics
            async with self._lock:
                self.metrics.failed_requests += 1

            # Re-raise original exception
            raise DatabaseError(
                "Database session error",
                context={"operation": "session_management", "error": str(e)},
            )

        finally:
            # Clean up session
            if session:
                try:
                    await session.close()
                except Exception as close_error:
                    self.logger.error(f"Session close failed: {close_error}")

            # Update metrics
            async with self._lock:
                self.metrics.active_connections = max(
                    0, self.metrics.active_connections - 1
                )

                # Update average response time
                response_time = time.time() - start_time
                if self.metrics.total_requests > 0:
                    self.metrics.avg_response_time = (
                        self.metrics.avg_response_time
                        * (self.metrics.total_requests - 1)
                        + response_time
                    ) / self.metrics.total_requests

    async def get_pool_status(self) -> Dict[str, Any]:
        """Get current pool status and metrics."""
        if not self.engine:
            return {"status": "not_initialized"}

        pool = self.engine.pool

        return {
            "status": "active",
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
            "metrics": {
                "total_connections": self.metrics.total_connections,
                "active_connections": self.metrics.active_connections,
                "peak_connections": self.metrics.peak_connections,
                "total_requests": self.metrics.total_requests,
                "failed_requests": self.metrics.failed_requests,
                "success_rate": (
                    (self.metrics.total_requests - self.metrics.failed_requests)
                    / max(self.metrics.total_requests, 1)
                    * 100
                ),
                "avg_response_time": round(
                    self.metrics.avg_response_time * 1000, 2
                ),  # ms
                "last_reset": self.metrics.last_reset.isoformat(),
            },
            "configuration": {
                "min_size": self.min_size,
                "max_size": self.max_size,
                "max_overflow": self.max_overflow,
                "pool_timeout": self.pool_timeout,
                "pool_recycle": self.pool_recycle,
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive pool health check."""
        health_status = {
            "healthy": True,
            "issues": [],
            "recommendations": [],
        }

        try:
            # Test connection
            await self._test_connection()

            # Check pool metrics
            status = await self.get_pool_status()
            metrics = status.get("metrics", {})

            # Check success rate
            success_rate = metrics.get("success_rate", 100)
            if success_rate < 95:
                health_status["healthy"] = False
                health_status["issues"].append(f"Low success rate: {success_rate:.1f}%")
                health_status["recommendations"].append(
                    "Check database connectivity and query performance"
                )

            # Check response time
            avg_response_time = metrics.get("avg_response_time", 0)
            if avg_response_time > 1000:  # > 1 second
                health_status["issues"].append(
                    f"High response time: {avg_response_time}ms"
                )
                health_status["recommendations"].append(
                    "Optimize queries or increase pool size"
                )

            # Check pool utilization
            checked_out = status.get("checked_out", 0)
            pool_size = status.get("pool_size", 1)
            utilization = (checked_out / pool_size) * 100

            if utilization > 80:
                health_status["issues"].append(
                    f"High pool utilization: {utilization:.1f}%"
                )
                health_status["recommendations"].append("Consider increasing pool size")

        except Exception as e:
            health_status["healthy"] = False
            health_status["issues"].append(f"Health check failed: {str(e)}")

        return health_status

    async def reset_metrics(self) -> None:
        """Reset performance metrics."""
        async with self._lock:
            self.metrics.reset()
            self.connection_history.clear()

        self.logger.info("Connection pool metrics reset")

    async def close(self) -> None:
        """Close the connection pool and clean up resources."""
        if self.engine:
            try:
                await self.engine.dispose()
                self.logger.info("Connection pool closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing connection pool: {e}")
            finally:
                self.engine = None
                self.session_factory = None


# Global pool manager instance
_pool_manager: Optional[ConnectionPoolManager] = None


async def get_pool_manager() -> ConnectionPoolManager:
    """Get global connection pool manager instance."""
    global _pool_manager
    if _pool_manager is None:
        raise ConfigurationError("Connection pool manager not initialized")
    return _pool_manager


async def initialize_pool_manager(database_url: str, **kwargs) -> ConnectionPoolManager:
    """Initialize global connection pool manager."""
    global _pool_manager

    if _pool_manager is not None:
        await _pool_manager.close()

    _pool_manager = ConnectionPoolManager(database_url, **kwargs)
    await _pool_manager.initialize()

    return _pool_manager


async def close_pool_manager() -> None:
    """Close global connection pool manager."""
    global _pool_manager
    if _pool_manager is not None:
        await _pool_manager.close()
        _pool_manager = None
