"""
ESP32 Production Runner - Complete Production Setup
==================================================
Production-ready runner for ESP32 Chat Server with all services configured.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Optional, Dict, Any
from time import perf_counter

from src.core.exceptions import ConfigurationError
from src.services.esp32_service_factory import ESP32ServiceFactory
from src.services.service_registry import ServiceRegistry
from src.utils.redaction import sanitize_text, sanitize_mapping


class ESP32ProductionRunner:
    """Production runner for ESP32 Chat Server."""

    def __init__(self):
        self.logger = self._setup_logging()
        self.chat_server = None
        self.service_registry = None
        self.metrics: Dict[str, Any] = {"init_runs": 0, "successful_inits": 0, "failed_inits": 0}
        self._init_lock = asyncio.Lock()

    def _setup_logging(self) -> logging.Logger:
        """Setup production logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('esp32_chat_server.log')
            ]
        )
        return logging.getLogger(__name__)

    async def _start_mock_services(self, config, metrics, start_total, *, mode: str = "mock") -> dict:
        """Initialize mock ESP32 pipeline used for tests or AI fallback."""
        from types import SimpleNamespace
        from src.services.esp32_chat_server import ESP32ChatServer
        from src.shared.dto.ai_response import AIResponse

        class MockSTTProvider:
            async def optimize_for_realtime(self) -> None:
                return None

            async def transcribe(self, audio_bytes: bytes, language: str = "auto"):
                _ = audio_bytes, language
                return SimpleNamespace(text="mock transcription", confidence=1.0)

        class MockTTSService:
            async def convert_text_to_speech(self, text: str, voice_settings=None) -> bytes:
                _ = text, voice_settings
                return b"\x00\x00" * 8000

            async def __call__(self, text: str) -> bytes:
                return await self.convert_text_to_speech(text)

        class MockAIService:
            async def generate_safe_response(self, **kwargs) -> AIResponse:
                _ = kwargs
                return AIResponse(
                    content="أنا روبوت تجريبي سعيد بمساعدتك!",
                    metadata={"mock": True},
                    model_used="mock-ai",
                )

        class MockSafetyService:
            async def check_content(self, text: str, child_age: int) -> bool:
                _ = text, child_age
                return True

        mock_chat_server = ESP32ChatServer(config=config)
        mock_chat_server.inject_services(
            MockSTTProvider(),
            MockTTSService(),
            MockAIService(),
            MockSafetyService(),
        )

        from src.services.esp32_chat_server import esp32_chat_server as _esp32_proxy
        _esp32_proxy.set(mock_chat_server)
        self.chat_server = mock_chat_server

        metrics["mode"] = mode
        metrics["status"] = "ready"
        metrics["last_ready_at"] = time.time()
        total_ms = round((perf_counter() - start_total) * 1000, 2)
        metrics["total_ms"] = total_ms
        metrics["successful_inits"] += 1
        self.metrics = metrics
        self.logger.info(
            "Mock ESP32 Chat Server initialized",
            extra={"total_ms": total_ms, "mode": mode},
        )
        return dict(metrics)

    async def initialize_services(self, config=None) -> dict:
        """Initialize all required services with explicit config injection."""
        async with self._init_lock:
            if self.chat_server:
                self.logger.info("ESP32 services already initialized; reusing existing instance")
                self.metrics.setdefault("status", "ready")
                self.metrics.setdefault("last_ready_at", time.time())
                self.metrics["cached"] = True
                return dict(self.metrics)

            start_total = perf_counter()
            durations: dict[str, float] = {}

            def mark(step: str, *, reset: bool = True) -> None:
                nonlocal step_timer
                now = perf_counter()
                durations[step] = round((now - step_timer) * 1000, 2)
                if reset:
                    step_timer = now

            metrics = {
                "init_runs": self.metrics.get("init_runs", 0) + 1,
                "successful_inits": self.metrics.get("successful_inits", 0),
                "failed_inits": self.metrics.get("failed_inits", 0),
                "started_at": time.time(),
                "status": "initializing",
                "steps_ms": durations,
            }
            self.metrics = metrics
            step_timer = start_total

            self.logger.info("Initializing ESP32 Chat Server services...")

            try:
                # Resolve configuration explicitly
                if config is None:
                    from src.infrastructure.config.production_config import (
                        get_config as get_loaded_config,
                        load_config as load_config_safely,
                    )

                    try:
                        config = get_loaded_config()
                    except ConfigurationError:
                        self.logger.warning("Configuration not preloaded; loading via load_config() for ESP32 services")
                        config = load_config_safely()

                mark("config_resolution")

                use_mock_services = bool(
                    getattr(config, "USE_MOCK_SERVICES", False)
                    or os.getenv("USE_MOCK_SERVICES", "false").strip().lower() in ("1", "true", "yes")
                )

                openai_key_present = getattr(config, "OPENAI_API_KEY", None)
                if use_mock_services and openai_key_present and openai_key_present.startswith("sk-"):
                    if not getattr(config, "ALLOW_AI_FAILURE_FALLBACK", False):
                        self.logger.info(
                            "Disabling mock services because a valid OPENAI_API_KEY is configured and fallback is disabled"
                        )
                        use_mock_services = False

                if use_mock_services:
                    return await self._start_mock_services(config, metrics, start_total, mode="mock")
                # Initialize service registry with explicit config
                self.service_registry = ServiceRegistry(config=config)
                mark("service_registry")

                async def _dependency_checks() -> tuple[dict[str, Any], dict[str, float]]:
                    readiness: dict[str, Any] = {"db": False, "redis": False, "openai": False, "errors": []}
                    timings: dict[str, float] = {}

                    async def run_check(name: str, coroutine) -> None:
                        started = perf_counter()
                        try:
                            await asyncio.wait_for(coroutine(), timeout=5)
                            readiness[name] = True
                        except Exception as exc:
                            sanitized = sanitize_text(str(exc)) or str(exc)
                            readiness["errors"].append(f"{name}: {sanitized}")
                            readiness[name] = False
                        finally:
                            timings[f"{name}_ms"] = round((perf_counter() - started) * 1000, 2)

                    async def db_check() -> None:
                        try:
                            from src.adapters.database_production import get_session_cm
                            async with get_session_cm() as session:
                                from sqlalchemy import text
                                await session.execute(text("SELECT 1"))
                        except ImportError:
                            database_url = getattr(config, "DATABASE_URL", None)
                            if not database_url:
                                raise RuntimeError("DATABASE_URL not set")
                            if not database_url.startswith(("postgresql://", "postgresql+asyncpg://", "postgres://", "sqlite://", "sqlite+aiosqlite://")):
                                raise RuntimeError("Unsupported DATABASE_URL format")
                        except Exception as exc:
                            raise RuntimeError(exc)

                    async def redis_check() -> None:
                        redis_url = getattr(config, "REDIS_URL", None)
                        if not redis_url:
                            raise RuntimeError("REDIS_URL not set")
                        try:
                            import redis.asyncio as aioredis
                            client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
                            try:
                                await client.ping()
                            finally:
                                await client.close()
                        except Exception as exc:
                            raise RuntimeError(exc)

                    async def openai_check() -> None:
                        api_key = getattr(config, "OPENAI_API_KEY", None)
                        if not api_key:
                            raise RuntimeError("OPENAI_API_KEY not set")
                        if not api_key.startswith("sk-"):
                            raise RuntimeError("Invalid OPENAI_API_KEY format")
                        model_name = getattr(config, "OPENAI_MODEL", "gpt-4o-mini")
                        try:
                            from openai import AsyncOpenAI
                            client = AsyncOpenAI(api_key=api_key, timeout=5)
                            await client.models.retrieve(model_name)
                        except Exception as exc:
                            raise RuntimeError(exc)

                    if getattr(config, "ENABLE_DATABASE", True):
                        await run_check("db", db_check)
                    else:
                        readiness["db"] = True
                        timings["db_ms"] = 0.0

                    if getattr(config, "ENABLE_REDIS", True):
                        await run_check("redis", redis_check)
                    else:
                        readiness["redis"] = True
                        timings["redis_ms"] = 0.0

                    if getattr(config, "ENABLE_AI_SERVICES", True):
                        await run_check("openai", openai_check)
                    else:
                        readiness["openai"] = True
                        timings["openai_ms"] = 0.0

                    return readiness, timings

                readiness_snapshot, dependency_timings = await _dependency_checks()
                mark("dependencies_check")
                durations.update(
                    {
                        f"dependency_{key}": value
                        for key, value in dependency_timings.items()
                        if isinstance(value, (int, float))
                    }
                )
                sanitized_readiness = sanitize_mapping(dict(readiness_snapshot))
                metrics["readiness"] = sanitized_readiness
                metrics["dependencies_healthy"] = {
                    "db": readiness_snapshot.get("db"),
                    "redis": readiness_snapshot.get("redis"),
                    "openai": readiness_snapshot.get("openai"),
                }

                fallback_allowed = getattr(config, "ALLOW_AI_FAILURE_FALLBACK", True)
                env_override = os.getenv("ALLOW_AI_FAILURE_FALLBACK")
                if env_override is not None:
                    fallback_allowed = env_override.strip().lower() in ("1", "true", "yes")

                self.logger.info(
                    "Dependency readiness check completed",
                    extra={"readiness": sanitized_readiness, "timings_ms": dependency_timings},
                )

                if not all(readiness_snapshot.get(key) for key in ("db", "redis")):
                    sanitized_failure = sanitize_mapping(dict(readiness_snapshot))
                    raise RuntimeError(f"Dependency readiness failed: {sanitized_failure}")

                if not readiness_snapshot.get("openai"):
                    if fallback_allowed:
                        self.logger.warning(
                            "OpenAI readiness failed, enabling mock fallback",
                            extra={"errors": sanitized_readiness.get("errors")},
                        )
                        return await self._start_mock_services(config, metrics, start_total, mode="mock-fallback")
                    sanitized_failure = sanitize_mapping(dict(readiness_snapshot))
                    raise RuntimeError(f"Dependency readiness failed: {sanitized_failure}")

                # Get services from registry
                ai_service = await self.service_registry.get_ai_service()
                mark("ai_service")

                tts_service = await self.service_registry.get_service("tts_service")
                mark("tts_service")

                stt_provider = await self.service_registry.get_service("stt_provider")
                mark("stt_provider")
                if stt_provider is None:
                    raise RuntimeError("STT provider could not be resolved from service registry")

                redis_url = os.getenv("REDIS_URL", getattr(config, "REDIS_URL", "redis://localhost:6379"))

                # Create production server with all services using proper DI
                factory = ESP32ServiceFactory(config=config)

                self.chat_server = await factory.create_production_server(
                    ai_provider=ai_service,
                    tts_service=tts_service,
                    stt_provider=stt_provider,
                    redis_url=redis_url,
                )
                mark("chat_server")

                from src.services.esp32_chat_server import esp32_chat_server as _esp32_proxy
                _esp32_proxy.set(self.chat_server)

                total_ms = round((perf_counter() - start_total) * 1000, 2)
                metrics.update(
                    {
                        "status": "ready",
                        "total_ms": total_ms,
                        "last_ready_at": time.time(),
                        "openai_init_ms": durations.get("ai_service"),
                        "tts_init_ms": durations.get("tts_service"),
                        "stt_init_ms": durations.get("stt_provider"),
                        "pipeline_init_ms": durations.get("chat_server"),
                    }
                )
                metrics.setdefault("mode", "production")
                metrics["successful_inits"] += 1
                self.metrics = metrics
                self.logger.info(
                    "ESP32 Chat Server services initialized successfully",
                    extra={"durations_ms": durations, "total_ms": total_ms},
                )
                return dict(metrics)

            except Exception as e:
                sanitized_error = sanitize_text(str(e)) or str(e)
                metrics["failed_inits"] += 1
                metrics["status"] = "error"
                metrics["error"] = sanitized_error
                metrics["failed_at"] = time.time()
                metrics["total_ms"] = round((perf_counter() - start_total) * 1000, 2)
                self.metrics = metrics
                self.logger.exception("Failed to initialize ESP32 services", extra={"error": sanitized_error})
                self.chat_server = None
                self.service_registry = None
                raise

    async def start_server(self) -> None:
        """Start the ESP32 Chat Server."""
        try:
            if not self.chat_server:
                await self.initialize_services()

            self.logger.info("ESP32 Chat Server is ready for connections")
            
            # The server is now ready to handle WebSocket connections
            # In a real deployment, this would be integrated with FastAPI
            
            # Keep the server running
            while True:
                # Perform health checks
                health_status = await self.chat_server.health_check()
                
                if health_status["status"] != "healthy":
                    self.logger.warning(f"Server health check failed: {health_status}")
                
                # Log metrics every 5 minutes
                metrics = self.chat_server.get_session_metrics()
                self.logger.info(f"Server metrics: {metrics}")
                
                await asyncio.sleep(300)  # 5 minutes

        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
            await self.shutdown()
        except Exception as e:
            sanitized_error = sanitize_text(str(e)) or str(e)
            self.logger.error(
                "Server error",
                exc_info=True,
                extra={"error": sanitized_error},
            )
            await self.shutdown()
            raise

    async def shutdown(self) -> None:
        """Gracefully shutdown the server."""
        try:
            self.logger.info("Shutting down ESP32 Chat Server...")
            
            if self.chat_server:
                await self.chat_server.shutdown()
            
            self.logger.info("ESP32 Chat Server shutdown complete")
            
        except Exception as e:
            sanitized_error = sanitize_text(str(e)) or str(e)
            self.logger.error(
                "Error during shutdown",
                exc_info=True,
                extra={"error": sanitized_error},
            )

    async def health_check(self) -> dict:
        """Get server health status."""
        if not self.chat_server:
            return {"status": "not_initialized"}
        
        return await self.chat_server.health_check()

    def get_chat_server(self):
        """Get the chat server instance for integration with FastAPI."""
        return self.chat_server


# Global production runner instance
esp32_production_runner = ESP32ProductionRunner()


async def main():
    """Main entry point for standalone server."""
    try:
        await esp32_production_runner.start_server()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        sanitized_error = sanitize_text(str(e)) or str(e)
        print(f"Server failed to start: {sanitized_error}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
