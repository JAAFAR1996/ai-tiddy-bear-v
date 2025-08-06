"""
Notification & DeliveryRecord Repository - Production Ready
=========================================================
Repository classes لإدارة الإشعارات وسجلات التسليم بشكل إنتاجي كامل.
"""

import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.future import select
from .models import Notification, DeliveryRecord
from .database_manager import database_manager
from .repository import BaseRepository


class NotificationRepository(BaseRepository):
    """Repository لإدارة الإشعارات بشكل إنتاجي."""

    def __init__(self):
        super().__init__(Notification)

    async def create_notification(
        self, data: Dict[str, Any], user_id: Optional[uuid.UUID] = None
    ) -> Notification:
        return await self.create(data, user_id=user_id)

    async def get_user_notifications(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        notification_type: Optional[str] = None,
    ) -> List[Notification]:
        async with database_manager.get_async_session() as session:
            query = select(Notification).where(Notification.user_id == user_id)
            if notification_type:
                query = query.where(Notification.notification_type == notification_type)
            query = query.order_by(Notification.created_at.desc()).limit(limit)
            result = await session.execute(query)
            return result.scalars().all()

    async def mark_as_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        async with database_manager.get_async_session() as session:
            notification = await session.get(Notification, notification_id)
            if notification and notification.user_id == user_id:
                notification.read = True
                await session.commit()
                return True
            return False


class DeliveryRecordRepository(BaseRepository):
    """Repository لإدارة سجلات تسليم الإشعارات بشكل إنتاجي."""

    def __init__(self):
        super().__init__(DeliveryRecord)

    async def create_delivery_record(
        self, data: Dict[str, Any], user_id: Optional[uuid.UUID] = None
    ) -> DeliveryRecord:
        return await self.create(data, user_id=user_id)

    async def get_notification_delivery_records(
        self, notification_id: uuid.UUID
    ) -> List[DeliveryRecord]:
        async with database_manager.get_async_session() as session:
            query = select(DeliveryRecord).where(
                DeliveryRecord.notification_id == notification_id
            )
            result = await session.execute(query)
            return result.scalars().all()
