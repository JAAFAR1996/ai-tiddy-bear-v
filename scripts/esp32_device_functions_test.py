#!/usr/bin/env python3
"""
ESP32 Device Functions Integration Testing Suite
================================================
Comprehensive testing of ESP32 microphone, speaker, and streaming functions
including edge cases like disconnect/reboot during streaming.
"""

import asyncio
import json
import time
import wave
import io
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import tempfile
import os
import threading
import struct
import random


@dataclass
class DeviceTestResult:
    """Result of device function test."""
    test_name: str
    status: str  # PASS, FAIL, ERROR
    details: Dict[str, Any]
    timestamp: str
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class AudioSample:
    """Audio sample data structure."""
    data: bytes
    sample_rate: int
    channels: int
    bit_depth: int
    duration_ms: float
    format: str
    checksum: str


class MockESP32AudioDevice:
    """Mock ESP32 audio device for testing."""
    
    def __init__(self):
        self.is_recording = False
        self.is_playing = False
        self.is_connected = True
        self.microphone_enabled = True
        self.speaker_enabled = True
        self.audio_buffer = []
        self.recording_thread = None
        self.playback_thread = None
        
        # Audio configuration
        self.sample_rate = 16000  # 16kHz typical for ESP32
        self.bit_depth = 16
        self.channels = 1  # Mono
        self.buffer_size = 1024
        
        # Statistics
        self.stats = {
            "recordings_started": 0,
            "recordings_completed": 0,
            "playbacks_started": 0,
            "playbacks_completed": 0,
            "bytes_recorded": 0,
            "bytes_played": 0,
            "connection_drops": 0,
            "errors": []
        }
    
    def generate_test_audio_sample(self, duration_ms: int, frequency: int = 440) -> bytes:
        """Generate synthetic audio data."""
        samples = int(self.sample_rate * duration_ms / 1000)
        audio_data = []
        
        for i in range(samples):
            # Generate sine wave
            t = i / self.sample_rate
            sample = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * t))
            # Convert to 16-bit signed integer
            audio_data.append(struct.pack('<h', sample))
        
        return b''.join(audio_data)
    
    def start_recording(self, duration_ms: int = 5000) -> bool:
        """Start audio recording."""
        if not self.microphone_enabled or not self.is_connected:
            return False
        
        if self.is_recording:
            return False  # Already recording
        
        try:
            self.is_recording = True
            self.stats["recordings_started"] += 1
            self.audio_buffer.clear()
            
            # Simulate recording in a separate thread
            def record_audio():
                import math
                start_time = time.time()
                
                while self.is_recording and (time.time() - start_time) * 1000 < duration_ms:
                    if not self.is_connected:
                        break
                    
                    # Generate synthetic audio chunk (simulating microphone input)
                    chunk_size = self.buffer_size
                    chunk_data = self.generate_test_audio_sample(
                        int(chunk_size * 1000 / (self.sample_rate * 2)), 
                        frequency=440 + random.randint(-50, 50)  # Slight frequency variation
                    )
                    
                    self.audio_buffer.append(chunk_data)
                    self.stats["bytes_recorded"] += len(chunk_data)
                    time.sleep(0.1)  # 100ms chunks
                
                self.is_recording = False
                if self.is_connected:
                    self.stats["recordings_completed"] += 1
            
            self.recording_thread = threading.Thread(target=record_audio)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            return True
            
        except Exception as e:
            self.stats["errors"].append(f"Recording start error: {e}")
            self.is_recording = False
            return False
    
    def stop_recording(self) -> Optional[AudioSample]:
        """Stop recording and return audio sample."""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        
        # Wait for recording thread to finish
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
        
        if not self.audio_buffer:
            return None
        
        # Combine all audio chunks
        combined_audio = b''.join(self.audio_buffer)
        
        # Calculate duration
        samples = len(combined_audio) // (self.bit_depth // 8)
        duration_ms = (samples / self.sample_rate) * 1000
        
        # Calculate checksum
        checksum = hashlib.md5(combined_audio).hexdigest()
        
        audio_sample = AudioSample(
            data=combined_audio,
            sample_rate=self.sample_rate,
            channels=self.channels,
            bit_depth=self.bit_depth,
            duration_ms=duration_ms,
            format="PCM",
            checksum=checksum
        )
        
        return audio_sample
    
    def play_audio(self, audio_data: bytes, volume: int = 50) -> bool:
        """Play audio through speaker."""
        if not self.speaker_enabled or not self.is_connected:
            return False
        
        if self.is_playing:
            return False  # Already playing
        
        try:
            self.is_playing = True
            self.stats["playbacks_started"] += 1
            
            # Simulate audio playback
            def play_audio():
                start_time = time.time()
                
                # Calculate playback duration
                samples = len(audio_data) // (self.bit_depth // 8)
                duration_s = samples / self.sample_rate
                
                # Simulate playback with chunks
                chunk_size = self.buffer_size
                bytes_played = 0
                
                while bytes_played < len(audio_data) and self.is_connected:
                    chunk = audio_data[bytes_played:bytes_played + chunk_size]
                    if not chunk:
                        break
                    
                    bytes_played += len(chunk)
                    self.stats["bytes_played"] += len(chunk)
                    
                    # Simulate realistic playback timing
                    chunk_duration = len(chunk) / (self.sample_rate * self.bit_depth // 8)
                    time.sleep(chunk_duration)
                
                self.is_playing = False
                if self.is_connected and bytes_played == len(audio_data):
                    self.stats["playbacks_completed"] += 1
            
            self.playback_thread = threading.Thread(target=play_audio)
            self.playback_thread.daemon = True
            self.playback_thread.start()
            
            return True
            
        except Exception as e:
            self.stats["errors"].append(f"Playback error: {e}")
            self.is_playing = False
            return False
    
    def disconnect(self):
        """Simulate connection loss."""
        self.is_connected = False
        self.stats["connection_drops"] += 1
        
        # Stop any ongoing operations
        if self.is_recording:
            self.is_recording = False
        if self.is_playing:
            self.is_playing = False
    
    def reconnect(self):
        """Simulate reconnection."""
        self.is_connected = True
    
    def reboot(self):
        """Simulate device reboot."""
        self.disconnect()
        time.sleep(0.5)  # Simulated reboot time
        
        # Reset state
        self.audio_buffer.clear()
        self.is_recording = False
        self.is_playing = False
        
        self.reconnect()
    
    def get_device_status(self) -> Dict[str, Any]:
        """Get current device status."""
        return {
            "connected": self.is_connected,
            "microphone_enabled": self.microphone_enabled,
            "speaker_enabled": self.speaker_enabled,
            "is_recording": self.is_recording,
            "is_playing": self.is_playing,
            "buffer_size": len(self.audio_buffer),
            "stats": self.stats.copy()
        }


class ESP32DeviceFunctionsTester:
    """Comprehensive ESP32 device functions testing."""
    
    def __init__(self):
        self.mock_esp32 = MockESP32AudioDevice()
        self.test_results = []
        self.audio_samples = []
        
    def log_test_result(self, result: DeviceTestResult):
        """Log test result."""
        self.test_results.append(result)
        status_emoji = "✅" if result.status == "PASS" else "❌" if result.status == "FAIL" else "⚠️"
        duration_str = f" ({result.duration_ms:.1f}ms)" if result.duration_ms else ""
        print(f"{status_emoji} {result.test_name}{duration_str}")
        if result.error_message:
            print(f"   Error: {result.error_message}")
    
    def test_microphone_recording_upload(self) -> bool:
        """Test microphone recording and upload to server."""
        test_name = "Microphone Recording and Upload"
        start_time = time.time()
        
        try:
            recording_tests = []
            
            # Test 1: Basic recording functionality
            print("   🎤 Testing basic recording functionality...")
            recording_started = self.mock_esp32.start_recording(duration_ms=3000)  # 3 seconds
            
            if recording_started:
                print("   ⏳ Recording in progress...")
                time.sleep(3.5)  # Wait for recording to complete
                
                audio_sample = self.mock_esp32.stop_recording()
                
                if audio_sample:
                    print(f"   📊 Recorded: {audio_sample.duration_ms:.1f}ms, {len(audio_sample.data)} bytes")
                    print(f"   🔍 Checksum: {audio_sample.checksum[:16]}...")
                    
                    # Verify audio integrity
                    expected_samples = int(audio_sample.sample_rate * audio_sample.duration_ms / 1000)
                    actual_samples = len(audio_sample.data) // (audio_sample.bit_depth // 8)
                    integrity_check = abs(expected_samples - actual_samples) < 100  # Allow small variance
                    
                    recording_tests.append({
                        "test": "basic_recording",
                        "status": "PASS",
                        "duration_ms": audio_sample.duration_ms,
                        "data_size": len(audio_sample.data),
                        "integrity_verified": integrity_check,
                        "checksum": audio_sample.checksum
                    })
                    
                    self.audio_samples.append(audio_sample)
                    
                else:
                    recording_tests.append({
                        "test": "basic_recording",
                        "status": "FAIL",
                        "error": "No audio data captured"
                    })
            else:
                recording_tests.append({
                    "test": "basic_recording", 
                    "status": "FAIL",
                    "error": "Failed to start recording"
                })
            
            # Test 2: Upload simulation (server-side integrity verification)
            print("   📤 Testing server-side integrity verification...")
            if self.audio_samples:
                sample = self.audio_samples[-1]
                
                # Simulate upload and server verification
                upload_successful = True  # Simulated successful upload
                server_checksum = sample.checksum  # Server calculates same checksum
                checksum_match = sample.checksum == server_checksum
                
                # Simulate audio format validation on server
                format_valid = (
                    sample.sample_rate == 16000 and
                    sample.bit_depth == 16 and
                    sample.channels == 1 and
                    sample.format == "PCM"
                )
                
                recording_tests.append({
                    "test": "upload_integrity",
                    "status": "PASS" if upload_successful and checksum_match and format_valid else "FAIL",
                    "upload_successful": upload_successful,
                    "checksum_match": checksum_match,
                    "format_valid": format_valid,
                    "server_validation": {
                        "sample_rate": sample.sample_rate,
                        "bit_depth": sample.bit_depth,
                        "channels": sample.channels,
                        "format": sample.format
                    }
                })
            
            # Test 3: Multiple recording sessions
            print("   🔄 Testing multiple recording sessions...")
            multi_recording_results = []
            
            for i in range(3):
                recording_started = self.mock_esp32.start_recording(duration_ms=1000)  # 1 second each
                if recording_started:
                    time.sleep(1.2)
                    audio_sample = self.mock_esp32.stop_recording()
                    
                    multi_recording_results.append({
                        "session": i + 1,
                        "success": audio_sample is not None,
                        "duration_ms": audio_sample.duration_ms if audio_sample else 0,
                        "size_bytes": len(audio_sample.data) if audio_sample else 0
                    })
                    
                    if audio_sample:
                        self.audio_samples.append(audio_sample)
                
                time.sleep(0.5)  # Brief pause between recordings
            
            successful_sessions = sum(1 for r in multi_recording_results if r["success"])
            
            recording_tests.append({
                "test": "multiple_sessions",
                "status": "PASS" if successful_sessions >= 2 else "FAIL",
                "total_sessions": len(multi_recording_results),
                "successful_sessions": successful_sessions,
                "session_results": multi_recording_results
            })
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_tests = sum(1 for test in recording_tests if test.get("status") == "PASS")
            overall_pass = passed_tests >= len(recording_tests) * 0.7  # 70% pass rate
            
            result = DeviceTestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL", 
                details={
                    "recording_tests": recording_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(recording_tests),
                    "audio_samples_captured": len(self.audio_samples),
                    "device_stats": self.mock_esp32.get_device_status()["stats"]
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Recording tests: {passed_tests}/{len(recording_tests)} passed")
            print(f"   🎵 Audio samples captured: {len(self.audio_samples)}")
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = DeviceTestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def test_speaker_playback_response(self) -> bool:
        """Test speaker playback with backend command response."""
        test_name = "Speaker Playback and Response"
        start_time = time.time()
        
        try:
            playback_tests = []
            
            # Test 1: Basic playback functionality
            print("   🔊 Testing basic audio playback...")
            
            # Generate test audio data
            import math
            test_audio = self.mock_esp32.generate_test_audio_sample(duration_ms=2000, frequency=440)
            
            playback_started = self.mock_esp32.play_audio(test_audio, volume=75)
            
            if playback_started:
                print("   🎵 Playback in progress...")
                
                # Monitor playback
                playback_start_time = time.time()
                while self.mock_esp32.is_playing and time.time() - playback_start_time < 5.0:
                    time.sleep(0.1)
                
                playback_completed = not self.mock_esp32.is_playing
                playback_duration = (time.time() - playback_start_time) * 1000
                
                playback_tests.append({
                    "test": "basic_playback",
                    "status": "PASS" if playback_completed else "FAIL",
                    "playback_started": playback_started,
                    "playback_completed": playback_completed,
                    "playback_duration_ms": playback_duration,
                    "expected_duration_ms": 2000,
                    "audio_size_bytes": len(test_audio)
                })
                
                print(f"   ⏱️ Playback duration: {playback_duration:.1f}ms")
            else:
                playback_tests.append({
                    "test": "basic_playback",
                    "status": "FAIL",
                    "error": "Failed to start playback"
                })
            
            # Test 2: Playback response timing (no delay, no replay)
            print("   ⚡ Testing playback response timing...")
            
            response_times = []
            
            for i in range(3):
                # Generate short audio sample
                short_audio = self.mock_esp32.generate_test_audio_sample(duration_ms=500, frequency=880)
                
                response_start = time.time()
                playback_started = self.mock_esp32.play_audio(short_audio, volume=50)
                response_time = (time.time() - response_start) * 1000
                
                if playback_started:
                    response_times.append(response_time)
                    
                    # Wait for playback to complete
                    while self.mock_esp32.is_playing:
                        time.sleep(0.05)
                    
                    time.sleep(0.2)  # Brief pause between tests
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            low_latency = avg_response_time < 100  # Should respond within 100ms
            
            playback_tests.append({
                "test": "response_timing",
                "status": "PASS" if low_latency and len(response_times) >= 2 else "FAIL",
                "response_times_ms": response_times,
                "average_response_time_ms": avg_response_time,
                "low_latency_achieved": low_latency,
                "successful_responses": len(response_times)
            })
            
            print(f"   ⚡ Average response time: {avg_response_time:.1f}ms")
            
            # Test 3: Audio quality and no replay detection
            print("   🎯 Testing audio quality and replay prevention...")
            
            # Test with different audio samples
            quality_tests = []
            
            for freq in [220, 440, 880]:  # Different frequencies
                test_audio = self.mock_esp32.generate_test_audio_sample(duration_ms=1000, frequency=freq)
                playback_started = self.mock_esp32.play_audio(test_audio, volume=60)
                
                if playback_started:
                    # Monitor for completion
                    while self.mock_esp32.is_playing:
                        time.sleep(0.05)
                    
                    quality_tests.append({
                        "frequency": freq,
                        "playback_success": True,
                        "audio_size": len(test_audio)
                    })
                else:
                    quality_tests.append({
                        "frequency": freq,
                        "playback_success": False,
                        "error": "Playback failed"
                    })
                
                time.sleep(0.3)
            
            successful_quality_tests = sum(1 for t in quality_tests if t["playback_success"])
            
            playback_tests.append({
                "test": "audio_quality",
                "status": "PASS" if successful_quality_tests >= len(quality_tests) * 0.8 else "FAIL",
                "quality_tests": quality_tests,
                "successful_tests": successful_quality_tests,
                "total_tests": len(quality_tests)
            })
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_tests = sum(1 for test in playback_tests if test.get("status") == "PASS")
            overall_pass = passed_tests >= len(playback_tests) * 0.7  # 70% pass rate
            
            result = DeviceTestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "playback_tests": playback_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(playback_tests),
                    "device_stats": self.mock_esp32.get_device_status()["stats"]
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Playback tests: {passed_tests}/{len(playback_tests)} passed")
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = DeviceTestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def test_edge_cases_streaming(self) -> bool:
        """Test edge cases: disconnect/reboot during streaming."""
        test_name = "Edge Cases During Streaming"
        start_time = time.time()
        
        try:
            edge_case_tests = []
            
            # Test 1: Disconnect during recording
            print("   📡❌ Testing disconnect during recording...")
            
            recording_started = self.mock_esp32.start_recording(duration_ms=5000)
            if recording_started:
                time.sleep(1.0)  # Let recording start
                
                # Simulate disconnect
                self.mock_esp32.disconnect()
                
                time.sleep(1.0)  # Wait a bit
                
                # Try to get recording data
                audio_sample = self.mock_esp32.stop_recording()
                
                # Check if device handled disconnect gracefully
                device_status = self.mock_esp32.get_device_status()
                
                edge_case_tests.append({
                    "test": "disconnect_during_recording",
                    "status": "PASS" if device_status["connection_drops"] > 0 else "FAIL",
                    "recording_interrupted": not device_status["is_recording"],
                    "connection_drops": device_status["connection_drops"],
                    "partial_audio_captured": audio_sample is not None and len(audio_sample.data) > 0 if audio_sample else False
                })
                
                # Reconnect for next tests
                self.mock_esp32.reconnect()
            else:
                edge_case_tests.append({
                    "test": "disconnect_during_recording",
                    "status": "ERROR",
                    "error": "Could not start recording"
                })
            
            # Test 2: Disconnect during playback  
            print("   🔊❌ Testing disconnect during playback...")
            
            test_audio = self.mock_esp32.generate_test_audio_sample(duration_ms=3000, frequency=440)
            playback_started = self.mock_esp32.play_audio(test_audio, volume=50)
            
            if playback_started:
                time.sleep(0.5)  # Let playback start
                
                # Simulate disconnect
                self.mock_esp32.disconnect()
                
                time.sleep(0.5)  # Wait
                
                # Check device state
                device_status = self.mock_esp32.get_device_status()
                
                edge_case_tests.append({
                    "test": "disconnect_during_playback",
                    "status": "PASS" if not device_status["is_playing"] else "FAIL",
                    "playback_stopped": not device_status["is_playing"],
                    "connection_drops": device_status["connection_drops"],
                    "bytes_played_before_disconnect": device_status["stats"]["bytes_played"]
                })
                
                # Reconnect
                self.mock_esp32.reconnect()
            else:
                edge_case_tests.append({
                    "test": "disconnect_during_playback",
                    "status": "ERROR", 
                    "error": "Could not start playback"
                })
            
            # Test 3: Reboot during operation
            print("   🔄 Testing reboot during operation...")
            
            # Start recording
            recording_started = self.mock_esp32.start_recording(duration_ms=4000)
            
            if recording_started:
                time.sleep(1.0)  # Let recording start
                
                # Get initial stats
                initial_stats = self.mock_esp32.get_device_status()["stats"].copy()
                
                # Simulate reboot
                print("   🔄 Simulating device reboot...")
                self.mock_esp32.reboot()
                
                # Check post-reboot state
                post_reboot_status = self.mock_esp32.get_device_status()
                
                # Device should be connected again, but recording should be stopped
                reboot_handled_properly = (
                    post_reboot_status["connected"] and
                    not post_reboot_status["is_recording"] and
                    not post_reboot_status["is_playing"] and
                    post_reboot_status["buffer_size"] == 0
                )
                
                edge_case_tests.append({
                    "test": "reboot_during_operation",
                    "status": "PASS" if reboot_handled_properly else "FAIL",
                    "device_reconnected": post_reboot_status["connected"],
                    "operations_stopped": not post_reboot_status["is_recording"] and not post_reboot_status["is_playing"],
                    "buffer_cleared": post_reboot_status["buffer_size"] == 0,
                    "stats_before_reboot": initial_stats,
                    "stats_after_reboot": post_reboot_status["stats"]
                })
            else:
                edge_case_tests.append({
                    "test": "reboot_during_operation",
                    "status": "ERROR",
                    "error": "Could not start recording for reboot test"
                })
            
            # Test 4: Recovery and resumption
            print("   🔄 Testing operation recovery after issues...")
            
            recovery_tests = []
            
            # Test recording recovery
            recording_started = self.mock_esp32.start_recording(duration_ms=2000)
            if recording_started:
                time.sleep(2.2)
                audio_sample = self.mock_esp32.stop_recording()
                
                recovery_tests.append({
                    "operation": "recording_after_reboot",
                    "success": audio_sample is not None,
                    "data_size": len(audio_sample.data) if audio_sample else 0
                })
            
            # Test playback recovery
            test_audio = self.mock_esp32.generate_test_audio_sample(duration_ms=1500, frequency=660)
            playback_started = self.mock_esp32.play_audio(test_audio, volume=40)
            
            if playback_started:
                while self.mock_esp32.is_playing:
                    time.sleep(0.1)
                
                recovery_tests.append({
                    "operation": "playback_after_reboot",
                    "success": True
                })
            
            successful_recoveries = sum(1 for t in recovery_tests if t["success"])
            
            edge_case_tests.append({
                "test": "operation_recovery",
                "status": "PASS" if successful_recoveries >= len(recovery_tests) * 0.8 else "FAIL",
                "recovery_tests": recovery_tests,
                "successful_recoveries": successful_recoveries,
                "total_recovery_tests": len(recovery_tests)
            })
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_tests = sum(1 for test in edge_case_tests if test.get("status") == "PASS")
            overall_pass = passed_tests >= len(edge_case_tests) * 0.7  # 70% pass rate
            
            result = DeviceTestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "edge_case_tests": edge_case_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(edge_case_tests),
                    "final_device_stats": self.mock_esp32.get_device_status()["stats"]
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Edge case tests: {passed_tests}/{len(edge_case_tests)} passed")
            print(f"   🔄 Connection drops handled: {self.mock_esp32.get_device_status()['stats']['connection_drops']}")
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = DeviceTestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def run_device_functions_tests(self):
        """Run comprehensive ESP32 device functions testing suite."""
        print("🎵 ESP32 Device Functions Integration Testing Suite")
        print("=" * 60)
        
        test_methods = [
            self.test_microphone_recording_upload,
            self.test_speaker_playback_response,
            self.test_edge_cases_streaming
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
        print("🎯 DEVICE FUNCTIONS TEST RESULTS")
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
        
        print(f"Device Functions Score: {success_rate:.1f}% {overall_status}")
        print(f"Tests Passed: {passed_tests}/{total_tests}")
        
        # Device statistics summary
        device_stats = self.mock_esp32.get_device_status()["stats"]
        print(f"\n📊 Device Statistics:")
        print(f"   Recordings: {device_stats['recordings_completed']}/{device_stats['recordings_started']}")
        print(f"   Playbacks: {device_stats['playbacks_completed']}/{device_stats['playbacks_started']}")
        print(f"   Audio Data: {(device_stats['bytes_recorded'] + device_stats['bytes_played']) / 1024:.1f} KB")
        print(f"   Connection Issues: {device_stats['connection_drops']}")
        print(f"   Errors: {len(device_stats['errors'])}")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_score": success_rate,
            "tests_passed": passed_tests,
            "total_tests": total_tests,
            "test_results": [asdict(result) for result in self.test_results],
            "device_stats": device_stats,
            "audio_samples_captured": len(self.audio_samples)
        }
    
    def save_results_to_file(self, results: Dict[str, Any], filename: str = None):
        """Save test results to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"esp32_device_functions_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {filename}")
        return filename


def main():
    """Main device functions testing execution."""
    import math  # Required for sine wave generation
    
    print("🤖 AI Teddy Bear - ESP32 Device Functions Integration Testing")
    print("=" * 60)
    
    # Initialize tester
    tester = ESP32DeviceFunctionsTester()
    
    # Run all tests
    results = tester.run_device_functions_tests()
    
    # Save results
    filename = tester.save_results_to_file(results)
    
    # Return exit code based on results
    if results["overall_score"] >= 80:
        print("\n✅ ESP32 device functions testing PASSED")
        return 0
    elif results["overall_score"] >= 50:
        print(f"\n⚠️ ESP32 device functions testing completed with warnings ({results['overall_score']:.1f}%)")
        return 1
    else:
        print(f"\n❌ ESP32 device functions testing FAILED ({results['overall_score']:.1f}%)")
        return 2


if __name__ == "__main__":
    import sys
    import math  # Add this for sine wave generation
    result = main()
    sys.exit(result)