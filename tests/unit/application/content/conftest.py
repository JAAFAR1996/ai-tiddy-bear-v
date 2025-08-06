"""
Shared test fixtures and configuration for content module tests.

This module provides common fixtures and utilities used across
all content management system tests.
"""

import pytest
import sys
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))


@pytest.fixture(scope="session")
def sample_story_data():
    """Sample story data used across multiple tests."""
    return {
        "bedtime_stories": [
            {
                "id": "bedtime_1",
                "title": "The Sleepy Bear",
                "text": "Once upon a time, there was a sleepy bear who lived in a cozy cave.",
                "age_range": [3, 7],
                "duration": "5 minutes",
                "type": "bedtime"
            },
            {
                "id": "bedtime_2",
                "title": "Moonlight Adventure",
                "text": "Under the bright moonlight, little rabbit went on a magical journey.",
                "age_range": [4, 8],
                "duration": "7 minutes",
                "type": "bedtime"
            }
        ],
        "educational_stories": [
            {
                "id": "edu_1",
                "title": "Counting with Friends",
                "text": "Let's count together with our animal friends: 1 elephant, 2 lions, 3 zebras!",
                "age_range": [4, 8],
                "subject": "math",
                "difficulty": "basic"
            },
            {
                "id": "edu_2",
                "title": "Colors of Nature",
                "text": "Nature has many beautiful colors: green leaves, blue sky, red flowers!",
                "age_range": [3, 6],
                "subject": "science",
                "difficulty": "basic"
            }
        ],
        "interactive_games": [
            {
                "id": "game_1",
                "title": "Find the Shapes",
                "text": "Can you find all the circles in this picture?",
                "age_range": [3, 6],
                "type": "visual",
                "interaction": "search"
            }
        ]
    }


@pytest.fixture(scope="session")
def unsafe_content_data():
    """Unsafe content data for testing content validation."""
    return {
        "unsafe_stories": [
            {
                "id": "unsafe_1",
                "title": "Dangerous Story",
                "text": "This story contains violence and scary monsters that hurt people.",
                "age_range": [5, 10],
                "type": "story"
            },
            {
                "id": "unsafe_2",
                "title": "Frightening Tale",
                "text": "The scary creature made everyone afraid with unsafe behavior.",
                "age_range": [6, 12],
                "type": "story"
            }
        ]
    }


@pytest.fixture
def temp_story_files(sample_story_data):
    """Create temporary story template files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create story template files
        for category, stories in sample_story_data.items():
            if category == "bedtime_stories":
                filename = "bedtime_stories.json"
                data = {"stories": stories}
            elif category == "educational_stories":
                filename = "educational_stories.json"
                data = {"stories": stories}
            elif category == "interactive_games":
                filename = "interactive_games.json"
                data = {"games": stories}
            else:
                continue
            
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
        
        yield temp_dir


@pytest.fixture
def mock_content_dependencies():
    """Mock dependencies for content components."""
    with patch('src.application.content.content_manager.StoryTemplates') as mock_stories, \
         patch('src.application.content.content_manager.EducationalContent') as mock_educational, \
         patch('src.application.content.content_manager.AgeFilter') as mock_age_filter, \
         patch('src.application.content.content_manager.ContentValidator') as mock_validator:
        
        # Configure mocks with reasonable defaults
        mock_stories_instance = Mock()
        mock_educational_instance = Mock()
        mock_age_filter_instance = Mock()
        mock_validator_instance = Mock()
        
        mock_stories.return_value = mock_stories_instance
        mock_educational.return_value = mock_educational_instance
        mock_age_filter.return_value = mock_age_filter_instance
        mock_validator.return_value = mock_validator_instance
        
        # Set default return values
        mock_stories_instance.get_template.return_value = None
        mock_educational_instance.get_content.return_value = None
        mock_age_filter_instance.is_allowed.return_value = True
        mock_validator_instance.is_valid.return_value = True
        
        yield {
            'stories': mock_stories_instance,
            'educational': mock_educational_instance,
            'age_filter': mock_age_filter_instance,
            'validator': mock_validator_instance
        }


@pytest.fixture
def sample_valid_content():
    """Sample valid content for testing."""
    return {
        "id": "test_content_1",
        "title": "Safe Test Content",
        "text": "This is perfectly safe content for children with happy animals playing.",
        "age_range": [4, 8],
        "type": "story"
    }


@pytest.fixture
def sample_unsafe_content():
    """Sample unsafe content for testing."""
    return {
        "id": "test_unsafe_1",
        "title": "Unsafe Test Content",
        "text": "This content contains violence and scary elements that are unsafe.",
        "age_range": [5, 10],
        "type": "story"
    }


@pytest.fixture
def content_test_ages():
    """Standard test ages for COPPA compliance testing."""
    return {
        "too_young": 2,        # Below COPPA minimum
        "minimum": 3,          # COPPA minimum
        "typical_young": 5,    # Typical young child
        "typical_older": 9,    # Typical older child  
        "maximum": 13,         # COPPA maximum
        "too_old": 14         # Above COPPA maximum
    }


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration for each test."""
    import logging
    
    # Store original level
    original_level = logging.getLogger().level
    
    yield
    
    # Restore original level
    logging.getLogger().setLevel(original_level)


@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
        
        def assert_under(self, max_seconds):
            assert self.elapsed is not None, "Timer not properly used"
            assert self.elapsed < max_seconds, f"Operation took {self.elapsed:.3f}s, expected under {max_seconds}s"
    
    return Timer()


@pytest.fixture
def memory_monitor():
    """Memory monitoring fixture for memory leak testing."""
    import gc
    import sys
    
    class MemoryMonitor:
        def __init__(self):
            self.initial_objects = None
        
        def start(self):
            gc.collect()  # Clean up before measuring
            self.initial_objects = len(gc.get_objects())
        
        def check_no_major_leaks(self, tolerance=100):
            """Check that object count hasn't increased significantly."""
            gc.collect()
            current_objects = len(gc.get_objects())
            increase = current_objects - self.initial_objects
            
            assert increase < tolerance, f"Potential memory leak: {increase} new objects created"
    
    return MemoryMonitor()


# Pytest markers for test categorization
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "memory: marks tests as memory usage tests"
    )
    config.addinivalue_line(
        "markers", "thread_safety: marks tests as thread safety tests"
    )
    config.addinivalue_line(
        "markers", "coppa: marks tests as COPPA compliance tests"
    )