"""
Tests for UsageReports - real usage reporting functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock

from src.adapters.dashboard.usage_reports import UsageReports


class TestUsageReports:
    @pytest.fixture
    def mock_user_service(self):
        service = Mock()
        service.get_usage_summary = AsyncMock()
        service.get_child_usage_report = AsyncMock()
        return service

    @pytest.fixture
    def usage_reports(self, mock_user_service):
        return UsageReports(mock_user_service)

    def test_init(self, mock_user_service):
        reports = UsageReports(mock_user_service)
        assert reports.user_service == mock_user_service

    @pytest.mark.asyncio
    async def test_get_usage_summary_success(self, usage_reports):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        expected_summary = {
            "total_sessions": 15,
            "total_time_minutes": 450,
            "average_session_duration": 30.0,
            "daily_breakdown": {
                "Monday": 60,
                "Tuesday": 45,
                "Wednesday": 75
            },
            "peak_hours": [16, 17, 19],
            "content_categories": {
                "educational": 60,
                "entertainment": 30,
                "creative": 10
            }
        }
        
        usage_reports.user_service.get_usage_summary.return_value = expected_summary
        
        result = await usage_reports.get_usage_summary(parent_id)
        
        assert result == expected_summary
        usage_reports.user_service.get_usage_summary.assert_called_once_with(parent_id)

    @pytest.mark.asyncio
    async def test_get_usage_summary_empty_parent_id(self, usage_reports):
        with pytest.raises(ValueError) as exc:
            await usage_reports.get_usage_summary("")
        
        assert "Parent ID is required" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_usage_summary_none_parent_id(self, usage_reports):
        with pytest.raises(ValueError) as exc:
            await usage_reports.get_usage_summary(None)
        
        assert "Parent ID is required" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_usage_summary_whitespace_parent_id(self, usage_reports):
        with pytest.raises(ValueError) as exc:
            await usage_reports.get_usage_summary("   ")
        
        assert "Parent ID is required" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_usage_summary_invalid_response(self, usage_reports):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Test with None response
        usage_reports.user_service.get_usage_summary.return_value = None
        
        result = await usage_reports.get_usage_summary(parent_id)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_usage_summary_non_dict_response(self, usage_reports):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Test with non-dict response
        usage_reports.user_service.get_usage_summary.return_value = "invalid response"
        
        result = await usage_reports.get_usage_summary(parent_id)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_usage_summary_service_error(self, usage_reports):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        
        usage_reports.user_service.get_usage_summary.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception) as exc:
            await usage_reports.get_usage_summary(parent_id)
        
        assert "Database connection failed" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_child_report_success(self, usage_reports):
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        expected_report = {
            "child_id": child_id,
            "name": "Ahmed",
            "age": 8,
            "total_sessions": 8,
            "total_time_minutes": 240,
            "average_session_duration": 30.0,
            "favorite_activities": ["stories", "games", "learning"],
            "safety_incidents": 0,
            "learning_progress": {
                "completed_lessons": 12,
                "current_level": "intermediate",
                "achievements": ["storyteller", "curious_learner"]
            },
            "usage_patterns": {
                "most_active_day": "Saturday",
                "preferred_time": "afternoon",
                "session_consistency": "regular"
            },
            "parental_controls": {
                "time_limits": {"weekday": 60, "weekend": 90},
                "content_filter": "medium",
                "blocked_categories": []
            }
        }
        
        usage_reports.user_service.get_child_usage_report.return_value = expected_report
        
        result = await usage_reports.get_child_report(child_id)
        
        assert result == expected_report
        assert result["child_id"] == child_id
        assert result["total_sessions"] == 8
        assert result["safety_incidents"] == 0
        usage_reports.user_service.get_child_usage_report.assert_called_once_with(child_id)

    @pytest.mark.asyncio
    async def test_get_child_report_empty_child_id(self, usage_reports):
        with pytest.raises(ValueError) as exc:
            await usage_reports.get_child_report("")
        
        assert "Child ID is required" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_child_report_none_child_id(self, usage_reports):
        with pytest.raises(ValueError) as exc:
            await usage_reports.get_child_report(None)
        
        assert "Child ID is required" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_child_report_whitespace_child_id(self, usage_reports):
        with pytest.raises(ValueError) as exc:
            await usage_reports.get_child_report("   ")
        
        assert "Child ID is required" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_child_report_invalid_response(self, usage_reports):
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        # Test with None response
        usage_reports.user_service.get_child_usage_report.return_value = None
        
        result = await usage_reports.get_child_report(child_id)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_child_report_non_dict_response(self, usage_reports):
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        # Test with non-dict response
        usage_reports.user_service.get_child_usage_report.return_value = ["invalid", "response"]
        
        result = await usage_reports.get_child_report(child_id)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_child_report_service_error(self, usage_reports):
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        usage_reports.user_service.get_child_usage_report.side_effect = Exception("Child not found")
        
        with pytest.raises(Exception) as exc:
            await usage_reports.get_child_report(child_id)
        
        assert "Child not found" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_usage_summary_comprehensive_data(self, usage_reports):
        """Test with comprehensive usage data structure"""
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        comprehensive_summary = {
            "parent_id": parent_id,
            "children_count": 2,
            "total_sessions": 25,
            "total_time_minutes": 750,
            "average_session_duration": 30.0,
            "daily_breakdown": {
                "Monday": 90,
                "Tuesday": 105,
                "Wednesday": 120,
                "Thursday": 95,
                "Friday": 110,
                "Saturday": 130,
                "Sunday": 100
            },
            "weekly_trends": {
                "current_week": 750,
                "previous_week": 680,
                "change_percentage": 10.3
            },
            "peak_hours": [15, 16, 17, 19, 20],
            "content_categories": {
                "educational": 45,
                "entertainment": 30,
                "creative": 15,
                "social": 10
            },
            "safety_metrics": {
                "total_violations": 2,
                "resolved_violations": 2,
                "pending_violations": 0,
                "safety_score": 0.95
            },
            "device_usage": {
                "tablet": 60,
                "phone": 25,
                "computer": 15
            },
            "learning_metrics": {
                "lessons_completed": 28,
                "skills_learned": 12,
                "achievements_earned": 8
            }
        }
        
        usage_reports.user_service.get_usage_summary.return_value = comprehensive_summary
        
        result = await usage_reports.get_usage_summary(parent_id)
        
        assert result == comprehensive_summary
        assert result["children_count"] == 2
        assert result["safety_metrics"]["safety_score"] == 0.95
        assert result["weekly_trends"]["change_percentage"] == 10.3

    @pytest.mark.asyncio
    async def test_get_child_report_comprehensive_data(self, usage_reports):
        """Test with comprehensive child report data structure"""
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        comprehensive_report = {
            "child_id": child_id,
            "name": "Fatima",
            "age": 10,
            "profile_created": "2024-01-15",
            "last_activity": "2025-01-29T14:30:00Z",
            "usage_statistics": {
                "total_sessions": 15,
                "total_time_minutes": 450,
                "average_session_duration": 30.0,
                "longest_session": 45,
                "shortest_session": 15
            },
            "activity_breakdown": {
                "stories": 40,
                "games": 25,
                "learning": 20,
                "creative": 15
            },
            "learning_progress": {
                "completed_lessons": 18,
                "current_level": "advanced",
                "skills_mastered": ["reading", "math_basics", "creativity"],
                "achievements": ["bookworm", "math_star", "creative_genius"],
                "next_goals": ["advanced_math", "science_explorer"]
            },
            "safety_record": {
                "total_incidents": 1,
                "resolved_incidents": 1,
                "incident_types": ["mild_language"],
                "overall_safety_score": 0.92,
                "parental_interventions": 0
            },
            "behavioral_insights": {
                "preferred_times": ["afternoon", "early_evening"],
                "engagement_level": "high",
                "attention_span": "above_average",
                "learning_style": "visual_auditory"
            },
            "parental_controls": {
                "time_limits": {
                    "weekday": 45,
                    "weekend": 75,
                    "bedtime_cutoff": "20:00"
                },
                "content_restrictions": {
                    "filter_level": "medium",
                    "blocked_categories": ["violence"],
                    "allowed_categories": ["educational", "creative", "stories"]
                },
                "monitoring_level": "standard"
            },
            "recommendations": {
                "suggested_activities": ["science_experiments", "advanced_stories"],
                "skill_development": ["critical_thinking", "problem_solving"],
                "time_adjustments": "consider_increasing_weekend_limit"
            }
        }
        
        usage_reports.user_service.get_child_usage_report.return_value = comprehensive_report
        
        result = await usage_reports.get_child_report(child_id)
        
        assert result == comprehensive_report
        assert result["name"] == "Fatima"
        assert result["age"] == 10
        assert result["learning_progress"]["current_level"] == "advanced"
        assert result["safety_record"]["overall_safety_score"] == 0.92
        assert "science_experiments" in result["recommendations"]["suggested_activities"]

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, usage_reports):
        """Test handling multiple concurrent requests"""
        import asyncio
        
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_id1 = "550e8400-e29b-41d4-a716-446655440001"
        child_id2 = "550e8400-e29b-41d4-a716-446655440002"
        
        # Mock responses
        usage_reports.user_service.get_usage_summary.return_value = {"total_sessions": 10}
        usage_reports.user_service.get_child_usage_report.side_effect = [
            {"child_id": child_id1, "sessions": 5},
            {"child_id": child_id2, "sessions": 5}
        ]
        
        # Execute concurrent requests
        tasks = [
            usage_reports.get_usage_summary(parent_id),
            usage_reports.get_child_report(child_id1),
            usage_reports.get_child_report(child_id2)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        assert results[0]["total_sessions"] == 10
        assert results[1]["child_id"] == child_id1
        assert results[2]["child_id"] == child_id2