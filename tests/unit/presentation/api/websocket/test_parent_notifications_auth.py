"""
Test WebSocket Authentication for Parent Notifications
=====================================================
Tests for token authentication in parent WebSocket endpoints.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

from src.infrastructure.security.auth import AuthenticationError
from src.presentation.api.websocket.parent_notifications import (
    parent_notification_websocket,
)


class TestParentNotificationWebSocketAuth:
    """Test authentication for parent notification WebSocket endpoint."""

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket object."""
        websocket = Mock(spec=WebSocket)
        websocket.accept = AsyncMock()
        websocket.close = AsyncMock()
        websocket.send_json = AsyncMock()
        websocket.receive_text = AsyncMock()
        websocket.query_params = {}
        websocket.headers = {}
        return websocket

    @pytest.fixture
    def mock_real_time_service(self):
        """Create mock RealTimeNotificationService."""
        service = Mock()
        service.websocket_adapter = Mock()
        service.websocket_adapter.connect = AsyncMock(return_value="connection_123")
        service.websocket_adapter.disconnect = AsyncMock()
        service.register_parent_connection = AsyncMock()
        return service

    @pytest.fixture
    def mock_token_manager(self):
        """Create mock TokenManager."""
        with patch('src.presentation.api.websocket.parent_notifications.TokenManager') as mock:
            manager = Mock()
            manager.verify_token = AsyncMock()
            mock.return_value = manager
            yield manager

    @pytest.mark.asyncio
    async def test_websocket_auth_with_query_token_success(
        self, mock_websocket, mock_real_time_service, mock_token_manager
    ):
        """Test successful authentication with token in query params."""
        # Setup
        parent_id = "parent_123"
        token = "valid_token_123"
        
        mock_websocket.query_params = {"token": token}
        mock_token_manager.verify_token.return_value = {
            "sub": parent_id,
            "user_type": "parent",
            "role": "parent"
        }
        
        # Mock WebSocketDisconnect to break the while loop
        mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")
        
        # Execute
        try:
            await parent_notification_websocket(
                websocket=mock_websocket,
                parent_id=parent_id,
                real_time_service=mock_real_time_service
            )
        except Exception:
            pass  # Expected due to mocked WebSocketDisconnect
        
        # Verify
        mock_websocket.accept.assert_called_once()
        mock_token_manager.verify_token.assert_called_once_with(token)
        mock_real_time_service.websocket_adapter.connect.assert_called_once()
        mock_real_time_service.register_parent_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_auth_with_header_token_success(
        self, mock_websocket, mock_real_time_service, mock_token_manager
    ):
        """Test successful authentication with token in Authorization header."""
        # Setup
        parent_id = "parent_123"
        token = "valid_token_123"
        
        mock_websocket.query_params = {}
        mock_websocket.headers = {"authorization": f"Bearer {token}"}
        mock_token_manager.verify_token.return_value = {
            "sub": parent_id,
            "user_type": "parent",
            "role": "parent"
        }
        
        # Mock WebSocketDisconnect to break the while loop
        mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")
        
        # Execute
        try:
            await parent_notification_websocket(
                websocket=mock_websocket,
                parent_id=parent_id,
                real_time_service=mock_real_time_service
            )
        except Exception:
            pass  # Expected due to mocked WebSocketDisconnect
        
        # Verify
        mock_websocket.accept.assert_called_once()
        mock_token_manager.verify_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_websocket_auth_missing_token(
        self, mock_websocket, mock_real_time_service, mock_token_manager
    ):
        """Test WebSocket connection rejected when token is missing."""
        # Setup
        parent_id = "parent_123"
        
        mock_websocket.query_params = {}
        mock_websocket.headers = {}
        
        # Execute
        await parent_notification_websocket(
            websocket=mock_websocket,
            parent_id=parent_id,
            real_time_service=mock_real_time_service
        )
        
        # Verify
        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=1008)
        mock_token_manager.verify_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_auth_invalid_token(
        self, mock_websocket, mock_real_time_service, mock_token_manager
    ):
        """Test WebSocket connection rejected with invalid token."""
        # Setup
        parent_id = "parent_123"
        token = "invalid_token_123"
        
        mock_websocket.query_params = {"token": token}
        mock_token_manager.verify_token.side_effect = AuthenticationError("Invalid token")
        
        # Execute
        await parent_notification_websocket(
            websocket=mock_websocket,
            parent_id=parent_id,
            real_time_service=mock_real_time_service
        )
        
        # Verify
        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=1008)
        mock_token_manager.verify_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_websocket_auth_wrong_user_type(
        self, mock_websocket, mock_real_time_service, mock_token_manager
    ):
        """Test WebSocket connection rejected when token is not for parent."""
        # Setup
        parent_id = "parent_123"
        token = "child_token_123"
        
        mock_websocket.query_params = {"token": token}
        mock_token_manager.verify_token.return_value = {
            "sub": "child_123",
            "user_type": "child",
            "role": "child"
        }
        
        # Execute
        await parent_notification_websocket(
            websocket=mock_websocket,
            parent_id=parent_id,
            real_time_service=mock_real_time_service
        )
        
        # Verify
        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=1008)
        mock_token_manager.verify_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_websocket_auth_user_id_mismatch(
        self, mock_websocket, mock_real_time_service, mock_token_manager
    ):
        """Test WebSocket connection rejected when parent_id doesn't match token."""
        # Setup
        parent_id = "parent_123"
        token = "parent_token_456"
        
        mock_websocket.query_params = {"token": token}
        mock_token_manager.verify_token.return_value = {
            "sub": "parent_456",  # Different from parent_id
            "user_type": "parent",
            "role": "parent"
        }
        
        # Execute
        await parent_notification_websocket(
            websocket=mock_websocket,
            parent_id=parent_id,
            real_time_service=mock_real_time_service
        )
        
        # Verify
        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=1008)
        mock_token_manager.verify_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_websocket_auth_token_verification_error(
        self, mock_websocket, mock_real_time_service, mock_token_manager
    ):
        """Test WebSocket connection error during token verification."""
        # Setup
        parent_id = "parent_123"
        token = "token_123"
        
        mock_websocket.query_params = {"token": token}
        mock_token_manager.verify_token.side_effect = Exception("Unexpected error")
        
        # Execute
        await parent_notification_websocket(
            websocket=mock_websocket,
            parent_id=parent_id,
            real_time_service=mock_real_time_service
        )
        
        # Verify
        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=1011)
        mock_token_manager.verify_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_websocket_auth_query_params_priority_over_header(
        self, mock_websocket, mock_real_time_service, mock_token_manager
    ):
        """Test query params token takes priority over header token."""
        # Setup
        parent_id = "parent_123"
        query_token = "query_token_123"
        header_token = "header_token_456"
        
        mock_websocket.query_params = {"token": query_token}
        mock_websocket.headers = {"authorization": f"Bearer {header_token}"}
        mock_token_manager.verify_token.return_value = {
            "sub": parent_id,
            "user_type": "parent",
            "role": "parent"
        }
        
        # Mock WebSocketDisconnect to break the while loop
        mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")
        
        # Execute
        try:
            await parent_notification_websocket(
                websocket=mock_websocket,
                parent_id=parent_id,
                real_time_service=mock_real_time_service
            )
        except Exception:
            pass  # Expected due to mocked WebSocketDisconnect
        
        # Verify - should use query token, not header token
        mock_token_manager.verify_token.assert_called_once_with(query_token)

    @pytest.mark.asyncio
    async def test_websocket_auth_malformed_authorization_header(
        self, mock_websocket, mock_real_time_service, mock_token_manager
    ):
        """Test WebSocket handles malformed Authorization header."""
        # Setup
        parent_id = "parent_123"
        
        mock_websocket.query_params = {}
        mock_websocket.headers = {"authorization": "InvalidFormat token123"}
        
        # Execute
        await parent_notification_websocket(
            websocket=mock_websocket,
            parent_id=parent_id,
            real_time_service=mock_real_time_service
        )
        
        # Verify - should be treated as missing token
        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=1008)
        mock_token_manager.verify_token.assert_not_called()