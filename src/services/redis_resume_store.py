"""
Redis-backed session resume store for ESP32 WebSocket messaging.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


@dataclass
class ResumeMessage:
    """Envelope for a persisted outbound message."""

    session_id: str
    device_id: str
    seq: int
    payload: Dict[str, Any]
    recorded_at: str
    classification: str


class RedisSessionResumeStore:
    """Redis-backed store for delivering missed messages after reconnects."""

    def __init__(
        self,
        redis_url: str,
        *,
        prefix: str = "esp32:resume",
        ttl_seconds: int = 900,
        max_messages_per_session: int = 200,
        max_sessions: int = 1000,
        on_messages_dropped: Optional[Callable[[int], None]] = None,
    ) -> None:
        self._redis = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        self._prefix = prefix.rstrip(":")
        self._ttl = int(ttl_seconds)
        self._max_messages = max(10, int(max_messages_per_session))
        self._max_sessions = max(1, int(max_sessions))
        self._on_messages_dropped = on_messages_dropped
        self._logger = logging.getLogger(f"{__name__}.RedisSessionResumeStore")
        self._dropped_messages_count = 0

    def _state_key(self, session_id: str) -> str:
        return f"{self._prefix}:state:{session_id}"

    def _messages_key(self, session_id: str) -> str:
        return f"{self._prefix}:msgs:{session_id}"

    def _device_index_key(self, device_id: str) -> str:
        return f"{self._prefix}:device:{device_id}"

    async def register_session(self, session_id: str, device_id: str) -> None:
        try:
            pipe = self._redis.pipeline()
            pipe.hset(self._state_key(session_id), mapping={
                "session_id": session_id,
                "device_id": device_id,
                "last_seq": 0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            pipe.expire(self._state_key(session_id), self._ttl)
            pipe.set(self._device_index_key(device_id), session_id, ex=self._ttl)
            await pipe.execute()
        except Exception as exc:
            self._logger.error("Failed to register resume session: %s", exc)

    async def append(
        self,
        *,
        session_id: str,
        device_id: str,
        seq: int,
        classification: str,
        payload: Dict[str, Any],
    ) -> None:
        """Append an outbound message to the resume buffer."""
        envelope = ResumeMessage(
            session_id=session_id,
            device_id=device_id,
            seq=seq,
            payload=payload,
            recorded_at=datetime.now(timezone.utc).isoformat(),
            classification=classification,
        )
        state_key = self._state_key(session_id)
        messages_key = self._messages_key(session_id)
        try:
            pipe = self._redis.pipeline()
            pipe.hset(state_key, mapping={
                "session_id": session_id,
                "device_id": device_id,
                "last_seq": seq,
                "updated_at": envelope.recorded_at,
            })
            pipe.expire(state_key, self._ttl)
            pipe.zadd(messages_key, {json.dumps(envelope.__dict__): seq})
            pipe.expire(messages_key, self._ttl)
            pipe.zcard(messages_key)
            results = await pipe.execute()
            message_count = results[-1]
            if message_count and message_count > self._max_messages:
                trim_count = message_count - self._max_messages
                removed = await self._redis.zremrangebyrank(messages_key, 0, trim_count - 1)
                if removed and self._on_messages_dropped:
                    self._dropped_messages_count += int(removed)
                    self._on_messages_dropped(int(removed))
        except Exception as exc:
            self._logger.error("Failed to append resume message: %s", exc)

    async def acknowledge(self, session_id: str, ack_seq: int) -> None:
        """Trim persisted messages up to ack_seq inclusive."""
        try:
            state_key = self._state_key(session_id)
            updated = datetime.now(timezone.utc).isoformat()
            pipe = self._redis.pipeline()
            pipe.hset(state_key, mapping={"updated_at": updated, "ack_seq": ack_seq})
            pipe.expire(state_key, self._ttl)
            pipe.zremrangebyscore(self._messages_key(session_id), 0, ack_seq)
            await pipe.execute()
        except Exception as exc:
            self._logger.warning("Failed to acknowledge resume messages: %s", exc)

    async def get_backlog(
        self,
        session_id: str,
        *,
        after_seq: int,
        limit: Optional[int] = None,
    ) -> List[ResumeMessage]:
        """Fetch backlog messages newer than after_seq."""
        try:
            limit = limit or self._max_messages
            raw_messages = await self._redis.zrangebyscore(
                self._messages_key(session_id),
                min=after_seq + 1,
                max="+inf",
                start=0,
                num=limit,
            )
            messages: List[ResumeMessage] = []
            for raw in raw_messages:
                try:
                    data = json.loads(raw)
                    messages.append(ResumeMessage(**data))
                except Exception:
                    continue
            return messages
        except Exception as exc:
            self._logger.error("Failed to fetch backlog: %s", exc)
            return []

    async def load_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        try:
            data = await self._redis.hgetall(self._state_key(session_id))
            return data or None
        except Exception as exc:
            self._logger.error("Failed to load session state: %s", exc)
            return None

    async def resolve_device_session(self, device_id: str) -> Optional[str]:
        try:
            return await self._redis.get(self._device_index_key(device_id))
        except Exception as exc:
            self._logger.error("Failed to resolve device session: %s", exc)
            return None

    async def purge_session(self, session_id: str) -> None:
        try:
            state_key = self._state_key(session_id)
            messages_key = self._messages_key(session_id)
            pipe = self._redis.pipeline()
            pipe.delete(state_key)
            pipe.delete(messages_key)
            await pipe.execute()
        except Exception as exc:
            self._logger.warning("Failed to purge resume session: %s", exc)

    async def offer_resume(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Check if device has resumable session and return offer."""
        try:
            session_id = await self.resolve_device_session(device_id)
            if not session_id:
                return None
            
            state = await self.load_session_state(session_id)
            if not state:
                return None
            
            last_seq = int(state.get("last_seq", 0))
            ack_seq = int(state.get("ack_seq", 0))
            missed_count = max(0, last_seq - ack_seq)
            
            return {
                "session_id": session_id,
                "last_seq": last_seq,
                "ack_seq": ack_seq,
                "missed_count": missed_count,
                "can_resume": missed_count <= self._max_messages
            }
        except Exception as exc:
            self._logger.error("Failed to offer resume: %s", exc)
            return None

    async def get_metrics(self) -> Dict[str, Any]:
        """Get resume store metrics."""
        try:
            pattern = f"{self._prefix}:state:*"
            keys = await self._redis.keys(pattern)
            active_sessions = len(keys)
            
            return {
                "active_sessions": active_sessions,
                "max_sessions": self._max_sessions,
                "max_messages_per_session": self._max_messages,
                "ttl_seconds": self._ttl,
                "dropped_messages_total": self._dropped_messages_count
            }
        except Exception as exc:
            self._logger.error("Failed to get metrics: %s", exc)
            return {}

    async def close(self) -> None:
        try:
            await self._redis.close()
        except Exception:
            pass