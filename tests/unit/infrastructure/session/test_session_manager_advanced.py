"""
Advanced Session Manager Tests
==============================
Tests for comprehensive session management with COPPA compliance and child safety.
"""

import pytest
import asyncio
import time
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import uuid


class SessionState(Enum):
    """Session states."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"


class UserType(Enum):
    """User types for session management."""
    CHILD = "child"
    PARENT = "parent"
    GUARDIAN = "guardian"
    ADMIN = "admin"


@dataclass
class SessionData:
    """Session data structure."""
    session_id: str
    user_id: str
    user_type: UserType
    user_age: Optional[int]
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    state: SessionState = SessionState.ACTIVE
    
    # Child safety data
    parent_consent: bool = False
    content_filter_level: str = "strict"
    interaction_count: int = 0
    session_duration_limit: int = 3600  # seconds
    
    # Device information
    device_id: Optional[str] = None
    device_type: str = "unknown"
    ip_address: Optional[str] = None
    
    # Session metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_type": self.user_type.value,
            "user_age": self.user_age,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "state": self.state.value,
            "parent_consent": self.parent_consent,
            "content_filter_level": self.content_filter_level,
            "interaction_count": self.interaction_count,
            "session_duration_limit": self.session_duration_limit,
            "device_id": self.device_id,
            "device_type": self.device_type,
            "ip_address": self.ip_address,
            "metadata": self.metadata
        }
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now() > self.expires_at
    
    def is_child_session(self) -> bool:
        """Check if this is a child session."""
        return self.user_type == UserType.CHILD or (self.user_age and self.user_age < 13)
    
    def get_remaining_time(self) -> int:
        """Get remaining session time in seconds."""
        if self.is_expired():
            return 0
        return int((self.expires_at - datetime.now()).total_seconds())


@dataclass
class SessionMetrics:
    """Session management metrics."""
    total_sessions: int = 0
    active_sessions: int = 0
    child_sessions: int = 0
    expired_sessions: int = 0
    terminated_sessions: int = 0
    average_session_duration: float = 0.0
    coppa_violations: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "active_sessions": self.active_sessions,
            "child_sessions": self.child_sessions,
            "expired_sessions": self.expired_sessions,
            "terminated_sessions": self.terminated_sessions,
            "average_session_duration": self.average_session_duration,
            "coppa_violations": self.coppa_violations
        }


class AdvancedSessionManager:
    """Advanced session manager with COPPA compliance and child safety features."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.sessions: Dict[str, SessionData] = {}
        self.user_sessions: Dict[str, List[str]] = {}  # user_id -> session_ids
        self.metrics = SessionMetrics()
        
        # Configuration
        self.default_session_duration = 3600  # 1 hour
        self.child_session_duration = 1800    # 30 minutes for children
        self.max_sessions_per_user = 3
        self.cleanup_interval = 300  # 5 minutes
        
        # COPPA compliance settings
        self.coppa_mode = True
        self.require_parent_consent = True
        self.data_retention_days = 30
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Callbacks
        self.on_session_created: Optional[callable] = None
        self.on_session_expired: Optional[callable] = None
        self.on_coppa_violation: Optional[callable] = None
    
    async def create_session(
        self,
        user_id: str,
        user_type: UserType,
        user_age: Optional[int] = None,
        device_id: Optional[str] = None,
        device_type: str = "unknown",
        ip_address: Optional[str] = None,
        parent_consent: bool = False,
        **metadata
    ) -> SessionData:
        """Create a new session."""
        # Validate COPPA compliance for children
        if user_age and user_age < 13:
            if self.coppa_mode and self.require_parent_consent and not parent_consent:
                if self.on_coppa_violation:
                    await self.on_coppa_violation("session_creation_without_consent", user_id)
                raise COPPAViolationError("Parent consent required for children under 13")
        
        # Check session limits
        existing_sessions = self.user_sessions.get(user_id, [])
        active_sessions = [
            sid for sid in existing_sessions
            if sid in self.sessions and self.sessions[sid].state == SessionState.ACTIVE
        ]
        
        if len(active_sessions) >= self.max_sessions_per_user:
            # Terminate oldest session
            oldest_session_id = min(active_sessions, key=lambda sid: self.sessions[sid].created_at)
            await self.terminate_session(oldest_session_id, "session_limit_exceeded")
        
        # Determine session duration
        is_child = user_type == UserType.CHILD or (user_age and user_age < 13)
        duration = self.child_session_duration if is_child else self.default_session_duration
        
        # Create session
        session_id = str(uuid.uuid4())
        now = datetime.now()
        
        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            user_type=user_type,
            user_age=user_age,
            created_at=now,
            last_activity=now,
            expires_at=now + timedelta(seconds=duration),
            parent_consent=parent_consent,
            content_filter_level="strict" if is_child else "moderate",
            session_duration_limit=duration,
            device_id=device_id,
            device_type=device_type,
            ip_address=ip_address,
            metadata=metadata
        )
        
        # Store session
        self.sessions[session_id] = session
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        self.user_sessions[user_id].append(session_id)
        
        # Update metrics
        self.metrics.total_sessions += 1
        self.metrics.active_sessions += 1
        if is_child:
            self.metrics.child_sessions += 1
        
        # Store in Redis if available
        if self.redis_client:
            await self._store_session_in_redis(session)
        
        # Callback
        if self.on_session_created:
            await self.on_session_created(session)
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        # Try memory first
        if session_id in self.sessions:
            session = self.sessions[session_id]
            
            # Check if expired
            if session.is_expired():
                await self._expire_session(session_id)
                return None
            
            return session
        
        # Try Redis if available
        if self.redis_client:
            session = await self._load_session_from_redis(session_id)
            if session:
                self.sessions[session_id] = session
                return session
        
        return None
    
    async def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity timestamp."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.last_activity = datetime.now()
        session.interaction_count += 1
        
        # Check child session limits
        if session.is_child_session():
            session_duration = (datetime.now() - session.created_at).total_seconds()
            if session_duration > session.session_duration_limit:
                await self.terminate_session(session_id, "duration_limit_exceeded")
                return False
        
        # Update in Redis
        if self.redis_client:
            await self._store_session_in_redis(session)
        
        return True
    
    async def terminate_session(self, session_id: str, reason: str = "user_logout") -> bool:
        """Terminate a session."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        # Update session state
        session.state = SessionState.TERMINATED
        session.metadata["termination_reason"] = reason
        session.metadata["terminated_at"] = datetime.now().isoformat()
        
        # Update metrics
        self.metrics.active_sessions -= 1
        self.metrics.terminated_sessions += 1
        
        # Calculate session duration for metrics
        duration = (datetime.now() - session.created_at).total_seconds()
        self._update_average_duration(duration)
        
        # Remove from active sessions
        if session.user_id in self.user_sessions:
            self.user_sessions[session.user_id] = [
                sid for sid in self.user_sessions[session.user_id]
                if sid != session_id
            ]
        
        # Update in Redis
        if self.redis_client:
            await self._store_session_in_redis(session)
        
        return True
    
    async def extend_session(self, session_id: str, additional_seconds: int) -> bool:
        """Extend session expiration time."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        # Child sessions have stricter limits
        if session.is_child_session():
            max_extension = 1800  # 30 minutes max for children
            additional_seconds = min(additional_seconds, max_extension)
        
        session.expires_at += timedelta(seconds=additional_seconds)
        
        # Update in Redis
        if self.redis_client:
            await self._store_session_in_redis(session)
        
        return True
    
    async def get_user_sessions(self, user_id: str) -> List[SessionData]:
        """Get all sessions for a user."""
        session_ids = self.user_sessions.get(user_id, [])
        sessions = []
        
        for session_id in session_ids:
            session = await self.get_session(session_id)
            if session:
                sessions.append(session)
        
        return sessions
    
    async def get_active_sessions(self) -> List[SessionData]:
        """Get all active sessions."""
        active_sessions = []
        
        for session_id, session in self.sessions.items():
            if session.state == SessionState.ACTIVE and not session.is_expired():
                active_sessions.append(session)
        
        return active_sessions
    
    async def get_child_sessions(self) -> List[SessionData]:
        """Get all child sessions for monitoring."""
        child_sessions = []
        
        for session in await self.get_active_sessions():
            if session.is_child_session():
                child_sessions.append(session)
        
        return child_sessions
    
    async def validate_session(self, session_id: str, user_id: str = None) -> bool:
        """Validate session exists and is active."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        if session.state != SessionState.ACTIVE:
            return False
        
        if user_id and session.user_id != user_id:
            return False
        
        return True
    
    async def start_cleanup_task(self):
        """Start background cleanup task."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while self._running:
            try:
                await self._cleanup_expired_sessions()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Session cleanup error: {e}")
                await asyncio.sleep(30)
    
    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        expired_session_ids = []
        
        for session_id, session in self.sessions.items():
            if session.is_expired() or session.state in [SessionState.EXPIRED, SessionState.TERMINATED]:
                expired_session_ids.append(session_id)
        
        for session_id in expired_session_ids:
            await self._expire_session(session_id)
    
    async def _expire_session(self, session_id: str):
        """Mark session as expired and clean up."""
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        session.state = SessionState.EXPIRED
        
        # Update metrics
        if session.state == SessionState.ACTIVE:
            self.metrics.active_sessions -= 1
        self.metrics.expired_sessions += 1
        
        # Calculate duration for metrics
        duration = (datetime.now() - session.created_at).total_seconds()
        self._update_average_duration(duration)
        
        # Remove from user sessions
        if session.user_id in self.user_sessions:
            self.user_sessions[session.user_id] = [
                sid for sid in self.user_sessions[session.user_id]
                if sid != session_id
            ]
        
        # Callback
        if self.on_session_expired:
            await self.on_session_expired(session)
        
        # Remove from memory after delay (for audit purposes)
        await asyncio.sleep(300)  # Keep for 5 minutes
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def _update_average_duration(self, duration: float):
        """Update average session duration metric."""
        total_completed = self.metrics.expired_sessions + self.metrics.terminated_sessions
        if total_completed == 1:
            self.metrics.average_session_duration = duration
        else:
            # Running average
            current_total = self.metrics.average_session_duration * (total_completed - 1)
            self.metrics.average_session_duration = (current_total + duration) / total_completed
    
    async def _store_session_in_redis(self, session: SessionData):
        """Store session in Redis."""
        if not self.redis_client:
            return
        
        try:
            session_data = json.dumps(session.to_dict(), default=str)
            await self.redis_client.setex(
                f"session:{session.session_id}",
                int((session.expires_at - datetime.now()).total_seconds()),
                session_data
            )
        except Exception as e:
            print(f"Redis storage error: {e}")
    
    async def _load_session_from_redis(self, session_id: str) -> Optional[SessionData]:
        """Load session from Redis."""
        if not self.redis_client:
            return None
        
        try:
            session_data = await self.redis_client.get(f"session:{session_id}")
            if session_data:
                data = json.loads(session_data)
                return SessionData(
                    session_id=data["session_id"],
                    user_id=data["user_id"],
                    user_type=UserType(data["user_type"]),
                    user_age=data.get("user_age"),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    last_activity=datetime.fromisoformat(data["last_activity"]),
                    expires_at=datetime.fromisoformat(data["expires_at"]),
                    state=SessionState(data["state"]),
                    parent_consent=data.get("parent_consent", False),
                    content_filter_level=data.get("content_filter_level", "strict"),
                    interaction_count=data.get("interaction_count", 0),
                    session_duration_limit=data.get("session_duration_limit", 3600),
                    device_id=data.get("device_id"),
                    device_type=data.get("device_type", "unknown"),
                    ip_address=data.get("ip_address"),
                    metadata=data.get("metadata", {})
                )
        except Exception as e:
            print(f"Redis load error: {e}")
        
        return None
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get session management metrics."""
        return self.metrics.to_dict()
    
    async def get_session_report(self) -> Dict[str, Any]:
        """Get comprehensive session report."""
        active_sessions = await self.get_active_sessions()
        child_sessions = await self.get_child_sessions()
        
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": len(active_sessions),
            "child_sessions": len(child_sessions),
            "metrics": self.get_metrics(),
            "coppa_compliance": {
                "child_sessions_with_consent": len([
                    s for s in child_sessions if s.parent_consent
                ]),
                "child_sessions_without_consent": len([
                    s for s in child_sessions if not s.parent_consent
                ])
            },
            "timestamp": datetime.now().isoformat()
        }


class COPPAViolationError(Exception):
    """Exception raised for COPPA compliance violations."""
    pass


@pytest.fixture
def session_manager():
    """Create session manager for testing."""
    return AdvancedSessionManager()


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = AsyncMock(spec=True)
    redis_mock.setex = AsyncMock(spec=True)
    redis_mock.get = AsyncMock(return_value=None)
    return redis_mock


@pytest.mark.asyncio
class TestAdvancedSessionManager:
    """Test advanced session management functionality."""
    
    async def test_session_creation(self, session_manager):
        """Test basic session creation."""
        session = await session_manager.create_session(
            user_id="user_123",
            user_type=UserType.PARENT,
            user_age=35,
            device_id="device_001",
            device_type="mobile"
        )
        
        assert session.session_id is not None
        assert session.user_id == "user_123"
        assert session.user_type == UserType.PARENT
        assert session.user_age == 35
        assert session.state == SessionState.ACTIVE
        assert session.device_id == "device_001"
        assert session.device_type == "mobile"
    
    async def test_child_session_creation_with_consent(self, session_manager):
        """Test child session creation with parent consent."""
        session = await session_manager.create_session(
            user_id="child_123",
            user_type=UserType.CHILD,
            user_age=8,
            parent_consent=True
        )
        
        assert session.is_child_session()
        assert session.parent_consent is True
        assert session.content_filter_level == "strict"
        assert session.session_duration_limit == session_manager.child_session_duration
    
    async def test_child_session_creation_without_consent(self, session_manager):
        """Test child session creation without parent consent (should fail)."""
        with pytest.raises(COPPAViolationError):
            await session_manager.create_session(
                user_id="child_123",
                user_type=UserType.CHILD,
                user_age=8,
                parent_consent=False
            )
    
    async def test_session_retrieval(self, session_manager):
        """Test session retrieval by ID."""
        # Create session
        created_session = await session_manager.create_session(
            user_id="user_123",
            user_type=UserType.PARENT
        )
        
        # Retrieve session
        retrieved_session = await session_manager.get_session(created_session.session_id)
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == created_session.session_id
        assert retrieved_session.user_id == created_session.user_id
    
    async def test_session_activity_update(self, session_manager):
        """Test session activity updates."""
        # Create session
        session = await session_manager.create_session(
            user_id="user_123",
            user_type=UserType.PARENT
        )
        
        original_activity = session.last_activity
        original_count = session.interaction_count
        
        # Wait a bit and update activity
        await asyncio.sleep(0.1)
        success = await session_manager.update_session_activity(session.session_id)
        
        assert success is True
        assert session.last_activity > original_activity
        assert session.interaction_count == original_count + 1
    
    async def test_session_termination(self, session_manager):
        """Test session termination."""
        # Create session
        session = await session_manager.create_session(
            user_id="user_123",
            user_type=UserType.PARENT
        )
        
        # Terminate session
        success = await session_manager.terminate_session(
            session.session_id,
            "user_logout"
        )
        
        assert success is True
        assert session.state == SessionState.TERMINATED
        assert session.metadata["termination_reason"] == "user_logout"
    
    async def test_session_extension(self, session_manager):
        """Test session time extension."""
        # Create session
        session = await session_manager.create_session(
            user_id="user_123",
            user_type=UserType.PARENT
        )
        
        original_expiry = session.expires_at
        
        # Extend session
        success = await session_manager.extend_session(session.session_id, 1800)
        
        assert success is True
        assert session.expires_at > original_expiry
        assert (session.expires_at - original_expiry).total_seconds() == 1800
    
    async def test_child_session_extension_limits(self, session_manager):
        """Test child session extension limits."""
        # Create child session
        session = await session_manager.create_session(
            user_id="child_123",
            user_type=UserType.CHILD,
            user_age=8,
            parent_consent=True
        )
        
        original_expiry = session.expires_at
        
        # Try to extend by 2 hours (should be limited to 30 minutes)
        success = await session_manager.extend_session(session.session_id, 7200)
        
        assert success is True
        extension = (session.expires_at - original_expiry).total_seconds()
        assert extension == 1800  # Limited to 30 minutes
    
    async def test_session_validation(self, session_manager):
        """Test session validation."""
        # Create session
        session = await session_manager.create_session(
            user_id="user_123",
            user_type=UserType.PARENT
        )
        
        # Valid session
        is_valid = await session_manager.validate_session(session.session_id, "user_123")
        assert is_valid is True
        
        # Invalid user
        is_valid = await session_manager.validate_session(session.session_id, "wrong_user")
        assert is_valid is False
        
        # Terminate session
        await session_manager.terminate_session(session.session_id)
        
        # Should be invalid now
        is_valid = await session_manager.validate_session(session.session_id, "user_123")
        assert is_valid is False
    
    async def test_user_session_limits(self, session_manager):
        """Test session limits per user."""
        user_id = "user_123"
        
        # Create sessions up to limit
        sessions = []
        for i in range(session_manager.max_sessions_per_user):
            session = await session_manager.create_session(
                user_id=user_id,
                user_type=UserType.PARENT
            )
            sessions.append(session)
        
        # All sessions should be active
        user_sessions = await session_manager.get_user_sessions(user_id)
        active_sessions = [s for s in user_sessions if s.state == SessionState.ACTIVE]
        assert len(active_sessions) == session_manager.max_sessions_per_user
        
        # Create one more session (should terminate oldest)
        new_session = await session_manager.create_session(
            user_id=user_id,
            user_type=UserType.PARENT
        )
        
        # Should still have max sessions, but oldest should be terminated
        user_sessions = await session_manager.get_user_sessions(user_id)
        active_sessions = [s for s in user_sessions if s.state == SessionState.ACTIVE]
        assert len(active_sessions) == session_manager.max_sessions_per_user
        
        # First session should be terminated
        assert sessions[0].state == SessionState.TERMINATED
    
    async def test_child_session_duration_limits(self, session_manager):
        """Test child session duration limits."""
        # Set very short duration for testing
        session_manager.child_session_duration = 1
        
        # Create child session
        session = await session_manager.create_session(
            user_id="child_123",
            user_type=UserType.CHILD,
            user_age=8,
            parent_consent=True
        )
        
        # Wait for duration limit
        await asyncio.sleep(1.1)
        
        # Try to update activity (should terminate due to duration)
        success = await session_manager.update_session_activity(session.session_id)
        
        assert success is False
        assert session.state == SessionState.TERMINATED
        assert session.metadata.get("termination_reason") == "duration_limit_exceeded"
    
    async def test_session_expiration(self, session_manager):
        """Test session expiration handling."""
        # Create session with short expiry
        session = await session_manager.create_session(
            user_id="user_123",
            user_type=UserType.PARENT
        )
        
        # Manually set expiry to past
        session.expires_at = datetime.now() - timedelta(seconds=1)
        
        # Try to get session (should return None due to expiry)
        retrieved_session = await session_manager.get_session(session.session_id)
        assert retrieved_session is None
        
        # Session should be marked as expired
        assert session.state == SessionState.EXPIRED
    
    async def test_active_sessions_retrieval(self, session_manager):
        """Test retrieving active sessions."""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = await session_manager.create_session(
                user_id=f"user_{i}",
                user_type=UserType.PARENT
            )
            sessions.append(session)
        
        # Terminate one session
        await session_manager.terminate_session(sessions[1].session_id)
        
        # Get active sessions
        active_sessions = await session_manager.get_active_sessions()
        
        assert len(active_sessions) == 2
        active_ids = [s.session_id for s in active_sessions]
        assert sessions[0].session_id in active_ids
        assert sessions[2].session_id in active_ids
        assert sessions[1].session_id not in active_ids
    
    async def test_child_sessions_monitoring(self, session_manager):
        """Test child session monitoring."""
        # Create mixed sessions
        adult_session = await session_manager.create_session(
            user_id="adult_123",
            user_type=UserType.PARENT,
            user_age=35
        )
        
        child_session = await session_manager.create_session(
            user_id="child_123",
            user_type=UserType.CHILD,
            user_age=8,
            parent_consent=True
        )
        
        # Get child sessions
        child_sessions = await session_manager.get_child_sessions()
        
        assert len(child_sessions) == 1
        assert child_sessions[0].session_id == child_session.session_id
        assert child_sessions[0].is_child_session()
    
    async def test_session_metrics(self, session_manager):
        """Test session metrics collection."""
        # Create various sessions
        await session_manager.create_session("user_1", UserType.PARENT)
        await session_manager.create_session("child_1", UserType.CHILD, user_age=8, parent_consent=True)
        
        session_to_terminate = await session_manager.create_session("user_2", UserType.PARENT)
        await session_manager.terminate_session(session_to_terminate.session_id)
        
        # Get metrics
        metrics = session_manager.get_metrics()
        
        assert metrics["total_sessions"] == 3
        assert metrics["active_sessions"] == 2
        assert metrics["child_sessions"] == 1
        assert metrics["terminated_sessions"] == 1
    
    async def test_session_cleanup_task(self, session_manager):
        """Test background session cleanup."""
        # Set short cleanup interval for testing
        session_manager.cleanup_interval = 0.1
        
        # Create session and expire it
        session = await session_manager.create_session("user_123", UserType.PARENT)
        session.expires_at = datetime.now() - timedelta(seconds=1)
        
        # Start cleanup task
        await session_manager.start_cleanup_task()
        
        # Wait for cleanup
        await asyncio.sleep(0.2)
        
        # Stop cleanup task
        await session_manager.stop_cleanup_task()
        
        # Session should be expired
        assert session.state == SessionState.EXPIRED
    
    async def test_redis_integration(self, session_manager, mock_redis):
        """Test Redis integration for session storage."""
        session_manager.redis_client = mock_redis
        
        # Create session
        session = await session_manager.create_session(
            user_id="user_123",
            user_type=UserType.PARENT
        )
        
        # Verify Redis storage was called
        mock_redis.setex.assert_called_once()
        
        # Test session loading from Redis
        mock_redis.get.return_value = json.dumps(session.to_dict(), default=str)
        
        # Clear memory and load from Redis
        session_manager.sessions.clear()
        loaded_session = await session_manager.get_session(session.session_id)
        
        assert loaded_session is not None
        assert loaded_session.user_id == "user_123"
    
    async def test_coppa_compliance_reporting(self, session_manager):
        """Test COPPA compliance reporting."""
        # Create child sessions with and without consent
        await session_manager.create_session(
            "child_1", UserType.CHILD, user_age=7, parent_consent=True
        )
        
        # Disable COPPA mode temporarily to create session without consent
        session_manager.coppa_mode = False
        await session_manager.create_session(
            "child_2", UserType.CHILD, user_age=9, parent_consent=False
        )
        session_manager.coppa_mode = True
        
        # Get session report
        report = await session_manager.get_session_report()
        
        assert report["child_sessions"] == 2
        assert report["coppa_compliance"]["child_sessions_with_consent"] == 1
        assert report["coppa_compliance"]["child_sessions_without_consent"] == 1
    
    async def test_session_callbacks(self, session_manager):
        """Test session event callbacks."""
        created_sessions = []
        expired_sessions = []
        
        async def on_created(session):
            created_sessions.append(session)
        
        async def on_expired(session):
            expired_sessions.append(session)
        
        session_manager.on_session_created = on_created
        session_manager.on_session_expired = on_expired
        
        # Create session
        session = await session_manager.create_session("user_123", UserType.PARENT)
        
        # Expire session
        await session_manager._expire_session(session.session_id)
        
        # Verify callbacks called
        assert len(created_sessions) == 1
        assert len(expired_sessions) == 1
        assert created_sessions[0].session_id == session.session_id