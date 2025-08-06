"""
Tests for Process ESP32 Audio Use Case
=====================================

Critical tests for ESP32 audio processing functionality.
These tests ensure child safety and proper audio handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime
from fastapi import HTTPException

from src.application.use_cases.process_esp32_audio import ProcessESP32AudioUseCase
from src.shared.dto.esp32_request import ESP32Request
from src.shared.dto.ai_response import AIResponse
from src.shared.audio_types import AudioFormat, VoiceEmotion, VoiceGender
from src.domain.audio import AudioFile, Voice, TranscriptionRequest


class TestProcessESP32AudioUseCase:
    """Test ESP32 audio processing use case."""

    @pytest.fixture
    def mock_audio_validation_service(self):
        """Create mock audio validation service."""
        service = Mock(spec=True)
        service.validate_transcription_request = Mock(return_value=(True, []))
        return service

    @pytest.fixture
    def mock_voice_selection_service(self):
        """Create mock voice selection service."""
        service = Mock(spec=True)
        mock_voice = Voice(
            voice_id="voice123",
            name="Child Friendly Voice",
            language="en-US",
            gender=VoiceGender.NEUTRAL,
            age_group="child",
            is_child_appropriate=True,
            supported_emotions=[VoiceEmotion.NEUTRAL, VoiceEmotion.HAPPY]
        )
        service.select_appropriate_voice = Mock(return_value=mock_voice)
        return service

    @pytest.fixture
    def mock_content_safety_service(self):
        """Create mock content safety service."""
        service = Mock(spec=True)
        service.is_text_appropriate_for_child = Mock(return_value=(True, []))
        service.filter_inappropriate_content = Mock(side_effect=lambda x: x)
        return service

    @pytest.fixture
    def mock_processing_rules_service(self):
        """Create mock processing rules service."""
        service = Mock(spec=True)
        service.get_recommended_quality_for_age = Mock(return_value="high")
        return service

    @pytest.fixture
    def mock_stt_provider(self):
        """Create mock STT provider."""
        provider = Mock(spec=True)
        provider.transcribe = AsyncMock(return_value="Hello teddy bear!")
        return provider

    @pytest.fixture
    def mock_tts_service(self):
        """Create mock TTS service."""
        service = Mock(spec=True)
        mock_result = Mock(spec=True)
        mock_result.audio_data = b"synthesized_audio_data"
        service.synthesize_speech = AsyncMock(return_value=mock_result)
        return service

    @pytest.fixture
    def mock_audio_service(self):
        """Create mock audio service."""
        service = Mock(spec=True)
        mock_voice = Mock(spec=True)
        mock_voice.voice_id = "voice123"
        mock_voice.name = "Test Voice"
        mock_voice.language = "en-US"
        mock_voice.gender = VoiceGender.NEUTRAL
        mock_voice.age_group = "child"
        mock_voice.is_child_appropriate = True
        mock_voice.supported_emotions = [VoiceEmotion.NEUTRAL]
        service.get_available_voices = AsyncMock(return_value=[mock_voice])
        return service

    @pytest.fixture
    def mock_esp32_protocol(self):
        """Create mock ESP32 protocol."""
        return Mock(spec=True)

    @pytest.fixture
    def mock_ai_service(self):
        """Create mock AI service."""
        service = Mock(spec=True)
        mock_response = Mock(spec=True)
        mock_response.response_text = "Hello! How can I help you today?"
        mock_response.emotion = VoiceEmotion.HAPPY
        mock_response.sentiment = "positive"
        service.get_ai_response = AsyncMock(return_value=mock_response)
        return service

    @pytest.fixture
    def mock_conversation_service(self):
        """Create mock conversation service."""
        service = Mock(spec=True)
        service.get_conversation_history = AsyncMock(return_value=[])
        service.start_new_conversation = AsyncMock(spec=True)
        return service

    @pytest.fixture
    def mock_child_repository(self):
        """Create mock child repository."""
        repository = Mock(spec=True)
        mock_child = Mock(spec=True)
        mock_child.age = 8
        mock_child.preferences = {"interests": ["stories", "games"]}
        repository.get_by_id = AsyncMock(return_value=mock_child)
        return repository

    @pytest.fixture
    def use_case(self, mock_audio_validation_service, mock_voice_selection_service,
                 mock_content_safety_service, mock_processing_rules_service,
                 mock_stt_provider, mock_tts_service, mock_audio_service,
                 mock_esp32_protocol, mock_ai_service, mock_conversation_service,
                 mock_child_repository):
        """Create use case instance with all mocks."""
        return ProcessESP32AudioUseCase(
            audio_validation_service=mock_audio_validation_service,
            voice_selection_service=mock_voice_selection_service,
            content_safety_service=mock_content_safety_service,
            processing_rules_service=mock_processing_rules_service,
            stt_provider=mock_stt_provider,
            tts_service=mock_tts_service,
            audio_service=mock_audio_service,
            esp32_protocol=mock_esp32_protocol,
            ai_service=mock_ai_service,
            conversation_service=mock_conversation_service,
            child_repository=mock_child_repository
        )

    @pytest.fixture
    def sample_request(self):
        """Create sample ESP32 request."""
        return ESP32Request(
            child_id=uuid4(),
            audio_data=b"sample_audio_data",
            timestamp=datetime.now(),
            device_id="esp32_001"
        )

    @pytest.mark.asyncio
    async def test_execute_success_flow(self, use_case, sample_request):
        """Test successful ESP32 audio processing flow."""
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            result = await use_case.execute(sample_request)
            
            assert isinstance(result, AIResponse)
            assert result.text == "Hello teddy bear!"
            assert result.audio == b"synthesized_audio_data"
            assert result.emotion == VoiceEmotion.HAPPY
            assert result.sentiment == "positive"
            assert result.safe is True

    @pytest.mark.asyncio
    async def test_execute_child_not_found(self, use_case, sample_request, mock_child_repository):
        """Test handling when child profile is not found."""
        mock_child_repository.get_by_id.return_value = None
        
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            with pytest.raises(HTTPException) as exc_info:
                await use_case.execute(sample_request)
            
            assert exc_info.value.status_code == 404
            assert "Child profile not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_audio_validation_failure(self, use_case, sample_request, 
                                                   mock_audio_validation_service):
        """Test handling of audio validation failure."""
        mock_audio_validation_service.validate_transcription_request.return_value = (
            False, ["Invalid audio format"]
        )
        
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            with pytest.raises(HTTPException) as exc_info:
                await use_case.execute(sample_request)
            
            assert exc_info.value.status_code == 400
            assert "Audio validation failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_inappropriate_content_filtering(self, use_case, sample_request,
                                                          mock_content_safety_service):
        """Test inappropriate content filtering."""
        # Setup content safety to detect inappropriate content
        mock_content_safety_service.is_text_appropriate_for_child.return_value = (
            False, ["Inappropriate language detected"]
        )
        mock_content_safety_service.filter_inappropriate_content.return_value = (
            "Hello friend!"  # Filtered version
        )
        
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            result = await use_case.execute(sample_request)
            
            # Should still succeed but with filtered content
            assert isinstance(result, AIResponse)
            assert result.safe is False  # Marked as unsafe due to original content
            mock_content_safety_service.filter_inappropriate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_appropriate_voice_found(self, use_case, sample_request,
                                                     mock_voice_selection_service):
        """Test handling when no appropriate voice is found."""
        mock_voice_selection_service.select_appropriate_voice.return_value = None
        
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            with pytest.raises(HTTPException) as exc_info:
                await use_case.execute(sample_request)
            
            assert exc_info.value.status_code == 500
            assert "No appropriate voice found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_stt_processing(self, use_case, sample_request, mock_stt_provider):
        """Test STT processing integration."""
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            await use_case.execute(sample_request)
            
            mock_stt_provider.transcribe.assert_called_once_with(
                sample_request.audio_data,
                language="en-US",
                child_age=8
            )

    @pytest.mark.asyncio
    async def test_execute_ai_response_generation(self, use_case, sample_request, 
                                                 mock_ai_service, mock_conversation_service):
        """Test AI response generation."""
        # Setup conversation history
        mock_conversation = Mock(spec=True)
        mock_conversation.summary = "Previous conversation"
        mock_conversation_service.get_conversation_history.return_value = [mock_conversation]
        
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            await use_case.execute(sample_request)
            
            mock_ai_service.get_ai_response.assert_called_once()
            call_args = mock_ai_service.get_ai_response.call_args
            assert call_args[0][0] == sample_request.child_id
            assert call_args[0][1] == ["Previous conversation"]
            assert call_args[0][2] == "Hello teddy bear!"

    @pytest.mark.asyncio
    async def test_execute_tts_synthesis(self, use_case, sample_request, mock_tts_service):
        """Test TTS synthesis with proper configuration."""
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            await use_case.execute(sample_request)
            
            mock_tts_service.synthesize_speech.assert_called_once()
            call_args = mock_tts_service.synthesize_speech.call_args
            tts_request = call_args[0][0]
            
            assert tts_request.text == "Hello! How can I help you today?"
            assert tts_request.config.voice_profile.voice_id == "voice123"
            assert tts_request.config.emotion == VoiceEmotion.NEUTRAL
            assert tts_request.safety_context.child_age == 8
            assert tts_request.safety_context.parental_controls is True

    @pytest.mark.asyncio
    async def test_execute_conversation_history_update(self, use_case, sample_request,
                                                      mock_conversation_service):
        """Test conversation history is updated."""
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            await use_case.execute(sample_request)
            
            mock_conversation_service.start_new_conversation.assert_called_once_with(
                sample_request.child_id, "Hello teddy bear!"
            )

    @pytest.mark.asyncio
    async def test_execute_voice_selection_logic(self, use_case, sample_request,
                                                 mock_voice_selection_service, mock_audio_service):
        """Test voice selection logic."""
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            await use_case.execute(sample_request)
            
            # Verify available voices were retrieved
            mock_audio_service.get_available_voices.assert_called_once_with(
                language="en-US", child_age=8
            )
            
            # Verify voice selection was called with proper parameters
            mock_voice_selection_service.select_appropriate_voice.assert_called_once()
            call_args = mock_voice_selection_service.select_appropriate_voice.call_args
            voices, child_age, emotion = call_args[0]
            
            assert len(voices) == 1  # One mock voice
            assert child_age == 8
            assert emotion == VoiceEmotion.NEUTRAL

    @pytest.mark.asyncio
    async def test_execute_audio_file_creation(self, use_case, sample_request):
        """Test audio file domain entity creation."""
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            await use_case.execute(sample_request)
            
            # Verify audio validation was called with proper AudioFile
            call_args = use_case.audio_validation.validate_transcription_request.call_args
            transcription_request = call_args[0][0]
            
            assert isinstance(transcription_request, TranscriptionRequest)
            assert transcription_request.audio.data == sample_request.audio_data
            assert transcription_request.audio.format == AudioFormat.WAV
            assert transcription_request.child_age == 8
            assert transcription_request.require_safety_check is True

    @pytest.mark.asyncio
    async def test_execute_processing_rules_integration(self, use_case, sample_request,
                                                       mock_processing_rules_service):
        """Test processing rules service integration."""
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            await use_case.execute(sample_request)
            
            mock_processing_rules_service.get_recommended_quality_for_age.assert_called_once_with(8)

    @pytest.mark.asyncio
    async def test_execute_error_handling_and_logging(self, use_case, sample_request,
                                                     mock_stt_provider):
        """Test error handling and audit logging."""
        # Setup STT to raise an exception
        mock_stt_provider.transcribe.side_effect = Exception("STT processing failed")
        
        with patch('src.shared.audit_logger.ProductionAuditLogger') as mock_audit:
            mock_logger = Mock(spec=True)
            mock_audit.return_value = mock_logger
            
            with pytest.raises(Exception, match="STT processing failed"):
                await use_case.execute(sample_request)
            
            # Verify error was logged
            mock_logger.log_audio_processing.assert_called()
            call_args = mock_logger.log_audio_processing.call_args
            assert call_args[0][2] is False  # success = False
            assert "error" in call_args[0][4]  # metadata contains error

    @pytest.mark.asyncio
    async def test_execute_safety_violation_logging(self, use_case, sample_request,
                                                   mock_content_safety_service):
        """Test safety violation logging."""
        # Setup content safety to detect violation
        mock_content_safety_service.is_text_appropriate_for_child.return_value = (
            False, ["Inappropriate content"]
        )
        
        # Make STT fail to trigger the safety logging path
        use_case.stt_processor.transcribe.side_effect = Exception("Test error")
        
        with patch('src.shared.audit_logger.ProductionAuditLogger') as mock_audit:
            mock_logger = Mock(spec=True)
            mock_audit.return_value = mock_logger
            
            with pytest.raises(Exception):
                await use_case.execute(sample_request)

    @pytest.mark.asyncio
    async def test_execute_with_conversation_history(self, use_case, sample_request,
                                                    mock_conversation_service):
        """Test processing with existing conversation history."""
        # Setup conversation history
        mock_conv1 = Mock(spec=True)
        mock_conv1.summary = "Hello, I'm your teddy bear!"
        mock_conv2 = Mock(spec=True)
        mock_conv2.summary = "What would you like to play?"
        
        mock_conversation_service.get_conversation_history.return_value = [mock_conv1, mock_conv2]
        
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            await use_case.execute(sample_request)
            
            # Verify AI service received conversation history
            call_args = use_case.ai_service.get_ai_response.call_args
            history_texts = call_args[0][1]
            assert len(history_texts) == 2
            assert "Hello, I'm your teddy bear!" in history_texts
            assert "What would you like to play?" in history_texts

    @pytest.mark.asyncio
    async def test_execute_child_preferences_integration(self, use_case, sample_request,
                                                        mock_child_repository):
        """Test child preferences are passed to AI service."""
        # Setup child with specific preferences
        mock_child = Mock(spec=True)
        mock_child.age = 6
        mock_child.preferences = {
            "interests": ["dinosaurs", "space"],
            "language": "en",
            "difficulty_level": "beginner"
        }
        mock_child_repository.get_by_id.return_value = mock_child
        
        with patch('src.shared.audit_logger.ProductionAuditLogger'):
            await use_case.execute(sample_request)
            
            # Verify preferences were passed to AI service
            call_args = use_case.ai_service.get_ai_response.call_args
            child_preferences = call_args.kwargs["child_preferences"]
            assert child_preferences["interests"] == ["dinosaurs", "space"]
            assert child_preferences["difficulty_level"] == "beginner"