"""
Logging Middleware - FastAPI Integration
=====================================
FastAPI middleware for structured logging integration:
- Automatic request/response logging with correlation IDs
- Performance tracking and metrics
- Error logging with stack traces
- Security event logging
- Child safety interaction logging
- Request sanitization and PII protection
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from urllib.parse import urlparse, parse_qs

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .structured_logger import (
    StructuredLogger, LogContext, LogCategory, LogLevel,
    set_log_context, get_log_context, SecurityFilter,
    http_logger, security_logger, child_safety_logger, performance_logger
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging."""
    
    def __init__(self, app: ASGIApp, logger: Optional[StructuredLogger] = None):
        super().__init__(app)
        self.logger = logger or http_logger
        
        # Configure which paths to log
        self.log_request_body = True
        self.log_response_body = True
        self.max_body_size = 10000  # 10KB max body logging
        
        # Paths to exclude from logging
        self.exclude_paths = {
            '/health', '/metrics', '/favicon.ico'
        }
        
        # Sensitive headers to redact
        self.sensitive_headers = {
            'authorization', 'cookie', 'x-api-key', 'x-auth-token'
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response with comprehensive logging."""
        start_time = time.time()
        
        # Generate correlation ID and setup context
        correlation_id = str(uuid.uuid4())
        trace_id = request.headers.get('x-trace-id') or str(uuid.uuid4())
        
        # Extract user information
        user_id = request.headers.get('x-user-id')
        child_id = request.headers.get('x-child-id')
        parent_id = request.headers.get('x-parent-id')
        session_id = request.headers.get('x-session-id')
        
        # Create log context
        context = LogContext(
            correlation_id=correlation_id,
            trace_id=trace_id,
            user_id=user_id,
            child_id=child_id,
            parent_id=parent_id,
            session_id=session_id,
            request_id=correlation_id,
            operation=f"{request.method} {request.url.path}",
            component="http_middleware"
        )
        
        # Set context for this request
        set_log_context(context)
        
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            response = await call_next(request)
            return response
        
        # Log request
        await self._log_request(request, context)
        
        # Process request and handle errors
        try:
            response = await call_next(request)
            
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000
            
            # Log response
            await self._log_response(request, response, processing_time, context)
            
            # Add correlation headers to response
            response.headers['X-Correlation-ID'] = correlation_id
            response.headers['X-Trace-ID'] = trace_id
            
            return response
            
        except HTTPException as e:
            processing_time = (time.time() - start_time) * 1000
            await self._log_http_exception(request, e, processing_time, context)
            raise
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            await self._log_unhandled_exception(request, e, processing_time, context)
            
            # Return generic error response
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "correlation_id": correlation_id},
                headers={'X-Correlation-ID': correlation_id, 'X-Trace-ID': trace_id}
            )
    
    async def _log_request(self, request: Request, context: LogContext):
        """Log incoming request details."""
        # Extract request information
        method = request.method
        url = str(request.url)
        headers = dict(request.headers)
        query_params = dict(request.query_params)
        
        # Sanitize headers
        sanitized_headers = self._sanitize_headers(headers)
        
        # Get request body if configured
        request_body = None
        if self.log_request_body and method in ['POST', 'PUT', 'PATCH']:
            try:
                body = await request.body()
                if len(body) <= self.max_body_size:
                    try:
                        request_body = json.loads(body.decode('utf-8'))
                        request_body = SecurityFilter.sanitize_data(request_body)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_body = f"<binary data: {len(body)} bytes>"
                else:
                    request_body = f"<large body: {len(body)} bytes>"
            except Exception:
                request_body = "<unable to read body>"
        
        # Extract client information
        client_ip = self._get_client_ip(request)
        user_agent = headers.get('user-agent', 'unknown')
        
        # Determine if this is a child-related request
        is_child_request = context.child_id is not None or 'child' in url.lower()
        
        # Log the request
        log_data = {
            'method': method,
            'url': url,
            'headers': sanitized_headers,
            'query_params': SecurityFilter.sanitize_data(query_params),
            'client_ip': SecurityFilter.sanitize_data(client_ip),
            'user_agent': user_agent,
            'content_length': headers.get('content-length', '0'),
            'content_type': headers.get('content-type', ''),
            'is_child_request': is_child_request
        }
        
        if request_body is not None:
            log_data['request_body'] = request_body
        
        self.logger.info(
            f"HTTP Request: {method} {request.url.path}",
            category=LogCategory.HTTP,
            **log_data
        )
        
        # Log child safety events
        if is_child_request:
            child_safety_logger.info(
                f"Child interaction request: {method} {request.url.path}",
                child_id=context.child_id,
                metadata={
                    'endpoint': request.url.path,
                    'method': method,
                    'has_query_params': bool(query_params)
                }
            )
    
    async def _log_response(self, request: Request, response: Response, 
                          processing_time: float, context: LogContext):
        """Log response details."""
        status_code = response.status_code
        
        # Get response body if configured and safe to do so
        response_body = None
        if (self.log_response_body and 
            status_code < 400 and 
            hasattr(response, 'body')):
            try:
                if hasattr(response.body, 'decode'):
                    body_str = response.body.decode('utf-8')
                    if len(body_str) <= self.max_body_size:
                        try:
                            response_body = json.loads(body_str)
                            response_body = SecurityFilter.sanitize_data(response_body)
                        except json.JSONDecodeError:
                            response_body = f"<non-json: {len(body_str)} chars>"
                    else:
                        response_body = f"<large response: {len(body_str)} chars>"
            except Exception:
                response_body = "<unable to read response>"
        
        # Determine log level based on status code
        if status_code < 400:
            log_level = LogLevel.INFO
        elif status_code < 500:
            log_level = LogLevel.WARNING
        else:
            log_level = LogLevel.ERROR
        
        # Log response
        log_data = {
            'status_code': status_code,
            'processing_time_ms': processing_time,
            'response_headers': dict(response.headers),
            'method': request.method,
            'url': str(request.url),
            'client_ip': self._get_client_ip(request)
        }
        
        if response_body is not None:
            log_data['response_body'] = response_body
        
        self.logger._log(
            log_level,
            LogCategory.HTTP,
            f"HTTP Response: {request.method} {request.url.path} -> {status_code}",
            **log_data
        )
        
        # Log performance metrics
        performance_logger.info(
            f"Request performance: {request.method} {request.url.path}",
            duration_ms=processing_time,
            performance_metrics={
                'response_time_ms': processing_time,
                'status_code': status_code,
                'endpoint': request.url.path,
                'method': request.method
            }
        )
        
        # Log slow requests
        if processing_time > 1000:  # > 1 second
            performance_logger.warning(
                f"Slow request detected: {request.method} {request.url.path}",
                duration_ms=processing_time,
                metadata={
                    'threshold_exceeded': '1000ms',
                    'actual_time': f"{processing_time:.2f}ms"
                }
            )
    
    async def _log_http_exception(self, request: Request, exception: HTTPException,
                                processing_time: float, context: LogContext):
        """Log HTTP exceptions."""
        self.logger.warning(
            f"HTTP Exception: {request.method} {request.url.path} -> {exception.status_code}",
            category=LogCategory.HTTP,
            error_details={
                'status_code': exception.status_code,
                'detail': str(exception.detail),
                'headers': getattr(exception, 'headers', None)
            },
            processing_time_ms=processing_time,
            method=request.method,
            url=str(request.url),
            client_ip=self._get_client_ip(request)
        )
    
    async def _log_unhandled_exception(self, request: Request, exception: Exception,
                                     processing_time: float, context: LogContext):
        """Log unhandled exceptions."""
        import traceback
        
        self.logger.error(
            f"Unhandled Exception: {request.method} {request.url.path}",
            category=LogCategory.HTTP,
            error=exception,
            processing_time_ms=processing_time,
            method=request.method,
            url=str(request.url),
            client_ip=self._get_client_ip(request),
            error_details={
                'type': type(exception).__name__,
                'message': str(exception),
                'traceback': traceback.format_exc()
            }
        )
        
        # Log as security event if it might be malicious
        if self._is_potential_security_issue(request, exception):
            security_logger.security(
                f"Potential security issue: {type(exception).__name__}",
                metadata={
                    'endpoint': request.url.path,
                    'method': request.method,
                    'client_ip': self._get_client_ip(request),
                    'user_agent': request.headers.get('user-agent', ''),
                    'exception_type': type(exception).__name__
                }
            )
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize sensitive headers."""
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in self.sensitive_headers:
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = SecurityFilter.sanitize_data(value)
        return sanitized
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        # Check for forwarded headers
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if hasattr(request, 'client') and request.client:
            return request.client.host
        
        return 'unknown'
    
    def _is_potential_security_issue(self, request: Request, exception: Exception) -> bool:
        """Determine if an exception might indicate a security issue."""
        # Check for suspicious patterns
        suspicious_exceptions = [
            'ValidationError', 'ValueError', 'TypeError',
            'KeyError', 'IndexError', 'AttributeError'
        ]
        
        if type(exception).__name__ in suspicious_exceptions:
            return True
        
        # Check for suspicious request patterns
        url_path = request.url.path.lower()
        suspicious_patterns = [
            'admin', 'config', 'debug', '.env', 'passwd',
            'shadow', 'etc', 'proc', 'var', 'tmp'
        ]
        
        for pattern in suspicious_patterns:
            if pattern in url_path:
                return True
        
        return False


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware specifically for security event logging."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.suspicious_patterns = [
            'union select', 'drop table', 'delete from',
            '<script', 'javascript:', 'alert(',
            '../', '..\\', '/etc/', '/proc/',
            'cmd.exe', 'powershell', 'bash'
        ]
        
        self.rate_limit_tracking = {}
        self.max_requests_per_minute = 100
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check for security issues and log accordingly."""
        client_ip = self._get_client_ip(request)
        
        # Check for suspicious content
        if await self._check_suspicious_content(request):
            security_logger.security(
                "Suspicious request content detected",
                metadata={
                    'client_ip': client_ip,
                    'endpoint': request.url.path,
                    'method': request.method,
                    'user_agent': request.headers.get('user-agent', ''),
                    'suspicious_content': True
                }
            )
        
        # Rate limit tracking
        await self._track_rate_limit(client_ip)
        
        response = await call_next(request)
        
        # Log authentication failures
        if response.status_code in [401, 403]:
            security_logger.security(
                f"Authentication/Authorization failure: {response.status_code}",
                metadata={
                    'status_code': response.status_code,
                    'client_ip': client_ip,
                    'endpoint': request.url.path,
                    'method': request.method,
                    'user_agent': request.headers.get('user-agent', '')
                }
            )
        
        return response
    
    async def _check_suspicious_content(self, request: Request) -> bool:
        """Check request for suspicious content."""
        # Check URL path
        url_path = request.url.path.lower()
        for pattern in self.suspicious_patterns:
            if pattern in url_path:
                return True
        
        # Check query parameters
        for param_value in request.query_params.values():
            param_lower = param_value.lower()
            for pattern in self.suspicious_patterns:
                if pattern in param_lower:
                    return True
        
        # Check headers
        for header_value in request.headers.values():
            header_lower = header_value.lower()
            for pattern in self.suspicious_patterns:
                if pattern in header_lower:
                    return True
        
        # Check body for POST/PUT requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode('utf-8').lower()
                    for pattern in self.suspicious_patterns:
                        if pattern in body_str:
                            return True
            except Exception:
                pass  # Unable to decode body
        
        return False
    
    async def _track_rate_limit(self, client_ip: str):
        """Track request rates per IP."""
        current_time = datetime.now()
        minute_key = current_time.strftime('%Y-%m-%d %H:%M')
        
        if client_ip not in self.rate_limit_tracking:
            self.rate_limit_tracking[client_ip] = {}
        
        if minute_key not in self.rate_limit_tracking[client_ip]:
            self.rate_limit_tracking[client_ip][minute_key] = 0
        
        self.rate_limit_tracking[client_ip][minute_key] += 1
        
        # Clean old entries
        self._cleanup_rate_limit_tracking()
        
        # Check if rate limit exceeded
        if self.rate_limit_tracking[client_ip][minute_key] > self.max_requests_per_minute:
            security_logger.security(
                "Rate limit exceeded",
                metadata={
                    'client_ip': client_ip,
                    'requests_count': self.rate_limit_tracking[client_ip][minute_key],
                    'time_window': minute_key,
                    'limit': self.max_requests_per_minute
                }
            )
    
    def _cleanup_rate_limit_tracking(self):
        """Clean up old rate limit tracking data."""
        current_time = datetime.now()
        cutoff_time = current_time.replace(minute=current_time.minute - 5)
        cutoff_key = cutoff_time.strftime('%Y-%m-%d %H:%M')
        
        for client_ip in list(self.rate_limit_tracking.keys()):
            for time_key in list(self.rate_limit_tracking[client_ip].keys()):
                if time_key < cutoff_key:
                    del self.rate_limit_tracking[client_ip][time_key]
            
            # Remove empty client entries
            if not self.rate_limit_tracking[client_ip]:
                del self.rate_limit_tracking[client_ip]
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        if hasattr(request, 'client') and request.client:
            return request.client.host
        
        return 'unknown'


class ChildSafetyLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for child safety specific logging."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.child_endpoints = {
            '/api/children', '/api/stories', '/api/conversations',
            '/api/safety', '/api/interactions'
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log child safety related interactions."""
        is_child_endpoint = any(
            request.url.path.startswith(endpoint) 
            for endpoint in self.child_endpoints
        )
        
        child_id = request.headers.get('x-child-id')
        parent_id = request.headers.get('x-parent-id')
        
        if is_child_endpoint or child_id:
            # Log child interaction start
            context = get_log_context()
            
            child_safety_logger.child_safety(
                f"Child interaction started: {request.method} {request.url.path}",
                child_id=child_id,
                metadata={
                    'endpoint': request.url.path,
                    'method': request.method,
                    'parent_id': parent_id,
                    'has_supervision': parent_id is not None,
                    'client_ip': self._get_client_ip(request)
                }
            )
        
        response = await call_next(request)
        
        if is_child_endpoint or child_id:
            # Log child interaction completion
            child_safety_logger.child_safety(
                f"Child interaction completed: {request.method} {request.url.path} -> {response.status_code}",
                child_id=child_id,
                metadata={
                    'endpoint': request.url.path,
                    'method': request.method,
                    'status_code': response.status_code,
                    'parent_id': parent_id,
                    'success': response.status_code < 400
                }
            )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        if hasattr(request, 'client') and request.client:
            return request.client.host
        
        return 'unknown'


def setup_logging_middleware(app):
    """Setup all logging middleware for a FastAPI app."""
    # Add middleware in reverse order (last added = first executed)
    app.add_middleware(ChildSafetyLoggingMiddleware)
    app.add_middleware(SecurityLoggingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
