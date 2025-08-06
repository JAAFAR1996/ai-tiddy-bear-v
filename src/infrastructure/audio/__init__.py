"""
Audio Infrastructure Module
===========================
Production-ready audio services for the AI Teddy Bear application.

This module contains TTS (Text-to-Speech) providers and related audio infrastructure:
- OpenAI TTS Provider (production-ready)
- ElevenLabs TTS Provider (production-ready)
- Azure TTS Provider (future implementation)

All providers implement the unified ITTSService interface and include:
- Full COPPA compliance for child safety
- Comprehensive error handling
- Performance monitoring and metrics
- Cache integration for cost optimization
- Health checks and status monitoring
"""

from .openai_tts_provider import OpenAITTSProvider
from .elevenlabs_tts_provider import ElevenLabsTTSProvider

__all__ = [
    "OpenAITTSProvider",
    "ElevenLabsTTSProvider",
]
