"""End-to-End Tests for ConsolidatedConversationService

This test suite provides comprehensive E2E testing covering:
- Full API workflow testing through FastAPI endpoints
- Real database persistence and retrieval
- Integration with all external services
- User journey testing from start to finish
- Production-like environment testing
"""

import asyncio
import pytest
import json
from datetime import datetime
from typing import Dict, Any, List
from uuid import UUID, uuid4
from httpx import AsyncClient

from src.services.conversation_service import (
    ConsolidatedConversationService,
    MessageType,
    ConversationStatus,
    InteractionType,
)


class TestConversationAPIEndpoints:
    """Test conversation service through API endpoints."""
    
    @pytest.fixture
    async def client(self):
        """Create test client with full application setup."""
        from src.main import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    async def auth_headers(self):
        """Create authentication headers for testing."""
        # Mock JWT token for testing
        mock_token = "test_jwt_token_here"
        return {"Authorization": f"Bearer {mock_token}"}
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_conversation_creation_api(self, client, auth_headers):
        """Test conversation creation through API endpoint."""
        child_id = str(uuid4())
        
        # Create conversation via API
        response = await client.post(
            "/api/v1/conversations",
            headers=auth_headers,
            json={
                "child_id": child_id,
                "initial_message": "Hello, I want to chat!",
                "interaction_type": "chat",
                "metadata": {
                    "session_type": "api_test",
                    "client_version": "1.0.0"
                }
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert "conversation_id" in data
        assert "status" in data
        assert data["status"] == "active"
        
        # Verify conversation can be retrieved
        conversation_id = data["conversation_id"]
        get_response = await client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers=auth_headers
        )
        
        assert get_response.status_code == 200
        conversation_data = get_response.json()
        assert conversation_data["id"] == conversation_id
        assert conversation_data["child_id"] == child_id
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_message_flow_api(self, client, auth_headers):
        """Test complete message flow through API."""
        child_id = str(uuid4())
        
        # 1. Create conversation
        create_response = await client.post(
            "/api/v1/conversations",
            headers=auth_headers,
            json={
                "child_id": child_id,
                "initial_message": "Hi teddy!",
                "interaction_type": "chat"
            }
        )
        
        conversation_id = create_response.json()["conversation_id"]
        
        # 2. Add messages through API
        messages = [
            {"content": "How are you today?", "type": "user_input"},
            {"content": "I'm doing great! What would you like to talk about?", "type": "ai_response"},
            {"content": "Can you tell me about dinosaurs?", "type": "user_input"},
        ]
        
        for message_data in messages:
            response = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={
                    **message_data,
                    "sender_id": child_id if message_data["type"] == "user_input" else None
                }
            )
            assert response.status_code == 201
        
        # 3. Get conversation messages
        messages_response = await client.get(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=auth_headers
        )
        
        assert messages_response.status_code == 200
        messages_data = messages_response.json()
        
        # Should have initial message + added messages
        assert len(messages_data["messages"]) >= len(messages)
        
        # 4. Get conversation analytics
        analytics_response = await client.get(
            f"/api/v1/conversations/{conversation_id}/analytics",
            headers=auth_headers
        )
        
        assert analytics_response.status_code == 200
        analytics = analytics_response.json()
        assert analytics["total_messages"] >= len(messages)
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_conversation_management_api(self, client, auth_headers):
        """Test conversation management operations through API."""
        child_id = str(uuid4())
        
        # Create multiple conversations
        conversation_ids = []
        for i in range(3):
            response = await client.post(
                "/api/v1/conversations",
                headers=auth_headers,
                json={
                    "child_id": child_id,
                    "initial_message": f"Conversation {i+1}",
                    "interaction_type": "chat"
                }
            )
            conversation_ids.append(response.json()["conversation_id"])
        
        # List conversations for child
        list_response = await client.get(
            f"/api/v1/children/{child_id}/conversations",
            headers=auth_headers
        )
        
        assert list_response.status_code == 200
        conversations_list = list_response.json()["conversations"]
        assert len(conversations_list) >= 3
        
        # Archive a conversation
        archive_response = await client.post(
            f"/api/v1/conversations/{conversation_ids[0]}/archive",
            headers=auth_headers
        )
        
        assert archive_response.status_code == 200
        
        # Verify conversation is archived
        get_response = await client.get(
            f"/api/v1/conversations/{conversation_ids[0]}",
            headers=auth_headers
        )
        
        conversation_data = get_response.json()
        assert conversation_data["status"] == "completed"


class TestRealDatabaseE2E:
    """Test with real database operations end-to-end."""
    
    @pytest.fixture
    async def service_with_real_db(self):
        """Create service with real database connection."""
        from src.services.service_registry import get_conversation_service
        
        # Get service from registry (should use real database)
        service = await get_conversation_service()
        yield service
        
        # Cleanup test data would go here
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.database
    async def test_full_conversation_persistence(self, service_with_real_db):
        """Test complete conversation persistence with real database."""
        service = service_with_real_db
        child_id = uuid4()
        
        # Create conversation
        conversation = await service.start_new_conversation(
            child_id=child_id,
            initial_message="Real database test",
            interaction_type=InteractionType.CHAT,
            metadata={"test_type": "e2e_database"}
        )
        
        conversation_id = conversation.id
        
        # Add multiple messages
        messages = [
            "Hello teddy, this is a real database test",
            "How are you feeling today?",
            "Can you help me learn about space?",
            "Thank you for being my friend!"
        ]
        
        for message_content in messages:
            await service.add_message_internal(
                conversation_id=conversation_id,
                message_type=MessageType.USER_INPUT,
                content=message_content,
                sender_id=child_id
            )
        
        # Verify persistence by creating new service instance
        new_service = await get_conversation_service()
        
        # Retrieve conversation with new service instance
        retrieved_conversation = await new_service.get_conversation_internal(conversation_id)
        assert retrieved_conversation.id == conversation_id
        assert retrieved_conversation.child_id == child_id
        
        # Retrieve messages
        retrieved_messages = await new_service.get_conversation_messages(conversation_id)
        
        # Should have initial message + added messages
        assert len(retrieved_messages) >= len(messages)
        
        # Verify message content
        message_contents = [msg.content for msg in retrieved_messages]
        for message in messages:
            assert message in message_contents
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.database
    async def test_child_conversation_history(self, service_with_real_db):
        """Test child conversation history with real database."""
        service = service_with_real_db
        child_id = uuid4()
        
        # Create multiple conversations for child
        conversations = []
        for i in range(5):
            conv = await service.start_new_conversation(
                child_id=child_id,
                initial_message=f"Conversation {i+1} for history test",
                interaction_type=InteractionType.CHAT
            )
            conversations.append(conv)
            
            # Add some messages to each conversation
            for j in range(3):
                await service.add_message_internal(
                    conversation_id=conv.id,
                    message_type=MessageType.USER_INPUT,
                    content=f"Message {j+1} in conversation {i+1}",
                    sender_id=child_id
                )
        
        # End some conversations
        for conv in conversations[:2]:
            await service.end_conversation(conv.id, "test_cleanup")
        
        # Retrieve conversation history
        active_conversations = await service.get_conversations_for_child(
            child_id=child_id,
            limit=10,
            include_completed=False
        )
        
        completed_conversations = await service.get_conversations_for_child(
            child_id=child_id,
            limit=10,
            include_completed=True
        )
        
        # Verify results
        assert len(active_conversations) >= 3  # 3 still active
        assert len(completed_conversations) >= 5  # All conversations


class TestUserJourneyE2E:
    """Test complete user journeys end-to-end."""
    
    @pytest.fixture
    async def full_app_setup(self):
        """Setup full application stack for testing."""
        from src.services.service_registry import get_service_registry
        
        # Initialize service registry
        registry = await get_service_registry()
        
        yield {
            "conversation_service": await registry.get_conversation_service(),
            "user_service": await registry.get_user_service(),
            "child_safety_service": await registry.get_child_safety_service(),
        }
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.user_journey
    async def test_child_first_conversation_journey(self, full_app_setup):
        """Test a child's first conversation journey."""
        services = full_app_setup
        conversation_service = services["conversation_service"]
        
        # Simulate child starting first conversation
        child_id = uuid4()
        
        # 1. Child says hello
        conversation = await conversation_service.start_new_conversation(
            child_id=child_id,
            initial_message="Hi! I'm new here. What's your name?",
            interaction_type=InteractionType.CHAT,
            metadata={"first_time_user": True}
        )
        
        # 2. AI introduces itself
        await conversation_service.add_message_internal(
            conversation_id=conversation.id,
            message_type=MessageType.AI_RESPONSE,
            content="Hello! I'm your friendly AI Teddy Bear! I'm so excited to meet you. What's your name?",
            sender_id=None
        )
        
        # 3. Child shares name and asks about games
        await conversation_service.add_message_internal(
            conversation_id=conversation.id,
            message_type=MessageType.USER_INPUT,
            content="My name is Alex! Do you know any fun games we can play?",
            sender_id=child_id
        )
        
        # 4. AI suggests games
        await conversation_service.add_message_internal(
            conversation_id=conversation.id,
            message_type=MessageType.AI_RESPONSE,
            content="Nice to meet you, Alex! I know lots of games! We could play 20 questions, tell stories together, or I could teach you about animals. What sounds fun?",
            sender_id=None
        )
        
        # 5. Child chooses activity
        await conversation_service.add_message_internal(
            conversation_id=conversation.id,
            message_type=MessageType.USER_INPUT,
            content="I love animals! Can you tell me about dolphins?",
            sender_id=child_id
        )
        
        # 6. Record interaction event
        await conversation_service.record_interaction_event(
            conversation_id=conversation.id,
            event_type="topic_selection",
            event_data={"topic": "animals", "specific": "dolphins"}
        )
        
        # 7. Get conversation analytics
        analytics = await conversation_service.get_conversation_analytics(conversation.id)
        
        # Verify journey success
        assert analytics["total_messages"] >= 5
        assert analytics["user_messages"] >= 2
        assert analytics["ai_responses"] >= 2
        assert conversation.status == ConversationStatus.ACTIVE.value
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.user_journey
    async def test_safety_incident_journey(self, full_app_setup):
        """Test safety incident handling journey."""
        services = full_app_setup
        conversation_service = services["conversation_service"]
        
        child_id = uuid4()
        
        # Start normal conversation
        conversation = await conversation_service.start_new_conversation(
            child_id=child_id,
            initial_message="Hi teddy, I want to ask you something",
            interaction_type=InteractionType.CHAT
        )
        
        # Child sends concerning message
        concerning_message = "Someone at school asked for my phone number and address"
        
        # This should trigger safety mechanisms
        try:
            await conversation_service.add_message_internal(
                conversation_id=conversation.id,
                message_type=MessageType.USER_INPUT,
                content=concerning_message,
                sender_id=child_id
            )
        except Exception:
            # Expected - safety check should prevent this
            pass
        
        # Report safety incident
        incident_result = await conversation_service.report_safety_incident(
            conversation_id=conversation.id,
            incident_type="potential_personal_info_request",
            severity=IncidentSeverity.HIGH,
            details={
                "message_content": concerning_message,
                "child_id": str(child_id),
                "timestamp": datetime.now().isoformat(),
                "detected_keywords": ["phone number", "address"]
            }
        )
        
        assert incident_result is True
        assert conversation_service.safety_incidents >= 1
        
        # Add safe redirect message
        await conversation_service.add_message_internal(
            conversation_id=conversation.id,
            message_type=MessageType.SYSTEM_MESSAGE,
            content="It's important to keep personal information private. Let's talk about something fun instead! What's your favorite subject in school?",
            sender_id=None
        )
        
        # Continue with safe conversation
        await conversation_service.add_message_internal(
            conversation_id=conversation.id,
            message_type=MessageType.USER_INPUT,
            content="I like science! Can you tell me about stars?",
            sender_id=child_id
        )
        
        # Verify conversation continued safely
        messages = await conversation_service.get_conversation_messages(conversation.id)
        assert len(messages) >= 2  # Initial + safe redirect + safe response
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.user_journey
    async def test_long_conversation_journey(self, full_app_setup):
        """Test long conversation session journey."""
        services = full_app_setup
        conversation_service = services["conversation_service"]
        
        child_id = uuid4()
        
        # Start storytelling conversation
        conversation = await conversation_service.start_new_conversation(
            child_id=child_id,
            initial_message="Can you tell me a really long story about space adventure?",
            interaction_type=InteractionType.STORY
        )
        
        # Simulate long back-and-forth storytelling
        story_parts = [
            ("Once upon a time, there was a brave astronaut named Captain Star...", MessageType.AI_RESPONSE),
            ("Ooh, what did Captain Star look like?", MessageType.USER_INPUT),
            ("Captain Star wore a shiny silver space suit and had kind blue eyes...", MessageType.AI_RESPONSE),
            ("Did Captain Star have a spaceship?", MessageType.USER_INPUT),
            ("Yes! Captain Star had the most amazing spaceship called the Galaxy Explorer...", MessageType.AI_RESPONSE),
            ("What color was the spaceship?", MessageType.USER_INPUT),
            ("The Galaxy Explorer was bright blue with silver stars painted on the sides...", MessageType.AI_RESPONSE),
            ("Where did Captain Star go first?", MessageType.USER_INPUT),
            ("Captain Star's first destination was the colorful planet of Rainbowland...", MessageType.AI_RESPONSE),
            ("What was on Rainbowland?", MessageType.USER_INPUT),
        ]
        
        for content, msg_type in story_parts:
            sender_id = child_id if msg_type == MessageType.USER_INPUT else None
            
            await conversation_service.add_message_internal(
                conversation_id=conversation.id,
                message_type=msg_type,
                content=content,
                sender_id=sender_id
            )
        
        # Record story progression events
        await conversation_service.record_interaction_event(
            conversation_id=conversation.id,
            event_type="story_progression",
            event_data={"story_length": len(story_parts), "engagement_level": "high"}
        )
        
        # Get conversation context (should be well-managed even with many messages)
        context = await conversation_service.get_conversation_context(
            conversation.id,
            context_size=5
        )
        
        assert len(context) <= 5  # Should limit context appropriately
        
        # Get final analytics
        analytics = await conversation_service.get_conversation_analytics(conversation.id)
        
        assert analytics["total_messages"] >= len(story_parts)
        assert analytics["duration_minutes"] > 0
        assert "interaction_patterns" in analytics


class TestPerformanceE2E:
    """Test performance characteristics end-to-end."""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.performance
    async def test_concurrent_users_performance(self):
        """Test performance with multiple concurrent users."""
        from src.services.service_registry import get_conversation_service
        
        service = await get_conversation_service()
        
        async def simulate_user_session(user_id: int):
            """Simulate a complete user session."""
            child_id = uuid4()
            
            # Start conversation
            conversation = await service.start_new_conversation(
                child_id=child_id,
                initial_message=f"Hi from user {user_id}!",
                interaction_type=InteractionType.CHAT
            )
            
            # Add several messages
            for i in range(5):
                await service.add_message_internal(
                    conversation_id=conversation.id,
                    message_type=MessageType.USER_INPUT,
                    content=f"Message {i+1} from user {user_id}",
                    sender_id=child_id
                )
            
            # Get analytics
            await service.get_conversation_analytics(conversation.id)
            
            # End conversation
            await service.end_conversation(
                conversation.id,
                reason="session_completed"
            )
            
            return conversation.id
        
        import time
        start_time = time.time()
        
        # Simulate 20 concurrent users
        tasks = [simulate_user_session(i) for i in range(20)]
        conversation_ids = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle 20 concurrent users efficiently
        assert duration < 10.0, f"Performance issue: {duration}s for 20 concurrent users"
        assert len(conversation_ids) == 20
        assert all(isinstance(cid, UUID) for cid in conversation_ids)
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.performance
    async def test_message_throughput_e2e(self):
        """Test message processing throughput end-to-end."""
        from src.services.service_registry import get_conversation_service
        
        service = await get_conversation_service()
        child_id = uuid4()
        
        # Start conversation
        conversation = await service.start_new_conversation(
            child_id=child_id,
            initial_message="Throughput test"
        )
        
        import time
        start_time = time.time()
        
        # Add 100 messages rapidly
        tasks = []
        for i in range(100):
            task = service.add_message_internal(
                conversation_id=conversation.id,
                message_type=MessageType.USER_INPUT,
                content=f"Throughput test message {i}",
                sender_id=child_id
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        throughput = 100 / duration
        
        # Should process messages efficiently
        assert throughput > 50, f"Throughput issue: {throughput} messages/second"


if __name__ == "__main__":
    # Run E2E tests
    pytest.main([__file__, "-v", "--tb=short", "-m", "e2e"])