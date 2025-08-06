"""
Unit Tests for Unified JWT Implementation
========================================
Tests the integration between basic auth.py and advanced jwt_advanced.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.security.auth import (
    TokenManager,
    UserAuthenticator,
    AuthorizationManager,
    get_token_manager,
    get_user_authenticator,
    get_authorization_manager,
    AuthenticationError,
)
from src.infrastructure.security.jwt_advanced import (
    AdvancedJWTManager,
    TokenType,
)


class TestUnifiedJWTSystem:
    """Test unified JWT system integration."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        from src.infrastructure.config.loader import get_config

        config = MagicMock(spec=get_config().__class__)
        config.JWT_SECRET_KEY = "test-secret-key"
        config.REDIS_URL = "redis://localhost:6379"
        return config

    @pytest.fixture
    def token_manager(self, mock_config):
        """Create token manager instance."""
        with patch(
            "src.infrastructure.security.auth.get_config",
            return_value=mock_config,
            autospec=True,
        ):
            return TokenManager(mock_config)

    @pytest.fixture
    def user_authenticator(self):
        """Create user authenticator instance."""
        return UserAuthenticator()

    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        return {
            "id": "123",
            "sub": "123",
            "email": "test@example.com",
            "role": "parent",
            "user_type": "parent",
            "permissions": ["child:read", "child:create"],
        }

    @pytest.mark.asyncio
    async def test_token_creation_with_advanced_features(
        self, token_manager, sample_user_data
    ):
        """Test token creation using advanced JWT manager."""
        # Test access token creation
        access_token = token_manager.create_access_token(sample_user_data)
        assert access_token is not None
        assert isinstance(access_token, str)
        assert len(access_token) > 0

        # Test refresh token creation
        refresh_token = token_manager.create_refresh_token(sample_user_data)
        assert refresh_token is not None
        assert isinstance(refresh_token, str)
        assert len(refresh_token) > 0

        # Tokens should be different
        assert access_token != refresh_token

    @pytest.mark.asyncio
    async def test_token_verification_with_advanced_features(
        self, token_manager, sample_user_data
    ):
        """Test token verification using advanced JWT manager."""
        # Create token
        token = token_manager.create_access_token(sample_user_data)

        # Verify token
        payload = token_manager.verify_token(token)

        assert payload is not None
        assert payload["sub"] == sample_user_data["id"]
        assert payload["email"] == sample_user_data["email"]
        assert payload["role"] == sample_user_data["role"]
        assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_token_refresh_with_advanced_features(
        self, token_manager, sample_user_data
    ):
        """Test token refresh using advanced JWT manager."""
        # Create refresh token
        refresh_token = token_manager.create_refresh_token(sample_user_data)

        # Refresh access token
        new_access_token = await token_manager.refresh_access_token(refresh_token)

        assert new_access_token is not None
        assert isinstance(new_access_token, str)

        # Verify new token
        payload = token_manager.verify_token(new_access_token)
        assert payload["sub"] == sample_user_data["id"]
        assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_token_revocation(self, token_manager, sample_user_data):
        """Test token revocation functionality."""
        # Create token
        token = token_manager.create_access_token(sample_user_data)
        payload = token_manager.verify_token(token)
        jti = payload["jti"]

        # Revoke token
        await token_manager.revoke_token(jti, "test_revocation")

        # Test passes if no exception is raised
        assert True

    @pytest.mark.asyncio
    async def test_user_sessions_management(self, token_manager, sample_user_data):
        """Test user sessions management."""
        user_id = sample_user_data["id"]

        # Get user sessions
        sessions = await token_manager.get_user_sessions(user_id)

        # Should return list (empty or with sessions)
        assert isinstance(sessions, list)

    @pytest.mark.asyncio
    async def test_enhanced_authentication_with_device_tracking(
        self, user_authenticator
    ):
        """Test enhanced authentication with device and IP tracking."""
        device_info = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "platform": "Windows",
            "timezone": "UTC",
        }
        ip_address = "192.168.1.100"

        # Mock database response
        with patch(
            "src.infrastructure.persistence.database.production_config.initialize_database",
            autospec=True,
        ) as mock_db:
            # Setup mock
            mock_session = AsyncMock(spec="AsyncSession")
            mock_result = MagicMock(spec="Result")
            mock_result.first.return_value = (
                "123",
                "test@example.com",
                "$argon2id$v=19$m=65536,t=3,p=4$hash",
                "parent",
                True,
            )
            mock_session.execute = AsyncMock(
                return_value=mock_result, spec="AsyncSession.execute"
            )
            mock_db_manager = AsyncMock(spec="DBManager")
            mock_db_manager.get_session.return_value.__aenter__.return_value = (
                mock_session
            )
            mock_db.return_value = mock_db_manager
            # Mock password verification
            with patch.object(
                user_authenticator.password_manager,
                "verify_password",
                return_value=True,
                autospec=True,
            ):
                user_data = await user_authenticator.authenticate_user(
                    "test@example.com", "password123", device_info, ip_address
                )
                assert user_data is not None
                assert user_data["email"] == "test@example.com"
                assert user_data["device_info"] == device_info
                assert user_data["ip_address"] == ip_address

    @pytest.mark.asyncio
    async def test_enhanced_token_creation_with_security_context(
        self, user_authenticator
    ):
        """Test enhanced token creation with security context."""
        user_data = {
            "id": "123",
            "email": "test@example.com",
            "role": "parent",
            "user_type": "parent",
            "device_info": {"user_agent": "test-agent"},
            "ip_address": "192.168.1.100",
            "permissions": ["child:read"],
        }

        # Create tokens with enhanced security features
        tokens = await user_authenticator.create_user_tokens(user_data)

        assert tokens is not None
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "bearer"

    def test_permission_validation(self):
        """Test permission validation system."""
        auth_manager = AuthorizationManager()

        # Test admin permissions
        assert auth_manager.check_permission("admin", "any:permission")

        # Test parent permissions
        assert auth_manager.check_permission("parent", "child:read")
        assert auth_manager.check_permission("parent", "conversation:create")
        assert not auth_manager.check_permission("parent", "admin:delete")

        # Test child permissions
        assert auth_manager.check_permission("child", "conversation:create")
        assert not auth_manager.check_permission("child", "child:create")

    def test_authorization_error_handling(self):
        """Test authorization error handling."""
        auth_manager = AuthorizationManager()

        user = {"id": "123", "role": "child", "user_type": "child"}

        # Should raise AuthorizationError for insufficient permissions
        with pytest.raises(Exception):  # AuthorizationError
            auth_manager.require_permission(user, "admin:delete")

    def test_global_instances_initialization(self):
        """Test global instances are properly initialized."""
        token_manager = get_token_manager()
        user_authenticator = get_user_authenticator()
        auth_manager = get_authorization_manager()

        assert token_manager is not None
        assert user_authenticator is not None
        assert auth_manager is not None

        # Test singleton pattern
        assert get_token_manager() is token_manager
        assert get_user_authenticator() is user_authenticator
        assert get_authorization_manager() is auth_manager

    @pytest.mark.asyncio
    async def test_advanced_jwt_features_integration(self):
        """Test integration with advanced JWT features."""
        advanced_jwt = AdvancedJWTManager()

        # Test token creation with advanced features
        token = await advanced_jwt.create_token(
            user_id="123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS,
            permissions=["child:read"],
            ip_address="192.168.1.100",
        )

        assert token is not None
        assert isinstance(token, str)

        # Test token verification
        claims = await advanced_jwt.verify_token(token)

        assert claims.sub == "123"
        assert claims.email == "test@example.com"
        assert claims.role == "parent"
        assert claims.type == TokenType.ACCESS

    @pytest.mark.asyncio
    async def test_error_handling_for_invalid_tokens(self, token_manager):
        """Test error handling for invalid tokens."""
        # Test invalid token
        with pytest.raises(AuthenticationError):
            token_manager.verify_token("invalid.token.here")

        # Test expired token (mock)
        with patch("jwt.decode", side_effect=Exception("Token expired")):
            with pytest.raises(AuthenticationError):
                token_manager.verify_token("expired.token.here")

    def test_backward_compatibility(self, token_manager, sample_user_data):
        """Test backward compatibility with existing code."""
        # Old style token creation should still work
        token = token_manager.create_access_token(sample_user_data)
        assert token is not None

        # Old style verification should still work
        payload = token_manager.verify_token(token)
        assert payload["sub"] == sample_user_data["id"]

        # Permission validation should still work
        has_permission = token_manager.validate_token_permissions(token, "child:read")
        assert isinstance(has_permission, bool)


class TestJWTSecurityFeatures:
    """Test advanced JWT security features."""

    @pytest.mark.asyncio
    async def test_device_fingerprinting(self):
        """Test device fingerprinting functionality."""
        advanced_jwt = AdvancedJWTManager()

        device_info = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "platform": "Windows",
            "screen_resolution": "1920x1080",
            "timezone": "America/New_York",
        }

        # Create token with device fingerprint
        token = await advanced_jwt.create_token(
            user_id="123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS,
            device_info=device_info,
        )

        # Verify with same device info
        claims = await advanced_jwt.verify_token(
            token, verify_device=True, current_device_info=device_info
        )

        assert claims.device_id is not None

    @pytest.mark.asyncio
    async def test_ip_address_tracking(self):
        """Test IP address tracking functionality."""
        advanced_jwt = AdvancedJWTManager()

        ip_address = "192.168.1.100"

        # Create token with IP tracking
        token = await advanced_jwt.create_token(
            user_id="123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS,
            ip_address=ip_address,
        )

        # Verify with same IP
        claims = await advanced_jwt.verify_token(token, current_ip=ip_address)

        assert claims.ip_address == ip_address

    @pytest.mark.asyncio
    async def test_token_type_validation(self):
        """Test token type validation."""
        advanced_jwt = AdvancedJWTManager()

        # Create access token
        access_token = await advanced_jwt.create_token(
            user_id="123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS,
        )

        # Verify as access token
        claims = await advanced_jwt.verify_token(
            access_token, expected_type=TokenType.ACCESS
        )

        assert claims.type == TokenType.ACCESS

        # Should fail when verifying as refresh token
        with pytest.raises(Exception):
            await advanced_jwt.verify_token(
                access_token, expected_type=TokenType.REFRESH
            )


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
