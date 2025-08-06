"""
Multi-Layer Caching Strategy System
Comprehensive caching with Redis, in-memory, database query, and child-safe content caching
"""

import asyncio
import json
import pickle
import hashlib
import time
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import weakref

import redis.asyncio as redis
from cachetools import TTLCache, LRUCache
import msgpack

from src.core.exceptions import CacheError, ValidationError
from src.core.utils.crypto_utils import (
    encrypt_sensitive_data,
    decrypt_sensitive_data,
    hash_data,
)
from src.utils.date_utils import get_current_timestamp


logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheLevel(Enum):
    """Cache levels with different priorities and TTLs."""

    L1_MEMORY = "l1_memory"  # Fastest, smallest capacity
    L2_REDIS = "l2_redis"  # Fast, medium capacity, shared across instances
    L3_DATABASE = "l3_database"  # Slower, large capacity, persistent


class CacheStrategy(Enum):
    """Cache invalidation strategies."""

    TTL_BASED = "ttl_based"  # Time-based expiration
    EVENT_DRIVEN = "event_driven"  # Invalidate on specific events
    WRITE_THROUGH = "write_through"  # Update cache on write
    WRITE_BEHIND = "write_behind"  # Async cache update
    CHILD_SAFE = "child_safe"  # Special handling for child data


@dataclass
class CachePolicy:
    """Cache policy configuration."""

    name: str
    ttl_seconds: int
    max_size: Optional[int] = None
    strategy: CacheStrategy = CacheStrategy.TTL_BASED
    levels: List[CacheLevel] = field(
        default_factory=lambda: [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
    )
    child_safe: bool = False
    encrypt_data: bool = False
    compress_data: bool = True
    invalidation_tags: List[str] = field(default_factory=list)


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    cache_name: str
    level: CacheLevel
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0
    error_count: int = 0
    total_size_bytes: int = 0
    avg_get_time_ms: float = 0.0
    avg_set_time_ms: float = 0.0
    hit_ratio: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


class BaseCacheBackend(ABC, Generic[T]):
    """Base class for cache backends."""

    def __init__(self, name: str, policy: CachePolicy):
        self.name = name
        self.policy = policy
        self.metrics = CacheMetrics(cache_name=name, level=self.get_level())

    @abstractmethod
    async def get(self, key: str) -> Optional[T]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    def get_level(self) -> CacheLevel:
        """Get cache level."""
        pass

    async def get_metrics(self) -> CacheMetrics:
        """Get cache metrics."""
        if self.metrics.hit_count + self.metrics.miss_count > 0:
            self.metrics.hit_ratio = self.metrics.hit_count / (
                self.metrics.hit_count + self.metrics.miss_count
            )
        self.metrics.last_updated = datetime.now()
        return self.metrics

    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage."""
        if self.policy.compress_data:
            data = msgpack.packb(value, use_bin_type=True)
        else:
            data = pickle.dumps(value)

        if self.policy.encrypt_data:
            data = encrypt_sensitive_data(data.decode("latin-1")).encode("latin-1")

        return data

    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        if self.policy.encrypt_data:
            data = decrypt_sensitive_data(data.decode("latin-1")).encode("latin-1")

        if self.policy.compress_data:
            return msgpack.unpackb(data, raw=False)
        else:
            return pickle.loads(data)


class MemoryCacheBackend(BaseCacheBackend[T]):
    """In-memory cache backend using cachetools."""

    def __init__(self, name: str, policy: CachePolicy):
        super().__init__(name, policy)

        # Choose cache implementation based on policy
        cache_size = policy.max_size or 1000
        if policy.ttl_seconds > 0:
            self._cache = TTLCache(maxsize=cache_size, ttl=policy.ttl_seconds)
        else:
            self._cache = LRUCache(maxsize=cache_size)

        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        """Get value from memory cache."""
        start_time = time.time()

        try:
            async with self._lock:
                if key in self._cache:
                    value = self._cache[key]
                    self.metrics.hit_count += 1

                    # Handle child-safe data
                    if self.policy.child_safe and isinstance(value, dict):
                        # Validate child data hasn't expired beyond safety limits
                        if self._is_child_data_expired(value):
                            del self._cache[key]
                            self.metrics.miss_count += 1
                            return None

                    return value
                else:
                    self.metrics.miss_count += 1
                    return None
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Memory cache get error for key {key}: {e}")
            return None
        finally:
            self.metrics.avg_get_time_ms = (
                self.metrics.avg_get_time_ms * 0.9
                + (time.time() - start_time) * 1000 * 0.1
            )

    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        """Set value in memory cache."""
        start_time = time.time()

        try:
            async with self._lock:
                # Add child-safe metadata
                if self.policy.child_safe:
                    if isinstance(value, dict):
                        value["_child_safe_cached_at"] = get_current_timestamp()
                        value["_child_safe_ttl"] = ttl or self.policy.ttl_seconds

                self._cache[key] = value
                return True
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Memory cache set error for key {key}: {e}")
            return False
        finally:
            self.metrics.avg_set_time_ms = (
                self.metrics.avg_set_time_ms * 0.9
                + (time.time() - start_time) * 1000 * 0.1
            )

    async def delete(self, key: str) -> bool:
        """Delete key from memory cache."""
        try:
            async with self._lock:
                if key in self._cache:
                    del self._cache[key]
                    return True
                return False
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Memory cache delete error for key {key}: {e}")
            return False

    async def clear(self) -> bool:
        """Clear all memory cache entries."""
        try:
            async with self._lock:
                self._cache.clear()
                return True
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Memory cache clear error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in memory cache."""
        try:
            async with self._lock:
                return key in self._cache
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Memory cache exists error for key {key}: {e}")
            return False

    def get_level(self) -> CacheLevel:
        return CacheLevel.L1_MEMORY

    def _is_child_data_expired(self, value: dict) -> bool:
        """Check if child data has expired beyond safety limits."""
        if not isinstance(value, dict):
            return False

        cached_at = value.get("_child_safe_cached_at")
        ttl = value.get("_child_safe_ttl", self.policy.ttl_seconds)

        if cached_at and ttl:
            # Child data expires faster than regular data for safety
            child_safety_factor = 0.5  # 50% of normal TTL
            safe_ttl = ttl * child_safety_factor

            return (get_current_timestamp() - cached_at) > safe_ttl

        return False


class RedisCacheBackend(BaseCacheBackend[T]):
    """Redis cache backend."""

    def __init__(self, name: str, policy: CachePolicy, redis_client: redis.Redis):
        super().__init__(name, policy)
        self.redis_client = redis_client
        self.key_prefix = f"cache:{name}:"

    async def get(self, key: str) -> Optional[T]:
        """Get value from Redis cache."""
        start_time = time.time()

        try:
            redis_key = self.key_prefix + key
            data = await self.redis_client.get(redis_key)

            if data is not None:
                value = self._deserialize_value(data)
                self.metrics.hit_count += 1

                # Handle child-safe data
                if self.policy.child_safe and isinstance(value, dict):
                    if self._is_child_data_expired(value):
                        await self.redis_client.delete(redis_key)
                        self.metrics.miss_count += 1
                        return None

                return value
            else:
                self.metrics.miss_count += 1
                return None
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Redis cache get error for key {key}: {e}")
            return None
        finally:
            self.metrics.avg_get_time_ms = (
                self.metrics.avg_get_time_ms * 0.9
                + (time.time() - start_time) * 1000 * 0.1
            )

    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        """Set value in Redis cache."""
        start_time = time.time()

        try:
            redis_key = self.key_prefix + key

            # Add child-safe metadata
            if self.policy.child_safe and isinstance(value, dict):
                value["_child_safe_cached_at"] = get_current_timestamp()
                value["_child_safe_ttl"] = ttl or self.policy.ttl_seconds

            data = self._serialize_value(value)
            cache_ttl = ttl or self.policy.ttl_seconds

            if cache_ttl > 0:
                await self.redis_client.setex(redis_key, cache_ttl, data)
            else:
                await self.redis_client.set(redis_key, data)

            # Add to invalidation sets if needed
            for tag in self.policy.invalidation_tags:
                await self.redis_client.sadd(f"cache:tag:{tag}", redis_key)

            return True
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Redis cache set error for key {key}: {e}")
            return False
        finally:
            self.metrics.avg_set_time_ms = (
                self.metrics.avg_set_time_ms * 0.9
                + (time.time() - start_time) * 1000 * 0.1
            )

    async def delete(self, key: str) -> bool:
        """Delete key from Redis cache."""
        try:
            redis_key = self.key_prefix + key
            result = await self.redis_client.delete(redis_key)
            return result > 0
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Redis cache delete error for key {key}: {e}")
            return False

    async def clear(self) -> bool:
        """Clear all Redis cache entries for this cache."""
        try:
            pattern = self.key_prefix + "*"
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
            return True
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Redis cache clear error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis cache."""
        try:
            redis_key = self.key_prefix + key
            return await self.redis_client.exists(redis_key) > 0
        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Redis cache exists error for key {key}: {e}")
            return False

    def get_level(self) -> CacheLevel:
        return CacheLevel.L2_REDIS

    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a specific tag."""
        try:
            tag_key = f"cache:tag:{tag}"
            keys = await self.redis_client.smembers(tag_key)

            if keys:
                # Delete all keys with this tag
                await self.redis_client.delete(*keys)
                # Clear the tag set
                await self.redis_client.delete(tag_key)

                logger.info(f"Invalidated {len(keys)} cache entries with tag '{tag}'")
                return len(keys)

            return 0
        except Exception as e:
            logger.error(f"Tag invalidation error for tag {tag}: {e}")
            return 0

    def _is_child_data_expired(self, value: dict) -> bool:
        """Check if child data has expired beyond safety limits."""
        if not isinstance(value, dict):
            return False

        cached_at = value.get("_child_safe_cached_at")
        ttl = value.get("_child_safe_ttl", self.policy.ttl_seconds)

        if cached_at and ttl:
            # Child data expires faster for safety
            child_safety_factor = 0.5
            safe_ttl = ttl * child_safety_factor

            return (get_current_timestamp() - cached_at) > safe_ttl

        return False


class MultiLevelCache:
    """Multi-level cache with automatic promotion/demotion."""

    def __init__(
        self, name: str, policy: CachePolicy, redis_client: Optional[redis.Redis] = None
    ):
        self.name = name
        self.policy = policy
        self.backends: Dict[CacheLevel, BaseCacheBackend] = {}

        # Initialize backends based on policy levels
        for level in policy.levels:
            if level == CacheLevel.L1_MEMORY:
                self.backends[level] = MemoryCacheBackend(f"{name}_l1", policy)
            elif level == CacheLevel.L2_REDIS and redis_client:
                self.backends[level] = RedisCacheBackend(
                    f"{name}_l2", policy, redis_client
                )

        self.metrics_history = []

    async def get(self, key: str) -> Optional[T]:
        """Get value from cache with automatic promotion."""
        # Try each level in order
        for level in self.policy.levels:
            if level not in self.backends:
                continue

            backend = self.backends[level]
            value = await backend.get(key)

            if value is not None:
                # Promote to higher levels
                await self._promote_to_higher_levels(key, value, level)
                return value

        return None

    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        """Set value in all configured cache levels."""
        results = []

        for level in self.policy.levels:
            if level not in self.backends:
                continue

            backend = self.backends[level]
            result = await backend.set(key, value, ttl)
            results.append(result)

        return any(results)  # Success if at least one backend succeeded

    async def delete(self, key: str) -> bool:
        """Delete key from all cache levels."""
        results = []

        for level in self.policy.levels:
            if level not in self.backends:
                continue

            backend = self.backends[level]
            result = await backend.delete(key)
            results.append(result)

        return any(results)

    async def clear(self) -> bool:
        """Clear all cache levels."""
        results = []

        for backend in self.backends.values():
            result = await backend.clear()
            results.append(result)

        return all(results)

    async def exists(self, key: str) -> bool:
        """Check if key exists in any cache level."""
        for level in self.policy.levels:
            if level not in self.backends:
                continue

            backend = self.backends[level]
            if await backend.exists(key):
                return True

        return False

    async def _promote_to_higher_levels(
        self, key: str, value: T, found_level: CacheLevel
    ) -> None:
        """Promote cache entry to higher levels."""
        found_index = self.policy.levels.index(found_level)

        # Promote to all higher levels
        for i in range(found_index):
            level = self.policy.levels[i]
            if level in self.backends:
                await self.backends[level].set(key, value)

    async def get_metrics(self) -> Dict[CacheLevel, CacheMetrics]:
        """Get metrics from all cache levels."""
        metrics = {}

        for level, backend in self.backends.items():
            metrics[level] = await backend.get_metrics()

        return metrics

    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate cache entries by tag across all levels."""
        total_invalidated = 0

        for backend in self.backends.values():
            if hasattr(backend, "invalidate_by_tag"):
                count = await backend.invalidate_by_tag(tag)
                total_invalidated += count

        return total_invalidated


class CacheManager:
    """Main cache management system."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.caches: Dict[str, MultiLevelCache] = {}
        self.policies: Dict[str, CachePolicy] = {}

        # Initialize default policies
        self._initialize_default_policies()

    def _initialize_default_policies(self) -> None:
        """Initialize default cache policies for different content types."""

        # API response caching
        self.policies["api_responses"] = CachePolicy(
            name="api_responses",
            ttl_seconds=300,  # 5 minutes
            max_size=1000,
            strategy=CacheStrategy.TTL_BASED,
            levels=[CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
            child_safe=False,
            compress_data=True,
        )

        # Child data caching (special handling)
        self.policies["child_data"] = CachePolicy(
            name="child_data",
            ttl_seconds=600,  # 10 minutes
            max_size=500,
            strategy=CacheStrategy.CHILD_SAFE,
            levels=[CacheLevel.L1_MEMORY],  # Only memory cache for sensitivity
            child_safe=True,
            encrypt_data=True,
            compress_data=True,
            invalidation_tags=["child_data", "privacy"],
        )

        # Database query caching
        self.policies["db_queries"] = CachePolicy(
            name="db_queries",
            ttl_seconds=1800,  # 30 minutes
            max_size=2000,
            strategy=CacheStrategy.TTL_BASED,
            levels=[CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
            compress_data=True,
            invalidation_tags=["database"],
        )

        # TTS audio caching
        self.policies["tts_audio"] = CachePolicy(
            name="tts_audio",
            ttl_seconds=3600,  # 1 hour
            max_size=100,  # Audio files are large
            strategy=CacheStrategy.TTL_BASED,
            levels=[CacheLevel.L2_REDIS],  # Redis only for large files
            child_safe=True,
            compress_data=True,
            invalidation_tags=["tts", "audio"],
        )

        # Static file caching
        self.policies["static_files"] = CachePolicy(
            name="static_files",
            ttl_seconds=86400,  # 24 hours
            max_size=5000,
            strategy=CacheStrategy.TTL_BASED,
            levels=[CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
            compress_data=True,
        )

        # Session data caching
        self.policies["sessions"] = CachePolicy(
            name="sessions",
            ttl_seconds=1800,  # 30 minutes
            max_size=1000,
            strategy=CacheStrategy.TTL_BASED,
            levels=[CacheLevel.L2_REDIS],  # Redis for shared sessions
            child_safe=True,
            encrypt_data=True,
            invalidation_tags=["sessions", "auth"],
        )

    def get_cache(
        self, cache_name: str, policy_name: Optional[str] = None
    ) -> MultiLevelCache:
        """Get or create a cache instance."""
        if cache_name not in self.caches:
            # Use provided policy or default to cache name
            policy_key = policy_name or cache_name

            if policy_key not in self.policies:
                # Create default policy
                self.policies[policy_key] = CachePolicy(
                    name=policy_key,
                    ttl_seconds=600,
                    max_size=1000,
                    levels=(
                        [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
                        if self.redis_client
                        else [CacheLevel.L1_MEMORY]
                    ),
                )

            policy = self.policies[policy_key]
            self.caches[cache_name] = MultiLevelCache(
                cache_name, policy, self.redis_client
            )

        return self.caches[cache_name]

    async def cached(
        self,
        cache_name: str,
        key: str,
        func: Callable,
        ttl: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """Decorator-like function for caching function results."""
        cache = self.get_cache(cache_name)

        # Try to get from cache first
        cached_value = await cache.get(key)
        if cached_value is not None:
            return cached_value

        # Execute function and cache result
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = func(**kwargs)

            await cache.set(key, result, ttl)
            return result
        except Exception as e:
            logger.error(f"Error executing cached function for key {key}: {e}")
            raise

    async def invalidate_child_data(self, child_id: str) -> Dict[str, int]:
        """Invalidate all child-related data across all caches."""
        results = {}

        # Clear specific child data
        child_cache = self.get_cache("child_data")
        child_pattern_keys = [
            f"child:{child_id}:*",
            f"profile:{child_id}",
            f"conversations:{child_id}:*",
            f"preferences:{child_id}",
        ]

        for pattern in child_pattern_keys:
            await child_cache.delete(pattern)

        # Invalidate by tags
        for cache_name, cache in self.caches.items():
            if hasattr(cache, "invalidate_by_tag"):
                count = await cache.invalidate_by_tag(f"child:{child_id}")
                if count > 0:
                    results[cache_name] = count

        # Log for compliance
        logger.info(
            f"Child data invalidation completed for child_id: {child_id}",
            extra={
                "child_id": child_id,
                "caches_affected": list(results.keys()),
                "total_entries_cleared": sum(results.values()),
                "compliance": "COPPA",
            },
        )

        return results

    async def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive caching metrics across all caches."""
        all_metrics = {}
        total_hits = 0
        total_misses = 0
        total_errors = 0

        for cache_name, cache in self.caches.items():
            cache_metrics = await cache.get_metrics()
            all_metrics[cache_name] = {}

            for level, metrics in cache_metrics.items():
                all_metrics[cache_name][level.value] = {
                    "hit_count": metrics.hit_count,
                    "miss_count": metrics.miss_count,
                    "hit_ratio": metrics.hit_ratio,
                    "error_count": metrics.error_count,
                    "avg_get_time_ms": metrics.avg_get_time_ms,
                    "avg_set_time_ms": metrics.avg_set_time_ms,
                    "total_size_bytes": metrics.total_size_bytes,
                }

                total_hits += metrics.hit_count
                total_misses += metrics.miss_count
                total_errors += metrics.error_count

        overall_hit_ratio = (
            total_hits / (total_hits + total_misses)
            if (total_hits + total_misses) > 0
            else 0.0
        )

        return {
            "overall": {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "overall_hit_ratio": overall_hit_ratio,
                "total_errors": total_errors,
                "total_caches": len(self.caches),
            },
            "by_cache": all_metrics,
            "policies": {
                name: {
                    "ttl_seconds": policy.ttl_seconds,
                    "max_size": policy.max_size,
                    "child_safe": policy.child_safe,
                    "encrypt_data": policy.encrypt_data,
                    "levels": [level.value for level in policy.levels],
                }
                for name, policy in self.policies.items()
            },
        }

    async def warm_cache(self, cache_name: str, data_loader: Callable) -> int:
        """Warm up cache with pre-loaded data."""
        cache = self.get_cache(cache_name)
        count = 0

        try:
            if asyncio.iscoroutinefunction(data_loader):
                data_items = await data_loader()
            else:
                data_items = data_loader()

            for key, value in data_items.items():
                await cache.set(key, value)
                count += 1

            logger.info(
                f"Cache warming completed for {cache_name}: {count} items loaded"
            )
            return count

        except Exception as e:
            logger.error(f"Cache warming failed for {cache_name}: {e}")
            return count

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for all caching systems."""
        health_status = {
            "overall_status": "healthy",
            "redis_status": "unknown",
            "memory_caches": 0,
            "redis_caches": 0,
            "total_caches": len(self.caches),
            "issues": [],
        }

        # Test Redis connection
        if self.redis_client:
            try:
                await self.redis_client.ping()
                health_status["redis_status"] = "healthy"
            except Exception as e:
                health_status["redis_status"] = "unhealthy"
                health_status["issues"].append(f"Redis connection failed: {e}")

        # Check individual caches
        for cache_name, cache in self.caches.items():
            try:
                metrics = await cache.get_metrics()

                for level, level_metrics in metrics.items():
                    if level == CacheLevel.L1_MEMORY:
                        health_status["memory_caches"] += 1
                    elif level == CacheLevel.L2_REDIS:
                        health_status["redis_caches"] += 1

                    # Check for high error rates
                    total_ops = level_metrics.hit_count + level_metrics.miss_count
                    if total_ops > 0:
                        error_rate = level_metrics.error_count / total_ops
                        if error_rate > 0.05:  # More than 5% error rate
                            health_status["issues"].append(
                                f"High error rate in {cache_name}:{level.value}: {error_rate:.2%}"
                            )
            except Exception as e:
                health_status["issues"].append(
                    f"Health check failed for cache {cache_name}: {e}"
                )

        if health_status["issues"]:
            health_status["overall_status"] = "degraded"

        return health_status


# Factory function for easy initialization
def create_cache_manager(redis_url: Optional[str] = None) -> CacheManager:
    """Create cache manager with optional Redis connection."""
    redis_client = None

    if redis_url:
        try:
            redis_client = redis.from_url(redis_url)
            logger.info("Cache manager initialized with Redis backend")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client: {e}")
            logger.info("Cache manager initialized with memory-only caching")

    return CacheManager(redis_client)
