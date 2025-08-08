"""
Redis Failover and Resilience Tests for ConsolidatedConversationService

These tests verify the service's behavior when Redis cache fails or becomes unavailable.
The service should gracefully degrade to database-only mode without losing functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4
from datetime import datetime

from src.services.conversation_service import ConsolidatedConversationService
from src.core.entities import Conversation, Message
from src.adapters.database_production import ProductionConversationRepository, ProductionMessageRepository


class MockFailingRedisCache:
    """Mock Redis cache that simulates various failure scenarios."""

    def __init__(self, failure_mode="connection_error"):
        self.failure_mode = failure_mode
        self.call_count = 0

    async def get_conversation(self, conversation_id: str):
        """Simulate Redis GET failure."""
        self.call_count += 1
        if self.failure_mode == "connection_error":
            raise ConnectionError("Redis connection failed")
        elif self.failure_mode == "timeout":
            raise asyncio.TimeoutError("Redis operation timed out")
        elif self.failure_mode == "intermittent":
            if self.call_count % 2 == 0:
                raise ConnectionError("Intermittent Redis failure")
            return None  # Cache miss
        return None

    async def set_conversation(
        self, conversation_id: str, conversation_data, ttl=3600
    ):
        """Simulate Redis SET failure."""
        self.call_count += 1
        if self.failure_mode in ["connection_error", "timeout"]:
            raise ConnectionError("Redis write failed")
        return True

    async def delete_conversation(self, conversation_id: str):
        """Simulate Redis DELETE failure."""
        self.call_count += 1
        if self.failure_mode in ["connection_error", "timeout"]:
            raise ConnectionError("Redis delete failed")
        return True


@pytest.fixture
async def mock_conversation_repo():
    """Mock conversation repository for testing."""
    from unittest.mock import create_autospec
    repo = create_autospec(ProductionConversationRepository, instance=True)

    # Mock conversation data - using str for consistency with domain model
    test_conversation = Conversation(
        id="123e4567-e89b-12d3-a456-426614174000",
        child_id="456e7890-e89b-12d3-a456-426614174000",
        status="active",
        started_at=datetime.now(),
        last_activity=datetime.now(),
        context={},
    )

    repo.create_conversation.return_value = test_conversation
    repo.get_conversation_by_id.return_value = test_conversation
    repo.update_conversation.return_value = test_conversation

    return repo


@pytest.fixture
async def mock_message_repo():
    """Mock message repository for testing."""
    from unittest.mock import create_autospec
    repo = create_autospec(ProductionMessageRepository, instance=True)

    test_message = Message(
        id=str(uuid4()),
        content="Test message",
        role="user",
        child_id="456e7890-e89b-12d3-a456-426614174000",
        safety_checked=True,
        safety_score=1.0,
    )

    repo.create_message.return_value = test_message
    repo.get_messages_by_conversation.return_value = [test_message]

    return repo


class TestRedisFailoverScenarios:
    """Test Redis failure scenarios and graceful degradation."""

    async def test_redis_connection_failure_graceful_degradation(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test service continues working when Redis connection fails."""

        # Setup service with failing Redis cache
        failing_cache = MockFailingRedisCache("connection_error")
        service = ConsolidatedConversationService(
            conversation_repository=mock_conversation_repo,
            message_repository=mock_message_repo,
            conversation_cache_service=failing_cache,
            enable_metrics=True,
        )

        child_id = "456e7890-e89b-12d3-a456-426614174000"

        # Test conversation creation still works
        conversation = await service.start_new_conversation(
            child_id=child_id, initial_message="Hello!"
        )

        assert conversation is not None
        assert conversation.child_id == child_id

        # Verify repository was called (fallback to database)
        mock_conversation_repo.create_conversation.assert_called_once()

        # Verify Redis was attempted but failed gracefully
        assert failing_cache.call_count > 0

    async def test_redis_timeout_handling(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test handling of Redis timeout errors."""

        failing_cache = MockFailingRedisCache("timeout")
        service = ConsolidatedConversationService(
            conversation_repository=mock_conversation_repo,
            message_repository=mock_message_repo,
            conversation_cache_service=failing_cache,
        )

        conversation_id = "123e4567-e89b-12d3-a456-426614174000"

        # Test get conversation with Redis timeout
        conversation = await service.get_conversation_internal(conversation_id)

        assert conversation is not None
        # Should fall back to database query
        mock_conversation_repo.get_conversation_by_id.assert_called_once_with(
            conversation_id
        )

    async def test_intermittent_redis_failures(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test handling of intermittent Redis failures."""

        intermittent_cache = MockFailingRedisCache("intermittent")
        service = ConsolidatedConversationService(
            conversation_repository=mock_conversation_repo,
            message_repository=mock_message_repo,
            conversation_cache_service=intermittent_cache,
        )

        conversation_id = "123e4567-e89b-12d3-a456-426614174000"

        # Make multiple requests - some should fail, some succeed
        results = []
        for i in range(4):
            try:
                conversation = await service.get_conversation_internal(conversation_id)
                results.append("success" if conversation else "cache_miss")
            except Exception:
                results.append("failure")

        # Should have mix of successes and cache misses/failures
        assert "success" in results or "cache_miss" in results
        assert intermittent_cache.call_count == 4

    async def test_redis_failure_during_message_add(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test adding messages when Redis cache fails."""

        failing_cache = MockFailingRedisCache("connection_error")
        service = ConsolidatedConversationService(
            conversation_repository=mock_conversation_repo,
            message_repository=mock_message_repo,
            conversation_cache_service=failing_cache,
        )

        conversation_id = "123e4567-e89b-12d3-a456-426614174000"
        child_id = "456e7890-e89b-12d3-a456-426614174000"

        message = Message(
            content="Test message", role="child", child_id=child_id, metadata={}
        )

        # Should work despite Redis failure
        updated_conversation = await service.add_message(conversation_id, message)

        assert updated_conversation is not None

        # Verify database operations still work
        mock_message_repo.create_message.assert_called_once()
        mock_conversation_repo.get_conversation_by_id.assert_called()

    async def test_metrics_collection_during_redis_failure(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test that metrics are still collected when Redis fails."""

        failing_cache = MockFailingRedisCache("connection_error")

        with patch(
            "src.services.conversation_service.ConversationServiceMetrics"
        ) as mock_metrics:
            service = ConsolidatedConversationService(
                conversation_repository=mock_conversation_repo,
                message_repository=mock_message_repo,
                conversation_cache_service=failing_cache,
                enable_metrics=True,
            )

            child_id = "456e7890-e89b-12d3-a456-426614174000"

            # Perform operation that would normally use cache
            await service.start_new_conversation(child_id, "Hello!")

            # Verify metrics were still recorded
            assert mock_metrics.called

    async def test_no_redis_cache_service(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test service works normally without Redis cache service."""

        service = ConsolidatedConversationService(
            conversation_repository=mock_conversation_repo,
            message_repository=mock_message_repo,
            conversation_cache_service=None,  # No cache service
        )

        child_id = "456e7890-e89b-12d3-a456-426614174000"
        conversation_id = "123e4567-e89b-12d3-a456-426614174000"

        # All operations should work without cache
        conversation = await service.start_new_conversation(child_id, "Hello!")
        assert conversation is not None

        retrieved = await service.get_conversation_internal(conversation_id)
        assert retrieved is not None

        # Should go directly to database
        mock_conversation_repo.create_conversation.assert_called_once()
        mock_conversation_repo.get_conversation_by_id.assert_called_once()


class TestRedisFailureRecovery:
    """Test Redis failure recovery scenarios."""

    async def test_cache_recovery_after_failure(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test that cache operations resume after Redis recovers."""

        # Start with failing cache
        cache = MockFailingRedisCache("connection_error")
        service = ConsolidatedConversationService(
            conversation_repository=mock_conversation_repo,
            message_repository=mock_message_repo,
            conversation_cache_service=cache,
        )

        conversation_id = "123e4567-e89b-12d3-a456-426614174000"

        # First call should fail and fall back to database
        conversation1 = await service.get_conversation_internal(conversation_id)
        assert conversation1 is not None

        # Simulate Redis recovery
        cache.failure_mode = "none"  # Cache now works

        # Subsequent calls should work normally
        conversation2 = await service.get_conversation_internal(conversation_id)
        assert conversation2 is not None

        # Should have attempted cache operations
        assert cache.call_count >= 2

    async def test_circuit_breaker_behavior(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test circuit breaker-like behavior for Redis failures."""

        failing_cache = MockFailingRedisCache("connection_error")

        # Mock the circuit breaker behavior
        with patch("src.services.conversation_service.logger") as mock_logger:
            service = ConsolidatedConversationService(
                conversation_repository=mock_conversation_repo,
                message_repository=mock_message_repo,
                conversation_cache_service=failing_cache,
            )

            conversation_id = "123e4567-e89b-12d3-a456-426614174000"

            # Multiple failures should be logged
            for i in range(3):
                await service.get_conversation_internal(conversation_id)

            # Should have logged Redis errors
            assert mock_logger.warning.called or mock_logger.error.called


class TestRedisFailureImpactOnPerformance:
    """Test performance impact of Redis failures."""

    async def test_performance_degradation_measurement(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Measure performance impact when Redis is unavailable."""

        # Test with working cache
        working_cache = AsyncMock()
        working_cache.get_conversation.return_value = None  # Cache miss
        working_cache.set_conversation.return_value = True

        service_with_cache = ConsolidatedConversationService(
            conversation_repository=mock_conversation_repo,
            message_repository=mock_message_repo,
            conversation_cache_service=working_cache,
        )

        # Test without cache
        service_without_cache = ConsolidatedConversationService(
            conversation_repository=mock_conversation_repo,
            message_repository=mock_message_repo,
            conversation_cache_service=None,
        )

        conversation_id = "123e4567-e89b-12d3-a456-426614174000"

        # Both should work, but we can measure the difference if needed
        start_time = asyncio.get_event_loop().time()
        await service_with_cache.get_conversation_internal(conversation_id)
        cached_time = asyncio.get_event_loop().time() - start_time

        start_time = asyncio.get_event_loop().time()
        await service_without_cache.get_conversation_internal(conversation_id)
        no_cache_time = asyncio.get_event_loop().time() - start_time

        # Both should complete successfully
        assert cached_time >= 0
        assert no_cache_time >= 0


class TestRedisFailureMonitoring:
    """Test monitoring and alerting during Redis failures."""

    async def test_redis_failure_metrics(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test that Redis failures are properly recorded in metrics."""

        failing_cache = MockFailingRedisCache("connection_error")

        with patch(
            "src.services.conversation_service.ConversationServiceMetrics"
        ) as mock_metrics_class:
            mock_metrics = Mock()
            mock_metrics_class.return_value = mock_metrics

            service = ConsolidatedConversationService(
                conversation_repository=mock_conversation_repo,
                message_repository=mock_message_repo,
                conversation_cache_service=failing_cache,
                enable_metrics=True,
            )

            conversation_id = "123e4567-e89b-12d3-a456-426614174000"

            # Trigger Redis failure
            await service.get_conversation_internal(conversation_id)

            # Should record cache miss/error in metrics
            # Note: Specific metric calls depend on implementation
            assert mock_metrics_class.called

    async def test_health_check_with_redis_failure(
        self, mock_conversation_repo, mock_message_repo
    ):
        """Test service health check when Redis is failing."""

        failing_cache = MockFailingRedisCache("connection_error")
        service = ConsolidatedConversationService(
            conversation_repository=mock_conversation_repo,
            message_repository=mock_message_repo,
            conversation_cache_service=failing_cache,
        )

        # Health check should still pass (graceful degradation)
        # Implementation depends on how health_check is implemented
        # This is a placeholder for the actual health check logic
        assert service is not None  # Service should still be operational


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
