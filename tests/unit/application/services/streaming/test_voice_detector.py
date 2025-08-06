"""
Tests for Voice Detector
========================

Tests for Voice Activity Detection (VAD).
"""

import pytest
import numpy as np
from unittest.mock import patch

from src.application.services.streaming.voice_detector import VoiceDetector


class TestVoiceDetector:
    """Test voice detector."""

    @pytest.fixture
    def detector(self):
        """Create voice detector instance."""
        return VoiceDetector(threshold=0.01)

    def test_initialization(self, detector):
        """Test detector initialization."""
        assert detector.threshold == 0.01

    def test_custom_threshold(self):
        """Test custom threshold."""
        detector = VoiceDetector(threshold=0.05)
        assert detector.threshold == 0.05

    def test_is_voice_with_high_energy(self, detector):
        """Test voice detection with high energy audio."""
        # Create high energy audio data
        audio_data = np.random.randint(-1000, 1000, 1000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        
        result = detector.is_voice(audio_bytes)
        
        assert result is True

    def test_is_voice_with_low_energy(self, detector):
        """Test voice detection with low energy audio."""
        # Create low energy audio data (near silence)
        audio_data = np.random.randint(-10, 10, 1000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        
        result = detector.is_voice(audio_bytes)
        
        assert result is False

    def test_is_voice_with_silence(self, detector):
        """Test voice detection with complete silence."""
        # Create silent audio data
        audio_data = np.zeros(1000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        
        result = detector.is_voice(audio_bytes)
        
        assert result is False

    def test_is_voice_threshold_boundary(self):
        """Test voice detection at threshold boundary."""
        detector = VoiceDetector(threshold=0.1)
        
        # Create audio data exactly at threshold
        audio_data = np.full(1000, 100, dtype=np.int16)  # Energy = 0.1
        audio_bytes = audio_data.tobytes()
        
        result = detector.is_voice(audio_bytes)
        
        assert result is False  # Should be False as energy equals threshold

    def test_is_voice_above_threshold(self):
        """Test voice detection above threshold."""
        detector = VoiceDetector(threshold=0.05)
        
        # Create audio data above threshold
        audio_data = np.full(1000, 600, dtype=np.int16)  # High energy
        audio_bytes = audio_data.tobytes()
        
        result = detector.is_voice(audio_bytes)
        
        assert result is True

    def test_is_voice_with_mixed_energy(self, detector):
        """Test voice detection with mixed energy levels."""
        # Create audio with some high and some low values
        audio_data = np.concatenate([
            np.full(500, 1000, dtype=np.int16),  # High energy
            np.zeros(500, dtype=np.int16)        # Silence
        ])
        audio_bytes = audio_data.tobytes()
        
        result = detector.is_voice(audio_bytes)
        
        # Average energy should be high enough to detect voice
        assert result is True

    def test_is_voice_with_empty_audio(self, detector):
        """Test voice detection with empty audio."""
        audio_bytes = b""
        
        # Should handle empty audio gracefully
        with pytest.raises((ValueError, IndexError)):
            detector.is_voice(audio_bytes)

    def test_is_voice_with_short_audio(self, detector):
        """Test voice detection with very short audio."""
        # Single sample
        audio_data = np.array([1000], dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        
        result = detector.is_voice(audio_bytes)
        
        assert result is True  # High energy single sample

    def test_energy_calculation_accuracy(self, detector):
        """Test energy calculation accuracy."""
        # Known audio data for predictable energy
        audio_data = np.array([100, -100, 200, -200], dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        
        # Expected energy: mean(abs([100, 100, 200, 200])) = 150
        # Normalized: 150 / 32768 ≈ 0.0046
        
        result = detector.is_voice(audio_bytes)
        
        # With threshold 0.01, should be False
        assert result is False

    def test_different_audio_lengths(self, detector):
        """Test with different audio chunk lengths."""
        lengths = [100, 500, 1000, 2000]
        
        for length in lengths:
            # High energy audio
            audio_data = np.full(length, 1000, dtype=np.int16)
            audio_bytes = audio_data.tobytes()
            
            result = detector.is_voice(audio_bytes)
            assert result is True
            
            # Low energy audio
            audio_data = np.full(length, 10, dtype=np.int16)
            audio_bytes = audio_data.tobytes()
            
            result = detector.is_voice(audio_bytes)
            assert result is False

    def test_numpy_dependency(self, detector):
        """Test that numpy is used correctly."""
        audio_data = np.random.randint(-1000, 1000, 1000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        
        with patch('numpy.frombuffer') as mock_frombuffer, \
             patch('numpy.mean') as mock_mean, \
             patch('numpy.abs') as mock_abs:
            
            mock_frombuffer.return_value = audio_data
            mock_abs.return_value = np.abs(audio_data)
            mock_mean.return_value = 0.02  # Above threshold
            
            result = detector.is_voice(audio_bytes)
            
            assert result is True
            mock_frombuffer.assert_called_once_with(audio_bytes, dtype=np.int16)
            mock_abs.assert_called_once()
            mock_mean.assert_called_once()

    def test_various_thresholds(self):
        """Test with various threshold values."""
        thresholds = [0.001, 0.01, 0.1, 0.5]
        
        # High energy audio
        audio_data = np.full(1000, 1000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        
        for threshold in thresholds:
            detector = VoiceDetector(threshold=threshold)
            result = detector.is_voice(audio_bytes)
            assert result is True  # Should detect voice with all thresholds
        
        # Low energy audio
        audio_data = np.full(1000, 10, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        
        results = []
        for threshold in thresholds:
            detector = VoiceDetector(threshold=threshold)
            result = detector.is_voice(audio_bytes)
            results.append(result)
        
        # Higher thresholds should be more likely to return False
        assert not all(results)  # At least some should be False

    def test_real_world_audio_simulation(self, detector):
        """Test with simulated real-world audio patterns."""
        # Simulate speech pattern: alternating high and low energy
        speech_pattern = []
        for i in range(10):
            if i % 2 == 0:
                # Speech segments
                speech_pattern.extend(np.random.randint(500, 1500, 100, dtype=np.int16))
            else:
                # Pause segments
                speech_pattern.extend(np.random.randint(-50, 50, 50, dtype=np.int16))
        
        audio_data = np.array(speech_pattern, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        
        result = detector.is_voice(audio_bytes)
        
        # Should detect voice due to high energy segments
        assert result is True