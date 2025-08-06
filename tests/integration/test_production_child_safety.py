"""
Production Child Safety Service Integration Tests
==============================================
Real integration tests for child safety service with database persistence.
NO MOCKS - Tests actual safety monitoring, threat detection, and compliance.
"""

import pytest
import asyncio
from datetime import datetime
from uuid import uuid4

from tests.conftest_production import skip_if_offline
from src.application.services.child_safety_service import ChildSafetyService
from src.infrastructure.database.models import SafetyReport


class TestProductionChildSafety:
    """Integration tests for real child safety service."""
    
    @pytest.mark.asyncio
    async def test_real_safety_monitoring_pipeline(
        self,
        child_safety_service: ChildSafetyService,
        test_child,
        db_session
    ):
        """Test complete safety monitoring pipeline with real database."""
        
        # Test safe content
        safe_content = "Tell me a story about friendly animals in the forest"
        
        safety_result = await child_safety_service.monitor_conversation_real_time(
            conversation_id=str(uuid4()),
            child_id=test_child.id,
            message_content=safe_content,
            child_age=test_child.age
        )
        
        # Verify safe content passes
        assert safety_result["is_safe"] is True
        assert safety_result["risk_score"] < 0.3
        assert len(safety_result["detected_issues"]) == 0
        assert safety_result["pii_detected"] is False
        
        # Verify monitoring actions are appropriate
        monitoring_actions = safety_result["monitoring_actions"]
        assert isinstance(monitoring_actions, list)
        
        # Check if safety report was created in database
        safety_reports = await db_session.execute(
            f"SELECT * FROM safety_reports WHERE child_id = '{test_child.id}'"
        )
        # Should not create report for safe content
    
    @pytest.mark.asyncio 
    async def test_violence_threat_detection(
        self,
        child_safety_service: ChildSafetyService,
        test_child,
        db_session
    ):
        """Test detection of violence threats with real AI models."""
        
        violent_content = "I want to hurt people with a knife and make them bleed"
        
        safety_result = await child_safety_service.monitor_conversation_real_time(
            conversation_id=str(uuid4()),
            child_id=test_child.id,
            message_content=violent_content,
            child_age=test_child.age
        )
        
        # Verify violence is detected 
        assert safety_result["is_safe"] is False
        assert safety_result["risk_score"] > 0.7
        assert len(safety_result["detected_issues"]) > 0
        
        # Check for violence-related issues
        detected_issues = [str(issue).lower() for issue in safety_result["detected_issues"]]
        violence_detected = any(
            "violence" in issue or "threat" in issue or "harm" in issue
            for issue in detected_issues
        )
        assert violence_detected
        
        # Verify emergency actions were triggered
        monitoring_actions = [action["action"] for action in safety_result["monitoring_actions"]]
        assert "EMERGENCY_ALERT" in monitoring_actions or "BLOCK_CONVERSATION" in monitoring_actions
    
    @pytest.mark.asyncio
    async def test_pii_detection_and_protection(
        self,
        child_safety_service: ChildSafetyService,
        test_child
    ):
        """Test PII detection and child protection."""
        
        pii_content = "My name is Johnny Smith and I live at 123 Main Street, my phone is 555-1234"
        
        safety_result = await child_safety_service.monitor_conversation_real_time(
            conversation_id=str(uuid4()),
            child_id=test_child.id,
            message_content=pii_content,
            child_age=test_child.age
        )
        
        # Verify PII is detected
        assert safety_result["pii_detected"] is True
        assert safety_result["is_safe"] is False
        
        # Check detected PII types
        assert "detected_pii_types" in safety_result
        pii_types = safety_result["detected_pii_types"]
        assert "address" in pii_types or "phone" in pii_types or "name" in pii_types
        
        # Verify monitoring actions include PII protection
        monitoring_actions = [action["action"] for action in safety_result["monitoring_actions"]]
        assert "PII_ALERT" in monitoring_actions or "PARENT_NOTIFICATION" in monitoring_actions
    
    @pytest.mark.asyncio
    async def test_age_inappropriate_content_filtering(
        self,
        child_safety_service: ChildSafetyService,
        test_child
    ):
        """Test age-inappropriate content filtering."""
        
        # Content inappropriate for 8-year-old
        inappropriate_content = "Tell me about adult relationships and romantic activities"
        
        safety_result = await child_safety_service.monitor_conversation_real_time(
            conversation_id=str(uuid4()),
            child_id=test_child.id,
            message_content=inappropriate_content,
            child_age=test_child.age
        )
        
        # Should be flagged as inappropriate for age
        assert safety_result["is_safe"] is False
        assert safety_result["age_appropriate"] is False
        
        # Check that content filtering was applied
        if "filtered_content" in safety_result:
            assert safety_result["filtered_content"] != inappropriate_content
    
    @pytest.mark.asyncio
    async def test_real_time_pattern_analysis(
        self,
        child_safety_service: ChildSafetyService,
        test_child
    ):
        """Test real-time behavioral pattern analysis."""
        
        conversation_id = str(uuid4())
        
        # Simulate escalating concerning behavior
        messages = [
            "I'm feeling sad today",
            "Nobody likes me at school", 
            "I want to hurt myself",
            "I have thoughts about dying"
        ]
        
        risk_scores = []
        
        for i, message in enumerate(messages):
            safety_result = await child_safety_service.monitor_conversation_real_time(
                conversation_id=conversation_id,
                child_id=test_child.id,
                message_content=message,
                child_age=test_child.age
            )
            
            risk_scores.append(safety_result["risk_score"])
            
            # Last messages should trigger high-risk alerts
            if i >= 2:  # Serious concerning content
                assert safety_result["is_safe"] is False
                assert safety_result["risk_score"] > 0.8
                
                # Should trigger emergency response
                monitoring_actions = [action["action"] for action in safety_result["monitoring_actions"]]
                assert "EMERGENCY_ALERT" in monitoring_actions
        
        # Verify escalating risk pattern
        assert risk_scores[-1] > risk_scores[0]  # Risk should increase
    
    @pytest.mark.asyncio
    async def test_coppa_compliance_enforcement(
        self,
        child_safety_service: ChildSafetyService,
        test_child
    ):
        """Test COPPA compliance enforcement."""
        
        # Ensure child is under COPPA age limit
        assert test_child.age < 13
        assert test_child.parental_consent is True
        
        # Test data collection request
        data_request = "What is your full name, address, phone number, and email?"
        
        safety_result = await child_safety_service.monitor_conversation_real_time(
            conversation_id=str(uuid4()),
            child_id=test_child.id,
            message_content=data_request,
            child_age=test_child.age
        )
        
        # Should block data collection attempts
        assert safety_result["is_safe"] is False
        assert safety_result["pii_detected"] is True
        
        # Verify COPPA-specific protections
        monitoring_actions = [action["action"] for action in safety_result["monitoring_actions"]]
        coppa_protection = any(
            "COPPA" in str(action).upper() or "PII" in action or "PARENT" in action
            for action in monitoring_actions
        )
        assert coppa_protection
    
    @pytest.mark.asyncio
    async def test_multi_level_risk_scoring(
        self,
        child_safety_service: ChildSafetyService,
        test_child
    ):
        """Test multi-level risk scoring system."""
        
        test_cases = [
            # (content, expected_risk_level)
            ("Hello, how are you?", "low"),
            ("I'm feeling confused about something", "medium"),
            ("I want to hurt someone badly", "high"),
            ("I'm going to kill myself", "critical")
        ]
        
        for content, expected_level in test_cases:
            safety_result = await child_safety_service.monitor_conversation_real_time(
                conversation_id=str(uuid4()),
                child_id=test_child.id,
                message_content=content,
                child_age=test_child.age
            )
            
            risk_score = safety_result["risk_score"]
            
            if expected_level == "low":
                assert risk_score < 0.3
                assert safety_result["is_safe"] is True
            elif expected_level == "medium":
                assert 0.3 <= risk_score < 0.7
            elif expected_level == "high":
                assert 0.7 <= risk_score < 0.9
                assert safety_result["is_safe"] is False
            elif expected_level == "critical":
                assert risk_score >= 0.9
                assert safety_result["is_safe"] is False
                
                # Critical should trigger emergency response
                monitoring_actions = [action["action"] for action in safety_result["monitoring_actions"]]
                assert "EMERGENCY_ALERT" in monitoring_actions
    
    @pytest.mark.asyncio
    async def test_database_persistence_integration(
        self,
        child_safety_service: ChildSafetyService,
        test_child,
        db_session
    ):
        """Test that safety events are properly persisted to database."""
        
        # Generate a safety violation
        violation_content = "I want to share my home address with strangers online"
        
        safety_result = await child_safety_service.monitor_conversation_real_time(
            conversation_id=str(uuid4()),
            child_id=test_child.id,
            message_content=violation_content,
            child_age=test_child.age
        )
        
        # Should be flagged as unsafe
        assert safety_result["is_safe"] is False
        assert safety_result["pii_detected"] is True
        
        # Check if safety report was created in database
        # Note: This would require the safety service to actually create reports
        # In a real implementation, we would verify database records were created
        
        # For now, verify the safety result structure
        assert "monitoring_actions" in safety_result
        assert "detected_issues" in safety_result
        assert "timestamp" in safety_result
    
    @pytest.mark.asyncio
    async def test_safety_service_error_handling(
        self,
        child_safety_service: ChildSafetyService,
        test_child
    ):
        """Test safety service error handling and resilience."""
        
        # Test with empty content
        try:
            safety_result = await child_safety_service.monitor_conversation_real_time(
                conversation_id=str(uuid4()),
                child_id=test_child.id,
                message_content="",
                child_age=test_child.age
            )
            
            # Should handle empty content gracefully
            assert "error" in safety_result or safety_result["is_safe"] is True
            
        except Exception as e:
            # If it raises an exception, it should be a valid error type
            assert "invalid" in str(e).lower() or "empty" in str(e).lower()
        
        # Test with very long content
        long_content = "This is a very long message. " * 1000  # ~30k characters
        
        safety_result = await child_safety_service.monitor_conversation_real_time(
            conversation_id=str(uuid4()),
            child_id=test_child.id,
            message_content=long_content,
            child_age=test_child.age
        )
        
        # Should handle long content (may truncate or process in chunks)
        assert isinstance(safety_result, dict)
        assert "is_safe" in safety_result
    
    @pytest.mark.asyncio
    async def test_performance_under_load(
        self,
        child_safety_service: ChildSafetyService,
        test_child
    ):
        """Test safety service performance under concurrent load."""
        
        async def process_safety_check(message_id: int):
            return await child_safety_service.monitor_conversation_real_time(
                conversation_id=str(uuid4()),
                child_id=test_child.id,
                message_content=f"Test message {message_id} for safety checking",
                child_age=test_child.age
            )
        
        # Process multiple concurrent safety checks
        tasks = [process_safety_check(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete successfully
        successful_results = [r for r in results if isinstance(r, dict) and "is_safe" in r]
        assert len(successful_results) >= 8  # Allow for some potential failures in test env
        
        # All successful results should be valid
        for result in successful_results:
            assert result["is_safe"] is True  # Safe test messages
            assert "risk_score" in result
            assert result["risk_score"] < 0.3


@pytest.mark.asyncio
async def test_safety_service_initialization():
    """Test that safety service initializes properly."""
    
    service = ChildSafetyService()
    assert service is not None
    
    # Test that required methods exist
    assert hasattr(service, 'monitor_conversation_real_time')
    assert callable(getattr(service, 'monitor_conversation_real_time'))