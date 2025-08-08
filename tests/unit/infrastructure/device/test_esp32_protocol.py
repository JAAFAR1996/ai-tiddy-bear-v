"""
ESP32 Protocol Communication Tests
==================================
Tests for ESP32 device communication protocol and command handling.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.infrastructure.device.esp32_protocol import (
    ESP32Protocol,
    ESP32Response,
    CommandType,
    ESP32ProtocolError
)
from src.shared.dto.esp32_request import ESP32Request
from src.shared.dto.esp32.esp32_data import ESP32Data
from src.core.exceptions import ServiceUnavailableError, ValidationError


@pytest.fixture
def esp32_protocol():
    """Create ESP32 protocol instance for testing."""
    return ESP32Protocol(device_ip="192.168.1.100", port=80)


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    websocket = AsyncMock(spec=True)
    websocket.send = AsyncMock(spec=True)
    websocket.recv = AsyncMock(spec=True)
    websocket.close = AsyncMock(spec=True)
    return websocket


@pytest.mark.asyncio
class TestESP32Protocol:
    """Test ESP32 communication protocol."""
    
    async def test_protocol_initialization(self, esp32_protocol):
        """Test protocol initialization with device parameters."""
        assert esp32_protocol.device_ip == "192.168.1.100"
        assert esp32_protocol.port == 80
        assert esp32_protocol.connected is False
        assert esp32_protocol.message_id == 0
        assert esp32_protocol.timeout == 5.0
    
    def test_handshake_success(self, esp32_protocol):
        """Test successful handshake with ESP32 device."""
        device_id = "teddy_bear_001"
        
        # Perform handshake
        result = esp32_protocol.handshake(device_id)
        
        # Verify handshake response
        assert result["status"] == "ok"
        assert result["device_id"] == device_id
        assert result["protocol_version"] == "1.0"
        assert "timestamp" in result
        assert esp32_protocol.connected is True
    
    def test_handshake_validation_error(self, esp32_protocol):
        """Test handshake with invalid device ID."""
        with pytest.raises(ValidationError):
            esp32_protocol.handshake("")
        
        with pytest.raises(ValidationError):
            esp32_protocol.handshake(None)
    
    @patch('websockets.connect')
    async def test_websocket_connection_success(self, mock_connect, esp32_protocol, mock_websocket):
        """Test successful WebSocket connection to ESP32."""
        mock_connect.return_value = mock_websocket
        
        # Connect to device
        success = await esp32_protocol.connect("192.168.1.100")
        
        # Verify connection
        assert success is True
        assert esp32_protocol.connected is True
        assert esp32_protocol.websocket == mock_websocket
        mock_connect.assert_called_once_with("ws://192.168.1.100:80/ws")
    
    @patch('websockets.connect')
    async def test_websocket_connection_failure(self, mock_connect, esp32_protocol):
        """Test WebSocket connection failure."""
        mock_connect.side_effect = Exception("Connection refused")
        
        # Should raise ServiceUnavailableError
        with pytest.raises(ServiceUnavailableError):
            await esp32_protocol.connect("192.168.1.100")
        
        assert esp32_protocol.connected is False
    
    async def test_websocket_connection_without_websockets_library(self, esp32_protocol):
        """Test connection when websockets library is not available."""
        with patch.dict('sys.modules', {'websockets': None}):
            success = await esp32_protocol.connect("192.168.1.100")
            assert success is False
    
    async def test_send_command_with_websocket(self, esp32_protocol, mock_websocket):
        """Test sending command through WebSocket."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock response
        response_data = {
            "status": "ok",
            "data": {"sensor_value": 25.5, "unit": "celsius"},
            "timestamp": datetime.now().isoformat()
        }
        mock_websocket.recv.return_value = json.dumps(response_data)
        
        # Send command
        response = await esp32_protocol.send_command(
            "sensor_read",
            {"sensor_type": "temperature"}
        )
        
        # Verify command sent
        mock_websocket.send.assert_called_once()
        sent_data = json.loads(mock_websocket.send.call_args[0][0])
        assert sent_data["type"] == "sensor_read"
        assert sent_data["params"]["sensor_type"] == "temperature"
        assert sent_data["id"] == 1
        
        # Verify response
        assert response.status == "ok"
        assert response.data["sensor_value"] == 25.5
        assert response.error is None
    
    async def test_send_command_without_websocket(self, esp32_protocol):
        """Test sending command without WebSocket (simulation mode)."""
        esp32_protocol.connected = True
        esp32_protocol.websocket = None
        
        # Send command
        response = await esp32_protocol.send_command(
            "led_control",
            {"led_id": "status", "color": "blue"}
        )
        
        # Should return simulated response
        assert response.status == "ok"
        assert response.data["command"] == "led_control"
        assert response.data["params"]["color"] == "blue"
    
    async def test_send_command_timeout(self, esp32_protocol, mock_websocket):
        """Test command timeout handling."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock timeout
        mock_websocket.recv.side_effect = asyncio.TimeoutError()
        
        # Send command
        response = await esp32_protocol.send_command("status_check")
        
        # Should return None on timeout
        assert response is None
    
    async def test_send_command_not_connected(self, esp32_protocol):
        """Test sending command when not connected."""
        esp32_protocol.connected = False
        
        # Should raise protocol error
        with pytest.raises(ESP32ProtocolError):
            await esp32_protocol.send_command("test_command")
    
    async def test_get_sensor_data(self, esp32_protocol, mock_websocket):
        """Test getting sensor data from ESP32."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock sensor response
        sensor_response = {
            "status": "ok",
            "data": {
                "temperature": 24.5,
                "humidity": 65.2,
                "light_level": 450,
                "motion_detected": False
            }
        }
        mock_websocket.recv.return_value = json.dumps(sensor_response)
        
        # Get sensor data
        data = await esp32_protocol.get_sensor_data("all")
        
        # Verify sensor data
        assert data["temperature"] == 24.5
        assert data["humidity"] == 65.2
        assert data["light_level"] == 450
        assert data["motion_detected"] is False
    
    async def test_control_actuator(self, esp32_protocol, mock_websocket):
        """Test controlling ESP32 actuators."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock success response
        mock_websocket.recv.return_value = json.dumps({"status": "ok", "data": {}})
        
        # Control actuator
        success = await esp32_protocol.control_actuator(
            "servo_arm",
            "move",
            {"angle": 90, "speed": 50}
        )
        
        # Verify command sent
        assert success is True
        mock_websocket.send.assert_called_once()
        
        sent_data = json.loads(mock_websocket.send.call_args[0][0])
        assert sent_data["type"] == "actuator_control"
        assert sent_data["params"]["actuator"] == "servo_arm"
        assert sent_data["params"]["action"] == "move"
        assert sent_data["params"]["params"]["angle"] == 90
    
    async def test_control_led(self, esp32_protocol, mock_websocket):
        """Test LED control functionality."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock success response
        mock_websocket.recv.return_value = json.dumps({"status": "ok", "data": {}})
        
        # Control LED
        success = await esp32_protocol.control_led("eyes", "green", 75)
        
        # Verify LED control
        assert success is True
        
        sent_data = json.loads(mock_websocket.send.call_args[0][0])
        assert sent_data["type"] == "led_control"
        assert sent_data["params"]["led_id"] == "eyes"
        assert sent_data["params"]["color"] == "green"
        assert sent_data["params"]["brightness"] == 75
    
    async def test_control_motor(self, esp32_protocol, mock_websocket):
        """Test motor control functionality."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock success response
        mock_websocket.recv.return_value = json.dumps({"status": "ok", "data": {}})
        
        # Control motor
        success = await esp32_protocol.control_motor("head_turn", "left", 30)
        
        # Verify motor control
        assert success is True
        
        sent_data = json.loads(mock_websocket.send.call_args[0][0])
        assert sent_data["type"] == "motor_control"
        assert sent_data["params"]["motor_id"] == "head_turn"
        assert sent_data["params"]["direction"] == "left"
        assert sent_data["params"]["speed"] == 30
    
    async def test_play_audio(self, esp32_protocol, mock_websocket):
        """Test audio playback functionality."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock success response
        mock_websocket.recv.return_value = json.dumps({"status": "ok", "data": {}})
        
        # Play audio
        success = await esp32_protocol.play_audio("hello_child.wav", 80)
        
        # Verify audio command
        assert success is True
        
        sent_data = json.loads(mock_websocket.send.call_args[0][0])
        assert sent_data["type"] == "audio_play"
        assert sent_data["params"]["file"] == "hello_child.wav"
        assert sent_data["params"]["volume"] == 80
    
    async def test_get_status(self, esp32_protocol, mock_websocket):
        """Test getting device status."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock status response
        status_response = {
            "status": "ok",
            "data": {
                "uptime": 3600,
                "memory_free": 45000,
                "wifi_strength": -45,
                "battery_level": 85,
                "temperature": 42.3
            }
        }
        mock_websocket.recv.return_value = json.dumps(status_response)
        
        # Get status
        status = await esp32_protocol.get_status()
        
        # Verify status data
        assert status["uptime"] == 3600
        assert status["memory_free"] == 45000
        assert status["wifi_strength"] == -45
        assert status["battery_level"] == 85
        assert status["temperature"] == 42.3
    
    def test_parse_message_success(self, esp32_protocol):
        """Test successful message parsing."""
        raw_message = json.dumps({
            "command": "sensor_read",
            "params": {"sensor_type": "temperature"},
            "device_id": "teddy_001",
            "timestamp": "2024-01-01T12:00:00"
        }).encode('utf-8')
        
        # Parse message
        request = esp32_protocol.parse_message(raw_message)
        
        # Verify parsed request
        assert isinstance(request, ESP32Request)
        assert request.command == "sensor_read"
        assert request.params["sensor_type"] == "temperature"
        assert request.device_id == "teddy_001"
        assert request.timestamp == "2024-01-01T12:00:00"
    
    def test_parse_message_invalid_json(self, esp32_protocol):
        """Test parsing invalid JSON message."""
        raw_message = b"invalid json {"
        
        # Should raise protocol error
        with pytest.raises(ESP32ProtocolError):
            esp32_protocol.parse_message(raw_message)
    
    def test_build_response_success(self, esp32_protocol):
        """Test successful response building."""
        # Create mock ESP32Data
        data = type('ESP32Data', (), {
            'sensor_value': 25.5,
            'status': 'active',
            'timestamp': datetime.now().isoformat()
        })()
        
        # Build response
        response_bytes = esp32_protocol.build_response(data)
        
        # Verify response
        response_data = json.loads(response_bytes.decode('utf-8'))
        assert response_data["status"] == "ok"
        assert response_data["data"]["sensor_value"] == 25.5
        assert response_data["data"]["status"] == "active"
        assert "timestamp" in response_data
    
    def test_build_response_with_dict(self, esp32_protocol):
        """Test building response with dictionary data."""
        data = {
            "temperature": 23.5,
            "humidity": 60.0,
            "status": "ok"
        }
        
        # Build response
        response_bytes = esp32_protocol.build_response(data)
        
        # Verify response
        response_data = json.loads(response_bytes.decode('utf-8'))
        assert response_data["status"] == "ok"
        assert response_data["data"]["temperature"] == 23.5
        assert response_data["data"]["humidity"] == 60.0
    
    async def test_disconnect(self, esp32_protocol, mock_websocket):
        """Test disconnection from ESP32."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Disconnect
        await esp32_protocol.disconnect()
        
        # Verify disconnection
        mock_websocket.close.assert_called_once()
        assert esp32_protocol.websocket is None
        assert esp32_protocol.connected is False
    
    async def test_disconnect_with_error(self, esp32_protocol, mock_websocket):
        """Test disconnection with WebSocket error."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock close error
        mock_websocket.close.side_effect = Exception("Close error")
        
        # Should handle error gracefully
        await esp32_protocol.disconnect()
        
        assert esp32_protocol.websocket is None
        assert esp32_protocol.connected is False
    
    async def test_context_manager_usage(self, esp32_protocol, mock_websocket):
        """Test using ESP32Protocol as async context manager."""
        with patch.object(esp32_protocol, 'connect', return_value=True) as mock_connect:
            with patch.object(esp32_protocol, 'disconnect') as mock_disconnect:
                
                async with esp32_protocol as protocol:
                    assert protocol == esp32_protocol
                    mock_connect.assert_called_once()
                
                mock_disconnect.assert_called_once()
    
    async def test_command_error_handling(self, esp32_protocol, mock_websocket):
        """Test error handling in command execution."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock error response
        error_response = {
            "status": "error",
            "data": {},
            "error": "Sensor not found"
        }
        mock_websocket.recv.return_value = json.dumps(error_response)
        
        # Send command
        response = await esp32_protocol.send_command("invalid_sensor")
        
        # Verify error response
        assert response.status == "error"
        assert response.error == "Sensor not found"
    
    async def test_concurrent_commands(self, esp32_protocol, mock_websocket):
        """Test handling concurrent commands."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock responses
        responses = [
            {"status": "ok", "data": {"sensor": "temp", "value": 25}},
            {"status": "ok", "data": {"sensor": "humidity", "value": 60}},
            {"status": "ok", "data": {"sensor": "light", "value": 400}}
        ]
        
        mock_websocket.recv.side_effect = [json.dumps(r) for r in responses]
        
        # Send concurrent commands
        tasks = [
            esp32_protocol.send_command("sensor_read", {"type": "temperature"}),
            esp32_protocol.send_command("sensor_read", {"type": "humidity"}),
            esp32_protocol.send_command("sensor_read", {"type": "light"})
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all commands completed
        assert len(results) == 3
        assert all(r.status == "ok" for r in results)
        
        # Verify message IDs incremented
        assert esp32_protocol.message_id == 3
    
    async def test_coppa_compliance_commands(self, esp32_protocol, mock_websocket):
        """Test COPPA-compliant commands for child safety."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock success response
        mock_websocket.recv.return_value = json.dumps({"status": "ok", "data": {}})
        
        # Test child-safe LED colors
        success = await esp32_protocol.control_led("eyes", "soft_blue", 50)
        assert success is True
        
        # Test child-safe audio volume (not too loud)
        success = await esp32_protocol.play_audio("lullaby.wav", 40)
        assert success is True
        
        # Test gentle motor movements
        success = await esp32_protocol.control_motor("head_nod", "gentle", 20)
        assert success is True
        
        # Verify all commands sent with appropriate parameters
        assert mock_websocket.send.call_count == 3
    
    async def test_device_safety_monitoring(self, esp32_protocol, mock_websocket):
        """Test device safety monitoring features."""
        esp32_protocol.websocket = mock_websocket
        esp32_protocol.connected = True
        
        # Mock status with safety concerns
        safety_status = {
            "status": "ok",
            "data": {
                "temperature": 65.0,  # High temperature
                "battery_level": 15,  # Low battery
                "memory_free": 1000,  # Low memory
                "error_count": 5      # Multiple errors
            }
        }
        mock_websocket.recv.return_value = json.dumps(safety_status)
        
        # Get status
        status = await esp32_protocol.get_status()
        
        # Verify safety monitoring data
        assert status["temperature"] == 65.0
        assert status["battery_level"] == 15
        assert status["memory_free"] == 1000
        assert status["error_count"] == 5
        
        # In real implementation, would trigger safety alerts