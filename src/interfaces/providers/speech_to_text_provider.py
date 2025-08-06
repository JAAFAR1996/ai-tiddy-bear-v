"""
SpeechToTextProvider interface for all speech-to-text providers.
Depends on: nothing (pure interface)
Security: All implementations must enforce child safety and COPPA compliance at the service layer.
"""

from abc import ABC, abstractmethod


class SpeechToTextProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, language: str = None) -> str:
        """Transcribe audio to text."""
        pass
