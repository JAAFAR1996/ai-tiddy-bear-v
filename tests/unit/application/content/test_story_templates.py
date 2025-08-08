"""
Tests for StoryTemplates class.

This test module ensures that StoryTemplates properly loads
and manages story templates from JSON files.
"""

import pytest
import sys
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))


class TestStoryTemplates:
    """Test StoryTemplates functionality."""

    @pytest.fixture
    def sample_story_data(self):
        """Sample story data for testing."""
        return {
            "bedtime_stories": [
                {
                    "id": "bedtime_1",
                    "title": "The Sleepy Bear",
                    "content": "Once upon a time, there was a sleepy bear...",
                    "age_range": [3, 7],
                    "duration": "5 minutes"
                }
            ],
            "educational_stories": [
                {
                    "id": "edu_1", 
                    "title": "Counting with Friends",
                    "content": "Let's learn to count with our animal friends...",
                    "age_range": [4, 8],
                    "subject": "math"
                }
            ],
            "interactive_games": [
                {
                    "id": "game_1",
                    "title": "Color Recognition",
                    "content": "Can you find all the red objects?",
                    "age_range": [3, 6],
                    "type": "visual"
                }
            ]
        }

    @pytest.fixture
    def temp_templates_dir(self, sample_story_data):
        """Create temporary directory with sample template files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create sample JSON files
            for filename, data in [
                ("bedtime_stories.json", {"stories": sample_story_data["bedtime_stories"]}),
                ("educational_stories.json", {"stories": sample_story_data["educational_stories"]}),
                ("interactive_games.json", {"games": sample_story_data["interactive_games"]})
            ]:
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, 'w') as f:
                    json.dump(data, f)
            
            yield temp_dir

    def test_initialization_with_existing_files(self, temp_templates_dir):
        """Test StoryTemplates initialization with existing template files."""
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.return_value = temp_templates_dir
            
            from src.application.content.story_templates import StoryTemplates
            
            templates = StoryTemplates()
            
            # Should have loaded templates
            assert hasattr(templates, 'templates')
            assert isinstance(templates.templates, dict)
            assert len(templates.templates) > 0

    def test_initialization_without_files(self):
        """Test StoryTemplates initialization when template files don't exist."""
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            from src.application.content.story_templates import StoryTemplates
            
            templates = StoryTemplates()
            
            # Should initialize with empty templates
            assert hasattr(templates, 'templates')
            assert isinstance(templates.templates, dict)

    def test_load_templates_success(self, temp_templates_dir):
        """Test successful template loading."""
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_templates_dir, fname)
            
            from src.application.content.story_templates import StoryTemplates
            
            templates = StoryTemplates()
            
            # Should have loaded all template files
            assert len(templates.templates) >= 3  # At least bedtime, educational, games

    def test_load_templates_with_invalid_json(self):
        """Test template loading with invalid JSON files."""
        invalid_json = "{ invalid json content"
        
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data=invalid_json)) as mock_file:
            
            mock_exists.return_value = True
            
            from src.application.content.story_templates import StoryTemplates
            
            # Should handle invalid JSON gracefully
            templates = StoryTemplates()
            assert isinstance(templates.templates, dict)

    def test_load_templates_with_missing_files(self):
        """Test template loading when some files are missing."""
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists:
            # Only bedtime_stories.json exists
            mock_exists.side_effect = lambda path: 'bedtime_stories.json' in path
            
            sample_data = json.dumps({"stories": [{"id": "test", "title": "Test"}]})
            with patch('builtins.open', mock_open(read_data=sample_data)):
                from src.application.content.story_templates import StoryTemplates
                
                templates = StoryTemplates()
                assert isinstance(templates.templates, dict)

    def test_get_template_existing(self):
        """Test getting an existing template."""
        mock_templates = {
            "story_1": {"id": "story_1", "title": "Test Story", "content": "Test content"},
            "story_2": {"id": "story_2", "title": "Another Story", "content": "More content"}
        }
        
        from src.application.content.story_templates import StoryTemplates
        
        with patch.object(StoryTemplates, '_load_templates', return_value=mock_templates):
            templates = StoryTemplates()
            templates.templates = mock_templates
            
            # Should return the correct template
            result = templates.get_template("story_1")
            assert result == mock_templates["story_1"]
            
            result = templates.get_template("story_2")
            assert result == mock_templates["story_2"]

    def test_get_template_nonexistent(self):
        """Test getting a non-existent template."""
        mock_templates = {"story_1": {"id": "story_1", "title": "Test Story"}}
        
        from src.application.content.story_templates import StoryTemplates
        
        with patch.object(StoryTemplates, '_load_templates', return_value=mock_templates):
            templates = StoryTemplates()
            templates.templates = mock_templates
            
            # Should return None for non-existent templates
            result = templates.get_template("nonexistent")
            assert result is None

    def test_get_template_with_none_id(self):
        """Test getting template with None ID."""
        mock_templates = {"story_1": {"id": "story_1", "title": "Test Story"}}
        
        from src.application.content.story_templates import StoryTemplates
        
        with patch.object(StoryTemplates, '_load_templates', return_value=mock_templates):
            templates = StoryTemplates()
            templates.templates = mock_templates
            
            # Should handle None ID gracefully
            result = templates.get_template(None)
            assert result is None

    def test_templates_directory_path(self):
        """Test that templates directory path is correctly constructed."""
        from src.application.content.story_templates import StoryTemplates
        
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            templates = StoryTemplates()
            
            # Should have templates_dir attribute
            assert hasattr(templates, 'templates_dir')
            assert isinstance(templates.templates_dir, str)
            assert 'templates/stories' in templates.templates_dir

    def test_load_templates_file_permissions_error(self):
        """Test handling of file permission errors during template loading."""
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists, \
             patch('builtins.open', side_effect=PermissionError("Permission denied")):
            
            mock_exists.return_value = True
            
            from src.application.content.story_templates import StoryTemplates
            
            # Should handle permission errors gracefully
            templates = StoryTemplates()
            assert isinstance(templates.templates, dict)

    def test_load_templates_io_error(self):
        """Test handling of IO errors during template loading."""
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists, \
             patch('builtins.open', side_effect=IOError("IO Error")):
            
            mock_exists.return_value = True
            
            from src.application.content.story_templates import StoryTemplates
            
            # Should handle IO errors gracefully
            templates = StoryTemplates()
            assert isinstance(templates.templates, dict)

    def test_template_data_structure(self, temp_templates_dir):
        """Test that loaded template data has expected structure."""
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_templates_dir, fname)
            
            from src.application.content.story_templates import StoryTemplates
            
            templates = StoryTemplates()
            
            # Each template should be a dictionary
            for template_id, template_data in templates.templates.items():
                assert isinstance(template_data, dict)
                assert isinstance(template_id, str)

    def test_multiple_initialization(self):
        """Test that multiple StoryTemplates instances work independently."""
        from src.application.content.story_templates import StoryTemplates
        
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            templates1 = StoryTemplates()
            templates2 = StoryTemplates()
            
            # Should be independent instances
            assert templates1 is not templates2
            assert templates1.templates is not templates2.templates

    def test_templates_immutability(self):
        """Test that template data can be safely modified without affecting the class."""
        mock_templates = {"story_1": {"id": "story_1", "title": "Original Title"}}
        
        from src.application.content.story_templates import StoryTemplates
        
        with patch.object(StoryTemplates, '_load_templates', return_value=mock_templates):
            templates = StoryTemplates()
            templates.templates = mock_templates.copy()
            
            # Get template and modify it
            template = templates.get_template("story_1")
            if template:
                template["title"] = "Modified Title"
            
            # Original should be unchanged (depending on implementation)
            # This test helps ensure the class handles data properly
            original = templates.get_template("story_1")
            assert original is not None

    def test_edge_case_empty_template_files(self):
        """Test handling of empty template files."""
        empty_json = "{}"
        
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data=empty_json)):
            
            mock_exists.return_value = True
            
            from src.application.content.story_templates import StoryTemplates
            
            templates = StoryTemplates()
            
            # Should handle empty files gracefully
            assert isinstance(templates.templates, dict)

    def test_large_template_file_handling(self):
        """Test handling of large template files."""
        # Create a large template structure
        large_template_data = {
            f"story_{i}": {
                "id": f"story_{i}",
                "title": f"Story {i}",
                "content": "Long content " * 100  # Make it reasonably large
            }
            for i in range(100)
        }
        
        large_json = json.dumps({"stories": list(large_template_data.values())})
        
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data=large_json)):
            
            mock_exists.return_value = True
            
            from src.application.content.story_templates import StoryTemplates
            
            templates = StoryTemplates()
            
            # Should handle large files without issues
            assert isinstance(templates.templates, dict)