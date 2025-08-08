"""
Tests for Generate Dynamic Story Use Case
========================================

Critical tests for dynamic story generation functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID, uuid4

from src.application.use_cases.generate_dynamic_story import GenerateDynamicStoryUseCase


class TestGenerateDynamicStoryUseCase:
    """Test dynamic story generation use case."""

    @pytest.fixture
    def mock_ai_service(self):
        """Create mock AI service."""
        service = Mock()
        service.generate_story = AsyncMock()
        return service

    @pytest.fixture
    def mock_profile_service(self):
        """Create mock profile service."""
        service = Mock()
        service.get_child_profile = AsyncMock()
        return service

    @pytest.fixture
    def mock_content_manager(self):
        """Create mock content manager."""
        manager = Mock()
        manager.stories = Mock()
        manager.stories.templates = {}
        manager.age_filter = Mock()
        manager.age_filter.is_allowed = Mock(return_value=True)
        manager.get_story = Mock()
        return manager

    @pytest.fixture
    def use_case(self, mock_ai_service, mock_profile_service, mock_content_manager):
        """Create use case instance."""
        with patch('src.application.use_cases.generate_dynamic_story.get_logger'):
            return GenerateDynamicStoryUseCase(
                ai_service=mock_ai_service,
                profile_service=mock_profile_service,
                content_manager=mock_content_manager
            )

    @pytest.mark.asyncio
    async def test_execute_with_valid_child_profile(self, use_case, mock_ai_service, mock_profile_service):
        """Test story generation with valid child profile."""
        # Setup
        child_id = uuid4()
        child_profile = Mock()
        child_profile.age = 8
        child_profile.name = "Test Child"
        child_profile.preferences = {"interests": ["animals", "adventures"]}
        
        mock_profile_service.get_child_profile.return_value = child_profile
        mock_ai_service.generate_story.return_value = {
            "title": "The Adventure of Brave Bear",
            "content": "Once upon a time...",
            "educational_elements": ["friendship", "courage"]
        }
        
        # Execute
        result = await use_case.execute(
            child_id=child_id,
            story_theme="animals",
            story_length="medium"
        )
        
        # Verify
        assert result["success"] is True
        assert "story" in result
        assert result["metadata"]["theme"] == "animals"
        assert result["metadata"]["length"] == "medium"
        assert result["metadata"]["child_id"] == child_id
        
        mock_profile_service.get_child_profile.assert_called_once_with(child_id)
        mock_ai_service.generate_story.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_no_profile_uses_defaults(self, use_case, mock_ai_service, mock_profile_service):
        """Test story generation when no child profile exists."""
        # Setup
        child_id = uuid4()
        mock_profile_service.get_child_profile.return_value = None
        mock_ai_service.generate_story.return_value = {
            "title": "Default Story",
            "content": "A simple story...",
            "educational_elements": ["friendship"]
        }
        
        # Execute
        result = await use_case.execute(child_id=child_id)
        
        # Verify
        assert result["success"] is True
        assert "story" in result
        mock_ai_service.generate_story.assert_called_once()
        
        # Check that default preferences were used
        call_args = mock_ai_service.generate_story.call_args
        child_preferences = call_args.kwargs["child_preferences"]
        assert child_preferences["age"] == 5
        assert "animals" in child_preferences["interests"]

    @pytest.mark.asyncio
    async def test_execute_handles_ai_service_error(self, use_case, mock_ai_service, mock_profile_service):
        """Test error handling when AI service fails."""
        # Setup
        child_id = uuid4()
        mock_profile_service.get_child_profile.return_value = None
        mock_ai_service.generate_story.side_effect = Exception("AI service error")
        
        # Execute
        result = await use_case.execute(child_id=child_id)
        
        # Verify
        assert result["success"] is False
        assert "error" in result
        assert result["story"] is None
        assert "AI service error" in result["error"]

    def test_create_story_prompt_with_theme(self, use_case):
        """Test story prompt creation with theme."""
        preferences = {"age": 7, "interests": ["space", "robots"]}
        
        prompt = use_case._create_story_prompt(
            theme="space adventure",
            preferences=preferences,
            length="long"
        )
        
        assert "long story" in prompt
        assert "7-year-old" in prompt
        assert "space adventure" in prompt
        assert "educational" in prompt

    def test_create_story_prompt_with_interests(self, use_case):
        """Test story prompt creation using interests."""
        preferences = {"age": 6, "interests": ["animals", "friendship"]}
        
        prompt = use_case._create_story_prompt(
            theme=None,
            preferences=preferences,
            length="short"
        )
        
        assert "short story" in prompt
        assert "6-year-old" in prompt
        assert "animals, friendship" in prompt
        assert "educational" in prompt

    def test_get_default_preferences(self, use_case):
        """Test default preferences generation."""
        defaults = use_case._get_default_preferences()
        
        assert defaults["age"] == 5
        assert "animals" in defaults["interests"]
        assert defaults["language"] == "en"
        assert defaults["name"] == "Friend"

    def test_get_age_appropriate_interests(self, use_case):
        """Test age-appropriate interests selection."""
        # Test toddler interests (age 3)
        interests_3 = use_case._get_age_appropriate_interests(3)
        assert "animals" in interests_3
        assert "colors" in interests_3
        assert "family" in interests_3
        
        # Test preschool interests (age 5)
        interests_5 = use_case._get_age_appropriate_interests(5)
        assert "animals" in interests_5
        assert "adventures" in interests_5
        assert "toys" in interests_5
        
        # Test school age interests (age 8)
        interests_8 = use_case._get_age_appropriate_interests(8)
        assert "adventures" in interests_8
        assert "school" in interests_8
        assert "nature" in interests_8
        
        # Test pre-teen interests (age 12)
        interests_12 = use_case._get_age_appropriate_interests(12)
        assert "science" in interests_12
        assert "art" in interests_12

    @pytest.mark.asyncio
    async def test_get_child_preferences_success(self, use_case, mock_profile_service):
        """Test successful child preferences retrieval."""
        # Setup
        child_id = uuid4()
        child_profile = Mock()
        child_profile.age = 7
        child_profile.name = "Test Child"
        child_profile.preferences = {
            "interests": ["dinosaurs", "science"],
            "language": "en"
        }
        mock_profile_service.get_child_profile.return_value = child_profile
        
        # Execute
        preferences = await use_case._get_child_preferences(child_id)
        
        # Verify
        assert preferences is not None
        assert preferences["age"] == 7
        assert preferences["name"] == "Test Child"
        assert "dinosaurs" in preferences["interests"]
        assert preferences["language"] == "en"

    @pytest.mark.asyncio
    async def test_get_child_preferences_adds_missing_fields(self, use_case, mock_profile_service):
        """Test that missing preference fields are added."""
        # Setup
        child_id = uuid4()
        child_profile = Mock()
        child_profile.age = 6
        child_profile.name = "Test Child"
        child_profile.preferences = {}  # Empty preferences
        mock_profile_service.get_child_profile.return_value = child_profile
        
        # Execute
        preferences = await use_case._get_child_preferences(child_id)
        
        # Verify
        assert preferences is not None
        assert "interests" in preferences
        assert "language" in preferences
        assert preferences["language"] == "en"
        assert len(preferences["interests"]) > 0

    @pytest.mark.asyncio
    async def test_get_child_preferences_handles_service_error(self, use_case, mock_profile_service):
        """Test error handling in preferences retrieval."""
        # Setup
        child_id = uuid4()
        mock_profile_service.get_child_profile.side_effect = Exception("Service error")
        
        # Execute
        preferences = await use_case._get_child_preferences(child_id)
        
        # Verify
        assert preferences is None

    @pytest.mark.asyncio
    async def test_execute_with_story_template(self, use_case, mock_ai_service, mock_profile_service, mock_content_manager):
        """Test story generation using content template."""
        # Setup
        child_id = uuid4()
        child_profile = Mock()
        child_profile.age = 6
        child_profile.name = "Test Child"
        child_profile.preferences = {"interests": ["animals"]}
        
        # Setup template
        template = {
            "id": "template123",
            "title": "Animal Adventure",
            "text": "A story about friendly animals..."
        }
        mock_content_manager.stories.templates = {"animals": [template]}
        mock_content_manager.get_story.return_value = template
        
        mock_profile_service.get_child_profile.return_value = child_profile
        mock_ai_service.generate_story.return_value = {
            "title": "Enhanced Animal Adventure",
            "content": "An expanded story...",
            "educational_elements": ["friendship", "nature"]
        }
        
        # Execute
        result = await use_case.execute(
            child_id=child_id,
            story_theme="animals"
        )
        
        # Verify
        assert result["success"] is True
        assert result["metadata"]["template_id"] == "template123"
        mock_content_manager.get_story.assert_called_once_with("template123", 6)

    @pytest.mark.asyncio
    async def test_execute_different_story_lengths(self, use_case, mock_ai_service, mock_profile_service):
        """Test story generation with different lengths."""
        child_id = uuid4()
        mock_profile_service.get_child_profile.return_value = None
        mock_ai_service.generate_story.return_value = {"title": "Test", "content": "Test story"}
        
        # Test short story
        result_short = await use_case.execute(child_id=child_id, story_length="short")
        assert result_short["metadata"]["length"] == "short"
        
        # Test long story
        result_long = await use_case.execute(child_id=child_id, story_length="long")
        assert result_long["metadata"]["length"] == "long"