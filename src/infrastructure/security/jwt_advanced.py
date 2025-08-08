"""
Production JWT Implementation - Enterprise Security
=================================================
Advanced JWT implementation with:
- RS256 asymmetric encryption for production
- Key rotation and versioning
- Token blacklisting and revocation
- Device fingerprinting
- Session management
- Multi-factor authentication support
"""

import os
import jwt
import time
import uuid
import hashlib
import secrets
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import redis.asyncio as redis
import json


class TokenType(Enum):
    """JWT token types."""

    ACCESS = "access"
    REFRESH = "refresh"
    MFA = "mfa"  # Multi-factor authentication
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    API_KEY = "api_key"


class TokenStatus(Enum):
    """Token status for tracking."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    REPLACED = "replaced"


@dataclass
class JWTClaims:
    """Standard JWT claims with extended fields."""

    # Standard claims
    sub: str  # Subject (user_id)
    iat: int  # Issued at
    exp: int  # Expiration
    nbf: int  # Not before
    jti: str  # JWT ID

    # Custom claims
    type: TokenType
    email: str
    role: str
    user_type: str

    # Security claims
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None

    # MFA claims
    mfa_verified: bool = False
    mfa_required: bool = False

    # Additional metadata
    permissions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JWT encoding."""
        return {
            "sub": self.sub,
            "iat": self.iat,
            "exp": self.exp,
            "nbf": self.nbf,
            "jti": self.jti,
            "type": self.type.value,
            "email": self.email,
            "role": self.role,
            "user_type": self.user_type,
            "device_id": self.device_id,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "mfa_verified": self.mfa_verified,
            "mfa_required": self.mfa_required,
            "permissions": self.permissions,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JWTClaims":
        """Create from dictionary after JWT decoding."""
        return cls(
            sub=data["sub"],
            iat=data["iat"],
            exp=data["exp"],
            nbf=data.get("nbf", data["iat"]),
            jti=data["jti"],
            type=TokenType(data["type"]),
            email=data["email"],
            role=data["role"],
            user_type=data["user_type"],
            device_id=data.get("device_id"),
            ip_address=data.get("ip_address"),
            session_id=data.get("session_id"),
            mfa_verified=data.get("mfa_verified", False),
            mfa_required=data.get("mfa_required", False),
            permissions=data.get("permissions", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class JWTKeyPair:
    """RSA key pair for JWT signing."""

    key_id: str
    private_key: str
    public_key: str
    created_at: datetime
    expires_at: datetime
    algorithm: str = "RS256"

    def is_valid(self) -> bool:
        """Check if key pair is still valid."""
        return datetime.now(timezone.utc) < self.expires_at


class AdvancedJWTManager:
    """
    Production-grade JWT manager with enterprise security features.

    Features:
    - RSA asymmetric encryption
    - Key rotation and versioning
    - Token blacklisting and revocation
    - Device fingerprinting
    - Session management
    - MFA support
    - Rate limiting
    - Audit logging
    """

    def __init__(self):
        self.logger = None  # Will be injected
        self._redis_client: Optional[redis.Redis] = None

        # Configuration
        self.access_token_ttl = int(
            os.getenv("JWT_ACCESS_TOKEN_TTL", "900")
        )  # 15 minutes
        self.refresh_token_ttl = int(
            os.getenv("JWT_REFRESH_TOKEN_TTL", "604800")
        )  # 7 days
        self.mfa_token_ttl = int(os.getenv("JWT_MFA_TOKEN_TTL", "300"))  # 5 minutes
        self.key_rotation_interval = int(os.getenv("JWT_KEY_ROTATION_DAYS", "30"))

        # Algorithm configuration - PRODUCTION SECURITY
        env_algorithm = os.getenv("JWT_ALGORITHM", "RS256")
        env_mode = os.getenv("ENVIRONMENT", "development")

        if env_mode == "production":
            # PRODUCTION: Only allow RS256
            if env_algorithm != "RS256":
                raise Exception("SECURITY VIOLATION: Only RS256 allowed in production")
            self.algorithm = "RS256"
            self.fallback_algorithm = None  # NO FALLBACK IN PRODUCTION
        else:
            # For development environments only
            self.algorithm = env_algorithm
            self.fallback_algorithm = "HS256" if env_mode != "production" else None

        # Security settings
        self.require_device_id = (
            os.getenv("JWT_REQUIRE_DEVICE_ID", "true").lower() == "true"
        )
        self.track_ip_address = (
            os.getenv("JWT_TRACK_IP_ADDRESS", "true").lower() == "true"
        )
        self.max_active_sessions = int(os.getenv("JWT_MAX_ACTIVE_SESSIONS", "5"))

        # Key storage
        self._current_key_pair: Optional[JWTKeyPair] = None
        self._key_cache: Dict[str, JWTKeyPair] = {}

        # Initialize keys
        self._initialize_keys()

    def validate_server_side_authorization(
        self,
        claims: JWTClaims,
        required_role: str = None,
        session_data: Dict[str, Any] = None,
    ) -> bool:
        """Validate authorization using server-side session data only."""
        # Only trust server-side session data for authorization
        if not session_data:
            if self.logger:
                self.logger.warning(
                    f"No server-side session data for authorization check - User: {self._sanitize_log_input(claims.sub)}"
                )
            return False

        # Get server-side role from session (not from token)
        server_role = session_data.get("server_role")
        if not server_role:
            if self.logger:
                self.logger.warning(
                    f"No server-side role found in session - User: {self._sanitize_log_input(claims.sub)}"
                )
            return False

        # Verify required role
        if required_role and server_role != required_role:
            if self.logger:
                self.logger.warning(
                    f"Insufficient server-side privileges - User: {self._sanitize_log_input(claims.sub)}, Required: {required_role}, Got: {server_role}"
                )
            return False

        return True

    def _initialize_keys(self):
        """Initialize RSA key pairs for JWT signing."""
        if self.algorithm == "RS256":
            # Check for existing keys in environment
            private_key = os.getenv("JWT_PRIVATE_KEY")
            public_key = os.getenv("JWT_PUBLIC_KEY")

            if private_key and public_key:
                # Use existing keys
                key_id = self._generate_key_id()
                self._current_key_pair = JWTKeyPair(
                    key_id=key_id,
                    private_key=private_key,
                    public_key=public_key,
                    created_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc)
                    + timedelta(days=self.key_rotation_interval),
                    algorithm=self.algorithm,
                )
                self._key_cache[key_id] = self._current_key_pair
            else:
                # Generate new key pair
                self._rotate_keys()

    def _generate_key_id(self) -> str:
        """Generate unique key ID."""
        return f"kid_{int(time.time())}_{secrets.token_urlsafe(8)}"

    def _generate_rsa_key_pair(self) -> Tuple[str, str]:
        """Generate new RSA key pair."""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

        # Get private key PEM
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Get public key PEM
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        return private_pem, public_pem

    def _rotate_keys(self):
        """Rotate RSA keys for enhanced security."""
        if self.algorithm != "RS256":
            return

        # Generate new key pair
        private_key, public_key = self._generate_rsa_key_pair()
        key_id = self._generate_key_id()

        # Create new key pair
        new_key_pair = JWTKeyPair(
            key_id=key_id,
            private_key=private_key,
            public_key=public_key,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self.key_rotation_interval),
            algorithm=self.algorithm,
        )

        # Store old key for verification of existing tokens
        if self._current_key_pair:
            self._key_cache[self._current_key_pair.key_id] = self._current_key_pair

        # Set new key as current
        self._current_key_pair = new_key_pair
        self._key_cache[key_id] = new_key_pair

        # Clean up expired keys
        self._cleanup_expired_keys()

        if self.logger:
            self.logger.info(
                f"JWT keys rotated successfully - New KeyID: {self._sanitize_log_input(key_id)}"
            )

    def _cleanup_expired_keys(self):
        """Remove expired keys from cache."""
        now = datetime.now(timezone.utc)
        expired_keys = [
            kid
            for kid, key_pair in self._key_cache.items()
            if key_pair != self._current_key_pair
            and now > key_pair.expires_at + timedelta(days=7)
        ]

        for kid in expired_keys:
            del self._key_cache[kid]

    def _generate_jti(self, token_type: TokenType) -> str:
        """Generate unique JWT ID."""
        return f"{token_type.value}_{uuid.uuid4().hex}"

    def _generate_device_fingerprint(self, device_info: Dict[str, Any]) -> str:
        """Generate device fingerprint for security tracking."""
        # Combine device characteristics
        fingerprint_data = f"{device_info.get('user_agent', '')}"
        fingerprint_data += f"{device_info.get('platform', '')}"
        fingerprint_data += f"{device_info.get('screen_resolution', '')}"
        fingerprint_data += f"{device_info.get('timezone', '')}"

        # Generate hash
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

    async def create_token(
        self,
        user_id: str,
        email: str,
        role: str,
        user_type: str,
        token_type: TokenType,
        device_info: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        mfa_verified: bool = False,
        mfa_required: bool = False,
    ) -> str:
        """
        Create JWT token with comprehensive security features.

        Args:
            user_id: User identifier
            email: User email
            role: User role
            user_type: User type (parent/child/admin)
            token_type: Type of token to create
            device_info: Device information for fingerprinting
            ip_address: Client IP address
            permissions: User permissions list
            metadata: Additional metadata
            mfa_verified: Whether MFA was verified
            mfa_required: Whether MFA is required

        Returns:
            Encoded JWT token
        """
        now = datetime.now(timezone.utc)

        # Determine TTL based on token type
        ttl_map = {
            TokenType.ACCESS: self.access_token_ttl,
            TokenType.REFRESH: self.refresh_token_ttl,
            TokenType.MFA: self.mfa_token_ttl,
            TokenType.PASSWORD_RESET: 3600,  # 1 hour
            TokenType.EMAIL_VERIFICATION: 86400,  # 24 hours
            TokenType.API_KEY: 31536000,  # 1 year
        }
        ttl = ttl_map.get(token_type, self.access_token_ttl)

        # Generate device fingerprint if required
        device_id = None
        if self.require_device_id and device_info:
            device_id = self._generate_device_fingerprint(device_info)

        # Create claims
        claims = JWTClaims(
            sub=user_id,
            iat=int(now.timestamp()),
            exp=int((now + timedelta(seconds=ttl)).timestamp()),
            nbf=int(now.timestamp()),
            jti=self._generate_jti(token_type),
            type=token_type,
            email=email,
            role=role,
            user_type=user_type,
            device_id=device_id,
            ip_address=ip_address if self.track_ip_address else None,
            session_id=str(uuid.uuid4()) if token_type == TokenType.REFRESH else None,
            mfa_verified=mfa_verified,
            mfa_required=mfa_required,
            permissions=permissions or [],
            metadata=metadata or {},
        )

        # Encode token - PRODUCTION SECURITY ENFORCEMENT
        if self.algorithm == "RS256":
            if not self._current_key_pair:
                raise Exception(
                    "SECURITY VIOLATION: No RSA key pair available for JWT signing"
                )
            encoded_token = jwt.encode(
                claims.to_dict(),
                self._current_key_pair.private_key,
                algorithm=self.algorithm,
                headers={"kid": self._current_key_pair.key_id},
            )
        else:
            # Fallback for development environments only
            if os.getenv("ENVIRONMENT") == "production":
                raise Exception("SECURITY VIOLATION: HS256 not allowed in production")

            from src.infrastructure.config.production_config import get_config

            config = get_config()
            jwt_secret = config.JWT_SECRET_KEY
            if not jwt_secret:
                raise Exception(
                    "JWT_SECRET_KEY missing in config. COPPA compliance violation."
                )

            if not self.fallback_algorithm:
                raise Exception(
                    "SECURITY VIOLATION: No fallback algorithm available in production"
                )

            encoded_token = jwt.encode(
                claims.to_dict(), jwt_secret, algorithm=self.fallback_algorithm
            )

        # Store token metadata in Redis for tracking
        if self._redis_client:
            await self._store_token_metadata(claims, token_type)

        # Log token creation (sanitize inputs)
        if self.logger:
            self.logger.info(
                "JWT token created",
                extra={
                    "user_id": self._sanitize_log_input(user_id),
                    "token_type": token_type.value,
                    "jti": claims.jti,
                    "device_id": (
                        self._sanitize_log_input(device_id) if device_id else None
                    ),
                    "ip_address": (
                        self._sanitize_log_input(ip_address) if ip_address else None
                    ),
                },
            )

        return encoded_token

    async def verify_token(
        self,
        token: str,
        expected_type: Optional[TokenType] = None,
        verify_device: bool = True,
        current_device_info: Optional[Dict[str, Any]] = None,
        current_ip: Optional[str] = None,
    ) -> JWTClaims:
        """
        Verify JWT token with comprehensive security checks.

        Args:
            token: JWT token to verify
            expected_type: Expected token type
            verify_device: Whether to verify device fingerprint
            current_device_info: Current device information
            current_ip: Current IP address

        Returns:
            Decoded JWT claims

        Raises:
            Various JWT and security exceptions
        """
        try:
            # Decode header to get key ID
            headers = jwt.get_unverified_header(token)
            kid = headers.get("kid")

            # Determine verification key/secret
            if kid and kid in self._key_cache:
                # Use specific key for verification
                key_pair = self._key_cache[kid]
                payload = jwt.decode(
                    token, key_pair.public_key, algorithms=[self.algorithm]
                )
            elif self.algorithm == "RS256" and self._current_key_pair:
                # Try current key
                payload = jwt.decode(
                    token,
                    self._current_key_pair.public_key,
                    algorithms=[self.algorithm],
                )
            else:
                # PRODUCTION SECURITY: NO FALLBACK ALLOWED
                if os.getenv("ENVIRONMENT") == "production":
                    raise jwt.InvalidTokenError(
                        "SECURITY VIOLATION: Invalid token format in production"
                    )

                # Fallback for development environments only
                if not self.fallback_algorithm:
                    raise jwt.InvalidTokenError("No valid signing key available")

                from src.infrastructure.config.production_config import get_config

                config = get_config()
                jwt_secret = config.JWT_SECRET_KEY
                if not jwt_secret:
                    raise Exception(
                        "JWT_SECRET_KEY missing in config. COPPA compliance violation."
                    )

                payload = jwt.decode(
                    token, jwt_secret, algorithms=[self.fallback_algorithm]
                )

            # Parse claims
            claims = JWTClaims.from_dict(payload)

            # Verify token type
            if expected_type and claims.type != expected_type:
                raise jwt.InvalidTokenError(
                    f"Invalid token type: expected {expected_type.value}, got {claims.type.value}"
                )

            # Check if token is blacklisted
            if self._redis_client:
                is_blacklisted = await self._is_token_blacklisted(claims.jti)
                if is_blacklisted:
                    raise jwt.InvalidTokenError("Token has been revoked")

            # Verify device fingerprint if required
            if verify_device and self.require_device_id and claims.device_id:
                if not current_device_info:
                    raise jwt.InvalidTokenError(
                        "Device verification required but no device info provided"
                    )

                current_device_id = self._generate_device_fingerprint(
                    current_device_info
                )
                if claims.device_id != current_device_id:
                    # Log potential security issue (sanitize inputs)
                    if self.logger:
                        self.logger.warning(
                            "Device fingerprint mismatch",
                            extra={
                                "user_id": self._sanitize_log_input(claims.sub),
                                "expected_device": self._sanitize_log_input(
                                    claims.device_id
                                ),
                                "current_device": self._sanitize_log_input(
                                    current_device_id
                                ),
                            },
                        )
                    raise jwt.InvalidTokenError("Device verification failed")

            # Verify IP address if tracking is enabled
            if self.track_ip_address and claims.ip_address and current_ip:
                if claims.ip_address != current_ip:
                    # Log IP change (might be legitimate, sanitize inputs)
                    if self.logger:
                        self.logger.info(
                            "IP address changed",
                            extra={
                                "user_id": self._sanitize_log_input(claims.sub),
                                "original_ip": self._sanitize_log_input(
                                    claims.ip_address
                                ),
                                "current_ip": self._sanitize_log_input(current_ip),
                            },
                        )

            # Check MFA requirements
            if claims.mfa_required and not claims.mfa_verified:
                if claims.type != TokenType.MFA:
                    raise jwt.InvalidTokenError("MFA verification required")

            # Update last activity if Redis available
            if self._redis_client and claims.session_id:
                await self._update_session_activity(claims.session_id)

            return claims

        except jwt.ExpiredSignatureError:
            if self.logger:
                self.logger.warning(
                    "JWT token expired",
                    extra={"token_preview": self._sanitize_log_input(token[-10:])},
                )
            raise
        except jwt.InvalidTokenError as e:
            if self.logger:
                self.logger.warning(
                    f"JWT token invalid: {self._sanitize_log_input(str(e))}",
                    extra={"token_preview": self._sanitize_log_input(token[-10:])},
                )
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"JWT verification error: {self._sanitize_log_input(str(e))}",
                    exc_info=True,
                )
            raise jwt.InvalidTokenError(f"Token verification failed: {str(e)}")

    async def revoke_token(self, jti: str, reason: str = "manual_revocation"):
        """Revoke a token by adding to blacklist."""
        if not self._redis_client:
            return

        # Add to blacklist with expiration
        blacklist_key = f"jwt:blacklist:{jti}"
        await self._redis_client.setex(
            blacklist_key,
            self.refresh_token_ttl,  # Keep for max token lifetime
            json.dumps(
                {"revoked_at": datetime.now(timezone.utc).isoformat(), "reason": reason}
            ),
        )

        if self.logger:
            self.logger.info(
                f"Token revoked - JTI: {self._sanitize_log_input(jti)}, Reason: {self._sanitize_log_input(reason)}"
            )

    async def revoke_all_user_tokens(
        self, user_id: str, reason: str = "security_reset"
    ):
        """Revoke all tokens for a user."""
        if not self._redis_client:
            return

        # Get all active sessions for user
        pattern = f"jwt:session:{user_id}:*"
        cursor = 0

        while True:
            cursor, keys = await self._redis_client.scan(
                cursor, match=pattern, count=100
            )

            for key in keys:
                session_data = await self._redis_client.get(key)
                if session_data:
                    session = json.loads(session_data)
                    jti = session.get("jti")
                    if jti:
                        await self.revoke_token(jti, reason)

            if cursor == 0:
                break

        if self.logger:
            self.logger.info(
                f"All tokens revoked for user - UserID: {self._sanitize_log_input(user_id)}, Reason: {self._sanitize_log_input(reason)}"
            )

    async def refresh_token(
        self,
        refresh_token: str,
        device_info: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Refresh access token using refresh token.

        Returns:
            Tuple of (new_access_token, new_refresh_token)
        """
        # Verify refresh token
        claims = await self.verify_token(
            refresh_token,
            expected_type=TokenType.REFRESH,
            verify_device=True,
            current_device_info=device_info,
            current_ip=ip_address,
        )

        # Revoke old refresh token
        await self.revoke_token(claims.jti, "token_refresh")

        # Create new tokens
        new_access_token = await self.create_token(
            user_id=claims.sub,
            email=claims.email,
            role=claims.role,
            user_type=claims.user_type,
            token_type=TokenType.ACCESS,
            device_info=device_info,
            ip_address=ip_address,
            permissions=claims.permissions,
            metadata=claims.metadata,
            mfa_verified=claims.mfa_verified,
            mfa_required=claims.mfa_required,
        )

        new_refresh_token = await self.create_token(
            user_id=claims.sub,
            email=claims.email,
            role=claims.role,
            user_type=claims.user_type,
            token_type=TokenType.REFRESH,
            device_info=device_info,
            ip_address=ip_address,
            permissions=claims.permissions,
            metadata=claims.metadata,
            mfa_verified=claims.mfa_verified,
            mfa_required=claims.mfa_required,
        )

        return new_access_token, new_refresh_token

    async def _store_token_metadata(self, claims: JWTClaims, token_type: TokenType):
        """Store token metadata in Redis for tracking."""
        if not self._redis_client:
            return

        # Store session data
        if token_type == TokenType.REFRESH and claims.session_id:
            session_key = f"jwt:session:{claims.sub}:{claims.session_id}"
            session_data = {
                "jti": claims.jti,
                "created_at": datetime.fromtimestamp(
                    claims.iat, tz=timezone.utc
                ).isoformat(),
                "expires_at": datetime.fromtimestamp(
                    claims.exp, tz=timezone.utc
                ).isoformat(),
                "device_id": claims.device_id,
                "ip_address": claims.ip_address,
                "last_activity": datetime.now(timezone.utc).isoformat(),
            }

            await self._redis_client.setex(
                session_key, claims.exp - claims.iat, json.dumps(session_data)
            )

            # Enforce max active sessions
            await self._enforce_max_sessions(claims.sub)

    async def _enforce_max_sessions(self, user_id: str):
        """Enforce maximum active sessions per user."""
        if not self._redis_client:
            return

        # Get all sessions for user
        pattern = f"jwt:session:{user_id}:*"
        cursor = 0
        sessions = []

        while True:
            cursor, keys = await self._redis_client.scan(
                cursor, match=pattern, count=100
            )

            for key in keys:
                session_data = await self._redis_client.get(key)
                if session_data:
                    session = json.loads(session_data)
                    session["key"] = key
                    sessions.append(session)

            if cursor == 0:
                break

        # Sort by last activity
        sessions.sort(key=lambda s: s.get("last_activity", ""), reverse=True)

        # Revoke oldest sessions if over limit
        if len(sessions) > self.max_active_sessions:
            for session in sessions[self.max_active_sessions :]:
                jti = session.get("jti")
                if jti:
                    await self.revoke_token(jti, "max_sessions_exceeded")
                await self._redis_client.delete(session["key"])

    async def _is_token_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted."""
        if not self._redis_client:
            return False

        blacklist_key = f"jwt:blacklist:{jti}"
        result = await self._redis_client.get(blacklist_key)
        return result is not None

    async def _update_session_activity(self, session_id: str):
        """Update session last activity timestamp."""
        if not self._redis_client:
            return

        # Find session key
        pattern = f"jwt:session:*:{session_id}"
        cursor = 0

        while True:
            cursor, keys = await self._redis_client.scan(
                cursor, match=pattern, count=10
            )

            for key in keys:
                session_data = await self._redis_client.get(key)
                if session_data:
                    session = json.loads(session_data)
                    session["last_activity"] = datetime.now(timezone.utc).isoformat()

                    # Get TTL and update
                    ttl = await self._redis_client.ttl(key)
                    if ttl > 0:
                        await self._redis_client.setex(key, ttl, json.dumps(session))

            if cursor == 0:
                break

    async def set_redis_client(self, redis_client: redis.Redis):
        """Set Redis client for token tracking."""
        self._redis_client = redis_client

    def set_logger(self, logger):
        """Set logger for audit logging."""
        self.logger = logger

    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user."""
        if not self._redis_client:
            return []

        sessions = []
        pattern = f"jwt:session:{user_id}:*"
        cursor = 0

        while True:
            cursor, keys = await self._redis_client.scan(
                cursor, match=pattern, count=100
            )

            for key in keys:
                session_data = await self._redis_client.get(key)
                if session_data:
                    session = json.loads(session_data)
                    sessions.append(session)

            if cursor == 0:
                break

        return sessions

    def _sanitize_log_input(self, value: str) -> str:
        """Sanitize input for safe logging."""
        if not value:
            return ""

        # Remove newlines and control characters that could break log integrity
        sanitized = str(value).replace("\n", "").replace("\r", "").replace("\t", " ")

        # Limit length to prevent log flooding
        if len(sanitized) > 100:
            sanitized = sanitized[:97] + "..."

        return sanitized

    def get_public_keys(self) -> Dict[str, str]:
        """Get all public keys for external verification."""
        return {
            kid: key_pair.public_key
            for kid, key_pair in self._key_cache.items()
            if key_pair.is_valid()
        }


# Global instance
advanced_jwt_manager = AdvancedJWTManager()
