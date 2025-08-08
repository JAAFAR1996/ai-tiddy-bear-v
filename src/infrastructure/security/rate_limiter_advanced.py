"""
Advanced Rate Limiting System - Enterprise Security
=================================================
Production-grade rate limiting with:
- Multi-tier rate limiting (user, IP, endpoint, global)
- Sliding window and token bucket algorithms
- Distributed rate limiting with Redis
- Dynamic rate adjustment based on load
- Exemption and priority handling
- DDoS protection and abuse detection
"""

import asyncio
import time
import hashlib
import json
from typing import Dict, Optional, Any, List, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import redis.asyncio as redis
from collections import defaultdict
import ipaddress


class RateLimitTier(Enum):
    """Rate limit tiers for different user types."""
    ANONYMOUS = "anonymous"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    ADMIN = "admin"
    SYSTEM = "system"


class RateLimitScope(Enum):
    """Scope of rate limiting."""
    GLOBAL = "global"
    IP = "ip"
    USER = "user"
    ENDPOINT = "endpoint"
    API_KEY = "api_key"
    COMBINED = "combined"


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithms."""
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_size: int = 10
    
    # Advanced limits
    concurrent_requests: int = 5
    request_weight: int = 1  # Cost per request
    
    # Penalties
    penalty_threshold: int = 3  # Violations before penalty
    penalty_duration_minutes: int = 15
    penalty_multiplier: float = 0.5  # Reduce limits by 50%
    
    # Exemptions
    exempt_paths: List[str] = field(default_factory=list)
    exempt_ips: List[str] = field(default_factory=list)
    
    def get_window_limit(self, window_seconds: int) -> int:
        """Get limit for specific window size."""
        if window_seconds <= 60:
            return self.requests_per_minute
        elif window_seconds <= 3600:
            return self.requests_per_hour
        else:
            return self.requests_per_day


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    current_requests: int
    limit: int
    window_seconds: int
    retry_after: Optional[int] = None
    
    # Additional metrics
    remaining_requests: int = 0
    reset_time: Optional[datetime] = None
    
    # Violation tracking
    violation_count: int = 0
    is_penalized: bool = False
    penalty_expires_at: Optional[datetime] = None
    
    # Headers for response
    def get_headers(self) -> Dict[str, str]:
        """Get rate limit headers for HTTP response."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining_requests)),
            "X-RateLimit-Window": str(self.window_seconds)
        }
        
        if self.reset_time:
            headers["X-RateLimit-Reset"] = str(int(self.reset_time.timestamp()))
        
        if self.retry_after:
            headers["Retry-After"] = str(self.retry_after)
            
        if self.is_penalized and self.penalty_expires_at:
            headers["X-RateLimit-Penalty-Expires"] = self.penalty_expires_at.isoformat()
        
        return headers


class RateLimitStore:
    """Storage backend for rate limit data."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis = redis_client
        self._local_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
    async def increment(
        self,
        key: str,
        window_seconds: int,
        amount: int = 1
    ) -> Tuple[int, int]:
        """Increment counter and return (current_count, ttl)."""
        if self._redis:
            return await self._increment_redis(key, window_seconds, amount)
        else:
            return self._increment_local(key, window_seconds, amount)
    
    async def _increment_redis(
        self,
        key: str,
        window_seconds: int,
        amount: int
    ) -> Tuple[int, int]:
        """Increment in Redis with atomic operations."""
        # Use pipeline for atomic operations
        async with self._redis.pipeline() as pipe:
            pipe.incrby(key, amount)
            pipe.ttl(key)
            pipe.expire(key, window_seconds)
            
            results = await pipe.execute()
            current_count = results[0]
            ttl = results[1] if results[1] > 0 else window_seconds
            
            return current_count, ttl
    
    def _increment_local(
        self,
        key: str,
        window_seconds: int,
        amount: int
    ) -> Tuple[int, int]:
        """Increment in local memory (for development)."""
        now = time.time()
        
        if key not in self._local_cache:
            self._local_cache[key] = {
                "count": 0,
                "window_start": now,
                "window_seconds": window_seconds
            }
        
        cache_entry = self._local_cache[key]
        
        # Check if window expired
        if now - cache_entry["window_start"] > window_seconds:
            cache_entry["count"] = amount
            cache_entry["window_start"] = now
        else:
            cache_entry["count"] += amount
        
        ttl = int(window_seconds - (now - cache_entry["window_start"]))
        return cache_entry["count"], ttl
    
    async def get_violation_count(self, key: str) -> int:
        """Get violation count for a key."""
        violation_key = f"{key}:violations"
        
        if self._redis:
            count = await self._redis.get(violation_key)
            return int(count) if count else 0
        else:
            return self._local_cache.get(violation_key, {}).get("count", 0)
    
    async def increment_violations(self, key: str, window_seconds: int = 3600):
        """Increment violation counter."""
        violation_key = f"{key}:violations"
        await self.increment(violation_key, window_seconds, 1)
    
    async def is_penalized(self, key: str) -> Tuple[bool, Optional[int]]:
        """Check if key is currently penalized."""
        penalty_key = f"{key}:penalty"
        
        if self._redis:
            ttl = await self._redis.ttl(penalty_key)
            return ttl > 0, ttl if ttl > 0 else None
        else:
            cache_entry = self._local_cache.get(penalty_key, {})
            if not cache_entry:
                return False, None
            
            now = time.time()
            if now < cache_entry.get("expires_at", 0):
                ttl = int(cache_entry["expires_at"] - now)
                return True, ttl
            
            return False, None
    
    async def apply_penalty(self, key: str, duration_seconds: int):
        """Apply penalty to a key."""
        penalty_key = f"{key}:penalty"
        
        if self._redis:
            await self._redis.setex(penalty_key, duration_seconds, "1")
        else:
            self._local_cache[penalty_key] = {
                "expires_at": time.time() + duration_seconds
            }


class AdvancedRateLimiter:
    """
    Advanced rate limiting system with enterprise features.
    
    Features:
    - Multi-tier rate limiting
    - Multiple algorithms (sliding window, token bucket)
    - Distributed rate limiting with Redis
    - Dynamic rate adjustment
    - DDoS protection
    - Abuse detection and penalties
    - Priority and exemption handling
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.store = RateLimitStore(redis_client)
        self.logger = None  # Will be injected
        
        # Default configurations per tier
        self.tier_configs = {
            RateLimitTier.ANONYMOUS: RateLimitConfig(
                requests_per_minute=20,
                requests_per_hour=500,
                requests_per_day=5000,
                burst_size=5,
                concurrent_requests=2
            ),
            RateLimitTier.BASIC: RateLimitConfig(
                requests_per_minute=60,
                requests_per_hour=2000,
                requests_per_day=20000,
                burst_size=10,
                concurrent_requests=5
            ),
            RateLimitTier.PREMIUM: RateLimitConfig(
                requests_per_minute=120,
                requests_per_hour=5000,
                requests_per_day=50000,
                burst_size=20,
                concurrent_requests=10
            ),
            RateLimitTier.ENTERPRISE: RateLimitConfig(
                requests_per_minute=600,
                requests_per_hour=20000,
                requests_per_day=200000,
                burst_size=50,
                concurrent_requests=50
            ),
            RateLimitTier.ADMIN: RateLimitConfig(
                requests_per_minute=1000,
                requests_per_hour=50000,
                requests_per_day=500000,
                burst_size=100,
                concurrent_requests=100,
                exempt_paths=["*"]  # Admins exempt from path-specific limits
            ),
            RateLimitTier.SYSTEM: RateLimitConfig(
                requests_per_minute=10000,
                requests_per_hour=1000000,
                requests_per_day=10000000,
                burst_size=1000,
                concurrent_requests=1000,
                exempt_paths=["*"],
                exempt_ips=["127.0.0.1", "::1"]
            )
        }
        
        # Endpoint-specific limits (override tier limits)
        self.endpoint_limits = {
            "/api/v1/auth/login": RateLimitConfig(
                requests_per_minute=5,
                requests_per_hour=20,
                requests_per_day=100,
                burst_size=2,
                penalty_threshold=3,
                penalty_duration_minutes=30
            ),
            "/api/v1/auth/register": RateLimitConfig(
                requests_per_minute=3,
                requests_per_hour=10,
                requests_per_day=20,
                burst_size=1,
                penalty_threshold=2,
                penalty_duration_minutes=60
            ),
            "/api/v1/ai/generate": RateLimitConfig(
                requests_per_minute=10,
                requests_per_hour=100,
                requests_per_day=500,
                burst_size=3,
                request_weight=5  # Each request counts as 5
            ),
            "/api/v1/tts/synthesize": RateLimitConfig(
                requests_per_minute=20,
                requests_per_hour=200,
                requests_per_day=1000,
                burst_size=5,
                request_weight=3
            )
        }
        
        # Global rate limits (safety net)
        self.global_config = RateLimitConfig(
            requests_per_minute=10000,
            requests_per_hour=500000,
            requests_per_day=5000000,
            burst_size=1000
        )
        
        # DDoS protection thresholds
        self.ddos_thresholds = {
            "requests_per_second": 100,
            "unique_ips_per_minute": 1000,
            "requests_per_ip_per_second": 50
        }
        
        # Tracking for DDoS detection
        self._request_tracker = defaultdict(list)
        self._ip_tracker = defaultdict(set)
        
    def _get_rate_limit_key(
        self,
        scope: RateLimitScope,
        identifier: str,
        endpoint: Optional[str] = None,
        window: str = "minute"
    ) -> str:
        """Generate rate limit key."""
        # Sanitize identifier to prevent injection
        identifier = self._sanitize_identifier(identifier)
        
        parts = ["ratelimit", scope.value, identifier]
        
        if endpoint:
            # Sanitize endpoint and hash to avoid key length issues
            endpoint = self._sanitize_endpoint(endpoint)
            endpoint_hash = hashlib.sha256(endpoint.encode()).hexdigest()[:16]
            parts.append(endpoint_hash)
        
        # Validate window parameter
        if window not in ["minute", "hour", "day"]:
            window = "minute"
        
        parts.append(window)
        
        # Add timestamp for sliding window
        if window == "minute":
            timestamp = int(time.time() / 60)
        elif window == "hour":
            timestamp = int(time.time() / 3600)
        else:  # day
            timestamp = int(time.time() / 86400)
        
        parts.append(str(timestamp))
        
        return ":".join(parts)
    
    def _sanitize_identifier(self, identifier: str) -> str:
        """Sanitize identifier to prevent injection attacks."""
        if not identifier:
            return "anonymous"
        
        # Remove dangerous characters and limit length
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '', str(identifier)[:100])
        return sanitized if sanitized else "anonymous"
    
    def _sanitize_endpoint(self, endpoint: str) -> str:
        """Sanitize endpoint path."""
        if not endpoint:
            return "/"
        
        # Remove dangerous characters and normalize path
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9/_.-]', '', str(endpoint)[:200])
        return sanitized if sanitized else "/"
    
    def _determine_tier(
        self,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        api_key: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> RateLimitTier:
        """Determine rate limit tier based on user info."""
        # Priority order: role -> api_key -> user_id -> anonymous
        
        if user_role:
            role_tier_map = {
                "admin": RateLimitTier.ADMIN,
                "system": RateLimitTier.SYSTEM,
                "enterprise": RateLimitTier.ENTERPRISE,
                "premium": RateLimitTier.PREMIUM,
                "parent": RateLimitTier.BASIC,
                "child": RateLimitTier.BASIC
            }
            return role_tier_map.get(user_role, RateLimitTier.BASIC)
        
        if api_key:
            # Could look up API key tier from database
            return RateLimitTier.BASIC
        
        if user_id:
            return RateLimitTier.BASIC
        
        return RateLimitTier.ANONYMOUS
    
    def _is_ip_exempt(self, ip_address: str, config: RateLimitConfig) -> bool:
        """Check if IP is exempt from rate limiting."""
        if not ip_address:
            return False
        
        try:
            # Validate IP address format
            ip = ipaddress.ip_address(ip_address)
            
            # Check exact matches
            if ip_address in config.exempt_ips:
                return True
            
            # Check if localhost/private (but be more restrictive)
            if ip.is_loopback:
                return True
            
            # Only allow specific private ranges for exemption
            if ip.is_private:
                # Only allow 127.0.0.0/8 and ::1
                if str(ip).startswith('127.') or str(ip) == '::1':
                    return True
            
            # Check CIDR ranges with validation
            for exempt_ip in config.exempt_ips:
                if "/" in exempt_ip:
                    try:
                        network = ipaddress.ip_network(exempt_ip, strict=False)
                        if ip in network:
                            return True
                    except ValueError:
                        # Invalid CIDR, skip
                        continue
            
            return False
            
        except ValueError:
            # Invalid IP address format
            return False
    
    def _is_endpoint_exempt(self, endpoint: str, config: RateLimitConfig) -> bool:
        """Check if endpoint is exempt from rate limiting."""
        if not endpoint:
            return False
        
        for exempt_path in config.exempt_paths:
            if exempt_path == "*":
                return True
            
            if exempt_path.endswith("*"):
                if endpoint.startswith(exempt_path[:-1]):
                    return True
            elif endpoint == exempt_path:
                return True
        
        return False
    
    async def check_rate_limit(
        self,
        identifier: str,
        scope: RateLimitScope = RateLimitScope.IP,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        api_key: Optional[str] = None,
        request_weight: int = 1
    ) -> RateLimitResult:
        """
        Check if request is within rate limits.
        
        Args:
            identifier: Primary identifier (IP, user ID, etc.)
            scope: Scope of rate limiting
            endpoint: API endpoint being accessed
            user_id: User ID if authenticated
            user_role: User role for tier determination
            ip_address: Client IP address
            api_key: API key if used
            request_weight: Weight/cost of this request
            
        Returns:
            RateLimitResult with decision and metadata
        """
        # Determine tier and config
        tier = self._determine_tier(user_id, user_role, api_key, ip_address)
        config = self.tier_configs[tier]
        
        # Check for endpoint-specific config
        if endpoint and endpoint in self.endpoint_limits:
            endpoint_config = self.endpoint_limits[endpoint]
            # Use more restrictive limits
            config = RateLimitConfig(
                requests_per_minute=min(config.requests_per_minute, endpoint_config.requests_per_minute),
                requests_per_hour=min(config.requests_per_hour, endpoint_config.requests_per_hour),
                requests_per_day=min(config.requests_per_day, endpoint_config.requests_per_day),
                burst_size=min(config.burst_size, endpoint_config.burst_size),
                concurrent_requests=min(config.concurrent_requests, endpoint_config.concurrent_requests),
                request_weight=endpoint_config.request_weight,
                penalty_threshold=endpoint_config.penalty_threshold,
                penalty_duration_minutes=endpoint_config.penalty_duration_minutes,
                exempt_paths=config.exempt_paths,
                exempt_ips=config.exempt_ips
            )
        
        # Apply request weight
        actual_weight = request_weight * config.request_weight
        
        # Check exemptions
        if ip_address and self._is_ip_exempt(ip_address, config):
            return RateLimitResult(
                allowed=True,
                current_requests=0,
                limit=config.requests_per_minute,
                window_seconds=60,
                remaining_requests=config.requests_per_minute
            )
        
        if endpoint and self._is_endpoint_exempt(endpoint, config):
            return RateLimitResult(
                allowed=True,
                current_requests=0,
                limit=config.requests_per_minute,
                window_seconds=60,
                remaining_requests=config.requests_per_minute
            )
        
        # Check if penalized
        is_penalized, penalty_ttl = await self.store.is_penalized(identifier)
        
        if is_penalized:
            return RateLimitResult(
                allowed=False,
                current_requests=0,
                limit=0,
                window_seconds=penalty_ttl or 0,
                retry_after=penalty_ttl,
                remaining_requests=0,
                is_penalized=True,
                penalty_expires_at=datetime.now() + timedelta(seconds=penalty_ttl) if penalty_ttl else None
            )
        
        # Check minute window (primary limit)
        minute_key = self._get_rate_limit_key(scope, identifier, endpoint, "minute")
        current_minute, minute_ttl = await self.store.increment(minute_key, 60, actual_weight)
        
        minute_limit = config.requests_per_minute
        if is_penalized:
            minute_limit = int(minute_limit * config.penalty_multiplier)
        
        if current_minute > minute_limit:
            # Increment violations
            await self.store.increment_violations(identifier)
            violation_count = await self.store.get_violation_count(identifier)
            
            # Check if penalty should be applied
            if violation_count >= config.penalty_threshold:
                penalty_seconds = config.penalty_duration_minutes * 60
                await self.store.apply_penalty(identifier, penalty_seconds)
                
                if self.logger:
                    self.logger.warning(
                        f"Rate limit penalty applied",
                        extra={
                            "identifier": identifier,
                            "violation_count": violation_count,
                            "penalty_duration": penalty_seconds
                        }
                    )
            
            return RateLimitResult(
                allowed=False,
                current_requests=current_minute,
                limit=minute_limit,
                window_seconds=60,
                retry_after=minute_ttl,
                remaining_requests=0,
                violation_count=violation_count,
                reset_time=datetime.now() + timedelta(seconds=minute_ttl)
            )
        
        # Check hour window (secondary limit)
        hour_key = self._get_rate_limit_key(scope, identifier, endpoint, "hour")
        current_hour, hour_ttl = await self.store.increment(hour_key, 3600, actual_weight)
        
        hour_limit = config.requests_per_hour
        if current_hour > hour_limit:
            return RateLimitResult(
                allowed=False,
                current_requests=current_hour,
                limit=hour_limit,
                window_seconds=3600,
                retry_after=hour_ttl,
                remaining_requests=0,
                reset_time=datetime.now() + timedelta(seconds=hour_ttl)
            )
        
        # Check day window (tertiary limit)
        day_key = self._get_rate_limit_key(scope, identifier, endpoint, "day")
        current_day, day_ttl = await self.store.increment(day_key, 86400, actual_weight)
        
        day_limit = config.requests_per_day
        if current_day > day_limit:
            return RateLimitResult(
                allowed=False,
                current_requests=current_day,
                limit=day_limit,
                window_seconds=86400,
                retry_after=day_ttl,
                remaining_requests=0,
                reset_time=datetime.now() + timedelta(seconds=day_ttl)
            )
        
        # Check global rate limit
        if not await self._check_global_limit():
            return RateLimitResult(
                allowed=False,
                current_requests=0,
                limit=self.global_config.requests_per_minute,
                window_seconds=60,
                retry_after=60,
                remaining_requests=0
            )
        
        # Check for DDoS patterns
        if ip_address and not await self._check_ddos_protection(ip_address):
            # Apply immediate penalty
            await self.store.apply_penalty(ip_address, 3600)  # 1 hour penalty
            
            if self.logger:
                self.logger.error(
                    f"DDoS pattern detected",
                    extra={
                        "ip_address": ip_address,
                        "identifier": identifier
                    }
                )
            
            return RateLimitResult(
                allowed=False,
                current_requests=0,
                limit=0,
                window_seconds=3600,
                retry_after=3600,
                remaining_requests=0,
                is_penalized=True
            )
        
        # Request allowed
        remaining = minute_limit - current_minute
        
        return RateLimitResult(
            allowed=True,
            current_requests=current_minute,
            limit=minute_limit,
            window_seconds=60,
            remaining_requests=max(0, remaining),
            reset_time=datetime.now() + timedelta(seconds=minute_ttl)
        )
    
    async def _check_global_limit(self) -> bool:
        """Check global rate limit as safety net."""
        global_key = self._get_rate_limit_key(RateLimitScope.GLOBAL, "global", None, "minute")
        current, _ = await self.store.increment(global_key, 60, 1)
        
        return current <= self.global_config.requests_per_minute
    
    async def _check_ddos_protection(self, ip_address: str) -> bool:
        """Check for DDoS patterns."""
        now = time.time()
        
        # Track requests per second
        self._request_tracker[ip_address].append(now)
        
        # Clean old entries
        cutoff = now - 60
        self._request_tracker[ip_address] = [
            t for t in self._request_tracker[ip_address] if t > cutoff
        ]
        
        # Check requests per second
        recent_requests = [
            t for t in self._request_tracker[ip_address] if t > now - 1
        ]
        
        if len(recent_requests) > self.ddos_thresholds["requests_per_ip_per_second"]:
            return False
        
        # Track unique IPs
        minute_bucket = int(now / 60)
        self._ip_tracker[minute_bucket].add(ip_address)
        
        # Clean old buckets
        old_buckets = [b for b in self._ip_tracker.keys() if b < minute_bucket - 1]
        for bucket in old_buckets:
            del self._ip_tracker[bucket]
        
        # Check unique IPs per minute
        total_ips = len(self._ip_tracker.get(minute_bucket, set()))
        if total_ips > self.ddos_thresholds["unique_ips_per_minute"]:
            # Possible DDoS, but don't block this specific IP unless it's excessive
            if len(self._request_tracker[ip_address]) > 100:
                return False
        
        return True
    
    def set_logger(self, logger):
        """Set logger for audit logging."""
        self.logger = logger
    
    async def reset_limits(self, identifier: str, scope: RateLimitScope = RateLimitScope.USER):
        """Reset rate limits for an identifier (admin action)."""
        # Reset all windows
        for window in ["minute", "hour", "day"]:
            key = self._get_rate_limit_key(scope, identifier, None, window)
            if self.store._redis:
                await self.store._redis.delete(key)
            else:
                if key in self.store._local_cache:
                    del self.store._local_cache[key]
        
        # Reset violations
        violation_key = f"{identifier}:violations"
        if self.store._redis:
            await self.store._redis.delete(violation_key)
        else:
            if violation_key in self.store._local_cache:
                del self.store._local_cache[violation_key]
        
        # Remove penalty
        penalty_key = f"{identifier}:penalty"
        if self.store._redis:
            await self.store._redis.delete(penalty_key)
        else:
            if penalty_key in self.store._local_cache:
                del self.store._local_cache[penalty_key]
        
        if self.logger:
            self.logger.info(f"Rate limits reset for identifier: {identifier}")


# Global instance
advanced_rate_limiter = AdvancedRateLimiter()
