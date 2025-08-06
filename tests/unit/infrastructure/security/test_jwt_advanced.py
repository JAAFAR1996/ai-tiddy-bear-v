"""
Unit tests for AdvancedJWTManager
Tests enterprise JWT implementation with RSA encryption and advanced security features
"""

import pytest
import jwt
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4

from src.infrastructure.security.jwt_advanced import (
    AdvancedJWTManager,
    JWTClaims,
    JWTKeyPair,
    TokenType,
    TokenStatus
)


class TestJWTClaims:
    """Test JWTClaims dataclass functionality."""

    def test_jwt_claims_creation(self):
        """Test JWTClaims creation with required fields."""
        now = int(time.time())
        claims = JWTClaims(
            sub="user123",
            iat=now,
            exp=now + 3600,
            nbf=now,
            jti="jwt123",
            type=TokenType.ACCESS,
            email="test@example.com",
            role="parent",
            user_type="parent"
        )
        
        assert claims.sub == "user123"
        assert claims.type == TokenType.ACCESS
        assert claims.email == "test@example.com"
        assert claims.mfa_verified is False
        assert claims.permissions == []

    def test_jwt_claims_to_dict(self):
        """Test JWTClaims to dictionary conversion."""
        now = int(time.time())
        claims = JWTClaims(
            sub="user123",
            iat=now,
            exp=now + 3600,
            nbf=now,
            jti="jwt123",
            type=TokenType.ACCESS,
            email="test@example.com",
            role="parent",
            user_type="parent",
            permissions=["read", "write"]
        )
        
        claims_dict = claims.to_dict()
        
        assert claims_dict["sub"] == "user123"
        assert claims_dict["type"] == "access"
        assert claims_dict["permissions"] == ["read", "write"]
        assert claims_dict["mfa_verified"] is False

    def test_jwt_claims_from_dict(self):
        """Test JWTClaims creation from dictionary."""
        now = int(time.time())
        data = {
            "sub": "user123",
            "iat": now,
            "exp": now + 3600,
            "nbf": now,
            "jti": "jwt123",
            "type": "access",
            "email": "test@example.com",
            "role": "parent",
            "user_type": "parent",
            "permissions": ["read", "write"],
            "mfa_verified": True
        }
        
        claims = JWTClaims.from_dict(data)
        
        assert claims.sub == "user123"
        assert claims.type == TokenType.ACCESS
        assert claims.permissions == ["read", "write"]
        assert claims.mfa_verified is True


class TestJWTKeyPair:
    """Test JWTKeyPair functionality."""

    def test_key_pair_creation(self):
        """Test JWTKeyPair creation."""
        now = datetime.now(timezone.utc)
        key_pair = JWTKeyPair(
            key_id="test_key",
            private_key="private_key_content",
            public_key="public_key_content",
            created_at=now,
            expires_at=now + timedelta(days=30)
        )
        
        assert key_pair.key_id == "test_key"
        assert key_pair.algorithm == "RS256"
        assert key_pair.is_valid() is True

    def test_key_pair_expiration(self):
        """Test key pair expiration check."""
        now = datetime.now(timezone.utc)
        expired_key_pair = JWTKeyPair(
            key_id="expired_key",
            private_key="private_key_content",
            public_key="public_key_content",
            created_at=now - timedelta(days=60),
            expires_at=now - timedelta(days=30)
        )
        
        assert expired_key_pair.is_valid() is False


class TestAdvancedJWTManager:
    """Test AdvancedJWTManager functionality."""

    @pytest.fixture
    def jwt_manager(self):
        """Create AdvancedJWTManager instance for testing."""
        with patch.dict('os.environ', {
            'JWT_SECRET_KEY': 'test-secret-key',
            'JWT_ALGORITHM': 'HS256',  # Use HS256 for testing
            'JWT_ACCESS_TOKEN_TTL': '900',
            'JWT_REFRESH_TOKEN_TTL': '604800'
        }):
            manager = AdvancedJWTManager()
            manager.algorithm = 'HS256'  # Force HS256 for testing
            return manager

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        mock_redis = AsyncMock(spec=True)
        mock_redis.setex = AsyncMock(spec=True)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(spec=True)
        mock_redis.scan = AsyncMock(return_value=(0, []))
        mock_redis.ttl = AsyncMock(return_value=3600)
        return mock_redis

    def test_jwt_manager_initialization(self, jwt_manager):
        """Test JWT manager initialization."""
        assert jwt_manager.access_token_ttl == 900
        assert jwt_manager.refresh_token_ttl == 604800
        assert jwt_manager.algorithm in ['RS256', 'HS256']
        assert jwt_manager.max_active_sessions == 5

    def test_generate_key_id(self, jwt_manager):
        """Test key ID generation."""
        key_id = jwt_manager._generate_key_id()
        assert key_id.startswith("kid_")
        assert len(key_id) > 10

    def test_generate_jti(self, jwt_manager):
        """Test JWT ID generation."""
        jti = jwt_manager._generate_jti(TokenType.ACCESS)
        assert jti.startswith("access_")
        assert len(jti) > 10

    def test_generate_device_fingerprint(self, jwt_manager):
        """Test device fingerprint generation."""
        device_info = {
            "user_agent": "Mozilla/5.0",
            "platform": "Windows",
            "screen_resolution": "1920x1080",
            "timezone": "UTC"
        }
        
        fingerprint = jwt_manager._generate_device_fingerprint(device_info)
        assert len(fingerprint) == 16
        assert isinstance(fingerprint, str)

    @pytest.mark.asyncio
    async def test_create_access_token(self, jwt_manager):
        """Test access token creation."""
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS
        )
        
        assert isinstance(token, str)
        assert len(token) > 50

    @pytest.mark.asyncio
    async def test_create_refresh_token(self, jwt_manager):
        """Test refresh token creation."""
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.REFRESH
        )
        
        assert isinstance(token, str)
        assert len(token) > 50

    @pytest.mark.asyncio
    async def test_create_token_with_device_info(self, jwt_manager):
        """Test token creation with device information."""
        device_info = {
            "user_agent": "Mozilla/5.0",
            "platform": "Windows"
        }
        
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS,
            device_info=device_info,
            ip_address="192.168.1.1"
        )
        
        assert isinstance(token, str)

    @pytest.mark.asyncio
    async def test_verify_valid_token(self, jwt_manager):
        """Test verification of valid token."""
        # Create token
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS
        )
        
        # Verify token
        claims = await jwt_manager.verify_token(token, TokenType.ACCESS)
        
        assert claims.sub == "user123"
        assert claims.email == "test@example.com"
        assert claims.type == TokenType.ACCESS

    @pytest.mark.asyncio
    async def test_verify_token_wrong_type(self, jwt_manager):
        """Test verification with wrong token type."""
        # Create access token
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS
        )
        
        # Try to verify as refresh token
        with pytest.raises(jwt.InvalidTokenError):
            await jwt_manager.verify_token(token, TokenType.REFRESH)

    @pytest.mark.asyncio
    async def test_verify_expired_token(self, jwt_manager):
        """Test verification of expired token."""
        # Create token with very short TTL
        with patch.dict('os.environ', {'JWT_ACCESS_TOKEN_TTL': '1'}):
            token = await jwt_manager.create_token(
                user_id="user123",
                email="test@example.com",
                role="parent",
                user_type="parent",
                token_type=TokenType.ACCESS
            )
        
        # Wait for expiration
        import time
        time.sleep(2)
        
        # Verify expired token
        with pytest.raises(jwt.ExpiredSignatureError):
            await jwt_manager.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_token_with_device_verification(self, jwt_manager):
        """Test token verification with device fingerprint."""
        device_info = {
            "user_agent": "Mozilla/5.0",
            "platform": "Windows"
        }
        
        # Create token with device info
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS,
            device_info=device_info
        )
        
        # Verify with same device info
        claims = await jwt_manager.verify_token(
            token,
            verify_device=True,
            current_device_info=device_info
        )
        
        assert claims.sub == "user123"

    @pytest.mark.asyncio
    async def test_verify_token_device_mismatch(self, jwt_manager):
        """Test token verification with device mismatch."""
        original_device = {"user_agent": "Mozilla/5.0", "platform": "Windows"}
        different_device = {"user_agent": "Chrome/90.0", "platform": "Mac"}
        
        # Create token with original device
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS,
            device_info=original_device
        )
        
        # Try to verify with different device
        with pytest.raises(jwt.InvalidTokenError, match="Device verification failed"):
            await jwt_manager.verify_token(
                token,
                verify_device=True,
                current_device_info=different_device
            )

    @pytest.mark.asyncio
    async def test_revoke_token(self, jwt_manager, mock_redis):
        """Test token revocation."""
        jwt_manager._redis_client = mock_redis
        
        await jwt_manager.revoke_token("test_jti", "manual_revocation")
        
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert "jwt:blacklist:test_jti" in call_args[0]

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, jwt_manager, mock_redis):
        """Test revoking all tokens for a user."""
        jwt_manager._redis_client = mock_redis
        
        # Mock scan to return session keys
        mock_redis.scan.return_value = (0, ["jwt:session:user123:session1"])
        mock_redis.get.return_value = json.dumps({"jti": "test_jti"})
        
        await jwt_manager.revoke_all_user_tokens("user123", "security_reset")
        
        mock_redis.scan.assert_called()
        mock_redis.get.assert_called()

    @pytest.mark.asyncio
    async def test_refresh_token_flow(self, jwt_manager):
        """Test refresh token flow."""
        # Create refresh token
        refresh_token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.REFRESH
        )
        
        # Refresh tokens
        new_access, new_refresh = await jwt_manager.refresh_token(refresh_token)
        
        assert isinstance(new_access, str)
        assert isinstance(new_refresh, str)
        assert new_access != new_refresh

    @pytest.mark.asyncio
    async def test_is_token_blacklisted(self, jwt_manager, mock_redis):
        """Test token blacklist check."""
        jwt_manager._redis_client = mock_redis
        
        # Test non-blacklisted token
        mock_redis.get.return_value = None
        is_blacklisted = await jwt_manager._is_token_blacklisted("test_jti")
        assert is_blacklisted is False
        
        # Test blacklisted token
        mock_redis.get.return_value = json.dumps({"revoked_at": "2023-01-01"})
        is_blacklisted = await jwt_manager._is_token_blacklisted("test_jti")
        assert is_blacklisted is True

    @pytest.mark.asyncio
    async def test_store_token_metadata(self, jwt_manager, mock_redis):
        """Test storing token metadata."""
        jwt_manager._redis_client = mock_redis
        
        now = int(time.time())
        claims = JWTClaims(
            sub="user123",
            iat=now,
            exp=now + 3600,
            nbf=now,
            jti="jwt123",
            type=TokenType.REFRESH,
            email="test@example.com",
            role="parent",
            user_type="parent",
            session_id="session123"
        )
        
        await jwt_manager._store_token_metadata(claims, TokenType.REFRESH)
        
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_enforce_max_sessions(self, jwt_manager, mock_redis):
        """Test maximum sessions enforcement."""
        jwt_manager._redis_client = mock_redis
        jwt_manager.max_active_sessions = 2
        
        # Mock multiple sessions
        sessions = [
            "jwt:session:user123:session1",
            "jwt:session:user123:session2",
            "jwt:session:user123:session3"
        ]
        mock_redis.scan.return_value = (0, sessions)
        
        # Mock session data
        session_data = [
            {"jti": "jti1", "last_activity": "2023-01-01T10:00:00"},
            {"jti": "jti2", "last_activity": "2023-01-01T11:00:00"},
            {"jti": "jti3", "last_activity": "2023-01-01T12:00:00"}
        ]
        mock_redis.get.side_effect = [json.dumps(data) for data in session_data]
        
        await jwt_manager._enforce_max_sessions("user123")
        
        # Should revoke oldest session
        assert mock_redis.setex.call_count >= 1  # Blacklist call

    @pytest.mark.asyncio
    async def test_update_session_activity(self, jwt_manager, mock_redis):
        """Test session activity update."""
        jwt_manager._redis_client = mock_redis
        
        mock_redis.scan.return_value = (0, ["jwt:session:user123:session123"])
        mock_redis.get.return_value = json.dumps({
            "jti": "test_jti",
            "last_activity": "2023-01-01T10:00:00"
        })
        
        await jwt_manager._update_session_activity("session123")
        
        mock_redis.scan.assert_called()
        mock_redis.get.assert_called()
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_get_user_sessions(self, jwt_manager, mock_redis):
        """Test getting user sessions."""
        jwt_manager._redis_client = mock_redis
        
        mock_redis.scan.return_value = (0, ["jwt:session:user123:session1"])
        mock_redis.get.return_value = json.dumps({
            "jti": "test_jti",
            "created_at": "2023-01-01T10:00:00"
        })
        
        sessions = await jwt_manager.get_user_sessions("user123")
        
        assert len(sessions) == 1
        assert sessions[0]["jti"] == "test_jti"

    def test_get_public_keys(self, jwt_manager):
        """Test getting public keys."""
        # Add mock key pair
        now = datetime.now(timezone.utc)
        key_pair = JWTKeyPair(
            key_id="test_key",
            private_key="private_key",
            public_key="public_key",
            created_at=now,
            expires_at=now + timedelta(days=30)
        )
        jwt_manager._key_cache["test_key"] = key_pair
        
        public_keys = jwt_manager.get_public_keys()
        
        assert "test_key" in public_keys
        assert public_keys["test_key"] == "public_key"

    @pytest.mark.asyncio
    async def test_set_redis_client(self, jwt_manager, mock_redis):
        """Test setting Redis client."""
        await jwt_manager.set_redis_client(mock_redis)
        assert jwt_manager._redis_client == mock_redis

    def test_set_logger(self, jwt_manager):
        """Test setting logger."""
        mock_logger = Mock(spec=True)
        jwt_manager.set_logger(mock_logger)
        assert jwt_manager.logger == mock_logger

    @pytest.mark.asyncio
    async def test_mfa_token_creation(self, jwt_manager):
        """Test MFA token creation."""
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.MFA,
            mfa_required=True
        )
        
        claims = await jwt_manager.verify_token(token, TokenType.MFA)
        assert claims.type == TokenType.MFA
        assert claims.mfa_required is True

    @pytest.mark.asyncio
    async def test_token_with_permissions(self, jwt_manager):
        """Test token creation with permissions."""
        permissions = ["read_profile", "write_messages"]
        
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS,
            permissions=permissions
        )
        
        claims = await jwt_manager.verify_token(token)
        assert claims.permissions == permissions

    @pytest.mark.asyncio
    async def test_token_with_metadata(self, jwt_manager):
        """Test token creation with metadata."""
        metadata = {"client_version": "1.0.0", "feature_flags": ["new_ui"]}
        
        token = await jwt_manager.create_token(
            user_id="user123",
            email="test@example.com",
            role="parent",
            user_type="parent",
            token_type=TokenType.ACCESS,
            metadata=metadata
        )
        
        claims = await jwt_manager.verify_token(token)
        assert claims.metadata == metadata

    def test_token_type_enum_values(self):
        """Test TokenType enum values."""
        assert TokenType.ACCESS.value == "access"
        assert TokenType.REFRESH.value == "refresh"
        assert TokenType.MFA.value == "mfa"
        assert TokenType.PASSWORD_RESET.value == "password_reset"
        assert TokenType.EMAIL_VERIFICATION.value == "email_verification"
        assert TokenType.API_KEY.value == "api_key"

    def test_token_status_enum_values(self):
        """Test TokenStatus enum values."""
        assert TokenStatus.ACTIVE.value == "active"
        assert TokenStatus.REVOKED.value == "revoked"
        assert TokenStatus.EXPIRED.value == "expired"
        assert TokenStatus.REPLACED.value == "replaced"