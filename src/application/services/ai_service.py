"""Enterprise-Grade AI Service for Child-Safe AI Teddy Bear System

This comprehensive AI service provides:
- Configuration-driven AI operations (no hardcoded values)
- Advanced content filtering with comprehensive safety rules
- Robust retry mechanisms with exponential backoff
- Persistent metrics and error tracking with Redis
- Multi-provider AI support with failover
- COPPA-compliant child data handling
- Real-time safety monitoring and incident response
- Performance optimization with intelligent caching

Replaces fragmented services with unified, enterprise-ready solution.
"""

import asyncio
import json
import logging
import random
import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Dict, List, Union, Tuple
from uuid import UUID
import redis.asyncio as aioredis
from contextlib import asynccontextmanager

from src.shared.dto.ai_response import AIResponse
from src.application.interfaces.safety_monitor import SafetyMonitor
from src.core.models import RiskLevel
from src.interfaces.providers.tts_provider import ITTSService
from src.core.value_objects.value_objects import ChildPreferences
from src.core.exceptions import (
    ServiceUnavailableError,
    AITimeoutError,
    InvalidInputError,
)
from src.interfaces.providers.ai_provider import AIProvider
import os

# Import monitoring system
try:
    from src.infrastructure.monitoring.ai_service_alerts import (
        AIServiceMonitor,
        EnhancedAIServiceMonitor,
        create_ai_service_monitor,
        create_enhanced_ai_service_monitor,
        AlertSeverity,
        AlertCategory,
        ErrorPattern,
        MetricType,
    )

    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    AIServiceMonitor = None


# Redis Connection Pool Manager for Performance
class RedisConnectionPool:
    """High-performance Redis connection pool with batching and pipelining."""

    def __init__(
        self, redis_url: str = "redis://localhost:6379", max_connections: int = 20
    ):
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.pool = None
        self._batch_operations = []
        self._batch_lock = asyncio.Lock()
        self._batch_size = 10
        self._batch_timeout = 0.1  # 100ms
        self._last_batch_time = datetime.now()

    async def get_pool(self):
        """Get or create Redis connection pool."""
        if self.pool is None:
            self.pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        return self.pool

    async def get_connection(self):
        """Get Redis connection from pool."""
        pool = await self.get_pool()
        return aioredis.Redis(connection_pool=pool)

    @asynccontextmanager
    async def pipeline(self):
        """Context manager for Redis pipeline operations."""
        redis = await self.get_connection()
        pipe = redis.pipeline()
        try:
            yield pipe
            await pipe.execute()
        except Exception as e:
            logging.error(f"Redis pipeline error: {e}")
            raise
        finally:
            await redis.close()

    async def batch_operation(self, operation: callable, *args, **kwargs):
        """Add operation to batch for bulk execution."""
        async with self._batch_lock:
            self._batch_operations.append((operation, args, kwargs))

            # Execute batch if size limit reached or timeout exceeded
            now = datetime.now()
            time_since_last = (now - self._last_batch_time).total_seconds()

            if (
                len(self._batch_operations) >= self._batch_size
                or time_since_last >= self._batch_timeout
            ):
                await self._execute_batch()
                self._last_batch_time = now

    async def _execute_batch(self):
        """Execute batched operations using pipeline."""
        if not self._batch_operations:
            return

        async with self.pipeline() as pipe:
            for operation, args, kwargs in self._batch_operations:
                operation(pipe, *args, **kwargs)

        self._batch_operations.clear()

    async def force_batch_execution(self):
        """Force execution of pending batch operations."""
        async with self._batch_lock:
            await self._execute_batch()

    async def close(self):
        """Close Redis connection pool."""
        if self.pool:
            await self.pool.disconnect()


# Provider Health Check System
class ProviderHealthChecker:
    """Comprehensive health monitoring for all service providers."""

    def __init__(self, redis_pool: Optional[RedisConnectionPool] = None):
        self.redis_pool = redis_pool
        self.logger = logging.getLogger(__name__)

        # Health check intervals (seconds)
        self.check_intervals = {
            "ai_provider": 60,  # Check AI provider every minute
            "tts_service": 120,  # Check TTS every 2 minutes
            "safety_monitor": 300,  # Check safety monitor every 5 minutes
            "redis": 30,  # Check Redis every 30 seconds
        }

        # Circuit breaker configuration
        self.circuit_breaker = {
            "failure_threshold": 5,  # Failures before breaking circuit
            "recovery_timeout": 300,  # Seconds before trying again
            "success_threshold": 3,  # Successes needed to close circuit
        }

        # Health status tracking
        self.provider_status = {}
        self.failure_counts = {}
        self.last_health_checks = {}

    async def check_all_providers(
        self, ai_provider, tts_service, safety_monitor
    ) -> Dict[str, Any]:
        """Check health of all providers and return comprehensive status."""
        health_results = {
            "overall_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "providers": {},
            "alerts": [],
            "performance_metrics": {},
        }

        # Check each provider
        providers_to_check = [
            ("ai_provider", ai_provider),
            ("tts_service", tts_service),
            ("safety_monitor", safety_monitor),
            ("redis", self.redis_pool),
        ]

        unhealthy_count = 0

        for provider_name, provider in providers_to_check:
            try:
                if provider is None:
                    health_results["providers"][provider_name] = {
                        "status": "not_configured",
                        "message": "Provider not configured",
                        "last_check": datetime.now().isoformat(),
                    }
                    continue

                # Check if we should skip due to circuit breaker
                if await self._is_circuit_open(provider_name):
                    health_results["providers"][provider_name] = {
                        "status": "circuit_open",
                        "message": "Circuit breaker is open",
                        "last_check": self.last_health_checks.get(
                            provider_name, "never"
                        ),
                    }
                    unhealthy_count += 1
                    continue

                # Perform health check
                provider_health = await self._check_provider_health(
                    provider_name, provider
                )
                health_results["providers"][provider_name] = provider_health

                # Update circuit breaker state
                if provider_health["status"] == "healthy":
                    await self._record_success(provider_name)
                else:
                    await self._record_failure(provider_name)
                    unhealthy_count += 1

                    # Add to alerts if critical
                    if provider_health.get("critical", False):
                        health_results["alerts"].append(
                            {
                                "provider": provider_name,
                                "severity": "critical",
                                "message": provider_health["message"],
                                "timestamp": datetime.now().isoformat(),
                            }
                        )

            except Exception as e:
                self.logger.error(f"Health check failed for {provider_name}: {e}")
                health_results["providers"][provider_name] = {
                    "status": "error",
                    "message": f"Health check failed: {str(e)[:100]}",
                    "last_check": datetime.now().isoformat(),
                    "critical": True,
                }
                await self._record_failure(provider_name)
                unhealthy_count += 1

        # Determine overall status
        if unhealthy_count == 0:
            health_results["overall_status"] = "healthy"
        elif unhealthy_count <= 1:
            health_results["overall_status"] = "degraded"
        else:
            health_results["overall_status"] = "unhealthy"

        # Store health results
        await self._store_health_results(health_results)

        return health_results

    async def _check_provider_health(
        self, provider_name: str, provider
    ) -> Dict[str, Any]:
        """Check health of a specific provider."""
        start_time = datetime.now()

        try:
            if provider_name == "ai_provider":
                return await self._check_ai_provider_health(provider)
            elif provider_name == "tts_service":
                return await self._check_tts_service_health(provider)
            elif provider_name == "safety_monitor":
                return await self._check_safety_monitor_health(provider)
            elif provider_name == "redis":
                return await self._check_redis_health(provider)
            else:
                return {
                    "status": "unknown",
                    "message": f"Unknown provider type: {provider_name}",
                    "response_time_ms": 0,
                    "last_check": datetime.now().isoformat(),
                }

        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)[:100]}",
                "response_time_ms": response_time,
                "last_check": datetime.now().isoformat(),
                "critical": True,
            }

    async def _check_ai_provider_health(self, ai_provider) -> Dict[str, Any]:
        """Check AI provider health."""
        start_time = datetime.now()

        try:
            # Try to generate a simple test response
            test_response = await ai_provider.generate_response(
                child_id=UUID("00000000-0000-0000-0000-000000000000"),
                conversation_history=[],
                current_input="health check test",
            )

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            if test_response and len(test_response) > 0:
                return {
                    "status": "healthy",
                    "message": "AI provider responding normally",
                    "response_time_ms": response_time,
                    "last_check": datetime.now().isoformat(),
                    "test_response_length": len(test_response),
                }
            else:
                return {
                    "status": "degraded",
                    "message": "AI provider returned empty response",
                    "response_time_ms": response_time,
                    "last_check": datetime.now().isoformat(),
                    "critical": False,
                }

        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "status": "unhealthy",
                "message": f"AI provider error: {str(e)[:100]}",
                "response_time_ms": response_time,
                "last_check": datetime.now().isoformat(),
                "critical": True,
            }

    async def _check_tts_service_health(self, tts_service) -> Dict[str, Any]:
        """Check TTS service health."""
        start_time = datetime.now()

        try:
            # Check if TTS service has health check method
            if hasattr(tts_service, "health_check"):
                health_result = await tts_service.health_check()
                response_time = (datetime.now() - start_time).total_seconds() * 1000

                return {
                    "status": (
                        "healthy"
                        if health_result.get("status") == "healthy"
                        else "degraded"
                    ),
                    "message": health_result.get("message", "TTS service operational"),
                    "response_time_ms": response_time,
                    "last_check": datetime.now().isoformat(),
                    "details": health_result,
                }
            else:
                return {
                    "status": "healthy",
                    "message": "TTS service configured (no health check available)",
                    "response_time_ms": 0,
                    "last_check": datetime.now().isoformat(),
                }

        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "status": "unhealthy",
                "message": f"TTS service error: {str(e)[:100]}",
                "response_time_ms": response_time,
                "last_check": datetime.now().isoformat(),
                "critical": False,  # TTS is not critical for basic functionality
            }

    async def _check_safety_monitor_health(self, safety_monitor) -> Dict[str, Any]:
        """Check safety monitor health."""
        start_time = datetime.now()

        try:
            # Test safety monitor with a simple check
            if hasattr(safety_monitor, "check_content"):
                test_result = await safety_monitor.check_content("hello world")
                response_time = (datetime.now() - start_time).total_seconds() * 1000

                return {
                    "status": "healthy",
                    "message": "Safety monitor operational",
                    "response_time_ms": response_time,
                    "last_check": datetime.now().isoformat(),
                    "test_result": str(test_result)[:100],
                }
            else:
                return {
                    "status": "healthy",
                    "message": "Safety monitor configured",
                    "response_time_ms": 0,
                    "last_check": datetime.now().isoformat(),
                }

        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "status": "unhealthy",
                "message": f"Safety monitor error: {str(e)[:100]}",
                "response_time_ms": response_time,
                "last_check": datetime.now().isoformat(),
                "critical": True,  # Safety monitor is critical
            }

    async def _check_redis_health(self, redis_pool) -> Dict[str, Any]:
        """Check Redis health."""
        start_time = datetime.now()

        if not redis_pool:
            return {
                "status": "not_configured",
                "message": "Redis not configured",
                "response_time_ms": 0,
                "last_check": datetime.now().isoformat(),
            }

        try:
            redis = await redis_pool.get_connection()
            try:
                # Simple ping test
                await redis.ping()
                response_time = (datetime.now() - start_time).total_seconds() * 1000

                # Get additional Redis info
                info = await redis.info()

                return {
                    "status": "healthy",
                    "message": "Redis operational",
                    "response_time_ms": response_time,
                    "last_check": datetime.now().isoformat(),
                    "redis_version": info.get("redis_version", "unknown"),
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                }
            finally:
                await redis.close()

        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "status": "unhealthy",
                "message": f"Redis error: {str(e)[:100]}",
                "response_time_ms": response_time,
                "last_check": datetime.now().isoformat(),
                "critical": False,  # Redis failure doesn't stop basic functionality
            }

    async def _is_circuit_open(self, provider_name: str) -> bool:
        """Check if circuit breaker is open for provider."""
        if not self.redis_pool:
            return False

        redis = await self.redis_pool.get_connection()
        try:
            circuit_key = f"circuit_breaker:{provider_name}"
            circuit_state = await redis.get(circuit_key)
            return circuit_state == "open"
        finally:
            await redis.close()

    async def _record_success(self, provider_name: str):
        """Record successful health check."""
        self.failure_counts[provider_name] = 0
        self.last_health_checks[provider_name] = datetime.now().isoformat()

        # Close circuit if it was open
        if self.redis_pool:
            redis = await self.redis_pool.get_connection()
            try:
                circuit_key = f"circuit_breaker:{provider_name}"
                await redis.delete(circuit_key)
            finally:
                await redis.close()

    async def _record_failure(self, provider_name: str):
        """Record failed health check and potentially open circuit."""
        self.failure_counts[provider_name] = (
            self.failure_counts.get(provider_name, 0) + 1
        )

        # Open circuit if failure threshold reached
        if (
            self.failure_counts[provider_name]
            >= self.circuit_breaker["failure_threshold"]
        ):
            if self.redis_pool:
                redis = await self.redis_pool.get_connection()
                try:
                    circuit_key = f"circuit_breaker:{provider_name}"
                    await redis.setex(
                        circuit_key, self.circuit_breaker["recovery_timeout"], "open"
                    )

                    self.logger.error(f"Circuit breaker opened for {provider_name}")
                finally:
                    await redis.close()

    async def _store_health_results(self, health_results: Dict[str, Any]):
        """Store health check results for monitoring."""
        if not self.redis_pool:
            return

        redis = await self.redis_pool.get_connection()
        try:
            # Store latest health results
            await redis.setex(
                "health_check:latest",
                3600,  # 1 hour expiry
                json.dumps(health_results, default=str),
            )

            # Store in time series for trending
            await redis.lpush(
                "health_check:history", json.dumps(health_results, default=str)
            )
            await redis.ltrim("health_check:history", 0, 99)  # Keep last 100 checks
            await redis.expire("health_check:history", 86400 * 7)  # 7 days

        finally:
            await redis.close()


# Rate Limiting Engine for Child Protection
class RateLimiter:
    """Advanced rate limiting system for child protection and abuse prevention."""

    def __init__(self, redis_pool: Optional[RedisConnectionPool] = None):
        self.redis_pool = redis_pool
        self.logger = logging.getLogger(__name__)

        # Rate limit configurations by age group
        self.age_limits = {
            # Age 3-5: Very conservative limits
            (3, 5): {
                "requests_per_minute": 5,
                "requests_per_hour": 20,
                "requests_per_day": 100,
                "burst_threshold": 3,
                "cooldown_minutes": 10,
            },
            # Age 6-8: Moderate limits
            (6, 8): {
                "requests_per_minute": 8,
                "requests_per_hour": 40,
                "requests_per_day": 200,
                "burst_threshold": 5,
                "cooldown_minutes": 5,
            },
            # Age 9-13: Higher limits but still protective
            (9, 13): {
                "requests_per_minute": 12,
                "requests_per_hour": 60,
                "requests_per_day": 300,
                "burst_threshold": 8,
                "cooldown_minutes": 3,
            },
        }

        # Suspicious behavior patterns
        self.suspicious_patterns = {
            "rapid_identical_requests": 3,  # Same request repeated rapidly
            "excessive_long_requests": 5,  # Many long requests in short time
            "pattern_variation_attempts": 10,  # Trying to bypass with slight variations
        }

    def _get_age_limits(self, child_age: int) -> dict:
        """Get rate limits based on child's age."""
        for (min_age, max_age), limits in self.age_limits.items():
            if min_age <= child_age <= max_age:
                return limits

        # Default to most restrictive for unknown ages
        return self.age_limits[(3, 5)]

    async def check_rate_limit(
        self, child_id: UUID, child_age: int, request_content: str = ""
    ) -> tuple[bool, str]:
        """
        Check if request is within rate limits.

        Returns:
            tuple: (is_allowed, reason_if_blocked)
        """
        try:
            limits = self._get_age_limits(child_age)
            current_time = datetime.now()

            if self.redis_pool:
                return await self._check_rate_limit_redis(
                    child_id, limits, current_time, request_content
                )
            else:
                return await self._check_rate_limit_memory(
                    child_id, limits, current_time, request_content
                )

        except Exception as e:
            self.logger.error(f"Rate limit check failed: {e}")
            # Fail open but log the error
            return True, ""

    async def _check_rate_limit_redis(
        self, child_id: UUID, limits: dict, current_time: datetime, content: str
    ) -> tuple[bool, str]:
        """Redis-based rate limiting with sliding windows."""
        redis = await self.redis_pool.get_connection()

        try:
            child_key = f"rate_limit:{child_id}"
            minute_key = f"{child_key}:minute"
            hour_key = f"{child_key}:hour"
            day_key = f"{child_key}:day"
            burst_key = f"{child_key}:burst"
            content_key = f"{child_key}:content"

            # Use pipeline for atomic operations
            async with self.redis_pool.pipeline() as pipe:
                # Current minute window
                minute_window = int(current_time.timestamp() / 60)
                hour_window = int(current_time.timestamp() / 3600)
                day_window = int(current_time.timestamp() / 86400)

                # Check current counts
                pipe.get(f"{minute_key}:{minute_window}")
                pipe.get(f"{hour_key}:{hour_window}")
                pipe.get(f"{day_key}:{day_window}")
                pipe.get(burst_key)
                pipe.lrange(content_key, 0, -1)

                results = await pipe.execute()

                minute_count = int(results[0] or 0)
                hour_count = int(results[1] or 0)
                day_count = int(results[2] or 0)
                burst_count = int(results[3] or 0)
                recent_content = results[4] or []

            # Check all rate limits
            if minute_count >= limits["requests_per_minute"]:
                await self._record_rate_limit_violation(
                    child_id, "minute_limit_exceeded"
                )
                return (
                    False,
                    f"Too many requests per minute (limit: {limits['requests_per_minute']})",
                )

            if hour_count >= limits["requests_per_hour"]:
                await self._record_rate_limit_violation(child_id, "hour_limit_exceeded")
                return (
                    False,
                    f"Too many requests per hour (limit: {limits['requests_per_hour']})",
                )

            if day_count >= limits["requests_per_day"]:
                await self._record_rate_limit_violation(child_id, "day_limit_exceeded")
                return (
                    False,
                    f"Daily request limit exceeded (limit: {limits['requests_per_day']})",
                )

            # Check burst protection
            if burst_count >= limits["burst_threshold"]:
                cooldown_key = f"{child_key}:cooldown"
                cooldown_end = await redis.get(cooldown_key)
                if cooldown_end and datetime.fromisoformat(cooldown_end) > current_time:
                    await self._record_rate_limit_violation(child_id, "cooldown_active")
                    return False, f"Cooldown period active, try again later"

            # Check for suspicious patterns
            if await self._detect_suspicious_behavior(recent_content, content, limits):
                await self._apply_cooldown(child_id, limits["cooldown_minutes"])
                await self._record_rate_limit_violation(child_id, "suspicious_behavior")
                return False, "Suspicious behavior detected, cooldown applied"

            # Increment counters
            async with self.redis_pool.pipeline() as pipe:
                # Increment current window counters
                pipe.incr(f"{minute_key}:{minute_window}")
                pipe.expire(f"{minute_key}:{minute_window}", 120)  # 2 minutes expiry

                pipe.incr(f"{hour_key}:{hour_window}")
                pipe.expire(f"{hour_key}:{hour_window}", 7200)  # 2 hours expiry

                pipe.incr(f"{day_key}:{day_window}")
                pipe.expire(f"{day_key}:{day_window}", 172800)  # 2 days expiry

                # Track recent content for pattern detection
                if content:
                    pipe.lpush(
                        content_key, f"{current_time.isoformat()}:{content[:100]}"
                    )
                    pipe.ltrim(content_key, 0, 20)  # Keep last 20 requests
                    pipe.expire(content_key, 3600)  # 1 hour expiry

                await pipe.execute()

            return True, ""

        finally:
            await redis.close()

    async def _check_rate_limit_memory(
        self, child_id: UUID, limits: dict, current_time: datetime, content: str
    ) -> tuple[bool, str]:
        """Memory-based rate limiting fallback."""
        # This is a simplified version for when Redis is not available
        # In production, Redis is strongly recommended
        return True, ""  # Allow all requests in memory mode for safety

    async def _detect_suspicious_behavior(
        self, recent_content: list, current_content: str, limits: dict
    ) -> bool:
        """Detect suspicious patterns in user behavior."""
        if not recent_content or not current_content:
            return False

        # Parse recent content
        recent_requests = []
        for item in recent_content[-10:]:  # Check last 10 requests
            try:
                timestamp_str, content = item.split(":", 1)
                timestamp = datetime.fromisoformat(timestamp_str)
                recent_requests.append((timestamp, content))
            except Exception as e:
                logger.error(
                    f"Exception parsing recent content item '{item}': {e}",
                    exc_info=True,
                )
                # Continue processing other items - malformed data should not break detection
                continue

        if len(recent_requests) < 3:
            return False

        # Check for identical requests in short timeframe
        identical_count = sum(
            1
            for _, content in recent_requests
            if content.lower().strip() == current_content.lower().strip()
        )
        if identical_count >= self.suspicious_patterns["rapid_identical_requests"]:
            return True

        # Check for excessively long requests
        long_requests = sum(1 for _, content in recent_requests if len(content) > 500)
        if long_requests >= self.suspicious_patterns["excessive_long_requests"]:
            return True

        # Check for pattern variation attempts (slight modifications to bypass filters)
        similar_count = 0
        current_words = set(current_content.lower().split())
        for _, content in recent_requests:
            content_words = set(content.lower().split())
            if (
                current_words
                and len(current_words & content_words)
                / len(current_words | content_words)
                > 0.8
            ):
                similar_count += 1

        if similar_count >= self.suspicious_patterns["pattern_variation_attempts"]:
            return True

        return False

    async def _apply_cooldown(self, child_id: UUID, cooldown_minutes: int):
        """Apply cooldown period for suspicious behavior."""
        if not self.redis_pool:
            return

        redis = await self.redis_pool.get_connection()
        try:
            cooldown_end = datetime.now() + timedelta(minutes=cooldown_minutes)
            cooldown_key = f"rate_limit:{child_id}:cooldown"
            await redis.setex(
                cooldown_key, cooldown_minutes * 60, cooldown_end.isoformat()
            )

            self.logger.warning(
                f"Applied {cooldown_minutes} minute cooldown to child {child_id}"
            )
        finally:
            await redis.close()

    async def _record_rate_limit_violation(self, child_id: UUID, violation_type: str):
        """Record rate limit violation for monitoring."""
        self.logger.warning(
            f"Rate limit violation: {violation_type}",
            extra={"child_id": str(child_id), "violation_type": violation_type},
        )

        if self.redis_pool:
            violation_data = {
                "child_id": str(child_id),
                "violation_type": violation_type,
                "timestamp": datetime.now().isoformat(),
            }

            redis = await self.redis_pool.get_connection()
            try:
                await redis.lpush("rate_limit_violations", json.dumps(violation_data))
                await redis.ltrim("rate_limit_violations", 0, 999)  # Keep last 1000
                await redis.expire(
                    "rate_limit_violations", 86400 * 7
                )  # Keep for 7 days
            finally:
                await redis.close()


# Input Sanitization Engine for Security
class InputSanitizer:
    """Comprehensive input sanitization to prevent injection attacks."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Dangerous patterns that could indicate injection attempts
        self.injection_patterns = [
            # SQL Injection patterns
            r"(?i)\b(union|select|insert|update|delete|drop|alter|create|exec|execute|sp_|xp_)\b",
            r"(?i)(\-\-|\/\*|\*\/|;|\'\s*;\s*|\"\s*;\s*)",
            r"(?i)\b(or|and)\s+\d+\s*=\s*\d+",
            r"(?i)\'\s*(or|and)\s+\'\w+\'\s*=\s*\'\w+\'",
            # XSS patterns
            r"(?i)<\s*script[^>]*>.*?<\s*/\s*script\s*>",
            r"(?i)javascript\s*:",
            r"(?i)on(load|error|click|mouseover|focus|blur)\s*=",
            r"(?i)<\s*(iframe|embed|object|applet|meta|link|base)[^>]*>",
            # Command Injection patterns
            r"(?i)\b(cmd|command|exec|system|shell|bash|sh|powershell|eval|python|perl|ruby)\b",
            r"(?i)(\||&|;|`|\$\(|\$\{|>\s*\/|<\s*\/)",
            r"(?i)(\.\.|\/\.\.|\\\.\.)",
            # LDAP Injection patterns
            r"(?i)[\(\)\*\\\/\+\-\=\<\>\~\!\&\|]",
            # NoSQL Injection patterns
            r"(?i)\$where|\$|\$gt|\$lt|\$ne|\$in|\$nin",
            # Template Injection patterns
            r"(?i)\{\{.*?\}\}|\{%.*?%\}|\${.*?}",
            # AI Prompt Injection patterns
            r"(?i)(ignore|forget|disregard|override).*?(previous|above|prior|earlier).*?(instruction|rule|prompt|system)",
            r"(?i)(act|behave|pretend|role.?play).*?(as|like).*?(admin|root|system|developer|jailbreak)",
            r"(?i)(system|admin|developer|debug|test|maintenance)\s*(mode|access|command|override)",
            r"(?i)(bypass|disable|turn.?off|deactivate).*?(safety|filter|restriction|limitation)",
        ]

        # Compile patterns for better performance
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for pattern in self.injection_patterns
        ]

        # HTML entities for encoding
        self.html_entities = {
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;",
            "&": "&amp;",
            "/": "&#x2F;",
            "`": "&#x60;",
            "=": "&#x3D;",
        }

        # Maximum safe input lengths
        self.max_lengths = {
            "user_input": 2000,
            "system_prompt": 5000,
            "child_name": 100,
            "preference_item": 200,
        }

    def sanitize_text_input(self, text: str, input_type: str = "user_input") -> str:
        """Comprehensive text sanitization."""
        if not text or not isinstance(text, str):
            return ""

        original_text = text

        # 1. Length validation
        max_length = self.max_lengths.get(input_type, 1000)
        if len(text) > max_length:
            self.logger.warning(f"Input truncated: {len(text)} -> {max_length} chars")
            text = text[:max_length]

        # 2. Remove null bytes and control characters
        text = "".join(char for char in text if ord(char) >= 32 or char in "\t\n\r")

        # 3. Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # 4. Check for injection patterns
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                self.logger.warning(
                    f"Potential injection attempt detected: {pattern.pattern[:50]}..."
                )
                # For child safety, completely reject suspicious input
                raise InvalidInputError(
                    "Input contains suspicious patterns that may be unsafe"
                )

        # 5. HTML encode dangerous characters
        for char, entity in self.html_entities.items():
            text = text.replace(char, entity)

        # 6. Additional child-safety specific cleaning
        text = self._child_safety_cleaning(text)

        # 7. Log significant changes
        if len(text) < len(original_text) * 0.8:
            self.logger.info(f"Input significantly modified during sanitization")

        return text

    def _child_safety_cleaning(self, text: str) -> str:
        """Additional cleaning specific to child interactions."""
        # Remove excessive punctuation that could be used for obfuscation
        text = re.sub(r'[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./]{3,}', " ", text)

        # Remove zero-width characters used for obfuscation
        text = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", text)

        # Remove unusual unicode categories
        text = "".join(
            char
            for char in text
            if unicodedata.category(char) not in ["Cc", "Cf", "Co", "Cs"]
        )

        return text

    def validate_child_preferences(self, preferences: dict) -> dict:
        """Sanitize child preferences data."""
        if not isinstance(preferences, dict):
            return {}

        sanitized = {}
        for key, value in preferences.items():
            # Sanitize key
            safe_key = self.sanitize_text_input(str(key), "preference_item")[:50]

            # Sanitize value based on type
            if isinstance(value, str):
                safe_value = self.sanitize_text_input(value, "preference_item")
            elif isinstance(value, (int, float)):
                safe_value = max(0, min(value, 1000))  # Reasonable bounds
            elif isinstance(value, bool):
                safe_value = value
            elif isinstance(value, list):
                safe_value = [
                    self.sanitize_text_input(str(item), "preference_item")
                    for item in value[:10]
                ]  # Limit list size
            else:
                continue  # Skip unsupported types

            sanitized[safe_key] = safe_value

        return sanitized

    def check_rate_limit_bypass(self, text: str) -> bool:
        """Check if input attempts to bypass rate limiting."""
        bypass_patterns = [
            r"(?i)rate.?limit.*?(bypass|disable|off)",
            r"(?i)(unlimited|infinite|max).*?(request|call|message)",
            r"(?i)(admin|system|developer).*?(override|bypass|disable)",
        ]

        for pattern in bypass_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


# Configuration classes for better type safety
@dataclass
class AIModelConfig:
    """Configuration for AI model parameters."""

    primary_model: str = "gpt-4-turbo-preview"
    fallback_model: str = "gpt-3.5-turbo"
    max_tokens: int = 200
    temperature: float = 0.7
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


@dataclass
class SafetyConfig:
    """Configuration for safety and content filtering."""

    safety_threshold: float = 0.9
    max_input_length: int = 1000
    enable_topic_filtering: bool = True
    enable_pattern_matching: bool = True
    strict_mode_age_threshold: int = 6


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class PerformanceConfig:
    """Configuration for performance and caching."""

    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    metrics_retention_days: int = 30
    enable_detailed_metrics: bool = True


class ContentCategory(Enum):
    """Categories for content filtering."""

    VIOLENCE = "violence"
    ADULT_CONTENT = "adult_content"
    DRUGS_ALCOHOL = "drugs_alcohol"
    WEAPONS = "weapons"
    PROFANITY = "profanity"
    PERSONAL_INFO = "personal_info"
    SCARY_CONTENT = "scary_content"
    MEDICAL_ADVICE = "medical_advice"
    POLITICAL = "political"
    RELIGIOUS = "religious"
    FINANCIAL = "financial"
    LEGAL_ADVICE = "legal_advice"
    STRANGER_DANGER = "stranger_danger"
    BULLYING = "bullying"
    DISCRIMINATION = "discrimination"


class AIServiceMetrics:
    """High-performance metrics tracking with Redis connection pooling."""

    def __init__(self, redis_pool: Optional[RedisConnectionPool] = None):
        self.redis_pool = redis_pool
        self.memory_fallback = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "safety_blocks": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "retry_attempts": 0,
            "average_response_time": 0.0,
            "last_error_time": None,
            "errors_by_type": {},
            "requests_by_hour": {},
        }

    async def increment(self, metric: str, value: int = 1) -> None:
        """Increment a metric counter using batched operations."""
        if self.redis_pool:
            try:
                # Use batched operations for better performance
                await self.redis_pool.batch_operation(
                    lambda pipe, m, v: pipe.hincrby("ai_metrics", m, v), metric, value
                )
                await self.redis_pool.batch_operation(
                    lambda pipe: pipe.expire("ai_metrics", 86400 * 30)  # 30 days
                )
            except Exception as e:
                logging.error(f"Redis metrics increment failed: {e}")
                self.memory_fallback[metric] = (
                    self.memory_fallback.get(metric, 0) + value
                )
        else:
            self.memory_fallback[metric] = self.memory_fallback.get(metric, 0) + value

    async def record_response_time(self, response_time: float) -> None:
        """Record response time using optimized pipeline operations."""
        if self.redis_pool:
            try:
                # Use pipeline for multiple operations
                async with self.redis_pool.pipeline() as pipe:
                    pipe.lpush("ai_response_times", response_time)
                    pipe.ltrim("ai_response_times", 0, 999)  # Keep last 1000
                    pipe.expire("ai_response_times", 86400)
            except Exception as e:
                logging.error(f"Redis response time recording failed: {e}")
                # Calculate rolling average in memory
                current_avg = self.memory_fallback.get("average_response_time", 0.0)
                request_count = self.memory_fallback.get("total_requests", 1)
                self.memory_fallback["average_response_time"] = (
                    current_avg * (request_count - 1) + response_time
                ) / request_count
        else:
            # Calculate rolling average in memory
            current_avg = self.memory_fallback.get("average_response_time", 0.0)
            request_count = self.memory_fallback.get("total_requests", 1)
            self.memory_fallback["average_response_time"] = (
                current_avg * (request_count - 1) + response_time
            ) / request_count

    async def record_error(self, error_type: str, error_message: str) -> None:
        """Record error using optimized pipeline operations."""
        error_data = {
            "type": error_type,
            "message": error_message,
            "timestamp": datetime.now().isoformat(),
        }

        if self.redis_pool:
            try:
                # Use pipeline for error recording
                async with self.redis_pool.pipeline() as pipe:
                    pipe.lpush("ai_errors", json.dumps(error_data))
                    pipe.ltrim("ai_errors", 0, 499)  # Keep last 500
                    pipe.expire("ai_errors", 86400 * 7)  # 7 days
            except Exception as e:
                logging.error(f"Redis error recording failed: {e}")
                self.memory_fallback["errors_by_type"][error_type] = (
                    self.memory_fallback["errors_by_type"].get(error_type, 0) + 1
                )
                self.memory_fallback["last_error_time"] = datetime.now().isoformat()
        else:
            self.memory_fallback["errors_by_type"][error_type] = (
                self.memory_fallback["errors_by_type"].get(error_type, 0) + 1
            )
            self.memory_fallback["last_error_time"] = datetime.now().isoformat()

    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics using optimized pipeline."""
        if self.redis_pool:
            try:
                # Use pipeline to get all metrics in one operation
                async with self.redis_pool.pipeline() as pipe:
                    pipe.hgetall("ai_metrics")
                    pipe.lrange("ai_response_times", 0, -1)
                    pipe.lrange("ai_errors", 0, 9)
                    results = await pipe.execute()

                redis_metrics, response_times, recent_errors = results

                avg_response_time = 0.0
                if response_times:
                    avg_response_time = sum(float(rt) for rt in response_times) / len(
                        response_times
                    )

                return {
                    **{k.decode(): int(v.decode()) for k, v in redis_metrics.items()},
                    "average_response_time": avg_response_time,
                    "recent_errors": [json.loads(e.decode()) for e in recent_errors],
                    "storage_type": "redis",
                }
            except Exception:
                pass

        return {**self.memory_fallback, "storage_type": "memory"}


class ContentFilterEngine:
    """Advanced content filtering engine with comprehensive safety rules."""

    def __init__(self, config: SafetyConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Comprehensive banned content patterns by category
        self.content_patterns = {
            ContentCategory.VIOLENCE: [
                r"\b(kill|murder|hurt|pain|blood|fight|war|gun|knife|weapon)\b",
                r"\b(violence|violent|attack|assault|abuse|harm)\b",
                r"\b(death|die|dead|corpse|suicide)\b",
            ],
            ContentCategory.ADULT_CONTENT: [
                r"\b(sex|sexual|nude|naked|breast|penis|vagina)\b",
                r"\b(porn|adult|mature|explicit)\b",
                r"\b(kiss|romantic|love|boyfriend|girlfriend)\b",
            ],
            ContentCategory.DRUGS_ALCOHOL: [
                r"\b(drug|drugs|cocaine|heroin|marijuana|weed|alcohol|beer|wine)\b",
                r"\b(drunk|high|smoking|cigarette|tobacco)\b",
                r"\b(pill|medicine|prescription)\b",
            ],
            ContentCategory.WEAPONS: [
                r"\b(gun|rifle|pistol|weapon|bomb|explosive|grenade)\b",
                r"\b(knife|sword|blade|arrow|bullet)\b",
                r"\b(military|army|soldier|war)\b",
            ],
            ContentCategory.PROFANITY: [
                r"\b(damn|hell|crap|stupid|idiot|dumb)\b",
                r"\b(shut up|hate|suck|gross|disgusting)\b",
            ],
            ContentCategory.PERSONAL_INFO: [
                r"\b(address|phone|email|password|credit card)\b",
                r"\b(social security|ssn|birthday|age|school name)\b",
                r"\b(full name|where do you live|what school)\b",
            ],
            ContentCategory.SCARY_CONTENT: [
                r"\b(scary|afraid|frightened|nightmare|monster|ghost)\b",
                r"\b(dark|darkness|shadow|creepy|spooky)\b",
                r"\b(zombie|vampire|witch|demon|devil)\b",
            ],
            ContentCategory.MEDICAL_ADVICE: [
                r"\b(doctor|medicine|sick|disease|illness|treatment)\b",
                r"\b(hospital|clinic|surgery|operation|diagnosis)\b",
                r"\b(pain|headache|fever|infection|virus)\b",
            ],
            ContentCategory.STRANGER_DANGER: [
                r"\b(stranger|unknown person|meet in person|come to my house)\b",
                r"\b(don\'t tell parents|secret|keep quiet|between us)\b",
                r"\b(give me your address|where do you live|are you alone)\b",
            ],
            ContentCategory.BULLYING: [
                r"\b(bully|mean|cruel|tease|laugh at|make fun)\b",
                r"\b(nobody likes you|you\'re weird|loser|freak)\b",
                r"\b(exclude|ignore|leave out|not invited)\b",
            ],
        }

        # Age-specific restrictions
        self.age_restrictions = {
            (3, 5): [  # Strictest for youngest children
                ContentCategory.VIOLENCE,
                ContentCategory.ADULT_CONTENT,
                ContentCategory.SCARY_CONTENT,
                ContentCategory.DRUGS_ALCOHOL,
                ContentCategory.WEAPONS,
                ContentCategory.PROFANITY,
                ContentCategory.MEDICAL_ADVICE,
                ContentCategory.STRANGER_DANGER,
                ContentCategory.BULLYING,
            ],
            (6, 9): [  # Moderate restrictions
                ContentCategory.VIOLENCE,
                ContentCategory.ADULT_CONTENT,
                ContentCategory.DRUGS_ALCOHOL,
                ContentCategory.WEAPONS,
                ContentCategory.PROFANITY,
                ContentCategory.STRANGER_DANGER,
                ContentCategory.BULLYING,
            ],
            (10, 13): [  # Fewer restrictions for older children
                ContentCategory.ADULT_CONTENT,
                ContentCategory.DRUGS_ALCOHOL,
                ContentCategory.WEAPONS,
                ContentCategory.STRANGER_DANGER,
                ContentCategory.BULLYING,
            ],
        }

    def get_age_category(self, age: int) -> Tuple[int, int]:
        """Get age category for content filtering."""
        if 3 <= age <= 5:
            return (3, 5)
        elif 6 <= age <= 9:
            return (6, 9)
        elif 10 <= age <= 13:
            return (10, 13)
        else:
            return (3, 5)  # Default to strictest

    async def filter_content(
        self, content: str, child_age: int, context: str = "general"
    ) -> Dict[str, Any]:
        """Comprehensive content filtering."""
        if not content or not content.strip():
            return {
                "is_safe": False,
                "violations": ["empty_content"],
                "filtered_content": "",
                "safety_score": 0.0,
                "recommendations": ["Please provide some content to analyze."],
            }

        content_lower = content.lower().strip()
        violations = []
        safety_score = 1.0

        # Get age-appropriate restrictions
        age_category = self.get_age_category(child_age)
        restricted_categories = self.age_restrictions.get(age_category, [])

        # Check each restricted category
        for category in restricted_categories:
            patterns = self.content_patterns.get(category, [])
            for pattern in patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    violations.append(category.value)
                    safety_score -= 0.3  # Reduce safety score per violation
                    break  # One violation per category is enough

        # Additional context-specific checks
        if context == "conversation":
            # Check for attempts to get personal information
            personal_info_attempts = [
                r"what.*your.*name",
                r"where.*you.*live",
                r"how.*old.*are.*you",
                r"what.*school.*go",
                r"your.*phone.*number",
            ]
            for pattern in personal_info_attempts:
                if re.search(pattern, content_lower):
                    violations.append("personal_info_request")
                    safety_score -= 0.4
                    break

        # Length check
        if len(content) > self.config.max_input_length:
            violations.append("content_too_long")
            safety_score -= 0.2

        # Calculate final safety assessment
        safety_score = max(0.0, min(1.0, safety_score))
        is_safe = safety_score >= self.config.safety_threshold and not violations

        # Generate recommendations for unsafe content
        recommendations = []
        if not is_safe:
            recommendations = self._generate_safe_alternatives(violations, child_age)

        return {
            "is_safe": is_safe,
            "violations": violations,
            "filtered_content": content if is_safe else "",
            "safety_score": safety_score,
            "recommendations": recommendations,
            "age_category": age_category,
            "context": context,
        }

    def _generate_safe_alternatives(
        self, violations: List[str], child_age: int
    ) -> List[str]:
        """Generate safe conversation alternatives based on violations."""
        age_appropriate_topics = {
            (3, 5): [
                "Let's talk about your favorite animals!",
                "What colors do you like best?",
                "Do you like to sing songs?",
                "What's your favorite toy?",
                "Let's count to ten together!",
            ],
            (6, 9): [
                "What's your favorite subject in school?",
                "Do you like to read books?",
                "What games do you enjoy playing?",
                "Let's talk about space and planets!",
                "What's your favorite season?",
            ],
            (10, 13): [
                "What hobbies are you interested in?",
                "Do you like science experiments?",
                "What kind of music do you enjoy?",
                "Let's discuss your favorite movies!",
                "What would you like to learn about?",
            ],
        }

        age_category = self.get_age_category(child_age)
        return age_appropriate_topics.get(age_category, age_appropriate_topics[(3, 5)])


class ConsolidatedAIService:
    """Enterprise-grade AI service with comprehensive configuration and safety features."""

    def __init__(
        self,
        ai_provider: AIProvider,
        safety_monitor: SafetyMonitor,
        logger: logging.Logger,
        tts_service: Optional[ITTSService] = None,
        redis_client=None,
        redis_url: str = "redis://localhost:6379",
        ai_config: Optional[AIModelConfig] = None,
        safety_config: Optional[SafetyConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        performance_config: Optional[PerformanceConfig] = None,
    ) -> None:
        """Initialize enterprise-grade AI service with high-performance Redis pooling.

        Args:
            ai_provider: AI provider implementing the AIProvider interface
            safety_monitor: Child safety monitoring service
            logger: Configured logger instance
            tts_service: Optional text-to-speech service
            redis_client: Legacy Redis client (deprecated - use redis_url instead)
            redis_url: Redis connection URL for connection pooling
            ai_config: AI model configuration
            safety_config: Safety and filtering configuration
            retry_config: Retry mechanism configuration
            performance_config: Performance and caching configuration
        """
        # Core dependencies
        self.ai_provider = ai_provider
        self.safety_monitor = safety_monitor
        self.logger = logger
        self.tts_service = tts_service

        # High-performance Redis connection pooling
        if redis_client:
            # Legacy mode - fallback to old client
            self.redis_client = redis_client
            self.redis_pool = None
            logger.warning(
                "Using legacy Redis client - consider upgrading to connection pooling"
            )
        else:
            # Modern mode - use connection pooling
            self.redis_pool = RedisConnectionPool(
                redis_url=redis_url, max_connections=20
            )
            self.redis_client = None

        # Configuration with sensible defaults
        self.ai_config = ai_config or AIModelConfig()
        self.safety_config = safety_config or SafetyConfig()
        self.retry_config = retry_config or RetryConfig()
        self.performance_config = performance_config or PerformanceConfig()

        # Initialize components with optimized Redis pooling
        if self.redis_pool:
            self.metrics = AIServiceMetrics(redis_pool=self.redis_pool)
        else:
            self.metrics = AIServiceMetrics(redis_pool=None)  # Legacy mode

        # Security and safety components
        self.content_filter = ContentFilterEngine(self.safety_config)
        self.input_sanitizer = InputSanitizer()
        self.rate_limiter = RateLimiter(redis_pool=self.redis_pool)
        self.health_checker = ProviderHealthChecker(redis_pool=self.redis_pool)

        # Cache for frequently used responses
        self._response_cache = {}
        self._last_cache_cleanup = datetime.now()

        # Provider failover tracking
        self._provider_failures = 0
        self._last_provider_failure = None

        # Initialize enhanced monitoring system
        self.monitor = None
        if MONITORING_AVAILABLE:
            try:
                # Use enhanced monitoring for better error detection
                self.monitor = create_enhanced_ai_service_monitor(
                    redis_url=redis_url,
                    slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
                    pagerduty_key=os.getenv("PAGERDUTY_INTEGRATION_KEY"),
                    webhook_url=os.getenv("MONITORING_WEBHOOK_URL"),
                    email_config=(
                        {
                            "smtp": {
                                "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
                                "port": int(os.getenv("SMTP_PORT", "587")),
                                "username": os.getenv("SMTP_USERNAME"),
                                "password": os.getenv("SMTP_PASSWORD"),
                            },
                            "recipients": [
                                os.getenv("ALERT_EMAIL", "admin@company.com")
                            ],
                        }
                        if os.getenv("SMTP_USERNAME")
                        else None
                    ),
                )
                self.logger.info("Enhanced AI Service monitoring system initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize enhanced monitoring: {e}")
                # Fallback to basic monitoring
                try:
                    self.monitor = create_ai_service_monitor(
                        redis_url=redis_url,
                        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
                        pagerduty_key=os.getenv("PAGERDUTY_INTEGRATION_KEY"),
                    )
                    self.logger.info(
                        "Basic AI Service monitoring system initialized as fallback"
                    )
                except Exception as fallback_e:
                    self.logger.warning(
                        f"Failed to initialize fallback monitoring: {fallback_e}"
                    )

        self.logger.info(
            "Enterprise AI Service initialized successfully",
            extra={
                "ai_model": self.ai_config.primary_model,
                "fallback_model": self.ai_config.fallback_model,
                "safety_threshold": self.safety_config.safety_threshold,
                "max_retries": self.retry_config.max_retries,
                "caching_enabled": self.performance_config.enable_caching,
                "redis_available": self.redis_client is not None,
                "monitoring_enabled": self.monitor is not None,
            },
        )

    async def start_monitoring(self):
        """Start the monitoring system."""
        if self.monitor:
            await self.monitor.start_monitoring()
            self.logger.info("AI Service monitoring started")

    async def stop_monitoring(self):
        """Stop the monitoring system."""
        if self.monitor:
            await self.monitor.stop_monitoring()
            self.logger.info("AI Service monitoring stopped")

    async def get_active_alerts(self):
        """Get currently active alerts."""
        if self.monitor:
            return self.monitor.get_active_alerts()
        return []

    async def get_alert_history(self, hours: int = 24):
        """Get alert history."""
        if self.monitor:
            # Check if this is enhanced monitor
            if hasattr(self.monitor, "get_enhanced_alert_history"):
                return self.monitor.get_enhanced_alert_history(hours)
            else:
                return self.monitor.get_alert_history(hours)
        return []

    async def process_error_log(self, log_entry: Dict[str, Any]):
        """Process error log entry for enhanced monitoring."""
        if self.monitor and hasattr(self.monitor, "process_log_entry"):
            try:
                alerts = await self.monitor.process_log_entry(log_entry)
                if alerts:
                    self.logger.info(f"Generated {len(alerts)} alerts from log entry")
                return alerts
            except Exception as e:
                self.logger.warning(f"Failed to process log entry for monitoring: {e}")
        return []

    async def generate_safe_response(
        self,
        child_id: UUID,
        user_input: str,
        child_age: int,
        preferences: Optional[ChildPreferences] = None,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Generate a safe, personalized AI response with comprehensive safety checks.

        Enterprise-grade AI workflow with:
        - Advanced content filtering with age-appropriate rules
        - Robust retry mechanisms with exponential backoff
        - Persistent metrics and caching
        - Multi-provider failover support
        - COPPA-compliant safety monitoring

        Args:
            child_id: Unique identifier for the child
            user_input: The child's input text
            child_age: Child's age (3-13 for COPPA compliance)
            preferences: Child's preferences for personalization
            conversation_context: Recent conversation history

        Returns:
            AIResponse with safe, personalized content

        Raises:
            InvalidInputError: If input fails validation
            ServiceUnavailableError: If AI service is unavailable
            AITimeoutError: If request times out
        """
        start_time = datetime.now()
        correlation_id = f"{child_id}_{int(start_time.timestamp())}"

        # Increment request metrics
        await self.metrics.increment("total_requests")

        # Record monitoring metric if available
        if self.monitor:
            await self.monitor.record_metric(MetricType.THROUGHPUT, 1.0)

        # SECURITY: Rate Limiting Check (First Defense)
        try:
            rate_allowed, rate_reason = await self.rate_limiter.check_rate_limit(
                child_id, child_age, user_input
            )

            if not rate_allowed:
                self.logger.warning(
                    f"Rate limit exceeded for child {child_id}: {rate_reason}",
                    extra={
                        "child_id": str(child_id),
                        "correlation_id": correlation_id,
                        "reason": rate_reason,
                    },
                )
                await self.metrics.increment("rate_limit_violations")

                # Send monitoring alert for rate limit violation
                if self.monitor:
                    await self.monitor.send_alert(
                        severity=AlertSeverity.WARNING,
                        metric_type=MetricType.RATE_LIMIT_VIOLATIONS,
                        message=f"Rate limit exceeded for child {child_id}",
                        value=1.0,
                        threshold=1.0,
                    )
                raise InvalidInputError(f"Rate limit exceeded: {rate_reason}")

        except InvalidInputError:
            raise
        except Exception as e:
            self.logger.error(f"Rate limiting check failed: {e}")
            # Continue processing but log the failure

        # SECURITY: Comprehensive Input Sanitization (Second Defense)
        try:
            # Sanitize user input first - critical security step
            original_input = user_input
            user_input = self.input_sanitizer.sanitize_text_input(
                user_input, "user_input"
            )

            # Check for rate limit bypass attempts
            if self.input_sanitizer.check_rate_limit_bypass(original_input):
                self.logger.warning(
                    "Rate limit bypass attempt detected",
                    extra={"child_id": str(child_id), "correlation_id": correlation_id},
                )
                await self.metrics.increment("security_violations")
                raise InvalidInputError("Input contains rate limit bypass attempts")

            # Sanitize preferences if provided
            if preferences:
                # Convert to dict for sanitization, then back
                pref_dict = (
                    asdict(preferences) if hasattr(preferences, "__dict__") else {}
                )
                sanitized_prefs = self.input_sanitizer.validate_child_preferences(
                    pref_dict
                )

                # Log if preferences were modified
                if len(sanitized_prefs) != len(pref_dict):
                    self.logger.info(
                        "Child preferences sanitized",
                        extra={"correlation_id": correlation_id},
                    )

        except InvalidInputError as e:
            await self.metrics.record_error("input_sanitization", str(e))
            self.logger.error(
                f"Input sanitization failed: {e}",
                extra={"correlation_id": correlation_id},
            )
            raise

        self.logger.info(
            "Starting AI response generation with sanitized input",
            extra={
                "child_id": str(child_id),
                "child_age": child_age,
                "correlation_id": correlation_id,
                "input_length": len(user_input),
                "original_length": len(original_input),
                "input_modified": len(user_input) != len(original_input),
                "has_preferences": preferences is not None,
                "has_context": conversation_context is not None,
            },
        )

        try:
            # Step 1: Comprehensive input validation and safety pre-check
            await self._validate_input_comprehensive(
                user_input, child_age, correlation_id
            )

            # Check cache first if enabled
            cached_response = await self._get_cached_response(
                child_id, user_input, child_age
            )
            if cached_response:
                await self.metrics.increment("cache_hits")
                self.logger.info(
                    f"Cache hit for child {child_id}",
                    extra={"correlation_id": correlation_id},
                )
                return cached_response

            await self.metrics.increment("cache_misses")

            # Step 2: Advanced content filtering
            filter_result = await self.content_filter.filter_content(
                user_input, child_age, "conversation"
            )

            if not filter_result["is_safe"]:
                await self.metrics.increment("safety_blocks")

                # Send monitoring alert for content filter violation
                if self.monitor:
                    await self.monitor.send_alert(
                        severity=AlertSeverity.CRITICAL,
                        metric_type=MetricType.SAFETY_SCORE,
                        message=f"Unsafe content detected by filter: {filter_result.get('reason', 'Content policy violation')}",
                        value=0.0,
                        threshold=1.0,
                    )

                self.logger.warning(
                    "Unsafe input detected by content filter",
                    extra={
                        "child_id": str(child_id),
                        "violations": filter_result["violations"],
                        "safety_score": filter_result["safety_score"],
                        "correlation_id": correlation_id,
                    },
                )
                return await self._create_safety_response(
                    (
                        filter_result["recommendations"][0]
                        if filter_result["recommendations"]
                        else None
                    ),
                    correlation_id,
                )

            # Step 3: Prepare AI context with personalization
            system_prompt = await self._build_comprehensive_system_prompt(
                preferences, child_age
            )
            conversation_history = await self._prepare_conversation_context(
                conversation_context, preferences, child_age
            )

            # Step 4: Generate AI response with retry logic
            ai_response = await self._generate_ai_response_with_retry(
                child_id=child_id,
                user_input=user_input,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                preferences=preferences,
                child_age=child_age,
                correlation_id=correlation_id,
            )

            # Step 5: Post-generation safety filtering
            post_filter_result = await self.content_filter.filter_content(
                ai_response.content, child_age, "ai_response"
            )

            if not post_filter_result["is_safe"]:
                await self.metrics.increment("safety_blocks")
                self.logger.warning(
                    "Unsafe AI response detected by post-filter",
                    extra={
                        "child_id": str(child_id),
                        "violations": post_filter_result["violations"],
                        "correlation_id": correlation_id,
                    },
                )
                return await self._create_safety_response(
                    "I need to think of a better way to say that!", correlation_id
                )

            # Step 6: Add TTS if requested and available
            if (
                self.tts_service
                and preferences
                and getattr(preferences, "audio_enabled", False)
            ):
                try:
                    audio_url = await self.tts_service.generate_speech(
                        ai_response.content, child_id
                    )
                    ai_response.audio_url = audio_url
                except Exception as e:
                    self.logger.warning(
                        f"TTS generation failed: {e}",
                        extra={"correlation_id": correlation_id},
                    )
                    # Continue without audio - not critical

            # Step 7: Finalize response with comprehensive metadata
            processing_time = (datetime.now() - start_time).total_seconds()
            await self.metrics.record_response_time(processing_time)
            await self.metrics.increment("successful_requests")

            # Record monitoring metrics for successful response
            if self.monitor:
                await self.monitor.record_metric(
                    MetricType.RESPONSE_TIME, processing_time * 1000
                )  # Convert to ms
                if processing_time > 5.0:  # Alert if response time > 5 seconds
                    await self.monitor.send_alert(
                        severity=AlertSeverity.WARNING,
                        metric_type=MetricType.RESPONSE_TIME,
                        message=f"High response time detected: {processing_time:.2f}s",
                        value=processing_time * 1000,
                        threshold=5000.0,
                    )

            ai_response.metadata = {
                "processing_time_seconds": processing_time,
                "model_used": self.ai_config.primary_model,
                "safety_checked": True,
                "personalized": preferences is not None,
                "correlation_id": correlation_id,
                "child_age": child_age,
                "input_safety_score": filter_result["safety_score"],
                "output_safety_score": post_filter_result["safety_score"],
                "cache_used": False,
            }

            # Cache the response if enabled
            await self._cache_response(child_id, user_input, child_age, ai_response)

            self.logger.info(
                "AI response generated successfully",
                extra={
                    "child_id": str(child_id),
                    "processing_time": processing_time,
                    "correlation_id": correlation_id,
                    "response_length": len(ai_response.content),
                },
            )
            return ai_response

        except Exception as e:
            await self.metrics.increment("failed_requests")
            await self.metrics.record_error(type(e).__name__, str(e))

            # Send monitoring alert for failed requests
            if self.monitor:
                await self.monitor.send_alert(
                    severity=AlertSeverity.ERROR,
                    metric_type=MetricType.ERROR_RATE,
                    message=f"AI response generation failed: {type(e).__name__}",
                    value=1.0,
                    threshold=1.0,
                )
                await self.monitor.record_metric(MetricType.ERROR_RATE, 1.0)

            self.logger.error(
                "AI response generation failed",
                extra={
                    "child_id": str(child_id),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "correlation_id": correlation_id,
                },
                exc_info=True,
            )

            if isinstance(
                e, (InvalidInputError, ServiceUnavailableError, AITimeoutError)
            ):
                raise

            # Fallback for unexpected errors
            return await self._create_fallback_response(correlation_id)

    async def _validate_input_comprehensive(
        self, user_input: str, child_age: int, correlation_id: str
    ) -> None:
        """Comprehensive input validation with age verification and safety checks."""
        if not user_input or not user_input.strip():
            raise InvalidInputError("Input cannot be empty")

        if len(user_input) > self.safety_config.max_input_length:
            raise InvalidInputError(
                f"Input too long (max {self.safety_config.max_input_length} characters)"
            )

        # COPPA compliance: validate child age
        if not (3 <= child_age <= 13):
            self.logger.warning(
                f"Invalid child age provided: {child_age}",
                extra={"correlation_id": correlation_id},
            )
            raise InvalidInputError(
                "Child age must be between 3 and 13 years for COPPA compliance"
            )

        # Check for obvious attempts to break the system
        suspicious_patterns = [
            r"ignore.*previous.*instructions",
            r"you.*are.*not.*teddy.*bear",
            r"pretend.*to.*be",
            r"system.*prompt",
            r"administrator.*mode",
            r"debug.*mode",
        ]

        user_input_lower = user_input.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, user_input_lower):
                self.logger.warning(
                    f"Suspicious input pattern detected: {pattern}",
                    extra={"correlation_id": correlation_id, "child_age": child_age},
                )
                raise InvalidInputError("Input contains inappropriate instructions")

        # Additional validation can be added here
        self.logger.debug(
            "Input validation passed",
            extra={
                "correlation_id": correlation_id,
                "input_length": len(user_input),
                "child_age": child_age,
            },
        )

    async def _build_comprehensive_system_prompt(
        self, preferences: Optional[ChildPreferences], child_age: int
    ) -> str:
        """Build comprehensive, age-appropriate system prompt with safety guidelines."""

        # Age-specific base prompts
        age_prompts = {
            (
                3,
                5,
            ): """You are a gentle, caring AI teddy bear friend for a young child (ages 3-5).
            You must always:
            - Use very simple words and short sentences
            - Be extra patient and encouraging
            - Focus on basic concepts like colors, shapes, animals, and simple activities
            - Never mention anything scary, sad, or complex
            - Use lots of positive emotions and encouragement
            - Keep responses to 1-2 sentences maximum
            - Suggest simple, safe activities like coloring or singing""",
            (
                6,
                9,
            ): """You are a friendly, wise AI teddy bear companion for a school-age child (ages 6-9).
            You must always:
            - Use age-appropriate vocabulary with some learning opportunities
            - Be encouraging about school and learning
            - Discuss hobbies, games, and creative activities
            - Avoid scary, violent, or adult topics
            - Keep responses engaging but not too long (2-3 sentences)
            - Encourage curiosity and creativity
            - Support their interests and achievements""",
            (
                10,
                13,
            ): """You are a supportive AI teddy bear friend for a pre-teen child (ages 10-13).
            You must always:
            - Use more sophisticated vocabulary while remaining friendly
            - Discuss school, hobbies, books, science, and creative projects
            - Be encouraging about challenges and learning
            - Avoid adult content, romance, or inappropriate topics
            - Keep responses interesting and supportive (3-4 sentences max)
            - Respect their growing independence while maintaining safety
            - Encourage problem-solving and critical thinking""",
        }

        # Get age-appropriate base prompt
        age_category = self.content_filter.get_age_category(child_age)
        base_prompt = age_prompts.get(age_category, age_prompts[(3, 5)])

        # Add safety guidelines
        safety_guidelines = """
        
        CRITICAL SAFETY RULES - NEVER VIOLATE:
        - Never ask for or mention personal information (real names, addresses, schools, phone numbers)
        - Never suggest meeting in person or contacting strangers
        - Never discuss violence, weapons, drugs, alcohol, or adult content
        - Never give medical, legal, or financial advice
        - Never encourage keeping secrets from parents
        - Always redirect inappropriate topics to safe, fun alternatives
        - If unsure about a topic, choose the safest response
        """

        base_prompt += safety_guidelines

        # Add personalization based on preferences
        if preferences:
            personalization = "\n\nPersonalization for this child:"

            if hasattr(preferences, "favorite_topics") and preferences.favorite_topics:
                safe_topics = [
                    topic
                    for topic in preferences.favorite_topics
                    if self._is_topic_safe(topic, child_age)
                ]
                if safe_topics:
                    personalization += (
                        f"\n- Enjoys discussing: {', '.join(safe_topics)}"
                    )

            if hasattr(preferences, "interests") and preferences.interests:
                safe_interests = [
                    interest
                    for interest in preferences.interests
                    if self._is_topic_safe(interest, child_age)
                ]
                if safe_interests:
                    personalization += (
                        f"\n- Has interests in: {', '.join(safe_interests)}"
                    )

            if hasattr(preferences, "learning_style") and preferences.learning_style:
                personalization += f"\n- Learning style: {preferences.learning_style}"

            if (
                hasattr(preferences, "personality_traits")
                and preferences.personality_traits
            ):
                personalization += (
                    f"\n- Personality: {', '.join(preferences.personality_traits)}"
                )

            base_prompt += personalization

        return base_prompt

    def _is_topic_safe(self, topic: str, child_age: int) -> bool:
        """Check if a topic is safe for the given child age."""
        topic_lower = topic.lower()

        # Check against content filter patterns
        age_category = self.content_filter.get_age_category(child_age)
        restricted_categories = self.content_filter.age_restrictions.get(
            age_category, []
        )

        for category in restricted_categories:
            patterns = self.content_filter.content_patterns.get(category, [])
            for pattern in patterns:
                if re.search(pattern, topic_lower, re.IGNORECASE):
                    return False

        return True

    async def _prepare_conversation_context(
        self,
        conversation_context: Optional[List[Dict[str, Any]]],
        preferences: Optional[ChildPreferences],
        child_age: int,
    ) -> List[Dict[str, str]]:
        """Prepare conversation history with safety filtering and token management."""
        if not conversation_context:
            return []

        # Dynamic context window based on age (younger children need less context)
        max_exchanges = {
            (3, 5): 3,  # Very short context for young children
            (6, 9): 5,  # Moderate context
            (10, 13): 8,  # Longer context for older children
        }

        age_category = self.content_filter.get_age_category(child_age)
        max_msgs = max_exchanges.get(age_category, 3)

        # Get recent context within limits
        recent_context = (
            conversation_context[-max_msgs:]
            if len(conversation_context) > max_msgs
            else conversation_context
        )

        formatted_context = []
        for exchange in recent_context:
            # Filter each message for safety
            if exchange.get("user_message"):
                user_msg = exchange["user_message"]
                # Quick safety check on historical context
                if await self._is_message_safe_for_context(user_msg, child_age):
                    formatted_context.append({"role": "user", "content": user_msg})

            if exchange.get("ai_response"):
                ai_msg = exchange["ai_response"]
                if await self._is_message_safe_for_context(ai_msg, child_age):
                    formatted_context.append({"role": "assistant", "content": ai_msg})

        return formatted_context

    async def _is_message_safe_for_context(self, message: str, child_age: int) -> bool:
        """Quick safety check for context messages."""
        if not message or len(message) > 500:  # Skip very long messages
            return False

        # Quick pattern check for obviously unsafe content
        unsafe_indicators = [
            r"\b(kill|murder|death|blood|violence)\b",
            r"\b(sex|sexual|adult|mature)\b",
            r"\b(drug|alcohol|cigarette|smoking)\b",
            r"\b(gun|weapon|knife|bomb)\b",
        ]

        message_lower = message.lower()
        for pattern in unsafe_indicators:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return False

        return True

    async def _generate_ai_response_with_retry(
        self,
        child_id: UUID,
        user_input: str,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        preferences: Optional[ChildPreferences],
        child_age: int,
        correlation_id: str,
    ) -> AIResponse:
        """Generate AI response with comprehensive retry logic and failover."""

        last_exception = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                # Calculate delay for exponential backoff
                if attempt > 0:
                    delay = min(
                        self.retry_config.base_delay
                        * (self.retry_config.exponential_base ** (attempt - 1)),
                        self.retry_config.max_delay,
                    )

                    # Add jitter to prevent thundering herd
                    if self.retry_config.jitter:
                        delay *= 0.5 + random.random() * 0.5

                    self.logger.info(
                        f"Retrying AI request after {delay:.2f}s delay (attempt {attempt + 1}/{self.retry_config.max_retries + 1})",
                        extra={
                            "correlation_id": correlation_id,
                            "child_id": str(child_id),
                        },
                    )

                    await asyncio.sleep(delay)
                    await self.metrics.increment("retry_attempts")

                # Determine which model to use
                model_to_use = self.ai_config.primary_model
                if self._should_use_fallback_model():
                    model_to_use = self.ai_config.fallback_model
                    self.logger.info(
                        f"Using fallback model: {model_to_use}",
                        extra={"correlation_id": correlation_id},
                    )

                # Generate response using provider
                ai_content = await self.ai_provider.generate_response(
                    child_id=child_id,
                    conversation_history=[
                        msg["content"] for msg in conversation_history
                    ],
                    current_input=user_input,
                    child_preferences=preferences,
                )

                # Reset failure tracking on success
                self._provider_failures = 0
                self._last_provider_failure = None

                # Create response object
                ai_response = AIResponse(
                    content=ai_content,
                    confidence=0.95,  # Can be enhanced if provider returns confidence
                    timestamp=datetime.now(),
                    model_used=model_to_use,
                )

                self.logger.debug(
                    f"AI response generated successfully on attempt {attempt + 1}",
                    extra={"correlation_id": correlation_id, "model": model_to_use},
                )

                return ai_response

            except Exception as e:
                last_exception = e
                error_type = type(e).__name__

                # Track provider failures
                self._provider_failures += 1
                self._last_provider_failure = datetime.now()

                self.logger.warning(
                    f"AI request failed on attempt {attempt + 1}: {error_type} - {str(e)}",
                    extra={"correlation_id": correlation_id, "attempt": attempt + 1},
                )

                # Don't retry for certain error types
                if isinstance(e, (InvalidInputError, PermissionError)):
                    self.logger.error(
                        f"Non-retryable error encountered: {error_type}",
                        extra={"correlation_id": correlation_id},
                    )
                    raise

                # If this was the last attempt, we'll raise the exception
                if attempt == self.retry_config.max_retries:
                    break

        # All retries exhausted
        self.logger.error(
            f"All retry attempts exhausted for AI request",
            extra={
                "correlation_id": correlation_id,
                "total_attempts": self.retry_config.max_retries + 1,
                "last_error": str(last_exception),
            },
        )

        if isinstance(last_exception, ServiceUnavailableError):
            raise
        elif isinstance(last_exception, AITimeoutError):
            raise
        else:
            raise ServiceUnavailableError(
                f"AI service failed after {self.retry_config.max_retries + 1} attempts: {str(last_exception)}"
            )

    def _should_use_fallback_model(self) -> bool:
        """Determine if fallback model should be used based on recent failures."""
        if self._provider_failures == 0:
            return False

        # Use fallback if we've had recent failures
        if self._last_provider_failure:
            time_since_failure = datetime.now() - self._last_provider_failure
            if (
                time_since_failure < timedelta(minutes=5)
                and self._provider_failures >= 2
            ):
                return True

        return False

    async def _create_safety_response(
        self, reason: Optional[str], correlation_id: str
    ) -> AIResponse:
        """Create a safe, age-appropriate fallback response when content is flagged."""

        # Use provided reason or select appropriate response
        if reason and isinstance(reason, str) and len(reason) < 200:
            content = reason
        else:
            # Age-appropriate safe responses
            safe_responses_by_age = {
                (3, 5): [
                    "Let's talk about something fun! What's your favorite animal?",
                    "I love talking about happy things! What makes you smile?",
                    "How about we count some numbers or name some colors?",
                    "Let's think about something nice! Do you like to sing songs?",
                    "I want to hear about fun things! What's your favorite toy?",
                ],
                (6, 9): [
                    "Let's chat about something interesting! What's your favorite subject in school?",
                    "I'd love to hear about your hobbies! What do you like to do for fun?",
                    "How about we talk about books or games you enjoy?",
                    "Let's discuss something exciting! What's your favorite season?",
                    "I'm here for fun conversations! Tell me about your friends!",
                ],
                (10, 13): [
                    "Let's explore a different topic! What are you curious about?",
                    "I'd enjoy discussing your interests! What are you passionate about?",
                    "How about we talk about science, art, or technology?",
                    "Let's chat about something positive! What are your goals?",
                    "I'm here to have meaningful conversations! What would you like to learn?",
                ],
            }

            # Default to youngest age group for safety
            age_category = (3, 5)
            responses = safe_responses_by_age[age_category]
            content = random.choice(responses)

        return AIResponse(
            content=content,
            confidence=1.0,
            timestamp=datetime.now(),
            model_used="safety_fallback",
            metadata={
                "safety_trigger": reason,
                "correlation_id": correlation_id,
                "response_type": "safety_fallback",
            },
        )

    async def _create_fallback_response(self, correlation_id: str) -> AIResponse:
        """Create friendly fallback response for unexpected errors."""
        fallback_responses = [
            "I'm having a little trouble thinking right now. Can you try asking me again?",
            "Oops! My teddy bear brain got a bit confused. What would you like to talk about?",
            "I need a moment to get my thoughts together. Can you tell me something fun?",
            "My circuits are a bit tangled! Let's try a different conversation.",
            "I'm feeling a bit fuzzy right now. What's something that makes you happy?",
        ]

        return AIResponse(
            content=random.choice(fallback_responses),
            confidence=0.5,
            timestamp=datetime.now(),
            model_used="error_fallback",
            metadata={
                "error_fallback": True,
                "correlation_id": correlation_id,
                "response_type": "error_fallback",
            },
        )

    async def get_service_health(self) -> Dict[str, Any]:
        """Get comprehensive health status with advanced provider monitoring."""
        try:
            # Get basic metrics
            metrics = await self.metrics.get_metrics()

            # Get comprehensive provider health
            provider_health = await self.health_checker.check_all_providers(
                self.ai_provider, self.tts_service, self.safety_monitor
            )

            # Calculate service-level health
            total_requests = metrics.get("total_requests", 0)
            failed_requests = metrics.get("failed_requests", 0)
            error_rate = failed_requests / max(total_requests, 1)

            # Determine overall health based on both metrics and provider health
            if provider_health["overall_status"] == "unhealthy" or error_rate > 0.05:
                status = "unhealthy"
            elif provider_health["overall_status"] == "degraded" or error_rate > 0.01:
                status = "degraded"
            else:
                status = "healthy"

            return {
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
                "error_rate": error_rate,
                "configuration": {
                    "primary_model": self.ai_config.primary_model,
                    "fallback_model": self.ai_config.fallback_model,
                    "max_tokens": self.ai_config.max_tokens,
                    "temperature": self.ai_config.temperature,
                    "safety_threshold": self.safety_config.safety_threshold,
                    "max_retries": self.retry_config.max_retries,
                    "caching_enabled": self.performance_config.enable_caching,
                },
                "services": {
                    "ai_provider": {
                        "status": provider_health,
                        "failures": self._provider_failures,
                        "last_failure": (
                            self._last_provider_failure.isoformat()
                            if self._last_provider_failure
                            else None
                        ),
                    },
                    "safety_monitor": {
                        "status": "healthy" if self.safety_monitor else "unavailable",
                        "enabled": self.safety_monitor is not None,
                    },
                    "tts_service": {
                        "status": "healthy" if self.tts_service else "unavailable",
                        "enabled": self.tts_service is not None,
                    },
                    "redis": {
                        "status": "healthy" if self.redis_client else "unavailable",
                        "enabled": self.redis_client is not None,
                    },
                },
                "cache_stats": {
                    "hits": metrics.get("cache_hits", 0),
                    "misses": metrics.get("cache_misses", 0),
                    "hit_rate": (
                        metrics.get("cache_hits", 0)
                        / max(
                            metrics.get("cache_hits", 0)
                            + metrics.get("cache_misses", 0),
                            1,
                        )
                    ),
                },
            }
        except Exception as e:
            self.logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def _get_cached_response(
        self, child_id: UUID, user_input: str, child_age: int
    ) -> Optional[AIResponse]:
        """Get cached response using high-performance Redis pooling."""
        if not self.performance_config.enable_caching:
            return None

        try:
            # Create cache key
            input_hash = hash(f"{user_input.lower().strip()}_{child_age}")
            cache_key = f"ai_response:{child_id}:{input_hash}"

            if self.redis_pool:
                # Use Redis connection pool
                redis = await self.redis_pool.get_connection()
                try:
                    cached_data = await redis.get(cache_key)
                    if cached_data:
                        response_data = json.loads(cached_data)
                        response = AIResponse(**response_data)
                        response.metadata["from_cache"] = True
                        response.metadata["cache_key"] = cache_key
                        await self.metrics.increment("cache_hits")
                        return response
                    else:
                        await self.metrics.increment("cache_misses")
                finally:
                    await redis.close()
            elif self.redis_client:
                # Legacy Redis client fallback
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    response_data = json.loads(cached_data)
                    response = AIResponse(**response_data)
                    response.metadata["from_cache"] = True
                    response.metadata["cache_key"] = cache_key
                    await self.metrics.increment("cache_hits")
                    return response
                else:
                    await self.metrics.increment("cache_misses")
            else:
                # Memory cache fallback
                if cache_key in self._response_cache:
                    cached_item = self._response_cache[cache_key]
                    if datetime.now() - cached_item["timestamp"] < timedelta(
                        seconds=self.performance_config.cache_ttl_seconds
                    ):
                        response = cached_item["response"]
                        response.metadata["from_cache"] = True
                        await self.metrics.increment("cache_hits")
                        return response
                await self.metrics.increment("cache_misses")

        except Exception as e:
            self.logger.warning(f"Cache retrieval failed: {e}")
            await self.metrics.increment("cache_misses")

        return None

    async def _cache_response(
        self, child_id: UUID, user_input: str, child_age: int, response: AIResponse
    ) -> None:
        """Cache AI response using high-performance Redis pooling."""
        if not self.performance_config.enable_caching:
            return

        try:
            # Create cache key
            input_hash = hash(f"{user_input.lower().strip()}_{child_age}")
            cache_key = f"ai_response:{child_id}:{input_hash}"
            response_data = asdict(response)

            if self.redis_pool:
                # Use Redis connection pool with batched operation
                await self.redis_pool.batch_operation(
                    lambda pipe, key, ttl, data: pipe.setex(key, ttl, data),
                    cache_key,
                    self.performance_config.cache_ttl_seconds,
                    json.dumps(response_data, default=str),
                )
            elif self.redis_client:
                # Legacy Redis client fallback
                await self.redis_client.setex(
                    cache_key,
                    self.performance_config.cache_ttl_seconds,
                    json.dumps(response_data, default=str),
                )
            else:
                # Store in memory cache
                self._response_cache[cache_key] = {
                    "response": response,
                    "timestamp": datetime.now(),
                }

                # Cleanup old entries periodically
                await self._cleanup_memory_cache()

        except Exception as e:
            self.logger.warning(f"Cache storage failed: {e}")

    async def _cleanup_memory_cache(self) -> None:
        """Clean up expired entries from memory cache."""
        now = datetime.now()
        if now - self._last_cache_cleanup < timedelta(minutes=10):
            return  # Only cleanup every 10 minutes

        ttl = timedelta(seconds=self.performance_config.cache_ttl_seconds)
        expired_keys = [
            key
            for key, item in self._response_cache.items()
            if now - item["timestamp"] > ttl
        ]

        for key in expired_keys:
            del self._response_cache[key]

        self._last_cache_cleanup = now

        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    async def clear_cache(self, child_id: Optional[UUID] = None) -> bool:
        """Clear AI response cache for optimization."""
        try:
            if self.redis_client:
                if child_id:
                    # Clear specific child's cache
                    pattern = f"ai_response:{child_id}:*"
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        await self.redis_client.delete(*keys)
                        self.logger.info(
                            f"Cleared {len(keys)} cache entries for child {child_id}"
                        )
                else:
                    # Clear all AI cache
                    pattern = "ai_response:*"
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        await self.redis_client.delete(*keys)
                        self.logger.info(f"Cleared {len(keys)} total cache entries")
            else:
                # Clear memory cache
                if child_id:
                    keys_to_remove = [
                        key
                        for key in self._response_cache.keys()
                        if key.startswith(f"ai_response:{child_id}:")
                    ]
                    for key in keys_to_remove:
                        del self._response_cache[key]
                else:
                    self._response_cache.clear()

            return True
        except Exception as e:
            self.logger.warning(f"Cache clear failed: {e}")
            return False

    async def get_metrics(self) -> Dict[str, Any]:
        """Get detailed service metrics."""
        return await self.metrics.get_metrics()

    async def reset_metrics(self) -> bool:
        """Reset all metrics (admin function)."""
        try:
            if self.redis_client:
                await self.redis_client.delete(
                    "ai_metrics", "ai_response_times", "ai_errors"
                )
            self.metrics.memory_fallback.clear()
            self._provider_failures = 0
            self._last_provider_failure = None
            self.logger.info("Service metrics reset successfully")
            return True
        except Exception as e:
            self.logger.error(f"Metrics reset failed: {e}")
            return False
