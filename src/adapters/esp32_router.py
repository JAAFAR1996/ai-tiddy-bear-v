"""
ESP32 WebSocket Endpoint for AI Teddy Bear
=========================================
Simplified WebSocket endpoint for ESP32 devices.
"""

import logging
import os
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, WebSocket, Query, HTTPException

from ..services.esp32_chat_server import esp32_chat_server

# Module-level logger
logger = logging.getLogger(__name__)


async def ws_auth_dependency(websocket: WebSocket) -> Dict[str, str]:
    """
    Simplified WebSocket authentication - only requires device_id.
    """
    try:
        device_id = websocket.query_params.get("device_id", "")
        
        if not device_id:
            await websocket.close(code=1008, reason="Device ID required")
            raise HTTPException(status_code=403, detail="Device ID required")
        
        logger.info(f"Device {device_id} connecting")
        return {"type": "device", "device_id": device_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")
        raise


class FirmwareManager:
    """
    Firmware manager for ESP32 firmware files.
    """
    
    @staticmethod
    def get_firmware_info(firmware_filename: str) -> Dict[str, Any]:
        """
        Get firmware file info with security validation.
        """
        # Validate filename to prevent path traversal
        if not firmware_filename or ".." in firmware_filename or "/" in firmware_filename:
            return {
                "filename": "invalid",
                "size": 0,
                "sha256": "",
                "valid": False,
                "error": "Invalid filename"
            }
        
        # Safe firmware paths
        base_paths = ["src/static/firmware", "/app/static/firmware", "static/firmware"]
        
        for base_path in base_paths:
            try:
                # Use safe path joining
                firmware_path = Path(base_path) / firmware_filename
                
                # Ensure path is within allowed directory
                if not str(firmware_path.resolve()).startswith(str(Path(base_path).resolve())):
                    continue
                    
                if firmware_path.exists():
                    file_size = firmware_path.stat().st_size
                    
                    sha256_hash = hashlib.sha256()
                    with open(firmware_path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            sha256_hash.update(chunk)
                    
                    return {
                        "filename": firmware_filename,
                        "size": file_size,
                        "sha256": sha256_hash.hexdigest(),
                        "valid": True
                    }
            except (OSError, IOError, PermissionError) as e:
                logger.error(f"Error reading firmware file: {e}")
                continue
        
        return {
            "filename": firmware_filename,
            "size": 0,
            "sha256": "",
            "valid": False,
            "error": "File not found"
        }


# Create routers for RouteManager compatibility
router = APIRouter(prefix="/api/v1/esp32", tags=["ESP32"])
esp32_public = router  # Public router (same as main router)
esp32_private = APIRouter(prefix="/api/v1/esp32/private", tags=["ESP32-Private"])


@router.get("/config")
async def get_esp32_config():
    """Get ESP32 configuration."""
    return {
        "websocket_url": "/api/v1/esp32/chat",
        "firmware_version": "1.0.0",
        "status": "ok"
    }


@router.get("/firmware")
async def get_firmware_info():
    """Get firmware information."""
    try:
        return FirmwareManager.get_firmware_info("esp32_firmware.bin")
    except Exception as e:
        logger.error(f"Firmware info error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get firmware info")


@router.websocket("/chat")
async def websocket_endpoint(
    websocket: WebSocket,
    device_id: str = Query(...),
    child_id: Optional[str] = Query(None),
    child_name: Optional[str] = Query(None),
    child_age: Optional[int] = Query(None)
):
    """WebSocket endpoint for ESP32 chat."""
    auth_info = await ws_auth_dependency(websocket)
    await esp32_chat_server.handle_websocket_connection(
        websocket, auth_info, child_id, child_name, child_age
    )


# Private router endpoints (authenticated)
@esp32_private.get("/metrics")
async def get_private_metrics():
    """Get ESP32 metrics (private endpoint)."""
    try:
        # Get real metrics from esp32_chat_server
        metrics = esp32_chat_server.get_session_metrics()
        return {
            "active_sessions": metrics.get("active_sessions", 0),
            "total_messages": metrics.get("total_messages", 0),
            "uptime": f"{metrics.get('uptime_seconds', 0)//3600}h {(metrics.get('uptime_seconds', 0)%3600)//60}m",
            "status": "ok",
            "timestamp": metrics.get("timestamp")
        }
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return {
            "active_sessions": 0,
            "total_messages": 0,
            "uptime": "unknown",
            "status": "error"
        }


@esp32_private.websocket("/chat")
async def private_websocket_endpoint(
    websocket: WebSocket,
    device_id: str = Query(...),
    child_id: Optional[str] = Query(None),
    child_name: Optional[str] = Query(None),
    child_age: Optional[int] = Query(None)
):
    """Private WebSocket endpoint for ESP32 chat."""
    auth_info = await ws_auth_dependency(websocket)
    await esp32_chat_server.handle_websocket_connection(
        websocket, auth_info, child_id, child_name, child_age
    )