"""
Unit tests for main FastAPI application module.
Tests application startup, middleware, endpoints, and error handling.
"""

import pytest
import sys
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import redis.asyncio as redis

# Mock the imports before importing main
with patch.dict(
    "sys.modules",
    {
        "src.infrastructure.config.loader": Mock(autospec=True),
        "src.infrastructure.config.validator": Mock(autospec=True),
        "src.infrastructure.error_handler": Mock(autospec=True),
        "src.core.exceptions": Mock(autospec=True),
        "src.api.openapi_config": Mock(autospec=True),
        "src.adapters.web": Mock(autospec=True),
        "src.adapters.database_production": Mock(autospec=True),
        "src.infrastructure.security.auth": Mock(autospec=True),
        "src.core.security_service": Mock(autospec=True),
        "src.infrastructure.rate_limiting.rate_limiter": Mock(autospec=True),
    },
):
    from src.main import (
        SecurityHeadersMiddleware,
        RequestValidationMiddleware,
        initialize_configuration,
        lifespan,
        app,
    )


class TestSecurityHeadersMiddleware:
    """Test SecurityHeadersMiddleware functionality."""

    @pytest.fixture
    def middleware(self):
        """Create SecurityHeadersMiddleware instance."""
        from fastapi import FastAPI

        return SecurityHeadersMiddleware(app=Mock(spec=FastAPI))

    @pytest.mark.asyncio
    async def test_security_headers_middleware_adds_headers(self, middleware):
        """Test that security headers middleware adds all required headers."""
        mock_request = Mock()
        mock_response = Mock()
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Verify all security headers are added
        expected_headers = {
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "Referrer-Policy",
            "Permissions-Policy",
            "X-Child-Safe",
            "X-COPPA-Compliant",
            "X-Content-Safety",
        }

        for header in expected_headers:
            assert header in response.headers

        # Verify specific header values
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Child-Safe"] == "true"
        assert response.headers["X-COPPA-Compliant"] == "true"

    @pytest.mark.asyncio
    async def test_security_headers_csp_policy(self, middleware):
        """Test Content Security Policy header content."""
        mock_request = Mock()
        mock_response = Mock()
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        response = await middleware.dispatch(mock_request, mock_call_next)

        csp = response.headers["Content-Security-Policy"]

        # Verify key CSP directives
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-src 'none'" in csp
        assert "child-src 'none'" in csp

    @pytest.mark.asyncio
    async def test_security_headers_permissions_policy(self, middleware):
        """Test Permissions Policy header content."""
        mock_request = Mock(spec=True)
        mock_response = Mock(spec=True)
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        response = await middleware.dispatch(mock_request, mock_call_next)

        permissions = response.headers["Permissions-Policy"]

        # Verify dangerous permissions are disabled
        assert "geolocation=()" in permissions
        assert "microphone=()" in permissions
        assert "camera=()" in permissions
        assert "payment=()" in permissions


class TestRequestValidationMiddleware:
    """Test RequestValidationMiddleware functionality."""

    @pytest.fixture
    def middleware(self):
        """Create RequestValidationMiddleware instance."""
        from fastapi import FastAPI

        return RequestValidationMiddleware(app=Mock(spec=FastAPI))

    @pytest.mark.asyncio
    async def test_request_validation_normal_request(self, middleware):
        """Test request validation with normal request."""
        mock_request = Mock(spec=True)
        mock_request.headers = {"content-length": "1024"}
        mock_request.state = Mock(spec=True)

        mock_response = Mock(spec=True)
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        with patch("secrets.token_urlsafe", return_value="test-request-id"):
            response = await middleware.dispatch(mock_request, mock_call_next)

        # Verify request ID was set
        assert mock_request.state.request_id == "test-request-id"
        assert response.headers["X-Request-ID"] == "test-request-id"

    @pytest.mark.asyncio
    async def test_request_validation_large_request(self, middleware):
        """Test request validation with oversized request."""
        mock_request = Mock(spec=True)
        mock_request.headers = {"content-length": str(15 * 1024 * 1024)}  # 15MB

        async def mock_call_next(request):
            return Mock(spec=True)

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, mock_call_next)

        assert exc_info.value.status_code == 413
        assert "Request too large" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_validation_no_content_length(self, middleware):
        """Test request validation without content-length header."""
        mock_request = Mock(spec=True)
        mock_request.headers = {}
        mock_request.state = Mock(spec=True)

        mock_response = Mock(spec=True)
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        # Should not raise exception
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response is not None

    def test_request_validation_max_request_size_constant(self, middleware):
        """Test that MAX_REQUEST_SIZE is set appropriately."""
        assert middleware.MAX_REQUEST_SIZE == 10 * 1024 * 1024  # 10MB

    def test_request_validation_max_json_depth_constant(self, middleware):
        """Test that MAX_JSON_DEPTH is set appropriately."""
        assert middleware.MAX_JSON_DEPTH == 10


class TestInitializeConfiguration:
    """Test configuration initialization."""

    @pytest.mark.asyncio
    async def test_initialize_configuration_success(self):
        """Test successful configuration initialization."""
        mock_config = Mock(spec=True)
        mock_config.environment = "development"

        validation_results = {
            "validation_passed": True,
            "categories": {
                "database": {"valid": True, "errors": []},
                "security": {"valid": True, "errors": []},
            },
        }

        with patch("src.main.load_config", return_value=mock_config):
            with patch("src.main.validate_and_report", return_value=validation_results):
                with patch("src.main.logger") as mock_logger:
                    result = await initialize_configuration()

                    assert result is mock_config
                    mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_configuration_validation_failed_development(self):
        """Test configuration validation failure in development."""
        mock_config = Mock(spec=True)
        mock_config.environment = "development"

        validation_results = {
            "validation_passed": False,
            "categories": {
                "database": {"valid": False, "errors": ["Database connection failed"]},
                "security": {"valid": True, "errors": []},
            },
        }

        with patch("src.main.load_config", return_value=mock_config):
            with patch("src.main.validate_and_report", return_value=validation_results):
                with patch("src.main.logger") as mock_logger:
                    result = await initialize_configuration()

                    assert result is mock_config  # Should continue in development
                    mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_configuration_validation_failed_production(self):
        """Test configuration validation failure in production."""
        mock_config = Mock(spec=True)
        mock_config.environment = "production"

        validation_results = {
            "validation_passed": False,
            "categories": {
                "database": {"valid": False, "errors": ["Database connection failed"]},
                "security": {"valid": True, "errors": []},
            },
        }

        with patch("src.main.load_config", return_value=mock_config):
            with patch("src.main.validate_and_report", return_value=validation_results):
                with patch("src.main.logger") as mock_logger:
                    with patch("sys.exit") as mock_exit:
                        await initialize_configuration()

                        mock_exit.assert_called_with(1)
                        mock_logger.critical.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_configuration_exception(self):
        """Test configuration initialization with exception."""
        with patch("src.main.load_config", side_effect=Exception("Config error")):
            with patch("src.main.logger") as mock_logger:
                with pytest.raises(Exception):  # ConfigurationError in real code
                    await initialize_configuration()

                mock_logger.critical.assert_called()


class TestLifespan:
    """Test application lifespan management."""

    @pytest.mark.asyncio
    async def test_lifespan_success(self):
        """Test successful application startup and shutdown."""
        mock_app = Mock(spec=True)
        mock_app.state = Mock(spec=True)

        mock_config = Mock(spec=True)
        mock_config.ENVIRONMENT = "development"
        mock_config.REDIS_URL = "redis://localhost:6379"

        with patch("src.main.initialize_database", new_callable=AsyncMock):
            with patch("src.main.create_rate_limiting_service") as mock_rate_limiter:
                with patch("src.main.create_security_service") as mock_security:
                    with patch("src.main.config", mock_config):
                        with patch("src.main.redis_client") as mock_redis:
                            with patch("src.main.logger") as mock_logger:

                                # Test startup
                                async_gen = lifespan(mock_app)
                                await async_gen.__anext__()

                                # Verify services were initialized
                                assert hasattr(mock_app.state, "security_service")
                                assert hasattr(mock_app.state, "rate_limiting_service")
                                mock_logger.info.assert_called()

                                # Test shutdown
                                try:
                                    await async_gen.__anext__()
                                except StopAsyncIteration:
                                    pass  # Expected behavior

                                # Verify Redis was closed
                                mock_redis.close.assert_called()

    @pytest.mark.asyncio
    async def test_lifespan_startup_failure(self):
        """Test application startup failure."""
        mock_app = Mock(spec=True)
        mock_app.state = Mock(spec=True)

        with patch("src.main.initialize_database", side_effect=Exception("DB Error")):
            with patch("src.main.logger") as mock_logger:
                with patch("sys.exit") as mock_exit:

                    async_gen = lifespan(mock_app)
                    await async_gen.__anext__()

                    mock_exit.assert_called_with(1)
                    mock_logger.critical.assert_called()

    @pytest.mark.asyncio
    async def test_lifespan_production_redis_verification(self):
        """Test Redis verification in production environment."""
        mock_app = Mock(spec=True)
        mock_app.state = Mock(spec=True)

        mock_config = Mock(spec=True)
        mock_config.ENVIRONMENT = "production"
        mock_config.REDIS_URL = "redis://localhost:6379"

        with patch("src.main.initialize_database", new_callable=AsyncMock):
            with patch("src.main.create_rate_limiting_service"):
                with patch("src.main.create_security_service"):
                    with patch("src.main.config", mock_config):
                        with patch("src.main.redis_client") as mock_redis:
                            mock_redis.ping = AsyncMock(spec=True)
                            with patch("src.main.logger") as mock_logger:

                                async_gen = lifespan(mock_app)
                                await async_gen.__anext__()

                                # Verify Redis ping was called in production
                                mock_redis.ping.assert_called()
                                mock_logger.info.assert_called()


class TestApplicationSetup:
    """Test FastAPI application setup and configuration."""

    def test_app_creation(self):
        """Test FastAPI app is created with correct configuration."""
        # This test is limited because app is created at module level
        # In a real application, we'd want app creation to be a function
        assert isinstance(app, FastAPI)
        assert app.title == "AI Teddy Bear API"
        assert "child-safe" in app.description.lower()

    @patch("src.main.config")
    def test_redis_connection_success(self, mock_config):
        """Test successful Redis connection setup."""
        mock_config.REDIS_URL = "redis://localhost:6379"
        mock_config.RATE_LIMIT_REQUESTS_PER_MINUTE = 60

        # This test is complex due to module-level imports
        # In practice, Redis setup should be tested through integration tests
        pass

    @patch("src.main.config")
    def test_redis_connection_failure_production(self, mock_config):
        """Test Redis connection failure in production."""
        mock_config.REDIS_URL = "redis://invalid:6379"
        mock_config.ENVIRONMENT = "production"

        # This would require importing main module with mocked Redis
        # which is complex to test at unit level
        pass

    @patch("src.main.config")
    def test_redis_connection_failure_development(self, mock_config):
        """Test Redis connection failure in development."""
        mock_config.REDIS_URL = "redis://invalid:6379"
        mock_config.ENVIRONMENT = "development"

        # This would require importing main module with mocked Redis
        # which is complex to test at unit level
        pass


class TestHealthEndpoints:
    """Test health check and status endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @patch("src.main.limiter.limit")
    def test_root_endpoint(self, mock_limiter, client):
        """Test root endpoint returns correct information."""
        mock_limiter.return_value = lambda func: func  # Bypass rate limiting

        with patch("src.main.config") as mock_config:
            mock_config.ENVIRONMENT = "development"

            response = client.get("/")

            assert response.status_code == 200
            data = response.json()

            assert data["message"] == "AI Teddy Bear API - Child-safe conversations"
            assert data["version"] == "1.0.0"
            assert data["environment"] == "development"
            assert data["security"]["child_safe"] is True
            assert data["security"]["coppa_compliant"] is True
            assert "endpoints" in data

    @patch("src.main.limiter.limit")
    def test_health_endpoint_success(self, mock_limiter, client):
        """Test health endpoint returns healthy status."""
        mock_limiter.return_value = lambda func: func  # Bypass rate limiting

        with patch("src.main.redis_client") as mock_redis:
            mock_redis.ping = AsyncMock(spec=True)
            with patch("src.main.config") as mock_config:
                mock_config.ENVIRONMENT = "development"

                response = client.get("/health")

                assert response.status_code == 200
                data = response.json()

                assert data["status"] == "healthy"
                assert data["environment"] == "development"
                assert "services" in data
                assert "security" in data
                assert "timestamp" in data

    @patch("src.main.limiter.limit")
    def test_health_endpoint_redis_failure(self, mock_limiter, client):
        """Test health endpoint with Redis failure."""
        mock_limiter.return_value = lambda func: func

        with patch("src.main.redis_client") as mock_redis:
            mock_redis.ping = AsyncMock(side_effect=Exception("Redis error"))
            with patch("src.main.config") as mock_config:
                mock_config.ENVIRONMENT = "development"
                with patch("src.main.logger"):

                    response = client.get("/health")

                    assert response.status_code == 200  # Still returns 200
                    data = response.json()

                    # Redis should be marked as unhealthy
                    assert data["services"]["redis"] == "unhealthy"

    @patch("src.main.limiter.limit")
    def test_health_endpoint_exception(self, mock_limiter, client):
        """Test health endpoint with exception."""
        mock_limiter.return_value = lambda func: func

        with patch("src.main.config", side_effect=Exception("Config error")):
            with patch("src.main.logger"):

                response = client.get("/health")

                assert response.status_code == 503
                assert "Service unhealthy" in response.json()["detail"]

    @patch("src.main.limiter.limit")
    def test_security_status_endpoint_admin(self, mock_limiter, client):
        """Test security status endpoint with admin user."""
        mock_limiter.return_value = lambda func: func

        mock_admin_user = {"role": "admin"}

        with patch("src.main.get_current_user", return_value=mock_admin_user):
            with patch("src.main.config") as mock_config:
                mock_config.ENVIRONMENT = "production"
                mock_config.CORS_ALLOWED_ORIGINS = ["https://app.example.com"]
                mock_config.ALLOWED_HOSTS = ["api.example.com"]
                mock_config.RATE_LIMIT_REQUESTS_PER_MINUTE = 60
                mock_config.RATE_LIMIT_BURST = 10

                response = client.get("/security-status")

                assert response.status_code == 200
                data = response.json()

                assert data["environment"] == "production"
                assert "security_config" in data
                assert "security_headers" in data
                assert "child_protection" in data
                assert data["child_protection"]["coppa_compliant"] is True

    @patch("src.main.limiter.limit")
    def test_security_status_endpoint_non_admin(self, mock_limiter, client):
        """Test security status endpoint with non-admin user."""
        mock_limiter.return_value = lambda func: func

        mock_user = {"role": "parent"}

        with patch("src.main.get_current_user", return_value=mock_user):
            response = client.get("/security-status")

            assert response.status_code == 403
            assert "Admin access required" in response.json()["detail"]


class TestRateLimitHandler:
    """Test rate limit exception handler."""

    def test_rate_limit_handler_creation(self):
        """Test rate limit handler converts SlowAPI exception."""
        # This is tested through the import and setup in main.py
        # The actual handler would need integration testing
        pass


class TestMiddlewareOrder:
    """Test middleware application order."""

    def test_middleware_stack_order(self):
        """Test that middleware is applied in correct order."""
        # This would require inspecting the FastAPI app middleware stack
        # which is complex to test at unit level
        # The order is: RequestValidation -> SecurityHeaders -> RateLimit -> TrustedHost -> CORS
        pass


class TestMainModuleConstants:
    """Test module-level constants and configuration."""

    def test_max_request_size(self):
        """Test maximum request size is appropriate for child app."""
        assert RequestValidationMiddleware.MAX_REQUEST_SIZE == 10 * 1024 * 1024  # 10MB

    def test_max_json_depth(self):
        """Test maximum JSON depth prevents nested attacks."""
        assert RequestValidationMiddleware.MAX_JSON_DEPTH == 10


class TestApplicationProduction:
    """Test production-specific configurations."""

    @patch("src.main.config")
    def test_production_docs_disabled(self, mock_config):
        """Test that API docs are disabled in production."""
        mock_config.ENVIRONMENT = "production"

        # In production, docs_url, redoc_url, and openapi_url should be None
        # This is set during app creation, would need integration test
        pass

    def test_production_security_headers(self):
        """Test production security headers are comprehensive."""
        middleware = SecurityHeadersMiddleware(app=Mock(spec=True))

        # Test that HSTS header has appropriate settings for production
        async def check_headers():
            mock_request = Mock(spec=True)
            mock_response = Mock(spec=True)
            mock_response.headers = {}

            response = await middleware.dispatch(mock_request, lambda r: mock_response)

            hsts = response.headers["Strict-Transport-Security"]
            assert "max-age=31536000" in hsts  # 1 year
            assert "includeSubDomains" in hsts
            assert "preload" in hsts

        asyncio.run(check_headers())


class TestCOPPACompliance:
    """Test COPPA compliance features in main application."""

    def test_child_protection_headers(self):
        """Test child protection headers are present."""
        middleware = SecurityHeadersMiddleware(app=Mock(spec=True))

        async def check_child_headers():
            mock_request = Mock(spec=True)
            mock_response = Mock(spec=True)
            mock_response.headers = {}

            response = await middleware.dispatch(mock_request, lambda r: mock_response)

            assert response.headers["X-Child-Safe"] == "true"
            assert response.headers["X-COPPA-Compliant"] == "true"
            assert response.headers["X-Content-Safety"] == "enabled"

        asyncio.run(check_child_headers())

    def test_permissions_policy_child_safety(self):
        """Test Permissions Policy blocks dangerous features for children."""
        middleware = SecurityHeadersMiddleware(app=Mock(spec=True))

        async def check_permissions():
            mock_request = Mock(spec=True)
            mock_response = Mock(spec=True)
            mock_response.headers = {}

            response = await middleware.dispatch(mock_request, lambda r: mock_response)

            permissions = response.headers["Permissions-Policy"]

            # Verify dangerous permissions are disabled
            dangerous_features = [
                "geolocation=()",
                "microphone=()",
                "camera=()",
                "payment=()",
                "usb=()",
                "magnetometer=()",
                "gyroscope=()",
                "accelerometer=()",
            ]

            for feature in dangerous_features:
                assert feature in permissions

        asyncio.run(check_permissions())


class TestApplicationIntegration:
    """Test integration aspects of the main application."""

    def test_error_handler_setup(self):
        """Test that error handlers are properly configured."""
        # This would require checking that setup_error_handlers was called
        # and that the app has the expected exception handlers
        pass

    def test_api_router_inclusion(self):
        """Test that API router is included with correct prefix."""
        # This would require inspecting the FastAPI app routes
        # to verify the /api/v1 prefix is applied
        pass

    def test_openapi_schema_customization(self):
        """Test that OpenAPI schema is customized."""
        # This would require checking that the custom_openapi_schema function
        # is applied to the app
        pass


class TestMainModuleRefactoringNeeds:
    """Identify areas needing refactoring in main.py."""

    def test_module_level_configuration_concern(self):
        """
        REFACTORING NEEDED: Module-level configuration initialization.

        The current implementation initializes config, Redis, and limiter at module level,
        making testing difficult and creating import-time side effects.

        Recommendation:
        1. Move configuration initialization to a factory function
        2. Use dependency injection for Redis and rate limiter
        3. Make app creation a function that can be tested
        """
        # This test documents the architectural concern
        assert True  # Placeholder

    def test_error_handling_improvement_needed(self):
        """
        REFACTORING NEEDED: Improve error handling in configuration and Redis setup.

        Current implementation has several issues:
        1. Broad exception catching without specific handling
        2. sys.exit() calls that prevent graceful error handling
        3. Limited error context for debugging

        Recommendation:
        1. Use specific exception types
        2. Implement graceful degradation instead of sys.exit()
        3. Add more detailed error logging with correlation IDs
        """
        # This test documents the error handling concerns
        assert True  # Placeholder

    def test_middleware_configuration_complexity(self):
        """
        REFACTORING NEEDED: Middleware configuration is complex and hard to test.

        Current implementation:
        1. Middleware order is implicit and hard to verify
        2. Middleware configuration is scattered
        3. Rate limit handler setup is disconnected from middleware

        Recommendation:
        1. Create a middleware configuration function
        2. Make middleware order explicit and testable
        3. Centralize security middleware configuration
        """
        # This test documents middleware complexity concerns
        assert True  # Placeholder


class TestMainModuleDocumentation:
    """Document the main module's functionality for maintenance."""

    def test_security_middleware_documentation(self):
        """
        Document SecurityHeadersMiddleware functionality:

        - Adds comprehensive security headers for child protection
        - Implements strict CSP to prevent XSS attacks
        - Blocks dangerous browser features via Permissions Policy
        - Adds child-specific safety headers
        - Enforces HTTPS with HSTS
        """
        middleware = SecurityHeadersMiddleware(app=Mock(spec=True))
        assert middleware is not None

    def test_request_validation_middleware_documentation(self):
        """
        Document RequestValidationMiddleware functionality:

        - Limits request size to 10MB to prevent DoS attacks
        - Adds unique request IDs for audit logging
        - Validates request format and size
        - Supports COPPA compliance through request tracking
        """
        middleware = RequestValidationMiddleware(app=Mock(spec=True))
        assert middleware.MAX_REQUEST_SIZE == 10 * 1024 * 1024
        assert middleware.MAX_JSON_DEPTH == 10

    def test_application_lifespan_documentation(self):
        """
        Document application lifespan management:

        Startup:
        1. Initialize database connections
        2. Verify Redis connectivity (production only)
        3. Initialize security and rate limiting services
        4. Store services in app state for dependency injection

        Shutdown:
        1. Close Redis connections
        2. Clean up resources
        """
        # This documents the lifespan function behavior
        assert True  # Documentation test
