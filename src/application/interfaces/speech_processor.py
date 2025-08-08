"""
Speech Processor Interface
===========================

Protocol interface for speech processing services that handle speech-to-text conversion
for child interactions in the AI Teddy Bear system.

This interface provides a unified contract for speech processing while maintaining
COPPA compliance and child safety requirements.

Note:
    Text-to-speech functionality is handled by the unified ITTSService interface
    located at src.interfaces.providers.tts_provider
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SpeechProcessor(Protocol):
    """
    Protocol for speech processing services.
    
    This protocol defines the contract for speech-to-text conversion services
    used in child interactions. All implementations must ensure COPPA compliance
    and appropriate content filtering for children aged 3-13.
    
    Key Requirements:
    - Async-first design for real-time processing
    - Child-safe content handling
    - Language detection and validation
    - Error handling for malformed audio
    - Performance monitoring capabilities
    """
    
    async def speech_to_text(self, audio_data: bytes, language: str) -> str:
        """
        Convert speech audio data to text.
        
        This method processes audio data and returns transcribed text that is
        appropriate for children. All implementations must filter inappropriate
        content and handle COPPA compliance requirements.
        
        Args:
            audio_data: Raw audio data in supported format (WAV, MP3, etc.)
            language: ISO language code (e.g., 'en-US', 'ar-IQ')
            
        Returns:
            Transcribed text string, filtered for child safety
            
        Raises:
            AudioProcessingError: If audio format is invalid or processing fails
            ContentFilteringError: If content is not appropriate for children
            LanguageNotSupportedError: If language is not supported
            SpeechProcessingTimeoutError: If processing exceeds time limits
            
        Safety Requirements:
        - All transcribed content must be filtered for inappropriate language
        - Personal information detection and filtering
        - Age-appropriate vocabulary validation
        - COPPA compliance for data handling
        
        Performance Requirements:
        - Processing should complete within 5 seconds for typical audio clips
        - Support for streaming/chunked audio processing
        - Efficient memory usage for large audio files
        
        Example:
            >>> processor = get_speech_processor()
            >>> audio_bytes = load_audio_file("child_voice.wav")
            >>> text = await processor.speech_to_text(audio_bytes, "en-US")
            >>> print(text)  # "Hello AI teddy bear, can you tell me a story?"
        """
        ...
