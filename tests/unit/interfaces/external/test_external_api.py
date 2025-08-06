"""
Unit tests for external service interfaces.
Tests all external service contracts and data structures for dependency inversion compliance.
"""

import pytest
from abc import ABC, abstractmethod
from unittest.mock import Mock, patch, AsyncMock
from typing import Any, Dict, List, Optional, Union
import numpy as np

from src.interfaces.external import (
    TranscriptionResult,
    TTSResult,
    IOpenAIService,
    IAnthropicService,
    IGoogleAIService,
    IElevenLabsService,
    IPineconeService,
    IWebSearchService,
    IWeatherService,
    ITranslationService,
    IImageGenerationService,
    IEmailService,
    ISMSService,
)


class TestTranscriptionResult:
    """Test TranscriptionResult dataclass."""

    def test_transcription_result_creation(self):
        """Test TranscriptionResult creation with all fields."""
        result = TranscriptionResult(
            text="Hello, how are you?",
            confidence=0.95,
            language="en-US",
            duration=2.5
        )
        
        assert result.text == "Hello, how are you?"
        assert result.confidence == 0.95
        assert result.language == "en-US"
        assert result.duration == 2.5

    def test_transcription_result_dataclass_behavior(self):
        """Test TranscriptionResult behaves as dataclass."""
        result1 = TranscriptionResult("text", 0.9, "en", 1.0)
        result2 = TranscriptionResult("text", 0.9, "en", 1.0)
        result3 = TranscriptionResult("different", 0.9, "en", 1.0)
        
        assert result1 == result2
        assert result1 != result3
        assert str(result1) == "TranscriptionResult(text='text', confidence=0.9, language='en', duration=1.0)"

    def test_transcription_result_with_unicode(self):
        """Test TranscriptionResult with unicode text."""
        result = TranscriptionResult(
            text="مرحبا بك في تطبيق الدب الذكي",
            confidence=0.88,
            language="ar-SA",
            duration=3.2
        )
        
        assert "مرحبا" in result.text
        assert result.language == "ar-SA"

    def test_transcription_result_edge_cases(self):
        """Test TranscriptionResult with edge case values."""
        # Empty text
        result_empty = TranscriptionResult("", 0.0, "", 0.0)
        assert result_empty.text == ""
        assert result_empty.confidence == 0.0
        
        # Very long text
        long_text = "word " * 1000
        result_long = TranscriptionResult(long_text, 0.95, "en", 30.0)
        assert len(result_long.text) > 5000
        
        # Perfect confidence
        result_perfect = TranscriptionResult("perfect", 1.0, "en", 1.0)
        assert result_perfect.confidence == 1.0

    def test_transcription_result_child_safety_content(self):
        """Test TranscriptionResult with child-appropriate content."""
        safe_content = "I love learning about animals and playing with friends!"
        result = TranscriptionResult(
            text=safe_content,
            confidence=0.92,
            language="en-US",
            duration=4.1
        )
        
        assert "animals" in result.text
        assert "friends" in result.text
        assert result.confidence > 0.9


class TestTTSResult:
    """Test TTSResult dataclass."""

    def test_tts_result_creation(self):
        """Test TTSResult creation with all fields."""
        audio_data = b"fake_audio_data_bytes"
        result = TTSResult(
            audio_data=audio_data,
            sample_rate=44100,
            duration=3.5,
            format="mp3"
        )
        
        assert result.audio_data == audio_data
        assert result.sample_rate == 44100
        assert result.duration == 3.5
        assert result.format == "mp3"

    def test_tts_result_dataclass_behavior(self):
        """Test TTSResult behaves as dataclass."""
        audio_data = b"test_audio"
        result1 = TTSResult(audio_data, 22050, 2.0, "wav")
        result2 = TTSResult(audio_data, 22050, 2.0, "wav")
        result3 = TTSResult(b"different", 22050, 2.0, "wav")
        
        assert result1 == result2
        assert result1 != result3

    def test_tts_result_with_different_formats(self):
        """Test TTSResult with different audio formats."""
        formats = ["mp3", "wav", "flac", "ogg", "m4a"]
        
        for fmt in formats:
            result = TTSResult(
                audio_data=b"audio_data",
                sample_rate=44100,
                duration=1.0,
                format=fmt
            )
            assert result.format == fmt

    def test_tts_result_with_various_sample_rates(self):
        """Test TTSResult with different sample rates."""
        sample_rates = [8000, 16000, 22050, 44100, 48000, 96000]
        
        for rate in sample_rates:
            result = TTSResult(
                audio_data=b"audio",
                sample_rate=rate,
                duration=1.0,
                format="wav"
            )
            assert result.sample_rate == rate

    def test_tts_result_large_audio_data(self):
        """Test TTSResult with large audio data."""
        # Simulate large audio file (1MB)
        large_audio = b"x" * (1024 * 1024)
        result = TTSResult(
            audio_data=large_audio,
            sample_rate=44100,
            duration=60.0,
            format="wav"
        )
        
        assert len(result.audio_data) == 1024 * 1024
        assert result.duration == 60.0


class TestIOpenAIService:
    """Test IOpenAIService interface."""

    def test_iopenai_service_is_abstract(self):
        """Test IOpenAIService is abstract base class."""
        assert issubclass(IOpenAIService, ABC)
        
        with pytest.raises(TypeError):
            IOpenAIService()

    def test_iopenai_service_abstract_methods(self):
        """Test IOpenAIService has all required abstract methods."""
        abstract_methods = IOpenAIService.__abstractmethods__
        expected_methods = {
            'generate_completion',
            'generate_embedding',
            'transcribe_audio',
            'moderate_content'
        }
        
        assert abstract_methods == expected_methods

    def test_iopenai_service_implementation_requirements(self):
        """Test that implementing IOpenAIService requires all methods."""
        
        class IncompleteOpenAIService(IOpenAIService):
            async def generate_completion(self, prompt, model="gpt-4", temperature=0.7, max_tokens=150, system_prompt=None):
                return "test"
        
        # Should still be abstract due to missing methods
        with pytest.raises(TypeError):
            IncompleteOpenAIService()

    def test_iopenai_service_complete_implementation(self):
        """Test complete implementation of IOpenAIService."""
        
        class TestOpenAIService(IOpenAIService):
            async def generate_completion(self, prompt, model="gpt-4", temperature=0.7, max_tokens=150, system_prompt=None):
                return f"Generated response for: {prompt}"
            
            async def generate_embedding(self, text, model="text-embedding-ada-002"):
                return [0.1, 0.2, 0.3] * 512  # Simulate 1536-dim embedding
            
            async def transcribe_audio(self, audio_data, language=None):
                return TranscriptionResult("transcribed text", 0.95, "en-US", 5.0)
            
            async def moderate_content(self, text):
                return {"flagged": False, "categories": {}}
        
        # Should be able to instantiate
        service = TestOpenAIService()
        assert isinstance(service, IOpenAIService)

    @pytest.mark.asyncio
    async def test_iopenai_service_generate_completion_signature(self):
        """Test generate_completion method signature."""
        
        class MockOpenAIService(IOpenAIService):
            async def generate_completion(self, prompt, model="gpt-4", temperature=0.7, max_tokens=150, system_prompt=None):
                return "test response"
            
            async def generate_embedding(self, text, model="text-embedding-ada-002"):
                return []
            
            async def transcribe_audio(self, audio_data, language=None):
                return TranscriptionResult("", 0.0, "", 0.0)
            
            async def moderate_content(self, text):
                return {}
        
        service = MockOpenAIService()
        
        # Test with minimal args
        result = await service.generate_completion("test prompt")
        assert result == "test response"
        
        # Test with all args
        result = await service.generate_completion(
            prompt="test",
            model="gpt-3.5-turbo",
            temperature=0.5,
            max_tokens=100,
            system_prompt="You are helpful"
        )
        assert result == "test response"

    @pytest.mark.asyncio
    async def test_iopenai_service_child_safety_moderation(self):
        """Test OpenAI service content moderation for child safety."""
        
        class SafetyAwareOpenAIService(IOpenAIService):
            async def generate_completion(self, prompt, model="gpt-4", temperature=0.7, max_tokens=150, system_prompt=None):
                if "inappropriate" in prompt.lower():
                    return "I can't help with that. Let's talk about something fun!"
                return "Safe response"
            
            async def generate_embedding(self, text, model="text-embedding-ada-002"):
                return [0.0] * 1536
            
            async def transcribe_audio(self, audio_data, language=None):
                return TranscriptionResult("child-safe content", 0.95, "en-US", 2.0)
            
            async def moderate_content(self, text):
                unsafe_words = ["violence", "scary", "inappropriate"]
                flagged = any(word in text.lower() for word in unsafe_words)
                return {
                    "flagged": flagged,
                    "categories": {"violence": "violence" in text.lower()}
                }
        
        service = SafetyAwareOpenAIService()
        
        # Test safe content
        safe_result = await service.moderate_content("I love animals and nature!")
        assert safe_result["flagged"] is False
        
        # Test unsafe content
        unsafe_result = await service.moderate_content("This contains violence")
        assert unsafe_result["flagged"] is True
        assert unsafe_result["categories"]["violence"] is True


class TestIAnthropicService:
    """Test IAnthropicService interface."""

    def test_ianthropic_service_is_abstract(self):
        """Test IAnthropicService is abstract base class."""
        assert issubclass(IAnthropicService, ABC)
        
        with pytest.raises(TypeError):
            IAnthropicService()

    def test_ianthropic_service_abstract_methods(self):
        """Test IAnthropicService has all required abstract methods."""
        abstract_methods = IAnthropicService.__abstractmethods__
        expected_methods = {'generate_completion', 'analyze_image'}
        
        assert abstract_methods == expected_methods

    def test_ianthropic_service_complete_implementation(self):
        """Test complete implementation of IAnthropicService."""
        
        class TestAnthropicService(IAnthropicService):
            async def generate_completion(self, prompt, model="claude-3-sonnet-20240229", temperature=0.7, max_tokens=150):
                return f"Claude response: {prompt}"
            
            async def analyze_image(self, image_data, prompt):
                return "This image shows child-appropriate content"
        
        service = TestAnthropicService()
        assert isinstance(service, IAnthropicService)

    @pytest.mark.asyncio
    async def test_ianthropic_service_image_analysis_child_safety(self):
        """Test Anthropic image analysis for child safety."""
        
        class SafeImageAnalysisService(IAnthropicService):
            async def generate_completion(self, prompt, model="claude-3-sonnet-20240229", temperature=0.7, max_tokens=150):
                return "Safe completion"
            
            async def analyze_image(self, image_data, prompt):
                # Simulate child-safe image analysis
                if b"unsafe" in image_data:
                    return "This image is not appropriate for children"
                return "This is a safe, child-friendly image showing animals playing"
        
        service = SafeImageAnalysisService()
        
        # Test safe image
        safe_result = await service.analyze_image(b"safe_image_data", "What do you see?")
        assert "child-friendly" in safe_result
        
        # Test potentially unsafe image
        unsafe_result = await service.analyze_image(b"unsafe_content", "Describe this")
        assert "not appropriate" in unsafe_result


class TestIGoogleAIService:
    """Test IGoogleAIService interface."""

    def test_igoogleai_service_is_abstract(self):
        """Test IGoogleAIService is abstract base class."""
        assert issubclass(IGoogleAIService, ABC)
        
        with pytest.raises(TypeError):
            IGoogleAIService()

    def test_igoogleai_service_abstract_methods(self):
        """Test IGoogleAIService has all required abstract methods."""
        abstract_methods = IGoogleAIService.__abstractmethods__
        expected_methods = {'generate_completion', 'text_to_speech', 'speech_to_text'}
        
        assert abstract_methods == expected_methods

    def test_igoogleai_service_complete_implementation(self):
        """Test complete implementation of IGoogleAIService."""
        
        class TestGoogleAIService(IGoogleAIService):
            async def generate_completion(self, prompt, model="gemini-pro", temperature=0.7):
                return f"Gemini response: {prompt}"
            
            async def text_to_speech(self, text, voice="en-US-Wavenet-D", speaking_rate=1.0):
                return TTSResult(b"tts_audio", 22050, len(text) * 0.1, "mp3")
            
            async def speech_to_text(self, audio_data, language_code="en-US"):
                return TranscriptionResult("transcribed", 0.9, language_code, 2.0)
        
        service = TestGoogleAIService()
        assert isinstance(service, IGoogleAIService)

    @pytest.mark.asyncio
    async def test_igoogleai_service_child_friendly_tts(self):
        """Test Google AI TTS with child-friendly voices."""
        
        class ChildFriendlyTTSService(IGoogleAIService):
            async def generate_completion(self, prompt, model="gemini-pro", temperature=0.7):
                return "Friendly response"
            
            async def text_to_speech(self, text, voice="en-US-Wavenet-D", speaking_rate=1.0):
                # Use child-appropriate voice settings
                child_friendly_voices = [
                    "en-US-Wavenet-D",  # Friendly female
                    "en-US-Wavenet-A",  # Gentle male
                    "en-US-Standard-E"  # Child-like
                ]
                
                if voice not in child_friendly_voices:
                    voice = "en-US-Wavenet-D"  # Default to friendly voice
                
                return TTSResult(
                    audio_data=f"TTS:{text}:{voice}".encode(),
                    sample_rate=22050,
                    duration=len(text) * 0.1,
                    format="wav"
                )
            
            async def speech_to_text(self, audio_data, language_code="en-US"):
                return TranscriptionResult("child speech", 0.95, language_code, 1.5)
        
        service = ChildFriendlyTTSService()
        
        # Test child-friendly TTS
        result = await service.text_to_speech(
            "Hello, little friend! Let's learn about animals!",
            voice="en-US-Wavenet-D"
        )
        
        assert isinstance(result, TTSResult)
        assert result.sample_rate == 22050
        assert b"TTS:" in result.audio_data


class TestIElevenLabsService:
    """Test IElevenLabsService interface."""

    def test_ielevenlabs_service_is_abstract(self):
        """Test IElevenLabsService is abstract base class."""
        assert issubclass(IElevenLabsService, ABC)
        
        with pytest.raises(TypeError):
            IElevenLabsService()

    def test_ielevenlabs_service_abstract_methods(self):
        """Test IElevenLabsService has all required abstract methods."""
        abstract_methods = IElevenLabsService.__abstractmethods__
        expected_methods = {'synthesize_speech', 'get_voices', 'clone_voice'}
        
        assert abstract_methods == expected_methods

    @pytest.mark.asyncio
    async def test_ielevenlabs_service_child_safe_synthesis(self):
        """Test ElevenLabs service with child-safe voice synthesis."""
        
        class ChildSafeElevenLabsService(IElevenLabsService):
            async def synthesize_speech(self, text, voice_id, stability=0.5, similarity_boost=0.5):
                # Ensure child-appropriate content
                if any(word in text.lower() for word in ["scary", "violence", "adult"]):
                    raise ValueError("Content not appropriate for children")
                
                return TTSResult(
                    audio_data=f"ElevenLabs:{text}:{voice_id}".encode(),
                    sample_rate=44100,
                    duration=len(text) * 0.08,
                    format="mp3"
                )
            
            async def get_voices(self):
                return [
                    {"voice_id": "child_friendly_1", "name": "Friendly Teacher", "category": "child_safe"},
                    {"voice_id": "child_friendly_2", "name": "Kind Storyteller", "category": "child_safe"}
                ]
            
            async def clone_voice(self, name, audio_samples):
                # For child safety, only allow supervised voice cloning
                if "child" not in name.lower() or len(audio_samples) < 3:
                    raise ValueError("Voice cloning requires safety approval")
                return f"cloned_voice_{hash(name) % 1000}"
        
        service = ChildSafeElevenLabsService()
        
        # Test safe synthesis
        result = await service.synthesize_speech(
            "Hello! Let's learn about the wonderful world of animals!",
            "child_friendly_1"
        )
        assert isinstance(result, TTSResult)
        
        # Test unsafe content rejection
        with pytest.raises(ValueError, match="not appropriate"):
            await service.synthesize_speech("scary story", "voice_id")


class TestIPineconeService:
    """Test IPineconeService interface."""

    def test_ipinecone_service_is_abstract(self):
        """Test IPineconeService is abstract base class."""
        assert issubclass(IPineconeService, ABC)
        
        with pytest.raises(TypeError):
            IPineconeService()

    def test_ipinecone_service_abstract_methods(self):
        """Test IPineconeService has all required abstract methods."""
        abstract_methods = IPineconeService.__abstractmethods__
        expected_methods = {'upsert_vectors', 'query_vectors', 'delete_vectors'}
        
        assert abstract_methods == expected_methods

    @pytest.mark.asyncio
    async def test_ipinecone_service_child_data_isolation(self):
        """Test Pinecone service with child data isolation."""
        
        class ChildSafePineconeService(IPineconeService):
            def __init__(self):
                self.child_namespaces = {}
            
            async def upsert_vectors(self, vectors, namespace=None):
                # Ensure child data is in isolated namespace
                if namespace and "child_" in namespace:
                    if namespace not in self.child_namespaces:
                        self.child_namespaces[namespace] = []
                    return {"upserted_count": len(vectors)}
                return {"upserted_count": 0}
            
            async def query_vectors(self, vector, top_k=10, namespace=None, filter=None):
                # Only return results from appropriate namespace
                if namespace and namespace in self.child_namespaces:
                    return [
                        {"id": f"safe_memory_{i}", "score": 0.9 - i*0.1, "metadata": {"safe": True}}
                        for i in range(min(top_k, 3))
                    ]
                return []
            
            async def delete_vectors(self, ids, namespace=None):
                # Only allow deletion from child namespace with proper auth
                if namespace and "child_" in namespace:
                    return {"deleted_count": len(ids)}
                return {"deleted_count": 0}
        
        service = ChildSafePineconeService()
        
        # Test child data isolation
        child_vectors = [
            {"id": "memory_1", "values": [0.1] * 1536, "metadata": {"content": "safe_memory"}}
        ]
        
        result = await service.upsert_vectors(child_vectors, namespace="child_123")
        assert result["upserted_count"] == 1
        
        # Test querying child data
        query_result = await service.query_vectors([0.2] * 1536, namespace="child_123")
        assert len(query_result) > 0
        assert all("safe" in item["metadata"] for item in query_result)


class TestIWebSearchService:
    """Test IWebSearchService interface."""

    def test_iwebsearch_service_is_abstract(self):
        """Test IWebSearchService is abstract base class."""
        assert issubclass(IWebSearchService, ABC)
        
        with pytest.raises(TypeError):
            IWebSearchService()

    @pytest.mark.asyncio
    async def test_iwebsearch_service_safe_search_enforcement(self):
        """Test web search service with safe search enforcement."""
        
        class ChildSafeWebSearchService(IWebSearchService):
            async def search(self, query, max_results=10, safe_search=True):
                # Always enforce safe search for child protection
                if not safe_search:
                    safe_search = True  # Override for child safety
                
                # Filter out inappropriate queries
                unsafe_terms = ["violence", "scary", "adult", "weapon"]
                if any(term in query.lower() for term in unsafe_terms):
                    return []
                
                # Return safe, educational results
                safe_results = [
                    {
                        "title": f"Educational content about {query}",
                        "url": f"https://safe-educational-site.com/{query}",
                        "snippet": f"Learn about {query} in a fun, safe way!",
                        "safe_for_children": True
                    }
                ]
                
                return safe_results[:max_results]
            
            async def get_news(self, topic, max_results=5):
                # Only return positive, educational news for children
                child_friendly_topics = ["animals", "science", "nature", "space", "books"]
                
                if not any(friendly in topic.lower() for friendly in child_friendly_topics):
                    return []
                
                return [
                    {
                        "title": f"Amazing discovery about {topic}!",
                        "summary": f"Scientists made a wonderful discovery about {topic}",
                        "category": "education",
                        "child_appropriate": True
                    }
                ]
        
        service = ChildSafeWebSearchService()
        
        # Test safe search
        results = await service.search("cute animals", max_results=3)
        assert len(results) > 0
        assert all(result["safe_for_children"] for result in results)
        
        # Test filtering unsafe queries
        unsafe_results = await service.search("scary monsters")
        assert len(unsafe_results) == 0


class TestIWeatherService:
    """Test IWeatherService interface."""

    def test_iweather_service_is_abstract(self):
        """Test IWeatherService is abstract base class."""
        assert issubclass(IWeatherService, ABC)
        
        with pytest.raises(TypeError):
            IWeatherService()

    @pytest.mark.asyncio
    async def test_iweather_service_child_friendly_descriptions(self):
        """Test weather service with child-friendly descriptions."""
        
        class ChildFriendlyWeatherService(IWeatherService):
            async def get_current_weather(self, location):
                return {
                    "location": location,
                    "temperature": "72°F (22°C)",
                    "condition": "Sunny and bright",
                    "description": "It's a beautiful sunny day - perfect for playing outside!",
                    "child_friendly": True,
                    "activity_suggestion": "Great weather for a nature walk!"
                }
            
            async def get_forecast(self, location, days=5):
                friendly_conditions = [
                    "Sunny and warm - perfect for outdoor fun!",
                    "Partly cloudy with gentle breezes",
                    "Light rain - great for watching from inside with a book!",
                    "Clear skies - amazing for stargazing!",
                    "Cool and crisp - perfect sweater weather!"
                ]
                
                return [
                    {
                        "day": f"Day {i+1}",
                        "condition": friendly_conditions[i % len(friendly_conditions)],
                        "temperature_high": f"{70 + i*2}°F",
                        "temperature_low": f"{55 + i}°F",
                        "child_activity": f"Perfect for activity {i+1}"
                    }
                    for i in range(days)
                ]
        
        service = ChildFriendlyWeatherService()
        
        # Test child-friendly weather description
        weather = await service.get_current_weather("New York")
        assert weather["child_friendly"] is True
        assert "beautiful" in weather["description"] or "perfect" in weather["description"]
        
        # Test child-friendly forecast
        forecast = await service.get_forecast("London", days=3)
        assert len(forecast) == 3
        assert all("child_activity" in day for day in forecast)


class TestITranslationService:
    """Test ITranslationService interface."""

    def test_itranslation_service_is_abstract(self):
        """Test ITranslationService is abstract base class."""
        assert issubclass(ITranslationService, ABC)
        
        with pytest.raises(TypeError):
            ITranslationService()

    @pytest.mark.asyncio
    async def test_itranslation_service_content_filtering(self):
        """Test translation service with content filtering."""
        
        class SafeTranslationService(ITranslationService):
            async def translate(self, text, target_language, source_language=None):
                # Filter inappropriate content before translation
                unsafe_words = ["violence", "scary", "inappropriate"]
                if any(word in text.lower() for word in unsafe_words):
                    return "I can only translate child-friendly content!"
                
                # Simple mock translation
                translations = {
                    "es": f"Spanish: {text}",
                    "fr": f"French: {text}",
                    "de": f"German: {text}"
                }
                
                return translations.get(target_language, f"Translated to {target_language}: {text}")
            
            async def detect_language(self, text):
                # Simple language detection mock
                if any(word in text for word in ["hola", "buenos", "gracias"]):
                    return "es"
                elif any(word in text for word in ["bonjour", "merci", "au revoir"]):
                    return "fr"
                return "en"
            
            async def get_supported_languages(self):
                return [
                    {"code": "en", "name": "English"},
                    {"code": "es", "name": "Spanish"},
                    {"code": "fr", "name": "French"},
                    {"code": "de", "name": "German"}
                ]
        
        service = SafeTranslationService()
        
        # Test safe translation
        result = await service.translate("Hello, how are you?", "es")
        assert "Spanish" in result
        
        # Test content filtering
        filtered_result = await service.translate("scary story", "es")
        assert "child-friendly" in filtered_result


class TestIImageGenerationService:
    """Test IImageGenerationService interface."""

    def test_iimage_generation_service_is_abstract(self):
        """Test IImageGenerationService is abstract base class."""
        assert issubclass(IImageGenerationService, ABC)
        
        with pytest.raises(TypeError):
            IImageGenerationService()

    @pytest.mark.asyncio
    async def test_iimage_generation_service_child_safe_prompts(self):
        """Test image generation with child-safe prompt filtering."""
        
        class ChildSafeImageGenerationService(IImageGenerationService):
            async def generate_image(self, prompt, size="1024x1024", style=None):
                # Filter prompts for child safety
                unsafe_terms = ["scary", "violence", "adult", "inappropriate"]
                if any(term in prompt.lower() for term in unsafe_terms):
                    raise ValueError("Prompt not appropriate for children")
                
                # Enhance prompts with child-friendly elements
                safe_prompt = f"child-friendly, colorful, happy {prompt}"
                return f"Generated safe image for: {safe_prompt}".encode()
            
            async def edit_image(self, image, mask, prompt):
                # Ensure editing prompts are child-appropriate
                if any(word in prompt.lower() for word in ["remove", "delete", "scary"]):
                    prompt = "make it more colorful and happy"
                
                return f"Edited image with: {prompt}".encode()
            
            async def create_variations(self, image, n=1):
                return [f"Safe variation {i+1}".encode() for i in range(n)]
        
        service = ChildSafeImageGenerationService()
        
        # Test safe image generation
        safe_image = await service.generate_image("cute animals playing in a meadow")
        assert b"child-friendly" in safe_image
        
        # Test unsafe prompt rejection
        with pytest.raises(ValueError, match="not appropriate"):
            await service.generate_image("scary monster")


class TestIEmailService:
    """Test IEmailService interface."""

    def test_iemail_service_is_abstract(self):
        """Test IEmailService is abstract base class."""
        assert issubclass(IEmailService, ABC)
        
        with pytest.raises(TypeError):
            IEmailService()

    @pytest.mark.asyncio
    async def test_iemail_service_parent_notifications(self):
        """Test email service for parent notifications."""
        
        class ParentNotificationEmailService(IEmailService):
            async def send_email(self, to, subject, body, html_body=None, attachments=None):
                # Validate parent email communications
                if "child" in subject.lower() or "child" in body.lower():
                    # This is child-related communication - ensure compliance
                    subject = f"[COPPA Compliant] {subject}"
                    body = f"COPPA Notice: This email contains information about your child.\n\n{body}"
                
                return True  # Mock successful send
            
            async def send_template_email(self, to, template_id, template_data):
                # Use pre-approved templates for child-related communications
                approved_templates = [
                    "parent_consent_request",
                    "child_activity_summary",
                    "safety_alert",
                    "weekly_progress_report"
                ]
                
                if template_id not in approved_templates:
                    raise ValueError(f"Template {template_id} not approved for child communications")
                
                return True
        
        service = ParentNotificationEmailService()
        
        # Test parent notification
        result = await service.send_email(
            to="parent@example.com",
            subject="Your child's weekly activity summary",
            body="Your child had 5 safe conversations this week."
        )
        assert result is True
        
        # Test template validation
        template_result = await service.send_template_email(
            to="parent@example.com",
            template_id="parent_consent_request",
            template_data={"child_name": "Alice", "activity": "voice_chat"}
        )
        assert template_result is True


class TestISMSService:
    """Test ISMSService interface."""

    def test_isms_service_is_abstract(self):
        """Test ISMSService is abstract base class."""
        assert issubclass(ISMSService, ABC)
        
        with pytest.raises(TypeError):
            ISMSService()

    @pytest.mark.asyncio
    async def test_isms_service_parent_verification(self):
        """Test SMS service for parent verification."""
        
        class ParentVerificationSMSService(ISMSService):
            def __init__(self):
                self.verification_codes = {}
            
            async def send_sms(self, to, message, from_number=None):
                # Ensure SMS is for parent verification only
                if "verification" not in message.lower() and "parent" not in message.lower():
                    raise ValueError("SMS service only for parent verification")
                
                # Store verification code for testing
                if "code:" in message:
                    code = message.split("code:")[-1].strip()
                    self.verification_codes[to] = code
                
                return {
                    "message_id": f"sms_{hash(to + message) % 10000}",
                    "status": "sent",
                    "to": to
                }
            
            async def verify_phone_number(self, phone_number, code):
                stored_code = self.verification_codes.get(phone_number)
                return stored_code == code
        
        service = ParentVerificationSMSService()
        
        # Test parent verification SMS
        sms_result = await service.send_sms(
            to="+1234567890",
            message="Parent verification code: 123456"
        )
        assert sms_result["status"] == "sent"
        
        # Test verification
        verification_result = await service.verify_phone_number("+1234567890", "123456")
        assert verification_result is True


class TestExternalServiceInterfaceIntegration:
    """Test integration scenarios between external service interfaces."""

    @pytest.mark.asyncio
    async def test_multi_service_child_interaction_flow(self):
        """Test complete child interaction flow using multiple services."""
        
        # Mock implementations for integration test
        class MockOpenAIService(IOpenAIService):
            async def generate_completion(self, prompt, model="gpt-4", temperature=0.7, max_tokens=150, system_prompt=None):
                return "Hello! I love talking about animals and nature!"
            
            async def generate_embedding(self, text, model="text-embedding-ada-002"):
                return [0.1] * 1536
            
            async def transcribe_audio(self, audio_data, language=None):
                return TranscriptionResult("Tell me about elephants", 0.95, "en-US", 2.0)
            
            async def moderate_content(self, text):
                return {"flagged": False, "categories": {}}
        
        class MockGoogleTTS(IGoogleAIService):
            async def generate_completion(self, prompt, model="gemini-pro", temperature=0.7):
                return "Gemini response"
            
            async def text_to_speech(self, text, voice="en-US-Wavenet-D", speaking_rate=1.0):
                return TTSResult(
                    audio_data=f"TTS:{text}".encode(),
                    sample_rate=22050,
                    duration=len(text) * 0.1,
                    format="wav"
                )
            
            async def speech_to_text(self, audio_data, language_code="en-US"):
                return TranscriptionResult("child speech", 0.9, language_code, 1.5)
        
        # Simulate child interaction flow
        openai_service = MockOpenAIService()
        tts_service = MockGoogleTTS()
        
        # 1. Transcribe child's speech
        child_audio = b"fake_audio_data"
        transcription = await openai_service.transcribe_audio(child_audio)
        assert transcription.text == "Tell me about elephants"
        assert transcription.confidence > 0.9
        
        # 2. Check content safety
        moderation = await openai_service.moderate_content(transcription.text)
        assert moderation["flagged"] is False
        
        # 3. Generate AI response
        ai_response = await openai_service.generate_completion(
            transcription.text,
            system_prompt="You are a friendly AI teddy bear for children"
        )
        assert "animals" in ai_response or "nature" in ai_response
        
        # 4. Convert response to speech
        tts_result = await tts_service.text_to_speech(ai_response, voice="en-US-Wavenet-D")
        assert isinstance(tts_result, TTSResult)
        assert tts_result.sample_rate == 22050

    def test_external_service_interface_contracts(self):
        """Test that all external service interfaces maintain proper contracts."""
        
        # All service interfaces should be abstract
        service_interfaces = [
            IOpenAIService,
            IAnthropicService,
            IGoogleAIService,
            IElevenLabsService,
            IPineconeService,
            IWebSearchService,
            IWeatherService,
            ITranslationService,
            IImageGenerationService,
            IEmailService,
            ISMSService
        ]
        
        for interface in service_interfaces:
            assert issubclass(interface, ABC)
            assert len(interface.__abstractmethods__) > 0
            
            # Should not be instantiable
            with pytest.raises(TypeError):
                interface()

    def test_data_structures_child_safety_compliance(self):
        """Test that data structures support child safety requirements."""
        
        # TranscriptionResult should handle child speech
        child_transcription = TranscriptionResult(
            text="I want to learn about dinosaurs!",
            confidence=0.92,
            language="en-US",
            duration=3.5
        )
        
        assert "learn" in child_transcription.text
        assert child_transcription.confidence > 0.9
        
        # TTSResult should support child-friendly audio
        child_audio = TTSResult(
            audio_data=b"child_friendly_audio_content",
            sample_rate=22050,  # Appropriate for child content
            duration=5.0,
            format="wav"
        )
        
        assert child_audio.sample_rate == 22050
        assert child_audio.format in ["wav", "mp3"]  # Child-appropriate formats