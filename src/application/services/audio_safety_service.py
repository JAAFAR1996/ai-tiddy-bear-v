"""
Audio Safety Service - Single Responsibility
===========================================
Handles all child safety and content filtering.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class SafetyCheckResult:
    """Safety check result."""
    is_safe: bool
    violations: List[str]
    confidence: float
    recommendations: List[str]


class AudioSafetyService:
    """Focused audio safety service."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.unsafe_patterns = [
            "excessive_noise",
            "distorted_speech", 
            "inappropriate_content",
            "adult_conversation",
            "multiple_speakers"
        ]
    
    async def check_audio_safety(self, audio_data: bytes, child_age: Optional[int] = None) -> SafetyCheckResult:
        """Check if audio is safe for children."""
        violations = []
        recommendations = []
        
        # Basic safety checks
        if len(audio_data) == 0:
            violations.append("Empty audio data")
            recommendations.append("Provide valid audio")
        
        # Duration check
        estimated_duration = len(audio_data) / 16
        if estimated_duration > 300000:  # 5 minutes
            violations.append("Audio too long for child attention span")
            recommendations.append("Keep audio under 5 minutes")
        
        # Quality check for child comprehension
        quality_score = self._assess_audio_quality(audio_data)
        if quality_score < 0.5:
            violations.append("Audio quality insufficient for children")
            recommendations.append("Improve audio clarity")
        
        # Age-specific checks
        if child_age and child_age < 5:
            if estimated_duration > 60000:  # 1 minute for very young children
                violations.append("Audio too long for very young children")
                recommendations.append("Keep under 1 minute for children under 5")
        
        is_safe = len(violations) == 0
        confidence = 0.9 if is_safe else 0.3
        
        return SafetyCheckResult(
            is_safe=is_safe,
            violations=violations,
            confidence=confidence,
            recommendations=recommendations
        )
    
    async def check_text_safety(self, text: str) -> SafetyCheckResult:
        """Check if transcribed text is child-safe."""
        violations = []
        recommendations = []
        
        if not text or not text.strip():
            return SafetyCheckResult(True, [], 1.0, [])
        
        # Enhanced text safety with categorized patterns
        unsafe_patterns = {
            "violence": ["fight", "hit", "hurt", "weapon", "gun"],
            "fear": ["scary", "frightening", "monster", "nightmare"],
            "adult_content": ["drug", "alcohol", "cigarette"],
            "inappropriate": ["stupid", "hate", "ugly"]
        }
        
        text_lower = text.lower()
        for category, words in unsafe_patterns.items():
            for word in words:
                if word in text_lower:
                    violations.append(f"Contains {category}: {word}")
                    recommendations.append(f"Replace {category} content")
                    break
        
        is_safe = len(violations) == 0
        confidence = 0.95 if is_safe else 0.2
        
        return SafetyCheckResult(
            is_safe=is_safe,
            violations=violations,
            confidence=confidence,
            recommendations=recommendations
        )
    
    async def filter_content(self, content: str) -> str:
        """Filter inappropriate content from text."""
        if not content:
            return content
        
        # Enhanced content filtering
        unsafe_words = ["scary", "frightening", "violence", "weapon", "fight", "hurt", "monster"]
        filtered = content
        
        for word in unsafe_words:
            filtered = filtered.replace(word, "[filtered]")
            filtered = filtered.replace(word.capitalize(), "[filtered]")
        
        return filtered
    
    def _assess_audio_quality(self, audio_data: bytes) -> float:
        """Assess audio quality for child comprehension."""
        if len(audio_data) < 1000:
            return 0.1  # Too short
        
        # Simplified quality assessment
        return 0.7  # Would use actual audio analysis in production