"""
ESP32 Chat Server - Production Implementation
===========================================
Real-time chat service for ESP32 AI Teddy Bear devices.

Features:
- WebSocket communication with ESP32 devices
- Real-time audio processing (Speech-to-Text-to-AI-to-Speech)
- Child safety integration
- Session management
- COPPA compliance
- Production monitoring and logging
"""

import asyncio
import json
import logging
import uuid
import re
import base64
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from fastapi import WebSocket, HTTPException, status
from fastapi.websockets import WebSocketState

from src.shared.audio_types import AudioFormat, AudioProcessingError
from src.shared.dto.ai_response import AIResponse


def validate_device_id(device_id: str) -> bool:
    """Validate ESP32 device ID format."""
    # ESP32 device ID should be alphanumeric, 8-32 characters
    if not device_id or len(device_id) < 8 or len(device_id) > 32:
        return False
    return re.match(r"^[a-zA-Z0-9_-]+$", device_id) is not None


class ProductionConfig:
    """Production configuration class."""

    ESP32_SESSION_TIMEOUT = "30"
    ESP32_MAX_SESSIONS = "100"
    ESP32_AUDIO_MAX_DURATION = "30"
    ESP32_AUDIO_CHUNK_SIZE = "4096"
    ESP32_AUDIO_SAMPLE_RATE = "16000"


def get_config():
    """Get configuration - production ready."""
    from src.infrastructure.config.production_config import get_config as get_loaded_config
    return get_loaded_config()


logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """ESP32 session status."""

    CONNECTING = "connecting"
    ACTIVE = "active"
    IDLE = "idle"
    DISCONNECTING = "disconnecting"
    TERMINATED = "terminated"


class MessageType(Enum):
    """ESP32 message types."""

    AUDIO_START = "audio_start"
    AUDIO_CHUNK = "audio_chunk"
    AUDIO_END = "audio_end"
    TEXT_MESSAGE = "text_message"
    SYSTEM_STATUS = "system_status"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class ESP32Session:
    """ESP32 device session."""

    session_id: str
    device_id: str
    child_id: str
    child_name: str
    child_age: int
    websocket: WebSocket
    status: SessionStatus = SessionStatus.CONNECTING
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    total_audio_duration: float = 0.0
    current_audio_session: Optional[str] = None

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session is expired."""
        return (datetime.now() - self.last_activity).total_seconds() > (
            timeout_minutes * 60
        )


@dataclass
class AudioMessage:
    """Audio message from ESP32."""

    session_id: str
    chunk_id: str
    audio_data: bytes
    is_final: bool
    timestamp: datetime = field(default_factory=datetime.now)
    format: str = AudioFormat.WAV.value
    sample_rate: int = 16000


@dataclass
class AudioSession:
    """Audio processing session."""

    session_id: str
    audio_session_id: str
    chunks: List[bytes] = field(default_factory=list)
    total_duration: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)
    is_complete: bool = False


class ESP32ChatServer:
    """
    Production ESP32 Chat Server.

    Handles real-time communication with ESP32 AI Teddy Bear devices:
    - WebSocket connection management
    - Audio processing pipeline
    - Child safety integration
    - Session management
    - Production monitoring
    """

    def __init__(
        self,
        *,
        config,
        stt_provider=None,
        tts_service=None,
        ai_service=None,
        safety_service=None,
    ):
        """Initialize with explicit config injection (production-grade)"""
        if config is None:
            raise RuntimeError("ESP32ChatServer requires config parameter - no fallback allowed in production")
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Core services - will be injected in production
        self.stt_provider = stt_provider
        self.tts_service = tts_service
        self.ai_service = ai_service
        self.safety_service = safety_service

        # Session management
        self.active_sessions: Dict[str, ESP32Session] = {}
        self.device_sessions: Dict[str, str] = {}  # device_id -> session_id

        # Audio processing
        self.audio_buffers: Dict[str, List[bytes]] = {}
        self.audio_sessions: Dict[str, AudioSession] = {}

        # Configuration
        self.session_timeout_minutes = int(
            getattr(self.config, "ESP32_SESSION_TIMEOUT", 30)
        )
        self.max_sessions = int(getattr(self.config, "ESP32_MAX_SESSIONS", 100))
        self.audio_max_duration = int(
            getattr(self.config, "ESP32_AUDIO_MAX_DURATION", 30)
        )  # seconds

        # Background tasks (will be started when needed)
        self.cleanup_task: Optional[asyncio.Task] = None
        self._background_tasks_started = False

        self.logger.info("ESP32 Chat Server initialized")

    def inject_services(
        self, stt_provider, tts_service, ai_service, safety_service
    ) -> None:
        """Inject production services with validation."""
        # Validate all required services are provided
        if not stt_provider:
            raise ValueError("STT provider is required for production deployment")
        if not tts_service:
            raise ValueError("TTS service is required for production deployment")
        if not ai_service:
            raise ValueError("AI service is required for production deployment")
        if not safety_service:
            raise ValueError("Safety service is required for production deployment")
            
        self.stt_provider = stt_provider
        self.tts_service = tts_service
        self.ai_service = ai_service
        self.safety_service = safety_service
        self.logger.info("Production services injected and validated successfully")

    def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        if not self._background_tasks_started:
            try:
                self.cleanup_task = asyncio.create_task(self._cleanup_sessions_loop())
                self._background_tasks_started = True
                self.logger.info("Background tasks started")
            except RuntimeError:
                # No event loop running - tasks will be started when first connection comes
                self.logger.debug(
                    "No event loop running - background tasks will be started later"
                )
                pass

    async def connect_device(
        self,
        websocket: WebSocket,
        device_id: str,
        child_id: str,
        child_name: str,
        child_age: int,
    ) -> str:
        """
        Connect ESP32 device and create session.

        Args:
            websocket: WebSocket connection
            device_id: Unique ESP32 device identifier
            child_id: Child profile identifier
            child_name: Child's name
            child_age: Child's age (3-13 for COPPA)

        Returns:
            Session ID

        Raises:
            HTTPException: If connection fails validation
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Start background tasks if not already started
            self._start_background_tasks()

            # COPPA age validation
            if not (3 <= child_age <= 13):
                self.logger.warning(f"[{correlation_id}] Invalid age: {child_age}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Child age must be 3-13 for COPPA compliance",
                )

            # Device validation
            if not validate_device_id(device_id):
                # Sanitize device_id for logging
                safe_device_id = (
                    device_id.replace("\n", "").replace("\r", "")[:50]
                    if device_id
                    else "None"
                )
                self.logger.warning(
                    f"[{correlation_id}] Invalid device ID: {safe_device_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid device identifier",
                )

            # Check session limits
            if len(self.active_sessions) >= self.max_sessions:
                self.logger.warning(f"[{correlation_id}] Session limit exceeded")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Maximum sessions exceeded",
                )

            # Check if device already connected
            if device_id in self.device_sessions:
                old_session_id = self.device_sessions[device_id]
                await self._terminate_session(old_session_id, "device_reconnection")

            # Accept WebSocket connection
            await websocket.accept()

            # Create session
            session_id = str(uuid.uuid4())
            session = ESP32Session(
                session_id=session_id,
                device_id=device_id,
                child_id=child_id,
                child_name=child_name,
                child_age=child_age,
                websocket=websocket,
                status=SessionStatus.ACTIVE,
            )

            # Store session
            self.active_sessions[session_id] = session
            self.device_sessions[device_id] = session_id

            # Send welcome message
            await self._send_system_message(
                session_id,
                {
                    "type": "connection_established",
                    "session_id": session_id,
                    "message": f"Hello {child_name}! I'm ready to chat!",
                    "server_time": datetime.now().isoformat(),
                },
            )

            self.logger.info(
                f"[{correlation_id}] ESP32 device connected",
                extra={
                    "session_id": session_id,
                    "device_id": device_id,
                    "child_id": child_id,
                    "child_age": child_age,
                },
            )

            return session_id

        except Exception as e:
            self.logger.error(
                f"[{correlation_id}] ESP32 connection failed: {e}", exc_info=True
            )
            try:
                await websocket.close(code=1011, reason=str(e))
            except Exception:
                pass
            raise

    async def handle_message(self, session_id: str, raw_message: str) -> None:
        """
        Handle incoming message from ESP32 device.

        Args:
            session_id: Session identifier
            raw_message: Raw JSON message from ESP32
        """
        session = self.active_sessions.get(session_id)
        if not session:
            # Sanitize session_id for logging
            safe_session_id = (
                session_id.replace("\n", "").replace("\r", "")[:50]
                if session_id
                else "None"
            )
            self.logger.warning(f"Message from unknown session: {safe_session_id}")
            return

        try:
            # Parse message
            message_data = json.loads(raw_message)
            message_type = MessageType(message_data.get("type"))

            # Update session activity
            session.update_activity()
            session.message_count += 1

            # Route message based on type
            if message_type == MessageType.AUDIO_START:
                await self._handle_audio_start(session, message_data)
            elif message_type == MessageType.AUDIO_CHUNK:
                await self._handle_audio_chunk(session, message_data)
            elif message_type == MessageType.AUDIO_END:
                await self._handle_audio_end(session, message_data)
            elif message_type == MessageType.TEXT_MESSAGE:
                await self._handle_text_message(session, message_data)
            elif message_type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(session, message_data)
            elif message_type == MessageType.SYSTEM_STATUS:
                await self._handle_system_status(session, message_data)
            else:
                self.logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            # Sanitize session_id and error for logging
            safe_session_id = (
                session_id.replace("\n", "").replace("\r", "")[:50]
                if session_id
                else "None"
            )
            safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
            self.logger.error(
                f"Invalid JSON from session {safe_session_id}: {safe_error}"
            )
            await self._send_error(session_id, "invalid_json", "Invalid message format")
        except Exception as e:
            # Sanitize session_id and error for logging
            safe_session_id = (
                session_id.replace("\n", "").replace("\r", "")[:50]
                if session_id
                else "None"
            )
            safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
            self.logger.error(
                f"Message handling error for session {safe_session_id}: {safe_error}",
                exc_info=True,
            )
            await self._send_error(
                session_id, "processing_error", "Message processing failed"
            )

    async def _handle_audio_start(
        self, session: ESP32Session, message_data: Dict[str, Any]
    ) -> None:
        """Handle audio session start from ESP32."""
        try:
            audio_session_id = str(uuid.uuid4())
            
            # Create new audio session
            audio_session = AudioSession(
                session_id=session.session_id,
                audio_session_id=audio_session_id,
            )
            
            self.audio_sessions[audio_session_id] = audio_session
            session.current_audio_session = audio_session_id
            
            # Initialize audio buffer
            if session.session_id not in self.audio_buffers:
                self.audio_buffers[session.session_id] = []
            
            self.logger.info(
                f"Audio session started: {audio_session_id}",
                extra={
                    "session_id": session.session_id,
                    "device_id": session.device_id,
                    "child_id": session.child_id,
                },
            )
            
            # Send acknowledgment
            await self._send_system_message(
                session.session_id,
                {
                    "type": "audio_start_ack",
                    "audio_session_id": audio_session_id,
                    "status": "ready",
                },
            )
            
        except Exception as e:
            self.logger.error(f"Audio start handling failed: {e}", exc_info=True)
            await self._send_error(
                session.session_id, "audio_start_error", "Failed to start audio session"
            )

    async def _handle_audio_chunk(
        self, session: ESP32Session, message_data: Dict[str, Any]
    ) -> None:
        """
        Handle audio chunk from ESP32 - PRODUCTION IMPLEMENTATION.
        
        Complete audio processing pipeline:
        1. Receive and validate audio chunk
        2. Buffer audio data
        3. Process when complete
        4. Speech-to-Text conversion
        5. AI response generation
        6. Text-to-Speech conversion
        7. Send audio response back to ESP32
        """
        try:
            # Extract audio data
            audio_data_b64 = message_data.get("audio_data")
            chunk_id = message_data.get("chunk_id", str(uuid.uuid4()))
            is_final = message_data.get("is_final", False)
            audio_session_id = message_data.get("audio_session_id")
            
            if not audio_data_b64:
                await self._send_error(
                    session.session_id, "missing_audio_data", "No audio data provided"
                )
                return
            
            # Decode base64 audio data
            try:
                audio_data = base64.b64decode(audio_data_b64)
            except Exception as e:
                self.logger.error(f"Failed to decode audio data: {e}")
                await self._send_error(
                    session.session_id, "invalid_audio_data", "Invalid audio encoding"
                )
                return
            
            # Validate audio session
            if audio_session_id and audio_session_id in self.audio_sessions:
                audio_session = self.audio_sessions[audio_session_id]
                audio_session.chunks.append(audio_data)
            else:
                # Fallback: use session buffer
                if session.session_id not in self.audio_buffers:
                    self.audio_buffers[session.session_id] = []
                self.audio_buffers[session.session_id].append(audio_data)
            
            # Log chunk received
            self.logger.debug(
                f"Audio chunk received: {len(audio_data)} bytes, final: {is_final}",
                extra={
                    "session_id": session.session_id,
                    "chunk_id": chunk_id,
                    "audio_session_id": audio_session_id,
                },
            )
            
            # If this is the final chunk, process the complete audio
            if is_final:
                await self._process_complete_audio(session, audio_session_id)
            
        except Exception as e:
            self.logger.error(f"Audio chunk handling failed: {e}", exc_info=True)
            await self._send_error(
                session.session_id, "audio_chunk_error", "Failed to process audio chunk"
            )

    async def _handle_audio_end(
        self, session: ESP32Session, message_data: Dict[str, Any]
    ) -> None:
        """Handle audio session end from ESP32."""
        try:
            audio_session_id = message_data.get("audio_session_id")
            
            if audio_session_id and audio_session_id in self.audio_sessions:
                audio_session = self.audio_sessions[audio_session_id]
                audio_session.is_complete = True
                
                # Process the complete audio
                await self._process_complete_audio(session, audio_session_id)
            else:
                # Fallback: process buffered audio
                await self._process_complete_audio(session, None)
            
        except Exception as e:
            self.logger.error(f"Audio end handling failed: {e}", exc_info=True)
            await self._send_error(
                session.session_id, "audio_end_error", "Failed to end audio session"
            )

    async def _process_complete_audio(
        self, session: ESP32Session, audio_session_id: Optional[str]
    ) -> None:
        """
        Process complete audio through the full pipeline.
        
        PRODUCTION AUDIO PROCESSING PIPELINE:
        1. Combine audio chunks
        2. Validate audio quality and safety
        3. Speech-to-Text conversion (Whisper)
        4. Content safety check
        5. AI response generation
        6. Text-to-Speech conversion
        7. Send audio response to ESP32
        """
        correlation_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        try:
            # Step 1: Combine audio chunks
            if audio_session_id and audio_session_id in self.audio_sessions:
                audio_session = self.audio_sessions[audio_session_id]
                audio_chunks = audio_session.chunks
            else:
                audio_chunks = self.audio_buffers.get(session.session_id, [])
            
            if not audio_chunks:
                self.logger.warning(f"No audio data to process for session {session.session_id}")
                await self._send_error(
                    session.session_id, "no_audio_data", "No audio data received"
                )
                return
            
            # Combine all chunks into single audio data
            complete_audio = b"".join(audio_chunks)
            
            self.logger.info(
                f"[{correlation_id}] Processing complete audio: {len(complete_audio)} bytes",
                extra={
                    "session_id": session.session_id,
                    "child_id": session.child_id,
                    "child_age": session.child_age,
                    "chunks_count": len(audio_chunks),
                },
            )
            
            # Step 2: Validate audio (basic checks)
            if len(complete_audio) < 1000:  # Minimum audio size
                await self._send_error(
                    session.session_id, "audio_too_short", "Audio too short to process"
                )
                return
            
            if len(complete_audio) > 10 * 1024 * 1024:  # Maximum 10MB
                await self._send_error(
                    session.session_id, "audio_too_large", "Audio file too large"
                )
                return
            
            # Step 3: Speech-to-Text conversion
            if not self.stt_provider:
                self.logger.error("STT provider not available")
                await self._send_fallback_response(session, "I'm having trouble hearing you right now.")
                return
            
            try:
                stt_result = await self.stt_provider.transcribe(
                    complete_audio, language="auto"
                )
                
                # Extract text from result
                if hasattr(stt_result, "text"):
                    transcribed_text = stt_result.text.strip()
                    confidence = getattr(stt_result, "confidence", 0.8)
                else:
                    transcribed_text = str(stt_result).strip()
                    confidence = 0.8
                
                if not transcribed_text:
                    await self._send_fallback_response(session, "I didn't hear anything. Can you try again?")
                    return
                
                self.logger.info(
                    f"[{correlation_id}] STT completed: '{transcribed_text[:100]}...'",
                    extra={
                        "session_id": session.session_id,
                        "confidence": confidence,
                        "text_length": len(transcribed_text),
                    },
                )
                
            except Exception as e:
                self.logger.error(f"STT processing failed: {e}", exc_info=True)
                await self._send_fallback_response(session, "I'm having trouble understanding you. Can you speak a bit louder?")
                return
            
            # Step 4: Content safety check
            if self.safety_service:
                try:
                    is_safe = await self.safety_service.check_content(
                        transcribed_text, session.child_age
                    )
                    
                    if not is_safe:
                        self.logger.warning(
                            f"[{correlation_id}] Unsafe content detected",
                            extra={
                                "session_id": session.session_id,
                                "child_id": session.child_id,
                            },
                        )
                        await self._send_fallback_response(
                            session, "Let's talk about something else! What's your favorite animal?"
                        )
                        return
                        
                except Exception as e:
                    self.logger.error(f"Safety check failed: {e}", exc_info=True)
                    # Continue processing but log the error
            
            # Step 5: AI response generation
            if not self.ai_service:
                self.logger.error("AI service not available")
                await self._send_fallback_response(session, "I'm thinking... Can you tell me more?")
                return
            
            try:
                # Create child preferences (basic)
                child_preferences = None  # Could be loaded from database
                
                # Generate AI response
                ai_response = await self.ai_service.generate_safe_response(
                    child_id=UUID(session.child_id),
                    user_input=transcribed_text,
                    child_age=session.child_age,
                    preferences=child_preferences,
                    conversation_context=None,  # Could include recent conversation
                )
                
                if not ai_response or not ai_response.content:
                    await self._send_fallback_response(session, "That's interesting! Tell me more!")
                    return
                
                response_text = ai_response.content.strip()
                
                self.logger.info(
                    f"[{correlation_id}] AI response generated: '{response_text[:100]}...'",
                    extra={
                        "session_id": session.session_id,
                        "response_length": len(response_text),
                    },
                )
                
            except Exception as e:
                self.logger.error(f"AI response generation failed: {e}", exc_info=True)
                await self._send_fallback_response(session, "That's really cool! What else would you like to talk about?")
                return
            
            # Step 6: Text-to-Speech conversion
            if not self.tts_service:
                self.logger.error("TTS service not available")
                # Send text response as fallback
                await self._send_text_response(session, response_text)
                return
            
            try:
                # Convert response to speech
                if hasattr(self.tts_service, 'convert_text_to_speech'):
                    # AudioService interface
                    tts_audio = await self.tts_service.convert_text_to_speech(
                        response_text,
                        voice_settings={
                            "voice_id": "alloy",  # Child-friendly voice
                            "speed": 1.0,
                            "emotion": "happy",
                        },
                    )
                elif hasattr(self.tts_service, 'synthesize_speech'):
                    # ITTSService interface
                    from src.interfaces.providers.tts_provider import (
                        TTSRequest, TTSConfiguration, VoiceProfile, ChildSafetyContext
                    )
                    from src.shared.audio_types import VoiceGender, VoiceEmotion, AudioFormat, AudioQuality
                    
                    # Create TTS request
                    voice_profile = VoiceProfile(
                        voice_id="alloy",
                        name="Child-friendly Voice",
                        language="en-US",
                        gender=VoiceGender.NEUTRAL,
                        age_range="adult",
                        description="Child-friendly voice for AI teddy bear",
                        is_child_safe=True,
                    )
                    
                    config = TTSConfiguration(
                        voice_profile=voice_profile,
                        emotion=VoiceEmotion.HAPPY,
                        speed=1.0,
                        audio_format=AudioFormat.MP3,
                        quality=AudioQuality.STANDARD,
                    )
                    
                    safety_context = ChildSafetyContext(
                        child_age=session.child_age,
                        parental_controls=True,
                        content_filter_level="strict",
                    )
                    
                    request = TTSRequest(
                        text=response_text,
                        config=config,
                        safety_context=safety_context,
                    )
                    
                    tts_result = await self.tts_service.synthesize_speech(request)
                    tts_audio = tts_result.audio_data
                else:
                    # Fallback - assume it's a simple callable
                    tts_audio = await self.tts_service(response_text)
                
                if not tts_audio:
                    await self._send_text_response(session, response_text)
                    return
                
                # Step 7: Send audio response to ESP32
                await self._send_audio_response(session, tts_audio, response_text)
                
                processing_time = (datetime.now() - start_time).total_seconds()
                
                self.logger.info(
                    f"[{correlation_id}] Audio processing completed successfully",
                    extra={
                        "session_id": session.session_id,
                        "processing_time_seconds": processing_time,
                        "input_text": transcribed_text[:100],
                        "output_text": response_text[:100],
                        "audio_size_bytes": len(tts_audio) if isinstance(tts_audio, bytes) else 0,
                    },
                )
                
            except Exception as e:
                self.logger.error(f"TTS processing failed: {e}", exc_info=True)
                # Send text response as fallback
                await self._send_text_response(session, response_text)
                return
            
        except Exception as e:
            self.logger.error(
                f"[{correlation_id}] Audio processing pipeline failed: {e}",
                exc_info=True,
            )
            await self._send_fallback_response(session, "I'm having some trouble right now. Can you try again?")
        
        finally:
            # Cleanup audio session
            if audio_session_id and audio_session_id in self.audio_sessions:
                del self.audio_sessions[audio_session_id]
            
            # Clear audio buffer
            if session.session_id in self.audio_buffers:
                self.audio_buffers[session.session_id] = []
            
            # Reset current audio session
            session.current_audio_session = None

    async def _send_audio_response(
        self, session: ESP32Session, audio_data: bytes, text: str
    ) -> None:
        """Send audio response to ESP32."""
        try:
            # Encode audio as base64
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
            
            response_message = {
                "type": "audio_response",
                "audio_data": audio_b64,
                "text": text,
                "format": "mp3",
                "sample_rate": 22050,
                "timestamp": datetime.now().isoformat(),
            }
            
            await session.websocket.send_text(json.dumps(response_message))
            
            self.logger.info(
                f"Audio response sent: {len(audio_data)} bytes",
                extra={
                    "session_id": session.session_id,
                    "text_length": len(text),
                },
            )
            
        except Exception as e:
            self.logger.error(f"Failed to send audio response: {e}", exc_info=True)
            # Fallback to text response
            await self._send_text_response(session, text)

    async def _send_text_response(self, session: ESP32Session, text: str) -> None:
        """Send text response to ESP32 as fallback."""
        try:
            response_message = {
                "type": "text_response",
                "text": text,
                "timestamp": datetime.now().isoformat(),
            }
            
            await session.websocket.send_text(json.dumps(response_message))
            
            self.logger.info(
                f"Text response sent: '{text[:100]}...'",
                extra={"session_id": session.session_id},
            )
            
        except Exception as e:
            self.logger.error(f"Failed to send text response: {e}", exc_info=True)

    async def _send_fallback_response(self, session: ESP32Session, message: str) -> None:
        """Send fallback response when processing fails."""
        await self._send_text_response(session, message)

    async def _handle_text_message(
        self, session: ESP32Session, message_data: Dict[str, Any]
    ) -> None:
        """Handle text message from ESP32 (not used for teddy bear, but kept for completeness)."""
        try:
            text = message_data.get("text", "").strip()
            
            if not text:
                await self._send_error(
                    session.session_id, "empty_text", "No text provided"
                )
                return
            
            self.logger.info(
                f"Text message received: '{text[:100]}...'",
                extra={"session_id": session.session_id},
            )
            
            # For teddy bear, we primarily use audio, but this could be used for debugging
            await self._send_text_response(session, f"I received your text: {text}")
            
        except Exception as e:
            self.logger.error(f"Text message handling failed: {e}", exc_info=True)
            await self._send_error(
                session.session_id, "text_processing_error", "Failed to process text message"
            )

    async def _handle_heartbeat(
        self, session: ESP32Session, message_data: Dict[str, Any]
    ) -> None:
        """Handle heartbeat message."""
        await self._send_system_message(
            session.session_id,
            {
                "type": "heartbeat_response",
                "timestamp": datetime.now().isoformat(),
                "session_status": session.status.value,
            },
        )

    async def _handle_system_status(
        self, session: ESP32Session, message_data: Dict[str, Any]
    ) -> None:
        """Handle system status message."""
        # Log ESP32 device status for monitoring
        self.logger.info(
            "ESP32 system status",
            extra={
                "session_id": session.session_id,
                "device_id": session.device_id,
                "status": message_data,
            },
        )

    async def _send_system_message(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Send system message to ESP32."""
        session = self.active_sessions.get(session_id)
        if not session or session.websocket.client_state != WebSocketState.CONNECTED:
            return False

        try:
            message = {
                "type": "system",
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }

            await session.websocket.send_text(json.dumps(message))
            return True

        except Exception as e:
            # Sanitize session_id and error for logging
            safe_session_id = (
                session_id.replace("\n", "").replace("\r", "")[:50]
                if session_id
                else "None"
            )
            safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
            self.logger.error(
                f"Failed to send system message to {safe_session_id}: {safe_error}"
            )
            await self._terminate_session(session_id, "send_error")
            return False

    async def _send_error(
        self, session_id: str, error_code: str, error_message: str
    ) -> bool:
        """Send error message to ESP32."""
        session = self.active_sessions.get(session_id)
        if not session:
            return False

        try:
            error_msg = {
                "type": "error",
                "error_code": error_code,
                "error_message": error_message,
                "timestamp": datetime.now().isoformat(),
            }

            await session.websocket.send_text(json.dumps(error_msg))
            return True

        except Exception as e:
            # Sanitize session_id and error for logging
            safe_session_id = (
                session_id.replace("\n", "").replace("\r", "")[:50]
                if session_id
                else "None"
            )
            safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
            self.logger.error(
                f"Failed to send error to {safe_session_id}: {safe_error}"
            )
            return False

    async def disconnect_device(
        self, session_id: str, reason: str = "normal_closure"
    ) -> None:
        """Disconnect ESP32 device and cleanup session."""
        await self._terminate_session(session_id, reason)

    async def _terminate_session(self, session_id: str, reason: str) -> None:
        """Terminate ESP32 session and cleanup resources."""
        session = self.active_sessions.get(session_id)
        if not session:
            return

        try:
            # Update session status
            session.status = SessionStatus.TERMINATED

            # Close WebSocket
            if session.websocket.client_state == WebSocketState.CONNECTED:
                await session.websocket.close(code=1000, reason=reason)

            # Cleanup resources
            if session.device_id in self.device_sessions:
                del self.device_sessions[session.device_id]

            if session_id in self.audio_buffers:
                del self.audio_buffers[session_id]

            # Cleanup audio sessions
            audio_sessions_to_remove = [
                audio_id
                for audio_id, audio_session in self.audio_sessions.items()
                if audio_session.session_id == session_id
            ]
            for audio_id in audio_sessions_to_remove:
                del self.audio_sessions[audio_id]

            # Remove session
            del self.active_sessions[session_id]

            self.logger.info(
                "ESP32 session terminated",
                extra={
                    "session_id": session_id,
                    "device_id": session.device_id,
                    "reason": reason,
                    "duration_minutes": (
                        datetime.now() - session.created_at
                    ).total_seconds()
                    / 60,
                    "message_count": session.message_count,
                },
            )

        except Exception as e:
            self.logger.error(f"Session termination error: {e}", exc_info=True)

    async def _cleanup_sessions_loop(self) -> None:
        """Background task to cleanup expired sessions."""
        while True:
            try:
                expired_sessions = []

                for session_id, session in self.active_sessions.items():
                    if session.is_expired(self.session_timeout_minutes):
                        expired_sessions.append(session_id)

                # Cleanup expired sessions
                for session_id in expired_sessions:
                    await self._terminate_session(session_id, "timeout")

                if expired_sessions:
                    self.logger.info(
                        f"Cleaned up {len(expired_sessions)} expired sessions"
                    )

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                self.logger.error(f"Session cleanup error: {e}", exc_info=True)
                await asyncio.sleep(30)  # Shorter retry on error

    def get_session_metrics(self) -> Dict[str, Any]:
        """Get current session metrics."""
        active_count = len(self.active_sessions)
        total_messages = sum(
            session.message_count for session in self.active_sessions.values()
        )

        return {
            "active_sessions": active_count,
            "max_sessions": self.max_sessions,
            "total_messages": total_messages,
            "session_timeout_minutes": self.session_timeout_minutes,
            "devices_connected": len(self.device_sessions),
            "audio_sessions": len(self.audio_sessions),
            "services_status": {
                "stt_provider": self.stt_provider is not None,
                "tts_service": self.tts_service is not None,
                "ai_service": self.ai_service is not None,
                "safety_service": self.safety_service is not None,
            },
            "timestamp": datetime.now().isoformat(),
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for ESP32 Chat Server."""
        try:
            session_count = len(self.active_sessions)
            cleanup_running = self.cleanup_task and not self.cleanup_task.done()

            # Check service availability
            services_healthy = all([
                self.stt_provider is not None,
                self.tts_service is not None,
                self.ai_service is not None,
                self.safety_service is not None,
            ])

            status = "healthy" if cleanup_running and services_healthy else "degraded"

            return {
                "status": status,
                "active_sessions": session_count,
                "max_sessions": self.max_sessions,
                "cleanup_task_running": cleanup_running,
                "services_available": {
                    "stt_provider": self.stt_provider is not None,
                    "tts_service": self.tts_service is not None,
                    "ai_service": self.ai_service is not None,
                    "safety_service": self.safety_service is not None,
                },
                "metrics": self.get_session_metrics(),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def shutdown(self) -> None:
        """Shutdown ESP32 Chat Server."""
        self.logger.info("Shutting down ESP32 Chat Server")

        # Cancel background tasks
        if self.cleanup_task:
            self.cleanup_task.cancel()

        # Terminate all sessions
        session_ids = list(self.active_sessions.keys())
        for session_id in session_ids:
            await self._terminate_session(session_id, "server_shutdown")

        self.logger.info("ESP32 Chat Server shutdown complete")


class _ESP32ServerProxy:
    """Back-compat proxy: keeps the old import path but defers real instance injection."""
    __slots__ = ("_inst",)
    def __init__(self):
        self._inst = None

    def set(self, inst):
        self._inst = inst

    def __getattr__(self, name):
        if self._inst is None:
            raise RuntimeError(
                "ESP32ChatServer not initialized yet (proxy). "
                "Initialize via ESP32ServiceFactory before use."
            )
        return getattr(self._inst, name)

# Exported symbol for old imports:
esp32_chat_server = _ESP32ServerProxy()
