"""
Unified TTS (Text-to-Speech) Service Interface
==============================================

Production-ready, comprehensive TTS interface that unifies all TTS functionality
across the entire application. This is the single source of truth for TTS operations.

Key Features:
- Complete voice customization (emotion, gender, quality, language)
- Child safety context integration
- Audio format and quality control
- Comprehensive error handling
- Performance optimization support
- Provider-agnostic design
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

# Import unified audio types - NO DUPLICATES
from src.shared.audio_types import AudioFormat, AudioQuality, VoiceGender, VoiceEmotion


@dataclass
class VoiceProfile:
    """Complete voice configuration."""

    voice_id: str
    name: str
    language: str
    gender: VoiceGender
    age_range: str  # e.g., "adult", "child", "teen"
    description: str
    is_child_safe: bool = True
    supported_emotions: List[VoiceEmotion] = None

    def __post_init__(self):
        if self.supported_emotions is None:
            self.supported_emotions = [VoiceEmotion.NEUTRAL]


@dataclass
class ChildSafetyContext:
    """Child safety context for TTS operations."""

    child_age: Optional[int] = None
    parental_controls: bool = True
    content_filter_level: str = "strict"  # strict, moderate, basic
    blocked_words: List[str] = None

    def __post_init__(self):
        if self.blocked_words is None:
            self.blocked_words = []


@dataclass
class TTSConfiguration:
    """Complete TTS request configuration."""

    voice_profile: VoiceProfile
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    speed: float = 1.0  # 0.25 to 4.0
    pitch: float = 1.0  # 0.5 to 2.0
    volume: float = 1.0  # 0.0 to 1.0
    audio_format: AudioFormat = AudioFormat.MP3
    quality: AudioQuality = AudioQuality.STANDARD
    language: Optional[str] = None  # Override voice language
    stability: float = 0.5  # Voice stability (0.0 to 1.0)
    similarity_boost: float = 0.5  # Voice similarity (0.0 to 1.0)
    use_speaker_boost: bool = False
    optimize_streaming_latency: bool = False


@dataclass
class TTSRequest:
    """Complete TTS request with all parameters."""

    text: str
    config: TTSConfiguration
    safety_context: Optional[ChildSafetyContext] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.request_id is None:
            self.request_id = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


@dataclass
class TTSResult:
    """Complete TTS response with metadata."""

    audio_data: bytes
    request_id: str
    provider_name: str
    config: TTSConfiguration

    # Audio metadata
    duration_seconds: float
    sample_rate: int
    bit_rate: int
    file_size_bytes: int
    format: AudioFormat

    # Performance metrics
    processing_time_ms: float
    provider_latency_ms: float

    # Safety and quality
    content_filtered: bool = False
    safety_warnings: List[str] = None
    quality_score: Optional[float] = None

    # Caching
    cache_key: Optional[str] = None
    cached: bool = False

    # Timestamps
    created_at: datetime = None

    def __post_init__(self):
        if self.safety_warnings is None:
            self.safety_warnings = []
        if self.created_at is None:
            self.created_at = datetime.now()


class TTSError(Exception):
    """Base exception for all TTS errors."""

    def __init__(self, message: str, provider: str = None, request_id: str = None):
        super().__init__(message)
        self.provider = provider
        self.request_id = request_id


class TTSProviderError(TTSError):
    """Error from TTS provider service."""

    pass


class TTSConfigurationError(TTSError):
    """Invalid TTS configuration."""

    pass


class TTSUnsafeContentError(TTSError):
    """Content failed safety checks."""

    pass


class TTSRateLimitError(TTSError):
    """Provider rate limit exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class TTSProviderUnavailableError(TTSError):
    """TTS provider is unavailable."""

    pass


class ITTSService(ABC):
    """
    Unified TTS Service Interface
    ============================

    The single, comprehensive interface that all TTS providers must implement.
    This interface covers all TTS functionality with proper error handling,
    child safety, performance optimization, and extensibility.
    """

    @abstractmethod
    async def synthesize_speech(self, request: TTSRequest) -> TTSResult:
        """
        Synthesize speech from text with complete configuration.

        Args:
            request: Complete TTS request with text, config, and safety context

        Returns:
            TTSResult with audio data and metadata

        Raises:
            TTSProviderError: Provider-specific errors
            TTSConfigurationError: Invalid configuration
            TTSUnsafeContentError: Content failed safety checks
            TTSRateLimitError: Rate limit exceeded
            TTSProviderUnavailableError: Provider unavailable
        """
        pass

    @abstractmethod
    async def get_available_voices(
        self, language: Optional[str] = None, child_safe_only: bool = True
    ) -> List[VoiceProfile]:
        """
        Get available voices, optionally filtered by language and safety.

        Args:
            language: Language code filter (e.g., 'en-US', 'ar-SA')
            child_safe_only: Return only child-safe voices

        Returns:
            List of available voice profiles
        """
        pass

    @abstractmethod
    async def validate_content_safety(
        self, text: str, safety_context: ChildSafetyContext
    ) -> tuple[bool, List[str]]:
        """
        Validate text content for child safety.

        Args:
            text: Text to validate
            safety_context: Child safety requirements

        Returns:
            Tuple of (is_safe, warnings_list)
        """
        pass

    @abstractmethod
    async def estimate_cost(self, request: TTSRequest) -> Dict[str, Any]:
        """
        Estimate cost for TTS request.

        Args:
            request: TTS request to estimate

        Returns:
            Cost estimation details
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check provider health and availability.

        Returns:
            Health status information
        """
        pass

    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get provider information and capabilities.

        Returns:
            Provider metadata and capabilities
        """
        pass

    @abstractmethod
    async def clone_voice(
        self, name: str, audio_samples: List[bytes], safety_context: ChildSafetyContext
    ) -> VoiceProfile:
        """
        Clone a voice from audio samples (if supported by provider).

        Args:
            name: Name for the cloned voice
            audio_samples: Audio samples for cloning
            safety_context: Safety validation context

        Returns:
            Cloned voice profile

        Raises:
            TTSProviderError: If voice cloning not supported or failed
        """
        pass


# Export unified interface and models
__all__ = [
    # Core Interface
    "ITTSService",
    # Data Models
    "TTSRequest",
    "TTSResult",
    "VoiceProfile",
    "TTSConfiguration",
    "ChildSafetyContext",
    # Enums
    "AudioFormat",
    "AudioQuality",
    "VoiceEmotion",
    "VoiceGender",
    # Exceptions
    "TTSError",
    "TTSProviderError",
    "TTSConfigurationError",
    "TTSUnsafeContentError",
    "TTSRateLimitError",
    "TTSProviderUnavailableError",
]
