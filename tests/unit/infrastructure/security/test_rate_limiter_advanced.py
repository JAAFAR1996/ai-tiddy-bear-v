"""
Tests for Advanced Rate Limiter
==============================

Critical security tests for rate limiting system.
"""

import pytest
from unittest.mock import Mock, AsyncMock
import time

from src.infrastructure.security.rate_limiter_advanced import (
    AdvancedRateLimiter,
    RateLimitTier,
    RateLimitScope,
    RateLimitConfig,
    RateLimitResult,
    RateLimitStore
)


class TestAdvancedRateLimiter:
    """Test advanced rate limiter."""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter instance."""
        return AdvancedRateLimiter()

    @pytest.fixture
    def mock_store(self):
        """Create mock rate limit store."""
        store = Mock(spec=RateLimitStore)
        store.increment = AsyncMock(return_value=(1, 60))
        store.get_violation_count = AsyncMock(return_value=0)
        store.is_penalized = AsyncMock(return_value=(False, None))
        store.increment_violations = AsyncMock(spec=True)
        store.apply_penalty = AsyncMock(spec=True)
        return store

    def test_initialization(self, rate_limiter):
        """Test rate limiter initialization."""
        assert len(rate_limiter.tier_configs) == 6
        assert RateLimitTier.ANONYMOUS in rate_limiter.tier_configs
        assert RateLimitTier.PREMIUM in rate_limiter.tier_configs

    def test_determine_tier_anonymous(self, rate_limiter):
        """Test tier determination for anonymous users."""
        tier = rate_limiter._determine_tier()
        assert tier == RateLimitTier.ANONYMOUS

    def test_determine_tier_by_role(self, rate_limiter):
        """Test tier determination by user role."""
        tier = rate_limiter._determine_tier(user_role="admin")
        assert tier == RateLimitTier.ADMIN
        
        tier = rate_limiter._determine_tier(user_role="premium")
        assert tier == RateLimitTier.PREMIUM

    def test_determine_tier_by_user_id(self, rate_limiter):
        """Test tier determination by user ID."""
        tier = rate_limiter._determine_tier(user_id="user123")
        assert tier == RateLimitTier.BASIC

    def test_is_ip_exempt_localhost(self, rate_limiter):
        """Test IP exemption for localhost."""
        config = RateLimitConfig(requests_per_minute=10, requests_per_hour=100, requests_per_day=1000)
        
        assert rate_limiter._is_ip_exempt("127.0.0.1", config) is True
        assert rate_limiter._is_ip_exempt("::1", config) is True
        assert rate_limiter._is_ip_exempt("192.168.1.1", config) is True

    def test_is_ip_exempt_configured(self, rate_limiter):
        """Test IP exemption for configured IPs."""
        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=1000,
            exempt_ips=["203.0.113.1", "192.168.0.0/24"]
        )
        
        assert rate_limiter._is_ip_exempt("203.0.113.1", config) is True
        assert rate_limiter._is_ip_exempt("192.168.0.100", config) is True
        assert rate_limiter._is_ip_exempt("8.8.8.8", config) is False

    def test_is_endpoint_exempt(self, rate_limiter):
        """Test endpoint exemption."""
        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=1000,
            exempt_paths=["/health", "/api/public/*"]
        )
        
        assert rate_limiter._is_endpoint_exempt("/health", config) is True
        assert rate_limiter._is_endpoint_exempt("/api/public/status", config) is True
        assert rate_limiter._is_endpoint_exempt("/api/private/data", config) is False

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter, mock_store):
        """Test rate limit check when request is allowed."""
        rate_limiter.store = mock_store
        
        result = await rate_limiter.check_rate_limit("user123", RateLimitScope.USER)
        
        assert result.allowed is True
        assert result.current_requests == 1
        assert result.remaining_requests > 0

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, rate_limiter, mock_store):
        """Test rate limit check when limit is exceeded."""
        rate_limiter.store = mock_store
        # Mock store to return count exceeding limit
        mock_store.increment.return_value = (100, 60)  # Exceeds anonymous limit
        
        result = await rate_limiter.check_rate_limit("user123", RateLimitScope.USER)
        
        assert result.allowed is False
        assert result.retry_after is not None

    @pytest.mark.asyncio
    async def test_check_rate_limit_penalized(self, rate_limiter, mock_store):
        """Test rate limit check when user is penalized."""
        rate_limiter.store = mock_store
        mock_store.is_penalized.return_value = (True, 300)  # 5 minutes penalty
        
        result = await rate_limiter.check_rate_limit("user123", RateLimitScope.USER)
        
        assert result.allowed is False
        assert result.is_penalized is True
        assert result.retry_after == 300

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_endpoint_config(self, rate_limiter, mock_store):
        """Test rate limit with endpoint-specific configuration."""
        rate_limiter.store = mock_store
        
        result = await rate_limiter.check_rate_limit(
            "user123",
            RateLimitScope.USER,
            endpoint="/api/v1/auth/login"
        )
        
        # Should use more restrictive login limits
        assert result.allowed is True
        assert result.limit <= 5  # Login endpoint limit

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_weight(self, rate_limiter, mock_store):
        """Test rate limit with request weight."""
        rate_limiter.store = mock_store
        
        result = await rate_limiter.check_rate_limit(
            "user123",
            RateLimitScope.USER,
            endpoint="/api/v1/ai/generate",
            request_weight=2
        )
        
        # Should account for request weight
        mock_store.increment.assert_called()
        # Weight should be multiplied by endpoint weight (5) = 10 total

    @pytest.mark.asyncio
    async def test_check_rate_limit_exempt_ip(self, rate_limiter, mock_store):
        """Test rate limit exemption for IP."""
        rate_limiter.store = mock_store
        
        result = await rate_limiter.check_rate_limit(
            "127.0.0.1",
            RateLimitScope.IP,
            ip_address="127.0.0.1"
        )
        
        assert result.allowed is True
        # Should not call store for exempt IPs
        mock_store.increment.assert_not_called()

    @pytest.mark.asyncio
    async def test_violation_tracking(self, rate_limiter, mock_store):
        """Test violation tracking and penalty application."""
        rate_limiter.store = mock_store
        mock_store.increment.return_value = (100, 60)  # Exceeds limit
        mock_store.get_violation_count.return_value = 3  # Exceeds threshold
        
        result = await rate_limiter.check_rate_limit("user123", RateLimitScope.USER)
        
        assert result.allowed is False
        mock_store.increment_violations.assert_called_once()
        mock_store.apply_penalty.assert_called_once()

    @pytest.mark.asyncio
    async def test_ddos_protection(self, rate_limiter):
        """Test DDoS protection mechanism."""
        # Simulate rapid requests from same IP
        ip = "203.0.113.1"
        
        # Fill request tracker to trigger DDoS detection
        now = time.time()
        rate_limiter._request_tracker[ip] = [now - i * 0.01 for i in range(60)]
        
        result = await rate_limiter._check_ddos_protection(ip)
        assert result is False

    @pytest.mark.asyncio
    async def test_global_limit_check(self, rate_limiter, mock_store):
        """Test global rate limit check."""
        rate_limiter.store = mock_store
        mock_store.increment.return_value = (10001, 60)  # Exceeds global limit
        
        result = await rate_limiter._check_global_limit()
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_limits(self, rate_limiter):
        """Test resetting rate limits."""
        mock_redis = Mock(spec=True)
        mock_redis.delete = AsyncMock(spec=True)
        rate_limiter.store._redis = mock_redis
        
        await rate_limiter.reset_limits("user123", RateLimitScope.USER)
        
        # Should delete multiple keys
        assert mock_redis.delete.call_count >= 3

    def test_rate_limit_key_generation(self, rate_limiter):
        """Test rate limit key generation."""
        key = rate_limiter._get_rate_limit_key(
            RateLimitScope.USER,
            "user123",
            "/api/test",
            "minute"
        )
        
        assert "ratelimit" in key
        assert "user" in key
        assert "user123" in key

    def test_tier_config_values(self, rate_limiter):
        """Test tier configuration values."""
        anonymous_config = rate_limiter.tier_configs[RateLimitTier.ANONYMOUS]
        premium_config = rate_limiter.tier_configs[RateLimitTier.PREMIUM]
        
        # Premium should have higher limits than anonymous
        assert premium_config.requests_per_minute > anonymous_config.requests_per_minute
        assert premium_config.requests_per_hour > anonymous_config.requests_per_hour
        assert premium_config.concurrent_requests > anonymous_config.concurrent_requests

    def test_endpoint_specific_limits(self, rate_limiter):
        """Test endpoint-specific rate limits."""
        login_config = rate_limiter.endpoint_limits["/api/v1/auth/login"]
        ai_config = rate_limiter.endpoint_limits["/api/v1/ai/generate"]
        
        # Login should be more restrictive
        assert login_config.requests_per_minute < ai_config.requests_per_minute
        assert login_config.penalty_threshold <= 3
        assert ai_config.request_weight > 1

    def test_logger_integration(self, rate_limiter):
        """Test logger integration."""
        mock_logger = Mock(spec=True)
        rate_limiter.set_logger(mock_logger)
        
        assert rate_limiter.logger == mock_logger


class TestRateLimitResult:
    """Test rate limit result."""

    def test_get_headers(self):
        """Test getting HTTP headers from result."""
        result = RateLimitResult(
            allowed=True,
            current_requests=5,
            limit=100,
            window_seconds=60,
            remaining_requests=95
        )
        
        headers = result.get_headers()
        
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "95"
        assert headers["X-RateLimit-Window"] == "60"

    def test_get_headers_with_retry_after(self):
        """Test headers with retry-after."""
        result = RateLimitResult(
            allowed=False,
            current_requests=101,
            limit=100,
            window_seconds=60,
            retry_after=30,
            remaining_requests=0
        )
        
        headers = result.get_headers()
        
        assert headers["Retry-After"] == "30"
        assert headers["X-RateLimit-Remaining"] == "0"


class TestRateLimitStore:
    """Test rate limit store."""

    @pytest.fixture
    def store(self):
        """Create rate limit store."""
        return RateLimitStore()

    @pytest.mark.asyncio
    async def test_increment_local(self, store):
        """Test local increment."""
        count, ttl = await store.increment("test_key", 60, 1)
        
        assert count == 1
        assert ttl <= 60

    @pytest.mark.asyncio
    async def test_increment_multiple(self, store):
        """Test multiple increments."""
        await store.increment("test_key", 60, 1)
        count, ttl = await store.increment("test_key", 60, 1)
        
        assert count == 2

    @pytest.mark.asyncio
    async def test_violation_tracking(self, store):
        """Test violation count tracking."""
        await store.increment_violations("user123")
        count = await store.get_violation_count("user123")
        
        assert count == 1

    @pytest.mark.asyncio
    async def test_penalty_application(self, store):
        """Test penalty application and checking."""
        await store.apply_penalty("user123", 300)
        is_penalized, ttl = await store.is_penalized("user123")
        
        assert is_penalized is True
        assert ttl is not None


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_get_window_limit(self):
        """Test getting limit for specific window."""
        config = RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=1000,
            requests_per_day=10000
        )
        
        assert config.get_window_limit(30) == 60  # minute
        assert config.get_window_limit(1800) == 1000  # hour
        assert config.get_window_limit(43200) == 10000  # day

    def test_default_values(self):
        """Test default configuration values."""
        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=1000
        )
        
        assert config.burst_size == 10
        assert config.concurrent_requests == 5
        assert config.request_weight == 1
        assert config.penalty_threshold == 3