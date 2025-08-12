from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from hmac import compare_digest
from hashlib import sha256
from time import time as get_time
from os import getenv
from jwt import encode as jwt_encode, decode as jwt_decode, ExpiredSignatureError, InvalidTokenError
from redis import Redis
from typing import Optional
import logging
import re

router = APIRouter()
logger = logging.getLogger(__name__)

try:
    r = Redis(host=getenv("REDIS_HOST", "localhost"), decode_responses=True)
    r.ping()  # Test connection
except Exception as e:
    logging.error(f"Redis connection failed: {e}")
    r = None

ACCESS_TTL = 3600
REFRESH_TTL = 60*24*3600

class ClaimRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    child_id: str = Field(min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    nonce: str = Field(min_length=10, max_length=100)
    hmac_hex: str = Field(pattern=r'^[0-9a-fA-F]{64}$')

class TokenResponse(BaseModel):
    access: str
    refresh: str

class RefreshRequest(BaseModel):
    refresh_token: str

def verify_nonce_once(nonce: str) -> None:
    if not r:
        raise HTTPException(status_code=503, detail="Service unavailable")
    if not r.setnx(f"nonce:{nonce}", "1"):
        raise HTTPException(status_code=409, detail="Nonce replay detected")
    r.expire(f"nonce:{nonce}", 300)

def verify_hmac(device_id: str, child_id: str, nonce: str, hmac_hex: str, oob_secret_hex: str) -> bool:
    try:
        import hmac
        mac = hmac.new(bytes.fromhex(oob_secret_hex), digestmod=sha256)
        mac.update(device_id.encode('utf-8'))
        mac.update(child_id.encode('utf-8'))
        mac.update(nonce.encode('utf-8'))
        return compare_digest(mac.hexdigest(), hmac_hex.lower())
    except Exception:
        return False

def issue_tokens(subject: str) -> tuple[str, str]:
    now = int(get_time())
    
    access_secret = getenv("JWT_ACCESS_SECRET")
    refresh_secret = getenv("JWT_REFRESH_SECRET")
    
    if not access_secret or not refresh_secret:
        raise HTTPException(status_code=500, detail="JWT secrets not configured")
    
    access_payload = {
        "sub": subject,
        "iat": now,
        "exp": now + ACCESS_TTL,
        "aud": "teddy-api",
        "iss": "teddy-bear-system",
        "typ": "access"
    }
    
    refresh_payload = {
        "sub": subject,
        "iat": now,
        "exp": now + REFRESH_TTL,
        "aud": "teddy-api",
        "iss": "teddy-bear-system",
        "typ": "refresh"
    }
    
    access_token = jwt_encode(access_payload, access_secret, algorithm="HS256")
    refresh_token = jwt_encode(refresh_payload, refresh_secret, algorithm="HS256")
    
    return access_token, refresh_token

def get_device_record(device_id: str) -> Optional[dict]:
    mock_devices = {
        "Teddy-ESP32-0001": {
            "oob_secret_hex": "A1B2C3D4E5F6789012345678901234567890ABCDEF1234567890ABCDEF123456",
            "enabled": True
        }
    }
    return mock_devices.get(device_id)

@router.post("/api/v1/pair/claim", response_model=TokenResponse)
async def claim_device(request: ClaimRequest):
    try:
        verify_nonce_once(request.nonce)
        
        device_record = get_device_record(request.device_id)
        if not device_record:
            raise HTTPException(status_code=404, detail="Device not found")
        
        if not device_record.get("enabled", False):
            raise HTTPException(status_code=403, detail="Device disabled")
        
        if not verify_hmac(
            request.device_id,
            request.child_id,
            request.nonce,
            request.hmac_hex,
            device_record["oob_secret_hex"]
        ):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        subject = f"{request.device_id}:{request.child_id}"
        access_token, refresh_token = issue_tokens(subject)
        
        safe_device_id = re.sub(r'[^\w-]', '', request.device_id)[:20]
        safe_child_id = re.sub(r'[^\w-]', '', request.child_id)[:20]
        logger.info(f"Device {safe_device_id} claimed for child {safe_child_id}")
        
        return TokenResponse(access=access_token, refresh=refresh_token)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Claim error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/api/v1/token/refresh")
async def refresh_access_token(request: RefreshRequest):
    try:
        refresh_secret = getenv("JWT_REFRESH_SECRET")
        if not refresh_secret:
            raise HTTPException(status_code=500, detail="JWT secret not configured")
            
        payload = jwt_decode(
            request.refresh_token,
            refresh_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            audience="teddy-api",
            issuer="teddy-bear-system"
        )
        
        if payload.get("typ") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        access_token, _ = issue_tokens(payload["sub"])
        
        return {"access": access_token}
        
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")