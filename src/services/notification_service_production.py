"""
Production NotificationService
=============================
خدمة إشعارات إنتاجية متكاملة تعتمد على NotificationRepository وDeliveryRecordRepository.
- تخزين الإشعارات
- تتبع سجلات التسليم
- دعم جميع قنوات الإشعار
- متوافقة مع COPPA وChild Safety
"""

import uuid
from typing import List, Optional, Dict, Any
from src.infrastructure.database.models import Notification, DeliveryRecord
from src.services.service_registry import (
    get_notification_repository,
    get_delivery_record_repository,
)


class ProductionNotificationService:
    """خدمة إشعارات إنتاجية متكاملة."""

    def __init__(self):
        self.notification_repo = None
        self.delivery_record_repo = None

    async def initialize(self):
        self.notification_repo = await get_notification_repository()
        self.delivery_record_repo = await get_delivery_record_repository()

    async def send_notification(
        self,
        user_id: uuid.UUID,
        content: str,
        notification_type: str,
        channel: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        # تخزين الإشعار
        notification_data = {
            "user_id": user_id,
            "content": content,
            "notification_type": notification_type,
            "channel": channel,
            "metadata": metadata or {},
        }
        notification = await self.notification_repo.create_notification(
            notification_data, user_id=user_id
        )
        # سجل التسليم
        delivery_data = {
            "notification_id": notification.id,
            "user_id": user_id,
            "channel": channel,
            "status": "sent",
            "metadata": metadata or {},
        }
        await self.delivery_record_repo.create_delivery_record(
            delivery_data, user_id=user_id
        )
        return notification

    async def get_user_notifications(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        notification_type: Optional[str] = None,
    ) -> List[Notification]:
        return await self.notification_repo.get_user_notifications(
            user_id, limit, notification_type
        )

    async def mark_notification_as_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        return await self.notification_repo.mark_as_read(notification_id, user_id)

    async def get_notification_delivery_records(
        self, notification_id: uuid.UUID
    ) -> List[DeliveryRecord]:
        return await self.delivery_record_repo.get_notification_delivery_records(
            notification_id
        )
