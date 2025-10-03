"""
Shared Audio Types - SINGLE SOURCE OF TRUTH
===========================================
Production-ready unified audio type definitions.

WARNING: CRITICAL RULE: ALL shared audio enums MUST be defined here.
    Any duplication or external definition is a BUG and will be removed.

    Specialized enums (TTS-only, Compression-only) go in their specific modules
    with clear "SPECIALIZED" documentation.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List


class AudioFormat(Enum):
    """
    Unified Audio Formats - Production Standard
    ==========================================
    Supported audio formats across the entire application.

    Usage:
    - Domain layer: All general audio processing
    - Application layer: Audio validation, streaming
    - Infrastructure layer: File I/O, conversion

    DO NOT duplicate this enum anywhere else.
    """

    WAV = "wav"  # Uncompressed, high quality
    MP3 = "mp3"  # Common compressed format
    OGG = "ogg"  # Open source compressed
    FLAC = "flac"  # Lossless compression
    AAC = "aac"  # Advanced Audio Codec (for TTS)


class AudioQuality(Enum):
    """
    Unified Audio Quality Levels - Production Standard
    =================================================
    Standard quality levels with technical specifications.
    """

    LOW = "low"  # 16kHz, 64kbps - Basic quality
    STANDARD = "standard"  # 22kHz, 128kbps - Good quality
    HIGH = "high"  # 44kHz, 192kbps - High quality
    PREMIUM = "premium"  # 48kHz, 320kbps - Studio quality


class VoiceGender(Enum):
    """
    Unified Voice Gender Options - Production Standard
    =================================================
    Voice gender classifications for TTS and voice selection.
    """

    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"
    CHILD = "child"  # Special category for child-appropriate voices


class VoiceEmotion(Enum):
    """
    Unified Voice Emotion Styles - Production Standard
    ================================================
    Complete set of voice emotions for child-safe AI interactions.
    """

    # Core emotions (always available)
    NEUTRAL = "neutral"
    HAPPY = "happy"
    CALM = "calm"
    PLAYFUL = "playful"

    # Extended emotions (child-appropriate)
    GENTLE = "gentle"
    ENCOURAGING = "encouraging"
    CARING = "caring"
    EDUCATIONAL = "educational"

    # Limited emotions (age-restricted)
    EXCITED = "excited"
    SAD = "sad"  # Only for appropriate contexts


# Exceptions
class AudioProcessingError(Exception):
    """Base audio processing error."""

    pass


class AudioFormatError(AudioProcessingError):
    """Audio format related error."""

    pass


class AudioValidationError(AudioProcessingError):
    """Audio validation error."""

    pass


class AudioSafetyError(AudioProcessingError):
    """Audio safety violation error."""

    pass


class AudioQualityError(AudioProcessingError):
    """Audio quality error."""

    pass


@dataclass
class AudioMetadata:
    """Production-ready audio metadata."""

    format: AudioFormat
    quality: AudioQuality
    duration_ms: float
    sample_rate: int
    bit_rate: int
    channels: int
    file_size_bytes: int
    is_child_safe: bool = True


@dataclass
class AudioProcessingResult:
    """Complete audio processing result."""

    success: bool
    audio_data: Optional[bytes]
    metadata: Optional[AudioMetadata]
    processing_time_ms: float
    errors: List[str]
    warnings: List[str]
