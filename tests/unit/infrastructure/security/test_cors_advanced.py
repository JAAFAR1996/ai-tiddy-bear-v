"""
Tests for Advanced CORS Configuration
====================================

Critical security tests for CORS and security headers.
"""

import pytest
from unittest.mock import Mock, patch
import os

from src.infrastructure.security.cors_advanced import (
    AdvancedCORSManager,
    CORSEnvironment,
    SecurityHeaderLevel,
    CORSPolicy,
    SecurityHeaders
)


class TestAdvancedCORSManager:
    """Test advanced CORS manager."""

    @pytest.fixture
    def cors_manager(self):
        """Create CORS manager instance."""
        return AdvancedCORSManager(environment="testing")

    def test_initialization(self, cors_manager):
        """Test CORS manager initialization."""
        assert cors_manager.environment == CORSEnvironment.TESTING
        assert len(cors_manager.policies) == 4
        assert len(cors_manager.security_levels) == 4

    def test_validate_origin_allowed(self, cors_manager):
        """Test origin validation for allowed origins."""
        # Test exact match
        assert cors_manager.validate_origin("http://testserver") is True
        assert cors_manager.validate_origin("http://localhost") is True

    def test_validate_origin_rejected(self, cors_manager):
        """Test origin validation for rejected origins."""
        assert cors_manager.validate_origin("https://malicious.com") is False
        assert cors_manager.validate_origin("") is False
        assert cors_manager.validate_origin(None) is False

    def test_production_origin_validation(self):
        """Test production origin validation."""
        prod_manager = AdvancedCORSManager(environment="production")
        
        # Should allow production domains
        assert prod_manager.validate_origin("https://app.aiteddybear.com") is True
        
        # Should reject HTTP
        assert prod_manager.validate_origin("http://app.aiteddybear.com") is False
        
        # Should reject staging in production
        assert prod_manager.validate_origin("https://staging.aiteddybear.com") is False

    def test_development_origin_validation(self):
        """Test development origin validation."""
        dev_manager = AdvancedCORSManager(environment="development")
        
        # Should allow localhost
        assert dev_manager.validate_origin("http://localhost:3000") is True
        assert dev_manager.validate_origin("http://127.0.0.1:8000") is True

    def test_get_cors_headers_valid_origin(self, cors_manager):
        """Test CORS headers for valid origin."""
        headers = cors_manager.get_cors_headers("http://testserver", "GET")
        
        assert "Access-Control-Allow-Origin" in headers
        assert headers["Access-Control-Allow-Origin"] == "http://testserver"
        assert headers.get("Access-Control-Allow-Credentials") == "true"

    def test_get_cors_headers_invalid_origin(self, cors_manager):
        """Test CORS headers for invalid origin."""
        headers = cors_manager.get_cors_headers("https://malicious.com", "GET")
        
        # Should return empty headers for invalid origin
        assert len(headers) == 0

    def test_preflight_request_headers(self, cors_manager):
        """Test preflight request headers."""
        headers = cors_manager.get_cors_headers(
            "http://testserver", 
            "OPTIONS",
            requested_headers=["Content-Type", "Authorization"]
        )
        
        assert "Access-Control-Allow-Methods" in headers
        assert "Access-Control-Allow-Headers" in headers
        assert "Access-Control-Max-Age" in headers

    def test_security_headers_minimal(self, cors_manager):
        """Test minimal security headers."""
        headers = cors_manager.get_security_headers(SecurityHeaderLevel.MINIMAL)
        
        assert "Content-Security-Policy" in headers
        assert "X-Frame-Options" in headers
        # Should be permissive for development
        assert "*" in headers["Content-Security-Policy"]

    def test_security_headers_strict(self, cors_manager):
        """Test strict security headers."""
        headers = cors_manager.get_security_headers(SecurityHeaderLevel.STRICT)
        
        assert "Content-Security-Policy" in headers
        assert "Strict-Transport-Security" in headers
        assert "X-Content-Type-Options" in headers
        assert "Permissions-Policy" in headers
        # Should be restrictive
        assert "'none'" in headers["Content-Security-Policy"]

    def test_csp_with_nonce(self, cors_manager):
        """Test CSP header with nonce."""
        nonce = "abc123"
        headers = cors_manager.get_security_headers(
            SecurityHeaderLevel.STRICT, 
            nonce=nonce
        )
        
        csp = headers["Content-Security-Policy"]
        assert f"'nonce-{nonce}'" in csp

    def test_route_override(self, cors_manager):
        """Test route-specific CORS policy override."""
        # Add route override
        override_policy = CORSPolicy(
            allowed_origins=["https://special.com"],
            allowed_methods=["GET", "POST"]
        )
        cors_manager.add_route_override("/api/special/*", override_policy)
        
        # Test override is applied
        policy = cors_manager.get_policy("/api/special/endpoint")
        assert "https://special.com" in policy.allowed_origins

    def test_safe_header_validation(self, cors_manager):
        """Test safe header validation."""
        assert cors_manager._is_safe_header("X-Custom-Header") is True
        assert cors_manager._is_safe_header("Content-Type") is True
        
        # Should reject dangerous headers
        assert cors_manager._is_safe_header("Cookie") is False
        assert cors_manager._is_safe_header("Authorization") is False
        assert cors_manager._is_safe_header("Sec-Fetch-Site") is False

    @patch.dict(os.environ, {"CORS_ALLOWED_ORIGINS": "https://custom1.com,https://custom2.com"})
    def test_custom_origins_from_env(self):
        """Test loading custom origins from environment."""
        manager = AdvancedCORSManager(environment="development")
        dev_policy = manager.policies[CORSEnvironment.DEVELOPMENT]
        
        assert "https://custom1.com" in dev_policy.allowed_origins
        assert "https://custom2.com" in dev_policy.allowed_origins

    def test_logger_integration(self, cors_manager):
        """Test logger integration."""
        mock_logger = Mock(spec=True)
        cors_manager.set_logger(mock_logger)
        
        # Test rejected origin logging
        cors_manager.validate_origin("https://malicious.com")
        
        mock_logger.warning.assert_called_once()
        assert "CORS origin rejected" in mock_logger.warning.call_args[0][0]

    def test_permissions_policy_generation(self, cors_manager):
        """Test Permissions-Policy header generation."""
        headers = cors_manager.get_security_headers(SecurityHeaderLevel.STANDARD)
        
        permissions_policy = headers.get("Permissions-Policy")
        assert permissions_policy is not None
        assert "microphone=(self)" in permissions_policy
        assert "camera=()" in permissions_policy

    def test_vary_headers(self, cors_manager):
        """Test Vary headers in CORS response."""
        headers = cors_manager.get_cors_headers("http://testserver", "GET")
        
        assert "Vary" in headers
        assert "Origin" in headers["Vary"]

    def test_null_origin_handling(self):
        """Test null origin handling."""
        # Create policy that allows null origin
        policy = CORSPolicy(
            allowed_origins=["http://testserver"],
            allow_null_origin=True
        )
        
        manager = AdvancedCORSManager(environment="testing")
        manager.policies[CORSEnvironment.TESTING] = policy
        
        assert manager.validate_origin("null") is True

    def test_file_protocol_handling(self):
        """Test file protocol handling."""
        policy = CORSPolicy(
            allowed_origins=["http://testserver"],
            allow_file_protocol=True
        )
        
        manager = AdvancedCORSManager(environment="testing")
        manager.policies[CORSEnvironment.TESTING] = policy
        
        assert manager.validate_origin("file://") is True

    def test_wildcard_origin_matching(self):
        """Test wildcard origin matching."""
        policy = CORSPolicy(
            allowed_origins=["https://*.example.com"],
            allow_wildcards=True
        )
        
        manager = AdvancedCORSManager(environment="testing")
        manager.policies[CORSEnvironment.TESTING] = policy
        
        assert manager.validate_origin("https://app.example.com") is True
        assert manager.validate_origin("https://api.example.com") is True
        assert manager.validate_origin("https://malicious.com") is False


class TestCORSPolicy:
    """Test CORS policy data structure."""

    def test_cors_policy_defaults(self):
        """Test CORS policy default values."""
        policy = CORSPolicy()
        
        assert policy.allow_credentials is True
        assert policy.max_age == 86400
        assert policy.require_https is True
        assert "GET" in policy.allowed_methods
        assert "Authorization" in policy.allowed_headers

    def test_cors_policy_custom_values(self):
        """Test CORS policy with custom values."""
        policy = CORSPolicy(
            allowed_origins=["https://example.com"],
            allow_credentials=False,
            max_age=3600
        )
        
        assert policy.allowed_origins == ["https://example.com"]
        assert policy.allow_credentials is False
        assert policy.max_age == 3600


class TestSecurityHeaders:
    """Test security headers configuration."""

    def test_security_headers_defaults(self):
        """Test security headers default values."""
        headers = SecurityHeaders()
        
        assert "'self'" in headers.content_security_policy["default-src"]
        assert headers.x_content_type_options == "nosniff"
        assert headers.x_frame_options == "DENY"
        assert "microphone" in headers.permissions_policy

    def test_security_headers_custom_csp(self):
        """Test custom CSP configuration."""
        headers = SecurityHeaders(
            content_security_policy={
                "default-src": ["'none'"],
                "script-src": ["'self'"]
            }
        )
        
        assert headers.content_security_policy["default-src"] == ["'none'"]
        assert headers.content_security_policy["script-src"] == ["'self'"]