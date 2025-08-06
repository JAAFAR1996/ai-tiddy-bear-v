"""
Unit tests for web adapter API endpoints.
Tests FastAPI routes, request validation, response formatting, and error handling.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.adapters.web import router
from src.adapters.api_routes import ChatRequest, ChatResponse, LoginRequest, LoginResponse
from src.core.entities import Message, AIResponse


class TestChatEndpoint:
    """Test suite for /chat endpoint."""

    @pytest.fixture
    def mock_dependencies(self, mock_ai_service, mock_child_safety_service, mock_conversation_repository):
        """Mock all chat endpoint dependencies."""
        with patch("src.adapters.web.get_chat_service") as mock_get_chat:
            with patch("src.adapters.web.get_conversation_service") as mock_get_conv:
                # Setup chat service
                chat_service = Mock()
                chat_service.generate_response = AsyncMock(return_value=AIResponse(
                    content="Once upon a time...",
                    emotion="happy",
                    safety_score=0.95,
                    age_appropriate=True
                ))
                mock_get_chat.return_value = chat_service
                
                # Setup conversation service
                conv_service = Mock()
                conv_service.get_conversation_history = Mock(return_value=[])
                conv_service.add_message = Mock()
                mock_get_conv.return_value = conv_service
                
                yield {
                    "chat_service": chat_service,
                    "conversation_service": conv_service
                }

    @pytest.mark.asyncio
    async def test_chat_valid_request(self, mock_dependencies):
        """Test chat endpoint with valid request."""
        from src.adapters.web import chat_with_ai
        
        request = ChatRequest(
            message="Tell me a story about dinosaurs",
            child_id="child-123",
            child_name="Tommy",
            child_age=7
        )
        
        # Mock dependencies injection
        response = await chat_with_ai(
            request=request,
            chat_service=mock_dependencies["chat_service"],
            conversation_service=mock_dependencies["conversation_service"]
        )
        
        assert isinstance(response, ChatResponse)
        assert response.response == "Once upon a time..."
        assert response.emotion == "happy"
        assert response.safe is True
        assert response.safety_score == 0.95
        assert response.timestamp is not None
        
        # Verify service calls
        mock_dependencies["chat_service"].generate_response.assert_called_once()
        mock_dependencies["conversation_service"].add_message.assert_called()

    @pytest.mark.asyncio
    async def test_chat_age_too_young(self):
        """Test chat endpoint rejects children under 3."""
        from src.adapters.web import chat_with_ai
        
        request = ChatRequest(
            message="Hello",
            child_id="child-baby",
            child_name="Baby",
            child_age=2  # Too young
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await chat_with_ai(
                request=request,
                chat_service=Mock(),
                conversation_service=Mock()
            )
        
        assert exc_info.value.status_code == 400
        assert "COPPA compliance" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_chat_age_too_old(self):
        """Test chat endpoint rejects children over 13."""
        from src.adapters.web import chat_with_ai
        
        request = ChatRequest(
            message="Hello",
            child_id="child-teen",
            child_name="Teen",
            child_age=14  # Too old
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await chat_with_ai(
                request=request,
                chat_service=Mock(),
                conversation_service=Mock()
            )
        
        assert exc_info.value.status_code == 400
        assert "3-13 years" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_chat_with_conversation_history(self, mock_dependencies):
        """Test chat uses conversation history."""
        from src.adapters.web import chat_with_ai
        
        # Setup conversation history
        history = [
            Message(content="Previous message", role="user", child_id="child-123"),
            Message(content="Previous response", role="assistant", child_id="child-123")
        ]
        mock_dependencies["conversation_service"].get_conversation_history.return_value = history
        
        request = ChatRequest(
            message="Continue the story",
            child_id="child-123",
            child_name="Tommy",
            child_age=7
        )
        
        await chat_with_ai(
            request=request,
            chat_service=mock_dependencies["chat_service"],
            conversation_service=mock_dependencies["conversation_service"]
        )
        
        # Verify history was passed to AI service
        call_args = mock_dependencies["chat_service"].generate_response.call_args[1]
        assert call_args["conversation_history"] == history

    @pytest.mark.asyncio
    async def test_chat_saves_messages(self, mock_dependencies):
        """Test chat saves both user and AI messages."""
        from src.adapters.web import chat_with_ai
        
        request = ChatRequest(
            message="User message",
            child_id="child-123",
            child_name="Tommy",
            child_age=7
        )
        
        await chat_with_ai(
            request=request,
            chat_service=mock_dependencies["chat_service"],
            conversation_service=mock_dependencies["conversation_service"]
        )
        
        # Should save exactly 2 messages (user + AI)
        assert mock_dependencies["conversation_service"].add_message.call_count == 2
        
        # Check user message
        user_msg_call = mock_dependencies["conversation_service"].add_message.call_args_list[0]
        user_msg = user_msg_call[0][1]  # Second argument
        assert user_msg.content == "User message"
        assert user_msg.role == "user"
        assert user_msg.child_id == "child-123"
        
        # Check AI message
        ai_msg_call = mock_dependencies["conversation_service"].add_message.call_args_list[1]
        ai_msg = ai_msg_call[0][1]  # Second argument
        assert ai_msg.content == "Once upon a time..."
        assert ai_msg.role == "assistant"

    @pytest.mark.asyncio
    async def test_chat_handles_ai_service_error(self, mock_dependencies):
        """Test chat handles AI service failures gracefully."""
        from src.adapters.web import chat_with_ai
        
        # Make AI service fail
        mock_dependencies["chat_service"].generate_response.side_effect = Exception("AI service error")
        
        request = ChatRequest(
            message="Hello",
            child_id="child-123",
            child_name="Tommy",
            child_age=7
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await chat_with_ai(
                request=request,
                chat_service=mock_dependencies["chat_service"],
                conversation_service=mock_dependencies["conversation_service"]
            )
        
        assert exc_info.value.status_code == 500
        assert "service temporarily unavailable" in exc_info.value.detail.lower()


class TestLoginEndpoint:
    """Test suite for /login endpoint."""

    @pytest.fixture
    def mock_auth_service(self):
        """Mock authentication service."""
        with patch("src.adapters.web.get_auth_service") as mock_get_auth:
            auth_service = Mock()
            auth_service.authenticate = AsyncMock(return_value={
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "user_id": "user-123"
            })
            mock_get_auth.return_value = auth_service
            yield auth_service

    @pytest.mark.asyncio
    async def test_login_valid_credentials(self, mock_auth_service):
        """Test login with valid credentials."""
        from src.adapters.web import login
        
        request = LoginRequest(
            email="parent@example.com",
            password="SecurePassword123!"
        )
        
        response = await login(request, auth_service=mock_auth_service)
        
        assert isinstance(response, LoginResponse)
        assert response.access_token == "test-access-token"
        assert response.refresh_token == "test-refresh-token"
        assert response.token_type == "bearer"
        
        mock_auth_service.authenticate.assert_called_once_with(
            email="parent@example.com",
            password="SecurePassword123!"
        )

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, mock_auth_service):
        """Test login with invalid credentials."""
        from src.adapters.web import login
        
        # Make auth fail
        mock_auth_service.authenticate.return_value = None
        
        request = LoginRequest(
            email="wrong@example.com",
            password="WrongPassword"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await login(request, auth_service=mock_auth_service)
        
        assert exc_info.value.status_code == 401
        assert "Invalid credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_auth_service_error(self, mock_auth_service):
        """Test login handles auth service errors."""
        from src.adapters.web import login
        
        mock_auth_service.authenticate.side_effect = Exception("Database error")
        
        request = LoginRequest(
            email="parent@example.com",
            password="Password123"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await login(request, auth_service=mock_auth_service)
        
        assert exc_info.value.status_code == 500


class TestConversationHistoryEndpoint:
    """Test suite for /conversations/{child_id}/history endpoint."""

    @pytest.fixture
    def mock_conv_service(self):
        """Mock conversation service."""
        with patch("src.adapters.web.get_conversation_service") as mock_get_conv:
            conv_service = Mock()
            conv_service.get_conversation_history = Mock(return_value=[
                Message(
                    id="msg-1",
                    content="Hello AI",
                    role="user",
                    child_id="child-123",
                    timestamp=datetime.now()
                ),
                Message(
                    id="msg-2",
                    content="Hello! How can I help?",
                    role="assistant",
                    child_id="child-123",
                    timestamp=datetime.now()
                )
            ])
            mock_get_conv.return_value = conv_service
            yield conv_service

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, mock_conv_service):
        """Test getting conversation history."""
        from src.adapters.web import get_conversation_history
        
        response = await get_conversation_history(
            child_id="child-123",
            conversation_service=mock_conv_service
        )
        
        assert response.count == 2
        assert len(response.messages) == 2
        assert response.messages[0]["content"] == "Hello AI"
        assert response.messages[0]["role"] == "user"
        assert response.messages[1]["content"] == "Hello! How can I help?"
        assert response.messages[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_get_empty_conversation_history(self, mock_conv_service):
        """Test getting history for child with no conversations."""
        from src.adapters.web import get_conversation_history
        
        mock_conv_service.get_conversation_history.return_value = []
        
        response = await get_conversation_history(
            child_id="child-new",
            conversation_service=mock_conv_service
        )
        
        assert response.count == 0
        assert response.messages == []


class TestHealthEndpoint:
    """Test suite for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check when all services are healthy."""
        from src.adapters.web import health_check
        
        with patch("src.adapters.web.redis.asyncio.from_url") as mock_redis:
            # Mock Redis client
            redis_client = Mock()
            redis_client.ping = AsyncMock(return_value=True)
            mock_redis.return_value = redis_client
            
            with patch("src.adapters.web.database_production.check_database_health") as mock_db:
                mock_db.return_value = AsyncMock(return_value=True)
                
                response = await health_check()
                
                assert response.status_code == 200
                data = response.body.decode()
                assert "healthy" in data
                assert "database" in data
                assert "redis" in data

    @pytest.mark.asyncio
    async def test_health_check_database_failure(self):
        """Test health check when database is down."""
        from src.adapters.web import health_check
        
        with patch("src.adapters.web.redis.asyncio.from_url") as mock_redis:
            redis_client = Mock()
            redis_client.ping = AsyncMock(return_value=True)
            mock_redis.return_value = redis_client
            
            with patch("src.adapters.web.database_production.check_database_health") as mock_db:
                mock_db.return_value = AsyncMock(return_value=False)
                
                response = await health_check()
                
                assert response.status_code == 503
                data = response.body.decode()
                assert "unhealthy" in data

    @pytest.mark.asyncio
    async def test_health_check_redis_failure(self):
        """Test health check when Redis is down."""
        from src.adapters.web import health_check
        
        with patch("src.adapters.web.redis.asyncio.from_url") as mock_redis:
            redis_client = Mock()
            redis_client.ping = AsyncMock(side_effect=Exception("Connection refused"))
            mock_redis.return_value = redis_client
            
            with patch("src.adapters.web.database_production.check_database_health") as mock_db:
                mock_db.return_value = AsyncMock(return_value=True)
                
                response = await health_check()
                
                assert response.status_code == 503


class TestRequestValidation:
    """Test request model validation."""

    def test_chat_request_validation(self):
        """Test ChatRequest model validation."""
        # Valid request
        valid = ChatRequest(
            message="Hello",
            child_id="child-123",
            child_name="Alice",
            child_age=8
        )
        assert valid.message == "Hello"
        assert valid.child_name == "Alice"
        
        # Missing required fields
        with pytest.raises(ValueError):
            ChatRequest(message="Hello")  # Missing child_id and age

    def test_login_request_validation(self):
        """Test LoginRequest email validation."""
        # Valid email
        valid = LoginRequest(
            email="user@example.com",
            password="password123"
        )
        assert valid.email == "user@example.com"
        
        # Invalid email format (basic validation in Pydantic)
        # Note: Detailed email validation may be in the model itself