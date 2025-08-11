"""
Whisper STT Provider - Local Implementation
==========================================
Production-ready local Whisper implementation for real-time speech-to-text
with Arabic and English support and minimal latency.
"""

import asyncio
import io
import logging
import time
from typing import Optional, Dict, Any, List

try:
    import whisper
    import torch

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import numpy as np
    import librosa

    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False

from src.interfaces.providers.stt_provider import ISTTProvider, STTResult, STTError


class WhisperSTTProvider(ISTTProvider):
    """
    Local Whisper STT Provider - Zero Latency Implementation
    ======================================================

    Features:
    - Local Whisper model (no API calls)
    - Arabic and English language support
    - Real-time processing with minimal latency
    - Optimized for ESP32 audio streams
    - Automatic language detection
    - Production-ready error handling
    """

    def __init__(
        self,
        model_size: str = "turbo",  # Upgraded to turbo model for optimal speed and accuracy
        device: str = "auto",
        compute_type: str = "float16",  # Optimized for GPU performance
        language: Optional[str] = None,
        enable_vad: bool = True,
        adaptive_model: bool = True,  # Enable adaptive model switching
        target_latency_ms: int = 2000,  # Target latency for model selection
    ):
        """
        Initialize Whisper STT Provider.

        Args:
            model_size: Whisper model size ("tiny", "base", "small", "medium", "large")
            device: Device to use ("cpu", "cuda", "auto")
            compute_type: Computation type for optimization
            language: Fixed language (None for auto-detection)
            enable_vad: Enable Voice Activity Detection
        """
        if not WHISPER_AVAILABLE:
            raise STTError(
                "Whisper not installed. Install with: pip install openai-whisper"
            )

        if not AUDIO_PROCESSING_AVAILABLE:
            raise STTError(
                "Audio processing libraries not available. Install: pip install librosa numpy"
            )

        self.model_size = model_size
        self.language = language
        self.enable_vad = enable_vad
        self.adaptive_model = adaptive_model
        self.target_latency_ms = target_latency_ms
        self._model = None
        self._fallback_model = None  # Smaller model for high-latency scenarios
        self._logger = logging.getLogger(__name__)

        # Determine optimal device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Performance metrics
        self._total_requests = 0
        self._successful_requests = 0
        self._total_processing_time = 0.0
        self._language_detections = {"ar": 0, "en": 0, "other": 0}

    async def _load_model(self) -> whisper.Whisper:
        """Load Whisper model with optimization and fallback."""
        if self._model is None:
            self._logger.info(
                f"Loading Whisper model: {self.model_size} on {self.device}"
            )
            start_time = time.time()

            # Load model in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self._model = await loop.run_in_executor(
                None, lambda: whisper.load_model(self.model_size, device=self.device)
            )

            load_time = time.time() - start_time
            self._logger.info(f"Whisper model loaded in {load_time:.2f}s")

            # Load fallback model if adaptive mode is enabled
            if self.adaptive_model:
                await self._load_fallback_model()

        return self._model

    async def _load_fallback_model(self) -> None:
        """Load smaller fallback model for high-latency scenarios."""
        fallback_size = "tiny" if self.model_size != "tiny" else "base"
        self._logger.info(f"Loading fallback model: {fallback_size}")
        
        try:
            loop = asyncio.get_event_loop()
            self._fallback_model = await loop.run_in_executor(
                None, lambda: whisper.load_model(fallback_size, device=self.device)
            )
            self._logger.info(f"Fallback model {fallback_size} loaded successfully")
        except Exception as e:
            self._logger.warning(f"Failed to load fallback model: {e}")

    def _should_use_fallback(self, recent_latency: float) -> bool:
        """Determine if fallback model should be used based on recent latency."""
        return (
            self.adaptive_model and 
            self._fallback_model is not None and
            recent_latency > self.target_latency_ms
        )

    async def transcribe(
        self, audio_data: bytes, language: Optional[str] = None
    ) -> STTResult:
        """
        Transcribe audio with minimal latency.

        Args:
            audio_data: Raw audio bytes
            language: Language code ("ar", "en", or None for auto-detection)

        Returns:
            STTResult with transcription and metadata
        """
        start_time = time.time()
        self._total_requests += 1

        try:
            # Load model if needed
            model = await self._load_model()

            # Preprocess audio for optimal performance
            audio_array = await self._preprocess_audio(audio_data)

            # Determine language
            target_language = language or self.language

            # Check if we should use fallback model based on recent performance
            avg_latency = self._total_processing_time / max(self._successful_requests, 1) * 1000
            use_fallback = self._should_use_fallback(avg_latency)
            
            if use_fallback:
                self._logger.info(f"Using fallback model due to high latency ({avg_latency:.0f}ms)")
                selected_model = self._fallback_model
            else:
                selected_model = model

            # Transcribe with optimizations
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._transcribe_sync, selected_model, audio_array, target_language
            )

            processing_time = time.time() - start_time
            self._total_processing_time += processing_time
            self._successful_requests += 1

            # Track language detection
            detected_lang = result.get("language", "unknown")
            if detected_lang in self._language_detections:
                self._language_detections[detected_lang] += 1
            else:
                self._language_detections["other"] += 1

            self._logger.info(
                f"Transcription completed in {processing_time:.3f}s, "
                f"language: {detected_lang}, "
                f"confidence: {result.get('avg_logprob', 0):.3f}"
            )

            return STTResult(
                text=result["text"].strip(),
                language=detected_lang,
                confidence=self._calculate_confidence(result),
                processing_time_ms=processing_time * 1000,
                segments=self._extract_segments(result),
                metadata={
                    "model_size": self.model_size,
                    "device": self.device,
                    "avg_logprob": result.get("avg_logprob", 0),
                    "no_speech_prob": result.get("no_speech_prob", 0),
                },
            )

        except Exception as e:
            self._logger.error(f"Transcription failed: {e}", exc_info=True)
            raise STTError(f"Transcription failed: {e}")

    def _transcribe_sync(
        self, model: whisper.Whisper, audio: np.ndarray, language: Optional[str]
    ) -> Dict[str, Any]:
        """Synchronous transcription for executor."""
        options = {
            "task": "transcribe",
            "best_of": 1,  # Optimize for speed
            "beam_size": 1,  # Optimize for speed
            "temperature": 0.0,  # Deterministic output
            "compression_ratio_threshold": 2.4,
            "logprob_threshold": -1.0,
            "no_speech_threshold": 0.6,
        }

        if language:
            options["language"] = language

        return model.transcribe(audio, **options)

    async def _preprocess_audio(self, audio_data: bytes) -> np.ndarray:
        """Preprocess audio for optimal Whisper performance."""
        try:
            # Convert bytes to numpy array
            audio_io = io.BytesIO(audio_data)

            # Load and resample to 16kHz (Whisper's expected sample rate)
            loop = asyncio.get_event_loop()
            audio, sr = await loop.run_in_executor(
                None, lambda: librosa.load(audio_io, sr=16000, mono=True)
            )

            # Apply basic noise reduction if needed
            if self.enable_vad:
                audio = self._apply_vad(audio)

            # Normalize audio
            audio = librosa.util.normalize(audio)

            return audio

        except Exception as e:
            self._logger.error(f"Audio preprocessing failed: {e}")
            raise STTError(f"Audio preprocessing failed: {e}")

    def _apply_vad(self, audio: np.ndarray) -> np.ndarray:
        """Apply simple Voice Activity Detection."""
        # Simple energy-based VAD
        frame_length = 2048
        hop_length = 512

        # Calculate energy for each frame
        energy = librosa.feature.rms(
            y=audio, frame_length=frame_length, hop_length=hop_length
        )[0]

        # Threshold for voice activity (adjust as needed)
        threshold = np.mean(energy) * 0.3

        # Create mask for voice activity
        voice_frames = energy > threshold

        # Expand frame-level decisions to sample-level
        voice_samples = np.repeat(voice_frames, hop_length)
        voice_samples = voice_samples[: len(audio)]

        # Return audio with silence reduced
        if np.any(voice_samples):
            return audio[voice_samples]
        else:
            return audio  # Return original if no voice detected

    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate confidence score from Whisper result."""
        avg_logprob = result.get("avg_logprob", -1.0)
        no_speech_prob = result.get("no_speech_prob", 1.0)

        # Convert log probability to confidence (0-1)
        # Higher avg_logprob and lower no_speech_prob = higher confidence
        confidence = max(0.0, min(1.0, (avg_logprob + 1.0) * (1.0 - no_speech_prob)))

        return confidence

    def _extract_segments(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract segment information for detailed analysis."""
        segments = []

        for segment in result.get("segments", []):
            segments.append(
                {
                    "start": segment.get("start", 0),
                    "end": segment.get("end", 0),
                    "text": segment.get("text", "").strip(),
                    "confidence": self._calculate_confidence(segment),
                }
            )

        return segments

    async def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return ["ar", "en", "auto"]

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check."""
        try:
            # Test model loading
            model = await self._load_model()

            # Create test audio (1 second of silence)
            test_audio = np.zeros(16000, dtype=np.float32)

            # Test transcription
            start_time = time.time()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: model.transcribe(test_audio, language="en", task="transcribe"),
            )
            test_time = time.time() - start_time

            return {
                "status": "healthy",
                "model_size": self.model_size,
                "device": self.device,
                "model_loaded": True,
                "test_transcription_time": test_time,
                "supported_languages": await self.get_supported_languages(),
                "statistics": await self.get_statistics(),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model_loaded": self._model is not None,
            }

    async def get_statistics(self) -> Dict[str, Any]:
        """Get provider statistics."""
        avg_processing_time = self._total_processing_time / max(
            self._successful_requests, 1
        )

        success_rate = (self._successful_requests / max(self._total_requests, 1)) * 100

        return {
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "success_rate": success_rate,
            "average_processing_time_ms": avg_processing_time * 1000,
            "language_detections": self._language_detections.copy(),
            "model_info": {
                "size": self.model_size,
                "device": self.device,
                "loaded": self._model is not None,
            },
        }

    async def optimize_for_realtime(self) -> None:
        """Optimize settings for real-time performance."""
        # Pre-load model to reduce first-request latency
        await self._load_model()

        # Warm up with dummy audio
        dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: self._model.transcribe(dummy_audio, language="en")
            )
            self._logger.info("Whisper model warmed up for real-time performance")
        except Exception as e:
            self._logger.warning(f"Model warm-up failed: {e}")
