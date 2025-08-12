"""
🧸 AI TEDDY BEAR V5 - SIMPLIFIED ERROR HANDLER
==============================================
Streamlined error handling with enhanced circuit breaker.
"""

import asyncio
import time
import traceback
from enum import Enum
from typing import Dict, Any, Optional, Callable
from uuid import uuid4
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import our logging system
from .logging.production_logger import get_logger, security_logger
from .monitoring.audit import coppa_audit, get_user_context_from_request
from src.core.exceptions import (
    AITeddyBearException,
    AuthorizationError,
    ChildSafetyViolation,
    COPPAViolation,
    RateLimitExceeded,
    AuthenticationError,
)
from src.infrastructure.exceptions import map_exception

# Global logger for error handling
error_logger = get_logger(__name__, "error_handler")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ErrorHandler:
    """Simplified centralized error handling."""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = error_logger
        self._error_handlers = {
            AITeddyBearException: self._handle_custom_exception,
            (HTTPException, StarletteHTTPException): self._handle_http_exception,
        }

    async def handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Main exception handler with simplified routing."""
        user_context = get_user_context_from_request(request)
        correlation_id = getattr(request.state, "correlation_id", str(uuid4()))

        # Route to appropriate handler
        for exc_type, handler in self._error_handlers.items():
            if isinstance(exc, exc_type):
                return await handler(request, exc, user_context)

        # Handle unexpected exceptions
        return await self._handle_unexpected_exception(
            request, exc, user_context, correlation_id
        )

    async def _handle_custom_exception(
        self, request: Request, exc: AITeddyBearException, user_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle custom application exceptions with simplified logging."""
        log_data = {
            "error_code": exc.error_code,
            "correlation_id": exc.correlation_id,
            "path": request.url.path,
            "method": request.method,
            "user_context": user_context,
        }

        # Simplified logging based on exception type
        if isinstance(exc, (AuthenticationError, AuthorizationError)):
            security_logger.warning("Security exception", extra=log_data)
            self._audit_security_event(exc, user_context)
        elif isinstance(exc, (ChildSafetyViolation, COPPAViolation)):
            security_logger.error("Child safety violation", extra=log_data)
            self._audit_safety_violation(exc, user_context)
        elif isinstance(exc, RateLimitExceeded):
            self.logger.info("Rate limit exceeded", extra=log_data)
        else:
            self.logger.warning("Application exception", extra=log_data)

        # Return filtered response
        response_data = exc.to_dict()
        if not self.debug and exc.details:
            response_data["error"]["details"] = self._filter_sensitive_data(exc.details)

        return JSONResponse(status_code=exc.status_code, content=response_data)

    def _audit_security_event(
        self, exc: AITeddyBearException, user_context: Dict[str, Any]
    ):
        """Audit security-related events."""
        coppa_audit.log_event(
            {
                "event_type": "security_exception",
                "severity": "warning",
                "description": f"Security exception: {exc.error_code}",
                "metadata": {
                    "error_code": exc.error_code,
                    "correlation_id": exc.correlation_id,
                    **user_context,
                },
            }
        )

    def _audit_safety_violation(
        self, exc: AITeddyBearException, user_context: Dict[str, Any]
    ):
        """Audit child safety violations."""
        coppa_audit.log_event(
            {
                "event_type": "child_safety_violation",
                "severity": "error",
                "description": f"Child safety violation: {exc.message}",
                "metadata": {
                    "error_code": exc.error_code,
                    "correlation_id": exc.correlation_id,
                    **user_context,
                },
            }
        )

    def _filter_sensitive_data(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Filter sensitive data from error details."""
        sensitive_keys = {"password", "token", "secret", "key", "internal_id"}
        return {k: v for k, v in details.items() if k not in sensitive_keys}

    async def _handle_http_exception(
        self, request: Request, exc: HTTPException, user_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle FastAPI HTTPException with simplified logging."""
        correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
        # Simplified logging - remove status_code from extra kwargs
        log_msg = f"HTTP error {exc.status_code}: {exc.detail}"
        log_extra = {
            "correlation_id": correlation_id,
            "path": request.url.path,
            "method": request.method,
            "user_context": user_context,
        }

        if exc.status_code >= 500:
            self.logger.error(log_msg, extra=log_extra)
        elif exc.status_code >= 400:
            self.logger.warning(log_msg, extra=log_extra)
            if exc.status_code in [401, 403, 404]:
                security_logger.warning(log_msg, extra=log_extra)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "correlation_id": correlation_id,
                }
            },
        )

    async def _handle_unexpected_exception(
        self,
        request: Request,
        exc: Exception,
        user_context: Dict[str, Any],
        correlation_id: str,
    ) -> JSONResponse:
        """Handle unexpected exceptions with safe error handling."""
        # Try to map to custom exceptions
        try:
            mapped_exc = map_exception(exc)
            if isinstance(mapped_exc, AITeddyBearException):
                mapped_exc.correlation_id = correlation_id
                return await self._handle_custom_exception(
                    request, mapped_exc, user_context
                )
        except Exception:
            pass  # Continue with generic handling

        # Safe logging with fallback
        try:
            log_data = {
                "error": str(exc),
                "error_type": type(exc).__name__,
                "correlation_id": correlation_id,
                "path": request.url.path,
                "method": request.method,
            }

            if isinstance(exc, (SystemError, MemoryError, KeyboardInterrupt)):
                self.logger.critical("Critical system error", extra=log_data)
                self._audit_critical_error(exc, correlation_id, user_context)
            else:
                self.logger.error(
                    "Unhandled exception", extra=dict(log_data, traceback=traceback.format_exc())
                )
        except Exception:
            pass  # Prevent error handler from failing

        # Safe response generation
        response_content = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": (
                    str(exc)
                    if self.debug
                    else "An internal error occurred. Please contact support."
                ),
                "correlation_id": correlation_id,
            }
        }

        if self.debug:
            response_content["error"]["debug"] = {
                "exception_type": type(exc).__name__,
                "traceback": traceback.format_exc(),
            }

        return JSONResponse(status_code=500, content=response_content)

    def _audit_critical_error(
        self, exc: Exception, correlation_id: str, user_context: Dict[str, Any]
    ):
        """Audit critical system errors safely."""
        try:
            coppa_audit.log_event(
                {
                    "event_type": "critical_system_error",
                    "severity": "critical",
                    "description": f"Critical system error: {type(exc).__name__}",
                    "metadata": {
                        "error_type": type(exc).__name__,
                        "correlation_id": correlation_id,
                        **user_context,
                    },
                }
            )
        except Exception:
            pass  # Prevent audit failure from breaking error handling


class ErrorContextMiddleware:
    """Middleware to add error context and correlation IDs to requests."""

    def __init__(self, app):
        self.app = app
        self.logger = get_logger(__name__, "error_context")

    async def __call__(self, scope, receive, send):
        """Add correlation ID and error context to all requests."""

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate correlation ID
        headers = dict(scope["headers"])
        correlation_id = None

        for header_name, header_value in headers.items():
            if header_name.lower() == b"x-correlation-id":
                correlation_id = header_value.decode()
                break

        if not correlation_id:
            correlation_id = str(uuid4())

        # Add correlation ID to scope for request handlers
        scope["correlation_id"] = correlation_id

        # Setup structured logging context
        import structlog

        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            path=scope.get("path", "unknown"),
            method=scope.get("method", "unknown"),
        )

        # Add response header middleware
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Add correlation ID to response headers
                headers = message.get("headers", [])
                headers.append([b"x-correlation-id", correlation_id.encode()])
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


# Global error handler instance
global_error_handler = ErrorHandler()


# Exception handler functions for FastAPI
async def handle_custom_exception(
    request: Request, exc: AITeddyBearException
) -> JSONResponse:
    """Handle custom application exceptions."""
    return await global_error_handler.handle_exception(request, exc)


async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    return await global_error_handler.handle_exception(request, exc)


async def handle_general_exception(request: Request, exc: Exception) -> JSONResponse:
    """Handle any unhandled exceptions."""
    return await global_error_handler.handle_exception(request, exc)


def setup_error_handlers(app, debug: bool = False):
    """Setup all error handlers for the FastAPI application."""

    # Update global handler debug mode
    global_error_handler.debug = debug

    # Add exception handlers
    app.add_exception_handler(AITeddyBearException, handle_custom_exception)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_general_exception)

    # Add error context middleware
    app.add_middleware(ErrorContextMiddleware)

    error_logger.info(f"Global error handlers configured - Debug mode: {debug}")


class CircuitBreaker:
    """Enhanced circuit breaker with proper state management."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
        service_name: str = "unknown",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.service_name = service_name

        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.next_attempt_time = None

        self.logger = get_logger(__name__, f"circuit_breaker_{service_name}")
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            await self._check_state()

            if self.state == CircuitState.OPEN:
                raise Exception(
                    f"Service {self.service_name} is temporarily unavailable"
                )

        try:
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise e

    async def _check_state(self):
        """Check and update circuit breaker state."""
        current_time = time.time()

        if self.state == CircuitState.OPEN:
            if self.next_attempt_time and current_time >= self.next_attempt_time:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.logger.info(
                    f"Circuit breaker {self.service_name} moved to HALF_OPEN"
                )

    async def _on_success(self):
        """Handle successful operation."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._reset()
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    async def _on_failure(self):
        """Handle failed operation."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                self._open_circuit()
            elif (
                self.state == CircuitState.CLOSED
                and self.failure_count >= self.failure_threshold
            ):
                self._open_circuit()

    def _open_circuit(self):
        """Open the circuit breaker."""
        self.state = CircuitState.OPEN
        self.next_attempt_time = time.time() + self.recovery_timeout
        self.logger.error(
            f"Circuit breaker {self.service_name} OPENED",
            failure_count=self.failure_count,
            threshold=self.failure_threshold,
        )

    def _reset(self):
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.next_attempt_time = None
        self.logger.info(f"Circuit breaker {self.service_name} RESET to CLOSED")

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "service_name": self.service_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "next_attempt_time": self.next_attempt_time,
        }
