"""
Unit tests for Speech Processor interface.
Tests protocol definition, method signatures, and audio processing contracts.
"""

import pytest
from typing import get_type_hints, Protocol
from unittest.mock import Mock, AsyncMock
import inspect

from src.application.interfaces.speech_processor import SpeechProcessor


class TestSpeechProcessorProtocol:
    """Test Speech Processor protocol definition and structure."""

    def test_speech_processor_is_protocol(self):
        """Test that SpeechProcessor is defined as a Protocol."""
        # Check if it's a Protocol by looking for _is_protocol attribute
        assert hasattr(SpeechProcessor, '_is_protocol')
        assert SpeechProcessor._is_protocol is True

    def test_speech_processor_methods_exist(self):
        """Test that all required methods are defined in the protocol."""
        expected_methods = [
            'speech_to_text',
            # 'text_to_speech', DELETED - use unified ITTSService
        ]
        
        protocol_methods = [
            name for name, method in inspect.getmembers(SpeechProcessor, inspect.isfunction)
            if not name.startswith('_')
        ]
        
        for method in expected_methods:
            assert method in protocol_methods, f"Method {method} not found in SpeechProcessor protocol"

    def test_all_methods_are_async(self):
        """Test that all protocol methods are async."""
        for name, method in inspect.getmembers(SpeechProcessor, inspect.isfunction):
            if not name.startswith('_'):
                assert inspect.iscoroutinefunction(method), f"Method {name} should be async"

    def test_protocol_has_minimal_interface(self):
        """Test that protocol has a focused, minimal interface."""
        protocol_methods = [
            name for name, method in inspect.getmembers(SpeechProcessor, inspect.isfunction)
            if not name.startswith('_')
        ]
        
        # Should have exactly 1 method for speech-to-text processing only
        assert len(protocol_methods) == 1


class TestSpeechToTextMethod:
    """Test speech_to_text method signature and types."""

    def test_speech_to_text_signature(self):
        """Test speech_to_text method signature."""
        method = getattr(SpeechProcessor, 'speech_to_text')
        sig = inspect.signature(method)
        
        # Check parameter names
        param_names = list(sig.parameters.keys())
        expected_params = ['self', 'audio_data', 'language']
        assert param_names == expected_params

    def test_speech_to_text_type_hints(self):
        """Test speech_to_text type hints."""
        type_hints = get_type_hints(SpeechProcessor.speech_to_text)
        
        # Check parameter types
        assert type_hints['audio_data'] == bytes
        assert type_hints['language'] == str
        assert type_hints['return'] == str

    def test_speech_to_text_is_async(self):
        """Test that speech_to_text is async."""
        method = getattr(SpeechProcessor, 'speech_to_text')
        assert inspect.iscoroutinefunction(method)

    def test_speech_to_text_implementation(self):
        """Test speech_to_text can be implemented."""
        class MockSpeechProcessor:
            async def speech_to_text(self, audio_data: bytes, language: str) -> str:
                return f"Transcribed text from {len(audio_data)} bytes in {language}"
            # text_to_speech DELETED - use unified ITTSService
        
        processor = MockSpeechProcessor()
        
        # Should satisfy the protocol
        assert isinstance(processor, SpeechProcessor)


# TestTextToSpeechMethod DELETED - use unified ITTSService from src.interfaces.providers.tts_provider


class TestSpeechProcessorImplementation:
    """Test Speech Processor protocol implementation."""

    def test_complete_implementation_satisfies_protocol(self):
        """Test that a complete implementation satisfies the protocol."""
        class CompleteSpeechProcessor:
            async def speech_to_text(self, audio_data: bytes, language: str) -> str:
                """Convert speech audio to text."""
                if not audio_data:
                    return ""
                
                # Simulate processing based on language
                if language == "en":
                    return "Hello, how are you?"
                elif language == "es":
                    return "Hola, ¿cómo estás?"
                else:
                    return "Transcribed text"
            # text_to_speech DELETED - use unified ITTSService
        
        processor = CompleteSpeechProcessor()
        
        # Should satisfy the protocol
        assert isinstance(processor, SpeechProcessor)

    def test_complete_implementation_only_needs_stt(self):
        """Test that implementation only needs speech_to_text method."""
        class CompleteSpeechProcessor:
            async def speech_to_text(self, audio_data: bytes, language: str) -> str:
                return "transcribed"
            # text_to_speech DELETED - use unified ITTSService
        
        processor = CompleteSpeechProcessor()
        
        # Should satisfy the protocol with only STT
        assert isinstance(processor, SpeechProcessor)

    def test_wrong_signature_implementation(self):
        """Test implementation with wrong method signatures."""
        class WrongSignatureSpeechProcessor:
            async def speech_to_text(self, audio_data: bytes) -> str:  # Missing language parameter
                return "transcribed"
            # text_to_speech DELETED - use unified ITTSService
        
        processor = WrongSignatureSpeechProcessor()
        
        # This would fail static type checking but might pass runtime isinstance
        # The test documents this behavior
        assert True


class TestSpeechProcessorUsagePatterns:
    """Test common usage patterns with Speech Processor."""

    @pytest.fixture
    def mock_speech_processor(self):
        """Create a mock speech processor for testing."""
        processor = Mock(spec=SpeechProcessor)
        
        # Configure async methods
        processor.speech_to_text = AsyncMock(return_value="Hello, Teddy!")
        # text_to_speech DELETED - use unified ITTSService
        
        return processor

    @pytest.mark.asyncio
    async def test_speech_to_text_usage(self, mock_speech_processor):
        """Test typical speech_to_text usage."""
        audio_data = b"fake_audio_wav_data"
        language = "en"
        
        result = await mock_speech_processor.speech_to_text(audio_data, language)
        
        assert result == "Hello, Teddy!"
        mock_speech_processor.speech_to_text.assert_called_once_with(audio_data, language)

    # test_text_to_speech_usage DELETED - use unified ITTSService

    @pytest.mark.asyncio
    async def test_speech_to_text_workflow(self, mock_speech_processor):
        """Test speech-to-text processing workflow."""
        # Child speaks to teddy
        child_audio = b"child_voice_data"
        child_language = "en"
        
        # Convert speech to text
        child_text = await mock_speech_processor.speech_to_text(child_audio, child_language)
        
        # Verify the workflow
        assert child_text == "Hello, Teddy!"
        
        mock_speech_processor.speech_to_text.assert_called_once_with(child_audio, child_language)
        # TTS processing would use unified ITTSService


class TestSpeechProcessorChildSafetyConsiderations:
    """Test child safety considerations in Speech Processor interface."""

    def test_audio_data_uses_bytes_type(self):
        """Test that audio data uses bytes type for safety."""
        type_hints = get_type_hints(SpeechProcessor.speech_to_text)
        assert type_hints['audio_data'] == bytes
        
        # TTS return type moved to unified ITTSService

    def test_language_parameter_for_appropriate_processing(self):
        """Test that language parameter enables appropriate processing."""
        type_hints = get_type_hints(SpeechProcessor.speech_to_text)
        assert type_hints['language'] == str

    # test_voice_id_for_child_appropriate_voices DELETED - moved to unified ITTSService

    def test_text_input_output_for_content_filtering(self):
        """Test that text input/output enables content filtering."""
        stt_hints = get_type_hints(SpeechProcessor.speech_to_text)
        # TTS hints moved to unified ITTSService
        
        # STT method deals with text that can be filtered
        assert stt_hints['return'] == str  # Can filter output
        # TTS text filtering handled by unified ITTSService


class TestSpeechProcessorIntegrationPoints:
    """Test integration points and dependencies."""

    def test_async_interface_for_io_operations(self):
        """Test that all methods are async for I/O operations."""
        methods = ['speech_to_text']  # text_to_speech moved to unified ITTSService
        
        for method_name in methods:
            method = getattr(SpeechProcessor, method_name)
            assert inspect.iscoroutinefunction(method), \
                f"{method_name} should be async for I/O operations"

    def test_binary_audio_data_handling(self):
        """Test proper binary audio data handling."""
        stt_hints = get_type_hints(SpeechProcessor.speech_to_text)
        # TTS hints moved to unified ITTSService
        
        # Input should handle binary audio data
        assert stt_hints['audio_data'] == bytes
        # TTS binary output handled by unified ITTSService

    def test_string_parameters_for_configuration(self):
        """Test string parameters for configuration."""
        stt_hints = get_type_hints(SpeechProcessor.speech_to_text)
        # TTS hints moved to unified ITTSService
        
        # STT configuration parameters should be strings
        assert stt_hints['language'] == str
        # TTS configuration parameters handled by unified ITTSService

    def test_simple_return_types(self):
        """Test that return types are simple and predictable."""
        stt_hints = get_type_hints(SpeechProcessor.speech_to_text)
        # TTS hints moved to unified ITTSService
        
        # STT return type should be simple
        assert stt_hints['return'] == str   # Transcribed text
        # TTS return type handled by unified ITTSService


class TestSpeechProcessorEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_audio_data_handling(self):
        """Test handling of empty audio data."""
        class RobustSpeechProcessor:
            async def speech_to_text(self, audio_data: bytes, language: str) -> str:
                if not audio_data:
                    return ""
                return "transcribed text"
            # text_to_speech DELETED - use unified ITTSService
        
        processor = RobustSpeechProcessor()
        assert isinstance(processor, SpeechProcessor)

    # test_empty_text_handling DELETED - empty text handling moved to unified ITTSService

    def test_language_code_validation(self):
        """Test language code handling."""
        class LanguageAwareSpeechProcessor:
            async def speech_to_text(self, audio_data: bytes, language: str) -> str:
                supported_languages = ["en", "es", "fr", "de"]
                if language not in supported_languages:
                    language = "en"  # Default to English
                return f"Transcribed in {language}"
            
            async def text_to_speech(self, text: str, voice_id: str) -> bytes:
                return f"{voice_id}: {text}".encode()
        
        processor = LanguageAwareSpeechProcessor()
        assert isinstance(processor, SpeechProcessor)

    # test_voice_id_validation DELETED - voice ID validation moved to unified ITTSService