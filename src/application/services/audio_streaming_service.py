"""
Audio Streaming Service - Single Responsibility
==============================================
Handles audio streaming and buffer management.
"""

import asyncio
import logging
from typing import AsyncIterable, Optional, Tuple
from collections import deque


class AudioStreamingService:
    """Focused audio streaming service."""
    
    def __init__(self, buffer_size: int = 4096, logger: Optional[logging.Logger] = None):
        self.buffer_size = buffer_size
        self.logger = logger or logging.getLogger(__name__)
        self._buffer = deque()
        self._lock = asyncio.Lock()
    
    async def process_stream(self, audio_stream: AsyncIterable[bytes]) -> bytes:
        """Process audio stream and return combined data."""
        try:
            await self._collect_stream_data(audio_stream)
            return await self._get_buffered_data()
        except Exception as e:
            self.logger.error(f"Stream processing failed: {e}")
            raise
    
    async def add_chunk(self, chunk: bytes) -> None:
        """Add audio chunk to buffer."""
        async with self._lock:
            if len(self._buffer) >= self.buffer_size:
                self._buffer.popleft()
            self._buffer.append(chunk)
    
    async def get_all_data(self) -> bytes:
        """Get all buffered data and clear buffer."""
        async with self._lock:
            data = b"".join(self._buffer)
            self._buffer.clear()
            return data
    
    async def clear_buffer(self) -> None:
        """Clear the audio buffer."""
        async with self._lock:
            self._buffer.clear()
    
    def is_voice_detected(self, chunk: bytes) -> bool:
        """Simple voice activity detection."""
        if len(chunk) < 2:
            return False
        
        # Basic energy threshold
        try:
            import numpy as np
            audio_np = np.frombuffer(chunk, dtype=np.int16)
            energy = np.mean(np.abs(audio_np))
            return energy > 0.01
        except ImportError:
            # Fallback without numpy
            return len(chunk) > 100
    
    async def _collect_stream_data(self, audio_stream: AsyncIterable[bytes]) -> None:
        """Collect data from audio stream."""
        async for chunk in audio_stream:
            if chunk:
                await self.add_chunk(chunk)
    
    async def _get_buffered_data(self) -> bytes:
        """Get all buffered data."""
        return await self.get_all_data()