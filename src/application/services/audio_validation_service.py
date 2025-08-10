"""
Audio Validation Service - Single Responsibility
===============================================
Handles all audio validation logic separately from processing.
"""

import logging
from typing import Optional
from dataclasses import dataclass
from src.shared.audio_types import AudioFormat, AudioProcessingError


@dataclass
class ValidationResult:
    """Simple validation result."""
    is_valid: bool
    format: Optional[AudioFormat]
    duration_ms: float
    quality_score: float
    is_child_safe: bool
    issues: list[str]


class AudioValidationService:
    """Focused audio validation service."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.MAX_SIZE_MB = 50
        self.MIN_DURATION_MS = 100
        self.MAX_DURATION_MS = 300000
        self.MIN_QUALITY = 0.3
    
    async def validate_audio(self, audio_data: bytes) -> ValidationResult:
        """Validate audio data comprehensively."""
        issues = []
        
        # Basic checks
        if not audio_data or len(audio_data) == 0:
            return ValidationResult(False, None, 0, 0, False, ["Empty audio data"])
        
        # Size check
        size_mb = len(audio_data) / (1024 * 1024)
        if size_mb > self.MAX_SIZE_MB:
            issues.append(f"File too large: {size_mb:.1f}MB")
        
        # Format detection
        audio_format = self._detect_format(audio_data)
        if not audio_format:
            issues.append("Unsupported audio format")
        
        # Duration estimation
        duration_ms = self._estimate_duration(audio_data)
        if duration_ms < self.MIN_DURATION_MS:
            issues.append("Audio too short")
        elif duration_ms > self.MAX_DURATION_MS:
            issues.append("Audio too long")
        
        # Quality check
        quality_score = self._calculate_quality(audio_data)
        if quality_score < self.MIN_QUALITY:
            issues.append("Audio quality insufficient")
        
        # Child safety
        is_child_safe = self._check_child_safety(audio_data, quality_score)
        if not is_child_safe:
            issues.append("Not child-appropriate")
        
        is_valid = len(issues) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            format=audio_format,
            duration_ms=duration_ms,
            quality_score=quality_score,
            is_child_safe=is_child_safe,
            issues=issues
        )
    
    def _detect_format(self, audio_data: bytes) -> Optional[AudioFormat]:
        """Detect audio format from data."""
        if audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:12]:
            return AudioFormat.WAV
        elif audio_data.startswith(b'ID3') or audio_data.startswith(b'\\xff\\xfb'):
            return AudioFormat.MP3
        elif audio_data.startswith(b'OggS'):
            return AudioFormat.OGG
        elif audio_data.startswith(b'fLaC'):
            return AudioFormat.FLAC
        return None
    
    def _estimate_duration(self, audio_data: bytes) -> float:
        """Estimate audio duration."""
        return len(audio_data) / 16  # Rough estimate
    
    def _calculate_quality(self, audio_data: bytes) -> float:
        """Calculate audio quality score using actual analysis."""
        try:
            import numpy as np
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_np) == 0:
                return 0.0
            
            # SNR calculation
            signal_power = np.mean(audio_np ** 2)
            noise_floor = np.percentile(np.abs(audio_np), 10)
            snr = signal_power / max(noise_floor ** 2, 1e-10)
            
            # Quality score (0.0 to 1.0)
            quality_score = min(1.0, np.log10(snr + 1) * 0.4)
            return max(0.0, quality_score)
            
        except ImportError:
            return 0.7  # Fallback
        except Exception:
            return 0.3
    
    def _check_child_safety(self, audio_data: bytes, quality: float) -> bool:
        """Check if audio is child-safe with volume analysis."""
        try:
            if quality < self.MIN_QUALITY:
                return False
            
            import numpy as np
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_np) > 0:
                max_amplitude = np.max(np.abs(audio_np))
                if max_amplitude > 25000:  # Too loud
                    return False
            
            return True
        except Exception:
            return quality >= self.MIN_QUALITY
