"""Drain manager for orchestrating instance drain mode and readiness gating."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


@dataclass
class DrainStatus:
    """Lightweight drain state snapshot for reporting."""

    is_draining: bool
    started_at: Optional[datetime] = None
    initiated_by: Optional[str] = None
    reason: Optional[str] = None
    max_session_age_seconds: Optional[int] = None
    notes: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "is_draining": self.is_draining,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "initiated_by": self.initiated_by,
            "reason": self.reason,
            "max_session_age_seconds": self.max_session_age_seconds,
            "notes": self.notes,
        }
        return {k: v for k, v in payload.items() if v is not None}


class DrainManager:
    """Coordinate drain mode for a single application instance."""

    def __init__(
        self,
        *,
        instance_id: str,
        default_max_session_age_seconds: int = 900,
    ) -> None:
        self._instance_id = instance_id or "app"
        self._default_max_age = max(60, int(default_max_session_age_seconds))
        self._lock = asyncio.Lock()
        self._status = DrainStatus(is_draining=False)

    @property
    def instance_id(self) -> str:
        return self._instance_id

    async def start_drain(
        self,
        *,
        initiated_by: str,
        reason: Optional[str] = None,
        max_session_age_seconds: Optional[int] = None,
    ) -> DrainStatus:
        async with self._lock:
            if self._status.is_draining:
                return self._status

            ttl = max_session_age_seconds or self._default_max_age
            self._status = DrainStatus(
                is_draining=True,
                started_at=datetime.utcnow(),
                initiated_by=initiated_by,
                reason=reason,
                max_session_age_seconds=ttl,
            )
            return self._status

    async def end_drain(self, *, initiated_by: str, notes: Optional[Dict[str, Any]] = None) -> DrainStatus:
        async with self._lock:
            if not self._status.is_draining:
                return self._status

            self._status = DrainStatus(
                is_draining=False,
                notes={"ended_by": initiated_by, **(notes or {})},
            )
            return self._status

    async def extend(self, *, max_session_age_seconds: int) -> DrainStatus:
        async with self._lock:
            if not self._status.is_draining:
                return self._status
            ttl = max(60, int(max_session_age_seconds))
            self._status.max_session_age_seconds = ttl
            return self._status

    async def annotate(self, *, notes: Dict[str, Any]) -> DrainStatus:
        async with self._lock:
            if not self._status.is_draining:
                return self._status
            self._status.notes.update(notes)
            return self._status

    def is_draining(self) -> bool:
        return self._status.is_draining

    def can_accept_new_sessions(self) -> bool:
        return not self._status.is_draining

    def get_status(self) -> DrainStatus:
        return self._status

    def deadline(self) -> Optional[datetime]:
        if not self._status.is_draining or not self._status.started_at:
            return None
        ttl = self._status.max_session_age_seconds or self._default_max_age
        return self._status.started_at + timedelta(seconds=ttl)