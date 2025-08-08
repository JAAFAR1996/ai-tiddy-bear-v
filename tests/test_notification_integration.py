"""Integration tests for notification service."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.application.services.notification.notification_service import (
    ProductionNotificationService,
    NotificationRequest,
    NotificationRecipient,
    NotificationTemplate,
    NotificationChannel,
    NotificationStatus,
    ConsoleAlertService,
    RateLimiter,
)
from src.core.entities.subscription import NotificationType, NotificationPriority


class MockProvider:
    """Mock provider for testing."""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.sent_notifications = []
    
    async def send(self, notification_id, recipient, template, priority):
        self.sent_notifications.append({
            'id': notification_id,
            'recipient': recipient,
            'template': template
        })
        
        if self.should_fail:
            return {"status": NotificationStatus.FAILED.value, "error": "Mock failure"}
        return {"status": NotificationStatus.SENT.value, "provider": "mock"}


class MockAlertService:
    """Mock alert service for testing."""
    
    def __init__(self):
        self.alerts = []
    
    async def send_alert(self, message, context):
        self.alerts.append({"message": message, "context": context})


@pytest.fixture
def mock_config():
    return {"redis_url": "redis://localhost:6379"}


@pytest.fixture
def notification_request():
    return NotificationRequest(
        notification_type=NotificationType.SAFETY_ALERT,
        priority=NotificationPriority.HIGH,
        recipient=NotificationRecipient(
            user_id="test_user_123",
            email="test@example.com",
            phone="+1234567890"
        ),
        template=NotificationTemplate(
            title="Test Alert",
            body="Test message"
        ),
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS]
    )


@pytest.mark.asyncio
async def test_multi_channel_notification_success(mock_config, notification_request):
    """Test successful multi-channel notification."""
    # Setup
    email_provider = MockProvider()
    sms_provider = MockProvider()
    
    providers = {
        NotificationChannel.EMAIL: email_provider,
        NotificationChannel.SMS: sms_provider
    }
    
    service = ProductionNotificationService(
        config=mock_config,
        delivery_providers=providers
    )
    
    # Execute
    result = await service.send_notification(notification_request)
    
    # Assert
    assert result["status"] == "processed"
    assert len(result["delivery_results"]) == 2
    assert result["delivery_results"]["email"]["status"] == NotificationStatus.SENT.value
    assert result["delivery_results"]["sms"]["status"] == NotificationStatus.SENT.value
    
    # Verify providers were called
    assert len(email_provider.sent_notifications) == 1
    assert len(sms_provider.sent_notifications) == 1


@pytest.mark.asyncio
async def test_all_channels_fail_triggers_alert(mock_config, notification_request):
    """Test that failing all channels triggers critical alert."""
    # Setup
    email_provider = MockProvider(should_fail=True)
    sms_provider = MockProvider(should_fail=True)
    alert_service = MockAlertService()
    
    providers = {
        NotificationChannel.EMAIL: email_provider,
        NotificationChannel.SMS: sms_provider
    }
    
    service = ProductionNotificationService(
        config=mock_config,
        delivery_providers=providers,
        alert_service=alert_service
    )
    
    # Execute
    result = await service.send_notification(notification_request)
    
    # Assert
    assert result["status"] == "processed"
    assert all(r["status"] == NotificationStatus.FAILED.value for r in result["delivery_results"].values())
    
    # Verify alert was sent
    assert len(alert_service.alerts) == 1
    assert "All channels failed" in alert_service.alerts[0]["message"]


@pytest.mark.asyncio
async def test_rate_limit_exceeded(mock_config, notification_request):
    """Test rate limiting logic."""
    # Setup
    rate_limiter = RateLimiter()
    # Mock the rate limiter to return False (rate limit exceeded)
    rate_limiter.check_rate_limit = AsyncMock(return_value=False)
    
    service = ProductionNotificationService(
        config=mock_config,
        rate_limiter=rate_limiter
    )
    
    # Execute
    result = await service.send_notification(notification_request)
    
    # Assert
    assert result["status"] == "processed"
    assert all(r["status"] == NotificationStatus.FAILED.value for r in result["delivery_results"].values())
    assert all("Rate limit exceeded" in r["error"] for r in result["delivery_results"].values())


@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint."""
    # Setup
    service = ProductionNotificationService(config={})
    
    # Execute
    health = await service.health_check()
    
    # Assert
    assert health["status"] in ["healthy", "degraded"]
    assert "timestamp" in health
    assert "pending_notifications" in health
    assert "channels" in health
    assert len(health["channels"]) > 0


@pytest.mark.asyncio
async def test_rate_limiter_memory_fallback():
    """Test rate limiter memory fallback."""
    # Setup - no Redis
    rate_limiter = RateLimiter(redis_url="invalid://url")
    
    # Execute multiple requests
    user_id = "test_user"
    channel = "email"
    
    # Should allow first few requests
    for i in range(5):
        result = await rate_limiter.check_rate_limit(user_id, channel)
        assert result is True
    
    # Should start rate limiting after limit
    for i in range(10):
        result = await rate_limiter.check_rate_limit(user_id, channel)
        # Some should be rate limited
        if i > 5:
            assert result is False


if __name__ == "__main__":
    pytest.main([__file__])