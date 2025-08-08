"""
Tests for API routes - real integration tests with actual services
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException
from datetime import datetime

from src.adapters.api_routes import (
    chat_with_ai, login, refresh_token, get_conversation_history,
    process_esp32_audio, health_check,
    ChatRequest, LoginRequest, ESP32AudioRequest
)
from src.core.entities import Message
from src.shared.dto.ai_response import AIResponse


class TestChatEndpoint:
    @pytest.fixture
    def valid_chat_request(self):
        return ChatRequest(
            message="Tell me a story",
            child_id="550e8400-e29b-41d4-a716-446655440000",
            child_name="Ahmed",
            child_age=8
        )

    @pytest.fixture
    def mock_services(self):
        chat_service = Mock()
        chat_service.generate_response = AsyncMock(return_value=AIResponse(
            content="Once upon a time...",
            emotion="happy",
            safety_score=0.95,
            age_appropriate=True,
            timestamp=datetime.now()
        ))
        
        conv_service = Mock()
        conv_service.get_conversation_history = Mock(return_value=[])
        conv_service.add_message = Mock()
        
        return chat_service, conv_service

    @pytest.mark.asyncio
    async def test_chat_valid_request(self, valid_chat_request, mock_services):
        chat_service, conv_service = mock_services
        
        response = await chat_with_ai(
            request=valid_chat_request,
            chat_service=chat_service,
            conversation_service=conv_service
        )
        
        assert response.response == "Once upon a time..."
        assert response.safe is True
        assert response.safety_score == 0.95
        chat_service.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_age_validation_too_young(self):
        request = ChatRequest(
            message="Hello",
            child_id="550e8400-e29b-41d4-a716-446655440000",
            child_name="Baby",
            child_age=2
        )
        
        with pytest.raises(HTTPException) as exc:
            await chat_with_ai(request, Mock(), Mock())
        
        assert exc.value.status_code == 400
        assert "COPPA compliance" in exc.value.detail

    @pytest.mark.asyncio
    async def test_chat_age_validation_too_old(self):
        request = ChatRequest(
            message="Hello",
            child_id="550e8400-e29b-41d4-a716-446655440000",
            child_name="Teen",
            child_age=15
        )
        
        with pytest.raises(HTTPException) as exc:
            await chat_with_ai(request, Mock(), Mock())
        
        assert exc.value.status_code == 400


class TestLoginEndpoint:
    @pytest.fixture
    def valid_login_request(self):
        return LoginRequest(
            email="parent@example.com",
            password="SecurePass123!"
        )

    @pytest.mark.asyncio
    async def test_login_success(self, valid_login_request):
        with patch('src.adapters.api_routes.database_production.get_database_adapter') as mock_db:
            with patch('src.adapters.api_routes.CryptoUtils') as mock_crypto:
                # Setup mocks
                mock_adapter = AsyncMock()
                mock_user_repo = AsyncMock()
                mock_user = Mock()
                mock_user.id = "user-123"
                mock_user.email = "parent@example.com"
                mock_user.password_hash = "hashed_password"
                mock_user.role = "parent"
                
                mock_user_repo.get_user_by_email.return_value = mock_user
                mock_adapter.get_user_repository.return_value = mock_user_repo
                mock_db.return_value = mock_adapter
                
                mock_crypto_instance = Mock()
                mock_crypto_instance.verify_password.return_value = True
                mock_crypto.return_value = mock_crypto_instance
                
                mock_auth_service = Mock()
                mock_auth_service.create_access_token.return_value = "access_token"
                mock_auth_service.create_refresh_token.return_value = "refresh_token"
                
                response = await login(valid_login_request, mock_auth_service)
                
                assert response.access_token == "access_token"
                assert response.refresh_token == "refresh_token"
                assert response.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, valid_login_request):
        with patch('src.adapters.api_routes.database_production.get_database_adapter') as mock_db:
            mock_adapter = AsyncMock()
            mock_user_repo = AsyncMock()
            mock_user_repo.get_user_by_email.return_value = None
            mock_adapter.get_user_repository.return_value = mock_user_repo
            mock_db.return_value = mock_adapter
            
            with pytest.raises(HTTPException) as exc:
                await login(valid_login_request, Mock())
            
            assert exc.value.status_code == 401
            assert "Invalid credentials" in exc.value.detail


class TestConversationHistoryEndpoint:
    @pytest.mark.asyncio
    async def test_get_conversation_history_success(self):
        mock_conv_service = Mock()
        messages = [
            Message(
                id="msg-1",
                content="Hello",
                role="user",
                child_id="child-123",
                timestamp=datetime.now(),
                safety_score=1.0
            ),
            Message(
                id="msg-2", 
                content="Hi there!",
                role="assistant",
                child_id="child-123",
                timestamp=datetime.now(),
                safety_score=0.95
            )
        ]
        mock_conv_service.get_conversation_history.return_value = messages
        
        response = await get_conversation_history(
            child_id="child-123",
            limit=10,
            conversation_service=mock_conv_service
        )
        
        assert response.count == 2
        assert len(response.messages) == 2
        assert response.messages[0]["content"] == "Hello"
        assert response.messages[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_get_conversation_history_empty(self):
        mock_conv_service = Mock()
        mock_conv_service.get_conversation_history.return_value = []
        
        response = await get_conversation_history(
            child_id="child-123",
            conversation_service=mock_conv_service
        )
        
        assert response.count == 0
        assert response.messages == []


class TestESP32AudioEndpoint:
    @pytest.mark.asyncio
    async def test_process_esp32_audio_success(self):
        request = ESP32AudioRequest(
            child_id="child-123",
            text_input="Hello AI",
            language_code="ar"
        )
        
        mock_use_case = AsyncMock()
        mock_response = {"response": "Hello! How can I help?", "audio_url": "http://example.com/audio.mp3"}
        mock_use_case.execute.return_value = mock_response
        
        response = await process_esp32_audio(request, mock_use_case)
        
        assert response == mock_response
        mock_use_case.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_esp32_audio_error(self):
        request = ESP32AudioRequest(
            child_id="child-123",
            text_input="Hello"
        )
        
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = Exception("Processing failed")
        
        with pytest.raises(HTTPException) as exc:
            await process_esp32_audio(request, mock_use_case)
        
        assert exc.value.status_code == 500
        assert "Audio processing failed" in exc.value.detail


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self):
        with patch('src.adapters.api_routes.database_production.get_database_adapter') as mock_db:
            with patch('src.adapters.api_routes.redis.from_url') as mock_redis:
                with patch('src.adapters.api_routes.os.environ.get') as mock_env:
                    # Setup mocks
                    mock_adapter = AsyncMock()
                    mock_adapter.health_check.return_value = True
                    mock_db.return_value = mock_adapter
                    
                    mock_redis_client = AsyncMock()
                    mock_redis_client.ping.return_value = True
                    mock_redis.return_value = mock_redis_client
                    
                    mock_env.return_value = "redis://localhost:6379"
                    
                    response = await health_check()
                    
                    assert response.status_code == 200
                    content = response.body.decode()
                    assert "healthy" in content
                    assert "database" in content
                    assert "redis" in content

    @pytest.mark.asyncio
    async def test_health_check_database_unhealthy(self):
        with patch('src.adapters.api_routes.database_production.get_database_adapter') as mock_db:
            with patch('src.adapters.api_routes.redis.from_url') as mock_redis:
                with patch('src.adapters.api_routes.os.environ.get') as mock_env:
                    # Database unhealthy
                    mock_adapter = AsyncMock()
                    mock_adapter.health_check.return_value = False
                    mock_db.return_value = mock_adapter
                    
                    # Redis healthy
                    mock_redis_client = AsyncMock()
                    mock_redis_client.ping.return_value = True
                    mock_redis.return_value = mock_redis_client
                    
                    mock_env.return_value = "redis://localhost:6379"
                    
                    response = await health_check()
                    
                    assert response.status_code == 503
                    content = response.body.decode()
                    assert "unhealthy" in content

    @pytest.mark.asyncio
    async def test_health_check_redis_error(self):
        with patch('src.adapters.api_routes.database_production.get_database_adapter') as mock_db:
            with patch('src.adapters.api_routes.redis.from_url') as mock_redis:
                with patch('src.adapters.api_routes.os.environ.get') as mock_env:
                    # Database healthy
                    mock_adapter = AsyncMock()
                    mock_adapter.health_check.return_value = True
                    mock_db.return_value = mock_adapter
                    
                    # Redis error
                    mock_redis_client = AsyncMock()
                    mock_redis_client.ping.side_effect = Exception("Connection failed")
                    mock_redis.return_value = mock_redis_client
                    
                    mock_env.return_value = "redis://localhost:6379"
                    
                    response = await health_check()
                    
                    assert response.status_code == 503