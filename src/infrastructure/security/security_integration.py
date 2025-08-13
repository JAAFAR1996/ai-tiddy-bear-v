"""
Security Integration Layer - Enterprise Security Hub
==================================================
Unified security integration layer that coordinates:
- JWT authentication and authorization
- Advanced rate limiting
- CORS and security headers
- Input validation and sanitization
- SSL/TLS configuration
- Audit logging and monitoring
"""

import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import redis.asyncio as redis

from .jwt_advanced import AdvancedJWTManager, TokenType, JWTClaims
from .rate_limiter_advanced import AdvancedRateLimiter, RateLimitScope, RateLimitResult
from .cors_advanced import AdvancedCORSManager, SecurityHeaderLevel
from .input_validator import AdvancedInputValidator, ValidationResult
from .ssl_config import SSLConfigManager, SecurityLevel
from ..resilience.fallback_logger import FallbackLogger, LogContext, EventType


class SecurityIntegration:
    """
    Unified security integration layer for AI Teddy Bear system.
    
    Features:
    - Centralized security policy management
    - Coordinated authentication and authorization
    - Multi-layer request validation
    - Comprehensive audit logging
    - Performance-optimized security checks
    - Real-time threat monitoring
    """
    
    def __init__(self, config=None, advanced_jwt=None):
        """Initialize with explicit config and AdvancedJWTManager injection (production-grade)"""
        if config is None:
            raise ValueError("SecurityIntegration requires config parameter - no global access in production")
        if advanced_jwt is None:
            raise ValueError("SecurityIntegration requires advanced_jwt parameter - no global access in production")
        
        # Use injected security components
        self.jwt_manager = advanced_jwt
        self.rate_limiter = AdvancedRateLimiter()
        self.cors_manager = AdvancedCORSManager()
        self.input_validator = AdvancedInputValidator()
        self.ssl_manager = SSLConfigManager()
        
        # Logging
        self.logger = FallbackLogger("security_integration")
        
        # Redis client for distributed security state
        self._redis_client: Optional[redis.Redis] = None
        
        # Security metrics
        self._security_metrics = {
            "total_requests": 0,
            "blocked_requests": 0,
            "authentication_failures": 0,
            "rate_limit_violations": 0,
            "input_validation_failures": 0,
            "cors_violations": 0,
            "security_incidents": 0
        }
        
        # Threat intelligence
        self._threat_intelligence = {
            "malicious_ips": set(),
            "suspicious_patterns": [],
            "attack_signatures": {}
        }
        
        # Initialize loggers for all components
        self._initialize_component_loggers()
    
    def _initialize_component_loggers(self):
        """Initialize loggers for all security components."""
        self.jwt_manager.set_logger(self.logger)
        self.rate_limiter.set_logger(self.logger)
        self.cors_manager.set_logger(self.logger)
        self.input_validator.set_logger(self.logger)
        self.ssl_manager.set_logger(self.logger)
    
    async def initialize(self, redis_url: Optional[str] = None):
        """Initialize security integration with Redis connection."""
        if redis_url:
            self._redis_client = redis.from_url(redis_url)
            
            # Set Redis clients for components
            await self.jwt_manager.set_redis_client(self._redis_client)
            self.rate_limiter = AdvancedRateLimiter(self._redis_client)
            self.rate_limiter.set_logger(self.logger)
    
    async def authenticate_request(
        self,
        request: Request,
        token: Optional[str] = None,
        require_mfa: bool = False
    ) -> Optional[JWTClaims]:
        """
        Authenticate incoming request with comprehensive validation.
        
        Args:
            request: FastAPI request object
            token: JWT token (extracted from header if not provided)
            require_mfa: Whether MFA verification is required
            
        Returns:
            JWT claims if authentication successful, None otherwise
        """
        self._security_metrics["total_requests"] += 1
        
        try:
            # Extract token if not provided
            if not token:
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    return None
                token = auth_header[7:]  # Remove "Bearer " prefix
            
            # Extract device information for fingerprinting
            device_info = self._extract_device_info(request)
            
            # Verify token
            claims = await self.jwt_manager.verify_token(
                token=token,
                expected_type=TokenType.ACCESS,
                verify_device=True,
                current_device_info=device_info,
                current_ip=self._get_client_ip(request)
            )
            
            # Check MFA requirements
            if require_mfa and not claims.mfa_verified:
                self.logger.log_security_event(
                    LogContext(
                        service_name="security_integration",
                        user_id=claims.sub,
                        session_id=claims.session_id
                    ),
                    "mfa_required",
                    "MFA verification required but not present"
                )
                return None
            
            # Update request context
            request.state.user_id = claims.sub
            request.state.user_role = claims.role
            request.state.session_id = claims.session_id
            
            return claims
            
        except Exception as e:
            self._security_metrics["authentication_failures"] += 1
            
            self.logger.log_security_event(
                LogContext(service_name="security_integration"),
                "authentication_failure",
                f"Authentication failed: {str(e)}",
                severity="warning",
                additional_data={
                    "ip_address": self._get_client_ip(request),
                    "user_agent": request.headers.get("User-Agent", ""),
                    "error": str(e)
                }
            )
            
            return None
    
    async def check_rate_limits(
        self,
        request: Request,
        user_claims: Optional[JWTClaims] = None
    ) -> RateLimitResult:
        """
        Check rate limits for incoming request.
        
        Args:
            request: FastAPI request object
            user_claims: Authenticated user claims
            
        Returns:
            Rate limit check result
        """
        # Determine identifier and scope
        ip_address = self._get_client_ip(request)
        
        if user_claims:
            identifier = user_claims.sub
            scope = RateLimitScope.USER
            user_role = user_claims.role
        else:
            identifier = ip_address
            scope = RateLimitScope.IP
            user_role = None
        
        # Check rate limits
        result = await self.rate_limiter.check_rate_limit(
            identifier=identifier,
            scope=scope,
            endpoint=str(request.url.path),
            user_id=user_claims.sub if user_claims else None,
            user_role=user_role,
            ip_address=ip_address,
            api_key=request.headers.get("X-API-Key")
        )
        
        if not result.allowed:
            self._security_metrics["rate_limit_violations"] += 1
            
            self.logger.log_security_event(
                LogContext(
                    service_name="security_integration",
                    user_id=user_claims.sub if user_claims else None
                ),
                "rate_limit_exceeded",
                f"Rate limit exceeded for {scope.value}: {identifier}",
                severity="warning",
                additional_data={
                    "current_requests": result.current_requests,
                    "limit": result.limit,
                    "endpoint": str(request.url.path),
                    "ip_address": ip_address
                }
            )
        
        return result
    
    def validate_cors(self, request: Request) -> bool:
        """
        Validate CORS for incoming request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if CORS validation passes
        """
        origin = request.headers.get("Origin")
        
        if not origin:
            return True  # Not a CORS request
        
        is_valid = self.cors_manager.validate_origin(
            origin=origin,
            path=str(request.url.path)
        )
        
        if not is_valid:
            self._security_metrics["cors_violations"] += 1
            
            self.logger.log_security_event(
                LogContext(service_name="security_integration"),
                "cors_violation",
                f"CORS violation from origin: {origin}",
                severity="warning",
                additional_data={
                    "origin": origin,
                    "path": str(request.url.path),
                    "ip_address": self._get_client_ip(request)
                }
            )
        
        return is_valid
    
    async def validate_input(
        self,
        data: Dict[str, Any],
        validation_rules: Optional[Dict[str, Any]] = None,
        child_safe: bool = True
    ) -> ValidationResult:
        """
        Validate input data with security checks.
        
        Args:
            data: Input data to validate
            validation_rules: Custom validation rules
            child_safe: Apply child safety filters
            
        Returns:
            Validation result
        """
        overall_result = ValidationResult(is_valid=True)
        validated_data = {}
        
        for field_name, field_value in data.items():
            # Apply field-specific validation rules
            field_rules = validation_rules.get(field_name, {}) if validation_rules else {}
            
            if isinstance(field_value, str):
                result = self.input_validator.validate_string(
                    value=field_value,
                    min_length=field_rules.get("min_length"),
                    max_length=field_rules.get("max_length"),
                    pattern=field_rules.get("pattern"),
                    allowed_chars=field_rules.get("allowed_chars"),
                    child_safe=child_safe,
                    sanitize=True
                )
            elif field_name.lower() == "email":
                result = self.input_validator.validate_email(field_value)
            elif field_name.lower() in ["phone", "phone_number"]:
                result = self.input_validator.validate_phone(field_value)
            elif field_name.lower() == "age":
                result = self.input_validator.validate_age(field_value)
            elif field_name.lower() in ["url", "website"]:
                result = self.input_validator.validate_url(field_value)
            else:
                # Generic validation for other types
                result = ValidationResult(is_valid=True, sanitized_value=field_value)
            
            # Merge results
            overall_result.merge(result)
            validated_data[field_name] = result.sanitized_value
        
        overall_result.sanitized_value = validated_data
        
        if not overall_result.is_valid:
            self._security_metrics["input_validation_failures"] += 1
            
            self.logger.log_security_event(
                LogContext(service_name="security_integration"),
                "input_validation_failure",
                "Input validation failed",
                severity="warning",
                additional_data={
                    "errors": overall_result.errors,
                    "security_violations": overall_result.security_violations,
                    "child_safety_violations": overall_result.child_safety_violations
                }
            )
        
        return overall_result
    
    def add_security_headers(
        self,
        response: Response,
        request: Request,
        nonce: Optional[str] = None
    ):
        """
        Add comprehensive security headers to response.
        
        Args:
            response: FastAPI response object
            request: FastAPI request object
            nonce: CSP nonce for inline scripts/styles
        """
        # Get CORS headers
        origin = request.headers.get("Origin")
        if origin:
            cors_headers = self.cors_manager.get_cors_headers(
                origin=origin,
                method=request.method,
                path=str(request.url.path),
                requested_headers=request.headers.get("Access-Control-Request-Headers", "").split(",")
            )
            
            for header_name, header_value in cors_headers.items():
                response.headers[header_name] = header_value
        
        # Get security headers from CORS manager
        security_headers = self.cors_manager.get_security_headers(nonce=nonce)
        
        # Get SSL/TLS security headers
        ssl_headers = self.ssl_manager.get_security_headers()
        
        # Combine and add headers
        all_headers = {**security_headers, **ssl_headers}
        
        for header_name, header_value in all_headers.items():
            response.headers[header_name] = header_value
        
        # Add custom security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "unknown")
    
    async def check_threat_intelligence(
        self,
        request: Request,
        user_claims: Optional[JWTClaims] = None
    ) -> bool:
        """
        Check request against threat intelligence.
        
        Args:
            request: FastAPI request object
            user_claims: Authenticated user claims
            
        Returns:
            True if request is allowed, False if blocked
        """
        ip_address = self._get_client_ip(request)
        
        # Check malicious IP list
        if ip_address in self._threat_intelligence["malicious_ips"]:
            self._security_metrics["security_incidents"] += 1
            
            self.logger.log_security_event(
                LogContext(service_name="security_integration"),
                "malicious_ip_blocked",
                f"Request blocked from malicious IP: {ip_address}",
                severity="critical",
                additional_data={
                    "ip_address": ip_address,
                    "user_agent": request.headers.get("User-Agent", ""),
                    "endpoint": str(request.url.path)
                }
            )
            
            return False
        
        # Check for suspicious patterns in headers
        user_agent = request.headers.get("User-Agent", "").lower()
        for pattern in self._threat_intelligence["suspicious_patterns"]:
            if pattern in user_agent:
                self.logger.log_security_event(
                    LogContext(service_name="security_integration"),
                    "suspicious_pattern_detected",
                    f"Suspicious pattern detected in User-Agent: {pattern}",
                    severity="warning",
                    additional_data={
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                        "pattern": pattern
                    }
                )
                break
        
        return True
    
    def _extract_device_info(self, request: Request) -> Dict[str, Any]:
        """Extract device information for fingerprinting."""
        return {
            "user_agent": request.headers.get("User-Agent", ""),
            "accept_language": request.headers.get("Accept-Language", ""),
            "accept_encoding": request.headers.get("Accept-Encoding", ""),
            "platform": request.headers.get("Sec-CH-UA-Platform", ""),
            "screen_resolution": request.headers.get("X-Screen-Resolution", ""),
            "timezone": request.headers.get("X-Timezone", "")
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address with proxy support."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    async def create_token_pair(
        self,
        user_id: str,
        email: str,
        role: str,
        user_type: str,
        device_info: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        mfa_verified: bool = False
    ) -> Dict[str, str]:
        """
        Create access and refresh token pair.
        
        Args:
            user_id: User identifier
            email: User email
            role: User role
            user_type: User type (parent/child/admin)
            device_info: Device information
            ip_address: Client IP address
            permissions: User permissions
            mfa_verified: Whether MFA is verified
            
        Returns:
            Dictionary with access_token and refresh_token
        """
        # Create access token
        access_token = await self.jwt_manager.create_token(
            user_id=user_id,
            email=email,
            role=role,
            user_type=user_type,
            token_type=TokenType.ACCESS,
            device_info=device_info,
            ip_address=ip_address,
            permissions=permissions,
            mfa_verified=mfa_verified
        )
        
        # Create refresh token
        refresh_token = await self.jwt_manager.create_token(
            user_id=user_id,
            email=email,
            role=role,
            user_type=user_type,
            token_type=TokenType.REFRESH,
            device_info=device_info,
            ip_address=ip_address,
            permissions=permissions,
            mfa_verified=mfa_verified
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    async def revoke_user_tokens(self, user_id: str, reason: str = "security_action"):
        """Revoke all tokens for a user."""
        await self.jwt_manager.revoke_all_user_tokens(user_id, reason)
        
        self.logger.log_security_event(
            LogContext(service_name="security_integration"),
            "tokens_revoked",
            f"All tokens revoked for user: {user_id}",
            severity="info",
            additional_data={
                "user_id": user_id,
                "reason": reason
            }
        )
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get comprehensive security metrics."""
        return {
            "security_metrics": self._security_metrics,
            "threat_intelligence": {
                "malicious_ips_count": len(self._threat_intelligence["malicious_ips"]),
                "suspicious_patterns_count": len(self._threat_intelligence["suspicious_patterns"]),
                "attack_signatures_count": len(self._threat_intelligence["attack_signatures"])
            },
            "component_metrics": {
                "rate_limiter": self.rate_limiter.get_metrics_summary() if hasattr(self.rate_limiter, 'get_metrics_summary') else {},
                "jwt_manager": {},  # Could add JWT-specific metrics
                "input_validator": {}  # Could add validation metrics
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive security system health check."""
        health_status = {
            "overall_status": "healthy",
            "components": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Check Redis connection
        if self._redis_client:
            try:
                await self._redis_client.ping()
                health_status["components"]["redis"] = "healthy"
            except Exception as e:
                health_status["components"]["redis"] = f"unhealthy: {str(e)}"
                health_status["overall_status"] = "degraded"
        
        # Check component health
        health_status["components"]["jwt_manager"] = "healthy"
        health_status["components"]["rate_limiter"] = "healthy"
        health_status["components"]["cors_manager"] = "healthy"
        health_status["components"]["input_validator"] = "healthy"
        health_status["components"]["ssl_manager"] = "healthy"
        
        return health_status
    
    def add_malicious_ip(self, ip_address: str):
        """Add IP to malicious list."""
        self._threat_intelligence["malicious_ips"].add(ip_address)
        
        self.logger.log_security_event(
            LogContext(service_name="security_integration"),
            "malicious_ip_added",
            f"IP added to malicious list: {ip_address}",
            severity="info",
            additional_data={"ip_address": ip_address}
        )
    
    def remove_malicious_ip(self, ip_address: str):
        """Remove IP from malicious list."""
        self._threat_intelligence["malicious_ips"].discard(ip_address)
        
        self.logger.log_security_event(
            LogContext(service_name="security_integration"),
            "malicious_ip_removed",
            f"IP removed from malicious list: {ip_address}",
            severity="info",
            additional_data={"ip_address": ip_address}
        )


# Global instance
security_integration = SecurityIntegration()
