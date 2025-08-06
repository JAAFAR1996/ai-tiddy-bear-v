"""
ProductionNotificationRepository & ProductionDeliveryRecordRepository
===================================================================
Production-ready repository implementations for Notification and DeliveryRecord models.
"""

from src.infrastructure.database.notification_repository import (
    NotificationRepository,
    DeliveryRecordRepository,
)
from src.infrastructure.database.database_manager import database_manager


class ProductionNotificationRepository(NotificationRepository):
    def __init__(self, session=None):
        super().__init__()
        self.session = session or database_manager.get_sync_session()


class ProductionDeliveryRecordRepository(DeliveryRecordRepository):
    def __init__(self, session=None):
        super().__init__()
        self.session = session or database_manager.get_sync_session()
