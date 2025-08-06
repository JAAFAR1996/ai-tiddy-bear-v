"""
Audio Domain Entities - Pure Business Objects
============================================
Core business entities with no infrastructure dependencies.
"""

from dataclasses import dataclass
from typing import Optional, List
from src.shared.audio_types import AudioFormat, AudioQuality, VoiceGender, VoiceEmotion


@dataclass
class AudioFile:
    """Core audio business entity."""
    data: bytes
    format: AudioFormat
    duration_ms: float
    sample_rate: int
    is_child_safe: bool = False
    
    def is_valid_for_processing(self) -> bool:
        """Business rule: audio must meet minimum requirements."""
        return (
            len(self.data) > 0 and 
            self.duration_ms > 100 and 
            self.duration_ms < 300000 and
            self.sample_rate >= 8000
        )
    
    def is_appropriate_for_child_age(self, child_age: int) -> bool:
        """Business rule: duration limits based on child age."""
        if child_age < 5:
            return self.duration_ms <= 60000  # 1 minute max for very young
        elif child_age < 8:
            return self.duration_ms <= 120000  # 2 minutes max
        else:
            return self.duration_ms <= 300000  # 5 minutes max


@dataclass
class Voice:
    """Voice business entity."""
    voice_id: str
    name: str
    language: str
    gender: VoiceGender
    age_group: str
    is_child_appropriate: bool
    supported_emotions: List[VoiceEmotion]
    
    def can_be_used_by_child(self, child_age: int) -> bool:
        """Business rule: voice appropriateness by age."""
        if not self.is_child_appropriate:
            return False
        
        # Age-specific voice rules
        if child_age < 5 and self.age_group not in ["child", "teen"]:
            return False
        
        return True
    
    def supports_emotion(self, emotion: VoiceEmotion) -> bool:
        """Business rule: check emotion support."""
        return emotion in self.supported_emotions


@dataclass
class TranscriptionRequest:
    """Speech-to-text business request."""
    audio: AudioFile
    target_language: str
    child_age: Optional[int]
    require_safety_check: bool = True
    
    def is_valid(self) -> bool:
        """Business validation for transcription."""
        if not self.audio.is_valid_for_processing():
            return False
        
        if self.child_age and not self.audio.is_appropriate_for_child_age(self.child_age):
            return False
        
        return True


@dataclass
class SynthesisRequest:
    """Text-to-speech business request."""
    text: str
    voice: Voice
    emotion: VoiceEmotion
    quality: AudioQuality
    child_age: Optional[int]
    
    def is_valid(self) -> bool:
        """Business validation for synthesis."""
        if not self.text or not self.text.strip():
            return False
        
        if not self.voice.supports_emotion(self.emotion):
            return False
        
        if self.child_age and not self.voice.can_be_used_by_child(self.child_age):
            return False
        
        return True


@dataclass
class ProcessingResult:
    """Generic processing result."""
    success: bool
    data: Optional[bytes]
    text_content: Optional[str]
    processing_time_ms: float
    is_child_safe: bool
    warnings: List[str]
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []