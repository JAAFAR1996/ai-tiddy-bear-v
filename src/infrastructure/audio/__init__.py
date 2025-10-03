"""
Audio Infrastructure Module
===========================
Production-ready audio services for the AI Teddy Bear application.

This module contains audio providers and related infrastructure:
- OpenAI TTS Provider (production-ready)
- ElevenLabs TTS Provider (production-ready)
- OpenAI STT Provider (cloud transcription)

All providers implement unified interfaces and include:
- Full COPPA compliance for child safety
- Comprehensive error handling
- Performance monitoring and metrics
- Cache integration for cost optimization
- Health checks and status monitoring
"""

from .openai_tts_provider import OpenAITTSProvider
from .elevenlabs_tts_provider import ElevenLabsTTSProvider
from .openai_stt_provider import OpenAISTTProvider

__all__ = [
    "OpenAITTSProvider",
    "ElevenLabsTTSProvider",
    "OpenAISTTProvider",
]
