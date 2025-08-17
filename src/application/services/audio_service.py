"""
Audio Service - Coordinator with Unified TTS Integration
========================================================
Coordinates between validation, streaming, safety services, and unified TTS.
Includes production-ready TTS caching for performance optimization.
"""

import logging
import hashlib
import time
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, AsyncIterable, Tuple, Union
from dataclasses import dataclass

from src.interfaces.services import IAudioService
from src.interfaces.providers.tts_provider import (
    ITTSService,
    TTSRequest,
    TTSResult,
    VoiceProfile,
    TTSConfiguration,
    ChildSafetyContext,
    TTSError,
    TTSProviderError,
    TTSConfigurationError,
)
from src.shared.audio_types import AudioFormat, AudioQuality, VoiceEmotion, VoiceGender
from src.application.services.audio_validation_service import AudioValidationService
from src.application.services.audio_streaming_service import AudioStreamingService
from src.application.services.audio_safety_service import AudioSafetyService
from src.shared.audio_types import AudioProcessingError
from src.infrastructure.caching.production_tts_cache_service import (
    ProductionTTSCacheService,
)


@dataclass
class TTSMetrics:
    """
    TTS Performance Metrics for Production Monitoring
    =================================================
    Comprehensive metrics for monitoring TTS service performance,
    costs, safety, and user satisfaction.
    """

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cache_hit_rate: float = 0.0
    average_response_time: float = 0.0
    error_rate: float = 0.0
    safety_violations: int = 0
    total_characters_processed: int = 0
    estimated_cost_usd: float = 0.0
    provider_errors: Dict[str, int] = None
    cache_stats: Dict[str, Any] = None

    def __post_init__(self):
        if self.provider_errors is None:
            self.provider_errors = {}
        if self.cache_stats is None:
            self.cache_stats = {}

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def average_cost_per_request(self) -> float:
        """Calculate average cost per request."""
        if self.total_requests == 0:
            return 0.0
        return self.estimated_cost_usd / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "cache_hit_rate": self.cache_hit_rate,
            "average_response_time_ms": self.average_response_time,
            "error_rate": self.error_rate,
            "safety_violations": self.safety_violations,
            "total_characters_processed": self.total_characters_processed,
            "estimated_cost_usd": self.estimated_cost_usd,
            "average_cost_per_request": self.average_cost_per_request,
            "provider_errors": self.provider_errors,
            "cache_stats": self.cache_stats,
        }


class TTSCacheService:
    """
    Production-ready TTS Caching Service
    ====================================

    High-performance caching for TTS responses to minimize provider costs
    and reduce latency. Includes cache invalidation, size limits, and TTL.
    """

    def __init__(
        self, enabled: bool = True, ttl_seconds: int = 3600, max_cache_size: int = 1000
    ):
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, Tuple[TTSResult, datetime]] = {}
        self._logger = logging.getLogger(__name__)

        if self.enabled:
            self._safe_log(
                "TTS cache initialized",
                {"ttl_seconds": ttl_seconds, "max_size": max_cache_size},
            )

    def _safe_log(self, message: str, extra: dict = None, level: str = "info") -> None:
        """Sanitize cache log messages."""
        safe_message = str(message).replace("\n", "\\n").replace("\r", "\\r")
        if len(safe_message) > 500:
            safe_message = safe_message[:497] + "..."

        log_method = getattr(self._logger, level.lower(), self._logger.info)
        if extra:
            log_method(safe_message, extra=extra)
        else:
            log_method(safe_message)

    async def get(self, cache_key: str) -> Optional[TTSResult]:
        """Get cached TTS result if valid."""
        if not self.enabled:
            return None

        if cache_key not in self._cache:
            return None

        result, cached_at = self._cache[cache_key]

        # Check if expired (using UTC timezone)
        now_utc = datetime.now(timezone.utc)
        if now_utc - cached_at > timedelta(seconds=self.ttl_seconds):
            del self._cache[cache_key]
            self._safe_log(f"Cache expired for key: {cache_key[:16]}...", level="debug")
            return None

        # Mark as cached
        result.cached = True
        self._safe_log(f"Cache hit for key: {cache_key[:16]}...", level="debug")
        return result

    async def set(self, cache_key: str, result: TTSResult) -> None:
        """Cache TTS result with TTL."""
        if not self.enabled:
            return

        # Enforce cache size limit
        if len(self._cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
            self._safe_log(
                "Cache size limit reached, removed oldest entry", level="debug"
            )

        self._cache[cache_key] = (result, datetime.now(timezone.utc))
        self._safe_log(f"Cached result for key: {cache_key[:16]}...", level="debug")

    async def invalidate(self, cache_key: str) -> None:
        """Invalidate specific cache entry."""
        if cache_key in self._cache:
            del self._cache[cache_key]

    async def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._safe_log("TTS cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "enabled": self.enabled,
            "size": len(self._cache),
            "max_size": self.max_cache_size,
            "ttl_seconds": self.ttl_seconds,
        }


class AudioService(IAudioService):
    """
    Audio Service - Unified TTS Coordinator
    =======================================
    Orchestrates validation, streaming, safety services, and unified TTS.
    Includes production-ready caching and comprehensive error handling.
    """

    def __init__(
        self,
        stt_provider,
        tts_service: ITTSService,
        validation_service: AudioValidationService,
        streaming_service: AudioStreamingService,
        safety_service: AudioSafetyService,
        cache_service: Optional[ProductionTTSCacheService] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize with injected services - NO internal creation.

        Args:
            stt_provider: Speech-to-text provider
            tts_service: Unified TTS service (ITTSService)
            validation_service: Injected validation service
            streaming_service: Injected streaming service
            safety_service: Injected safety service
            cache_service: Optional Production TTS caching service
            logger: Logger instance
        """
        self.stt_provider = stt_provider
        self.tts_service = tts_service  # Updated to unified interface
        self.validation_service = validation_service
        self.streaming_service = streaming_service
        self.safety_service = safety_service
        self.cache_service = (
            cache_service  # Production cache service injected externally
        )
        self.logger = logger or logging.getLogger(__name__)

        # TTS Metrics for production monitoring
        self._metrics = TTSMetrics()
        self._response_times = []  # Track response times for average calculation

        # Simple metrics - no complex logic
        self._request_count = 0
        self._success_count = 0
        self._tts_request_count = 0
        self._cache_hits = 0

        self._safe_log("Audio Service initialized with unified TTS interface")

    def _safe_log(self, message: str, level: str = "info", **kwargs) -> None:
        """
        Sanitize log messages to prevent injection attacks.

        Args:
            message: Log message to sanitize
            level: Log level (info, debug, warning, error)
            **kwargs: Additional log parameters
        """
        # Sanitize message by removing/escaping dangerous characters
        safe_message = str(message).replace("\n", "\\n").replace("\r", "\\r")
        safe_message = safe_message.replace("\t", "\\t").replace("\0", "\\x00")

        # Limit message length to prevent log flooding
        if len(safe_message) > 1000:
            safe_message = safe_message[:997] + "..."

        # Choose appropriate log level
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(safe_message, **kwargs)

    async def process_audio(self, audio_stream: AsyncIterable[bytes]) -> Dict[str, Any]:
        """
        Coordinate audio processing through injected services.
        Pure orchestration - no business logic.
        """
        start_time = datetime.now(timezone.utc)
        self._request_count += 1

        try:
            # Step 1: Stream processing
            audio_data = await self.streaming_service.process_stream(audio_stream)

            # Step 2: Validation
            validation_result = await self.validation_service.validate_audio(audio_data)
            if not validation_result.is_valid:
                raise AudioProcessingError(
                    f"Validation failed: {validation_result.issues}"
                )

            # Step 3: Safety check
            safety_result = await self.safety_service.check_audio_safety(audio_data)
            if not safety_result.is_safe:
                raise AudioProcessingError(
                    f"Safety check failed: {safety_result.violations}"
                )

            # Step 4: STT processing with Whisper
            stt_result = await self.stt_provider.transcribe(audio_data)
            text = stt_result.text if hasattr(stt_result, "text") else stt_result

            # Step 5: Text safety check
            text_safety = await self.safety_service.check_text_safety(text)
            if not text_safety.is_safe:
                text = await self.safety_service.filter_content(text)

            # Step 6: TTS processing using unified interface
            child_age = (
                safety_result.child_age if hasattr(safety_result, "child_age") else None
            )
            tts_audio = await self._convert_text_to_speech_unified(
                text, child_age=child_age
            )

            # Step 7: Return coordinated result
            processing_time = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self._success_count += 1

            return {
                "success": True,
                "text": text,
                "tts_audio": (
                    tts_audio.audio_data
                    if isinstance(tts_audio, TTSResult)
                    else tts_audio
                ),
                "processing_time_ms": processing_time,
                "child_safe": safety_result.is_safe and text_safety.is_safe,
                "warnings": (
                    safety_result.recommendations + text_safety.recommendations
                ),
                "tts_metadata": {
                    "provider": (
                        tts_audio.provider_name
                        if isinstance(tts_audio, TTSResult)
                        else "unknown"
                    ),
                    "cached": (
                        tts_audio.cached if isinstance(tts_audio, TTSResult) else False
                    ),
                    "duration_seconds": (
                        tts_audio.duration_seconds
                        if isinstance(tts_audio, TTSResult)
                        else None
                    ),
                },
            }

        except Exception as e:
            self._safe_log(f"Audio processing coordination failed: {e}", "error")
            raise AudioProcessingError(f"Processing failed: {e}")

    async def process_stream(
        self, audio_stream: AsyncIterable[bytes]
    ) -> Tuple[str, bytes]:
        """Delegate stream processing to streaming service."""
        try:
            audio_data = await self.streaming_service.process_stream(audio_stream)
            stt_result = await self.stt_provider.transcribe(audio_data)
            text = stt_result.text if hasattr(stt_result, "text") else stt_result
            tts_result = await self._convert_text_to_speech_unified(text)
            return text, (
                tts_result.audio_data
                if isinstance(tts_result, TTSResult)
                else tts_result
            )
        except Exception as e:
            raise AudioProcessingError(f"Stream processing failed: {e}")

    async def convert_text_to_speech(
        self, text: str, voice_settings: Dict[str, Any] = None
    ) -> bytes:
        """Convert text to speech using unified TTS interface."""
        try:
            result = await self._convert_text_to_speech_unified(text, voice_settings)
            return result.audio_data if isinstance(result, TTSResult) else result
        except TTSConfigurationError as e:
            self._safe_log(f"TTS configuration failed: {e}", "error")
            raise AudioProcessingError(f"TTS configuration failed: {e}")
        except TTSProviderError as e:
            self._safe_log(f"TTS provider failed: {e}", "error")
            raise AudioProcessingError(f"TTS provider failed: {e}")
        except Exception as e:
            self._safe_log(f"TTS conversion failed: {e}", "error")
            raise AudioProcessingError(f"TTS conversion failed: {e}")

    async def convert_speech_to_text(self, audio_data: bytes) -> str:
        """Delegate STT to provider with Whisper support."""
        stt_result = await self.stt_provider.transcribe(audio_data)
        return stt_result.text if hasattr(stt_result, "text") else stt_result

    async def _convert_text_to_speech_unified(
        self,
        text: str,
        voice_settings: Dict[str, Any] = None,
        child_age: Optional[int] = None,
    ) -> TTSResult:
        """
        Convert text to speech using unified TTS interface with caching.

        Args:
            text: Text to convert to speech
            voice_settings: Optional voice configuration
            child_age: Optional child age for safety context

        Returns:
            TTSResult with audio data and metadata
        """
        self._tts_request_count += 1
        request_start_time = datetime.now(timezone.utc)

        # Update metrics
        self._metrics.total_requests += 1
        self._metrics.total_characters_processed += len(text)

        try:
            # Create default voice profile
            default_voice = VoiceProfile(
                voice_id=(
                    voice_settings.get("voice_id", "alloy")
                    if voice_settings
                    else "alloy"
                ),
                name="Default Voice",
                language="en-US",
                gender=VoiceGender.NEUTRAL,
                age_range="adult",
                description="Default TTS voice",
                is_child_safe=True,
            )

            # Create TTS configuration
            config = TTSConfiguration(
                voice_profile=default_voice,
                emotion=VoiceEmotion.NEUTRAL,
                speed=voice_settings.get("speed", 1.0) if voice_settings else 1.0,
                audio_format=AudioFormat.MP3,
                quality=AudioQuality.STANDARD,
            )

            # Create safety context
            safety_context = (
                ChildSafetyContext(
                    child_age=child_age,
                    parental_controls=True,
                    content_filter_level="strict",
                )
                if child_age
                else None
            )

            # Create TTS request
            request = TTSRequest(
                text=text, config=config, safety_context=safety_context
            )

            # Check cache first if available
            cache_key = None
            if self.cache_service:
                cache_key = self._generate_cache_key(request)
                cached_result = await self.cache_service.get(cache_key)
                if cached_result:
                    self._cache_hits += 1
                    self._metrics.cache_hit_rate = self._cache_hits / max(
                        self._tts_request_count, 1
                    )
                    return cached_result

            # Call unified TTS service
            result = await self.tts_service.synthesize_speech(request)

            # Cache the result if cache service available
            if self.cache_service and cache_key:
                estimated_cost = result.estimated_cost or 0.0
                await self.cache_service.set(cache_key, result, cost=estimated_cost)

            # Track cache hits and update metrics
            if result.cached:
                self._cache_hits += 1

            # Update success metrics
            self._metrics.successful_requests += 1
            request_time = (
                datetime.now(timezone.utc) - request_start_time
            ).total_seconds() * 1000
            self._response_times.append(request_time)

            # Update average response time
            if self._response_times:
                self._metrics.average_response_time = sum(self._response_times) / len(
                    self._response_times
                )

            # Update cache hit rate
            self._metrics.cache_hit_rate = self._cache_hits / max(
                self._tts_request_count, 1
            )

            # Update error rate
            self._metrics.error_rate = self._metrics.failed_requests / max(
                self._metrics.total_requests, 1
            )

            self._safe_log(
                f"TTS conversion completed: {len(result.audio_data)} bytes, cached={result.cached}"
            )
            return result

        except TTSConfigurationError as e:
            self._update_error_metrics("configuration_error")
            self._safe_log(f"TTS configuration error: {e}", "error")
            raise AudioProcessingError(f"TTS configuration error: {e}")
        except TTSProviderError as e:
            self._update_error_metrics("provider_error")
            self._safe_log(f"TTS provider error: {e}", "error")
            raise AudioProcessingError(f"TTS provider error: {e}")
        except TTSError as e:
            self._update_error_metrics("tts_error")
            self._safe_log(f"TTS service error: {e}", "error")
            raise AudioProcessingError(f"TTS service error: {e}")
        except ValueError as e:
            self._update_error_metrics("validation_error")
            self._safe_log(f"Invalid TTS parameters: {e}", "error")
            raise AudioProcessingError(f"Invalid TTS parameters: {e}")
        except TimeoutError as e:
            self._update_error_metrics("timeout_error")
            self._safe_log(f"TTS request timeout: {e}", "error")
            raise AudioProcessingError(f"TTS request timeout: {e}")
        except Exception as e:
            self._update_error_metrics("unexpected_error")
            self._safe_log(f"Unexpected TTS error: {e}", "error")
            raise AudioProcessingError(f"Unexpected TTS error: {e}")

    def _generate_cache_key(self, request: TTSRequest) -> str:
        """
        Generate intelligent cache key for TTS request.
        Includes text content, voice settings, and safety context.
        """
        key_components = [
            request.text,
            request.config.voice_profile.voice_id,
            str(request.config.speed),
            request.config.audio_format.value,
            request.config.quality.value,
            request.config.emotion.value,
        ]

        # Add safety context if present
        if request.safety_context:
            key_components.extend(
                [
                    str(request.safety_context.child_age or "no_age"),
                    str(request.safety_context.parental_controls),
                    request.safety_context.content_filter_level or "default",
                ]
            )

        # Create hash of all components
        key_string = "|".join(key_components)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _update_error_metrics(self, error_type: str) -> None:
        """Update error metrics for monitoring."""
        self._metrics.failed_requests += 1
        if error_type not in self._metrics.provider_errors:
            self._metrics.provider_errors[error_type] = 0
        self._metrics.provider_errors[error_type] += 1

        # Update error rate
        self._metrics.error_rate = self._metrics.failed_requests / max(
            self._metrics.total_requests, 1
        )

    async def validate_audio_safety(self, audio_data: bytes) -> bool:
        """Delegate safety validation to safety service."""
        result = await self.safety_service.check_audio_safety(audio_data)
        return result.is_safe

    async def get_service_health(self) -> Dict[str, Any]:
        """Comprehensive health check including TTS metrics."""
        success_rate = self._success_count / max(self._request_count, 1)
        cache_hit_rate = self._cache_hits / max(self._tts_request_count, 1)

        # Check TTS service health
        tts_health = await self.tts_service.health_check()

        # Get comprehensive cache stats if available
        cache_stats = {}
        if self.cache_service:
            try:
                cache_stats = await self.cache_service.get_comprehensive_stats()
            except Exception as e:
                cache_stats = {"error": str(e)}

        return {
            "status": (
                "healthy"
                if success_rate > 0.9 and tts_health.get("status") == "healthy"
                else "degraded"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "audio_processing": {
                "total_requests": self._request_count,
                "success_count": self._success_count,
                "success_rate": success_rate,
            },
            "tts_service": {
                "total_requests": self._tts_request_count,
                "cache_hits": self._cache_hits,
                "cache_hit_rate": cache_hit_rate,
                "provider_health": tts_health,
            },
            "production_cache": cache_stats,
        }

    async def get_available_voices(
        self, language: str = None, child_safe_only: bool = True
    ) -> list[VoiceProfile]:
        """Get available TTS voices through unified interface."""
        try:
            return await self.tts_service.get_available_voices(
                language, child_safe_only
            )
        except Exception as e:
            self._safe_log(f"Failed to get available voices: {e}", "error")
            return []

    async def estimate_tts_cost(self, text: str) -> Dict[str, Any]:
        """Estimate TTS cost for given text."""
        try:
            # Create minimal request for cost estimation
            request = TTSRequest(
                text=text,
                config=TTSConfiguration(
                    voice_profile=VoiceProfile(
                        "alloy",
                        "Alloy",
                        "en-US",
                        VoiceGender.NEUTRAL,
                        "adult",
                        "Default",
                    )
                ),
            )
            return await self.tts_service.estimate_cost(request)
        except Exception as e:
            self._safe_log(f"Failed to estimate TTS cost: {e}", "error")
            return {"error": str(e)}

    async def get_tts_metrics(self) -> Dict[str, Any]:
        """Get comprehensive TTS metrics for monitoring."""
        # Get production cache metrics if available
        cache_metrics = {}
        if self.cache_service:
            try:
                cache_health = await self.cache_service.health_check()
                cache_stats = await self.cache_service.get_comprehensive_stats()
                cache_metrics = {"health": cache_health, "performance": cache_stats}
            except Exception as e:
                cache_metrics = {"error": str(e)}

        return {
            "tts_metrics": self._metrics.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_info": {
                "total_audio_requests": self._request_count,
                "total_tts_requests": self._tts_request_count,
                "cache_hits": self._cache_hits,
            },
            "production_cache_metrics": cache_metrics,
        }
