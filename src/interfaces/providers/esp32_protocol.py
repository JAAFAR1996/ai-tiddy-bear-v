"""
ESP32Protocol interface for all ESP32 device communication providers.
Depends on: nothing (pure interface)
Security: All implementations must enforce child safety and COPPA compliance at the service layer.
"""

from abc import ABC, abstractmethod


class ESP32Protocol(ABC):
    @abstractmethod
    async def handshake(self, device_id: str) -> dict:
        """Perform handshake with ESP32 device."""
        pass

    @abstractmethod
    async def parse_message(self, raw: bytes):
        """Parse raw bytes to message object."""
        pass

    @abstractmethod
    async def build_response(self, data) -> bytes:
        """Serialize data to bytes for ESP32 response."""
        pass
