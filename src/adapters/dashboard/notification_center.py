"""
NotificationCenter: Handles parent notifications and event updates.
- Fetches real notifications/events from the system (not dummy).
- Exposes notification data for dashboard display.
"""
class NotificationCenter:
    def __init__(self, user_service):
        self.user_service = user_service

    async def get_notifications(self, parent_id: str):
        return await self.user_service.get_notifications(parent_id)
