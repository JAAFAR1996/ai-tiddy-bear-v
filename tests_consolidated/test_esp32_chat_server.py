"""
ESP32 Chat Server - Production Tests
===================================
Comprehensive test suite for ESP32 WebSocket chat functionality.
"""

import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketState, WebSocket
from unittest.mock import AsyncMock, MagicMock

from src.services.esp32_chat_server import (
    ESP32ChatServer,
    ESP32Session,
    SessionStatus,
    MessageType,
)
from src.main import app


class TestESP32ChatServer:
    """Test ESP32 Chat Server core functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chat_server = ESP32ChatServer()

    def test_device_id_validation(self):
        """Test device ID validation."""
        from src.services.esp32_chat_server import validate_device_id

        # Valid device IDs
        assert validate_device_id("ESP32_001")
        assert validate_device_id("device12345")
        assert validate_device_id("ABC123DEF456")

        # Invalid device IDs
        assert not validate_device_id("")
        assert not validate_device_id("short")  # Too short
        assert not validate_device_id("a" * 50)  # Too long
        assert not validate_device_id("device@123")  # Special chars
        assert not validate_device_id("device 123")  # Spaces

    @pytest.mark.asyncio
    async def test_session_creation(self):
        """Test ESP32 session creation."""
        # Mock WebSocket
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.accept = AsyncMock(spec=WebSocket.accept)
        mock_ws.send_text = AsyncMock(spec=WebSocket.send_text)
        mock_ws.client_state = WebSocketState.CONNECTED

        # Test valid session creation
        session_id = await self.chat_server.connect_device(
            websocket=mock_ws,
            device_id="TEST_ESP32_001",
            child_id="child_123",
            child_name="Alice",
            child_age=8,
        )

        assert session_id is not None
        assert session_id in self.chat_server.active_sessions

        session = self.chat_server.active_sessions[session_id]
        assert session.device_id == "TEST_ESP32_001"
        assert session.child_name == "Alice"
        assert session.child_age == 8
        assert session.status == SessionStatus.ACTIVE

        # Verify WebSocket was accepted
        mock_ws.accept.assert_called_once()
        mock_ws.send_text.assert_called()

    @pytest.mark.asyncio
    async def test_coppa_age_validation(self):
        """Test COPPA age validation."""
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.accept = AsyncMock(spec=WebSocket.accept)
        mock_ws.close = AsyncMock(spec=WebSocket.close)

        # Test invalid ages (below 3)
        with pytest.raises(Exception):
            await self.chat_server.connect_device(
                websocket=mock_ws,
                device_id="TEST_ESP32_002",
                child_id="child_123",
                child_name="Baby",
                child_age=2,
            )

        # Test invalid ages (above 13)
        with pytest.raises(Exception):
            await self.chat_server.connect_device(
                websocket=mock_ws,
                device_id="TEST_ESP32_003",
                child_id="child_123",
                child_name="Teen",
                child_age=14,
            )

    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test session cleanup and termination."""
        # Create mock session
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.accept = AsyncMock(spec=True)
        mock_ws.send_text = AsyncMock(spec=True)
        mock_ws.close = AsyncMock(spec=True)
        mock_ws.client_state = WebSocketState.CONNECTED

        session_id = await self.chat_server.connect_device(
            websocket=mock_ws,
            device_id="TEST_ESP32_004",
            child_id="child_123",
            child_name="Bob",
            child_age=7,
        )

        # Verify session exists
        assert session_id in self.chat_server.active_sessions

        # Disconnect device
        await self.chat_server.disconnect_device(session_id, "test_cleanup")

        # Verify session was cleaned up
        assert session_id not in self.chat_server.active_sessions
        mock_ws.close.assert_called()

    @pytest.mark.asyncio
    async def test_message_handling(self):
        """Test WebSocket message handling."""
        # Create session
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.accept = AsyncMock(spec=True)
        mock_ws.send_text = AsyncMock(spec=True)
        mock_ws.client_state = WebSocketState.CONNECTED

        session_id = await self.chat_server.connect_device(
            websocket=mock_ws,
            device_id="TEST_ESP32_005",
            child_id="child_123",
            child_name="Charlie",
            child_age=9,
        )

        # Test heartbeat message
        heartbeat_msg = json.dumps(
            {"type": "heartbeat", "timestamp": "2024-01-01T12:00:00Z"}
        )

        await self.chat_server.handle_message(session_id, heartbeat_msg)

        # Verify response was sent
        mock_ws.send_text.assert_called()

        # Check that session activity was updated
        session = self.chat_server.active_sessions[session_id]
        assert session.message_count > 0

    def test_session_metrics(self):
        """Test session metrics collection."""
        metrics = self.chat_server.get_session_metrics()

        assert "active_sessions" in metrics
        assert "max_sessions" in metrics
        assert "total_messages" in metrics
        assert "timestamp" in metrics
        assert isinstance(metrics["active_sessions"], int)

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint."""
        health = await self.chat_server.health_check()

        assert "status" in health
        assert "active_sessions" in health
        assert "timestamp" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]


class TestESP32Router:
    """Test ESP32 FastAPI router endpoints."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_health_endpoint(self):
        """Test ESP32 health endpoint."""
        response = self.client.get("/api/v1/esp32/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "active_sessions" in data

    def test_metrics_endpoint(self):
        """Test ESP32 metrics endpoint."""
        response = self.client.get("/api/v1/esp32/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "active_sessions" in data
        assert "max_sessions" in data

    def test_connection_validation(self):
        """Test ESP32 connection parameter validation."""
        # Test valid parameters
        response = self.client.post(
            "/api/v1/esp32/test-connection",
            params={"device_id": "ESP32_TEST_001", "child_age": 8},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "valid"

        # Test invalid device ID
        response = self.client.post(
            "/api/v1/esp32/test-connection",
            params={"device_id": "bad@id", "child_age": 8},
        )
        assert response.status_code == 400

        # Test invalid age
        response = self.client.post(
            "/api/v1/esp32/test-connection",
            params={"device_id": "ESP32_TEST_002", "child_age": 15},
        )
        assert response.status_code == 400


class TestESP32WebSocket:
    """Test ESP32 WebSocket integration."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_websocket_connection_parameters(self):
        """Test WebSocket connection with various parameters."""
        # Test with valid parameters - should establish connection
        with self.client.websocket_connect(
            "/api/v1/esp32/chat?device_id=ESP32_WS_001&child_id=child_123&child_name=TestChild&child_age=8"
        ) as websocket:
            # Should receive welcome message
            data = websocket.receive_json()
            assert data["type"] == "system"
            assert "connection_established" in str(data)

    def test_websocket_invalid_age(self):
        """Test WebSocket connection with invalid age."""
        # Should reject connection due to invalid age
        with pytest.raises(Exception):
            with self.client.websocket_connect(
                "/api/v1/esp32/chat?device_id=ESP32_WS_002&child_id=child_123&child_name=TestChild&child_age=2"
            ) as websocket:
                pass

    def test_websocket_heartbeat(self):
        """Test WebSocket heartbeat functionality."""
        with self.client.websocket_connect(
            "/api/v1/esp32/chat?device_id=ESP32_WS_003&child_id=child_123&child_name=TestChild&child_age=10"
        ) as websocket:
            # Receive welcome message
            welcome = websocket.receive_json()
            assert welcome["type"] == "system"

            # Send heartbeat
            websocket.send_json(
                {"type": "heartbeat", "timestamp": "2024-01-01T12:00:00Z"}
            )

            # Should receive heartbeat response
            response = websocket.receive_json()
            assert response["type"] == "system"
            assert response["data"]["type"] == "heartbeat_response"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
