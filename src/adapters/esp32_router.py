"""
ESP32 WebSocket Endpoint for AI Teddy Bear
=========================================
Production-ready WebSocket endpoint for ESP32 devices.
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from typing import Optional

from ..services.esp32_chat_server import esp32_chat_server


logger = logging.getLogger(__name__)
router = APIRouter(tags=["ESP32"])


@router.websocket("/chat")
async def esp32_chat_websocket(
    websocket: WebSocket,
    device_id: str = Query(
        ..., min_length=8, max_length=32, description="Unique ESP32 device identifier"
    ),
    child_id: str = Query(
        ..., min_length=1, max_length=50, description="Child profile identifier"
    ),
    child_name: str = Query(
        ..., min_length=1, max_length=30, description="Child's name"
    ),
    child_age: int = Query(..., ge=3, le=13, description="Child's age (3-13)"),
):
    """
    WebSocket endpoint for ESP32 AI Teddy Bear chat.

    Real-time communication endpoint supporting:
    - Audio streaming (Speech-to-Text)
    - AI response generation
    - Text-to-Speech response streaming
    - Child safety validation
    - Session management

    Query Parameters:
    - device_id: Unique ESP32 device identifier (8-32 alphanumeric chars)
    - child_id: Child profile identifier
    - child_name: Child's name for personalization
    - child_age: Child's age (must be 3-13 for COPPA compliance)

    Message Protocol:
    {
        "type": "audio_chunk|text_message|heartbeat|system_status",
        "data": {...},
        "timestamp": "ISO-8601"
    }
    """
    session_id: Optional[str] = None

    try:
        # Input validation and sanitization
        import re

        # Sanitize device_id
        device_id = re.sub(r"[^a-zA-Z0-9_-]", "", device_id)
        if not device_id or len(device_id) < 8:
            await websocket.close(code=1008, reason="Invalid device ID")
            return

        # Sanitize child_id
        child_id = re.sub(r"[^a-zA-Z0-9_-]", "", child_id)
        if not child_id:
            await websocket.close(code=1008, reason="Invalid child ID")
            return

        # Sanitize child_name
        child_name = re.sub(r"[^a-zA-Z0-9\s]", "", child_name[:30])
        if not child_name:
            child_name = "friend"

        # Validate child_age
        if not isinstance(child_age, int) or not (3 <= child_age <= 13):
            await websocket.close(code=1008, reason="Invalid child age")
            return

        # Connect device and create session
        session_id = await esp32_chat_server.connect_device(
            websocket=websocket,
            device_id=device_id,
            child_id=child_id,
            child_name=child_name,
            child_age=child_age,
        )

        logger.info(
            f"ESP32 WebSocket connected: device_id={device_id}, session_id={session_id}"
        )

        # Message handling loop
        while True:
            try:
                # Receive message from ESP32 with size limit
                raw_message = await websocket.receive_text()

                # Validate message size
                if len(raw_message) > 10000:  # 10KB limit
                    logger.warning(f"Message too large from session {session_id}")
                    await esp32_chat_server._send_error(
                        session_id, "message_too_large", "Message exceeds size limit"
                    )
                    continue

                # Basic message validation
                if not raw_message.strip():
                    continue

                # Handle message through chat server
                await esp32_chat_server.handle_message(session_id, raw_message)

            except WebSocketDisconnect:
                logger.info(f"ESP32 WebSocket disconnected: session_id={session_id}")
                break
            except Exception as e:
                logger.error(f"Message handling error: {e}", exc_info=True)
                # Send error to ESP32 if possible
                try:
                    await esp32_chat_server._send_error(
                        session_id, "processing_error", str(e)
                    )
                except Exception:
                    pass
                break

    except HTTPException:
        # Re-raise FastAPI exceptions (validation errors)
        raise
    except Exception as e:
        logger.error(f"ESP32 WebSocket connection error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
    finally:
        # Cleanup session
        if session_id:
            await esp32_chat_server.disconnect_device(session_id, "websocket_closed")


@router.get("/metrics")
async def esp32_metrics():
    """ESP32 Chat Server metrics."""
    return esp32_chat_server.get_session_metrics()


# SECURITY FIX: Removed test endpoint - production should not expose test functionality
# Device validation should happen during actual connection establishment only
