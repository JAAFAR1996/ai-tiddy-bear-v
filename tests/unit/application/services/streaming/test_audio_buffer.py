"""
Unit tests for AudioBuffer
Tests real-time audio buffer functionality
"""

import pytest
import asyncio

from src.application.services.streaming.audio_buffer import AudioBuffer


class TestAudioBuffer:
    """Test AudioBuffer functionality."""

    @pytest.fixture
    def audio_buffer(self):
        """Create AudioBuffer instance."""
        return AudioBuffer(max_size=5)

    @pytest.fixture
    def sample_chunks(self):
        """Sample audio chunks for testing."""
        return [b"chunk1", b"chunk2", b"chunk3", b"chunk4", b"chunk5"]

    @pytest.mark.asyncio
    async def test_add_single_chunk(self, audio_buffer):
        """Test adding a single audio chunk."""
        chunk = b"test_chunk"
        await audio_buffer.add_chunk(chunk)
        
        data = await audio_buffer.get_all()
        assert data == chunk

    @pytest.mark.asyncio
    async def test_add_multiple_chunks(self, audio_buffer, sample_chunks):
        """Test adding multiple audio chunks."""
        for chunk in sample_chunks[:3]:
            await audio_buffer.add_chunk(chunk)
        
        data = await audio_buffer.get_all()
        expected = b"chunk1chunk2chunk3"
        assert data == expected

    @pytest.mark.asyncio
    async def test_buffer_overflow(self, audio_buffer, sample_chunks):
        """Test buffer behavior when exceeding max_size."""
        # Add more chunks than max_size
        for chunk in sample_chunks:
            await audio_buffer.add_chunk(chunk)
        
        # Add one more to trigger overflow
        await audio_buffer.add_chunk(b"overflow")
        
        data = await audio_buffer.get_all()
        # Should contain last 5 chunks (max_size)
        expected = b"chunk2chunk3chunk4chunk5overflow"
        assert data == expected

    @pytest.mark.asyncio
    async def test_get_all_clears_buffer(self, audio_buffer):
        """Test that get_all() clears the buffer."""
        await audio_buffer.add_chunk(b"test1")
        await audio_buffer.add_chunk(b"test2")
        
        # First get_all should return data
        data1 = await audio_buffer.get_all()
        assert data1 == b"test1test2"
        
        # Second get_all should return empty
        data2 = await audio_buffer.get_all()
        assert data2 == b""

    @pytest.mark.asyncio
    async def test_clear_buffer(self, audio_buffer, sample_chunks):
        """Test manual buffer clearing."""
        for chunk in sample_chunks[:3]:
            await audio_buffer.add_chunk(chunk)
        
        await audio_buffer.clear()
        
        data = await audio_buffer.get_all()
        assert data == b""

    @pytest.mark.asyncio
    async def test_empty_buffer_get_all(self, audio_buffer):
        """Test get_all() on empty buffer."""
        data = await audio_buffer.get_all()
        assert data == b""

    @pytest.mark.asyncio
    async def test_concurrent_access(self, audio_buffer):
        """Test concurrent access to buffer."""
        async def add_chunks():
            for i in range(10):
                await audio_buffer.add_chunk(f"chunk{i}".encode())
                await asyncio.sleep(0.001)  # Small delay

        async def read_chunks():
            results = []
            for _ in range(5):
                await asyncio.sleep(0.002)  # Small delay
                data = await audio_buffer.get_all()
                if data:
                    results.append(data)
            return results

        # Run concurrent operations
        add_task = asyncio.create_task(add_chunks())
        read_task = asyncio.create_task(read_chunks())
        
        await add_task
        results = await read_task
        
        # Should have some results without errors
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_large_chunks(self, audio_buffer):
        """Test handling of large audio chunks."""
        large_chunk = b"x" * 10000  # 10KB chunk
        await audio_buffer.add_chunk(large_chunk)
        
        data = await audio_buffer.get_all()
        assert data == large_chunk

    @pytest.mark.asyncio
    async def test_empty_chunks(self, audio_buffer):
        """Test handling of empty chunks."""
        await audio_buffer.add_chunk(b"")
        await audio_buffer.add_chunk(b"valid")
        await audio_buffer.add_chunk(b"")
        
        data = await audio_buffer.get_all()
        assert data == b"valid"

    def test_buffer_initialization_default(self):
        """Test buffer initialization with default parameters."""
        buffer = AudioBuffer()
        assert buffer.max_size == 4096
        assert len(buffer.buffer) == 0

    def test_buffer_initialization_custom_size(self):
        """Test buffer initialization with custom max_size."""
        buffer = AudioBuffer(max_size=100)
        assert buffer.max_size == 100
        assert len(buffer.buffer) == 0

    @pytest.mark.asyncio
    async def test_buffer_size_tracking(self, audio_buffer, sample_chunks):
        """Test that buffer size is properly tracked."""
        # Add chunks one by one and check size
        for i, chunk in enumerate(sample_chunks):
            await audio_buffer.add_chunk(chunk)
            expected_size = min(i + 1, audio_buffer.max_size)
            assert len(audio_buffer.buffer) == expected_size

    @pytest.mark.asyncio
    async def test_fifo_behavior(self, audio_buffer):
        """Test First-In-First-Out behavior when buffer overflows."""
        # Fill buffer to max capacity
        for i in range(5):
            await audio_buffer.add_chunk(f"chunk{i}".encode())
        
        # Add one more to trigger FIFO
        await audio_buffer.add_chunk(b"newest")
        
        data = await audio_buffer.get_all()
        # Should not contain the first chunk (chunk0)
        assert b"chunk0" not in data
        assert b"newest" in data

    @pytest.mark.asyncio
    async def test_thread_safety_simulation(self, audio_buffer):
        """Test thread safety by simulating concurrent operations."""
        async def writer():
            for i in range(20):
                await audio_buffer.add_chunk(f"w{i}".encode())

        async def reader():
            results = []
            for _ in range(10):
                data = await audio_buffer.get_all()
                results.append(len(data))
            return results

        async def clearer():
            for _ in range(5):
                await asyncio.sleep(0.001)
                await audio_buffer.clear()

        # Run all operations concurrently
        writer_task = asyncio.create_task(writer())
        reader_task = asyncio.create_task(reader())
        clearer_task = asyncio.create_task(clearer())
        
        await asyncio.gather(writer_task, reader_task, clearer_task)
        
        # Should complete without errors
        assert True

    @pytest.mark.asyncio
    async def test_buffer_state_after_operations(self, audio_buffer):
        """Test buffer state consistency after various operations."""
        # Add some data
        await audio_buffer.add_chunk(b"test1")
        await audio_buffer.add_chunk(b"test2")
        
        # Get all data
        data = await audio_buffer.get_all()
        assert data == b"test1test2"
        
        # Buffer should be empty now
        assert len(audio_buffer.buffer) == 0
        
        # Add more data
        await audio_buffer.add_chunk(b"test3")
        
        # Clear buffer
        await audio_buffer.clear()
        assert len(audio_buffer.buffer) == 0
        
        # Final get_all should return empty
        final_data = await audio_buffer.get_all()
        assert final_data == b""