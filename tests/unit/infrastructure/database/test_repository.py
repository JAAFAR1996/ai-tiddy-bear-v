"""
Tests for Database Repository
============================

Critical tests for repository pattern implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import uuid

from src.infrastructure.database.repository import (
    BaseRepository,
    UserRepository,
    ChildRepository,
    ConversationRepository,
    RepositoryError,
    ValidationError,
    PermissionError,
    NotFoundError,
    RepositoryManager
)


class MockModel:
    """Mock model for testing."""
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


class TestBaseRepository:
    """Test base repository functionality."""

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        class MockRepository(BaseRepository[MockModel]):
            def __init__(self):
                super().__init__(MockModel)
            
            async def _validate_create_data(self, data):
                return data
            
            async def _validate_update_data(self, data, existing_entity):
                return data
            
            async def _check_read_permission(self, entity, user_id):
                return True
            
            async def _check_write_permission(self, entity, user_id):
                return True
            
            async def _check_delete_permission(self, entity, user_id):
                return True
        
        return MockRepository()

    def test_repository_initialization(self, mock_repository):
        """Test repository initialization."""
        assert mock_repository.model_class == MockModel

    def test_involves_child_data(self, mock_repository):
        """Test child data detection."""
        data_with_child = {"child_id": uuid.uuid4(), "content": "test"}
        assert mock_repository._involves_child_data(data_with_child) is True
        
        data_without_child = {"content": "test", "user_id": uuid.uuid4()}
        assert mock_repository._involves_child_data(data_without_child) is False

    @pytest.mark.asyncio
    async def test_validate_child_data_operation(self, mock_repository):
        """Test child data operation validation."""
        user_id = uuid.uuid4()
        child_id = uuid.uuid4()
        data = {"child_id": child_id, "content": "test"}
        
        with patch.object(mock_repository, '_user_can_access_child_data', return_value=True):
            await mock_repository._validate_child_data_operation(data, "create", user_id)

    @pytest.mark.asyncio
    async def test_validate_child_data_operation_permission_denied(self, mock_repository):
        """Test child data operation with permission denied."""
        user_id = uuid.uuid4()
        child_id = uuid.uuid4()
        data = {"child_id": child_id, "content": "test"}
        
        with patch.object(mock_repository, '_user_can_access_child_data', return_value=False):
            with pytest.raises(PermissionError):
                await mock_repository._validate_child_data_operation(data, "create", user_id)


class TestUserRepository:
    """Test user repository."""

    @pytest.fixture
    def user_repo(self):
        """Create user repository."""
        return UserRepository()

    @pytest.mark.asyncio
    async def test_validate_create_data_success(self, user_repo):
        """Test successful user creation validation."""
        data = {"username": "testuser", "role": "parent"}
        
        with patch.object(user_repo, '_username_exists', return_value=False):
            result = await user_repo._validate_create_data(data)
            assert result == data

    @pytest.mark.asyncio
    async def test_validate_create_data_missing_fields(self, user_repo):
        """Test user creation validation with missing fields."""
        data = {"email": "test@example.com"}
        
        with pytest.raises(ValidationError, match="Missing required field"):
            await user_repo._validate_create_data(data)

    @pytest.mark.asyncio
    async def test_check_read_permission_own_data(self, user_repo):
        """Test read permission for own data."""
        user_id = uuid.uuid4()
        user = MockModel(id=user_id, username="testuser")
        
        result = await user_repo._check_read_permission(user, user_id)
        assert result is True


class TestChildRepository:
    """Test child repository."""

    @pytest.fixture
    def child_repo(self):
        """Create child repository."""
        return ChildRepository()

    @pytest.mark.asyncio
    async def test_validate_create_data_success(self, child_repo):
        """Test successful child creation validation."""
        parent_id = uuid.uuid4()
        data = {"parent_id": parent_id, "name": "Test Child"}
        
        with patch.object(child_repo, '_parent_exists', return_value=True):
            result = await child_repo._validate_create_data(data)
            assert result == data

    @pytest.mark.asyncio
    async def test_validate_create_data_coppa_compliance(self, child_repo):
        """Test COPPA compliance validation."""
        parent_id = uuid.uuid4()
        data = {
            "parent_id": parent_id,
            "name": "Young Child",
            "estimated_age": 10,
            "parental_consent": False
        }
        
        with patch.object(child_repo, '_parent_exists', return_value=True):
            with pytest.raises(ValidationError, match="Parental consent required"):
                await child_repo._validate_create_data(data)


class TestRepositoryManager:
    """Test repository manager."""

    @pytest.fixture
    def repo_manager(self):
        """Create repository manager."""
        return RepositoryManager()

    def test_get_repository_valid(self, repo_manager):
        """Test getting valid repository."""
        user_repo = repo_manager.get_repository("user")
        assert isinstance(user_repo, UserRepository)

    def test_get_repository_invalid(self, repo_manager):
        """Test getting invalid repository."""
        with pytest.raises(ValueError, match="No repository found"):
            repo_manager.get_repository("invalid")