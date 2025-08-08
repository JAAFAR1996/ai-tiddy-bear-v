"""
Unit tests for GenerateAIResponseUseCase
Tests AI response generation with COPPA compliance
"""

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

from src.application.use_cases.generate_ai_response import GenerateAIResponseUseCase
from src.shared.dto.ai_response import AIResponse


class TestGenerateAIResponseUseCase:
    """Test GenerateAIResponseUseCase functionality."""

    @pytest.fixture
    def mock_ai_service(self):
        """Mock AI orchestration service."""
        mock_service = Mock()
        mock_service.get_ai_response = AsyncMock(return_value=AIResponse(
            content="Hello! How can I help you today?",
            confidence=0.95,
            safe=True,
            safety_score=0.98
        ))
        return mock_service

    @pytest.fixture
    def mock_audio_service(self):
        """Mock audio processing service."""
        mock_service = Mock()
        mock_service.generate_audio_response = AsyncMock(return_value=b"audio_data")
        return mock_service

    @pytest.fixture
    def mock_consent_manager(self):
        """Mock consent manager."""
        mock_manager = Mock()
        mock_manager.verify_consent = AsyncMock(return_value=True)
        return mock_manager

    @pytest.fixture
    def use_case(self, mock_ai_service, mock_audio_service):
        """Create use case instance."""
        return GenerateAIResponseUseCase(
            ai_orchestration_service=mock_ai_service,
            audio_processing_service=mock_audio_service
        )

    @pytest.fixture
    def use_case_with_consent(self, mock_ai_service, mock_audio_service, mock_consent_manager):
        """Create use case with consent manager."""
        return GenerateAIResponseUseCase(
            ai_orchestration_service=mock_ai_service,
            audio_processing_service=mock_audio_service,
            consent_manager=mock_consent_manager
        )

    @pytest.mark.asyncio
    async def test_execute_without_consent_check(self, use_case):
        """Test basic execution without consent verification."""
        child_id = uuid4()
        conversation_history = ["Hello", "Hi there!"]
        current_input = "How are you?"
        voice_id = "voice_123"

        result = await use_case.execute(
            child_id=child_id,
            conversation_history=conversation_history,
            current_input=current_input,
            voice_id=voice_id
        )

        assert isinstance(result, AIResponse)
        assert result.content == "Hello! How can I help you today?"
        assert result.audio_response == b"audio_data"

    @pytest.mark.asyncio
    async def test_execute_with_valid_consent(self, use_case_with_consent, mock_consent_manager):
        """Test execution with valid parental consent."""
        child_id = uuid4()
        parent_id = "parent_123"
        
        result = await use_case_with_consent.execute(
            child_id=child_id,
            conversation_history=["Hello"],
            current_input="How are you?",
            voice_id="voice_123",
            parent_id=parent_id
        )

        # Verify consent was checked for all required types
        assert mock_consent_manager.verify_consent.call_count == 3
        calls = mock_consent_manager.verify_consent.call_args_list
        consent_types = [call[1]['operation'] for call in calls]
        
        assert "data_collection" in consent_types
        assert "voice_recording" in consent_types
        assert "usage_analytics" in consent_types
        
        assert isinstance(result, AIResponse)

    @pytest.mark.asyncio
    async def test_execute_with_missing_consent(self, use_case_with_consent, mock_consent_manager):
        """Test execution fails with missing consent."""
        mock_consent_manager.verify_consent = AsyncMock(return_value=False)
        
        child_id = uuid4()
        parent_id = "parent_123"

        with pytest.raises(Exception) as exc_info:
            await use_case_with_consent.execute(
                child_id=child_id,
                conversation_history=["Hello"],
                current_input="How are you?",
                voice_id="voice_123",
                parent_id=parent_id
            )

        assert "Parental consent required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_with_parent_id_but_no_consent_manager(self, use_case):
        """Test execution fails when parent_id provided but no consent manager."""
        child_id = uuid4()
        parent_id = "parent_123"

        with pytest.raises(Exception) as exc_info:
            await use_case.execute(
                child_id=child_id,
                conversation_history=["Hello"],
                current_input="How are you?",
                voice_id="voice_123",
                parent_id=parent_id
            )

        assert "Consent manager required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ai_service_integration(self, use_case, mock_ai_service):
        """Test integration with AI service."""
        child_id = uuid4()
        conversation_history = ["Previous message"]
        current_input = "New input"
        voice_id = "voice_456"

        await use_case.execute(
            child_id=child_id,
            conversation_history=conversation_history,
            current_input=current_input,
            voice_id=voice_id
        )

        mock_ai_service.get_ai_response.assert_called_once_with(
            child_id,
            conversation_history,
            current_input,
            voice_id
        )

    @pytest.mark.asyncio
    async def test_audio_service_integration(self, use_case, mock_audio_service):
        """Test integration with audio service."""
        child_id = uuid4()
        voice_id = "voice_789"

        await use_case.execute(
            child_id=child_id,
            conversation_history=[],
            current_input="Test input",
            voice_id=voice_id
        )

        mock_audio_service.generate_audio_response.assert_called_once_with(
            "Hello! How can I help you today?",
            voice_id
        )

    @pytest.mark.asyncio
    async def test_consent_verification_error_handling(self, use_case_with_consent, mock_consent_manager):
        """Test handling of consent verification errors."""
        mock_consent_manager.verify_consent = AsyncMock(side_effect=Exception("Consent service error"))
        
        child_id = uuid4()
        parent_id = "parent_123"

        with pytest.raises(Exception) as exc_info:
            await use_case_with_consent.execute(
                child_id=child_id,
                conversation_history=["Hello"],
                current_input="How are you?",
                voice_id="voice_123",
                parent_id=parent_id
            )

        assert "Error during consent verification" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_conversation_history(self, use_case):
        """Test execution with empty conversation history."""
        child_id = uuid4()
        
        result = await use_case.execute(
            child_id=child_id,
            conversation_history=[],
            current_input="First message",
            voice_id="voice_123"
        )

        assert isinstance(result, AIResponse)
        assert result.content == "Hello! How can I help you today?"

    @pytest.mark.asyncio
    async def test_long_conversation_history(self, use_case):
        """Test execution with long conversation history."""
        child_id = uuid4()
        long_history = [f"Message {i}" for i in range(100)]
        
        result = await use_case.execute(
            child_id=child_id,
            conversation_history=long_history,
            current_input="Latest message",
            voice_id="voice_123"
        )

        assert isinstance(result, AIResponse)

    def test_use_case_initialization(self, mock_ai_service, mock_audio_service):
        """Test use case initialization."""
        use_case = GenerateAIResponseUseCase(
            ai_orchestration_service=mock_ai_service,
            audio_processing_service=mock_audio_service
        )
        
        assert use_case.ai_orchestration_service == mock_ai_service
        assert use_case.audio_processing_service == mock_audio_service
        assert use_case._consent_manager is None

    def test_use_case_initialization_with_consent(self, mock_ai_service, mock_audio_service, mock_consent_manager):
        """Test use case initialization with consent manager."""
        use_case = GenerateAIResponseUseCase(
            ai_orchestration_service=mock_ai_service,
            audio_processing_service=mock_audio_service,
            consent_manager=mock_consent_manager
        )
        
        assert use_case._consent_manager == mock_consent_manager