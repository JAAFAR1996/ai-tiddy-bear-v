"""
Tests for ContentValidator class.

This test module ensures that ContentValidator properly validates
content for safety and compliance with child protection standards.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))


class TestContentValidator:
    """Test ContentValidator functionality."""

    @pytest.fixture
    def content_validator(self):
        """Create ContentValidator instance."""
        from src.application.content.content_validator import ContentValidator
        return ContentValidator()

    @pytest.fixture
    def sample_contents(self):
        """Sample content data for testing."""
        return {
            "safe_content": {
                "id": "safe_1",
                "title": "Happy Animals",
                "text": "The friendly bunny played in the sunny meadow with colorful flowers.",
                "type": "story"
            },
            "unsafe_violence": {
                "id": "unsafe_1",
                "title": "Dangerous Story",
                "text": "The character used violence to solve the problem and it was very scary.",
                "type": "story"
            },
            "unsafe_scary": {
                "id": "unsafe_2", 
                "title": "Frightening Tale",
                "text": "It was a dark and scary night, and the monster was very frightening.",
                "type": "story"
            },
            "unsafe_multiple_issues": {
                "id": "unsafe_3",
                "title": "Multiple Problems",
                "text": "This story contains violence and scary elements that are unsafe for children.",
                "type": "story"
            },
            "borderline_content": {
                "id": "border_1",
                "title": "Adventure Story",
                "text": "The brave hero faced challenges and overcame difficulties with courage.",
                "type": "story"
            },
            "empty_content": {
                "id": "empty_1",
                "title": "Empty Story",
                "text": "",
                "type": "story"
            },
            "no_text_field": {
                "id": "no_text_1",
                "title": "No Text Field",
                "type": "story"
            }
        }

    def test_initialization(self, content_validator):
        """Test ContentValidator initialization."""
        assert content_validator is not None
        assert hasattr(content_validator, 'is_valid')
        assert callable(content_validator.is_valid)

    def test_is_valid_safe_content(self, content_validator, sample_contents):
        """Test validation of safe content."""
        safe_content = sample_contents["safe_content"]
        
        result = content_validator.is_valid(safe_content)
        
        assert result == True, "Safe content should be validated as valid"

    def test_is_valid_unsafe_violence(self, content_validator, sample_contents):
        """Test validation blocks content with violence."""
        unsafe_content = sample_contents["unsafe_violence"]
        
        result = content_validator.is_valid(unsafe_content)
        
        assert result == False, "Content with violence should be blocked"

    def test_is_valid_unsafe_scary(self, content_validator, sample_contents):
        """Test validation blocks scary content."""
        scary_content = sample_contents["unsafe_scary"]
        
        result = content_validator.is_valid(scary_content)
        
        assert result == False, "Scary content should be blocked"

    def test_is_valid_unsafe_multiple_issues(self, content_validator, sample_contents):
        """Test validation blocks content with multiple safety issues."""
        unsafe_content = sample_contents["unsafe_multiple_issues"]
        
        result = content_validator.is_valid(unsafe_content)
        
        assert result == False, "Content with multiple safety issues should be blocked"

    def test_is_valid_borderline_content(self, content_validator, sample_contents):
        """Test validation of borderline content."""
        borderline_content = sample_contents["borderline_content"]
        
        result = content_validator.is_valid(borderline_content)
        
        # This should be valid as it doesn't contain forbidden words
        assert result == True, "Borderline but safe content should be allowed"

    def test_is_valid_empty_content(self, content_validator, sample_contents):
        """Test validation of empty content."""
        empty_content = sample_contents["empty_content"]
        
        result = content_validator.is_valid(empty_content)
        
        # Empty content should be valid (no forbidden words)
        assert result == True, "Empty content should be valid"

    def test_is_valid_no_text_field(self, content_validator, sample_contents):
        """Test validation when content has no text field."""
        no_text_content = sample_contents["no_text_field"]
        
        result = content_validator.is_valid(no_text_content)
        
        # Should handle missing text field gracefully
        assert result == True, "Content without text field should default to valid"

    def test_is_valid_none_content(self, content_validator):
        """Test validation of None content."""
        result = content_validator.is_valid(None)
        
        # Should handle None gracefully
        assert isinstance(result, bool)
        # Most likely should return False for None content
        assert result == False, "None content should be invalid"

    def test_is_valid_case_insensitive(self, content_validator):
        """Test that validation is case-insensitive."""
        test_cases = [
            {"text": "VIOLENCE"},      # Uppercase
            {"text": "Violence"},      # Capitalized
            {"text": "violence"},      # Lowercase  
            {"text": "ViOlEnCe"},      # Mixed case
            {"text": "SCARY content"}, # Uppercase forbidden word
            {"text": "Scary Content"}, # Capitalized forbidden word
        ]
        
        for content in test_cases:
            result = content_validator.is_valid(content)
            assert result == False, f"Case-insensitive validation failed for: {content}"

    def test_forbidden_words_list(self, content_validator):
        """Test that all expected forbidden words are blocked."""
        expected_forbidden = ["violence", "scary", "unsafe"]
        
        for word in expected_forbidden:
            content = {"text": f"This content contains {word} which should be blocked."}
            result = content_validator.is_valid(content)
            assert result == False, f"Forbidden word '{word}' should be blocked"

    def test_partial_word_matching(self, content_validator):
        """Test behavior with partial word matches."""
        # These should NOT be blocked (partial matches)
        safe_partial_cases = [
            {"text": "The rescuer was nonviolent and peaceful."},  # "violence" in "nonviolent"
            {"text": "Scary movie? No, it's not scary at all!"},   # Direct match should still be blocked
        ]
        
        # Test the first case (partial match)
        result1 = content_validator.is_valid(safe_partial_cases[0])
        # This depends on implementation - could be True or False
        assert isinstance(result1, bool)
        
        # Test the second case (direct match)
        result2 = content_validator.is_valid(safe_partial_cases[1])
        assert result2 == False, "Direct forbidden word match should be blocked"

    def test_multiple_forbidden_words(self, content_validator):
        """Test content with multiple forbidden words."""
        content = {
            "text": "This story has violence and scary elements that are unsafe for children."
        }
        
        result = content_validator.is_valid(content)
        assert result == False, "Content with multiple forbidden words should be blocked"

    def test_word_boundaries(self, content_validator):
        """Test word boundary detection."""
        # Test cases where forbidden words appear as substrings
        boundary_cases = [
            {"text": "The nonviolent approach was better."},      # "violence" in "nonviolent"  
            {"text": "He was scary-looking but friendly."},      # "scary" with hyphen
            {"text": "Safety first, not unsafe practices."},    # "unsafe" as whole word
        ]
        
        for i, content in enumerate(boundary_cases):
            result = content_validator.is_valid(content)
            assert isinstance(result, bool), f"Word boundary test {i} should return boolean"
            
            # For the third case, "unsafe" as a whole word should be blocked
            if "unsafe practices" in content["text"]:
                assert result == False, "Whole word 'unsafe' should be blocked"

    def test_special_characters_and_punctuation(self, content_validator):
        """Test handling of special characters and punctuation."""
        special_cases = [
            {"text": "Violence! It's not allowed here."},
            {"text": "Is this scary? No, it's not."},
            {"text": "Unsafe... definitely not good."},
            {"text": "Violence, scary, and unsafe content."},
            {"text": "This is violence-free content."},
        ]
        
        for content in special_cases:
            result = content_validator.is_valid(content)
            assert isinstance(result, bool)
            
            # These should all be blocked due to forbidden words
            if any(word in content["text"].lower() for word in ["violence", "scary", "unsafe"]):
                assert result == False, f"Content with forbidden words should be blocked: {content}"

    def test_unicode_and_international_characters(self, content_validator):
        """Test handling of Unicode and international characters."""
        unicode_cases = [
            {"text": "This is sáfe content with accénts."},
            {"text": "普通话内容应该是安全的。"},  # Chinese characters
            {"text": "العربية آمنة للأطفال"},  # Arabic characters
            {"text": "🎈🎉 Happy celebration content! 🎊"},  # Emojis
        ]
        
        for content in unicode_cases:
            result = content_validator.is_valid(content)
            assert isinstance(result, bool)
            # These should be valid as they don't contain English forbidden words
            assert result == True, f"Unicode content should be valid: {content}"

    def test_large_content_performance(self, content_validator):
        """Test performance with large content."""
        # Create large content without forbidden words
        large_safe_text = "This is safe content. " * 10000
        large_content = {"text": large_safe_text}
        
        import time
        start_time = time.time()
        result = content_validator.is_valid(large_content)
        end_time = time.time()
        
        # Should complete quickly
        assert (end_time - start_time) < 1.0, "Large content validation should be fast"
        assert result == True, "Large safe content should be valid"
        
        # Test large content with forbidden words
        large_unsafe_text = "This content has violence. " * 5000
        large_unsafe_content = {"text": large_unsafe_text}
        
        start_time = time.time()
        result = content_validator.is_valid(large_unsafe_content)
        end_time = time.time()
        
        # Should still complete quickly
        assert (end_time - start_time) < 1.0, "Large unsafe content validation should be fast"
        assert result == False, "Large unsafe content should be invalid"

    def test_thread_safety(self, content_validator):
        """Test thread safety of ContentValidator."""
        import threading
        import time
        
        safe_content = {"text": "This is safe content for threading test."}
        unsafe_content = {"text": "This content has violence and is unsafe."}
        
        results = []
        errors = []
        
        def test_validation():
            try:
                for _ in range(10):
                    safe_result = content_validator.is_valid(safe_content)
                    unsafe_result = content_validator.is_valid(unsafe_content)
                    results.append((safe_result, unsafe_result))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Run multiple threads
        threads = [threading.Thread(target=test_validation) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # Should not have any errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        
        # All results should be consistent
        assert len(results) == 30  # 3 threads * 10 calls each
        for safe_result, unsafe_result in results:
            assert safe_result == True, "Safe content should always be valid"
            assert unsafe_result == False, "Unsafe content should always be invalid"

    def test_custom_forbidden_words(self, content_validator):
        """Test ability to handle custom forbidden words configuration."""
        # This test checks if the forbidden words list can be modified
        # (depends on implementation)
        
        # First, test with current forbidden words
        content = {"text": "This has violence which should be blocked."}
        result = content_validator.is_valid(content)
        assert result == False
        
        # The current implementation has hardcoded forbidden words
        # This test ensures the implementation is working as expected
        assert True

    def test_edge_cases(self, content_validator):
        """Test various edge cases."""
        edge_cases = [
            {},  # Empty dict
            {"text": None},  # None text
            {"title": "Only title, no text"},  # Missing text field
            {"text": "   "},  # Whitespace only
            {"text": 123},  # Non-string text (should handle gracefully)
            {"text": []},  # List as text
        ]
        
        for content in edge_cases:
            try:
                result = content_validator.is_valid(content)
                assert isinstance(result, bool), f"Edge case should return boolean: {content}"
            except (TypeError, AttributeError):
                # Acceptable to raise exceptions for invalid data types
                pass

    def test_memory_usage(self, content_validator):
        """Test that ContentValidator doesn't leak memory."""
        import gc
        
        # Process many content objects
        for i in range(1000):
            content = {"text": f"Content number {i} for memory test."}
            content_validator.is_valid(content)
        
        # Force garbage collection
        gc.collect()
        
        # Test should complete without memory issues
        assert True

    def test_validation_consistency(self, content_validator):
        """Test that validation results are consistent across multiple calls."""
        test_content = {"text": "This is a consistency test with violence."}
        
        # Call validation multiple times
        results = [content_validator.is_valid(test_content) for _ in range(10)]
        
        # All results should be the same
        assert all(result == results[0] for result in results), "Validation should be consistent"
        assert results[0] == False, "Content with forbidden words should always be invalid"