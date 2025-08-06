"""
Tests for Production Event Bus Advanced.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from src.infrastructure.messaging.production_event_bus_advanced import (
    ProductionEventBus,
    DomainEvent,
    EventMetadata,
    EventHandler,
    EventPriority,
    EventStatus,
    BackendType,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    QueueMessage,
    MessagePriority
)


class TestEventMetadata:
    """Test event metadata functionality."""

    def test_event_metadata_creation(self):
        """Test event metadata creation."""
        metadata = EventMetadata(
            event_id="test-123",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.HIGH,
            created_at=datetime.now(),
            correlation_id="corr-123"
        )
        
        assert metadata.event_id == "test-123"
        assert metadata.event_type == "user.created"
        assert metadata.priority == EventPriority.HIGH
        assert metadata.status == EventStatus.PENDING
        assert metadata.attempts == 0

    def test_event_metadata_to_dict(self):
        """Test event metadata serialization."""
        now = datetime.now()
        metadata = EventMetadata(
            event_id="test-123",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.HIGH,
            created_at=now
        )
        
        data = metadata.to_dict()
        
        assert data["event_id"] == "test-123"
        assert data["priority"] == EventPriority.HIGH.value
        assert data["status"] == EventStatus.PENDING.value
        assert data["created_at"] == now.isoformat()

    def test_event_metadata_from_dict(self):
        """Test event metadata deserialization."""
        now = datetime.now()
        data = {
            "event_id": "test-123",
            "event_type": "user.created",
            "source_service": "user-service",
            "version": "1.0",
            "priority": EventPriority.HIGH.value,
            "created_at": now.isoformat(),
            "status": EventStatus.PENDING.value,
            "attempts": 0,
            "max_attempts": 3,
            "retry_after": None,
            "correlation_id": None,
            "causation_id": None,
            "user_id": None,
            "session_id": None,
            "target_services": [],
            "routing_key": None
        }
        
        metadata = EventMetadata.from_dict(data)
        
        assert metadata.event_id == "test-123"
        assert metadata.priority == EventPriority.HIGH
        assert metadata.created_at == now


class TestDomainEvent:
    """Test domain event functionality."""

    def test_domain_event_creation(self):
        """Test domain event creation."""
        metadata = EventMetadata(
            event_id="test-123",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now()
        )
        
        event = DomainEvent(
            metadata=metadata,
            payload={"user_id": "user-123", "email": "test@example.com"}
        )
        
        assert event.metadata.event_id == "test-123"
        assert event.payload["user_id"] == "user-123"
        assert event.schema_version == "1.0"

    def test_domain_event_to_message(self):
        """Test domain event message conversion."""
        metadata = EventMetadata(
            event_id="test-123",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now()
        )
        
        event = DomainEvent(
            metadata=metadata,
            payload={"user_id": "user-123"}
        )
        
        message = event.to_message()
        
        assert "metadata" in message
        assert "payload" in message
        assert message["payload"]["user_id"] == "user-123"

    def test_domain_event_from_message(self):
        """Test domain event from message conversion."""
        now = datetime.now()
        message = {
            "metadata": {
                "event_id": "test-123",
                "event_type": "user.created",
                "source_service": "user-service",
                "version": "1.0",
                "priority": EventPriority.NORMAL.value,
                "created_at": now.isoformat(),
                "status": EventStatus.PENDING.value,
                "attempts": 0,
                "max_attempts": 3,
                "retry_after": None,
                "correlation_id": None,
                "causation_id": None,
                "user_id": None,
                "session_id": None,
                "target_services": [],
                "routing_key": None
            },
            "payload": {"user_id": "user-123"},
            "schema_version": "1.0"
        }
        
        event = DomainEvent.from_message(message)
        
        assert event.metadata.event_id == "test-123"
        assert event.payload["user_id"] == "user-123"


class TestQueueMessage:
    """Test queue message functionality."""

    def test_queue_message_creation(self):
        """Test queue message creation."""
        message = QueueMessage(
            topic="user.events",
            payload={"user_id": "user-123"},
            priority=MessagePriority.HIGH
        )
        
        assert message.topic == "user.events"
        assert message.priority == MessagePriority.HIGH
        assert message.retry_count == 0
        assert len(message.id) > 0

    def test_queue_message_to_dict(self):
        """Test queue message serialization."""
        now = datetime.now()
        message = QueueMessage(
            id="msg-123",
            topic="user.events",
            payload={"user_id": "user-123"},
            priority=MessagePriority.HIGH,
            created_at=now
        )
        
        data = message.to_dict()
        
        assert data["id"] == "msg-123"
        assert data["topic"] == "user.events"
        assert data["priority"] == MessagePriority.HIGH.value
        assert data["created_at"] == now.isoformat()

    def test_queue_message_from_dict(self):
        """Test queue message deserialization."""
        now = datetime.now()
        data = {
            "id": "msg-123",
            "topic": "user.events",
            "payload": {"user_id": "user-123"},
            "priority": MessagePriority.HIGH.value,
            "created_at": now.isoformat(),
            "retry_count": 0,
            "max_retries": 3,
            "delay_seconds": 0,
            "expires_at": None,
            "correlation_id": None,
            "reply_to": None
        }
        
        message = QueueMessage.from_dict(data)
        
        assert message.id == "msg-123"
        assert message.priority == MessagePriority.HIGH
        assert message.created_at == now


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker instance."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60,
            success_threshold=2
        )
        return CircuitBreaker("test_breaker", config)

    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self, circuit_breaker):
        """Test successful circuit breaker call."""
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self, circuit_breaker):
        """Test circuit breaker opening after failure threshold."""
        async def failing_func():
            raise Exception("Test failure")
        
        # Fail enough times to trip the breaker
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state(self, circuit_breaker):
        """Test circuit breaker behavior in open state."""
        # Trip the breaker
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.last_failure_time = datetime.now()
        
        async def test_func():
            return "should not execute"
        
        with pytest.raises(Exception, match="Circuit breaker.*is OPEN"):
            await circuit_breaker.call(test_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, circuit_breaker):
        """Test circuit breaker recovery through half-open state."""
        # Set to half-open state
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker.success_count = 0
        
        async def success_func():
            return "success"
        
        # Succeed enough times to close the breaker
        for _ in range(2):
            await circuit_breaker.call(success_func)
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0


class TestEventHandler:
    """Test event handler base class."""

    def test_event_handler_creation(self):
        """Test event handler creation."""
        handler = EventHandler("test_handler")
        
        assert handler.handler_name == "test_handler"
        assert handler.logger is not None

    @pytest.mark.asyncio
    async def test_event_handler_abstract_methods(self):
        """Test event handler abstract methods."""
        handler = EventHandler("test_handler")
        
        with pytest.raises(NotImplementedError):
            await handler.handle(Mock(spec=True))
        
        with pytest.raises(NotImplementedError):
            handler.can_handle("test.event")


class TestProductionEventBus:
    """Test production event bus functionality."""

    @pytest.fixture
    def event_bus(self):
        """Create event bus instance."""
        return ProductionEventBus(backend_type=BackendType.REDIS_STREAMS)

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        return AsyncMock(spec=True)

    def test_event_bus_initialization(self, event_bus):
        """Test event bus initialization."""
        assert event_bus.backend_type == BackendType.REDIS_STREAMS
        assert event_bus._handlers == {}
        assert event_bus._circuit_breakers == {}
        assert event_bus._event_store == {}

    @pytest.mark.asyncio
    async def test_publish_event(self, event_bus):
        """Test event publishing."""
        with patch.object(event_bus, '_publish_to_redis', new_callable=AsyncMock) as mock_publish:
            event_id = await event_bus.publish_event(
                event_type="user.created",
                payload={"user_id": "user-123"},
                source_service="user-service",
                correlation_id="corr-123"
            )
            
            assert event_id is not None
            assert len(event_id) > 0
            mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event_with_priority(self, event_bus):
        """Test event publishing with priority."""
        with patch.object(event_bus, '_publish_to_redis', new_callable=AsyncMock):
            event_id = await event_bus.publish_event(
                event_type="urgent.alert",
                payload={"message": "Critical alert"},
                source_service="alert-service",
                priority=EventPriority.CRITICAL
            )
            
            assert event_id is not None
            assert event_bus._metrics["events_published"] == 1

    def test_register_handler(self, event_bus):
        """Test event handler registration."""
        handler = EventHandler("test_handler")
        
        event_bus.register_handler("user.created", handler)
        
        assert "user.created" in event_bus._handlers
        assert handler in event_bus._handlers["user.created"]
        assert event_bus._metrics["handlers_registered"] == 1

    @pytest.mark.asyncio
    async def test_process_event_success(self, event_bus):
        """Test successful event processing."""
        # Create mock handler
        mock_handler = Mock(spec=EventHandler)
        mock_handler.handler_name = "test_handler"
        mock_handler.handle = AsyncMock(return_value=True)
        
        event_bus.register_handler("user.created", mock_handler)
        
        # Create test event
        metadata = EventMetadata(
            event_id="test-123",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now()
        )
        event = DomainEvent(metadata=metadata, payload={"user_id": "user-123"})
        
        # Process event
        result = await event_bus._process_event(event)
        
        assert result is True
        assert event_bus._metrics["events_processed"] == 1
        mock_handler.handle.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_process_event_failure(self, event_bus):
        """Test event processing failure."""
        # Create mock handler that fails
        mock_handler = Mock(spec=EventHandler)
        mock_handler.handler_name = "failing_handler"
        mock_handler.handle = AsyncMock(side_effect=Exception("Handler failed"))
        
        event_bus.register_handler("user.created", mock_handler)
        
        # Create test event
        metadata = EventMetadata(
            event_id="test-123",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now()
        )
        event = DomainEvent(metadata=metadata, payload={"user_id": "user-123"})
        
        # Process event
        result = await event_bus._process_event(event)
        
        assert result is False
        assert event_bus._metrics["events_failed"] == 1

    @pytest.mark.asyncio
    async def test_process_event_no_handlers(self, event_bus):
        """Test event processing with no handlers."""
        # Create test event
        metadata = EventMetadata(
            event_id="test-123",
            event_type="unknown.event",
            source_service="test-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now()
        )
        event = DomainEvent(metadata=metadata, payload={})
        
        # Process event
        result = await event_bus._process_event(event)
        
        assert result is True  # No handlers is not an error

    @pytest.mark.asyncio
    async def test_handle_processing_failure_retry(self, event_bus):
        """Test processing failure with retry."""
        metadata = EventMetadata(
            event_id="test-123",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now(),
            attempts=0
        )
        event = DomainEvent(metadata=metadata, payload={"user_id": "user-123"})
        
        with patch.object(event_bus, '_schedule_retry', new_callable=AsyncMock) as mock_schedule:
            await event_bus._handle_processing_failure(event, "redis")
            
            assert event.metadata.attempts == 1
            assert event.metadata.status == EventStatus.RETRYING
            mock_schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_processing_failure_dlq(self, event_bus):
        """Test processing failure sent to DLQ."""
        metadata = EventMetadata(
            event_id="test-123",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now(),
            attempts=3  # Max attempts reached
        )
        event = DomainEvent(metadata=metadata, payload={"user_id": "user-123"})
        
        with patch.object(event_bus, '_send_to_dlq', new_callable=AsyncMock) as mock_dlq:
            await event_bus._handle_processing_failure(event, "redis")
            
            mock_dlq.assert_called_once_with(event, "max_retries_exceeded")
            assert event_bus._metrics["events_dlq"] == 1

    @pytest.mark.asyncio
    async def test_replay_events(self, event_bus):
        """Test event replay functionality."""
        correlation_id = "corr-123"
        
        # Add events to event store
        metadata1 = EventMetadata(
            event_id="event-1",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now()
        )
        event1 = DomainEvent(metadata=metadata1, payload={"user_id": "user-1"})
        
        metadata2 = EventMetadata(
            event_id="event-2",
            event_type="user.updated",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now()
        )
        event2 = DomainEvent(metadata=metadata2, payload={"user_id": "user-1"})
        
        event_bus._event_store[correlation_id] = [event1, event2]
        
        # Replay events
        replayed_events = await event_bus.replay_events(correlation_id)
        
        assert len(replayed_events) == 2
        assert replayed_events[0].metadata.event_id == "event-1"
        assert replayed_events[1].metadata.event_id == "event-2"

    @pytest.mark.asyncio
    async def test_replay_events_with_timestamp_filter(self, event_bus):
        """Test event replay with timestamp filtering."""
        correlation_id = "corr-123"
        now = datetime.now()
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)
        
        # Add events with different timestamps
        metadata1 = EventMetadata(
            event_id="event-1",
            event_type="user.created",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=past
        )
        event1 = DomainEvent(metadata=metadata1, payload={"user_id": "user-1"})
        
        metadata2 = EventMetadata(
            event_id="event-2",
            event_type="user.updated",
            source_service="user-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=now
        )
        event2 = DomainEvent(metadata=metadata2, payload={"user_id": "user-1"})
        
        event_bus._event_store[correlation_id] = [event1, event2]
        
        # Replay events from now onwards
        replayed_events = await event_bus.replay_events(
            correlation_id, 
            from_timestamp=now
        )
        
        assert len(replayed_events) == 1
        assert replayed_events[0].metadata.event_id == "event-2"

    def test_get_metrics(self, event_bus):
        """Test metrics retrieval."""
        # Set some metrics
        event_bus._metrics["events_published"] = 10
        event_bus._metrics["events_processed"] = 8
        event_bus._metrics["events_failed"] = 2
        
        metrics = event_bus.get_metrics()
        
        assert metrics["events_published"] == 10
        assert metrics["events_processed"] == 8
        assert metrics["events_failed"] == 2
        assert "circuit_breakers" in metrics
        assert "timestamp" in metrics

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, event_bus):
        """Test health check when healthy."""
        # Mock Redis client
        mock_redis = AsyncMock(spec=True)
        mock_redis.ping = AsyncMock(spec=True)
        event_bus._redis_client = mock_redis
        
        health = await event_bus.health_check()
        
        assert health["overall_status"] == "healthy"
        assert health["backends"]["redis"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, event_bus):
        """Test health check when unhealthy."""
        # Mock Redis client that fails
        mock_redis = AsyncMock(spec=True)
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection failed"))
        event_bus._redis_client = mock_redis
        
        health = await event_bus.health_check()
        
        assert health["overall_status"] == "degraded"
        assert "unhealthy" in health["backends"]["redis"]

    @pytest.mark.asyncio
    async def test_legacy_publish_compatibility(self, event_bus):
        """Test legacy publish method compatibility."""
        # Mock event object
        mock_event = Mock(spec=True)
        mock_event.event_type = "user.created"
        mock_event.data = {"user_id": "user-123"}
        mock_event.aggregate_type = "user"
        mock_event.correlation_id = "corr-123"
        
        with patch.object(event_bus, 'publish_event', new_callable=AsyncMock) as mock_publish:
            mock_publish.return_value = "event-123"
            
            result = await event_bus.publish(mock_event)
            
            assert result is True
            mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_legacy_subscribe_compatibility(self, event_bus):
        """Test legacy subscribe method compatibility."""
        async def test_handler(event):
            pass
        
        result = await event_bus.subscribe("user.created", test_handler, "test_handler")
        
        assert result is True
        assert "user.created" in event_bus._handlers
        assert len(event_bus._handlers["user.created"]) == 1

    @pytest.mark.asyncio
    async def test_send_message_compatibility(self, event_bus):
        """Test message queue send compatibility."""
        with patch.object(event_bus, 'publish_event', new_callable=AsyncMock) as mock_publish:
            mock_publish.return_value = "event-123"
            
            result = await event_bus.send_message(
                topic="user.notifications",
                payload={"message": "Welcome!"},
                priority=MessagePriority.HIGH
            )
            
            assert result is True
            mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_depth(self, event_bus):
        """Test queue depth retrieval."""
        # Mock Redis client
        mock_redis = AsyncMock(spec=True)
        mock_redis.xinfo_stream = AsyncMock(return_value={"length": 5})
        event_bus._redis_client = mock_redis
        
        depth = await event_bus.get_queue_depth("test.topic")
        
        assert depth == 5

    @pytest.mark.asyncio
    async def test_shutdown(self, event_bus):
        """Test graceful shutdown."""
        # Mock clients
        mock_redis = AsyncMock(spec=True)
        mock_rabbitmq_pool = AsyncMock(spec=True)
        
        event_bus._redis_client = mock_redis
        event_bus._rabbitmq_pool = mock_rabbitmq_pool
        
        await event_bus.shutdown()
        
        mock_redis.close.assert_called_once()
        mock_rabbitmq_pool.close.assert_called_once()


class TestProductionEventBusErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def event_bus(self):
        return ProductionEventBus(backend_type=BackendType.REDIS_STREAMS)

    @pytest.mark.asyncio
    async def test_publish_event_backend_failure(self, event_bus):
        """Test event publishing with backend failure."""
        with patch.object(event_bus, '_publish_to_redis', side_effect=Exception("Redis failed")):
            with pytest.raises(Exception, match="Redis failed"):
                await event_bus.publish_event(
                    event_type="test.event",
                    payload={"test": "data"},
                    source_service="test-service"
                )

    @pytest.mark.asyncio
    async def test_process_event_circuit_breaker(self, event_bus):
        """Test event processing with circuit breaker."""
        # Create handler that will trigger circuit breaker
        mock_handler = Mock(spec=EventHandler)
        mock_handler.handler_name = "failing_handler"
        mock_handler.handle = AsyncMock(side_effect=Exception("Handler failed"))
        
        event_bus.register_handler("test.event", mock_handler)
        
        # Create test event
        metadata = EventMetadata(
            event_id="test-123",
            event_type="test.event",
            source_service="test-service",
            version="1.0",
            priority=EventPriority.NORMAL,
            created_at=datetime.now()
        )
        event = DomainEvent(metadata=metadata, payload={})
        
        # Process event multiple times to trip circuit breaker
        for _ in range(5):
            await event_bus._process_event(event)
        
        # Circuit breaker should be open
        circuit_breaker_name = "failing_handler_test.event"
        circuit_breaker = event_bus._circuit_breakers[circuit_breaker_name]
        assert circuit_breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_legacy_methods_error_handling(self, event_bus):
        """Test error handling in legacy compatibility methods."""
        # Test publish with invalid event
        result = await event_bus.publish(None)
        assert result is False
        
        # Test subscribe with invalid handler
        result = await event_bus.subscribe("test.event", None)
        assert result is False
        
        # Test send_message with backend failure
        with patch.object(event_bus, 'publish_event', side_effect=Exception("Backend failed")):
            result = await event_bus.send_message("test.topic", {"test": "data"})
            assert result is False