"""
Tests for UserService - real user management functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from datetime import datetime

from src.application.services.user_service import UserService


class TestUserService:
    @pytest.fixture
    def mock_user_repo(self):
        return Mock()

    @pytest.fixture
    def mock_child_repo(self):
        return Mock()

    @pytest.fixture
    def user_service(self, mock_user_repo, mock_child_repo):
        return UserService(mock_user_repo, mock_child_repo)

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service, mock_user_repo):
        """Test successful user creation."""
        user_data = {
            "email": "parent@example.com",
            "password_hash": "hashed_password",
            "first_name": "John",
            "last_name": "Doe"
        }
        
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user_repo.create_user.return_value = mock_user
        
        result = await user_service.create_user(user_data)
        
        assert result == mock_user
        mock_user_repo.create_user.assert_called_once_with(**user_data)

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, user_service, mock_user_repo):
        """Test getting user by ID when found."""
        user_id = uuid4()
        mock_user = Mock()
        mock_user_repo.get_user_by_id.return_value = mock_user
        
        result = await user_service.get_user_by_id(user_id)
        
        assert result == mock_user
        mock_user_repo.get_user_by_id.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_service, mock_user_repo):
        """Test getting user by ID when not found."""
        user_id = uuid4()
        mock_user_repo.get_user_by_id.return_value = None
        
        result = await user_service.get_user_by_id(user_id)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_email_found(self, user_service, mock_user_repo):
        """Test getting user by email when found."""
        email = "parent@example.com"
        mock_user = Mock()
        mock_user_repo.get_user_by_email.return_value = mock_user
        
        result = await user_service.get_user_by_email(email)
        
        assert result == mock_user
        mock_user_repo.get_user_by_email.assert_called_once_with(email)

    @pytest.mark.asyncio
    async def test_update_user_success(self, user_service, mock_user_repo):
        """Test successful user update."""
        user_id = uuid4()
        update_data = {"first_name": "Jane"}
        
        mock_user = Mock()
        mock_user_repo.update_user.return_value = mock_user
        
        result = await user_service.update_user(user_id, update_data)
        
        assert result == mock_user
        mock_user_repo.update_user.assert_called_once_with(user_id, update_data)

    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_service, mock_user_repo):
        """Test successful user deletion."""
        user_id = uuid4()
        mock_user_repo.delete_user.return_value = True
        
        result = await user_service.delete_user(user_id)
        
        assert result is True
        mock_user_repo.delete_user.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_create_child_profile_success(self, user_service, mock_child_repo):
        """Test successful child profile creation."""
        parent_id = uuid4()
        child_data = {
            "name": "Emma",
            "age": 8,
            "interests": ["animals", "stories"]
        }
        
        mock_child = Mock()
        mock_child.id = uuid4()
        mock_child_repo.create_child.return_value = mock_child
        
        result = await user_service.create_child_profile(parent_id, child_data)
        
        assert result == mock_child
        mock_child_repo.create_child.assert_called_once_with(
            parent_id=parent_id, **child_data
        )

    @pytest.mark.asyncio
    async def test_get_children_by_parent(self, user_service, mock_child_repo):
        """Test getting children by parent ID."""
        parent_id = uuid4()
        mock_children = [Mock(), Mock()]
        mock_child_repo.get_children_by_parent.return_value = mock_children
        
        result = await user_service.get_children_by_parent(parent_id)
        
        assert result == mock_children
        mock_child_repo.get_children_by_parent.assert_called_once_with(parent_id)

    @pytest.mark.asyncio
    async def test_get_child_by_id_found(self, user_service, mock_child_repo):
        """Test getting child by ID when found."""
        child_id = uuid4()
        mock_child = Mock()
        mock_child_repo.get_child_by_id.return_value = mock_child
        
        result = await user_service.get_child_by_id(child_id)
        
        assert result == mock_child
        mock_child_repo.get_child_by_id.assert_called_once_with(child_id)

    @pytest.mark.asyncio
    async def test_update_child_profile_success(self, user_service, mock_child_repo):
        """Test successful child profile update."""
        child_id = uuid4()
        update_data = {"interests": ["dinosaurs", "space"]}
        
        mock_child = Mock()
        mock_child_repo.update_child.return_value = mock_child
        
        result = await user_service.update_child_profile(child_id, update_data)
        
        assert result == mock_child
        mock_child_repo.update_child.assert_called_once_with(child_id, update_data)

    @pytest.mark.asyncio
    async def test_delete_child_profile_success(self, user_service, mock_child_repo):
        """Test successful child profile deletion."""
        child_id = uuid4()
        mock_child_repo.delete_child.return_value = True
        
        result = await user_service.delete_child_profile(child_id)
        
        assert result is True
        mock_child_repo.delete_child.assert_called_once_with(child_id)

    @pytest.mark.asyncio
    async def test_get_usage_summary(self, user_service):
        """Test getting usage summary for parent."""
        parent_id = uuid4()
        
        # Mock implementation would aggregate data from multiple sources
        result = await user_service.get_usage_summary(parent_id)
        
        # Should return usage statistics
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_child_usage_report(self, user_service):
        """Test getting detailed usage report for child."""
        child_id = uuid4()
        
        # Mock implementation would gather comprehensive child data
        result = await user_service.get_child_usage_report(child_id)
        
        # Should return detailed child report
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_notifications(self, user_service):
        """Test getting notifications for parent."""
        parent_id = uuid4()
        
        # Mock implementation would fetch notifications
        result = await user_service.get_notifications(parent_id)
        
        # Should return list of notifications
        assert isinstance(result, list)