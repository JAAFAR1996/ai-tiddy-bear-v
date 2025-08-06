"""
Performance and Load Tests for AI Service
==========================================
Comprehensive load testing for ConsolidatedAIService under high load conditions.
Tests Redis connection pooling, batch operations, and concurrent request handling.
"""

import asyncio
import pytest
import time
import statistics
from unittest.mock import Mock, AsyncMock, patch
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

from src.application.services.ai_service import ConsolidatedAIService
from src.application.services.child_safety_service import ChildSafetyService
from src.shared.dto.ai_response import AIResponse


class TestAIServiceLoadPerformance:
    """Load and performance tests for AI Service."""

    @pytest.fixture
    async def ai_service_load_test(self):
        """Create AI service configured for load testing."""
        # Mock AI provider with realistic response times
        mock_ai_provider = Mock()
        mock_ai_provider.generate_response = AsyncMock(
            return_value=AIResponse(
                content="Test response from AI",
                emotion="happy",
                age_appropriate=True,
                safety_score=0.95,
                timestamp=time.time()
            )
        )
        
        # Real child safety service
        safety_monitor = ChildSafetyService()
        
        # Mock logger
        logger = Mock()
        logger.info = Mock()
        logger.error = Mock()
        logger.warning = Mock()
        
        # Create service with Redis pooling
        service = ConsolidatedAIService(
            ai_provider=mock_ai_provider,
            safety_monitor=safety_monitor,
            logger=logger,
            redis_url="redis://localhost:6379"
        )
        
        return service, mock_ai_provider, safety_monitor

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_request_handling(self, ai_service_load_test):
        """Test AI service under concurrent load (100 simultaneous requests)."""
        service, mock_ai_provider, _ = ai_service_load_test
        
        # Configure mock to simulate realistic AI response times
        async def mock_generate_with_delay(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms realistic AI response time
            return AIResponse(
                content=f"Response {time.time()}",
                emotion="neutral",
                age_appropriate=True,
                safety_score=0.9,
                timestamp=time.time()
            )
        
        mock_ai_provider.generate_response = mock_generate_with_delay
        
        # Prepare test data
        num_requests = 100
        child_id = "child-load-test"
        test_messages = [f"Test message {i}" for i in range(num_requests)]
        
        # Measure concurrent execution time
        start_time = time.time()
        
        # Create concurrent tasks
        tasks = []
        for i, message in enumerate(test_messages):
            task = service.generate_response(
                user_message=message,
                child_age=8,
                child_name="TestChild",
                conversation_history=[],
                child_id=child_id
            )
            tasks.append(task)
        
        # Execute all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Validate results
        successful_responses = [r for r in results if isinstance(r, AIResponse)]
        errors = [r for r in results if isinstance(r, Exception)]
        
        # Performance assertions
        assert len(successful_responses) >= 95, f"Expected at least 95% success rate, got {len(successful_responses)}/100"
        assert len(errors) <= 5, f"Too many errors: {len(errors)}"
        assert total_time < 5.0, f"100 concurrent requests took {total_time:.2f}s, expected < 5s"
        
        # Throughput calculation
        throughput = num_requests / total_time
        assert throughput > 20, f"Throughput {throughput:.2f} req/s is too low, expected > 20 req/s"
        
        print(f"✅ Concurrent Load Test Results:")
        print(f"   - Total requests: {num_requests}")
        print(f"   - Successful: {len(successful_responses)}")
        print(f"   - Errors: {len(errors)}")
        print(f"   - Total time: {total_time:.2f}s")
        print(f"   - Throughput: {throughput:.2f} req/s")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_redis_connection_pooling_performance(self, ai_service_load_test):
        """Test Redis connection pooling under high load."""
        service, mock_ai_provider, _ = ai_service_load_test
        
        # Test Redis pool performance with batch operations
        pool_performance_times = []
        num_batches = 50
        batch_size = 20
        
        for batch in range(num_batches):
            start_time = time.time()
            
            # Simulate batch Redis operations
            async with service.redis_pool.pipeline() as pipe:
                for i in range(batch_size):
                    key = f"test:batch:{batch}:item:{i}"
                    pipe.set(key, f"value_{batch}_{i}")
                    pipe.expire(key, 60)
                
                await pipe.execute()
            
            batch_time = time.time() - start_time
            pool_performance_times.append(batch_time)
        
        # Performance analysis
        avg_batch_time = statistics.mean(pool_performance_times)
        max_batch_time = max(pool_performance_times)
        p95_batch_time = statistics.quantiles(pool_performance_times, n=20)[18]  # 95th percentile
        
        # Performance assertions
        assert avg_batch_time < 0.1, f"Average batch time {avg_batch_time:.3f}s too high"
        assert max_batch_time < 0.5, f"Max batch time {max_batch_time:.3f}s too high"
        assert p95_batch_time < 0.2, f"P95 batch time {p95_batch_time:.3f}s too high"
        
        print(f"✅ Redis Connection Pool Performance:")
        print(f"   - Batches tested: {num_batches}")
        print(f"   - Operations per batch: {batch_size}")
        print(f"   - Average batch time: {avg_batch_time:.3f}s")
        print(f"   - Max batch time: {max_batch_time:.3f}s")
        print(f"   - P95 batch time: {p95_batch_time:.3f}s")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_rate_limiting_performance(self, ai_service_load_test):
        """Test rate limiting performance under burst conditions."""
        service, mock_ai_provider, _ = ai_service_load_test
        
        child_id = "child-rate-test"
        
        # Test burst of requests within rate limits
        burst_size = 30  # Within typical burst limit
        burst_times = []
        
        for i in range(burst_size):
            start_time = time.time()
            
            # Check rate limit
            allowed, message = await service._check_rate_limit(
                child_id=child_id,
                current_time=time.time(),
                content=f"Burst message {i}"
            )
            
            check_time = time.time() - start_time
            burst_times.append(check_time)
            
            assert allowed, f"Request {i} was rate limited: {message}"
        
        # Performance analysis
        avg_check_time = statistics.mean(burst_times)
        max_check_time = max(burst_times)
        
        # Performance assertions
        assert avg_check_time < 0.01, f"Average rate limit check {avg_check_time:.4f}s too slow"
        assert max_check_time < 0.05, f"Max rate limit check {max_check_time:.4f}s too slow"
        
        print(f"✅ Rate Limiting Performance:")
        print(f"   - Burst requests: {burst_size}")
        print(f"   - Average check time: {avg_check_time:.4f}s")
        print(f"   - Max check time: {max_check_time:.4f}s")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_safety_filtering_performance(self, ai_service_load_test):
        """Test safety filtering performance with large content."""
        service, _, safety_monitor = ai_service_load_test
        
        # Test with various content sizes
        test_contents = [
            "Short safe message",
            "Medium length message that contains some normal conversation content for testing",
            "Very long message content " * 50,  # ~1250 characters
            "Extremely long content " * 200,     # ~5000 characters
        ]
        
        performance_results = []
        
        for content in test_contents:
            # Run multiple iterations for accurate timing
            times = []
            for _ in range(10):
                start_time = time.time()
                
                result = await safety_monitor.validate_content(content, child_age=8)
                
                end_time = time.time()
                times.append(end_time - start_time)
            
            avg_time = statistics.mean(times)
            performance_results.append({
                "content_length": len(content),
                "avg_time": avg_time,
                "throughput": len(content) / avg_time  # chars/second
            })
        
        # Performance assertions
        for result in performance_results:
            assert result["avg_time"] < 0.01, f"Safety check too slow: {result['avg_time']:.4f}s for {result['content_length']} chars"
            assert result["throughput"] > 10000, f"Safety throughput too low: {result['throughput']:.0f} chars/s"
        
        print(f"✅ Safety Filtering Performance:")
        for result in performance_results:
            print(f"   - {result['content_length']} chars: {result['avg_time']:.4f}s ({result['throughput']:.0f} chars/s)")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_memory_usage_under_load(self, ai_service_load_test):
        """Test memory usage doesn't grow excessively under sustained load."""
        service, mock_ai_provider, _ = ai_service_load_test
        
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Simulate sustained load
        num_rounds = 10
        requests_per_round = 50
        
        for round_num in range(num_rounds):
            tasks = []
            for i in range(requests_per_round):
                task = service.generate_response(
                    user_message=f"Memory test message {round_num}-{i}",
                    child_age=8,
                    child_name="MemoryTest",
                    conversation_history=[],
                    child_id=f"child-memory-{i % 10}"  # Rotate child IDs
                )
                tasks.append(task)
                
            # Execute round
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check memory after each round
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_growth = current_memory - initial_memory
            
            # Memory growth should be reasonable
            assert memory_growth < 100, f"Memory growth {memory_growth:.1f}MB too high after round {round_num}"
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_growth = final_memory - initial_memory
        
        print(f"✅ Memory Usage Test:")
        print(f"   - Initial memory: {initial_memory:.1f}MB")
        print(f"   - Final memory: {final_memory:.1f}MB")
        print(f"   - Total growth: {total_growth:.1f}MB")
        print(f"   - Requests processed: {num_rounds * requests_per_round}")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_error_recovery_performance(self, ai_service_load_test):
        """Test service performance during error conditions and recovery."""
        service, mock_ai_provider, _ = ai_service_load_test
        
        # Configure mock to simulate intermittent failures
        call_count = 0
        async def mock_generate_with_failures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            # Fail every 10th request
            if call_count % 10 == 0:
                raise Exception("Simulated AI provider failure")
            
            await asyncio.sleep(0.05)  # 50ms normal response
            return AIResponse(
                content=f"Success response {call_count}",
                emotion="neutral",
                age_appropriate=True,
                safety_score=0.9,
                timestamp=time.time()
            )
        
        mock_ai_provider.generate_response = mock_generate_with_failures
        
        # Test error recovery
        num_requests = 100
        start_time = time.time()
        
        tasks = []
        for i in range(num_requests):
            task = service.generate_response(
                user_message=f"Error recovery test {i}",
                child_age=8,
                child_name="ErrorTest",
                conversation_history=[],
                child_id="child-error-test"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results
        successful_responses = [r for r in results if isinstance(r, AIResponse)]
        errors = [r for r in results if isinstance(r, Exception)]
        
        # Performance assertions with error tolerance
        success_rate = len(successful_responses) / num_requests
        total_time = end_time - start_time
        
        assert success_rate >= 0.8, f"Success rate {success_rate:.2f} too low during errors"
        assert total_time < 15.0, f"Error recovery took too long: {total_time:.2f}s"
        
        print(f"✅ Error Recovery Performance:")
        print(f"   - Total requests: {num_requests}")
        print(f"   - Success rate: {success_rate:.2%}")
        print(f"   - Total time: {total_time:.2f}s")
        print(f"   - Throughput: {num_requests/total_time:.1f} req/s")


class TestAIServiceStressTest:
    """Stress tests for extreme load conditions."""

    @pytest.mark.asyncio
    @pytest.mark.stress
    @pytest.mark.skipif(
        True,  # Skip by default, run manually for stress testing
        reason="Stress test - run manually with: pytest -m stress"
    )
    async def test_extreme_concurrent_load(self):
        """Stress test with 1000 concurrent requests."""
        # This test is for manual execution during stress testing
        # pytest -m stress -v tests/performance/test_ai_service_load.py::TestAIServiceStressTest::test_extreme_concurrent_load
        
        # Mock setup for stress testing
        mock_ai_provider = Mock()
        mock_ai_provider.generate_response = AsyncMock(
            return_value=AIResponse(
                content="Stress test response",
                emotion="neutral", 
                age_appropriate=True,
                safety_score=0.9,
                timestamp=time.time()
            )
        )
        
        safety_monitor = ChildSafetyService()
        logger = Mock()
        
        service = ConsolidatedAIService(
            ai_provider=mock_ai_provider,
            safety_monitor=safety_monitor,
            logger=logger,
            redis_url="redis://localhost:6379"
        )
        
        # Extreme load test
        num_requests = 1000
        start_time = time.time()
        
        tasks = []
        for i in range(num_requests):
            task = service.generate_response(
                user_message=f"Stress test message {i}",
                child_age=8,
                child_name="StressTest",
                conversation_history=[],
                child_id=f"child-stress-{i % 50}"  # 50 different children
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Stress test analysis
        successful_responses = [r for r in results if isinstance(r, AIResponse)]
        errors = [r for r in results if isinstance(r, Exception)]
        success_rate = len(successful_responses) / num_requests
        total_time = end_time - start_time
        throughput = num_requests / total_time
        
        print(f"🔥 Extreme Load Stress Test Results:")
        print(f"   - Total requests: {num_requests}")
        print(f"   - Successful: {len(successful_responses)}")
        print(f"   - Errors: {len(errors)}")
        print(f"   - Success rate: {success_rate:.2%}")
        print(f"   - Total time: {total_time:.2f}s")
        print(f"   - Throughput: {throughput:.1f} req/s")
        
        # Stress test assertions (more lenient than load tests)
        assert success_rate >= 0.7, f"Stress test success rate too low: {success_rate:.2%}"
        assert throughput > 10, f"Stress test throughput too low: {throughput:.1f} req/s"


# Performance test configuration
@pytest.fixture(scope="session")
def performance_config():
    """Configuration for performance tests."""
    return {
        "redis_url": "redis://localhost:6379",
        "max_connections": 50,
        "request_timeout": 30.0,
        "batch_size": 20
    }


# Utility functions for performance testing
def measure_execution_time(func):
    """Decorator to measure execution time."""
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    return wrapper


@pytest.mark.performance
class TestPerformanceMetrics:
    """Test performance metrics collection."""
    
    def test_performance_baseline_requirements(self):
        """Document performance baseline requirements."""
        requirements = {
            "concurrent_requests": {
                "target": 100,
                "max_response_time": 5.0,
                "min_throughput": 20,
                "success_rate": 0.95
            },
            "redis_operations": {
                "avg_batch_time": 0.1,
                "max_batch_time": 0.5,
                "p95_batch_time": 0.2
            },
            "rate_limiting": {
                "avg_check_time": 0.01,
                "max_check_time": 0.05
            },
            "safety_filtering": {
                "max_check_time": 0.01,
                "min_throughput": 10000  # chars/second
            },
            "memory_usage": {
                "max_growth": 100  # MB under sustained load
            }
        }
        
        # This test documents the performance requirements
        # Actual performance tests validate against these requirements
        assert requirements is not None
        print("📊 Performance Requirements Documented:")
        for category, reqs in requirements.items():
            print(f"   {category}: {reqs}")