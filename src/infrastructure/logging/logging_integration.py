"""
Logging Integration - FastAPI and Application Integration
=======================================================
Complete logging integration for AI Teddy Bear system:
- FastAPI application setup with logging
- Database query logging
- Provider call logging
- Cache operation logging
- Business logic logging
- Error tracking and alerting
"""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable

from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from .structured_logger import (
    StructuredLogger,
    LogContext,
    LogCategory,
    LogLevel,
    get_logger,
    set_log_context,
    http_logger,
    database_logger,
    cache_logger,
    provider_logger,
    security_logger,
    child_safety_logger,
    performance_logger,
    business_logger,
    system_logger,
    audit_logger,
)
from .logging_middleware import (
    RequestLoggingMiddleware,
    SecurityLoggingMiddleware,
    ChildSafetyLoggingMiddleware,
    setup_logging_middleware,
)


class LoggingIntegration:
    """Main class for logging integration and management."""

    def __init__(self):
        self.logger = get_logger("logging_integration")
        self.log_processors = []
        self.error_handlers = []
        self.metrics = {
            "total_logs": 0,
            "logs_by_level": {},
            "logs_by_category": {},
            "errors_count": 0,
            "child_safety_events": 0,
            "security_events": 0,
        }

        # Handler protection
        self._logger_handlers_snapshot = {}

        # Background tasks
        self._log_processing_task = None
        self._metrics_collection_task = None
        self._log_rotation_task = None
        self._handler_check_task = None

    async def start(self):
        """Start logging integration services with production safety checks and logger health check."""
        try:
            # --- Production handler health check ---
            from .structured_logger import StructuredLogger, _LOGGER_REGISTRY

            env = os.getenv("ENVIRONMENT", "development")
            health = StructuredLogger.get_health_status()
            if env == "production":
                critical_failures = health.get("critical_failures", [])
                if critical_failures:
                    system_logger.critical(
                        f"Critical logging handler failure(s) in production: {critical_failures}",
                        category=LogCategory.SYSTEM,
                    )
                    raise SystemExit(
                        f"Startup aborted: Logging handler failure(s): {critical_failures}"
                    )

                # --- Logger instance health check ---
                for name, logger in _LOGGER_REGISTRY.items():
                    if not isinstance(logger, StructuredLogger):
                        system_logger.critical(
                            f"Logger '{name}' is not a StructuredLogger instance in production!",
                            category=LogCategory.SYSTEM,
                        )
                        raise SystemExit(
                            f"Startup aborted: Logger '{name}' is not a StructuredLogger instance."
                        )

            # --- Snapshot logger handlers after startup ---
            self._logger_handlers_snapshot = {}
            for name, logger in _LOGGER_REGISTRY.items():
                # Save a tuple of handler ids for immutability
                self._logger_handlers_snapshot[name] = tuple(
                    id(h) for h in getattr(logger.logger, "handlers", [])
                )

            # Start background tasks
            self._log_processing_task = asyncio.create_task(self._process_logs())
            self._metrics_collection_task = asyncio.create_task(self._collect_metrics())
            self._log_rotation_task = asyncio.create_task(self._manage_log_rotation())
            self._handler_check_task = asyncio.create_task(self._check_handlers_integrity())

            # Initialize application logging
            system_logger.info(
                "Logging integration started",
                category=LogCategory.SYSTEM,
                metadata={
                    "log_level": os.getenv("LOG_LEVEL", "INFO"),
                    "elasticsearch_enabled": bool(os.getenv("ELASTICSEARCH_HOSTS")),
                    "cloudwatch_enabled": bool(os.getenv("CLOUDWATCH_LOG_GROUP")),
                    "file_logging_enabled": True,
                },
            )

        except Exception as e:
            self.logger.error("Failed to start logging integration", error=e)
            raise

    async def _check_handlers_integrity(self):
        """Background task to check logger handlers integrity in production."""
        from .structured_logger import _LOGGER_REGISTRY

        env = os.getenv("ENVIRONMENT", "development")
        while True:
            try:
                await asyncio.sleep(60)  # Check every 60 seconds
                if env != "production":
                    continue
                for name, logger in _LOGGER_REGISTRY.items():
                    expected = self._logger_handlers_snapshot.get(name)
                    current = tuple(
                        id(h) for h in getattr(logger.logger, "handlers", [])
                    )
                    if expected != current:
                        system_logger.critical(
                            f"Logger '{name}' handlers changed after startup in production!",
                            category=LogCategory.SYSTEM,
                        )
                        raise SystemExit(
                            f"Critical: Logger '{name}' handlers changed after startup."
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Handler integrity check error", error=e)

    async def stop(self):
        """Stop logging integration services."""
        try:
            # Cancel background tasks
            if self._log_processing_task:
                self._log_processing_task.cancel()
            if self._metrics_collection_task:
                self._metrics_collection_task.cancel()
            if self._log_rotation_task:
                self._log_rotation_task.cancel()
            if self._handler_check_task:
                self._handler_check_task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(
                self._log_processing_task,
                self._metrics_collection_task,
                self._log_rotation_task,
                self._handler_check_task,
                return_exceptions=True,
            )

            system_logger.info(
                "Logging integration stopped", category=LogCategory.SYSTEM
            )

        except Exception as e:
            self.logger.error("Error stopping logging integration", error=e)

    async def _process_logs(self):
        """Background task to process and forward logs with production failure escalation."""
        failure_count = 0
        while True:
            try:
                await asyncio.sleep(30)  # Process every 30 seconds

                # Update metrics
                self._update_metrics()

                # Process any queued log processors
                for processor in self.log_processors:
                    try:
                        await processor()
                    except Exception as e:
                        self.logger.error(f"Log processor failed: {str(e)}")

                failure_count = 0  # Reset on success

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Log processing error", error=e)
                failure_count += 1
                env = os.getenv("ENVIRONMENT", "development")
                if env == "production" and failure_count >= 3:
                    system_logger.critical(
                        "_process_logs failed 3 times in a row in production. Shutting down.",
                        category=LogCategory.SYSTEM,
                    )
                    raise SystemExit(
                        "Critical: _process_logs failed repeatedly in production."
                    )

    async def _collect_metrics(self):
        """Collect logging metrics with production failure escalation."""
        failure_count = 0
        while True:
            try:
                await asyncio.sleep(300)  # Collect every 5 minutes
                
                # Update metrics
                self._update_metrics()

                # Log metrics summary
                performance_logger.info(
                    "Logging metrics collected",
                    category=LogCategory.PERFORMANCE,
                    metadata=self.metrics,
                )

                failure_count = 0  # Reset on success

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Metrics collection error", error=e)
                failure_count += 1
                env = os.getenv("ENVIRONMENT", "development")
                if env == "production" and failure_count >= 3:
                    system_logger.critical(
                        "_collect_metrics failed 3 times in a row in production. Shutting down.",
                        category=LogCategory.SYSTEM,
                    )
                    raise SystemExit(
                        "Critical: _collect_metrics failed repeatedly in production."
                    )

    async def _manage_log_rotation(self):
        """Manage log file rotation and cleanup with production failure escalation."""
        failure_count = 0
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour

                # This would typically handle log file rotation
                # For now, just log the rotation check
                system_logger.debug(
                    "Log rotation check completed", category=LogCategory.SYSTEM
                )

                failure_count = 0  # Reset on success

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Log rotation error", error=e)
                failure_count += 1
                env = os.getenv("ENVIRONMENT", "development")
                if env == "production" and failure_count >= 3:
                    system_logger.critical(
                        "_manage_log_rotation failed 3 times in a row in production. Shutting down.",
                        category=LogCategory.SYSTEM,
                    )
                    raise SystemExit(
                        "Critical: _manage_log_rotation failed repeatedly in production."
                    )

    def _update_metrics(self):
        """Update internal logging metrics."""
        from .structured_logger import SecurityFilter
        
        self.metrics["security_events"] = len(SecurityFilter.get_audit_log())
        self.metrics["total_logs"] += 1

    def add_log_processor(self, processor: Callable):
        """Add a custom log processor function."""
        self.log_processors.append(processor)

    def add_error_handler(self, handler: Callable):
        """Add a custom error handler."""
        self.error_handlers.append(handler)

    def get_metrics(self) -> Dict[str, Any]:
        """Get current logging metrics."""
        return self.metrics.copy()


# Global logging integration instance
logging_integration = LoggingIntegration()


@asynccontextmanager
async def logging_lifespan(app: FastAPI):
    """Lifespan context manager for logging integration."""
    # Startup
    await logging_integration.start()

    try:
        yield
    finally:
        # Shutdown
        await logging_integration.stop()


# Database logging decorators and utilities
def log_database_operation(operation_type: str, table_name: str = None):
    """Decorator for logging database operations."""

    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"db_{operation_type}_{int(start_time)}"

            database_logger.info(
                f"Database operation started: {operation_type}",
                category=LogCategory.DATABASE,
                metadata={
                    "operation_type": operation_type,
                    "table_name": table_name,
                    "operation_id": operation_id,
                },
            )

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                database_logger.info(
                    f"Database operation completed: {operation_type}",
                    category=LogCategory.DATABASE,
                    duration_ms=duration_ms,
                    metadata={
                        "operation_type": operation_type,
                        "table_name": table_name,
                        "operation_id": operation_id,
                        "success": True,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                database_logger.error(
                    f"Database operation failed: {operation_type}",
                    category=LogCategory.DATABASE,
                    error=e,
                    duration_ms=duration_ms,
                    metadata={
                        "operation_type": operation_type,
                        "table_name": table_name,
                        "operation_id": operation_id,
                        "success": False,
                    },
                )
                raise

        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"db_{operation_type}_{int(start_time)}"

            database_logger.info(
                f"Database operation started: {operation_type}",
                category=LogCategory.DATABASE,
                metadata={
                    "operation_type": operation_type,
                    "table_name": table_name,
                    "operation_id": operation_id,
                },
            )

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                database_logger.info(
                    f"Database operation completed: {operation_type}",
                    category=LogCategory.DATABASE,
                    duration_ms=duration_ms,
                    metadata={
                        "operation_type": operation_type,
                        "table_name": table_name,
                        "operation_id": operation_id,
                        "success": True,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                database_logger.error(
                    f"Database operation failed: {operation_type}",
                    category=LogCategory.DATABASE,
                    error=e,
                    duration_ms=duration_ms,
                    metadata={
                        "operation_type": operation_type,
                        "table_name": table_name,
                        "operation_id": operation_id,
                        "success": False,
                    },
                )
                raise

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def log_provider_call(provider_id: str, provider_type: str, operation: str):
    """Decorator for logging provider calls."""

    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            call_id = f"provider_{provider_id}_{int(start_time)}"

            provider_logger.info(
                f"Provider call started: {provider_id}.{operation}",
                category=LogCategory.PROVIDER,
                metadata={
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                    "operation": operation,
                    "call_id": call_id,
                },
            )

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                provider_logger.info(
                    f"Provider call completed: {provider_id}.{operation}",
                    category=LogCategory.PROVIDER,
                    duration_ms=duration_ms,
                    metadata={
                        "provider_id": provider_id,
                        "provider_type": provider_type,
                        "operation": operation,
                        "call_id": call_id,
                        "success": True,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                provider_logger.error(
                    f"Provider call failed: {provider_id}.{operation}",
                    category=LogCategory.PROVIDER,
                    error=e,
                    duration_ms=duration_ms,
                    metadata={
                        "provider_id": provider_id,
                        "provider_type": provider_type,
                        "operation": operation,
                        "call_id": call_id,
                        "success": False,
                    },
                )
                raise

        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            call_id = f"provider_{provider_id}_{int(start_time)}"

            provider_logger.info(
                f"Provider call started: {provider_id}.{operation}",
                category=LogCategory.PROVIDER,
                metadata={
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                    "operation": operation,
                    "call_id": call_id,
                },
            )

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                provider_logger.info(
                    f"Provider call completed: {provider_id}.{operation}",
                    category=LogCategory.PROVIDER,
                    duration_ms=duration_ms,
                    metadata={
                        "provider_id": provider_id,
                        "provider_type": provider_type,
                        "operation": operation,
                        "call_id": call_id,
                        "success": True,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                provider_logger.error(
                    f"Provider call failed: {provider_id}.{operation}",
                    category=LogCategory.PROVIDER,
                    error=e,
                    duration_ms=duration_ms,
                    metadata={
                        "provider_id": provider_id,
                        "provider_type": provider_type,
                        "operation": operation,
                        "call_id": call_id,
                        "success": False,
                    },
                )
                raise

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def log_cache_operation(cache_name: str, operation: str):
    """Decorator for logging cache operations."""

    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                cache_logger.info(
                    f"Cache operation: {cache_name}.{operation}",
                    category=LogCategory.CACHE,
                    duration_ms=duration_ms,
                    metadata={
                        "cache_name": cache_name,
                        "operation": operation,
                        "hit": result is not None if operation == "get" else None,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                cache_logger.error(
                    f"Cache operation failed: {cache_name}.{operation}",
                    category=LogCategory.CACHE,
                    error=e,
                    duration_ms=duration_ms,
                    metadata={"cache_name": cache_name, "operation": operation},
                )
                raise

        def sync_wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                cache_logger.info(
                    f"Cache operation: {cache_name}.{operation}",
                    category=LogCategory.CACHE,
                    duration_ms=duration_ms,
                    metadata={
                        "cache_name": cache_name,
                        "operation": operation,
                        "hit": result is not None if operation == "get" else None,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                cache_logger.error(
                    f"Cache operation failed: {cache_name}.{operation}",
                    category=LogCategory.CACHE,
                    error=e,
                    duration_ms=duration_ms,
                    metadata={"cache_name": cache_name, "operation": operation},
                )
                raise

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def log_business_operation(operation_type: str, child_id: str = None):
    """Decorator for logging business operations."""

    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"business_{operation_type}_{int(start_time)}"

            business_logger.info(
                f"Business operation started: {operation_type}",
                category=LogCategory.BUSINESS,
                metadata={
                    "operation_type": operation_type,
                    "operation_id": operation_id,
                    "child_id": child_id,
                },
            )

            # Log child safety if child is involved
            if child_id:
                child_safety_logger.child_safety(
                    f"Child business operation: {operation_type}",
                    child_id=child_id,
                    metadata={
                        "operation_type": operation_type,
                        "operation_id": operation_id,
                    },
                )

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                business_logger.info(
                    f"Business operation completed: {operation_type}",
                    category=LogCategory.BUSINESS,
                    duration_ms=duration_ms,
                    metadata={
                        "operation_type": operation_type,
                        "operation_id": operation_id,
                        "child_id": child_id,
                        "success": True,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                business_logger.error(
                    f"Business operation failed: {operation_type}",
                    category=LogCategory.BUSINESS,
                    error=e,
                    duration_ms=duration_ms,
                    metadata={
                        "operation_type": operation_type,
                        "operation_id": operation_id,
                        "child_id": child_id,
                        "success": False,
                    },
                )

                # Log as child safety event if child is involved
                if child_id:
                    child_safety_logger.error(
                        f"Child business operation failed: {operation_type}",
                        error=e,
                        child_id=child_id,
                        metadata={
                            "operation_type": operation_type,
                            "operation_id": operation_id,
                            "requires_investigation": True,
                        },
                    )

                raise

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # Similar sync wrapper would go here
            return func

    return decorator


def add_logging_routes(app: FastAPI):
    """Add logging management routes to FastAPI application."""

    @app.get("/api/logging/metrics")
    async def get_logging_metrics():
        """Get logging metrics and statistics."""
        return logging_integration.get_metrics()

    @app.get("/api/logging/health")
    async def get_logging_health():
        """Get logging system health status."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "integrations": {
                "elasticsearch": bool(os.getenv("ELASTICSEARCH_HOSTS")),
                "cloudwatch": bool(os.getenv("CLOUDWATCH_LOG_GROUP")),
                "file_logging": True,
            },
            "metrics": logging_integration.get_metrics(),
        }

    @app.post("/api/logging/test")
    async def test_logging(
        level: str = "info",
        category: str = "application",
        message: str = "Test log message",
    ):
        """Test logging functionality."""
        logger = get_logger("test_logger")

        if level.lower() == "debug":
            logger.debug(message, category=LogCategory(category))
        elif level.lower() == "info":
            logger.info(message, category=LogCategory(category))
        elif level.lower() == "warning":
            logger.warning(message, category=LogCategory(category))
        elif level.lower() == "error":
            logger.error(message, category=LogCategory(category))
        else:
            logger.info(message, category=LogCategory(category))

        return {
            "message": "Test log sent",
            "level": level,
            "category": category,
            "timestamp": datetime.now().isoformat(),
        }


def create_logging_app() -> FastAPI:
    """Create FastAPI application with logging integration."""
    app = FastAPI(
        title="AI Teddy Bear Logging API", version="1.0.0", lifespan=logging_lifespan
    )

    # Setup logging middleware
    setup_logging_middleware(app)

    # Add logging routes
    add_logging_routes(app)

    return app


def setup_logging_integration(app: FastAPI) -> LoggingIntegration:
    """Setup logging integration with an existing FastAPI app."""
    # Setup logging middleware
    setup_logging_middleware(app)

    # Add logging routes
    add_logging_routes(app)

    return logging_integration


def add_log_processor(processor: Callable):
    """Add a custom log processor function."""
    logging_integration.add_log_processor(processor)


def add_error_handler(handler: Callable):
    """Add a custom error handler."""
    logging_integration.add_error_handler(handler)


def get_metrics() -> Dict[str, Any]:
    """Get current logging metrics."""
    return logging_integration.get_metrics()


# Create the main logging application
logging_app = create_logging_app()
