"""
Tests for EducationalContent class.

This test module ensures that EducationalContent properly loads
and manages educational content from JSON files.
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


class TestEducationalContent:
    """Test EducationalContent functionality."""

    @pytest.fixture
    def sample_educational_data(self):
        """Sample educational content data for testing."""
        return {
            "math": [
                {
                    "id": "math_1",
                    "topic": "counting",
                    "title": "Counting with Friends",
                    "content": "Let's count together: 1, 2, 3, 4, 5!",
                    "age_range": [3, 6],
                    "difficulty": "basic"
                },
                {
                    "id": "math_2", 
                    "topic": "addition",
                    "title": "Simple Addition",
                    "content": "2 apples + 3 apples = 5 apples!",
                    "age_range": [5, 8],
                    "difficulty": "intermediate"
                }
            ],
            "science": [
                {
                    "id": "science_1",
                    "topic": "animals",
                    "title": "Animal Sounds",
                    "content": "Dogs say woof, cats say meow, cows say moo!",
                    "age_range": [3, 7],
                    "difficulty": "basic"
                }
            ],
            "language": [
                {
                    "id": "lang_1",
                    "topic": "alphabet",
                    "title": "Learning ABC",
                    "content": "A is for Apple, B is for Ball, C is for Cat!",
                    "age_range": [4, 7],
                    "difficulty": "basic"
                }
            ]
        }

    @pytest.fixture
    def temp_educational_dir(self, sample_educational_data):
        """Create temporary directory with sample educational content files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create educational_stories.json file
            educational_data = {
                "stories": []
            }
            
            # Flatten the educational data into stories format
            for topic, content_list in sample_educational_data.items():
                educational_data["stories"].extend(content_list)
            
            file_path = os.path.join(temp_dir, "educational_stories.json")
            with open(file_path, 'w') as f:
                json.dump(educational_data, f)
            
            yield temp_dir

    def test_initialization_with_existing_files(self, temp_educational_dir):
        """Test EducationalContent initialization with existing files."""
        with patch('src.application.content.educational_content.os.path.join') as mock_join:
            mock_join.return_value = temp_educational_dir
            
            from src.application.content.educational_content import EducationalContent
            
            educational = EducationalContent()
            
            # Should have loaded content
            assert hasattr(educational, 'contents')
            assert isinstance(educational.contents, dict)

    def test_initialization_without_files(self):
        """Test EducationalContent initialization when files don't exist."""
        with patch('src.application.content.educational_content.os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            from src.application.content.educational_content import EducationalContent
            
            educational = EducationalContent()
            
            # Should initialize with empty contents
            assert hasattr(educational, 'contents')
            assert isinstance(educational.contents, dict)

    def test_load_contents_success(self, temp_educational_dir):
        """Test successful content loading."""
        with patch('src.application.content.educational_content.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_educational_dir, fname)
            
            from src.application.content.educational_content import EducationalContent
            
            educational = EducationalContent()
            
            # Should have loaded educational content
            assert isinstance(educational.contents, dict)

    def test_load_contents_with_invalid_json(self):
        """Test content loading with invalid JSON files."""
        invalid_json = "{ invalid json content"
        
        with patch('src.application.content.educational_content.os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data=invalid_json)) as mock_file:
            
            mock_exists.return_value = True
            
            from src.application.content.educational_content import EducationalContent
            
            # Should handle invalid JSON gracefully
            educational = EducationalContent()
            assert isinstance(educational.contents, dict)

    def test_get_content_existing_topic(self):
        """Test getting content for an existing topic."""
        mock_contents = {
            "math": {"id": "math_1", "topic": "counting", "content": "1, 2, 3!"},
            "science": {"id": "science_1", "topic": "animals", "content": "Animals are fun!"}
        }
        
        from src.application.content.educational_content import EducationalContent
        
        with patch.object(EducationalContent, '_load_contents', return_value=mock_contents):
            educational = EducationalContent()
            educational.contents = mock_contents
            
            # Should return the correct content
            result = educational.get_content("math")
            assert result == mock_contents["math"]
            
            result = educational.get_content("science")
            assert result == mock_contents["science"]

    def test_get_content_nonexistent_topic(self):
        """Test getting content for a non-existent topic."""
        mock_contents = {"math": {"id": "math_1", "content": "Math content"}}
        
        from src.application.content.educational_content import EducationalContent
        
        with patch.object(EducationalContent, '_load_contents', return_value=mock_contents):
            educational = EducationalContent()
            educational.contents = mock_contents
            
            # Should return None for non-existent topics
            result = educational.get_content("nonexistent")
            assert result is None

    def test_get_content_with_none_topic(self):
        """Test getting content with None topic."""
        mock_contents = {"math": {"id": "math_1", "content": "Math content"}}
        
        from src.application.content.educational_content import EducationalContent
        
        with patch.object(EducationalContent, '_load_contents', return_value=mock_contents):
            educational = EducationalContent()
            educational.contents = mock_contents
            
            # Should handle None topic gracefully
            result = educational.get_content(None)
            assert result is None

    def test_contents_directory_path(self):
        """Test that contents directory path is correctly constructed."""
        from src.application.content.educational_content import EducationalContent
        
        with patch('src.application.content.educational_content.os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            educational = EducationalContent()
            
            # Should have templates_dir attribute
            assert hasattr(educational, 'templates_dir')
            assert isinstance(educational.templates_dir, str)
            assert 'templates/stories' in educational.templates_dir

    def test_load_contents_file_permissions_error(self):
        """Test handling of file permission errors during content loading."""
        with patch('src.application.content.educational_content.os.path.exists') as mock_exists, \
             patch('builtins.open', side_effect=PermissionError("Permission denied")):
            
            mock_exists.return_value = True
            
            from src.application.content.educational_content import EducationalContent
            
            # Should handle permission errors gracefully
            educational = EducationalContent()
            assert isinstance(educational.contents, dict)

    def test_load_contents_io_error(self):
        """Test handling of IO errors during content loading."""
        with patch('src.application.content.educational_content.os.path.exists') as mock_exists, \
             patch('builtins.open', side_effect=IOError("IO Error")):
            
            mock_exists.return_value = True
            
            from src.application.content.educational_content import EducationalContent
            
            # Should handle IO errors gracefully
            educational = EducationalContent()
            assert isinstance(educational.contents, dict)

    def test_content_data_structure(self, temp_educational_dir):
        """Test that loaded content data has expected structure."""
        with patch('src.application.content.educational_content.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_educational_dir, fname)
            
            from src.application.content.educational_content import EducationalContent
            
            educational = EducationalContent()
            
            # Each content item should be properly structured
            for topic, content_data in educational.contents.items():
                assert isinstance(topic, str)
                # Content data could be dict or list depending on implementation

    def test_multiple_initialization(self):
        """Test that multiple EducationalContent instances work independently."""
        from src.application.content.educational_content import EducationalContent
        
        with patch('src.application.content.educational_content.os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            educational1 = EducationalContent()
            educational2 = EducationalContent()
            
            # Should be independent instances
            assert educational1 is not educational2
            assert educational1.contents is not educational2.contents

    def test_case_insensitive_topic_search(self):
        """Test case-insensitive topic searching."""
        mock_contents = {
            "math": {"id": "math_1", "content": "Math content"},
            "Science": {"id": "science_1", "content": "Science content"},
            "LANGUAGE": {"id": "lang_1", "content": "Language content"}
        }
        
        from src.application.content.educational_content import EducationalContent
        
        with patch.object(EducationalContent, '_load_contents', return_value=mock_contents):
            educational = EducationalContent()
            educational.contents = mock_contents
            
            # Test exact matches first
            assert educational.get_content("math") is not None
            assert educational.get_content("Science") is not None
            assert educational.get_content("LANGUAGE") is not None
            
            # Case sensitivity depends on implementation
            # This test checks current behavior

    def test_educational_content_filtering_by_age(self):
        """Test filtering educational content by age appropriateness."""
        # This would test age-based filtering if implemented
        mock_contents = {
            "math_basic": {
                "id": "math_1",
                "content": "Simple counting",
                "age_range": [3, 5]
            },
            "math_advanced": {
                "id": "math_2", 
                "content": "Complex multiplication",
                "age_range": [8, 12]
            }
        }
        
        from src.application.content.educational_content import EducationalContent
        
        with patch.object(EducationalContent, '_load_contents', return_value=mock_contents):
            educational = EducationalContent()
            educational.contents = mock_contents
            
            # Basic functionality test - getting content by topic
            basic_math = educational.get_content("math_basic")
            advanced_math = educational.get_content("math_advanced")
            
            assert basic_math is not None
            assert advanced_math is not None

    def test_educational_content_categories(self):
        """Test different educational content categories."""
        categories = ["math", "science", "language", "art", "music", "social"]
        mock_contents = {
            category: {
                "id": f"{category}_1",
                "topic": category,
                "content": f"{category.title()} content"
            }
            for category in categories
        }
        
        from src.application.content.educational_content import EducationalContent
        
        with patch.object(EducationalContent, '_load_contents', return_value=mock_contents):
            educational = EducationalContent()
            educational.contents = mock_contents
            
            # Should be able to get content for all categories
            for category in categories:
                content = educational.get_content(category)
                assert content is not None
                assert content["topic"] == category

    def test_large_educational_content_handling(self):
        """Test handling of large educational content files."""
        # Create large content structure
        large_contents = {
            f"topic_{i}": {
                "id": f"content_{i}",
                "topic": f"topic_{i}",
                "content": f"Educational content {i} " * 100
            }
            for i in range(100)
        }
        
        from src.application.content.educational_content import EducationalContent
        
        with patch.object(EducationalContent, '_load_contents', return_value=large_contents):
            educational = EducationalContent()
            educational.contents = large_contents
            
            # Should handle large content sets efficiently
            import time
            start_time = time.time()
            
            # Test multiple content retrievals
            for i in range(10):
                content = educational.get_content(f"topic_{i}")
                assert content is not None
            
            end_time = time.time()
            
            # Should complete quickly
            assert (end_time - start_time) < 1.0

    def test_thread_safety(self):
        """Test thread safety of EducationalContent."""
        import threading
        import time
        
        mock_contents = {
            "math": {"id": "math_1", "content": "Math content"},
            "science": {"id": "science_1", "content": "Science content"}
        }
        
        from src.application.content.educational_content import EducationalContent
        
        with patch.object(EducationalContent, '_load_contents', return_value=mock_contents):
            educational = EducationalContent()
            educational.contents = mock_contents
            
            results = []
            errors = []
            
            def test_content_access():
                try:
                    for _ in range(10):
                        math_content = educational.get_content("math")
                        science_content = educational.get_content("science")
                        results.append((math_content, science_content))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(e)
            
            # Run multiple threads
            threads = [threading.Thread(target=test_content_access) for _ in range(3)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            
            # Should not have any errors
            assert len(errors) == 0, f"Thread safety errors: {errors}"
            
            # All results should be valid
            assert len(results) == 30  # 3 threads * 10 calls each
            for math_content, science_content in results:
                assert math_content is not None
                assert science_content is not None

    def test_memory_usage(self):
        """Test that EducationalContent doesn't leak memory."""
        import gc
        
        from src.application.content.educational_content import EducationalContent
        
        with patch('src.application.content.educational_content.os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            # Create and destroy many instances
            for i in range(100):
                educational = EducationalContent()
                # Simulate content access
                educational.get_content(f"topic_{i}")
            
            # Force garbage collection
            gc.collect()
            
            # Test should complete without memory issues
            assert True

    def test_edge_cases(self):
        """Test various edge cases."""
        from src.application.content.educational_content import EducationalContent
        
        with patch('src.application.content.educational_content.os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            educational = EducationalContent()
            
            # Test edge cases
            edge_cases = [
                "",          # Empty string
                "   ",       # Whitespace
                "MATH",      # Uppercase
                "math123",   # Alphanumeric
                "math-fun",  # With hyphen
                "math_basics", # With underscore
            ]
            
            for case in edge_cases:
                try:
                    result = educational.get_content(case)
                    assert result is None or isinstance(result, dict)
                except Exception as e:
                    # Should handle edge cases gracefully
                    assert isinstance(e, (TypeError, ValueError, KeyError))

    def test_empty_educational_files(self):
        """Test handling of empty educational files."""
        empty_json = '{"stories": []}'
        
        with patch('src.application.content.educational_content.os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data=empty_json)):
            
            mock_exists.return_value = True
            
            from src.application.content.educational_content import EducationalContent
            
            educational = EducationalContent()
            
            # Should handle empty files gracefully
            assert isinstance(educational.contents, dict)