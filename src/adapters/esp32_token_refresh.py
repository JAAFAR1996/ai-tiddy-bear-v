"""
ESP32 Token Refresh Endpoint
"""
import logging
import os
import time
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Create router for token refresh
token_refresh_router = APIRouter(tags=["ESP32-Token"])

@token_refresh_router.post("/refresh")
async def refresh_esp32_token(
    device_id: str = Query(..., description="ESP32 device identifier"),
    old_token: str = Query(..., description="Expired JWT token")
):
    """
    Refresh expired ESP32 JWT token
    """
    try:
        # Validate device_id format
        if not device_id or len(device_id) < 8:
            raise HTTPException(status_code=400, detail="Invalid device_id")
        
        # Create new JWT token with extended expiry
        current_time = int(time.time())
        new_token_payload = {
            "sub": f"device:{device_id}:child:child-unknown",
            "device_id": device_id,
            "child_id": "child-unknown", 
            "session_id": f"refresh-{current_time}",
            "type": "device_access",
            "aud": "teddy-api",
            "iss": "teddy-device-system",
            "iat": current_time,
            "exp": current_time + (24 * 60 * 60)  # 24 hours from now
        }
        
        # Import JWT creation (simplified for immediate fix)
        import jwt
        secret = os.getenv("JWT_SECRET_KEY", "fallback-secret")
        
        new_token = jwt.encode(new_token_payload, secret, algorithm="HS256")
        
        logger.info(f"Generated new JWT token for device {device_id}")
        
        return JSONResponse({
            "success": True,
            "new_token": new_token,
            "expires_at": new_token_payload["exp"],
            "device_id": device_id
        })
        
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(status_code=500, detail="Token refresh failed")

@token_refresh_router.get("/generate")
async def generate_fresh_token(
    device_id: str = Query(..., description="ESP32 device identifier")
):
    """
    Generate fresh JWT token for ESP32
    """
    try:
        current_time = int(time.time())
        token_payload = {
            "sub": f"device:{device_id}:child:child-unknown",
            "device_id": device_id,
            "child_id": "child-unknown",
            "session_id": f"fresh-{current_time}",
            "type": "device_access", 
            "aud": "teddy-api",
            "iss": "teddy-device-system",
            "iat": current_time,
            "exp": current_time + (24 * 60 * 60)  # 24 hours
        }
        
        import jwt
        secret = os.getenv("JWT_SECRET_KEY", "fallback-secret")
        token = jwt.encode(token_payload, secret, algorithm="HS256")
        
        logger.info(f"Generated fresh JWT token for device {device_id}")
        
        return JSONResponse({
            "success": True,
            "token": token,
            "expires_at": token_payload["exp"],
            "device_id": device_id,
            "issued_at": current_time
        })
        
    except Exception as e:
        logger.error(f"Fresh token generation failed: {e}")
        raise HTTPException(status_code=500, detail="Token generation failed")