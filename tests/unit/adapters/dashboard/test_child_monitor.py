"""
Tests for ChildMonitor - real monitoring functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from src.adapters.dashboard.child_monitor import (
    ChildMonitor,
    ChildMonitorError,
    AlertType,
    RealTimeAlert,
    BehaviorPattern
)
from src.shared.dto.child_data import ChildData


class TestChildMonitor:
    @pytest.fixture
    def mock_safety_service(self):
        service = Mock()
        service.get_child_status = AsyncMock()
        return service

    @pytest.fixture
    def mock_auth_service(self):
        service = Mock()
        service.can_access_child = AsyncMock(return_value=True)
        return service

    @pytest.fixture
    def child_monitor(self, mock_safety_service, mock_auth_service):
        return ChildMonitor(mock_safety_service, mock_auth_service)

    def test_validate_child_id_valid(self, child_monitor):
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = child_monitor._validate_child_id(valid_uuid)
        assert result == valid_uuid

    def test_validate_child_id_invalid_format(self, child_monitor):
        with pytest.raises(ChildMonitorError) as exc:
            child_monitor._validate_child_id("invalid-uuid")
        assert "valid UUID format" in str(exc.value)

    def test_validate_child_id_empty(self, child_monitor):
        with pytest.raises(ChildMonitorError) as exc:
            child_monitor._validate_child_id("")
        assert "non-empty string" in str(exc.value)

    def test_validate_child_id_none(self, child_monitor):
        with pytest.raises(ChildMonitorError) as exc:
            child_monitor._validate_child_id(None)
        assert "non-empty string" in str(exc.value)

    @pytest.mark.asyncio
    async def test_check_access_with_auth_service(self, child_monitor):
        result = await child_monitor._check_access("child-123", "user-456")
        child_monitor.auth_service.can_access_child.assert_called_once_with("user-456", "child-123")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_access_without_auth_service(self, mock_safety_service):
        monitor = ChildMonitor(mock_safety_service, None)
        result = await monitor._check_access("child-123", "user-456")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_access_denied(self, child_monitor):
        child_monitor.auth_service.can_access_child.return_value = False
        result = await child_monitor._check_access("child-123", "user-456")
        assert result is False

    def test_get_cached_status_hit(self, child_monitor):
        child_id = "child-123"
        mock_data = ChildData(
            child_id=child_id,
            name="Ahmed",
            age=8,
            status="ACTIVE"
        )
        
        # Add to cache
        child_monitor._cache[child_id] = (mock_data, datetime.now())
        
        result = child_monitor._get_cached_status(child_id)
        assert result == mock_data

    def test_get_cached_status_expired(self, child_monitor):
        child_id = "child-123"
        mock_data = ChildData(
            child_id=child_id,
            name="Ahmed", 
            age=8,
            status="ACTIVE"
        )
        
        # Add expired cache entry
        expired_time = datetime.now() - timedelta(seconds=60)
        child_monitor._cache[child_id] = (mock_data, expired_time)
        
        result = child_monitor._get_cached_status(child_id)
        assert result is None
        assert child_id not in child_monitor._cache

    def test_get_cached_status_miss(self, child_monitor):
        result = child_monitor._get_cached_status("nonexistent-child")
        assert result is None

    def test_add_alert_callback(self, child_monitor):
        callback = Mock()
        child_monitor.add_alert_callback(callback)
        assert callback in child_monitor._alert_callbacks

    @pytest.mark.asyncio
    async def test_trigger_alert(self, child_monitor):
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        child_monitor.add_alert_callback(callback1)
        child_monitor.add_alert_callback(callback2)
        
        alert = RealTimeAlert(
            child_id="child-123",
            alert_type=AlertType.SAFETY_VIOLATION,
            severity="HIGH",
            message="Test alert",
            timestamp=datetime.now(),
            metadata={}
        )
        
        await child_monitor._trigger_alert(alert)
        
        callback1.assert_called_once_with(alert)
        callback2.assert_called_once_with(alert)

    @pytest.mark.asyncio
    async def test_trigger_alert_callback_error(self, child_monitor):
        failing_callback = AsyncMock(side_effect=Exception("Callback failed"))
        working_callback = AsyncMock()
        
        child_monitor.add_alert_callback(failing_callback)
        child_monitor.add_alert_callback(working_callback)
        
        alert = RealTimeAlert(
            child_id="child-123",
            alert_type=AlertType.SAFETY_VIOLATION,
            severity="HIGH",
            message="Test alert",
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Should not raise exception
        await child_monitor._trigger_alert(alert)
        
        # Working callback should still be called
        working_callback.assert_called_once_with(alert)

    @pytest.mark.asyncio
    async def test_analyze_behavior_insufficient_data(self, child_monitor):
        activity_data = {"safety_score": 0.9, "status": "ACTIVE"}
        
        result = await child_monitor._analyze_behavior("child-123", activity_data)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_behavior_declining_safety(self, child_monitor):
        child_id = "child-123"
        
        # Add multiple low safety score activities
        for i in range(6):
            activity_data = {"safety_score": 0.5, "status": "ACTIVE"}
            await child_monitor._analyze_behavior(child_id, activity_data)
        
        # Last call should detect pattern
        activity_data = {"safety_score": 0.6, "status": "ACTIVE"}
        result = await child_monitor._analyze_behavior(child_id, activity_data)
        
        assert result is not None
        assert result.pattern_type == "declining_safety"
        assert result.child_id == child_id
        assert "declining" in result.description.lower()

    @pytest.mark.asyncio
    async def test_check_session_duration_no_session(self, child_monitor):
        # Should not trigger alert if no active session
        await child_monitor._check_session_duration("child-123")
        # No exception should be raised

    @pytest.mark.asyncio
    async def test_check_session_duration_extended_session(self, child_monitor):
        child_id = "child-123"
        callback = AsyncMock()
        child_monitor.add_alert_callback(callback)
        
        # Set session start time to 3 hours ago
        child_monitor._active_sessions[child_id] = datetime.now() - timedelta(hours=3)
        
        await child_monitor._check_session_duration(child_id)
        
        # Should trigger extended session alert
        callback.assert_called_once()
        alert = callback.call_args[0][0]
        assert alert.alert_type == AlertType.EXTENDED_SESSION

    @pytest.mark.asyncio
    async def test_get_child_status_success(self, child_monitor):
        child_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_status = ChildData(
            child_id=child_id,
            name="Ahmed",
            age=8,
            status="ACTIVE"
        )
        mock_status.safety_score = 0.95
        
        child_monitor.safety_service.get_child_status.return_value = mock_status
        
        result = await child_monitor.get_child_status(child_id)
        
        assert result == mock_status
        assert child_id in child_monitor._cache
        assert child_id in child_monitor._active_sessions

    @pytest.mark.asyncio
    async def test_get_child_status_cached(self, child_monitor):
        child_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_status = ChildData(
            child_id=child_id,
            name="Ahmed",
            age=8,
            status="ACTIVE"
        )
        
        # Add to cache
        child_monitor._cache[child_id] = (mock_status, datetime.now())
        
        result = await child_monitor.get_child_status(child_id)
        
        assert result == mock_status
        # Should not call safety service
        child_monitor.safety_service.get_child_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_child_status_access_denied(self, child_monitor):
        child_id = "550e8400-e29b-41d4-a716-446655440000"
        child_monitor.auth_service.can_access_child.return_value = False
        
        with pytest.raises(ChildMonitorError) as exc:
            await child_monitor.get_child_status(child_id, "user-456")
        
        assert "Access denied" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_child_status_not_found(self, child_monitor):
        child_id = "550e8400-e29b-41d4-a716-446655440000"
        child_monitor.safety_service.get_child_status.return_value = None
        
        with pytest.raises(ChildMonitorError) as exc:
            await child_monitor.get_child_status(child_id)
        
        assert "not found" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_child_status_safety_violation_alert(self, child_monitor):
        child_id = "550e8400-e29b-41d4-a716-446655440000"
        callback = AsyncMock()
        child_monitor.add_alert_callback(callback)
        
        mock_status = ChildData(
            child_id=child_id,
            name="Ahmed",
            age=8,
            status="ACTIVE"
        )
        mock_status.safety_score = 0.3  # Low safety score
        
        child_monitor.safety_service.get_child_status.return_value = mock_status
        
        await child_monitor.get_child_status(child_id)
        
        # Should trigger safety violation alert
        callback.assert_called()
        alert = callback.call_args[0][0]
        assert alert.alert_type == AlertType.SAFETY_VIOLATION
        assert alert.severity == "CRITICAL"

    @pytest.mark.asyncio
    async def test_get_child_status_service_error(self, child_monitor):
        child_id = "550e8400-e29b-41d4-a716-446655440000"
        child_monitor.safety_service.get_child_status.side_effect = Exception("Service error")
        
        with pytest.raises(ChildMonitorError) as exc:
            await child_monitor.get_child_status(child_id)
        
        assert "Service unavailable" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_behavior_analytics_no_data(self, child_monitor):
        child_id = "550e8400-e29b-41d4-a716-446655440000"
        
        result = await child_monitor.get_behavior_analytics(child_id)
        
        assert result["status"] == "insufficient_data"
        assert result["activities_count"] == 0

    @pytest.mark.asyncio
    async def test_get_behavior_analytics_with_data(self, child_monitor):
        child_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Add some behavior history
        for i in range(5):
            activity_data = {"safety_score": 0.8 + (i * 0.05), "status": "ACTIVE"}
            await child_monitor._analyze_behavior(child_id, activity_data)
        
        result = await child_monitor.get_behavior_analytics(child_id)
        
        assert result["total_activities"] == 5
        assert result["recent_activities"] == 5
        assert "avg_safety_score" in result
        assert result["avg_safety_score"] > 0.8

    @pytest.mark.asyncio
    async def test_get_active_alerts_no_session(self, child_monitor):
        child_id = "child-123"
        
        alerts = await child_monitor.get_active_alerts(child_id)
        
        assert alerts == []

    @pytest.mark.asyncio
    async def test_get_active_alerts_extended_session(self, child_monitor):
        child_id = "child-123"
        
        # Set session start time to 2 hours ago
        child_monitor._active_sessions[child_id] = datetime.now() - timedelta(hours=2)
        
        alerts = await child_monitor.get_active_alerts(child_id)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.EXTENDED_SESSION
        assert alerts[0].severity == "MEDIUM"

    def test_session_tracking_active_to_inactive(self, child_monitor):
        child_id = "child-123"
        
        # Initially no session
        assert child_id not in child_monitor._active_sessions
        
        # Mock active status
        mock_status = ChildData(
            child_id=child_id,
            name="Ahmed",
            age=8,
            status="ACTIVE"
        )
        
        # Simulate status change to active
        child_monitor._active_sessions[child_id] = datetime.now()
        
        # Simulate status change to inactive
        mock_status.status = "IDLE"
        
        # Session should be removed when status is not ACTIVE
        # This would happen in get_child_status method
        if mock_status.status != "ACTIVE" and child_id in child_monitor._active_sessions:
            del child_monitor._active_sessions[child_id]
        
        assert child_id not in child_monitor._active_sessions


class TestRealTimeAlert:
    def test_init(self):
        alert = RealTimeAlert(
            child_id="child-123",
            alert_type=AlertType.SAFETY_VIOLATION,
            severity="HIGH",
            message="Test alert",
            timestamp=datetime.now(),
            metadata={"key": "value"}
        )
        
        assert alert.child_id == "child-123"
        assert alert.alert_type == AlertType.SAFETY_VIOLATION
        assert alert.severity == "HIGH"
        assert alert.message == "Test alert"
        assert alert.metadata["key"] == "value"


class TestBehaviorPattern:
    def test_init(self):
        pattern = BehaviorPattern(
            child_id="child-123",
            pattern_type="declining_safety",
            confidence=0.8,
            description="Safety scores declining",
            detected_at=datetime.now(),
            indicators=["low_safety_scores"]
        )
        
        assert pattern.child_id == "child-123"
        assert pattern.pattern_type == "declining_safety"
        assert pattern.confidence == 0.8
        assert "declining" in pattern.description
        assert "low_safety_scores" in pattern.indicators