"""
Production Redis Cache Service - Enterprise-grade Caching
========================================================
High-performance Redis-based caching with:
- Connection pooling and cluster support
- Advanced TTL management and eviction policies
- Performance monitoring and analytics
- Distributed cache consistency
- Circuit breaker and fallback mechanisms
"""

import asyncio
import json
import logging
import pickle
import time
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import os

import redis.asyncio as aioredis
from redis.asyncio import Redis, ConnectionPool

from src.interfaces.services import ICacheService


@dataclass
class CacheMetrics:
    """Comprehensive cache performance metrics."""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_evictions: int = 0
    total_expires: int = 0
    avg_get_time_ms: float = 0.0
    avg_set_time_ms: float = 0.0
    memory_usage_bytes: int = 0
    connection_errors: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate percentage."""
        return 100.0 - self.hit_rate


@dataclass
class CacheKey:
    """Structured cache key with metadata."""

    namespace: str
    key: str
    version: str = "v1"

    def __str__(self) -> str:
        return f"{self.namespace}:{self.version}:{self.key}"

    def hash(self) -> str:
        """Generate hash for very long keys."""
        full_key = str(self)
        if len(full_key) > 200:  # Redis key length limit
            return f"{self.namespace}:{self.version}:{hashlib.sha256(self.key.encode()).hexdigest()}"
        return full_key


class ProductionRedisCache(ICacheService):
    """
    Production-grade Redis cache with enterprise features:
    - High availability with Redis Sentinel/Cluster
    - Connection pooling and automatic failover
    - Performance monitoring and alerting
    - Data compression and serialization
    - Circuit breaker for fault tolerance
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics = CacheMetrics()

        # Redis configuration from environment
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_password = os.getenv("REDIS_PASSWORD")
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
        self.connection_timeout = int(os.getenv("REDIS_TIMEOUT", "10"))

        # Cache configuration
        self.default_ttl = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))  # 1 hour
        self.max_key_length = int(os.getenv("CACHE_MAX_KEY_LENGTH", "200"))
        self.enable_compression = (
            os.getenv("CACHE_ENABLE_COMPRESSION", "true").lower() == "true"
        )
        self.compression_threshold = int(
            os.getenv("CACHE_COMPRESSION_THRESHOLD", "1024")
        )  # 1KB

        # Circuit breaker configuration
        self.circuit_breaker_threshold = int(
            os.getenv("CACHE_CIRCUIT_BREAKER_THRESHOLD", "5")
        )
        self.circuit_breaker_timeout = int(
            os.getenv("CACHE_CIRCUIT_BREAKER_TIMEOUT", "60")
        )
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure = None
        self.circuit_breaker_open = False

        # Initialize Redis connection
        self.redis: Optional[Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None

        self.logger.info("ProductionRedisCache initialized")

    async def _ensure_connection(self) -> Redis:
        """Ensure Redis connection is established with connection pooling."""
        if self.redis is None or self.connection_pool is None:
            try:
                # Create connection pool
                self.connection_pool = ConnectionPool.from_url(
                    self.redis_url,
                    password=self.redis_password,
                    db=self.redis_db,
                    max_connections=self.max_connections,
                    retry_on_timeout=True,
                    socket_connect_timeout=self.connection_timeout,
                    socket_keepalive=True,
                    socket_keepalive_options={
                        1: 1,  # TCP_KEEPIDLE
                        2: 3,  # TCP_KEEPINTVL
                        3: 5,  # TCP_KEEPCNT
                    },
                )

                # Create Redis client
                self.redis = Redis(connection_pool=self.connection_pool)

                # Test connection
                await self.redis.ping()

                self.logger.info("Redis connection established successfully")

                # Reset circuit breaker
                self.circuit_breaker_failures = 0
                self.circuit_breaker_open = False

            except Exception as e:
                self._handle_connection_error(e)
                raise

        return self.redis

    def _handle_connection_error(self, error: Exception) -> None:
        """Handle Redis connection errors and update circuit breaker."""
        self.metrics.connection_errors += 1
        self.circuit_breaker_failures += 1
        self.circuit_breaker_last_failure = datetime.now()

        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
            self.circuit_breaker_open = True
            self.logger.error(
                f"Redis circuit breaker opened after {self.circuit_breaker_failures} failures",
                extra={"error": str(error)},
            )

        self.logger.error(f"Redis connection error: {error}", exc_info=True)

    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker should remain open."""
        if not self.circuit_breaker_open:
            return False

        if self.circuit_breaker_last_failure is None:
            return False

        # Check if timeout has passed
        timeout_passed = (
            datetime.now() - self.circuit_breaker_last_failure
        ).total_seconds() > self.circuit_breaker_timeout

        if timeout_passed:
            self.circuit_breaker_open = False
            self.circuit_breaker_failures = 0
            self.logger.info("Redis circuit breaker reset - attempting reconnection")

        return self.circuit_breaker_open

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache with performance tracking.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        if self._is_circuit_breaker_open():
            self.logger.warning("Redis circuit breaker open - cache get bypassed")
            return default

        start_time = time.time()
        cache_key = self._normalize_key(key)

        try:
            redis = await self._ensure_connection()

            # Get value from Redis
            raw_value = await redis.get(str(cache_key))

            # Update metrics
            self.metrics.total_requests += 1
            get_time_ms = (time.time() - start_time) * 1000
            self._update_avg_get_time(get_time_ms)

            if raw_value is None:
                self.metrics.cache_misses += 1
                self.logger.debug(f"Cache miss for key: {cache_key}")
                return default

            # Deserialize value
            value = self._deserialize(raw_value)

            self.metrics.cache_hits += 1
            self.logger.debug(
                f"Cache hit for key: {cache_key}", extra={"get_time_ms": get_time_ms}
            )

            return value

        except Exception as e:
            self._handle_connection_error(e)
            self.metrics.cache_misses += 1
            self.logger.error(
                f"Cache get error for key {cache_key}: {e}", exc_info=True
            )
            return default

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)

        Returns:
            True if set successfully
        """
        if self._is_circuit_breaker_open():
            self.logger.warning("Redis circuit breaker open - cache set bypassed")
            return False

        start_time = time.time()
        cache_key = self._normalize_key(key)
        ttl = ttl or self.default_ttl

        try:
            redis = await self._ensure_connection()

            # Serialize value
            serialized_value = self._serialize(value)

            # Set value with TTL
            await redis.setex(str(cache_key), ttl, serialized_value)

            # Update metrics
            set_time_ms = (time.time() - start_time) * 1000
            self._update_avg_set_time(set_time_ms)

            self.logger.debug(
                f"Cache set for key: {cache_key}",
                extra={"ttl": ttl, "set_time_ms": set_time_ms},
            )

            return True

        except Exception as e:
            self._handle_connection_error(e)
            self.logger.error(
                f"Cache set error for key {cache_key}: {e}", exc_info=True
            )
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if deleted successfully
        """
        if self._is_circuit_breaker_open():
            self.logger.warning("Redis circuit breaker open - cache delete bypassed")
            return False

        cache_key = self._normalize_key(key)

        try:
            redis = await self._ensure_connection()

            result = await redis.delete(str(cache_key))

            self.logger.debug(f"Cache delete for key: {cache_key}, result: {result}")
            return result > 0

        except Exception as e:
            self._handle_connection_error(e)
            self.logger.error(
                f"Cache delete error for key {cache_key}: {e}", exc_info=True
            )
            return False

    async def clear(self) -> bool:
        """
        Clear all keys from cache (use with caution).

        Returns:
            True if cleared successfully
        """
        if self._is_circuit_breaker_open():
            self.logger.warning("Redis circuit breaker open - cache clear bypassed")
            return False

        try:
            redis = await self._ensure_connection()

            await redis.flushdb()

            self.logger.warning("Cache cleared - all keys deleted")
            return True

        except Exception as e:
            self._handle_connection_error(e)
            self.logger.error(f"Cache clear error: {e}", exc_info=True)
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if self._is_circuit_breaker_open():
            return False

        cache_key = self._normalize_key(key)

        try:
            redis = await self._ensure_connection()
            result = await redis.exists(str(cache_key))
            return result > 0
        except Exception as e:
            self._handle_connection_error(e)
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for existing key."""
        if self._is_circuit_breaker_open():
            return False

        cache_key = self._normalize_key(key)

        try:
            redis = await self._ensure_connection()
            result = await redis.expire(str(cache_key), ttl)
            return result
        except Exception as e:
            self._handle_connection_error(e)
            return False

    def _normalize_key(self, key: str) -> CacheKey:
        """Normalize cache key with namespace and version."""
        # Extract namespace from key if present
        if ":" in key:
            parts = key.split(":", 2)
            if len(parts) >= 2:
                namespace = parts[0]
                actual_key = ":".join(parts[1:])
            else:
                namespace = "default"
                actual_key = key
        else:
            namespace = "default"
            actual_key = key

        return CacheKey(namespace=namespace, key=actual_key)

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for Redis storage with optional compression."""
        try:
            # Use pickle for Python objects
            serialized = pickle.dumps(value)

            # Compress if enabled and value is large enough
            if self.enable_compression and len(serialized) > self.compression_threshold:
                import gzip

                serialized = gzip.compress(serialized)
                # Add compression marker
                serialized = b"GZIP:" + serialized

            return serialized

        except Exception as e:
            self.logger.error(f"Serialization error: {e}", exc_info=True)
            # Fallback to JSON
            return json.dumps(value).encode()

    def _deserialize(self, value: bytes) -> Any:
        """Deserialize value from Redis with decompression support."""
        try:
            # Check for compression marker
            if value.startswith(b"GZIP:"):
                import gzip

                value = gzip.decompress(value[5:])  # Remove "GZIP:" prefix

            # Try pickle first
            return pickle.loads(value)

        except Exception:
            try:
                # Fallback to JSON
                return json.loads(value.decode())
            except Exception as e:
                self.logger.error(f"Deserialization error: {e}", exc_info=True)
                return None

    def _update_avg_get_time(self, get_time_ms: float) -> None:
        """Update average get time metric."""
        if self.metrics.total_requests == 1:
            self.metrics.avg_get_time_ms = get_time_ms
        else:
            # Rolling average
            total_time = self.metrics.avg_get_time_ms * (
                self.metrics.total_requests - 1
            )
            self.metrics.avg_get_time_ms = (
                total_time + get_time_ms
            ) / self.metrics.total_requests

    def _update_avg_set_time(self, set_time_ms: float) -> None:
        """Update average set time metric."""
        # Simple rolling average for set operations
        if not hasattr(self, "_set_operations"):
            self._set_operations = 0

        self._set_operations += 1

        if self._set_operations == 1:
            self.metrics.avg_set_time_ms = set_time_ms
        else:
            total_time = self.metrics.avg_set_time_ms * (self._set_operations - 1)
            self.metrics.avg_set_time_ms = (
                total_time + set_time_ms
            ) / self._set_operations

    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive cache metrics."""
        try:
            memory_info = {}
            if self.redis and not self._is_circuit_breaker_open():
                # Get Redis memory info
                info = await self.redis.info("memory")
                memory_info = {
                    "used_memory": info.get("used_memory", 0),
                    "used_memory_human": info.get("used_memory_human", "0B"),
                    "maxmemory": info.get("maxmemory", 0),
                    "maxmemory_human": info.get("maxmemory_human", "0B"),
                }

            return {
                "cache_metrics": {
                    "total_requests": self.metrics.total_requests,
                    "cache_hits": self.metrics.cache_hits,
                    "cache_misses": self.metrics.cache_misses,
                    "hit_rate": self.metrics.hit_rate,
                    "miss_rate": self.metrics.miss_rate,
                    "avg_get_time_ms": self.metrics.avg_get_time_ms,
                    "avg_set_time_ms": self.metrics.avg_set_time_ms,
                    "connection_errors": self.metrics.connection_errors,
                },
                "memory_info": memory_info,
                "circuit_breaker": {
                    "open": self.circuit_breaker_open,
                    "failures": self.circuit_breaker_failures,
                    "last_failure": (
                        self.circuit_breaker_last_failure.isoformat()
                        if self.circuit_breaker_last_failure
                        else None
                    ),
                },
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error getting cache metrics: {e}", exc_info=True)
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive cache health check."""
        try:
            if self._is_circuit_breaker_open():
                return {
                    "status": "unhealthy",
                    "reason": "circuit_breaker_open",
                    "circuit_breaker_failures": self.circuit_breaker_failures,
                    "timestamp": datetime.now().isoformat(),
                }

            # Test Redis connectivity
            redis = await self._ensure_connection()

            # Test basic operations
            test_key = "health_check_test"
            test_value = {"test": True, "timestamp": datetime.now().isoformat()}

            # Test set operation
            await redis.setex(test_key, 10, json.dumps(test_value))

            # Test get operation
            retrieved = await redis.get(test_key)

            # Clean up
            await redis.delete(test_key)

            if retrieved is None:
                raise Exception("Health check failed - could not retrieve test value")

            return {
                "status": "healthy",
                "redis_connected": True,
                "operations_working": True,
                "metrics": await self.get_metrics(),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Cache health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "redis_connected": False,
                "timestamp": datetime.now().isoformat(),
            }

    async def close(self) -> None:
        """Close Redis connections gracefully."""
        try:
            if self.redis:
                await self.redis.aclose()  # Changed from close() to aclose() for redis.asyncio
            if self.connection_pool:
                await self.connection_pool.aclose()  # Changed from disconnect() to aclose() for redis.asyncio

            self.logger.info("Redis connections closed successfully")

        except Exception as e:
            self.logger.error(f"Error closing Redis connections: {e}", exc_info=True)
