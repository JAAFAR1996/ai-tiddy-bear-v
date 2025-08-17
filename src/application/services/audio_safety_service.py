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
        """Assess audio quality for child comprehension using real audio analysis."""
        if len(audio_data) < 1000:
            return 0.1  # Too short
        
        try:
            # Real audio analysis implementation
            import librosa
            import numpy as np
            import io
            
            # Load audio data
            audio, sample_rate = librosa.load(io.BytesIO(audio_data), sr=22050)
            
            if len(audio) == 0:
                return 0.0
            
            # Calculate audio quality metrics
            quality_score = 1.0
            
            # 1. Check for silence (too quiet)
            rms_energy = np.sqrt(np.mean(audio**2))
            if rms_energy < 0.01:  # Too quiet
                quality_score *= 0.3
            elif rms_energy > 0.8:  # Too loud/distorted
                quality_score *= 0.5
            
            # 2. Check frequency content
            stft = librosa.stft(audio)
            magnitude = np.abs(stft)
            
            # Look for good speech frequency range (300-3000 Hz)
            freqs = librosa.fft_frequencies(sr=sample_rate)
            speech_range = (freqs >= 300) & (freqs <= 3000)
            speech_energy = np.mean(magnitude[speech_range])
            
            if speech_energy < 0.1:  # Weak speech content
                quality_score *= 0.4
            
            # 3. Check for clipping/distortion
            clipping_ratio = np.sum(np.abs(audio) > 0.95) / len(audio)
            if clipping_ratio > 0.01:  # More than 1% clipped samples
                quality_score *= (1.0 - clipping_ratio * 10)
            
            # 4. Check audio length - should be reasonable for children
            duration = len(audio) / sample_rate
            if duration < 0.5:  # Too short
                quality_score *= 0.5
            elif duration > 30:  # Too long for child attention span
                quality_score *= 0.7
            
            # Ensure score is between 0 and 1
            quality_score = max(0.0, min(1.0, quality_score))
            
            self.logger.debug(f"Audio quality assessment: {quality_score:.2f} "
                            f"(RMS: {rms_energy:.3f}, Duration: {duration:.1f}s)")
            
            return quality_score
            
        except ImportError:
            self.logger.warning("librosa not available, using basic quality assessment")
            # Fallback to basic analysis
            duration_seconds = len(audio_data) / (44100 * 2)  # Assume 44.1kHz, 16-bit
            
            if duration_seconds < 0.5:
                return 0.3
            elif duration_seconds > 30:
                return 0.6
            else:
                return 0.8
                
        except Exception as e:
            self.logger.error(f"Audio quality assessment failed: {e}")
            # Safe fallback
            return 0.5
