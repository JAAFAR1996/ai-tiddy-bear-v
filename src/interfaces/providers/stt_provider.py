"""
Speech-to-Text Provider Interface
================================
Interface for STT providers with support for real-time transcription.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class STTResult:
    """Result from speech-to-text transcription."""

    text: str
    language: str
    confidence: float
    processing_time_ms: float
    segments: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class STTError(Exception):
    """Base exception for STT provider errors."""


class ISTTProvider(ABC):
    """Interface for Speech-to-Text providers."""

    @abstractmethod
    async def transcribe(
        self, audio_data: bytes, language: Optional[str] = None
    ) -> STTResult:
        """Transcribe audio data to text."""
        ...

    @abstractmethod
    async def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        ...

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check provider health and return status."""
        ...

    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get provider usage statistics."""
        ...
