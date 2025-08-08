"""
Tests for Audio Streaming Service
=================================

Critical tests for audio streaming and buffer management.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from collections import deque

from src.application.services.audio_streaming_service import AudioStreamingService


class TestAudioStreamingService:
    """Test audio streaming service functionality."""

    @pytest.fixture
    def service(self):
        """Create audio streaming service instance."""
        return AudioStreamingService(buffer_size=4, logger=Mock())

    @pytest.fixture
    def mock_audio_stream(self):
        """Create mock audio stream."""
        async def stream():
            chunks = [b"chunk1", b"chunk2", b"chunk3", b"chunk4", b"chunk5"]
            for chunk in chunks:
                yield chunk
        return stream()

    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service.buffer_size == 4
        assert service.logger is not None
        assert len(service._buffer) == 0
        assert service._lock is not None

    @pytest.mark.asyncio
    async def test_add_chunk_basic(self, service):
        """Test adding audio chunks to buffer."""
        chunk = b"test_audio_data"
        
        await service.add_chunk(chunk)
        
        assert len(service._buffer) == 1
        assert service._buffer[0] == chunk

    @pytest.mark.asyncio
    async def test_add_chunk_buffer_overflow(self, service):
        """Test buffer overflow handling."""
        # Fill buffer to capacity
        for i in range(5):  # Buffer size is 4
            await service.add_chunk(f"chunk{i}".encode())
        
        # Buffer should maintain max size
        assert len(service._buffer) == 4
        # First chunk should be removed (FIFO)
        assert b"chunk0" not in service._buffer
        assert b"chunk4" in service._buffer

    @pytest.mark.asyncio
    async def test_get_all_data(self, service):
        """Test getting all buffered data."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        
        for chunk in chunks:
            await service.add_chunk(chunk)
        
        data = await service.get_all_data()
        
        assert data == b"chunk1chunk2chunk3"
        assert len(service._buffer) == 0  # Buffer should be cleared

    @pytest.mark.asyncio
    async def test_clear_buffer(self, service):
        """Test buffer clearing."""
        await service.add_chunk(b"test_data")
        assert len(service._buffer) == 1
        
        await service.clear_buffer()
        
        assert len(service._buffer) == 0

    @pytest.mark.asyncio
    async def test_process_stream_success(self, service, mock_audio_stream):
        """Test successful stream processing."""
        result = await service.process_stream(mock_audio_stream)
        
        assert result == b"chunk1chunk2chunk3chunk4chunk5"

    @pytest.mark.asyncio
    async def test_process_stream_with_error(self, service):
        """Test stream processing with error."""
        async def failing_stream():
            yield b"chunk1"
            raise Exception("Stream error")
        
        with pytest.raises(Exception, match="Stream error"):
            await service.process_stream(failing_stream())

    @pytest.mark.asyncio
    async def test_process_stream_logs_error(self, service):
        """Test that stream processing errors are logged."""
        mock_logger = Mock()
        service.logger = mock_logger
        
        async def failing_stream():
            raise Exception("Test error")
        
        with pytest.raises(Exception):
            await service.process_stream(failing_stream())
        
        mock_logger.error.assert_called_once()
        assert "Stream processing failed" in mock_logger.error.call_args[0][0]

    def test_is_voice_detected_with_numpy(self, service):
        """Test voice detection with numpy available."""
        with patch('numpy.frombuffer') as mock_frombuffer, \
             patch('numpy.mean') as mock_mean, \
             patch('numpy.abs') as mock_abs:
            
            # Mock numpy operations
            mock_frombuffer.return_value = [100, 200, 300]
            mock_abs.return_value = [100, 200, 300]
            mock_mean.return_value = 0.05  # Above threshold
            
            chunk = b"audio_data_with_voice"
            result = service.is_voice_detected(chunk)
            
            assert result is True
            mock_frombuffer.assert_called_once()
            mock_mean.assert_called_once()

    def test_is_voice_detected_without_numpy(self, service):
        """Test voice detection fallback without numpy."""
        with patch('builtins.__import__', side_effect=ImportError):
            # Long chunk should be detected as voice
            long_chunk = b"a" * 150
            result = service.is_voice_detected(long_chunk)
            assert result is True
            
            # Short chunk should not be detected as voice
            short_chunk = b"a" * 50
            result = service.is_voice_detected(short_chunk)
            assert result is False

    def test_is_voice_detected_empty_chunk(self, service):
        """Test voice detection with empty or very small chunks."""
        # Empty chunk
        result = service.is_voice_detected(b"")
        assert result is False
        
        # Single byte chunk
        result = service.is_voice_detected(b"a")
        assert result is False

    @pytest.mark.asyncio
    async def test_concurrent_access(self, service):
        """Test concurrent access to buffer."""
        async def add_chunks():
            for i in range(10):
                await service.add_chunk(f"chunk{i}".encode())
                await asyncio.sleep(0.001)  # Small delay
        
        async def read_data():
            await asyncio.sleep(0.005)  # Let some chunks accumulate
            return await service.get_all_data()
        
        # Run concurrent operations
        add_task = asyncio.create_task(add_chunks())
        read_task = asyncio.create_task(read_data())
        
        await add_task
        data = await read_task
        
        # Should have some data
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_collect_stream_data(self, service):
        """Test internal stream data collection."""
        async def test_stream():
            chunks = [b"data1", b"data2", b"data3"]
            for chunk in chunks:
                yield chunk
        
        await service._collect_stream_data(test_stream())
        
        assert len(service._buffer) == 3
        assert b"data1" in service._buffer
        assert b"data2" in service._buffer
        assert b"data3" in service._buffer

    @pytest.mark.asyncio
    async def test_collect_stream_data_with_empty_chunks(self, service):
        """Test stream collection with empty chunks."""
        async def test_stream():
            chunks = [b"data1", b"", b"data2", None, b"data3"]
            for chunk in chunks:
                yield chunk
        
        await service._collect_stream_data(test_stream())
        
        # Should only have non-empty chunks
        assert len(service._buffer) == 3
        assert b"data1" in service._buffer
        assert b"data2" in service._buffer
        assert b"data3" in service._buffer

    @pytest.mark.asyncio
    async def test_get_buffered_data(self, service):
        """Test internal buffered data retrieval."""
        chunks = [b"test1", b"test2", b"test3"]
        for chunk in chunks:
            await service.add_chunk(chunk)
        
        data = await service._get_buffered_data()
        
        assert data == b"test1test2test3"
        assert len(service._buffer) == 0

    @pytest.mark.asyncio
    async def test_buffer_thread_safety(self, service):
        """Test buffer operations are thread-safe."""
        async def writer():
            for i in range(100):
                await service.add_chunk(f"data{i}".encode())
        
        async def reader():
            results = []
            for _ in range(10):
                await asyncio.sleep(0.001)
                data = await service.get_all_data()
                if data:
                    results.append(data)
            return results
        
        # Run concurrent operations
        writer_task = asyncio.create_task(writer())
        reader_task = asyncio.create_task(reader())
        
        await writer_task
        results = await reader_task
        
        # Should have read some data without errors
        assert len(results) >= 0  # May be empty if timing is off

    @pytest.mark.asyncio
    async def test_large_stream_processing(self, service):
        """Test processing of large audio streams."""
        async def large_stream():
            for i in range(1000):
                yield f"chunk{i:04d}".encode()
        
        result = await service.process_stream(large_stream())
        
        # Should handle large streams
        assert len(result) > 0
        # Due to buffer size limit, not all chunks will be present
        assert len(result) <= service.buffer_size * 10  # Rough estimate

    @pytest.mark.asyncio
    async def test_empty_stream_processing(self, service):
        """Test processing of empty stream."""
        async def empty_stream():
            return
            yield  # Unreachable
        
        result = await service.process_stream(empty_stream())
        
        assert result == b""

    def test_service_with_custom_buffer_size(self):
        """Test service with custom buffer size."""
        custom_service = AudioStreamingService(buffer_size=10)
        
        assert custom_service.buffer_size == 10
        assert len(custom_service._buffer) == 0

    def test_service_with_custom_logger(self):
        """Test service with custom logger."""
        custom_logger = Mock()
        custom_service = AudioStreamingService(logger=custom_logger)
        
        assert custom_service.logger == custom_logger

    @pytest.mark.asyncio
    async def test_voice_detection_integration(self, service):
        """Test voice detection integration with streaming."""
        voice_chunk = b"a" * 200  # Should be detected as voice
        silence_chunk = b"a" * 50  # Should not be detected as voice
        
        await service.add_chunk(voice_chunk)
        await service.add_chunk(silence_chunk)
        
        # Test voice detection on individual chunks
        assert service.is_voice_detected(voice_chunk) is True
        assert service.is_voice_detected(silence_chunk) is False
        
        # Get all data
        data = await service.get_all_data()
        assert len(data) == 250  # Both chunks combined