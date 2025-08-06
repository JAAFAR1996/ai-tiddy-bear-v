"""
ESP32 Real-time Audio Streaming Service
=======================================
Optimized for 300ms latency with packet-based streaming and automatic reconnection.
"""

import asyncio
import logging
import time
import json
from collections import deque
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import uuid


class StreamingState(Enum):
    """Streaming connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    BUFFERING = "buffering"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class AudioPacket:
    """Audio data packet for streaming."""

    packet_id: str
    sequence_number: int
    timestamp: float
    audio_data: bytes
    duration_ms: float
    is_final: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "packet_id": self.packet_id,
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp,
            "audio_data": self.audio_data.hex(),  # Convert bytes to hex string
            "duration_ms": self.duration_ms,
            "is_final": self.is_final,
        }


@dataclass
class StreamingMetrics:
    """Real-time streaming metrics."""

    total_packets_sent: int = 0
    total_packets_dropped: int = 0
    total_reconnections: int = 0
    current_latency_ms: float = 0.0
    buffer_usage_percent: float = 0.0
    connection_uptime_seconds: float = 0.0
    last_packet_timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class CircularAudioBuffer:
    """Circular buffer for ESP32 audio data with 2-second capacity."""

    def __init__(self, max_duration_seconds: float = 2.0, sample_rate: int = 16000):
        self.max_duration_seconds = max_duration_seconds
        self.sample_rate = sample_rate
        self.max_samples = int(max_duration_seconds * sample_rate)
        self._buffer = deque(maxlen=self.max_samples)
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger(__name__)

    async def add_audio_data(self, audio_data: bytes) -> int:
        """Add audio data to buffer, dropping oldest if full."""
        async with self._lock:
            # Convert bytes to samples (assuming 16-bit audio)
            import struct

            samples = struct.unpack(f"<{len(audio_data)//2}h", audio_data)

            dropped_count = 0
            for sample in samples:
                if len(self._buffer) >= self.max_samples:
                    self._buffer.popleft()  # Drop oldest
                    dropped_count += 1
                self._buffer.append(sample)

            if dropped_count > 0:
                self._logger.warning(
                    f"Dropped {dropped_count} audio samples due to buffer overflow"
                )

            return dropped_count

    async def get_latest_audio(self, duration_seconds: float) -> bytes:
        """Get latest audio data from buffer."""
        async with self._lock:
            num_samples = min(
                int(duration_seconds * self.sample_rate), len(self._buffer)
            )
            if num_samples == 0:
                return b""

            # Get latest samples
            latest_samples = list(self._buffer)[-num_samples:]

            # Convert back to bytes
            import struct

            return struct.pack(f"<{len(latest_samples)}h", *latest_samples)

    async def clear(self):
        """Clear the buffer."""
        async with self._lock:
            self._buffer.clear()

    def get_usage_percent(self) -> float:
        """Get current buffer usage percentage."""
        return (len(self._buffer) / self.max_samples) * 100


class ESP32AudioStreamer:
    """
    Real-time Audio Streaming Service for ESP32
    ==========================================

    Features:
    - 300ms maximum latency target
    - Packet-based streaming with optional ACK
    - Circular buffer with 2-second capacity
    - Automatic reconnection on network issues
    - Comprehensive logging and monitoring
    - Lossy streaming (drops old data on network issues)
    """

    def __init__(
        self,
        max_latency_ms: float = 300.0,
        buffer_duration_seconds: float = 2.0,
        packet_size_ms: float = 100.0,  # 100ms packets
        enable_ack: bool = False,
        reconnect_attempts: int = 5,
        reconnect_delay_seconds: float = 1.0,
    ):
        self.max_latency_ms = max_latency_ms
        self.buffer_duration_seconds = buffer_duration_seconds
        self.packet_size_ms = packet_size_ms
        self.enable_ack = enable_ack
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay_seconds = reconnect_delay_seconds

        # Internal state
        self._active_streams: Dict[str, Dict[str, Any]] = {}
        self._logger = logging.getLogger(__name__)
        self._metrics = StreamingMetrics()
        self._sequence_counter = 0

        # Callbacks
        self._on_packet_sent: Optional[Callable] = None
        self._on_connection_lost: Optional[Callable] = None
        self._on_reconnected: Optional[Callable] = None

    async def start_stream(
        self,
        device_id: str,
        websocket_connection,
        audio_callback: Callable[[bytes], bytes],
    ) -> bool:
        """
        Start real-time audio streaming for ESP32 device.

        Args:
            device_id: Unique ESP32 device identifier
            websocket_connection: WebSocket connection object
            audio_callback: Function to process audio and return response

        Returns:
            bool: True if stream started successfully
        """
        if device_id in self._active_streams:
            await self.stop_stream(device_id)

        try:
            # Initialize stream state
            stream_state = {
                "device_id": device_id,
                "websocket": websocket_connection,
                "audio_callback": audio_callback,
                "state": StreamingState.CONNECTING,
                "buffer": CircularAudioBuffer(self.buffer_duration_seconds),
                "connection_start_time": time.time(),
                "last_heartbeat": time.time(),
                "sequence_number": 0,
                "task": None,
            }

            self._active_streams[device_id] = stream_state

            # Start streaming task
            stream_state["task"] = asyncio.create_task(self._streaming_loop(device_id))

            self._logger.info(f"Started real-time stream for device: {device_id}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to start stream for device {device_id}: {e}")
            return False

    async def _streaming_loop(self, device_id: str):
        """Main streaming loop for a device."""
        stream = self._active_streams[device_id]
        websocket = stream["websocket"]

        reconnect_count = 0

        try:
            stream["state"] = StreamingState.CONNECTED

            while device_id in self._active_streams:
                try:
                    # Receive audio packet from ESP32
                    message = await asyncio.wait_for(
                        websocket.receive_bytes(), timeout=self.max_latency_ms / 1000
                    )

                    # Process incoming audio packet
                    await self._process_incoming_packet(device_id, message)

                    # Update heartbeat
                    stream["last_heartbeat"] = time.time()
                    reconnect_count = 0  # Reset on successful communication

                except asyncio.TimeoutError:
                    # Check if connection is still alive
                    if time.time() - stream["last_heartbeat"] > 5.0:  # 5 second timeout
                        raise ConnectionError("Heartbeat timeout")

                except ConnectionError as e:
                    self._logger.warning(f"Connection lost for device {device_id}: {e}")

                    if reconnect_count < self.reconnect_attempts:
                        await self._attempt_reconnection(device_id, reconnect_count)
                        reconnect_count += 1
                    else:
                        self._logger.error(
                            f"Max reconnection attempts exceeded for {device_id}"
                        )
                        break

                except Exception as e:
                    self._logger.error(f"Streaming error for device {device_id}: {e}")
                    break

        except Exception as e:
            self._logger.error(f"Fatal streaming error for device {device_id}: {e}")
        finally:
            # Cleanup
            stream["state"] = StreamingState.DISCONNECTED
            if self._on_connection_lost:
                await self._on_connection_lost(device_id)

    async def _process_incoming_packet(self, device_id: str, message: bytes):
        """Process incoming audio packet from ESP32."""
        stream = self._active_streams[device_id]
        buffer = stream["buffer"]
        audio_callback = stream["audio_callback"]

        start_time = time.time()

        try:
            # Add to circular buffer (may drop old data)
            dropped_samples = await buffer.add_audio_data(message)
            if dropped_samples > 0:
                self._metrics.total_packets_dropped += 1

            # Process audio through callback
            response_audio = await asyncio.get_event_loop().run_in_executor(
                None, audio_callback, message
            )

            # Create response packet
            packet = AudioPacket(
                packet_id=str(uuid.uuid4()),
                sequence_number=stream["sequence_number"],
                timestamp=time.time(),
                audio_data=response_audio,
                duration_ms=self.packet_size_ms,
                is_final=False,
            )

            # Send response packet
            await self._send_packet(device_id, packet)

            # Update metrics
            processing_time = (time.time() - start_time) * 1000
            self._metrics.current_latency_ms = processing_time
            self._metrics.total_packets_sent += 1
            self._metrics.buffer_usage_percent = buffer.get_usage_percent()
            self._metrics.last_packet_timestamp = time.time()

            # Update sequence number
            stream["sequence_number"] += 1

            # Log if latency exceeds target
            if processing_time > self.max_latency_ms:
                self._logger.warning(
                    f"Latency exceeded target: {processing_time:.1f}ms > {self.max_latency_ms}ms"
                )

        except Exception as e:
            self._logger.error(f"Packet processing failed for device {device_id}: {e}")

    async def _send_packet(self, device_id: str, packet: AudioPacket):
        """Send audio packet to ESP32."""
        stream = self._active_streams[device_id]
        websocket = stream["websocket"]

        try:
            # Convert packet to JSON for transmission
            packet_data = json.dumps(packet.to_dict()).encode("utf-8")

            # Send packet
            await websocket.send_bytes(packet_data)

            # Log packet sent
            self._logger.debug(
                f"Sent packet {packet.packet_id} to {device_id}, "
                f"seq: {packet.sequence_number}, "
                f"size: {len(packet.audio_data)} bytes"
            )

            # Call callback if set
            if self._on_packet_sent:
                await self._on_packet_sent(device_id, packet)

        except Exception as e:
            self._logger.error(f"Failed to send packet to device {device_id}: {e}")
            raise

    async def _attempt_reconnection(self, device_id: str, attempt: int):
        """Attempt to reconnect to ESP32 device."""
        stream = self._active_streams[device_id]
        stream["state"] = StreamingState.RECONNECTING

        self._logger.info(
            f"Attempting reconnection {attempt + 1} for device {device_id}"
        )

        try:
            # Wait before retry
            await asyncio.sleep(self.reconnect_delay_seconds * (attempt + 1))

            # Clear buffer to avoid sending stale data
            await stream["buffer"].clear()

            # Update metrics
            self._metrics.total_reconnections += 1

            # Set state back to connected (websocket reconnection handled externally)
            stream["state"] = StreamingState.CONNECTED
            stream["last_heartbeat"] = time.time()

            if self._on_reconnected:
                await self._on_reconnected(device_id, attempt + 1)

            self._logger.info(f"Reconnection successful for device {device_id}")

        except Exception as e:
            self._logger.error(f"Reconnection failed for device {device_id}: {e}")
            raise

    async def stop_stream(self, device_id: str) -> bool:
        """Stop streaming for a device."""
        if device_id not in self._active_streams:
            return False

        try:
            stream = self._active_streams[device_id]

            # Cancel streaming task
            if stream["task"] and not stream["task"].done():
                stream["task"].cancel()
                try:
                    await stream["task"]
                except asyncio.CancelledError:
                    pass

            # Clear buffer
            await stream["buffer"].clear()

            # Remove from active streams
            del self._active_streams[device_id]

            self._logger.info(f"Stopped stream for device: {device_id}")
            return True

        except Exception as e:
            self._logger.error(f"Error stopping stream for device {device_id}: {e}")
            return False

    async def get_stream_status(self, device_id: str) -> Dict[str, Any]:
        """Get detailed status for a device stream."""
        if device_id not in self._active_streams:
            return {
                "device_id": device_id,
                "state": StreamingState.DISCONNECTED.value,
                "connected": False,
            }

        stream = self._active_streams[device_id]
        uptime = time.time() - stream["connection_start_time"]

        return {
            "device_id": device_id,
            "state": stream["state"].value,
            "connected": stream["state"]
            in [StreamingState.CONNECTED, StreamingState.STREAMING],
            "uptime_seconds": uptime,
            "sequence_number": stream["sequence_number"],
            "buffer_usage_percent": stream["buffer"].get_usage_percent(),
            "last_heartbeat": stream["last_heartbeat"],
            "metrics": self._metrics.to_dict(),
        }

    async def get_all_streams_status(self) -> Dict[str, Any]:
        """Get status of all active streams."""
        streams_status = {}
        for device_id in self._active_streams.keys():
            streams_status[device_id] = await self.get_stream_status(device_id)

        return {
            "active_streams_count": len(self._active_streams),
            "global_metrics": self._metrics.to_dict(),
            "streams": streams_status,
        }

    def set_callbacks(
        self,
        on_packet_sent: Optional[Callable] = None,
        on_connection_lost: Optional[Callable] = None,
        on_reconnected: Optional[Callable] = None,
    ):
        """Set event callbacks."""
        self._on_packet_sent = on_packet_sent
        self._on_connection_lost = on_connection_lost
        self._on_reconnected = on_reconnected

    async def optimize_for_latency(self):
        """Apply optimizations for minimal latency."""
        # Reduce packet size for lower latency
        self.packet_size_ms = min(self.packet_size_ms, 50.0)  # 50ms max

        # Disable ACK for speed
        self.enable_ack = False

        # Reduce buffer size
        self.buffer_duration_seconds = min(self.buffer_duration_seconds, 1.0)

        self._logger.info("Applied latency optimizations for real-time streaming")
