"""
ESP32 WebSocket Router - FastAPI Integration
===========================================
FastAPI router for ESP32 WebSocket connections with complete audio processing.
"""

import logging
from typing import Optional

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Query,
    Depends,
)
from fastapi.responses import JSONResponse

from src.services.esp32_production_runner import esp32_production_runner
from src.infrastructure.security.admin_security import (
    require_admin_permission,
    AdminPermission,
    SecurityLevel,
    AdminSession,
)


# Create router
esp32_router = APIRouter(tags=["ESP32"])
logger = logging.getLogger(__name__)


@esp32_router.on_event("startup")
async def startup_esp32_services():
    """Initialize ESP32 services on startup."""
    try:
        await esp32_production_runner.initialize_services()
        logger.info("ESP32 services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize ESP32 services: {e}", exc_info=True)
        raise


@esp32_router.websocket("/connect")
async def esp32_websocket_endpoint(
    websocket: WebSocket,
    device_id: str = Query(..., description="ESP32 device identifier"),
    child_id: str = Query(..., description="Child profile identifier"),
    child_name: str = Query(..., description="Child's name"),
    child_age: int = Query(..., description="Child's age (3-13)"),
):
    """
    WebSocket endpoint for ESP32 device connections.

    Complete audio processing pipeline:
    1. Device authentication and session creation
    2. Real-time audio streaming
    3. Speech-to-Text conversion (Whisper)
    4. AI response generation
    5. Text-to-Speech conversion
    6. Audio response streaming back to device

    Query Parameters:
    - device_id: Unique ESP32 device identifier (8-32 chars, alphanumeric)
    - child_id: Child profile UUID
    - child_name: Child's display name
    - child_age: Child's age (must be 3-13 for COPPA compliance)

    WebSocket Message Format:

    Audio Messages (ESP32 -> Server):
    {
        "type": "audio_start",
        "audio_session_id": "uuid"
    }
    {
        "type": "audio_chunk",
        "audio_data": "base64_encoded_audio",
        "chunk_id": "uuid",
        "audio_session_id": "uuid",
        "is_final": false
    }
    {
        "type": "audio_end",
        "audio_session_id": "uuid"
    }

    Response Messages (Server -> ESP32):
    {
        "type": "audio_response",
        "audio_data": "base64_encoded_audio",
        "text": "AI response text",
        "format": "mp3",
        "audio_rate": 22050
    }

    System Messages:
    {
        "type": "system",
        "data": {
            "type": "connection_established",
            "session_id": "uuid",
            "message": "Hello! I'm ready to chat!"
        }
    }

    Error Messages:
    {
        "type": "error",
        "error_code": "error_type",
        "error_message": "Human readable error"
    }
    """
    chat_server = esp32_production_runner.get_chat_server()

    if not chat_server:
        await websocket.close(code=1011, reason="Server not initialized")
        return

    session_id = None

    try:
        # Connect device and create session
        session_id = await chat_server.connect_device(
            websocket=websocket,
            device_id=device_id,
            child_id=child_id,
            child_name=child_name,
            child_age=child_age,
        )

        logger.info(
            f"ESP32 device connected via WebSocket",
            extra={
                "session_id": session_id,
                "device_id": device_id,
                "child_id": child_id,
                "child_age": child_age,
            },
        )

        # Handle messages
        while True:
            try:
                # Receive message from ESP32
                raw_message = await websocket.receive_text()

                # Process message through chat server
                await chat_server.handle_message(session_id, raw_message)

            except WebSocketDisconnect:
                logger.info(f"ESP32 device disconnected: {session_id}")
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)
                # Continue processing other messages

    except HTTPException as e:
        logger.warning(f"ESP32 connection rejected: {e.detail}")
        try:
            await websocket.close(code=e.status_code, reason=e.detail)
        except Exception as close_e:
            logger.error(
                f"Exception closing WebSocket connection after HTTP rejection: {close_e}",
                exc_info=True,
            )
            # Continue - connection may already be closed by client
    except Exception as e:
        logger.error(f"ESP32 WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception as close_e:
            logger.error(
                f"Exception closing WebSocket connection after internal error: {close_e}",
                exc_info=True,
            )
            # Continue - connection may already be closed or in invalid state
    finally:
        # Cleanup session
        if session_id and chat_server:
            try:
                await chat_server.disconnect_device(session_id, "websocket_closed")
            except Exception as e:
                logger.error(f"Error cleaning up session: {e}")


@esp32_router.get("/metrics")
async def esp32_metrics():
    """
    Get ESP32 Chat Server metrics.

    Returns:
        JSON with session metrics, service status, and performance data
    """
    try:
        chat_server = esp32_production_runner.get_chat_server()

        if not chat_server:
            return JSONResponse(
                status_code=503, content={"error": "Server not initialized"}
            )

        metrics = chat_server.get_session_metrics()

        return JSONResponse(status_code=200, content=metrics)

    except Exception as e:
        logger.error(f"Failed to get metrics: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@esp32_router.post("/admin/shutdown")
async def esp32_admin_shutdown(
    session: AdminSession = Depends(
        require_admin_permission(AdminPermission.SYSTEM_ADMIN, SecurityLevel.CRITICAL)
    )
):
    """
    🔒 SECURED: Administrative endpoint to gracefully shutdown ESP32 Chat Server.

    CRITICAL SECURITY: Requires SYSTEM_ADMIN permission + MFA + Certificate auth.
    """
    try:
        await esp32_production_runner.shutdown()

        return JSONResponse(
            status_code=200,
            content={
                "message": "ESP32 Chat Server shutdown initiated",
                "initiated_by": session.user_id,
                "timestamp": "2025-01-27T12:00:00Z",
            },
        )

    except Exception as e:
        logger.error(f"Shutdown failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


# Export router for inclusion in main FastAPI app
__all__ = ["esp32_router"]
