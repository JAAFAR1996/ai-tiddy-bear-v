"""
Tests for Audio Validation Service
==================================

Tests for audio validation and quality checks.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from src.application.services.audio_validation_service import (
    AudioValidationService,
    ValidationResult
)
from src.shared.audio_types import AudioFormat


class TestAudioValidationService:
    """Test audio validation service."""

    @pytest.fixture
    def service(self):
        """Create audio validation service."""
        return AudioValidationService()

    @pytest.fixture
    def valid_wav_data(self):
        """Create valid WAV audio data."""
        # WAV header + some audio data
        header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00'
        audio_data = np.random.randint(-1000, 1000, 1000, dtype=np.int16).tobytes()
        return header + audio_data

    @pytest.fixture
    def valid_mp3_data(self):
        """Create valid MP3 audio data."""
        # MP3 header + some data
        header = b'\xff\xfb\x90\x00'
        audio_data = b'\x00' * 2000
        return header + audio_data

    def test_initialization(self, service):
        """Test service initialization."""
        assert service.MAX_SIZE_MB == 50
        assert service.MIN_DURATION_MS == 100
        assert service.MAX_DURATION_MS == 300000
        assert service.MIN_QUALITY == 0.3

    @pytest.mark.asyncio
    async def test_validate_empty_audio(self, service):
        """Test validation of empty audio."""
        result = await service.validate_audio(b"")
        
        assert result.is_valid is False
        assert "Empty audio data" in result.issues

    @pytest.mark.asyncio
    async def test_validate_valid_wav_audio(self, service, valid_wav_data):
        """Test validation of valid WAV audio."""
        result = await service.validate_audio(valid_wav_data)
        
        assert result.format == AudioFormat.WAV
        assert result.duration_ms > 0
        assert result.quality_score >= 0

    @pytest.mark.asyncio
    async def test_validate_valid_mp3_audio(self, service, valid_mp3_data):
        """Test validation of valid MP3 audio."""
        result = await service.validate_audio(valid_mp3_data)
        
        assert result.format == AudioFormat.MP3

    @pytest.mark.asyncio
    async def test_validate_oversized_audio(self, service):
        """Test validation of oversized audio."""
        # Create audio larger than 50MB
        large_audio = b'\x00' * (60 * 1024 * 1024)
        
        result = await service.validate_audio(large_audio)
        
        assert result.is_valid is False
        assert any("too large" in issue for issue in result.issues)

    @pytest.mark.asyncio
    async def test_validate_unsupported_format(self, service):
        """Test validation of unsupported format."""
        unsupported_data = b"UNSUPPORTED_FORMAT" + b'\x00' * 1000
        
        result = await service.validate_audio(unsupported_data)
        
        assert result.is_valid is False
        assert "Unsupported audio format" in result.issues

    def test_detect_wav_format(self, service):
        """Test WAV format detection."""
        wav_data = b'RIFF\x24\x08\x00\x00WAVEfmt '
        
        format_detected = service._detect_format(wav_data)
        
        assert format_detected == AudioFormat.WAV

    def test_detect_mp3_format(self, service):
        """Test MP3 format detection."""
        mp3_data = b'\xff\xfb\x90\x00'
        
        format_detected = service._detect_format(mp3_data)
        
        assert format_detected == AudioFormat.MP3

    def test_detect_ogg_format(self, service):
        """Test OGG format detection."""
        ogg_data = b'OggS\x00\x02'
        
        format_detected = service._detect_format(ogg_data)
        
        assert format_detected == AudioFormat.OGG

    def test_detect_flac_format(self, service):
        """Test FLAC format detection."""
        flac_data = b'fLaC\x00\x00'
        
        format_detected = service._detect_format(flac_data)
        
        assert format_detected == AudioFormat.FLAC

    def test_detect_unknown_format(self, service):
        """Test unknown format detection."""
        unknown_data = b'UNKNOWN\x00\x00'
        
        format_detected = service._detect_format(unknown_data)
        
        assert format_detected is None

    def test_estimate_duration(self, service):
        """Test duration estimation."""
        audio_data = b'\x00' * 1600  # 1600 bytes
        
        duration = service._estimate_duration(audio_data)
        
        assert duration == 100.0  # 1600 / 16

    @patch('numpy.frombuffer')
    @patch('numpy.mean')
    @patch('numpy.percentile')
    @patch('numpy.log10')
    def test_calculate_quality_with_numpy(self, mock_log10, mock_percentile, 
                                         mock_mean, mock_frombuffer, service):
        """Test quality calculation with numpy."""
        # Setup mocks
        mock_audio = np.array([100, -100, 200, -200], dtype=np.int16)
        mock_frombuffer.return_value = mock_audio
        mock_mean.return_value = 25000  # Signal power
        mock_percentile.return_value = 50  # Noise floor
        mock_log10.return_value = 2.0
        
        audio_data = b'\x00' * 100
        quality = service._calculate_quality(audio_data)
        
        assert quality >= 0.0
        assert quality <= 1.0
        mock_frombuffer.assert_called_once()

    def test_calculate_quality_without_numpy(self, service):
        """Test quality calculation fallback without numpy."""
        with patch('builtins.__import__', side_effect=ImportError):
            quality = service._calculate_quality(b'\x00' * 100)
            
            assert quality == 0.7  # Fallback value

    def test_calculate_quality_with_exception(self, service):
        """Test quality calculation with exception."""
        with patch('numpy.frombuffer', side_effect=Exception("Test error")):
            quality = service._calculate_quality(b'\x00' * 100)
            
            assert quality == 0.3  # Error fallback

    @patch('numpy.frombuffer')
    @patch('numpy.max')
    @patch('numpy.abs')
    def test_check_child_safety_safe_audio(self, mock_abs, mock_max, 
                                          mock_frombuffer, service):
        """Test child safety check for safe audio."""
        mock_audio = np.array([100, -100, 200, -200], dtype=np.int16)
        mock_frombuffer.return_value = mock_audio
        mock_abs.return_value = np.abs(mock_audio)
        mock_max.return_value = 200  # Safe amplitude
        
        is_safe = service._check_child_safety(b'\x00' * 100, 0.5)
        
        assert is_safe is True

    @patch('numpy.frombuffer')
    @patch('numpy.max')
    @patch('numpy.abs')
    def test_check_child_safety_too_loud(self, mock_abs, mock_max, 
                                        mock_frombuffer, service):
        """Test child safety check for too loud audio."""
        mock_audio = np.array([30000, -30000], dtype=np.int16)
        mock_frombuffer.return_value = mock_audio
        mock_abs.return_value = np.abs(mock_audio)
        mock_max.return_value = 30000  # Too loud
        
        is_safe = service._check_child_safety(b'\x00' * 100, 0.5)
        
        assert is_safe is False

    def test_check_child_safety_low_quality(self, service):
        """Test child safety check with low quality."""
        is_safe = service._check_child_safety(b'\x00' * 100, 0.1)  # Below threshold
        
        assert is_safe is False

    def test_check_child_safety_exception_handling(self, service):
        """Test child safety check exception handling."""
        with patch('numpy.frombuffer', side_effect=Exception("Test error")):
            is_safe = service._check_child_safety(b'\x00' * 100, 0.5)
            
            # Should fall back to quality check
            assert is_safe is True  # Quality >= MIN_QUALITY

    @pytest.mark.asyncio
    async def test_validate_audio_too_short(self, service):
        """Test validation of too short audio."""
        short_audio = b'RIFF\x24\x08\x00\x00WAVEfmt ' + b'\x00' * 10
        
        result = await service.validate_audio(short_audio)
        
        assert result.is_valid is False
        assert "Audio too short" in result.issues

    @pytest.mark.asyncio
    async def test_validate_audio_too_long(self, service):
        """Test validation of too long audio."""
        # Create audio that would be estimated as too long
        long_audio = b'RIFF\x24\x08\x00\x00WAVEfmt ' + b'\x00' * (400000 * 16)
        
        result = await service.validate_audio(long_audio)
        
        assert result.is_valid is False
        assert "Audio too long" in result.issues

    @pytest.mark.asyncio
    async def test_validate_audio_poor_quality(self, service):
        """Test validation of poor quality audio."""
        with patch.object(service, '_calculate_quality', return_value=0.1):
            audio_data = b'RIFF\x24\x08\x00\x00WAVEfmt ' + b'\x00' * 1000
            
            result = await service.validate_audio(audio_data)
            
            assert result.is_valid is False
            assert "Audio quality insufficient" in result.issues

    @pytest.mark.asyncio
    async def test_validate_audio_not_child_safe(self, service):
        """Test validation of non-child-safe audio."""
        with patch.object(service, '_check_child_safety', return_value=False):
            audio_data = b'RIFF\x24\x08\x00\x00WAVEfmt ' + b'\x00' * 1000
            
            result = await service.validate_audio(audio_data)
            
            assert result.is_valid is False
            assert "Not child-appropriate" in result.issues

    @pytest.mark.asyncio
    async def test_validation_result_structure(self, service, valid_wav_data):
        """Test validation result structure."""
        result = await service.validate_audio(valid_wav_data)
        
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'format')
        assert hasattr(result, 'duration_ms')
        assert hasattr(result, 'quality_score')
        assert hasattr(result, 'is_child_safe')
        assert hasattr(result, 'issues')
        assert isinstance(result.issues, list)

    def test_custom_logger(self):
        """Test service with custom logger."""
        mock_logger = Mock()
        service = AudioValidationService(logger=mock_logger)
        
        assert service.logger == mock_logger