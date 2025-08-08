"""
Unit tests for ChildSafetyService.
Tests content validation, filtering, safety monitoring, and COPPA compliance.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.application.services.child_safety_service import ChildSafetyService
from src.interfaces.services import IChildSafetyService


class TestChildSafetyService:
    """Test suite for child safety service implementation."""

    @pytest.fixture
    def safety_service(self):
        """Create a child safety service instance."""
        return ChildSafetyService()

    @pytest.fixture
    def custom_config_service(self):
        """Create service with custom configuration."""
        config = {
            "strict_mode": True,
            "max_violations": 3,
            "custom_patterns": [r"\b(custom_bad_word)\b"],
        }
        return ChildSafetyService(config=config)

    @pytest.mark.asyncio
    async def test_validate_content_safe(self, safety_service):
        """Test validation of safe, age-appropriate content."""
        content = "Let's learn about friendly dinosaurs and rainbows!"
        result = await safety_service.validate_content(content, child_age=7)

        assert result["is_safe"] is True
        assert result["confidence"] >= 0.8
        assert len(result["issues"]) == 0
        assert result["age_appropriate"] is True
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_validate_content_violence(self, safety_service):
        """Test detection of violent content."""
        content = "The character used a gun to kill the monster"
        result = await safety_service.validate_content(content, child_age=8)

        assert result["is_safe"] is False
        assert len(result["issues"]) > 0

        # Check specific violation
        violence_issue = next(
            (
                issue
                for issue in result["issues"]
                if issue["type"] == "inappropriate_content"
            ),
            None,
        )
        assert violence_issue is not None
        assert violence_issue["severity"] == "high"

    @pytest.mark.asyncio
    async def test_validate_content_drugs_alcohol(self, safety_service):
        """Test detection of drug/alcohol references."""
        content = "The adult was smoking cigarettes and drinking alcohol"
        result = await safety_service.validate_content(content, child_age=6)

        assert result["is_safe"] is False
        assert len(result["issues"]) >= 2  # Both smoking and alcohol

    @pytest.mark.asyncio
    async def test_validate_content_hate_speech(self, safety_service):
        """Test detection of hate speech and discrimination."""
        content = "We should show hate towards different people"
        result = await safety_service.validate_content(content, child_age=10)

        assert result["is_safe"] is False
        assert any(
            issue["type"] == "inappropriate_content" for issue in result["issues"]
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "age,expected_appropriate",
        [
            (3, False),  # Too complex for toddler
            (5, False),  # Complex for preschool
            (8, True),  # OK for elementary
            (11, True),  # OK for late elementary
            (13, True),  # OK for preteen
        ],
    )
    async def test_age_appropriate_complexity(
        self, safety_service, age, expected_appropriate
    ):
        """Test age-appropriate content complexity detection."""
        # Complex scientific content
        content = (
            "Photosynthesis converts carbon dioxide into oxygen through chlorophyll"
        )
        result = await safety_service.validate_content(content, age)

        assert result["age_appropriate"] == expected_appropriate
        if not expected_appropriate:
            assert any(
                issue["type"] == "age_inappropriate" for issue in result["issues"]
            )

    @pytest.mark.asyncio
    async def test_filter_content_removes_violations(self, safety_service):
        """Test content filtering removes inappropriate words."""
        content = "This story has violence and death in it"
        filtered = await safety_service.filter_content(content)

        assert "violence" not in filtered.lower()
        assert "death" not in filtered.lower()
        assert "[filtered]" in filtered

    @pytest.mark.asyncio
    async def test_filter_content_preserves_safe_content(self, safety_service):
        """Test filtering preserves safe content."""
        safe_content = "The happy bunny hopped through the garden"
        filtered = await safety_service.filter_content(safe_content)

        assert filtered == safe_content
        assert "[filtered]" not in filtered

    @pytest.mark.asyncio
    async def test_filter_content_handles_mixed_case(self, safety_service):
        """Test filtering handles mixed case appropriately."""
        content = "The story had VIOLENCE and WeApOnS in it"
        filtered = await safety_service.filter_content(content)

        assert "violence" not in filtered.lower()
        assert "weapon" not in filtered.lower()

    @pytest.mark.asyncio
    async def test_log_safety_event_success(self, safety_service):
        """Test logging safety events."""
        event = {
            "event_type": "content_violation",
            "child_id": "child-123",
            "severity": "high",
            "details": "Detected violent content",
            "timestamp": datetime.now().isoformat(),
        }

        result = await safety_service.log_safety_event(event)
        assert result is True

        # Verify event was stored
        assert len(safety_service.safety_events) == 1
        assert safety_service.safety_events[0] == event

    @pytest.mark.asyncio
    async def test_log_safety_event_with_auto_timestamp(self, safety_service):
        """Test logging event without timestamp adds one automatically."""
        event = {
            "event_type": "safety_check",
            "child_id": "child-456",
            "result": "pass",
        }

        result = await safety_service.log_safety_event(event)
        assert result is True

        logged_event = safety_service.safety_events[0]
        assert "timestamp" in logged_event
        assert logged_event["timestamp"] is not None

    @pytest.mark.asyncio
    async def test_get_safety_recommendations_no_violations(self, safety_service):
        """Test recommendations for child with no violations."""
        # Log some safe interactions
        await safety_service.log_safety_event(
            {"event_type": "content_check", "child_id": "child-safe", "result": "safe"}
        )

        recommendations = await safety_service.get_safety_recommendations("child-safe")

        assert isinstance(recommendations, list)
        assert any(
            "positive" in str(rec).lower() or "well" in str(rec).lower()
            for rec in recommendations
        )

    @pytest.mark.asyncio
    async def test_get_safety_recommendations_with_violations(self, safety_service):
        """Test recommendations for child with safety violations."""
        # Log violations
        for i in range(3):
            await safety_service.log_safety_event(
                {
                    "event_type": "content_violation",
                    "child_id": "child-concern",
                    "severity": "high",
                    "violation_type": "violence",
                }
            )

        recommendations = await safety_service.get_safety_recommendations(
            "child-concern"
        )

        assert len(recommendations) > 0
        assert any(
            "monitor" in str(rec).lower() or "concern" in str(rec).lower()
            for rec in recommendations
        )

    @pytest.mark.asyncio
    async def test_custom_patterns_detection(self, custom_config_service):
        """Test service with custom inappropriate patterns."""
        content = "This contains custom_bad_word in the text"
        result = await custom_config_service.validate_content(content, child_age=8)

        assert result["is_safe"] is False
        assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_validate_empty_content(self, safety_service):
        """Test validation of empty content."""
        result = await safety_service.validate_content("", child_age=7)

        assert result["is_safe"] is True
        assert result["confidence"] == 1.0
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_concurrent_validations(self, safety_service):
        """Test service handles concurrent validation requests."""
        contents = [
            "Safe content about puppies",
            "Violent content with weapons",
            "Educational content about science",
            "Inappropriate adult content",
        ]

        # Run validations concurrently
        tasks = [
            safety_service.validate_content(content, child_age=8)
            for content in contents
        ]
        results = await asyncio.gather(*tasks)

        # Verify results
        assert len(results) == 4
        assert results[0]["is_safe"] is True  # puppies
        assert results[1]["is_safe"] is False  # weapons
        assert results[2]["is_safe"] is True  # science
        assert results[3]["is_safe"] is False  # adult content

    @pytest.mark.asyncio
    async def test_safety_event_filtering_by_child(self, safety_service):
        """Test getting safety events for specific child."""
        # Log events for multiple children
        children = ["child-1", "child-2", "child-3"]
        for child_id in children:
            for i in range(3):
                await safety_service.log_safety_event(
                    {
                        "event_type": "content_check",
                        "child_id": child_id,
                        "result": "safe" if i < 2 else "violation",
                    }
                )

        # Get recommendations for specific child
        child_events = [
            event
            for event in safety_service.safety_events
            if event["child_id"] == "child-2"
        ]

        assert len(child_events) == 3
        assert sum(1 for e in child_events if e["result"] == "violation") == 1

    def test_age_level_categorization(self, safety_service):
        """Test age level categorization logic."""
        age_tests = [
            (2, "toddler"),
            (4, "preschool"),
            (7, "early_elementary"),
            (10, "late_elementary"),
            (12, "preteen"),
        ]

        for age, expected_level in age_tests:
            # Find matching level
            level = None
            for level_name, (min_age, max_age) in safety_service.age_levels.items():
                if min_age <= age <= max_age:
                    level = level_name
                    break

            assert (
                level == expected_level
            ), f"Age {age} should be {expected_level}, got {level}"

    @pytest.mark.asyncio
    async def test_interface_compliance(self):
        """Test that ChildSafetyService implements IChildSafetyService interface."""
        service = ChildSafetyService()

        # Verify all interface methods are implemented
        assert hasattr(service, "validate_content")
        assert hasattr(service, "filter_content")
        assert hasattr(service, "log_safety_event")
        assert hasattr(service, "get_safety_recommendations")
        assert hasattr(service, "verify_parental_consent")

        # Verify they are callable
        assert callable(service.validate_content)
        assert callable(service.filter_content)
        assert callable(service.log_safety_event)
        assert callable(service.get_safety_recommendations)
        assert callable(service.verify_parental_consent)

    @pytest.mark.asyncio
    async def test_verify_parental_consent(self, safety_service):
        """Test parental consent verification."""
        # Test basic consent verification
        result = await safety_service.verify_parental_consent("child_123")
        assert isinstance(result, bool)
        assert result is True  # Default implementation returns True
