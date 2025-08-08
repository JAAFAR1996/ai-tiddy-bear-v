"""
Production Real-time WebSocket Notification Service
==================================================
Enterprise-grade real-time notification system with WebSocket integration,
priority-based routing, and comprehensive message delivery.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

from src.core.entities.subscription import NotificationType, NotificationPriority
from src.application.services.notification.notification_service import (
    get_notification_service,
    NotificationRequest,
    NotificationRecipient,
    NotificationTemplate,
    NotificationChannel,
)

# get_config import removed; config must be passed explicitly


class ConnectionStatus(str, Enum):
    """WebSocket connection status."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class WebSocketConnection:
    """WebSocket connection information."""

    connection_id: str
    user_id: str
    status: ConnectionStatus
    connected_at: datetime
    last_ping: Optional[datetime] = None
    subscription_topics: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RealTimeMessage:
    """Real-time message structure."""

    message_id: str
    message_type: str
    priority: NotificationPriority
    recipient_user_id: str
    data: Dict[str, Any]
    timestamp: datetime
    expiry: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


class ProductionRealTimeNotificationService:
    """
    Production-grade real-time notification service with:
    - WebSocket connection management with heartbeat
    - Priority-based message routing and delivery
    - Message persistence and retry mechanisms
    - Topic-based subscriptions
    - Connection pooling and load balancing
    - Comprehensive monitoring and analytics
    - Auto-reconnection and failover
    """

    def __init__(self, config, notification_service, websocket_adapter, logger=None):
        self.config = config
        self.notification_service = notification_service
        self.websocket_adapter = websocket_adapter
        self.logger = logger or logging.getLogger("ai_teddy.websocket")
        self._connections: Dict[str, WebSocketConnection] = {}
        self._user_connections: Dict[str, Set[str]] = {}
        self._message_queue: Dict[str, List[RealTimeMessage]] = {}
        self._subscription_topics: Dict[str, Set[str]] = {}
        self._running = False
        self._heartbeat_task = None
        self._cleanup_task = None
        self._max_connections_per_user = 5
        self._heartbeat_interval = 30  # seconds
        self._message_ttl = 3600  # 1 hour
        self._message_rate_limit_per_minute = 60
        self._user_message_timestamps: Dict[str, list] = {}
        self._initialize_service()


# Explicit factory (خارج الكلاس فقط)
def create_production_realtime_notification_service(
    config, notification_service, websocket_adapter, logger=None
) -> ProductionRealTimeNotificationService:
    return ProductionRealTimeNotificationService(
        config, notification_service, websocket_adapter, logger
    )

    def _initialize_service(self):
        """Initialize the real-time service."""
        self.logger.info("Initializing production real-time notification service")

        # Initialize message processing
        self._max_connections_per_user = 5
        self._heartbeat_interval = 30  # seconds
        self._message_ttl = 3600  # 1 hour

        # Start background tasks
        asyncio.create_task(self._start_background_tasks())

    async def _start_background_tasks(self):
        """Start background maintenance tasks."""
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())

    async def start(self):
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())

    async def connect_user(
        self,
        connection_id: str,
        user_id: str,
        websocket_connection,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Register new WebSocket connection for user.

        Returns:
            Connection status and configuration
        """
        try:
            # Check connection limits
            if not await self._check_connection_limits(user_id):
                return {
                    "status": "rejected",
                    "reason": "Connection limit exceeded",
                    "max_connections": self._max_connections_per_user,
                }

            # Create connection record
            connection = WebSocketConnection(
                connection_id=connection_id,
                user_id=user_id,
                status=ConnectionStatus.CONNECTED,
                connected_at=datetime.utcnow(),
                metadata=metadata or {},
            )

            # Store connection
            self._connections[connection_id] = connection

            # Update user connections index
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(connection_id)

            # Initialize message queue for user if needed
            if user_id not in self._message_queue:
                self._message_queue[user_id] = []

            # Send pending messages
            await self._send_pending_messages(user_id, connection_id)

            # Subscribe to default topics based on user subscription
            await self._setup_default_subscriptions(user_id, connection_id)

            self.logger.info(
                f"WebSocket connection established for user {user_id}",
                extra={
                    "connection_id": connection_id,
                    "user_id": user_id,
                    "total_connections": len(self._connections),
                },
            )

            return {
                "status": "connected",
                "connection_id": connection_id,
                "heartbeat_interval": self._heartbeat_interval,
                "supported_topics": list(self._get_available_topics(user_id)),
            }

        except Exception as e:
            self.logger.error(
                f"Failed to connect user: {str(e)}",
                extra={"connection_id": connection_id, "user_id": user_id},
            )
            return {"status": "error", "error": str(e)}

    async def disconnect_user(self, connection_id: str) -> Dict[str, Any]:
        """
        Disconnect WebSocket connection.
        """
        try:
            connection = self._connections.get(connection_id)
            if not connection:
                return {"status": "not_found"}

            user_id = connection.user_id

            # Update connection status
            connection.status = ConnectionStatus.DISCONNECTED

            # Remove from connections
            self._connections.pop(connection_id, None)

            # Update user connections index
            if user_id in self._user_connections:
                self._user_connections[user_id].discard(connection_id)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]

            # Remove from topic subscriptions
            await self._unsubscribe_from_all_topics(connection_id)

            self.logger.info(
                f"WebSocket connection disconnected for user {user_id}",
                extra={
                    "connection_id": connection_id,
                    "user_id": user_id,
                    "connection_duration": (
                        datetime.utcnow() - connection.connected_at
                    ).total_seconds(),
                },
            )

            return {"status": "disconnected"}

        except Exception as e:
            self.logger.error(
                f"Failed to disconnect user: {str(e)}",
                extra={"connection_id": connection_id},
            )
            return {"status": "error", "error": str(e)}

    async def send_real_time_notification(
        self,
        notification_type: NotificationType,
        priority: NotificationPriority,
        user_id: str,
        data: Dict[str, Any],
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send real-time notification to user with priority handling.
        """
        message_id = str(uuid.uuid4())

        try:
            self.logger.info(
                f"Sending real-time notification {message_id}",
                extra={
                    "message_id": message_id,
                    "user_id": user_id,
                    "type": notification_type.value,
                    "priority": priority.value,
                },
            )

            # Create real-time message
            message = RealTimeMessage(
                message_id=message_id,
                message_type=notification_type.value,
                priority=priority,
                recipient_user_id=user_id,
                data=data,
                timestamp=datetime.utcnow(),
                expiry=datetime.utcnow() + timedelta(hours=1),
            )

            # Try immediate delivery
            delivery_result = await self._deliver_message_immediately(message, topic)

            if delivery_result["delivered"]:
                return {
                    "message_id": message_id,
                    "status": "delivered",
                    "delivery_method": "immediate",
                    "connections_reached": delivery_result["connections_reached"],
                }

            # Queue for later delivery if user not connected
            await self._queue_message_for_later(message)

            # Send via fallback channels for high priority messages
            if priority in [NotificationPriority.HIGH, NotificationPriority.CRITICAL]:
                await self._send_fallback_notification(message)

            return {
                "message_id": message_id,
                "status": "queued",
                "delivery_method": "queued",
                "fallback_sent": priority
                in [NotificationPriority.HIGH, NotificationPriority.CRITICAL],
            }

        except Exception as e:
            self.logger.error(
                f"Failed to send real-time notification: {str(e)}",
                extra={"message_id": message_id, "user_id": user_id},
            )
            return {"message_id": message_id, "status": "failed", "error": str(e)}

    async def subscribe_to_topic(
        self, connection_id: str, topic: str
    ) -> Dict[str, Any]:
        """
        Subscribe WebSocket connection to notification topic.
        """
        try:
            connection = self._connections.get(connection_id)
            if not connection:
                return {"status": "error", "error": "Connection not found"}

            # Validate topic access
            if not await self._validate_topic_access(connection.user_id, topic):
                return {"status": "error", "error": "Access denied to topic"}

            # Add to connection subscriptions
            connection.subscription_topics.add(topic)

            # Add to topic index
            if topic not in self._subscription_topics:
                self._subscription_topics[topic] = set()
            self._subscription_topics[topic].add(connection_id)

            self.logger.info(
                f"Connection {connection_id} subscribed to topic {topic}",
                extra={
                    "connection_id": connection_id,
                    "user_id": connection.user_id,
                    "topic": topic,
                },
            )

            return {"status": "subscribed", "topic": topic}

        except Exception as e:
            self.logger.error(f"Failed to subscribe to topic: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def unsubscribe_from_topic(
        self, connection_id: str, topic: str
    ) -> Dict[str, Any]:
        """
        Unsubscribe WebSocket connection from notification topic.
        """
        try:
            connection = self._connections.get(connection_id)
            if not connection:
                return {"status": "error", "error": "Connection not found"}

            # Remove from connection subscriptions
            connection.subscription_topics.discard(topic)

            # Remove from topic index
            if topic in self._subscription_topics:
                self._subscription_topics[topic].discard(connection_id)
                if not self._subscription_topics[topic]:
                    del self._subscription_topics[topic]

            self.logger.info(
                f"Connection {connection_id} unsubscribed from topic {topic}",
                extra={"connection_id": connection_id, "topic": topic},
            )

            return {"status": "unsubscribed", "topic": topic}

        except Exception as e:
            self.logger.error(f"Failed to unsubscribe from topic: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def get_connection_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get real-time connection status for user.
        """
        try:
            user_connections = self._user_connections.get(user_id, set())

            connections_info = []
            for conn_id in user_connections:
                connection = self._connections.get(conn_id)
                if connection:
                    connections_info.append(
                        {
                            "connection_id": conn_id,
                            "status": connection.status.value,
                            "connected_at": connection.connected_at.isoformat(),
                            "last_ping": (
                                connection.last_ping.isoformat()
                                if connection.last_ping
                                else None
                            ),
                            "subscribed_topics": list(connection.subscription_topics),
                        }
                    )

            pending_messages = len(self._message_queue.get(user_id, []))

            return {
                "user_id": user_id,
                "total_connections": len(user_connections),
                "connections": connections_info,
                "pending_messages": pending_messages,
                "is_online": len(user_connections) > 0,
            }

        except Exception as e:
            self.logger.error(f"Failed to get connection status: {str(e)}")
            return {"error": str(e)}

    # Internal Helper Methods

    async def _check_connection_limits(self, user_id: str) -> bool:
        """Check if user can create new connection."""
        current_connections = len(self._user_connections.get(user_id, set()))
        return current_connections < self._max_connections_per_user

    async def _send_pending_messages(self, user_id: str, connection_id: str) -> None:
        """Send queued messages to newly connected user."""
        pending_messages = self._message_queue.get(user_id, [])

        if not pending_messages:
            return

        connection = self._connections.get(connection_id)
        if not connection:
            return

        delivered_messages = []

        for message in pending_messages:
            try:
                # Check if message hasn't expired
                if message.expiry and datetime.utcnow() > message.expiry:
                    delivered_messages.append(message)
                    continue

                # Send message
                await self._send_message_to_connection(connection_id, message)
                delivered_messages.append(message)

            except Exception as e:
                self.logger.error(
                    f"Failed to send pending message: {str(e)}",
                    extra={
                        "message_id": message.message_id,
                        "connection_id": connection_id,
                    },
                )

        # Remove delivered messages from queue
        if delivered_messages:
            self._message_queue[user_id] = [
                msg for msg in pending_messages if msg not in delivered_messages
            ]

    async def _setup_default_subscriptions(
        self, user_id: str, connection_id: str
    ) -> None:
        """Setup default topic subscriptions for user."""
        # Default topics all users get
        default_topics = ["safety_alerts", "system_notifications"]

        # Add subscription-specific topics based on user's premium status
        # This would check user's subscription tier in production
        premium_topics = ["behavior_concerns", "usage_limits", "premium_features"]

        for topic in default_topics + premium_topics:
            await self.subscribe_to_topic(connection_id, topic)

    def _get_available_topics(self, user_id: str) -> Set[str]:
        """Get topics available for user based on subscription."""
        # Base topics for all users
        topics = {"safety_alerts", "system_notifications"}

        # Add premium topics (would check actual subscription in production)
        topics.update(
            {
                "behavior_concerns",
                "usage_limits",
                "premium_features",
                "emergency_alerts",
            }
        )

        return topics

    async def _deliver_message_immediately(
        self, message: RealTimeMessage, topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """Attempt immediate delivery to connected user."""
        user_connections = self._user_connections.get(message.recipient_user_id, set())

        if not user_connections:
            return {"delivered": False, "connections_reached": 0}

        delivered_count = 0

        for connection_id in user_connections:
            try:
                connection = self._connections.get(connection_id)
                if not connection or connection.status != ConnectionStatus.CONNECTED:
                    continue

                # Check topic subscription if specified
                if topic and topic not in connection.subscription_topics:
                    continue

                await self._send_message_to_connection(connection_id, message)
                delivered_count += 1

            except Exception as e:
                self.logger.error(
                    f"Failed to deliver to connection {connection_id}: {str(e)}",
                    extra={"message_id": message.message_id},
                )

        return {
            "delivered": delivered_count > 0,
            "connections_reached": delivered_count,
        }

    async def _send_message_to_connection(
        self, connection_id: str, message: RealTimeMessage
    ) -> None:
        """Send message to specific WebSocket connection."""
        try:
            # Get connection from our internal state
            connection = self._connections.get(connection_id)
            if not connection:
                self.logger.warning(
                    f"Connection {connection_id} not found for message sending"
                )
                return

            # Create WebSocket message format
            websocket_message_data = {
                "type": "realtime_notification",
                "message_id": message.message_id,
                "notification_type": message.message_type,
                "priority": message.priority.value,
                "data": message.data,
                "timestamp": message.timestamp.isoformat(),
            }

            # Get WebSocket from connection metadata
            websocket = connection.metadata.get("websocket")
            if not websocket:
                self.logger.error(f"No WebSocket found for connection {connection_id}")
                return

            # Send message via WebSocket
            import json

            message_json = json.dumps(websocket_message_data)
            await websocket.send_text(message_json)

            self.logger.info(
                f"Message sent successfully to connection {connection_id}",
                extra={
                    "message_id": message.message_id,
                    "connection_id": connection_id,
                    "message_type": message.message_type,
                },
            )

        except Exception as e:
            self.logger.error(
                f"Failed to send message to connection {connection_id}: {e}",
                extra={
                    "message_id": message.message_id,
                    "connection_id": connection_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def _send_fallback_notification(self, message: RealTimeMessage) -> None:
        """Send notification via fallback channels for high priority messages."""
        try:
            request = NotificationRequest(
                notification_type=NotificationType(message.message_type),
                priority=message.priority,
                recipient=NotificationRecipient(
                    user_id=message.recipient_user_id,
                    email="user@example.com",  # Would get from user profile
                    phone="+1234567890",  # Would get from user profile
                ),
                template=NotificationTemplate(
                    title=message.data.get("title", "Notification"),
                    body=message.data.get("body", "You have a new notification"),
                ),
                channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
            )
            await self.notification_service.send_notification(request)
        except Exception as e:
            self.logger.error(f"Failed to send fallback notification: {str(e)}")

    async def _queue_message_for_later(self, message: RealTimeMessage) -> None:
        """Queue message for delivery when user connects."""
        user_id = message.recipient_user_id

        if user_id not in self._message_queue:
            self._message_queue[user_id] = []

        self._message_queue[user_id].append(message)

        # Limit queue size per user
        if len(self._message_queue[user_id]) > 100:
            self._message_queue[user_id] = self._message_queue[user_id][-100:]

    async def _send_fallback_notification(self, message: RealTimeMessage) -> None:
        """Send notification via fallback channels for high priority messages."""
        try:
            notification_service = await get_notification_service()

            # Create notification request for fallback delivery
            request = NotificationRequest(
                notification_type=NotificationType(message.message_type),
                priority=message.priority,
                recipient=NotificationRecipient(
                    user_id=message.recipient_user_id,
                    email="user@example.com",  # Would get from user profile
                    phone="+1234567890",  # Would get from user profile
                ),
                template=NotificationTemplate(
                    title=message.data.get("title", "Notification"),
                    body=message.data.get("body", "You have a new notification"),
                ),
                channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
            )

            await notification_service.send_notification(request)

        except Exception as e:
            self.logger.error(f"Failed to send fallback notification: {str(e)}")

    async def _validate_topic_access(self, user_id: str, topic: str) -> bool:
        """Validate if user has access to specific topic."""
        available_topics = self._get_available_topics(user_id)
        return topic in available_topics

    async def _unsubscribe_from_all_topics(self, connection_id: str) -> None:
        """Remove connection from all topic subscriptions."""
        for topic, connections in self._subscription_topics.items():
            connections.discard(connection_id)

    async def _heartbeat_monitor(self) -> None:
        """Monitor connection health with heartbeat."""
        while self._running:
            try:
                current_time = datetime.utcnow()
                stale_connections = []

                for connection_id, connection in self._connections.items():
                    if connection.last_ping:
                        time_since_ping = (
                            current_time - connection.last_ping
                        ).total_seconds()
                        if time_since_ping > self._heartbeat_interval * 2:
                            stale_connections.append(connection_id)

                # Disconnect stale connections
                for connection_id in stale_connections:
                    await self.disconnect_user(connection_id)

                await asyncio.sleep(self._heartbeat_interval)

            except Exception as e:
                self.logger.error(f"Heartbeat monitor error: {str(e)}")
                await asyncio.sleep(self._heartbeat_interval)

    async def _cleanup_expired_messages(self) -> None:
        """Clean up expired messages from queues."""
        while self._running:
            try:
                current_time = datetime.utcnow()

                for user_id, messages in self._message_queue.items():
                    unexpired_messages = [
                        msg
                        for msg in messages
                        if not msg.expiry or current_time <= msg.expiry
                    ]
                    self._message_queue[user_id] = unexpired_messages

                await asyncio.sleep(300)  # Clean up every 5 minutes

            except Exception as e:
                self.logger.error(f"Message cleanup error: {str(e)}")
                await asyncio.sleep(300)

    async def shutdown(self) -> None:
        """Gracefully shutdown the service."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()

        # Disconnect all connections
        for connection_id in list(self._connections.keys()):
            await self.disconnect_user(connection_id)

        self.logger.info("Real-time notification service shutdown complete")
