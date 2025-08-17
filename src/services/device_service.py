"""
Device service layer for business logic separation.
Handles device management operations with proper validation and error handling.
Uses Async SQLAlchemy to match project architecture.
"""
from typing import Optional, List
from datetime import datetime, timedelta
import hashlib
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
import logging

from src.infrastructure.database.models import Device, DeviceStatus

logger = logging.getLogger(__name__)


class DeviceService:
    """Service layer for device management operations using Async SQLAlchemy."""
    
    @staticmethod
    async def create_device(
        device_id: str,
        oob_secret: str,
        firmware_version: Optional[str] = None,
        db: AsyncSession = None
    ) -> Device:
        """
        Create a new device with validation.
        
        Args:
            device_id: Unique device identifier
            oob_secret: Out-of-band secret for authentication
            firmware_version: Optional firmware version
            db: Async database session
            
        Returns:
            Created Device instance
            
        Raises:
            ValueError: If device_id is invalid or already exists
        """
        if not DeviceService.validate_device_id(device_id):
            raise ValueError(f"Invalid device ID format: {device_id}")
            
        try:
            # Check if device already exists
            stmt = select(Device).where(Device.device_id == device_id)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                raise ValueError(f"Device {DeviceService.mask_sensitive(device_id)} already exists")
            
            # Create new device
            device = Device(
                device_id=device_id,
                status=DeviceStatus.PENDING,
                oob_secret=oob_secret,
                firmware_version=firmware_version,
                is_active=True
            )
            
            db.add(device)
            await db.commit()
            await db.refresh(device)
            
            logger.info(f"Created device {DeviceService.mask_sensitive(device_id)} with status {device.status}")
            return device
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create device {DeviceService.mask_sensitive(device_id)}: {str(e)}")
            raise
    
    @staticmethod
    async def get_device(device_id: str, db: AsyncSession) -> Optional[Device]:
        """
        Get device by ID.
        
        Args:
            device_id: Device identifier
            db: Async database session
            
        Returns:
            Device instance or None if not found
        """
        stmt = select(Device).where(
            and_(
                Device.device_id == device_id,
                Device.is_active == True,
                Device.is_deleted == False
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_firmware_version(device_id: str, firmware_version: str, db: AsyncSession) -> bool:
        """
        Update device firmware version.
        
        Args:
            device_id: Device identifier
            firmware_version: New firmware version
            db: Async database session
            
        Returns:
            True if updated successfully, False if device not found
        """
        try:
            device = await DeviceService.get_device(device_id, db)
            if not device:
                return False
                
            device.firmware_version = firmware_version
            device.updated_at = datetime.utcnow()
            
            await db.commit()
            logger.info(f"Updated firmware version for device {DeviceService.mask_sensitive(device.device_id)}: {firmware_version}")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update firmware for device {DeviceService.mask_sensitive(device_id)}: {str(e)}")
            return False
    
    @staticmethod
    async def deactivate_device(device_id: str, db: AsyncSession) -> bool:
        """
        Soft delete device by setting is_active to False.
        
        Args:
            device_id: Device identifier
            db: Async database session
            
        Returns:
            True if deactivated successfully, False if device not found
        """
        try:
            device = await DeviceService.get_device(device_id, db)
            if not device:
                return False
                
            device.is_active = False
            device.updated_at = datetime.utcnow()
            
            await db.commit()
            logger.info(f"Deactivated device {DeviceService.mask_sensitive(device_id)}")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to deactivate device {DeviceService.mask_sensitive(device_id)}: {str(e)}")
            return False
    
    @staticmethod
    def validate_device_id(device_id: str) -> bool:
        """
        Validate device ID format.
        
        Args:
            device_id: Device identifier to validate
            
        Returns:
            True if valid format, False otherwise
        """
        if not device_id or len(device_id.strip()) == 0:
            return False
            
        # Allow alphanumeric, hyphens, underscores, and dots
        # Length between 3 and 64 characters
        pattern = r'^[a-zA-Z0-9\-_.]{3,64}$'
        return bool(re.match(pattern, device_id.strip()))
    
    @staticmethod
    def mask_sensitive(device_id: str) -> str:
        """
        Mask sensitive parts of device ID for logging.
        
        Args:
            device_id: Device identifier to mask
            
        Returns:
            Masked device ID for safe logging
        """
        if not device_id or len(device_id) <= 6:
            return "***"
            
        # Show first 3 and last 3 characters
        return f"{device_id[:3]}***{device_id[-3:]}"
    
    @staticmethod
    async def get_active_devices(limit: int = 100, offset: int = 0, db: AsyncSession = None) -> List[Device]:
        """
        Get list of active devices with pagination.
        
        Args:
            limit: Maximum number of devices to return
            offset: Number of devices to skip
            db: Async database session
            
        Returns:
            List of active Device instances
        """
        stmt = select(Device).where(
            and_(
                Device.is_active == True,
                Device.is_deleted == False
            )
        ).offset(offset).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def count_devices_by_status(status: DeviceStatus = None, db: AsyncSession = None) -> int:
        """
        Count devices by status.
        
        Args:
            status: Optional device status to filter by
            db: Async database session
            
        Returns:
            Count of devices matching criteria
        """
        stmt = select(func.count(Device.id)).where(
            and_(
                Device.is_active == True,
                Device.is_deleted == False
            )
        )
        
        if status:
            stmt = stmt.where(Device.status == status)
            
        result = await db.execute(stmt)
        return result.scalar()