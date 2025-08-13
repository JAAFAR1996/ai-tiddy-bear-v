"""
🧸 AI TEDDY BEAR V5 - AUTHENTICATION & AUTHORIZATION
===================================================
Production-grade authentication with COPPA compliance.
"""

import jwt
import time
import os
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .auth import TokenManager  # لتفادي الدورات الاستيرادية
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from passlib.hash import argon2
import redis.asyncio as redis

from ..config.config_provider import get_config
from ..logging.production_logger import get_logger, security_logger
from ..monitoring.audit import coppa_audit
from .jwt_advanced import AdvancedJWTManager, TokenType, JWTClaims


# Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# JWT token handler
security = HTTPBearer()

# Logger
auth_logger = get_logger(__name__, "authentication")


class AuthenticationError(Exception):
    """Authentication failed."""

    pass


class AuthorizationError(Exception):
    """Authorization failed."""

    pass


class TokenManager:
    """Unified JWT token management with advanced security features."""

    def __init__(self, config=None, advanced_jwt=None):
        """Initialize with explicit config and AdvancedJWTManager injection (production-grade)"""
        if config is None:
            raise ValueError("TokenManager requires config parameter - no global access in production")
        if advanced_jwt is None:
            raise ValueError("TokenManager requires advanced_jwt parameter - no global access in production")
        
        self.config = config
        self.advanced_jwt = advanced_jwt  # Use injected instance
        self._pending_redis_client = None

        # Initialize Redis for advanced features if available
        try:
            redis_url = getattr(self.config, "REDIS_URL", None) or os.getenv(
                "REDIS_URL"
            )
            if redis_url:
                # Set up Redis client for token tracking
                redis_client = redis.from_url(redis_url)
                # Store redis client for later initialization when event loop is available
                self._pending_redis_client = redis_client
                # Will be set during startup in initialize_auth_services()
        except Exception as e:
            auth_logger.warning(
                f"Redis initialization failed, advanced features disabled: {e}"
            )

    async def initialize_async_services(self):
        """Initialize async services when event loop is available."""
        if self._pending_redis_client:
            try:
                await self.advanced_jwt.set_redis_client(self._pending_redis_client)
                auth_logger.info("Redis client initialized for JWT manager")
            except Exception as e:
                auth_logger.warning(f"Failed to initialize Redis client: {e}")

    async def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token using advanced JWT manager (async)."""
        try:
            return await self.advanced_jwt.create_token(
                user_id=str(data.get("sub") or data.get("id")),
                email=data.get("email", ""),
                role=data.get("role", "parent"),
                user_type=data.get("user_type", "parent"),
                token_type=TokenType.ACCESS,
                permissions=data.get("permissions", []),
            )
        except Exception as e:
            auth_logger.error(f"Failed to create access token - Error: {str(e)}")
            raise AuthenticationError("Token creation failed")

    async def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Create JWT refresh token using advanced JWT manager (async)."""
        try:
            return await self.advanced_jwt.create_token(
                user_id=str(data.get("sub") or data.get("id")),
                email=data.get("email", ""),
                role=data.get("role", "parent"),
                user_type=data.get("user_type", "parent"),
                token_type=TokenType.REFRESH,
                permissions=data.get("permissions", []),
            )
        except Exception as e:
            auth_logger.error(f"Failed to create refresh token - Error: {str(e)}")
            raise AuthenticationError("Token creation failed")

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token using advanced JWT manager (async)."""
        try:
            claims = await self.advanced_jwt.verify_token(token)
            # Convert JWTClaims to dictionary for backward compatibility
            return {
                "sub": claims.sub,
                "email": claims.email,
                "role": claims.role,
                "user_type": claims.user_type,
                "type": claims.type.value,
                "iat": claims.iat,
                "exp": claims.exp,
                "jti": claims.jti,
                "permissions": claims.permissions,
                "metadata": claims.metadata,
            }
        except jwt.ExpiredSignatureError:
            auth_logger.warning(f"Token expired - TokenJTI: {token[-10:]}")
            raise AuthenticationError("Token expired")
        except jwt.InvalidTokenError as e:
            auth_logger.warning(
                f"Invalid token - Error: {str(e)}, TokenJTI: {token[-10:]}"
            )
            raise AuthenticationError("Invalid token")
        except Exception as e:
            auth_logger.error(f"Token verification failed - Error: {str(e)}")
            raise AuthenticationError("Token verification failed")

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Refresh access token using valid refresh token (async version)."""
        try:
            # Verify refresh token
            claims = await self.advanced_jwt.verify_token(
                refresh_token, expected_type=TokenType.REFRESH
            )

            # Create new access token
            new_access_token = await self.advanced_jwt.create_token(
                user_id=claims.sub,
                email=claims.email,
                role=claims.role,
                user_type=claims.user_type,
                token_type=TokenType.ACCESS,
                permissions=claims.permissions,
                metadata=claims.metadata,
            )

            return new_access_token

        except Exception as e:
            auth_logger.error(f"Token refresh failed - Error: {str(e)}")
            raise AuthenticationError("Token refresh failed")

    async def validate_token_permissions(self, token: str, required_permission: str) -> bool:
        """Validate if token has required permission (async)."""
        try:
            payload = await self.verify_token(token)
            permissions = payload.get("permissions", [])
            user_role = payload.get("role", "")

            # Admin has all permissions
            if user_role == "admin" or "admin" in permissions:
                return True

            # Check specific permission
            return required_permission in permissions

        except AuthenticationError:
            return False
        except Exception as e:
            auth_logger.error(f"Permission validation failed - Error: {str(e)}")
            return False

    async def revoke_token(self, jti: str, reason: str = "manual_revocation"):
        """Revoke a token by adding to blacklist."""
        await self.advanced_jwt.revoke_token(jti, reason)

    async def revoke_all_user_tokens(
        self, user_id: str, reason: str = "security_reset"
    ):
        """Revoke all tokens for a user."""
        await self.advanced_jwt.revoke_all_user_tokens(user_id, reason)

    async def get_user_sessions(self, user_id: str):
        """Get all active sessions for a user."""
        return await self.advanced_jwt.get_user_sessions(user_id)


class PasswordManager:
    """Secure password management."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using Argon2."""
        try:
            return pwd_context.hash(password)
        except Exception as e:
            auth_logger.error(f"Password hashing failed - Error: {str(e)}")
            raise AuthenticationError("Password processing failed")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            auth_logger.error(f"Password verification failed - Error: {str(e)}")
            return False


class UserAuthenticator:
    """User authentication service."""

    def __init__(self, config=None, token_manager: "TokenManager" = None):
        """Initialize with explicit config and token_manager injection (production-grade)"""
        if config is None:
            raise ValueError("UserAuthenticator requires config parameter - no global access in production")
        if token_manager is None:
            raise ValueError("UserAuthenticator requires token_manager parameter - no global access in production")

        self.config = config
        self.token_manager = token_manager
        self.password_manager = PasswordManager()

    async def authenticate_user(
        self,
        email: str,
        password: str,
        device_info: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Authenticate user with email and password (production, async with enhanced security)."""
        from sqlalchemy import text
        from sqlalchemy.exc import SQLAlchemyError
        from src.infrastructure.persistence.database.production_config import (
            initialize_database,
        )

        # Input validation
        if not email or not password:
            raise AuthenticationError("Email and password are required")

        # Validate email format
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise AuthenticationError("Invalid email format")

        # Sanitize email
        email = email.lower().strip()

        # Validate IP address if provided
        if ip_address:
            import ipaddress

            try:
                ipaddress.ip_address(ip_address)
            except ValueError:
                auth_logger.warning(f"Invalid IP address format: {ip_address}")
                ip_address = None

        # Log authentication attempt with sanitized data
        masked_email = (
            f"{email[:3]}***@{email.split('@')[1] if '@' in email else 'unknown'}"
        )
        auth_logger.info(
            f"Authentication attempt - Email: {masked_email}, IP: {ip_address}"
        )
        try:
            db_manager = await initialize_database()
            async with db_manager.get_session() as session:
                result = await session.execute(
                    text(
                        "SELECT id, email, password_hash, role, is_active FROM users WHERE email = :email AND is_active = true"
                    ),
                    {"email": email},
                )
                user_row = result.first()
                if not user_row:
                    auth_logger.warning(
                        f"Authentication failed: user not found - Email: {masked_email}, IP: {ip_address}"
                    )
                    raise AuthenticationError("Invalid email or password")
                user_id, user_email, password_hash, role, is_active = user_row
                if not self.password_manager.verify_password(password, password_hash):
                    auth_logger.warning(
                        f"Authentication failed: wrong password - Email: {masked_email}, IP: {ip_address}"
                    )
                    raise AuthenticationError("Invalid email or password")

                # Sanitize device info
                if device_info:
                    device_info = self._sanitize_device_info(device_info)

                user_data = {
                    "id": user_id,
                    "email": user_email,
                    "role": role,
                    "user_type": role,
                    "device_info": device_info,
                    "ip_address": ip_address,
                }
        except SQLAlchemyError as e:
            auth_logger.error(
                f"Database error during authentication - Error: {str(e)[:100]}"
            )
            raise AuthenticationError("Authentication service unavailable")

    def _sanitize_device_info(self, device_info: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize device information to prevent injection attacks."""
        import re

        sanitized = {}
        allowed_keys = ["user_agent", "platform", "browser", "version", "device_type"]

        for key, value in device_info.items():
            if key in allowed_keys and isinstance(value, str):
                # Remove potentially dangerous characters
                sanitized_value = re.sub(r'[<>"\';\\]', "", str(value)[:200])
                sanitized[key] = sanitized_value

        return sanitized
        # Log successful authentication
        auth_logger.info(
            f"Authentication successful - UserID: {user_data['id']}, "
            f"Email: {email}, Role: {user_data['role']}, IP: {ip_address}"
        )
        # Audit log with enhanced security tracking
        coppa_audit.log_event(
            {
                "event_type": "authentication_success",
                "severity": "info",
                "description": "User authentication successful",
                "user_id": user_data["id"],
                "user_type": user_data["user_type"],
                "metadata": {
                    "email": email,
                    "role": user_data["role"],
                    "ip_address": ip_address,
                    "device_fingerprint": (
                        device_info.get("user_agent", "") if device_info else None
                    ),
                },
            }
        )
        return user_data

    async def create_user_tokens(self, user_data: Dict[str, Any]) -> Dict[str, str]:
        """Create access and refresh tokens for user with enhanced security."""

        # Extract device and IP info for enhanced security
        device_info = user_data.get("device_info")
        ip_address = user_data.get("ip_address")

        # Create access token with advanced features
        access_token = await self.token_manager.advanced_jwt.create_token(
            user_id=str(user_data["id"]),
            email=user_data["email"],
            role=user_data["role"],
            user_type=user_data.get("user_type", "parent"),
            token_type=TokenType.ACCESS,
            device_info=device_info,
            ip_address=ip_address,
            permissions=user_data.get("permissions", []),
        )

        # Create refresh token with advanced features
        refresh_token = await self.token_manager.advanced_jwt.create_token(
            user_id=str(user_data["id"]),
            email=user_data["email"],
            role=user_data["role"],
            user_type=user_data.get("user_type", "parent"),
            token_type=TokenType.REFRESH,
            device_info=device_info,
            ip_address=ip_address,
            permissions=user_data.get("permissions", []),
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }


class AuthorizationManager:
    """Role-based authorization."""

    ROLE_PERMISSIONS = {
        "admin": ["*"],  # All permissions
        "parent": [
            "child:read",
            "child:create",
            "child:update",
            "conversation:read",
            "conversation:create",
            "profile:read",
            "profile:update",
        ],
        "child": ["conversation:create", "conversation:read_own"],
    }

    def check_permission(self, user_role: str, required_permission: str) -> bool:
        """Check if user role has required permission."""

        user_permissions = self.ROLE_PERMISSIONS.get(user_role, [])

        # Admin has all permissions
        if "*" in user_permissions:
            return True

        # Check specific permission
        return required_permission in user_permissions

    def require_permission(self, user: Dict[str, Any], permission: str):
        """Require specific permission or raise authorization error."""

        user_role = user.get("role", "")

        if not self.check_permission(user_role, permission):
            # Log authorization failure
            security_logger.warning(
                "Authorization failed",
                user_id=user.get("id"),
                user_role=user_role,
                required_permission=permission,
            )

            # Audit log
            coppa_audit.log_event(
                {
                    "event_type": "authorization_failure",
                    "severity": "warning",
                    "description": f"Authorization failed for permission: {permission}",
                    "user_id": user.get("id"),
                    "user_type": user.get("user_type"),
                    "metadata": {
                        "user_role": user_role,
                        "required_permission": permission,
                    },
                }
            )

            raise AuthorizationError(f"Permission denied: {permission}")


# Global instances - lazy initialization to prevent config issues during testing
_token_manager = None
_user_authenticator = None
_authorization_manager = None


# Removed lazy initialization - use pure DI pattern instead
# Token manager should be created in lifespan and stored in app.state
# or injected via Depends(get_token_manager_from_state)


def get_user_authenticator():
    """Get user authenticator instance - DEPRECATED: Use dependency injection instead."""
    raise RuntimeError("get_user_authenticator() is deprecated - use UserAuthenticator with proper dependency injection")


def get_authorization_manager():
    """Get authorization manager instance with lazy initialization."""
    global _authorization_manager
    if _authorization_manager is None:
        _authorization_manager = AuthorizationManager()
    return _authorization_manager


# For backward compatibility - functions that use the global instances need to be updated


# FastAPI dependencies
async def get_current_user(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get current authenticated user from JWT token (async)."""

    try:
        # Verify token (now async)
        payload = await get_token_manager().verify_token(credentials.credentials)

        # Extract user info
        user_data = {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "user_type": payload.get("user_type", "parent"),
        }

        # Add user context to request state for logging
        if hasattr(request, "state"):
            request.state.user_id = user_data["id"]
            request.state.user_type = user_data["user_type"]

        return user_data

    except AuthenticationError as e:
        # Log authentication failure
        security_logger.warning(
            "Authentication failed",
            error=str(e),
            token_preview=(
                credentials.credentials[-10:] if credentials.credentials else None
            ),
        )

        # Audit log
        coppa_audit.log_event(
            {
                "event_type": "authentication_failure",
                "severity": "warning",
                "description": f"Authentication failed: {str(e)}",
                "metadata": {"error": str(e)},
            }
        )

        raise HTTPException(
            status_code=401,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current user and require admin role."""

    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return current_user


async def get_current_parent_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current user and require parent role."""

    if current_user.get("role") not in ["parent", "admin"]:
        raise HTTPException(status_code=403, detail="Parent access required")

    return current_user


def require_permission(permission: str):
    """Decorator factory for requiring specific permissions."""

    def permission_dependency(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        get_authorization_manager().require_permission(current_user, permission)
        return current_user

    return permission_dependency
