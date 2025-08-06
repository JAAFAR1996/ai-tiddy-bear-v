"""
ESP32 Real-time Audio Streaming Tests
====================================
Tests for low-latency audio streaming with ESP32 devices.
"""

import pytest
import time
import json
from unittest.mock import AsyncMock, patch

from src.infrastructure.streaming.esp32_realtime_streamer import (
    ESP32AudioStreamer,
    AudioPacket,
    StreamingState,
    CircularAudioBuffer,
)


@pytest.fixture
def audio_streamer():
    """Create ESP32 audio streamer for testing."""
    return ESP32AudioStreamer(
        max_latency_ms=300.0,
        buffer_duration_seconds=2.0,
        packet_size_ms=100.0,
        enable_ack=False,
        reconnect_attempts=3,
    )


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    from fastapi.websockets import WebSocket

    websocket = AsyncMock(spec=WebSocket)
    websocket.receive_bytes = AsyncMock(spec=WebSocket.receive_bytes)
    websocket.send_bytes = AsyncMock(spec=WebSocket.send_bytes)
    return websocket


@pytest.fixture
def sample_audio_data():
    """Generate sample audio data."""
    # 16-bit PCM audio data (100ms at 16kHz)
    import struct

    samples = [int(1000 * (i % 100) / 100) for i in range(1600)]  # 100ms worth
    return struct.pack(f"<{len(samples)}h", *samples)


@pytest.mark.asyncio
class TestESP32AudioStreamer:
    """Test ESP32 real-time audio streaming."""

    async def test_stream_initialization(self, audio_streamer, mock_websocket):
        """Test stream initialization and setup."""
        device_id = "esp32_teddy_001"

        def mock_audio_callback(audio_data: bytes) -> bytes:
            # Echo back the audio data
            return audio_data

        # Start stream
        success = await audio_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=mock_audio_callback,
        )

        # Verify stream started
        assert success
        assert device_id in audio_streamer._active_streams

        stream = audio_streamer._active_streams[device_id]
        assert stream["device_id"] == device_id
        assert stream["state"] == StreamingState.CONNECTING
        assert stream["websocket"] == mock_websocket
        assert stream["audio_callback"] == mock_audio_callback

        # Cleanup
        await audio_streamer.stop_stream(device_id)

    async def test_audio_packet_processing(
        self, audio_streamer, mock_websocket, sample_audio_data
    ):
        """Test audio packet processing and response generation."""
        device_id = "esp32_teddy_001"
        processed_audio = []

        def mock_audio_callback(audio_data: bytes) -> bytes:
            processed_audio.append(audio_data)
            # Return processed audio (TTS response)
            return b"processed_" + audio_data[:10]

        # Start stream
        await audio_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=mock_audio_callback,
        )

        # Process incoming packet
        await audio_streamer._process_incoming_packet(device_id, sample_audio_data)

        # Verify audio was processed
        assert len(processed_audio) == 1
        assert processed_audio[0] == sample_audio_data

        # Verify response packet was sent
        mock_websocket.send_bytes.assert_called_once()
        sent_data = mock_websocket.send_bytes.call_args[0][0]
        packet_data = json.loads(sent_data.decode("utf-8"))

        assert packet_data["sequence_number"] == 0
        assert packet_data["duration_ms"] == 100.0
        assert "audio_data" in packet_data

        # Cleanup
        await audio_streamer.stop_stream(device_id)

    async def test_latency_monitoring(
        self, audio_streamer, mock_websocket, sample_audio_data
    ):
        """Test latency monitoring and warnings."""
        device_id = "esp32_teddy_001"

        def slow_audio_callback(audio_data: bytes) -> bytes:
            # Simulate slow processing
            time.sleep(0.4)  # 400ms - exceeds 300ms target
            return audio_data

        # Start stream
        await audio_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=slow_audio_callback,
        )

        # Process packet (should trigger latency warning)
        with patch("logging.Logger.warning", autospec=True) as mock_warning:
            await audio_streamer._process_incoming_packet(device_id, sample_audio_data)

            # Verify latency warning was logged
            mock_warning.assert_called()
            warning_msg = mock_warning.call_args[0][0]
            assert "Latency exceeded target" in warning_msg

        # Verify metrics updated
        assert audio_streamer._metrics.current_latency_ms > 300.0

        # Cleanup
        await audio_streamer.stop_stream(device_id)

    async def test_circular_buffer_functionality(self):
        """Test circular audio buffer operations."""
        buffer = CircularAudioBuffer(max_duration_seconds=1.0, sample_rate=16000)

        # Test buffer capacity
        assert buffer.max_samples == 16000
        assert buffer.get_usage_percent() == 0.0

        # Add audio data
        import struct

        audio_data = struct.pack("<1600h", *range(1600))  # 100ms worth

        dropped = await buffer.add_audio_data(audio_data)
        assert dropped == 0
        assert buffer.get_usage_percent() == 10.0  # 1600/16000 * 100

        # Fill buffer to capacity
        for _ in range(10):
            await buffer.add_audio_data(audio_data)

        # Should be at 100% capacity
        assert buffer.get_usage_percent() == 100.0

        # Adding more should drop old samples
        dropped = await buffer.add_audio_data(audio_data)
        assert dropped > 0

        # Get latest audio
        latest = await buffer.get_latest_audio(0.5)  # 500ms
        assert len(latest) == 16000  # 8000 samples * 2 bytes

        # Clear buffer
        await buffer.clear()
        assert buffer.get_usage_percent() == 0.0

    async def test_reconnection_handling(self, audio_streamer, mock_websocket):
        """Test automatic reconnection on connection loss."""
        device_id = "esp32_teddy_001"
        reconnection_events = []

        def mock_audio_callback(audio_data: bytes) -> bytes:
            return audio_data

        def on_reconnected(device_id: str, attempt: int):
            reconnection_events.append((device_id, attempt))

        # Set reconnection callback
        audio_streamer.set_callbacks(on_reconnected=on_reconnected)

        # Start stream
        await audio_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=mock_audio_callback,
        )

        # Simulate reconnection
        await audio_streamer._attempt_reconnection(device_id, 0)

        # Verify reconnection handled
        stream = audio_streamer._active_streams[device_id]
        assert stream["state"] == StreamingState.CONNECTED
        assert audio_streamer._metrics.total_reconnections == 1

        # Cleanup
        await audio_streamer.stop_stream(device_id)

    async def test_multiple_concurrent_streams(self, audio_streamer):
        """Test handling multiple concurrent device streams."""
        devices = ["esp32_teddy_001", "esp32_teddy_002", "esp32_teddy_003"]
        from fastapi.websockets import WebSocket

        websockets = [AsyncMock(spec=WebSocket) for _ in devices]

        def mock_audio_callback(audio_data: bytes) -> bytes:
            return audio_data

        # Start multiple streams
        for device_id, websocket in zip(devices, websockets):
            success = await audio_streamer.start_stream(
                device_id=device_id,
                websocket_connection=websocket,
                audio_callback=mock_audio_callback,
            )
            assert success

        # Verify all streams active
        assert len(audio_streamer._active_streams) == 3

        # Get status of all streams
        all_status = await audio_streamer.get_all_streams_status()
        assert all_status["active_streams_count"] == 3
        assert len(all_status["streams"]) == 3

        # Stop all streams
        for device_id in devices:
            await audio_streamer.stop_stream(device_id)

        assert len(audio_streamer._active_streams) == 0

    async def test_stream_status_reporting(self, audio_streamer, mock_websocket):
        """Test detailed stream status reporting."""
        device_id = "esp32_teddy_001"

        def mock_audio_callback(audio_data: bytes) -> bytes:
            return audio_data

        # Start stream
        await audio_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=mock_audio_callback,
        )

        # Get stream status
        status = await audio_streamer.get_stream_status(device_id)

        # Verify status details
        assert status["device_id"] == device_id
        assert status["connected"] is True
        assert status["uptime_seconds"] >= 0
        assert status["sequence_number"] == 0
        assert status["buffer_usage_percent"] == 0.0
        assert "metrics" in status

        # Test non-existent device
        empty_status = await audio_streamer.get_stream_status("non_existent")
        assert empty_status["connected"] is False
        assert empty_status["state"] == StreamingState.DISCONNECTED.value

        # Cleanup
        await audio_streamer.stop_stream(device_id)

    async def test_packet_acknowledgment(self, audio_streamer, mock_websocket):
        """Test packet acknowledgment when enabled."""
        # Create streamer with ACK enabled
        ack_streamer = ESP32AudioStreamer(enable_ack=True)
        device_id = "esp32_teddy_001"

        def mock_audio_callback(audio_data: bytes) -> bytes:
            return audio_data

        # Start stream
        await ack_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=mock_audio_callback,
        )

        # Create audio packet
        packet = AudioPacket(
            packet_id="test_packet_001",
            sequence_number=1,
            timestamp=time.time(),
            audio_data=b"test_audio_data",
            duration_ms=100.0,
        )

        # Send packet
        await ack_streamer._send_packet(device_id, packet)

        # Verify packet sent
        mock_websocket.send_bytes.assert_called_once()
        sent_data = mock_websocket.send_bytes.call_args[0][0]
        packet_data = json.loads(sent_data.decode("utf-8"))

        assert packet_data["packet_id"] == "test_packet_001"
        assert packet_data["sequence_number"] == 1

        # Cleanup
        await ack_streamer.stop_stream(device_id)

    async def test_latency_optimization(self, audio_streamer):
        """Test latency optimization settings."""
        # Apply optimizations
        await audio_streamer.optimize_for_latency()

        # Verify optimizations applied
        assert audio_streamer.packet_size_ms <= 50.0
        assert audio_streamer.enable_ack is False
        assert audio_streamer.buffer_duration_seconds <= 1.0

    async def test_error_handling_and_recovery(self, audio_streamer, mock_websocket):
        """Test error handling and recovery mechanisms."""
        device_id = "esp32_teddy_001"

        def failing_audio_callback(audio_data: bytes) -> bytes:
            raise Exception("Audio processing failed")

        # Start stream with failing callback
        await audio_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=failing_audio_callback,
        )

        # Process packet (should handle error gracefully)
        sample_data = b"test_audio_data"

        with patch("logging.Logger.error", autospec=True) as mock_error:
            await audio_streamer._process_incoming_packet(device_id, sample_data)

            # Verify error was logged
            mock_error.assert_called()

        # Stream should still be active
        assert device_id in audio_streamer._active_streams

        # Cleanup
        await audio_streamer.stop_stream(device_id)

    async def test_metrics_collection_and_reporting(
        self, audio_streamer, mock_websocket, sample_audio_data
    ):
        """Test comprehensive metrics collection."""
        device_id = "esp32_teddy_001"

        def mock_audio_callback(audio_data: bytes) -> bytes:
            return audio_data

        # Start stream
        await audio_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=mock_audio_callback,
        )

        # Process multiple packets
        for i in range(5):
            await audio_streamer._process_incoming_packet(device_id, sample_audio_data)

        # Get metrics
        metrics = audio_streamer._metrics

        # Verify metrics collected
        assert metrics.total_packets_sent == 5
        assert metrics.current_latency_ms > 0
        assert metrics.last_packet_timestamp > 0

        # Get stream status with metrics
        status = await audio_streamer.get_stream_status(device_id)
        assert "metrics" in status

        # Cleanup
        await audio_streamer.stop_stream(device_id)

    async def test_coppa_compliance_audio_filtering(
        self, audio_streamer, mock_websocket
    ):
        """Test COPPA compliance features in audio streaming."""
        device_id = "esp32_teddy_child_001"
        filtered_content = []

        def child_safe_audio_callback(audio_data: bytes) -> bytes:
            # Simulate content filtering for child safety
            filtered_content.append("filtered")
            # Return child-appropriate audio response
            return b"child_safe_audio_response"

        # Start stream with child-safe callback
        await audio_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=child_safe_audio_callback,
        )

        # Process audio packet
        sample_data = b"potentially_inappropriate_audio"
        await audio_streamer._process_incoming_packet(device_id, sample_data)

        # Verify content was filtered
        assert len(filtered_content) == 1

        # Verify child-safe response sent
        mock_websocket.send_bytes.assert_called_once()
        sent_data = mock_websocket.send_bytes.call_args[0][0]
        packet_data = json.loads(sent_data.decode("utf-8"))

        # Audio data should be child-safe
        import binascii

        audio_bytes = binascii.unhexlify(packet_data["audio_data"])
        assert audio_bytes == b"child_safe_audio_response"

        # Cleanup
        await audio_streamer.stop_stream(device_id)

    async def test_buffer_overflow_handling(self, audio_streamer, mock_websocket):
        """Test handling of buffer overflow conditions."""
        device_id = "esp32_teddy_001"

        def mock_audio_callback(audio_data: bytes) -> bytes:
            return audio_data

        # Start stream
        await audio_streamer.start_stream(
            device_id=device_id,
            websocket_connection=mock_websocket,
            audio_callback=mock_audio_callback,
        )

        stream = audio_streamer._active_streams[device_id]
        buffer = stream["buffer"]

        # Fill buffer beyond capacity
        import struct

        large_audio_data = struct.pack("<32000h", *range(32000))  # 2 seconds worth

        # Should handle overflow gracefully
        dropped = await buffer.add_audio_data(large_audio_data)
        assert dropped > 0

        # Verify metrics updated
        await audio_streamer._process_incoming_packet(device_id, large_audio_data)
        assert audio_streamer._metrics.total_packets_dropped > 0

        # Cleanup
        await audio_streamer.stop_stream(device_id)
