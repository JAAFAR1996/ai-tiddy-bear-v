"""
Unified Rate Limiting Service - Production Implementation

Consolidates ALL rate limiting logic from scattered implementations into a single, comprehensive service:
- Multiple rate limiting algorithms (sliding window, token bucket, fixed window)
- Child-specific safety limits with age-appropriate restrictions
- Redis backend with memory fallback for high availability
- Integration with AI, Audio, and Conversation services
- Performance optimization with async processing
- Comprehensive logging and monitoring
- COPPA compliance with child protection features

Replaces:
- ComprehensiveRateLimiter (infrastructure security service)
- ChildSafetyLimiter (legacy child-specific limiter)
- SlidingWindowRateLimiter (fallback rate limiter)
- APISecurityManager rate limiting (child safety API manager)
- Various scattered rate limiting decorators and middleware
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
from src.infrastructure.database.repository import ChildRepository

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

# Configure logging
logger = logging.getLogger(__name__)


# DATA MODELS AND TYPES

class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithm types."""
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    FIXED_WINDOW = "fixed_window"


class OperationType(str, Enum):
    """Types of operations for rate limiting."""
    AI_REQUEST = "ai_request"
    AUDIO_GENERATION = "audio_generation"
    CONVERSATION_MESSAGE = "conversation_message"
    CONVERSATION_START = "conversation_start"
    CONVERSATION_END = "conversation_end"
    MESSAGE_BURST = "message_burst"
    SAFETY_INCIDENT = "safety_incident"
    DAILY_USAGE = "daily_usage"
    CONCURRENT_CONVERSATIONS = "concurrent_conversations"
    API_CALL = "api_call"
    AUTHENTICATION = "authentication"
    DATA_ACCESS = "data_access"


@dataclass
class RateLimitResult:
    """Result of rate limiting check."""
    allowed: bool
    remaining: int = 0
    reset_time: Optional[datetime] = None
    retry_after_seconds: int = 0
    operation_type: str = ""
    child_id: Optional[str] = None
    reason: Optional[str] = None
    safety_triggered: bool = False
    usage_stats: Dict[str, Any] = field(default_factory=dict)
    # New conversation-specific fields
    conversation_id: Optional[str] = None
    concurrent_conversations: int = 0
    safety_cooldown_active: bool = False
    burst_protection_triggered: bool = False
    daily_limit_reached: bool = False


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting rules."""
    operation_type: OperationType
    max_requests: int
    window_seconds: int
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    burst_capacity: Optional[int] = None
    refill_rate: Optional[float] = None
    block_duration_seconds: int = 300
    child_safe_mode: bool = True
    age_based_scaling: bool = True


@dataclass
class ChildAgeLimits:
    """Age-based rate limiting configuration."""
    age_group: str
    min_age: int
    max_age: int
    ai_requests_per_hour: int
    audio_generation_per_hour: int
    conversation_messages_per_hour: int
    api_calls_per_hour: int
    session_duration_minutes: int
    # New conversation-specific limits
    conversations_per_hour: int = 3
    conversations_per_day: int = 10
    messages_per_minute: int = 8
    messages_per_day: int = 500
    max_concurrent_conversations: int = 2
    max_conversation_duration_minutes: int = 45
    safety_incident_cooldown_minutes: int = 30
    max_safety_incidents_per_day: int = 2
    burst_window_seconds: int = 30
    burst_limit: int = 15


# ================================
# CHILD-SAFE RATE LIMIT CONFIGURATIONS
# ================================

CHILD_AGE_LIMITS = {
    "toddler": ChildAgeLimits(
        age_group="toddler", min_age=3, max_age=4,
        ai_requests_per_hour=20, audio_generation_per_hour=10, 
        conversation_messages_per_hour=50, api_calls_per_hour=100, session_duration_minutes=10,
        # Conversation-specific limits for toddlers (most restrictive)
        conversations_per_hour=2, conversations_per_day=5,
        messages_per_minute=5, messages_per_day=200,
        max_concurrent_conversations=1, max_conversation_duration_minutes=30,
        safety_incident_cooldown_minutes=60, max_safety_incidents_per_day=1,
        burst_window_seconds=30, burst_limit=10
    ),
    "preschool": ChildAgeLimits(
        age_group="preschool", min_age=5, max_age=6,
        ai_requests_per_hour=30, audio_generation_per_hour=15,
        conversation_messages_per_hour=75, api_calls_per_hour=150, session_duration_minutes=15,
        # Conversation limits for preschoolers
        conversations_per_hour=3, conversations_per_day=8,
        messages_per_minute=8, messages_per_day=400,
        max_concurrent_conversations=2, max_conversation_duration_minutes=45,
        safety_incident_cooldown_minutes=30, max_safety_incidents_per_day=2,
        burst_window_seconds=30, burst_limit=15
    ),
    "early_child": ChildAgeLimits(
        age_group="early_child", min_age=7, max_age=8,
        ai_requests_per_hour=40, audio_generation_per_hour=18,
        conversation_messages_per_hour=90, api_calls_per_hour=180, session_duration_minutes=25,
        # Conversation limits for early children
        conversations_per_hour=5, conversations_per_day=15,
        messages_per_minute=12, messages_per_day=800,
        max_concurrent_conversations=3, max_conversation_duration_minutes=60,
        safety_incident_cooldown_minutes=20, max_safety_incidents_per_day=3,
        burst_window_seconds=30, burst_limit=20
    ),
    "middle_child": ChildAgeLimits(
        age_group="middle_child", min_age=9, max_age=10,
        ai_requests_per_hour=45, audio_generation_per_hour=20,
        conversation_messages_per_hour=95, api_calls_per_hour=200, session_duration_minutes=35,
        # Conversation limits for middle children
        conversations_per_hour=6, conversations_per_day=20,
        messages_per_minute=15, messages_per_day=1200,
        max_concurrent_conversations=4, max_conversation_duration_minutes=90,
        safety_incident_cooldown_minutes=15, max_safety_incidents_per_day=4,
        burst_window_seconds=30, burst_limit=25
    ),
    "preteen": ChildAgeLimits(
        age_group="preteen", min_age=11, max_age=13,
        ai_requests_per_hour=50, audio_generation_per_hour=20,
        conversation_messages_per_hour=100, api_calls_per_hour=200, session_duration_minutes=45,
        # Conversation limits for preteens (most permissive)
        conversations_per_hour=8, conversations_per_day=25,
        messages_per_minute=20, messages_per_day=1500,
        max_concurrent_conversations=5, max_conversation_duration_minutes=120,
        safety_incident_cooldown_minutes=15, max_safety_incidents_per_day=5,
        burst_window_seconds=30, burst_limit=30
    ),
}

DEFAULT_RATE_LIMITS = {
    OperationType.AI_REQUEST: RateLimitConfig(
        operation_type=OperationType.AI_REQUEST,
        max_requests=50,
        window_seconds=3600,  # 1 hour
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
        child_safe_mode=True,
        age_based_scaling=True
    ),
    OperationType.AUDIO_GENERATION: RateLimitConfig(
        operation_type=OperationType.AUDIO_GENERATION,
        max_requests=20,
        window_seconds=3600,  # 1 hour
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        burst_capacity=5,
        refill_rate=0.33,  # ~20 per hour
        child_safe_mode=True,
        age_based_scaling=True
    ),
    OperationType.CONVERSATION_MESSAGE: RateLimitConfig(
        operation_type=OperationType.CONVERSATION_MESSAGE,
        max_requests=100,
        window_seconds=3600,  # 1 hour
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
        child_safe_mode=True,
        age_based_scaling=True
    ),
    OperationType.API_CALL: RateLimitConfig(
        operation_type=OperationType.API_CALL,
        max_requests=200,
        window_seconds=3600,  # 1 hour
        algorithm=RateLimitAlgorithm.FIXED_WINDOW,
        burst_capacity=10,
        child_safe_mode=True,
        age_based_scaling=True
    ),
    OperationType.AUTHENTICATION: RateLimitConfig(
        operation_type=OperationType.AUTHENTICATION,
        max_requests=5,
        window_seconds=900,  # 15 minutes
        algorithm=RateLimitAlgorithm.FIXED_WINDOW,
        block_duration_seconds=3600,  # 1 hour
        child_safe_mode=True,
        age_based_scaling=False
    ),
    # New conversation-specific rate limits
    OperationType.CONVERSATION_START: RateLimitConfig(
        operation_type=OperationType.CONVERSATION_START,
        max_requests=8,  # Conversations per hour (will be age-scaled)
        window_seconds=3600,  # 1 hour
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
        child_safe_mode=True,
        age_based_scaling=True
    ),
    OperationType.MESSAGE_BURST: RateLimitConfig(
        operation_type=OperationType.MESSAGE_BURST,
        max_requests=30,  # Burst limit (will be age-scaled)
        window_seconds=30,  # 30 seconds burst window
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
        child_safe_mode=True,
        age_based_scaling=True
    ),
    OperationType.DAILY_USAGE: RateLimitConfig(
        operation_type=OperationType.DAILY_USAGE,
        max_requests=1500,  # Messages per day (will be age-scaled)
        window_seconds=86400,  # 24 hours
        algorithm=RateLimitAlgorithm.FIXED_WINDOW,
        child_safe_mode=True,
        age_based_scaling=True
    ),
    OperationType.CONCURRENT_CONVERSATIONS: RateLimitConfig(
        operation_type=OperationType.CONCURRENT_CONVERSATIONS,
        max_requests=5,  # Max concurrent (will be age-scaled)
        window_seconds=7200,  # 2 hours
        algorithm=RateLimitAlgorithm.FIXED_WINDOW,
        child_safe_mode=True,
        age_based_scaling=True
    ),
    OperationType.SAFETY_INCIDENT: RateLimitConfig(
        operation_type=OperationType.SAFETY_INCIDENT,
        max_requests=5,  # Max incidents per day (will be age-scaled)
        window_seconds=86400,  # 24 hours
        algorithm=RateLimitAlgorithm.FIXED_WINDOW,
        block_duration_seconds=1800,  # 30 minutes cooldown
        child_safe_mode=True,
        age_based_scaling=True
    ),
}


# ================================
# STORAGE BACKENDS
# ================================

class RateLimitStorage(ABC):
    """Abstract storage backend for rate limiting data."""

    @abstractmethod
    async def get_requests(self, key: str, window_seconds: int) -> List[float]:
        """Get request timestamps within the time window."""

    @abstractmethod
    async def add_request(self, key: str, timestamp: float, window_seconds: int) -> None:
        """Add a new request timestamp."""

    @abstractmethod
    async def get_token_bucket(self, key: str) -> Dict[str, float]:
        """Get token bucket state (tokens, last_refill)."""

    @abstractmethod
    async def update_token_bucket(self, key: str, tokens: float, last_refill: float) -> None:
        """Update token bucket state."""

    @abstractmethod
    async def cleanup_expired(self, max_age_seconds: int) -> int:
        """Clean up expired entries."""


class RedisRateLimitStorage(RateLimitStorage):
    """Redis-based storage backend for production use."""

    def __init__(self, redis_client: Optional[Any] = None, redis_url: str = "redis://localhost:6379"):
        """Initialize Redis storage backend."""
        if redis_client:
            self.redis = redis_client
        elif REDIS_AVAILABLE:
            self.redis = redis.from_url(redis_url, decode_responses=True)
        else:
            raise RuntimeError("Redis not available and no client provided")

        logger.info("RedisRateLimitStorage initialized")

    async def get_requests(self, key: str, window_seconds: int) -> List[float]:
        """Get request timestamps within the time window."""
        try:
            now = time.time()
            min_time = now - window_seconds

            # Remove expired entries and get current ones
            await self.redis.zremrangebyscore(f"rate_limit:{key}", 0, min_time)
            timestamps = await self.redis.zrangebyscore(f"rate_limit:{key}", min_time, now)

            return [float(ts) for ts in timestamps]
        except Exception as e:
            logger.error(f"Redis get_requests error: {e}")
            return []

    async def add_request(self, key: str, timestamp: float, window_seconds: int) -> None:
        """Add a new request timestamp."""
        try:
            pipe = self.redis.pipeline()
            pipe.zadd(f"rate_limit:{key}", {str(timestamp): timestamp})
            pipe.expire(f"rate_limit:{key}", window_seconds * 2)  # Keep extra time for cleanup
            await pipe.execute()
        except Exception as e:
            logger.error(f"Redis add_request error: {e}")

    async def get_token_bucket(self, key: str) -> Dict[str, float]:
        """Get token bucket state."""
        try:
            data = await self.redis.hgetall(f"token_bucket:{key}")
            if data:
                return {
                    "tokens": float(data.get("tokens", 0)),
                    "last_refill": float(data.get("last_refill", time.time()))
                }
            return {"tokens": 0.0, "last_refill": time.time()}
        except Exception as e:
            logger.error(f"Redis get_token_bucket error: {e}")
            return {"tokens": 0.0, "last_refill": time.time()}

    async def update_token_bucket(self, key: str, tokens: float, last_refill: float) -> None:
        """Update token bucket state."""
        try:
            await self.redis.hset(f"token_bucket:{key}", mapping={
                "tokens": str(tokens),
                "last_refill": str(last_refill)
            })
            await self.redis.expire(f"token_bucket:{key}", 3600)  # 1 hour expiry
        except Exception as e:
            logger.error(f"Redis update_token_bucket error: {e}")

    async def cleanup_expired(self, max_age_seconds: int) -> int:
        """Clean up expired entries."""
        try:
            cutoff_time = time.time() - max_age_seconds
            pattern = "rate_limit:*"

            count = 0
            async for key in self.redis.scan_iter(match=pattern):
                removed = await self.redis.zremrangebyscore(key, 0, cutoff_time)
                count += removed

            return count
        except Exception as e:
            logger.error(f"Redis cleanup error: {e}")
            return 0


class MemoryRateLimitStorage(RateLimitStorage):
    """In-memory storage backend for development/fallback."""

    def __init__(self):
        """Initialize memory storage backend."""
        self.requests_data: Dict[str, List[float]] = {}
        self.token_buckets: Dict[str, Dict[str, float]] = {}
        self.last_cleanup = time.time()
        logger.info("MemoryRateLimitStorage initialized")

    async def get_requests(self, key: str, window_seconds: int) -> List[float]:
        """Get request timestamps within the time window."""
        now = time.time()
        min_time = now - window_seconds

        if key not in self.requests_data:
            return []

        # Filter out expired requests
        valid_requests = [ts for ts in self.requests_data[key] if ts >= min_time]
        self.requests_data[key] = valid_requests

        return valid_requests

    async def add_request(self, key: str, timestamp: float, window_seconds: int) -> None:
        """Add a new request timestamp."""
        if key not in self.requests_data:
            self.requests_data[key] = []

        self.requests_data[key].append(timestamp)

        # Periodic cleanup
        if time.time() - self.last_cleanup > 300:  # Every 5 minutes
            await self.cleanup_expired(3600)
            self.last_cleanup = time.time()

    async def get_token_bucket(self, key: str) -> Dict[str, float]:
        """Get token bucket state."""
        if key not in self.token_buckets:
            return {"tokens": 0.0, "last_refill": time.time()}
        return self.token_buckets[key].copy()

    async def update_token_bucket(self, key: str, tokens: float, last_refill: float) -> None:
        """Update token bucket state."""
        self.token_buckets[key] = {
            "tokens": tokens,
            "last_refill": last_refill
        }

    async def cleanup_expired(self, max_age_seconds: int) -> int:
        """Clean up expired entries."""
        now = time.time()
        cutoff_time = now - max_age_seconds

        count = 0
        for key in list(self.requests_data.keys()):
            original_count = len(self.requests_data[key])
            self.requests_data[key] = [ts for ts in self.requests_data[key] if ts >= cutoff_time]
            if not self.requests_data[key]:
                del self.requests_data[key]
            count += original_count - len(self.requests_data.get(key, []))

        # Clean up expired token buckets
        expired_buckets = [
            key for key, data in self.token_buckets.items()
            if data["last_refill"] < cutoff_time
        ]
        for key in expired_buckets:
            del self.token_buckets[key]
            count += 1

        return count


# ================================
# RATE LIMITING ALGORITHMS
# ================================

class RateLimitAlgorithmImpl:
    """Rate limiting algorithm implementations."""

    @staticmethod
    async def sliding_window(
        storage: RateLimitStorage,
        key: str,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """Sliding window rate limiting algorithm."""
        current_requests = await storage.get_requests(key, config.window_seconds)
        request_count = len(current_requests)

        if request_count >= config.max_requests:
            # Find reset time (oldest request + window)
            reset_time = None
            if current_requests:
                oldest_request = min(current_requests)
                reset_time = datetime.fromtimestamp(oldest_request + config.window_seconds)

            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after_seconds=config.window_seconds,
                reason="rate_limit_exceeded",
                usage_stats={"current_requests": request_count, "max_requests": config.max_requests}
            )

        # Add current request
        await storage.add_request(key, time.time(), config.window_seconds)

        return RateLimitResult(
            allowed=True,
            remaining=config.max_requests - request_count - 1,
            reset_time=datetime.fromtimestamp(time.time() + config.window_seconds),
            usage_stats={"current_requests": request_count + 1, "max_requests": config.max_requests}
        )

    @staticmethod
    async def token_bucket(
        storage: RateLimitStorage,
        key: str,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """Token bucket rate limiting algorithm."""
        bucket_data = await storage.get_token_bucket(key)
        now = time.time()

        tokens = bucket_data["tokens"]
        last_refill = bucket_data["last_refill"]

        # Calculate tokens to add based on refill rate
        if config.refill_rate and last_refill:
            time_passed = now - last_refill
            new_tokens = time_passed * config.refill_rate
            tokens = min(config.burst_capacity or config.max_requests, tokens + new_tokens)
        else:
            # Fallback: simple refill based on window
            if tokens <= 0:
                tokens = config.max_requests

        if tokens < 1:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after_seconds=int(1 / (config.refill_rate or 1)),
                reason="no_tokens_available",
                usage_stats={"tokens": tokens, "capacity": config.burst_capacity or config.max_requests}
            )

        # Consume one token
        tokens -= 1
        await storage.update_token_bucket(key, tokens, now)

        return RateLimitResult(
            allowed=True,
            remaining=int(tokens),
            usage_stats={"tokens": tokens, "capacity": config.burst_capacity or config.max_requests}
        )

    @staticmethod
    async def fixed_window(
        storage: RateLimitStorage,
        key: str,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """Fixed window rate limiting algorithm."""
        now = time.time()
        window_start = int(now / config.window_seconds) * config.window_seconds
        window_key = f"{key}:{window_start}"

        current_requests = await storage.get_requests(window_key, config.window_seconds)
        request_count = len(current_requests)

        if request_count >= config.max_requests:
            next_window = window_start + config.window_seconds
            reset_time = datetime.fromtimestamp(next_window)

            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after_seconds=int(next_window - now),
                reason="fixed_window_exceeded",
                usage_stats={"current_requests": request_count, "max_requests": config.max_requests}
            )

        # Add current request
        await storage.add_request(window_key, now, config.window_seconds)

        return RateLimitResult(
            allowed=True,
            remaining=config.max_requests - request_count - 1,
            reset_time=datetime.fromtimestamp(window_start + config.window_seconds),
            usage_stats={"current_requests": request_count + 1, "max_requests": config.max_requests}
        )


# ================================
# UNIFIED RATE LIMITING SERVICE
# ================================

class RateLimitingService:
    """
    Unified rate limiting service with child safety and multiple backend support.

    Provides comprehensive rate limiting for all AI Teddy Bear operations with:
    - Child-specific age-appropriate limits
    - Multiple algorithms (sliding window, token bucket, fixed window)
    - Redis backend with memory fallback
    - Integration with AI, Audio, and Conversation services
    - Performance monitoring and usage statistics
    - COPPA compliance and child protection
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        redis_url: str = "redis://localhost:6379",
        use_redis: bool = True,
        enable_cleanup: bool = True
    ):
        """
        Initialize the unified rate limiting service.

        Args:
            redis_client: Optional Redis client instance
            redis_url: Redis connection URL
            use_redis: Whether to use Redis backend (falls back to memory)
            enable_cleanup: Enable automatic cleanup of expired entries
        """
        # Initialize storage backend
        if use_redis and REDIS_AVAILABLE:
            try:
                self.storage = RedisRateLimitStorage(redis_client, redis_url)
                self.backend_type = "redis"
            except Exception as e:
                logger.warning(f"Redis initialization failed, falling back to memory: {e}")
                self.storage = MemoryRateLimitStorage()
                self.backend_type = "memory"
        else:
            self.storage = MemoryRateLimitStorage()
            self.backend_type = "memory"

        # Rate limiting configurations
        self.configs = DEFAULT_RATE_LIMITS.copy()
        self.child_age_limits = CHILD_AGE_LIMITS.copy()

        # Performance tracking
        self.request_count = 0
        self.blocked_count = 0
        self.total_processing_time = 0.0

        # Store cleanup settings - will be started via start() method
        self.enable_cleanup = enable_cleanup
        self._cleanup_task = None
        self._started = False
        
        # Initialize database repository
        self.child_repo = ChildRepository()

        logger.info(f"RateLimitingService initialized with {self.backend_type} backend")

    async def start(self):
        """Start the rate limiting service - must be called from async context."""
        if self._started:
            return
        
        if self.enable_cleanup:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Rate limiting cleanup task started")
        
        self._started = True

    async def _ensure_cleanup_task(self):
        """Ensure cleanup task is running if enabled."""
        if self.enable_cleanup and self._cleanup_task is None:
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._cleanup_loop())
            except RuntimeError:
                pass  # No running event loop

    async def check_rate_limit(
        self,
        child_id: str,
        operation: OperationType,
        child_age: Optional[int] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> RateLimitResult:
        """
        Check if operation is within rate limits for a child.

        Args:
            child_id: Unique identifier for the child
            operation: Type of operation being performed
            child_age: Age of child for age-appropriate limits
            additional_context: Additional context for rate limiting decisions

        Returns:
            RateLimitResult indicating if operation is allowed
        """
        start_time = time.time()
        self.request_count += 1

        # Ensure cleanup task is running
        await self._ensure_cleanup_task()

        try:
            # Get configuration for operation
            config = self._get_config_for_operation(operation, child_age)

            # Generate unique key for this child and operation
            key = f"child:{child_id}:op:{operation.value}"

            # Apply rate limiting algorithm
            result = await self._apply_algorithm(key, config)

            # Add contextual information
            result.operation_type = operation.value
            result.child_id = child_id

            # Track blocked requests
            if not result.allowed:
                self.blocked_count += 1
                result.safety_triggered = config.child_safe_mode
                logger.warning(
                    f"Rate limit exceeded for child {child_id}, operation {operation.value}: {result.reason}"
                )

            # Track processing time
            processing_time = time.time() - start_time
            self.total_processing_time += processing_time

            logger.debug(
                f"Rate limit check completed: child={child_id}, op={operation.value}, "
                f"allowed={result.allowed}, remaining={result.remaining}"
            )

            return result

        except Exception as e:
            logger.error(f"Rate limiting error for child {child_id}, operation {operation.value}: {e}")
            # Fail open - allow request if there's an error
            return RateLimitResult(
                allowed=True,
                remaining=0,
                reason="rate_limit_error",
                operation_type=operation.value,
                child_id=child_id
            )

    async def record_request(
        self,
        child_id: str,
        operation: OperationType,
        success: bool = True,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a completed request for usage tracking.

        Args:
            child_id: Child identifier
            operation: Operation type
            success: Whether the operation was successful
            additional_metadata: Additional metadata to store
        """
        try:
            # This is primarily for statistics and monitoring
            # The actual rate limiting is handled in check_rate_limit
            timestamp = time.time()
            metadata_key = f"metadata:{child_id}:op:{operation.value}"

            metadata = {
                "timestamp": timestamp,
                "success": success,
                "operation": operation.value,
                "child_id": child_id
            }

            if additional_metadata:
                metadata.update(additional_metadata)

            # Store metadata for statistics (simple implementation)
            # In production, this could be enhanced with more sophisticated tracking
            logger.debug(f"Recorded request: {metadata}")

        except Exception as e:
            logger.error(f"Error recording request: {e}")

    async def get_usage_stats(self, child_id: str) -> Dict[str, Any]:
        """
        Get usage statistics for a child.

        Args:
            child_id: Child identifier

        Returns:
            Dictionary with usage statistics
        """
        try:
            stats = {}

            for operation in OperationType:
                key = f"child:{child_id}:op:{operation.value}"
                config = self._get_config_for_operation(operation)

                # Get current usage for each operation
                current_requests = await self.storage.get_requests(key, config.window_seconds)

                stats[operation.value] = {
                    "current_requests": len(current_requests),
                    "max_requests": config.max_requests,
                    "remaining": max(0, config.max_requests - len(current_requests)),
                    "window_seconds": config.window_seconds,
                    "usage_percentage": (len(current_requests) / config.max_requests) * 100
                }

            # Add child-specific information
            age_group = self._get_age_group_for_child(child_id)
            if age_group:
                stats["age_group"] = age_group.age_group
                stats["age_limits"] = {
                    "ai_requests_per_hour": age_group.ai_requests_per_hour,
                    "audio_generation_per_hour": age_group.audio_generation_per_hour,
                    "conversation_messages_per_hour": age_group.conversation_messages_per_hour,
                    "session_duration_minutes": age_group.session_duration_minutes
                }

            return stats

        except Exception as e:
            logger.error(f"Error getting usage stats for child {child_id}: {e}")
            return {}

    async def reset_limits(
        self,
        child_id: str,
        operation: Optional[OperationType] = None
    ) -> None:
        """
        Reset rate limits for a child (admin function).

        Args:
            child_id: Child identifier
            operation: Specific operation to reset (None for all operations)
        """
        try:
            operations_to_reset = [operation] if operation else list(OperationType)

            for op in operations_to_reset:
                key = f"child:{child_id}:op:{op.value}"

                # For sliding window and fixed window, we can clear the requests
                if hasattr(self.storage, 'requests_data') and isinstance(self.storage, MemoryRateLimitStorage):
                    # Memory storage
                    if key in self.storage.requests_data:
                        del self.storage.requests_data[key]
                elif isinstance(self.storage, RedisRateLimitStorage):
                    # Redis storage
                    await self.storage.redis.delete(f"rate_limit:{key}")
                    await self.storage.redis.delete(f"token_bucket:{key}")

            logger.info(f"Reset limits for child {child_id}, operations: {operations_to_reset}")

        except Exception as e:
            logger.error(f"Error resetting limits for child {child_id}: {e}")

    def _get_config_for_operation(
        self,
        operation: OperationType,
        child_age: Optional[int] = None
    ) -> RateLimitConfig:
        """Get rate limiting configuration for an operation."""
        base_config = self.configs.get(operation, DEFAULT_RATE_LIMITS[operation])

        if base_config.age_based_scaling and child_age:
            age_group = self._get_age_group_by_age(child_age)
            if age_group:
                # Scale limits based on age group
                scaling_factor = self._get_scaling_factor(operation, age_group)
                scaled_config = RateLimitConfig(
                    operation_type=operation,
                    max_requests=int(base_config.max_requests * scaling_factor),
                    window_seconds=base_config.window_seconds,
                    algorithm=base_config.algorithm,
                    burst_capacity=int(base_config.burst_capacity * scaling_factor) if base_config.burst_capacity else None,
                    refill_rate=base_config.refill_rate,
                    block_duration_seconds=base_config.block_duration_seconds,
                    child_safe_mode=base_config.child_safe_mode,
                    age_based_scaling=base_config.age_based_scaling
                )
                return scaled_config

        return base_config

    def _get_age_group_by_age(self, age: int) -> Optional[ChildAgeLimits]:
        """Get age group configuration by child age."""
        for age_group in self.child_age_limits.values():
            if age_group.min_age <= age <= age_group.max_age:
                return age_group
        return None

    def _get_age_group_for_child(self, child_id: str) -> Optional[ChildAgeLimits]:
        """Get age group for a child from production database."""
        try:
            # Get child from database
            import asyncio
            import uuid
            
            # Create async context if needed
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context
                child = asyncio.create_task(self.child_repo.get_by_id(uuid.UUID(child_id))).result()
            else:
                # Sync context - run async method
                child = loop.run_until_complete(self.child_repo.get_by_id(uuid.UUID(child_id)))
            
            if child and hasattr(child, 'age'):
                age = child.age
                if age <= 5:
                    return self.child_age_limits["young_child"]
                elif age <= 8:
                    return self.child_age_limits["middle_child"]
                else:
                    return self.child_age_limits["older_child"]
        except Exception as e:
            logger.warning(f"Failed to get child age from database: {e}")
        
        # Default to middle child limits if lookup fails
        return self.child_age_limits["middle_child"]

    def _get_scaling_factor(self, operation: OperationType, age_group: ChildAgeLimits) -> float:
        """Get scaling factor for rate limits based on age group."""
        # Map operation types to age group limits
        if operation == OperationType.AI_REQUEST:
            return age_group.ai_requests_per_hour / 50  # 50 is the default
        elif operation == OperationType.AUDIO_GENERATION:
            return age_group.audio_generation_per_hour / 20  # 20 is the default
        elif operation == OperationType.CONVERSATION_MESSAGE:
            return age_group.conversation_messages_per_hour / 100  # 100 is the default
        elif operation == OperationType.API_CALL:
            return age_group.api_calls_per_hour / 200  # 200 is the default
        # New conversation-specific scaling factors
        elif operation == OperationType.CONVERSATION_START:
            return age_group.conversations_per_hour / 8  # 8 is the default
        elif operation == OperationType.MESSAGE_BURST:
            return age_group.burst_limit / 30  # 30 is the default
        elif operation == OperationType.DAILY_USAGE:
            return age_group.messages_per_day / 1500  # 1500 is the default
        elif operation == OperationType.CONCURRENT_CONVERSATIONS:
            return age_group.max_concurrent_conversations / 5  # 5 is the default
        elif operation == OperationType.SAFETY_INCIDENT:
            return age_group.max_safety_incidents_per_day / 5  # 5 is the default
        else:
            return 1.0  # No scaling for other operations

    async def _apply_algorithm(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        """Apply the configured rate limiting algorithm."""
        if config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return await RateLimitAlgorithmImpl.sliding_window(self.storage, key, config)
        elif config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return await RateLimitAlgorithmImpl.token_bucket(self.storage, key, config)
        elif config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            return await RateLimitAlgorithmImpl.fixed_window(self.storage, key, config)
        else:
            # Default to sliding window
            return await RateLimitAlgorithmImpl.sliding_window(self.storage, key, config)

    # ================================
    # CONVERSATION-SPECIFIC METHODS
    # ================================

    async def check_conversation_start_limit(
        self,
        child_id: str,
        child_age: int,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RateLimitResult:
        """Check if child can start a new conversation."""
        # Get age group for more specific limits
        age_group = self._get_age_group_by_age(child_age)
        
        # Check multiple limits for conversation start
        results = []
        
        # 1. Check hourly conversation limit
        hourly_result = await self.check_rate_limit(
            child_id=child_id,
            operation=OperationType.CONVERSATION_START,
            child_age=child_age,
            additional_context={"conversation_id": conversation_id}
        )
        results.append(hourly_result)
        
        # 2. Check daily conversation limit
        daily_key = f"child:{child_id}:daily_conversations"
        daily_config = RateLimitConfig(
            operation_type=OperationType.CONVERSATION_START,
            max_requests=int(age_group.conversations_per_day),
            window_seconds=86400,  # 24 hours
            algorithm=RateLimitAlgorithm.FIXED_WINDOW,
            child_safe_mode=True
        )
        daily_result = await self._apply_algorithm(daily_key, daily_config)
        daily_result.operation_type = OperationType.CONVERSATION_START.value
        daily_result.child_id = child_id
        results.append(daily_result)
        
        # 3. Check concurrent conversation limit
        concurrent_result = await self._check_concurrent_conversations(child_id, age_group)
        results.append(concurrent_result)
        
        # 4. Check safety incident cooldown
        safety_result = await self._check_safety_cooldown(child_id, age_group)
        if not safety_result.allowed:
            results.append(safety_result)
        
        # Return the most restrictive result
        for result in results:
            if not result.allowed:
                result.conversation_id = conversation_id
                result.concurrent_conversations = await self._get_concurrent_conversation_count(child_id)
                result.safety_cooldown_active = not safety_result.allowed
                return result
        
        # If all passed, increment concurrent counter
        await self._increment_concurrent_conversations(child_id)
        
        # Return success result
        success_result = hourly_result
        success_result.conversation_id = conversation_id
        success_result.concurrent_conversations = await self._get_concurrent_conversation_count(child_id)
        return success_result

    async def check_message_limit(
        self,
        child_id: str,
        child_age: int,
        conversation_id: str,
        message_type: str = "user_input"
    ) -> RateLimitResult:
        """Check if child can send a message."""
        age_group = self._get_age_group_by_age(child_age)
        
        # Check multiple message limits
        results = []
        
        # 1. Check per-minute burst protection
        burst_key = f"child:{child_id}:message_burst"
        burst_config = RateLimitConfig(
            operation_type=OperationType.MESSAGE_BURST,
            max_requests=int(age_group.burst_limit),
            window_seconds=age_group.burst_window_seconds,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            child_safe_mode=True
        )
        burst_result = await self._apply_algorithm(burst_key, burst_config)
        burst_result.operation_type = OperationType.MESSAGE_BURST.value
        burst_result.child_id = child_id
        burst_result.conversation_id = conversation_id
        if not burst_result.allowed:
            burst_result.burst_protection_triggered = True
            return burst_result
        
        # 2. Check hourly message limit
        hourly_result = await self.check_rate_limit(
            child_id=child_id,
            operation=OperationType.CONVERSATION_MESSAGE,
            child_age=child_age,
            additional_context={"conversation_id": conversation_id, "message_type": message_type}
        )
        results.append(hourly_result)
        
        # 3. Check daily message limit
        daily_key = f"child:{child_id}:daily_messages"
        daily_config = RateLimitConfig(
            operation_type=OperationType.DAILY_USAGE,
            max_requests=int(age_group.messages_per_day),
            window_seconds=86400,  # 24 hours
            algorithm=RateLimitAlgorithm.FIXED_WINDOW,
            child_safe_mode=True
        )
        daily_result = await self._apply_algorithm(daily_key, daily_config)
        daily_result.operation_type = OperationType.DAILY_USAGE.value
        daily_result.child_id = child_id
        daily_result.conversation_id = conversation_id
        if not daily_result.allowed:
            daily_result.daily_limit_reached = True
            return daily_result
        
        # Return success result with additional context
        success_result = hourly_result
        success_result.conversation_id = conversation_id
        success_result.burst_protection_triggered = False
        success_result.daily_limit_reached = False
        return success_result

    async def report_safety_incident(
        self,
        child_id: str,
        child_age: int,
        incident_type: str,
        severity: str,
        conversation_id: str,
        cooldown_minutes: Optional[int] = None
    ) -> RateLimitResult:
        """Report safety incident and apply cooldown."""
        age_group = self._get_age_group_by_age(child_age)
        
        # Check daily safety incident limit
        incident_result = await self.check_rate_limit(
            child_id=child_id,
            operation=OperationType.SAFETY_INCIDENT,
            child_age=child_age,
            additional_context={
                "incident_type": incident_type,
                "severity": severity,
                "conversation_id": conversation_id
            }
        )
        
        # Apply cooldown based on severity
        if cooldown_minutes is None:
            if severity == "critical":
                cooldown_minutes = age_group.safety_incident_cooldown_minutes * 2
            elif severity == "high":
                cooldown_minutes = age_group.safety_incident_cooldown_minutes
            else:
                cooldown_minutes = age_group.safety_incident_cooldown_minutes // 2
        
        # Set safety cooldown
        cooldown_key = f"child:{child_id}:safety_cooldown"
        cooldown_expiry = int(time.time()) + (cooldown_minutes * 60)
        await self.storage.set_value(
            cooldown_key,
            json.dumps({
                "incident_type": incident_type,
                "severity": severity,
                "conversation_id": conversation_id,
                "expires_at": cooldown_expiry
            }),
            expire_seconds=cooldown_minutes * 60
        )
        
        incident_result.safety_cooldown_active = True
        incident_result.conversation_id = conversation_id
        incident_result.retry_after_seconds = cooldown_minutes * 60
        
        return incident_result

    async def conversation_ended(self, child_id: str, conversation_id: str):
        """Mark conversation as ended for concurrent tracking."""
        await self._decrement_concurrent_conversations(child_id)

    async def get_conversation_usage_stats(self, child_id: str, child_age: int) -> Dict[str, Any]:
        """Get comprehensive conversation usage statistics."""
        age_group = self._get_age_group_by_age(child_age)
        
        # Get current counts from various keys
        current_time = int(time.time())
        hour_start = current_time - (current_time % 3600)
        day_start = current_time - (current_time % 86400)
        
        stats = {
            # Conversation stats
            "conversations_this_hour": await self._get_usage_count(f"child:{child_id}:op:conversation_start", hour_start),
            "conversations_today": await self._get_usage_count(f"child:{child_id}:daily_conversations", day_start),
            "concurrent_conversations": await self._get_concurrent_conversation_count(child_id),
            
            # Message stats
            "messages_this_hour": await self._get_usage_count(f"child:{child_id}:op:conversation_message", hour_start),
            "messages_today": await self._get_usage_count(f"child:{child_id}:daily_messages", day_start),
            
            # Safety stats
            "safety_incidents_today": await self._get_usage_count(f"child:{child_id}:op:safety_incident", day_start),
            "in_safety_cooldown": await self._is_in_safety_cooldown(child_id),
            
            # Limits
            "limits": {
                "conversations_per_hour": age_group.conversations_per_hour,
                "conversations_per_day": age_group.conversations_per_day,
                "messages_per_hour": age_group.conversation_messages_per_hour,
                "messages_per_day": age_group.messages_per_day,
                "max_concurrent": age_group.max_concurrent_conversations,
                "burst_limit": age_group.burst_limit,
            }
        }
        
        return stats

    # Helper methods for conversation-specific operations
    
    def _get_age_group_by_age(self, age: int) -> ChildAgeLimits:
        """Get age group configuration by age."""
        for age_group in self.child_age_limits.values():
            if age_group.min_age <= age <= age_group.max_age:
                return age_group
        # Default to middle_child if age not found
        return self.child_age_limits["middle_child"]

    async def _check_concurrent_conversations(self, child_id: str, age_group: ChildAgeLimits) -> RateLimitResult:
        """Check concurrent conversation limit."""
        current_count = await self._get_concurrent_conversation_count(child_id)
        
        if current_count >= age_group.max_concurrent_conversations:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after_seconds=300,  # 5 minutes
                reason=f"Maximum concurrent conversations reached ({current_count}/{age_group.max_concurrent_conversations})",
                operation_type=OperationType.CONCURRENT_CONVERSATIONS.value,
                child_id=child_id,
                concurrent_conversations=current_count
            )
        
        return RateLimitResult(
            allowed=True,
            remaining=age_group.max_concurrent_conversations - current_count,
            operation_type=OperationType.CONCURRENT_CONVERSATIONS.value,
            child_id=child_id,
            concurrent_conversations=current_count
        )

    async def _check_safety_cooldown(self, child_id: str, age_group: ChildAgeLimits) -> RateLimitResult:
        """Check if child is in safety cooldown."""
        cooldown_key = f"child:{child_id}:safety_cooldown"
        cooldown_data = await self.storage.get_value(cooldown_key)
        
        if cooldown_data:
            try:
                cooldown_info = json.loads(cooldown_data)
                expires_at = cooldown_info.get("expires_at", 0)
                
                if time.time() < expires_at:
                    return RateLimitResult(
                        allowed=False,
                        remaining=0,
                        retry_after_seconds=int(expires_at - time.time()),
                        reason=f"Safety incident cooldown active ({cooldown_info.get('severity', 'unknown')} severity)",
                        operation_type=OperationType.SAFETY_INCIDENT.value,
                        child_id=child_id,
                        safety_cooldown_active=True
                    )
            except json.JSONDecodeError:
                pass
        
        return RateLimitResult(
            allowed=True,
            remaining=1,
            operation_type=OperationType.SAFETY_INCIDENT.value,
            child_id=child_id,
            safety_cooldown_active=False
        )

    async def _get_concurrent_conversation_count(self, child_id: str) -> int:
        """Get current concurrent conversation count."""
        key = f"child:{child_id}:concurrent_conversations"
        count_str = await self.storage.get_value(key)
        return int(count_str) if count_str else 0

    async def _increment_concurrent_conversations(self, child_id: str):
        """Increment concurrent conversation count."""
        key = f"child:{child_id}:concurrent_conversations"
        current_count = await self._get_concurrent_conversation_count(child_id)
        await self.storage.set_value(key, str(current_count + 1), expire_seconds=7200)  # 2 hours

    async def _decrement_concurrent_conversations(self, child_id: str):
        """Decrement concurrent conversation count."""
        key = f"child:{child_id}:concurrent_conversations"
        current_count = await self._get_concurrent_conversation_count(child_id)
        if current_count > 0:
            await self.storage.set_value(key, str(current_count - 1), expire_seconds=7200)

    async def _get_usage_count(self, key: str, since_timestamp: int) -> int:
        """Get usage count since timestamp."""
        # Get all requests for the key
        requests = await self.storage.get_requests(key, window_seconds=86400)  # 24 hours
        
        # Count requests since the given timestamp
        count = sum(1 for req_time in requests if req_time >= since_timestamp)
        
        return count

    async def _is_in_safety_cooldown(self, child_id: str) -> bool:
        """Check if child is currently in safety cooldown."""
        cooldown_key = f"child:{child_id}:safety_cooldown"
        cooldown_data = await self.storage.get_value(cooldown_key)
        
        if cooldown_data:
            try:
                cooldown_info = json.loads(cooldown_data)
                expires_at = cooldown_info.get("expires_at", 0)
                return time.time() < expires_at
            except json.JSONDecodeError:
                pass
        
        return False

    async def _cleanup_loop(self):
        """Background cleanup loop for expired entries."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                cleaned = await self.storage.cleanup_expired(3600)  # Clean entries older than 1 hour
                if cleaned > 0:
                    logger.debug(f"Cleaned up {cleaned} expired rate limit entries")
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Get service health and performance metrics."""
        try:
            return {
                "status": "healthy",
                "backend_type": self.backend_type,
                "redis_available": REDIS_AVAILABLE,
                "total_requests": self.request_count,
                "blocked_requests": self.blocked_count,
                "block_rate": self.blocked_count / max(1, self.request_count),
                "avg_processing_time_ms": (self.total_processing_time / max(1, self.request_count)) * 1000,
                "supported_operations": [op.value for op in OperationType],
                "supported_algorithms": [alg.value for alg in RateLimitAlgorithm],
                "child_age_groups": list(self.child_age_limits.keys())
            }
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {"status": "unhealthy", "error": str(e)}


# FACTORY FUNCTIONS

def create_rate_limiting_service(
    redis_url: str = "redis://localhost:6379",
    use_redis: bool = True,
    redis_client: Optional[Any] = None
) -> RateLimitingService:
    """
    Create a production rate limiting service.
    
    Note: Call await service.start() from async context to enable cleanup.

    Args:
        redis_url: Redis connection URL
        use_redis: Whether to use Redis backend
        redis_client: Optional existing Redis client

    Returns:
        Configured RateLimitingService instance
    """
    return RateLimitingService(
        redis_client=redis_client,
        redis_url=redis_url,
        use_redis=use_redis,
        enable_cleanup=True
    )


def create_memory_rate_limiting_service() -> RateLimitingService:
    """Create a memory-only rate limiting service for testing."""
    return RateLimitingService(
        use_redis=False,
        enable_cleanup=True
    )


# ================================
# EXPORT SYMBOLS
# ================================

__all__ = [
    "RateLimitingService",
    "RateLimitResult",
    "RateLimitConfig",
    "OperationType",
    "RateLimitAlgorithm",
    "ChildAgeLimits",
    "create_rate_limiting_service",
    "create_memory_rate_limiting_service",
    "CHILD_AGE_LIMITS",
    "DEFAULT_RATE_LIMITS"
]
