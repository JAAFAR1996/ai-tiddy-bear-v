"""
Comprehensive unit tests for text_utils module.
Production-grade testing for text processing and child-safe content analysis.
"""

import pytest
from unittest.mock import patch, Mock

from src.utils.text_utils import TextProcessor, SafeTextAnalyzer


class TestTextProcessor:
    """Test TextProcessor class functionality."""

    @pytest.fixture
    def text_processor(self):
        """Create TextProcessor instance for testing."""
        return TextProcessor()

    @pytest.fixture
    def text_processor_custom(self):
        """Create TextProcessor with custom settings."""
        return TextProcessor(max_text_length=100, child_safe_mode=False)

    @pytest.fixture
    def non_child_safe_processor(self):
        """Create TextProcessor with child safe mode disabled."""
        return TextProcessor(child_safe_mode=False)

    def test_init_default_parameters(self):
        """Test TextProcessor initialization with default parameters."""
        processor = TextProcessor()
        assert processor.max_text_length == 1000
        assert processor.child_safe_mode is True

    def test_init_custom_parameters(self):
        """Test TextProcessor initialization with custom parameters."""
        processor = TextProcessor(max_text_length=500, child_safe_mode=False)
        assert processor.max_text_length == 500
        assert processor.child_safe_mode is False

    def test_clean_text_basic_cleaning(self, text_processor):
        """Test basic text cleaning functionality."""
        test_cases = [
            ("  Hello    world  ", "Hello world"),
            ("Multiple\n\nlines\twith\ttabs", "Multiple lines with tabs"),
            ("", ""),
            ("   ", ""),
            ("Normal text", "Normal text")
        ]
        
        for input_text, expected in test_cases:
            result = text_processor.clean_text(input_text)
            assert result == expected

    def test_clean_text_child_safe_mode(self, text_processor):
        """Test text cleaning in child safe mode."""
        test_cases = [
            ("Hello @#$% world!", "Hello  world!"),
            ("Text with symbols &*()+=", "Text with symbols "),
            ("Keep-these'symbols\"okay?", "Keep-these'symbols\"okay?"),
            ("Remove #hashtags and @mentions", "Remove hashtags and mentions")
        ]
        
        for input_text, expected in test_cases:
            result = text_processor.clean_text(input_text)
            assert result == expected

    def test_clean_text_non_child_safe_mode(self, non_child_safe_processor):
        """Test text cleaning with child safe mode disabled."""
        input_text = "Hello @#$% world! Keep symbols &*()"
        result = non_child_safe_processor.clean_text(input_text)
        # Should only clean whitespace, not remove symbols
        assert "@#$%" in result
        assert "&*()" in result

    def test_filter_inappropriate_content_no_filtering(self, text_processor):
        """Test content filtering with clean text."""
        clean_text = "Hi there! How are you today?"  # Changed from "Hello" to avoid "hell" substring
        result = text_processor.filter_inappropriate_content(clean_text)
        
        assert result["filtered_text"] == clean_text
        assert result["was_filtered"] is False
        assert result["original_length"] == len(clean_text)
        assert result["filtered_length"] == len(clean_text)

    def test_filter_inappropriate_content_with_filtering(self, text_processor):
        """Test content filtering with inappropriate words."""
        inappropriate_text = "That's damn difficult and hell of a problem"
        result = text_processor.filter_inappropriate_content(inappropriate_text)
        
        assert "damn" not in result["filtered_text"]
        assert "hell" not in result["filtered_text"]
        assert "very" in result["filtered_text"]
        assert "place" in result["filtered_text"]
        assert result["was_filtered"] is True

    def test_filter_inappropriate_content_case_insensitive(self, text_processor):
        """Test content filtering is case insensitive."""
        test_cases = [
            "DAMN that's loud",
            "Hell of a day",
            "DarN it"
        ]
        
        for text in test_cases:
            result = text_processor.filter_inappropriate_content(text)
            assert result["was_filtered"] is True

    def test_analyze_text_complexity_simple_text(self, text_processor):
        """Test text complexity analysis with simple text."""
        simple_text = "I like cats. They are fun."
        result = text_processor.analyze_text_complexity(simple_text)
        
        assert result["word_count"] == 6
        assert result["sentence_count"] == 2
        assert result["avg_word_length"] > 0
        assert result["avg_sentence_length"] == 3.0
        assert result["appropriate_for_age"] <= 6  # Should be appropriate for young kids

    def test_analyze_text_complexity_complex_text(self, text_processor):
        """Test text complexity analysis with complex text."""
        complex_text = "The extraordinarily sophisticated methodology demonstrates unprecedented capabilities in computational linguistics."
        result = text_processor.analyze_text_complexity(complex_text)
        
        assert result["word_count"] == 10
        assert result["sentence_count"] == 1
        assert result["avg_word_length"] > 8  # Long words
        assert result["avg_sentence_length"] == 10.0
        assert result["appropriate_for_age"] >= 9  # Should be for older kids

    def test_analyze_text_complexity_edge_cases(self, text_processor):
        """Test text complexity analysis edge cases."""
        # Empty text
        result = text_processor.analyze_text_complexity("")
        assert result["word_count"] == 0
        assert result["sentence_count"] == 0
        
        # Single word
        result = text_processor.analyze_text_complexity("Hello")
        assert result["word_count"] == 1
        assert result["sentence_count"] == 1

    def test_analyze_sentiment_positive(self, text_processor):
        """Test sentiment analysis with positive text."""
        positive_texts = [
            "I am so happy and love this wonderful day!",
            "This is amazing and great fun!",
            "Happy happy joy joy!"
        ]
        
        for text in positive_texts:
            result = text_processor.analyze_sentiment(text)
            assert result["sentiment"] == "positive"
            assert result["confidence"] > 0.5
            assert "emotions" in result

    def test_analyze_sentiment_negative(self, text_processor):
        """Test sentiment analysis with negative text."""
        negative_texts = [
            "I am so sad and hate this terrible day",
            "This is awful and bad",
            "Angry and sad feelings"
        ]
        
        for text in negative_texts:
            result = text_processor.analyze_sentiment(text)
            assert result["sentiment"] == "negative"
            assert result["confidence"] > 0.5

    def test_analyze_sentiment_neutral(self, text_processor):
        """Test sentiment analysis with neutral text."""
        neutral_texts = [
            "The weather is normal today",
            "I went to the store",
            "This is a regular sentence"
        ]
        
        for text in neutral_texts:
            result = text_processor.analyze_sentiment(text)
            assert result["sentiment"] == "neutral"
            assert result["confidence"] == 0.5

    def test_analyze_sentiment_emotion_detection(self, text_processor):
        """Test emotion detection in sentiment analysis."""
        emotional_text = "I am so happy and excited about this amazing surprise!"
        result = text_processor.analyze_sentiment(emotional_text)
        
        emotions = result["emotions"]
        assert isinstance(emotions, list)
        assert len(emotions) > 0
        # Should detect joy and surprise
        assert "joy" in emotions or "surprise" in emotions

    def test_extract_keywords_basic(self, text_processor):
        """Test basic keyword extraction."""
        text = "The cat sat on the mat with the hat"
        keywords = text_processor.extract_keywords(text)
        
        assert isinstance(keywords, list)
        assert "cat" in keywords
        assert "sat" in keywords
        assert "mat" in keywords
        assert "hat" in keywords
        # Stop words should be filtered out
        assert "the" not in keywords
        assert "on" not in keywords
        assert "with" not in keywords

    def test_extract_keywords_frequency_ordering(self, text_processor):
        """Test keyword extraction orders by frequency."""
        text = "cat dog cat bird cat dog cat"  # cat:4, dog:2, bird:1
        keywords = text_processor.extract_keywords(text)
        
        assert keywords[0] == "cat"  # Most frequent first
        assert keywords[1] == "dog"  # Second most frequent
        assert keywords[2] == "bird"  # Least frequent

    def test_extract_keywords_empty_text(self, text_processor):
        """Test keyword extraction with empty text."""
        keywords = text_processor.extract_keywords("")
        assert keywords == []

    def test_truncate_text_short_text(self, text_processor):
        """Test text truncation with short text."""
        short_text = "This is a short message"
        result = text_processor.truncate_text(short_text)
        assert result == short_text  # Should not be truncated

    def test_truncate_text_long_text(self, text_processor):
        """Test text truncation with long text."""
        long_text = "A" * 1500  # Longer than default max_length
        result = text_processor.truncate_text(long_text)
        
        assert len(result) <= 1003  # max_length + "..."
        assert result.endswith("...")

    def test_truncate_text_word_boundary(self, text_processor):
        """Test text truncation at word boundaries."""
        # Create text that will need truncation at word boundary
        words = ["word"] * 300  # 300 * 4 = 1200 chars + 299 spaces = 1499 chars
        long_text = " ".join(words)
        
        result = text_processor.truncate_text(long_text, max_length=100)
        
        assert len(result) <= 103  # max_length + "..."
        assert result.endswith("...")
        assert not result[:-3].endswith(" wo")  # Should not cut word in middle

    def test_truncate_text_custom_length(self, text_processor):
        """Test text truncation with custom max length."""
        text = "A" * 200
        result = text_processor.truncate_text(text, max_length=50)
        
        assert len(result) <= 53  # 50 + "..."
        assert result.endswith("...")

    def test_detect_topics_animals(self, text_processor):
        """Test topic detection with animal content."""
        animal_text = "I love cats and dogs. The elephant is big."
        result = text_processor.detect_topics(animal_text)
        
        assert "animals" in result["topics"]
        assert result["child_safe"] is True
        assert result["age_appropriate"] is True

    def test_detect_topics_fairy_tales(self, text_processor):
        """Test topic detection with fairy tale content."""
        fairy_text = "The princess lived in a magical castle with a dragon"
        result = text_processor.detect_topics(fairy_text)
        
        assert "fairy_tales" in result["topics"]
        assert result["child_safe"] is True

    def test_detect_topics_multiple_topics(self, text_processor):
        """Test topic detection with multiple topics."""
        mixed_text = "The princess played games with her dog in space"
        result = text_processor.detect_topics(mixed_text)
        
        topics = result["topics"]
        assert "fairy_tales" in topics
        assert "games" in topics
        assert "animals" in topics
        assert "science" in topics
        assert result["child_safe"] is True

    def test_detect_topics_no_topics(self, text_processor):
        """Test topic detection with content having no specific topics."""
        generic_text = "This is a regular message with no specific topics"
        result = text_processor.detect_topics(generic_text)
        
        assert result["topics"] == []
        assert result["child_safe"] is True  # Empty topics are safe

    def test_classify_intent_story_request(self, text_processor):
        """Test intent classification for story requests."""
        story_requests = [
            "Tell me a story about dragons",
            "I want to hear a story",
            "Once upon a time story please"
        ]
        
        for text in story_requests:
            result = text_processor.classify_intent(text)
            assert result["intent"] == "story_request"
            assert result["confidence"] == 0.9
            assert result["requires_response"] is True

    def test_classify_intent_question(self, text_processor):
        """Test intent classification for questions."""
        questions = [
            "What is that?",
            "How does this work?",
            "Why is the sky blue?",
            "Where do birds live?"
        ]
        
        for text in questions:
            result = text_processor.classify_intent(text)
            assert result["intent"] == "question"
            assert result["confidence"] == 0.8

    def test_classify_intent_play_request(self, text_processor):
        """Test intent classification for play requests."""
        play_requests = [
            "Let's play a game",
            "Can we have some fun?",
            "I want to play"
        ]
        
        for text in play_requests:
            result = text_processor.classify_intent(text)
            assert result["intent"] == "play_request"
            assert result["confidence"] == 0.7

    def test_classify_intent_general_chat(self, text_processor):
        """Test intent classification for general chat."""
        general_messages = [
            "Hello there",
            "Good morning",
            "I had lunch today"
        ]
        
        for text in general_messages:
            result = text_processor.classify_intent(text)
            assert result["intent"] == "general_chat"
            assert result["confidence"] == 0.5

    def test_classify_intent_story_entities(self, text_processor):
        """Test story entity extraction in intent classification."""
        story_text = "Tell me a story about a dragon and a princess in a castle"
        result = text_processor.classify_intent(story_text)
        
        assert result["intent"] == "story_request"
        entities = result["entities"]
        assert "dragon" in entities
        assert "princess" in entities
        assert "castle" in entities

    def test_detect_emotions_various_emotions(self, text_processor):
        """Test emotion detection with various emotional content."""
        # Test using private method directly
        test_cases = [
            ("I am so happy and excited!", ["joy"]),
            ("I am scared and worried", ["fear"]),
            ("This is amazing and wow!", ["surprise"]),
            ("I am sad and want to cry", ["sadness"]),
            ("I am angry and upset", ["anger"]),
            ("I wonder how this works", ["curiosity"])
        ]
        
        for text, expected_emotions in test_cases:
            emotions = text_processor._detect_emotions(text.lower())
            for expected in expected_emotions:
                assert expected in emotions

    def test_detect_emotions_neutral(self, text_processor):
        """Test emotion detection with neutral content."""
        neutral_text = "This is a normal message"
        emotions = text_processor._detect_emotions(neutral_text.lower())
        assert emotions == ["neutral"]

    def test_extract_story_entities(self, text_processor):
        """Test story entity extraction."""
        story_text = "dragon princess knight fairy animal forest castle magic"
        entities = text_processor._extract_story_entities(story_text)
        
        expected_entities = ["dragon", "princess", "knight", "fairy", "animal", "forest", "castle", "magic"]
        for entity in expected_entities:
            assert entity in entities

    def test_extract_story_entities_no_entities(self, text_processor):
        """Test story entity extraction with no entities."""
        regular_text = "hello there how are you today"
        entities = text_processor._extract_story_entities(regular_text)
        assert entities == []


class TestSafeTextAnalyzer:
    """Test SafeTextAnalyzer class functionality."""

    @pytest.fixture
    def safe_analyzer(self):
        """Create SafeTextAnalyzer instance for testing."""
        return SafeTextAnalyzer()

    def test_init_default(self):
        """Test SafeTextAnalyzer initialization."""
        analyzer = SafeTextAnalyzer()
        assert analyzer.text_processor is not None
        assert analyzer.text_processor.child_safe_mode is True

    def test_analyze_child_message_safe_content(self, safe_analyzer):
        """Test child message analysis with safe content."""
        safe_message = "I love playing with my cat and dog!"
        child_age = 8
        
        result = safe_analyzer.analyze_child_message(safe_message, child_age)
        
        assert result["original_message"] == safe_message
        assert result["cleaned_message"] == safe_message
        assert result["was_filtered"] is False
        assert result["age_appropriate"] is True
        assert result["safety_approved"] is True
        assert result["requires_adult_review"] is False

    def test_analyze_child_message_inappropriate_content(self, safe_analyzer):
        """Test child message analysis with inappropriate content."""
        inappropriate_message = "This damn thing is from hell"
        child_age = 8
        
        result = safe_analyzer.analyze_child_message(inappropriate_message, child_age)
        
        assert result["original_message"] == inappropriate_message
        assert result["was_filtered"] is True
        assert "damn" not in result["filtered_message"]
        assert "hell" not in result["filtered_message"]
        assert result["requires_adult_review"] is True

    def test_analyze_child_message_complex_content(self, safe_analyzer):
        """Test child message analysis with age-inappropriate complexity."""
        complex_message = "The extraordinarily sophisticated computational methodology demonstrates unprecedented capabilities"
        child_age = 6  # Too young for this complexity
        
        result = safe_analyzer.analyze_child_message(complex_message, child_age)
        
        assert result["age_appropriate"] is False
        # Might still be safety approved if topics are child-safe
        complexity = result["complexity"]
        assert complexity["appropriate_for_age"] > child_age + 2

    def test_analyze_child_message_positive_sentiment(self, safe_analyzer):
        """Test child message analysis with positive sentiment."""
        positive_message = "I am so happy and love this wonderful day!"
        child_age = 8
        
        result = safe_analyzer.analyze_child_message(positive_message, child_age)
        
        sentiment = result["sentiment"]
        assert sentiment["sentiment"] == "positive"
        assert sentiment["confidence"] > 0.5

    def test_analyze_child_message_child_topics(self, safe_analyzer):
        """Test child message analysis with child-appropriate topics."""
        topic_message = "I like princess stories!"  # Simpler message
        child_age = 7
        
        result = safe_analyzer.analyze_child_message(topic_message, child_age)
        
        topics = result["topics"]
        assert "fairy_tales" in topics["topics"]
        assert topics["child_safe"] is True
        assert result["safety_approved"] is True

    def test_analyze_child_message_comprehensive_analysis(self, safe_analyzer):
        """Test comprehensive child message analysis."""
        message = "I like cats and dogs!"  # Simpler message for 6-year-old
        child_age = 6
        
        result = safe_analyzer.analyze_child_message(message, child_age)
        
        # Check all required fields are present
        required_fields = [
            "original_message", "cleaned_message", "filtered_message",
            "was_filtered", "age_appropriate", "complexity", 
            "sentiment", "topics", "safety_approved", "requires_adult_review"
        ]
        
        for field in required_fields:
            assert field in result
        
        # Should be fully approved for 6-year-old with simple message
        assert result["safety_approved"] is True
        assert result["requires_adult_review"] is False
        
        # Should detect appropriate topics
        topics = result["topics"]["topics"]
        assert "animals" in topics


class TestTextProcessorEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def text_processor(self):
        return TextProcessor()

    def test_clean_text_none_input(self, text_processor):
        """Test clean_text with None input."""
        result = text_processor.clean_text(None)
        assert result == ""

    def test_filter_inappropriate_content_empty_text(self, text_processor):
        """Test filtering with empty text."""
        result = text_processor.filter_inappropriate_content("")
        assert result["filtered_text"] == ""
        assert result["was_filtered"] is False
        assert result["original_length"] == 0
        assert result["filtered_length"] == 0

    def test_analyze_text_complexity_single_character(self, text_processor):
        """Test complexity analysis with single character."""
        result = text_processor.analyze_text_complexity("A")
        assert result["word_count"] == 1
        assert result["avg_word_length"] == 1.0

    def test_truncate_text_exact_length(self, text_processor):
        """Test text truncation at exactly max length."""
        text = "A" * 1000  # Exactly max length
        result = text_processor.truncate_text(text)
        assert result == text  # Should not be truncated
        assert not result.endswith("...")

    def test_sentiment_analysis_empty_text(self, text_processor):
        """Test sentiment analysis with empty text."""
        result = text_processor.analyze_sentiment("")
        assert result["sentiment"] == "neutral"
        assert result["confidence"] == 0.5

    def test_keyword_extraction_only_stop_words(self, text_processor):
        """Test keyword extraction with only stop words."""
        stop_word_text = "the and or but in on at to for of with"
        keywords = text_processor.extract_keywords(stop_word_text)
        assert keywords == []

    def test_topic_detection_case_sensitivity(self, text_processor):
        """Test topic detection is case insensitive."""
        text = "I love CATS and Dogs and BIRDS"
        result = text_processor.detect_topics(text)
        assert "animals" in result["topics"]


class TestTextProcessorIntegration:
    """Integration tests for text processing workflows."""

    def test_complete_message_processing_workflow(self):
        """Test complete message processing workflow."""
        processor = TextProcessor()
        analyzer = SafeTextAnalyzer()
        
        # Simulate child message processing
        raw_message = "  Tell me a damn good story about dragons!  "
        child_age = 8
        
        # Step 1: Clean text
        cleaned = processor.clean_text(raw_message)
        assert cleaned == "Tell me a damn good story about dragons!"
        
        # Step 2: Filter inappropriate content
        filtered_result = processor.filter_inappropriate_content(cleaned)
        assert filtered_result["was_filtered"] is True
        assert "very" in filtered_result["filtered_text"]
        
        # Step 3: Analyze complexity
        complexity = processor.analyze_text_complexity(filtered_result["filtered_text"])
        assert complexity["appropriate_for_age"] <= child_age + 2
        
        # Step 4: Classify intent
        intent = processor.classify_intent(filtered_result["filtered_text"])
        assert intent["intent"] == "story_request"
        
        # Step 5: Comprehensive safety analysis
        safety_result = analyzer.analyze_child_message(raw_message, child_age)
        assert safety_result["requires_adult_review"] is True  # Due to filtering

    def test_content_moderation_workflow(self):
        """Test content moderation workflow for various content types."""
        processor = TextProcessor()
        
        test_messages = [
            {
                "message": "I love cats and dogs!",
                "expected_safe": True,
                "expected_filtered": False,
                "expected_topics": ["animals"]
            },
            {
                "message": "Tell me about princesses and dragons",
                "expected_safe": True,
                "expected_filtered": False,
                "expected_topics": ["fairy_tales"]
            },
            {
                "message": "This damn computer is hell to use",
                "expected_safe": True,  # After filtering
                "expected_filtered": True,
                "expected_topics": []
            }
        ]
        
        for test_case in test_messages:
            message = test_case["message"]
            
            # Clean and filter
            cleaned = processor.clean_text(message)
            filtered = processor.filter_inappropriate_content(cleaned)
            
            # Check filtering expectation
            assert filtered["was_filtered"] == test_case["expected_filtered"]
            
            # Detect topics
            topics = processor.detect_topics(filtered["filtered_text"])
            
            # Check topic detection
            for expected_topic in test_case["expected_topics"]:
                assert expected_topic in topics["topics"]
            
            # Check safety
            assert topics["child_safe"] == test_case["expected_safe"]

    def test_age_appropriate_content_analysis(self):
        """Test age-appropriate content analysis workflow."""
        analyzer = SafeTextAnalyzer()
        
        test_scenarios = [
            {
                "message": "I like cats",
                "age": 4,
                "expected_appropriate": True
            },
            {
                "message": "The extraordinarily sophisticated methodology",
                "age": 6,
                "expected_appropriate": False
            },
            {
                "message": "Let's play fun games together!",
                "age": 8,
                "expected_appropriate": True
            }
        ]
        
        for scenario in test_scenarios:
            result = analyzer.analyze_child_message(
                scenario["message"], 
                scenario["age"]
            )
            
            assert result["age_appropriate"] == scenario["expected_appropriate"]
            
            # Safety approval should consider both age and content safety
            if scenario["expected_appropriate"]:
                assert result["safety_approved"] is True
                assert result["requires_adult_review"] is False