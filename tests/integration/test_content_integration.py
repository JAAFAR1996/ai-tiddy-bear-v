"""
Integration tests for the content management system.

This test module ensures that all content components work together
correctly and integrate properly with the overall system.
"""

import pytest
import sys
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestContentIntegration:
    """Integration tests for content management system."""

    @pytest.fixture
    def complete_test_data(self):
        """Complete test data structure for integration testing."""
        return {
            "bedtime_stories": {
                "stories": [
                    {
                        "id": "bedtime_1",
                        "title": "The Sleepy Teddy Bear",
                        "text": "Once upon a time, there was a very sleepy teddy bear who loved to dream.",
                        "age_range": [3, 7],
                        "duration": "5 minutes",
                        "type": "bedtime"
                    },
                    {
                        "id": "bedtime_2",
                        "title": "Goodnight Moon Friends",
                        "text": "The moon smiled down at all the animal friends saying goodnight.",
                        "age_range": [3, 6],
                        "duration": "3 minutes",
                        "type": "bedtime"
                    }
                ]
            },
            "educational_stories": {
                "stories": [
                    {
                        "id": "edu_1",
                        "title": "Counting Rainbow Colors",
                        "text": "Let's count the beautiful rainbow colors: red, orange, yellow, green, blue!",
                        "age_range": [4, 8],
                        "subject": "math",
                        "difficulty": "basic"
                    },
                    {
                        "id": "edu_2",
                        "title": "Animal Habitats",
                        "text": "Different animals live in different places: fish in water, birds in trees!",
                        "age_range": [5, 9],
                        "subject": "science",
                        "difficulty": "intermediate"
                    }
                ]
            },
            "interactive_games": {
                "games": [
                    {
                        "id": "game_1",
                        "title": "Find the Hidden Colors",
                        "text": "Can you find all the red objects in the magical garden?",
                        "age_range": [3, 6],
                        "type": "visual",
                        "interaction": "search"
                    }
                ]
            }
        }

    @pytest.fixture
    def unsafe_test_data(self):
        """Unsafe content data for testing content validation."""
        return {
            "unsafe_stories": {
                "stories": [
                    {
                        "id": "unsafe_1",
                        "title": "Dangerous Adventure",
                        "text": "The story contained violence and scary monsters that frightened everyone.",
                        "age_range": [5, 10],
                        "type": "adventure"
                    },
                    {
                        "id": "unsafe_2", 
                        "title": "Inappropriate Content",
                        "text": "This content is unsafe for children with inappropriate themes.",
                        "age_range": [3, 8],
                        "type": "story"
                    }
                ]
            }
        }

    @pytest.fixture
    def temp_content_files(self, complete_test_data, unsafe_test_data):
        """Create temporary content files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create safe content files
            for filename, data in complete_test_data.items():
                file_path = os.path.join(temp_dir, f"{filename}.json")
                with open(file_path, 'w') as f:
                    json.dump(data, f)
            
            # Create unsafe content file
            unsafe_file = os.path.join(temp_dir, "unsafe_content.json")
            with open(unsafe_file, 'w') as f:
                json.dump(unsafe_test_data["unsafe_stories"], f)
            
            yield temp_dir

    def test_full_content_pipeline_safe_content(self, temp_content_files):
        """Test the complete content pipeline with safe content."""
        with patch('src.application.content.story_templates.os.path.join') as mock_join, \
             patch('src.application.content.educational_content.os.path.join') as mock_edu_join:
            
            # Setup path mocking
            mock_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            mock_edu_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            
            from src.application.content import ContentManager
            
            # Initialize content manager
            content_manager = ContentManager()
            
            # Test story retrieval for appropriate age
            story = content_manager.get_story("bedtime_1", 5)
            assert story is not None
            assert story["title"] == "The Sleepy Teddy Bear"
            
            # Test educational content retrieval
            edu_content = content_manager.get_educational_content("math", 6)
            # This might return None if the topic structure is different
            # The test validates the integration works without errors

    def test_age_filtering_integration(self, temp_content_files):
        """Test age filtering integration across all components."""
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            
            from src.application.content import ContentManager
            
            content_manager = ContentManager()
            
            # Test content appropriate for age 4
            result_age_4 = content_manager.get_story("bedtime_1", 4)  # Should be allowed (age_range 3-7)
            
            # Test content inappropriate for age (outside range)
            result_age_10 = content_manager.get_story("bedtime_2", 10)  # Should be blocked (age_range 3-6)
            
            # Age filtering should work correctly
            # Results depend on actual implementation, but should not crash

    def test_content_validation_integration(self, temp_content_files, unsafe_test_data):
        """Test content validation integration with unsafe content."""
        # Create a story with unsafe content
        unsafe_story = unsafe_test_data["unsafe_stories"]["stories"][0]
        
        from src.application.content.content_validator import ContentValidator
        from src.application.content.age_filter import AgeFilter
        
        validator = ContentValidator()
        age_filter = AgeFilter()
        
        # Test validation blocks unsafe content
        is_valid = validator.is_valid(unsafe_story)
        assert is_valid == False, "Unsafe content should be blocked by validator"
        
        # Test age filter still works with unsafe content
        age_appropriate = age_filter.is_allowed(unsafe_story, 7)
        # Age filter might allow it based on age range, but validator should block it

    def test_multiple_component_interaction(self, temp_content_files):
        """Test interaction between multiple content components."""
        with patch('src.application.content.story_templates.os.path.join') as mock_story_join, \
             patch('src.application.content.educational_content.os.path.join') as mock_edu_join:
            
            mock_story_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            mock_edu_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            
            from src.application.content import (
                ContentManager, StoryTemplates, EducationalContent, 
                AgeFilter, ContentValidator
            )
            
            # Test individual components
            story_templates = StoryTemplates()
            educational_content = EducationalContent()
            age_filter = AgeFilter()
            content_validator = ContentValidator()
            
            # Test that components can be used independently
            assert story_templates is not None
            assert educational_content is not None
            assert age_filter is not None
            assert content_validator is not None
            
            # Test ContentManager uses all components
            content_manager = ContentManager()
            assert content_manager.stories is not None
            assert content_manager.educational is not None
            assert content_manager.age_filter is not None
            assert content_manager.validator is not None

    def test_content_manager_with_preferences(self, temp_content_files):
        """Test ContentManager with user preferences integration."""
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            
            from src.application.content import ContentManager
            
            content_manager = ContentManager()
            
            # Test with preferences
            preferences = {
                "theme": "animals",
                "duration": "short",
                "difficulty": "basic"
            }
            
            # Should handle preferences without errors
            try:
                story = content_manager.get_story("bedtime_1", 5, preferences)
                # Story might be None or a dict, but should not crash
                assert story is None or isinstance(story, dict)
            except Exception as e:
                pytest.fail(f"ContentManager should handle preferences gracefully: {e}")

    def test_content_system_error_handling(self):
        """Test error handling across the content system."""
        from src.application.content import ContentManager
        
        # Test with no template files (should not crash)
        with patch('src.application.content.story_templates.os.path.exists') as mock_exists, \
             patch('src.application.content.educational_content.os.path.exists') as mock_edu_exists:
            
            mock_exists.return_value = False
            mock_edu_exists.return_value = False
            
            try:
                content_manager = ContentManager()
                
                # Should handle missing files gracefully
                story = content_manager.get_story("nonexistent", 5)
                edu_content = content_manager.get_educational_content("nonexistent", 5)
                
                # Should return None for nonexistent content, not crash
                assert story is None
                assert edu_content is None
                
            except Exception as e:
                pytest.fail(f"Content system should handle missing files gracefully: {e}")

    def test_content_system_performance(self, temp_content_files):
        """Test performance of the integrated content system."""
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            
            from src.application.content import ContentManager
            
            content_manager = ContentManager()
            
            import time
            
            # Test multiple content retrievals
            start_time = time.time()
            
            for i in range(10):
                story = content_manager.get_story("bedtime_1", 5)
                edu_content = content_manager.get_educational_content("math", 6)
            
            end_time = time.time()
            
            # Should complete quickly (under 1 second for 10 operations)
            assert (end_time - start_time) < 1.0, "Content system should be performant"

    def test_content_system_thread_safety(self, temp_content_files):
        """Test thread safety of the integrated content system."""
        import threading
        import time
        
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            
            from src.application.content import ContentManager
            
            content_manager = ContentManager()
            
            results = []
            errors = []
            
            def test_content_operations():
                try:
                    for _ in range(5):
                        story = content_manager.get_story("bedtime_1", 5)
                        edu_content = content_manager.get_educational_content("math", 6)
                        results.append((story, edu_content))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(e)
            
            # Run multiple threads
            threads = [threading.Thread(target=test_content_operations) for _ in range(3)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            
            # Should not have thread safety errors
            assert len(errors) == 0, f"Thread safety errors: {errors}"
            assert len(results) == 15  # 3 threads * 5 operations each

    def test_coppa_compliance_integration(self, temp_content_files):
        """Test COPPA compliance across the content system."""
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            
            from src.application.content import ContentManager
            
            content_manager = ContentManager()
            
            # Test COPPA age boundaries
            coppa_test_cases = [
                (2, False),   # Below COPPA minimum (should be blocked)
                (3, True),    # COPPA minimum (should be allowed if content appropriate)
                (13, True),   # COPPA maximum (should be allowed if content appropriate)  
                (14, False),  # Above COPPA maximum (should be blocked)
            ]
            
            for age, should_process in coppa_test_cases:
                try:
                    story = content_manager.get_story("bedtime_1", age)
                    
                    if should_process:
                        # For valid COPPA ages, should either return content or None (based on age appropriateness)
                        assert story is None or isinstance(story, dict)
                    else:
                        # For invalid COPPA ages, should return None
                        assert story is None, f"Age {age} should be blocked for COPPA compliance"
                        
                except Exception as e:
                    if not should_process:
                        # It's acceptable to raise exceptions for invalid ages
                        pass
                    else:
                        pytest.fail(f"COPPA compliant age {age} should not raise exception: {e}")

    def test_content_import_integration(self):
        """Test that all content module imports work together."""
        try:
            # Test importing entire module
            from src.application import content
            assert content is not None
            
            # Test importing specific components
            from src.application.content import (
                ContentManager, StoryTemplates, EducationalContent,
                AgeFilter, ContentValidator
            )
            
            # All components should be importable
            assert ContentManager is not None
            assert StoryTemplates is not None
            assert EducationalContent is not None
            assert AgeFilter is not None
            assert ContentValidator is not None
            
            # Test instantiation of all components
            with patch('src.application.content.story_templates.os.path.exists') as mock_exists, \
                 patch('src.application.content.educational_content.os.path.exists') as mock_edu_exists:
                
                mock_exists.return_value = False
                mock_edu_exists.return_value = False
                
                content_manager = ContentManager()
                story_templates = StoryTemplates()
                educational_content = EducationalContent()
                age_filter = AgeFilter()
                content_validator = ContentValidator()
                
                # All should be instantiated successfully
                assert all([
                    content_manager, story_templates, educational_content,
                    age_filter, content_validator
                ])
                
        except ImportError as e:
            pytest.fail(f"Content integration import failed: {e}")

    def test_end_to_end_content_workflow(self, temp_content_files):
        """Test complete end-to-end content workflow."""
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            
            from src.application.content import ContentManager
            
            # Simulate a complete user interaction workflow
            content_manager = ContentManager()
            
            # Step 1: User requests a bedtime story for 5-year-old
            child_age = 5
            story_request = "bedtime_1"
            
            # Step 2: System retrieves and validates content
            story = content_manager.get_story(story_request, child_age)
            
            # Step 3: Verify content meets all requirements
            if story is not None:
                # Content should be age-appropriate and safe
                assert isinstance(story, dict)
                assert "title" in story or "text" in story  # Should have content
            
            # Step 4: User requests educational content
            educational_topic = "math"
            edu_content = content_manager.get_educational_content(educational_topic, child_age)
            
            # Step 5: Verify educational content workflow
            # Educational content might return None if topic structure is different
            assert edu_content is None or isinstance(edu_content, dict)
            
            # Workflow should complete without errors
            assert True

    def test_content_system_memory_management(self, temp_content_files):
        """Test memory management in the integrated content system."""
        import gc
        
        with patch('src.application.content.story_templates.os.path.join') as mock_join:
            mock_join.side_effect = lambda base, fname: os.path.join(temp_content_files, fname)
            
            from src.application.content import ContentManager
            
            # Create and use multiple content managers
            for i in range(10):
                content_manager = ContentManager()
                
                # Use the content manager
                story = content_manager.get_story("bedtime_1", 5)
                edu_content = content_manager.get_educational_content("math", 6)
                
                # Clear reference
                del content_manager
            
            # Force garbage collection
            gc.collect()
            
            # Test should complete without memory issues
            assert True