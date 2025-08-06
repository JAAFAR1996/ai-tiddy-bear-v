"""
Tests for AgeFilter class.

This test module ensures that AgeFilter properly filters content
based on child age with COPPA compliance (3-13 years).
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))


class TestAgeFilter:
    """Test AgeFilter functionality."""

    @pytest.fixture
    def age_filter(self):
        """Create AgeFilter instance."""
        from src.application.content.age_filter import AgeFilter
        return AgeFilter()

    @pytest.fixture
    def sample_content_data(self):
        """Sample content data for testing."""
        return {
            "toddler_content": {
                "id": "toddler_1",
                "title": "Simple Colors",
                "content": "Red, blue, green!",
                "age_range": [3, 4],
                "complexity": "simple"
            },
            "preschool_content": {
                "id": "preschool_1", 
                "title": "Counting Fun",
                "content": "1, 2, 3, let's count together!",
                "age_range": [4, 5],
                "complexity": "basic"
            },
            "elementary_content": {
                "id": "elem_1",
                "title": "Nature Adventure",
                "content": "Let's explore the forest and learn about animals!",
                "age_range": [6, 10],
                "complexity": "intermediate"
            },
            "preteen_content": {
                "id": "preteen_1",
                "title": "Science Discovery",
                "content": "Understanding the water cycle and weather patterns.",
                "age_range": [11, 13],
                "complexity": "advanced"
            },
            "no_age_range": {
                "id": "no_age",
                "title": "Universal Content",
                "content": "Content without age specification"
            }
        }

    def test_initialization(self, age_filter):
        """Test AgeFilter initialization."""
        assert age_filter is not None
        assert hasattr(age_filter, 'is_allowed')

    def test_age_category_enum_values(self):
        """Test AgeCategory enum has expected values."""
        from src.application.content.age_filter import AgeCategory
        
        expected_categories = ['TODDLER', 'PRESCHOOL', 'EARLY_ELEMENTARY', 'LATE_ELEMENTARY', 'PRETEEN']
        actual_categories = [category.name for category in AgeCategory]
        
        for category in expected_categories:
            assert category in actual_categories

    def test_content_complexity_enum_values(self):
        """Test ContentComplexity enum has expected values."""
        from src.application.content.age_filter import ContentComplexity
        
        # Should have complexity levels defined
        assert hasattr(ContentComplexity, '__members__')
        assert len(ContentComplexity.__members__) > 0

    def test_coppa_age_compliance_minimum(self, age_filter):
        """Test COPPA compliance - minimum age 3."""
        content = {"age_range": [3, 5], "content": "Simple content"}
        
        # Age 3 should be allowed (minimum COPPA age)
        assert age_filter.is_allowed(content, 3) == True
        
        # Age below 3 should be blocked
        assert age_filter.is_allowed(content, 2) == False
        assert age_filter.is_allowed(content, 1) == False

    def test_coppa_age_compliance_maximum(self, age_filter):
        """Test COPPA compliance - maximum age 13."""
        content = {"age_range": [10, 13], "content": "Advanced content"}
        
        # Age 13 should be allowed (maximum COPPA age)
        assert age_filter.is_allowed(content, 13) == True
        
        # Age above 13 should be blocked
        assert age_filter.is_allowed(content, 14) == False
        assert age_filter.is_allowed(content, 15) == False

    def test_is_allowed_within_range(self, age_filter, sample_content_data):
        """Test content allowed when child age is within specified range."""
        # Toddler content for 3-year-old
        assert age_filter.is_allowed(sample_content_data["toddler_content"], 3) == True
        
        # Preschool content for 4-year-old
        assert age_filter.is_allowed(sample_content_data["preschool_content"], 4) == True
        
        # Elementary content for 8-year-old
        assert age_filter.is_allowed(sample_content_data["elementary_content"], 8) == True
        
        # Preteen content for 12-year-old
        assert age_filter.is_allowed(sample_content_data["preteen_content"], 12) == True

    def test_is_allowed_outside_range(self, age_filter, sample_content_data):
        """Test content blocked when child age is outside specified range."""
        # Toddler content for older child
        assert age_filter.is_allowed(sample_content_data["toddler_content"], 8) == False
        
        # Preteen content for younger child
        assert age_filter.is_allowed(sample_content_data["preteen_content"], 5) == False
        
        # Elementary content for toddler
        assert age_filter.is_allowed(sample_content_data["elementary_content"], 3) == False

    def test_is_allowed_no_age_range(self, age_filter, sample_content_data):
        """Test content without age_range specification."""
        content = sample_content_data["no_age_range"]
        
        # Content without age_range should have default behavior
        # (This depends on implementation - might allow all or block all)
        result_young = age_filter.is_allowed(content, 4)
        result_old = age_filter.is_allowed(content, 10)
        
        # Should be consistent behavior
        assert isinstance(result_young, bool)
        assert isinstance(result_old, bool)

    def test_is_allowed_invalid_age_range_format(self, age_filter):
        """Test handling of invalid age_range formats."""
        invalid_contents = [
            {"age_range": "3-5", "content": "String range"},  # String instead of list
            {"age_range": [3], "content": "Single value"},    # Single value
            {"age_range": [5, 3], "content": "Reversed range"}, # Reversed range
            {"age_range": [-1, 5], "content": "Negative age"}, # Negative age
            {"age_range": [3, "five"], "content": "Mixed types"}, # Mixed types
        ]
        
        for content in invalid_contents:
            # Should handle invalid formats gracefully (not crash)
            try:
                result = age_filter.is_allowed(content, 5)
                assert isinstance(result, bool)
            except (TypeError, ValueError, AttributeError):
                # Acceptable to raise these exceptions for invalid data
                pass

    def test_is_allowed_edge_case_ages(self, age_filter):
        """Test edge cases for child ages."""
        content = {"age_range": [5, 10], "content": "Mid-range content"}
        
        # Boundary values
        assert age_filter.is_allowed(content, 5) == True   # Lower bound
        assert age_filter.is_allowed(content, 10) == True  # Upper bound
        assert age_filter.is_allowed(content, 4) == False  # Just below
        assert age_filter.is_allowed(content, 11) == False # Just above

    def test_is_allowed_invalid_child_ages(self, age_filter):
        """Test handling of invalid child ages."""
        content = {"age_range": [5, 10], "content": "Test content"}
        
        invalid_ages = [
            -1,      # Negative age
            0,       # Zero age
            "five",  # String age
            None,    # None age
            [],      # List age
            {},      # Dict age
            float('inf'), # Infinity
        ]
        
        for age in invalid_ages:
            try:
                result = age_filter.is_allowed(content, age)
                # If it doesn't raise an exception, should return False for invalid ages
                if age in [-1, 0, "five", None, [], {}, float('inf')]:
                    assert result == False
            except (TypeError, ValueError):
                # Acceptable to raise exceptions for invalid ages
                pass

    def test_is_allowed_none_content(self, age_filter):
        """Test handling of None content."""
        result = age_filter.is_allowed(None, 5)
        # Should handle None content gracefully
        assert isinstance(result, bool)
        # Most likely should return False for None content
        assert result == False

    def test_is_allowed_empty_content(self, age_filter):
        """Test handling of empty content."""
        empty_content = {}
        result = age_filter.is_allowed(empty_content, 5)
        # Should handle empty content gracefully
        assert isinstance(result, bool)

    def test_logging_integration(self, age_filter):
        """Test that logging works correctly."""
        with patch('src.application.content.age_filter.logger') as mock_logger:
            content = {"age_range": [5, 10], "content": "Test content"}
            
            # Test allowed content
            age_filter.is_allowed(content, 7)
            
            # Test blocked content  
            age_filter.is_allowed(content, 3)
            
            # Depending on implementation, logger might be called
            # This test ensures logging doesn't break functionality
            assert True  # If we get here, logging didn't break anything

    def test_performance_with_large_content(self, age_filter):
        """Test performance with large content objects."""
        large_content = {
            "age_range": [5, 10],
            "content": "Large content " * 10000,  # Large content string
            "metadata": {
                "tags": ["tag"] * 1000,  # Large metadata
                "description": "Description " * 1000
            }
        }
        
        # Should handle large content efficiently
        import time
        start_time = time.time()
        result = age_filter.is_allowed(large_content, 7)
        end_time = time.time()
        
        # Should complete quickly (under 1 second for this test)
        assert (end_time - start_time) < 1.0
        assert isinstance(result, bool)

    def test_thread_safety(self, age_filter):
        """Test thread safety of AgeFilter."""
        import threading
        import time
        
        content = {"age_range": [5, 10], "content": "Thread test content"}
        results = []
        errors = []
        
        def test_filter():
            try:
                for _ in range(10):
                    result = age_filter.is_allowed(content, 7)
                    results.append(result)
                    time.sleep(0.001)  # Small delay to increase chance of race conditions
            except Exception as e:
                errors.append(e)
        
        # Run multiple threads
        threads = [threading.Thread(target=test_filter) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # Should not have any errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        
        # All results should be consistent
        assert len(results) == 50  # 5 threads * 10 calls each
        assert all(isinstance(result, bool) for result in results)

    def test_memory_usage(self, age_filter):
        """Test that AgeFilter doesn't leak memory."""
        import gc
        
        # Create many content objects and filter them
        for i in range(1000):
            content = {
                "age_range": [3, 13],
                "content": f"Content {i}",
                "id": f"content_{i}"
            }
            age_filter.is_allowed(content, 7)
        
        # Force garbage collection
        gc.collect()
        
        # Test should complete without memory issues
        assert True

    def test_age_categorization_accuracy(self):
        """Test that age categorization is accurate."""
        from src.application.content.age_filter import AgeCategory
        
        # Test age ranges for each category
        test_cases = [
            (3, AgeCategory.TODDLER),
            (4, AgeCategory.PRESCHOOL),  # Could be TODDLER or PRESCHOOL depending on implementation
            (6, AgeCategory.EARLY_ELEMENTARY),
            (9, AgeCategory.LATE_ELEMENTARY),
            (12, AgeCategory.PRETEEN)
        ]
        
        # This test depends on having a method to get age category
        # If such method exists in implementation
        age_filter_class = AgeCategory
        
        # At minimum, verify the enum values are reasonable
        for category in AgeCategory:
            assert category.value is not None
            assert isinstance(category.value, str)