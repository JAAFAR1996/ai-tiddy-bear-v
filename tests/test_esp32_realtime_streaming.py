"""🧸 AI TEDDY BEAR V5 - ESP32 Real-time Streaming Tests
Test suite for ESP32 real-time audio streaming with latency validation.
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, patch, AsyncMock
import json
import websockets

from src.infrastructure.streaming.esp32_realtime_streamer import (
    ESP32AudioStreamer,
    CircularAudioBuffer,
)


class TestCircularAudioBuffer:
    """Test suite for circular audio buffer."""

    def test_buffer_initialization(self):
        """Test proper initialization of circular buffer."""
        buffer = CircularAudioBuffer(duration=2.0, sample_rate=16000)

        assert buffer.duration == 2.0
        assert buffer.sample_rate == 16000
        assert buffer.buffer_size == 32000  # 2 seconds * 16kHz
        assert len(buffer.buffer) == 32000
        assert buffer.write_pos == 0
        assert buffer.read_pos == 0

    def test_buffer_write_read(self):
        """Test writing and reading from circular buffer."""
        buffer = CircularAudioBuffer(duration=1.0, sample_rate=16000)

        # Write some audio data
        audio_chunk = np.random.randn(1024).astype(np.float32)
        buffer.write(audio_chunk)

        assert buffer.write_pos == 1024

        # Read back the data
        read_data = buffer.read(1024)

        np.testing.assert_array_almost_equal(audio_chunk, read_data)

    def test_buffer_overflow_handling(self):
        """Test circular buffer overflow behavior."""
        buffer = CircularAudioBuffer(duration=0.1, sample_rate=16000)  # Small buffer

        # Write more data than buffer can hold
        large_chunk = np.random.randn(3200).astype(np.float32)  # 0.2 seconds
        buffer.write(large_chunk)

        # Should wrap around without errors
        assert buffer.write_pos < buffer.buffer_size

    def test_buffer_available_data(self):
        """Test available data calculation."""
        buffer = CircularAudioBuffer(duration=1.0, sample_rate=16000)

        # Initially empty
        assert buffer.available_data() == 0

        # Write some data
        buffer.write(np.random.randn(1024).astype(np.float32))
        assert buffer.available_data() == 1024

        # Read some data
        buffer.read(512)
        assert buffer.available_data() == 512


class TestESP32AudioStreamer:
    """Test suite for ESP32 real-time audio streamer."""

    @pytest.fixture
    def streamer(self):
        """Create ESP32AudioStreamer instance for testing."""
        return ESP32AudioStreamer(
            buffer_duration=2.0,
            chunk_size=1024,
            target_latency=0.3,
            auto_reconnect=True,
        )

    def test_streamer_initialization(self, streamer):
        """Test proper initialization of ESP32 streamer."""
        assert streamer.buffer_duration == 2.0
        assert streamer.chunk_size == 1024
        assert streamer.target_latency == 0.3
        assert streamer.auto_reconnect is True
        assert isinstance(streamer.audio_buffer, CircularAudioBuffer)

    @pytest.mark.asyncio
    async def test_process_audio_packet(self, streamer):
        """Test processing single audio packet."""
        # Create sample audio packet
        audio_data = np.random.randn(1024).astype(np.float32).tolist()

        with patch.object(streamer, "_transcribe_audio") as mock_transcribe:
            mock_transcribe.return_value = {
                "text": "test transcription",
                "language": "en",
                "confidence": 0.95,
            }

            result = await streamer.process_audio_packet(
                audio_data=audio_data, child_id="test_child", packet_id="packet_001"
            )

            assert result["packet_id"] == "packet_001"
            assert result["child_id"] == "test_child"
            assert result["status"] == "processed"
            assert "processing_time_ms" in result
            assert result["processing_time_ms"] < 300  # Latency requirement

    @pytest.mark.asyncio
    async def test_real_time_latency(self, streamer):
        """Test real-time latency requirements."""
        audio_data = np.random.randn(1024).astype(np.float32).tolist()

        start_time = asyncio.get_event_loop().time()

        result = await streamer.process_audio_packet(
            audio_data=audio_data, child_id="test_child", packet_id="latency_test"
        )

        end_time = asyncio.get_event_loop().time()
        processing_time = (end_time - start_time) * 1000

        # Should meet 300ms latency target
        assert processing_time < 300
        assert result["processing_time_ms"] < 300

    @pytest.mark.asyncio
    async def test_concurrent_packet_processing(self, streamer):
        """Test concurrent processing of multiple packets."""
        packets = []
        for i in range(5):
            packets.append(
                {
                    "audio_data": np.random.randn(1024).astype(np.float32).tolist(),
                    "child_id": f"child_{i}",
                    "packet_id": f"packet_{i:03d}",
                }
            )

        # Process packets concurrently
        tasks = [streamer.process_audio_packet(**packet) for packet in packets]

        results = await asyncio.gather(*tasks)

        # All should complete successfully
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result["packet_id"] == f"packet_{i:03d}"
            assert result["status"] == "processed"

    @pytest.mark.asyncio
    async def test_buffer_management(self, streamer):
        """Test audio buffer management."""
        # Fill buffer with audio data
        for i in range(10):
            audio_chunk = np.random.randn(1024).astype(np.float32)
            streamer.audio_buffer.write(audio_chunk)

        # Buffer should handle overflow gracefully
        assert streamer.audio_buffer.available_data() > 0

        # Read data from buffer
        read_data = streamer.audio_buffer.read(2048)
        assert len(read_data) == 2048

    @pytest.mark.asyncio
    async def test_error_handling(self, streamer):
        """Test error handling in packet processing."""
        # Invalid audio data
        invalid_data = "not_audio_data"

        result = await streamer.process_audio_packet(
            audio_data=invalid_data, child_id="test_child", packet_id="error_test"
        )

        assert result["status"] == "error"
        assert "error_message" in result

    def test_get_metrics(self, streamer):
        """Test metrics collection."""
        metrics = streamer.get_metrics()

        assert "buffer_usage" in metrics
        assert "average_latency_ms" in metrics
        assert "packets_processed" in metrics
        assert "packets_dropped" in metrics
        assert "target_latency_ms" in metrics
        assert metrics["target_latency_ms"] == 300

    @pytest.mark.asyncio
    async def test_stream_quality_optimization(self, streamer):
        """Test stream quality optimization features."""
        # Test with different audio qualities
        quality_levels = ["low", "medium", "high"]

        for quality in quality_levels:
            audio_data = np.random.randn(1024).astype(np.float32).tolist()

            result = await streamer.process_audio_packet(
                audio_data=audio_data,
                child_id="test_child",
                packet_id=f"quality_{quality}",
                quality=quality,
            )

            assert result["status"] == "processed"
            # Higher quality should take more time but still meet targets
            if quality == "high":
                assert result["processing_time_ms"] < 500  # Relaxed for high quality


@pytest.mark.integration
class TestESP32WebSocketIntegration:
    """Integration tests for ESP32 WebSocket streaming."""

    @pytest.mark.asyncio
    async def test_websocket_connection_flow(self):
        """Test complete WebSocket connection and streaming flow."""

        # Mock WebSocket server behavior
        async def mock_websocket_handler(websocket, path):
            try:
                await websocket.send(
                    json.dumps(
                        {
                            "type": "connection_established",
                            "message": "ESP32 streaming ready",
                        }
                    )
                )

                # Simulate receiving audio packets
                for i in range(3):
                    packet = {
                        "type": "audio_packet",
                        "audio_data": np.random.randn(1024).tolist(),
                        "child_id": "test_child",
                        "packet_id": f"packet_{i}",
                    }

                    await websocket.send(json.dumps(packet))

                    # Wait for response
                    response = await websocket.recv()
                    response_data = json.loads(response)

                    assert response_data["type"] == "audio_response"
                    assert response_data["packet_id"] == f"packet_{i}"

            except websockets.exceptions.ConnectionClosed:
                pass

    @pytest.mark.asyncio
    async def test_websocket_error_recovery(self):
        """Test WebSocket error recovery and reconnection."""
        streamer = ESP32AudioStreamer(
            buffer_duration=2.0,
            chunk_size=1024,
            target_latency=0.3,
            auto_reconnect=True,
        )

        # Simulate connection error
        with patch("websockets.connect") as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("Connection failed")

            # Should handle connection error gracefully
            result = await streamer.process_audio_packet(
                audio_data=np.random.randn(1024).tolist(),
                child_id="test_child",
                packet_id="reconnect_test",
            )

            # Should indicate connection issue but not crash
            assert "status" in result

    @pytest.mark.performance
    async def test_throughput_performance(self):
        """Test streaming throughput performance."""
        streamer = ESP32AudioStreamer(
            buffer_duration=2.0,
            chunk_size=1024,
            target_latency=0.3,
            auto_reconnect=True,
        )

        # Simulate high-throughput scenario
        start_time = asyncio.get_event_loop().time()
        packet_count = 50

        tasks = []
        for i in range(packet_count):
            audio_data = np.random.randn(1024).astype(np.float32).tolist()
            task = streamer.process_audio_packet(
                audio_data=audio_data,
                child_id="throughput_test",
                packet_id=f"throughput_{i:03d}",
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        total_time = end_time - start_time
        packets_per_second = packet_count / total_time

        # Should handle at least 20 packets per second for real-time
        assert packets_per_second >= 20

        # All packets should be processed successfully
        successful_packets = sum(1 for r in results if r.get("status") == "processed")
        assert successful_packets >= packet_count * 0.95  # 95% success rate


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not performance"])
