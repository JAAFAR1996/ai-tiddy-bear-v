"""
Tests for Concurrent Handler
============================

Tests for managing multiple audio sessions concurrently.
"""

import pytest
import asyncio
from unittest.mock import Mock

from src.application.services.streaming.concurrent_handler import ConcurrentHandler


class TestConcurrentHandler:
    """Test concurrent session handler."""

    @pytest.fixture
    def handler(self):
        """Create concurrent handler instance."""
        return ConcurrentHandler()

    @pytest.fixture
    def mock_processor(self):
        """Create mock processor."""
        return Mock()

    @pytest.mark.asyncio
    async def test_start_session(self, handler, mock_processor):
        """Test starting a session."""
        session_id = "session123"
        
        await handler.start_session(session_id, mock_processor)
        
        assert session_id in handler.sessions
        assert handler.sessions[session_id] == mock_processor

    @pytest.mark.asyncio
    async def test_stop_session(self, handler, mock_processor):
        """Test stopping a session."""
        session_id = "session123"
        
        await handler.start_session(session_id, mock_processor)
        await handler.stop_session(session_id)
        
        assert session_id not in handler.sessions

    @pytest.mark.asyncio
    async def test_stop_nonexistent_session(self, handler):
        """Test stopping non-existent session."""
        # Should not raise error
        await handler.stop_session("nonexistent")
        
        assert len(handler.sessions) == 0

    @pytest.mark.asyncio
    async def test_get_session(self, handler, mock_processor):
        """Test getting a session."""
        session_id = "session123"
        
        await handler.start_session(session_id, mock_processor)
        result = await handler.get_session(session_id)
        
        assert result == mock_processor

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, handler):
        """Test getting non-existent session."""
        result = await handler.get_session("nonexistent")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_sessions(self, handler):
        """Test managing multiple sessions."""
        processor1 = Mock()
        processor2 = Mock()
        
        await handler.start_session("session1", processor1)
        await handler.start_session("session2", processor2)
        
        assert len(handler.sessions) == 2
        assert await handler.get_session("session1") == processor1
        assert await handler.get_session("session2") == processor2

    @pytest.mark.asyncio
    async def test_concurrent_access(self, handler):
        """Test concurrent access to sessions."""
        async def add_session(session_id):
            processor = Mock()
            await handler.start_session(session_id, processor)
        
        # Start multiple sessions concurrently
        tasks = [add_session(f"session{i}") for i in range(10)]
        await asyncio.gather(*tasks)
        
        assert len(handler.sessions) == 10

    @pytest.mark.asyncio
    async def test_session_replacement(self, handler):
        """Test replacing existing session."""
        session_id = "session123"
        processor1 = Mock()
        processor2 = Mock()
        
        await handler.start_session(session_id, processor1)
        await handler.start_session(session_id, processor2)
        
        # Should replace the processor
        result = await handler.get_session(session_id)
        assert result == processor2
        assert len(handler.sessions) == 1