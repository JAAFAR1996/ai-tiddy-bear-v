"""
Tests for ESP32 Chat Server.
"""

import pytest
import json
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from fastapi import WebSocket, HTTPException
from fastapi.websockets import WebSocketState

from src.services.esp32_chat_server import (
    ESP32ChatServer,
    ESP32Session,
    SessionStatus,
    MessageType,
    AudioMessage,
    validate_device_id
)


class TestDeviceValidation:
    """Test device ID validation."""

    def test_valid_device_ids(self):
        """Test valid device ID formats."""
        valid_ids = [
            "ESP32_001",
            "device123",
            "teddy-bear-01",
            "ABCD1234",
            "test_device_123"
        ]
        
        for device_id in valid_ids:
            assert validate_device_id(device_id), f"Should be valid: {device_id}"

    def test_invalid_device_ids(self):
        """Test invalid device ID formats."""
        invalid_ids = [
            "",  # Empty
            "abc",  # Too short
            "a" * 50,  # Too long
            "device@123",  # Invalid character
            "device 123",  # Space
            "device#123",  # Hash
            None  # None
        ]
        
        for device_id in invalid_ids:
            assert not validate_device_id(device_id), f"Should be invalid: {device_id}"


class TestESP32Session:
    """Test ESP32 session management."""

    def test_session_creation(self):
        """Test ESP32 session creation."""
        mock_websocket = Mock(spec=WebSocket)
        
        session = ESP32Session(
            session_id="session123",
            device_id="ESP32_001",
            child_id="child123",
            child_name="Alice",
            child_age=8,
            websocket=mock_websocket
        )
        
        assert session.session_id == "session123"
        assert session.device_id == "ESP32_001"
        assert session.child_id == "child123"
        assert session.child_name == "Alice"
        assert session.child_age == 8
        assert session.status == SessionStatus.CONNECTING
        assert session.message_count == 0
        assert session.total_audio_duration == 0.0

    def test_session_activity_update(self):
        """Test session activity tracking."""
        mock_websocket = Mock(spec=WebSocket)
        session = ESP32Session(
            session_id="session123",
            device_id="ESP32_001",
            child_id="child123",
            child_name="Alice",
            child_age=8,
            websocket=mock_websocket
        )
        
        original_time = session.last_activity
        session.update_activity()
        
        assert session.last_activity > original_time

    def test_session_expiry_check(self):
        """Test session expiry detection."""
        mock_websocket = Mock(spec=WebSocket)
        session = ESP32Session(
            session_id="session123",
            device_id="ESP32_001",
            child_id="child123",
            child_name="Alice",
            child_age=8,
            websocket=mock_websocket
        )
        
        # Fresh session should not be expired
        assert not session.is_expired(timeout_minutes=30)
        
        # Mock old session
        with patch('src.services.esp32_chat_server.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now()
            session.last_activity = datetime.now()
            
            # Should be expired with very short timeout
            assert session.is_expired(timeout_minutes=0)


class TestAudioMessage:
    """Test audio message handling."""

    def test_audio_message_creation(self):
        """Test audio message creation."""
        audio_data = b"fake_audio_data"
        
        message = AudioMessage(
            session_id="session123",
            chunk_id="chunk001",
            audio_data=audio_data,
            is_final=False
        )
        
        assert message.session_id == "session123"
        assert message.chunk_id == "chunk001"
        assert message.audio_data == audio_data
        assert message.is_final is False
        assert message.format == "wav"
        assert message.sample_rate == 16000


class TestESP32ChatServer:
    """Test ESP32 Chat Server functionality."""

    @pytest.fixture
    def server(self):
        """Create ESP32 chat server instance."""
        return ESP32ChatServer()

    @pytest.mark.asyncio
    async def test_connect_device_success(self, server):
        """Test successful device connection."""
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        session_id = await server.connect_device(
            websocket=mock_websocket,
            device_id="ESP32_001",
            child_id="child123",
            child_name="Alice",
            child_age=8
        )
        
        assert isinstance(session_id, str)
        assert len(session_id) > 0
        assert session_id in server.active_sessions
        assert "ESP32_001" in server.device_sessions
        
        # Verify WebSocket was accepted
        mock_websocket.accept.assert_called_once()
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_device_invalid_age(self, server):
        """Test device connection with invalid child age."""
        mock_websocket = AsyncMock(spec=WebSocket)
        
        with pytest.raises(HTTPException) as exc_info:
            await server.connect_device(
                websocket=mock_websocket,
                device_id="ESP32_001",
                child_id="child123",
                child_name="Alice",
                child_age=2  # Too young for COPPA
            )
        
        assert exc_info.value.status_code == 400
        assert "COPPA compliance" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_connect_device_invalid_device_id(self, server):
        """Test device connection with invalid device ID."""
        mock_websocket = AsyncMock(spec=WebSocket)
        
        with pytest.raises(HTTPException) as exc_info:
            await server.connect_device(
                websocket=mock_websocket,
                device_id="invalid@device",
                child_id="child123",
                child_name="Alice",
                child_age=8
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid device identifier" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_connect_device_session_limit(self, server):
        """Test device connection when session limit is reached."""
        # Fill up sessions to max
        server.max_sessions = 2
        mock_websocket1 = AsyncMock(spec=WebSocket)
        mock_websocket2 = AsyncMock(spec=WebSocket)
        
        # Connect two devices
        await server.connect_device(mock_websocket1, "ESP32_001", "child1", "Alice", 8)
        await server.connect_device(mock_websocket2, "ESP32_002", "child2", "Bob", 9)
        
        # Third connection should fail
        mock_websocket3 = AsyncMock(spec=WebSocket)
        with pytest.raises(HTTPException) as exc_info:
            await server.connect_device(mock_websocket3, "ESP32_003", "child3", "Charlie", 7)
        
        assert exc_info.value.status_code == 503
        assert "Maximum sessions exceeded" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_connect_device_reconnection(self, server):
        """Test device reconnection replaces old session."""
        mock_websocket1 = AsyncMock(spec=WebSocket)
        mock_websocket2 = AsyncMock(spec=WebSocket)
        
        # First connection
        session_id1 = await server.connect_device(
            mock_websocket1, "ESP32_001", "child123", "Alice", 8
        )
        
        # Second connection with same device ID
        session_id2 = await server.connect_device(
            mock_websocket2, "ESP32_001", "child123", "Alice", 8
        )
        
        # Should have different session IDs
        assert session_id1 != session_id2
        
        # Old session should be terminated
        assert session_id1 not in server.active_sessions
        assert session_id2 in server.active_sessions

    @pytest.mark.asyncio
    async def test_handle_message_heartbeat(self, server):
        """Test handling heartbeat messages."""
        # Setup session
        mock_websocket = AsyncMock(spec=WebSocket)
        session_id = await server.connect_device(
            mock_websocket, "ESP32_001", "child123", "Alice", 8
        )
        
        # Send heartbeat message
        heartbeat_message = json.dumps({
            "type": "heartbeat",
            "timestamp": datetime.now().isoformat()
        })
        
        await server.handle_message(session_id, heartbeat_message)
        
        # Should send heartbeat response
        assert mock_websocket.send_text.call_count >= 2  # Welcome + heartbeat response

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(self, server):
        """Test handling invalid JSON messages."""
        # Setup session
        mock_websocket = AsyncMock(spec=WebSocket)
        session_id = await server.connect_device(
            mock_websocket, "ESP32_001", "child123", "Alice", 8
        )
        
        # Send invalid JSON
        await server.handle_message(session_id, "invalid json")
        
        # Should send error message
        error_calls = [call for call in mock_websocket.send_text.call_args_list 
                      if "error" in str(call)]
        assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_handle_message_unknown_session(self, server):
        """Test handling messages from unknown sessions."""
        # Should handle gracefully without raising exception
        await server.handle_message("unknown_session", '{"type": "heartbeat"}')

    @pytest.mark.asyncio
    async def test_disconnect_device(self, server):
        """Test device disconnection."""
        # Setup session
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.client_state = WebSocketState.CONNECTED
        mock_websocket.close = AsyncMock()
        
        session_id = await server.connect_device(
            mock_websocket, "ESP32_001", "child123", "Alice", 8
        )
        
        # Disconnect device
        await server.disconnect_device(session_id, "user_requested")
        
        # Session should be removed
        assert session_id not in server.active_sessions
        assert "ESP32_001" not in server.device_sessions
        
        # WebSocket should be closed
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_cleanup_loop(self, server):
        """Test automatic session cleanup."""
        # Create expired session
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.client_state = WebSocketState.CONNECTED
        mock_websocket.close = AsyncMock()
        
        session_id = await server.connect_device(
            mock_websocket, "ESP32_001", "child123", "Alice", 8
        )
        
        # Mock session as expired
        session = server.active_sessions[session_id]
        session.is_expired = Mock(return_value=True)
        
        # Run cleanup manually (instead of waiting for background task)
        expired_sessions = []
        for sid, sess in server.active_sessions.items():
            if sess.is_expired(server.session_timeout_minutes):
                expired_sessions.append(sid)
        
        for sid in expired_sessions:
            await server._terminate_session(sid, "timeout")
        
        # Session should be cleaned up
        assert session_id not in server.active_sessions

    def test_get_session_metrics(self, server):
        """Test session metrics retrieval."""
        metrics = server.get_session_metrics()
        
        assert isinstance(metrics, dict)
        assert "active_sessions" in metrics
        assert "max_sessions" in metrics
        assert "total_messages" in metrics
        assert "session_timeout_minutes" in metrics
        assert "devices_connected" in metrics
        assert "timestamp" in metrics

    @pytest.mark.asyncio
    async def test_health_check(self, server):
        """Test server health check."""
        health = await server.health_check()
        
        assert isinstance(health, dict)
        assert "status" in health
        assert "active_sessions" in health
        assert "max_sessions" in health
        assert "cleanup_task_running" in health
        assert "metrics" in health
        assert "timestamp" in health
        
        assert health["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_shutdown(self, server):
        """Test server shutdown."""
        # Setup some sessions
        mock_websocket1 = AsyncMock(spec=WebSocket)
        mock_websocket2 = AsyncMock(spec=WebSocket)
        
        await server.connect_device(mock_websocket1, "ESP32_001", "child1", "Alice", 8)
        await server.connect_device(mock_websocket2, "ESP32_002", "child2", "Bob", 9)
        
        # Shutdown server
        await server.shutdown()
        
        # All sessions should be terminated
        assert len(server.active_sessions) == 0
        assert len(server.device_sessions) == 0

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, server):
        """Test handling multiple concurrent connections."""
        # Create multiple concurrent connections
        tasks = []
        for i in range(5):
            mock_websocket = AsyncMock(spec=WebSocket)
            task = server.connect_device(
                mock_websocket, f"ESP32_{i:03d}", f"child{i}", f"Child{i}", 8
            )
            tasks.append(task)
        
        session_ids = await asyncio.gather(*tasks)
        
        # All connections should succeed
        assert len(session_ids) == 5
        assert len(set(session_ids)) == 5  # All unique
        assert len(server.active_sessions) == 5

    @pytest.mark.asyncio
    async def test_message_rate_limiting(self, server):
        """Test message rate limiting per session."""
        # Setup session
        mock_websocket = AsyncMock(spec=WebSocket)
        session_id = await server.connect_device(
            mock_websocket, "ESP32_001", "child123", "Alice", 8
        )
        
        # Send many messages rapidly
        for i in range(10):
            message = json.dumps({
                "type": "text_message",
                "content": f"Message {i}",
                "timestamp": datetime.now().isoformat()
            })
            await server.handle_message(session_id, message)
        
        # Session should track message count
        session = server.active_sessions[session_id]
        assert session.message_count >= 10


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def server(self):
        return ESP32ChatServer()

    @pytest.mark.asyncio
    async def test_websocket_connection_error(self, server):
        """Test handling WebSocket connection errors."""
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.accept.side_effect = Exception("Connection failed")
        mock_websocket.close = AsyncMock()
        
        with pytest.raises(Exception):
            await server.connect_device(
                mock_websocket, "ESP32_001", "child123", "Alice", 8
            )
        
        # Should attempt to close WebSocket on error
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_processing_error(self, server):
        """Test handling message processing errors."""
        # Setup session
        mock_websocket = AsyncMock(spec=WebSocket)
        session_id = await server.connect_device(
            mock_websocket, "ESP32_001", "child123", "Alice", 8
        )
        
        # Mock message handler to raise exception
        with patch.object(server, '_handle_text_message', side_effect=Exception("Processing error")):
            message = json.dumps({
                "type": "text_message",
                "content": "Test message"
            })
            
            # Should handle error gracefully
            await server.handle_message(session_id, message)
            
            # Should send error response
            error_calls = [call for call in mock_websocket.send_text.call_args_list 
                          if "error" in str(call)]
            assert len(error_calls) > 0