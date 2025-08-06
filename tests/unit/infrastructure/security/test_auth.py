"""
Tests for authentication and authorization system.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from src.infrastructure.security.auth import (
    TokenManager,
    PasswordManager,
    UserAuthenticator,
    AuthorizationManager,
    AuthenticationError,
    AuthorizationError
)


class TestTokenManager:
    """Test JWT token management."""

    @pytest.fixture
    def token_manager(self):
        return TokenManager()

    def test_create_access_token(self, token_manager):
        """Test access token creation."""
        data = {
            "sub": "user123",
            "email": "test@example.com",
            "role": "parent"
        }
        
        token = token_manager.create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_token(self, token_manager):
        """Test valid token verification."""
        data = {
            "sub": "user123",
            "email": "test@example.com",
            "role": "parent"
        }
        
        token = token_manager.create_access_token(data)
        payload = token_manager.verify_token(token)
        
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "parent"

    def test_verify_invalid_token(self, token_manager):
        """Test invalid token verification."""
        with pytest.raises(AuthenticationError, match="Invalid token"):
            token_manager.verify_token("invalid.token.here")


class TestPasswordManager:
    """Test password hashing and verification."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "secure_password123"
        hashed = PasswordManager.hash_password(password)
        
        assert isinstance(hashed, str)
        assert hashed != password
        assert len(hashed) > 50

    def test_verify_correct_password(self):
        """Test correct password verification."""
        password = "secure_password123"
        hashed = PasswordManager.hash_password(password)
        
        assert PasswordManager.verify_password(password, hashed)

    def test_verify_incorrect_password(self):
        """Test incorrect password verification."""
        password = "secure_password123"
        wrong_password = "wrong_password"
        hashed = PasswordManager.hash_password(password)
        
        assert not PasswordManager.verify_password(wrong_password, hashed)


class TestAuthorizationManager:
    """Test role-based authorization."""

    @pytest.fixture
    def auth_manager(self):
        return AuthorizationManager()

    def test_admin_has_all_permissions(self, auth_manager):
        """Test that admin role has all permissions."""
        assert auth_manager.check_permission("admin", "any_permission")
        assert auth_manager.check_permission("admin", "child:delete")

    def test_parent_permissions(self, auth_manager):
        """Test parent role permissions."""
        assert auth_manager.check_permission("parent", "child:read")
        assert auth_manager.check_permission("parent", "child:create")
        assert not auth_manager.check_permission("parent", "system:admin")

    def test_child_permissions(self, auth_manager):
        """Test child role permissions."""
        assert auth_manager.check_permission("child", "conversation:create")
        assert not auth_manager.check_permission("child", "child:create")

    def test_require_permission_failure(self, auth_manager):
        """Test failed permission requirement."""
        user = {"id": "user123", "role": "child"}
        
        with pytest.raises(AuthorizationError, match="Permission denied"):
            auth_manager.require_permission(user, "child:create")