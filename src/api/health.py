"""Health check endpoints for notification service."""

from fastapi import APIRouter, Depends
from typing import Dict, Any

from src.application.services.notification.notification_service_main import (
    ProductionNotificationService,
    create_production_notification_service
)

router = APIRouter(prefix="/health", tags=["health"])


async def get_notification_service() -> ProductionNotificationService:
    """Dependency to get notification service."""
    # This would typically come from dependency injection container
    config = {"redis_url": "redis://localhost:6379"}
    return create_production_notification_service(config)


@router.get("/")
async def health_check() -> Dict[str, str]:
    """Basic health check."""
    return {"status": "healthy", "service": "notification"}


@router.get("/detailed")
async def detailed_health_check(
    service: ProductionNotificationService = Depends(get_notification_service)
) -> Dict[str, Any]:
    """Detailed health check with service status."""
    return await service.health_check()


@router.get("/metrics")
async def get_metrics(
    service: ProductionNotificationService = Depends(get_notification_service)
) -> Dict[str, Any]:
    """Get basic metrics."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return {"metrics": generate_latest().decode('utf-8')}
    except ImportError:
        # Fallback metrics
        health = await service.health_check()
        return {
            "pending_notifications": health.get("pending_notifications", 0),
            "channels_healthy": sum(
                1 for ch in health.get("channels", {}).values() 
                if ch.get("status") == "healthy"
            ),
            "total_channels": len(health.get("channels", {}))
        }
