"""
ConcurrentHandler: Manage multiple real-time audio sessions concurrently.
"""

import asyncio


class ConcurrentHandler:
    def __init__(self):
        self.sessions = {}
        self.lock = asyncio.Lock()

    async def start_session(self, session_id, processor):
        async with self.lock:
            self.sessions[session_id] = processor

    async def stop_session(self, session_id):
        async with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]

    async def get_session(self, session_id):
        async with self.lock:
            return self.sessions.get(session_id)
