"""
🔥 CRITICAL SECURITY TESTS - Rate Limiter Attack Scenarios
==========================================================

Integration tests for rate limiting system against real attack scenarios.
These tests verify the system can withstand production attacks.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch
from concurrent.futures import ThreadPoolExecutor
import httpx
from fastapi.testclient import TestClient

from src.main import app
from src.infrastructure.rate_limiting.rate_limiter import (
    RateLimitingService,
    OperationType,
    create_memory_rate_limiting_service
)


class TestRateLimiterAttackScenarios:
    """Test rate limiter against realistic attack scenarios."""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiting service for testing."""
        return create_memory_rate_limiting_service()

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_brute_force_attack_protection(self, rate_limiter):
        """Test protection against brute force attacks on child accounts."""
        child_id = "child_attack_test"
        
        # Simulate rapid login attempts
        attack_requests = []
        for i in range(50):  # 50 rapid attempts
            result = await rate_limiter.check_rate_limit(
                child_id, 
                OperationType.AUTH_LOGIN,
                child_age=8
            )
            attack_requests.append(result)
        
        # First few should be allowed, then blocked
        allowed_count = sum(1 for r in attack_requests if r.allowed)
        blocked_count = sum(1 for r in attack_requests if not r.allowed)
        
        assert allowed_count < 10  # Should block most attempts
        assert blocked_count > 40  # Most should be blocked
        
        # Last requests should definitely be blocked
        assert not attack_requests[-10:][0].allowed
        assert attack_requests[-1].reason == "rate_limit_exceeded"

    @pytest.mark.asyncio
    async def test_ddos_attack_simulation(self, rate_limiter):
        """Test DDoS attack protection with concurrent requests."""
        
        async def make_attack_request(child_id_base, request_num):
            """Make a single attack request."""
            child_id = f"{child_id_base}_{request_num % 10}"  # 10 different children
            return await rate_limiter.check_rate_limit(
                child_id,
                OperationType.AI_REQUEST,
                child_age=8
            )
        
        # Launch 200 concurrent requests
        tasks = []
        for i in range(200):
            task = make_attack_request("ddos_test", i)
            tasks.append(task)
        
        # Execute all requests concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        execution_time = time.time() - start_time
        
        # Analyze results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        allowed_count = sum(1 for r in successful_results if r.allowed)
        blocked_count = sum(1 for r in successful_results if not r.allowed)
        
        # Should handle concurrent requests without crashing
        assert len(successful_results) > 100  # Most should complete
        assert execution_time < 10  # Should be fast
        assert blocked_count > 50  # Should block many requests
        
        print(f"DDoS Test: {allowed_count} allowed, {blocked_count} blocked in {execution_time:.2f}s")

    @pytest.mark.asyncio
    async def test_child_specific_attack_protection(self, rate_limiter):
        """Test that attackers can't exhaust limits for specific children."""
        
        # Attacker trying to exhaust limits for a specific child
        target_child = "innocent_child_123"
        
        # Make many requests for this child
        results = []
        for i in range(100):
            result = await rate_limiter.check_rate_limit(
                target_child,
                OperationType.AI_REQUEST,
                child_age=6  # Younger child = lower limits
            )
            results.append(result)
        
        # Should protect the child by rate limiting
        allowed_requests = [r for r in results if r.allowed]
        blocked_requests = [r for r in results if not r.allowed]
        
        # For 6-year-old, should have strict limits
        assert len(allowed_requests) < 30  # Age-appropriate limit
        assert len(blocked_requests) > 70  # Most should be blocked
        
        # Check that safety mechanisms kicked in
        for result in blocked_requests[-10:]:
            assert not result.allowed
            assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_conversation_flooding_attack(self, rate_limiter):
        """Test protection against conversation flooding attacks."""
        child_id = "flood_target_child"
        
        # Try to start many conversations rapidly
        conversation_starts = []
        for i in range(50):
            result = await rate_limiter.check_conversation_start_limit(
                child_id,
                child_age=8
            )
            conversation_starts.append(result)
        
        # Should limit conversation starts
        allowed_conversations = [r for r in conversation_starts if r.allowed]
        blocked_conversations = [r for r in conversation_starts if not r.allowed]
        
        assert len(allowed_conversations) < 10  # Reasonable conversation limit
        assert len(blocked_conversations) > 40  # Block excessive attempts
        
        # Check concurrent conversation limits
        last_result = conversation_starts[-1]
        assert hasattr(last_result, 'concurrent_conversations')

    @pytest.mark.asyncio
    async def test_audio_generation_abuse_protection(self, rate_limiter):
        """Test protection against audio generation abuse."""
        child_id = "audio_abuser"
        
        # Try to generate excessive audio (expensive operation)
        audio_requests = []
        for i in range(30):
            result = await rate_limiter.check_rate_limit(
                child_id,
                OperationType.AUDIO_GENERATION,
                child_age=10
            )
            audio_requests.append(result)
        
        # Audio generation should have stricter limits
        allowed_audio = [r for r in audio_requests if r.allowed]
        blocked_audio = [r for r in audio_requests if not r.allowed]
        
        # Should have very strict limits on expensive operations
        assert len(allowed_audio) < 15  # Conservative limit
        assert len(blocked_audio) > 15
        
        # Verify the cost-based limiting
        for blocked in blocked_audio[-5:]:
            assert "rate_limit_exceeded" in blocked.reason

    @pytest.mark.asyncio
    async def test_multi_child_attack_isolation(self, rate_limiter):
        """Test that attacking one child doesn't affect others."""
        
        # Attack one child
        attacked_child = "attacked_child"
        normal_child = "normal_child"
        
        # Exhaust attacked child's limits
        for i in range(100):
            await rate_limiter.check_rate_limit(
                attacked_child,
                OperationType.AI_REQUEST,
                child_age=8
            )
        
        # Normal child should still work
        normal_result = await rate_limiter.check_rate_limit(
            normal_child,
            OperationType.AI_REQUEST,
            child_age=8
        )
        
        assert normal_result.allowed is True
        assert normal_result.remaining > 0
        
        # Attacked child should be blocked
        attacked_result = await rate_limiter.check_rate_limit(
            attacked_child,
            OperationType.AI_REQUEST,
            child_age=8
        )
        
        assert attacked_result.allowed is False
        assert attacked_result.remaining == 0

    @pytest.mark.asyncio
    async def test_safety_incident_cooldown_attack(self, rate_limiter):
        """Test that safety incidents trigger proper cooldowns."""
        child_id = "safety_test_child"
        conversation_id = "safety_conv_123"
        
        # Mock storage for safety cooldown
        rate_limiter.storage.set_value = AsyncMock()
        rate_limiter.storage.get_value = AsyncMock(return_value=None)
        
        # Report a high-severity safety incident
        safety_result = await rate_limiter.report_safety_incident(
            child_id=child_id,
            child_age=7,
            incident_type="inappropriate_content",
            severity="high",
            conversation_id=conversation_id
        )
        
        assert safety_result.safety_cooldown_active is True
        
        # Mock that cooldown is active
        rate_limiter.storage.get_value = AsyncMock(return_value=time.time() + 300)
        
        # Try to make requests during cooldown
        cooldown_result = await rate_limiter.check_rate_limit(
            child_id,
            OperationType.AI_REQUEST,
            child_age=7
        )
        
        # Should be blocked during safety cooldown
        assert cooldown_result.allowed is False
        assert "safety_cooldown" in cooldown_result.reason.lower()

    @pytest.mark.asyncio
    async def test_age_bypass_attack_protection(self, rate_limiter):
        """Test protection against age manipulation attacks."""
        
        # Attacker tries different ages for same child to bypass limits
        child_id = "age_manipulation_test"
        
        # First exhaust limits as 5-year-old (strict limits)
        for i in range(20):
            await rate_limiter.check_rate_limit(child_id, OperationType.AI_REQUEST, child_age=5)
        
        # Try to bypass by claiming older age
        bypass_result = await rate_limiter.check_rate_limit(
            child_id, 
            OperationType.AI_REQUEST, 
            child_age=12  # Trying to get higher limits
        )
        
        # System should maintain the limits per child_id, not per age
        assert bypass_result.allowed is False
        assert bypass_result.remaining == 0

    @pytest.mark.asyncio
    async def test_error_handling_during_attack(self, rate_limiter):
        """Test system stability during storage errors during attack."""
        
        # Mock storage to occasionally fail
        original_get_requests = rate_limiter.storage.get_requests
        
        async def failing_get_requests(*args, **kwargs):
            if time.time() % 3 < 1:  # Fail ~1/3 of the time
                raise Exception("Storage temporarily unavailable")
            return await original_get_requests(*args, **kwargs)
        
        rate_limiter.storage.get_requests = failing_get_requests
        
        # Make requests during "storage issues"
        results = []
        for i in range(20):
            try:
                result = await rate_limiter.check_rate_limit(
                    f"error_test_child_{i}",
                    OperationType.AI_REQUEST,
                    child_age=8
                )
                results.append(result)
            except Exception as e:
                results.append(e)
        
        # Should handle errors gracefully
        successful_results = [r for r in results if not isinstance(r, Exception)]
        
        # Should have some successful results despite errors
        assert len(successful_results) > 10
        
        # When errors occur, should fail safe (allow by default)
        error_handled_results = [r for r in successful_results if "rate_limit_error" in r.reason]
        assert len(error_handled_results) > 0

    @pytest.mark.asyncio
    async def test_concurrent_child_attack(self, rate_limiter):
        """Test concurrent attacks on multiple children."""
        
        async def attack_child(child_id, num_requests=20):
            """Attack a specific child with requests."""
            results = []
            for i in range(num_requests):
                result = await rate_limiter.check_rate_limit(
                    child_id,
                    OperationType.AI_REQUEST,
                    child_age=7
                )
                results.append(result)
            return results
        
        # Launch concurrent attacks on 20 different children
        attack_tasks = []
        for i in range(20):
            task = attack_child(f"concurrent_attack_child_{i}")
            attack_tasks.append(task)
        
        # Execute all attacks concurrently
        start_time = time.time()
        all_results = await asyncio.gather(*attack_tasks)
        execution_time = time.time() - start_time
        
        # Analyze results
        total_requests = sum(len(results) for results in all_results)
        total_allowed = sum(
            sum(1 for r in results if r.allowed) 
            for results in all_results
        )
        total_blocked = total_requests - total_allowed
        
        # Should handle concurrent attacks efficiently
        assert execution_time < 15  # Should complete in reasonable time
        assert total_requests == 400  # 20 children × 20 requests
        assert total_blocked > 200  # Should block significant portion
        
        print(f"Concurrent Attack Test: {total_allowed} allowed, {total_blocked} blocked in {execution_time:.2f}s")

    def test_usage_statistics_during_attack(self, rate_limiter):
        """Test that usage statistics remain accurate during attacks."""
        
        async def run_attack_and_check_stats():
            child_id = "stats_test_child"
            
            # Make several requests
            for i in range(15):
                await rate_limiter.check_rate_limit(child_id, OperationType.AI_REQUEST, child_age=8)
                await rate_limiter.check_rate_limit(child_id, OperationType.AUDIO_GENERATION, child_age=8)
            
            # Get usage statistics
            stats = await rate_limiter.get_usage_stats(child_id)
            
            # Verify statistics are present and reasonable
            assert isinstance(stats, dict)
            assert OperationType.AI_REQUEST.value in stats
            assert OperationType.AUDIO_GENERATION.value in stats
            
            ai_stats = stats[OperationType.AI_REQUEST.value]
            assert ai_stats["current_requests"] >= 0
            assert ai_stats["max_requests"] > 0
            assert ai_stats["usage_percentage"] >= 0
            
            return stats
        
        # Run the test
        stats = asyncio.run(run_attack_and_check_stats())
        assert stats is not None


class TestRateLimiterProductionReadiness:
    """Test rate limiter for production readiness."""

    @pytest.fixture
    def rate_limiter(self):
        return create_memory_rate_limiting_service()

    @pytest.mark.asyncio
    async def test_system_health_under_load(self, rate_limiter):
        """Test system health monitoring under load."""
        
        # Generate load
        for i in range(100):
            await rate_limiter.check_rate_limit(f"load_test_child_{i % 10}", OperationType.AI_REQUEST, child_age=8)
        
        # Check health
        health = await rate_limiter.health_check()
        
        assert health["status"] == "healthy"
        assert health["total_requests"] >= 100
        assert len(health["supported_operations"]) > 0

    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, rate_limiter):
        """Test that memory usage remains stable under prolonged attack."""
        
        # Simulate prolonged attack
        for round_num in range(10):  # 10 rounds
            for child_num in range(50):  # 50 children per round
                child_id = f"memory_test_child_{child_num}"
                await rate_limiter.check_rate_limit(child_id, OperationType.AI_REQUEST, child_age=8)
        
        # System should still be responsive
        final_result = await rate_limiter.check_rate_limit("final_test_child", OperationType.AI_REQUEST, child_age=8)
        assert final_result.allowed is True

    @pytest.mark.asyncio
    async def test_cleanup_after_attack(self, rate_limiter):
        """Test that system properly cleans up after attacks."""
        
        child_id = "cleanup_test_child"
        
        # Simulate attack
        for i in range(50):
            await rate_limiter.check_rate_limit(child_id, OperationType.AI_REQUEST, child_age=8)
        
        # Reset limits (simulating admin intervention)
        await rate_limiter.reset_limits(child_id, OperationType.AI_REQUEST)
        
        # Child should be able to make requests again
        reset_result = await rate_limiter.check_rate_limit(child_id, OperationType.AI_REQUEST, child_age=8)
        assert reset_result.allowed is True
        assert reset_result.remaining > 0


if __name__ == "__main__":
    # Run critical tests
    pytest.main([__file__, "-v", "--tb=short"])