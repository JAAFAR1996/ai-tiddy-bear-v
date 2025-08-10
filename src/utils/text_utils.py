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
        """Analyze sentiment of text using production NLP models."""
        try:
            # Try to use transformers library for real sentiment analysis
            from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
            
            # Use a pre-trained sentiment analysis model
            model_name = "cardiffnlp/twitter-roberta-base-sentiment-latest"
            
            # Initialize sentiment analyzer
            sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model=model_name,
                tokenizer=model_name,
                return_all_scores=True
            )
            
            # Analyze sentiment
            results = sentiment_analyzer(text[:512])  # Limit text length
            
            # Convert to our format
            scores = {result['label'].lower(): result['score'] for result in results[0]}
            
            # Determine primary sentiment
            primary_sentiment = max(scores, key=scores.get)
            confidence = scores[primary_sentiment]
            
            # Map model labels to our format
            label_mapping = {
                'negative': 'negative',
                'neutral': 'neutral', 
                'positive': 'positive',
                'label_0': 'negative',
                'label_1': 'neutral',
                'label_2': 'positive'
            }
            
            mapped_sentiment = label_mapping.get(primary_sentiment, 'neutral')
            
            return {
                "sentiment": mapped_sentiment,
                "confidence": float(confidence),
                "emotions": self._detect_emotions_advanced(text),
                "scores": {k: float(v) for k, v in scores.items()},
                "model_used": "transformers_roberta"
            }
            
        except ImportError:
            self.logger.warning("transformers library not available, using fallback analysis")
            return self._analyze_sentiment_fallback(text)
            
        except Exception as e:
            self.logger.error(f"Sentiment analysis failed: {e}")
            return self._analyze_sentiment_fallback(text)
    
    def _analyze_sentiment_fallback(self, text: str) -> Dict[str, Any]:
        """Fallback sentiment analysis using enhanced word lists."""
        # Enhanced word lists for more accurate analysis
        positive_words = [
            "happy", "love", "fun", "great", "wonderful", "amazing", "excited", 
            "joy", "smile", "laugh", "fantastic", "awesome", "brilliant", "perfect",
            "beautiful", "friend", "play", "adventure", "discover", "learn", "grow"
        ]
        
        negative_words = [
            "sad", "angry", "hate", "bad", "terrible", "awful", "scared", "fear",
            "worry", "upset", "hurt", "pain", "dangerous", "scary", "frightening",
            "violence", "fight", "monster", "nightmare", "cry", "lonely"
        ]
        
        neutral_words = [
            "okay", "fine", "normal", "regular", "standard", "typical", "usual",
            "maybe", "perhaps", "possibly", "probably", "might", "could"
        ]

        text_lower = text.lower()
        
        # Count word occurrences with weights
        positive_score = 0
        negative_score = 0
        neutral_score = 0
        
        for word in positive_words:
            count = text_lower.count(word)
            positive_score += count * 1.0
            
        for word in negative_words:
            count = text_lower.count(word)
            negative_score += count * 1.2  # Weight negative words more heavily for safety
            
        for word in neutral_words:
            count = text_lower.count(word)
            neutral_score += count * 0.8
        
        total_score = positive_score + negative_score + neutral_score
        
        if total_score == 0:
            sentiment = "neutral"
            confidence = 0.5
        elif negative_score > positive_score and negative_score > neutral_score:
            sentiment = "negative"
            confidence = min(0.95, 0.6 + (negative_score / total_score) * 0.3)
        elif positive_score > negative_score and positive_score > neutral_score:
            sentiment = "positive"
            confidence = min(0.95, 0.6 + (positive_score / total_score) * 0.3)
        else:
            sentiment = "neutral"
            confidence = min(0.85, 0.5 + (neutral_score / total_score) * 0.3)

        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "emotions": self._detect_emotions(text_lower),
            "scores": {
                "positive": positive_score / max(1, total_score),
                "negative": negative_score / max(1, total_score),
                "neutral": neutral_score / max(1, total_score)
            },
            "model_used": "enhanced_wordlist"
        }
    
    def _detect_emotions_advanced(self, text: str) -> List[str]:
        """Advanced emotion detection using NLP patterns."""
        emotions = []
        text_lower = text.lower()
        
        emotion_patterns = {
            "joy": ["happy", "excited", "thrilled", "delighted", "joyful", "cheerful"],
            "sadness": ["sad", "unhappy", "depressed", "down", "blue", "melancholy"],
            "anger": ["angry", "mad", "furious", "annoyed", "irritated", "upset"],
            "fear": ["scared", "afraid", "frightened", "worried", "anxious", "nervous"],
            "surprise": ["surprised", "amazed", "shocked", "astonished", "stunned"],
            "curiosity": ["curious", "wonder", "interested", "intrigued", "questioning"],
            "love": ["love", "adore", "care", "affection", "like", "fond"]
        }
        
        for emotion, words in emotion_patterns.items():
            if any(word in text_lower for word in words):
                emotions.append(emotion)
        
        return emotions if emotions else ["neutral"]

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
