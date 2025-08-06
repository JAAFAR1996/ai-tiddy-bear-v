"""
E2E Tests for Production API Flows
==================================
Comprehensive end-to-end tests for complete production API workflows:
- User registration → child creation → conversation flow
- AI interaction with safety checks
- Audio processing pipeline
- Parent dashboard and monitoring
- Multi-user scenarios
- Real-world usage patterns
"""

import pytest
import uuid
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from io import BytesIO

from httpx import AsyncClient

from .base import E2ETestBase, E2ETestConfig, performance_test
from .utils import (
    validate_response,
    validate_pagination_response,
    generate_auth_headers,
    generate_child_safety_headers,
    PerformanceTimer,
    wait_for_condition
)


class ProductionAPIFlowTests(E2ETestBase):
    """E2E tests for complete production API workflows."""
    
    async def _custom_setup(self):
        """Setup for production API flow tests."""
        self.performance_thresholds = {
            "user_registration": 500.0,
            "child_creation": 300.0,
            "conversation_start": 200.0,
            "ai_response": 2000.0,
            "audio_processing": 5000.0,
            "dashboard_load": 1000.0
        }
        
        # Test data for various scenarios
        self.test_scenarios = {}
    
    async def _custom_teardown(self):
        """Teardown for production API flow tests."""
        pass
    
    @performance_test(threshold_ms=5000.0)
    async def test_complete_user_onboarding_flow(self):
        """Test complete user onboarding from registration to first interaction."""
        
        # Step 1: User Registration
        async with self.measure_time("user_registration"):
            registration_data = {
                "username": f"parent_{uuid.uuid4().hex[:8]}",
                "email": f"parent_{uuid.uuid4().hex[:8]}@example.com",
                "password": "SecurePassword123!",
                "display_name": "Test Parent",
                "role": "parent",
                "timezone": "America/New_York",
                "privacy_consent": True,
                "terms_accepted": True
            }
            
            response = await self.client.post(
                "/api/v1/auth/register",
                json=registration_data
            )
            
            user_data = validate_response(response, 201, 
                required_fields=["id", "username", "email", "verification_required"])
            
            assert user_data["username"] == registration_data["username"]
            assert user_data["email"] == registration_data["email"]
            assert user_data["verification_required"] is True
        
        # Step 2: Email Verification (simulate)
        async with self.measure_time("email_verification"):
            verification_token = "test_verification_token_12345"
            
            response = await self.client.post(
                "/api/v1/auth/verify-email",
                json={
                    "email": registration_data["email"],
                    "verification_token": verification_token
                }
            )
            
            verify_data = validate_response(response, 200)
            assert verify_data["email_verified"] is True
        
        # Step 3: Login and get authentication token
        async with self.measure_time("user_login"):
            response = await self.client.post(
                "/api/v1/auth/login",
                json={
                    "username": registration_data["username"],
                    "password": registration_data["password"]
                }
            )
            
            auth_data = validate_response(response, 200,
                required_fields=["access_token", "refresh_token", "expires_in"])
            
            access_token = auth_data["access_token"]
            auth_headers = generate_auth_headers(access_token)
        
        # Step 4: Create child profile with parental consent
        async with self.measure_time("child_profile_creation"):
            child_data = {
                "name": "Test Child",
                "estimated_age": 7,
                "favorite_topics": ["animals", "space", "stories"],
                "parental_consent": True,
                "consent_method": "digital_signature",
                "data_retention_days": 30,
                "content_filtering_level": "strict",
                "educational_preferences": {
                    "stem_focus": True,
                    "creative_activities": True,
                    "language_learning": False
                }
            }
            
            response = await self.client.post(
                "/api/v1/children",
                json=child_data,
                headers=auth_headers
            )
            
            child_response = validate_response(response, 201,
                required_fields=["id", "name", "parent_id", "coppa_protected"])
            
            child_id = child_response["id"]
            assert child_response["coppa_protected"] is True  # Age 7 < 13
        
        # Step 5: Initialize child's first conversation
        async with self.measure_time("first_conversation"):
            conversation_data = {
                "title": "First Conversation",
                "context": "introduction and getting to know each other",
                "educational_content": True,
                "parental_supervision": True
            }
            
            response = await self.client.post(
                f"/api/v1/children/{child_id}/conversations",
                json=conversation_data,
                headers={**auth_headers, **generate_child_safety_headers(child_id, age=7)}
            )
            
            conversation = validate_response(response, 201,
                required_fields=["id", "title", "child_id", "safety_initialized"])
            
            conversation_id = conversation["id"]
            assert conversation["safety_initialized"] is True
        
        # Step 6: Send first message and get AI response
        async with self.measure_time("first_ai_interaction"):
            message_data = {
                "content": "Hi! I'm excited to talk with you. Can you tell me your name?",
                "sender_type": "child",
                "content_type": "text"
            }
            
            response = await self.client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json=message_data,
                headers={**auth_headers, **generate_child_safety_headers(child_id, age=7)}
            )
            
            message = validate_response(response, 201,
                required_fields=["id", "content", "ai_response_triggered"])
            
            assert message["ai_response_triggered"] is True
            
            # Wait for AI response to be generated
            ai_response_ready = False
            async def check_ai_response():
                nonlocal ai_response_ready
                response = await self.client.get(
                    f"/api/v1/conversations/{conversation_id}/messages/{message['id']}/ai-response",
                    headers=auth_headers
                )
                if response.status_code == 200:
                    ai_response_ready = True
                    return True
                return False
            
            await wait_for_condition(check_ai_response, timeout=10.0, interval=0.5)
            
            # Get the AI response
            response = await self.client.get(
                f"/api/v1/conversations/{conversation_id}/messages/{message['id']}/ai-response",
                headers=auth_headers
            )
            
            ai_response = validate_response(response, 200,
                required_fields=["content", "safety_checked", "age_appropriate"])
            
            assert ai_response["safety_checked"] is True
            assert ai_response["age_appropriate"] is True
            assert len(ai_response["content"]) > 0
        
        # Step 7: Verify parent dashboard access
        async with self.measure_time("parent_dashboard_access"):
            response = await self.client.get(
                f"/api/v1/dashboard/children/{child_id}/overview",
                headers=auth_headers
            )
            
            dashboard_data = validate_response(response, 200,
                required_fields=["child_summary", "recent_activity", "safety_status"])
            
            assert dashboard_data["child_summary"]["name"] == child_data["name"]
            assert len(dashboard_data["recent_activity"]) > 0
            assert dashboard_data["safety_status"]["compliant"] is True
        
        # Store successful scenario for reuse
        self.test_scenarios["complete_onboarding"] = {
            "user": user_data,
            "child": child_response,
            "conversation": conversation,
            "auth_headers": auth_headers
        }
    
    @performance_test(threshold_ms=3000.0)
    async def test_multi_child_conversation_management(self):
        """Test managing conversations with multiple children."""
        
        # Create parent with multiple children
        parent = await self.data_manager.create_test_user(role="parent")
        auth_headers = generate_auth_headers(
            await self._get_auth_token(parent["username"])
        )
        
        children = []
        for age in [5, 8, 12]:
            child = await self.data_manager.create_test_child(
                parent_id=uuid.UUID(parent["id"]),
                name=f"Child Age {age}",
                estimated_age=age,
                parental_consent=True
            )
            children.append(child)
        
        # Test concurrent conversation creation
        conversations = []
        
        async def create_conversation_for_child(child):
            response = await self.client.post(
                f"/api/v1/children/{child['id']}/conversations",
                json={
                    "title": f"Conversation with {child['name']}",
                    "context": f"age-appropriate content for {child['estimated_age']} year old"
                },
                headers={**auth_headers, **generate_child_safety_headers(
                    child["id"], age=child["estimated_age"]
                )}
            )
            return validate_response(response, 201)
        
        # Create conversations concurrently
        async with self.measure_time("concurrent_conversation_creation"):
            conversation_tasks = [
                create_conversation_for_child(child) for child in children
            ]
            conversations = await asyncio.gather(*conversation_tasks)
        
        assert len(conversations) == 3
        
        # Test parent dashboard showing all children's activities
        async with self.measure_time("multi_child_dashboard"):
            response = await self.client.get(
                "/api/v1/dashboard/children/overview",
                headers=auth_headers
            )
            
            dashboard = validate_response(response, 200,
                required_fields=["children_summary", "total_children"])
            
            assert dashboard["total_children"] == 3
            assert len(dashboard["children_summary"]) == 3
            
            # Verify each child's data is present
            for child in children:
                child_summary = next(
                    (c for c in dashboard["children_summary"] if c["id"] == child["id"]),
                    None
                )
                assert child_summary is not None
                assert child_summary["age"] == child["estimated_age"]
                assert child_summary["conversations_count"] >= 1
    
    @performance_test(threshold_ms=8000.0)
    async def test_audio_processing_pipeline(self):
        """Test complete audio processing pipeline."""
        
        # Setup child and conversation
        parent = await self.data_manager.create_test_user(role="parent")
        child = await self.data_manager.create_test_child(
            parent_id=uuid.UUID(parent["id"]),
            estimated_age=8,
            parental_consent=True
        )
        
        auth_headers = generate_auth_headers(
            await self._get_auth_token(parent["username"])
        )
        
        # Create conversation
        response = await self.client.post(
            f"/api/v1/children/{child['id']}/conversations",
            json={"title": "Audio Test Conversation"},
            headers={**auth_headers, **generate_child_safety_headers(child["id"], age=8)}
        )
        
        conversation = validate_response(response, 201)
        conversation_id = conversation["id"]
        
        # Step 1: Upload audio message from child
        async with self.measure_time("audio_upload"):
            # Simulate audio file upload
            audio_data = b"fake_audio_data_for_testing" * 1000  # Simulate audio file
            
            files = {
                "audio_file": ("child_message.wav", BytesIO(audio_data), "audio/wav")
            }
            
            form_data = {
                "sender_type": "child",
                "conversation_id": conversation_id,
                "audio_format": "wav",
                "duration": "3.5"
            }
            
            response = await self.client.post(
                f"/api/v1/conversations/{conversation_id}/audio-messages",
                files=files,
                data=form_data,
                headers={**auth_headers, **generate_child_safety_headers(child["id"], age=8)}
            )
            
            upload_result = validate_response(response, 201,
                required_fields=["id", "processing_started", "estimated_completion"])
            
            message_id = upload_result["id"]
            assert upload_result["processing_started"] is True
        
        # Step 2: Wait for speech-to-text processing
        async with self.measure_time("speech_to_text_processing"):
            async def check_transcription():
                response = await self.client.get(
                    f"/api/v1/messages/{message_id}/transcription",
                    headers=auth_headers
                )
                return response.status_code == 200
            
            await wait_for_condition(
                check_transcription,
                timeout=30.0,
                error_message="Speech-to-text processing timeout"
            )
            
            # Get transcription result
            response = await self.client.get(
                f"/api/v1/messages/{message_id}/transcription",
                headers=auth_headers
            )
            
            transcription = validate_response(response, 200,
                required_fields=["text", "confidence", "language"])
            
            assert transcription["confidence"] > 0.7
            assert len(transcription["text"]) > 0
        
        # Step 3: Generate AI response
        async with self.measure_time("ai_response_generation"):
            response = await self.client.post(
                f"/api/v1/conversations/{conversation_id}/generate-ai-response",
                json={
                    "message_id": message_id,
                    "response_format": "both",  # text and audio
                    "voice_preference": "friendly_child"
                },
                headers={**auth_headers, **generate_child_safety_headers(child["id"], age=8)}
            )
            
            ai_generation = validate_response(response, 202,
                required_fields=["ai_response_id", "generation_started"])
            
            ai_response_id = ai_generation["ai_response_id"]
        
        # Step 4: Wait for text-to-speech generation
        async with self.measure_time("text_to_speech_generation"):
            async def check_audio_response():
                response = await self.client.get(
                    f"/api/v1/ai-responses/{ai_response_id}",
                    headers=auth_headers
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("audio_ready", False)
                return False
            
            await wait_for_condition(
                check_audio_response,
                timeout=60.0,
                error_message="Text-to-speech generation timeout"
            )
            
            # Get complete AI response
            response = await self.client.get(
                f"/api/v1/ai-responses/{ai_response_id}",
                headers=auth_headers
            )
            
            ai_response = validate_response(response, 200,
                required_fields=["text_content", "audio_url", "safety_approved"])
            
            assert ai_response["safety_approved"] is True
            assert ai_response["audio_url"] is not None
            assert len(ai_response["text_content"]) > 0
        
        # Step 5: Verify audio delivery to device
        async with self.measure_time("audio_delivery_verification"):
            response = await self.client.get(
                f"/api/v1/ai-responses/{ai_response_id}/delivery-status",
                headers=auth_headers
            )
            
            delivery_status = validate_response(response, 200,
                required_fields=["delivered", "delivery_method", "device_acknowledged"])
            
            # In production, this would be delivered to ESP32 device
            assert delivery_status["delivery_method"] in ["websocket", "http_push", "mqtt"]
    
    @performance_test(threshold_ms=2000.0)
    async def test_real_time_safety_monitoring(self):
        """Test real-time safety monitoring during conversations."""
        
        # Setup conversation
        parent = await self.data_manager.create_test_user(role="parent")
        child = await self.data_manager.create_test_child(
            parent_id=uuid.UUID(parent["id"]),
            estimated_age=6,  # COPPA protected
            parental_consent=True
        )
        
        auth_headers = generate_auth_headers(
            await self._get_auth_token(parent["username"])
        )
        
        response = await self.client.post(
            f"/api/v1/children/{child['id']}/conversations",
            json={"title": "Safety Monitoring Test"},
            headers={**auth_headers, **generate_child_safety_headers(child["id"], age=6)}
        )
        
        conversation = validate_response(response, 201)
        conversation_id = conversation["id"]
        
        # Test scenarios that should trigger safety alerts
        safety_test_scenarios = [
            {
                "message": "I want to tell you my home address",
                "expected_alert": "pii_detection",
                "severity": "medium"
            },
            {
                "message": "Someone at school is being mean to me",
                "expected_alert": "emotional_distress",
                "severity": "low"
            },
            {
                "message": "Can you help me with my homework about fractions?",
                "expected_alert": None,
                "severity": None
            }
        ]
        
        for scenario in safety_test_scenarios:
            # Send message
            async with self.measure_time("safety_check_processing"):
                response = await self.client.post(
                    f"/api/v1/conversations/{conversation_id}/messages",
                    json={
                        "content": scenario["message"],
                        "sender_type": "child"
                    },
                    headers={**auth_headers, **generate_child_safety_headers(child["id"], age=6)}
                )
                
                if scenario["expected_alert"]:
                    # Expect safety intervention
                    if response.status_code == 422:
                        # Message blocked
                        error_data = response.json()
                        assert error_data["error"] == scenario["expected_alert"]
                    else:
                        # Message allowed but flagged
                        message_data = validate_response(response, 201)
                        assert message_data["safety_flagged"] is True
                        assert message_data["alert_type"] == scenario["expected_alert"]
                else:
                    # Normal message processing
                    message_data = validate_response(response, 201)
                    assert message_data.get("safety_flagged", False) is False
            
            # Check safety monitoring dashboard
            response = await self.client.get(
                f"/api/v1/dashboard/children/{child['id']}/safety-alerts/recent",
                headers=auth_headers
            )
            
            alerts = validate_response(response, 200,
                required_fields=["alerts", "total_count"])
            
            if scenario["expected_alert"]:
                # Verify alert was created
                relevant_alerts = [
                    alert for alert in alerts["alerts"]
                    if alert["type"] == scenario["expected_alert"]
                ]
                assert len(relevant_alerts) > 0
                
                latest_alert = relevant_alerts[0]
                assert latest_alert["severity"] == scenario["severity"]
                assert latest_alert["child_id"] == child["id"]
    
    @performance_test(threshold_ms=1500.0)
    async def test_parent_dashboard_comprehensive_view(self):
        """Test comprehensive parent dashboard functionality."""
        
        # Create family with activity history
        parent = await self.data_manager.create_test_user(role="parent")
        children = []
        
        for age in [6, 10, 14]:
            child = await self.data_manager.create_test_child(
                parent_id=uuid.UUID(parent["id"]),
                estimated_age=age,
                parental_consent=True
            )
            children.append(child)
        
        auth_headers = generate_auth_headers(
            await self._get_auth_token(parent["username"])
        )
        
        # Generate activity for dashboard testing
        await self._generate_family_activity(children, auth_headers)
        
        # Test main dashboard overview
        async with self.measure_time("dashboard_overview"):
            response = await self.client.get(
                "/api/v1/dashboard/overview",
                headers=auth_headers
            )
            
            dashboard = validate_response(response, 200,
                required_fields=["family_summary", "children", "recent_activity", "safety_summary"])
            
            assert dashboard["family_summary"]["total_children"] == 3
            assert len(dashboard["children"]) == 3
            assert len(dashboard["recent_activity"]) > 0
        
        # Test detailed child analytics
        for child in children:
            async with self.measure_time(f"child_analytics_{child['estimated_age']}"):
                response = await self.client.get(
                    f"/api/v1/dashboard/children/{child['id']}/analytics",
                    params={"period": "7d"},
                    headers=auth_headers
                )
                
                analytics = validate_response(response, 200,
                    required_fields=["usage_stats", "educational_progress", "safety_metrics"])
                
                assert "total_interactions" in analytics["usage_stats"]
                assert "average_session_duration" in analytics["usage_stats"]
                assert "learning_achievements" in analytics["educational_progress"]
                assert "safety_score" in analytics["safety_metrics"]
        
        # Test safety reporting
        async with self.measure_time("safety_reporting"):
            response = await self.client.get(
                "/api/v1/dashboard/safety-report",
                params={"children": [child["id"] for child in children]},
                headers=auth_headers
            )
            
            safety_report = validate_response(response, 200,
                required_fields=["overall_safety_score", "per_child_summary", "recommendations"])
            
            assert 0.0 <= safety_report["overall_safety_score"] <= 1.0
            assert len(safety_report["per_child_summary"]) == 3
        
        # Test parental controls
        async with self.measure_time("parental_controls"):
            response = await self.client.get(
                "/api/v1/dashboard/parental-controls",
                headers=auth_headers
            )
            
            controls = validate_response(response, 200,
                required_fields=["content_filters", "time_limits", "safety_settings"])
            
            # Test updating controls
            updated_controls = {
                "content_filters": {
                    "strictness_level": "high",
                    "custom_blocked_topics": ["violence", "scary_content"]
                },
                "time_limits": {
                    "daily_limit_minutes": 60,
                    "bedtime_cutoff": "20:00"
                }
            }
            
            response = await self.client.put(
                "/api/v1/dashboard/parental-controls",
                json=updated_controls,
                headers=auth_headers
            )
            
            validate_response(response, 200)
    
    async def _get_auth_token(self, username: str, password: str = "test_password") -> str:
        """Get authentication token for user."""
        response = await self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password}
        )
        
        if response.status_code != 200:
            raise ValueError(f"Authentication failed for {username}")
        
        return response.json()["access_token"]
    
    async def _generate_family_activity(self, children: List[Dict], auth_headers: Dict[str, str]):
        """Generate test activity for family dashboard testing."""
        activities = [
            {"content": "Tell me about space", "type": "educational"},
            {"content": "Can you sing me a song?", "type": "entertainment"},
            {"content": "I learned something new today", "type": "sharing"},
            {"content": "What's the weather like?", "type": "conversation"}
        ]
        
        for child in children:
            # Create conversation
            response = await self.client.post(
                f"/api/v1/children/{child['id']}/conversations",
                json={"title": f"Activity for {child['name']}"},
                headers={**auth_headers, **generate_child_safety_headers(
                    child["id"], age=child["estimated_age"]
                )}
            )
            
            conversation = validate_response(response, 201)
            
            # Add messages
            for activity in activities[:2]:  # Limit activities for performance
                await self.client.post(
                    f"/api/v1/conversations/{conversation['id']}/messages",
                    json={
                        "content": activity["content"],
                        "sender_type": "child"
                    },
                    headers={**auth_headers, **generate_child_safety_headers(
                        child["id"], age=child["estimated_age"]
                    )}
                )
                
                await asyncio.sleep(0.1)  # Small delay for realistic timing


# Test execution configuration
@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.production_api
class TestProductionAPIFlowsE2E:
    """Test class for running production API flow tests."""
    
    async def test_run_production_api_flow_tests(self):
        """Run all production API flow tests."""
        config = E2ETestConfig(
            max_response_time_ms=5000.0,
            enable_security_tests=True,
            enable_child_safety_tests=True
        )
        
        test_suite = ProductionAPIFlowTests(config)
        
        try:
            await test_suite.setup()
            
            # Run all API flow tests
            await test_suite.test_complete_user_onboarding_flow()
            await test_suite.test_multi_child_conversation_management()
            await test_suite.test_audio_processing_pipeline()
            await test_suite.test_real_time_safety_monitoring()
            await test_suite.test_parent_dashboard_comprehensive_view()
            
        finally:
            await test_suite.teardown()


if __name__ == "__main__":
    # Direct execution for development/debugging
    asyncio.run(TestProductionAPIFlowsE2E().test_run_production_api_flow_tests())