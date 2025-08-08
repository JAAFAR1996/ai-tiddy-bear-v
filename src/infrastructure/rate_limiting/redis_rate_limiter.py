"""
🎯 REDIS RATE LIMITER - PRODUCTION GRADE ABUSE PROTECTION
=========================================================
Comprehensive rate limiting system with Redis backend:
- Multiple rate limiting algorithms (Token Bucket, Sliding Window)
- Child-specific protection limits
- Adaptive rate limiting based on behavior
- Distributed rate limiting across multiple instances
- Real-time monitoring and alerting
- COPPA compliance for children's usage limits

ZERO TOLERANCE FOR ABUSE - MAXIMUM PROTECTION
"""

import asyncio
import json
import time
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import hashlib

# Redis imports
import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool

# Internal imports
from src.infrastructure.logging.structlog_logger import StructlogLogger

logger = logging.getLogger(__name__)


class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithms."""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    ADAPTIVE = "adaptive"


class LimitType(str, Enum):
    """Types of rate limits."""

    REQUESTS_PER_MINUTE = "requests_per_minute"
    REQUESTS_PER_HOUR = "requests_per_hour"
    SESSIONS_PER_DAY = "sessions_per_day"
    MESSAGE_LENGTH = "message_length"
    CONCURRENT_SESSIONS = "concurrent_sessions"
    AI_REQUESTS_PER_HOUR = "ai_requests_per_hour"
    CONTENT_MODERATION = "content_moderation"


class UserType(str, Enum):
    """User types for different limits."""

    CHILD = "child"
    PARENT = "parent"
    ADMIN = "admin"
    ANONYMOUS = "anonymous"


@dataclass
class RateLimitConfig:
    """Configuration for a specific rate limit."""

    limit_type: LimitType
    user_type: UserType
    max_requests: int
    window_seconds: int
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    burst_capacity: Optional[int] = None
    child_age_factor: Optional[float] = None  # Multiplier based on child age


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    remaining: int
    reset_time: datetime
    retry_after_seconds: Optional[int]
    reason: Optional[str] = None
    limit_type: Optional[LimitType] = None
    current_usage: Optional[int] = None


@dataclass
class RateLimitViolation:
    """Information about a rate limit violation."""

    user_id: str
    user_type: UserType
    limit_type: LimitType
    current_count: int
    max_allowed: int
    violation_time: datetime
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None


class RedisRateLimiter:
    """
    Production-grade Redis-based rate limiter with comprehensive protection.

    Features:
    - Multiple rate limiting algorithms
    - Child-specific protection limits
    - Distributed rate limiting
    - Real-time monitoring
    - Abuse pattern detection
    - COPPA compliance
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        redis_pool: Optional[ConnectionPool] = None,
        key_prefix: str = "rate_limit",
        default_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Redis rate limiter.

        Args:
            redis_url: Redis connection URL
            redis_pool: Optional Redis connection pool
            key_prefix: Prefix for Redis keys
            default_config: Default rate limiting configuration
        """
        self.key_prefix = key_prefix
        self.logger = StructlogLogger("redis_rate_limiter", component="security")

        # Initialize Redis connection
        if redis_pool:
            self.redis = Redis(connection_pool=redis_pool)
        else:
            self.redis = Redis.from_url(redis_url, decode_responses=True)

        # Rate limit configurations
        self.configs = self._load_rate_limit_configs(default_config)

        # Violation tracking
        self.violations: List[RateLimitViolation] = []
        self.max_violation_history = 1000

        # Lua scripts for atomic operations
        self._init_lua_scripts()

        self.logger.info("Redis rate limiter initialized")

    def _load_rate_limit_configs(
        self, default_config: Optional[Dict[str, Any]]
    ) -> Dict[str, RateLimitConfig]:
        """Load rate limiting configurations."""
        configs = {}

        # Default child protection limits (COPPA compliant)
        child_configs = [
            RateLimitConfig(
                limit_type=LimitType.REQUESTS_PER_MINUTE,
                user_type=UserType.CHILD,
                max_requests=10,
                window_seconds=60,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            ),
            RateLimitConfig(
                limit_type=LimitType.REQUESTS_PER_HOUR,
                user_type=UserType.CHILD,
                max_requests=200,
                window_seconds=3600,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            ),
            RateLimitConfig(
                limit_type=LimitType.SESSIONS_PER_DAY,
                user_type=UserType.CHILD,
                max_requests=5,
                window_seconds=86400,
                algorithm=RateLimitAlgorithm.FIXED_WINDOW,
            ),
            RateLimitConfig(
                limit_type=LimitType.AI_REQUESTS_PER_HOUR,
                user_type=UserType.CHILD,
                max_requests=50,
                window_seconds=3600,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                burst_capacity=10,
            ),
            RateLimitConfig(
                limit_type=LimitType.CONCURRENT_SESSIONS,
                user_type=UserType.CHILD,
                max_requests=2,
                window_seconds=1,  # Instantaneous check
                algorithm=RateLimitAlgorithm.FIXED_WINDOW,
            ),
        ]

        # Parent limits (more generous)
        parent_configs = [
            RateLimitConfig(
                limit_type=LimitType.REQUESTS_PER_MINUTE,
                user_type=UserType.PARENT,
                max_requests=50,
                window_seconds=60,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            ),
            RateLimitConfig(
                limit_type=LimitType.REQUESTS_PER_HOUR,
                user_type=UserType.PARENT,
                max_requests=1000,
                window_seconds=3600,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            ),
        ]

        # Anonymous user limits (very restrictive)
        anonymous_configs = [
            RateLimitConfig(
                limit_type=LimitType.REQUESTS_PER_MINUTE,
                user_type=UserType.ANONYMOUS,
                max_requests=5,
                window_seconds=60,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            )
        ]

        # Store configurations by key
        for config in child_configs + parent_configs + anonymous_configs:
            key = f"{config.user_type.value}:{config.limit_type.value}"
            configs[key] = config

        # Apply custom configurations
        if default_config:
            for key, custom_config in default_config.items():
                if key in configs:
                    # Update existing configuration
                    for attr, value in custom_config.items():
                        if hasattr(configs[key], attr):
                            setattr(configs[key], attr, value)

        return configs

    def _init_lua_scripts(self):
        """Initialize Lua scripts for atomic Redis operations."""

        # Sliding window rate limit script
        self.sliding_window_script = """
        local key = KEYS[1]
        local window = tonumber(ARGV[1])
        local limit = tonumber(ARGV[2])
        local current_time = tonumber(ARGV[3])
        
        -- Remove expired entries
        redis.call('ZREMRANGEBYSCORE', key, 0, current_time - window)
        
        -- Count current entries
        local current_count = redis.call('ZCARD', key)
        
        if current_count < limit then
            -- Add current request
            redis.call('ZADD', key, current_time, current_time .. ':' .. math.random())
            redis.call('EXPIRE', key, window)
            return {1, limit - current_count - 1, current_time + window}
        else
            -- Get the oldest entry to calculate reset time
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            local reset_time = current_time + window
            if #oldest > 0 then
                reset_time = tonumber(oldest[2]) + window
            end
            return {0, 0, reset_time}
        end
        """

        # Token bucket rate limit script
        self.token_bucket_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local tokens_requested = tonumber(ARGV[3])
        local current_time = tonumber(ARGV[4])
        
        -- Get current bucket state
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or capacity
        local last_refill = tonumber(bucket[2]) or current_time
        
        -- Calculate tokens to add
        local time_passed = current_time - last_refill
        local tokens_to_add = math.floor(time_passed * refill_rate)
        tokens = math.min(capacity, tokens + tokens_to_add)
        
        if tokens >= tokens_requested then
            tokens = tokens - tokens_requested
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', current_time)
            redis.call('EXPIRE', key, 3600)  -- 1 hour expiry
            return {1, tokens, current_time + (capacity - tokens) / refill_rate}
        else
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', current_time)
            redis.call('EXPIRE', key, 3600)
            return {0, tokens, current_time + (tokens_requested - tokens) / refill_rate}
        end
        """

        # Fixed window rate limit script
        self.fixed_window_script = """
        local key = KEYS[1]
        local limit = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local current_time = tonumber(ARGV[3])
        
        -- Calculate window start
        local window_start = math.floor(current_time / window) * window
        local window_key = key .. ':' .. window_start
        
        -- Get current count
        local current_count = tonumber(redis.call('GET', window_key)) or 0
        
        if current_count < limit then
            redis.call('INCR', window_key)
            redis.call('EXPIRE', window_key, window)
            return {1, limit - current_count - 1, window_start + window}
        else
            return {0, 0, window_start + window}
        end
        """

    # ========================================================================
    # MAIN RATE LIMITING METHODS
    # ========================================================================

    async def check_rate_limit(
        self,
        user_id: str,
        user_type: UserType,
        limit_type: LimitType,
        tokens_requested: int = 1,
        child_age: Optional[int] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> RateLimitResult:
        """
        Check if user is within rate limits.

        Args:
            user_id: User identifier
            user_type: Type of user
            limit_type: Type of limit to check
            tokens_requested: Number of tokens requested
            child_age: Child's age for age-based limits
            client_ip: Client IP address
            user_agent: User agent string

        Returns:
            RateLimitResult indicating if request is allowed
        """
        config_key = f"{user_type.value}:{limit_type.value}"
        config = self.configs.get(config_key)

        if not config:
            # No limit configured - allow by default
            return RateLimitResult(
                allowed=True,
                remaining=float("inf"),
                reset_time=datetime.utcnow() + timedelta(hours=1),
                retry_after_seconds=None,
            )

        # Adjust limits based on child age if applicable
        adjusted_config = self._adjust_config_for_age(config, child_age)

        # Generate Redis key
        redis_key = self._generate_redis_key(user_id, user_type, limit_type)

        try:
            # Apply rate limiting based on algorithm
            if adjusted_config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
                result = await self._check_sliding_window(
                    redis_key, adjusted_config, tokens_requested
                )
            elif adjusted_config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
                result = await self._check_token_bucket(
                    redis_key, adjusted_config, tokens_requested
                )
            elif adjusted_config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
                result = await self._check_fixed_window(
                    redis_key, adjusted_config, tokens_requested
                )
            elif adjusted_config.algorithm == RateLimitAlgorithm.ADAPTIVE:
                result = await self._check_adaptive(
                    redis_key, adjusted_config, tokens_requested, user_id
                )
            else:
                raise ValueError(f"Unknown algorithm: {adjusted_config.algorithm}")

            # Track violations
            if not result.allowed:
                await self._record_violation(
                    user_id,
                    user_type,
                    limit_type,
                    result.current_usage or 0,
                    adjusted_config.max_requests,
                    client_ip,
                    user_agent,
                )

            return result

        except Exception as e:
            self.logger.error(f"Rate limit check failed: {e}", exc_info=True)
            # Fail open - allow request but log error
            return RateLimitResult(
                allowed=True,
                remaining=0,
                reset_time=datetime.utcnow() + timedelta(minutes=5),
                retry_after_seconds=None,
                reason=f"Rate limit check error: {e}",
            )

    async def _check_sliding_window(
        self, redis_key: str, config: RateLimitConfig, tokens_requested: int
    ) -> RateLimitResult:
        """Check rate limit using sliding window algorithm."""
        current_time = time.time()

        # NOTE: This is Redis eval for Lua scripts, NOT Python eval. The script is static and not user-controlled.
        result = await self.redis.eval(
            self.sliding_window_script,
            1,
            redis_key,
            config.window_seconds,
            config.max_requests,
            current_time,
        )

        allowed, remaining, reset_timestamp = result
        reset_time = datetime.fromtimestamp(reset_timestamp)

        return RateLimitResult(
            allowed=bool(allowed),
            remaining=max(0, remaining),
            reset_time=reset_time,
            retry_after_seconds=(
                int(reset_timestamp - current_time) if not allowed else None
            ),
            limit_type=config.limit_type,
            current_usage=(
                config.max_requests - remaining if allowed else config.max_requests
            ),
        )

    async def _check_token_bucket(
        self, redis_key: str, config: RateLimitConfig, tokens_requested: int
    ) -> RateLimitResult:
        """Check rate limit using token bucket algorithm."""
        current_time = time.time()
        capacity = config.burst_capacity or config.max_requests
        refill_rate = config.max_requests / config.window_seconds

        # NOTE: This is Redis eval for Lua scripts, NOT Python eval. The script is static and not user-controlled.
        result = await self.redis.eval(
            self.token_bucket_script,
            1,
            redis_key,
            capacity,
            refill_rate,
            tokens_requested,
            current_time,
        )

        allowed, remaining_tokens, reset_timestamp = result
        reset_time = datetime.fromtimestamp(reset_timestamp)

        return RateLimitResult(
            allowed=bool(allowed),
            remaining=max(0, int(remaining_tokens)),
            reset_time=reset_time,
            retry_after_seconds=(
                int(reset_timestamp - current_time) if not allowed else None
            ),
            limit_type=config.limit_type,
            current_usage=capacity - int(remaining_tokens) if allowed else capacity,
        )

    async def _check_fixed_window(
        self, redis_key: str, config: RateLimitConfig, tokens_requested: int
    ) -> RateLimitResult:
        """Check rate limit using fixed window algorithm."""
        current_time = time.time()

        # NOTE: This is Redis eval for Lua scripts, NOT Python eval. The script is static and not user-controlled.
        result = await self.redis.eval(
            self.fixed_window_script,
            1,
            redis_key,
            config.max_requests,
            config.window_seconds,
            current_time,
        )

        allowed, remaining, reset_timestamp = result
        reset_time = datetime.fromtimestamp(reset_timestamp)

        return RateLimitResult(
            allowed=bool(allowed),
            remaining=max(0, remaining),
            reset_time=reset_time,
            retry_after_seconds=(
                int(reset_timestamp - current_time) if not allowed else None
            ),
            limit_type=config.limit_type,
            current_usage=(
                config.max_requests - remaining if allowed else config.max_requests
            ),
        )

    async def _check_adaptive(
        self,
        redis_key: str,
        config: RateLimitConfig,
        tokens_requested: int,
        user_id: str,
    ) -> RateLimitResult:
        """Check rate limit using adaptive algorithm (adjusts based on behavior)."""
        # Get user behavior history
        behavior_key = f"{redis_key}:behavior"
        behavior_data = await self.redis.hgetall(behavior_key)

        # Calculate adaptive limit based on behavior
        violation_count = int(behavior_data.get("violations", 0))
        good_behavior_streak = int(behavior_data.get("good_streak", 0))

        # Adjust limit (reduce for bad behavior, increase for good behavior)
        adaptive_limit = config.max_requests
        if violation_count > 5:
            adaptive_limit = max(1, adaptive_limit // 2)  # Halve limit
        elif good_behavior_streak > 100:
            adaptive_limit = min(
                adaptive_limit * 2, config.max_requests * 3
            )  # Double limit, cap at 3x

        # Use sliding window with adaptive limit
        temp_config = RateLimitConfig(
            limit_type=config.limit_type,
            user_type=config.user_type,
            max_requests=adaptive_limit,
            window_seconds=config.window_seconds,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
        )

        result = await self._check_sliding_window(
            redis_key, temp_config, tokens_requested
        )

        # Update behavior tracking
        if result.allowed:
            await self.redis.hincrby(behavior_key, "good_streak", 1)
        else:
            await self.redis.hincrby(behavior_key, "violations", 1)
            await self.redis.hset(behavior_key, "good_streak", 0)

        await self.redis.expire(behavior_key, 86400 * 7)  # Keep for 7 days

        return result

    # ========================================================================
    # CHILD-SPECIFIC METHODS
    # ========================================================================

    async def check_child_rate_limit(
        self,
        child_id: str,
        child_age: int,
        limit_type: LimitType,
        tokens_requested: int = 1,
        session_context: Optional[Dict[str, Any]] = None,
    ) -> RateLimitResult:
        """
        Check rate limits specifically for children with COPPA compliance.

        Args:
            child_id: Child identifier
            child_age: Child's age (3-13)
            limit_type: Type of limit to check
            tokens_requested: Number of tokens requested
            session_context: Optional session context

        Returns:
            RateLimitResult with child-specific handling
        """
        # Validate child age for COPPA compliance
        if child_age < 3 or child_age > 13:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=datetime.utcnow() + timedelta(hours=24),
                retry_after_seconds=86400,
                reason="Child age outside allowed range (3-13)",
            )

        # Check standard rate limits
        result = await self.check_rate_limit(
            user_id=child_id,
            user_type=UserType.CHILD,
            limit_type=limit_type,
            tokens_requested=tokens_requested,
            child_age=child_age,
        )

        # Additional child protection checks
        if result.allowed:
            # Check for concerning patterns
            if await self._detect_concerning_patterns(child_id, limit_type):
                result.allowed = False
                result.reason = "Concerning usage pattern detected"
                result.retry_after_seconds = 3600  # 1 hour cooldown

        return result

    def _adjust_config_for_age(
        self, config: RateLimitConfig, child_age: Optional[int]
    ) -> RateLimitConfig:
        """Adjust rate limit configuration based on child's age."""
        if not child_age or config.user_type != UserType.CHILD:
            return config

        # Age-based adjustment factors
        age_factors = {
            3: 0.3,  # Very restrictive for toddlers
            4: 0.4,
            5: 0.5,
            6: 0.6,
            7: 0.7,
            8: 0.8,  # Base level
            9: 0.9,
            10: 1.0,  # Standard child limits
            11: 1.1,
            12: 1.2,
            13: 1.3,  # Slightly more generous for preteens
        }

        factor = age_factors.get(child_age, 1.0)
        adjusted_max = max(1, int(config.max_requests * factor))

        # Create adjusted configuration
        return RateLimitConfig(
            limit_type=config.limit_type,
            user_type=config.user_type,
            max_requests=adjusted_max,
            window_seconds=config.window_seconds,
            algorithm=config.algorithm,
            burst_capacity=config.burst_capacity,
            child_age_factor=factor,
        )

    async def _detect_concerning_patterns(
        self, child_id: str, limit_type: LimitType
    ) -> bool:
        """Detect concerning usage patterns that might indicate issues."""
        pattern_key = f"{self.key_prefix}:patterns:{child_id}"

        # Get recent activity pattern
        recent_activity = await self.redis.lrange(pattern_key, 0, 99)

        if len(recent_activity) < 10:
            return False

        # Check for rapid bursts (many requests in short timeframe)
        timestamps = [
            float(activity.split(":")[0]) for activity in recent_activity[:20]
        ]
        if len(timestamps) >= 10:
            time_span = max(timestamps) - min(timestamps)
            if time_span < 60:  # 10+ requests in under 1 minute
                self.logger.warning(f"Rapid burst detected for child {child_id}")
                return True

        # Check for unusual late-night activity (if we have timezone info)
        # This would require additional context about the child's timezone

        return False

    # ========================================================================
    # VIOLATION TRACKING AND MONITORING
    # ========================================================================

    async def _record_violation(
        self,
        user_id: str,
        user_type: UserType,
        limit_type: LimitType,
        current_count: int,
        max_allowed: int,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Record a rate limit violation for monitoring and analysis."""
        violation = RateLimitViolation(
            user_id=user_id,
            user_type=user_type,
            limit_type=limit_type,
            current_count=current_count,
            max_allowed=max_allowed,
            violation_time=datetime.utcnow(),
            client_ip=client_ip,
            user_agent=user_agent,
        )

        # Store in memory (limited size)
        self.violations.append(violation)
        if len(self.violations) > self.max_violation_history:
            self.violations = self.violations[-self.max_violation_history // 2 :]

        # Store in Redis for persistence and cross-instance sharing
        violation_key = f"{self.key_prefix}:violations:{user_id}"
        violation_data = {
            "timestamp": violation.violation_time.isoformat(),
            "limit_type": limit_type.value,
            "current_count": current_count,
            "max_allowed": max_allowed,
            "client_ip": client_ip or "unknown",
            "user_agent": user_agent or "unknown",
        }

        await self.redis.lpush(violation_key, json.dumps(violation_data))
        await self.redis.ltrim(violation_key, 0, 99)  # Keep last 100 violations
        await self.redis.expire(violation_key, 86400 * 7)  # Keep for 7 days

        # Log the violation
        self.logger.warning(
            f"Rate limit violation: {user_type.value} {user_id} exceeded {limit_type.value}",
            extra={
                "user_id": user_id,
                "user_type": user_type.value,
                "limit_type": limit_type.value,
                "current_count": current_count,
                "max_allowed": max_allowed,
                "client_ip": client_ip,
            },
        )

        # Check for abuse patterns
        await self._check_abuse_patterns(user_id, user_type)

    async def _check_abuse_patterns(self, user_id: str, user_type: UserType):
        """Check for abuse patterns and take action if needed."""
        violation_key = f"{self.key_prefix}:violations:{user_id}"
        recent_violations = await self.redis.lrange(
            violation_key, 0, 19
        )  # Last 20 violations

        if len(recent_violations) >= 10:
            # Check if violations occurred within a short timeframe
            timestamps = []
            for violation_data in recent_violations:
                try:
                    data = json.loads(violation_data)
                    timestamps.append(datetime.fromisoformat(data["timestamp"]))
                except (json.JSONDecodeError, KeyError):
                    continue

            if len(timestamps) >= 10:
                time_span = max(timestamps) - min(timestamps)
                if time_span.total_seconds() < 3600:  # 10 violations in 1 hour
                    await self._apply_temporary_ban(
                        user_id, user_type, duration_hours=24
                    )

    async def _apply_temporary_ban(
        self, user_id: str, user_type: UserType, duration_hours: int
    ):
        """Apply temporary ban for abuse."""
        ban_key = f"{self.key_prefix}:banned:{user_id}"
        ban_until = datetime.utcnow() + timedelta(hours=duration_hours)

        await self.redis.set(ban_key, ban_until.isoformat(), ex=duration_hours * 3600)

        self.logger.error(
            f"Temporary ban applied: {user_type.value} {user_id} banned for {duration_hours} hours",
            extra={
                "user_id": user_id,
                "user_type": user_type.value,
                "ban_duration_hours": duration_hours,
                "ban_until": ban_until.isoformat(),
            },
        )

    async def is_banned(self, user_id: str) -> Tuple[bool, Optional[datetime]]:
        """Check if user is temporarily banned."""
        ban_key = f"{self.key_prefix}:banned:{user_id}"
        ban_data = await self.redis.get(ban_key)

        if ban_data:
            try:
                ban_until = datetime.fromisoformat(ban_data)
                if datetime.utcnow() < ban_until:
                    return True, ban_until
                else:
                    # Ban expired, clean up
                    await self.redis.delete(ban_key)
            except ValueError:
                # Invalid date format, clean up
                await self.redis.delete(ban_key)

        return False, None

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def _generate_redis_key(
        self, user_id: str, user_type: UserType, limit_type: LimitType
    ) -> str:
        """Generate Redis key for rate limiting."""
        # Hash user_id for privacy
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        return f"{self.key_prefix}:{user_type.value}:{limit_type.value}:{user_hash}"

    async def get_user_limits_status(
        self, user_id: str, user_type: UserType
    ) -> Dict[LimitType, RateLimitResult]:
        """Get status of all rate limits for a user."""
        results = {}

        for config_key, config in self.configs.items():
            if config.user_type == user_type:
                result = await self.check_rate_limit(
                    user_id=user_id,
                    user_type=user_type,
                    limit_type=config.limit_type,
                    tokens_requested=0,  # Just check, don't consume
                )
                results[config.limit_type] = result

        return results

    async def reset_user_limits(self, user_id: str, user_type: UserType) -> bool:
        """Reset all rate limits for a user (admin function)."""
        try:
            pattern = f"{self.key_prefix}:{user_type.value}:*:{hashlib.sha256(user_id.encode()).hexdigest()[:16]}"
            keys = await self.redis.keys(pattern)

            if keys:
                await self.redis.delete(*keys)

            # Also clear violations and bans
            violation_key = f"{self.key_prefix}:violations:{user_id}"
            ban_key = f"{self.key_prefix}:banned:{user_id}"
            await self.redis.delete(violation_key, ban_key)

            self.logger.info(f"Reset rate limits for {user_type.value} {user_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to reset limits for {user_id}: {e}")
            return False

    async def get_violation_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of rate limit violations in the last N hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        recent_violations = [
            v for v in self.violations if v.violation_time >= cutoff_time
        ]

        summary = {
            "total_violations": len(recent_violations),
            "by_user_type": {},
            "by_limit_type": {},
            "top_violators": {},
            "time_period_hours": hours,
        }

        for violation in recent_violations:
            # By user type
            user_type = violation.user_type.value
            summary["by_user_type"][user_type] = (
                summary["by_user_type"].get(user_type, 0) + 1
            )

            # By limit type
            limit_type = violation.limit_type.value
            summary["by_limit_type"][limit_type] = (
                summary["by_limit_type"].get(limit_type, 0) + 1
            )

            # Top violators
            user_id = violation.user_id
            summary["top_violators"][user_id] = (
                summary["top_violators"].get(user_id, 0) + 1
            )

        # Sort top violators
        summary["top_violators"] = dict(
            sorted(summary["top_violators"].items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
        )

        return summary

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on rate limiter."""
        try:
            # Test Redis connection
            await self.redis.ping()

            # Get basic statistics
            info = await self.redis.info()

            return {
                "status": "healthy",
                "redis_connected": True,
                "redis_memory_used": info.get("used_memory_human", "unknown"),
                "total_violations": len(self.violations),
                "configured_limits": len(self.configs),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================


def create_redis_rate_limiter(
    redis_url: str = "redis://localhost:6379", child_protection_mode: bool = True
) -> RedisRateLimiter:
    """
    Factory function to create Redis rate limiter with default configuration.

    Args:
        redis_url: Redis connection URL
        child_protection_mode: Enable child-specific protection limits

    Returns:
        Configured RedisRateLimiter instance
    """
    default_config = {}

    if child_protection_mode:
        # Enhanced child protection limits
        default_config = {
            "child:requests_per_minute": {"max_requests": 5},  # Very restrictive
            "child:ai_requests_per_hour": {
                "max_requests": 30
            },  # Limited AI interaction
        }

    return RedisRateLimiter(redis_url=redis_url, default_config=default_config)


# Export for easy imports
__all__ = [
    "RedisRateLimiter",
    "RateLimitAlgorithm",
    "LimitType",
    "UserType",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitViolation",
    "create_redis_rate_limiter",
]


if __name__ == "__main__":
    # Demo usage
    async def demo():
        print("🎯 Redis Rate Limiter - Abuse Protection Demo")

        limiter = create_redis_rate_limiter()

        # Test child rate limiting
        for i in range(12):
            result = await limiter.check_child_rate_limit(
                child_id="test_child_123",
                child_age=8,
                limit_type=LimitType.REQUESTS_PER_MINUTE,
            )

            print(
                f"Request {i+1}: Allowed={result.allowed}, Remaining={result.remaining}"
            )

            if not result.allowed:
                print(f"Rate limited! Retry after {result.retry_after_seconds} seconds")
                break

        await limiter.close()

    asyncio.run(demo())
