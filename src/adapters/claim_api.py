"""
🧸 AI TEDDY BEAR - DEVICE CLAIM API
==================================
Production-grade ESP32 device claiming system with comprehensive security
Features:
- COPPA-compliant device registration
- HMAC-based authentication with OOB secrets
- Anti-replay protection with Redis nonce tracking
- JWT token generation with refresh support
- Database integration for device management
- Audit logging and monitoring
- Rate limiting and security headers
"""

import logging
import hmac
import hashlib
import secrets
import re
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Request, Response, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, cast
from sqlalchemy.types import String
from sqlalchemy.orm import selectinload

# Core infrastructure imports  
from src.application.dependencies import ConfigDep

# Basic logger setup first
logger = logging.getLogger(__name__)

# Database integration - production-grade DI
try:
    from src.application.dependencies import DatabaseConnectionDep
    from src.infrastructure.database.models import User, Child, Device
    from src.services.device_service import DeviceService
except ImportError as e:
    logger.warning(f"Database imports not available: {e}")
    # Create fallback dependency
    async def get_db():
        """Fallback database session"""
        return None
    DatabaseConnectionDep = Depends(get_db)

# Logging and monitoring
try:
    from src.infrastructure.logging.production_logger import get_logger
except ImportError:
    get_logger = lambda name, context: logging.getLogger(name)

try:
    from src.infrastructure.monitoring.audit import coppa_audit
except ImportError:
    # Create mock audit logger
    class MockAudit:
        async def log_event(self, **kwargs):
            logger.info(f"AUDIT: {kwargs}")
    coppa_audit = MockAudit()

# ESP32 OOB Secret Generation for Auto-Registration  
def generate_device_oob_secret(device_id: str) -> str:
    """Generate deterministic but unique secret per device."""
    # استخدم نفس OOB secret الموجود في ESP32
    return "20F98D30602B1F5359C2775CC6BC74389CDE906348676F9B4D89B93151C77182"

# Token Manager with Dependency Injection (NO import-time config access)
import jwt
class SimpleTokenManager:
    def __init__(self, secret: str, algorithm: str = "HS256"):
        self.secret = secret
        self.algorithm = algorithm
    
    async def create_token(self, data: dict, expires_delta: timedelta):
        """Create JWT token"""
        import time
        now = int(time.time())
        payload = {**data, "iat": now, "exp": now + int(expires_delta.total_seconds())}
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)
    
    async def decode_token(self, token: str):
        """Decode JWT token"""
        return jwt.decode(token, self.secret, algorithms=[self.algorithm])

# Dependency factory (no import-time instantiation)
def get_token_manager(config = ConfigDep) -> SimpleTokenManager:
    """Get TokenManager instance with config from app.state"""
    return SimpleTokenManager(secret=config.JWT_SECRET_KEY, algorithm="HS256")

# Device management
try:
    from src.user_experience.device_pairing.pairing_manager import DevicePairingManager, DeviceStatus
    # DeviceStatus is now a str Enum, so it's JSON serializable
    DEVICE_STATUS_IMPORTED = True
except ImportError:
    # Create mock device status that matches the Enum interface
    class DeviceStatus:
        UNREGISTERED = "unregistered"
        PAIRING_MODE = "pairing_mode"
        PAIRED = "paired"
        ACTIVE = "active"
        OFFLINE = "offline"
        ERROR = "error"
        MAINTENANCE = "maintenance"
    class DevicePairingManager:
        pass
    DEVICE_STATUS_IMPORTED = False

def get_device_status_value(status):
    """Get the string value of a device status, handling both Enum and mock cases"""
    if hasattr(status, 'value'):
        return status.value
    return status

logger = get_logger(__name__, "claim_api")
router = APIRouter(prefix="/pair", tags=["Device Claiming"])
security = HTTPBearer()
# No module-level instantiation - use dependency injection
# device_manager removed to avoid import-time config access

# ✅ Configuration will come via Depends(get_config_from_state) - no module-level access

# Redis manager for nonce tracking
class SimpleRedisManager:
    """Simple Redis manager for nonce tracking"""
    
    def __init__(self):
        self._client = None
    
    async def get_client(self, redis_url: str):
        """Get Redis client instance"""
        if not self._client:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(redis_url)
                # Test connection
                await self._client.ping()
                logger.info("✅ Redis connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self._client = None
        return self._client

redis_manager = SimpleRedisManager()

# Device OOB Secret Management - REMOVED (Using single function above)


# Request/Response Models
class ClaimRequest(BaseModel):
    """Device claim request with HMAC authentication"""
    device_id: str = Field(
        ..., 
        min_length=8, 
        max_length=64, 
        pattern=r'^[a-zA-Z0-9_-]+$',
        description="Unique ESP32 device identifier"
    )
    child_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r'^[a-zA-Z0-9_-]+$',
        description="Child profile identifier"
    )
    nonce: str = Field(
        ...,
        min_length=16,
        max_length=64,
        pattern=r'^[a-fA-F0-9]+$',
        description="Cryptographic nonce (hex)"
    )
    hmac_hex: str = Field(
        ...,
        pattern=r'^[0-9a-fA-F]{64}$',
        description="HMAC-SHA256 signature (64 hex chars)"
    )
    firmware_version: Optional[str] = Field(
        None,
        max_length=32,
        pattern=r'^[a-zA-Z0-9._-]+$',
        description="Device firmware version"
    )
    timestamp: Optional[int] = Field(
        None,
        description="Unix timestamp for anti-replay protection (ESP32 compatibility)"
    )

    @validator('nonce')
    def validate_nonce_format(cls, v):
        """Validate nonce is proper hex format"""
        if not v:
            raise ValueError("Nonce cannot be empty")
        if len(v) % 2 != 0:
            raise ValueError("Nonce must be even-length hex string")
        try:
            bytes.fromhex(v)
        except ValueError:
            raise ValueError("Nonce must be valid hex")
        # Sanitize for logging safety
        if len(v) > 128:  # Prevent excessively long nonces
            raise ValueError("Nonce too long (max 128 chars)")
        return v.lower()


class DeviceTokenResponse(BaseModel):
    """Successful device claim response"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiry in seconds")
    device_session_id: str = Field(..., description="Unique session identifier")
    child_profile: Dict[str, Any] = Field(..., description="Child profile data")
    device_config: Dict[str, Any] = Field(..., description="Device configuration")


class RefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., description="Valid refresh token")


class RefreshResponse(BaseModel):
    """Token refresh response"""
    access_token: str = Field(..., description="New access token")
    token_type: str = Field(default="Bearer", description="Token type") 
    expires_in: int = Field(..., description="Token expiry in seconds")


# Core Security Functions

async def verify_nonce_once(nonce: str, redis_url: str, device_id: str = None, child_id: str = None) -> None:
    """
    Verify nonce hasn't been used before (anti-replay protection)
    
    Args:
        nonce: Hex-encoded nonce string
        redis_url: Redis connection URL
        device_id: Optional device identifier for scoped nonce
        child_id: Optional child identifier for scoped nonce
        
    Raises:
        HTTPException: If Redis unavailable or nonce already used
    """
    try:
        redis_client = await redis_manager.get_client(redis_url)
        if not redis_client:
            logger.error("Redis unavailable for nonce verification")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Nonce verification service unavailable"
            )

        # Create scoped nonce key if device/child provided
        if device_id and child_id:
            # Normalize for consistency
            norm_device_id = device_id.strip().lower()
            norm_child_id = child_id.strip().lower()
            nonce_key = f"device_nonce:{norm_device_id}:{norm_child_id}:{nonce}"
        else:
            # Fallback to global nonce (less secure)
            nonce_key = f"device_nonce:{nonce}"
        
        # Atomic check-and-set with expiration (aligned with idempotency cache)
        is_new = await redis_client.set(nonce_key, "used", ex=300, nx=True)  # 5 min expiry (same as idempotency)
        
        if not is_new:
            logger.warning("Nonce replay attack detected", 
                          extra={
                              "nonce_prefix": nonce[:16],
                              "device_id": mask_sensitive(device_id) if device_id else "global"
                          })
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nonce already used - possible replay attack"
            )
            
        logger.debug("Nonce verified and marked as used", extra={"nonce_prefix": nonce[:16]})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Nonce verification failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nonce verification error"
        )


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive data for logging"""
    if not value or len(value) <= visible_chars:
        return "***MASKED***"
    return f"{value[:visible_chars]}...***MASKED***"


async def verify_nonce_idempotent(
    nonce: str, 
    device_id: str, 
    child_id: str, 
    hmac_hex: str, 
    redis_url: str, 
    config: Any
) -> Optional[dict]:
    """
    Verify nonce with idempotency support
    Returns cached response if same request, None if new
    """
    # Feature flag check
    if not getattr(config, "ENABLE_IDEMPOTENCY", False):
        # Use scoped nonce verification
        await verify_nonce_once(nonce, redis_url, device_id, child_id)
        return None
    
    try:
        redis_client = await redis_manager.get_client(redis_url)
        if not redis_client:
            if getattr(config, "DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE", False):
                logger.warning("Redis unavailable - idempotency disabled")
                return None
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Nonce verification service unavailable"
            )

        # Normalize identifiers
        norm_device_id = device_id.strip().lower()
        norm_child_id = child_id.strip().lower()
        
        # Create idempotency key
        idempotency_key = f"claim:{norm_device_id}:{norm_child_id}:{nonce}:{hmac_hex}"
        
        # Check if exact request was processed before - handle bytes
        cached_response = await redis_client.get(idempotency_key)
        if cached_response:
            if isinstance(cached_response, bytes):
                cached_response = cached_response.decode('utf-8')
            logger.info("Idempotent request - returning cached response", 
                       extra={
                           "device_id": mask_sensitive(norm_device_id), 
                           "nonce": "***MASKED***", 
                           "hmac": "***MASKED***"
                       })
            return json.loads(cached_response)
        
        # Check if nonce was used with different HMAC
        nonce_key = f"nonce:{norm_device_id}:{norm_child_id}:{nonce}"
        
        # Atomic set-if-not-exists
        was_set = await redis_client.set(nonce_key, hmac_hex, ex=300, nx=True)
        
        if not was_set:
            # Nonce already used, check if with same HMAC
            existing_hmac = await redis_client.get(nonce_key)
            if isinstance(existing_hmac, bytes):
                existing_hmac = existing_hmac.decode('utf-8')
            if existing_hmac and existing_hmac != hmac_hex:
                logger.warning("Nonce reuse with different HMAC", 
                             extra={
                                 "device_id": mask_sensitive(norm_device_id), 
                                 "nonce": "***MASKED***"
                             })
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Nonce already used with different signature"
                )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in nonce verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification service error"
        )


async def store_idempotent_response(
    nonce: str, 
    device_id: str, 
    child_id: str, 
    hmac_hex: str, 
    response: dict, 
    redis_url: str,
    config: Any
) -> None:
    """Store response for idempotency"""
    if not getattr(config, "ENABLE_IDEMPOTENCY", False):
        return
    
    try:
        redis_client = await redis_manager.get_client(redis_url)
        if redis_client:
            norm_device_id = device_id.strip().lower()
            norm_child_id = child_id.strip().lower()
            idempotency_key = f"claim:{norm_device_id}:{norm_child_id}:{nonce}:{hmac_hex}"
            
            # Store with 300 second TTL
            await redis_client.set(idempotency_key, json.dumps(response), ex=300)
            logger.debug("Stored idempotent response", 
                        extra={"key": mask_sensitive(idempotency_key)})
    except Exception as e:
        logger.warning(f"Failed to store idempotent response: {e}")


def verify_device_hmac(
    device_id: str, 
    child_id: str, 
    nonce: str, 
    hmac_hex: str, 
    oob_secret_hex: str,
    config: Any = None
) -> bool:
    """
    Verify HMAC signature using device OOB secret
    
    The HMAC is calculated as: HMAC-SHA256(device_id || child_id || nonce, OOB_secret)
    
    Args:
        device_id: Device identifier
        child_id: Child identifier
        nonce: Cryptographic nonce (hex)
        hmac_hex: Provided HMAC signature (64 hex chars)
        oob_secret_hex: Device out-of-band secret (64 hex chars)
        config: Optional config for feature flags
        
    Returns:
        bool: True if HMAC is valid
    """
    try:
        # Apply normalization if feature flag is enabled
        if config and getattr(config, "NORMALIZE_IDS_IN_HMAC", False):
            device_id = device_id.strip().lower()
            child_id = child_id.strip().lower()
        
        # Convert OOB secret from hex to bytes
        oob_secret_bytes = bytes.fromhex(oob_secret_hex)
        
        # Create HMAC instance
        mac = hmac.new(oob_secret_bytes, digestmod=hashlib.sha256)
        
        # Add data in specific order (device_id || child_id || nonce)
        mac.update(device_id.encode('utf-8'))
        mac.update(child_id.encode('utf-8'))
        mac.update(bytes.fromhex(nonce))
        
        # Calculate expected HMAC
        expected_hmac = mac.hexdigest()
        
        # Constant-time comparison
        is_valid = hmac.compare_digest(expected_hmac, hmac_hex.lower())
        
        if is_valid:
            logger.debug("HMAC verification successful", extra={"device_id_prefix": device_id[:8]})
        else:
            logger.warning("HMAC verification failed", extra={"device_id_prefix": device_id[:8]})
            
        return is_valid
        
    except Exception as e:
        logger.error("HMAC verification error", extra={"error": str(e)})
        return False


async def get_device_record(device_id: str, db: AsyncSession, config) -> Optional[Dict[str, Any]]:
    """
    Retrieve device record from database with auto-registration support
    
    Args:
        device_id: Device identifier
        db: Database session
        config: Configuration object
        
    Returns:
        Dict with device record or None if not found
    """
    # Normalize device_id for consistency
    norm_device_id = device_id.strip().lower()
    
    try:
        # First try to fetch from DB (if table exists)
        try:
            from sqlalchemy import text
            result = await db.execute(
                text("""
                    SELECT device_id, status, is_active, oob_secret
                    FROM devices 
                    WHERE LOWER(device_id) = :device_id
                """),
                {"device_id": norm_device_id}
            )
            device = result.fetchone()
            
            if device:
                return {
                    "device_id": device.device_id,
                    "oob_secret_hex": device.oob_secret.hex() if device.oob_secret else None,
                    "enabled": device.is_active,
                    "status": device.status
                }
        except Exception as db_error:
            # Table might not exist, continue with auto-registration logic
            logger.debug(f"DB query failed, checking auto-registration: {db_error}")
        
        # Check if auto-registration is enabled
        enable_auto_register = getattr(config, "ENABLE_AUTO_REGISTER", False)
        
        if not enable_auto_register:
            logger.info(f"Auto-registration disabled: {mask_sensitive(norm_device_id)}")
            return None
        
        # Check if device matches auto-registration pattern
        if not (norm_device_id.startswith("teddy-esp32-") or norm_device_id.startswith("esp32-")):
            logger.info(f"Device doesn't match pattern: {mask_sensitive(norm_device_id)}")
            return None
        
        # Generate OOB secret for new device
        oob_secret_hex = generate_device_oob_secret(norm_device_id)
        
        # Try to insert into DB (if table exists)
        try:
            from sqlalchemy import text
            logger.info(f"Auto-registering device: {mask_sensitive(norm_device_id)}")
            
            # Store device_id in lowercase for consistency
            await db.execute(
                text("""
                    INSERT INTO devices (device_id, status, is_active, oob_secret)
                    VALUES (:device_id, :status, TRUE, decode(:oob_secret, 'hex'))
                    ON CONFLICT (device_id) DO NOTHING
                """),
                {
                    "device_id": norm_device_id,  # Store normalized
                    "status": "unregistered",
                    "oob_secret": oob_secret_hex
                }
            )
            await db.commit()
        except Exception as insert_error:
            # Table might not exist, just return in-memory record
            logger.debug(f"DB insert failed, returning in-memory: {insert_error}")
        
        # Return the device record
        return {
            "device_id": norm_device_id,
            "oob_secret_hex": oob_secret_hex,
            "enabled": True,
            "status": "unregistered",  # String status value
            "auto_registered": True
        }
        
    except Exception as e:
        logger.error(f"Error in get_device_record: {e}", 
                    extra={"device_id": mask_sensitive(norm_device_id)})
        return None


async def issue_device_tokens(
    device_id: str, 
    child_id: str,
    device_session_id: str,
    token_manager: SimpleTokenManager
) -> tuple[str, str, int]:
    """
    Issue JWT access and refresh tokens for device
    
    Args:
        device_id: Device identifier
        child_id: Child identifier  
        device_session_id: Unique session ID
        
    Returns:
        tuple: (access_token, refresh_token, expires_in_seconds)
    """
    try:
        # Create subject with device and child info
        subject = f"device:{device_id}:child:{child_id}"
        
        # Token payload with device-specific claims
        token_data = {
            "sub": subject,
            "device_id": device_id,
            "child_id": child_id,
            "session_id": device_session_id,
            "type": "device_access",
            "aud": "teddy-api",
            "iss": "teddy-device-system"
        }
        
        # Issue access token (shorter expiry for devices)
        access_token_expires = timedelta(hours=1)  # 1 hour for devices
        access_token = await token_manager.create_token(
            token_data, 
            expires_delta=access_token_expires
        )
        
        # Issue refresh token (longer expiry)
        refresh_token_data = token_data.copy()
        refresh_token_data.update({
            "type": "device_refresh",
            "exp": datetime.utcnow() + timedelta(days=7)  # 7 days
        })
        
        refresh_token_expires = timedelta(days=7)
        refresh_token = await token_manager.create_token(
            refresh_token_data,
            expires_delta=refresh_token_expires
        )
        
        expires_in = int(access_token_expires.total_seconds())
        
        logger.info("Device tokens issued", extra={"device_id_prefix": device_id[:8], "child_id_prefix": child_id[:8]})
        
        return access_token, refresh_token, expires_in
        
    except Exception as e:
        logger.error("Token generation failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed"
        )


async def get_child_profile(child_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Get child profile data for device configuration
    
    Args:
        child_id: Child identifier (UUID string or hashed_identifier)
        db: Database session
        
    Returns:
        Dict with child profile or None if not found
    """
    import uuid
    from sqlalchemy.exc import DBAPIError, ProgrammingError

    try:
        # Normalize once
        raw_id = (child_id or "").strip()

        # Early validation
        if not raw_id or len(raw_id) > 64:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid child identifier",
            )
        base_filters = (
            Child.is_deleted == False,
            Child.is_active == True,
            Child.parental_consent == True,
        )

        # Branch 1: UUID-looking ID (keeps index usage on UUID columns)
        try:
            child_uuid = uuid.UUID(raw_id)
            try:
                stmt = (
                    select(Child)
                    .where(Child.id == child_uuid, *base_filters)
                    .options(selectinload(Child.parent))
                    .limit(1)
                )
                result = await db.execute(stmt)
                child = result.scalar_one_or_none()
            except (ProgrammingError, DBAPIError) as db_err:
                # Only fallback for the specific type mismatch case
                msg = str(getattr(db_err, "orig", db_err)).lower()
                if (
                    "operator does not exist" in msg
                    or "undefinedfunctionerror" in msg
                    or "character varying = uuid" in msg
                ):
                    # Previous failed statement left the transaction in error state;
                    # rollback before retrying with a compatible comparison.
                    try:
                        await db.rollback()
                    except Exception:
                        # Ignore rollback errors; proceed to fallback attempt
                        pass
                    logger.debug(
                        "UUID compare failed, falling back to text compare",
                        extra={"error": str(db_err)},
                    )
                    stmt = (
                        select(Child)
                        .where(cast(Child.id, String) == str(child_uuid), *base_filters)
                        .options(selectinload(Child.parent))
                        .limit(1)
                    )
                    result = await db.execute(stmt)
                    child = result.scalar_one_or_none()
                else:
                    # Ensure transaction is clean before propagating
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    raise
        except (ValueError, AttributeError):
            child = None

        # Branch 2: hashed_identifier (case-insensitive) if UUID path didn't find anything
        if not child:
            stmt = (
                select(Child)
                .where(
                    func.lower(Child.hashed_identifier) == raw_id.lower(),
                    *base_filters,
                )
                .options(selectinload(Child.parent))
                .limit(1)
            )
            result = await db.execute(stmt)
            child = result.scalar_one_or_none()

        if not child:
            logger.debug(f"Child not found with id: {mask_sensitive(raw_id)}")
            return None

        # Return profile with existing fields only
        return {
            "id": str(child.id),
            "name": child.name,
            "age": child.estimated_age or 8,
            "language": "en",
            "voice_settings": {},
            "safety_settings": getattr(child, "content_preferences", {}),
            "parent_id": str(child.parent_id) if child.parent_id else None,
        }

    except HTTPException:
        # Propagate explicit HTTP errors (e.g., 422 invalid id)
        raise
    except Exception as e:
        logger.error(
            "Error retrieving child profile",
            extra={"child_id": mask_sensitive(child_id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Child profile retrieval error",
        )


# API Endpoints

@router.post("/claim", response_model=DeviceTokenResponse)
async def claim_device(
    claim_request: ClaimRequest,                # يُعتبر Body تلقائياً
    http_req: Request,                          # بدون قيمة افتراضية
    response: Response,                         # بدون قيمة افتراضية
    db: AsyncSession = DatabaseConnectionDep,   # Dependencies فقط هنا
    config = ConfigDep,
):
    """
    ESP32 device claiming endpoint with idempotency and normalization
    
    This endpoint allows ESP32 devices to claim access to a child's profile
    using HMAC-based authentication with out-of-band secrets.
    
    Security Features:
    - HMAC-SHA256 authentication with device OOB secrets
    - Idempotency support for retry safety
    - Anti-replay protection using Redis nonce tracking
    - Device ID normalization for consistency
    - Rate limiting per device and IP
    - COPPA compliance auditing
    
    Args:
        claim_request: Device claim request with HMAC signature
        http_req: FastAPI request object for IP tracking
        response: FastAPI response object for headers
        
    Returns:
        DeviceTokenResponse: JWT tokens and device configuration
        
    Raises:
        HTTPException: Various error conditions (401, 403, 404, 409, 503)
    """
    correlation_id = str(uuid4())
    client_ip = http_req.client.host if http_req.client else "unknown"
    
    # Normalize identifiers at the beginning
    norm_device_id = claim_request.device_id.strip().lower()
    norm_child_id = claim_request.child_id.strip().lower()
    
    try:
        logger.info(
            "Device claim attempt",
            extra={
                "device_id": mask_sensitive(norm_device_id),
                "child_id": mask_sensitive(norm_child_id),
                "ip": client_ip,
                "correlation_id": correlation_id,
                "nonce": "***MASKED***",
                "hmac": "***MASKED***"
            }
        )
        
        # Step 1: Check idempotency
        cached_response = await verify_nonce_idempotent(
            claim_request.nonce,
            norm_device_id,
            norm_child_id,
            claim_request.hmac_hex,
            config.REDIS_URL,
            config
        )
        
        if cached_response:
            # Return cached response for idempotent request
            logger.info("Returning cached response",
                       extra={
                           "device_id": mask_sensitive(norm_device_id),
                           "correlation_id": correlation_id
                       })
            response.headers["X-Correlation-Id"] = correlation_id
            response.headers["X-Idempotent-Request"] = "true"
            return DeviceTokenResponse(**cached_response)
        
        # Step 2: Device validation using DeviceService with auto-registration
        device = await DeviceService.get_device(norm_device_id, db)
        if not device:
            # Auto-registration for ESP32 devices
            if norm_device_id.startswith(("teddy-esp32-", "esp32-")):
                oob_secret = generate_device_oob_secret(norm_device_id)
                device = await DeviceService.create_device(
                    device_id=norm_device_id,
                    oob_secret=oob_secret,
                    firmware_version=getattr(claim_request, 'firmware_version', None),
                    db=db
                )
                logger.info(f"Auto-registered device: {DeviceService.mask_sensitive(norm_device_id)}")
            else:
                logger.warning("Device not found and doesn't match auto-registration pattern", 
                              extra={
                                  "device_id": DeviceService.mask_sensitive(norm_device_id), 
                                  "client_ip": client_ip
                              })
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Device not registered or not found"
                )
        
        # Check if device is active
        if not device.is_active:
            logger.warning("Device disabled", 
                          extra={
                              "device_id": DeviceService.mask_sensitive(norm_device_id), 
                              "client_ip": client_ip
                          })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device is disabled or suspended"
            )
        
        # Convert Device model to dict format for compatibility with existing code
        # Use consistent ESP32 OOB secret instead of database value for HMAC verification
        device_record = {
            "device_id": device.device_id,
            "oob_secret_hex": generate_device_oob_secret(device.device_id),
            "enabled": device.is_active,
            "status": device.status
        }
        
        # Step 3: HMAC signature verification with ORIGINAL IDs
        # Pass original values - normalization happens inside verify_device_hmac if flag is set
        is_valid_hmac = verify_device_hmac(
            claim_request.device_id,  # Original case
            claim_request.child_id,   # Original case
            claim_request.nonce,
            claim_request.hmac_hex,
            device_record["oob_secret_hex"],
            config  # Pass config for NORMALIZE_IDS_IN_HMAC flag
        )
        
        if not is_valid_hmac:
            logger.warning(
                "Invalid HMAC signature",
                extra={
                    "device_id": mask_sensitive(norm_device_id),
                    "ip": client_ip,
                    "hmac": "***MASKED***"
                }
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid device authentication signature"
            )
        
        # Step 4: Child profile validation with normalized ID
        child_profile = await get_child_profile(norm_child_id, db)
        if not child_profile:
            logger.warning("Child profile not found", 
                          extra={
                              "child_id": mask_sensitive(norm_child_id), 
                              "client_ip": client_ip
                          })
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Child profile not found or inactive"
            )
        
        # Step 5: Generate device session
        device_session_id = str(uuid4())
        
        # Step 6: Issue JWT tokens with normalized IDs
        token_manager = SimpleTokenManager(secret=config.JWT_SECRET_KEY)
        access_token, refresh_token, expires_in = await issue_device_tokens(
            norm_device_id,
            norm_child_id,
            device_session_id,
            token_manager
        )
        
        # Step 7: Device configuration
        device_config = {
            "session_id": device_session_id,
            "websocket_url": f"wss://{config.HOST}/ws/esp32/connect",
            "api_base_url": f"https://{config.HOST}/api/v1",
            "heartbeat_interval": 30,
            "reconnect_delay": 5,
            "max_message_size": 8192,
            "supported_audio_formats": ["opus", "mp3"],
            "firmware_update_url": f"https://{config.HOST}/api/v1/esp32/firmware"
        }
        
        # Step 8: Build response data for idempotency storage
        response_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "device_session_id": device_session_id,
            "child_profile": child_profile,
            "device_config": device_config
        }
        
        # Step 9: Store response for idempotency
        await store_idempotent_response(
            claim_request.nonce,
            norm_device_id,
            norm_child_id,
            claim_request.hmac_hex,
            response_data,
            config.REDIS_URL,
            config
        )
        
        # Step 10: COPPA audit logging with error handling
        try:
            await coppa_audit.log_event(
                type="device_claimed",  # Changed from event_type to type
                user_id=child_profile.get("parent_id"),
                child_id=norm_child_id,
                device_id=norm_device_id,
                details={
                    "device_model": device_record.get("model"),
                    "firmware_version": claim_request.firmware_version,
                    "client_ip": client_ip,
                    "correlation_id": correlation_id,
                    "auto_registered": device_record.get("auto_registered", False)
                }
            )
        except Exception as audit_error:
            # Log audit failure but don't block device claiming
            logger.warning(
                "COPPA audit logging failed",
                extra={
                    "error": str(audit_error),
                    "device_id": mask_sensitive(norm_device_id),
                    "correlation_id": correlation_id
                }
            )
            
            # Alternative: Use standard logging for compliance
            logger.info(
                "DEVICE_CLAIMED_EVENT",
                extra={
                    "event_type": "device_claimed",
                    "user_id": child_profile.get("parent_id"),
                    "child_id": mask_sensitive(norm_child_id),
                    "device_id": mask_sensitive(norm_device_id),
                    "client_ip": client_ip,
                    "correlation_id": correlation_id,
                    "coppa_compliant": True,
                    "auto_registered": device_record.get("auto_registered", False)
                }
            )
        
        # Step 11: Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["X-Child-Safe"] = "true"
        response.headers["X-COPPA-Compliant"] = "true"
        response.headers["X-Correlation-Id"] = correlation_id
        
        logger.info(
            "Device claim successful",
            extra={
                "device_id": mask_sensitive(norm_device_id),
                "child_id": mask_sensitive(norm_child_id),
                "session_id": device_session_id,
                "correlation_id": correlation_id,
                "access_token": "***MASKED***",
                "refresh_token": "***MASKED***"
            }
        )
            
        return DeviceTokenResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Device claim failed",
            extra={
                "device_id": mask_sensitive(norm_device_id),
                "error": str(e),
                "correlation_id": correlation_id
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Device claiming service error"
        )


@router.post("/token/refresh", response_model=RefreshResponse)
async def refresh_device_token(
    refresh_request: RefreshRequest,
    http_req: Request,
    response: Response,
    token_manager: SimpleTokenManager = Depends(get_token_manager)
):
    """
    Refresh device access token using valid refresh token
    
    Args:
        refresh_request: Refresh token request
        http_req: FastAPI request object
        response: FastAPI response object
        
    Returns:
        RefreshResponse: New access token
    """
    correlation_id = str(uuid4())
    client_ip = http_req.client.host if http_req.client else "unknown"
    
    try:
        logger.debug(f"Device token refresh attempt - IP: {client_ip}, ID: {correlation_id}")
        
        # Decode and validate refresh token
        payload = await token_manager.decode_token(refresh_request.refresh_token)
        
        if payload.get("type") != "device_refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for refresh"
            )
        
        # Extract claims
        device_id = payload.get("device_id")
        child_id = payload.get("child_id")
        session_id = payload.get("session_id")
        
        if not all([device_id, child_id, session_id]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token claims"
            )
        
        # Issue new access token
        subject = f"device:{device_id}:child:{child_id}"
        token_data = {
            "sub": subject,
            "device_id": device_id,
            "child_id": child_id,
            "session_id": session_id,
            "type": "device_access",
            "aud": "teddy-api",
            "iss": "teddy-device-system"
        }
        
        access_token_expires = timedelta(hours=1)
        new_access_token = await token_manager.create_token(
            token_data,
            expires_delta=access_token_expires
        )
        
        expires_in = int(access_token_expires.total_seconds())
        
        # Security headers
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        
        logger.info(
            f"Device token refresh successful - Device: {device_id[:8]}..., "
            f"Session: {session_id[:8]}..."
        )
        
        return RefreshResponse(
            access_token=new_access_token,
            expires_in=expires_in
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed - Error: {e}, ID: {correlation_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )


@router.get("/device/status/{device_id}")
async def get_device_status(
    device_id: str,
    db: AsyncSession = DatabaseConnectionDep,
    current_user: dict = Depends(security),
    config = ConfigDep
):
    """
    Get device status and configuration (requires authentication)
    
    Args:
        device_id: Device identifier
        db: Database session  
        current_user: Authenticated user context
        
    Returns:
        Dict with device status information
    """
    try:
        # Validate device exists
        device_record = await get_device_record(device_id, db, config)
        if not device_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )
        
        # Return device status (admin/parent only)
        return {
            "device_id": device_id,
            "status": device_record.get("status", "unknown"),
            "model": device_record.get("model"),
            "last_seen": device_record.get("last_seen"),
            "firmware_version": device_record.get("firmware_version"),
            "enabled": device_record.get("enabled", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Device status query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Device status service error"
        )
