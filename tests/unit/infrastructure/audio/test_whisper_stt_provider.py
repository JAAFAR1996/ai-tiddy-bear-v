"""
Tests for Whisper STT Provider.
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, Mock, patch
from io import BytesIO

from src.infrastructure.audio.whisper_stt_provider import WhisperSTTProvider
from src.interfaces.providers.stt_provider import STTResult, STTError


class TestWhisperSTTProvider:
    """Test Whisper STT Provider functionality."""

    @pytest.fixture
    def mock_whisper_available(self):
        """Mock Whisper availability."""
        with patch('src.infrastructure.audio.whisper_stt_provider.WHISPER_AVAILABLE', True):
            with patch('src.infrastructure.audio.whisper_stt_provider.AUDIO_PROCESSING_AVAILABLE', True):
                yield

    @pytest.fixture
    def provider(self, mock_whisper_available):
        """Create Whisper STT provider instance."""
        with patch('src.infrastructure.audio.whisper_stt_provider.whisper') as mock_whisper:
            with patch('src.infrastructure.audio.whisper_stt_provider.torch') as mock_torch:
                mock_torch.cuda.is_available.return_value = False
                provider = WhisperSTTProvider(model_size="base", device="cpu")
                return provider

    def test_initialization_success(self, mock_whisper_available):
        """Test successful provider initialization."""
        with patch('src.infrastructure.audio.whisper_stt_provider.torch') as mock_torch:
            mock_torch.cuda.is_available.return_value = False
            
            provider = WhisperSTTProvider(model_size="base", device="auto")
            
            assert provider.model_size == "base"
            assert provider.device == "cpu"  # Should fallback to CPU
            assert provider.language is None
            assert provider.enable_vad is True

    def test_initialization_cuda_available(self, mock_whisper_available):
        """Test initialization when CUDA is available."""
        with patch('src.infrastructure.audio.whisper_stt_provider.torch') as mock_torch:
            mock_torch.cuda.is_available.return_value = True
            
            provider = WhisperSTTProvider(device="auto")
            
            assert provider.device == "cuda"

    def test_initialization_whisper_not_available(self):
        """Test initialization when Whisper is not available."""
        with patch('src.infrastructure.audio.whisper_stt_provider.WHISPER_AVAILABLE', False):
            with pytest.raises(STTError, match="Whisper not installed"):
                WhisperSTTProvider()

    def test_initialization_audio_processing_not_available(self):
        """Test initialization when audio processing libraries not available."""
        with patch('src.infrastructure.audio.whisper_stt_provider.WHISPER_AVAILABLE', True):
            with patch('src.infrastructure.audio.whisper_stt_provider.AUDIO_PROCESSING_AVAILABLE', False):
                with pytest.raises(STTError, match="Audio processing libraries not available"):
                    WhisperSTTProvider()

    @pytest.mark.asyncio
    async def test_load_model(self, provider):
        """Test model loading."""
        with patch('src.infrastructure.audio.whisper_stt_provider.whisper') as mock_whisper:
            mock_model = Mock()
            mock_whisper.load_model.return_value = mock_model
            
            model = await provider._load_model()
            
            assert model == mock_model
            mock_whisper.load_model.assert_called_once_with("base", device="cpu")

    @pytest.mark.asyncio
    async def test_load_model_cached(self, provider):
        """Test that model is cached after first load."""
        with patch('src.infrastructure.audio.whisper_stt_provider.whisper') as mock_whisper:
            mock_model = Mock()
            mock_whisper.load_model.return_value = mock_model
            
            # First call
            model1 = await provider._load_model()
            # Second call
            model2 = await provider._load_model()
            
            assert model1 == model2
            # Should only be called once due to caching
            mock_whisper.load_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_preprocess_audio(self, provider):
        """Test audio preprocessing."""
        # Create fake audio data
        fake_audio_bytes = b"fake_wav_data"
        
        with patch('src.infrastructure.audio.whisper_stt_provider.librosa') as mock_librosa:
            mock_audio = np.array([0.1, 0.2, 0.3, 0.4])
            mock_librosa.load.return_value = (mock_audio, 16000)
            mock_librosa.util.normalize.return_value = mock_audio
            
            result = await provider._preprocess_audio(fake_audio_bytes)
            
            assert isinstance(result, np.ndarray)
            mock_librosa.load.assert_called_once()
            mock_librosa.util.normalize.assert_called_once()

    def test_apply_vad(self, provider):
        """Test Voice Activity Detection."""
        # Create test audio signal
        audio = np.random.random(16000)  # 1 second of audio
        
        with patch('src.infrastructure.audio.whisper_stt_provider.librosa') as mock_librosa:
            # Mock energy calculation
            mock_energy = np.array([0.1, 0.8, 0.9, 0.2, 0.1])
            mock_librosa.feature.rms.return_value = [mock_energy]
            
            result = provider._apply_vad(audio)
            
            assert isinstance(result, np.ndarray)
            mock_librosa.feature.rms.assert_called_once()

    def test_calculate_confidence(self, provider):
        """Test confidence score calculation."""
        # Test high confidence result
        high_conf_result = {
            "avg_logprob": -0.1,
            "no_speech_prob": 0.1
        }
        confidence = provider._calculate_confidence(high_conf_result)
        assert 0.5 < confidence <= 1.0
        
        # Test low confidence result
        low_conf_result = {
            "avg_logprob": -2.0,
            "no_speech_prob": 0.9
        }
        confidence = provider._calculate_confidence(low_conf_result)
        assert 0.0 <= confidence < 0.5

    def test_extract_segments(self, provider):
        """Test segment extraction from Whisper result."""
        whisper_result = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.5,
                    "text": " Hello world",
                    "avg_logprob": -0.2
                },
                {
                    "start": 2.5,
                    "end": 5.0,
                    "text": " How are you?",
                    "avg_logprob": -0.3
                }
            ]
        }
        
        segments = provider._extract_segments(whisper_result)
        
        assert len(segments) == 2
        assert segments[0]["text"] == "Hello world"
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 2.5
        assert "confidence" in segments[0]

    @pytest.mark.asyncio
    async def test_transcribe_success(self, provider):
        """Test successful transcription."""
        fake_audio_bytes = b"fake_wav_data"
        
        # Mock all dependencies
        with patch.object(provider, '_load_model') as mock_load:
            with patch.object(provider, '_preprocess_audio') as mock_preprocess:
                with patch.object(provider, '_transcribe_sync') as mock_transcribe:
                    
                    mock_model = Mock()
                    mock_load.return_value = mock_model
                    
                    mock_audio = np.array([0.1, 0.2, 0.3])
                    mock_preprocess.return_value = mock_audio
                    
                    mock_result = {
                        "text": "Hello world",
                        "language": "en",
                        "avg_logprob": -0.2,
                        "no_speech_prob": 0.1,
                        "segments": []
                    }
                    mock_transcribe.return_value = mock_result
                    
                    # Mock asyncio.get_event_loop and run_in_executor
                    with patch('asyncio.get_event_loop') as mock_loop:
                        mock_loop_instance = Mock()
                        mock_loop.return_value = mock_loop_instance
                        mock_loop_instance.run_in_executor.return_value = mock_result
                        
                        result = await provider.transcribe(fake_audio_bytes)
                        
                        assert isinstance(result, STTResult)
                        assert result.text == "Hello world"
                        assert result.language == "en"
                        assert result.confidence > 0
                        assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_transcribe_with_language(self, provider):
        """Test transcription with specified language."""
        fake_audio_bytes = b"fake_wav_data"
        
        with patch.object(provider, '_load_model'):
            with patch.object(provider, '_preprocess_audio'):
                with patch.object(provider, '_transcribe_sync') as mock_transcribe:
                    with patch('asyncio.get_event_loop') as mock_loop:
                        
                        mock_result = {
                            "text": "مرحبا بالعالم",
                            "language": "ar",
                            "avg_logprob": -0.3,
                            "no_speech_prob": 0.2,
                            "segments": []
                        }
                        
                        mock_loop_instance = Mock()
                        mock_loop.return_value = mock_loop_instance
                        mock_loop_instance.run_in_executor.return_value = mock_result
                        
                        result = await provider.transcribe(fake_audio_bytes, language="ar")
                        
                        assert result.language == "ar"
                        assert result.text == "مرحبا بالعالم"

    @pytest.mark.asyncio
    async def test_transcribe_error_handling(self, provider):
        """Test transcription error handling."""
        fake_audio_bytes = b"fake_wav_data"
        
        with patch.object(provider, '_load_model', side_effect=Exception("Model load failed")):
            with pytest.raises(STTError, match="Transcription failed"):
                await provider.transcribe(fake_audio_bytes)

    def test_transcribe_sync(self, provider):
        """Test synchronous transcription method."""
        mock_model = Mock()
        mock_audio = np.array([0.1, 0.2, 0.3])
        
        expected_result = {
            "text": "Test transcription",
            "language": "en"
        }
        mock_model.transcribe.return_value = expected_result
        
        result = provider._transcribe_sync(mock_model, mock_audio, "en")
        
        assert result == expected_result
        mock_model.transcribe.assert_called_once()
        
        # Check that options were passed correctly
        call_args = mock_model.transcribe.call_args
        options = call_args[1]  # keyword arguments
        assert options["language"] == "en"
        assert options["task"] == "transcribe"
        assert options["temperature"] == 0.0

    def test_transcribe_sync_no_language(self, provider):
        """Test synchronous transcription without language specification."""
        mock_model = Mock()
        mock_audio = np.array([0.1, 0.2, 0.3])
        
        expected_result = {"text": "Test", "language": "auto"}
        mock_model.transcribe.return_value = expected_result
        
        result = provider._transcribe_sync(mock_model, mock_audio, None)
        
        call_args = mock_model.transcribe.call_args
        options = call_args[1]
        assert "language" not in options  # Should not set language if None

    @pytest.mark.asyncio
    async def test_get_supported_languages(self, provider):
        """Test getting supported languages."""
        languages = await provider.get_supported_languages()
        
        assert isinstance(languages, list)
        assert "ar" in languages
        assert "en" in languages
        assert "auto" in languages

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, provider):
        """Test health check when service is healthy."""
        with patch.object(provider, '_load_model') as mock_load:
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_model = Mock()
                mock_load.return_value = mock_model
                
                mock_loop_instance = Mock()
                mock_loop.return_value = mock_loop_instance
                mock_loop_instance.run_in_executor.return_value = {"text": "test"}
                
                health = await provider.health_check()
                
                assert health["status"] == "healthy"
                assert health["model_size"] == "base"
                assert health["device"] == "cpu"
                assert health["model_loaded"] is True
                assert "test_transcription_time" in health
                assert "supported_languages" in health
                assert "statistics" in health

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, provider):
        """Test health check when service is unhealthy."""
        with patch.object(provider, '_load_model', side_effect=Exception("Model error")):
            health = await provider.health_check()
            
            assert health["status"] == "unhealthy"
            assert "error" in health
            assert health["model_loaded"] is False

    @pytest.mark.asyncio
    async def test_get_statistics(self, provider):
        """Test getting provider statistics."""
        # Simulate some usage
        provider._total_requests = 10
        provider._successful_requests = 8
        provider._total_processing_time = 5.0
        provider._language_detections = {"en": 5, "ar": 3}
        
        stats = await provider.get_statistics()
        
        assert stats["total_requests"] == 10
        assert stats["successful_requests"] == 8
        assert stats["success_rate"] == 80.0
        assert stats["average_processing_time_ms"] == 625.0  # 5000ms / 8 requests
        assert stats["language_detections"]["en"] == 5
        assert stats["language_detections"]["ar"] == 3
        assert "model_info" in stats

    @pytest.mark.asyncio
    async def test_optimize_for_realtime(self, provider):
        """Test real-time optimization."""
        with patch.object(provider, '_load_model') as mock_load:
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_model = Mock()
                mock_load.return_value = mock_model
                
                mock_loop_instance = Mock()
                mock_loop.return_value = mock_loop_instance
                mock_loop_instance.run_in_executor.return_value = {"text": "warmup"}
                
                await provider.optimize_for_realtime()
                
                # Should load model and warm it up
                mock_load.assert_called_once()
                mock_loop_instance.run_in_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_for_realtime_error(self, provider):
        """Test real-time optimization with warmup error."""
        with patch.object(provider, '_load_model') as mock_load:
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_model = Mock()
                mock_load.return_value = mock_model
                
                mock_loop_instance = Mock()
                mock_loop.return_value = mock_loop_instance
                mock_loop_instance.run_in_executor.side_effect = Exception("Warmup failed")
                
                # Should not raise exception, just log warning
                await provider.optimize_for_realtime()
                
                mock_load.assert_called_once()


class TestWhisperSTTProviderEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.fixture
    def provider(self):
        with patch('src.infrastructure.audio.whisper_stt_provider.WHISPER_AVAILABLE', True):
            with patch('src.infrastructure.audio.whisper_stt_provider.AUDIO_PROCESSING_AVAILABLE', True):
                with patch('src.infrastructure.audio.whisper_stt_provider.torch') as mock_torch:
                    mock_torch.cuda.is_available.return_value = False
                    return WhisperSTTProvider()

    @pytest.mark.asyncio
    async def test_preprocess_audio_error(self, provider):
        """Test audio preprocessing error handling."""
        with patch('src.infrastructure.audio.whisper_stt_provider.librosa') as mock_librosa:
            mock_librosa.load.side_effect = Exception("Audio load failed")
            
            with pytest.raises(STTError, match="Audio preprocessing failed"):
                await provider._preprocess_audio(b"invalid_audio")

    def test_apply_vad_empty_audio(self, provider):
        """Test VAD with empty audio."""
        empty_audio = np.array([])
        
        with patch('src.infrastructure.audio.whisper_stt_provider.librosa') as mock_librosa:
            mock_librosa.feature.rms.return_value = [np.array([])]
            
            result = provider._apply_vad(empty_audio)
            
            # Should return original audio if no voice detected
            assert len(result) == 0

    def test_calculate_confidence_missing_fields(self, provider):
        """Test confidence calculation with missing fields."""
        # Test with missing avg_logprob
        result_missing_logprob = {"no_speech_prob": 0.5}
        confidence = provider._calculate_confidence(result_missing_logprob)
        assert 0.0 <= confidence <= 1.0
        
        # Test with missing no_speech_prob
        result_missing_speech = {"avg_logprob": -0.5}
        confidence = provider._calculate_confidence(result_missing_speech)
        assert 0.0 <= confidence <= 1.0

    def test_extract_segments_empty(self, provider):
        """Test segment extraction with empty segments."""
        empty_result = {"segments": []}
        segments = provider._extract_segments(empty_result)
        assert segments == []

    def test_extract_segments_missing_fields(self, provider):
        """Test segment extraction with missing fields."""
        incomplete_result = {
            "segments": [
                {"text": "Hello"},  # Missing start, end, avg_logprob
                {"start": 1.0, "end": 2.0}  # Missing text, avg_logprob
            ]
        }
        
        segments = provider._extract_segments(incomplete_result)
        
        assert len(segments) == 2
        assert segments[0]["text"] == "Hello"
        assert segments[0]["start"] == 0  # Default value
        assert segments[1]["text"] == ""  # Default value