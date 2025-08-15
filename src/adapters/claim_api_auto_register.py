"""
Enhanced Claim API with Auto-Registration
=========================================
Automatically registers new devices on first claim attempt
"""

from src.adapters.claim_api import *

async def auto_register_device(
    device_id: str,
    firmware_version: str,
    db: AsyncSession,
    config
) -> dict:
    """
    Automatically register a new device in the database.
    
    Args:
        device_id: Unique device identifier
        firmware_version: Current firmware version
        db: Database session
        config: Application configuration
        
    Returns:
        Device record dictionary
    """
    try:
        # Check if device already exists
        existing = await db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        if existing.scalar_one_or_none():
            return None  # Already registered
        
        # Create new device record
        new_device = Device(
            device_id=device_id,
            hardware_version="ESP32-WROOM-32",
            firmware_version=firmware_version,
            mac_address=device_id.split('-')[-1] if '-' in device_id else device_id[-8:],
            serial_number=device_id,
            manufacturing_date=datetime.utcnow(),
            activation_date=None,  # Will be set on first successful claim
            status="pending",  # pending → active after claim
            last_seen=datetime.utcnow(),
            metadata={
                "auto_registered": True,
                "registration_method": "first_claim",
                "ip_address": None  # Will be updated from request
            }
        )
        
        db.add(new_device)
        await db.commit()
        await db.refresh(new_device)
        
        logger.info(f"✅ Auto-registered new device: {device_id}")
        
        return {
            "device_id": new_device.device_id,
            "status": new_device.status,
            "auto_registered": True
        }
        
    except Exception as e:
        logger.error(f"Auto-registration failed for {device_id}: {e}")
        await db.rollback()
        return None


@router.post("/claim", response_model=DeviceTokenResponse)
async def claim_device_with_auto_register(
    claim_request: ClaimRequest,
    http_req: Request,
    response: Response,
    db: AsyncSession = DatabaseConnectionDep,
    config = ConfigDep,
):
    """
    Enhanced device claiming with automatic registration.
    
    If device is not registered, it will be auto-registered on first claim.
    
    Flow:
    1. Verify HMAC authentication
    2. Check if device exists → if not, auto-register
    3. Verify/create child profile
    4. Link device to child
    5. Generate JWT token
    
    This eliminates the need for manual device registration!
    """
    correlation_id = str(uuid4())
    request_metadata = {
        "correlation_id": correlation_id,
        "timestamp": datetime.utcnow().isoformat(),
        "device_id": claim_request.device_id,
        "child_id": claim_request.child_id,
        "firmware_version": getattr(claim_request, 'firmware_version', 'unknown'),
        "ip_address": http_req.client.host if http_req.client else None,
    }
    
    logger.info(f"Device claim attempt: {request_metadata}")
    
    try:
        # Step 1: HMAC Authentication
        if not await verify_hmac_production(
            claim_request.device_id,
            claim_request.child_id,
            claim_request.nonce,
            claim_request.hmac_hex,
            ESP32_SHARED_SECRET
        ):
            logger.warning(f"HMAC verification failed for {claim_request.device_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )
        
        # Step 2: Nonce verification (prevent replay attacks)
        await verify_nonce_once(claim_request.nonce, config.REDIS_URL)
        
        # Step 3: Get or Auto-Register Device
        device_record = await get_device_record(claim_request.device_id, db, config)
        
        if not device_record:
            # ✅ AUTO-REGISTER NEW DEVICE
            logger.info(f"Device {claim_request.device_id} not found - auto-registering...")
            
            device_record = await auto_register_device(
                device_id=claim_request.device_id,
                firmware_version=getattr(claim_request, 'firmware_version', '1.0.0'),
                db=db,
                config=config
            )
            
            if not device_record:
                logger.error(f"Auto-registration failed for {claim_request.device_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Device registration failed"
                )
            
            logger.info(f"✅ Device {claim_request.device_id} auto-registered successfully")
        
        # Step 4: Child Profile Validation/Creation
        child_profile = await get_child_profile(claim_request.child_id, db)
        
        if not child_profile:
            # Option: Auto-create child profile (if business logic allows)
            # For now, we require child to exist
            logger.warning(f"Child profile {claim_request.child_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Child profile not found - parent must register child first"
            )
        
        # Step 5: Link Device to Child (if not already linked)
        await link_device_to_child(
            device_id=claim_request.device_id,
            child_id=claim_request.child_id,
            db=db
        )
        
        # Step 6: Activate Device (if still pending)
        if device_record.get("status") == "pending":
            await activate_device(claim_request.device_id, db)
        
        # Step 7: Generate JWT Token
        token_data = await generate_device_token(
            device_id=claim_request.device_id,
            child_id=claim_request.child_id,
            device_metadata={
                "firmware_version": getattr(claim_request, 'firmware_version', 'unknown'),
                "auto_registered": device_record.get("auto_registered", False),
                "claim_time": datetime.utcnow().isoformat(),
            },
            config=config
        )
        
        # Step 8: Log successful claim
        await log_device_claim(
            device_id=claim_request.device_id,
            child_id=claim_request.child_id,
            ip_address=request_metadata["ip_address"],
            db=db
        )
        
        # Success response
        logger.info(f"✅ Device {claim_request.device_id} claimed successfully")
        
        response.status_code = status.HTTP_200_OK
        return DeviceTokenResponse(
            access_token=token_data["access_token"],
            token_type="bearer",
            expires_in=token_data["expires_in"],
            device_id=claim_request.device_id,
            child_id=claim_request.child_id,
            correlation_id=correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Claim failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Device claiming service error"
        )


async def link_device_to_child(device_id: str, child_id: str, db: AsyncSession):
    """Link device to child profile."""
    try:
        # Check if link already exists
        existing_link = await db.execute(
            select(DeviceChildLink).where(
                DeviceChildLink.device_id == device_id,
                DeviceChildLink.child_id == child_id
            )
        )
        if existing_link.scalar_one_or_none():
            return  # Already linked
        
        # Create new link
        new_link = DeviceChildLink(
            device_id=device_id,
            child_id=child_id,
            linked_at=datetime.utcnow(),
            active=True
        )
        db.add(new_link)
        await db.commit()
        
        logger.info(f"Linked device {device_id} to child {child_id}")
        
    except Exception as e:
        logger.error(f"Failed to link device to child: {e}")
        await db.rollback()


async def activate_device(device_id: str, db: AsyncSession):
    """Activate a pending device."""
    try:
        device = await db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = device.scalar_one_or_none()
        
        if device:
            device.status = "active"
            device.activation_date = datetime.utcnow()
            await db.commit()
            logger.info(f"Activated device {device_id}")
            
    except Exception as e:
        logger.error(f"Failed to activate device: {e}")
        await db.rollback()


async def log_device_claim(device_id: str, child_id: str, ip_address: str, db: AsyncSession):
    """Log successful device claim for audit."""
    try:
        claim_log = DeviceClaimLog(
            device_id=device_id,
            child_id=child_id,
            claimed_at=datetime.utcnow(),
            ip_address=ip_address,
            success=True
        )
        db.add(claim_log)
        await db.commit()
        
    except Exception as e:
        logger.error(f"Failed to log device claim: {e}")
        # Non-critical, don't fail the claim


# ===== FACTORY PRE-REGISTRATION (Optional) =====

@router.post("/factory/pre-register")
async def factory_pre_register_devices(
    devices: List[str],  # List of device IDs
    api_key: str = Header(...),  # Factory API key
    db: AsyncSession = DatabaseConnectionDep,
):
    """
    Bulk pre-register devices at factory (optional).
    
    This is optional - devices can also auto-register on first claim.
    """
    # Verify factory API key
    if api_key != "YOUR-FACTORY-SECRET-KEY":
        raise HTTPException(status_code=401, detail="Invalid factory key")
    
    registered = []
    failed = []
    
    for device_id in devices:
        try:
            result = await auto_register_device(
                device_id=device_id,
                firmware_version="1.0.0",
                db=db,
                config=None
            )
            if result:
                registered.append(device_id)
            else:
                failed.append(device_id)
        except Exception as e:
            logger.error(f"Failed to pre-register {device_id}: {e}")
            failed.append(device_id)
    
    return {
        "registered": registered,
        "failed": failed,
        "total": len(devices)
    }