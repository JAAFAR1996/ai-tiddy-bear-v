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

    async def create_safety_alert(self, alert_data: dict) -> dict:
        """Create a safety alert for administrators and parents."""
        try:
            # Validate required alert data fields
            required_fields = ["alert_id", "alert_type", "priority", "message"]
            missing_fields = [field for field in required_fields if field not in alert_data]
            if missing_fields:
                raise SafetyControlsError(f"Missing required alert fields: {missing_fields}")
            
            # Validate alert_id is a UUID
            alert_id = alert_data.get("alert_id", "")
            if alert_id:
                self._validate_uuid(alert_id, "alert_id")
            
            # Validate incident_id if provided
            incident_id = alert_data.get("incident_id")
            if incident_id:
                self._validate_uuid(incident_id, "incident_id")
            
            # Validate priority level
            valid_priorities = ["low", "medium", "high", "urgent", "critical", "emergency"]
            priority = alert_data.get("priority", "").lower()
            if priority not in valid_priorities:
                raise SafetyControlsError(f"Invalid priority level: {priority}. Must be one of {valid_priorities}")
            
            # Validate alert type
            valid_alert_types = [
                "content_violation", "inappropriate_interaction", "safety_concern",
                "human_review_required", "emergency_escalation", "coppa_violation"
            ]
            alert_type = alert_data.get("alert_type", "")
            if alert_type not in valid_alert_types:
                raise SafetyControlsError(f"Invalid alert type: {alert_type}. Must be one of {valid_alert_types}")
            
            # Log the alert creation
            logger.info(f"Creating safety alert: {alert_id} - {alert_type} - {priority}")
            
            # Create alert through safety service
            alert_result = await self.safety_service.create_safety_alert({
                "alert_id": alert_id,
                "incident_id": incident_id,
                "alert_type": alert_type,
                "priority": priority,
                "message": alert_data.get("message", ""),
                "severity_level": alert_data.get("severity_level", priority),
                "child_id": alert_data.get("child_id"),
                "timestamp": alert_data.get("timestamp"),
                "additional_data": alert_data.get("additional_data", {}),
                "requires_immediate_action": priority in ["urgent", "critical", "emergency"],
                "requires_parent_notification": True,
                "requires_admin_notification": priority in ["urgent", "critical", "emergency"],
            })
            
            logger.info(f"Safety alert {alert_id} created successfully")
            return alert_result
            
        except SafetyControlsError:
            # Re-raise SafetyControlsError as-is
            raise
        except Exception as e:
            logger.error(f"Failed to create safety alert {alert_data.get('alert_id', 'unknown')}: {e}")
            raise SafetyControlsError(f"Failed to create safety alert: {str(e)}")
