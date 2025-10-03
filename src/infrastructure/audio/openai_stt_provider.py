"""
OpenAI STT Provider - Production Implementation
==============================================
Speech-to-text provider backed by OpenAI Whisper API with production-grade
logging, metrics, and health checks.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.interfaces.providers.stt_provider import ISTTProvider, STTResult, STTError


class OpenAISTTProvider(ISTTProvider):
    """Production-ready STT provider using OpenAI's transcription API."""

    def __init__(
        self,
        api_key: str,
        model: str = "whisper-1",
        default_language: Optional[str] = None,
        request_timeout: float = 60.0,
        response_format: str = "verbose_json",
    ) -> None:
        if not api_key:
            raise STTError("OpenAI STT provider requires an API key")

        self.api_key = api_key
        self.model = model
        self.default_language = default_language
        self.request_timeout = request_timeout
        self.response_format = response_format

        self._client: Optional[AsyncOpenAI] = None
        self._logger = logging.getLogger(__name__)

        # Simple metrics for observability
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._cumulative_latency_ms = 0.0
        self._last_error: Optional[str] = None

        self._logger.info(
            "Initialized OpenAISTTProvider",
            extra={
                "model": self.model,
                "default_language": self.default_language,
                "timeout": self.request_timeout,
            },
        )

    async def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key, timeout=self.request_timeout)
        return self._client

    async def transcribe(
        self, audio_data: bytes, language: Optional[str] = None
    ) -> STTResult:
        if not audio_data:
            raise STTError("Audio payload is empty")

        client = await self._get_client()
        started = time.perf_counter()
        self._total_requests += 1

        try:
            audio_stream = io.BytesIO(audio_data)
            audio_stream.name = "audio.wav"

            options: Dict[str, Any] = {
                "model": self.model,
                "file": audio_stream,
                "response_format": self.response_format,
                "temperature": 0,
            }
            language_code = language or self.default_language
            if language_code:
                options["language"] = language_code

            response = await client.audio.transcriptions.create(**options)

            if isinstance(response, dict):
                payload = response
            else:  # openai-python returns pydantic model
                payload = response.dict()  # type: ignore[assignment]

            text = (payload.get("text") or "").strip()
            segments = payload.get("segments") or []
            language_detected = payload.get("language") or language_code or "auto"
            duration = payload.get("duration", 0)

            confidence = 1.0
            if segments:
                logprobs = [seg.get("avg_logprob") for seg in segments if seg.get("avg_logprob") is not None]
                if logprobs:
                    confidence = max(min(sum(logprobs) / len(logprobs) + 1.0, 1.0), 0.0)

            elapsed_ms = (time.perf_counter() - started) * 1000
            self._successful_requests += 1
            self._cumulative_latency_ms += elapsed_ms

            result_segments: List[Dict[str, Any]] = []
            for seg in segments:
                result_segments.append(
                    {
                        "id": seg.get("id"),
                        "start": seg.get("start"),
                        "end": seg.get("end"),
                        "text": seg.get("text", "").strip(),
                        "confidence": seg.get("avg_logprob"),
                        "no_speech_prob": seg.get("no_speech_prob"),
                    }
                )

            metadata = {
                "model": self.model,
                "language_detected": language_detected,
                "duration": duration,
                "raw_response": {
                    "segments": len(result_segments),
                    "has_confidence": bool(result_segments),
                },
            }

            return STTResult(
                text=text,
                language=language_detected,
                confidence=confidence,
                processing_time_ms=elapsed_ms,
                segments=result_segments,
                metadata=metadata,
            )
        except Exception as exc:
            self._failed_requests += 1
            self._last_error = str(exc)
            self._logger.error("OpenAI STT transcription failed", exc_info=True)
            raise STTError(f"OpenAI STT transcription failed: {exc}") from exc

    async def get_supported_languages(self) -> List[str]:
        # OpenAI Whisper currently supports many languages; list the most common ones.
        return [
            "auto",
            "en",
            "es",
            "fr",
            "de",
            "ar",
            "hi",
            "ja",
            "ko",
            "zh",
        ]

    async def health_check(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            client = await self._get_client()
            await asyncio.wait_for(client.models.retrieve(self.model), timeout=self.request_timeout)
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "status": "healthy",
                "model": self.model,
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            self._last_error = str(exc)
            self._logger.error("OpenAI STT health check failed", exc_info=True)
            return {
                "status": "unhealthy",
                "model": self.model,
                "error": str(exc),
            }

    async def get_statistics(self) -> Dict[str, Any]:
        avg_latency = 0.0
        if self._successful_requests:
            avg_latency = self._cumulative_latency_ms / self._successful_requests
        return {
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "average_latency_ms": avg_latency,
            "last_error": self._last_error,
        }
