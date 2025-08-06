"""
🧸 AI TEDDY BEAR V5 - MONITORING INTEGRATION
=============================================
FastAPI integration for logging, metrics, and health checks.
Provides flexible monitoring setup with comprehensive error handling.
"""

import asyncio
import logging
import platform
import sys
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware


# Standard logger to avoid circular imports
logger = logging.getLogger(__name__)


class MonitoringConfig:
    """Configuration for monitoring integration."""

    def __init__(
        self,
        enable_metrics: bool = True,
        enable_request_logging: bool = True,
        enable_health_checks: bool = True,
        enable_audit_logging: bool = True,
        enable_error_handling: bool = True,
        metrics_endpoint: str = "/metrics",
        health_endpoint: str = "/health",
        monitoring_status_endpoint: str = "/monitoring/status",
        audit_endpoints_prefix: str = "/admin/audit",
        log_level: str = "INFO",
        request_timeout: float = 30.0,
        max_request_body_size: int = 1024 * 1024,  # 1MB
        custom_middleware: Optional[List[Callable]] = None,
        custom_exception_handlers: Optional[Dict[type, Callable]] = None,
    ):
        self.enable_metrics = enable_metrics
        self.enable_request_logging = enable_request_logging
        self.enable_health_checks = enable_health_checks
        self.enable_audit_logging = enable_audit_logging
        self.enable_error_handling = enable_error_handling
        self.metrics_endpoint = metrics_endpoint
        self.health_endpoint = health_endpoint
        self.monitoring_status_endpoint = monitoring_status_endpoint
        self.audit_endpoints_prefix = audit_endpoints_prefix
        self.log_level = log_level
        self.request_timeout = request_timeout
        self.max_request_body_size = max_request_body_size
        self.custom_middleware = custom_middleware or []
        self.custom_exception_handlers = custom_exception_handlers or {}


class MonitoringIntegration:
    """
    Main monitoring integration class with flexible configuration.
    Avoids circular imports by lazy loading monitoring components.
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()
        self._components_loaded = False
        self._startup_complete = False
        self._shutdown_complete = False

        # Lazy-loaded components to avoid circular imports
        self._logging_components = None
        self._metrics_components = None
        self._health_components = None
        self._audit_components = None

        # Error tracking
        self._startup_errors = []
        self._runtime_errors = []

    def _load_logging_components(self):
        """Lazy load logging components to avoid circular imports."""
        if self._logging_components is not None:
            return self._logging_components

        try:
            from .logging.production_logger import (
                setup_logging,
                get_logger,
                RequestLogger,
                performance_logger,
                security_logger,
                audit_logger,
            )

            self._logging_components = {
                "setup_logging": setup_logging,
                "get_logger": get_logger,
                "RequestLogger": RequestLogger,
                "performance_logger": performance_logger,
                "security_logger": security_logger,
                "audit_logger": audit_logger,
            }

            logger.info("✅ Logging components loaded successfully")

        except ImportError as e:
            logger.error(f"Failed to load logging components: {e}")
            self._startup_errors.append(f"Logging components: {e}")
            # Provide fallback components
            self._logging_components = {
                "setup_logging": lambda: None,
                "get_logger": lambda name, component=None: logging.getLogger(name),
                "RequestLogger": type(
                    "RequestLogger",
                    (),
                    {
                        "log_request_start": lambda self, **kwargs: None,
                        "log_request_end": lambda self, **kwargs: None,
                    },
                ),
                "performance_logger": logger,
                "security_logger": logger,
                "audit_logger": logger,
            }

        return self._logging_components

    def _load_metrics_components(self):
        """Lazy load metrics components to avoid circular imports."""
        if self._metrics_components is not None:
            return self._metrics_components

        try:
            from .prometheus_metrics import (
                MetricsMiddleware,
                get_metrics_response,
                ai_metrics,
                safety_metrics,
            )

            self._metrics_components = {
                "MetricsMiddleware": MetricsMiddleware,
                "get_metrics_response": get_metrics_response,
                "ai_metrics": ai_metrics,
                "safety_metrics": safety_metrics,
            }

            logger.info("✅ Metrics components loaded successfully")

        except ImportError as e:
            logger.error(f"Failed to load metrics components: {e}")
            self._startup_errors.append(f"Metrics components: {e}")
            # Provide fallback components
            self._metrics_components = {
                "MetricsMiddleware": lambda: None,
                "get_metrics_response": lambda: "# Metrics unavailable\n",
                "ai_metrics": None,
                "safety_metrics": None,
            }

        return self._metrics_components

    def _load_health_components(self):
        """Lazy load health check components to avoid circular imports."""
        if self._health_components is not None:
            return self._health_components

        try:
            from ..health.health_monitoring_service import HealthMonitoringService, create_health_monitoring_service

            # Create health monitoring service instance
            health_service = create_health_monitoring_service()
            
            self._health_components = {
                "health_service": health_service,
                "setup_health_endpoints": lambda app: self._setup_health_endpoints_fallback(app, health_service),
                "health_manager": health_service,
            }

            logger.info("✅ Health check components loaded successfully")

        except ImportError as e:
            logger.error(f"Failed to load health check components: {e}")
            self._startup_errors.append(f"Health components: {e}")
            # Provide fallback components
            self._health_components = {
                "setup_health_endpoints": lambda app: None,
                "health_manager": None,
            }
    
    def _setup_health_endpoints_fallback(self, app, health_service):
        """Setup health endpoints using the new health monitoring service."""
        @app.get("/health")
        async def health_check():
            """Overall health check endpoint."""
            try:
                results = await health_service.run_all_health_checks()
                overall_status = health_service.get_overall_health_status()
                
                status_code = 200
                if overall_status['status'] in ['unhealthy', 'critical']:
                    status_code = 503
                
                return JSONResponse(
                    status_code=status_code,
                    content={
                        "status": overall_status['status'],
                        "timestamp": time.time(),
                        "services": len(results),
                        "details": overall_status
                    }
                )
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": str(e)}
                )

        return self._health_components

    def _load_audit_components(self):
        """Lazy load audit components to avoid circular imports."""
        if self._audit_components is not None:
            return self._audit_components

        try:
            from .monitoring.audit import coppa_audit, get_user_context_from_request

            self._audit_components = {
                "coppa_audit": coppa_audit,
                "get_user_context_from_request": get_user_context_from_request,
            }

            logger.info("✅ Audit components loaded successfully")

        except ImportError as e:
            logger.error(f"Failed to load audit components: {e}")
            self._startup_errors.append(f"Audit components: {e}")
            # Provide fallback components
            self._audit_components = {
                "coppa_audit": type(
                    "CoppaAudit",
                    (),
                    {
                        "log_event": lambda self, event: None,
                        "query_audit_logs": lambda self, **kwargs: [],
                    },
                )(),
                "get_user_context_from_request": lambda request: {"user_id": "unknown"},
            }

        return self._audit_components

    def _ensure_components_loaded(self):
        """Ensure all monitoring components are loaded."""
        if self._components_loaded:
            return

        self._load_logging_components()
        self._load_metrics_components()
        self._load_health_components()
        self._load_audit_components()

        self._components_loaded = True

        if self._startup_errors:
            logger.warning(
                f"Monitoring integration started with {len(self._startup_errors)} errors:"
            )
            for error in self._startup_errors:
                logger.warning(f"  - {error}")
        else:
            logger.info("✅ All monitoring components loaded successfully")

    @asynccontextmanager
    async def lifespan_manager(self, app: FastAPI):
        """Lifespan context manager for monitoring setup and cleanup."""

        try:
            # Startup
            logger.info(
                "🚀 Starting AI Teddy Bear application with production monitoring"
            )

            # Ensure components are loaded
            self._ensure_components_loaded()

            # Setup logging system
            if self.config.enable_request_logging:
                logging_components = self._load_logging_components()
                logging_components["setup_logging"]()
                logger.info("✅ Production logging system initialized")

            # Log startup metrics
            if self.config.enable_metrics:
                logger.info("📊 Metrics collection started")

            if self.config.enable_health_checks:
                logger.info("🏥 Health check system initialized")

            if self.config.enable_audit_logging:
                logger.info("📋 COPPA audit logging activated")

                # Register application startup
                audit_components = self._load_audit_components()
                try:
                    audit_components["coppa_audit"].log_event(
                        {
                            "event_type": "system_startup",
                            "severity": "info",
                            "description": "AI Teddy Bear application started",
                            "metadata": {
                                "component": "main_application",
                                "version": "5.0.0",
                            },
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to log startup event: {e}")

            self._startup_complete = True
            logger.info("✅ Monitoring integration startup complete")

            yield

        except Exception as e:
            logger.error(f"Failed during monitoring startup: {e}")
            self._startup_errors.append(f"Startup failure: {e}")
            # Still yield to allow app to start with degraded monitoring
            yield

        finally:
            # Shutdown
            try:
                logger.info("🛑 Shutting down AI Teddy Bear application")

                if self.config.enable_audit_logging and self._audit_components:
                    audit_components = self._load_audit_components()
                    try:
                        audit_components["coppa_audit"].log_event(
                            {
                                "event_type": "system_shutdown",
                                "severity": "info",
                                "description": "AI Teddy Bear application stopped",
                                "metadata": {"component": "main_application"},
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to log shutdown event: {e}")

                self._shutdown_complete = True
                logger.info("✅ Application shutdown complete")

            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

    def setup_monitoring(self, app: FastAPI):
        """Setup comprehensive production monitoring for FastAPI app."""

        try:
            self._ensure_components_loaded()

            # Add custom middleware first
            for middleware_func in self.config.custom_middleware:
                try:
                    app.add_middleware(middleware_func)
                    logger.info(
                        f"✅ Custom middleware added: {middleware_func.__name__}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to add custom middleware {middleware_func.__name__}: {e}"
                    )

            # Add metrics collection middleware
            if self.config.enable_metrics:
                metrics_components = self._load_metrics_components()
                if metrics_components["MetricsMiddleware"]:
                    app.add_middleware(metrics_components["MetricsMiddleware"])
                    logger.info("✅ Metrics middleware registered")

            # Add request logging middleware
            if self.config.enable_request_logging:
                self._setup_request_logging_middleware(app)

            # Setup health check endpoints
            if self.config.enable_health_checks:
                self._setup_health_endpoints(app)

            # Add metrics endpoint
            if self.config.enable_metrics:
                self._setup_metrics_endpoint(app)

            # Add monitoring status endpoint
            self._setup_monitoring_status_endpoint(app)

            # Add COPPA audit endpoints (admin only)
            if self.config.enable_audit_logging:
                self._setup_audit_endpoints(app)

            # Setup error handling
            if self.config.enable_error_handling:
                self._setup_error_handlers(app)

            # Add custom exception handlers
            for exc_type, handler in self.config.custom_exception_handlers.items():
                try:
                    app.add_exception_handler(exc_type, handler)
                    logger.info(
                        f"✅ Custom exception handler added for {exc_type.__name__}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to add exception handler for {exc_type.__name__}: {e}"
                    )

            logger.info("✅ Production monitoring setup complete")

        except Exception as e:
            logger.error(f"Failed to setup monitoring: {e}")
            self._startup_errors.append(f"Monitoring setup: {e}")

    def _setup_request_logging_middleware(self, app: FastAPI):
        """Setup request logging middleware with error handling."""

        try:
            logging_components = self._load_logging_components()
            audit_components = self._load_audit_components()

            @app.middleware("http")
            async def request_logging_middleware(request: Request, call_next):
                """Log all HTTP requests with security context."""

                try:
                    request_logger = logging_components["RequestLogger"]()

                    # Extract user context for audit logging
                    user_context = audit_components["get_user_context_from_request"](
                        request
                    )

                    # Log request start
                    await request_logger.log_request_start(
                        request=request, user_context=user_context
                    )

                    # Process request with timeout
                    try:
                        response = await asyncio.wait_for(
                            call_next(request), timeout=self.config.request_timeout
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Request timeout after {self.config.request_timeout}s: {request.url}"
                        )
                        return JSONResponse(
                            status_code=408, content={"detail": "Request timeout"}
                        )

                    # Log request completion
                    await request_logger.log_request_end(
                        request=request, response=response, user_context=user_context
                    )

                    return response

                except Exception as e:
                    logger.error(f"Error in request logging middleware: {e}")
                    self._runtime_errors.append(f"Request logging: {e}")
                    # Continue processing request even if logging fails
                    return await call_next(request)

            logger.info("✅ Request logging middleware registered")

        except Exception as e:
            logger.error(f"Failed to setup request logging middleware: {e}")

    def _setup_health_endpoints(self, app: FastAPI):
        """Setup health check endpoints with error handling."""

        try:
            health_components = self._load_health_components()
            health_components["setup_health_endpoints"](app)
            logger.info("✅ Health check endpoints registered")

        except Exception as e:
            logger.error(f"Failed to setup health endpoints: {e}")

            # Provide fallback health endpoint
            @app.get(self.config.health_endpoint)
            async def fallback_health():
                """Fallback health check endpoint."""
                return {
                    "status": "degraded",
                    "message": "Health monitoring unavailable",
                    "timestamp": time.time(),
                }

    def _setup_metrics_endpoint(self, app: FastAPI):
        """Setup metrics endpoint with error handling."""

        try:
            metrics_components = self._load_metrics_components()

            @app.get(self.config.metrics_endpoint)
            async def metrics_endpoint():
                """Prometheus metrics endpoint."""
                try:
                    return Response(
                        content=metrics_components["get_metrics_response"](),
                        media_type="text/plain",
                    )
                except Exception as e:
                    logger.error(f"Error generating metrics: {e}")
                    return Response(
                        content="# Metrics generation failed\n", media_type="text/plain"
                    )

            logger.info(
                f"✅ Metrics endpoint registered at {self.config.metrics_endpoint}"
            )

        except Exception as e:
            logger.error(f"Failed to setup metrics endpoint: {e}")

    def _setup_monitoring_status_endpoint(self, app: FastAPI):
        """Setup monitoring status endpoint."""

        @app.get(self.config.monitoring_status_endpoint)
        async def monitoring_status():
            """Get monitoring system status."""
            return {
                "logging": (
                    "operational" if self.config.enable_request_logging else "disabled"
                ),
                "metrics": "operational" if self.config.enable_metrics else "disabled",
                "health_checks": (
                    "operational" if self.config.enable_health_checks else "disabled"
                ),
                "audit_logging": (
                    "operational" if self.config.enable_audit_logging else "disabled"
                ),
                "startup_complete": self._startup_complete,
                "startup_errors": len(self._startup_errors),
                "runtime_errors": len(self._runtime_errors),
                "components_loaded": self._components_loaded,
                "timestamp": time.time(),
            }

        logger.info(
            f"✅ Monitoring status endpoint registered at {self.config.monitoring_status_endpoint}"
        )

    def _setup_audit_endpoints(self, app: FastAPI):
        """Setup audit endpoints with error handling."""

        try:
            audit_components = self._load_audit_components()

            @app.get(f"{self.config.audit_endpoints_prefix}/child/{{child_id}}")
            async def get_child_audit_logs(child_id: str, limit: int = 100):
                """Get audit logs for a specific child (admin only)."""
                try:
                    # Note: Add proper admin authentication middleware
                    logs = audit_components["coppa_audit"].query_audit_logs(
                        child_id=child_id, limit=limit
                    )
                    return {
                        "child_id": child_id,
                        "audit_logs": logs,
                        "total_entries": len(logs),
                    }
                except Exception as e:
                    logger.error(f"Error querying audit logs for child {child_id}: {e}")
                    return JSONResponse(
                        status_code=500,
                        content={"detail": "Failed to retrieve audit logs"},
                    )

            @app.get(f"{self.config.audit_endpoints_prefix}/errors")
            async def get_monitoring_errors():
                """Get monitoring system errors (admin only)."""
                return {
                    "startup_errors": self._startup_errors,
                    "runtime_errors": self._runtime_errors[-50:],  # Last 50 errors
                    "total_startup_errors": len(self._startup_errors),
                    "total_runtime_errors": len(self._runtime_errors),
                    "timestamp": time.time(),
                }

            logger.info("✅ Audit endpoints registered")

        except Exception as e:
            logger.error(f"Failed to setup audit endpoints: {e}")

    def _setup_error_handlers(self, app: FastAPI):
        """Setup comprehensive error handling."""

        try:
            audit_components = self._load_audit_components()

            @app.exception_handler(HTTPException)
            async def http_exception_handler(request: Request, exc: HTTPException):
                """Handle HTTP exceptions with proper logging."""

                try:
                    user_context = audit_components["get_user_context_from_request"](
                        request
                    )

                    # Log HTTP errors
                    logger.error(
                        f"HTTP exception: {exc.status_code} - {exc.detail}",
                        extra={
                            "status_code": exc.status_code,
                            "detail": exc.detail,
                            "endpoint": str(request.url.path),
                            "method": request.method,
                            "user_context": user_context,
                        },
                    )

                    # Log security-related errors specially
                    if exc.status_code in [401, 403, 404]:
                        logging_components = self._load_logging_components()
                        security_logger = logging_components.get(
                            "security_logger", logger
                        )
                        security_logger.warning(
                            f"Security-related HTTP error: {exc.status_code}",
                            extra={
                                "status_code": exc.status_code,
                                "detail": exc.detail,
                                "user_context": user_context,
                            },
                        )

                    return JSONResponse(
                        status_code=exc.status_code, content={"detail": exc.detail}
                    )

                except Exception as e:
                    logger.error(f"Error in HTTP exception handler: {e}")
                    return JSONResponse(
                        status_code=exc.status_code, content={"detail": exc.detail}
                    )

            @app.exception_handler(Exception)
            async def general_exception_handler(request: Request, exc: Exception):
                """Handle general exceptions with comprehensive logging."""

                try:
                    user_context = audit_components["get_user_context_from_request"](
                        request
                    )

                    # Log the full exception with traceback
                    logger.error(
                        f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
                        extra={
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                            "traceback": traceback.format_exc(),
                            "endpoint": str(request.url.path),
                            "method": request.method,
                            "user_context": user_context,
                        },
                    )

                    self._runtime_errors.append(f"{type(exc).__name__}: {str(exc)}")

                    # Log critical system errors
                    if isinstance(exc, (SystemError, MemoryError, KeyboardInterrupt)):
                        logger.critical(
                            f"Critical system error: {type(exc).__name__}",
                            extra={"error": str(exc), "error_type": type(exc).__name__},
                        )

                    return JSONResponse(
                        status_code=500, content={"detail": "Internal server error"}
                    )

                except Exception as e:
                    logger.error(f"Error in general exception handler: {e}")
                    return JSONResponse(
                        status_code=500, content={"detail": "Internal server error"}
                    )

            logger.info("✅ Error handlers registered")

        except Exception as e:
            logger.error(f"Failed to setup error handlers: {e}")

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get comprehensive monitoring system status."""
        return {
            "config": {
                "enable_metrics": self.config.enable_metrics,
                "enable_request_logging": self.config.enable_request_logging,
                "enable_health_checks": self.config.enable_health_checks,
                "enable_audit_logging": self.config.enable_audit_logging,
                "enable_error_handling": self.config.enable_error_handling,
            },
            "status": {
                "startup_complete": self._startup_complete,
                "shutdown_complete": self._shutdown_complete,
                "components_loaded": self._components_loaded,
            },
            "errors": {
                "startup_errors": len(self._startup_errors),
                "runtime_errors": len(self._runtime_errors),
            },
            "components": {
                "logging": self._logging_components is not None,
                "metrics": self._metrics_components is not None,
                "health": self._health_components is not None,
                "audit": self._audit_components is not None,
            },
        }


# Global monitoring integration instance
_monitoring_integration: Optional[MonitoringIntegration] = None


def get_monitoring_integration(
    config: Optional[MonitoringConfig] = None,
) -> MonitoringIntegration:
    """Get or create monitoring integration instance."""
    global _monitoring_integration

    if _monitoring_integration is None:
        _monitoring_integration = MonitoringIntegration(config)

    return _monitoring_integration


def setup_production_monitoring(
    app: FastAPI, config: Optional[MonitoringConfig] = None
):
    """Setup comprehensive production monitoring for FastAPI app."""
    integration = get_monitoring_integration(config)
    integration.setup_monitoring(app)
    return integration


@asynccontextmanager
async def monitoring_lifespan(app: FastAPI, config: Optional[MonitoringConfig] = None):
    """Lifespan context manager for monitoring setup and cleanup."""
    integration = get_monitoring_integration(config)
    async with integration.lifespan_manager(app):
        yield


def log_application_startup():
    """Log comprehensive application startup information."""

    try:
        startup_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "application": "AI Teddy Bear",
            "version": "5.0.0",
            "environment": "production",
            "python_version": sys.version,
            "platform": platform.platform(),
            "architecture": platform.architecture(),
            "hostname": platform.node(),
        }

        logger.info("🚀 AI Teddy Bear application startup", extra=startup_info)

        # Try to load logging components for specialized loggers
        try:
            integration = get_monitoring_integration()
            logging_components = integration._load_logging_components()

            # Log security initialization
            security_logger = logging_components.get("security_logger", logger)
            security_logger.info("🔒 Security systems initialized")

            # Log performance baseline
            performance_logger = logging_components.get("performance_logger", logger)
            performance_logger.info("⚡ Performance monitoring active")

            # Log audit system
            audit_logger = logging_components.get("audit_logger", logger)
            audit_logger.info("📋 COPPA audit logging operational")

        except Exception as e:
            logger.warning(f"Failed to load specialized loggers during startup: {e}")

    except Exception as e:
        logger.error(f"Error during application startup logging: {e}")


# Backward compatibility functions
def setup_error_monitoring():
    """Deprecated: Use MonitoringIntegration.setup_monitoring() instead."""
    logger.warning(
        "setup_error_monitoring() is deprecated. Use MonitoringIntegration.setup_monitoring()."
    )

    # This function had incomplete implementation in original code
    # Error handling is now integrated into the main setup process
    pass


# End of file
