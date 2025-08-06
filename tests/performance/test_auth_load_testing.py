"""
🚀 PRODUCTION LOAD TESTING - AUTH SERVER PERFORMANCE
==================================================
High-intensity load testing for authentication endpoints.
Target: Handle 10,000+ concurrent users with <500ms response time.

NO PERFORMANCE DEGRADATION ALLOWED FOR CHILD SAFETY.
"""

import asyncio
import aiohttp
import pytest
import time
import statistics
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import psutil
import threading
from dataclasses import dataclass
import matplotlib.pyplot as plt
import pandas as pd

# Performance testing framework
import locust
from locust import HttpUser, task, between
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging

# Internal imports
from src.infrastructure.security.auth import TokenManager, UserAuthenticator
from src.infrastructure.config.production_config import get_config


@dataclass
class LoadTestResult:
    """Performance test results container."""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    duration_seconds: float
    cpu_usage_avg: float
    memory_usage_avg: float
    concurrent_users: int
    
    def is_performance_acceptable(self) -> bool:
        """Check if performance meets production requirements."""
        return (
            self.avg_response_time < 500.0 and  # <500ms average
            self.p95_response_time < 1000.0 and  # <1s for 95% of requests
            self.error_rate < 0.01 and  # <1% error rate
            self.requests_per_second > 100  # >100 RPS minimum
        )


class AuthLoadTester:
    """Comprehensive authentication load testing suite."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[LoadTestResult] = []
        self.system_monitor = SystemMonitor()
        
    async def run_comprehensive_load_tests(self) -> Dict[str, Any]:
        """Run all load tests and generate comprehensive report."""
        print("🚀 Starting Comprehensive Auth Load Testing...")
        
        test_suite = [
            ("login_burst_test", self.test_login_burst_load),
            ("token_refresh_stress", self.test_token_refresh_stress),
            ("concurrent_auth_test", self.test_concurrent_authentication),
            ("sustained_load_test", self.test_sustained_load),
            ("failure_recovery_test", self.test_failure_recovery),
            ("geographic_distribution_test", self.test_geographic_distribution),
        ]
        
        overall_results = {}
        
        for test_name, test_func in test_suite:
            print(f"\n🔥 Running {test_name}...")
            try:
                result = await test_func()
                self.results.append(result)
                overall_results[test_name] = result
                
                if result.is_performance_acceptable():
                    print(f"✅ {test_name}: PASSED")
                else:
                    print(f"❌ {test_name}: FAILED - Performance below requirements")
                    
            except Exception as e:
                print(f"💥 {test_name}: ERROR - {e}")
                overall_results[test_name] = {"error": str(e)}
        
        # Generate comprehensive report
        return self.generate_performance_report(overall_results)
    
    async def test_login_burst_load(self) -> LoadTestResult:
        """Test login endpoint under burst load - 10,000 requests in 1 minute."""
        print("   🎯 Testing login burst: 10,000 requests/minute")
        
        start_time = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        # Monitor system resources
        self.system_monitor.start_monitoring()
        
        # Create test users pool
        test_users = self._generate_test_users(1000)
        
        # Burst configuration
        concurrent_users = 200
        requests_per_user = 50
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            
            # Create concurrent tasks
            tasks = []
            for user_batch in self._chunk_list(test_users, concurrent_users):
                for user in user_batch:
                    task = self._perform_login_requests(
                        session, user, requests_per_user
                    )
                    tasks.append(task)
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                else:
                    successful_requests += len(result["response_times"])
                    response_times.extend(result["response_times"])
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Stop monitoring and get averages
        cpu_avg, memory_avg = self.system_monitor.stop_monitoring()
        
        # Calculate statistics
        if response_times:
            avg_response = statistics.mean(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            p95_response = self._percentile(response_times, 95)
            p99_response = self._percentile(response_times, 99)
        else:
            avg_response = min_response = max_response = p95_response = p99_response = 0
        
        total_requests = successful_requests + failed_requests
        rps = total_requests / duration if duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        return LoadTestResult(
            test_name="login_burst_test",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response,
            min_response_time=min_response,
            max_response_time=max_response,
            p95_response_time=p95_response,
            p99_response_time=p99_response,
            requests_per_second=rps,
            error_rate=error_rate,
            duration_seconds=duration,
            cpu_usage_avg=cpu_avg,
            memory_usage_avg=memory_avg,
            concurrent_users=concurrent_users
        )
    
    async def test_token_refresh_stress(self) -> LoadTestResult:
        """Stress test token refresh under heavy load."""
        print("   🔄 Testing token refresh stress: high-frequency refresh operations")
        
        start_time = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        self.system_monitor.start_monitoring()
        
        # Create initial tokens
        token_manager = TokenManager()
        test_tokens = []
        
        for i in range(500):
            token_data = {
                "sub": f"user_{i}",
                "email": f"user_{i}@test.com",
                "role": "parent",
                "user_type": "parent"
            }
            refresh_token = token_manager.create_refresh_token(token_data)
            test_tokens.append(refresh_token)
        
        async with aiohttp.ClientSession() as session:
            # Create refresh tasks
            tasks = []
            for token in test_tokens:
                for _ in range(20):  # 20 refreshes per token
                    task = self._perform_token_refresh(session, token)
                    tasks.append(task)
            
            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                else:
                    successful_requests += 1
                    response_times.append(result["response_time"])
        
        end_time = time.time()
        duration = end_time - start_time
        cpu_avg, memory_avg = self.system_monitor.stop_monitoring()
        
        # Calculate statistics
        if response_times:
            avg_response = statistics.mean(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            p95_response = self._percentile(response_times, 95)
            p99_response = self._percentile(response_times, 99)
        else:
            avg_response = min_response = max_response = p95_response = p99_response = 0
        
        total_requests = successful_requests + failed_requests
        rps = total_requests / duration if duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        return LoadTestResult(
            test_name="token_refresh_stress",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response,
            min_response_time=min_response,
            max_response_time=max_response,
            p95_response_time=p95_response,
            p99_response_time=p99_response,
            requests_per_second=rps,
            error_rate=error_rate,
            duration_seconds=duration,
            cpu_usage_avg=cpu_avg,
            memory_usage_avg=memory_avg,
            concurrent_users=500
        )
    
    async def test_concurrent_authentication(self) -> LoadTestResult:
        """Test concurrent authentication from different sources."""
        print("   🌐 Testing concurrent auth: multiple geographic sources")
        
        start_time = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        self.system_monitor.start_monitoring()
        
        # Simulate different user types and locations
        user_scenarios = [
            {"type": "parent", "location": "US", "count": 100},
            {"type": "parent", "location": "EU", "count": 100},
            {"type": "admin", "location": "US", "count": 10},
            {"type": "parent", "location": "Asia", "count": 50},
        ]
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            for scenario in user_scenarios:
                for i in range(scenario["count"]):
                    user_data = {
                        "email": f"{scenario['type']}_{scenario['location']}_{i}@test.com",
                        "password": "test_password_123",
                        "user_type": scenario["type"],
                        "location": scenario["location"]
                    }
                    
                    # Each user performs multiple auth operations
                    for _ in range(5):
                        task = self._perform_full_auth_cycle(session, user_data)
                        tasks.append(task)
            
            # Execute all concurrent operations
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                else:
                    successful_requests += 1
                    response_times.append(result["total_time"])
        
        end_time = time.time()
        duration = end_time - start_time
        cpu_avg, memory_avg = self.system_monitor.stop_monitoring()
        
        # Calculate statistics
        if response_times:
            avg_response = statistics.mean(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            p95_response = self._percentile(response_times, 95)
            p99_response = self._percentile(response_times, 99)
        else:
            avg_response = min_response = max_response = p95_response = p99_response = 0
        
        total_requests = successful_requests + failed_requests
        rps = total_requests / duration if duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        return LoadTestResult(
            test_name="concurrent_authentication",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response,
            min_response_time=min_response,
            max_response_time=max_response,
            p95_response_time=p95_response,
            p99_response_time=p99_response,
            requests_per_second=rps,
            error_rate=error_rate,
            duration_seconds=duration,
            cpu_usage_avg=cpu_avg,
            memory_usage_avg=memory_avg,
            concurrent_users=260
        )
    
    async def test_sustained_load(self) -> LoadTestResult:
        """Test sustained load over extended period."""
        print("   ⏱️ Testing sustained load: 5 minutes constant traffic")
        
        start_time = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        self.system_monitor.start_monitoring()
        
        # Sustained load configuration
        duration_minutes = 5
        target_rps = 200
        concurrent_users = 50
        
        end_target_time = start_time + (duration_minutes * 60)
        
        async with aiohttp.ClientSession() as session:
            while time.time() < end_target_time:
                # Create batch of requests
                tasks = []
                for i in range(concurrent_users):
                    user_data = {
                        "email": f"sustained_user_{i}_{int(time.time())}@test.com",
                        "password": "test_password_123"
                    }
                    task = self._perform_login_requests(session, user_data, 1)
                    tasks.append(task)
                
                # Execute batch
                batch_start = time.time()
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process batch results
                for result in results:
                    if isinstance(result, Exception):
                        failed_requests += 1
                    else:
                        successful_requests += 1
                        if result.get("response_times"):
                            response_times.extend(result["response_times"])
                
                # Rate limiting to maintain target RPS
                batch_duration = time.time() - batch_start
                target_batch_duration = len(tasks) / target_rps
                if batch_duration < target_batch_duration:
                    await asyncio.sleep(target_batch_duration - batch_duration)
        
        end_time = time.time()
        duration = end_time - start_time
        cpu_avg, memory_avg = self.system_monitor.stop_monitoring()
        
        # Calculate statistics
        if response_times:
            avg_response = statistics.mean(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            p95_response = self._percentile(response_times, 95)
            p99_response = self._percentile(response_times, 99)
        else:
            avg_response = min_response = max_response = p95_response = p99_response = 0
        
        total_requests = successful_requests + failed_requests
        rps = total_requests / duration if duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        return LoadTestResult(
            test_name="sustained_load",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response,
            min_response_time=min_response,
            max_response_time=max_response,
            p95_response_time=p95_response,
            p99_response_time=p99_response,
            requests_per_second=rps,
            error_rate=error_rate,
            duration_seconds=duration,
            cpu_usage_avg=cpu_avg,
            memory_usage_avg=memory_avg,
            concurrent_users=concurrent_users
        )
    
    async def test_failure_recovery(self) -> LoadTestResult:
        """Test system recovery under failure conditions."""
        print("   💥 Testing failure recovery: bad credentials + system stress")
        
        start_time = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        self.system_monitor.start_monitoring()
        
        async with aiohttp.ClientSession() as session:
            # Mix of valid and invalid requests
            tasks = []
            
            # 70% valid requests
            for i in range(700):
                user_data = {
                    "email": f"valid_user_{i}@test.com",
                    "password": "correct_password_123"
                }
                task = self._perform_login_requests(session, user_data, 1)
                tasks.append(task)
            
            # 30% invalid requests (bad passwords, non-existent users)
            for i in range(300):
                if i % 2 == 0:
                    # Bad password
                    user_data = {
                        "email": f"valid_user_{i}@test.com",
                        "password": "wrong_password"
                    }
                else:
                    # Non-existent user
                    user_data = {
                        "email": f"nonexistent_{i}@test.com",
                        "password": "any_password"
                    }
                task = self._perform_login_requests(session, user_data, 1)
                tasks.append(task)
            
            # Execute all mixed requests
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                else:
                    # Count both successful and expected failures
                    if result.get("response_times"):
                        successful_requests += 1
                        response_times.extend(result["response_times"])
                    else:
                        # Expected auth failure (still counts as successful system response)
                        successful_requests += 1
                        response_times.append(result.get("response_time", 0))
        
        end_time = time.time()
        duration = end_time - start_time
        cpu_avg, memory_avg = self.system_monitor.stop_monitoring()
        
        # Calculate statistics
        if response_times:
            avg_response = statistics.mean(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            p95_response = self._percentile(response_times, 95)
            p99_response = self._percentile(response_times, 99)
        else:
            avg_response = min_response = max_response = p95_response = p99_response = 0
        
        total_requests = successful_requests + failed_requests
        rps = total_requests / duration if duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        return LoadTestResult(
            test_name="failure_recovery",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response,
            min_response_time=min_response,
            max_response_time=max_response,
            p95_response_time=p95_response,
            p99_response_time=p99_response,
            requests_per_second=rps,
            error_rate=error_rate,
            duration_seconds=duration,
            cpu_usage_avg=cpu_avg,
            memory_usage_avg=memory_avg,
            concurrent_users=1000
        )
    
    async def test_geographic_distribution(self) -> LoadTestResult:
        """Test performance with geographically distributed requests."""
        print("   🌍 Testing geographic distribution: simulated global load")
        
        start_time = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        self.system_monitor.start_monitoring()
        
        # Simulate different geographic regions with varying latencies
        regions = [
            {"name": "US_East", "users": 200, "latency_sim": 0.010},     # 10ms
            {"name": "US_West", "users": 150, "latency_sim": 0.020},     # 20ms
            {"name": "Europe", "users": 180, "latency_sim": 0.050},      # 50ms
            {"name": "Asia", "users": 120, "latency_sim": 0.080},        # 80ms
            {"name": "Australia", "users": 50, "latency_sim": 0.120},    # 120ms
        ]
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            for region in regions:
                for i in range(region["users"]):
                    user_data = {
                        "email": f"{region['name']}_user_{i}@test.com",
                        "password": "test_password_123",
                        "region": region["name"]
                    }
                    
                    # Add simulated network latency
                    task = self._perform_geo_distributed_auth(
                        session, user_data, region["latency_sim"]
                    )
                    tasks.append(task)
            
            # Execute all geo-distributed requests
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                else:
                    successful_requests += 1
                    response_times.append(result["response_time"])
        
        end_time = time.time()
        duration = end_time - start_time
        cpu_avg, memory_avg = self.system_monitor.stop_monitoring()
        
        # Calculate statistics
        if response_times:
            avg_response = statistics.mean(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            p95_response = self._percentile(response_times, 95)
            p99_response = self._percentile(response_times, 99)
        else:
            avg_response = min_response = max_response = p95_response = p99_response = 0
        
        total_requests = successful_requests + failed_requests
        rps = total_requests / duration if duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        return LoadTestResult(
            test_name="geographic_distribution",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response,
            min_response_time=min_response,
            max_response_time=max_response,
            p95_response_time=p95_response,
            p99_response_time=p99_response,
            requests_per_second=rps,
            error_rate=error_rate,
            duration_seconds=duration,
            cpu_usage_avg=cpu_avg,
            memory_usage_avg=memory_avg,
            concurrent_users=700
        )
    
    # Helper methods
    
    async def _perform_login_requests(self, session: aiohttp.ClientSession, 
                                    user_data: Dict[str, Any], count: int) -> Dict[str, Any]:
        """Perform multiple login requests for a user."""
        response_times = []
        
        for _ in range(count):
            start_time = time.time()
            try:
                async with session.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json=user_data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    await response.json()
                    end_time = time.time()
                    response_times.append((end_time - start_time) * 1000)  # Convert to ms
            except Exception as e:
                # Still record the time even for failed requests
                end_time = time.time()
                response_times.append((end_time - start_time) * 1000)
        
        return {"response_times": response_times}
    
    async def _perform_token_refresh(self, session: aiohttp.ClientSession, 
                                   refresh_token: str) -> Dict[str, Any]:
        """Perform token refresh operation."""
        start_time = time.time()
        try:
            async with session.post(
                f"{self.base_url}/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
                headers={"Content-Type": "application/json"}
            ) as response:
                await response.json()
                end_time = time.time()
                return {"response_time": (end_time - start_time) * 1000}
        except Exception as e:
            end_time = time.time()
            return {"response_time": (end_time - start_time) * 1000, "error": str(e)}
    
    async def _perform_full_auth_cycle(self, session: aiohttp.ClientSession,
                                     user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform complete authentication cycle: login -> refresh -> logout."""
        cycle_start = time.time()
        
        try:
            # Login
            async with session.post(
                f"{self.base_url}/api/v1/auth/login",
                json=user_data
            ) as response:
                auth_result = await response.json()
                access_token = auth_result.get("access_token")
                refresh_token = auth_result.get("refresh_token")
            
            # Refresh token
            if refresh_token:
                async with session.post(
                    f"{self.base_url}/api/v1/auth/refresh",
                    json={"refresh_token": refresh_token}
                ) as response:
                    await response.json()
            
            # Access protected endpoint
            if access_token:
                async with session.get(
                    f"{self.base_url}/api/v1/protected",
                    headers={"Authorization": f"Bearer {access_token}"}
                ) as response:
                    await response.json()
            
            cycle_end = time.time()
            return {"total_time": (cycle_end - cycle_start) * 1000}
            
        except Exception as e:
            cycle_end = time.time()
            return {"total_time": (cycle_end - cycle_start) * 1000, "error": str(e)}
    
    async def _perform_geo_distributed_auth(self, session: aiohttp.ClientSession,
                                          user_data: Dict[str, Any], 
                                          latency_sim: float) -> Dict[str, Any]:
        """Perform authentication with simulated geographic latency."""
        start_time = time.time()
        
        # Simulate network latency
        await asyncio.sleep(latency_sim)
        
        try:
            async with session.post(
                f"{self.base_url}/api/v1/auth/login",
                json=user_data,
                headers={
                    "Content-Type": "application/json",
                    "X-Forwarded-For": self._get_region_ip(user_data.get("region", "US")),
                    "X-Region": user_data.get("region", "US")
                }
            ) as response:
                await response.json()
                
        except Exception as e:
            pass  # Still measure total time
        
        end_time = time.time()
        return {"response_time": (end_time - start_time) * 1000}
    
    def _generate_test_users(self, count: int) -> List[Dict[str, Any]]:
        """Generate test user data."""
        users = []
        for i in range(count):
            users.append({
                "email": f"loadtest_user_{i}_{int(time.time())}@test.com",
                "password": "LoadTest_Password_123!",
                "first_name": f"LoadTest{i}",
                "last_name": "User"
            })
        return users
    
    def _chunk_list(self, lst: List, chunk_size: int) -> List[List]:
        """Split list into chunks."""
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_data) - 1)
        weight = index - lower_index
        return sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight
    
    def _get_region_ip(self, region: str) -> str:
        """Get simulated IP for region."""
        region_ips = {
            "US_East": "52.70.123.45",
            "US_West": "54.183.67.89",
            "Europe": "35.158.90.123",
            "Asia": "13.230.45.67",
            "Australia": "54.253.78.90"
        }
        return region_ips.get(region, "127.0.0.1")
    
    def generate_performance_report(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": len([r for r in results.values() if isinstance(r, LoadTestResult)]),
                "passed_tests": len([r for r in results.values() 
                                   if isinstance(r, LoadTestResult) and r.is_performance_acceptable()]),
                "failed_tests": len([r for r in results.values() 
                                   if isinstance(r, LoadTestResult) and not r.is_performance_acceptable()]),
                "error_tests": len([r for r in results.values() if not isinstance(r, LoadTestResult)])
            },
            "detailed_results": {},
            "performance_analysis": {},
            "recommendations": []
        }
        
        # Process detailed results
        for test_name, result in results.items():
            if isinstance(result, LoadTestResult):
                report["detailed_results"][test_name] = {
                    "status": "PASS" if result.is_performance_acceptable() else "FAIL",
                    "metrics": {
                        "avg_response_time_ms": result.avg_response_time,
                        "p95_response_time_ms": result.p95_response_time,
                        "p99_response_time_ms": result.p99_response_time,
                        "requests_per_second": result.requests_per_second,
                        "error_rate_percent": result.error_rate * 100,
                        "total_requests": result.total_requests,
                        "concurrent_users": result.concurrent_users,
                        "cpu_usage_percent": result.cpu_usage_avg,
                        "memory_usage_percent": result.memory_usage_avg
                    }
                }
        
        # Performance analysis
        all_results = [r for r in results.values() if isinstance(r, LoadTestResult)]
        if all_results:
            avg_response_times = [r.avg_response_time for r in all_results]
            total_rps = sum(r.requests_per_second for r in all_results)
            avg_error_rate = statistics.mean([r.error_rate for r in all_results])
            
            report["performance_analysis"] = {
                "overall_avg_response_time_ms": statistics.mean(avg_response_times),
                "best_response_time_ms": min(avg_response_times),
                "worst_response_time_ms": max(avg_response_times),
                "total_requests_per_second": total_rps,
                "overall_error_rate_percent": avg_error_rate * 100,
                "performance_grade": self._calculate_performance_grade(all_results)
            }
        
        # Recommendations
        if report["summary"]["failed_tests"] > 0:
            report["recommendations"].extend([
                "❌ Performance below requirements - investigate bottlenecks",
                "🔧 Consider adding database connection pooling",
                "🚀 Implement Redis caching for frequently accessed data",
                "📊 Monitor system resources during peak load"
            ])
        else:
            report["recommendations"].extend([
                "✅ All performance tests passed - system ready for production",
                "📈 Consider implementing auto-scaling for peak traffic",
                "🔍 Continue monitoring performance in production",
                "🎯 Set up alerting for performance degradation"
            ])
        
        return report
    
    def _calculate_performance_grade(self, results: List[LoadTestResult]) -> str:
        """Calculate overall performance grade."""
        passed_tests = sum(1 for r in results if r.is_performance_acceptable())
        total_tests = len(results)
        
        if total_tests == 0:
            return "UNKNOWN"
        
        pass_rate = passed_tests / total_tests
        
        if pass_rate >= 0.95:
            return "A+ (EXCELLENT)"
        elif pass_rate >= 0.90:
            return "A (VERY GOOD)"
        elif pass_rate >= 0.80:
            return "B (GOOD)"
        elif pass_rate >= 0.70:
            return "C (ACCEPTABLE)"
        elif pass_rate >= 0.60:
            return "D (NEEDS IMPROVEMENT)"
        else:
            return "F (CRITICAL ISSUES)"


class SystemMonitor:
    """System resource monitoring during load tests."""
    
    def __init__(self):
        self.monitoring = False
        self.cpu_samples = []
        self.memory_samples = []
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Start monitoring system resources."""
        self.monitoring = True
        self.cpu_samples = []
        self.memory_samples = []
        self.monitor_thread = threading.Thread(target=self._monitor_resources)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> tuple:
        """Stop monitoring and return averages."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        
        cpu_avg = statistics.mean(self.cpu_samples) if self.cpu_samples else 0
        memory_avg = statistics.mean(self.memory_samples) if self.memory_samples else 0
        
        return cpu_avg, memory_avg
    
    def _monitor_resources(self):
        """Monitor system resources in background thread."""
        while self.monitoring:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()
                
                self.cpu_samples.append(cpu_percent)
                self.memory_samples.append(memory_info.percent)
                
            except Exception:
                pass  # Continue monitoring even if sampling fails


# Locust-based load testing classes for advanced scenarios

class AuthLoadTestUser(HttpUser):
    """Locust user for authentication load testing."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Initialize user session."""
        self.user_id = str(uuid.uuid4())
        self.user_data = {
            "email": f"locust_user_{self.user_id}@test.com",
            "password": "LocustTest_Password_123!"
        }
        self.tokens = {}
    
    @task(3)
    def login(self):
        """Perform login operation."""
        with self.client.post(
            "/api/v1/auth/login",
            json=self.user_data,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.tokens = {
                    "access_token": data.get("access_token"),
                    "refresh_token": data.get("refresh_token")
                }
                response.success()
            else:
                response.failure(f"Login failed with status {response.status_code}")
    
    @task(1)
    def refresh_token(self):
        """Perform token refresh."""
        if not self.tokens.get("refresh_token"):
            return
        
        with self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": self.tokens["refresh_token"]},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.tokens["access_token"] = data.get("access_token")
                response.success()
            else:
                response.failure(f"Token refresh failed with status {response.status_code}")
    
    @task(2)
    def access_protected_endpoint(self):
        """Access protected endpoint with token."""
        if not self.tokens.get("access_token"):
            return
        
        headers = {"Authorization": f"Bearer {self.tokens['access_token']}"}
        with self.client.get(
            "/api/v1/protected",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Protected access failed with status {response.status_code}")


# Performance testing execution functions

async def run_auth_load_tests():
    """Main function to run all authentication load tests."""
    print("🚀 STARTING COMPREHENSIVE AUTH LOAD TESTING")
    print("=" * 60)
    
    tester = AuthLoadTester("http://localhost:8000")
    
    try:
        # Run all load tests
        results = await tester.run_comprehensive_load_tests()
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"auth_load_test_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📊 COMPREHENSIVE PERFORMANCE REPORT")
        print("=" * 60)
        print(f"Tests Run: {results['summary']['total_tests']}")
        print(f"Tests Passed: {results['summary']['passed_tests']}")
        print(f"Tests Failed: {results['summary']['failed_tests']}")
        print(f"Tests with Errors: {results['summary']['error_tests']}")
        
        if "performance_analysis" in results:
            analysis = results["performance_analysis"]
            print(f"\nPerformance Grade: {analysis['performance_grade']}")
            print(f"Overall Avg Response Time: {analysis['overall_avg_response_time_ms']:.2f}ms")
            print(f"Total RPS Capability: {analysis['total_requests_per_second']:.2f}")
            print(f"Overall Error Rate: {analysis['overall_error_rate_percent']:.2f}%")
        
        print(f"\n📁 Detailed report saved to: {report_file}")
        
        # Print recommendations
        if results.get("recommendations"):
            print("\n🎯 RECOMMENDATIONS:")
            for rec in results["recommendations"]:
                print(f"  {rec}")
        
        return results
        
    except Exception as e:
        print(f"💥 Load testing failed: {e}")
        raise


if __name__ == "__main__":
    # Run the load tests
    asyncio.run(run_auth_load_tests())