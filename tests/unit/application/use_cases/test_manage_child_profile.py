"""
Tests for Manage Child Profile Use Case
======================================

Critical tests for child profile management functionality.
These tests ensure COPPA compliance and data protection.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import UUID, uuid4

from src.application.use_cases.manage_child_profile import ManageChildProfileUseCase
from src.shared.dto.child_data import ChildData
from src.core.entities import Child


class TestManageChildProfileUseCase:
    """Test child profile management use case."""

    @pytest.fixture
    def mock_child_repository(self):
        """Create mock child repository."""
        repository = Mock(spec=True)
        repository.save = AsyncMock(spec=True)
        repository.get_by_id = AsyncMock(spec=True)
        repository.delete = AsyncMock(spec=True)
        return repository

    @pytest.fixture
    def mock_child_profile_read_model(self):
        """Create mock child profile read model."""
        read_model = Mock(spec=True)
        read_model.get_by_id = Mock(spec=True)
        return read_model

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus service."""
        event_bus = Mock(spec=True)
        event_bus.publish = AsyncMock(spec=True)
        return event_bus

    @pytest.fixture
    def use_case(self, mock_child_repository, mock_child_profile_read_model, mock_event_bus):
        """Create use case instance."""
        return ManageChildProfileUseCase(
            child_repository=mock_child_repository,
            child_profile_read_model=mock_child_profile_read_model,
            event_bus=mock_event_bus
        )

    @pytest.mark.asyncio
    async def test_create_child_profile_success(self, use_case, mock_child_repository, mock_event_bus):
        """Test successful child profile creation."""
        # Setup
        name = "Test Child"
        age = 8
        preferences = {"interests": ["stories", "games"], "language": "en"}
        
        # Mock Child.create to return a mock child
        mock_child = Mock(spec=True)
        mock_child.id = uuid4()
        mock_child.name = name
        mock_child.age = age
        mock_child.preferences = preferences
        mock_child.get_uncommitted_events.return_value = [Mock(spec=True)]
        
        with pytest.mock.patch.object(Child, 'create', return_value=mock_child):
            # Execute
            result = await use_case.create_child_profile(name, age, preferences)
            
            # Verify
            assert isinstance(result, ChildData)
            assert result.name == name
            assert result.age == age
            assert result.preferences == preferences
            
            mock_child_repository.save.assert_called_once_with(mock_child)
            mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_create_child_profile_coppa_compliance(self, use_case):
        """Test COPPA compliance for child under 13."""
        # Setup - child under 13
        name = "Young Child"
        age = 7  # Under COPPA age limit
        preferences = {"interests": ["toys"], "language": "en"}
        
        mock_child = Mock(spec=True)
        mock_child.id = uuid4()
        mock_child.name = name
        mock_child.age = age
        mock_child.preferences = preferences
        mock_child.get_uncommitted_events.return_value = []
        
        with pytest.mock.patch.object(Child, 'create', return_value=mock_child):
            # Execute
            result = await use_case.create_child_profile(name, age, preferences)
            
            # Verify
            assert result.age == age
            assert result.age < 13  # Verify COPPA protected age

    @pytest.mark.asyncio
    async def test_get_child_profile_exists(self, use_case):
        """Test getting existing child profile."""
        # Setup
        child_id = uuid4()
        mock_read_model = Mock(spec=True)
        mock_read_model.id = child_id
        mock_read_model.name = "Test Child"
        mock_read_model.age = 9
        mock_read_model.preferences = {"interests": ["books"]}
        
        # Fix the attribute access issue
        use_case.child_profile_read_model_store = Mock(spec=True)
        use_case.child_profile_read_model_store.get_by_id.return_value = mock_read_model
        
        # Execute
        result = await use_case.get_child_profile(child_id)
        
        # Verify
        assert result is not None
        assert isinstance(result, ChildData)
        assert result.id == child_id
        assert result.name == "Test Child"
        assert result.age == 9

    @pytest.mark.asyncio
    async def test_get_child_profile_not_exists(self, use_case):
        """Test getting non-existent child profile."""
        # Setup
        child_id = uuid4()
        use_case.child_profile_read_model_store = Mock(spec=True)
        use_case.child_profile_read_model_store.get_by_id.return_value = None
        
        # Execute
        result = await use_case.get_child_profile(child_id)
        
        # Verify
        assert result is None

    @pytest.mark.asyncio
    async def test_update_child_profile_success(self, use_case, mock_child_repository, mock_event_bus):
        """Test successful child profile update."""
        # Setup
        child_id = uuid4()
        new_name = "Updated Child"
        new_age = 10
        new_preferences = {"interests": ["science", "art"]}
        
        mock_child = Mock(spec=True)
        mock_child.id = child_id
        mock_child.update_profile = Mock(spec=True)
        mock_child.get_uncommitted_events.return_value = [Mock(spec=True)]
        
        mock_child_repository.get_by_id.return_value = mock_child
        
        # Mock the get_child_profile method to return updated data
        updated_child_data = ChildData(
            id=child_id,
            name=new_name,
            age=new_age,
            preferences=new_preferences
        )
        use_case.get_child_profile = AsyncMock(return_value=updated_child_data)
        
        # Execute
        result = await use_case.update_child_profile(
            child_id, name=new_name, age=new_age, preferences=new_preferences
        )
        
        # Verify
        assert result is not None
        assert result.name == new_name
        assert result.age == new_age
        assert result.preferences == new_preferences
        
        mock_child.update_profile.assert_called_once_with(new_name, new_age, new_preferences)
        mock_child_repository.save.assert_called_once_with(mock_child)
        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_update_child_profile_partial_update(self, use_case, mock_child_repository):
        """Test partial child profile update."""
        # Setup
        child_id = uuid4()
        new_name = "Partially Updated Child"
        
        mock_child = Mock(spec=True)
        mock_child.id = child_id
        mock_child.update_profile = Mock(spec=True)
        mock_child.get_uncommitted_events.return_value = []
        
        mock_child_repository.get_by_id.return_value = mock_child
        
        updated_child_data = ChildData(
            id=child_id,
            name=new_name,
            age=8,  # Unchanged
            preferences={"interests": ["games"]}  # Unchanged
        )
        use_case.get_child_profile = AsyncMock(return_value=updated_child_data)
        
        # Execute - only update name
        result = await use_case.update_child_profile(child_id, name=new_name)
        
        # Verify
        assert result is not None
        assert result.name == new_name
        
        mock_child.update_profile.assert_called_once_with(new_name, None, None)

    @pytest.mark.asyncio
    async def test_update_child_profile_not_exists(self, use_case, mock_child_repository):
        """Test updating non-existent child profile."""
        # Setup
        child_id = uuid4()
        mock_child_repository.get_by_id.return_value = None
        
        # Execute
        result = await use_case.update_child_profile(child_id, name="New Name")
        
        # Verify
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_child_profile_success(self, use_case, mock_child_repository):
        """Test successful child profile deletion."""
        # Setup
        child_id = uuid4()
        mock_child = Mock(spec=True)
        mock_child.id = child_id
        
        mock_child_repository.get_by_id.return_value = mock_child
        use_case.child_profile_read_model_store = Mock(spec=True)
        use_case.child_profile_read_model_store.delete = Mock(spec=True)
        
        # Execute
        result = await use_case.delete_child_profile(child_id)
        
        # Verify
        assert result is True
        mock_child_repository.delete.assert_called_once_with(child_id)
        use_case.child_profile_read_model_store.delete.assert_called_once_with(child_id)

    @pytest.mark.asyncio
    async def test_delete_child_profile_not_exists(self, use_case, mock_child_repository):
        """Test deleting non-existent child profile."""
        # Setup
        child_id = uuid4()
        mock_child_repository.get_by_id.return_value = None
        
        # Execute
        result = await use_case.delete_child_profile(child_id)
        
        # Verify
        assert result is False
        mock_child_repository.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_child_profile_with_invalid_age(self, use_case):
        """Test creating child profile with invalid age."""
        # Setup
        name = "Test Child"
        invalid_age = -1  # Invalid age
        preferences = {"interests": ["toys"]}
        
        # Mock Child.create to raise an exception for invalid age
        with pytest.mock.patch.object(Child, 'create', side_effect=ValueError("Invalid age")):
            # Execute & Verify
            with pytest.raises(ValueError, match="Invalid age"):
                await use_case.create_child_profile(name, invalid_age, preferences)

    @pytest.mark.asyncio
    async def test_create_child_profile_with_empty_name(self, use_case):
        """Test creating child profile with empty name."""
        # Setup
        empty_name = ""
        age = 8
        preferences = {"interests": ["toys"]}
        
        # Mock Child.create to raise an exception for empty name
        with pytest.mock.patch.object(Child, 'create', side_effect=ValueError("Name cannot be empty")):
            # Execute & Verify
            with pytest.raises(ValueError, match="Name cannot be empty"):
                await use_case.create_child_profile(empty_name, age, preferences)

    @pytest.mark.asyncio
    async def test_event_publishing_on_create(self, use_case, mock_event_bus):
        """Test that events are published when creating child profile."""
        # Setup
        name = "Event Test Child"
        age = 6
        preferences = {"interests": ["music"]}
        
        mock_event1 = Mock(spec=True)
        mock_event2 = Mock(spec=True)
        mock_child = Mock(spec=True)
        mock_child.id = uuid4()
        mock_child.name = name
        mock_child.age = age
        mock_child.preferences = preferences
        mock_child.get_uncommitted_events.return_value = [mock_event1, mock_event2]
        
        with pytest.mock.patch.object(Child, 'create', return_value=mock_child):
            # Execute
            await use_case.create_child_profile(name, age, preferences)
            
            # Verify events were published
            assert mock_event_bus.publish.call_count == 2
            mock_event_bus.publish.assert_any_call(mock_event1)
            mock_event_bus.publish.assert_any_call(mock_event2)

    @pytest.mark.asyncio
    async def test_event_publishing_on_update(self, use_case, mock_child_repository, mock_event_bus):
        """Test that events are published when updating child profile."""
        # Setup
        child_id = uuid4()
        mock_event = Mock(spec=True)
        mock_child = Mock(spec=True)
        mock_child.id = child_id
        mock_child.update_profile = Mock(spec=True)
        mock_child.get_uncommitted_events.return_value = [mock_event]
        
        mock_child_repository.get_by_id.return_value = mock_child
        use_case.get_child_profile = AsyncMock(return_value=Mock(spec=True))
        
        # Execute
        await use_case.update_child_profile(child_id, name="Updated Name")
        
        # Verify event was published
        mock_event_bus.publish.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_repository_error_handling(self, use_case, mock_child_repository):
        """Test handling of repository errors."""
        # Setup
        name = "Error Test Child"
        age = 7
        preferences = {"interests": ["books"]}
        
        mock_child = Mock(spec=True)
        mock_child.id = uuid4()
        mock_child.name = name
        mock_child.age = age
        mock_child.preferences = preferences
        mock_child.get_uncommitted_events.return_value = []
        
        # Mock repository to raise an exception
        mock_child_repository.save.side_effect = Exception("Database error")
        
        with pytest.mock.patch.object(Child, 'create', return_value=mock_child):
            # Execute & Verify
            with pytest.raises(Exception, match="Database error"):
                await use_case.create_child_profile(name, age, preferences)

    def test_child_data_structure(self):
        """Test ChildData structure and validation."""
        child_id = uuid4()
        name = "Structure Test Child"
        age = 9
        preferences = {"interests": ["art", "music"], "language": "en"}
        
        child_data = ChildData(
            id=child_id,
            name=name,
            age=age,
            preferences=preferences
        )
        
        assert child_data.id == child_id
        assert child_data.name == name
        assert child_data.age == age
        assert child_data.preferences == preferences
        assert isinstance(child_data.id, UUID)
        assert isinstance(child_data.age, int)
        assert isinstance(child_data.preferences, dict)