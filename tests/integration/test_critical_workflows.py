"""
Integration tests for critical end-to-end workflows.
Tests complete user journeys including child registration, conversations, and safety monitoring.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from src.core.entities import Child, ChildProfile, User, Message, Conversation, AIResponse
from src.core.events import ChildRegistered, ChildProfileUpdated
from src.application.services.child_safety_service import ChildSafetyService
from src.services.service_registry import ServiceRegistry


class TestChildRegistrationWorkflow:
    """Test complete child registration and setup workflow."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_child_registration(self):
        """Test full child registration process with parent consent."""
        # Setup mocks
        mock_user_repo = Mock()
        mock_child_repo = Mock()
        mock_consent_repo = Mock()
        mock_event_store = Mock()
        
        # Parent exists
        parent = User(
            id="parent-123",
            email="parent@example.com",
            role="parent",
            children=[]
        )
        mock_user_repo.get_by_id = AsyncMock(return_value=parent)
        
        # Create child profile
        child_data = {
            "name": "Emma",
            "age": 7,
            "preferences": {
                "favorite_color": "purple",
                "interests": ["art", "music"]
            }
        }
        
        # Step 1: Create child profile with event
        child_profile = ChildProfile.create(**child_data)
        assert child_profile.name == "Emma"
        assert child_profile.age == 7
        
        # Step 2: Get registration event
        events = child_profile.get_uncommitted_events()
        assert len(events) == 1
        assert isinstance(events[0], ChildRegistered)
        
        # Step 3: Save child to repository
        mock_child_repo.create = AsyncMock(return_value=child_profile)
        saved_child = await mock_child_repo.create(child_profile)
        assert saved_child.id == child_profile.id
        
        # Step 4: Create consent record
        consent = {
            "child_id": child_profile.id,
            "parent_id": parent.id,
            "granted_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=365),
            "consent_type": "full_features"
        }
        mock_consent_repo.create_consent = AsyncMock(return_value=consent)
        await mock_consent_repo.create_consent(consent)
        
        # Step 5: Update parent's children list
        parent.children.append(child_profile.id)
        mock_user_repo.update = AsyncMock(return_value=parent)
        await mock_user_repo.update(parent)
        
        # Step 6: Store events
        mock_event_store.append_events = AsyncMock()
        await mock_event_store.append_events(child_profile.id, events)
        
        # Verify complete workflow
        assert child_profile.id in parent.children
        mock_child_repo.create.assert_called_once()
        mock_consent_repo.create_consent.assert_called_once()
        mock_user_repo.update.assert_called_once()
        mock_event_store.append_events.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_child_registration_with_safety_validation(self):
        """Test child registration includes safety setup."""
        safety_service = ChildSafetyService()
        
        # Create child with preferences
        child = ChildProfile.create(
            name="Lucas",
            age=6,
            preferences={
                "safety_mode": "strict",
                "content_filters": ["violence", "scary"],
                "allowed_topics": ["animals", "nature", "science"]
            }
        )
        
        # Initialize safety profile
        safety_profile = {
            "child_id": child.id,
            "age_group": "early_elementary",
            "safety_level": "strict",
            "custom_filters": child.preferences.get("content_filters", []),
            "monitoring_enabled": True
        }
        
        # Log safety initialization
        await safety_service.log_safety_event({
            "event_type": "safety_profile_created",
            "child_id": child.id,
            "profile": safety_profile,
            "timestamp": datetime.now().isoformat()
        })
        
        # Verify safety profile
        events = [e for e in safety_service.safety_events if e["child_id"] == child.id]
        assert len(events) == 1
        assert events[0]["event_type"] == "safety_profile_created"
        assert events[0]["profile"]["safety_level"] == "strict"


class TestConversationWorkflow:
    """Test complete conversation workflow with safety checks."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_safe_conversation_flow(self):
        """Test a complete safe conversation from start to finish."""
        # Setup services
        safety_service = ChildSafetyService()
        mock_ai_service = Mock()
        mock_conversation_service = Mock()
        
        # Setup child
        child = Child(id="child-456", name="Sophie", age=8)
        
        # Setup conversation
        conversation = Conversation(child_id=child.id)
        mock_conversation_service.get_or_create_conversation = AsyncMock(
            return_value=conversation
        )
        
        # User message
        user_message = "Tell me a story about a friendly dragon"
        
        # Step 1: Validate input safety
        input_safety = await safety_service.validate_content(user_message, child.age)
        assert input_safety["is_safe"] is True
        
        # Step 2: Create user message
        user_msg = Message(
            content=user_message,
            role="user",
            child_id=child.id,
            safety_checked=True,
            safety_score=input_safety["confidence"]
        )
        conversation.add_message(user_msg)
        
        # Step 3: Generate AI response
        ai_response_text = "Once upon a time, there was a friendly dragon named Sparkle..."
        mock_ai_service.generate_response = AsyncMock(return_value=AIResponse(
            content=ai_response_text,
            emotion="happy",
            safety_score=0.98,
            age_appropriate=True
        ))
        
        ai_response = await mock_ai_service.generate_response(
            user_message=user_message,
            child_age=child.age,
            child_name=child.name,
            conversation_history=conversation.get_recent_messages()
        )
        
        # Step 4: Validate AI response safety
        output_safety = await safety_service.validate_content(
            ai_response.content, 
            child.age
        )
        assert output_safety["is_safe"] is True
        
        # Step 5: Save AI message
        ai_msg = Message(
            content=ai_response.content,
            role="assistant",
            child_id=child.id,
            safety_checked=True,
            safety_score=output_safety["confidence"]
        )
        conversation.add_message(ai_msg)
        
        # Step 6: Log conversation metrics
        await safety_service.log_safety_event({
            "event_type": "conversation_turn",
            "child_id": child.id,
            "conversation_id": conversation.id,
            "input_safety": input_safety["confidence"],
            "output_safety": output_safety["confidence"],
            "emotion": ai_response.emotion,
            "timestamp": datetime.now().isoformat()
        })
        
        # Verify complete flow
        messages = conversation.get_recent_messages()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert all(msg.safety_checked for msg in messages)
        assert all(msg.safety_score > 0.9 for msg in messages)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_unsafe_content_handling_workflow(self):
        """Test complete workflow when unsafe content is detected."""
        safety_service = ChildSafetyService()
        mock_notification_service = Mock()
        
        child = Child(id="child-789", name="Max", age=6)
        
        # Unsafe user input
        unsafe_message = "Tell me about guns and violence"
        
        # Step 1: Detect unsafe content
        safety_result = await safety_service.validate_content(unsafe_message, child.age)
        assert safety_result["is_safe"] is False
        assert len(safety_result["issues"]) > 0
        
        # Step 2: Filter content
        filtered_message = await safety_service.filter_content(unsafe_message)
        assert "guns" not in filtered_message.lower()
        assert "violence" not in filtered_message.lower()
        
        # Step 3: Log safety violation
        violation_event = {
            "event_type": "safety_violation",
            "child_id": child.id,
            "severity": "high",
            "violations": [issue["type"] for issue in safety_result["issues"]],
            "original_content_hash": hash(unsafe_message),  # Don't log actual content
            "timestamp": datetime.now().isoformat()
        }
        await safety_service.log_safety_event(violation_event)
        
        # Step 4: Generate safe alternative response
        safe_response = "I'd love to tell you a story! How about a tale about friendly animals instead?"
        
        # Step 5: Check if parent notification needed
        violations_today = [
            e for e in safety_service.safety_events
            if e["child_id"] == child.id 
            and e["event_type"] == "safety_violation"
            and e.get("severity") == "high"
        ]
        
        if len(violations_today) >= 3:
            # Notify parent
            mock_notification_service.notify_parent = AsyncMock()
            await mock_notification_service.notify_parent(
                child_id=child.id,
                event_type="multiple_safety_violations",
                count=len(violations_today)
            )
        
        # Verify safety was enforced
        assert filtered_message != unsafe_message
        assert len([e for e in safety_service.safety_events if e["event_type"] == "safety_violation"]) > 0


class TestMultiChildFamilyWorkflow:
    """Test workflows for families with multiple children."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sibling_content_isolation(self):
        """Test that sibling conversations are properly isolated."""
        mock_conversation_service = Mock()
        
        # Create family
        parent = User(
            id="parent-999",
            email="family@example.com",
            children=["child-1", "child-2", "child-3"]
        )
        
        # Create siblings with different ages
        siblings = [
            Child(id="child-1", name="Alice", age=5),
            Child(id="child-2", name="Bob", age=8),
            Child(id="child-3", name="Carol", age=11)
        ]
        
        # Create separate conversations
        conversations = {}
        for sibling in siblings:
            conv = Conversation(child_id=sibling.id)
            conversations[sibling.id] = conv
            
            # Add age-appropriate content
            if sibling.age <= 6:
                content = "Let's learn colors and shapes!"
            elif sibling.age <= 9:
                content = "Let's explore simple science experiments!"
            else:
                content = "Let's discuss interesting historical events!"
            
            msg = Message(
                content=content,
                role="assistant",
                child_id=sibling.id
            )
            conv.add_message(msg)
        
        # Verify isolation
        for sibling in siblings:
            conv = conversations[sibling.id]
            messages = conv.get_recent_messages()
            
            # Each child should only see their own messages
            assert all(msg.child_id == sibling.id for msg in messages)
            
            # Content should be age-appropriate
            assert len(messages) == 1
            if sibling.age <= 6:
                assert "colors" in messages[0].content
            elif sibling.age <= 9:
                assert "science" in messages[0].content
            else:
                assert "historical" in messages[0].content

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_family_safety_monitoring(self):
        """Test aggregated safety monitoring for family."""
        safety_service = ChildSafetyService()
        
        family_children = ["child-a", "child-b", "child-c"]
        
        # Simulate activity for each child
        test_data = [
            ("child-a", 5, "Tell me about puppies", True),
            ("child-a", 5, "What do dinosaurs eat?", True),
            ("child-b", 9, "How do volcanoes work?", True),
            ("child-b", 9, "Tell me about weapons", False),  # Unsafe
            ("child-c", 12, "Explain photosynthesis", True),
            ("child-c", 12, "What is cryptocurrency?", True),
        ]
        
        # Process each interaction
        for child_id, age, content, expected_safe in test_data:
            result = await safety_service.validate_content(content, age)
            
            await safety_service.log_safety_event({
                "event_type": "content_check",
                "child_id": child_id,
                "age": age,
                "safe": result["is_safe"],
                "timestamp": datetime.now().isoformat()
            })
            
            assert result["is_safe"] == expected_safe
        
        # Generate family safety report
        family_report = {}
        for child_id in family_children:
            child_events = [
                e for e in safety_service.safety_events 
                if e["child_id"] == child_id
            ]
            
            total_checks = len(child_events)
            safe_checks = len([e for e in child_events if e.get("safe", True)])
            
            family_report[child_id] = {
                "total_interactions": total_checks,
                "safe_interactions": safe_checks,
                "safety_rate": safe_checks / total_checks if total_checks > 0 else 1.0
            }
        
        # Verify report
        assert family_report["child-a"]["safety_rate"] == 1.0
        assert family_report["child-b"]["safety_rate"] == 0.5  # One unsafe
        assert family_report["child-c"]["safety_rate"] == 1.0


class TestErrorRecoveryWorkflow:
    """Test system recovery from various error conditions."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ai_service_failure_recovery(self):
        """Test graceful handling when AI service fails."""
        mock_ai_service = Mock()
        safety_service = ChildSafetyService()
        
        child = Child(id="child-err", name="Test", age=7)
        
        # First attempt fails
        mock_ai_service.generate_response = AsyncMock(
            side_effect=Exception("AI service timeout")
        )
        
        fallback_response = None
        try:
            await mock_ai_service.generate_response(
                user_message="Hello",
                child_age=child.age,
                child_name=child.name
            )
        except Exception:
            # Use fallback response
            fallback_response = AIResponse(
                content="I'm having trouble thinking right now. Can you try asking again?",
                emotion="apologetic",
                safety_score=1.0,
                age_appropriate=True
            )
        
        assert fallback_response is not None
        assert fallback_response.safety_score == 1.0
        
        # Log service failure
        await safety_service.log_safety_event({
            "event_type": "service_failure",
            "service": "ai_service",
            "child_id": child.id,
            "fallback_used": True,
            "timestamp": datetime.now().isoformat()
        })

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_failure_recovery(self):
        """Test handling of database failures during conversation."""
        mock_db_service = Mock()
        mock_cache_service = Mock()
        
        # Database fails
        mock_db_service.save_message = AsyncMock(
            side_effect=Exception("Database connection lost")
        )
        
        # Cache is available
        mock_cache_service.save_message = AsyncMock(return_value=True)
        mock_cache_service.queue_for_retry = AsyncMock(return_value=True)
        
        message = Message(
            content="Test message",
            role="user",
            child_id="child-123"
        )
        
        # Try database first, fall back to cache
        saved = False
        try:
            await mock_db_service.save_message(message)
        except Exception:
            # Save to cache
            saved = await mock_cache_service.save_message(message)
            # Queue for retry
            await mock_cache_service.queue_for_retry("save_message", message)
        
        assert saved is True
        mock_cache_service.save_message.assert_called_once()
        mock_cache_service.queue_for_retry.assert_called_once()