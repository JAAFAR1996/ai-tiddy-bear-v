"""
AudioBuffer: Real-time audio buffer for streaming audio chunks.
"""

import asyncio
from collections import deque


class AudioBuffer:
    def __init__(self, max_size: int = 4096):
        self.buffer = deque()
        self.max_size = max_size
        self.lock = asyncio.Lock()

    async def add_chunk(self, chunk: bytes):
        async with self.lock:
            if len(self.buffer) >= self.max_size:
                self.buffer.popleft()
            self.buffer.append(chunk)

    async def get_all(self) -> bytes:
        async with self.lock:
            data = b"".join(self.buffer)
            self.buffer.clear()
            return data

    async def clear(self):
        async with self.lock:
            self.buffer.clear()
