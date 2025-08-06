"""
Tests for unified rate limiting service.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from src.infrastructure.rate_limiting.rate_limiter import (
    RateLimitingService,
    OperationType,
    RateLimitResult,
    RateLimitAlgorithm,
    ChildAgeLimits,
    create_rate_limiting_service,
    create_memory_rate_limiting_service
)


class TestRateLimitingService:
    """Test unified rate limiting service."""

    @pytest.fixture
    def service(self):
        """Create rate limiting service with memory backend."""
        return create_memory_rate_limiting_service()

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, service):
        """Test rate limit check when request is allowed."""
        child_id = "child123"
        operation = OperationType.AI_REQUEST
        
        result = await service.check_rate_limit(child_id, operation, child_age=8)
        
        assert isinstance(result, RateLimitResult)
        assert result.allowed is True
        assert result.child_id == child_id
        assert result.operation_type == operation.value
        assert result.remaining >= 0

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, service):
        """Test rate limit check when limit is exceeded."""
        child_id = "child123"
        operation = OperationType.AI_REQUEST
        child_age = 4  # Toddler with lower limits
        
        # Make requests up to the limit
        age_group = service._get_age_group_by_age(child_age)
        limit = age_group.ai_requests_per_hour
        
        # Exceed the limit
        for _ in range(limit + 1):
            result = await service.check_rate_limit(child_id, operation, child_age)
        
        # Last request should be blocked
        assert result.allowed is False
        assert result.remaining == 0
        assert "rate_limit_exceeded" in result.reason

    @pytest.mark.asyncio
    async def test_age_based_scaling(self, service):
        """Test that rate limits scale based on child age."""
        child_id = "child123"
        operation = OperationType.AI_REQUEST
        
        # Test different age groups
        toddler_result = await service.check_rate_limit(child_id + "_toddler", operation, child_age=3)
        preteen_result = await service.check_rate_limit(child_id + "_preteen", operation, child_age=12)
        
        # Preteen should have higher limits than toddler
        toddler_config = service._get_config_for_operation(operation, 3)
        preteen_config = service._get_config_for_operation(operation, 12)
        
        assert preteen_config.max_requests > toddler_config.max_requests

    @pytest.mark.asyncio
    async def test_conversation_start_limit(self, service):
        """Test conversation start rate limiting."""
        child_id = "child123"
        child_age = 8
        
        result = await service.check_conversation_start_limit(child_id, child_age)
        
        assert isinstance(result, RateLimitResult)
        assert result.allowed is True
        assert hasattr(result, 'concurrent_conversations')

    @pytest.mark.asyncio
    async def test_message_burst_protection(self, service):
        """Test message burst protection."""
        child_id = "child123"
        child_age = 8
        conversation_id = "conv123"
        
        # Send messages rapidly
        results = []
        for i in range(10):
            result = await service.check_message_limit(child_id, child_age, conversation_id)
            results.append(result)
        
        # All should be allowed initially
        assert all(r.allowed for r in results[:5])

    @pytest.mark.asyncio
    async def test_safety_incident_reporting(self, service):
        """Test safety incident reporting and cooldown."""
        child_id = "child123"
        child_age = 8
        conversation_id = "conv123"
        
        # Mock storage method for safety cooldown
        service.storage.set_value = AsyncMock(spec=True)
        service.storage.get_value = AsyncMock(return_value=None)
        
        result = await service.report_safety_incident(
            child_id=child_id,
            child_age=child_age,
            incident_type="inappropriate_content",
            severity="high",
            conversation_id=conversation_id
        )
        
        assert isinstance(result, RateLimitResult)
        assert result.safety_cooldown_active is True

    @pytest.mark.asyncio
    async def test_get_usage_stats(self, service):
        """Test usage statistics retrieval."""
        child_id = "child123"
        
        # Make some requests first
        await service.check_rate_limit(child_id, OperationType.AI_REQUEST, child_age=8)
        await service.check_rate_limit(child_id, OperationType.AUDIO_GENERATION, child_age=8)
        
        stats = await service.get_usage_stats(child_id)
        
        assert isinstance(stats, dict)
        assert OperationType.AI_REQUEST.value in stats
        assert OperationType.AUDIO_GENERATION.value in stats
        
        # Check structure of individual operation stats
        ai_stats = stats[OperationType.AI_REQUEST.value]
        assert "current_requests" in ai_stats
        assert "max_requests" in ai_stats
        assert "remaining" in ai_stats
        assert "usage_percentage" in ai_stats

    @pytest.mark.asyncio
    async def test_reset_limits(self, service):
        """Test resetting rate limits for a child."""
        child_id = "child123"
        operation = OperationType.AI_REQUEST
        
        # Make a request to establish some usage
        await service.check_rate_limit(child_id, operation, child_age=8)
        
        # Reset limits
        await service.reset_limits(child_id, operation)
        
        # Should be able to make requests again
        result = await service.check_rate_limit(child_id, operation, child_age=8)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, service):
        """Test handling concurrent rate limit checks."""
        child_id = "child123"
        operation = OperationType.AI_REQUEST
        
        # Make concurrent requests
        tasks = []
        for _ in range(10):
            task = service.check_rate_limit(child_id, operation, child_age=8)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # All should be processed
        assert len(results) == 10
        assert all(isinstance(r, RateLimitResult) for r in results)

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Test service health check."""
        health = await service.health_check()
        
        assert isinstance(health, dict)
        assert "status" in health
        assert "backend_type" in health
        assert "total_requests" in health
        assert "supported_operations" in health
        assert health["status"] in ["healthy", "unhealthy"]


class TestRateLimitAlgorithms:
    """Test different rate limiting algorithms."""

    @pytest.fixture
    def service(self):
        return create_memory_rate_limiting_service()

    @pytest.mark.asyncio
    async def test_sliding_window_algorithm(self, service):
        """Test sliding window rate limiting."""
        from src.infrastructure.rate_limiting.rate_limiter import RateLimitAlgorithmImpl, RateLimitConfig
        
        config = RateLimitConfig(
            operation_type=OperationType.AI_REQUEST,
            max_requests=5,
            window_seconds=60,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW
        )
        
        # Test within limit
        result = await RateLimitAlgorithmImpl.sliding_window(service.storage, "test_key", config)
        assert result.allowed is True
        assert result.remaining == 4

    @pytest.mark.asyncio
    async def test_token_bucket_algorithm(self, service):
        """Test token bucket rate limiting."""
        from src.infrastructure.rate_limiting.rate_limiter import RateLimitAlgorithmImpl, RateLimitConfig
        
        config = RateLimitConfig(
            operation_type=OperationType.AUDIO_GENERATION,
            max_requests=10,
            window_seconds=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            burst_capacity=5,
            refill_rate=0.1
        )
        
        result = await RateLimitAlgorithmImpl.token_bucket(service.storage, "test_key", config)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_fixed_window_algorithm(self, service):
        """Test fixed window rate limiting."""
        from src.infrastructure.rate_limiting.rate_limiter import RateLimitAlgorithmImpl, RateLimitConfig
        
        config = RateLimitConfig(
            operation_type=OperationType.API_CALL,
            max_requests=100,
            window_seconds=3600,
            algorithm=RateLimitAlgorithm.FIXED_WINDOW
        )
        
        result = await RateLimitAlgorithmImpl.fixed_window(service.storage, "test_key", config)
        assert result.allowed is True


class TestChildAgeLimits:
    """Test child age-based rate limiting."""

    def test_age_group_configuration(self):
        """Test age group configurations are properly defined."""
        from src.infrastructure.rate_limiting.rate_limiter import CHILD_AGE_LIMITS
        
        assert "toddler" in CHILD_AGE_LIMITS
        assert "preschool" in CHILD_AGE_LIMITS
        assert "preteen" in CHILD_AGE_LIMITS
        
        toddler = CHILD_AGE_LIMITS["toddler"]
        preteen = CHILD_AGE_LIMITS["preteen"]
        
        # Preteen should have higher limits than toddler
        assert preteen.ai_requests_per_hour > toddler.ai_requests_per_hour
        assert preteen.conversation_messages_per_hour > toddler.conversation_messages_per_hour

    def test_age_group_ranges(self):
        """Test age group ranges don't overlap."""
        from src.infrastructure.rate_limiting.rate_limiter import CHILD_AGE_LIMITS
        
        age_ranges = []
        for group in CHILD_AGE_LIMITS.values():
            age_ranges.append((group.min_age, group.max_age))
        
        # Sort by min_age
        age_ranges.sort()
        
        # Check no overlaps
        for i in range(len(age_ranges) - 1):
            current_max = age_ranges[i][1]
            next_min = age_ranges[i + 1][0]
            assert current_max < next_min, f"Age ranges overlap: {age_ranges[i]} and {age_ranges[i + 1]}"


class TestFactoryFunctions:
    """Test factory functions for creating rate limiting services."""

    def test_create_memory_service(self):
        """Test creating memory-based rate limiting service."""
        service = create_memory_rate_limiting_service()
        
        assert isinstance(service, RateLimitingService)
        assert service.backend_type == "memory"

    @patch('src.infrastructure.rate_limiting.rate_limiter.REDIS_AVAILABLE', True)
    def test_create_redis_service(self):
        """Test creating Redis-based rate limiting service."""
        with patch('redis.asyncio.from_url') as mock_redis:
            mock_redis.return_value = Mock(spec=True)
            
            service = create_rate_limiting_service(use_redis=True)
            
            assert isinstance(service, RateLimitingService)

    def test_create_service_redis_fallback(self):
        """Test Redis fallback to memory when Redis unavailable."""
        with patch('src.infrastructure.rate_limiting.rate_limiter.REDIS_AVAILABLE', False):
            service = create_rate_limiting_service(use_redis=True)
            
            assert isinstance(service, RateLimitingService)
            assert service.backend_type == "memory"


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def service(self):
        return create_memory_rate_limiting_service()

    @pytest.mark.asyncio
    async def test_invalid_child_age(self, service):
        """Test handling of invalid child age."""
        child_id = "child123"
        operation = OperationType.AI_REQUEST
        
        # Test with negative age
        result = await service.check_rate_limit(child_id, operation, child_age=-1)
        assert result.allowed is True  # Should use default limits

        # Test with very high age
        result = await service.check_rate_limit(child_id, operation, child_age=100)
        assert result.allowed is True  # Should use default limits

    @pytest.mark.asyncio
    async def test_storage_error_handling(self, service):
        """Test handling of storage errors."""
        # Mock storage to raise exception
        service.storage.get_requests = AsyncMock(side_effect=Exception("Storage error"))
        
        # Should fail gracefully and allow request
        result = await service.check_rate_limit("child123", OperationType.AI_REQUEST)
        assert result.allowed is True
        assert "rate_limit_error" in result.reason

    @pytest.mark.asyncio
    async def test_conversation_ended_cleanup(self, service):
        """Test conversation cleanup when ended."""
        child_id = "child123"
        conversation_id = "conv123"
        
        # Mock concurrent conversation tracking
        service._increment_concurrent_conversations = AsyncMock(spec=True)
        service._decrement_concurrent_conversations = AsyncMock(spec=True)
        
        await service.conversation_ended(child_id, conversation_id)
        
        service._decrement_concurrent_conversations.assert_called_once_with(child_id)