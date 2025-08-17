"""Unified user management service implementation.

This service handles all user operations including creation, updates,
child management, sessions, and accessibility features.
"""

from typing import Dict, Any, Optional, List, Set

from asyncio import create_task, sleep, CancelledError, Lock, Task
import html
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.interfaces.services import IUserService
from src.interfaces.repositories import IUserRepository
from src.core.entities import User, Child
from src.core.exceptions import (
    InvalidInputError,
    UserNotFoundError,
    SessionExpiredError,
)
from src.core.value_objects.value_objects import ChildPreferences


@dataclass
class AsyncSessionData:
    session_id: str
    child_id: UUID
    status: str
    created_at: datetime
    last_activity: datetime
    device_info: Dict[str, Any] = field(default_factory=dict)
    accessibility_needs: List[str] = field(default_factory=list)
    preferences: Any = None
    activity_count: int = 0

    def is_expired(self, timeout: timedelta) -> bool:
        return (datetime.now(timezone.utc) - self.last_activity) > timeout


@dataclass
class SessionStats:
    total_sessions: int
    active_sessions: int
    total_activity_count: int
    average_session_duration: float


class SessionStatus:
    ACTIVE = "active"
    ENDED = "ended"


class UserService(IUserService):
    """Unified user service implementation."""

    def __init__(
        self,
        user_repository: IUserRepository,
        child_repository=None,
        logger=None,
        session_timeout_minutes: int = 30,
        max_sessions_per_user: int = 5,
    ):
        """Initialize user service with repositories."""
        self._user_repository = user_repository
        self._child_repository = child_repository
        self._logger = logger
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.max_sessions_per_user = max_sessions_per_user
        self.session_timeout_minutes = session_timeout_minutes
        self._sessions: Dict[str, AsyncSessionData] = {}
        self._user_sessions: Dict[UUID, Set[str]] = {}
        self._cleanup_task: Optional[Task] = None
        self._manager_lock = Lock()
        if self._logger:
            self._logger.info("UserService initialized successfully")

    # Core user management methods (IUserService interface)
    async def create_user(self, user_data: Dict[str, Any]) -> str:
        """Create new user."""
        if not user_data.get("email"):
            raise InvalidInputError("Email is required")

        existing_user = await self._user_repository.get_by_email(user_data["email"])
        if existing_user:
            raise InvalidInputError("User with this email already exists")

        user_data.update(
            {
                "id": str(uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "is_active": True,
            }
        )

        return await self._user_repository.create(user_data)

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get user by ID."""
        user = await self._user_repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")
        return user

    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user information."""
        user = await self._user_repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        return await self._user_repository.update(user_id, updates)

    async def delete_user(self, user_id: str) -> bool:
        """Delete user account."""
        user = await self._user_repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        return await self._user_repository.delete(user_id)

    async def verify_user_permissions(self, user_id: str, child_id: str) -> bool:
        """Verify user has permissions for child."""
        user = await self._user_repository.get_by_id(user_id)
        if not user:
            return False
        if not self._child_repository:
            return False
        child = await self._child_repository.get_by_id(child_id)
        return child and str(child.parent_id) == user_id

    # Extended methods from ConsolidatedUserService
    async def create_user_extended(
        self,
        email: str,
        display_name: str,
        user_type: str = "parent",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create user with extended validation."""
        if not email or "@" not in email:
            raise InvalidInputError("Valid email address is required")
        if not display_name or len(display_name.strip()) < 2:
            raise InvalidInputError("Display name must be at least 2 characters")

        try:
            existing = await self._user_repository.get_by_email(email)
            if existing:
                raise InvalidInputError(f"User with email {email} already exists")
        except UserNotFoundError:
            pass

        user = User(
            id=uuid4(),
            email=email.lower().strip(),
            display_name=display_name.strip(),
            user_type=user_type,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        await self._user_repository.create(user)
        if self._logger:
            self._logger.info(
                "Created new user",
                extra={
                    "user_id": str(user.id),
                    "email": email.replace("\n", "").replace("\r", ""),
                },
            )
        return user

    async def get_user_by_uuid(self, user_id: UUID) -> Any:
        """Get user by UUID."""
        user = await self._user_repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User not found: {user_id}")
        return user

    async def update_user_preferences(
        self, user_id: UUID, preferences: Dict[str, Any]
    ) -> Any:
        """Update user preferences."""
        user = await self.get_user_by_uuid(user_id)
        user.metadata.setdefault("preferences", {}).update(preferences)
        user.updated_at = datetime.now(timezone.utc)
        await self._user_repository.update(user)
        if self._logger:
            self._logger.info(
                "Updated preferences for user", extra={"user_id": str(user_id)}
            )
        return user

    # Child management methods
    async def create_child_profile(
        self,
        parent_id: UUID,
        name: str,
        birth_date: datetime,
        preferences: Optional[Any] = None,
    ) -> Any:
        """Create child profile."""
        if not self._child_repository:
            raise InvalidInputError("Child repository not configured")

        await self.get_user_by_uuid(parent_id)
        if not name or len(name.strip()) < 2:
            raise InvalidInputError("Child name must be at least 2 characters")

        age = (datetime.now() - birth_date).days // 365
        if age < 0 or age > 18:
            raise InvalidInputError("Child age must be between 0 and 18 years")

        child = Child(
            id=uuid4(),
            name=name.strip(),
            birth_date=birth_date,
            parent_id=parent_id,
            preferences=preferences or ChildPreferences(),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        try:
            await self._child_repository.create(child)
        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Failed to create child profile",
                    extra={"error": str(e), "parent_id": str(parent_id)},
                )
            raise
        if self._logger:
            self._logger.info(
                "Created child profile",
                extra={"child_id": str(child.id), "parent_id": str(parent_id)},
            )
        return child

    async def get_child(self, child_id: UUID) -> Any:
        """Get child by ID."""
        if not self._child_repository:
            raise InvalidInputError("Child repository not configured")

        child = await self._child_repository.get_by_id(child_id)
        if not child:
            raise UserNotFoundError(f"Child not found: {child_id}")
        return child

    async def get_children_for_parent(self, parent_id: UUID) -> List[Any]:
        """Get children for parent."""
        if not self._child_repository:
            raise InvalidInputError("Child repository not configured")

        await self.get_user_by_uuid(parent_id)
        children = await self._child_repository.get_by_parent_id(parent_id)
        return children or []

    async def update_child_preferences(self, child_id: UUID, preferences: Any) -> Any:
        """Update child preferences."""
        child = await self.get_child(child_id)
        child.preferences = preferences
        child.updated_at = datetime.now(timezone.utc)
        await self._child_repository.update(child)
        if self._logger:
            self._logger.info(
                "Updated preferences for child", extra={"child_id": str(child_id)}
            )
        return child

    # Session management methods
    async def create_session(
        self,
        child_id: UUID,
        device_info: Optional[Dict[str, Any]] = None,
        accessibility_needs: Optional[List[str]] = None,
    ) -> str:
        """Create session for child."""
        async with self._manager_lock:
            child = await self.get_child(child_id)
            user_session_ids = self._user_sessions.get(child_id, set())

            if len(user_session_ids) >= self.max_sessions_per_user:
                oldest_session_id = min(
                    user_session_ids,
                    key=lambda sid: self._sessions.get(
                        sid,
                        AsyncSessionData(
                            session_id=sid,
                            child_id=child_id,
                            status=SessionStatus.ACTIVE,
                            created_at=datetime.now(timezone.utc),
                            last_activity=datetime.now(timezone.utc),
                        ),
                    ).created_at,
                )
                await self._cleanup_session(oldest_session_id)

            session_id = f"session_{uuid4()}"
            session_data = AsyncSessionData(
                session_id=session_id,
                child_id=child_id,
                status=SessionStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc),
                device_info=device_info or {},
                accessibility_needs=accessibility_needs or [],
                preferences=child.preferences,
            )
            self._sessions[session_id] = session_data
            self._user_sessions.setdefault(child_id, set()).add(session_id)
            await self._start_cleanup_task()
            if self._logger:
                self._logger.info(
                    "Created session for child",
                    extra={
                        "session_id": html.escape(
                            session_id.replace("\n", "").replace("\r", "")
                        ),
                        "child_id": html.escape(str(child_id)),
                    },
                )
            return session_id

    async def get_session(self, session_id: str) -> AsyncSessionData:
        """Get session data."""
        session = self._sessions.get(session_id)
        if not session:
            raise SessionExpiredError(f"Session not found: {session_id}")
        if session.is_expired(self.session_timeout):
            await self._cleanup_session(session_id)
            raise SessionExpiredError(f"Session expired: {session_id}")
        return session

    async def update_session_activity(self, session_id: str) -> None:
        """Update session activity."""
        session = await self.get_session(session_id)
        session.last_activity = datetime.now(timezone.utc)
        session.activity_count += 1

    async def end_session(self, session_id: str) -> None:
        """End session."""
        await self._cleanup_session(session_id)
        if self._logger:
            self._logger.info(
                "Ended session",
                extra={
                    "session_id": html.escape(
                        session_id.replace("\n", "").replace("\r", "")
                    )
                },
            )

    async def get_session_stats(self, child_id: UUID) -> SessionStats:
        """Get session statistics."""
        user_sessions = self._user_sessions.get(child_id, set())
        active_sessions = [
            s
            for sid in user_sessions
            if (s := self._sessions.get(sid)) and not s.is_expired(self.session_timeout)
        ]
        total_activity = sum(session.activity_count for session in active_sessions)
        if active_sessions:
            avg_duration = sum(
                (datetime.now(timezone.utc) - s.created_at).total_seconds()
                for s in active_sessions
            ) / len(active_sessions)
        else:
            avg_duration = 0

        return SessionStats(
            total_sessions=len(user_sessions),
            active_sessions=len(active_sessions),
            total_activity_count=total_activity,
            average_session_duration=avg_duration,
        )

    # Accessibility methods
    async def configure_accessibility(
        self, child_id: UUID, accessibility_settings: Dict[str, Any]
    ) -> Any:
        """Configure accessibility settings."""
        child = await self.get_child(child_id)
        if not hasattr(child.preferences, "accessibility_settings"):
            child.preferences.accessibility_settings = {}
        child.preferences.accessibility_settings.update(accessibility_settings)
        child.updated_at = datetime.now(timezone.utc)
        await self._child_repository.update(child)
        if self._logger:
            self._logger.info(
                "Updated accessibility settings for child",
                extra={"child_id": str(child_id)},
            )
        return child

    # Test compatibility methods
    async def get_user_by_id(self, user_id: UUID) -> Any:
        """Get user by ID (test compatibility)."""
        return await self.get_user_by_uuid(user_id)

    async def get_user_by_email(self, email: str) -> Any:
        """Get user by email."""
        return await self._user_repository.get_by_email(email)

    async def get_children_by_parent(self, parent_id: UUID) -> List[Any]:
        """Get children by parent (test compatibility)."""
        return await self.get_children_for_parent(parent_id)

    async def get_child_by_id(self, child_id: UUID) -> Any:
        """Get child by ID (test compatibility)."""
        return await self.get_child(child_id)

    async def update_child_profile(
        self, child_id: UUID, update_data: Dict[str, Any]
    ) -> Any:
        """Update child profile."""
        existing_child = await self.get_child(child_id)
        for key, value in update_data.items():
            setattr(existing_child, key, value)
        existing_child.updated_at = datetime.now(timezone.utc)
        await self._child_repository.update(existing_child)
        return existing_child

    async def delete_child_profile(self, child_id: UUID) -> bool:
        """Delete child profile."""
        child = await self.get_child(child_id)
        try:
            return await self._child_repository.delete(child_id)
        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Failed to delete child profile",
                    extra={"error": str(e), "child_id": str(child_id)},
                    exc_info=True,
                )
            raise

    async def get_usage_summary(self, parent_id: UUID) -> Dict[str, Any]:
        """Get usage summary for parent."""
        children = await self.get_children_for_parent(parent_id)
        total_sessions = sum(
            len(self._user_sessions.get(child.id, set())) for child in children
        )
        return {"total_children": len(children), "total_sessions": total_sessions}

    async def get_child_usage_report(self, child_id: UUID) -> Dict[str, Any]:
        """Get child usage report."""
        stats = await self.get_session_stats(child_id)
        return {"child_id": str(child_id), "session_stats": stats}

    async def get_notifications(self, parent_id: UUID) -> List[Dict[str, Any]]:
        """Get notifications for parent."""
        await self.get_user_by_uuid(parent_id)

        notifications = []

        # Check for expired sessions
        children = await self.get_children_for_parent(parent_id)
        for child in children:
            child_sessions = self._user_sessions.get(child.id, set())
            expired_count = sum(
                1
                for sid in child_sessions
                if sid in self._sessions
                and self._sessions[sid].is_expired(self.session_timeout)
            )

            if expired_count > 0:
                notifications.append(
                    {
                        "type": "session_expired",
                        "child_id": str(child.id),
                        "child_name": child.name,
                        "count": expired_count,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        return notifications

    # Internal methods
    async def _start_cleanup_task(self) -> None:
        """Start cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Cleanup loop for expired sessions."""
        while True:
            try:
                await sleep(300)
                await self._cleanup_expired_sessions()
            except CancelledError:
                break
            except (CancelledError, KeyboardInterrupt):
                break
            except Exception as e:
                if self._logger:
                    self._logger.error(
                        "Session cleanup error",
                        extra={"error": str(e).replace("\n", "").replace("\r", "")},
                        exc_info=True,
                    )

    async def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions."""
        async with self._manager_lock:
            expired_sessions = [
                sid
                for sid, session in self._sessions.items()
                if session.is_expired(self.session_timeout)
            ]
            for session_id in expired_sessions:
                await self._cleanup_session(session_id)
            if expired_sessions and self._logger:
                self._logger.info(
                    "Cleaned up expired sessions",
                    extra={"count": len(expired_sessions)},
                )

    async def _cleanup_session(self, session_id: str) -> None:
        """Clean up single session."""
        session = self._sessions.pop(session_id, None)
        if session:
            user_sessions = self._user_sessions.get(session.child_id, set())
            user_sessions.discard(session_id)
            if not user_sessions:
                self._user_sessions.pop(session.child_id, None)

    async def get_service_health(self) -> Dict[str, Any]:
        """Get service health status."""
        return {
            "status": "healthy",
            "total_sessions": len(self._sessions),
            "total_users_with_sessions": len(self._user_sessions),
            "session_timeout_minutes": self.session_timeout_minutes,
            "max_sessions_per_user": self.max_sessions_per_user,
            "cleanup_task_running": self._cleanup_task is not None
            and not self._cleanup_task.done(),
        }

    async def stop_cleanup_task(self) -> None:
        """Stop cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except CancelledError:
                pass
