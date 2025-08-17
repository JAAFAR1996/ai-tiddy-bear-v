"""
Advanced CORS Configuration - Production Security
===============================================
Enterprise-grade CORS configuration with:
- Dynamic origin validation
- Environment-specific policies
- Preflight request optimization
- Security headers management
- CSP (Content Security Policy) integration
- CSRF protection coordination
"""

import os
import re
from typing import List, Optional, Dict, Any, Union, Set, Callable
from urllib.parse import urlparse
from dataclasses import dataclass, field
from enum import Enum
import fnmatch
from datetime import datetime
import json


class CORSEnvironment(Enum):
    """CORS environment profiles."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class SecurityHeaderLevel(Enum):
    """Security header strictness levels."""
    MINIMAL = "minimal"
    STANDARD = "standard"
    STRICT = "strict"
    PARANOID = "paranoid"


@dataclass
class CORSPolicy:
    """CORS policy configuration."""
    # Basic CORS
    allowed_origins: List[str] = field(default_factory=list)
    allowed_methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    allowed_headers: List[str] = field(default_factory=lambda: [
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "X-CSRF-Token",
        "X-Request-ID",
        "X-Device-ID"
    ])
    exposed_headers: List[str] = field(default_factory=lambda: [
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Request-ID"
    ])
    
    # Advanced settings
    allow_credentials: bool = True
    max_age: int = 86400  # 24 hours
    vary_headers: List[str] = field(default_factory=lambda: ["Origin", "Access-Control-Request-Method"])
    
    # Security constraints
    require_https: bool = True
    allow_wildcards: bool = False
    allow_null_origin: bool = False
    allow_file_protocol: bool = False
    
    # Dynamic validation
    origin_validator: Optional[Callable[[str], bool]] = None
    
    # Per-route overrides
    route_overrides: Dict[str, 'CORSPolicy'] = field(default_factory=dict)


@dataclass
class SecurityHeaders:
    """Security headers configuration."""
    # Content Security Policy
    content_security_policy: Dict[str, List[str]] = field(default_factory=lambda: {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'strict-dynamic'"],
        "style-src": ["'self'", "'unsafe-inline'"],  # For child-friendly UI
        "img-src": ["'self'", "data:", "https:"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "connect-src": ["'self'", "wss:", "https:"],
        "media-src": ["'self'", "blob:"],  # For audio/video
        "object-src": ["'none'"],
        "frame-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-ancestors": ["'none'"],
        "upgrade-insecure-requests": []
    })
    
    # Other security headers
    strict_transport_security: str = "max-age=31536000; includeSubDomains; preload"
    x_content_type_options: str = "nosniff"
    x_frame_options: str = "DENY"
    x_xss_protection: str = "1; mode=block"
    referrer_policy: str = "strict-origin-when-cross-origin"
    permissions_policy: Dict[str, List[str]] = field(default_factory=lambda: {
        "camera": [],
        "microphone": ["self"],  # For voice input
        "geolocation": [],
        "payment": [],
        "usb": [],
        "accelerometer": [],
        "gyroscope": []
    })
    
    # Custom headers
    custom_headers: Dict[str, str] = field(default_factory=dict)


class AdvancedCORSManager:
    """
    Advanced CORS and security headers manager.
    
    Features:
    - Environment-specific CORS policies
    - Dynamic origin validation
    - Security headers management
    - CSP generation and validation
    - Per-route customization
    - Audit logging
    """
    
    def __init__(self, environment: Optional[str] = None):
        self.environment = CORSEnvironment(
            environment or os.getenv("ENVIRONMENT", "development")
        )
        self.logger = None  # Will be injected
        
        # Initialize policies
        self.policies = self._initialize_policies()
        
        # Security header levels
        self.security_levels = self._initialize_security_levels()
        
        # Trusted domains cache
        self._trusted_domains_cache: Set[str] = set()
        self._load_trusted_domains()
        
        # Origin validation patterns
        self._origin_patterns: List[re.Pattern] = []
        self._compile_origin_patterns()
    
    def _initialize_policies(self) -> Dict[CORSEnvironment, CORSPolicy]:
        """Initialize environment-specific CORS policies."""
        policies = {}
        
        # Development - Most permissive
        policies[CORSEnvironment.DEVELOPMENT] = CORSPolicy(
            allowed_origins=[
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
                "http://localhost:5173",  # Vite
                "http://localhost:4200"   # Angular
            ],
            allow_credentials=True,
            require_https=False,
            max_age=3600,
            origin_validator=self._validate_development_origin
        )
        
        # Staging - Production-like but with some flexibility
        policies[CORSEnvironment.STAGING] = CORSPolicy(
            allowed_origins=[
                "https://staging.aiteddybear.com",
                "https://staging-app.aiteddybear.com",
                "https://staging-admin.aiteddybear.com"
            ],
            allow_credentials=True,
            require_https=True,
            max_age=43200,  # 12 hours
            origin_validator=self._validate_staging_origin
        )
        
        # Production - Most restrictive
        policies[CORSEnvironment.PRODUCTION] = CORSPolicy(
            allowed_origins=[
                "https://app.aiteddybear.com",
                "https://www.aiteddybear.com",
                "https://admin.aiteddybear.com",
                "https://m.aiteddybear.com"  # Mobile web
            ],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_credentials=True,
            require_https=True,
            allow_wildcards=False,
            allow_null_origin=False,
            max_age=86400,  # 24 hours
            origin_validator=self._validate_production_origin
        )
        
        # Testing - For automated tests
        policies[CORSEnvironment.TESTING] = CORSPolicy(
            allowed_origins=["http://testserver", "http://localhost"],
            allow_credentials=True,
            require_https=False,
            max_age=0  # No caching for tests
        )
        
        # Load custom origins from environment
        self._load_custom_origins(policies)
        
        return policies
    
    def _initialize_security_levels(self) -> Dict[SecurityHeaderLevel, SecurityHeaders]:
        """Initialize security header configurations."""
        levels = {}
        
        # Minimal - Development friendly
        levels[SecurityHeaderLevel.MINIMAL] = SecurityHeaders(
            content_security_policy={
                "default-src": ["*"],
                "script-src": ["* 'unsafe-inline' 'unsafe-eval'"],
                "style-src": ["* 'unsafe-inline'"]
            },
            strict_transport_security="",
            x_frame_options="SAMEORIGIN"
        )
        
        # Standard - Balanced security
        levels[SecurityHeaderLevel.STANDARD] = SecurityHeaders()  # Use defaults
        
        # Strict - Production recommended
        levels[SecurityHeaderLevel.STRICT] = SecurityHeaders(
            content_security_policy={
                "default-src": ["'none'"],
                "script-src": ["'self'", "'strict-dynamic'", "'nonce-{nonce}'"],
                "style-src": ["'self'", "'nonce-{nonce}'"],
                "img-src": ["'self'", "data:", "https://cdn.aiteddybear.com"],
                "font-src": ["'self'", "https://fonts.gstatic.com"],
                "connect-src": ["'self'", "wss://ws.aiteddybear.com", "https://api.aiteddybear.com"],
                "media-src": ["'self'", "blob:", "https://media.aiteddybear.com"],
                "object-src": ["'none'"],
                "frame-src": ["'none'"],
                "base-uri": ["'none'"],
                "form-action": ["'self'"],
                "frame-ancestors": ["'none'"],
                "block-all-mixed-content": [],
                "upgrade-insecure-requests": [],
                "require-trusted-types-for": ["'script'"]
            },
            referrer_policy="no-referrer",
            permissions_policy={
                "camera": [],
                "microphone": ["self"],
                "geolocation": [],
                "payment": [],
                "usb": [],
                "accelerometer": [],
                "gyroscope": [],
                "magnetometer": [],
                "ambient-light-sensor": [],
                "autoplay": ["self"],
                "encrypted-media": ["self"],
                "fullscreen": ["self"],
                "picture-in-picture": ["self"]
            }
        )
        
        # Paranoid - Maximum security
        levels[SecurityHeaderLevel.PARANOID] = SecurityHeaders(
            content_security_policy={
                "default-src": ["'none'"],
                "script-src": ["'self'"],
                "style-src": ["'self'"],
                "img-src": ["'self'"],
                "font-src": ["'self'"],
                "connect-src": ["'self'"],
                "media-src": ["'none'"],
                "object-src": ["'none'"],
                "frame-src": ["'none'"],
                "sandbox": ["allow-forms", "allow-same-origin", "allow-scripts"],
                "base-uri": ["'none'"],
                "form-action": ["'none'"],
                "frame-ancestors": ["'none'"],
                "block-all-mixed-content": [],
                "disown-opener": [],
                "require-sri-for": ["script", "style"],
                "require-trusted-types-for": ["'script'"],
                "trusted-types": ["default"]
            },
            x_frame_options="DENY",
            referrer_policy="no-referrer",
            custom_headers={
                "X-Permitted-Cross-Domain-Policies": "none",
                "X-Download-Options": "noopen",
                "X-DNS-Prefetch-Control": "off"
            }
        )
        
        return levels
    
    def _load_trusted_domains(self):
        """Load trusted domains from configuration."""
        # Default trusted domains
        self._trusted_domains_cache.update([
            "aiteddybear.com",
            "api.aiteddybear.com",
            "app.aiteddybear.com",
            "admin.aiteddybear.com",
            "cdn.aiteddybear.com",
            "media.aiteddybear.com"
        ])
        
        # Load from environment
        custom_domains = os.getenv("CORS_TRUSTED_DOMAINS", "").split(",")
        for domain in custom_domains:
            domain = domain.strip()
            if domain:
                self._trusted_domains_cache.add(domain)
    
    def _compile_origin_patterns(self):
        """Compile regex patterns for origin matching."""
        # Subdomain pattern
        subdomain_pattern = re.compile(
            r"^https?://([a-zA-Z0-9-]+\.)*aiteddybear\.com(:\d+)?$"
        )
        self._origin_patterns.append(subdomain_pattern)
        
        # Partner domains pattern (if any)
        partner_domains = os.getenv("CORS_PARTNER_DOMAINS", "")
        if partner_domains:
            for domain in partner_domains.split(","):
                domain = domain.strip()
                if domain:
                    pattern = re.compile(
                        rf"^https?://([a-zA-Z0-9-]+\.)*{re.escape(domain)}(:\d+)?$"
                    )
                    self._origin_patterns.append(pattern)
    
    def _load_custom_origins(self, policies: Dict[CORSEnvironment, CORSPolicy]):
        """Load custom origins from environment variables."""
        custom_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
        if custom_origins:
            origins = [o.strip() for o in custom_origins.split(",") if o.strip()]
            
            # Add to appropriate environments
            if self.environment == CORSEnvironment.PRODUCTION:
                # In production, only add HTTPS origins
                https_origins = [o for o in origins if o.startswith("https://")]
                policies[CORSEnvironment.PRODUCTION].allowed_origins.extend(https_origins)
            else:
                # In other environments, add all
                for env, policy in policies.items():
                    if env != CORSEnvironment.PRODUCTION:
                        policy.allowed_origins.extend(origins)
    
    def _validate_development_origin(self, origin: str) -> bool:
        """Validate origin for development environment."""
        parsed = urlparse(origin)
        
        # Allow localhost and local IPs
        if parsed.hostname in ["localhost", "127.0.0.1", "::1"]:
            return True
        
        # Allow local network IPs
        if parsed.hostname and (
            parsed.hostname.startswith("192.168.") or
            parsed.hostname.startswith("10.") or
            parsed.hostname.startswith("172.")
        ):
            return True
        
        # Allow configured development domains
        return self._check_origin_patterns(origin)
    
    def _validate_staging_origin(self, origin: str) -> bool:
        """Validate origin for staging environment."""
        parsed = urlparse(origin)
        
        # Must be HTTPS
        if parsed.scheme != "https":
            return False
        
        # Check if it's a staging subdomain
        if parsed.hostname and "staging" in parsed.hostname:
            return self._check_origin_patterns(origin)
        
        return False
    
    def _validate_production_origin(self, origin: str) -> bool:
        """Validate origin for production environment."""
        parsed = urlparse(origin)
        
        # Must be HTTPS
        if parsed.scheme != "https":
            return False
        
        # No staging/dev/test in production
        if parsed.hostname and any(env in parsed.hostname for env in ["staging", "dev", "test", "localhost"]):
            return False
        
        # Check trusted domains
        if parsed.hostname in self._trusted_domains_cache:
            return True
        
        # Check patterns
        return self._check_origin_patterns(origin)
    
    def _check_origin_patterns(self, origin: str) -> bool:
        """Check origin against compiled patterns."""
        for pattern in self._origin_patterns:
            if pattern.match(origin):
                return True
        return False
    
    def validate_origin(self, origin: str, path: Optional[str] = None) -> bool:
        """
        Validate if origin is allowed.
        
        Args:
            origin: Origin header value
            path: Request path for route-specific policies
            
        Returns:
            True if origin is allowed
        """
        if not origin:
            return False
        
        # Get current policy
        policy = self.get_policy(path)
        
        # Check exact matches first
        if origin in policy.allowed_origins:
            return True
        
        # Check null origin
        if origin == "null" and policy.allow_null_origin:
            return True
        
        # Check file protocol
        if origin.startswith("file://") and policy.allow_file_protocol:
            return True
        
        # Check wildcards
        if policy.allow_wildcards:
            for allowed_origin in policy.allowed_origins:
                if "*" in allowed_origin:
                    if fnmatch.fnmatch(origin, allowed_origin):
                        return True
        
        # Use custom validator if provided
        if policy.origin_validator:
            if policy.origin_validator(origin):
                return True
        
        # Log rejected origin
        if self.logger:
            self.logger.warning(
                f"CORS origin rejected",
                extra={
                    "origin": origin,
                    "path": path,
                    "environment": self.environment.value
                }
            )
        
        return False
    
    def get_policy(self, path: Optional[str] = None) -> CORSPolicy:
        """Get CORS policy for current environment and path."""
        base_policy = self.policies.get(self.environment, self.policies[CORSEnvironment.DEVELOPMENT])
        
        # Check for route-specific override
        if path and base_policy.route_overrides:
            for route_pattern, override_policy in base_policy.route_overrides.items():
                if fnmatch.fnmatch(path, route_pattern):
                    return override_policy
        
        return base_policy
    
    def get_security_headers(
        self,
        level: Optional[SecurityHeaderLevel] = None,
        nonce: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get security headers for response.
        
        Args:
            level: Security level (auto-determined if not provided)
            nonce: CSP nonce for inline scripts/styles
            
        Returns:
            Dictionary of security headers
        """
        # Determine security level
        if not level:
            if self.environment == CORSEnvironment.PRODUCTION:
                level = SecurityHeaderLevel.STRICT
            elif self.environment == CORSEnvironment.STAGING:
                level = SecurityHeaderLevel.STANDARD
            else:
                level = SecurityHeaderLevel.MINIMAL
        
        headers_config = self.security_levels[level]
        headers = {}
        
        # Build CSP header
        if headers_config.content_security_policy:
            csp_parts = []
            for directive, values in headers_config.content_security_policy.items():
                if values:
                    # Replace nonce placeholder
                    processed_values = []
                    for value in values:
                        if nonce and "{nonce}" in value:
                            processed_values.append(value.format(nonce=nonce))
                        else:
                            processed_values.append(value)
                    
                    csp_parts.append(f"{directive} {' '.join(processed_values)}")
                else:
                    csp_parts.append(directive)
            
            headers["Content-Security-Policy"] = "; ".join(csp_parts)
        
        # Add other security headers
        if headers_config.strict_transport_security:
            headers["Strict-Transport-Security"] = headers_config.strict_transport_security
        
        if headers_config.x_content_type_options:
            headers["X-Content-Type-Options"] = headers_config.x_content_type_options
        
        if headers_config.x_frame_options:
            headers["X-Frame-Options"] = headers_config.x_frame_options
        
        if headers_config.x_xss_protection:
            headers["X-XSS-Protection"] = headers_config.x_xss_protection
        
        if headers_config.referrer_policy:
            headers["Referrer-Policy"] = headers_config.referrer_policy
        
        # Build Permissions-Policy header
        if headers_config.permissions_policy:
            policy_parts = []
            for feature, allowlist in headers_config.permissions_policy.items():
                if allowlist:
                    policy_parts.append(f'{feature}=({" ".join(allowlist)})')
                else:
                    policy_parts.append(f"{feature}=()")
            
            headers["Permissions-Policy"] = ", ".join(policy_parts)
        
        # Add custom headers
        headers.update(headers_config.custom_headers)
        
        return headers
    
    def get_cors_headers(
        self,
        origin: str,
        method: str = "GET",
        path: Optional[str] = None,
        requested_headers: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Get CORS headers for response.
        
        Args:
            origin: Request origin
            method: HTTP method
            path: Request path
            requested_headers: Access-Control-Request-Headers value
            
        Returns:
            Dictionary of CORS headers
        """
        headers = {}
        
        # Validate origin
        if not self.validate_origin(origin, path):
            return headers
        
        policy = self.get_policy(path)
        
        # Allow origin
        headers["Access-Control-Allow-Origin"] = origin
        
        # Allow credentials
        if policy.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"
        
        # For preflight requests
        if method == "OPTIONS":
            # Allow methods
            headers["Access-Control-Allow-Methods"] = ", ".join(policy.allowed_methods)
            
            # Allow headers
            allowed_headers = policy.allowed_headers.copy()
            if requested_headers:
                # Add requested headers if they're safe
                for header in requested_headers:
                    if header.lower() not in [h.lower() for h in allowed_headers]:
                        # Validate header name
                        if self._is_safe_header(header):
                            allowed_headers.append(header)
            
            headers["Access-Control-Allow-Headers"] = ", ".join(allowed_headers)
            
            # Max age
            headers["Access-Control-Max-Age"] = str(policy.max_age)
        
        # Expose headers
        if policy.exposed_headers:
            headers["Access-Control-Expose-Headers"] = ", ".join(policy.exposed_headers)
        
        # Vary headers
        if policy.vary_headers:
            headers["Vary"] = ", ".join(policy.vary_headers)
        
        return headers
    
    def _is_safe_header(self, header: str) -> bool:
        """Check if header name is safe to allow."""
        # Reject potentially dangerous headers
        dangerous_headers = [
            "host", "cookie", "set-cookie", "authorization",
            "proxy-authorization", "sec-", "referer"
        ]
        
        header_lower = header.lower()
        for dangerous in dangerous_headers:
            if header_lower.startswith(dangerous):
                return False
        
        # Check header name format
        if not re.match(r"^[a-zA-Z0-9\-_]+$", header):
            return False
        
        return True
    
    def add_route_override(
        self,
        path_pattern: str,
        policy: CORSPolicy,
        environment: Optional[CORSEnvironment] = None
    ):
        """Add route-specific CORS policy override."""
        target_env = environment or self.environment
        if target_env in self.policies:
            self.policies[target_env].route_overrides[path_pattern] = policy
    
    def set_logger(self, logger):
        """Set logger for audit logging."""
        self.logger = logger


# Global instance
advanced_cors_manager = AdvancedCORSManager()
