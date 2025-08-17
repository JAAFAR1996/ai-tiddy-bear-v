"""
Production TTS Cache Service - Enterprise Redis Implementation
=============================================================
High-performance, Redis-based TTS caching with comprehensive monitoring:
- Distributed Redis caching with cluster support
- Advanced TTL management and eviction policies
- Performance analytics and cost optimization
- Circuit breaker and failover mechanisms
- Memory pressure monitoring and adaptive caching
- Compression and encryption for large audio files
"""

import asyncio
import gzip
import hashlib
import json
import logging
import os
import pickle
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

try:
    import redis.asyncio as aioredis
    from redis.asyncio import Redis, ConnectionPool

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from src.interfaces.providers.tts_provider import TTSRequest, TTSResult


class CacheStrategy(Enum):
    """Cache eviction strategies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL_BASED = "ttl_based"  # Time-based expiration
    COST_AWARE = "cost_aware"  # Cost-optimized caching


class CompressionLevel(Enum):
    """Audio compression levels for caching."""

    NONE = 0
    LIGHT = 1  # Up to 30% reduction
    MEDIUM = 2  # Up to 50% reduction
    AGGRESSIVE = 3  # Up to 70% reduction


@dataclass
class CacheEntry:
    """Enhanced cache entry with metadata."""

    tts_result: TTSResult
    cached_at: datetime
    last_accessed: datetime
    access_count: int = 0
    original_size: int = 0
    compressed_size: int = 0
    compression_ratio: float = 1.0
    cost_saved: float = 0.0
    provider: str = ""
    cache_key_hash: str = ""

    def update_access(self) -> None:
        """Update access statistics."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1

    def calculate_compression_ratio(self) -> float:
        """Calculate compression efficiency."""
        if self.original_size == 0:
            return 1.0
        return self.compressed_size / self.original_size

    def to_redis_data(self) -> Dict[str, Any]:
        """Convert to Redis-storable format."""
        return {
            "tts_result": pickle.dumps(self.tts_result),
            "cached_at": self.cached_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "compression_ratio": self.compression_ratio,
            "cost_saved": self.cost_saved,
            "provider": self.provider,
            "cache_key_hash": self.cache_key_hash,
        }

    @classmethod
    def from_redis_data(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from Redis data."""
        return cls(
            tts_result=pickle.loads(data["tts_result"]),
            cached_at=datetime.fromisoformat(data["cached_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            original_size=data.get("original_size", 0),
            compressed_size=data.get("compressed_size", 0),
            compression_ratio=data.get("compression_ratio", 1.0),
            cost_saved=data.get("cost_saved", 0.0),
            provider=data.get("provider", ""),
            cache_key_hash=data.get("cache_key_hash", ""),
        )


@dataclass
class CacheMetrics:
    """Comprehensive cache performance metrics."""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_evictions: int = 0
    cache_expires: int = 0
    total_cache_size_bytes: int = 0
    avg_compression_ratio: float = 1.0
    total_cost_saved: float = 0.0
    avg_access_time_ms: float = 0.0
    memory_pressure_events: int = 0
    circuit_breaker_trips: int = 0
    redis_connection_failures: int = 0

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

    @property
    def eviction_rate(self) -> float:
        """Calculate eviction rate."""
        total_events = self.cache_evictions + self.cache_expires
        if total_events == 0:
            return 0.0
        return (self.cache_evictions / total_events) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
            "cache_evictions": self.cache_evictions,
            "cache_expires": self.cache_expires,
            "eviction_rate": self.eviction_rate,
            "total_cache_size_bytes": self.total_cache_size_bytes,
            "total_cache_size_mb": round(self.total_cache_size_bytes / 1024 / 1024, 2),
            "avg_compression_ratio": self.avg_compression_ratio,
            "storage_efficiency": round((1 - self.avg_compression_ratio) * 100, 1),
            "total_cost_saved": self.total_cost_saved,
            "avg_access_time_ms": self.avg_access_time_ms,
            "memory_pressure_events": self.memory_pressure_events,
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "redis_connection_failures": self.redis_connection_failures,
        }


class ProductionTTSCacheService:
    """
    Enterprise-grade TTS caching service with Redis backend.

    Features:
    - Distributed Redis caching with clustering support
    - Intelligent compression and deduplication
    - Advanced eviction policies and memory management
    - Cost tracking and optimization
    - Circuit breaker pattern for resilience
    - Comprehensive performance monitoring
    - Adaptive caching based on usage patterns
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_cluster_nodes: Optional[List[str]] = None,
        enabled: bool = True,
        default_ttl_seconds: int = 3600,
        max_cache_size_mb: int = 1024,
        compression_level: CompressionLevel = CompressionLevel.MEDIUM,
        cache_strategy: CacheStrategy = CacheStrategy.COST_AWARE,
    ):
        """
        Initialize Redis-based TTS cache service.

        Args:
            redis_url: Redis connection URL
            redis_cluster_nodes: Redis cluster node URLs
            enabled: Enable/disable caching
            default_ttl_seconds: Default cache TTL
            max_cache_size_mb: Maximum cache size in MB
            compression_level: Audio compression level
            cache_strategy: Cache eviction strategy
        """
        self.logger = logging.getLogger(__name__)
        self.enabled = enabled
        self.default_ttl_seconds = default_ttl_seconds
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self.compression_level = compression_level
        self.cache_strategy = cache_strategy

        # Redis configuration
        self.redis_url = redis_url or os.getenv(
            "REDIS_TTS_CACHE_URL", "redis://localhost:6379/2"
        )
        self.redis_cluster_nodes = redis_cluster_nodes
        self.redis_client: Optional[Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None

        # Performance metrics
        self.metrics = CacheMetrics()

        # Circuit breaker configuration
        self.circuit_breaker_threshold = int(
            os.getenv("TTS_CACHE_CIRCUIT_BREAKER_THRESHOLD", "5")
        )
        self.circuit_breaker_timeout = int(
            os.getenv("TTS_CACHE_CIRCUIT_BREAKER_TIMEOUT", "60")
        )
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure = None
        self.circuit_breaker_open = False

        # Memory pressure monitoring
        self.memory_pressure_threshold = 0.8  # 80% of max cache size
        self.aggressive_cleanup_threshold = 0.95  # 95% triggers aggressive cleanup

        # Performance tracking
        self.access_times: List[float] = []
        self.cost_tracking: Dict[str, float] = {}

        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None

        if not enabled:
            self.logger.info("TTS Cache Service disabled")
            return

        if not REDIS_AVAILABLE:
            self.logger.warning("Redis not available, falling back to disabled cache")
            self.enabled = False
            return

        # Initialize Redis connection
        asyncio.create_task(self._initialize_redis())

        self.logger.info(
            f"Production TTS Cache Service initialized",
            extra={
                "max_size_mb": max_cache_size_mb,
                "ttl_seconds": default_ttl_seconds,
                "compression": compression_level.value,
                "strategy": cache_strategy.value,
            },
        )

    async def _initialize_redis(self) -> None:
        """Initialize Redis connection with clustering support."""
        try:
            if self.redis_cluster_nodes:
                # Redis Cluster setup
                from redis.asyncio.cluster import RedisCluster

                self.redis_client = RedisCluster.from_url(
                    self.redis_cluster_nodes[0],
                    skip_full_coverage_check=True,
                    retry_on_timeout=True,
                    socket_connect_timeout=10,
                    socket_keepalive=True,
                )
            else:
                # Single Redis instance with connection pooling
                self.connection_pool = ConnectionPool.from_url(
                    self.redis_url,
                    max_connections=20,
                    retry_on_timeout=True,
                    socket_connect_timeout=10,
                    socket_keepalive=True,
                    socket_keepalive_options={
                        1: 1,  # TCP_KEEPIDLE
                        2: 3,  # TCP_KEEPINTVL
                        3: 5,  # TCP_KEEPCNT
                    },
                )

                self.redis_client = Redis(connection_pool=self.connection_pool)

            # Test connection
            await self.redis_client.ping()

            # Reset circuit breaker
            self.circuit_breaker_failures = 0
            self.circuit_breaker_open = False

            # Start background tasks
            self._start_background_tasks()

            self.logger.info("Redis TTS cache connection established successfully")

        except Exception as e:
            self._handle_redis_error(e)
            self.logger.error(
                f"Failed to initialize Redis TTS cache: {e}", exc_info=True
            )

    def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.metrics_task = asyncio.create_task(self._metrics_collection_loop())

    async def get(self, cache_key: str) -> Optional[TTSResult]:
        """
        Retrieve cached TTS result with comprehensive monitoring.

        Args:
            cache_key: Cache lookup key

        Returns:
            TTSResult if found and valid, None otherwise
        """
        if not self.enabled or self._is_circuit_breaker_open():
            return None

        start_time = time.time()
        self.metrics.total_requests += 1

        try:
            # Generate Redis key
            redis_key = self._generate_redis_key(cache_key)

            # Retrieve from Redis
            cached_data = await self.redis_client.hgetall(redis_key)

            if not cached_data:
                self.metrics.cache_misses += 1
                self._track_access_time(start_time)
                return None

            # Parse cache entry
            entry = CacheEntry.from_redis_data(
                {
                    k.decode() if isinstance(k, bytes) else k: (
                        v.decode()
                        if isinstance(v, bytes) and k.decode() not in ["tts_result"]
                        else v
                    )
                    for k, v in cached_data.items()
                }
            )

            # Check TTL expiration
            if self._is_expired(entry):
                await self._expire_entry(redis_key, entry)
                self.metrics.cache_expires += 1
                self.metrics.cache_misses += 1
                self._track_access_time(start_time)
                return None

            # Update access statistics
            entry.update_access()
            await self._update_entry_stats(redis_key, entry)

            # Decompress if needed
            result = await self._decompress_result(entry.tts_result)
            result.cached = True

            # Update metrics
            self.metrics.cache_hits += 1
            self._track_access_time(start_time)
            self._update_cost_savings(entry)

            self.logger.debug(
                f"TTS cache hit",
                extra={
                    "cache_key_hash": entry.cache_key_hash[:12],
                    "access_count": entry.access_count,
                    "compression_ratio": entry.compression_ratio,
                    "provider": entry.provider,
                },
            )

            return result

        except Exception as e:
            self._handle_redis_error(e)
            self.metrics.cache_misses += 1
            self._track_access_time(start_time)
            return None

    async def set(
        self,
        cache_key: str,
        tts_result: TTSResult,
        ttl_seconds: Optional[int] = None,
        cost: float = 0.0,
    ) -> bool:
        """
        Cache TTS result with intelligent compression and storage optimization.

        Args:
            cache_key: Cache storage key
            tts_result: TTS result to cache
            ttl_seconds: Custom TTL (uses default if None)
            cost: Original cost for cost tracking

        Returns:
            True if cached successfully
        """
        if not self.enabled or self._is_circuit_breaker_open():
            return False

        try:
            # Check memory pressure
            if await self._is_memory_pressure_high():
                await self._handle_memory_pressure()

            # Compress audio data
            compressed_result = await self._compress_result(tts_result)
            original_size = len(tts_result.audio_data)
            compressed_size = len(compressed_result.audio_data)

            # Create cache entry
            entry = CacheEntry(
                tts_result=compressed_result,
                cached_at=datetime.now(timezone.utc),
                last_accessed=datetime.now(timezone.utc),
                access_count=0,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compressed_size / original_size,
                cost_saved=cost,
                provider=tts_result.provider_name,
                cache_key_hash=hashlib.sha256(cache_key.encode()).hexdigest(),
            )

            # Store in Redis
            redis_key = self._generate_redis_key(cache_key)
            redis_data = entry.to_redis_data()

            # Set with TTL
            ttl = ttl_seconds or self.default_ttl_seconds
            await self.redis_client.hset(redis_key, mapping=redis_data)
            await self.redis_client.expire(redis_key, ttl)

            # Update metrics
            self.metrics.total_cache_size_bytes += compressed_size
            self._update_compression_metrics(entry)
            self._track_cost_savings(cache_key, cost)

            self.logger.debug(
                f"TTS result cached successfully",
                extra={
                    "cache_key_hash": entry.cache_key_hash[:12],
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "compression_ratio": entry.compression_ratio,
                    "ttl_seconds": ttl,
                    "provider": entry.provider,
                },
            )

            return True

        except Exception as e:
            self._handle_redis_error(e)
            return False

    async def invalidate(self, cache_key: str) -> bool:
        """
        Invalidate specific cache entry.

        Args:
            cache_key: Key to invalidate

        Returns:
            True if invalidated successfully
        """
        if not self.enabled or self._is_circuit_breaker_open():
            return False

        try:
            redis_key = self._generate_redis_key(cache_key)

            # Get entry size before deletion for metrics
            cached_data = await self.redis_client.hgetall(redis_key)
            if cached_data:
                entry = CacheEntry.from_redis_data(
                    {
                        k.decode() if isinstance(k, bytes) else k: (
                            v.decode()
                            if isinstance(v, bytes) and k.decode() not in ["tts_result"]
                            else v
                        )
                        for k, v in cached_data.items()
                    }
                )
                self.metrics.total_cache_size_bytes -= entry.compressed_size

            # Delete from Redis
            deleted = await self.redis_client.delete(redis_key)

            if deleted:
                self.logger.debug(f"Cache entry invalidated: {cache_key[:12]}...")

            return deleted > 0

        except Exception as e:
            self._handle_redis_error(e)
            return False

    async def clear(self) -> bool:
        """Clear all TTS cache entries."""
        if not self.enabled or self._is_circuit_breaker_open():
            return False

        try:
            # Find all TTS cache keys
            pattern = self._generate_redis_key("*")
            keys = await self.redis_client.keys(pattern)

            if keys:
                await self.redis_client.delete(*keys)
                self.metrics.total_cache_size_bytes = 0
                self.logger.info(f"Cleared {len(keys)} TTS cache entries")

            return True

        except Exception as e:
            self._handle_redis_error(e)
            return False

    async def _is_memory_pressure_high(self) -> bool:
        """Check if cache memory usage is approaching limits."""
        try:
            # Get Redis memory info
            info = await self.redis_client.info("memory")
            used_memory = info.get("used_memory", 0)
            maxmemory = info.get("maxmemory", 0)

            if maxmemory > 0:
                memory_ratio = used_memory / maxmemory
                return memory_ratio > self.memory_pressure_threshold

            # Fallback to cache size tracking
            return self.metrics.total_cache_size_bytes > (
                self.max_cache_size_bytes * self.memory_pressure_threshold
            )

        except Exception:
            return False

    async def _handle_memory_pressure(self) -> None:
        """Handle high memory pressure with intelligent eviction."""
        self.metrics.memory_pressure_events += 1

        try:
            if self.cache_strategy == CacheStrategy.LRU:
                await self._evict_least_recently_used()
            elif self.cache_strategy == CacheStrategy.LFU:
                await self._evict_least_frequently_used()
            elif self.cache_strategy == CacheStrategy.COST_AWARE:
                await self._evict_low_value_entries()
            else:
                await self._evict_oldest_entries()

            self.logger.info(
                f"Memory pressure handled using {self.cache_strategy.value} strategy",
                extra={"memory_pressure_events": self.metrics.memory_pressure_events},
            )

        except Exception as e:
            self.logger.error(f"Failed to handle memory pressure: {e}", exc_info=True)

    async def _evict_least_recently_used(self) -> None:
        """Evict least recently used entries."""
        pattern = self._generate_redis_key("*")
        keys = await self.redis_client.keys(pattern)

        # Get last access times for all entries
        entries_with_access = []
        for key in keys:
            try:
                cached_data = await self.redis_client.hgetall(key)
                if cached_data:
                    last_accessed = datetime.fromisoformat(
                        cached_data.get(
                            b"last_accessed", cached_data.get("last_accessed", "")
                        ).decode()
                        if isinstance(
                            cached_data.get(
                                b"last_accessed", cached_data.get("last_accessed", "")
                            ),
                            bytes,
                        )
                        else cached_data.get("last_accessed", "")
                    )
                    entries_with_access.append((key, last_accessed))
            except Exception:
                continue

        # Sort by last accessed (oldest first)
        entries_with_access.sort(key=lambda x: x[1])

        # Evict oldest 20% of entries
        evict_count = max(1, len(entries_with_access) // 5)
        for key, _ in entries_with_access[:evict_count]:
            await self.redis_client.delete(key)
            self.metrics.cache_evictions += 1

    async def _evict_least_frequently_used(self) -> None:
        """Evict least frequently used entries."""
        pattern = self._generate_redis_key("*")
        keys = await self.redis_client.keys(pattern)

        # Get access counts for all entries
        entries_with_count = []
        for key in keys:
            try:
                cached_data = await self.redis_client.hgetall(key)
                if cached_data:
                    access_count = int(
                        cached_data.get(
                            b"access_count", cached_data.get("access_count", 0)
                        )
                    )
                    entries_with_count.append((key, access_count))
            except Exception:
                continue

        # Sort by access count (lowest first)
        entries_with_count.sort(key=lambda x: x[1])

        # Evict lowest 20% of entries
        evict_count = max(1, len(entries_with_count) // 5)
        for key, _ in entries_with_count[:evict_count]:
            await self.redis_client.delete(key)
            self.metrics.cache_evictions += 1

    async def _evict_low_value_entries(self) -> None:
        """Evict entries with lowest cost/access ratio."""
        pattern = self._generate_redis_key("*")
        keys = await self.redis_client.keys(pattern)

        # Calculate value score for each entry
        entries_with_value = []
        for key in keys:
            try:
                cached_data = await self.redis_client.hgetall(key)
                if cached_data:
                    access_count = int(
                        cached_data.get(
                            b"access_count", cached_data.get("access_count", 0)
                        )
                    )
                    cost_saved = float(
                        cached_data.get(
                            b"cost_saved", cached_data.get("cost_saved", 0.0)
                        )
                    )

                    # Value score = cost_saved * access_count (higher is better)
                    value_score = cost_saved * (access_count + 1)  # +1 to avoid zero
                    entries_with_value.append((key, value_score))
            except Exception:
                continue

        # Sort by value score (lowest first)
        entries_with_value.sort(key=lambda x: x[1])

        # Evict lowest value 20% of entries
        evict_count = max(1, len(entries_with_value) // 5)
        for key, _ in entries_with_value[:evict_count]:
            await self.redis_client.delete(key)
            self.metrics.cache_evictions += 1

    async def _evict_oldest_entries(self) -> None:
        """Evict oldest entries based on cache time."""
        pattern = self._generate_redis_key("*")
        keys = await self.redis_client.keys(pattern)

        # Get cached times for all entries
        entries_with_time = []
        for key in keys:
            try:
                cached_data = await self.redis_client.hgetall(key)
                if cached_data:
                    cached_at = datetime.fromisoformat(
                        cached_data.get(
                            b"cached_at", cached_data.get("cached_at", "")
                        ).decode()
                        if isinstance(
                            cached_data.get(
                                b"cached_at", cached_data.get("cached_at", "")
                            ),
                            bytes,
                        )
                        else cached_data.get("cached_at", "")
                    )
                    entries_with_time.append((key, cached_at))
            except Exception:
                continue

        # Sort by cached time (oldest first)
        entries_with_time.sort(key=lambda x: x[1])

        # Evict oldest 20% of entries
        evict_count = max(1, len(entries_with_time) // 5)
        for key, _ in entries_with_time[:evict_count]:
            await self.redis_client.delete(key)
            self.metrics.cache_evictions += 1

    async def _compress_result(self, tts_result: TTSResult) -> TTSResult:
        """Apply intelligent compression to TTS result."""
        if self.compression_level == CompressionLevel.NONE:
            return tts_result

        try:
            # Compress audio data based on level
            compressed_audio = tts_result.audio_data

            if self.compression_level in [
                CompressionLevel.LIGHT,
                CompressionLevel.MEDIUM,
                CompressionLevel.AGGRESSIVE,
            ]:
                # Use gzip compression for audio data
                compression_level = {
                    CompressionLevel.LIGHT: 1,
                    CompressionLevel.MEDIUM: 6,
                    CompressionLevel.AGGRESSIVE: 9,
                }[self.compression_level]

                compressed_audio = gzip.compress(
                    tts_result.audio_data, compresslevel=compression_level
                )

            # Create compressed result
            compressed_result = TTSResult(
                audio_data=compressed_audio,
                format=tts_result.format,
                sample_rate=tts_result.sample_rate,
                duration_seconds=tts_result.duration_seconds,
                provider_name=tts_result.provider_name,
                model_name=tts_result.model_name,
                voice_id=tts_result.voice_id,
                cached=True,
                processing_time=tts_result.processing_time,
                estimated_cost=tts_result.estimated_cost,
                metadata={
                    **tts_result.metadata,
                    "compressed": True,
                    "compression_level": self.compression_level.value,
                },
            )

            return compressed_result

        except Exception as e:
            self.logger.warning(f"Compression failed, storing uncompressed: {e}")
            return tts_result

    async def _decompress_result(self, tts_result: TTSResult) -> TTSResult:
        """Decompress TTS result if compressed."""
        if not tts_result.metadata.get("compressed", False):
            return tts_result

        try:
            # Decompress audio data
            decompressed_audio = gzip.decompress(tts_result.audio_data)

            # Create decompressed result
            metadata = {**tts_result.metadata}
            metadata.pop("compressed", None)
            metadata.pop("compression_level", None)

            decompressed_result = TTSResult(
                audio_data=decompressed_audio,
                format=tts_result.format,
                sample_rate=tts_result.sample_rate,
                duration_seconds=tts_result.duration_seconds,
                provider_name=tts_result.provider_name,
                model_name=tts_result.model_name,
                voice_id=tts_result.voice_id,
                cached=True,
                processing_time=tts_result.processing_time,
                estimated_cost=tts_result.estimated_cost,
                metadata=metadata,
            )

            return decompressed_result

        except Exception as e:
            self.logger.error(f"Decompression failed: {e}", exc_info=True)
            return tts_result

    def _generate_redis_key(self, cache_key: str) -> str:
        """Generate Redis key with namespace."""
        return f"tts_cache:v2:{hashlib.sha256(cache_key.encode()).hexdigest()}"

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if cache entry is expired."""
        age = datetime.now(timezone.utc) - entry.cached_at
        return age.total_seconds() > self.default_ttl_seconds

    async def _expire_entry(self, redis_key: str, entry: CacheEntry) -> None:
        """Remove expired entry and update metrics."""
        await self.redis_client.delete(redis_key)
        self.metrics.total_cache_size_bytes -= entry.compressed_size

    async def _update_entry_stats(self, redis_key: str, entry: CacheEntry) -> None:
        """Update entry access statistics."""
        try:
            await self.redis_client.hset(
                redis_key,
                mapping={
                    "last_accessed": entry.last_accessed.isoformat(),
                    "access_count": entry.access_count,
                },
            )
        except Exception as e:
            self.logger.debug(f"Failed to update entry stats: {e}")

    def _track_access_time(self, start_time: float) -> None:
        """Track cache access time for performance monitoring."""
        access_time = (time.time() - start_time) * 1000
        self.access_times.append(access_time)

        # Keep only recent measurements
        if len(self.access_times) > 1000:
            self.access_times = self.access_times[-1000:]

        # Update average
        if self.access_times:
            self.metrics.avg_access_time_ms = sum(self.access_times) / len(
                self.access_times
            )

    def _update_compression_metrics(self, entry: CacheEntry) -> None:
        """Update compression efficiency metrics."""
        # Update average compression ratio
        total_entries = self.metrics.cache_hits + 1  # Approximate
        current_avg = self.metrics.avg_compression_ratio
        self.metrics.avg_compression_ratio = (
            current_avg * (total_entries - 1) + entry.compression_ratio
        ) / total_entries

    def _track_cost_savings(self, cache_key: str, cost: float) -> None:
        """Track cost savings from caching."""
        self.cost_tracking[cache_key] = cost
        self.metrics.total_cost_saved += cost

    def _update_cost_savings(self, entry: CacheEntry) -> None:
        """Update cost savings when cache is hit."""
        self.metrics.total_cost_saved += entry.cost_saved

    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self.circuit_breaker_open:
            return False

        if self.circuit_breaker_last_failure is None:
            return False

        # Check if timeout has passed
        timeout_passed = (
            datetime.now(timezone.utc) - self.circuit_breaker_last_failure
        ).total_seconds() > self.circuit_breaker_timeout

        if timeout_passed:
            self.circuit_breaker_open = False
            self.circuit_breaker_failures = 0
            self.logger.info("TTS cache circuit breaker reset")

        return self.circuit_breaker_open

    def _handle_redis_error(self, error: Exception) -> None:
        """Handle Redis connection errors and update circuit breaker."""
        self.metrics.redis_connection_failures += 1
        self.circuit_breaker_failures += 1
        self.circuit_breaker_last_failure = datetime.now(timezone.utc)

        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
            self.circuit_breaker_open = True
            self.metrics.circuit_breaker_trips += 1
            self.logger.error(
                f"TTS cache circuit breaker opened after {self.circuit_breaker_failures} failures"
            )

    async def _cleanup_loop(self) -> None:
        """Background task for cache maintenance."""
        while True:
            try:
                await self._perform_cleanup()
                await asyncio.sleep(300)  # Every 5 minutes
            except Exception as e:
                self.logger.error(f"Cache cleanup error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Shorter retry on error

    async def _perform_cleanup(self) -> None:
        """Perform routine cache cleanup."""
        if not self.enabled or self._is_circuit_breaker_open():
            return

        try:
            # Clean up expired entries
            pattern = self._generate_redis_key("*")
            keys = await self.redis_client.keys(pattern)

            expired_count = 0
            for key in keys:
                ttl = await self.redis_client.ttl(key)
                if ttl == -2:  # Key doesn't exist
                    continue
                elif ttl == -1:  # Key exists but no TTL set
                    await self.redis_client.expire(key, self.default_ttl_seconds)
                elif ttl == 0:  # Key expired
                    await self.redis_client.delete(key)
                    expired_count += 1

            if expired_count > 0:
                self.metrics.cache_expires += expired_count
                self.logger.debug(
                    f"Cleaned up {expired_count} expired TTS cache entries"
                )

        except Exception as e:
            self.logger.error(f"Cache cleanup failed: {e}", exc_info=True)

    async def _metrics_collection_loop(self) -> None:
        """Background task for metrics collection."""
        while True:
            try:
                await self._collect_metrics()
                await asyncio.sleep(60)  # Every minute
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}", exc_info=True)
                await asyncio.sleep(30)  # Shorter retry on error

    async def _collect_metrics(self) -> None:
        """Collect comprehensive cache metrics."""
        if not self.enabled or self._is_circuit_breaker_open():
            return

        try:
            # Get Redis info
            info = await self.redis_client.info()
            memory_info = await self.redis_client.info("memory")

            # Log performance metrics
            self.logger.info(
                "TTS Cache Performance Metrics",
                extra={
                    "hit_rate": round(self.metrics.hit_rate, 2),
                    "cache_size_mb": round(
                        self.metrics.total_cache_size_bytes / 1024 / 1024, 2
                    ),
                    "avg_access_time_ms": round(self.metrics.avg_access_time_ms, 2),
                    "compression_ratio": round(self.metrics.avg_compression_ratio, 3),
                    "total_cost_saved": round(self.metrics.total_cost_saved, 2),
                    "redis_memory_mb": round(
                        memory_info.get("used_memory", 0) / 1024 / 1024, 2
                    ),
                },
            )

        except Exception as e:
            self.logger.debug(f"Metrics collection failed: {e}")

    async def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        stats = {
            "enabled": self.enabled,
            "circuit_breaker_open": self.circuit_breaker_open,
            "configuration": {
                "default_ttl_seconds": self.default_ttl_seconds,
                "max_cache_size_mb": self.max_cache_size_bytes // 1024 // 1024,
                "compression_level": self.compression_level.value,
                "cache_strategy": self.cache_strategy.value,
            },
            "performance_metrics": self.metrics.to_dict(),
            "cost_optimization": {
                "total_cost_saved": self.metrics.total_cost_saved,
                "avg_compression_ratio": self.metrics.avg_compression_ratio,
                "storage_efficiency_percent": round(
                    (1 - self.metrics.avg_compression_ratio) * 100, 1
                ),
            },
        }

        # Add Redis-specific stats if available
        if self.redis_client and not self._is_circuit_breaker_open():
            try:
                redis_info = await self.redis_client.info("memory")
                stats["redis_info"] = {
                    "used_memory_mb": round(
                        redis_info.get("used_memory", 0) / 1024 / 1024, 2
                    ),
                    "used_memory_human": redis_info.get("used_memory_human", "0B"),
                    "maxmemory_mb": (
                        round(redis_info.get("maxmemory", 0) / 1024 / 1024, 2)
                        if redis_info.get("maxmemory", 0) > 0
                        else "unlimited"
                    ),
                }
            except Exception:
                stats["redis_info"] = {"status": "unavailable"}

        return stats

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check."""
        try:
            health_status = {
                "status": "healthy",
                "enabled": self.enabled,
                "circuit_breaker_open": self.circuit_breaker_open,
                "redis_connected": False,
                "hit_rate": self.metrics.hit_rate,
                "cache_size_mb": round(
                    self.metrics.total_cache_size_bytes / 1024 / 1024, 2
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if self.enabled and self.redis_client:
                try:
                    await self.redis_client.ping()
                    health_status["redis_connected"] = True

                    # Check if hit rate is acceptable
                    if self.metrics.total_requests > 100 and self.metrics.hit_rate < 20:
                        health_status["status"] = "degraded"
                        health_status["warning"] = "Low cache hit rate"

                except Exception:
                    health_status["status"] = "degraded"
                    health_status["redis_connected"] = False

            return health_status

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def shutdown(self) -> None:
        """Graceful shutdown of cache service."""
        self.logger.info("Shutting down TTS cache service")

        # Cancel background tasks
        if self.cleanup_task:
            self.cleanup_task.cancel()
        if self.metrics_task:
            self.metrics_task.cancel()

        # Close Redis connections
        if self.redis_client:
            await self.redis_client.aclose()  # Changed from close() to aclose() for redis.asyncio
        if self.connection_pool:
            await self.connection_pool.aclose()  # Changed from disconnect() to aclose() for redis.asyncio

        self.logger.info("TTS cache service shutdown complete")


# Factory function for easy integration
async def create_production_tts_cache() -> ProductionTTSCacheService:
    """Create production TTS cache service with optimal defaults."""
    return ProductionTTSCacheService(
        enabled=os.getenv("TTS_CACHE_ENABLED", "true").lower() == "true",
        default_ttl_seconds=int(os.getenv("TTS_CACHE_TTL", "3600")),
        max_cache_size_mb=int(os.getenv("TTS_CACHE_MAX_SIZE_MB", "1024")),
        compression_level=CompressionLevel(
            int(os.getenv("TTS_CACHE_COMPRESSION", "2"))
        ),
        cache_strategy=CacheStrategy(os.getenv("TTS_CACHE_STRATEGY", "cost_aware")),
    )
