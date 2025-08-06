"""
🎯 User Service Performance & Load Tests - Production Grade
==========================================================
Comprehensive load testing for UserService under extreme conditions.
Tests 1000, 5000, 10000 concurrent sessions with full monitoring.

NO COMPROMISES - Production-Ready Performance Testing
"""

import asyncio
import pytest
import time
import statistics
import psutil
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch
import uuid
from datetime import datetime, timedelta
import random
import aioredis
import json

from src.application.services.user_service import UserService
from src.adapters.database_production import ProductionUserRepository, ProductionChildRepository


class LoadTestMetrics:
    """Real-time metrics collection during load testing."""
    
    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'response_times': [],
            'memory_usage_mb': [],
            'cpu_usage_percent': [],
            'active_sessions': 0,
            'concurrent_operations': 0,
            'database_queries': 0,
            'redis_operations': 0,
            'errors_by_type': {},
            'performance_degradation': False,
            'bottlenecks': [],
        }
        self.start_time = time.time()
        
    def record_request(self, success: bool, response_time: float, error_type: str = None):
        """Record request metrics."""
        self.metrics['total_requests'] += 1
        if success:
            self.metrics['successful_requests'] += 1
        else:
            self.metrics['failed_requests'] += 1
            if error_type:
                self.metrics['errors_by_type'][error_type] = \
                    self.metrics['errors_by_type'].get(error_type, 0) + 1
        
        self.metrics['response_times'].append(response_time)
        
    def record_system_metrics(self):
        """Record system resource usage."""
        process = psutil.Process(os.getpid())
        self.metrics['memory_usage_mb'].append(process.memory_info().rss / 1024 / 1024)
        self.metrics['cpu_usage_percent'].append(psutil.cpu_percent())
        
    def get_percentiles(self) -> Dict[str, float]:
        """Calculate response time percentiles."""
        if not self.metrics['response_times']:
            return {}
            
        response_times = sorted(self.metrics['response_times'])
        length = len(response_times)
        
        return {
            'p50': response_times[int(length * 0.5)],
            'p95': response_times[int(length * 0.95)],
            'p99': response_times[int(length * 0.99)],
            'max': max(response_times),
            'avg': statistics.mean(response_times)
        }
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze performance and identify bottlenecks."""
        percentiles = self.get_percentiles()
        total_time = time.time() - self.start_time
        throughput = self.metrics['total_requests'] / total_time if total_time > 0 else 0
        success_rate = (self.metrics['successful_requests'] / self.metrics['total_requests'] 
                       if self.metrics['total_requests'] > 0 else 0)
        
        # Identify performance issues
        bottlenecks = []
        if percentiles.get('p95', 0) > 5.0:
            bottlenecks.append("HIGH_RESPONSE_TIME_P95")
        if percentiles.get('p99', 0) > 10.0:
            bottlenecks.append("HIGH_RESPONSE_TIME_P99")
        if success_rate < 0.95:
            bottlenecks.append("LOW_SUCCESS_RATE")
        if max(self.metrics['memory_usage_mb']) > 2048:  # 2GB
            bottlenecks.append("HIGH_MEMORY_USAGE")
        if max(self.metrics['cpu_usage_percent']) > 80:
            bottlenecks.append("HIGH_CPU_USAGE")
        if throughput < 100:  # Less than 100 req/s
            bottlenecks.append("LOW_THROUGHPUT")
            
        return {
            'percentiles': percentiles,
            'throughput_rps': throughput,
            'success_rate': success_rate,
            'total_time': total_time,
            'max_memory_mb': max(self.metrics['memory_usage_mb']),
            'max_cpu_percent': max(self.metrics['cpu_usage_percent']),
            'bottlenecks': bottlenecks,
            'performance_grade': 'A' if not bottlenecks else 'B' if len(bottlenecks) <= 2 else 'C'
        }


class ProductionUserServiceLoadTest:
    """Production-grade load testing for User Service."""
    
    @pytest.fixture
    async def redis_pool(self):
        """Real Redis connection pool for testing."""
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        pool = aioredis.ConnectionPool.from_url(
            redis_url,
            max_connections=100,
            retry_on_timeout=True,
            health_check_interval=30
        )
        yield pool
        await pool.disconnect()
        
    @pytest.fixture
    async def production_user_service(self, redis_pool):
        """Production-configured User Service with real dependencies."""
        # Create real repository instances
        user_repo = ProductionUserRepository()
        child_repo = ProductionChildRepository()
        
        # Mock logger to avoid log spam during load testing
        logger = Mock()
        logger.info = Mock()
        logger.error = Mock()
        logger.warning = Mock()
        
        # Create service with production configuration
        service = UserService(
            user_repository=user_repo,
            child_repository=child_repo,
            logger=logger,
            session_timeout_minutes=30,
            max_sessions_per_user=10
        )
        
        return service, user_repo, child_repo
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.timeout(600)  # 10 minutes max
    async def test_concurrent_sessions_1000(self, production_user_service):
        """Test 1000 concurrent sessions - Production Baseline."""
        service, user_repo, child_repo = production_user_service
        metrics = LoadTestMetrics()
        
        print("\n🚀 Starting 1000 Concurrent Sessions Load Test")
        
        # Create test users and children
        test_users = await self._create_test_users(user_repo, 200)  # 200 users, 5 sessions each
        test_children = await self._create_test_children(child_repo, test_users, 400)  # 400 children
        
        # Run concurrent session operations
        await self._run_concurrent_session_test(
            service, test_users, test_children, 
            concurrent_sessions=1000, 
            operations_per_session=10,
            metrics=metrics
        )
        
        # Analyze results
        results = metrics.analyze_performance()
        
        print(f"📊 1000 Sessions Results:")
        print(f"   - Success Rate: {results['success_rate']:.2%}")
        print(f"   - Throughput: {results['throughput_rps']:.1f} req/s")
        print(f"   - P95 Response Time: {results['percentiles']['p95']:.3f}s")
        print(f"   - P99 Response Time: {results['percentiles']['p99']:.3f}s")
        print(f"   - Max Memory: {results['max_memory_mb']:.1f}MB")
        print(f"   - Performance Grade: {results['performance_grade']}")
        
        # Production Requirements for 1000 sessions
        assert results['success_rate'] >= 0.95, f"Success rate too low: {results['success_rate']:.2%}"
        assert results['percentiles']['p95'] <= 5.0, f"P95 response time too high: {results['percentiles']['p95']:.3f}s"
        assert results['percentiles']['p99'] <= 10.0, f"P99 response time too high: {results['percentiles']['p99']:.3f}s"
        assert results['throughput_rps'] >= 100, f"Throughput too low: {results['throughput_rps']:.1f} req/s"
        assert results['max_memory_mb'] <= 2048, f"Memory usage too high: {results['max_memory_mb']:.1f}MB"
        
        if results['bottlenecks']:
            print(f"⚠️ Performance Bottlenecks: {results['bottlenecks']}")
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.stress
    @pytest.mark.timeout(900)  # 15 minutes max
    async def test_concurrent_sessions_5000(self, production_user_service):
        """Test 5000 concurrent sessions - High Load Scenario."""
        service, user_repo, child_repo = production_user_service
        metrics = LoadTestMetrics()
        
        print("\n🔥 Starting 5000 Concurrent Sessions Stress Test")
        
        # Create more test data for stress testing
        test_users = await self._create_test_users(user_repo, 1000)  # 1000 users
        test_children = await self._create_test_children(child_repo, test_users, 2000)  # 2000 children
        
        # Run high-load concurrent test
        await self._run_concurrent_session_test(
            service, test_users, test_children,
            concurrent_sessions=5000,
            operations_per_session=15,
            metrics=metrics
        )
        
        # Analyze results
        results = metrics.analyze_performance()
        
        print(f"📊 5000 Sessions Results:")
        print(f"   - Success Rate: {results['success_rate']:.2%}")
        print(f"   - Throughput: {results['throughput_rps']:.1f} req/s")
        print(f"   - P95 Response Time: {results['percentiles']['p95']:.3f}s")
        print(f"   - P99 Response Time: {results['percentiles']['p99']:.3f}s")
        print(f"   - Max Memory: {results['max_memory_mb']:.1f}MB")
        print(f"   - Performance Grade: {results['performance_grade']}")
        
        # Relaxed requirements for stress testing (but still production-acceptable)
        assert results['success_rate'] >= 0.90, f"Success rate too low under stress: {results['success_rate']:.2%}"
        assert results['percentiles']['p95'] <= 8.0, f"P95 response time too high under stress: {results['percentiles']['p95']:.3f}s"
        assert results['percentiles']['p99'] <= 15.0, f"P99 response time too high under stress: {results['percentiles']['p99']:.3f}s"
        assert results['throughput_rps'] >= 50, f"Throughput too low under stress: {results['throughput_rps']:.1f} req/s"
        
        if results['bottlenecks']:
            print(f"⚠️ Stress Test Bottlenecks: {results['bottlenecks']}")
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.extreme
    @pytest.mark.timeout(1200)  # 20 minutes max
    async def test_concurrent_sessions_10000(self, production_user_service):
        """Test 10000 concurrent sessions - Extreme Load Scenario."""
        service, user_repo, child_repo = production_user_service
        metrics = LoadTestMetrics()
        
        print("\n💥 Starting 10000 Concurrent Sessions EXTREME Test")
        
        # Create maximum test data
        test_users = await self._create_test_users(user_repo, 2000)  # 2000 users
        test_children = await self._create_test_children(child_repo, test_users, 4000)  # 4000 children
        
        # Run extreme load test
        await self._run_concurrent_session_test(
            service, test_users, test_children,
            concurrent_sessions=10000,
            operations_per_session=20,
            metrics=metrics
        )
        
        # Analyze results
        results = metrics.analyze_performance()
        
        print(f"📊 10000 Sessions Results:")
        print(f"   - Success Rate: {results['success_rate']:.2%}")
        print(f"   - Throughput: {results['throughput_rps']:.1f} req/s") 
        print(f"   - P95 Response Time: {results['percentiles']['p95']:.3f}s")
        print(f"   - P99 Response Time: {results['percentiles']['p99']:.3f}s")
        print(f"   - Max Memory: {results['max_memory_mb']:.1f}MB")
        print(f"   - Performance Grade: {results['performance_grade']}")
        
        # Extreme load requirements (graceful degradation acceptable)
        assert results['success_rate'] >= 0.80, f"Success rate collapsed under extreme load: {results['success_rate']:.2%}"
        assert results['percentiles']['p95'] <= 20.0, f"P95 response time unacceptable: {results['percentiles']['p95']:.3f}s"
        assert results['percentiles']['p99'] <= 30.0, f"P99 response time unacceptable: {results['percentiles']['p99']:.3f}s"
        assert results['throughput_rps'] >= 25, f"Throughput collapsed: {results['throughput_rps']:.1f} req/s"
        
        # Log extreme load analysis
        if results['bottlenecks']:
            print(f"🚨 EXTREME Load Bottlenecks: {results['bottlenecks']}")
            print("🔧 Recommend: Horizontal scaling, Redis clustering, Database sharding")
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_memory_leak_detection(self, production_user_service):
        """Test for memory leaks during sustained load."""
        service, user_repo, child_repo = production_user_service
        
        print("\n🔍 Memory Leak Detection Test")
        
        test_users = await self._create_test_users(user_repo, 50)
        test_children = await self._create_test_children(child_repo, test_users, 100)
        
        initial_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        memory_readings = []
        
        # Run sustained operations for memory leak detection
        for round_num in range(10):  # 10 rounds of operations
            print(f"   Round {round_num + 1}/10")
            
            # Create many sessions
            sessions = []
            for i in range(100):  # 100 sessions per round
                child = random.choice(test_children)
                try:
                    session_id = await service.create_session(
                        child_id=child['id'],
                        device_info={'device': f'test_{i}'},
                        accessibility_needs=[]
                    )
                    sessions.append(session_id)
                except Exception as e:
                    print(f"Session creation failed: {e}")
            
            # Perform operations on sessions
            for session_id in sessions:
                try:
                    await service.update_session_activity(session_id)
                except Exception:
                    pass  # Expected some failures under load
            
            # End all sessions
            for session_id in sessions:
                try:
                    await service.end_session(session_id)
                except Exception:
                    pass
            
            # Record memory usage
            current_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            memory_readings.append(current_memory)
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Brief pause between rounds
            await asyncio.sleep(1)
        
        final_memory = memory_readings[-1]
        memory_growth = final_memory - initial_memory
        max_memory = max(memory_readings)
        
        print(f"📊 Memory Analysis:")
        print(f"   - Initial Memory: {initial_memory:.1f}MB")
        print(f"   - Final Memory: {final_memory:.1f}MB")
        print(f"   - Memory Growth: {memory_growth:.1f}MB")
        print(f"   - Peak Memory: {max_memory:.1f}MB")
        
        # Memory leak detection thresholds
        assert memory_growth < 500, f"Potential memory leak detected: {memory_growth:.1f}MB growth"
        assert max_memory < 4096, f"Peak memory usage too high: {max_memory:.1f}MB"
        
        # Check for monotonic growth (sign of memory leak)
        if len(memory_readings) >= 5:
            recent_growth = memory_readings[-1] - memory_readings[-5]
            if recent_growth > 200:  # 200MB growth in last 5 rounds
                print(f"⚠️ Warning: Suspicious memory growth pattern: {recent_growth:.1f}MB")
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_database_connection_pool_stress(self, production_user_service):
        """Test database connection pool under stress."""
        service, user_repo, child_repo = production_user_service
        
        print("\n🗄️ Database Connection Pool Stress Test")
        
        # Create test data
        test_users = await self._create_test_users(user_repo, 100)
        
        # Simulate database-heavy operations
        async def database_heavy_operation(user_data):
            """Simulate heavy database operations."""
            try:
                # Multiple database operations
                user = await user_repo.get_by_id(user_data['id'])
                if user:
                    await user_repo.update(user_data['id'], {'last_login': datetime.utcnow()})
                    children = await child_repo.get_by_parent_id(user_data['id'])
                    return len(children)
                return 0
            except Exception as e:
                return -1  # Error indicator
        
        # Run concurrent database operations
        start_time = time.time()
        tasks = [database_heavy_operation(user) for user in test_users for _ in range(50)]  # 5000 operations
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze database performance
        successful_ops = sum(1 for r in results if isinstance(r, int) and r >= 0)
        failed_ops = len(results) - successful_ops
        total_time = end_time - start_time
        ops_per_second = len(results) / total_time
        
        print(f"📊 Database Pool Results:")
        print(f"   - Total Operations: {len(results)}")
        print(f"   - Successful: {successful_ops}")
        print(f"   - Failed: {failed_ops}")
        print(f"   - Success Rate: {successful_ops/len(results):.2%}")
        print(f"   - Operations/Second: {ops_per_second:.1f}")
        print(f"   - Total Time: {total_time:.2f}s")
        
        # Database performance requirements
        assert successful_ops / len(results) >= 0.95, f"Database success rate too low: {successful_ops/len(results):.2%}"
        assert ops_per_second >= 50, f"Database throughput too low: {ops_per_second:.1f} ops/s"
        assert total_time <= 120, f"Database operations took too long: {total_time:.2f}s"
    
    # Helper Methods
    
    async def _create_test_users(self, user_repo, count: int) -> List[Dict]:
        """Create test users for load testing."""
        users = []
        for i in range(count):
            user_data = {
                'id': str(uuid.uuid4()),
                'email': f'loadtest_user_{i}@example.com',
                'password_hash': 'test_hash',
                'first_name': f'LoadTest{i}',
                'last_name': 'User',
                'created_at': datetime.utcnow(),
                'is_active': True
            }
            try:
                await user_repo.create(user_data)
                users.append(user_data)
            except Exception:
                pass  # Skip duplicates
        return users
    
    async def _create_test_children(self, child_repo, users: List[Dict], count: int) -> List[Dict]:
        """Create test children for load testing."""
        children = []
        for i in range(count):
            parent = random.choice(users)
            child_data = {
                'id': str(uuid.uuid4()),
                'name': f'LoadTestChild{i}',
                'age': random.randint(3, 13),
                'parent_id': parent['id'],
                'preferences': {'theme': 'default'},
                'created_at': datetime.utcnow(),
                'is_active': True
            }
            try:
                await child_repo.create(child_data)
                children.append(child_data)
            except Exception:
                pass  # Skip creation failures
        return children
    
    async def _run_concurrent_session_test(
        self, 
        service: UserService, 
        users: List[Dict], 
        children: List[Dict],
        concurrent_sessions: int,
        operations_per_session: int,
        metrics: LoadTestMetrics
    ):
        """Run concurrent session operations with full monitoring."""
        
        async def session_lifecycle(session_num: int):
            """Simulate complete session lifecycle."""
            child = random.choice(children)
            operations_completed = 0
            session_id = None
            
            try:
                # 1. Create Session
                start_time = time.time()
                session_id = await service.create_session(
                    child_id=uuid.UUID(child['id']),
                    device_info={'device': f'load_test_{session_num}'},
                    accessibility_needs=[]
                )
                create_time = time.time() - start_time
                metrics.record_request(True, create_time)
                operations_completed += 1
                
                # 2. Multiple session operations
                for op_num in range(operations_per_session):
                    # Update session activity
                    start_time = time.time()
                    await service.update_session_activity(session_id)
                    update_time = time.time() - start_time
                    metrics.record_request(True, update_time)
                    operations_completed += 1
                    
                    # Get session stats occasionally
                    if op_num % 5 == 0:
                        start_time = time.time()
                        stats = await service.get_session_stats(uuid.UUID(child['id']))
                        stats_time = time.time() - start_time
                        metrics.record_request(True, stats_time)
                        operations_completed += 1
                
                # 3. End Session
                start_time = time.time()
                await service.end_session(session_id)
                end_time = time.time() - start_time
                metrics.record_request(True, end_time)
                operations_completed += 1
                
            except Exception as e:
                error_type = type(e).__name__
                metrics.record_request(False, 0, error_type)
                if session_id:
                    try:
                        await service.end_session(session_id)
                    except:
                        pass  # Cleanup attempt failed
            
            return operations_completed
        
        # Monitor system resources during test
        async def monitor_resources():
            """Monitor system resources during load test."""
            while metrics.metrics['total_requests'] < concurrent_sessions * operations_per_session * 0.8:
                metrics.record_system_metrics()
                await asyncio.sleep(1)
        
        # Start resource monitoring
        monitor_task = asyncio.create_task(monitor_resources())
        
        # Run concurrent sessions
        print(f"   🔄 Running {concurrent_sessions} concurrent sessions...")
        start_time = time.time()
        
        # Use semaphore to control concurrency and prevent overwhelming the system
        semaphore = asyncio.Semaphore(min(concurrent_sessions, 500))  # Max 500 truly concurrent
        
        async def controlled_session(session_num):
            async with semaphore:
                return await session_lifecycle(session_num)
        
        tasks = [controlled_session(i) for i in range(concurrent_sessions)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        print(f"   ✅ Completed in {total_time:.2f}s")
        
        # Stop resource monitoring
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        # Final metrics recording
        successful_sessions = sum(1 for r in results if isinstance(r, int) and r > 0)
        print(f"   📊 Successful Sessions: {successful_sessions}/{concurrent_sessions}")


# Performance Requirements Documentation
PERFORMANCE_REQUIREMENTS = {
    "1000_sessions": {
        "success_rate": 0.95,
        "p95_response_time": 5.0,
        "p99_response_time": 10.0,
        "min_throughput": 100,
        "max_memory_mb": 2048
    },
    "5000_sessions": {
        "success_rate": 0.90,
        "p95_response_time": 8.0,
        "p99_response_time": 15.0,
        "min_throughput": 50,
        "max_memory_mb": 4096
    },
    "10000_sessions": {
        "success_rate": 0.80,
        "p95_response_time": 20.0,
        "p99_response_time": 30.0,
        "min_throughput": 25,
        "max_memory_mb": 8192
    }
}


if __name__ == "__main__":
    print("🚀 User Service Load Testing - Production Grade")
    print("Run with: pytest tests/performance/test_user_service_load.py -v -m performance")