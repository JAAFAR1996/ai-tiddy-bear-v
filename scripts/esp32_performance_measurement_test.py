#!/usr/bin/env python3
"""
ESP32 Performance Measurement Testing Suite
===========================================
Comprehensive testing of roundtrip latency, weak WiFi performance,
random disconnects, and full event logging systems.
"""

import asyncio
import json
import time
import threading
import random
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import tempfile
import os
import logging
from concurrent.futures import ThreadPoolExecutor
import queue


@dataclass
class PerformanceTestResult:
    """Result of performance test."""
    test_name: str
    status: str  # PASS, FAIL, ERROR
    details: Dict[str, Any]
    timestamp: str
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class LatencyMeasurement:
    """Latency measurement data."""
    timestamp: str
    request_type: str
    roundtrip_ms: float
    network_latency_ms: float
    processing_latency_ms: float
    packet_loss: bool
    signal_strength_dbm: int


@dataclass
class NetworkCondition:
    """Network condition simulation."""
    signal_strength_dbm: int
    packet_loss_rate: float
    disconnect_probability: float
    bandwidth_kbps: int
    jitter_ms: float


class MockESP32PerformanceDevice:
    """Mock ESP32 device for performance testing."""
    
    def __init__(self, device_id: str = "ESP32_PERF_TEST"):
        self.device_id = device_id
        self.is_connected = True
        self.network_condition = NetworkCondition(
            signal_strength_dbm=-45,  # Strong signal
            packet_loss_rate=0.01,   # 1% loss
            disconnect_probability=0.001,  # 0.1% chance
            bandwidth_kbps=1000,     # 1Mbps
            jitter_ms=5.0            # 5ms jitter
        )
        
        self.latency_measurements = []
        self.connection_events = []
        self.performance_stats = {
            "packets_sent": 0,
            "packets_received": 0,
            "packets_lost": 0,
            "total_latency_ms": 0.0,
            "disconnections": 0,
            "reconnections": 0
        }
        
    def set_network_condition(self, condition: NetworkCondition):
        """Set network conditions for testing."""
        self.network_condition = condition
        print(f"📶 Network condition: {condition.signal_strength_dbm}dBm, "
              f"{condition.packet_loss_rate*100:.1f}% loss, "
              f"{condition.bandwidth_kbps}kbps")
    
    def simulate_control_request(self, command: str) -> Optional[LatencyMeasurement]:
        """Simulate control command with latency measurement."""
        start_time = time.time()
        
        # Simulate network instability
        if random.random() < self.network_condition.disconnect_probability:
            self._simulate_disconnect()
            return None
        
        # Simulate packet loss
        if random.random() < self.network_condition.packet_loss_rate:
            self.performance_stats["packets_lost"] += 1
            return None
        
        self.performance_stats["packets_sent"] += 1
        
        # Calculate latencies
        base_network_latency = 15.0  # Base 15ms
        signal_penalty = max(0, (-50 - self.network_condition.signal_strength_dbm) * 2)
        bandwidth_penalty = max(0, (1000 - self.network_condition.bandwidth_kbps) / 100)
        jitter = random.uniform(-self.network_condition.jitter_ms, self.network_condition.jitter_ms)
        
        network_latency = base_network_latency + signal_penalty + bandwidth_penalty + jitter
        
        # Processing latency varies by command type
        processing_latencies = {
            "led_control": 5.0,
            "motor_control": 12.0,
            "audio_play": 25.0,
            "sensor_read": 8.0,
            "status_check": 3.0
        }
        
        processing_latency = processing_latencies.get(command, 10.0)
        
        # Add some randomness
        processing_latency += random.uniform(-2.0, 3.0)
        
        total_latency = network_latency + processing_latency
        
        # Simulate actual delay
        time.sleep(total_latency / 1000.0)  # Convert to seconds
        
        measurement = LatencyMeasurement(
            timestamp=datetime.now().isoformat(),
            request_type=command,
            roundtrip_ms=total_latency,
            network_latency_ms=network_latency,
            processing_latency_ms=processing_latency,
            packet_loss=False,
            signal_strength_dbm=self.network_condition.signal_strength_dbm
        )
        
        self.latency_measurements.append(measurement)
        self.performance_stats["packets_received"] += 1
        self.performance_stats["total_latency_ms"] += total_latency
        
        return measurement
    
    def simulate_data_transfer(self, data_size_kb: int) -> Optional[LatencyMeasurement]:
        """Simulate data transfer with latency measurement."""
        start_time = time.time()
        
        # Check connection
        if not self.is_connected:
            return None
        
        # Simulate network instability during data transfer
        if random.random() < self.network_condition.disconnect_probability * 2:  # Higher chance during data transfer
            self._simulate_disconnect()
            return None
        
        self.performance_stats["packets_sent"] += 1
        
        # Calculate transfer time based on bandwidth
        transfer_time_ms = (data_size_kb * 8) / (self.network_condition.bandwidth_kbps / 1000)  # Convert to ms
        
        # Add network latency
        base_latency = 20.0  # Base latency for data transfers
        signal_penalty = max(0, (-50 - self.network_condition.signal_strength_dbm) * 3)
        
        network_latency = base_latency + signal_penalty
        processing_latency = 5.0 + (data_size_kb * 0.1)  # Processing scales with size
        
        total_latency = network_latency + processing_latency + transfer_time_ms
        
        # Simulate transfer delay
        time.sleep(total_latency / 1000.0)
        
        measurement = LatencyMeasurement(
            timestamp=datetime.now().isoformat(),
            request_type=f"data_transfer_{data_size_kb}kb",
            roundtrip_ms=total_latency,
            network_latency_ms=network_latency,
            processing_latency_ms=processing_latency + transfer_time_ms,
            packet_loss=False,
            signal_strength_dbm=self.network_condition.signal_strength_dbm
        )
        
        self.latency_measurements.append(measurement)
        self.performance_stats["packets_received"] += 1
        self.performance_stats["total_latency_ms"] += total_latency
        
        return measurement
    
    def _simulate_disconnect(self):
        """Simulate network disconnection."""
        if self.is_connected:
            self.is_connected = False
            self.performance_stats["disconnections"] += 1
            
            disconnect_event = {
                "timestamp": datetime.now().isoformat(),
                "type": "disconnect",
                "reason": "network_instability",
                "signal_strength": self.network_condition.signal_strength_dbm
            }
            self.connection_events.append(disconnect_event)
            
            print(f"📡❌ Disconnected: {self.device_id}")
            
            # Schedule reconnection
            def reconnect():
                reconnect_delay = random.uniform(1.0, 5.0)  # 1-5 seconds
                time.sleep(reconnect_delay)
                
                self.is_connected = True
                self.performance_stats["reconnections"] += 1
                
                reconnect_event = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "reconnect",
                    "delay_seconds": reconnect_delay,
                    "signal_strength": self.network_condition.signal_strength_dbm
                }
                self.connection_events.append(reconnect_event)
                
                print(f"📡✅ Reconnected: {self.device_id} (after {reconnect_delay:.1f}s)")
            
            threading.Thread(target=reconnect, daemon=True).start()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance statistics summary."""
        if not self.latency_measurements:
            return {"error": "No measurements available"}
        
        latencies = [m.roundtrip_ms for m in self.latency_measurements]
        network_latencies = [m.network_latency_ms for m in self.latency_measurements]
        processing_latencies = [m.processing_latency_ms for m in self.latency_measurements]
        
        return {
            "total_measurements": len(self.latency_measurements),
            "latency_stats": {
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "avg_ms": statistics.mean(latencies),
                "median_ms": statistics.median(latencies),
                "std_dev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0
            },
            "network_latency": {
                "avg_ms": statistics.mean(network_latencies),
                "max_ms": max(network_latencies)
            },
            "processing_latency": {
                "avg_ms": statistics.mean(processing_latencies),
                "max_ms": max(processing_latencies)
            },
            "packet_stats": self.performance_stats.copy(),
            "connection_events": len(self.connection_events),
            "packet_loss_rate": (self.performance_stats["packets_lost"] / 
                               max(1, self.performance_stats["packets_sent"])) * 100
        }


class EventLogger:
    """Comprehensive event logging system."""
    
    def __init__(self, device_side: bool = True, backend_side: bool = True):
        self.device_side = device_side
        self.backend_side = backend_side
        self.events = []
        
        # Setup logging
        self.logger = logging.getLogger(f"ESP32_EventLogger_{'Device' if device_side else 'Backend'}")
        self.logger.setLevel(logging.DEBUG)
        
        # Create handler if not exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_event(self, event_type: str, details: Dict[str, Any], level: str = "INFO"):
        """Log an event with details."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details,
            "level": level,
            "source": "device" if self.device_side else "backend"
        }
        
        self.events.append(event)
        
        # Log to console
        log_message = f"[{event['source'].upper()}] {event_type}: {details}"
        
        if level == "DEBUG":
            self.logger.debug(log_message)
        elif level == "INFO":
            self.logger.info(log_message)
        elif level == "WARNING":
            self.logger.warning(log_message)
        elif level == "ERROR":
            self.logger.error(log_message)
        elif level == "CRITICAL":
            self.logger.critical(log_message)
    
    def get_events(self, event_type: str = None, level: str = None) -> List[Dict[str, Any]]:
        """Get filtered events."""
        filtered_events = self.events
        
        if event_type:
            filtered_events = [e for e in filtered_events if e["event_type"] == event_type]
        
        if level:
            filtered_events = [e for e in filtered_events if e["level"] == level]
        
        return filtered_events
    
    def get_event_summary(self) -> Dict[str, Any]:
        """Get summary of logged events."""
        if not self.events:
            return {"total_events": 0}
        
        event_types = {}
        levels = {}
        
        for event in self.events:
            event_type = event["event_type"]
            level = event["level"]
            
            event_types[event_type] = event_types.get(event_type, 0) + 1
            levels[level] = levels.get(level, 0) + 1
        
        return {
            "total_events": len(self.events),
            "event_types": event_types,
            "levels": levels,
            "first_event": self.events[0]["timestamp"],
            "last_event": self.events[-1]["timestamp"]
        }


class ESP32PerformanceTester:
    """Comprehensive ESP32 performance testing."""
    
    def __init__(self):
        self.mock_esp32 = MockESP32PerformanceDevice()
        self.device_logger = EventLogger(device_side=True)
        self.backend_logger = EventLogger(device_side=False)
        self.test_results = []
        
    def log_test_result(self, result: PerformanceTestResult):
        """Log test result."""
        self.test_results.append(result)
        status_emoji = "✅" if result.status == "PASS" else "❌" if result.status == "FAIL" else "⚠️"
        duration_str = f" ({result.duration_ms:.1f}ms)" if result.duration_ms else ""
        print(f"{status_emoji} {result.test_name}{duration_str}")
        if result.error_message:
            print(f"   Error: {result.error_message}")
    
    def test_roundtrip_latency_measurement(self) -> bool:
        """Test roundtrip latency for control and data operations."""
        test_name = "Roundtrip Latency Measurement"
        start_time = time.time()
        
        try:
            self.device_logger.log_event("test_started", {"test": test_name})
            self.backend_logger.log_event("test_started", {"test": test_name})
            
            latency_tests = []
            
            # Test 1: Control command latency
            print("   ⚡ Testing control command latency...")
            
            control_commands = ["led_control", "motor_control", "sensor_read", "status_check"]
            control_measurements = []
            
            for cmd in control_commands:
                for i in range(10):  # 10 measurements per command
                    self.device_logger.log_event("control_request", {"command": cmd, "attempt": i+1})
                    
                    measurement = self.mock_esp32.simulate_control_request(cmd)
                    if measurement:
                        control_measurements.append(measurement)
                        
                        self.backend_logger.log_event("control_response", {
                            "command": cmd,
                            "latency_ms": measurement.roundtrip_ms,
                            "network_ms": measurement.network_latency_ms,
                            "processing_ms": measurement.processing_latency_ms
                        })
                    
                    time.sleep(0.1)  # Small delay between commands
            
            if control_measurements:
                control_latencies = [m.roundtrip_ms for m in control_measurements]
                avg_control_latency = statistics.mean(control_latencies)
                max_control_latency = max(control_latencies)
                
                # Control commands should be under 100ms
                control_performance_good = avg_control_latency < 100.0
                
                latency_tests.append({
                    "test": "control_command_latency",
                    "status": "PASS" if control_performance_good else "FAIL",
                    "measurements": len(control_measurements),
                    "avg_latency_ms": avg_control_latency,
                    "max_latency_ms": max_control_latency,
                    "performance_threshold_met": control_performance_good,
                    "command_breakdown": {
                        cmd: {
                            "avg_ms": statistics.mean([m.roundtrip_ms for m in control_measurements if m.request_type == cmd]),
                            "count": len([m for m in control_measurements if m.request_type == cmd])
                        } for cmd in control_commands
                    }
                })
                
                print(f"      Control latency: {avg_control_latency:.1f}ms avg, {max_control_latency:.1f}ms max")
            else:
                latency_tests.append({
                    "test": "control_command_latency",
                    "status": "FAIL",
                    "error": "No successful control measurements"
                })
            
            # Test 2: Data transfer latency
            print("   📊 Testing data transfer latency...")
            
            data_sizes = [1, 5, 10, 25, 50]  # KB
            data_measurements = []
            
            for size_kb in data_sizes:
                for i in range(5):  # 5 measurements per size
                    self.device_logger.log_event("data_transfer", {"size_kb": size_kb, "attempt": i+1})
                    
                    measurement = self.mock_esp32.simulate_data_transfer(size_kb)
                    if measurement:
                        data_measurements.append(measurement)
                        
                        self.backend_logger.log_event("data_received", {
                            "size_kb": size_kb,
                            "latency_ms": measurement.roundtrip_ms,
                            "transfer_time_ms": measurement.processing_latency_ms
                        })
                    
                    time.sleep(0.2)  # Delay between transfers
            
            if data_measurements:
                data_latencies = [m.roundtrip_ms for m in data_measurements]
                avg_data_latency = statistics.mean(data_latencies)
                max_data_latency = max(data_latencies)
                
                # Data transfers should complete reasonably quickly
                data_performance_good = avg_data_latency < 500.0  # 500ms threshold
                
                latency_tests.append({
                    "test": "data_transfer_latency",
                    "status": "PASS" if data_performance_good else "FAIL",
                    "measurements": len(data_measurements),
                    "avg_latency_ms": avg_data_latency,
                    "max_latency_ms": max_data_latency,
                    "performance_threshold_met": data_performance_good,
                    "size_breakdown": {
                        f"{size}kb": {
                            "avg_ms": statistics.mean([m.roundtrip_ms for m in data_measurements if f"{size}" in m.request_type]),
                            "count": len([m for m in data_measurements if f"{size}" in m.request_type])
                        } for size in data_sizes
                    }
                })
                
                print(f"      Data latency: {avg_data_latency:.1f}ms avg, {max_data_latency:.1f}ms max")
            else:
                latency_tests.append({
                    "test": "data_transfer_latency",
                    "status": "FAIL",
                    "error": "No successful data transfer measurements"
                })
            
            # Test 3: Latency consistency under load
            print("   🔄 Testing latency consistency under load...")
            
            load_measurements = []
            
            # Simulate concurrent requests
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                
                for i in range(50):  # 50 concurrent requests
                    cmd = random.choice(control_commands)
                    future = executor.submit(self.mock_esp32.simulate_control_request, cmd)
                    futures.append(future)
                
                for future in futures:
                    measurement = future.result()
                    if measurement:
                        load_measurements.append(measurement)
            
            if load_measurements:
                load_latencies = [m.roundtrip_ms for m in load_measurements]
                avg_load_latency = statistics.mean(load_latencies)
                std_dev_load = statistics.stdev(load_latencies) if len(load_latencies) > 1 else 0
                
                # Consistency check - standard deviation should be reasonable
                latency_consistent = std_dev_load < 50.0  # Less than 50ms std deviation
                
                latency_tests.append({
                    "test": "latency_consistency_under_load",
                    "status": "PASS" if latency_consistent else "FAIL",
                    "concurrent_measurements": len(load_measurements),
                    "avg_latency_ms": avg_load_latency,
                    "std_deviation_ms": std_dev_load,
                    "consistency_good": latency_consistent
                })
                
                print(f"      Load latency: {avg_load_latency:.1f}ms avg, {std_dev_load:.1f}ms std dev")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_tests = sum(1 for test in latency_tests if test.get("status") == "PASS")
            overall_pass = passed_tests >= len(latency_tests) * 0.7  # 70% pass rate
            
            # Get performance summary
            perf_summary = self.mock_esp32.get_performance_summary()
            
            result = PerformanceTestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "latency_tests": latency_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(latency_tests),
                    "performance_summary": perf_summary,
                    "total_measurements": len(self.mock_esp32.latency_measurements)
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Latency tests: {passed_tests}/{len(latency_tests)} passed")
            print(f"   🎯 Total measurements: {len(self.mock_esp32.latency_measurements)}")
            
            self.device_logger.log_event("test_completed", {"test": test_name, "status": result.status})
            self.backend_logger.log_event("test_completed", {"test": test_name, "status": result.status})
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            self.device_logger.log_event("test_error", {"test": test_name, "error": str(e)}, "ERROR")
            
            result = PerformanceTestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def test_weak_wifi_random_disconnects(self) -> bool:
        """Test performance under weak WiFi and random disconnects."""
        test_name = "Weak WiFi and Random Disconnects"
        start_time = time.time()
        
        try:
            self.device_logger.log_event("weak_wifi_test_started", {"test": test_name})
            
            wifi_tests = []
            
            # Test different WiFi conditions
            test_conditions = [
                NetworkCondition(-55, 0.02, 0.005, 800, 10.0),    # Moderate
                NetworkCondition(-70, 0.05, 0.01, 500, 20.0),     # Weak
                NetworkCondition(-80, 0.15, 0.03, 200, 50.0),     # Very weak
                NetworkCondition(-90, 0.30, 0.10, 100, 100.0)     # Poor
            ]
            
            condition_names = ["moderate", "weak", "very_weak", "poor"]
            
            for i, (condition, name) in enumerate(zip(test_conditions, condition_names)):
                print(f"   📶 Testing {name} WiFi conditions...")
                
                # Set network condition
                self.mock_esp32.set_network_condition(condition)
                
                self.device_logger.log_event("network_condition_changed", {
                    "condition": name,
                    "signal_dbm": condition.signal_strength_dbm,
                    "packet_loss": condition.packet_loss_rate,
                    "bandwidth": condition.bandwidth_kbps
                })
                
                # Reset measurements for this condition
                condition_measurements = []
                condition_start = time.time()
                
                # Test for 15 seconds under this condition
                while time.time() - condition_start < 15.0:
                    cmd = random.choice(["led_control", "sensor_read", "status_check"])
                    measurement = self.mock_esp32.simulate_control_request(cmd)
                    
                    if measurement:
                        condition_measurements.append(measurement)
                        
                        self.device_logger.log_event("measurement", {
                            "condition": name,
                            "command": cmd,
                            "latency_ms": measurement.roundtrip_ms,
                            "signal_dbm": measurement.signal_strength_dbm
                        })
                    else:
                        self.device_logger.log_event("measurement_failed", {
                            "condition": name,
                            "command": cmd,
                            "reason": "packet_loss_or_disconnect"
                        }, "WARNING")
                    
                    time.sleep(0.5)  # 500ms between requests
                
                # Analyze results for this condition
                if condition_measurements:
                    latencies = [m.roundtrip_ms for m in condition_measurements]
                    avg_latency = statistics.mean(latencies)
                    success_rate = len(condition_measurements) / 30  # Expected ~30 requests in 15s
                    
                    # Define acceptable thresholds based on condition
                    thresholds = {
                        "moderate": {"latency": 80.0, "success": 0.95},
                        "weak": {"latency": 150.0, "success": 0.80},
                        "very_weak": {"latency": 300.0, "success": 0.60},
                        "poor": {"latency": 500.0, "success": 0.40}
                    }
                    
                    threshold = thresholds[name]
                    latency_acceptable = avg_latency <= threshold["latency"]
                    success_acceptable = success_rate >= threshold["success"]
                    
                    condition_pass = latency_acceptable and success_acceptable
                    
                    wifi_tests.append({
                        "condition": name,
                        "status": "PASS" if condition_pass else "FAIL",
                        "measurements": len(condition_measurements),
                        "avg_latency_ms": avg_latency,
                        "success_rate": success_rate,
                        "latency_threshold": threshold["latency"],
                        "success_threshold": threshold["success"],
                        "latency_acceptable": latency_acceptable,
                        "success_acceptable": success_acceptable,
                        "signal_strength_dbm": condition.signal_strength_dbm,
                        "packet_loss_rate": condition.packet_loss_rate
                    })
                    
                    print(f"      {name}: {avg_latency:.1f}ms avg, {success_rate*100:.1f}% success")
                else:
                    wifi_tests.append({
                        "condition": name,
                        "status": "FAIL",
                        "error": "No successful measurements under this condition"
                    })
                
                # Brief pause between conditions
                time.sleep(2.0)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_conditions = sum(1 for test in wifi_tests if test.get("status") == "PASS")
            overall_pass = passed_conditions >= 2  # At least 2 conditions should pass
            
            # Get connection events summary
            connection_events = self.mock_esp32.connection_events
            disconnections = len([e for e in connection_events if e["type"] == "disconnect"])
            reconnections = len([e for e in connection_events if e["type"] == "reconnect"])
            
            result = PerformanceTestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "wifi_condition_tests": wifi_tests,
                    "passed_conditions": passed_conditions,
                    "total_conditions": len(wifi_tests),
                    "connection_stability": {
                        "disconnections": disconnections,
                        "reconnections": reconnections,
                        "total_events": len(connection_events)
                    },
                    "overall_performance": self.mock_esp32.get_performance_summary(),
                    "wifi_resilience": overall_pass
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 WiFi conditions: {passed_conditions}/{len(wifi_tests)} passed")
            print(f"   📡 Connection events: {disconnections} disconnects, {reconnections} reconnects")
            
            self.device_logger.log_event("weak_wifi_test_completed", {
                "status": result.status,
                "conditions_passed": passed_conditions,
                "disconnections": disconnections
            })
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = PerformanceTestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def test_full_event_logging(self) -> bool:
        """Test comprehensive event logging on both device and backend sides."""
        test_name = "Full Event Logging System"
        start_time = time.time()
        
        try:
            print("   📝 Testing comprehensive event logging...")
            
            logging_tests = []
            
            # Test 1: Device-side event logging
            print("   📱 Testing device-side event logging...")
            
            device_events_before = len(self.device_logger.events)
            
            # Generate various device events
            test_events = [
                ("device_startup", {"device_id": "ESP32_TEST", "firmware_version": "1.0.0"}),
                ("wifi_connected", {"ssid": "TestNetwork", "signal_strength": -45}),
                ("sensor_reading", {"temperature": 23.5, "humidity": 60.0}),
                ("audio_recording_started", {"duration_s": 5, "sample_rate": 16000}),
                ("audio_playback_completed", {"file": "response.wav", "duration_ms": 2500}),
                ("error_occurred", {"error_code": "E001", "message": "Sensor timeout"}, "ERROR"),
                ("wifi_disconnected", {"reason": "signal_lost", "duration_s": 120}, "WARNING")
            ]
            
            for event_type, details, *level in test_events:
                log_level = level[0] if level else "INFO"
                self.device_logger.log_event(event_type, details, log_level)
            
            device_events_after = len(self.device_logger.events)
            device_events_logged = device_events_after - device_events_before
            
            device_logging_working = device_events_logged == len(test_events)
            
            logging_tests.append({
                "test": "device_side_logging",
                "status": "PASS" if device_logging_working else "FAIL",
                "events_generated": len(test_events),
                "events_logged": device_events_logged,
                "logging_working": device_logging_working
            })
            
            print(f"      Device events: {device_events_logged}/{len(test_events)} logged")
            
            # Test 2: Backend-side event logging
            print("   🖥️ Testing backend-side event logging...")
            
            backend_events_before = len(self.backend_logger.events)
            
            # Generate backend events
            backend_test_events = [
                ("client_connected", {"device_id": "ESP32_TEST", "ip_address": "192.168.1.100"}),
                ("request_received", {"endpoint": "/api/process-audio", "method": "POST"}),
                ("ai_processing_started", {"model": "gpt-4", "tokens": 50}),
                ("ai_response_generated", {"response_time_ms": 1200, "tokens_used": 45}),
                ("tts_generation_completed", {"text_length": 150, "audio_duration_ms": 3500}),
                ("response_sent", {"device_id": "ESP32_TEST", "payload_size_bytes": 2048}),
                ("rate_limit_exceeded", {"client_ip": "192.168.1.200", "requests_per_minute": 120}, "WARNING"),
                ("security_violation", {"device_id": "UNKNOWN", "reason": "invalid_token"}, "ERROR")
            ]
            
            for event_type, details, *level in backend_test_events:
                log_level = level[0] if level else "INFO"
                self.backend_logger.log_event(event_type, details, log_level)
            
            backend_events_after = len(self.backend_logger.events)
            backend_events_logged = backend_events_after - backend_events_before
            
            backend_logging_working = backend_events_logged == len(backend_test_events)
            
            logging_tests.append({
                "test": "backend_side_logging",
                "status": "PASS" if backend_logging_working else "FAIL",
                "events_generated": len(backend_test_events),
                "events_logged": backend_events_logged,
                "logging_working": backend_logging_working
            })
            
            print(f"      Backend events: {backend_events_logged}/{len(backend_test_events)} logged")
            
            # Test 3: Event filtering and querying
            print("   🔍 Testing event filtering and querying...")
            
            # Test filtering by event type
            error_events = self.device_logger.get_events(level="ERROR")
            warning_events = self.backend_logger.get_events(level="WARNING")
            
            # Test filtering by specific event types
            wifi_events = self.device_logger.get_events(event_type="wifi_connected")
            security_events = self.backend_logger.get_events(event_type="security_violation")
            
            filtering_working = (
                len(error_events) > 0 and
                len(warning_events) > 0 and
                len(wifi_events) > 0 and
                len(security_events) > 0
            )
            
            logging_tests.append({
                "test": "event_filtering_querying",
                "status": "PASS" if filtering_working else "FAIL",
                "device_error_events": len(error_events),
                "backend_warning_events": len(warning_events),
                "wifi_events": len(wifi_events),
                "security_events": len(security_events),
                "filtering_functional": filtering_working
            })
            
            print(f"      Event filtering: {len(error_events)} errors, {len(warning_events)} warnings")
            
            # Test 4: Event aggregation and summary
            print("   📊 Testing event aggregation and summary...")
            
            device_summary = self.device_logger.get_event_summary()
            backend_summary = self.backend_logger.get_event_summary()
            
            summary_complete = (
                device_summary["total_events"] > 0 and
                backend_summary["total_events"] > 0 and
                "event_types" in device_summary and
                "levels" in backend_summary
            )
            
            logging_tests.append({
                "test": "event_aggregation_summary",
                "status": "PASS" if summary_complete else "FAIL",
                "device_summary": device_summary,
                "backend_summary": backend_summary,
                "summary_generation_working": summary_complete
            })
            
            print(f"      Summary: Device {device_summary['total_events']} events, Backend {backend_summary['total_events']} events")
            
            # Test 5: Performance under high logging load
            print("   ⚡ Testing logging performance under load...")
            
            logging_start = time.time()
            
            # Generate many log events quickly
            for i in range(100):
                self.device_logger.log_event("load_test_event", {"iteration": i, "timestamp": datetime.now().isoformat()})
                self.backend_logger.log_event("load_test_response", {"iteration": i, "processed": True})
            
            logging_duration = (time.time() - logging_start) * 1000  # ms
            
            # Logging should complete quickly (under 1 second for 200 events)
            performance_acceptable = logging_duration < 1000.0
            
            logging_tests.append({
                "test": "logging_performance_under_load",
                "status": "PASS" if performance_acceptable else "FAIL",
                "events_logged": 200,
                "duration_ms": logging_duration,
                "performance_acceptable": performance_acceptable,
                "events_per_second": 200 / (logging_duration / 1000) if logging_duration > 0 else 0
            })
            
            print(f"      Performance: 200 events in {logging_duration:.1f}ms")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_tests = sum(1 for test in logging_tests if test.get("status") == "PASS")
            overall_pass = passed_tests == len(logging_tests)  # All logging tests should pass
            
            result = PerformanceTestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "logging_tests": logging_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(logging_tests),
                    "final_device_summary": self.device_logger.get_event_summary(),
                    "final_backend_summary": self.backend_logger.get_event_summary(),
                    "comprehensive_logging_functional": overall_pass
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Logging tests: {passed_tests}/{len(logging_tests)} passed")
            
            # Log the completion of logging test (meta!)
            self.device_logger.log_event("logging_test_completed", {"status": result.status})
            self.backend_logger.log_event("logging_test_completed", {"status": result.status})
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = PerformanceTestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def run_performance_tests(self):
        """Run comprehensive performance testing suite."""
        print("⚡ ESP32 Performance Measurement Testing Suite")
        print("=" * 60)
        
        test_methods = [
            self.test_roundtrip_latency_measurement,
            self.test_weak_wifi_random_disconnects,
            self.test_full_event_logging
        ]
        
        passed_tests = 0
        total_tests = len(test_methods)
        
        for test_method in test_methods:
            try:
                result = test_method()
                if result:
                    passed_tests += 1
            except Exception as e:
                print(f"❌ Test {test_method.__name__} failed with error: {e}")
        
        # Generate final report
        print("\n" + "=" * 60)
        print("⚡ PERFORMANCE MEASUREMENT TEST RESULTS")
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
        
        print(f"Performance Score: {success_rate:.1f}% {overall_status}")
        print(f"Tests Passed: {passed_tests}/{total_tests}")
        
        # Performance metrics summary
        perf_summary = self.mock_esp32.get_performance_summary()
        if "latency_stats" in perf_summary:
            print(f"\n📊 Final Performance Metrics:")
            print(f"   Avg Latency: {perf_summary['latency_stats']['avg_ms']:.1f}ms")
            print(f"   Max Latency: {perf_summary['latency_stats']['max_ms']:.1f}ms")
            print(f"   Measurements: {perf_summary['total_measurements']}")
            print(f"   Packet Loss: {perf_summary['packet_loss_rate']:.1f}%")
        
        # Logging summary
        device_summary = self.device_logger.get_event_summary()
        backend_summary = self.backend_logger.get_event_summary()
        print(f"   Device Events: {device_summary['total_events']}")
        print(f"   Backend Events: {backend_summary['total_events']}")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_score": success_rate,
            "tests_passed": passed_tests,
            "total_tests": total_tests,
            "test_results": [asdict(result) for result in self.test_results],
            "performance_metrics": perf_summary,
            "logging_summary": {
                "device_events": device_summary,
                "backend_events": backend_summary
            }
        }
    
    def save_results_to_file(self, results: Dict[str, Any], filename: str = None):
        """Save test results to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"esp32_performance_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {filename}")
        return filename


def main():
    """Main performance testing execution."""
    print("🤖 AI Teddy Bear - ESP32 Performance Measurement Testing")
    print("=" * 60)
    
    # Initialize tester
    tester = ESP32PerformanceTester()
    
    # Run all tests
    results = tester.run_performance_tests()
    
    # Save results
    filename = tester.save_results_to_file(results)
    
    # Return exit code based on results
    if results["overall_score"] >= 80:
        print("\n✅ ESP32 performance testing PASSED")
        return 0
    elif results["overall_score"] >= 60:
        print(f"\n⚠️ ESP32 performance testing completed with warnings ({results['overall_score']:.1f}%)")
        return 1
    else:
        print(f"\n❌ ESP32 performance testing FAILED ({results['overall_score']:.1f}%)")
        return 2


if __name__ == "__main__":
    import sys
    result = main()
    sys.exit(result)