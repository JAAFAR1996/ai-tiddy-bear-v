"""
Real-time Notification WebSocket Service
=======================================
Integrates WebSocket adapter with notification system for instant parent alerts.
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from enum import Enum

from src.infrastructure.websocket.production_websocket_adapter import (
    ProductionWebSocketAdapter,
    WebSocketMessage,
    MessageType,
)

from src.application.services.notification_service import NotificationService
from src.infrastructure.config.premium_websocket_config import (
    WEBSOCKET_CONFIG,
    ALERT_CONFIG,
)

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Notification priority levels for real-time delivery."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of real-time alerts."""

    SAFETY_ALERT = "safety_alert"
    BEHAVIOR_CONCERN = "behavior_concern"
    USAGE_LIMIT = "usage_limit"
    SYSTEM_ALERT = "system_alert"
    PREMIUM_FEATURE = "premium_feature"
    SUBSCRIPTION_UPDATE = "subscription_update"
    EMERGENCY = "emergency"


class RealTimeNotificationService:
    """
    Service for sending real-time notifications via WebSocket.

    Features:
    - Instant delivery to connected parents
    - Priority-based message routing
    - Fallback to traditional notification channels
    - Parent subscription management
    - Emergency escalation
    """

    def __init__(
        self,
        websocket_adapter: ProductionWebSocketAdapter,
        notification_service: Optional[NotificationService] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.websocket_adapter = websocket_adapter
        self.notification_service = notification_service
        self.config = config or WEBSOCKET_CONFIG
        self.logger = logger

        # Track parent subscriptions to specific alert types
        self.parent_subscriptions: Dict[str, Set[AlertType]] = (
            {}
        )  # parent_id -> alert_types
        self.child_parent_mapping: Dict[str, str] = {}  # child_id -> parent_id

        # Emergency escalation settings
        self.emergency_escalation_delay = int(
            self.config.get("EMERGENCY_ESCALATION_DELAY", "300")
        )  # 5 minutes
        self.max_retry_attempts = int(
            self.config.get("WS_NOTIFICATION_RETRY_ATTEMPTS", "3")
        )

        self.logger.info("RealTimeNotificationService initialized")

    async def register_parent_connection(
        self,
        parent_id: str,
        connection_id: str,
        alert_subscriptions: Optional[List[AlertType]] = None,
    ) -> None:
        """
        Register parent WebSocket connection for real-time notifications.

        Args:
            parent_id: Parent user ID
            connection_id: WebSocket connection ID
            alert_subscriptions: Types of alerts parent wants to receive
        """
        try:
            # Default to all alert types if not specified
            if alert_subscriptions is None:
                alert_subscriptions = list(AlertType)

            # Store parent subscriptions
            self.parent_subscriptions[parent_id] = set(alert_subscriptions)

            # Subscribe to parent-specific topics
            topics = [f"parent:{parent_id}", "system:all", "emergency:all"]
            for topic in topics:
                await self.websocket_adapter.subscribe_to_topic(connection_id, topic)

            # Send welcome message
            welcome_message = WebSocketMessage(
                message_type=MessageType.SYSTEM,
                data={
                    "type": "connection_established",
                    "message": "Real-time notifications enabled",
                    "subscribed_alerts": [alert.value for alert in alert_subscriptions],
                    "timestamp": datetime.now().isoformat(),
                },
                recipient_id=parent_id,
            )

            await self.websocket_adapter.send_message(connection_id, welcome_message)

            self.logger.info(
                f"Registered parent {parent_id} for real-time notifications"
            )

        except Exception as e:
            self.logger.error(
                f"Error registering parent connection: {e}", exc_info=True
            )

    async def map_child_to_parent(self, child_id: str, parent_id: str) -> None:
        """Map child ID to parent ID for notification routing."""
        self.child_parent_mapping[child_id] = parent_id
        self.logger.debug(f"Mapped child {child_id} to parent {parent_id}")

    async def send_safety_alert(
        self,
        child_id: str,
        alert_data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.HIGH,
    ) -> bool:
        """
        Send real-time safety alert to parent.

        Args:
            child_id: ID of child involved in safety event
            alert_data: Alert details and context
            priority: Alert priority level

        Returns:
            True if alert sent successfully via WebSocket
        """
        try:
            parent_id = self.child_parent_mapping.get(child_id)
            if not parent_id:
                self.logger.warning(f"No parent mapping found for child {child_id}")
                return False

            # Check if parent is subscribed to safety alerts
            subscriptions = self.parent_subscriptions.get(parent_id, set())
            if AlertType.SAFETY_ALERT not in subscriptions:
                self.logger.debug(f"Parent {parent_id} not subscribed to safety alerts")
                return False

            # Create WebSocket message
            message = WebSocketMessage(
                message_type=MessageType.NOTIFICATION,
                data={
                    "alert_type": AlertType.SAFETY_ALERT.value,
                    "priority": priority.value,
                    "child_id": child_id,
                    "title": "Safety Alert",
                    "message": alert_data.get("message", "Safety concern detected"),
                    "safety_score": alert_data.get("safety_score"),
                    "event_type": alert_data.get("event_type"),
                    "severity": alert_data.get("severity", "medium"),
                    "recommendations": alert_data.get("recommendations", []),
                    "timestamp": datetime.now().isoformat(),
                    "requires_action": priority
                    in [NotificationPriority.HIGH, NotificationPriority.CRITICAL],
                },
                recipient_id=parent_id,
            )

            # Send to parent
            success_count = await self.websocket_adapter.send_to_user(
                parent_id, message
            )

            # Also broadcast to parent topic for multiple devices
            topic_success = await self.websocket_adapter.broadcast_to_topic(
                f"parent:{parent_id}", message
            )

            total_success = success_count + topic_success

            # If critical priority and WebSocket delivery failed, escalate to emergency
            if priority == NotificationPriority.CRITICAL and total_success == 0:
                await self._escalate_to_emergency(child_id, parent_id, alert_data)

            # Fallback to traditional notification if WebSocket failed
            if total_success == 0:
                await self._fallback_notification(
                    parent_id, child_id, alert_data, AlertType.SAFETY_ALERT
                )

            self.logger.info(
                f"Safety alert sent to {total_success} connections for parent {parent_id}",
                extra={
                    "child_id": child_id,
                    "priority": priority.value,
                    "websocket_success": total_success > 0,
                },
            )

            return total_success > 0

        except Exception as e:
            self.logger.error(f"Error sending safety alert: {e}", exc_info=True)
            return False

    async def send_behavior_alert(
        self,
        child_id: str,
        behavior_data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.MEDIUM,
    ) -> bool:
        """Send real-time behavioral concern alert."""
        try:
            parent_id = self.child_parent_mapping.get(child_id)
            if not parent_id:
                return False

            subscriptions = self.parent_subscriptions.get(parent_id, set())
            if AlertType.BEHAVIOR_CONCERN not in subscriptions:
                return False

            message = WebSocketMessage(
                message_type=MessageType.NOTIFICATION,
                data={
                    "alert_type": AlertType.BEHAVIOR_CONCERN.value,
                    "priority": priority.value,
                    "child_id": child_id,
                    "title": "Behavioral Pattern Detected",
                    "message": behavior_data.get(
                        "message", "Behavioral concern identified"
                    ),
                    "pattern_type": behavior_data.get("pattern_type"),
                    "confidence_score": behavior_data.get("confidence_score"),
                    "recommended_actions": behavior_data.get("recommended_actions", []),
                    "trend_analysis": behavior_data.get("trend_analysis"),
                    "timestamp": datetime.now().isoformat(),
                },
                recipient_id=parent_id,
            )

            success_count = await self.websocket_adapter.send_to_user(
                parent_id, message
            )
            topic_success = await self.websocket_adapter.broadcast_to_topic(
                f"parent:{parent_id}", message
            )

            total_success = success_count + topic_success

            if total_success == 0:
                await self._fallback_notification(
                    parent_id, child_id, behavior_data, AlertType.BEHAVIOR_CONCERN
                )

            return total_success > 0

        except Exception as e:
            self.logger.error(f"Error sending behavior alert: {e}", exc_info=True)
            return False

    async def send_usage_limit_alert(
        self,
        child_id: str,
        limit_data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.LOW,
    ) -> bool:
        """Send usage limit notification."""
        try:
            parent_id = self.child_parent_mapping.get(child_id)
            if not parent_id:
                return False

            subscriptions = self.parent_subscriptions.get(parent_id, set())
            if AlertType.USAGE_LIMIT not in subscriptions:
                return False

            message = WebSocketMessage(
                message_type=MessageType.NOTIFICATION,
                data={
                    "alert_type": AlertType.USAGE_LIMIT.value,
                    "priority": priority.value,
                    "child_id": child_id,
                    "title": "Usage Limit Notification",
                    "message": limit_data.get("message", "Daily usage limit reached"),
                    "limit_type": limit_data.get(
                        "limit_type"
                    ),  # daily, session, feature
                    "current_usage": limit_data.get("current_usage"),
                    "limit_value": limit_data.get("limit_value"),
                    "auto_action": limit_data.get(
                        "auto_action"
                    ),  # pause, warning, restrict
                    "timestamp": datetime.now().isoformat(),
                },
                recipient_id=parent_id,
            )

            success_count = await self.websocket_adapter.send_to_user(
                parent_id, message
            )
            return success_count > 0

        except Exception as e:
            self.logger.error(f"Error sending usage limit alert: {e}", exc_info=True)
            return False

    async def send_premium_feature_alert(
        self,
        parent_id: str,
        feature_data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.LOW,
    ) -> bool:
        """Send premium feature notification."""
        try:
            subscriptions = self.parent_subscriptions.get(parent_id, set())
            if AlertType.PREMIUM_FEATURE not in subscriptions:
                return False

            message = WebSocketMessage(
                message_type=MessageType.NOTIFICATION,
                data={
                    "alert_type": AlertType.PREMIUM_FEATURE.value,
                    "priority": priority.value,
                    "title": "Premium Feature Update",
                    "message": feature_data.get(
                        "message", "Premium feature notification"
                    ),
                    "feature_id": feature_data.get("feature_id"),
                    "action_type": feature_data.get(
                        "action_type"
                    ),  # limit_reached, upgrade_available, etc.
                    "current_usage": feature_data.get("current_usage"),
                    "upgrade_options": feature_data.get("upgrade_options", []),
                    "timestamp": datetime.now().isoformat(),
                },
                recipient_id=parent_id,
            )

            success_count = await self.websocket_adapter.send_to_user(
                parent_id, message
            )
            return success_count > 0

        except Exception as e:
            self.logger.error(
                f"Error sending premium feature alert: {e}", exc_info=True
            )
            return False

    async def send_emergency_alert(
        self, child_id: str, emergency_data: Dict[str, Any]
    ) -> bool:
        """
        Send emergency alert to all available channels.

        Critical alerts bypass subscription preferences and use all available methods.
        """
        try:
            parent_id = self.child_parent_mapping.get(child_id)
            if not parent_id:
                self.logger.error(
                    f"No parent mapping for emergency alert - child {child_id}"
                )
                return False

            # Create emergency message
            message = WebSocketMessage(
                message_type=MessageType.NOTIFICATION,
                data={
                    "alert_type": AlertType.EMERGENCY.value,
                    "priority": NotificationPriority.CRITICAL.value,
                    "child_id": child_id,
                    "title": "EMERGENCY ALERT",
                    "message": emergency_data.get(
                        "message", "Emergency situation detected"
                    ),
                    "emergency_type": emergency_data.get("emergency_type"),
                    "severity": "critical",
                    "location": emergency_data.get("location"),
                    "immediate_actions": emergency_data.get("immediate_actions", []),
                    "contact_authorities": emergency_data.get(
                        "contact_authorities", False
                    ),
                    "timestamp": datetime.now().isoformat(),
                    "alert_id": emergency_data.get("alert_id"),
                },
                recipient_id=parent_id,
            )

            # Send to all parent connections
            success_count = await self.websocket_adapter.send_to_user(
                parent_id, message
            )

            # Broadcast to emergency topic (all connected administrators)
            emergency_success = await self.websocket_adapter.broadcast_to_topic(
                "emergency:all", message
            )

            # Always use fallback for emergencies
            await self._fallback_notification(
                parent_id, child_id, emergency_data, AlertType.EMERGENCY
            )

            # Log emergency alert
            self.logger.critical(
                "Emergency alert sent",
                extra={
                    "child_id": child_id,
                    "parent_id": parent_id,
                    "emergency_type": emergency_data.get("emergency_type"),
                    "websocket_delivered": success_count > 0,
                    "alert_id": emergency_data.get("alert_id"),
                },
            )

            return success_count > 0 or emergency_success > 0

        except Exception as e:
            self.logger.error(f"Error sending emergency alert: {e}", exc_info=True)
            return False

    async def _escalate_to_emergency(
        self, child_id: str, parent_id: str, alert_data: Dict[str, Any]
    ) -> None:
        """Escalate failed critical alert to emergency status."""
        try:
            # Wait for escalation delay
            await asyncio.sleep(self.emergency_escalation_delay)

            # Create emergency escalation
            emergency_data = {
                "message": "Critical safety alert escalated - parent notification failed",
                "emergency_type": "communication_failure",
                "original_alert": alert_data,
                "escalation_reason": "failed_notification_delivery",
                "alert_id": f"escalated_{datetime.now().timestamp()}",
            }

            await self.send_emergency_alert(child_id, emergency_data)

        except Exception as e:
            self.logger.error(f"Error escalating to emergency: {e}", exc_info=True)

    async def _fallback_notification(
        self,
        parent_id: str,
        child_id: str,
        alert_data: Dict[str, Any],
        alert_type: AlertType,
    ) -> None:
        """Send notification via traditional channels when WebSocket fails."""
        try:
            # Use notification service as fallback
            fallback_message = f"{alert_type.value.replace('_', ' ').title()}: {alert_data.get('message', 'Alert for your child')}"

            await self.notification_service.send_notification(
                recipient=parent_id,  # Would lookup email in production
                message=fallback_message,
                urgent=alert_type in [AlertType.SAFETY_ALERT, AlertType.EMERGENCY],
            )

            self.logger.info(
                f"Sent fallback notification for {alert_type.value} to parent {parent_id}"
            )

        except Exception as e:
            self.logger.error(
                f"Error sending fallback notification: {e}", exc_info=True
            )

    async def update_parent_subscriptions(
        self, parent_id: str, alert_types: List[AlertType]
    ) -> bool:
        """Update parent's alert subscriptions."""
        try:
            self.parent_subscriptions[parent_id] = set(alert_types)

            # Send confirmation
            confirmation_message = WebSocketMessage(
                message_type=MessageType.SYSTEM,
                data={
                    "type": "subscription_updated",
                    "subscribed_alerts": [alert.value for alert in alert_types],
                    "timestamp": datetime.now().isoformat(),
                },
                recipient_id=parent_id,
            )

            await self.websocket_adapter.send_to_user(parent_id, confirmation_message)

            self.logger.info(f"Updated alert subscriptions for parent {parent_id}")
            return True

        except Exception as e:
            self.logger.error(
                f"Error updating parent subscriptions: {e}", exc_info=True
            )
            return False

    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time notification service metrics."""
        try:
            websocket_metrics = self.websocket_adapter.get_metrics()

            return {
                "websocket_metrics": websocket_metrics,
                "parent_connections": len(self.parent_subscriptions),
                "child_mappings": len(self.child_parent_mapping),
                "subscription_breakdown": {
                    alert_type.value: len(
                        [
                            subs
                            for subs in self.parent_subscriptions.values()
                            if alert_type in subs
                        ]
                    )
                    for alert_type in AlertType
                },
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error getting real-time metrics: {e}", exc_info=True)
            return {"error": str(e)}


# Service factory function
def get_real_time_notification_service() -> RealTimeNotificationService:
    """Get real-time notification service instance."""
    # In production, these would be injected via DI container
    websocket_adapter = ProductionWebSocketAdapter()

    # Mock notification service for now
    class MockNotificationService:
        async def send_notification(
            self, recipient: str, message: str, urgent: bool = False
        ):
            logger.info(f"Fallback notification sent to {recipient}: {message}")

    notification_service = MockNotificationService()

    return RealTimeNotificationService(
        websocket_adapter=websocket_adapter,
        notification_service=notification_service,
        config=WEBSOCKET_CONFIG,
    )
