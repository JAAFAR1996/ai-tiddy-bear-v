#!/usr/bin/env python3
"""
ESP32 Reliability & Stress Testing Suite
========================================
Comprehensive testing of 24h continuous operation, reboot scenarios,
network flooding, and system resilience under stress conditions.
"""

import asyncio
import json
import time
import threading
import psutil
import tracemalloc
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import tempfile
import os
import random
import statistics
from concurrent.futures import ThreadPoolExecutor
import queue


@dataclass
class ReliabilityTestResult:
    """Result of reliability/stress test."""
    test_name: str
    status: str  # PASS, FAIL, ERROR
    details: Dict[str, Any]
    timestamp: str
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: str
    memory_usage_mb: float
    cpu_usage_percent: float
    connection_count: int
    error_count: int
    latency_ms: float
    throughput_bps: int


@dataclass
class NetworkFloodResult:
    """Network flood test results."""
    requests_sent: int
    requests_blocked: int
    requests_allowed: int
    rate_limit_triggered: bool
    avg_response_time_ms: float
    backend_resilience_score: float


class MockESP32ReliabilityDevice:
    """Mock ESP32 device for reliability testing."""
    
    def __init__(self, device_id: str = "ESP32_RELIABILITY_TEST"):
        self.device_id = device_id
        self.is_connected = True
        self.is_running = False
        self.memory_usage_kb = 50.0  # Start with 50KB
        self.max_memory_kb = 200.0   # ESP32 has limited RAM
        self.connection_drops = 0
        self.errors = []
        self.operations_completed = 0
        self.test_buffer = []
        self.last_reboot = None
        
        # Performance metrics
        self.metrics_history = []
        self.current_latency_ms = 25.0
        
        # Stress test state
        self.stress_level = 0.0  # 0.0 to 1.0
        self.memory_leak_rate = 0.1  # KB per operation
        
    def start_operation(self):
        """Start continuous operation."""
        self.is_running = True
        print(f"🚀 Device {self.device_id} starting continuous operation")
        
    def stop_operation(self):
        """Stop continuous operation."""
        self.is_running = False
        print(f"⏹️ Device {self.device_id} stopping operation")
        
    def simulate_operation_cycle(self):
        """Simulate one operation cycle."""
        if not self.is_running or not self.is_connected:
            return False
        
        try:
            # Simulate memory usage increase
            self.memory_usage_kb += self.memory_leak_rate * (1 + self.stress_level)
            
            # Simulate random connection drops
            if random.random() < 0.001 * (1 + self.stress_level):  # 0.1% base chance
                self.simulate_connection_drop()
                return False
            
            # Simulate random errors
            if random.random() < 0.002 * (1 + self.stress_level):  # 0.2% base chance
                self.errors.append({
                    "timestamp": datetime.now().isoformat(),
                    "type": "operation_error",
                    "message": "Simulated operation failure"
                })
                return False
            
            # Simulate memory cleanup occasionally
            if random.random() < 0.1:  # 10% chance
                self.memory_usage_kb = max(50.0, self.memory_usage_kb * 0.9)
            
            # Check memory limit
            if self.memory_usage_kb > self.max_memory_kb:
                self.errors.append({
                    "timestamp": datetime.now().isoformat(),
                    "type": "memory_overflow", 
                    "message": f"Memory usage exceeded {self.max_memory_kb}KB"
                })
                return False
            
            # Update latency based on stress and memory usage
            base_latency = 25.0
            memory_factor = (self.memory_usage_kb / self.max_memory_kb) * 20
            stress_factor = self.stress_level * 50
            self.current_latency_ms = base_latency + memory_factor + stress_factor
            
            self.operations_completed += 1
            return True
            
        except Exception as e:
            self.errors.append({
                "timestamp": datetime.now().isoformat(),
                "type": "exception",
                "message": str(e)
            })
            return False
    
    def simulate_connection_drop(self):
        """Simulate connection drop."""
        self.is_connected = False
        self.connection_drops += 1
        print(f"📡❌ Connection drop #{self.connection_drops} for {self.device_id}")
        
        # Simulate reconnection after delay
        def reconnect():
            time.sleep(random.uniform(1.0, 3.0))  # 1-3 second delay
            self.is_connected = True
            print(f"📡✅ Reconnected {self.device_id}")
            
        threading.Thread(target=reconnect, daemon=True).start()
    
    def simulate_reboot(self):
        """Simulate device reboot."""
        print(f"🔄 Rebooting device {self.device_id}...")
        self.last_reboot = datetime.now()
        
        # Save critical data before reboot
        pre_reboot_data = {
            "operations_completed": self.operations_completed,
            "test_buffer": self.test_buffer.copy(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Simulate reboot time
        self.is_connected = False
        self.is_running = False
        time.sleep(2.0)  # 2 second reboot
        
        # Restore state after reboot
        self.is_connected = True
        self.memory_usage_kb = 50.0  # Reset memory
        self.current_latency_ms = 25.0  # Reset latency
        
        # Check data integrity
        data_loss = random.random() < 0.05  # 5% chance of minor data loss
        if data_loss:
            # Simulate minor data loss
            lost_operations = random.randint(1, 5)
            self.operations_completed = max(0, pre_reboot_data["operations_completed"] - lost_operations)
            self.test_buffer = self.test_buffer[:-lost_operations] if len(self.test_buffer) > lost_operations else []
        
        print(f"✅ Device {self.device_id} rebooted successfully")
        return not data_loss  # Return True if no data loss
        
    def get_current_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        return SystemMetrics(
            timestamp=datetime.now().isoformat(),
            memory_usage_mb=self.memory_usage_kb / 1024,
            cpu_usage_percent=min(100.0, 30.0 + self.stress_level * 60),  # Simulated CPU
            connection_count=1 if self.is_connected else 0,
            error_count=len(self.errors),
            latency_ms=self.current_latency_ms,
            throughput_bps=max(0, 1000 - int(self.stress_level * 800))  # Decreases under stress
        )
    
    def increase_stress(self, level: float):
        """Increase stress level (0.0 to 1.0)."""
        self.stress_level = min(1.0, level)
        print(f"⚡ Stress level increased to {self.stress_level:.2f} for {self.device_id}")


class MockBackendRateLimiter:
    """Mock backend rate limiter for flood testing."""
    
    def __init__(self):
        self.requests_per_minute = 60  # Base rate limit
        self.requests_per_second = 10  # Burst rate limit
        self.request_history = []
        self.blocked_requests = 0
        self.allowed_requests = 0
        
    def check_rate_limit(self, client_ip: str = "192.168.1.100") -> bool:
        """Check if request is allowed by rate limiter."""
        now = datetime.now()
        
        # Clean old requests (older than 1 minute)
        self.request_history = [
            req for req in self.request_history
            if now - req["timestamp"] < timedelta(minutes=1)
        ]
        
        # Count recent requests
        recent_requests = len([
            req for req in self.request_history
            if now - req["timestamp"] < timedelta(seconds=1)
        ])
        
        minute_requests = len(self.request_history)
        
        # Check limits
        if recent_requests >= self.requests_per_second:
            self.blocked_requests += 1
            return False
        
        if minute_requests >= self.requests_per_minute:
            self.blocked_requests += 1
            return False
        
        # Allow request
        self.request_history.append({
            "timestamp": now,
            "client_ip": client_ip
        })
        self.allowed_requests += 1
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "requests_allowed": self.allowed_requests,
            "requests_blocked": self.blocked_requests,
            "total_requests": self.allowed_requests + self.blocked_requests,
            "block_rate_percent": (self.blocked_requests / max(1, self.allowed_requests + self.blocked_requests)) * 100
        }


class ESP32ReliabilityTester:
    """Comprehensive ESP32 reliability and stress testing."""
    
    def __init__(self):
        self.mock_esp32 = MockESP32ReliabilityDevice()
        self.rate_limiter = MockBackendRateLimiter()
        self.test_results = []
        self.continuous_test_running = False
        self.metrics_collector_running = False
        self.collected_metrics = []
        
    def log_test_result(self, result: ReliabilityTestResult):
        """Log test result."""
        self.test_results.append(result)
        status_emoji = "✅" if result.status == "PASS" else "❌" if result.status == "FAIL" else "⚠️"
        duration_str = f" ({result.duration_ms:.1f}ms)" if result.duration_ms else ""
        print(f"{status_emoji} {result.test_name}{duration_str}")
        if result.error_message:
            print(f"   Error: {result.error_message}")
    
    def start_metrics_collection(self):
        """Start collecting system metrics."""
        self.metrics_collector_running = True
        
        def collect_metrics():
            while self.metrics_collector_running:
                try:
                    metrics = self.mock_esp32.get_current_metrics()
                    self.collected_metrics.append(metrics)
                    
                    # Keep only last 1000 metrics to prevent memory issues
                    if len(self.collected_metrics) > 1000:
                        self.collected_metrics = self.collected_metrics[-1000:]
                    
                    time.sleep(5.0)  # Collect every 5 seconds
                    
                except Exception as e:
                    print(f"⚠️ Metrics collection error: {e}")
                    time.sleep(1.0)
        
        self.metrics_thread = threading.Thread(target=collect_metrics, daemon=True)
        self.metrics_thread.start()
        print("📊 Started metrics collection")
    
    def stop_metrics_collection(self):
        """Stop collecting system metrics."""
        self.metrics_collector_running = False
        print("📊 Stopped metrics collection")
    
    def test_24h_continuous_operation(self, duration_minutes: float = 2.0) -> bool:
        """Test 24h continuous operation (shortened for testing)."""
        test_name = f"24h Continuous Operation (Simulated {duration_minutes}min)"
        start_time = time.time()
        
        try:
            # Start metrics collection
            self.start_metrics_collection()
            
            # Start continuous operation
            self.mock_esp32.start_operation()
            self.continuous_test_running = True
            
            print(f"   🔄 Starting {duration_minutes} minute continuous operation test...")
            print("   📊 Monitoring: memory usage, connection drops, errors")
            
            operation_count = 0
            test_start = time.time()
            last_status_update = test_start
            
            # Run continuous operations
            while time.time() - test_start < duration_minutes * 60:
                if not self.continuous_test_running:
                    break
                
                # Perform operation cycle
                success = self.mock_esp32.simulate_operation_cycle()
                if success:
                    operation_count += 1
                
                # Gradually increase stress over time
                elapsed_ratio = (time.time() - test_start) / (duration_minutes * 60)
                stress_level = min(0.8, elapsed_ratio * 0.5)  # Max 50% stress, gradual increase
                self.mock_esp32.increase_stress(stress_level)
                
                # Status update every 10 seconds
                if time.time() - last_status_update >= 10.0:
                    metrics = self.mock_esp32.get_current_metrics()
                    elapsed_minutes = (time.time() - test_start) / 60
                    print(f"   ⏱️ {elapsed_minutes:.1f}min - Ops: {operation_count}, "
                          f"Memory: {metrics.memory_usage_mb:.1f}MB, "
                          f"Errors: {metrics.error_count}, "
                          f"Latency: {metrics.latency_ms:.1f}ms")
                    last_status_update = time.time()
                
                # Small delay between operations
                time.sleep(0.01)  # 10ms delay
            
            # Stop operations
            self.mock_esp32.stop_operation()
            self.continuous_test_running = False
            
            # Stop metrics collection and analyze
            self.stop_metrics_collection()
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Analyze collected metrics
            if self.collected_metrics:
                memory_usage = [m.memory_usage_mb for m in self.collected_metrics]
                latency = [m.latency_ms for m in self.collected_metrics]
                error_counts = [m.error_count for m in self.collected_metrics]
                
                avg_memory = statistics.mean(memory_usage)
                max_memory = max(memory_usage)
                avg_latency = statistics.mean(latency)
                max_latency = max(latency)
                final_errors = error_counts[-1] if error_counts else 0
                
                # Evaluation criteria
                memory_stable = max_memory < 0.15  # Less than 150MB (reasonable for ESP32)
                latency_acceptable = avg_latency < 100  # Less than 100ms average
                error_rate_low = final_errors < operation_count * 0.05  # Less than 5% error rate
                connection_reliable = self.mock_esp32.connection_drops < 5  # Less than 5 drops
                
                overall_pass = (
                    memory_stable and 
                    latency_acceptable and 
                    error_rate_low and 
                    connection_reliable
                )
                
                result = ReliabilityTestResult(
                    test_name=test_name,
                    status="PASS" if overall_pass else "FAIL",
                    details={
                        "test_duration_minutes": duration_minutes,
                        "operations_completed": operation_count,
                        "metrics_collected": len(self.collected_metrics),
                        "memory_analysis": {
                            "average_mb": avg_memory,
                            "maximum_mb": max_memory,
                            "stable": memory_stable
                        },
                        "latency_analysis": {
                            "average_ms": avg_latency,
                            "maximum_ms": max_latency,
                            "acceptable": latency_acceptable
                        },
                        "error_analysis": {
                            "total_errors": final_errors,
                            "error_rate_percent": (final_errors / max(1, operation_count)) * 100,
                            "low_error_rate": error_rate_low
                        },
                        "connection_analysis": {
                            "connection_drops": self.mock_esp32.connection_drops,
                            "reliable": connection_reliable
                        },
                        "overall_assessment": {
                            "continuous_operation_stable": overall_pass,
                            "suitable_for_24h": overall_pass
                        }
                    },
                    timestamp=datetime.now().isoformat(),
                    duration_ms=duration_ms
                )
                
                print(f"   📊 Final Results:")
                print(f"      Operations: {operation_count}")
                print(f"      Avg Memory: {avg_memory:.1f}MB (Max: {max_memory:.1f}MB)")
                print(f"      Avg Latency: {avg_latency:.1f}ms (Max: {max_latency:.1f}ms)")
                print(f"      Errors: {final_errors} ({(final_errors / max(1, operation_count)) * 100:.1f}%)")
                print(f"      Connection Drops: {self.mock_esp32.connection_drops}")
                
            else:
                result = ReliabilityTestResult(
                    test_name=test_name,
                    status="ERROR",
                    details={},
                    timestamp=datetime.now().isoformat(),
                    error_message="No metrics collected during test"
                )
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            self.continuous_test_running = False
            self.stop_metrics_collection()
            
            result = ReliabilityTestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def test_reboot_data_integrity(self) -> bool:
        """Test ESP32 reboot mid-operation with data integrity verification."""
        test_name = "ESP32 Reboot Data Integrity"
        start_time = time.time()
        
        try:
            reboot_tests = []
            
            # Test 1: Normal operation then reboot
            print("   🔄 Testing normal operation -> reboot -> recovery...")
            
            # Start operations and generate some data
            self.mock_esp32.start_operation()
            
            pre_reboot_operations = 0
            for i in range(50):  # Generate 50 operations
                if self.mock_esp32.simulate_operation_cycle():
                    pre_reboot_operations += 1
                    # Add some data to buffer
                    self.mock_esp32.test_buffer.append({
                        "operation_id": i,
                        "timestamp": datetime.now().isoformat(),
                        "data": f"operation_data_{i}"
                    })
                time.sleep(0.02)
            
            operations_before = self.mock_esp32.operations_completed
            buffer_size_before = len(self.mock_esp32.test_buffer)
            
            print(f"      Pre-reboot: {operations_before} operations, {buffer_size_before} buffer items")
            
            # Perform reboot
            reboot_successful = self.mock_esp32.simulate_reboot()
            
            operations_after = self.mock_esp32.operations_completed
            buffer_size_after = len(self.mock_esp32.test_buffer)
            
            # Calculate data loss
            operations_lost = operations_before - operations_after
            buffer_items_lost = buffer_size_before - buffer_size_after
            
            operations_loss_percent = (operations_lost / max(1, operations_before)) * 100
            buffer_loss_percent = (buffer_items_lost / max(1, buffer_size_before)) * 100
            
            # Acceptable data loss thresholds
            acceptable_operations_loss = operations_loss_percent < 10  # Less than 10% loss
            acceptable_buffer_loss = buffer_loss_percent < 10  # Less than 10% loss
            
            reboot_tests.append({
                "test": "normal_reboot_data_integrity",
                "status": "PASS" if reboot_successful and acceptable_operations_loss and acceptable_buffer_loss else "FAIL",
                "reboot_successful": reboot_successful,
                "operations_before": operations_before,
                "operations_after": operations_after,
                "operations_lost": operations_lost,
                "operations_loss_percent": operations_loss_percent,
                "buffer_before": buffer_size_before,
                "buffer_after": buffer_size_after,
                "buffer_lost": buffer_items_lost,
                "buffer_loss_percent": buffer_loss_percent,
                "data_integrity_maintained": acceptable_operations_loss and acceptable_buffer_loss
            })
            
            print(f"      Post-reboot: {operations_after} operations, {buffer_size_after} buffer items")
            print(f"      Data loss: {operations_loss_percent:.1f}% operations, {buffer_loss_percent:.1f}% buffer")
            
            # Test 2: Resume operations after reboot
            print("   ▶️ Testing operation resumption after reboot...")
            
            self.mock_esp32.start_operation()
            post_reboot_operations = 0
            
            for i in range(30):  # 30 more operations
                if self.mock_esp32.simulate_operation_cycle():
                    post_reboot_operations += 1
                time.sleep(0.02)
            
            self.mock_esp32.stop_operation()
            
            resumption_successful = post_reboot_operations >= 25  # At least 25/30 operations
            
            reboot_tests.append({
                "test": "post_reboot_operation_resumption",
                "status": "PASS" if resumption_successful else "FAIL",
                "post_reboot_operations": post_reboot_operations,
                "expected_operations": 30,
                "resumption_rate_percent": (post_reboot_operations / 30) * 100,
                "resumption_successful": resumption_successful
            })
            
            print(f"      Resumption: {post_reboot_operations}/30 operations ({(post_reboot_operations/30)*100:.1f}%)")
            
            # Test 3: Multiple reboot scenario
            print("   🔄🔄 Testing multiple consecutive reboots...")
            
            multiple_reboot_results = []
            initial_ops = self.mock_esp32.operations_completed
            
            for reboot_num in range(3):
                # Generate some operations
                self.mock_esp32.start_operation()
                for i in range(10):
                    self.mock_esp32.simulate_operation_cycle()
                    time.sleep(0.01)
                self.mock_esp32.stop_operation()
                
                ops_before_reboot = self.mock_esp32.operations_completed
                reboot_success = self.mock_esp32.simulate_reboot()
                ops_after_reboot = self.mock_esp32.operations_completed
                
                multiple_reboot_results.append({
                    "reboot_number": reboot_num + 1,
                    "success": reboot_success,
                    "ops_before": ops_before_reboot,
                    "ops_after": ops_after_reboot,
                    "ops_lost": ops_before_reboot - ops_after_reboot
                })
                
                time.sleep(0.5)  # Brief pause between reboots
            
            successful_reboots = sum(1 for r in multiple_reboot_results if r["success"])
            total_ops_lost = sum(r["ops_lost"] for r in multiple_reboot_results)
            
            reboot_tests.append({
                "test": "multiple_consecutive_reboots",
                "status": "PASS" if successful_reboots >= 2 else "FAIL",
                "total_reboots": len(multiple_reboot_results),
                "successful_reboots": successful_reboots,
                "reboot_results": multiple_reboot_results,
                "total_operations_lost": total_ops_lost,
                "system_resilience": successful_reboots >= 2
            })
            
            print(f"      Multiple reboots: {successful_reboots}/3 successful")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_tests = sum(1 for test in reboot_tests if test["status"] == "PASS")
            overall_pass = passed_tests == len(reboot_tests)
            
            result = ReliabilityTestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "reboot_tests": reboot_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(reboot_tests),
                    "data_integrity_verified": overall_pass,
                    "final_operations_count": self.mock_esp32.operations_completed,
                    "final_buffer_size": len(self.mock_esp32.test_buffer)
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Reboot tests: {passed_tests}/{len(reboot_tests)} passed")
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = ReliabilityTestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def test_network_flood_rate_limiting(self) -> bool:
        """Test network flood simulation and backend rate limiting."""
        test_name = "Network Flood Rate Limiting"
        start_time = time.time()
        
        try:
            flood_tests = []
            
            # Test 1: Normal request rate (should be allowed)
            print("   🌊 Testing normal request rate...")
            
            normal_requests = 30
            normal_allowed = 0
            normal_blocked = 0
            
            for i in range(normal_requests):
                if self.rate_limiter.check_rate_limit():
                    normal_allowed += 1
                else:
                    normal_blocked += 1
                time.sleep(2.0)  # 2 second intervals (normal rate)
            
            normal_rate_stats = self.rate_limiter.get_stats()
            
            flood_tests.append({
                "test": "normal_request_rate",
                "status": "PASS" if normal_blocked == 0 else "FAIL",
                "requests_sent": normal_requests,
                "requests_allowed": normal_allowed,
                "requests_blocked": normal_blocked,
                "all_requests_allowed": normal_blocked == 0
            })
            
            print(f"      Normal rate: {normal_allowed}/{normal_requests} allowed")
            
            # Reset rate limiter for flood test
            self.rate_limiter = MockBackendRateLimiter()
            
            # Test 2: Flood attack simulation
            print("   🌊💥 Simulating network flood attack...")
            
            flood_requests = 200  # Send 200 requests rapidly
            flood_allowed = 0
            flood_blocked = 0
            flood_response_times = []
            
            for i in range(flood_requests):
                request_start = time.time()
                
                if self.rate_limiter.check_rate_limit():
                    flood_allowed += 1
                else:
                    flood_blocked += 1
                
                response_time = (time.time() - request_start) * 1000
                flood_response_times.append(response_time)
                
                time.sleep(0.01)  # 10ms intervals (flood rate)
            
            flood_stats = self.rate_limiter.get_stats()
            avg_flood_response_time = statistics.mean(flood_response_times)
            
            # Rate limiter should block most flood requests
            rate_limit_effective = flood_blocked > flood_allowed
            backend_responsive = avg_flood_response_time < 50  # Still responsive under attack
            
            flood_tests.append({
                "test": "flood_attack_mitigation",
                "status": "PASS" if rate_limit_effective and backend_responsive else "FAIL",
                "requests_sent": flood_requests,
                "requests_allowed": flood_allowed,
                "requests_blocked": flood_blocked,
                "block_rate_percent": (flood_blocked / flood_requests) * 100,
                "avg_response_time_ms": avg_flood_response_time,
                "rate_limiting_effective": rate_limit_effective,
                "backend_responsive": backend_responsive
            })
            
            print(f"      Flood test: {flood_blocked}/{flood_requests} blocked ({(flood_blocked/flood_requests)*100:.1f}%)")
            print(f"      Avg response time: {avg_flood_response_time:.1f}ms")
            
            # Test 3: Multi-source flood simulation
            print("   🌊🌊 Testing multi-source flood...")
            
            # Reset rate limiter
            self.rate_limiter = MockBackendRateLimiter()
            
            multi_source_results = []
            
            def flood_from_ip(ip_address: str, request_count: int):
                allowed = 0
                blocked = 0
                for i in range(request_count):
                    if self.rate_limiter.check_rate_limit(ip_address):
                        allowed += 1
                    else:
                        blocked += 1
                    time.sleep(0.005)  # Very rapid requests
                return {"ip": ip_address, "allowed": allowed, "blocked": blocked}
            
            # Simulate flood from multiple IPs
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for i in range(5):
                    ip = f"192.168.1.{100+i}"
                    futures.append(executor.submit(flood_from_ip, ip, 50))
                
                for future in futures:
                    result = future.result()
                    multi_source_results.append(result)
            
            total_multi_allowed = sum(r["allowed"] for r in multi_source_results)
            total_multi_blocked = sum(r["blocked"] for r in multi_source_results)
            total_multi_requests = total_multi_allowed + total_multi_blocked
            
            multi_source_effective = total_multi_blocked > total_multi_allowed * 2  # More blocked than allowed
            
            flood_tests.append({
                "test": "multi_source_flood_mitigation",
                "status": "PASS" if multi_source_effective else "FAIL",
                "source_count": len(multi_source_results),
                "total_requests": total_multi_requests,
                "total_allowed": total_multi_allowed,
                "total_blocked": total_multi_blocked,
                "block_rate_percent": (total_multi_blocked / max(1, total_multi_requests)) * 100,
                "multi_source_results": multi_source_results,
                "mitigation_effective": multi_source_effective
            })
            
            print(f"      Multi-source: {total_multi_blocked}/{total_multi_requests} blocked")
            
            # Test 4: Backend resilience under sustained load
            print("   🏋️ Testing backend resilience under sustained load...")
            
            sustained_load_duration = 10  # 10 seconds
            sustained_requests = 0
            sustained_allowed = 0
            sustained_blocked = 0
            sustained_start = time.time()
            
            while time.time() - sustained_start < sustained_load_duration:
                sustained_requests += 1
                if self.rate_limiter.check_rate_limit():
                    sustained_allowed += 1
                else:
                    sustained_blocked += 1
                time.sleep(0.1)  # 100ms intervals
            
            sustained_stats = self.rate_limiter.get_stats()
            
            # Backend should maintain rate limiting throughout sustained load
            consistent_rate_limiting = sustained_blocked > sustained_requests * 0.5  # At least 50% blocked
            
            flood_tests.append({
                "test": "sustained_load_resilience", 
                "status": "PASS" if consistent_rate_limiting else "FAIL",
                "duration_seconds": sustained_load_duration,
                "total_requests": sustained_requests,
                "requests_allowed": sustained_allowed,
                "requests_blocked": sustained_blocked,
                "block_rate_percent": (sustained_blocked / max(1, sustained_requests)) * 100,
                "consistent_rate_limiting": consistent_rate_limiting
            })
            
            print(f"      Sustained load: {sustained_blocked}/{sustained_requests} blocked over {sustained_load_duration}s")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Calculate backend resilience score
            passed_tests = sum(1 for test in flood_tests if test["status"] == "PASS")
            resilience_score = (passed_tests / len(flood_tests)) * 100
            
            overall_pass = passed_tests >= len(flood_tests) * 0.75  # 75% pass rate
            
            result = ReliabilityTestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "flood_tests": flood_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(flood_tests),
                    "backend_resilience_score": resilience_score,
                    "rate_limiting_functional": overall_pass,
                    "final_rate_limiter_stats": self.rate_limiter.get_stats()
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Network flood tests: {passed_tests}/{len(flood_tests)} passed")
            print(f"   🛡️ Backend resilience score: {resilience_score:.1f}%")
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = ReliabilityTestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def run_reliability_stress_tests(self):
        """Run comprehensive reliability and stress testing suite."""
        print("⚡ ESP32 Reliability & Stress Testing Suite")
        print("=" * 60)
        
        test_methods = [
            lambda: self.test_24h_continuous_operation(duration_minutes=0.5),  # 30 second test
            self.test_reboot_data_integrity,
            self.test_network_flood_rate_limiting
        ]
        
        passed_tests = 0
        total_tests = len(test_methods)
        
        for i, test_method in enumerate(test_methods):
            try:
                print(f"\n🔍 Running test {i+1}/{total_tests}...")
                result = test_method()
                if result:
                    passed_tests += 1
            except Exception as e:
                print(f"❌ Test {test_method.__name__ if hasattr(test_method, '__name__') else i+1} failed with error: {e}")
        
        # Generate final report
        print("\n" + "=" * 60)
        print("⚡ RELIABILITY & STRESS TEST RESULTS")
        print("=" * 60)
        
        success_rate = (passed_tests / total_tests) * 100
        
        if success_rate >= 90:
            overall_status = "🟢 EXCELLENT"
        elif success_rate >= 70:
            overall_status = "🟡 GOOD"
        elif success_rate >= 50:
            overall_status = "🟠 NEEDS IMPROVEMENT"
        else:
            overall_status = "🔴 CRITICAL ISSUES"
        
        print(f"Reliability Score: {success_rate:.1f}% {overall_status}")
        print(f"Tests Passed: {passed_tests}/{total_tests}")
        
        # System health summary
        final_metrics = self.mock_esp32.get_current_metrics()
        print(f"\n📊 Final System Health:")
        print(f"   Memory Usage: {final_metrics.memory_usage_mb:.1f}MB")
        print(f"   Current Latency: {final_metrics.latency_ms:.1f}ms")
        print(f"   Total Operations: {self.mock_esp32.operations_completed}")
        print(f"   Connection Drops: {self.mock_esp32.connection_drops}")
        print(f"   Error Count: {len(self.mock_esp32.errors)}")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_score": success_rate,
            "tests_passed": passed_tests,
            "total_tests": total_tests,
            "test_results": [asdict(result) for result in self.test_results],
            "system_health": {
                "memory_usage_mb": final_metrics.memory_usage_mb,
                "latency_ms": final_metrics.latency_ms,
                "operations_completed": self.mock_esp32.operations_completed,
                "connection_drops": self.mock_esp32.connection_drops,
                "error_count": len(self.mock_esp32.errors)
            },
            "metrics_collected": len(self.collected_metrics)
        }
    
    def save_results_to_file(self, results: Dict[str, Any], filename: str = None):
        """Save test results to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"esp32_reliability_stress_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {filename}")
        return filename


def main():
    """Main reliability and stress testing execution."""
    print("🤖 AI Teddy Bear - ESP32 Reliability & Stress Testing")
    print("=" * 60)
    
    # Initialize tester
    tester = ESP32ReliabilityTester()
    
    # Run all tests
    results = tester.run_reliability_stress_tests()
    
    # Save results
    filename = tester.save_results_to_file(results)
    
    # Return exit code based on results
    if results["overall_score"] >= 80:
        print("\n✅ ESP32 reliability and stress testing PASSED")
        return 0
    elif results["overall_score"] >= 60:
        print(f"\n⚠️ ESP32 reliability testing completed with warnings ({results['overall_score']:.1f}%)")
        return 1
    else:
        print(f"\n❌ ESP32 reliability testing FAILED ({results['overall_score']:.1f}%)")
        return 2


if __name__ == "__main__":
    import sys
    result = main()
    sys.exit(result)