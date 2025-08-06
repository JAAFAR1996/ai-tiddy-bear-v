import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class UsageReports:
    def __init__(self, user_service):
        self.user_service = user_service

    async def get_usage_summary(self, parent_id: str) -> Optional[Dict[str, Any]]:
        if not parent_id or not parent_id.strip():
            raise ValueError("Parent ID is required")
        
        try:
            summary = await self.user_service.get_usage_summary(parent_id)
            if not summary or not isinstance(summary, dict):
                logger.warning(f"Invalid usage summary for parent {parent_id}")
                return None
            return summary
        except Exception as e:
            logger.error(f"Failed to get usage summary for parent {parent_id}: {str(e)}")
            raise

    async def get_child_report(self, child_id: str) -> Optional[Dict[str, Any]]:
        if not child_id or not child_id.strip():
            raise ValueError("Child ID is required")
        
        try:
            report = await self.user_service.get_child_usage_report(child_id)
            if not report or not isinstance(report, dict):
                logger.warning(f"Invalid child report for child {child_id}")
                return None
            return report
        except Exception as e:
            logger.error(f"Failed to get child report for child {child_id}: {str(e)}")
            raise
