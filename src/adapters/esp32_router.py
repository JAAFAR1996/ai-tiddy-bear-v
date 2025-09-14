"""
ESP32 WebSocket Endpoint for AI Teddy Bear
=========================================
Production-ready WebSocket endpoint for ESP32 devices with separated public/private routes.
"""

import logging
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Query,
    HTTPException,
    Depends,
    Response,
    Request,
)
from fastapi.security import HTTPBearer
from typing import Optional, Dict, Any
import hashlib
import json
import os
import time
from pathlib import Path
from starlette.requests import HTTPConnection

from ..services.esp32_chat_server import esp32_chat_server
from ..infrastructure.security.auth import get_current_user

# Module-level logger and one-time log flag (declare before use)
logger = logging.getLogger(__name__)
_esp32_expected_prefix_logged = False


def valid_esp32_token(token: str, device_id: str) -> bool:
    """
    Validate ESP32 device token with production-grade security.
    Expected: HMAC-SHA256(device_id, ESP32_SHARED_SECRET) as hex string
    """
    SECRET = os.getenv("ESP32_SHARED_SECRET", "")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    
    # Basic token format validation
    if not token or len(token) < 24:
        return False
    
    # Production: Require proper HMAC tokens
    if ENVIRONMENT == "production":
        if not SECRET:
            logger.error("ESP32_SHARED_SECRET not set in production!")
            return False
        
        # Must be 64-char hex HMAC
        if len(token) != 64 or not all(c in "0123456789abcdef" for c in token.lower()):
            return False
        
        if not device_id:
            return False
            
        import hmac
        import hashlib
        expected = hmac.new(
            SECRET.encode(), 
            device_id.encode(), 
            hashlib.sha256
        ).hexdigest()
        # Log expected prefix once for client/server comparison
        global _esp32_expected_prefix_logged
        if not _esp32_expected_prefix_logged:
            try:
                logger.info(f"ESP32 expected HMAC prefix: {expected[:8]}")
            except Exception:
                pass
            _esp32_expected_prefix_logged = True
        return hmac.compare_digest(token.lower(), expected)
    
    # Development: Allow HMAC or fallback to simple validation
    if SECRET and len(token) == 64 and all(c in "0123456789abcdef" for c in token.lower()):
        if device_id:
            import hmac
            import hashlib
            expected = hmac.new(
                SECRET.encode(), 
                device_id.encode(), 
                hashlib.sha256
            ).hexdigest()
            # Log expected prefix once for client/server comparison
            global _esp32_expected_prefix_logged
            if not _esp32_expected_prefix_logged:
                try:
                    logger.info(f"ESP32 expected HMAC prefix: {expected[:8]}")
                except Exception:
                    pass
                _esp32_expected_prefix_logged = True
            return hmac.compare_digest(token.lower(), expected)
    
    # Development fallback: accept long alphanumeric tokens
    return len(token) >= 24 and token.replace("-", "").replace("_", "").isalnum()


async def ws_auth_dependency(websocket: WebSocket) -> Dict[str, str]:
    """
    WebSocket authentication with enhanced token validation.
    ESP32 devices must pass: /chat?token=HMAC_TOKEN&device_id=...
    """
    try:
        # Only accept token from query parameter for ESP32 devices (no Authorization header)
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="Authentication required")
            raise HTTPException(status_code=403, detail="Token required")
        
        # Enhanced validation for ESP32 devices
        device_id = websocket.query_params.get("device_id", "")
        if device_id and len(device_id) >= 8:
            if not valid_esp32_token(token, device_id):
                # Extra diagnostics: log token/expected prefixes to help field debugging
                try:
                    secret = os.getenv("ESP32_SHARED_SECRET", "")
                    if secret:
                        import hmac as _hmac
                        import hashlib as _hashlib
                        _expected = _hmac.new(secret.encode(), device_id.encode(), _hashlib.sha256).hexdigest()
                        logger.warning(
                            f"Invalid ESP32 token for device {device_id} (got={token[:8]}, expected={_expected[:8]})"
                        )
                    else:
                        logger.warning(f"Invalid ESP32 token for device {device_id} (secret missing)")
                except Exception:
                    logger.warning(f"Invalid ESP32 token for device {device_id}")
                await websocket.close(code=1008, reason="Invalid token format")
                raise HTTPException(status_code=403, detail="Invalid token format")

            return {"type": "device", "device_id": device_id, "token": token}
        
        # For user tokens, require minimum length and format
        if not valid_esp32_token(token, ""):
            logger.warning(f"Invalid user token format")
            await websocket.close(code=1008, reason="Invalid token format") 
            raise HTTPException(status_code=403, detail="Invalid token format")
            
        return {"type": "user", "token": token}
        
    except HTTPException:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")
        raise

# logger and flag defined above


class FirmwareManager:
    """
    مدير ملفات الفيرموير - يقرأ الملفات الحقيقية ويحسب الحجم والـ SHA256 تلقائياً
    """
    
    @staticmethod
    def get_firmware_info(firmware_filename: str) -> Dict[str, Any]:
        """
        يحصل على معلومات الفيرموير من الملف الحقيقي
        
        Args:
            firmware_filename: اسم ملف الفيرموير
            
        Returns:
            معلومات الملف: حجم، SHA256، تاريخ التعديل، etc.
        """
        # Define possible firmware locations (production-safe paths only)
        firmware_paths = [
            f"src/static/firmware/{firmware_filename}",
            f"/app/src/static/firmware/{firmware_filename}",
            f"static/firmware/{firmware_filename}",
            f"/app/static/firmware/{firmware_filename}",
        ]

        for firmware_path in firmware_paths:
            if os.path.exists(firmware_path):
                try:
                    # Get file stats
                    stat_info = os.stat(firmware_path)
                    file_size = stat_info.st_size
                    last_modified = int(stat_info.st_mtime)
                    
                    # Calculate SHA256
                    sha256_hash = hashlib.sha256()
                    with open(firmware_path, "rb") as f:
                        while chunk := f.read(8192):  # 8KB chunks for efficiency
                            sha256_hash.update(chunk)
                    hash_result = sha256_hash.hexdigest()
                    
                    # Validate ESP32 firmware format
                    is_valid = FirmwareManager._is_valid_esp32_firmware(firmware_path, file_size)
                    
                    logger.info(
                        f"✅ Found firmware {firmware_filename}: {file_size} bytes, SHA256: {hash_result[:16]}..., Valid: {is_valid}"
                    )
                    
                    return {
                        "exists": True,
                        "path": firmware_path,
                        "size": file_size,
                        "sha256": hash_result,
                        "modified": last_modified,
                        "valid": is_valid
                    }
                except Exception as e:
                    logger.error(f"❌ Error reading firmware {firmware_path}: {e}")
                    continue

        # Fallback for missing firmware - deterministic placeholder
        placeholder_data = f"TEDDY_BEAR_FIRMWARE_V{FIRMWARE_VERSION}_{firmware_filename}".encode()
        placeholder_hash = hashlib.sha256(placeholder_data).hexdigest()
        
        logger.warning(
            f"⚠️ Firmware file {firmware_filename} not found. Using placeholder values."
        )
        
        return {
            "exists": False,
            "path": None,
            "size": 1048576,  # 1MB placeholder
            "sha256": placeholder_hash,
            "modified": int(time.time()),
            "valid": False
        }
    
    @staticmethod
    def _is_valid_esp32_firmware(file_path: str, file_size: int) -> bool:
        """
        Validate if file is a proper ESP32 firmware image.
        
        ESP32 firmware must have:
        - Minimum size (typically 200KB+ for real applications)
        - ESP32 image header format
        
        Args:
            file_path: Path to firmware file
            file_size: Size of the file in bytes
            
        Returns:
            True if valid ESP32 firmware, False otherwise
        """
        # ESP32 firmware minimum size check (200KB minimum for real firmware)
        MIN_FIRMWARE_SIZE = 200 * 1024  # 200KB
        
        if file_size < MIN_FIRMWARE_SIZE:
            logger.warning(f"⚠️ Firmware too small: {file_size} bytes (minimum: {MIN_FIRMWARE_SIZE})")
            return False
        
        # Check ESP32 image header (basic validation)
        try:
            with open(file_path, "rb") as f:
                # Read first 24 bytes (ESP32 image header)
                header = f.read(24)
                if len(header) < 24:
                    return False
                    
                # ESP32 image magic byte (0xE9 at offset 0)
                if header[0] != 0xE9:
                    logger.warning(f"⚠️ Invalid ESP32 magic byte: {hex(header[0])}")
                    return False
                    
                # Basic segment count check (should be reasonable)
                segment_count = header[1]
                if segment_count == 0 or segment_count > 16:
                    logger.warning(f"⚠️ Invalid segment count: {segment_count}")
                    return False
                    
                logger.info(f"✅ Valid ESP32 firmware detected: {segment_count} segments")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error validating firmware: {e}")
            return False

# Application version - single source of truth
APP_VERSION = "1.3.0"

# متغيرات الفيرموير - يمكن تغييرها من Environment Variables
FIRMWARE_FILENAME = os.getenv("FIRMWARE_FILENAME", "teddy-001.bin")
FIRMWARE_VERSION  = os.getenv("FIRMWARE_VERSION",  "1.2.1")
PUBLIC_HOST       = os.getenv("PUBLIC_HOST", "ai-tiddy-bear-v.onrender.com")

# Public router - no authentication required (prefix handled by RouteManager)
esp32_public = APIRouter(tags=["ESP32-Public"])

# Private router - authentication required (prefix handled by RouteManager)
esp32_private = APIRouter(
    tags=["ESP32-Private"],
    # NOTE: WebSocket auth handled separately - HTTPBearer doesn't work with WebSocket
)


# LEGACY: Wrapper functions for backward compatibility - use FirmwareManager directly
def _get_firmware_info(firmware_filename: str) -> Dict[str, Any]:
    """DEPRECATED: Use FirmwareManager.get_firmware_info() instead"""
    return FirmwareManager.get_firmware_info(firmware_filename)

def _calculate_firmware_sha256(firmware_filename: str) -> str:
    """DEPRECATED: Use FirmwareManager.get_firmware_info() instead"""
    return FirmwareManager.get_firmware_info(firmware_filename)["sha256"]


@esp32_private.websocket("/chat")
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
    auth_info: Dict[str, str] = Depends(ws_auth_dependency),
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


# PUBLIC ROUTES - No authentication required
@esp32_public.get("/config")
async def get_device_config(request: Request, response: Response):
    """
    Get device configuration for ESP32 devices.
    Public endpoint for initial device setup with ETag support.
    """
    config = {
        "host": PUBLIC_HOST,
        "port": 443,
        "ws_path": "/api/v1/esp32/private/chat",  # ✅ Corrected to match actual WebSocket endpoint
        "firmware_endpoint": "/api/v1/esp32/firmware",  # صريح للـESP32
        "tls": True,
        "ntp": ["pool.ntp.org", "time.google.com", "time.cloudflare.com", "time.nist.gov"],
        "features": {
            "ota": True, 
            "strict_tls": True,
            "audio_streaming": True,
            "child_safety": True
        },
        "app_version": APP_VERSION,  # نسخة التطبيق
        "firmware_version": FIRMWARE_VERSION,  # نسخة الفيرموير
        "timestamp": int(time.time())
    }

    # Generate stable ETag (exclude timestamp for proper caching)
    stable_config = {k: v for k, v in config.items() if k != "timestamp"}
    etag = '"' + hashlib.sha256(
        json.dumps(stable_config, sort_keys=True).encode()
    ).hexdigest()[:16] + '"'
    
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=600, stale-while-revalidate=60"
    
    # Check If-None-Match header for 304 response
    if_none_match = request.headers.get("if-none-match")
    if if_none_match == etag:
        return Response(status_code=304)
    
    # Add improved security headers for successful responses
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Child safety headers
    response.headers["X-Child-Safe"] = "true"
    response.headers["X-COPPA-Compliant"] = "true"
    # Remove deprecated X-XSS-Protection

    return config


@esp32_public.get("/firmware")
async def get_firmware_manifest(request: Request, response: Response):
    """
    يعيد معلومات التحديث (النسخة + الحجم + sha256 + رابط التنزيل)
    الحجم والهاش ينحسبون من الملف الحقيقي على السيرفر.
    """
    try:
        firmware_info = FirmwareManager.get_firmware_info(FIRMWARE_FILENAME)
        
        # Check if firmware file exists
        if not firmware_info["exists"]:
            logger.warning(f"⚠️ Firmware file {FIRMWARE_FILENAME} not found - returning 404")
            raise HTTPException(status_code=404, detail="Firmware not available")
        
        # Check if firmware is valid
        if not firmware_info["valid"]:
            logger.error(f"❌ Invalid firmware file {FIRMWARE_FILENAME} - corrupted or wrong format")
            raise HTTPException(status_code=503, detail="Firmware validation failed")

        manifest = {
            "version": FIRMWARE_VERSION,  # إنت تغيّرها لما تنزل إصدار جديد
            "build": int(time.time()),
            "available": True,
            "mandatory": False,
            "url": f"https://{PUBLIC_HOST}/web/firmware/{FIRMWARE_FILENAME}",
            "sha256": firmware_info["sha256"],  # ينحسب تلقائي
            "size":   firmware_info["size"],    # ينحسب تلقائي
            "notes":  "Release build with pinned Root CA and size-optimized flags",
            "compatibility": {
                "min_hardware_version": "1.0.0",
                "max_hardware_version": "2.0.0",
                "required_bootloader":  "1.1.0"
            },
            "meta": {
                "timestamp": int(time.time()),
                "request_id": getattr(request.state, "request_id", "unknown"),
                "file_exists": firmware_info["exists"],
                "last_modified": firmware_info["modified"],
                "validated": firmware_info["valid"]
            }
        }

        # Generate stable ETag (exclude dynamic timestamps for proper caching)
        stable_manifest = {
            "version": manifest["version"],
            "available": manifest["available"], 
            "url": manifest["url"],
            "sha256": manifest["sha256"],
            "size": manifest["size"],
            "notes": manifest["notes"],
            "compatibility": manifest["compatibility"]
        }
        etag = f'"{hashlib.sha256(json.dumps(stable_manifest, sort_keys=True).encode()).hexdigest()[:16]}"'
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
        
        # Check If-None-Match header for 304 response
        if_none_match = request.headers.get("if-none-match")
        if if_none_match == etag:
            return Response(status_code=304)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Child-Safe"] = "true"
        response.headers["X-COPPA-Compliant"] = "true"
        
        # Log request
        client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"
        logger.info(f"✅ Firmware manifest served to {client_ip} - {FIRMWARE_FILENAME} v{FIRMWARE_VERSION}")
        
        return manifest

    except HTTPException as he:
        # لا تحوّل 404/503 إلى 500
        raise he
    except Exception as e:
        logger.error(f"❌ Error serving firmware manifest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Firmware service error")


# PRIVATE ROUTES - Authentication required
@esp32_private.get("/metrics")
async def esp32_metrics(current_user = Depends(get_current_user)):
    """ESP32 Chat Server metrics - requires authentication."""
    return esp32_chat_server.get_session_metrics()


# SECURITY FIX: Removed test endpoint - production should not expose test functionality
# Device validation should happen during actual connection establishment only
