"""
Audio Streamer for ESP32 - Unified with AudioService

This module provides ESP32-specific audio streaming capabilities
integrated with the main AudioService.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, AsyncIterable
from src.application.services.audio_service import AudioService


class AudioStreamer:
    """ESP32 Audio Streamer integrated with unified AudioService."""
    
    def __init__(self, audio_service: AudioService, logger: Optional[logging.Logger] = None):
        self.audio_service = audio_service
        self.logger = logger or logging.getLogger(__name__)
        self._active_streams: Dict[str, asyncio.Task] = {}
        
    async def start_stream(self, device_id: str, audio_stream: AsyncIterable[bytes]) -> Dict[str, Any]:
        """Start audio stream processing for ESP32 device."""
        if device_id in self._active_streams:
            await self.stop_stream(device_id)
            
        try:
            # Process audio stream through unified service
            result = await self.audio_service.process_audio(audio_stream)
            
            self.logger.info(f"Started audio stream for device: {device_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to start stream for device {device_id}: {e}")
            raise
    
    async def stop_stream(self, device_id: str) -> bool:
        """Stop audio stream for ESP32 device."""
        if device_id in self._active_streams:
            task = self._active_streams.pop(device_id)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            self.logger.info(f"Stopped audio stream for device: {device_id}")
            return True
            
        return False
    
    async def get_stream_status(self, device_id: str) -> Dict[str, Any]:
        """Get status of audio stream for device."""
        is_active = device_id in self._active_streams
        return {
            "device_id": device_id,
            "is_active": is_active,
            "stream_count": len(self._active_streams)
        }
