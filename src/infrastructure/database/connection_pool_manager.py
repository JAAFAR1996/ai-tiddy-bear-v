"""
Advanced Async Connection Pool Manager (Production-Ready)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import ssl
from typing import Dict, Optional, Any, AsyncIterator, List
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError

from src.core.exceptions import DatabaseError


# --- Singleton Pool Manager Logic (حافظنا عليه كما هو) ---
_pool_manager: Optional["ConnectionPoolManager"] = None
_pool_manager_lock = asyncio.Lock()


async def initialize_pool_manager(
    database_url: str, **kwargs
) -> "ConnectionPoolManager":
    """
    Initialize the global ConnectionPoolManager singleton.
    If already initialized, closes the old one and creates a new instance.
    """
    global _pool_manager
    async with _pool_manager_lock:
        if _pool_manager is not None:
            await _pool_manager.close()
        _pool_manager = ConnectionPoolManager(database_url, **kwargs)
        await _pool_manager.initialize()
        return _pool_manager


async def get_pool_manager() -> "ConnectionPoolManager":
    """
    Get the global ConnectionPoolManager singleton. Raises if not initialized.
    """
    if _pool_manager is None:
        raise DatabaseError(
            "Connection pool manager not initialized. Call initialize_pool_manager first."
        )
    return _pool_manager


# ------------------------- Metrics -------------------------


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

    def reset(self) -> None:
        self.total_requests = 0
        self.failed_requests = 0
        self.avg_response_time = 0.0
        self.last_reset = datetime.utcnow()


# ---------------------- Pool Manager -----------------------


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

    @staticmethod
    def _extract_ssl_from_url(url: str):
        """
        يزيل sslmode وchannel_binding من URL ويحوّل sslmode لقيمة asyncpg 'ssl' (False/True/SSLContext).
        يرجّع: (clean_url, ssl_value_or_None)
        """
        parsed = urlparse(url)
        qs = dict(parse_qsl(parsed.query))
        ssl_val = None
        mode = (qs.pop("sslmode", "") or "").strip().lower()

        # شيل channel_binding من الـ URL
        qs.pop("channel_binding", None)

        if mode in ("disable", "off"):
            ssl_val = False
        elif mode in ("require", "prefer", "allow"):
            ssl_val = True
        elif mode in ("verify-ca", "verify_full", "verify-full"):
            ctx = ssl.create_default_context()
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.check_hostname = mode != "verify-ca"
            ssl_val = ctx

        clean = urlunparse(parsed._replace(query=urlencode(qs)))
        return clean, ssl_val

    def __init__(
        self,
        database_url: str,
        min_size: int = 5,
        max_size: int = 20,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,  # 1 hour
        enable_monitoring: bool = True,
        connect_args: Optional[Dict[str, Any]] = None,
        application_name: str = "ai_teddy_bear",
        statement_timeout_ms: int = 60000,
    ):
        if min_size < 0 or max_overflow < 0 or pool_timeout <= 0 or pool_recycle <= 0:
            raise ValueError("Invalid pool parameters")
        if min_size > max_size:
            raise ValueError("min_size cannot be greater than max_size")

        # 1) enforce asyncpg كما هو
        normalized = self._normalize_asyncpg_url(database_url)
        # 2) شِل sslmode من URL وحوّله لقيمة ssl
        clean_url, ssl_from_url = self._extract_ssl_from_url(normalized)
        self.database_url = clean_url
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

        self.logger = logging.getLogger("ai_teddy_bear.db")

        base_server_settings = {
            "application_name": application_name,
            "statement_timeout": str(statement_timeout_ms),
        }
        self._connect_args = {
            "command_timeout": max(statement_timeout_ms // 1000, 1),
            "server_settings": base_server_settings,
        }
        if connect_args:
            extra = dict(connect_args)
            # Remove unsupported keys for asyncpg
            for key in [
                "sslmode",
                "options",
                "application_name",
                "client_encoding",
                "connect_timeout",
                "fallback_application_name",
                "keepalives",
                "keepalives_idle",
                "keepalives_interval",
                "keepalives_count",
                "options",
                "service",
                "target_session_attrs",
                "channel_binding",
            ]:
                extra.pop(key, None)
            ss = extra.pop("server_settings", {})
            self._connect_args.update(extra)
            self._connect_args["server_settings"].update(ss)
        # لو فيه ssl من URL ومو محدّد في connect_args، طبّقه
        if ssl_from_url is not None and "ssl" not in self._connect_args:
            self._connect_args["ssl"] = ssl_from_url

        # 🔍 DEBUG: طباعة للتشخيص (مرة واحدة) - مع إخفاء كلمة المرور
        self.logger.warning({"connect_args_final": self._connect_args})
        # إخفاء كلمة المرور في URL قبل اللوج
        safe_db_url = re.sub(
            r"://([^:]+):([^@]+)@", r"://\1:***MASKED***@", self.database_url
        )
        self.logger.warning({"db_url_final": safe_db_url})

        # DEBUG: Log the final connect_args to ensure no unsupported keys remain
        self.logger.debug(f"Final connect_args for asyncpg: {self._connect_args}")

    async def initialize(self) -> None:
        """Initialize the connection pool with optimized settings."""
        try:
            self.engine = create_async_engine(
                self.database_url,
                pool_size=self.min_size,
                max_overflow=self.max_overflow,
                pool_timeout=self.pool_timeout,
                pool_recycle=self.pool_recycle,
                pool_pre_ping=True,
                echo=False,
                future=True,
                connect_args=self._connect_args,
            )

            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
            )

            if self.enable_monitoring:
                self._setup_monitoring()  # الاسم كما هو

            await self._test_connection()

            self.logger.info(
                "Database connection pool initialized",
                extra={
                    "min_size": self.min_size,
                    "max_size": self.max_size,
                    "max_overflow": self.max_overflow,
                    "pool_timeout": self.pool_timeout,
                    "pool_recycle": self.pool_recycle,
                },
            )
        except Exception as e:
            self.logger.critical("Failed to initialize connection pool", exc_info=True)
            raise DatabaseError(
                "Connection pool initialization failed",
                context={"operation": "initialize", "error": str(e)},
            ) from e

    def _setup_monitoring(self) -> None:
        """Set up connection pool monitoring. (حافظنا على الاسم ولكن أصلحنا المنطق)"""
        sync_pool = self.engine.sync_engine.pool  # type: ignore[union-attr]

        @event.listens_for(sync_pool, "connect")
        def on_connect(dbapi_conn, _connection_record):
            self.metrics.total_connections += 1
            self.metrics.idle_connections += 1
            self.metrics.peak_connections = max(
                self.metrics.peak_connections, self.metrics.active_connections
            )
            if self.enable_monitoring:
                self.connection_history.append(
                    {
                        "event": "connect",
                        "timestamp": datetime.utcnow().isoformat(),
                        "connection_id": id(dbapi_conn),
                    }
                )

        @event.listens_for(sync_pool, "checkout")
        def on_checkout(dbapi_conn, _connection_record, _proxy):
            self.metrics.active_connections += 1
            self.metrics.idle_connections = max(0, self.metrics.idle_connections - 1)
            self.metrics.peak_connections = max(
                self.metrics.peak_connections, self.metrics.active_connections
            )
            if self.enable_monitoring:
                self.connection_history.append(
                    {
                        "event": "checkout",
                        "timestamp": datetime.utcnow().isoformat(),
                        "connection_id": id(dbapi_conn),
                    }
                )

        @event.listens_for(sync_pool, "checkin")
        def on_checkin(dbapi_conn, _connection_record):
            self.metrics.active_connections = max(
                0, self.metrics.active_connections - 1
            )
            self.metrics.idle_connections += 1
            if self.enable_monitoring:
                self.connection_history.append(
                    {
                        "event": "checkin",
                        "timestamp": datetime.utcnow().isoformat(),
                        "connection_id": id(dbapi_conn),
                    }
                )

        @event.listens_for(sync_pool, "close")
        def on_close(dbapi_conn, _connection_record):
            # اتصال DBAPI تم إغلاقه
            self.metrics.idle_connections = max(0, self.metrics.idle_connections - 1)
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
                if result.scalar() != 1:
                    raise DatabaseError("Connection test failed (SELECT 1)")
        except Exception as e:
            raise DatabaseError(
                "Database connection test failed",
                context={"operation": "test_connection", "error": str(e)},
            ) from e

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """
        Get database session with automatic cleanup and error handling.
        Usage:
            async with pool_manager.get_session() as session:
                await session.execute(text("SELECT 1"))
        """
        if not self.session_factory:
            raise DatabaseError("Connection pool not initialized")

        start_time = time.time()
        session: Optional[AsyncSession] = None

        # metrics: بدء طلب
        async with self._lock:
            self.metrics.total_requests += 1
            self.metrics.active_connections += 1
            self.metrics.idle_connections = max(0, self.metrics.idle_connections - 1)
            self.metrics.peak_connections = max(
                self.metrics.peak_connections, self.metrics.active_connections
            )

        try:
            session = self.session_factory()
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            if session:
                try:
                    await session.rollback()
                except SQLAlchemyError as rollback_error:
                    self.logger.error(
                        "Session rollback failed", extra={"error": str(rollback_error)}
                    )
            async with self._lock:
                self.metrics.failed_requests += 1
            raise DatabaseError(
                "Database session error",
                context={"operation": "session_management", "error": str(e)},
            ) from e
        finally:
            if session:
                try:
                    await session.close()
                except SQLAlchemyError as close_error:
                    self.logger.error(
                        "Session close failed", extra={"error": str(close_error)}
                    )

            elapsed = time.time() - start_time
            async with self._lock:
                self.metrics.active_connections = max(
                    0, self.metrics.active_connections - 1
                )
                self.metrics.idle_connections += 1
                n = self.metrics.total_requests
                if n > 0:
                    self.metrics.avg_response_time = (
                        (self.metrics.avg_response_time * (n - 1)) + elapsed
                    ) / n

    async def get_pool_status(self) -> Dict[str, Any]:
        """Get current pool status and metrics."""
        if not self.engine:
            return {"status": "not_initialized"}

        pool = self.engine.pool
        try:
            pool_size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            overflow = pool.overflow()
        except Exception:
            # لتجنب كسر الكود لو تغيّر داخليًا في SQLAlchemy
            pool_size = checked_in = checked_out = overflow = -1

        return {
            "status": "active",
            "pool_size": pool_size,
            "checked_in": checked_in,
            "checked_out": checked_out,
            "overflow": overflow,
            "metrics": {
                "total_connections": self.metrics.total_connections,
                "active_connections": self.metrics.active_connections,
                "idle_connections": self.metrics.idle_connections,
                "peak_connections": self.metrics.peak_connections,
                "total_requests": self.metrics.total_requests,
                "failed_requests": self.metrics.failed_requests,
                "success_rate": (
                    (self.metrics.total_requests - self.metrics.failed_requests)
                    / max(self.metrics.total_requests, 1)
                    * 100.0
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
        health_status = {"healthy": True, "issues": [], "recommendations": []}
        try:
            await self._test_connection()

            status = await self.get_pool_status()
            metrics = status.get("metrics", {})
            success_rate = metrics.get("success_rate", 100.0)
            if success_rate < 95.0:
                health_status["healthy"] = False
                health_status["issues"].append(f"Low success rate: {success_rate:.1f}%")
                health_status["recommendations"].append(
                    "Check database connectivity and query performance"
                )

            avg_response_time = metrics.get("avg_response_time", 0.0)
            if avg_response_time > 1000.0:
                health_status["issues"].append(
                    f"High response time: {avg_response_time}ms"
                )
                health_status["recommendations"].append(
                    "Optimize queries or increase pool size"
                )

            checked_out = status.get("checked_out", 0) or 0
            pool_size = status.get("pool_size", 1) or 1
            try:
                utilization = (float(checked_out) / float(pool_size)) * 100.0
                if utilization > 80.0:
                    health_status["issues"].append(
                        f"High pool utilization: {utilization:.1f}%"
                    )
                    health_status["recommendations"].append(
                        "Consider increasing pool size"
                    )
            except Exception:
                pass

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
                self.logger.error(
                    "Error closing connection pool", extra={"error": str(e)}
                )
            finally:
                self.engine = None
                self.session_factory = None

    # -------------------- Internals ------------------------

    @staticmethod
    def _normalize_asyncpg_url(url: str) -> str:
        """Force asyncpg driver for PostgreSQL URLs."""
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url
