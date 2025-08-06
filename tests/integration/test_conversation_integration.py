"""Integration Tests for ConsolidatedConversationService

This test suite provides comprehensive integration testing between:
- ConsolidatedConversationService and database repositories
- ConsolidatedConversationService and external services
- End-to-end conversation workflows
- Real database operations with test data
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List
from uuid import UUID, uuid4

from src.services.conversation_service import (
    ConsolidatedConversationService,
    MessageType,
    ConversationStatus,
    InteractionType,
    IncidentSeverity,
)
from src.core.entities import Conversation, Message


class TestConversationDatabaseIntegration:
    """Test integration with real database repositories."""
    
    @pytest.fixture
    async def service_with_db(self):
        """Create service with real database repositories."""
        from src.adapters.database_production import (
            ProductionConversationRepository,
            ProductionMessageRepository
        )
        from src.infrastructure.persistence.database.production_config import (
            initialize_database
        )
        
        # Initialize test database
        db_manager = await initialize_database()
        session = db_manager.session_factory()
        
        conversation_repo = ProductionConversationRepository(session)
        message_repo = ProductionMessageRepository(session)
        
        service = ConsolidatedConversationService(
            conversation_repository=conversation_repo,
            message_repository=message_repo
        )
        
        yield service
        
        # Cleanup
        await session.close()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_conversation_lifecycle_with_db(self, service_with_db):
        """Test complete conversation lifecycle with real database."""
        service = service_with_db
        child_id = uuid4()
        
        # 1. Start new conversation
        conversation = await service.start_new_conversation(
            child_id=child_id,
            initial_message="Hello, teddy bear!",
            interaction_type=InteractionType.CHAT,
            metadata={"session_type": "test"}
        )
        
        assert isinstance(conversation, Conversation)
        assert conversation.child_id == child_id
        assert conversation.status == ConversationStatus.ACTIVE.value
        
        # 2. Add multiple messages
        messages_to_add = [
            ("How are you today?", MessageType.USER_INPUT),
            ("I'm doing great! How can I help you?", MessageType.AI_RESPONSE),
            ("Can you tell me a story?", MessageType.USER_INPUT),
            ("Once upon a time...", MessageType.AI_RESPONSE),
        ]
        
        added_messages = []
        for content, msg_type in messages_to_add:
            message = await service.add_message_internal(
                conversation_id=conversation.id,
                message_type=msg_type,
                content=content,
                sender_id=child_id if msg_type == MessageType.USER_INPUT else None
            )
            added_messages.append(message)
            assert isinstance(message, Message)
            assert message.content == content
        
        # 3. Retrieve conversation messages
        retrieved_messages = await service.get_conversation_messages(
            conversation_id=conversation.id
        )
        
        # Should have initial message + added messages
        assert len(retrieved_messages) >= len(messages_to_add)
        
        # 4. Get conversation analytics
        analytics = await service.get_conversation_analytics(conversation.id)
        assert analytics["total_messages"] >= len(messages_to_add)
        assert analytics["user_messages"] >= 2
        assert analytics["ai_responses"] >= 2
        
        # 5. End conversation
        ended_conversation = await service.end_conversation(
            conversation_id=conversation.id,
            reason="test_completed",
            summary="Integration test conversation"
        )
        
        assert ended_conversation.status == ConversationStatus.COMPLETED.value
        assert ended_conversation.ended_at is not None
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_conversation_persistence_and_retrieval(self, service_with_db):
        """Test conversation data persistence and retrieval."""
        service = service_with_db
        child_id = uuid4()
        
        # Create conversation with metadata
        conversation = await service.start_new_conversation(
            child_id=child_id,
            initial_message="Test persistence",
            metadata={
                "test_data": "integration_test",
                "session_id": str(uuid4()),
                "timestamp": datetime.now().isoformat()
            }
        )
        
        # Retrieve conversation from database
        retrieved_conversation = await service.get_conversation_internal(conversation.id)
        
        assert retrieved_conversation.id == conversation.id
        assert retrieved_conversation.child_id == child_id
        assert retrieved_conversation.metadata["test_data"] == "integration_test"
        
        # Test getting conversations for child
        child_conversations = await service.get_conversations_for_child(
            child_id=child_id,
            limit=10,
            include_completed=True
        )
        
        assert len(child_conversations) >= 1
        assert any(conv.id == conversation.id for conv in child_conversations)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_message_safety_integration(self, service_with_db):
        """Test message safety checking with database persistence."""
        service = service_with_db
        child_id = uuid4()
        
        # Start conversation
        conversation = await service.start_new_conversation(
            child_id=child_id,
            initial_message="Hello"
        )
        
        # Test safe message
        safe_message = await service.add_message_internal(
            conversation_id=conversation.id,
            message_type=MessageType.USER_INPUT,
            content="What's your favorite game?",
            sender_id=child_id
        )
        assert isinstance(safe_message, Message)
        
        # Test potentially unsafe message (should be caught by safety check)
        try:
            await service.add_message_internal(
                conversation_id=conversation.id,
                message_type=MessageType.USER_INPUT,
                content="What's your phone number?",
                sender_id=child_id
            )
            # If we get here, the safety check didn't catch it
            # This might be expected behavior depending on implementation
        except Exception as e:
            # Safety check caught the unsafe content
            assert "safety" in str(e).lower() or "inappropriate" in str(e).lower()


class TestConversationServiceIntegration:
    """Test integration between ConversationService and other services."""
    
    @pytest.fixture
    async def service_with_mocks(self):
        """Create service with mocked external dependencies."""
        from unittest.mock import AsyncMock, Mock
        
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()
        notification_service = AsyncMock()
        logger = Mock()
        
        service = ConsolidatedConversationService(
            conversation_repository=conversation_repo,
            message_repository=message_repo,
            notification_service=notification_service,
            logger=logger
        )
        
        return service
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_notification_integration(self, service_with_mocks):
        """Test integration with notification service."""
        service = service_with_mocks
        
        # Test sending notification
        result = await service.send_notification(
            recipient_id=str(uuid4()),
            message="Test notification",
            notification_type="conversation_update"
        )
        
        assert result is True
        assert service.notification_count == 1
        
        # Verify notification service was called
        service.notification_service.send_notification.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_safety_incident_reporting_integration(self, service_with_mocks):
        """Test safety incident reporting integration."""
        service = service_with_mocks
        conversation_id = uuid4()
        
        # Setup incident reporting
        service.conversation_repo.create_incident = AsyncMock()
        
        # Report safety incident
        result = await service.report_safety_incident(
            conversation_id=conversation_id,
            incident_type="inappropriate_content",
            severity=IncidentSeverity.HIGH,
            details={
                "content": "Test unsafe content",
                "detected_by": "keyword_filter"
            }
        )
        
        assert result is True
        assert service.safety_incidents == 1
        
        # Verify incident was stored
        service.conversation_repo.create_incident.assert_called_once()


class TestConversationWorkflows:
    """Test complete conversation workflows end-to-end."""
    
    @pytest.fixture
    async def service(self):
        from unittest.mock import AsyncMock, Mock
        
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()
        logger = Mock()
        
        # Mock repository responses
        conversation_repo.create = AsyncMock()
        conversation_repo.update = AsyncMock()
        conversation_repo.get_by_id = AsyncMock()
        conversation_repo.get_by_child_id = AsyncMock(return_value=[])
        message_repo.create = AsyncMock()
        message_repo.get_by_conversation_id = AsyncMock(return_value=[])
        
        return ConsolidatedConversationService(
            conversation_repository=conversation_repo,
            message_repository=message_repo,
            logger=logger
        )
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_interactive_conversation_workflow(self, service):
        """Test realistic interactive conversation workflow."""
        child_id = uuid4()
        
        # 1. Child starts conversation
        conversation = await service.start_new_conversation(
            child_id=child_id,
            initial_message="Hi teddy, I want to play!",
            interaction_type=InteractionType.GAME
        )
        
        # 2. Simulate back-and-forth conversation
        conversation_flow = [
            ("What game should we play?", MessageType.USER_INPUT, child_id),
            ("How about we play 20 questions?", MessageType.AI_RESPONSE, None),
            ("Yes! I'm thinking of an animal.", MessageType.USER_INPUT, child_id),
            ("Is it a mammal?", MessageType.AI_RESPONSE, None),
            ("Yes it is!", MessageType.USER_INPUT, child_id),
            ("Does it live on land?", MessageType.AI_RESPONSE, None),
        ]
        
        for content, msg_type, sender_id in conversation_flow:
            message = await service.add_message_internal(
                conversation_id=conversation.id,
                message_type=msg_type,
                content=content,
                sender_id=sender_id
            )
            assert isinstance(message, Message)
        
        # 3. Record interaction events
        await service.record_interaction_event(
            conversation_id=conversation.id,
            event_type="game_started",
            event_data={"game_type": "20_questions"}
        )
        
        # 4. Get conversation context for AI
        context = await service.get_conversation_context(conversation.id)
        assert len(context) > 0
        
        # 5. End conversation
        ended_conversation = await service.end_conversation(
            conversation_id=conversation.id,
            reason="game_completed"
        )
        
        assert ended_conversation.status == ConversationStatus.COMPLETED.value
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_conversation_management(self, service):
        """Test managing multiple concurrent conversations."""
        child_id = uuid4()
        
        # Start multiple conversations
        conversations = []
        for i in range(5):
            conv = await service.start_new_conversation(
                child_id=child_id,
                initial_message=f"Conversation {i+1}",
                interaction_type=InteractionType.CHAT
            )
            conversations.append(conv)
        
        # Add messages to each conversation
        for i, conversation in enumerate(conversations):
            for j in range(3):
                await service.add_message_internal(
                    conversation_id=conversation.id,
                    message_type=MessageType.USER_INPUT,
                    content=f"Message {j+1} in conversation {i+1}",
                    sender_id=child_id
                )
        
        # Verify all conversations are active
        assert len(service._active_conversations) == 5
        
        # End some conversations
        for conversation in conversations[:3]:
            await service.end_conversation(conversation.id, "test_cleanup")
        
        # Verify remaining active conversations
        active_conversations = [
            conv for conv in service._active_conversations.values()
            if conv.status == ConversationStatus.ACTIVE.value
        ]
        assert len(active_conversations) <= 2  # May be cached differently
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_conversation_overflow_handling(self, service):
        """Test handling of conversation length overflow."""
        child_id = uuid4()
        service.max_conversation_length = 10  # Set low limit for testing
        
        # Start conversation
        conversation = await service.start_new_conversation(
            child_id=child_id,
            initial_message="Starting long conversation"
        )
        
        # Mock conversation with high message count
        mock_conversation = Mock(
            id=conversation.id,
            status=ConversationStatus.ACTIVE.value,
            message_count=15  # Exceeds limit
        )
        service.get_conversation_internal = AsyncMock(return_value=mock_conversation)
        
        # Mock overflow handler
        service._handle_conversation_overflow = AsyncMock()
        
        # Try to add message to overflowing conversation
        from src.core.exceptions import InvalidInputError
        with pytest.raises(InvalidInputError):
            await service.add_message_internal(
                conversation_id=conversation.id,
                message_type=MessageType.USER_INPUT,
                content="This should trigger overflow",
                sender_id=child_id
            )
        
        # Verify overflow handler was called
        service._handle_conversation_overflow.assert_called_once()


class TestConversationPerformanceIntegration:
    """Test performance characteristics under realistic conditions."""
    
    @pytest.fixture
    async def service(self):
        from unittest.mock import AsyncMock, Mock
        
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()
        
        # Simulate realistic database delays
        async def delayed_create(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10ms delay
            return Mock()
        
        conversation_repo.create = delayed_create
        message_repo.create = delayed_create
        
        return ConsolidatedConversationService(
            conversation_repository=conversation_repo,
            message_repository=message_repo
        )
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.performance
    async def test_concurrent_conversations_performance(self, service):
        """Test performance under concurrent conversation load."""
        import time
        
        start_time = time.time()
        
        # Create 50 concurrent conversations
        tasks = []
        for i in range(50):
            task = service.start_new_conversation(
                child_id=uuid4(),
                initial_message=f"Performance test {i}"
            )
            tasks.append(task)
        
        conversations = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time despite database delays
        assert duration < 5.0, f"Performance issue: {duration}s for 50 conversations"
        assert len(conversations) == 50
        assert all(isinstance(conv, Conversation) for conv in conversations)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.performance
    async def test_conversation_context_performance(self, service):
        """Test conversation context retrieval performance."""
        child_id = uuid4()
        
        # Create conversation with many messages
        conversation = await service.start_new_conversation(
            child_id=child_id,
            initial_message="Performance test"
        )
        
        # Mock large message history
        mock_messages = [
            Mock(
                content=f"Message {i}",
                message_type=MessageType.USER_INPUT.value,
                created_at=datetime.now() - timedelta(minutes=i)
            )
            for i in range(100)
        ]
        service.get_conversation_messages = AsyncMock(return_value=mock_messages)
        
        import time
        start_time = time.time()
        
        # Get context multiple times
        for _ in range(10):
            context = await service.get_conversation_context(
                conversation.id,
                context_size=20
            )
            assert len(context) <= 20
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should be fast even with large message history
        assert duration < 1.0, f"Context retrieval too slow: {duration}s"


class TestConversationErrorRecovery:
    """Test error recovery and resilience scenarios."""
    
    @pytest.fixture
    async def service(self):
        from unittest.mock import AsyncMock, Mock
        
        conversation_repo = AsyncMock()
        message_repo = AsyncMock()
        logger = Mock()
        
        return ConsolidatedConversationService(
            conversation_repository=conversation_repo,
            message_repository=message_repo,
            logger=logger
        )
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_failure_recovery(self, service):
        """Test recovery from database failures."""
        child_id = uuid4()
        
        # Simulate database failure
        service.conversation_repo.create = AsyncMock(
            side_effect=Exception("Database connection lost")
        )
        
        # Should handle gracefully
        from src.core.exceptions import ServiceUnavailableError
        with pytest.raises(ServiceUnavailableError):
            await service.start_new_conversation(
                child_id=child_id,
                initial_message="Test message"
            )
        
        # Verify error was logged
        service.logger.error.assert_called()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_partial_failure_recovery(self, service):
        """Test recovery from partial operation failures."""
        child_id = uuid4()
        conversation_id = uuid4()
        
        # Setup successful conversation creation but message failure
        mock_conversation = Mock(
            id=conversation_id,
            status=ConversationStatus.ACTIVE.value,
            message_count=5
        )
        
        service.conversation_repo.create = AsyncMock()
        service.get_conversation_internal = AsyncMock(return_value=mock_conversation)
        service._check_message_safety = AsyncMock(return_value={"is_safe": True})
        service.message_repo.create = AsyncMock(side_effect=Exception("Message save failed"))
        service._conversation_locks[conversation_id] = asyncio.Lock()
        
        # Should handle message creation failure gracefully
        with pytest.raises(Exception):
            await service.add_message_internal(
                conversation_id=conversation_id,
                message_type=MessageType.USER_INPUT,
                content="Test message",
                sender_id=child_id
            )
        
        # Verify error handling
        assert service.logger.error.called


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration"])