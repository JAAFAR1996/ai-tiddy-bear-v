"""External service interfaces for dependency inversion.

All external service contracts are defined here to eliminate direct dependencies
on third-party services and ensure proper abstraction boundaries.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, AsyncIterator
from dataclasses import dataclass
import numpy as np


@dataclass
class TranscriptionResult:
    """Result from speech-to-text transcription."""
    text: str
    confidence: float
    language: str
    duration: float
    

# TTSResult DELETED - use unified TTSResult from tts_provider.py


class IOpenAIService(ABC):
    """Interface for OpenAI API integration."""
    
    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 150,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate text completion using OpenAI API."""
        pass
    
    @abstractmethod
    async def generate_embedding(
        self,
        text: str,
        model: str = "text-embedding-ada-002"
    ) -> List[float]:
        """Generate embedding vector for text."""
        pass
    
    @abstractmethod
    async def transcribe_audio(
        self,
        audio_data: bytes,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """Transcribe audio to text using Whisper."""
        pass
    
    @abstractmethod
    async def moderate_content(self, text: str) -> Dict[str, Any]:
        """Check content for safety using moderation API."""
        pass


class IAnthropicService(ABC):
    """Interface for Anthropic Claude API integration."""
    
    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        model: str = "claude-3-sonnet-20240229",
        temperature: float = 0.7,
        max_tokens: int = 150
    ) -> str:
        """Generate text completion using Claude API."""
        pass
    
    @abstractmethod
    async def analyze_image(
        self,
        image_data: bytes,
        prompt: str
    ) -> str:
        """Analyze image content with Claude Vision."""
        pass


class IGoogleAIService(ABC):
    """Interface for Google AI services."""
    
    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        model: str = "gemini-pro",
        temperature: float = 0.7
    ) -> str:
        """Generate text using Gemini API."""
        pass
    
    # text_to_speech DELETED - use unified ITTSService from tts_provider.py
    
    @abstractmethod
    async def speech_to_text(
        self,
        audio_data: bytes,
        language_code: str = "en-US"
    ) -> TranscriptionResult:
        """Convert speech to text using Google STT."""
        pass


# IElevenLabsService DELETED - use unified ITTSService from tts_provider.py

class IElevenLabsService(ABC):
    """Interface for ElevenLabs voice synthesis - NON-TTS FEATURES ONLY."""
    
    @abstractmethod
    async def get_user_subscription(self) -> Dict[str, Any]:
        """Get user subscription details."""
        pass
    
    @abstractmethod
    async def get_user_info(self) -> Dict[str, Any]:
        """Get user account information."""
        pass


class IPineconeService(ABC):
    """Interface for Pinecone vector database."""
    
    @abstractmethod
    async def upsert_vectors(
        self,
        vectors: List[Dict[str, Any]],
        namespace: Optional[str] = None
    ) -> Dict[str, int]:
        """Insert or update vectors in index."""
        pass
    
    @abstractmethod
    async def query_vectors(
        self,
        vector: List[float],
        top_k: int = 10,
        namespace: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query similar vectors."""
        pass
    
    @abstractmethod
    async def delete_vectors(
        self,
        ids: List[str],
        namespace: Optional[str] = None
    ) -> Dict[str, int]:
        """Delete vectors by ID."""
        pass


class IWebSearchService(ABC):
    """Interface for web search capabilities."""
    
    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        safe_search: bool = True
    ) -> List[Dict[str, Any]]:
        """Search the web for information."""
        pass
    
    @abstractmethod
    async def get_news(
        self,
        topic: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Get latest news on a topic."""
        pass


class IWeatherService(ABC):
    """Interface for weather information."""
    
    @abstractmethod
    async def get_current_weather(
        self,
        location: str
    ) -> Dict[str, Any]:
        """Get current weather for location."""
        pass
    
    @abstractmethod
    async def get_forecast(
        self,
        location: str,
        days: int = 5
    ) -> List[Dict[str, Any]]:
        """Get weather forecast."""
        pass


class ITranslationService(ABC):
    """Interface for language translation."""
    
    @abstractmethod
    async def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None
    ) -> str:
        """Translate text between languages."""
        pass
    
    @abstractmethod
    async def detect_language(self, text: str) -> str:
        """Detect language of text."""
        pass
    
    @abstractmethod
    async def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages."""
        pass


class IImageGenerationService(ABC):
    """Interface for AI image generation."""
    
    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        style: Optional[str] = None
    ) -> bytes:
        """Generate image from text prompt."""
        pass
    
    @abstractmethod
    async def edit_image(
        self,
        image: bytes,
        mask: bytes,
        prompt: str
    ) -> bytes:
        """Edit image with AI."""
        pass
    
    @abstractmethod
    async def create_variations(
        self,
        image: bytes,
        n: int = 1
    ) -> List[bytes]:
        """Create variations of an image."""
        pass


class IEmailService(ABC):
    """Interface for email delivery."""
    
    @abstractmethod
    async def send_email(
        self,
        to: Union[str, List[str]],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send email message."""
        pass
    
    @abstractmethod
    async def send_template_email(
        self,
        to: Union[str, List[str]],
        template_id: str,
        template_data: Dict[str, Any]
    ) -> bool:
        """Send email using template."""
        pass


class ISMSService(ABC):
    """Interface for SMS messaging."""
    
    @abstractmethod
    async def send_sms(
        self,
        to: str,
        message: str,
        from_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send SMS message."""
        pass
    
    @abstractmethod
    async def verify_phone_number(
        self,
        phone_number: str,
        code: str
    ) -> bool:
        """Verify phone number with code."""
        pass