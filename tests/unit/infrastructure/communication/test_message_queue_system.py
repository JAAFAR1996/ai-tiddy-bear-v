"""
Message Queue System Tests
==========================
Tests for reliable message queuing and processing system.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MessageStatus(Enum):
    """Message processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class QueueMessage:
    """Message in the queue."""
    id: str
    topic: str
    payload: Dict[str, Any]
    priority: MessagePriority
    created_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    status: MessageStatus = MessageStatus.PENDING
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "payload": self.payload,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "status": self.status.value
        }


class MessageQueueSystem:
    """Production message queue system."""
    
    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self.queues: Dict[str, List[QueueMessage]] = {}
        self.processors: Dict[str, callable] = {}
        self.dead_letter_queue: List[QueueMessage] = []
        self.metrics = {
            "messages_processed": 0,
            "messages_failed": 0,
            "messages_retried": 0,
            "queue_sizes": {},
            "processing_times": []
        }
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
    
    async def enqueue(self, message: QueueMessage) -> bool:
        """Add message to queue."""
        if message.topic not in self.queues:
            self.queues[message.topic] = []
        
        queue = self.queues[message.topic]
        
        if len(queue) >= self.max_queue_size:
            return False
        
        # Insert based on priority
        inserted = False
        for i, existing_msg in enumerate(queue):
            if message.priority.value > existing_msg.priority.value:
                queue.insert(i, message)
                inserted = True
                break
        
        if not inserted:
            queue.append(message)
        
        self.metrics["queue_sizes"][message.topic] = len(queue)
        return True
    
    async def dequeue(self, topic: str) -> QueueMessage:
        """Get next message from queue."""
        if topic not in self.queues or not self.queues[topic]:
            return None
        
        message = self.queues[topic].pop(0)
        self.metrics["queue_sizes"][topic] = len(self.queues[topic])
        return message
    
    def register_processor(self, topic: str, processor: callable):
        """Register message processor for topic."""
        self.processors[topic] = processor
    
    async def start_workers(self, worker_count: int = 3):
        """Start worker tasks."""
        self._running = True
        
        for i in range(worker_count):
            task = asyncio.create_task(self._worker_loop(f"worker_{i}"))
            self._worker_tasks.append(task)
    
    async def stop_workers(self):
        """Stop all workers."""
        self._running = False
        
        for task in self._worker_tasks:
            task.cancel()
        
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
    
    async def _worker_loop(self, worker_id: str):
        """Worker loop for processing messages."""
        while self._running:
            try:
                processed = False
                
                for topic in self.queues.keys():
                    message = await self.dequeue(topic)
                    if message:
                        await self._process_message(message, worker_id)
                        processed = True
                        break
                
                if not processed:
                    await asyncio.sleep(0.1)  # No messages, wait briefly
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)
    
    async def _process_message(self, message: QueueMessage, worker_id: str):
        """Process a single message."""
        start_time = time.time()
        message.status = MessageStatus.PROCESSING
        
        try:
            processor = self.processors.get(message.topic)
            if not processor:
                raise Exception(f"No processor for topic: {message.topic}")
            
            # Process message
            await processor(message.payload)
            
            message.status = MessageStatus.COMPLETED
            self.metrics["messages_processed"] += 1
            
            processing_time = time.time() - start_time
            self.metrics["processing_times"].append(processing_time)
            
        except Exception as e:
            message.status = MessageStatus.FAILED
            message.retry_count += 1
            
            if message.retry_count <= message.max_retries:
                message.status = MessageStatus.RETRY
                await self.enqueue(message)  # Re-queue for retry
                self.metrics["messages_retried"] += 1
            else:
                # Move to dead letter queue
                self.dead_letter_queue.append(message)
                self.metrics["messages_failed"] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get queue metrics."""
        avg_processing_time = 0
        if self.metrics["processing_times"]:
            avg_processing_time = sum(self.metrics["processing_times"]) / len(self.metrics["processing_times"])
        
        return {
            "messages_processed": self.metrics["messages_processed"],
            "messages_failed": self.metrics["messages_failed"],
            "messages_retried": self.metrics["messages_retried"],
            "queue_sizes": self.metrics["queue_sizes"].copy(),
            "dead_letter_queue_size": len(self.dead_letter_queue),
            "avg_processing_time_ms": avg_processing_time * 1000,
            "total_queues": len(self.queues)
        }


@pytest.fixture
def message_queue():
    """Create message queue system for testing."""
    return MessageQueueSystem(max_queue_size=100)


@pytest.fixture
def sample_message():
    """Create sample message for testing."""
    return QueueMessage(
        id="msg_001",
        topic="chat_processing",
        payload={"text": "Hello from teddy!", "user_id": "child_123"},
        priority=MessagePriority.NORMAL,
        created_at=datetime.now()
    )


@pytest.mark.asyncio
class TestMessageQueueSystem:
    """Test message queue system functionality."""
    
    async def test_message_enqueue_and_dequeue(self, message_queue, sample_message):
        """Test basic message enqueue and dequeue operations."""
        # Enqueue message
        success = await message_queue.enqueue(sample_message)
        assert success is True
        
        # Verify queue size
        assert message_queue.metrics["queue_sizes"]["chat_processing"] == 1
        
        # Dequeue message
        dequeued = await message_queue.dequeue("chat_processing")
        assert dequeued is not None
        assert dequeued.id == sample_message.id
        assert dequeued.topic == sample_message.topic
        
        # Verify queue empty
        assert message_queue.metrics["queue_sizes"]["chat_processing"] == 0
    
    async def test_priority_ordering(self, message_queue):
        """Test message priority ordering in queue."""
        messages = [
            QueueMessage("low", "test", {}, MessagePriority.LOW, datetime.now()),
            QueueMessage("high", "test", {}, MessagePriority.HIGH, datetime.now()),
            QueueMessage("normal", "test", {}, MessagePriority.NORMAL, datetime.now()),
            QueueMessage("critical", "test", {}, MessagePriority.CRITICAL, datetime.now())
        ]
        
        # Enqueue in random order
        for msg in messages:
            await message_queue.enqueue(msg)
        
        # Dequeue should return in priority order
        dequeued_order = []
        while True:
            msg = await message_queue.dequeue("test")
            if not msg:
                break
            dequeued_order.append(msg.id)
        
        # Should be: critical, high, normal, low
        expected_order = ["critical", "high", "normal", "low"]
        assert dequeued_order == expected_order
    
    async def test_queue_size_limit(self, message_queue):
        """Test queue size limiting."""
        # Set small limit for testing
        message_queue.max_queue_size = 3
        
        # Enqueue up to limit
        for i in range(3):
            msg = QueueMessage(f"msg_{i}", "test", {}, MessagePriority.NORMAL, datetime.now())
            success = await message_queue.enqueue(msg)
            assert success is True
        
        # Try to exceed limit
        overflow_msg = QueueMessage("overflow", "test", {}, MessagePriority.NORMAL, datetime.now())
        success = await message_queue.enqueue(overflow_msg)
        assert success is False
    
    async def test_message_processor_registration(self, message_queue):
        """Test message processor registration and execution."""
        processed_messages = []
        
        async def test_processor(payload: Dict[str, Any]):
            processed_messages.append(payload)
        
        # Register processor
        message_queue.register_processor("test_topic", test_processor)
        
        # Verify processor registered
        assert "test_topic" in message_queue.processors
        assert message_queue.processors["test_topic"] == test_processor
    
    async def test_worker_message_processing(self, message_queue):
        """Test worker-based message processing."""
        processed_messages = []
        
        async def chat_processor(payload: Dict[str, Any]):
            processed_messages.append(payload)
            await asyncio.sleep(0.01)  # Simulate processing time
        
        # Register processor
        message_queue.register_processor("chat", chat_processor)
        
        # Enqueue messages
        for i in range(5):
            msg = QueueMessage(
                f"msg_{i}",
                "chat",
                {"text": f"Message {i}", "user_id": "child_123"},
                MessagePriority.NORMAL,
                datetime.now()
            )
            await message_queue.enqueue(msg)
        
        # Start workers
        await message_queue.start_workers(worker_count=2)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Stop workers
        await message_queue.stop_workers()
        
        # Verify all messages processed
        assert len(processed_messages) == 5
        assert message_queue.metrics["messages_processed"] == 5
    
    async def test_message_retry_mechanism(self, message_queue):
        """Test message retry on processing failure."""
        retry_attempts = []
        
        async def failing_processor(payload: Dict[str, Any]):
            retry_attempts.append(payload)
            if len(retry_attempts) <= 2:  # Fail first 2 attempts
                raise Exception("Processing failed")
            # Succeed on 3rd attempt
        
        # Register failing processor
        message_queue.register_processor("retry_test", failing_processor)
        
        # Enqueue message
        msg = QueueMessage(
            "retry_msg",
            "retry_test",
            {"data": "test"},
            MessagePriority.NORMAL,
            datetime.now(),
            max_retries=3
        )
        await message_queue.enqueue(msg)
        
        # Start worker
        await message_queue.start_workers(worker_count=1)
        
        # Wait for retries
        await asyncio.sleep(0.5)
        
        # Stop worker
        await message_queue.stop_workers()
        
        # Verify retries occurred
        assert len(retry_attempts) == 3  # Initial + 2 retries
        assert message_queue.metrics["messages_retried"] == 2
        assert message_queue.metrics["messages_processed"] == 1
    
    async def test_dead_letter_queue(self, message_queue):
        """Test dead letter queue for failed messages."""
        async def always_failing_processor(payload: Dict[str, Any]):
            raise Exception("Always fails")
        
        # Register failing processor
        message_queue.register_processor("fail_test", always_failing_processor)
        
        # Enqueue message with limited retries
        msg = QueueMessage(
            "fail_msg",
            "fail_test",
            {"data": "will fail"},
            MessagePriority.NORMAL,
            datetime.now(),
            max_retries=1
        )
        await message_queue.enqueue(msg)
        
        # Start worker
        await message_queue.start_workers(worker_count=1)
        
        # Wait for processing and retries
        await asyncio.sleep(0.5)
        
        # Stop worker
        await message_queue.stop_workers()
        
        # Verify message in dead letter queue
        assert len(message_queue.dead_letter_queue) == 1
        assert message_queue.dead_letter_queue[0].id == "fail_msg"
        assert message_queue.metrics["messages_failed"] == 1
    
    async def test_multiple_topic_processing(self, message_queue):
        """Test processing messages from multiple topics."""
        chat_messages = []
        notification_messages = []
        
        async def chat_processor(payload: Dict[str, Any]):
            chat_messages.append(payload)
        
        async def notification_processor(payload: Dict[str, Any]):
            notification_messages.append(payload)
        
        # Register processors
        message_queue.register_processor("chat", chat_processor)
        message_queue.register_processor("notifications", notification_processor)
        
        # Enqueue messages to different topics
        chat_msg = QueueMessage("chat_1", "chat", {"text": "Hello"}, MessagePriority.NORMAL, datetime.now())
        notif_msg = QueueMessage("notif_1", "notifications", {"title": "Alert"}, MessagePriority.HIGH, datetime.now())
        
        await message_queue.enqueue(chat_msg)
        await message_queue.enqueue(notif_msg)
        
        # Start workers
        await message_queue.start_workers(worker_count=2)
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Stop workers
        await message_queue.stop_workers()
        
        # Verify both topics processed
        assert len(chat_messages) == 1
        assert len(notification_messages) == 1
        assert chat_messages[0]["text"] == "Hello"
        assert notification_messages[0]["title"] == "Alert"
    
    async def test_metrics_collection(self, message_queue):
        """Test comprehensive metrics collection."""
        async def test_processor(payload: Dict[str, Any]):
            await asyncio.sleep(0.01)  # Simulate processing time
        
        message_queue.register_processor("metrics_test", test_processor)
        
        # Enqueue multiple messages
        for i in range(10):
            msg = QueueMessage(
                f"metrics_msg_{i}",
                "metrics_test",
                {"index": i},
                MessagePriority.NORMAL,
                datetime.now()
            )
            await message_queue.enqueue(msg)
        
        # Start workers
        await message_queue.start_workers(worker_count=3)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Stop workers
        await message_queue.stop_workers()
        
        # Get metrics
        metrics = message_queue.get_metrics()
        
        # Verify metrics
        assert metrics["messages_processed"] == 10
        assert metrics["messages_failed"] == 0
        assert metrics["avg_processing_time_ms"] > 0
        assert metrics["total_queues"] >= 1
        assert "queue_sizes" in metrics
    
    async def test_concurrent_enqueue_dequeue(self, message_queue):
        """Test concurrent enqueue and dequeue operations."""
        async def enqueue_messages():
            for i in range(50):
                msg = QueueMessage(
                    f"concurrent_{i}",
                    "concurrent_test",
                    {"index": i},
                    MessagePriority.NORMAL,
                    datetime.now()
                )
                await message_queue.enqueue(msg)
        
        async def dequeue_messages():
            dequeued_count = 0
            while dequeued_count < 50:
                msg = await message_queue.dequeue("concurrent_test")
                if msg:
                    dequeued_count += 1
                else:
                    await asyncio.sleep(0.001)
            return dequeued_count
        
        # Run concurrent operations
        enqueue_task = asyncio.create_task(enqueue_messages())
        dequeue_task = asyncio.create_task(dequeue_messages())
        
        results = await asyncio.gather(enqueue_task, dequeue_task)
        
        # Verify all messages processed
        assert results[1] == 50  # All messages dequeued
    
    async def test_message_serialization(self, sample_message):
        """Test message serialization and deserialization."""
        # Serialize message
        message_dict = sample_message.to_dict()
        
        # Verify serialized format
        assert message_dict["id"] == "msg_001"
        assert message_dict["topic"] == "chat_processing"
        assert message_dict["payload"]["text"] == "Hello from teddy!"
        assert message_dict["priority"] == MessagePriority.NORMAL.value
        assert message_dict["status"] == MessageStatus.PENDING.value
        
        # Verify timestamp format
        datetime.fromisoformat(message_dict["created_at"])  # Should not raise
    
    async def test_coppa_compliant_message_processing(self, message_queue):
        """Test COPPA-compliant message processing for child safety."""
        child_messages = []
        
        async def child_safe_processor(payload: Dict[str, Any]):
            # Simulate content filtering
            if payload.get("user_age", 0) < 13:
                # Apply child safety filters
                filtered_payload = {
                    "text": payload.get("text", "").replace("inappropriate", "fun"),
                    "user_id": payload.get("user_id"),
                    "filtered": True,
                    "coppa_compliant": True
                }
                child_messages.append(filtered_payload)
            else:
                child_messages.append(payload)
        
        # Register child-safe processor
        message_queue.register_processor("child_chat", child_safe_processor)
        
        # Enqueue child message
        child_msg = QueueMessage(
            "child_msg_001",
            "child_chat",
            {
                "text": "This has inappropriate content",
                "user_id": "child_123",
                "user_age": 7
            },
            MessagePriority.HIGH,  # High priority for child messages
            datetime.now()
        )
        await message_queue.enqueue(child_msg)
        
        # Start worker
        await message_queue.start_workers(worker_count=1)
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Stop worker
        await message_queue.stop_workers()
        
        # Verify child-safe processing
        assert len(child_messages) == 1
        processed_msg = child_messages[0]
        assert processed_msg["filtered"] is True
        assert processed_msg["coppa_compliant"] is True
        assert "inappropriate" not in processed_msg["text"]
        assert "fun" in processed_msg["text"]
    
    async def test_emergency_message_priority(self, message_queue):
        """Test emergency message handling with critical priority."""
        processed_order = []
        
        async def emergency_processor(payload: Dict[str, Any]):
            processed_order.append(payload["message_type"])
        
        message_queue.register_processor("emergency", emergency_processor)
        
        # Enqueue messages in mixed order
        messages = [
            QueueMessage("normal", "emergency", {"message_type": "normal"}, MessagePriority.NORMAL, datetime.now()),
            QueueMessage("critical", "emergency", {"message_type": "emergency"}, MessagePriority.CRITICAL, datetime.now()),
            QueueMessage("low", "emergency", {"message_type": "info"}, MessagePriority.LOW, datetime.now()),
            QueueMessage("high", "emergency", {"message_type": "alert"}, MessagePriority.HIGH, datetime.now())
        ]
        
        for msg in messages:
            await message_queue.enqueue(msg)
        
        # Start worker
        await message_queue.start_workers(worker_count=1)
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Stop worker
        await message_queue.stop_workers()
        
        # Verify emergency messages processed first
        assert processed_order[0] == "emergency"  # Critical priority first
        assert processed_order[1] == "alert"      # High priority second
        assert processed_order[2] == "normal"     # Normal priority third
        assert processed_order[3] == "info"       # Low priority last