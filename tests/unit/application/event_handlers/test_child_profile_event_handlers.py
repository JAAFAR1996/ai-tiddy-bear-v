"""
Tests for Child Profile Event Handlers
======================================

Tests for child profile event handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock
import asyncio

from src.application.event_handlers.child_profile_event_handlers import (
    ChildProfileEventHandlers,
    create_child_profile_read_model
)
from src.core.events import ChildRegistered, ChildProfileUpdated


class TestChildProfileEventHandlers:
    """Test child profile event handlers."""

    @pytest.fixture
    def mock_read_model_store(self):
        """Create mock read model store."""
        store = Mock()
        store.async_save = AsyncMock()
        store.async_get_by_id = AsyncMock()
        return store

    @pytest.fixture
    def event_handlers(self, mock_read_model_store):
        """Create event handlers instance."""
        return ChildProfileEventHandlers(mock_read_model_store)

    def test_create_child_profile_read_model_valid(self):
        """Test creating valid child profile read model."""
        model = create_child_profile_read_model("child123", "Test Child", 8)
        
        assert model.child_id == "child123"
        assert model.name == "Test Child"
        assert model.age == 8
        assert model.preferences == {}

    def test_create_child_profile_read_model_with_preferences(self):
        """Test creating child profile with preferences."""
        preferences = {"interests": ["stories", "games"]}
        model = create_child_profile_read_model("child123", "Test Child", 8, preferences)
        
        assert model.preferences == preferences

    def test_create_child_profile_read_model_invalid_age(self):
        """Test creating child profile with invalid age."""
        with pytest.raises(ValueError, match="violates COPPA compliance"):
            create_child_profile_read_model("child123", "Test Child", 15)

    @pytest.mark.asyncio
    async def test_handle_child_registered_success(self, event_handlers, mock_read_model_store):
        """Test successful child registration handling."""
        event = ChildRegistered(
            child_id="child123",
            name="Test Child",
            age=8,
            preferences={"interests": ["stories"]}
        )
        
        await event_handlers.handle_child_registered(event)
        
        mock_read_model_store.async_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_child_registered_invalid_age(self, event_handlers):
        """Test child registration with invalid age."""
        event = ChildRegistered(
            child_id="child123",
            name="Test Child",
            age=15,  # Invalid age
            preferences={}
        )
        
        with pytest.raises(ValueError, match="violates COPPA compliance"):
            await event_handlers.handle_child_registered(event)

    @pytest.mark.asyncio
    async def test_handle_child_profile_updated_success(self, event_handlers, mock_read_model_store):
        """Test successful child profile update handling."""
        # Mock existing model
        existing_model = Mock()
        existing_model.age = 8
        existing_model.name = "Old Name"
        existing_model.preferences = {}
        mock_read_model_store.async_get_by_id.return_value = existing_model
        
        event = ChildProfileUpdated(
            child_id="child123",
            name="New Name",
            age=9,
            preferences={"interests": ["music"]}
        )
        
        await event_handlers.handle_child_profile_updated(event)
        
        assert existing_model.name == "New Name"
        assert existing_model.age == 9
        mock_read_model_store.async_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_child_profile_updated_not_found(self, event_handlers, mock_read_model_store):
        """Test child profile update when profile not found."""
        mock_read_model_store.async_get_by_id.return_value = None
        
        event = ChildProfileUpdated(
            child_id="nonexistent",
            name="New Name"
        )
        
        await event_handlers.handle_child_profile_updated(event)
        
        mock_read_model_store.async_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_child_profile_updated_invalid_age(self, event_handlers, mock_read_model_store):
        """Test child profile update with invalid age."""
        existing_model = Mock()
        existing_model.age = 8
        mock_read_model_store.async_get_by_id.return_value = existing_model
        
        event = ChildProfileUpdated(
            child_id="child123",
            age=15  # Invalid age
        )
        
        with pytest.raises(ValueError, match="violates COPPA compliance"):
            await event_handlers.handle_child_profile_updated(event)

    @pytest.mark.asyncio
    async def test_retry_operation_success(self, event_handlers):
        """Test retry operation success."""
        mock_operation = AsyncMock(return_value="success")
        
        result = await event_handlers._retry_operation(mock_operation, "arg1", key="value")
        
        assert result == "success"
        mock_operation.assert_called_once_with("arg1", key="value")

    @pytest.mark.asyncio
    async def test_retry_operation_with_retries(self, event_handlers):
        """Test retry operation with failures then success."""
        mock_operation = AsyncMock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        
        result = await event_handlers._retry_operation(mock_operation)
        
        assert result == "success"
        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_operation_max_retries_exceeded(self, event_handlers):
        """Test retry operation when max retries exceeded."""
        mock_operation = AsyncMock(side_effect=Exception("persistent failure"))
        
        with pytest.raises(Exception, match="persistent failure"):
            await event_handlers._retry_operation(mock_operation)
        
        assert mock_operation.call_count == 3  # max_retry_attempts