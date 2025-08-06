"""
ChildMonitor: Advanced child monitoring with real-time alerts and behavioral analytics.

Status types: ACTIVE, IDLE, OFFLINE, ALERT, BLOCKED
"""
import re
import logging
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from src.shared.dto.child_data import ChildData

logger = logging.getLogger(__name__)

class AlertType(Enum):
    SAFETY_VIOLATION = "safety_violation"
    UNUSUAL_ACTIVITY = "unusual_activity"
    EXTENDED_SESSION = "extended_session"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    BEHAVIORAL_CHANGE = "behavioral_change"

@dataclass
class RealTimeAlert:
    child_id: str
    alert_type: AlertType
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    message: str
    timestamp: datetime
    metadata: Dict[str, Any]

@dataclass
class BehaviorPattern:
    child_id: str
    pattern_type: str
    confidence: float
    description: str
    detected_at: datetime
    indicators: List[str]

class ChildMonitorError(Exception):
    pass

class ChildMonitor:
    def __init__(self, safety_service, auth_service=None):
        self.safety_service = safety_service
        self.auth_service = auth_service
        self._cache: Dict[str, tuple] = {}  # (data, timestamp)
        self._cache_ttl = 30  # seconds
        
        # Real-time monitoring
        self._alert_callbacks: List[Callable] = []
        self._active_sessions: Dict[str, datetime] = {}
        self._behavior_history: Dict[str, List[Dict]] = {}
        self._alert_thresholds = {
            "session_duration": 120,  # minutes
            "safety_score_threshold": 0.7,
            "unusual_activity_threshold": 0.8
        }

    def _validate_child_id(self, child_id: str) -> str:
        if not child_id or not isinstance(child_id, str):
            raise ChildMonitorError("child_id must be non-empty string")
        
        clean_id = child_id.strip()
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', clean_id, re.I):
            raise ChildMonitorError("child_id must be valid UUID format")
        
        return clean_id

    async def _check_access(self, child_id: str, user_id: str = None) -> bool:
        if not self.auth_service or not user_id:
            return True
        return await self.auth_service.can_access_child(user_id, child_id)

    def _get_cached_status(self, child_id: str) -> Optional[ChildData]:
        if child_id in self._cache:
            data, timestamp = self._cache[child_id]
            if datetime.now() - timestamp < timedelta(seconds=self._cache_ttl):
                return data
            del self._cache[child_id]
        return None

    def add_alert_callback(self, callback: Callable[[RealTimeAlert], None]):
        """Add callback for real-time alerts."""
        self._alert_callbacks.append(callback)
    
    async def _trigger_alert(self, alert: RealTimeAlert):
        """Trigger real-time alert to all callbacks."""
        logger.warning(f"Alert triggered: {alert.alert_type.value} for child {alert.child_id}")
        for callback in self._alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    async def _analyze_behavior(self, child_id: str, activity_data: Dict) -> Optional[BehaviorPattern]:
        """Analyze child behavior patterns."""
        if child_id not in self._behavior_history:
            self._behavior_history[child_id] = []
        
        history = self._behavior_history[child_id]
        history.append({**activity_data, "timestamp": datetime.now()})
        
        # Keep only last 50 activities
        if len(history) > 50:
            history.pop(0)
        
        # Simple behavioral analysis
        recent_activities = [h for h in history if datetime.now() - h["timestamp"] < timedelta(hours=24)]
        
        if len(recent_activities) >= 5:
            avg_safety_score = sum(a.get("safety_score", 1.0) for a in recent_activities) / len(recent_activities)
            
            if avg_safety_score < self._alert_thresholds["safety_score_threshold"]:
                return BehaviorPattern(
                    child_id=child_id,
                    pattern_type="declining_safety",
                    confidence=1.0 - avg_safety_score,
                    description=f"Safety scores declining (avg: {avg_safety_score:.2f})",
                    detected_at=datetime.now(),
                    indicators=["low_safety_scores", "pattern_detected"]
                )
        
        return None
    
    async def _check_session_duration(self, child_id: str):
        """Check for extended session alerts."""
        if child_id in self._active_sessions:
            session_start = self._active_sessions[child_id]
            duration = (datetime.now() - session_start).total_seconds() / 60
            
            if duration > self._alert_thresholds["session_duration"]:
                alert = RealTimeAlert(
                    child_id=child_id,
                    alert_type=AlertType.EXTENDED_SESSION,
                    severity="MEDIUM",
                    message=f"Extended session detected: {duration:.0f} minutes",
                    timestamp=datetime.now(),
                    metadata={"duration_minutes": duration}
                )
                await self._trigger_alert(alert)
    
    async def get_child_status(self, child_id: str, user_id: str = None) -> ChildData:
        """Get child status with advanced monitoring."""
        clean_id = self._validate_child_id(child_id)
        
        # Check cache first
        cached = self._get_cached_status(clean_id)
        if cached:
            logger.debug(f"Cache hit for child {clean_id}")
            return cached
        
        # Check access permissions
        if not await self._check_access(clean_id, user_id):
            logger.warning(f"Access denied for child {clean_id} by user {user_id}")
            raise ChildMonitorError("Access denied")
        
        try:
            logger.info(f"Fetching status for child {clean_id}")
            status = await self.safety_service.get_child_status(clean_id)
            
            if not status:
                raise ChildMonitorError(f"Child {clean_id} not found")
            
            # Track active session
            if status.status == "ACTIVE" and clean_id not in self._active_sessions:
                self._active_sessions[clean_id] = datetime.now()
            elif status.status != "ACTIVE" and clean_id in self._active_sessions:
                del self._active_sessions[clean_id]
            
            # Behavioral analysis
            activity_data = {
                "status": status.status,
                "safety_score": getattr(status, "safety_score", 1.0),
                "activity_type": getattr(status, "current_activity", "unknown")
            }
            
            behavior_pattern = await self._analyze_behavior(clean_id, activity_data)
            if behavior_pattern:
                alert = RealTimeAlert(
                    child_id=clean_id,
                    alert_type=AlertType.BEHAVIORAL_CHANGE,
                    severity="HIGH",
                    message=behavior_pattern.description,
                    timestamp=datetime.now(),
                    metadata={"pattern": behavior_pattern.pattern_type, "confidence": behavior_pattern.confidence}
                )
                await self._trigger_alert(alert)
            
            # Check session duration
            await self._check_session_duration(clean_id)
            
            # Safety violation check
            if hasattr(status, "safety_score") and status.safety_score < 0.5:
                alert = RealTimeAlert(
                    child_id=clean_id,
                    alert_type=AlertType.SAFETY_VIOLATION,
                    severity="CRITICAL",
                    message=f"Safety violation detected (score: {status.safety_score})",
                    timestamp=datetime.now(),
                    metadata={"safety_score": status.safety_score}
                )
                await self._trigger_alert(alert)
            
            # Cache the result
            self._cache[clean_id] = (status, datetime.now())
            logger.debug(f"Cached status for child {clean_id}")
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get status for child {clean_id}: {e}")
            if isinstance(e, ChildMonitorError):
                raise
            raise ChildMonitorError(f"Service unavailable: {str(e)}")
    
    async def get_behavior_analytics(self, child_id: str) -> Dict[str, Any]:
        """Get behavioral analytics for child."""
        clean_id = self._validate_child_id(child_id)
        history = self._behavior_history.get(clean_id, [])
        
        if not history:
            return {"status": "insufficient_data", "activities_count": 0}
        
        recent = [h for h in history if datetime.now() - h["timestamp"] < timedelta(days=7)]
        
        return {
            "total_activities": len(history),
            "recent_activities": len(recent),
            "avg_safety_score": sum(h.get("safety_score", 1.0) for h in recent) / max(1, len(recent)),
            "session_count": len([h for h in recent if h.get("status") == "ACTIVE"]),
            "last_activity": max(h["timestamp"] for h in history) if history else None
        }
    
    async def get_active_alerts(self, child_id: str) -> List[RealTimeAlert]:
        """Get active alerts for child (mock implementation)."""
        # In production, this would query a persistent alert store
        alerts = []
        
        # Check for extended session
        if child_id in self._active_sessions:
            duration = (datetime.now() - self._active_sessions[child_id]).total_seconds() / 60
            if duration > 60:  # 1 hour
                alerts.append(RealTimeAlert(
                    child_id=child_id,
                    alert_type=AlertType.EXTENDED_SESSION,
                    severity="MEDIUM",
                    message=f"Active session: {duration:.0f} minutes",
                    timestamp=datetime.now(),
                    metadata={"duration": duration}
                ))
        
        return alerts
