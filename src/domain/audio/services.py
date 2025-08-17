"""
Audio Domain Services - Pure Business Logic
==========================================
Domain services containing business rules and logic.
No infrastructure dependencies.
"""

import re
from typing import List, Optional
from src.domain.audio.entities import AudioFile, Voice, TranscriptionRequest, SynthesisRequest
from src.shared.audio_types import VoiceEmotion, AudioQuality


class AudioValidationService:
    """Domain service for audio business validation."""
    
    def validate_audio_for_child(self, audio: AudioFile, child_age: int) -> tuple[bool, List[str]]:
        """Business rule: validate audio appropriateness for child."""
        issues = []
        
        if not audio.is_valid_for_processing():
            issues.append("Audio does not meet processing requirements")
        
        if not audio.is_appropriate_for_child_age(child_age):
            issues.append(f"Audio duration inappropriate for age {child_age}")
        
        if not audio.is_child_safe:
            issues.append("Audio content not marked as child-safe")
        
        return len(issues) == 0, issues
    
    def validate_transcription_request(self, request: TranscriptionRequest) -> tuple[bool, List[str]]:
        """Business rule: validate transcription request."""
        issues = []
        
        if not request.is_valid():
            issues.append("Invalid transcription request")
        
        if request.child_age and request.child_age < 3:
            issues.append("Child age too young for speech processing")
        
        if request.child_age and request.child_age > 13:
            issues.append("Child age outside COPPA range")
        
        return len(issues) == 0, issues
    
    def validate_synthesis_request(self, request: SynthesisRequest) -> tuple[bool, List[str]]:
        """Business rule: validate synthesis request."""
        issues = []
        
        if not request.is_valid():
            issues.append("Invalid synthesis request")
        
        if len(request.text) > 1000:  # Business rule: text length limit
            issues.append("Text too long for child attention span")
        
        return len(issues) == 0, issues


class VoiceSelectionService:
    """Domain service for voice selection business logic."""
    
    def select_appropriate_voice(
        self, 
        available_voices: List[Voice], 
        child_age: int,
        preferred_emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    ) -> Optional[Voice]:
        """Business rule: select most appropriate voice for child."""
        
        # Filter child-appropriate voices
        suitable_voices = [
            voice for voice in available_voices 
            if voice.can_be_used_by_child(child_age) and voice.supports_emotion(preferred_emotion)
        ]
        
        if not suitable_voices:
            return None
        
        # Business rule: prefer child voices for younger children
        if child_age < 7:
            child_voices = [v for v in suitable_voices if v.age_group == "child"]
            if child_voices:
                return child_voices[0]
        
        # Business rule: prefer neutral gender for inclusivity
        neutral_voices = [v for v in suitable_voices if v.gender.value == "neutral"]
        if neutral_voices:
            return neutral_voices[0]
        
        return suitable_voices[0]
    
    def get_recommended_emotions_for_age(self, child_age: int) -> List[VoiceEmotion]:
        """Business rule: age-appropriate emotions."""
        base_emotions = [VoiceEmotion.NEUTRAL, VoiceEmotion.GENTLE, VoiceEmotion.CALM]
        
        if child_age >= 5:
            base_emotions.extend([VoiceEmotion.HAPPY, VoiceEmotion.PLAYFUL])
        
        if child_age >= 8:
            base_emotions.append(VoiceEmotion.ENCOURAGING)
        
        return base_emotions


class ContentSafetyService:
    """Domain service for content safety business rules."""
    
    def __init__(self):
        """Initialize with compiled regex patterns for performance."""
        # Unsafe words pattern - compiled once for performance
        unsafe_words = [
            "scary", "frightening", "violence", "weapon", "adult", "dangerous", 
            "hurt", "pain", "death", "kill", "blood", "war", "fight", "attack",
            "monster", "nightmare", "terror", "horror", "evil", "devil"
        ]
        self._unsafe_pattern = re.compile(
            r'\b(?:' + '|'.join(re.escape(word) for word in unsafe_words) + r')\b', 
            re.IGNORECASE
        )
        
        # URL pattern to detect web links
        self._url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            re.IGNORECASE
        )
        
        # Email pattern to detect email addresses
        self._email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
    
    def is_text_appropriate_for_child(self, text: str, child_age: int) -> tuple[bool, List[str]]:
        """Business rule: text content appropriateness using regex."""
        issues = []
        
        if not text or not text.strip():
            return True, []
        
        # Check for unsafe words using compiled regex
        unsafe_matches = self._unsafe_pattern.findall(text)
        if unsafe_matches:
            issues.append(f"Contains inappropriate words: {', '.join(set(unsafe_matches))}")
        
        # Check for URLs (not appropriate for children)
        if self._url_pattern.search(text):
            issues.append("Contains web URLs")
        
        # Check for email addresses (privacy concern)
        if self._email_pattern.search(text):
            issues.append("Contains email addresses")
        
        # Business rule: text complexity by age
        word_count = len(text.split())
        max_words = self._get_max_words_for_age(child_age)
        
        if word_count > max_words:
            issues.append(f"Text too complex for age {child_age}")
        
        return len(issues) == 0, issues
    
    def filter_inappropriate_content(self, text: str) -> str:
        """Business rule: content filtering using regex."""
        if not text:
            return text
        
        filtered_text = text
        
        # Filter unsafe words using regex
        filtered_text = self._unsafe_pattern.sub('[filtered]', filtered_text)
        
        # Filter URLs
        filtered_text = self._url_pattern.sub('[web-link-removed]', filtered_text)
        
        # Filter email addresses
        filtered_text = self._email_pattern.sub('[email-removed]', filtered_text)
        
        return filtered_text
    
    def _get_max_words_for_age(self, child_age: int) -> int:
        """Business rule: maximum words by age."""
        if child_age < 5:
            return 20
        elif child_age < 8:
            return 50
        else:
            return 100


class AudioProcessingRulesService:
    """Domain service for audio processing business rules."""
    
    def get_recommended_quality_for_age(self, child_age: int) -> AudioQuality:
        """Business rule: audio quality by age."""
        # Younger children need higher quality for comprehension
        if child_age < 6:
            return AudioQuality.HIGH
        elif child_age < 10:
            return AudioQuality.STANDARD
        else:
            return AudioQuality.STANDARD
    
    def should_enable_content_filtering(self, child_age: int) -> bool:
        """Business rule: content filtering requirement."""
        # Always enable for children under 13 (COPPA compliance)
        return child_age < 13
    
    def get_max_processing_time_for_age(self, child_age: int) -> float:
        """Business rule: processing time limits by age."""
        # Younger children have shorter attention spans
        if child_age < 5:
            return 3000  # 3 seconds max
        elif child_age < 8:
            return 5000  # 5 seconds max
        else:
            return 10000  # 10 seconds max
