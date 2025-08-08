"""Comprehensive unit tests for application dependencies with 100% coverage."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import Depends

from src.application.dependencies import (
    get_chat_service,
    get_auth_service,
    get_conversation_service,
    get_child_safety_service,
    get_ai_service,
    get_audio_service,
    get_notification_service,
    get_user_service,
    get_user_repository,
    get_child_repository,
    get_conversation_repository,
    get_message_repository,
    ChatServiceDep,
    AuthServiceDep,
    ConversationServiceDep,
    ChildSafetyServiceDep,
    AIServiceDep,
    AudioServiceDep,
    NotificationServiceDep,
    UserServiceDep,
    UserRepositoryDep,
    ChildRepositoryDep,
    ConversationRepositoryDep,
    MessageRepositoryDep,
)
from src.interfaces.services import (
    IAuthService,
    IChildSafetyService,
    IAIService,
)


class TestDependencyGetters:
    """Test all dependency getter functions."""
    
    @patch('src.application.dependencies.get_injector')
    def test_get_chat_service(self, mock_get_injector):
        """Test get_chat_service returns correct instance."""
        # Arrange
        mock_service = Mock()
        mock_injector = Mock()
        mock_injector.get.return_value = mock_service
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_chat_service()
        
        # Assert
        assert result == mock_service
        mock_injector.get.assert_called_once_with('ChatService')
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_auth_service(self, mock_get_injector):
        """Test get_auth_service returns correct instance."""
        # Arrange
        mock_service = Mock(spec=IAuthService)
        mock_injector = Mock()
        mock_injector.get.return_value = mock_service
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_auth_service()
        
        # Assert
        assert result == mock_service
        mock_injector.get.assert_called_once_with(IAuthService)
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_conversation_service(self, mock_get_injector):
        """Test get_conversation_service returns correct instance."""
        # Arrange
        mock_service = Mock()
        mock_injector = Mock()
        mock_injector.get.return_value = mock_service
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_conversation_service()
        
        # Assert
        assert result == mock_service
        mock_injector.get.assert_called_once_with('ConversationService')
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_child_safety_service(self, mock_get_injector):
        """Test get_child_safety_service returns correct instance."""
        # Arrange
        mock_service = Mock(spec=IChildSafetyService)
        mock_injector = Mock()
        mock_injector.get.return_value = mock_service
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_child_safety_service()
        
        # Assert
        assert result == mock_service
        mock_injector.get.assert_called_once_with(IChildSafetyService)
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_ai_service(self, mock_get_injector):
        """Test get_ai_service returns correct instance."""
        # Arrange
        mock_service = Mock(spec=IAIService)
        mock_injector = Mock()
        mock_injector.get.return_value = mock_service
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_ai_service()
        
        # Assert
        assert result == mock_service
        mock_injector.get.assert_called_once_with(IAIService)
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_audio_service(self, mock_get_injector):
        """Test get_audio_service returns correct instance."""
        # Arrange
        mock_service = Mock()
        mock_injector = Mock()
        mock_injector.get.return_value = mock_service
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_audio_service()
        
        # Assert
        assert result == mock_service
        mock_injector.get.assert_called_once_with('AudioService')
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_notification_service(self, mock_get_injector):
        """Test get_notification_service returns correct instance."""
        # Arrange
        mock_service = Mock()
        mock_injector = Mock()
        mock_injector.get.return_value = mock_service
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_notification_service()
        
        # Assert
        assert result == mock_service
        mock_injector.get.assert_called_once_with('NotificationService')
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_user_service(self, mock_get_injector):
        """Test get_user_service returns correct instance."""
        # Arrange
        mock_service = Mock()
        mock_injector = Mock()
        mock_injector.get.return_value = mock_service
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_user_service()
        
        # Assert
        assert result == mock_service
        mock_injector.get.assert_called_once_with('UserService')
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_user_repository(self, mock_get_injector):
        """Test get_user_repository returns correct instance."""
        # Arrange
        mock_repo = Mock()
        mock_injector = Mock()
        mock_injector.get.return_value = mock_repo
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_user_repository()
        
        # Assert
        assert result == mock_repo
        mock_injector.get.assert_called_once_with('UserRepository')
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_child_repository(self, mock_get_injector):
        """Test get_child_repository returns correct instance."""
        # Arrange
        mock_repo = Mock()
        mock_injector = Mock()
        mock_injector.get.return_value = mock_repo
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_child_repository()
        
        # Assert
        assert result == mock_repo
        mock_injector.get.assert_called_once_with('ChildRepository')
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_conversation_repository(self, mock_get_injector):
        """Test get_conversation_repository returns correct instance."""
        # Arrange
        mock_repo = Mock()
        mock_injector = Mock()
        mock_injector.get.return_value = mock_repo
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_conversation_repository()
        
        # Assert
        assert result == mock_repo
        mock_injector.get.assert_called_once_with('ConversationRepository')
        mock_get_injector.assert_called_once()
    
    @patch('src.application.dependencies.get_injector')
    def test_get_message_repository(self, mock_get_injector):
        """Test get_message_repository returns correct instance."""
        # Arrange
        mock_repo = Mock()
        mock_injector = Mock()
        mock_injector.get.return_value = mock_repo
        mock_get_injector.return_value = mock_injector
        
        # Act
        result = get_message_repository()
        
        # Assert
        assert result == mock_repo
        mock_injector.get.assert_called_once_with('MessageRepository')
        mock_get_injector.assert_called_once()


class TestDependencyMarkers:
    """Test FastAPI dependency markers."""
    
    def test_chat_service_dep(self):
        """Test ChatServiceDep is a Depends instance."""
        assert isinstance(ChatServiceDep, Depends)
        assert ChatServiceDep.dependency == get_chat_service
    
    def test_auth_service_dep(self):
        """Test AuthServiceDep is a Depends instance."""
        assert isinstance(AuthServiceDep, Depends)
        assert AuthServiceDep.dependency == get_auth_service
    
    def test_conversation_service_dep(self):
        """Test ConversationServiceDep is a Depends instance."""
        assert isinstance(ConversationServiceDep, Depends)
        assert ConversationServiceDep.dependency == get_conversation_service
    
    def test_child_safety_service_dep(self):
        """Test ChildSafetyServiceDep is a Depends instance."""
        assert isinstance(ChildSafetyServiceDep, Depends)
        assert ChildSafetyServiceDep.dependency == get_child_safety_service
    
    def test_ai_service_dep(self):
        """Test AIServiceDep is a Depends instance."""
        assert isinstance(AIServiceDep, Depends)
        assert AIServiceDep.dependency == get_ai_service
    
    def test_audio_service_dep(self):
        """Test AudioServiceDep is a Depends instance."""
        assert isinstance(AudioServiceDep, Depends)
        assert AudioServiceDep.dependency == get_audio_service
    
    def test_notification_service_dep(self):
        """Test NotificationServiceDep is a Depends instance."""
        assert isinstance(NotificationServiceDep, Depends)
        assert NotificationServiceDep.dependency == get_notification_service
    
    def test_user_service_dep(self):
        """Test UserServiceDep is a Depends instance."""
        assert isinstance(UserServiceDep, Depends)
        assert UserServiceDep.dependency == get_user_service
    
    def test_user_repository_dep(self):
        """Test UserRepositoryDep is a Depends instance."""
        assert isinstance(UserRepositoryDep, Depends)
        assert UserRepositoryDep.dependency == get_user_repository
    
    def test_child_repository_dep(self):
        """Test ChildRepositoryDep is a Depends instance."""
        assert isinstance(ChildRepositoryDep, Depends)
        assert ChildRepositoryDep.dependency == get_child_repository
    
    def test_conversation_repository_dep(self):
        """Test ConversationRepositoryDep is a Depends instance."""
        assert isinstance(ConversationRepositoryDep, Depends)
        assert ConversationRepositoryDep.dependency == get_conversation_repository
    
    def test_message_repository_dep(self):
        """Test MessageRepositoryDep is a Depends instance."""
        assert isinstance(MessageRepositoryDep, Depends)
        assert MessageRepositoryDep.dependency == get_message_repository


class TestDependencyInjectionIntegration:
    """Test integration scenarios and edge cases."""
    
    @patch('src.application.dependencies.get_injector')
    def test_injector_error_propagation(self, mock_get_injector):
        """Test that injector errors are properly propagated."""
        # Arrange
        mock_injector = Mock()
        mock_injector.get.side_effect = Exception("Injection failed")
        mock_get_injector.return_value = mock_injector
        
        # Act & Assert
        with pytest.raises(Exception, match="Injection failed"):
            get_chat_service()
    
    @patch('src.application.dependencies.get_injector')
    def test_multiple_calls_same_injector(self, mock_get_injector):
        """Test multiple calls use the same injector instance."""
        # Arrange
        mock_injector = Mock()
        mock_get_injector.return_value = mock_injector
        
        # Act
        get_chat_service()
        get_auth_service()
        get_user_repository()
        
        # Assert
        assert mock_get_injector.call_count == 3
        # All calls should use the same injector
        assert all(call[0] == () for call in mock_get_injector.call_args_list)
    
    @patch('src.application.dependencies.get_injector')
    def test_type_checking_with_interfaces(self, mock_get_injector):
        """Test that interface types are properly handled."""
        # Arrange
        mock_auth_service = Mock(spec=IAuthService)
        mock_safety_service = Mock(spec=IChildSafetyService)
        mock_ai_service = Mock(spec=IAIService)
        
        mock_injector = Mock()
        mock_injector.get.side_effect = [
            mock_auth_service,
            mock_safety_service,
            mock_ai_service
        ]
        mock_get_injector.return_value = mock_injector
        
        # Act
        auth = get_auth_service()
        safety = get_child_safety_service()
        ai = get_ai_service()
        
        # Assert
        assert auth == mock_auth_service
        assert safety == mock_safety_service
        assert ai == mock_ai_service
        
        # Verify the correct types were requested
        calls = mock_injector.get.call_args_list
        assert calls[0][0][0] == IAuthService
        assert calls[1][0][0] == IChildSafetyService
        assert calls[2][0][0] == IAIService


class TestModuleImports:
    """Test module imports and structure."""
    
    def test_module_docstring(self):
        """Test module has proper docstring."""
        import src.application.dependencies as deps
        assert deps.__doc__ is not None
        assert "Dependency injection" in deps.__doc__
    
    def test_all_imports_available(self):
        """Test all expected imports are available."""
        import src.application.dependencies as deps
        
        # Service getters
        assert hasattr(deps, 'get_chat_service')
        assert hasattr(deps, 'get_auth_service')
        assert hasattr(deps, 'get_conversation_service')
        assert hasattr(deps, 'get_child_safety_service')
        assert hasattr(deps, 'get_ai_service')
        assert hasattr(deps, 'get_audio_service')
        assert hasattr(deps, 'get_notification_service')
        assert hasattr(deps, 'get_user_service')
        
        # Repository getters
        assert hasattr(deps, 'get_user_repository')
        assert hasattr(deps, 'get_child_repository')
        assert hasattr(deps, 'get_conversation_repository')
        assert hasattr(deps, 'get_message_repository')
        
        # FastAPI dependencies
        assert hasattr(deps, 'ChatServiceDep')
        assert hasattr(deps, 'AuthServiceDep')
        assert hasattr(deps, 'ConversationServiceDep')
        assert hasattr(deps, 'ChildSafetyServiceDep')
        assert hasattr(deps, 'AIServiceDep')
        assert hasattr(deps, 'AudioServiceDep')
        assert hasattr(deps, 'NotificationServiceDep')
        assert hasattr(deps, 'UserServiceDep')
        assert hasattr(deps, 'UserRepositoryDep')
        assert hasattr(deps, 'ChildRepositoryDep')
        assert hasattr(deps, 'ConversationRepositoryDep')
        assert hasattr(deps, 'MessageRepositoryDep')