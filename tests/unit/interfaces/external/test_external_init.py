"""
Unit tests for external service interfaces.
Tests interface definitions, data classes, and abstract method contracts.
"""

import pytest
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from unittest.mock import Mock, AsyncMock
import numpy as np

from src.interfaces.external import (
    TranscriptionResult,
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

# TTSResult DELETED - use unified TTSResult from src.interfaces.providers.tts_provider


class TestTranscriptionResult:
    """Test TranscriptionResult data class."""
    
    def test_transcription_result_creation(self):
        """Test creating TranscriptionResult with valid data."""
        result = TranscriptionResult(
            text="Hello world",
            confidence=0.95,
            language="en-US",
            duration=2.5
        )
        
        assert result.text == "Hello world"
        assert result.confidence == 0.95
        assert result.language == "en-US"
        assert result.duration == 2.5
    
    def test_transcription_result_equality(self):
        """Test TranscriptionResult equality comparison."""
        result1 = TranscriptionResult("Hello", 0.95, "en-US", 2.5)
        result2 = TranscriptionResult("Hello", 0.95, "en-US", 2.5)
        result3 = TranscriptionResult("Hi", 0.95, "en-US", 2.5)
        
        assert result1 == result2
        assert result1 != result3
    
    def test_transcription_result_attributes(self):
        """Test TranscriptionResult has expected attributes."""
        result = TranscriptionResult("test", 0.9, "en", 1.0)
        
        assert hasattr(result, 'text')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'language')
        assert hasattr(result, 'duration')
    
    def test_transcription_result_types(self):
        """Test TranscriptionResult attribute types."""
        result = TranscriptionResult("test", 0.9, "en", 1.0)
        
        assert isinstance(result.text, str)
        assert isinstance(result.confidence, float)
        assert isinstance(result.language, str)
        assert isinstance(result.duration, float)


# TestTTSResult DELETED - use unified TTSResult from src.interfaces.providers.tts_provider


class TestIOpenAIService:
    """Test IOpenAIService interface."""
    
    def test_openai_service_is_abstract(self):
        """Test IOpenAIService is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            IOpenAIService()
    
    def test_openai_service_abstract_methods(self):
        """Test IOpenAIService has required abstract methods."""
        expected_methods = [
            'generate_completion',
            'generate_embedding',
            'transcribe_audio',
            'moderate_content'
        ]
        
        for method_name in expected_methods:
            assert hasattr(IOpenAIService, method_name)
            method = getattr(IOpenAIService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_openai_service_concrete_implementation(self):
        """Test concrete implementation of IOpenAIService works."""
        class MockOpenAIService(IOpenAIService):
            async def generate_completion(self, prompt, model="gpt-4", temperature=0.7, max_tokens=150, system_prompt=None):
                return f"Response to: {prompt}"
            
            async def generate_embedding(self, text, model="text-embedding-ada-002"):
                return [0.1, 0.2, 0.3]
            
            async def transcribe_audio(self, audio_data, language=None):
                return TranscriptionResult("transcribed text", 0.95, "en-US", 2.0)
            
            async def moderate_content(self, text):
                return {"flagged": False, "categories": {}}
        
        service = MockOpenAIService()
        assert isinstance(service, IOpenAIService)
    
    def test_openai_service_generate_completion_signature(self):
        """Test generate_completion method signature."""
        import inspect
        method = IOpenAIService.generate_completion
        sig = inspect.signature(method)
        
        expected_params = ['self', 'prompt', 'model', 'temperature', 'max_tokens', 'system_prompt']
        actual_params = list(sig.parameters.keys())
        
        assert actual_params == expected_params
        assert sig.parameters['model'].default == "gpt-4"
        assert sig.parameters['temperature'].default == 0.7
        assert sig.parameters['max_tokens'].default == 150
    
    def test_openai_service_generate_embedding_signature(self):
        """Test generate_embedding method signature."""
        import inspect
        method = IOpenAIService.generate_embedding
        sig = inspect.signature(method)
        
        expected_params = ['self', 'text', 'model']
        actual_params = list(sig.parameters.keys())
        
        assert actual_params == expected_params
        assert sig.parameters['model'].default == "text-embedding-ada-002"


class TestIAnthropicService:
    """Test IAnthropicService interface."""
    
    def test_anthropic_service_is_abstract(self):
        """Test IAnthropicService is abstract."""
        with pytest.raises(TypeError):
            IAnthropicService()
    
    def test_anthropic_service_abstract_methods(self):
        """Test IAnthropicService has required abstract methods."""
        expected_methods = ['generate_completion', 'analyze_image']
        
        for method_name in expected_methods:
            assert hasattr(IAnthropicService, method_name)
            method = getattr(IAnthropicService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_anthropic_service_concrete_implementation(self):
        """Test concrete implementation of IAnthropicService works."""
        class MockAnthropicService(IAnthropicService):
            async def generate_completion(self, prompt, model="claude-3-sonnet-20240229", temperature=0.7, max_tokens=150):
                return f"Claude response to: {prompt}"
            
            async def analyze_image(self, image_data, prompt):
                return f"Image analysis: {prompt}"
        
        service = MockAnthropicService()
        assert isinstance(service, IAnthropicService)
    
    def test_anthropic_service_method_signatures(self):
        """Test method signatures for IAnthropicService."""
        import inspect
        
        # Test generate_completion signature
        method = IAnthropicService.generate_completion
        sig = inspect.signature(method)
        assert 'claude-3-sonnet-20240229' in str(sig.parameters['model'].default)
        
        # Test analyze_image signature
        method = IAnthropicService.analyze_image
        sig = inspect.signature(method)
        expected_params = ['self', 'image_data', 'prompt']
        assert list(sig.parameters.keys()) == expected_params


class TestIGoogleAIService:
    """Test IGoogleAIService interface."""
    
    def test_google_ai_service_is_abstract(self):
        """Test IGoogleAIService is abstract."""
        with pytest.raises(TypeError):
            IGoogleAIService()
    
    def test_google_ai_service_abstract_methods(self):
        """Test IGoogleAIService has required abstract methods."""
        expected_methods = ['generate_completion', 'speech_to_text']
        
        for method_name in expected_methods:
            assert hasattr(IGoogleAIService, method_name)
            method = getattr(IGoogleAIService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_google_ai_service_concrete_implementation(self):
        """Test concrete implementation of IGoogleAIService works."""
        class MockGoogleAIService(IGoogleAIService):
            async def generate_completion(self, prompt, model="gemini-pro", temperature=0.7):
                return f"Gemini response: {prompt}"
            
            async def speech_to_text(self, audio_data, language_code="en-US"):
                return TranscriptionResult("speech text", 0.9, language_code, 1.5)
        
        service = MockGoogleAIService()
        assert isinstance(service, IGoogleAIService)


class TestIElevenLabsService:
    """Test IElevenLabsService interface."""
    
    def test_elevenlabs_service_is_abstract(self):
        """Test IElevenLabsService is abstract."""
        with pytest.raises(TypeError):
            IElevenLabsService()
    
    def test_elevenlabs_service_abstract_methods(self):
        """Test IElevenLabsService has required abstract methods (NON-TTS only)."""
        expected_methods = ['get_user_subscription', 'get_user_info']
        
        for method_name in expected_methods:
            assert hasattr(IElevenLabsService, method_name)
            method = getattr(IElevenLabsService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_elevenlabs_service_concrete_implementation(self):
        """Test concrete implementation of IElevenLabsService works (NON-TTS only)."""
        class MockElevenLabsService(IElevenLabsService):
            async def get_user_subscription(self):
                return {"tier": "free", "character_count": 10000, "character_limit": 10000}
            
            async def get_user_info(self):
                return {"user_id": "123", "email": "test@example.com"}
        
        service = MockElevenLabsService()
        assert isinstance(service, IElevenLabsService)
    
    def test_elevenlabs_service_method_signatures(self):
        """Test method signatures for IElevenLabsService (NON-TTS only)."""
        import inspect
        
        # Test get_user_subscription signature
        method = IElevenLabsService.get_user_subscription
        sig = inspect.signature(method)
        assert len(sig.parameters) == 1  # Only 'self' parameter
        
        # Test get_user_info signature
        method = IElevenLabsService.get_user_info
        sig = inspect.signature(method)
        assert len(sig.parameters) == 1  # Only 'self' parameter


class TestIPineconeService:
    """Test IPineconeService interface."""
    
    def test_pinecone_service_is_abstract(self):
        """Test IPineconeService is abstract."""
        with pytest.raises(TypeError):
            IPineconeService()
    
    def test_pinecone_service_abstract_methods(self):
        """Test IPineconeService has required abstract methods."""
        expected_methods = ['upsert_vectors', 'query_vectors', 'delete_vectors']
        
        for method_name in expected_methods:
            assert hasattr(IPineconeService, method_name)
            method = getattr(IPineconeService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_pinecone_service_concrete_implementation(self):
        """Test concrete implementation of IPineconeService works."""
        class MockPineconeService(IPineconeService):
            async def upsert_vectors(self, vectors, namespace=None):
                return {"upserted_count": len(vectors)}
            
            async def query_vectors(self, vector, top_k=10, namespace=None, filter=None):
                return [{"id": "match1", "score": 0.95}, {"id": "match2", "score": 0.87}]
            
            async def delete_vectors(self, ids, namespace=None):
                return {"deleted_count": len(ids)}
        
        service = MockPineconeService()
        assert isinstance(service, IPineconeService)
    
    def test_pinecone_service_method_signatures(self):
        """Test method signatures for IPineconeService."""
        import inspect
        
        # Test query_vectors signature
        method = IPineconeService.query_vectors
        sig = inspect.signature(method)
        assert sig.parameters['top_k'].default == 10


class TestIWebSearchService:
    """Test IWebSearchService interface."""
    
    def test_web_search_service_is_abstract(self):
        """Test IWebSearchService is abstract."""
        with pytest.raises(TypeError):
            IWebSearchService()
    
    def test_web_search_service_abstract_methods(self):
        """Test IWebSearchService has required abstract methods."""
        expected_methods = ['search', 'get_news']
        
        for method_name in expected_methods:
            assert hasattr(IWebSearchService, method_name)
            method = getattr(IWebSearchService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_web_search_service_concrete_implementation(self):
        """Test concrete implementation of IWebSearchService works."""
        class MockWebSearchService(IWebSearchService):
            async def search(self, query, max_results=10, safe_search=True):
                return [{"title": "Result 1", "url": "https://example.com", "snippet": "Safe content"}]
            
            async def get_news(self, topic, max_results=5):
                return [{"title": "News 1", "url": "https://news.com", "published": "2023-01-01"}]
        
        service = MockWebSearchService()
        assert isinstance(service, IWebSearchService)
    
    def test_web_search_service_safety_defaults(self):
        """Test that web search service defaults to safe search."""
        import inspect
        
        method = IWebSearchService.search
        sig = inspect.signature(method)
        assert sig.parameters['safe_search'].default is True
        assert sig.parameters['max_results'].default == 10


class TestIWeatherService:
    """Test IWeatherService interface."""
    
    def test_weather_service_is_abstract(self):
        """Test IWeatherService is abstract."""
        with pytest.raises(TypeError):
            IWeatherService()
    
    def test_weather_service_abstract_methods(self):
        """Test IWeatherService has required abstract methods."""
        expected_methods = ['get_current_weather', 'get_forecast']
        
        for method_name in expected_methods:
            assert hasattr(IWeatherService, method_name)
            method = getattr(IWeatherService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_weather_service_concrete_implementation(self):
        """Test concrete implementation of IWeatherService works."""
        class MockWeatherService(IWeatherService):
            async def get_current_weather(self, location):
                return {"location": location, "temperature": 72, "condition": "sunny"}
            
            async def get_forecast(self, location, days=5):
                return [{"day": i, "temperature": 70 + i, "condition": "clear"} for i in range(days)]
        
        service = MockWeatherService()
        assert isinstance(service, IWeatherService)


class TestITranslationService:
    """Test ITranslationService interface."""
    
    def test_translation_service_is_abstract(self):
        """Test ITranslationService is abstract."""
        with pytest.raises(TypeError):
            ITranslationService()
    
    def test_translation_service_abstract_methods(self):
        """Test ITranslationService has required abstract methods."""
        expected_methods = ['translate', 'detect_language', 'get_supported_languages']
        
        for method_name in expected_methods:
            assert hasattr(ITranslationService, method_name)
            method = getattr(ITranslationService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_translation_service_concrete_implementation(self):
        """Test concrete implementation of ITranslationService works."""
        class MockTranslationService(ITranslationService):
            async def translate(self, text, target_language, source_language=None):
                return f"Translated '{text}' to {target_language}"
            
            async def detect_language(self, text):
                return "en"
            
            async def get_supported_languages(self):
                return [{"code": "en", "name": "English"}, {"code": "es", "name": "Spanish"}]
        
        service = MockTranslationService()
        assert isinstance(service, ITranslationService)


class TestIImageGenerationService:
    """Test IImageGenerationService interface."""
    
    def test_image_generation_service_is_abstract(self):
        """Test IImageGenerationService is abstract."""
        with pytest.raises(TypeError):
            IImageGenerationService()
    
    def test_image_generation_service_abstract_methods(self):
        """Test IImageGenerationService has required abstract methods."""
        expected_methods = ['generate_image', 'edit_image', 'create_variations']
        
        for method_name in expected_methods:
            assert hasattr(IImageGenerationService, method_name)
            method = getattr(IImageGenerationService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_image_generation_service_concrete_implementation(self):
        """Test concrete implementation of IImageGenerationService works."""
        class MockImageGenerationService(IImageGenerationService):
            async def generate_image(self, prompt, size="1024x1024", style=None):
                return b"generated_image_data"
            
            async def edit_image(self, image, mask, prompt):
                return b"edited_image_data"
            
            async def create_variations(self, image, n=1):
                return [b"variation_data" for _ in range(n)]
        
        service = MockImageGenerationService()
        assert isinstance(service, IImageGenerationService)
    
    def test_image_generation_service_defaults(self):
        """Test default parameter values for image generation."""
        import inspect
        
        method = IImageGenerationService.generate_image
        sig = inspect.signature(method)
        assert sig.parameters['size'].default == "1024x1024"
        
        method = IImageGenerationService.create_variations
        sig = inspect.signature(method)
        assert sig.parameters['n'].default == 1


class TestIEmailService:
    """Test IEmailService interface."""
    
    def test_email_service_is_abstract(self):
        """Test IEmailService is abstract."""
        with pytest.raises(TypeError):
            IEmailService()
    
    def test_email_service_abstract_methods(self):
        """Test IEmailService has required abstract methods."""
        expected_methods = ['send_email', 'send_template_email']
        
        for method_name in expected_methods:
            assert hasattr(IEmailService, method_name)
            method = getattr(IEmailService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_email_service_concrete_implementation(self):
        """Test concrete implementation of IEmailService works."""
        class MockEmailService(IEmailService):
            async def send_email(self, to, subject, body, html_body=None, attachments=None):
                return True
            
            async def send_template_email(self, to, template_id, template_data):
                return True
        
        service = MockEmailService()
        assert isinstance(service, IEmailService)
    
    def test_email_service_method_signatures(self):
        """Test method signatures for IEmailService."""
        import inspect
        
        # Test send_email signature supports both single and multiple recipients
        method = IEmailService.send_email
        sig = inspect.signature(method)
        
        # The 'to' parameter should support Union[str, List[str]]
        param_annotation = sig.parameters['to'].annotation
        assert 'Union' in str(param_annotation) or 'str' in str(param_annotation)


class TestISMSService:
    """Test ISMSService interface."""
    
    def test_sms_service_is_abstract(self):
        """Test ISMSService is abstract."""
        with pytest.raises(TypeError):
            ISMSService()
    
    def test_sms_service_abstract_methods(self):
        """Test ISMSService has required abstract methods."""
        expected_methods = ['send_sms', 'verify_phone_number']
        
        for method_name in expected_methods:
            assert hasattr(ISMSService, method_name)
            method = getattr(ISMSService, method_name)
            assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_sms_service_concrete_implementation(self):
        """Test concrete implementation of ISMSService works."""
        class MockSMSService(ISMSService):
            async def send_sms(self, to, message, from_number=None):
                return {"message_id": "sms_123", "status": "sent"}
            
            async def verify_phone_number(self, phone_number, code):
                return True
        
        service = MockSMSService()
        assert isinstance(service, ISMSService)


class TestInterfaceInheritance:
    """Test interface inheritance patterns."""
    
    def test_all_interfaces_inherit_from_abc(self):
        """Test that all interfaces inherit from ABC."""
        interfaces = [
            IOpenAIService, IAnthropicService, IGoogleAIService,
            IElevenLabsService, IPineconeService, IWebSearchService,
            IWeatherService, ITranslationService, IImageGenerationService,
            IEmailService, ISMSService
        ]
        
        for interface in interfaces:
            assert issubclass(interface, ABC)
    
    def test_interfaces_cannot_be_instantiated(self):
        """Test that all interfaces cannot be instantiated directly."""
        interfaces = [
            IOpenAIService, IAnthropicService, IGoogleAIService,
            IElevenLabsService, IPineconeService, IWebSearchService,
            IWeatherService, ITranslationService, IImageGenerationService,
            IEmailService, ISMSService
        ]
        
        for interface in interfaces:
            with pytest.raises(TypeError):
                interface()


class TestDataClassesIntegration:
    """Test integration between data classes and interfaces."""
    
    def test_transcription_result_integration(self):
        """Test TranscriptionResult integrates properly with interfaces."""
        class MockService(IOpenAIService):
            async def generate_completion(self, prompt, **kwargs):
                return "response"
            
            async def generate_embedding(self, text, **kwargs):
                return [0.1, 0.2]
            
            async def transcribe_audio(self, audio_data, language=None):
                return TranscriptionResult("test text", 0.95, "en-US", 2.0)
            
            async def moderate_content(self, text):
                return {"flagged": False}
        
        service = MockService()
        assert isinstance(service, IOpenAIService)
    
    # test_tts_result_integration DELETED - TTSResult moved to unified interface


class TestInterfaceDocumentation:
    """Test interface documentation and contracts."""
    
    def test_interfaces_have_docstrings(self):
        """Test that all interfaces have documentation."""
        interfaces = [
            IOpenAIService, IAnthropicService, IGoogleAIService,
            IElevenLabsService, IPineconeService, IWebSearchService,
            IWeatherService, ITranslationService, IImageGenerationService,
            IEmailService, ISMSService
        ]
        
        for interface in interfaces:
            assert interface.__doc__ is not None
            assert len(interface.__doc__.strip()) > 0
    
    def test_abstract_methods_have_docstrings(self):
        """Test that abstract methods have documentation."""
        # Test a few key interfaces
        test_interfaces = [IOpenAIService, IEmailService, ITranslationService]
        
        for interface in test_interfaces:
            for attr_name in dir(interface):
                attr = getattr(interface, attr_name)
                if (hasattr(attr, '__isabstractmethod__') and 
                    getattr(attr, '__isabstractmethod__', False)):
                    assert attr.__doc__ is not None
                    assert len(attr.__doc__.strip()) > 0


class TestChildSafetyConsiderations:
    """Test child safety considerations in interface design."""
    
    def test_web_search_service_safe_by_default(self):
        """Test web search service is safe by default."""
        import inspect
        
        method = IWebSearchService.search
        sig = inspect.signature(method)
        
        # Safe search should be enabled by default
        assert sig.parameters['safe_search'].default is True
    
    def test_content_moderation_interface_exists(self):
        """Test that content moderation is included in AI interfaces."""
        # OpenAI service includes content moderation
        assert hasattr(IOpenAIService, 'moderate_content')
        method = getattr(IOpenAIService, 'moderate_content')
        assert getattr(method, '__isabstractmethod__', False) is True
    
    def test_image_generation_safe_parameters(self):
        """Test image generation interface has safe parameter structure."""
        import inspect
        
        method = IImageGenerationService.generate_image
        sig = inspect.signature(method)
        
        # Should have prompt parameter for content control
        assert 'prompt' in sig.parameters
        
        # Should have style parameter for artistic control
        assert 'style' in sig.parameters


class TestInterfaceRefactoringNeeds:
    """Identify areas needing refactoring in interfaces."""
    
    def test_numpy_import_concern(self):
        """
        REFACTORING NEEDED: Numpy import may not be used.
        
        The interfaces module imports numpy but may not actually use it.
        This creates an unnecessary dependency.
        
        Recommendation:
        1. Remove numpy import if not used
        2. If vector operations are needed, use List[float] instead
        3. Consider moving vector-specific types to a separate module
        """
        # Check if numpy is actually used in the interfaces
        import inspect
        import src.interfaces.external as ext_module
        
        source = inspect.getsource(ext_module)
        
        # If numpy is imported but not used in type hints or code
        if 'import numpy as np' in source:
            # Check if np is actually used
            np_usage_count = source.count('np.')
            if np_usage_count == 0:
                # Document the refactoring need
                assert True  # This documents the unused import issue
    
    def test_optional_parameter_consistency(self):
        """
        REFACTORING NEEDED: Inconsistent Optional parameter usage.
        
        Some interfaces use Optional[] consistently while others don't.
        This could lead to type checking issues.
        
        Recommendation:
        1. Standardize Optional[] usage across all interfaces
        2. Use Union[] consistently for multiple types
        3. Ensure all optional parameters have defaults
        """
        # This documents the consistency concern
        assert True  # Placeholder for refactoring documentation
    
    def test_error_handling_interfaces_missing(self):
        """
        REFACTORING NEEDED: No error handling interfaces defined.
        
        The interfaces don't define standard error types or error handling patterns.
        This could lead to inconsistent error handling across implementations.
        
        Recommendation:
        1. Define standard exception types for external service errors
        2. Add error handling methods to interfaces where appropriate
        3. Consider adding health check methods to all service interfaces
        """
        # This documents the error handling gap
        assert True  # Placeholder for refactoring documentation


class TestInterfaceUsagePatterns:
    """Test common usage patterns for interfaces."""
    
    @pytest.mark.asyncio
    async def test_service_composition_pattern(self):
        """Test how interfaces can be composed together (NON-TTS example)."""
        class CompositeService:
            def __init__(self, ai_service: IOpenAIService, translation_service: ITranslationService):
                self.ai_service = ai_service
                self.translation_service = translation_service
            
            async def generate_and_translate(self, prompt: str, target_language: str):
                text_response = await self.ai_service.generate_completion(prompt)
                translated_result = await self.translation_service.translate(text_response, target_language)
                return translated_result
        
        # Mock services
        mock_ai = AsyncMock(spec=IOpenAIService)
        mock_ai.generate_completion.return_value = "Hello world"
        
        mock_translation = AsyncMock(spec=ITranslationService)
        mock_translation.translate.return_value = "Hola mundo"
        
        composite = CompositeService(mock_ai, mock_translation)
        result = await composite.generate_and_translate("Say hello", "es")
        
        assert result == "Hola mundo"
        mock_ai.generate_completion.assert_called_once_with("Say hello")
        mock_translation.translate.assert_called_once_with("Hello world", "es")
    
    def test_dependency_injection_pattern(self):
        """Test dependency injection pattern with interfaces."""
        def create_ai_pipeline(
            ai_service: IOpenAIService,
            translation_service: ITranslationService,
            email_service: IEmailService
        ):
            """Factory function that accepts interface dependencies."""
            return {
                'ai': ai_service,
                'translation': translation_service,
                'email': email_service
            }
        
        # Mock services
        mock_ai = Mock(spec=IOpenAIService)
        mock_translation = Mock(spec=ITranslationService)
        mock_email = Mock(spec=IEmailService)
        
        pipeline = create_ai_pipeline(mock_ai, mock_translation, mock_email)
        
        assert isinstance(pipeline['ai'], IOpenAIService)
        assert isinstance(pipeline['translation'], ITranslationService)
        assert isinstance(pipeline['email'], IEmailService)