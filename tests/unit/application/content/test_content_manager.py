"""
Tests for ContentManager class.

This test module ensures that ContentManager properly integrates
story templates, educational content, age filtering, and content validation.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))


class TestContentManager:
    """Test ContentManager functionality."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for ContentManager."""
        with patch('src.application.content.content_manager.StoryTemplates') as mock_stories, \
             patch('src.application.content.content_manager.EducationalContent') as mock_educational, \
             patch('src.application.content.content_manager.AgeFilter') as mock_age_filter, \
             patch('src.application.content.content_manager.ContentValidator') as mock_validator:
            
            # Configure mocks
            mock_stories.return_value = Mock()
            mock_educational.return_value = Mock()
            mock_age_filter.return_value = Mock()
            mock_validator.return_value = Mock()
            
            yield {
                'stories': mock_stories.return_value,
                'educational': mock_educational.return_value,
                'age_filter': mock_age_filter.return_value,
                'validator': mock_validator.return_value
            }

    @pytest.fixture
    def content_manager(self, mock_dependencies):
        """Create ContentManager instance with mocked dependencies."""
        from src.application.content.content_manager import ContentManager
        return ContentManager()

    def test_initialization(self, mock_dependencies):
        """Test ContentManager initialization."""
        from src.application.content.content_manager import ContentManager
        
        manager = ContentManager()
        
        # Should have all required components
        assert hasattr(manager, 'stories')
        assert hasattr(manager, 'educational')
        assert hasattr(manager, 'age_filter')
        assert hasattr(manager, 'validator')
        
        # Components should not be None
        assert manager.stories is not None
        assert manager.educational is not None
        assert manager.age_filter is not None
        assert manager.validator is not None

    def test_get_story_success(self, content_manager, mock_dependencies):
        """Test successful story retrieval."""
        # Setup mocks
        mock_story = {"id": "story1", "title": "Test Story", "content": "Once upon a time..."}
        mock_dependencies['stories'].get_template.return_value = mock_story
        mock_dependencies['age_filter'].is_allowed.return_value = True
        mock_dependencies['validator'].is_valid.return_value = True
        
        # Test
        result = content_manager.get_story("story1", 5)
        
        # Assertions
        assert result == mock_story
        mock_dependencies['stories'].get_template.assert_called_once_with("story1")
        mock_dependencies['age_filter'].is_allowed.assert_called_once_with(mock_story, 5)
        mock_dependencies['validator'].is_valid.assert_called_once_with(mock_story)

    def test_get_story_age_filter_blocks(self, content_manager, mock_dependencies):
        """Test story retrieval blocked by age filter."""
        # Setup mocks
        mock_story = {"id": "story1", "title": "Adult Story", "content": "Complex content..."}
        mock_dependencies['stories'].get_template.return_value = mock_story
        mock_dependencies['age_filter'].is_allowed.return_value = False  # Blocked by age filter
        
        # Test
        result = content_manager.get_story("story1", 3)
        
        # Assertions
        assert result is None
        mock_dependencies['stories'].get_template.assert_called_once_with("story1")
        mock_dependencies['age_filter'].is_allowed.assert_called_once_with(mock_story, 3)
        # Validator should not be called if age filter blocks
        mock_dependencies['validator'].is_valid.assert_not_called()

    def test_get_story_validator_blocks(self, content_manager, mock_dependencies):
        """Test story retrieval blocked by content validator."""
        # Setup mocks
        mock_story = {"id": "story1", "title": "Unsafe Story", "content": "Violence and scary content..."}
        mock_dependencies['stories'].get_template.return_value = mock_story
        mock_dependencies['age_filter'].is_allowed.return_value = True
        mock_dependencies['validator'].is_valid.return_value = False  # Blocked by validator
        
        # Test
        result = content_manager.get_story("story1", 7)
        
        # Assertions
        assert result is None
        mock_dependencies['stories'].get_template.assert_called_once_with("story1")
        mock_dependencies['age_filter'].is_allowed.assert_called_once_with(mock_story, 7)
        mock_dependencies['validator'].is_valid.assert_called_once_with(mock_story)

    def test_get_story_with_preferences(self, content_manager, mock_dependencies):
        """Test story retrieval with preferences parameter."""
        # Setup mocks
        mock_story = {"id": "story1", "title": "Preferred Story", "content": "Animal adventure..."}
        mock_dependencies['stories'].get_template.return_value = mock_story
        mock_dependencies['age_filter'].is_allowed.return_value = True
        mock_dependencies['validator'].is_valid.return_value = True
        
        preferences = {"theme": "animals", "length": "short"}
        
        # Test
        result = content_manager.get_story("story1", 6, preferences)
        
        # Assertions
        assert result == mock_story
        mock_dependencies['stories'].get_template.assert_called_once_with("story1")

    def test_get_educational_content_success(self, content_manager, mock_dependencies):
        """Test successful educational content retrieval."""
        # Setup mocks
        mock_content = {"topic": "math", "content": "2 + 2 = 4", "difficulty": "basic"}
        mock_dependencies['educational'].get_content.return_value = mock_content
        mock_dependencies['age_filter'].is_allowed.return_value = True
        mock_dependencies['validator'].is_valid.return_value = True
        
        # Test
        result = content_manager.get_educational_content("math", 6)
        
        # Assertions
        assert result == mock_content
        mock_dependencies['educational'].get_content.assert_called_once_with("math")
        mock_dependencies['age_filter'].is_allowed.assert_called_once_with(mock_content, 6)
        mock_dependencies['validator'].is_valid.assert_called_once_with(mock_content)

    def test_get_educational_content_age_blocked(self, content_manager, mock_dependencies):
        """Test educational content blocked by age filter."""
        # Setup mocks
        mock_content = {"topic": "advanced_math", "content": "Calculus basics", "difficulty": "advanced"}
        mock_dependencies['educational'].get_content.return_value = mock_content
        mock_dependencies['age_filter'].is_allowed.return_value = False
        
        # Test
        result = content_manager.get_educational_content("advanced_math", 4)
        
        # Assertions
        assert result is None
        mock_dependencies['educational'].get_content.assert_called_once_with("advanced_math")
        mock_dependencies['age_filter'].is_allowed.assert_called_once_with(mock_content, 4)
        mock_dependencies['validator'].is_valid.assert_not_called()

    def test_get_educational_content_validation_blocked(self, content_manager, mock_dependencies):
        """Test educational content blocked by validator."""
        # Setup mocks
        mock_content = {"topic": "unsafe_topic", "content": "Inappropriate educational content", "difficulty": "basic"}
        mock_dependencies['educational'].get_content.return_value = mock_content
        mock_dependencies['age_filter'].is_allowed.return_value = True
        mock_dependencies['validator'].is_valid.return_value = False
        
        # Test
        result = content_manager.get_educational_content("unsafe_topic", 8)
        
        # Assertions
        assert result is None
        mock_dependencies['educational'].get_content.assert_called_once_with("unsafe_topic")
        mock_dependencies['age_filter'].is_allowed.assert_called_once_with(mock_content, 8)
        mock_dependencies['validator'].is_valid.assert_called_once_with(mock_content)

    def test_error_handling_story_retrieval(self, content_manager, mock_dependencies):
        """Test error handling in story retrieval."""
        # Setup mocks to raise exceptions
        mock_dependencies['stories'].get_template.side_effect = Exception("Template not found")
        
        # Test should handle exception gracefully
        with pytest.raises(Exception):
            content_manager.get_story("nonexistent", 5)

    def test_error_handling_educational_content(self, content_manager, mock_dependencies):
        """Test error handling in educational content retrieval."""
        # Setup mocks to raise exceptions
        mock_dependencies['educational'].get_content.side_effect = Exception("Content not found")
        
        # Test should handle exception gracefully
        with pytest.raises(Exception):
            content_manager.get_educational_content("nonexistent", 5)

    def test_integration_all_components(self, content_manager, mock_dependencies):
        """Test that all components work together properly."""
        # Setup complex scenario
        mock_story = {"id": "complex_story", "title": "Adventure", "content": "A great adventure..."}
        mock_dependencies['stories'].get_template.return_value = mock_story
        mock_dependencies['age_filter'].is_allowed.return_value = True
        mock_dependencies['validator'].is_valid.return_value = True
        
        # Test story
        story_result = content_manager.get_story("complex_story", 8, {"theme": "adventure"})
        
        # Setup educational content
        mock_edu_content = {"topic": "science", "content": "The water cycle...", "difficulty": "intermediate"}
        mock_dependencies['educational'].get_content.return_value = mock_edu_content
        
        # Test educational content  
        edu_result = content_manager.get_educational_content("science", 8)
        
        # Verify both work correctly
        assert story_result == mock_story
        assert edu_result == mock_edu_content
        
        # Verify all components were called
        assert mock_dependencies['stories'].get_template.called
        assert mock_dependencies['educational'].get_content.called
        assert mock_dependencies['age_filter'].is_allowed.call_count == 2
        assert mock_dependencies['validator'].is_valid.call_count == 2

    def test_content_manager_type_safety(self, content_manager):
        """Test that ContentManager methods handle type safety."""
        # Test with invalid parameters
        with pytest.raises((TypeError, AttributeError)):
            content_manager.get_story(None, 5)
        
        with pytest.raises((TypeError, ValueError)):
            content_manager.get_story("story1", "invalid_age")
        
        with pytest.raises((TypeError, AttributeError)):
            content_manager.get_educational_content(None, 5)
        
        with pytest.raises((TypeError, ValueError)):
            content_manager.get_educational_content("math", "invalid_age")

    def test_content_manager_edge_cases(self, content_manager, mock_dependencies):
        """Test ContentManager with edge cases."""
        # Test with empty story
        mock_dependencies['stories'].get_template.return_value = {}
        mock_dependencies['age_filter'].is_allowed.return_value = True
        mock_dependencies['validator'].is_valid.return_value = True
        
        result = content_manager.get_story("empty_story", 5)
        assert result == {}
        
        # Test with None returned from template
        mock_dependencies['stories'].get_template.return_value = None
        mock_dependencies['age_filter'].is_allowed.return_value = True
        mock_dependencies['validator'].is_valid.return_value = True
        
        result = content_manager.get_story("none_story", 5)
        # Should handle None gracefully
        assert result is None or result == None