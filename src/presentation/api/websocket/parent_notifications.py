"""
Parent Dashboard WebSocket Endpoints
===================================
Real-time WebSocket connections for parent mobile app.
"""

import logging
import json
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect, Depends
from fastapi.routing import APIRouter

from src.application.services.realtime.notification_websocket_service import (
    RealTimeNotificationService,
    get_real_time_notification_service,
    AlertType,
    NotificationPriority,
)
from src.infrastructure.websocket.production_websocket_adapter import (
    ProductionWebSocketAdapter,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/parent/notifications/{parent_id}")
async def parent_notification_websocket(
    websocket: WebSocket,
    parent_id: str,
    real_time_service: RealTimeNotificationService = Depends(
        get_real_time_notification_service
    ),
):
    """
    WebSocket endpoint for parent real-time notifications.

    Connection flow:
    1. Accept WebSocket connection
    2. Authenticate parent (token in query params or Authorization header)
    3. Verify parent_id matches token user_id
    4. Register for real-time notifications  
    5. Handle incoming subscription preferences
    6. Send real-time alerts and updates

    Message Types:
    - safety_alert: Immediate safety concerns
    - behavior_alert: Behavioral pattern notifications
    - usage_alert: Usage limit notifications
    - system_alert: System-wide notifications
    - premium_alert: Premium feature notifications
    """
    await websocket.accept()
    connection_id = None

    try:
        # Authentication via token in query params or headers
        token = None
        
        # Try to get token from query params first
        token = websocket.query_params.get("token")
        
        # If not in query params, try headers
        if not token:
            auth_header = websocket.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix
        
        if not token:
            await websocket.close(code=1008)
            logger.warning(
                f"Parent WebSocket rejected: missing token for parent {parent_id}"
            )
            return
        
        # Import TokenManager here to avoid circular imports  
        from src.infrastructure.security.auth import TokenManager, AuthenticationError
        from src.infrastructure.config.config_provider import get_config_from_state
        
        # Create TokenManager with config from app state (no module-level get_config)
        config = getattr(websocket.app.state, "config", None)
        if config is None:
            await websocket.close(code=1011, reason="Service not ready")
            return
        token_manager = TokenManager(config=config)
        try:
            # Use async verify_token (following the auth.py pattern)
            payload = await token_manager.verify_token(token)
            
            # Ensure token is for a parent and matches parent_id
            token_user_id = payload.get("sub")
            token_user_type = payload.get("user_type", "parent")
            
            if token_user_type != "parent":
                await websocket.close(code=1008)
                logger.warning(
                    f"Parent WebSocket rejected: token is not for parent user (type: {token_user_type})"
                )
                return
                
            if not token_user_id or token_user_id != parent_id:
                await websocket.close(code=1008)
                logger.warning(
                    f"Parent WebSocket rejected: parent_id mismatch (token: {token_user_id}, param: {parent_id})"
                )
                return
                
        except AuthenticationError as e:
            await websocket.close(code=1008)
            logger.warning(
                f"Parent WebSocket rejected: invalid token for parent {parent_id} ({e})"
            )
            return
        except Exception as e:
            await websocket.close(code=1011)
            logger.error(
                f"Parent WebSocket error during token verification for {parent_id}: {e}"
            )
            return

        # Register WebSocket connection
        websocket_adapter = real_time_service.websocket_adapter
        connection_id = await websocket_adapter.connect(
            websocket=websocket,
            user_id=parent_id,
            metadata={"connection_type": "parent_dashboard", "client": "mobile_app"},
        )

        # Register for real-time notifications (all alert types by default)
        await real_time_service.register_parent_connection(
            parent_id=parent_id,
            connection_id=connection_id,
            alert_subscriptions=list(AlertType),
        )

        logger.info(
            f"Parent {parent_id} connected via WebSocket (connection: {connection_id})"
        )

        # Send initial status
        await websocket.send_json(
            {
                "type": "connection_established",
                "message": "Real-time notifications enabled",
                "connection_id": connection_id,
                "timestamp": "2025-08-04T10:00:00Z",
                "features": {
                    "safety_alerts": True,
                    "behavior_monitoring": True,
                    "usage_tracking": True,
                    "premium_features": True,
                },
            }
        )

        # Listen for incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)

                await handle_parent_message(
                    parent_id=parent_id,
                    connection_id=connection_id,
                    message_data=message_data,
                    websocket=websocket,
                    real_time_service=real_time_service,
                )

            except WebSocketDisconnect:
                logger.info(f"Parent {parent_id} disconnected from WebSocket")
                break
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from parent {parent_id}: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Invalid JSON format",
                        "timestamp": "2025-08-04T10:00:00Z",
                    }
                )
            except Exception as e:
                logger.error(f"Error handling parent message: {e}", exc_info=True)
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Internal server error",
                        "timestamp": "2025-08-04T10:00:00Z",
                    }
                )

    except Exception as e:
        logger.error(
            f"WebSocket connection error for parent {parent_id}: {e}", exc_info=True
        )
        try:
            await websocket.send_json(
                {
                    "type": "connection_error",
                    "message": "Failed to establish connection",
                    "error": str(e),
                    "timestamp": "2025-08-04T10:00:00Z",
                }
            )
        except Exception:
            pass

    finally:
        # Clean up connection
        if connection_id:
            try:
                await real_time_service.websocket_adapter.disconnect(
                    connection_id, "client_disconnected"
                )
            except Exception as e:
                logger.error(f"Error cleaning up WebSocket connection: {e}")


async def handle_parent_message(
    parent_id: str,
    connection_id: str,
    message_data: Dict[str, Any],
    websocket: WebSocket,
    real_time_service: RealTimeNotificationService,
) -> None:
    """Handle incoming messages from parent WebSocket client."""
    try:
        message_type = message_data.get("type")

        if message_type == "ping":
            # Heartbeat response
            await websocket.send_json(
                {"type": "pong", "timestamp": "2025-08-04T10:00:00Z"}
            )

        elif message_type == "subscribe_alerts":
            # Update alert subscriptions
            alert_types_raw = message_data.get("alert_types", [])
            try:
                alert_types = [AlertType(alert) for alert in alert_types_raw]
                success = await real_time_service.update_parent_subscriptions(
                    parent_id=parent_id, alert_types=alert_types
                )

                await websocket.send_json(
                    {
                        "type": "subscription_updated",
                        "success": success,
                        "subscribed_alerts": alert_types_raw,
                        "timestamp": "2025-08-04T10:00:00Z",
                    }
                )

            except ValueError as e:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Invalid alert type: {e}",
                        "timestamp": "2025-08-04T10:00:00Z",
                    }
                )

        elif message_type == "map_child":
            # Map child to parent for notifications
            child_id = message_data.get("child_id")
            if child_id:
                await real_time_service.map_child_to_parent(child_id, parent_id)
                await websocket.send_json(
                    {
                        "type": "child_mapped",
                        "child_id": child_id,
                        "timestamp": "2025-08-04T10:00:00Z",
                    }
                )

        elif message_type == "get_metrics":
            # Send real-time metrics
            metrics = await real_time_service.get_real_time_metrics()
            await websocket.send_json(
                {
                    "type": "metrics",
                    "data": metrics,
                    "timestamp": "2025-08-04T10:00:00Z",
                }
            )

        # SECURITY FIX: Removed test alert functionality - production endpoints should not have test functions

        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": "2025-08-04T10:00:00Z",
                }
            )

    except Exception as e:
        logger.error(f"Error handling parent message: {e}", exc_info=True)
        await websocket.send_json(
            {
                "type": "error",
                "message": "Failed to process message",
                "timestamp": "2025-08-04T10:00:00Z",
            }
        )


# SECURITY FIX: Removed unsecured admin monitoring WebSocket endpoint
# Admin access must be implemented with proper authentication and authorization
# This endpoint was accessible without any authentication checks

# SECURITY FIX: Complete removal of admin endpoint implementation


# Helper functions for triggering real-time notifications
async def trigger_safety_alert(
    child_id: str, safety_data: Dict[str, Any], priority: str = "high"
) -> bool:
    """
    Helper function to trigger safety alert via WebSocket.

    Can be called from other services when safety events occur.
    """
    try:
        real_time_service = get_real_time_notification_service()

        priority_enum = NotificationPriority(priority.lower())

        return await real_time_service.send_safety_alert(
            child_id=child_id, alert_data=safety_data, priority=priority_enum
        )

    except Exception as e:
        logger.error(f"Error triggering safety alert: {e}", exc_info=True)
        return False


async def trigger_behavior_alert(child_id: str, behavior_data: Dict[str, Any]) -> bool:
    """Helper function to trigger behavior alert via WebSocket."""
    try:
        real_time_service = get_real_time_notification_service()

        return await real_time_service.send_behavior_alert(
            child_id=child_id,
            behavior_data=behavior_data,
            priority=NotificationPriority.MEDIUM,
        )

    except Exception as e:
        logger.error(f"Error triggering behavior alert: {e}", exc_info=True)
        return False


async def trigger_usage_alert(child_id: str, usage_data: Dict[str, Any]) -> bool:
    """Helper function to trigger usage limit alert via WebSocket."""
    try:
        real_time_service = get_real_time_notification_service()

        return await real_time_service.send_usage_limit_alert(
            child_id=child_id, limit_data=usage_data, priority=NotificationPriority.LOW
        )

    except Exception as e:
        logger.error(f"Error triggering usage alert: {e}", exc_info=True)
        return False


async def trigger_premium_alert(parent_id: str, feature_data: Dict[str, Any]) -> bool:
    """Helper function to trigger premium feature alert via WebSocket."""
    try:
        real_time_service = get_real_time_notification_service()

        return await real_time_service.send_premium_feature_alert(
            parent_id=parent_id,
            feature_data=feature_data,
            priority=NotificationPriority.LOW,
        )

    except Exception as e:
        logger.error(f"Error triggering premium alert: {e}", exc_info=True)
        return False


@router.websocket("/esp32/{device_id}")
async def esp32_websocket_endpoint(
    websocket: WebSocket,
    device_id: str,
):
    """
    WebSocket endpoint for ESP32 device communication.
    - device_id: Unique identifier for the ESP32 device
    - Requires ?token=YOUR_SECURE_ESP32_TOKEN in query params
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        logger.warning(
            f"ESP32 WebSocket rejected: missing token for device {device_id}"
        )
        return

    # Import TokenManager here to avoid circular imports
    from src.infrastructure.security.auth import TokenManager, AuthenticationError

    # Create TokenManager with config from app state (no module-level get_config)
    config = getattr(websocket.app.state, "config", None)
    if config is None:
        await websocket.close(code=1011, reason="Service not ready")
        return
    token_manager = TokenManager(config=config)
    try:
        payload = await token_manager.verify_token(token)
        # Extract device_id from subject field (format: device_id:child_id)
        subject = payload.get("sub")
        if not subject or ":" not in subject:
            await websocket.close(code=1008)
            logger.warning(
                f"ESP32 WebSocket rejected: invalid token subject format for device {device_id}"
            )
            return
            
        token_device_id = subject.split(":")[0]
        if token_device_id != device_id:
            await websocket.close(code=1008)
            logger.warning(
                f"ESP32 WebSocket rejected: device_id mismatch (token: {token_device_id}, param: {device_id})"
            )
            return
    except AuthenticationError as e:
        await websocket.close(code=1008)
        logger.warning(
            f"ESP32 WebSocket rejected: invalid token for device {device_id} ({e})"
        )
        return
    except Exception as e:
        await websocket.close(code=1011)
        logger.error(
            f"ESP32 WebSocket error during token verification for {device_id}: {e}"
        )
        return

    await websocket.accept()
    logger.info(f"ESP32 WebSocket connected: device_id={device_id}")
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received from ESP32 {device_id}: {data}")
            # هنا يمكنك معالجة البيانات أو الرد على الجهاز
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logger.info(f"ESP32 WebSocket disconnected: device_id={device_id}")
    except Exception as e:
        logger.error(f"ESP32 WebSocket error for {device_id}: {e}")
        await websocket.close()
