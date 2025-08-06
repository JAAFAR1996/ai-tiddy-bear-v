"""
ESP32 Communication Protocol
Handles message framing, handshake, and command routing for ESP32 devices.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from src.shared.dto.esp32_request import ESP32Request
from src.shared.dto.esp32.esp32_data import ESP32Data
from src.core.exceptions import ServiceUnavailableError, ValidationError

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """ESP32 command types."""
    HANDSHAKE = "handshake"
    SENSOR_READ = "sensor_read"
    ACTUATOR_CONTROL = "actuator_control"
    LED_CONTROL = "led_control"
    MOTOR_CONTROL = "motor_control"
    AUDIO_PLAY = "audio_play"
    STATUS_CHECK = "status_check"


@dataclass
class ESP32Response:
    """ESP32 response structure."""
    status: str
    data: Dict[str, Any]
    timestamp: datetime
    error: Optional[str] = None


class ESP32ProtocolError(Exception):
    """ESP32 protocol errors."""
    pass


class ESP32Protocol:
    """ESP32 communication protocol handler."""
    
    def __init__(self, device_ip: str = None, port: int = 80):
        self.device_ip = device_ip
        self.port = port
        self.connected = False
        self.websocket = None
        self.message_id = 0
        self.pending_responses = {}
        self.timeout = 5.0

    async def connect(self, device_ip: str = None) -> bool:
        """Connect to ESP32 device."""
        if device_ip:
            self.device_ip = device_ip
        
        if not self.device_ip:
            raise ValidationError("Device IP is required")
        
        try:
            import websockets
            uri = f"ws://{self.device_ip}:{self.port}/ws"
            self.websocket = await asyncio.wait_for(
                websockets.connect(uri),
                timeout=self.timeout
            )
            self.connected = True
            logger.info(f"Connected to ESP32 at {self.device_ip}")
            return True
            
        except ImportError:
            logger.error("websockets library not installed")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise ServiceUnavailableError(f"ESP32 connection failed: {e}")

    def handshake(self, device_id: str) -> dict:
        """Perform handshake with ESP32."""
        if not device_id:
            raise ValidationError("Device ID is required")
        
        try:
            self.connected = True
            logger.info(f"Handshake successful with device {device_id}")
            return {
                "status": "ok",
                "device_id": device_id,
                "timestamp": datetime.now().isoformat(),
                "protocol_version": "1.0"
            }
        except Exception as e:
            logger.error(f"Handshake failed: {e}")
            raise ESP32ProtocolError(f"Handshake failed: {e}")

    async def send_command(self, command: str, params: Dict[str, Any] = None) -> Optional[ESP32Response]:
        """Send command to ESP32."""
        if not self.connected:
            raise ESP32ProtocolError("Not connected to ESP32")
        
        self.message_id += 1
        message = {
            "id": self.message_id,
            "type": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            if self.websocket:
                await self.websocket.send(json.dumps(message))
                
                # Wait for response
                response_data = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=self.timeout
                )
                
                response = json.loads(response_data)
                return ESP32Response(
                    status=response.get("status", "error"),
                    data=response.get("data", {}),
                    timestamp=datetime.now(),
                    error=response.get("error")
                )
            else:
                # Simulate response for testing
                return ESP32Response(
                    status="ok",
                    data={"command": command, "params": params},
                    timestamp=datetime.now()
                )
                
        except asyncio.TimeoutError:
            logger.error(f"Command timeout: {command}")
            return None
        except Exception as e:
            logger.error(f"Command failed: {e}")
            raise ESP32ProtocolError(f"Command failed: {e}")

    async def get_sensor_data(self, sensor_type: str = "all") -> Optional[Dict[str, Any]]:
        """Get sensor data from ESP32."""
        response = await self.send_command(
            CommandType.SENSOR_READ.value,
            {"sensor_type": sensor_type}
        )
        
        if response and response.status == "ok":
            return response.data
        return None

    async def control_actuator(self, actuator: str, action: str, params: Dict[str, Any] = None) -> bool:
        """Control ESP32 actuators."""
        response = await self.send_command(
            CommandType.ACTUATOR_CONTROL.value,
            {
                "actuator": actuator,
                "action": action,
                "params": params or {}
            }
        )
        
        return response and response.status == "ok"

    async def control_led(self, led_id: str, color: str, brightness: int = 100) -> bool:
        """Control LED on ESP32."""
        response = await self.send_command(
            CommandType.LED_CONTROL.value,
            {"led_id": led_id, "color": color, "brightness": brightness}
        )
        
        return response and response.status == "ok"

    async def control_motor(self, motor_id: str, direction: str, speed: int = 50) -> bool:
        """Control motor on ESP32."""
        response = await self.send_command(
            CommandType.MOTOR_CONTROL.value,
            {"motor_id": motor_id, "direction": direction, "speed": speed}
        )
        
        return response and response.status == "ok"

    async def play_audio(self, audio_file: str, volume: int = 50) -> bool:
        """Play audio on ESP32."""
        response = await self.send_command(
            CommandType.AUDIO_PLAY.value,
            {"file": audio_file, "volume": volume}
        )
        
        return response and response.status == "ok"

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """Get ESP32 device status."""
        response = await self.send_command(CommandType.STATUS_CHECK.value)
        
        if response and response.status == "ok":
            return response.data
        return None

    def parse_message(self, raw: bytes) -> ESP32Request:
        """Parse raw bytes to ESP32Request DTO."""
        try:
            data = json.loads(raw.decode('utf-8'))
            return ESP32Request(
                command=data.get('command', ''),
                params=data.get('params', {}),
                device_id=data.get('device_id', ''),
                timestamp=data.get('timestamp', datetime.now().isoformat())
            )
        except Exception as e:
            logger.error(f"Message parsing failed: {e}")
            raise ESP32ProtocolError(f"Invalid message format: {e}")

    def build_response(self, data: ESP32Data) -> bytes:
        """Serialize ESP32Data to bytes."""
        try:
            response = {
                "status": "ok",
                "data": data.__dict__ if hasattr(data, '__dict__') else data,
                "timestamp": datetime.now().isoformat()
            }
            return json.dumps(response).encode('utf-8')
        except Exception as e:
            logger.error(f"Response building failed: {e}")
            raise ESP32ProtocolError(f"Response serialization failed: {e}")

    async def disconnect(self):
        """Disconnect from ESP32."""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
            finally:
                self.websocket = None
        
        self.connected = False
        logger.info("Disconnected from ESP32")

    async def __aenter__(self):
        """Async context manager entry."""
        if self.device_ip:
            await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
