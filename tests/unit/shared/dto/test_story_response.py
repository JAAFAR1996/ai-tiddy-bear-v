"""
Unit tests for StoryResponse DTO.
Tests story response data structure and validation.
"""

import pytest
from pydantic import ValidationError

from src.shared.dto.story_response import StoryResponse


class TestStoryResponseCreation:
    """Test StoryResponse creation and basic functionality."""

    def test_create_story_response_text_only(self):
        """Test creating story response with text only."""
        story = StoryResponse(story_text="Once upon a time...")
        
        assert story.story_text == "Once upon a time..."
        assert story.audio_url is None

    def test_create_story_response_with_audio(self):
        """Test creating story response with audio URL."""
        story = StoryResponse(
            story_text="A magical adventure awaits!",
            audio_url="https://example.com/story.mp3"
        )
        
        assert story.story_text == "A magical adventure awaits!"
        assert story.audio_url == "https://example.com/story.mp3"

    def test_create_story_response_empty_audio_url(self):
        """Test creating story response with empty audio URL."""
        story = StoryResponse(
            story_text="Test story",
            audio_url=""
        )
        
        assert story.story_text == "Test story"
        assert story.audio_url == ""


class TestStoryResponseValidation:
    """Test StoryResponse field validation."""

    def test_story_text_required(self):
        """Test that story_text is required."""
        with pytest.raises(ValidationError):
            StoryResponse()  # Missing required story_text

    def test_story_text_cannot_be_none(self):
        """Test that story_text cannot be None."""
        with pytest.raises(ValidationError):
            StoryResponse(story_text=None)

    def test_valid_story_text_formats(self):
        """Test various valid story text formats."""
        valid_texts = [
            "Simple story",
            "Story with numbers 123 and symbols !@#",
            "Multi-line story\nwith line breaks\nand more content",
            "Unicode story with émojis 🌟 and accénts",
            "Very long story " + "word " * 1000,
            "Single character story: A",
            "Story with\ttabs and\rcarriage returns"
        ]
        
        for text in valid_texts:
            story = StoryResponse(story_text=text)
            assert story.story_text == text

    def test_empty_story_text_allowed(self):
        """Test that empty string is allowed for story_text (edge case)."""
        story = StoryResponse(story_text="")
        assert story.story_text == ""

    def test_whitespace_only_story_text(self):
        """Test story text with only whitespace."""
        whitespace_text = "   \n\t  \r\n  "
        story = StoryResponse(story_text=whitespace_text)
        assert story.story_text == whitespace_text


class TestAudioUrlValidation:
    """Test audio URL field validation."""

    def test_audio_url_optional(self):
        """Test that audio_url is optional."""
        story = StoryResponse(story_text="Test")
        assert story.audio_url is None

    def test_valid_audio_urls(self):
        """Test various valid audio URL formats."""
        valid_urls = [
            "https://example.com/story.mp3",
            "http://cdn.example.com/audio/story123.wav",
            "https://s3.amazonaws.com/bucket/story.m4a",
            "file:///local/path/story.mp3",
            "ftp://server.com/audio.mp3",
            "https://example.com/story.mp3?version=1&format=mp3",
            "https://example.com/very/long/path/to/audio/file/story.mp3"
        ]
        
        for url in valid_urls:
            story = StoryResponse(
                story_text="Test story",
                audio_url=url
            )
            assert story.audio_url == url

    def test_audio_url_can_be_empty_string(self):
        """Test that audio_url can be empty string."""
        story = StoryResponse(
            story_text="Test story",
            audio_url=""
        )
        assert story.audio_url == ""

    def test_audio_url_unusual_formats(self):
        """Test unusual but potentially valid URL formats."""
        unusual_urls = [
            "data:audio/mpeg;base64,SGVsbG8gV29ybGQ=",
            "blob:https://example.com/12345-67890",
            "custom-protocol://audio/story.mp3",
            "//cdn.example.com/story.mp3",  # Protocol-relative URL
            "audio.mp3",  # Relative URL
            "/absolute/path/audio.mp3"  # Absolute path
        ]
        
        for url in unusual_urls:
            story = StoryResponse(
                story_text="Test story",
                audio_url=url
            )
            assert story.audio_url == url


class TestStoryResponseSerialization:
    """Test JSON serialization and Pydantic features."""

    def test_json_serialization_text_only(self):
        """Test JSON serialization with text only."""
        story = StoryResponse(story_text="A wonderful story")
        json_data = story.model_dump_json()
        
        assert isinstance(json_data, str)
        assert "A wonderful story" in json_data
        assert "audio_url" in json_data  # Should include null value

    def test_json_serialization_with_audio(self):
        """Test JSON serialization with audio URL."""
        story = StoryResponse(
            story_text="Another story",
            audio_url="https://example.com/audio.mp3"
        )
        json_data = story.model_dump_json()
        
        assert "Another story" in json_data
        assert "https://example.com/audio.mp3" in json_data

    def test_dict_conversion(self):
        """Test conversion to dictionary."""
        story = StoryResponse(
            story_text="Dict test story",
            audio_url="https://test.com/audio.wav"
        )
        
        data_dict = story.model_dump()
        assert isinstance(data_dict, dict)
        assert data_dict["story_text"] == "Dict test story"
        assert data_dict["audio_url"] == "https://test.com/audio.wav"

    def test_dict_conversion_with_none_audio(self):
        """Test dictionary conversion with None audio URL."""
        story = StoryResponse(story_text="No audio story")
        
        data_dict = story.model_dump()
        assert data_dict["story_text"] == "No audio story"
        assert data_dict["audio_url"] is None

    def test_from_dict_creation(self):
        """Test creating StoryResponse from dictionary."""
        data = {
            "story_text": "From dict story",
            "audio_url": "https://fromdict.com/audio.mp3"
        }
        
        story = StoryResponse(**data)
        assert story.story_text == "From dict story"
        assert story.audio_url == "https://fromdict.com/audio.mp3"

    def test_from_dict_with_missing_audio(self):
        """Test creating from dict without audio_url."""
        data = {"story_text": "Missing audio story"}
        
        story = StoryResponse(**data)
        assert story.story_text == "Missing audio story"
        assert story.audio_url is None


class TestStoryResponseEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_story_text(self):
        """Test handling of very long story text."""
        long_story = "Once upon a time " * 10000  # Very long story
        
        story = StoryResponse(story_text=long_story)
        assert story.story_text == long_story
        assert len(story.story_text) > 100000

    def test_unicode_story_content(self):
        """Test handling of unicode content in story."""
        unicode_story = """
        היה היה מלך 👑 שגר בארמון יפה.
        Il était une fois un roi qui vivait dans un château 🏰.
        从前有一个国王住在美丽的城堡里 🌸.
        Жил-был король в прекрасном замке ⭐.
        """
        
        story = StoryResponse(story_text=unicode_story)
        assert story.story_text == unicode_story

    def test_story_with_special_characters(self):
        """Test story text with special characters and formatting."""
        special_story = """
        "Hello," said the dragon. 'How are you?'
        The child replied: "I'm fine!"
        
        Mathematical symbols: ∑ ∫ π ∞
        Currency: $100 €50 ¥200 £75
        Punctuation: ... --- !!! ??? 
        """
        
        story = StoryResponse(story_text=special_story)
        assert story.story_text == special_story

    def test_very_long_audio_url(self):
        """Test handling of very long audio URLs."""
        long_url = "https://example.com/" + "very-long-path/" * 100 + "story.mp3"
        
        story = StoryResponse(
            story_text="Test",
            audio_url=long_url
        )
        assert story.audio_url == long_url

    def test_audio_url_with_special_characters(self):
        """Test audio URL with special characters."""
        special_url = "https://example.com/story-title-with-spaces-and-símb⭐ls.mp3"
        
        story = StoryResponse(
            story_text="Special URL test",
            audio_url=special_url
        )
        assert story.audio_url == special_url


class TestStoryResponseEquality:
    """Test equality and comparison operations."""

    def test_equality_same_content(self):
        """Test equality of stories with same content."""
        story1 = StoryResponse(
            story_text="Same story",
            audio_url="https://example.com/audio.mp3"
        )
        story2 = StoryResponse(
            story_text="Same story",
            audio_url="https://example.com/audio.mp3"
        )
        
        assert story1 == story2

    def test_equality_different_text(self):
        """Test inequality when story text differs."""
        story1 = StoryResponse(story_text="Story one")
        story2 = StoryResponse(story_text="Story two")
        
        assert story1 != story2

    def test_equality_different_audio(self):
        """Test inequality when audio URL differs."""
        story1 = StoryResponse(
            story_text="Same text",
            audio_url="https://example.com/audio1.mp3"
        )
        story2 = StoryResponse(
            story_text="Same text",
            audio_url="https://example.com/audio2.mp3"
        )
        
        assert story1 != story2

    def test_equality_one_with_none_audio(self):
        """Test inequality when one has None audio and other has URL."""
        story1 = StoryResponse(story_text="Test")  # audio_url is None
        story2 = StoryResponse(
            story_text="Test",
            audio_url="https://example.com/audio.mp3"
        )
        
        assert story1 != story2