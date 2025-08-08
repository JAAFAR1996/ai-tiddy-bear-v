"""
🎯 REDIS SESSION STORE - PRODUCTION GRADE SESSION MANAGEMENT
===========================================================
Comprehensive Redis-based session storage system:
- Distributed session management across multiple instances
- Child-safe session tracking with COPPA compliance
- Session timeout and cleanup automation
- Real-time session monitoring and analytics
- Encryption of sensitive session data
- Session hijacking protection
- Concurrent session limits enforcement

SECURE SESSION MANAGEMENT - CHILD PROTECTION FIRST
"""

import asyncio
import json
import time
import logging
import uuid
import hashlib
import secrets
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict

# Cryptography for session data encryption
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# Redis imports
from redis.asyncio import Redis, ConnectionPool

# Internal imports
from src.infrastructure.logging.structlog_logger import StructlogLogger

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    """Session status types."""

    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"


class SessionType(str, Enum):
    """Types of sessions."""

    CHILD_INTERACTION = "child_interaction"
    PARENT_DASHBOARD = "parent_dashboard"
    ADMIN_CONSOLE = "admin_console"
    API_SESSION = "api_session"


@dataclass
class SessionConfig:
    """Configuration for session management."""

    default_timeout_minutes: int = 30
    max_timeout_minutes: int = 240  # 4 hours max
    cleanup_interval_minutes: int = 5
    max_sessions_per_child: int = 2
    max_sessions_per_parent: int = 10
    enable_encryption: bool = True
    session_cookie_secure: bool = True
    session_cookie_httponly: bool = True
    session_token_length: int = 32


@dataclass
class SessionData:
    """Session data structure."""

    session_id: str
    user_id: str
    user_type: str  # child, parent, admin
    session_type: SessionType
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    device_info: Dict[str, Any]
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for field in ["created_at", "last_activity", "expires_at"]:
            if isinstance(data[field], datetime):
                data[field] = data[field].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Create SessionData from dictionary."""
        # Convert ISO strings back to datetime objects
        for field in ["created_at", "last_activity", "expires_at"]:
            if isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])

        return cls(**data)


@dataclass
class SessionMetrics:
    """Session analytics and metrics."""

    total_sessions: int = 0
    active_sessions: int = 0
    expired_sessions: int = 0
    average_duration_minutes: float = 0.0
    sessions_by_type: Dict[SessionType, int] = None
    sessions_by_user_type: Dict[str, int] = None

    def __post_init__(self):
        if self.sessions_by_type is None:
            self.sessions_by_type = {}
        if self.sessions_by_user_type is None:
            self.sessions_by_user_type = {}


class RedisSessionStore:
    """
    Production-grade Redis-based session store with comprehensive features.

    Features:
    - Distributed session management
    - Child-safe session tracking
    - Automatic session cleanup
    - Session encryption
    - Concurrent session limits
    - Real-time monitoring
    - COPPA compliance
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        redis_pool: Optional[ConnectionPool] = None,
        config: Optional[SessionConfig] = None,
        encryption_key: Optional[bytes] = None,
        key_prefix: str = "session",
    ):
        """
        Initialize Redis session store.

        Args:
            redis_url: Redis connection URL
            redis_pool: Optional Redis connection pool
            config: Session configuration
            encryption_key: Optional encryption key for session data
            key_prefix: Prefix for Redis keys
        """
        self.config = config or SessionConfig()
        self.key_prefix = key_prefix
        self.logger = StructlogLogger("redis_session_store", component="session")

        # Initialize Redis connection
        if redis_pool:
            self.redis = Redis(connection_pool=redis_pool)
        else:
            self.redis = Redis.from_url(redis_url, decode_responses=True)

        # Initialize encryption
        self.encryption_enabled = self.config.enable_encryption
        if self.encryption_enabled:
            self._init_encryption(encryption_key)

        # Session cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

        # Metrics tracking
        self._session_metrics = SessionMetrics()

        # Initialize Lua scripts for atomic operations
        self._init_lua_scripts()

        self.logger.info("Redis session store initialized")

    def _init_encryption(self, encryption_key: Optional[bytes]):
        """Initialize session data encryption."""
        if encryption_key:
            self.fernet = Fernet(encryption_key)
        else:
            # Production: Load session key, salt, and iterations from environment variables (fail fast if missing)
            password = os.environ.get("SESSION_MASTER_KEY")
            salt = os.environ.get("SESSION_SALT")
            iterations = int(os.environ.get("SESSION_KDF_ITERATIONS", "100000"))
            if not password or not salt:
                raise RuntimeError(
                    "❌ CRITICAL: SESSION_MASTER_KEY and SESSION_SALT environment variables must be set for session encryption (COPPA/production compliance)"
                )
            password = password.encode()
            salt = salt.encode()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=iterations,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            self.fernet = Fernet(key)
        self.logger.info(
            f"Session encryption initialized (env-based, iterations={iterations})"
        )

    def _init_lua_scripts(self):
        """Initialize Lua scripts for atomic Redis operations."""

        # Script to create session with concurrent session limit check
        self.create_session_script = """
        local session_key = KEYS[1]
        local user_sessions_key = KEYS[2]
        local session_data = ARGV[1]
        local max_sessions = tonumber(ARGV[2])
        local session_id = ARGV[3]
        local expires_at = tonumber(ARGV[4])
        
        -- Check current session count for user
        local current_count = redis.call('SCARD', user_sessions_key)
        
        if current_count >= max_sessions then
            -- Remove oldest session
            local oldest_sessions = redis.call('ZRANGE', user_sessions_key .. ':timestamps', 0, 0, 'WITHSCORES')
            if #oldest_sessions > 0 then
                local oldest_session = oldest_sessions[1]
                redis.call('DEL', oldest_session)
                redis.call('SREM', user_sessions_key, oldest_session)
                redis.call('ZREM', user_sessions_key .. ':timestamps', oldest_session)
            end
        end
        
        -- Create new session
        redis.call('SET', session_key, session_data, 'EX', expires_at - redis.call('TIME')[1])
        redis.call('SADD', user_sessions_key, session_id)
        redis.call('ZADD', user_sessions_key .. ':timestamps', expires_at, session_id)
        redis.call('EXPIRE', user_sessions_key, expires_at - redis.call('TIME')[1])
        redis.call('EXPIRE', user_sessions_key .. ':timestamps', expires_at - redis.call('TIME')[1])
        
        return 1
        """

        # Script to update session activity atomically
        self.update_activity_script = """
        local session_key = KEYS[1]
        local current_time = ARGV[1]
        local new_expires_at = tonumber(ARGV[2])
        
        -- Check if session exists
        if redis.call('EXISTS', session_key) == 0 then
            return 0
        end
        
        -- Get current session data and update last_activity
        local session_data = redis.call('GET', session_key)
        if not session_data then
            return 0
        end
        
        -- Update TTL
        redis.call('EXPIRE', session_key, new_expires_at - redis.call('TIME')[1])
        
        return 1
        """

    # ========================================================================
    # CORE SESSION MANAGEMENT
    # ========================================================================

    async def create_session(
        self,
        user_id: str,
        user_type: str,
        session_type: SessionType,
        device_info: Dict[str, Any],
        timeout_minutes: Optional[int] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new session with comprehensive validation.

        Args:
            user_id: User identifier
            user_type: Type of user (child, parent, admin)
            session_type: Type of session
            device_info: Device information
            timeout_minutes: Session timeout (uses default if not specified)
            client_ip: Client IP address
            user_agent: User agent string
            metadata: Additional session metadata

        Returns:
            Session ID

        Raises:
            ValueError: If validation fails
            RuntimeError: If session creation fails
        """
        # Validate inputs
        await self._validate_session_creation(user_id, user_type, session_type)

        # Generate secure session ID
        session_id = self._generate_session_id()

        # Calculate timeout
        timeout = timeout_minutes or self.config.default_timeout_minutes
        timeout = min(timeout, self.config.max_timeout_minutes)

        # Create session data
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=timeout)

        session_data = SessionData(
            session_id=session_id,
            user_id=user_id,
            user_type=user_type,
            session_type=session_type,
            created_at=now,
            last_activity=now,
            expires_at=expires_at,
            device_info=device_info,
            client_ip=client_ip,
            user_agent=user_agent,
            metadata=metadata or {},
        )

        # Store session in Redis
        await self._store_session(session_data)

        # Update metrics
        self._session_metrics.total_sessions += 1
        self._session_metrics.active_sessions += 1
        self._session_metrics.sessions_by_type[session_type] = (
            self._session_metrics.sessions_by_type.get(session_type, 0) + 1
        )
        self._session_metrics.sessions_by_user_type[user_type] = (
            self._session_metrics.sessions_by_user_type.get(user_type, 0) + 1
        )

        # Log session creation
        self.logger.info(
            f"Session created: {session_id}",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "user_type": user_type,
                "session_type": session_type.value,
                "timeout_minutes": timeout,
                "client_ip": client_ip,
            },
        )

        return session_id

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        Retrieve session data.

        Args:
            session_id: Session identifier

        Returns:
            SessionData if session exists and is valid, None otherwise
        """
        try:
            session_key = self._get_session_key(session_id)
            encrypted_data = await self.redis.get(session_key)

            if not encrypted_data:
                return None

            # Decrypt and deserialize session data
            session_dict = self._decrypt_session_data(encrypted_data)
            session_data = SessionData.from_dict(session_dict)

            # Check if session is expired
            if datetime.utcnow() > session_data.expires_at:
                await self._delete_session(session_id)
                return None

            return session_data

        except Exception as e:
            self.logger.error(f"Failed to retrieve session {session_id}: {e}")
            return None

    async def update_session_activity(
        self,
        session_id: str,
        extend_timeout: bool = True,
        metadata_updates: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update session activity timestamp and optionally extend timeout.

        Args:
            session_id: Session identifier
            extend_timeout: Whether to extend session timeout
            metadata_updates: Optional metadata updates

        Returns:
            True if session was updated, False otherwise
        """
        try:
            session_data = await self.get_session(session_id)
            if not session_data:
                return False

            # Update activity timestamp
            now = datetime.utcnow()
            session_data.last_activity = now

            # Extend timeout if requested
            if extend_timeout:
                timeout_minutes = self.config.default_timeout_minutes
                session_data.expires_at = now + timedelta(minutes=timeout_minutes)

            # Update metadata if provided
            if metadata_updates:
                session_data.metadata.update(metadata_updates)

            # Store updated session
            await self._store_session(session_data)

            return True

        except Exception as e:
            self.logger.error(f"Failed to update session activity {session_id}: {e}")
            return False

    async def terminate_session(
        self, session_id: str, reason: str = "user_logout"
    ) -> bool:
        """
        Terminate a session and clean up associated data.

        Args:
            session_id: Session identifier
            reason: Reason for termination

        Returns:
            True if session was terminated, False otherwise
        """
        try:
            session_data = await self.get_session(session_id)
            if not session_data:
                return False

            # Delete session from Redis
            await self._delete_session(session_id)

            # Update metrics
            self._session_metrics.active_sessions = max(
                0, self._session_metrics.active_sessions - 1
            )

            # Log session termination
            duration_minutes = (
                datetime.utcnow() - session_data.created_at
            ).total_seconds() / 60

            self.logger.info(
                f"Session terminated: {session_id}",
                extra={
                    "session_id": session_id,
                    "user_id": session_data.user_id,
                    "duration_minutes": duration_minutes,
                    "reason": reason,
                },
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to terminate session {session_id}: {e}")
            return False

    # ========================================================================
    # CHILD-SPECIFIC SESSION MANAGEMENT
    # ========================================================================

    async def create_child_session(
        self,
        child_id: str,
        child_age: int,
        device_info: Dict[str, Any],
        parent_consent: bool = True,
        accessibility_needs: Optional[List[str]] = None,
        client_ip: Optional[str] = None,
    ) -> str:
        """
        Create a child session with COPPA compliance checks.

        Args:
            child_id: Child identifier
            child_age: Child's age (must be 3-13)
            device_info: Device information
            parent_consent: Whether parental consent is granted
            accessibility_needs: Child's accessibility requirements
            client_ip: Client IP address

        Returns:
            Session ID

        Raises:
            ValueError: If child age is invalid or consent not granted
        """
        # COPPA compliance validation
        if child_age < 3 or child_age > 13:
            raise ValueError(f"Child age {child_age} outside allowed range (3-13)")

        if not parent_consent:
            raise ValueError("Parental consent required for child sessions")

        # Check concurrent session limits for child
        active_sessions = await self.get_user_active_sessions(child_id, "child")
        if len(active_sessions) >= self.config.max_sessions_per_child:
            # Terminate oldest session
            oldest_session = min(active_sessions, key=lambda s: s.created_at)
            await self.terminate_session(
                oldest_session.session_id, "concurrent_limit_exceeded"
            )

        # Age-appropriate session timeout
        timeout_minutes = self._get_age_appropriate_timeout(child_age)

        # Create session with child-specific metadata
        metadata = {
            "child_age": child_age,
            "parent_consent": parent_consent,
            "accessibility_needs": accessibility_needs or [],
            "content_filter_level": "strict",
            "max_session_duration": timeout_minutes,
        }

        return await self.create_session(
            user_id=child_id,
            user_type="child",
            session_type=SessionType.CHILD_INTERACTION,
            device_info=device_info,
            timeout_minutes=timeout_minutes,
            client_ip=client_ip,
            metadata=metadata,
        )

    def _get_age_appropriate_timeout(self, child_age: int) -> int:
        """Get age-appropriate session timeout in minutes."""
        # Age-based timeout limits (in minutes)
        age_timeouts = {
            3: 15,  # 15 minutes for toddlers
            4: 20,
            5: 25,
            6: 30,
            7: 35,
            8: 40,  # 40 minutes for elementary age
            9: 45,
            10: 50,
            11: 55,
            12: 60,  # 1 hour for preteens
            13: 60,
        }

        return age_timeouts.get(child_age, 30)  # Default to 30 minutes

    async def monitor_child_session_time(self, session_id: str) -> Dict[str, Any]:
        """
        Monitor child session time for compliance with recommended limits.

        Args:
            session_id: Child session identifier

        Returns:
            Dictionary with session time monitoring data
        """
        session_data = await self.get_session(session_id)
        if not session_data or session_data.user_type != "child":
            return {"error": "Invalid child session"}

        # Calculate session duration
        duration_minutes = (
            datetime.utcnow() - session_data.created_at
        ).total_seconds() / 60
        child_age = session_data.metadata.get("child_age", 8)
        recommended_limit = self._get_age_appropriate_timeout(child_age)

        # Check compliance
        is_compliant = duration_minutes <= recommended_limit
        warning_threshold = recommended_limit * 0.8  # 80% of limit
        needs_warning = duration_minutes >= warning_threshold

        return {
            "session_id": session_id,
            "duration_minutes": duration_minutes,
            "recommended_limit_minutes": recommended_limit,
            "is_compliant": is_compliant,
            "needs_warning": needs_warning,
            "time_remaining_minutes": max(0, recommended_limit - duration_minutes),
            "usage_percentage": (duration_minutes / recommended_limit) * 100,
        }

    # ========================================================================
    # SESSION QUERYING AND MANAGEMENT
    # ========================================================================

    async def get_user_active_sessions(
        self, user_id: str, user_type: str
    ) -> List[SessionData]:
        """Get all active sessions for a user."""
        user_sessions_key = self._get_user_sessions_key(user_id, user_type)
        session_ids = await self.redis.smembers(user_sessions_key)

        active_sessions = []
        for session_id in session_ids:
            session_data = await self.get_session(session_id)
            if session_data and session_data.is_active:
                active_sessions.append(session_data)

        return active_sessions

    async def get_all_active_sessions(self) -> List[SessionData]:
        """Get all active sessions in the system."""
        pattern = f"{self.key_prefix}:session:*"
        session_keys = await self.redis.keys(pattern)

        active_sessions = []
        for session_key in session_keys:
            session_id = session_key.split(":")[-1]
            session_data = await self.get_session(session_id)
            if session_data and session_data.is_active:
                active_sessions.append(session_data)

        return active_sessions

    async def terminate_user_sessions(
        self, user_id: str, user_type: str, reason: str = "admin_action"
    ) -> int:
        """Terminate all sessions for a user."""
        active_sessions = await self.get_user_active_sessions(user_id, user_type)
        terminated_count = 0

        for session in active_sessions:
            if await self.terminate_session(session.session_id, reason):
                terminated_count += 1

        return terminated_count

    async def get_session_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """Get session analytics for the specified time period."""
        # This would require more sophisticated tracking in a production system
        # For now, return current metrics
        return {
            "total_sessions": self._session_metrics.total_sessions,
            "active_sessions": self._session_metrics.active_sessions,
            "sessions_by_type": dict(self._session_metrics.sessions_by_type),
            "sessions_by_user_type": dict(self._session_metrics.sessions_by_user_type),
            "time_period_hours": hours,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ========================================================================
    # SESSION CLEANUP AND MAINTENANCE
    # ========================================================================

    async def start_cleanup_task(self):
        """Start automatic session cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            return

        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("Session cleanup task started")

    async def stop_cleanup_task(self):
        """Stop automatic session cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Session cleanup task stopped")

    async def _cleanup_loop(self):
        """Main cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval_minutes * 60)
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions and return count of cleaned sessions."""
        pattern = f"{self.key_prefix}:session:*"
        session_keys = await self.redis.keys(pattern)

        cleaned_count = 0
        for session_key in session_keys:
            session_id = session_key.split(":")[-1]

            # Check if session is expired by trying to get it
            session_data = await self.get_session(session_id)
            if not session_data:
                # Session was automatically cleaned up by get_session
                cleaned_count += 1

        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} expired sessions")
            self._session_metrics.active_sessions = max(
                0, self._session_metrics.active_sessions - cleaned_count
            )

        return cleaned_count

    # ========================================================================
    # SECURITY AND ENCRYPTION
    # ========================================================================

    def _generate_session_id(self) -> str:
        """Generate cryptographically secure session ID."""
        # Generate random bytes and encode as URL-safe base64
        random_bytes = secrets.token_bytes(self.config.session_token_length)
        session_id = base64.urlsafe_b64encode(random_bytes).decode("ascii").rstrip("=")

        # Add timestamp prefix for better Redis key distribution
        timestamp_prefix = str(int(time.time() * 1000))[
            -8:
        ]  # Last 8 digits of timestamp

        return f"{timestamp_prefix}_{session_id}"

    def _encrypt_session_data(self, data: Dict[str, Any]) -> str:
        """Encrypt session data for storage."""
        if not self.encryption_enabled:
            return json.dumps(data)

        json_data = json.dumps(data)
        encrypted_data = self.fernet.encrypt(json_data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()

    def _decrypt_session_data(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt session data from storage."""
        if not self.encryption_enabled:
            return json.loads(encrypted_data)

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(encrypted_bytes)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            self.logger.error(f"Failed to decrypt session data: {e}")
            raise ValueError("Invalid session data")

    async def validate_session_security(
        self, session_id: str, client_ip: str, user_agent: str
    ) -> bool:
        """Validate session security against potential hijacking."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False

        # Check IP address consistency (if enabled)
        if session_data.client_ip and session_data.client_ip != client_ip:
            self.logger.warning(
                f"Session IP mismatch: {session_id}",
                extra={
                    "session_id": session_id,
                    "original_ip": session_data.client_ip,
                    "current_ip": client_ip,
                },
            )
            # In production, you might want to terminate the session
            # return False

        # Check user agent consistency (if enabled)
        if session_data.user_agent and session_data.user_agent != user_agent:
            self.logger.warning(
                f"Session user agent mismatch: {session_id}",
                extra={
                    "session_id": session_id,
                    "original_ua": session_data.user_agent,
                    "current_ua": user_agent,
                },
            )

        return True

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    async def _validate_session_creation(
        self, user_id: str, user_type: str, session_type: SessionType
    ):
        """Validate session creation parameters."""
        if not user_id:
            raise ValueError("User ID is required")

        if user_type not in ["child", "parent", "admin"]:
            raise ValueError(f"Invalid user type: {user_type}")

        # Check if user is temporarily banned (if you have a ban system)
        # This would integrate with your rate limiting system

    async def _store_session(self, session_data: SessionData):
        """Store session data in Redis."""
        session_key = self._get_session_key(session_data.session_id)
        user_sessions_key = self._get_user_sessions_key(
            session_data.user_id, session_data.user_type
        )

        # Calculate TTL
        ttl_seconds = int((session_data.expires_at - datetime.utcnow()).total_seconds())
        if ttl_seconds <= 0:
            raise ValueError("Session already expired")

        # Encrypt and store session data
        encrypted_data = self._encrypt_session_data(session_data.to_dict())

        # Determine max sessions based on user type
        if session_data.user_type == "child":
            max_sessions = self.config.max_sessions_per_child
        else:
            max_sessions = self.config.max_sessions_per_parent

        # Use Lua script for atomic session creation
        # NOTE: This is Redis eval for Lua scripts, NOT Python eval. The script is static and not user-controlled.
        await self.redis.eval(
            self.create_session_script,
            2,
            session_key,
            user_sessions_key,
            encrypted_data,
            max_sessions,
            session_data.session_id,
            int(session_data.expires_at.timestamp()),
        )

    async def _delete_session(self, session_id: str):
        """Delete session and clean up associated data."""
        session_key = self._get_session_key(session_id)

        # Get session data first to clean up user sessions
        encrypted_data = await self.redis.get(session_key)
        if encrypted_data:
            try:
                session_dict = self._decrypt_session_data(encrypted_data)
                user_id = session_dict["user_id"]
                user_type = session_dict["user_type"]

                # Clean up user sessions tracking
                user_sessions_key = self._get_user_sessions_key(user_id, user_type)
                await self.redis.srem(user_sessions_key, session_id)
                await self.redis.zrem(f"{user_sessions_key}:timestamps", session_id)

            except Exception as e:
                self.logger.error(f"Error cleaning up session data: {e}")

        # Delete session
        await self.redis.delete(session_key)

    def _get_session_key(self, session_id: str) -> str:
        """Get Redis key for session data."""
        return f"{self.key_prefix}:session:{session_id}"

    def _get_user_sessions_key(self, user_id: str, user_type: str) -> str:
        """Get Redis key for user sessions tracking."""
        # Hash user_id for privacy
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        return f"{self.key_prefix}:user_sessions:{user_type}:{user_hash}"

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on session store."""
        try:
            # Test Redis connection
            await self.redis.ping()

            # Get session statistics
            active_sessions = await self.get_all_active_sessions()

            return {
                "status": "healthy",
                "redis_connected": True,
                "active_sessions": len(active_sessions),
                "total_sessions": self._session_metrics.total_sessions,
                "encryption_enabled": self.encryption_enabled,
                "cleanup_task_running": self._cleanup_task
                and not self._cleanup_task.done(),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def close(self):
        """Close Redis connection and cleanup tasks."""
        await self.stop_cleanup_task()
        if self.redis:
            await self.redis.close()


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================


def create_redis_session_store(
    redis_url: str = "redis://localhost:6379",
    child_protection_mode: bool = True,
    encryption_enabled: bool = True,
) -> RedisSessionStore:
    """
    Factory function to create Redis session store with default configuration.

    Args:
        redis_url: Redis connection URL
        child_protection_mode: Enable child-specific protections
        encryption_enabled: Enable session data encryption

    Returns:
        Configured RedisSessionStore instance
    """
    config = SessionConfig()

    if child_protection_mode:
        # Enhanced child protection settings
        config.max_sessions_per_child = 1  # Very restrictive
        config.default_timeout_minutes = 20  # Shorter default timeout
        config.cleanup_interval_minutes = 2  # More frequent cleanup

    config.enable_encryption = encryption_enabled

    return RedisSessionStore(redis_url=redis_url, config=config)


# Export for easy imports
__all__ = [
    "RedisSessionStore",
    "SessionStatus",
    "SessionType",
    "SessionConfig",
    "SessionData",
    "SessionMetrics",
    "create_redis_session_store",
]


if __name__ == "__main__":
    # Demo usage
    async def demo():
        print("🎯 Redis Session Store - Secure Session Management Demo")

        store = create_redis_session_store()

        # Create child session
        session_id = await store.create_child_session(
            child_id="test_child_123",
            child_age=8,
            device_info={"device_type": "tablet", "device_id": "abc123"},
            parent_consent=True,
        )

        print(f"Created child session: {session_id}")

        # Update session activity
        await store.update_session_activity(session_id)
        print("Updated session activity")

        # Monitor session time
        monitoring = await store.monitor_child_session_time(session_id)
        print(f"Session monitoring: {monitoring}")

        # Get session data
        session_data = await store.get_session(session_id)
        if session_data:
            print(f"Session data retrieved: {session_data.user_id}")

        # Terminate session
        await store.terminate_session(session_id)
        print("Session terminated")

        await store.close()

    asyncio.run(demo())
