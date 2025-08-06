"""
SafetyControls: Secure child safety settings management with validation and authorization.
"""
import re
import logging
from typing import Any, Set

logger = logging.getLogger(__name__)

class SafetyControlsError(Exception):
    pass

class SafetyControls:
    VALID_SETTINGS: Set[str] = {
        'content_filter_level', 'time_limits', 'blocked_categories', 
        'allowed_contacts', 'location_sharing', 'screen_time_limit'
    }
    
    SETTING_VALIDATORS = {
        'content_filter_level': lambda v: v in ['low', 'medium', 'high', 'strict'],
        'time_limits': lambda v: isinstance(v, dict) and all(isinstance(t, int) and 0 <= t <= 1440 for t in v.values()),
        'blocked_categories': lambda v: isinstance(v, list) and all(isinstance(c, str) for c in v),
        'screen_time_limit': lambda v: isinstance(v, int) and 0 <= v <= 1440
    }

    def __init__(self, safety_service, auth_service):
        self.safety_service = safety_service
        self.auth_service = auth_service

    def _validate_uuid(self, uuid_str: str, field_name: str) -> str:
        if not uuid_str or not isinstance(uuid_str, str):
            raise SafetyControlsError(f"{field_name} must be non-empty string")
        
        clean_id = uuid_str.strip()
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', clean_id, re.I):
            raise SafetyControlsError(f"{field_name} must be valid UUID")
        
        return clean_id

    def _validate_setting(self, setting: str, value: Any) -> None:
        if setting not in self.VALID_SETTINGS:
            raise SafetyControlsError(f"Invalid setting: {setting}")
        
        validator = self.SETTING_VALIDATORS.get(setting)
        if validator and not validator(value):
            raise SafetyControlsError(f"Invalid value for {setting}")

    async def _check_parent_access(self, parent_id: str, child_id: str) -> None:
        if not await self.auth_service.is_parent_of_child(parent_id, child_id):
            logger.warning(f"Unauthorized access: parent {parent_id} tried to modify child {child_id}")
            raise SafetyControlsError("Access denied: not authorized for this child")

    async def get_safety_overview(self, parent_id: str):
        parent_id = self._validate_uuid(parent_id, "parent_id")
        
        try:
            logger.info(f"Getting safety overview for parent {parent_id}")
            return await self.safety_service.get_safety_overview(parent_id)
        except Exception as e:
            logger.error(f"Failed to get safety overview for parent {parent_id}: {e}")
            raise SafetyControlsError(f"Failed to retrieve safety overview: {str(e)}")

    async def update_safety_setting(self, parent_id: str, child_id: str, setting: str, value: Any):
        parent_id = self._validate_uuid(parent_id, "parent_id")
        child_id = self._validate_uuid(child_id, "child_id")
        
        self._validate_setting(setting, value)
        await self._check_parent_access(parent_id, child_id)
        
        try:
            logger.info(f"Parent {parent_id} updating {setting} for child {child_id}")
            result = await self.safety_service.update_safety_setting(child_id, setting, value)
            logger.info(f"Successfully updated {setting} for child {child_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update {setting} for child {child_id}: {e}")
            raise SafetyControlsError(f"Failed to update setting: {str(e)}")