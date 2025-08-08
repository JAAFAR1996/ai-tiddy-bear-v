"""
Tests for NotificationCenter - real notification functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock

from src.adapters.dashboard.notification_center import NotificationCenter


class TestNotificationCenter:
    @pytest.fixture
    def mock_user_service(self):
        service = Mock()
        service.get_notifications = AsyncMock()
        return service

    @pytest.fixture
    def notification_center(self, mock_user_service):
        return NotificationCenter(mock_user_service)

    def test_init(self, mock_user_service):
        center = NotificationCenter(mock_user_service)
        assert center.user_service == mock_user_service

    @pytest.mark.asyncio
    async def test_get_notifications_success(self, notification_center):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        expected_notifications = [
            {
                "id": "notif-001",
                "type": "safety_alert",
                "priority": "high",
                "title": "Safety Alert",
                "message": "Content filter triggered for child Ahmed",
                "timestamp": "2025-01-29T14:30:00Z",
                "child_id": "550e8400-e29b-41d4-a716-446655440001",
                "child_name": "Ahmed",
                "read": False,
                "actions": ["review_content", "adjust_filters"]
            },
            {
                "id": "notif-002",
                "type": "usage_limit",
                "priority": "medium",
                "title": "Screen Time Limit Reached",
                "message": "Fatima has reached her daily screen time limit",
                "timestamp": "2025-01-29T13:15:00Z",
                "child_id": "550e8400-e29b-41d4-a716-446655440002",
                "child_name": "Fatima",
                "read": True,
                "actions": ["extend_time", "view_usage"]
            },
            {
                "id": "notif-003",
                "type": "achievement",
                "priority": "low",
                "title": "New Achievement Unlocked",
                "message": "Ahmed completed 10 educational activities!",
                "timestamp": "2025-01-29T12:00:00Z",
                "child_id": "550e8400-e29b-41d4-a716-446655440001",
                "child_name": "Ahmed",
                "read": False,
                "actions": ["view_progress", "share_achievement"]
            }
        ]
        
        notification_center.user_service.get_notifications.return_value = expected_notifications
        
        result = await notification_center.get_notifications(parent_id)
        
        assert result == expected_notifications
        assert len(result) == 3
        assert result[0]["type"] == "safety_alert"
        assert result[0]["priority"] == "high"
        assert result[1]["child_name"] == "Fatima"
        assert result[2]["type"] == "achievement"
        notification_center.user_service.get_notifications.assert_called_once_with(parent_id)

    @pytest.mark.asyncio
    async def test_get_notifications_empty_list(self, notification_center):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        
        notification_center.user_service.get_notifications.return_value = []
        
        result = await notification_center.get_notifications(parent_id)
        
        assert result == []
        notification_center.user_service.get_notifications.assert_called_once_with(parent_id)

    @pytest.mark.asyncio
    async def test_get_notifications_none_response(self, notification_center):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        
        notification_center.user_service.get_notifications.return_value = None
        
        result = await notification_center.get_notifications(parent_id)
        
        assert result is None
        notification_center.user_service.get_notifications.assert_called_once_with(parent_id)

    @pytest.mark.asyncio
    async def test_get_notifications_service_error(self, notification_center):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        
        notification_center.user_service.get_notifications.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception) as exc:
            await notification_center.get_notifications(parent_id)
        
        assert "Database connection failed" in str(exc.value)
        notification_center.user_service.get_notifications.assert_called_once_with(parent_id)

    @pytest.mark.asyncio
    async def test_get_notifications_comprehensive_data(self, notification_center):
        """Test with comprehensive notification data structure"""
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        comprehensive_notifications = [
            {
                "id": "notif-safety-001",
                "type": "safety_violation",
                "category": "content_filter",
                "priority": "critical",
                "severity": "high",
                "title": "Critical Safety Alert",
                "message": "Inappropriate content detected and blocked",
                "detailed_message": "The AI detected potentially harmful content in a conversation with Ahmed. The content has been automatically blocked and the conversation ended safely.",
                "timestamp": "2025-01-29T15:45:00Z",
                "child_id": "550e8400-e29b-41d4-a716-446655440001",
                "child_name": "Ahmed",
                "child_age": 8,
                "read": False,
                "acknowledged": False,
                "actions": [
                    {"id": "review_content", "label": "Review Content", "type": "primary"},
                    {"id": "adjust_filters", "label": "Adjust Filters", "type": "secondary"},
                    {"id": "contact_support", "label": "Contact Support", "type": "tertiary"}
                ],
                "metadata": {
                    "content_type": "text",
                    "filter_rule": "inappropriate_language",
                    "confidence_score": 0.95,
                    "auto_resolved": True
                },
                "related_notifications": [],
                "expiry_date": "2025-02-05T15:45:00Z"
            },
            {
                "id": "notif-usage-001",
                "type": "usage_alert",
                "category": "screen_time",
                "priority": "medium",
                "severity": "medium",
                "title": "Screen Time Warning",
                "message": "Fatima is approaching her daily screen time limit",
                "detailed_message": "Fatima has used 50 minutes of her 60-minute daily limit. She has 10 minutes remaining.",
                "timestamp": "2025-01-29T14:20:00Z",
                "child_id": "550e8400-e29b-41d4-a716-446655440002",
                "child_name": "Fatima",
                "child_age": 10,
                "read": True,
                "acknowledged": True,
                "actions": [
                    {"id": "extend_time", "label": "Extend Time (+15 min)", "type": "primary"},
                    {"id": "view_usage", "label": "View Usage Details", "type": "secondary"},
                    {"id": "set_reminder", "label": "Set Reminder", "type": "tertiary"}
                ],
                "metadata": {
                    "current_usage": 50,
                    "daily_limit": 60,
                    "remaining_time": 10,
                    "usage_trend": "normal"
                },
                "related_notifications": ["notif-usage-002"],
                "expiry_date": "2025-01-30T00:00:00Z"
            },
            {
                "id": "notif-achievement-001",
                "type": "positive_reinforcement",
                "category": "achievement",
                "priority": "low",
                "severity": "info",
                "title": "Learning Milestone Reached!",
                "message": "Ahmed completed his first week of consistent learning",
                "detailed_message": "Congratulations! Ahmed has successfully completed educational activities for 7 consecutive days. This shows great dedication to learning!",
                "timestamp": "2025-01-29T10:00:00Z",
                "child_id": "550e8400-e29b-41d4-a716-446655440001",
                "child_name": "Ahmed",
                "child_age": 8,
                "read": False,
                "acknowledged": False,
                "actions": [
                    {"id": "view_progress", "label": "View Learning Progress", "type": "primary"},
                    {"id": "share_achievement", "label": "Share Achievement", "type": "secondary"},
                    {"id": "set_new_goal", "label": "Set New Goal", "type": "tertiary"}
                ],
                "metadata": {
                    "achievement_type": "consistency",
                    "streak_days": 7,
                    "activities_completed": 21,
                    "skill_areas": ["reading", "math", "creativity"]
                },
                "related_notifications": [],
                "expiry_date": "2025-02-12T10:00:00Z"
            },
            {
                "id": "notif-system-001",
                "type": "system_update",
                "category": "maintenance",
                "priority": "low",
                "severity": "info",
                "title": "System Update Available",
                "message": "New features and improvements are available",
                "detailed_message": "A new update includes enhanced safety features, improved learning analytics, and better parental controls. Update recommended.",
                "timestamp": "2025-01-29T09:00:00Z",
                "child_id": null,
                "child_name": null,
                "child_age": null,
                "read": True,
                "acknowledged": False,
                "actions": [
                    {"id": "update_now", "label": "Update Now", "type": "primary"},
                    {"id": "schedule_update", "label": "Schedule for Later", "type": "secondary"},
                    {"id": "view_changelog", "label": "View Changes", "type": "tertiary"}
                ],
                "metadata": {
                    "version": "2.1.0",
                    "update_size": "15MB",
                    "estimated_time": "5 minutes",
                    "requires_restart": False
                },
                "related_notifications": [],
                "expiry_date": "2025-02-15T09:00:00Z"
            }
        ]
        
        notification_center.user_service.get_notifications.return_value = comprehensive_notifications
        
        result = await notification_center.get_notifications(parent_id)
        
        assert result == comprehensive_notifications
        assert len(result) == 4
        
        # Test safety notification
        safety_notif = result[0]
        assert safety_notif["type"] == "safety_violation"
        assert safety_notif["priority"] == "critical"
        assert safety_notif["metadata"]["confidence_score"] == 0.95
        assert len(safety_notif["actions"]) == 3
        
        # Test usage notification
        usage_notif = result[1]
        assert usage_notif["type"] == "usage_alert"
        assert usage_notif["metadata"]["remaining_time"] == 10
        assert usage_notif["acknowledged"] is True
        
        # Test achievement notification
        achievement_notif = result[2]
        assert achievement_notif["type"] == "positive_reinforcement"
        assert achievement_notif["metadata"]["streak_days"] == 7
        assert "reading" in achievement_notif["metadata"]["skill_areas"]
        
        # Test system notification
        system_notif = result[3]
        assert system_notif["type"] == "system_update"
        assert system_notif["child_id"] is None
        assert system_notif["metadata"]["version"] == "2.1.0"

    @pytest.mark.asyncio
    async def test_get_notifications_filtered_by_priority(self, notification_center):
        """Test notifications with different priority levels"""
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        priority_notifications = [
            {
                "id": "critical-001",
                "type": "emergency",
                "priority": "critical",
                "title": "Emergency Alert",
                "message": "Immediate attention required",
                "timestamp": "2025-01-29T16:00:00Z",
                "read": False
            },
            {
                "id": "high-001",
                "type": "safety_alert",
                "priority": "high",
                "title": "Safety Concern",
                "message": "Safety issue detected",
                "timestamp": "2025-01-29T15:30:00Z",
                "read": False
            },
            {
                "id": "medium-001",
                "type": "usage_alert",
                "priority": "medium",
                "title": "Usage Notice",
                "message": "Screen time reminder",
                "timestamp": "2025-01-29T15:00:00Z",
                "read": True
            },
            {
                "id": "low-001",
                "type": "info",
                "priority": "low",
                "title": "Information",
                "message": "General information",
                "timestamp": "2025-01-29T14:30:00Z",
                "read": True
            }
        ]
        
        notification_center.user_service.get_notifications.return_value = priority_notifications
        
        result = await notification_center.get_notifications(parent_id)
        
        assert len(result) == 4
        
        # Verify priority levels
        priorities = [notif["priority"] for notif in result]
        assert "critical" in priorities
        assert "high" in priorities
        assert "medium" in priorities
        assert "low" in priorities
        
        # Verify critical notification
        critical_notif = next(n for n in result if n["priority"] == "critical")
        assert critical_notif["type"] == "emergency"
        assert critical_notif["read"] is False

    @pytest.mark.asyncio
    async def test_get_notifications_with_child_specific_data(self, notification_center):
        """Test notifications with child-specific information"""
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_notifications = [
            {
                "id": "child-001",
                "type": "learning_progress",
                "priority": "medium",
                "title": "Learning Progress Update",
                "message": "Weekly learning summary for Ahmed",
                "timestamp": "2025-01-29T12:00:00Z",
                "child_id": "550e8400-e29b-41d4-a716-446655440001",
                "child_name": "Ahmed",
                "child_age": 8,
                "child_data": {
                    "grade_level": "3rd_grade",
                    "learning_style": "visual",
                    "favorite_subjects": ["stories", "math"],
                    "recent_achievements": ["completed_multiplication", "read_10_books"]
                },
                "read": False
            },
            {
                "id": "child-002",
                "type": "behavioral_insight",
                "priority": "low",
                "title": "Behavioral Pattern Noticed",
                "message": "Fatima shows increased engagement in creative activities",
                "timestamp": "2025-01-29T11:30:00Z",
                "child_id": "550e8400-e29b-41d4-a716-446655440002",
                "child_name": "Fatima",
                "child_age": 10,
                "child_data": {
                    "grade_level": "5th_grade",
                    "learning_style": "kinesthetic",
                    "favorite_subjects": ["art", "science"],
                    "behavioral_trends": ["increased_creativity", "longer_attention_span"]
                },
                "read": True
            }
        ]
        
        notification_center.user_service.get_notifications.return_value = child_notifications
        
        result = await notification_center.get_notifications(parent_id)
        
        assert len(result) == 2
        
        # Test Ahmed's notification
        ahmed_notif = result[0]
        assert ahmed_notif["child_name"] == "Ahmed"
        assert ahmed_notif["child_age"] == 8
        assert "stories" in ahmed_notif["child_data"]["favorite_subjects"]
        assert "completed_multiplication" in ahmed_notif["child_data"]["recent_achievements"]
        
        # Test Fatima's notification
        fatima_notif = result[1]
        assert fatima_notif["child_name"] == "Fatima"
        assert fatima_notif["child_age"] == 10
        assert fatima_notif["child_data"]["learning_style"] == "kinesthetic"
        assert "increased_creativity" in fatima_notif["child_data"]["behavioral_trends"]

    @pytest.mark.asyncio
    async def test_get_notifications_error_handling_robustness(self, notification_center):
        """Test various error scenarios and edge cases"""
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Test with malformed notification data
        malformed_notifications = [
            {
                "id": "valid-001",
                "type": "safety_alert",
                "priority": "high",
                "title": "Valid Notification",
                "message": "This is a valid notification",
                "timestamp": "2025-01-29T14:30:00Z",
                "read": False
            },
            {
                # Missing required fields
                "id": "invalid-001",
                "type": "incomplete"
                # Missing title, message, timestamp, etc.
            },
            {
                "id": "invalid-002",
                "type": None,  # Invalid type
                "priority": "unknown_priority",  # Invalid priority
                "title": "",  # Empty title
                "message": None,  # Null message
                "timestamp": "invalid-date",  # Invalid timestamp
                "read": "not_boolean"  # Invalid read status
            }
        ]
        
        notification_center.user_service.get_notifications.return_value = malformed_notifications
        
        # Should still return the data as-is (let the UI handle validation)
        result = await notification_center.get_notifications(parent_id)
        
        assert len(result) == 3
        assert result[0]["id"] == "valid-001"  # Valid notification preserved
        assert result[1]["id"] == "invalid-001"  # Incomplete notification preserved
        assert result[2]["type"] is None  # Invalid data preserved