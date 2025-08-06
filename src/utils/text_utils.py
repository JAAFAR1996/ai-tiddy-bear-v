"""
Text processing utilities for child-safe content handling.
Provides text analysis, filtering, and processing capabilities.
"""

import re
from typing import Dict, Any, List, Optional
from src.core.utils.text_filters import filter_inappropriate_content as core_filter_content


class TextProcessor:
    """Text processing and analysis utilities."""

    def __init__(self, max_text_length: int = 1000, child_safe_mode: bool = True):
        self.max_text_length = max_text_length
        self.child_safe_mode = child_safe_mode

    def clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""

        # Remove extra whitespace
        cleaned = re.sub(r"\s+", " ", text.strip())

        # Remove special characters if in child safe mode
        if self.child_safe_mode:
            cleaned = re.sub(r"[^\w\s\.\!\?\,\-\'\"]", "", cleaned)

        return cleaned

    def filter_inappropriate_content(self, text: str) -> Dict[str, Any]:
        """Filter inappropriate content using core filtering."""
        return core_filter_content(text)

    def analyze_text_complexity(self, text: str) -> Dict[str, Any]:
        """Analyze text complexity for age appropriateness."""
        words = text.split()
        sentences = re.split(r"[.!?]+", text)

        # Simple complexity metrics
        word_count = len(words)
        sentence_count = len([s for s in sentences if s.strip()])
        avg_word_length = sum(len(word) for word in words) / max(word_count, 1)
        avg_sentence_length = word_count / max(sentence_count, 1)

        # Estimate reading level (simplified)
        reading_level = (avg_word_length + avg_sentence_length) / 2

        # Determine appropriate age
        if reading_level <= 3:
            appropriate_for_age = 3
        elif reading_level <= 5:
            appropriate_for_age = 6
        elif reading_level <= 7:
            appropriate_for_age = 9
        else:
            appropriate_for_age = 12

        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "avg_word_length": avg_word_length,
            "avg_sentence_length": avg_sentence_length,
            "reading_level": reading_level,
            "appropriate_for_age": appropriate_for_age,
        }

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text (mock implementation)."""
        # This would use a real sentiment analysis library in production
        positive_words = ["happy", "love", "fun", "great", "wonderful", "amazing"]
        negative_words = ["sad", "angry", "hate", "bad", "terrible", "awful"]

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            sentiment = "positive"
            confidence = min(0.9, 0.5 + (positive_count - negative_count) * 0.1)
        elif negative_count > positive_count:
            sentiment = "negative"
            confidence = min(0.9, 0.5 + (negative_count - positive_count) * 0.1)
        else:
            sentiment = "neutral"
            confidence = 0.5

        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "emotions": self._detect_emotions(text_lower),
        }

    def extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text."""
        # Simple keyword extraction (would use NLP library in production)
        words = re.findall(r"\b\w+\b", text.lower())

        # Filter out common words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
        }

        keywords = [word for word in words if word not in stop_words and len(word) > 2]

        # Count frequency and return most common
        word_freq = {}
        for word in keywords:
            word_freq[word] = word_freq.get(word, 0) + 1

        # Sort by frequency and return top keywords
        sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_keywords[:10]]

    def truncate_text(self, text: str, max_length: Optional[int] = None) -> str:
        """Truncate text to maximum length."""
        max_len = max_length or self.max_text_length

        if len(text) <= max_len:
            return text

        # Truncate at word boundary if possible
        truncated = text[:max_len]
        last_space = truncated.rfind(" ")

        if last_space > max_len * 0.8:  # If last space is reasonably close to end
            truncated = truncated[:last_space]

        return truncated + "..."

    def detect_topics(self, text: str) -> Dict[str, Any]:
        """Detect topics in text for content categorization."""
        topic_keywords = {
            "animals": ["dog", "cat", "elephant", "lion", "bird", "fish", "animal"],
            "fairy_tales": ["princess", "prince", "fairy", "magic", "castle", "dragon"],
            "games": ["play", "game", "fun", "toy", "puzzle", "sport"],
            "science": ["space", "planet", "star", "experiment", "dinosaur"],
            "stories": ["story", "tale", "adventure", "journey", "hero"],
        }

        text_lower = text.lower()
        detected_topics = []

        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                detected_topics.append(topic)

        child_safe_topics = ["animals", "fairy_tales", "games", "science", "stories"]
        child_safe = all(topic in child_safe_topics for topic in detected_topics)

        return {
            "topics": detected_topics,
            "child_safe": child_safe,
            "age_appropriate": child_safe,  # Simplified logic
        }

    def classify_intent(self, text: str) -> Dict[str, Any]:
        """Classify the intent of user message."""
        text_lower = text.lower()

        # Simple intent classification
        if any(word in text_lower for word in ["story", "tell me", "once upon"]):
            intent = "story_request"
            confidence = 0.9
            entities = self._extract_story_entities(text_lower)
        elif any(
            word in text_lower
            for word in ["question", "what", "how", "why", "where", "when"]
        ):
            intent = "question"
            confidence = 0.8
            entities = []
        elif any(word in text_lower for word in ["play", "game", "fun"]):
            intent = "play_request"
            confidence = 0.7
            entities = []
        else:
            intent = "general_chat"
            confidence = 0.5
            entities = []

        return {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "requires_response": True,
        }

    def _detect_emotions(self, text: str) -> List[str]:
        """Detect emotions in text."""
        emotion_keywords = {
            "joy": ["happy", "joy", "excited", "fun", "wonderful"],
            "sadness": ["sad", "cry", "unhappy", "down"],
            "anger": ["angry", "mad", "upset", "frustrated"],
            "fear": ["scared", "afraid", "frightened", "worried"],
            "surprise": ["wow", "amazing", "surprised", "incredible"],
            "curiosity": ["wonder", "curious", "interesting", "why", "how"],
        }

        detected_emotions = []
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in text for keyword in keywords):
                detected_emotions.append(emotion)

        return detected_emotions or ["neutral"]

    def _extract_story_entities(self, text: str) -> List[str]:
        """Extract entities relevant to story requests."""
        entities = []

        # Common story entities
        story_entities = [
            "dragon",
            "princess",
            "knight",
            "fairy",
            "animal",
            "forest",
            "castle",
            "magic",
        ]

        for entity in story_entities:
            if entity in text:
                entities.append(entity)

        return entities


class SafeTextAnalyzer:
    """Specialized text analyzer for child safety."""

    def __init__(self):
        self.text_processor = TextProcessor(child_safe_mode=True)

    def analyze_child_message(self, message: str, child_age: int) -> Dict[str, Any]:
        """Comprehensive analysis of child message for safety."""
        # Clean and filter
        cleaned = self.text_processor.clean_text(message)
        filtered_result = self.text_processor.filter_inappropriate_content(cleaned)

        # Analyze complexity
        complexity = self.text_processor.analyze_text_complexity(cleaned)

        # Check age appropriateness
        age_appropriate = complexity["appropriate_for_age"] <= child_age + 2

        # Sentiment analysis
        sentiment = self.text_processor.analyze_sentiment(cleaned)

        # Topic detection
        topics = self.text_processor.detect_topics(cleaned)

        return {
            "original_message": message,
            "cleaned_message": cleaned,
            "filtered_message": filtered_result["filtered_text"],
            "was_filtered": filtered_result["was_filtered"],
            "age_appropriate": age_appropriate,
            "complexity": complexity,
            "sentiment": sentiment,
            "topics": topics,
            "safety_approved": topics["child_safe"] and age_appropriate,
            "requires_adult_review": not topics["child_safe"]
            or filtered_result["was_filtered"],
        }
