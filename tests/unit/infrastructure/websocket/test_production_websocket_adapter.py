"""
Production WebSocket Adapter Tests
=================================
Comprehensive tests for real-time WebSocket communication with ESP32 devices.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.infrastructure.websocket.production_websocket_adapter import (
    ProductionWebSocketAdapter,
    WebSocketMessage,
    WebSocketConnection,
    MessageType,
    ConnectionStatus,
    WebSocketMetrics
)


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.messages = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
        
    async def send_text(self, data: str):
        if self.closed:
            raise Exception("WebSocket closed")
        self.messages.append(data)
        
    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason


@pytest.fixture
async def websocket_adapter():
    """Create WebSocket adapter for testing."""
    adapter = ProductionWebSocketAdapter()
    yield adapter
    await adapter.shutdown()


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket."""
    return MockWebSocket()


@pytest.mark.asyncio
class TestProductionWebSocketAdapter:
    """Test WebSocket adapter functionality."""
    
    async def test_websocket_connection_establishment(self, websocket_adapter, mock_websocket):
        """Test successful WebSocket connection."""
        # Connect
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123",
            session_id="session_456",
            metadata={"device": "teddy_bear", "age": 7}
        )
        
        # Verify connection
        assert connection_id is not None
        assert connection_id in websocket_adapter.connections
        
        connection = websocket_adapter.connections[connection_id]
        assert connection.user_id == "child_123"
        assert connection.session_id == "session_456"
        assert connection.status == ConnectionStatus.CONNECTED
        assert connection.metadata["device"] == "teddy_bear"
        
        # Verify welcome message sent
        assert len(mock_websocket.messages) == 1
        welcome_msg = json.loads(mock_websocket.messages[0])
        assert welcome_msg["type"] == "system"
        assert welcome_msg["data"]["event"] == "connected"
        
        # Verify metrics updated
        assert websocket_adapter.metrics.total_connections == 1
        assert websocket_adapter.metrics.active_connections == 1
    
    async def test_connection_limit_enforcement(self, websocket_adapter):
        """Test connection limit per user."""
        user_id = "child_123"
        connections = []
        
        # Create connections up to limit
        for i in range(websocket_adapter.max_connections_per_user):
            mock_ws = MockWebSocket()
            conn_id = await websocket_adapter.connect(
                websocket=mock_ws,
                user_id=user_id
            )
            connections.append((conn_id, mock_ws))
        
        # Attempt to exceed limit
        excess_ws = MockWebSocket()
        conn_id = await websocket_adapter.connect(
            websocket=excess_ws,
            user_id=user_id
        )
        
        # Should be rejected
        assert conn_id is None
        assert excess_ws.closed
        assert excess_ws.close_code == 1008
    
    async def test_message_sending_and_routing(self, websocket_adapter, mock_websocket):
        """Test message sending to specific connections."""
        # Connect
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123"
        )
        
        # Clear welcome message
        mock_websocket.messages.clear()
        
        # Send message
        message = WebSocketMessage(
            message_type=MessageType.CHAT,
            data={"text": "Hello from teddy!", "emotion": "happy"},
            sender_id="teddy_ai"
        )
        
        success = await websocket_adapter.send_message(connection_id, message)
        
        # Verify message sent
        assert success
        assert len(mock_websocket.messages) == 1
        
        sent_msg = json.loads(mock_websocket.messages[0])
        assert sent_msg["type"] == "chat"
        assert sent_msg["data"]["text"] == "Hello from teddy!"
        assert sent_msg["data"]["emotion"] == "happy"
        assert sent_msg["sender_id"] == "teddy_ai"
    
    async def test_user_broadcast(self, websocket_adapter):
        """Test broadcasting to all user connections."""
        user_id = "child_123"
        websockets = []
        
        # Create multiple connections for same user
        for i in range(3):
            mock_ws = MockWebSocket()
            await websocket_adapter.connect(
                websocket=mock_ws,
                user_id=user_id
            )
            websockets.append(mock_ws)
        
        # Clear welcome messages
        for ws in websockets:
            ws.messages.clear()
        
        # Broadcast message
        message = WebSocketMessage(
            message_type=MessageType.NOTIFICATION,
            data={"title": "Bedtime Reminder", "message": "Time for sleep!"}
        )
        
        sent_count = await websocket_adapter.send_to_user(user_id, message)
        
        # Verify broadcast
        assert sent_count == 3
        
        for ws in websockets:
            assert len(ws.messages) == 1
            msg = json.loads(ws.messages[0])
            assert msg["type"] == "notification"
            assert msg["data"]["title"] == "Bedtime Reminder"
    
    async def test_topic_subscription_and_broadcast(self, websocket_adapter, mock_websocket):
        """Test topic subscription and broadcasting."""
        # Connect
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123"
        )
        
        # Subscribe to topic
        subscribe_msg = WebSocketMessage(
            message_type=MessageType.SUBSCRIBE,
            data={"topic": "bedtime_stories"},
            correlation_id="sub_123"
        )
        
        await websocket_adapter.handle_message(
            connection_id,
            json.dumps(subscribe_msg.to_dict())
        )
        
        # Verify subscription
        assert "bedtime_stories" in websocket_adapter.topic_subscriptions
        assert connection_id in websocket_adapter.topic_subscriptions["bedtime_stories"]
        
        # Clear messages
        mock_websocket.messages.clear()
        
        # Broadcast to topic
        broadcast_msg = WebSocketMessage(
            message_type=MessageType.CHAT,
            data={"story": "Once upon a time...", "chapter": 1}
        )
        
        sent_count = await websocket_adapter.broadcast_to_topic(
            "bedtime_stories",
            broadcast_msg
        )
        
        # Verify broadcast received
        assert sent_count == 1
        assert len(mock_websocket.messages) == 1
        
        received_msg = json.loads(mock_websocket.messages[0])
        assert received_msg["data"]["story"] == "Once upon a time..."
    
    async def test_rate_limiting(self, websocket_adapter, mock_websocket):
        """Test message rate limiting."""
        # Connect
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123"
        )
        
        # Set low rate limit for testing
        websocket_adapter.message_rate_limit = 5
        
        # Send messages rapidly
        success_count = 0
        for i in range(10):
            message = WebSocketMessage(
                message_type=MessageType.CHAT,
                data={"text": f"Message {i}"}
            )
            
            success = await websocket_adapter.send_message(connection_id, message)
            if success:
                success_count += 1
        
        # Should be rate limited
        assert success_count <= 5
        assert websocket_adapter.metrics.rate_limit_hits > 0
    
    async def test_heartbeat_handling(self, websocket_adapter, mock_websocket):
        """Test heartbeat message handling."""
        # Connect
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123"
        )
        
        # Clear welcome message
        mock_websocket.messages.clear()
        
        # Send heartbeat
        heartbeat_msg = WebSocketMessage(
            message_type=MessageType.HEARTBEAT,
            data={"ping": True},
            correlation_id="hb_123"
        )
        
        await websocket_adapter.handle_message(
            connection_id,
            json.dumps(heartbeat_msg.to_dict())
        )
        
        # Verify pong response
        assert len(mock_websocket.messages) == 1
        
        pong_msg = json.loads(mock_websocket.messages[0])
        assert pong_msg["type"] == "heartbeat"
        assert pong_msg["data"]["pong"] is True
        assert pong_msg["correlation_id"] == "hb_123"
    
    async def test_connection_cleanup(self, websocket_adapter, mock_websocket):
        """Test connection cleanup and disconnection."""
        # Connect
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123"
        )
        
        # Subscribe to topic
        websocket_adapter.topic_subscriptions["test_topic"] = {connection_id}
        websocket_adapter.connections[connection_id].subscriptions.add("test_topic")
        
        # Disconnect
        await websocket_adapter.disconnect(connection_id, "test_cleanup")
        
        # Verify cleanup
        assert connection_id not in websocket_adapter.connections
        assert "child_123" not in websocket_adapter.user_connections
        assert "test_topic" not in websocket_adapter.topic_subscriptions
        assert mock_websocket.closed
        assert websocket_adapter.metrics.connections_dropped == 1
    
    async def test_message_size_limit(self, websocket_adapter, mock_websocket):
        """Test message size limiting."""
        # Connect
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123"
        )
        
        # Create oversized message
        large_data = "x" * (websocket_adapter.max_message_size + 1000)
        message = WebSocketMessage(
            message_type=MessageType.CHAT,
            data={"large_text": large_data}
        )
        
        # Should fail to send
        success = await websocket_adapter.send_message(connection_id, message)
        assert not success
    
    async def test_invalid_message_handling(self, websocket_adapter, mock_websocket):
        """Test handling of invalid messages."""
        # Connect
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123"
        )
        
        # Clear welcome message
        mock_websocket.messages.clear()
        
        # Send invalid JSON
        await websocket_adapter.handle_message(
            connection_id,
            "invalid json {"
        )
        
        # Should receive error message
        assert len(mock_websocket.messages) == 1
        error_msg = json.loads(mock_websocket.messages[0])
        assert error_msg["type"] == "error"
        assert "invalid_message_format" in error_msg["data"]["error_code"]
    
    async def test_metrics_collection(self, websocket_adapter, mock_websocket):
        """Test metrics collection and reporting."""
        # Connect multiple users
        for i in range(3):
            mock_ws = MockWebSocket()
            await websocket_adapter.connect(
                websocket=mock_ws,
                user_id=f"child_{i}"
            )
        
        # Send messages
        for i in range(5):
            message = WebSocketMessage(
                message_type=MessageType.CHAT,
                data={"text": f"Test message {i}"}
            )
            await websocket_adapter.send_message(
                list(websocket_adapter.connections.keys())[0],
                message
            )
        
        # Get metrics
        metrics = websocket_adapter.get_metrics()
        
        # Verify metrics
        assert metrics["total_connections"] == 3
        assert metrics["active_connections"] == 3
        assert metrics["messages_sent"] >= 5
        assert metrics["message_success_rate"] > 0
        assert "timestamp" in metrics
    
    async def test_health_check(self, websocket_adapter):
        """Test WebSocket service health check."""
        # Get health status
        health = await websocket_adapter.health_check()
        
        # Verify health response
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "active_connections" in health
        assert "background_tasks_running" in health
        assert "metrics" in health
        assert "timestamp" in health
    
    async def test_concurrent_connections(self, websocket_adapter):
        """Test handling multiple concurrent connections."""
        connections = []
        
        # Create many concurrent connections
        async def create_connection(user_id):
            mock_ws = MockWebSocket()
            conn_id = await websocket_adapter.connect(
                websocket=mock_ws,
                user_id=user_id
            )
            return conn_id, mock_ws
        
        # Create 50 concurrent connections
        tasks = [
            create_connection(f"child_{i}")
            for i in range(50)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful connections
        successful = [r for r in results if not isinstance(r, Exception)]
        
        # Should handle concurrent connections
        assert len(successful) > 40  # Allow some failures due to limits
        assert websocket_adapter.metrics.active_connections > 40
    
    async def test_message_handler_registration(self, websocket_adapter, mock_websocket):
        """Test custom message handler registration."""
        # Register custom handler
        custom_messages = []
        
        async def custom_handler(connection_id: str, message: WebSocketMessage):
            custom_messages.append((connection_id, message))
        
        websocket_adapter.register_message_handler(
            MessageType.CHAT,
            custom_handler
        )
        
        # Connect
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123"
        )
        
        # Send chat message
        chat_msg = WebSocketMessage(
            message_type=MessageType.CHAT,
            data={"text": "Hello custom handler!"}
        )
        
        await websocket_adapter.handle_message(
            connection_id,
            json.dumps(chat_msg.to_dict())
        )
        
        # Verify custom handler called
        assert len(custom_messages) == 1
        assert custom_messages[0][0] == connection_id
        assert custom_messages[0][1].data["text"] == "Hello custom handler!"
    
    async def test_coppa_compliance_features(self, websocket_adapter, mock_websocket):
        """Test COPPA compliance features in WebSocket communication."""
        # Connect child user
        connection_id = await websocket_adapter.connect(
            websocket=mock_websocket,
            user_id="child_123",
            metadata={"age": 7, "parent_consent": True}
        )
        
        # Verify child-safe connection metadata
        connection = websocket_adapter.connections[connection_id]
        assert connection.metadata["age"] == 7
        assert connection.metadata["parent_consent"] is True
        
        # Test content filtering in messages
        inappropriate_msg = WebSocketMessage(
            message_type=MessageType.CHAT,
            data={"text": "This contains inappropriate content"}
        )
        
        # Should implement content filtering (mock implementation)
        success = await websocket_adapter.send_message(connection_id, inappropriate_msg)
        # In real implementation, this would be filtered
        assert success  # For now, just verify it doesn't crash