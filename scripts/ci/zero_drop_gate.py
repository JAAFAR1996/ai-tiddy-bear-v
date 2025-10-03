#!/usr/bin/env python3
"""
Zero-Drop CI Gate
================
Validates zero-drop deployment requirements before merge.
"""
import asyncio
import json
import logging
import sys
import time
from typing import Dict, Any, List
import aiohttp
import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ZeroDropValidator:
    """Validates zero-drop WebSocket functionality."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.ws_url = base_url.replace("http", "ws")
        self.failures = []
        
    async def validate_all(self) -> bool:
        """Run all zero-drop validations."""
        logger.info("Starting zero-drop validation...")
        
        tests = [
            self.test_websocket_resume(),
            self.test_drain_notifications(),
            self.test_sticky_routing(),
            self.test_metrics_collection(),
            self.test_message_sequencing(),
        ]
        
        results = await asyncio.gather(*tests, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        total_tests = len(tests)
        
        logger.info(f"Validation complete: {success_count}/{total_tests} tests passed")
        
        if self.failures:
            logger.error("Validation failures:")
            for failure in self.failures:
                logger.error(f"  - {failure}")
        
        return len(self.failures) == 0
    
    async def test_websocket_resume(self) -> bool:
        """Test WebSocket session resume functionality."""
        logger.info("Testing WebSocket resume...")
        
        try:
            device_id = f"test_device_{int(time.time())}"
            
            # First connection
            uri = f"{self.ws_url}/ws/esp32/connect?device_id={device_id}&child_id=test&child_name=Test&child_age=7&token=test"
            
            async with websockets.connect(uri) as ws1:
                # Send a message and get response
                await ws1.send(json.dumps({"type": "ping", "timestamp": time.time() * 1000}))
                response = await ws1.recv()
                data = json.loads(response)
                
                if data.get("type") != "pong":
                    self.failures.append("WebSocket ping/pong failed")
                    return False
            
            # Wait a moment then reconnect
            await asyncio.sleep(1)
            
            async with websockets.connect(uri) as ws2:
                # Should receive resume offer
                message = await asyncio.wait_for(ws2.recv(), timeout=5.0)
                data = json.loads(message)
                
                if data.get("type") == "resume_offer":
                    # Accept resume
                    await ws2.send(json.dumps({"type": "resume_ack", "accepted": True}))
                    
                    # Should receive resume complete
                    complete_msg = await asyncio.wait_for(ws2.recv(), timeout=5.0)
                    complete_data = json.loads(complete_msg)
                    
                    if complete_data.get("type") != "resume_complete":
                        self.failures.append("Resume complete message not received")
                        return False
                else:
                    self.failures.append("Resume offer not received on reconnection")
                    return False
            
            logger.info("✓ WebSocket resume test passed")
            return True
            
        except Exception as e:
            self.failures.append(f"WebSocket resume test failed: {e}")
            return False
    
    async def test_drain_notifications(self) -> bool:
        """Test drain mode notifications."""
        logger.info("Testing drain notifications...")
        
        try:
            # Start drain mode
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/admin/drain/start",
                    json={"reason": "ci_test", "max_session_age_seconds": 60},
                    headers={"Authorization": "Bearer test_admin_token"}
                ) as resp:
                    if resp.status != 202:
                        self.failures.append(f"Failed to start drain mode: {resp.status}")
                        return False
            
            # Connect WebSocket during drain
            device_id = f"drain_test_{int(time.time())}"
            uri = f"{self.ws_url}/ws/esp32/connect?device_id={device_id}&child_id=test&child_name=Test&child_age=7&token=test"
            
            try:
                async with websockets.connect(uri) as ws:
                    # Should be rejected with 4503
                    await ws.recv()
                    self.failures.append("WebSocket connection accepted during drain")
                    return False
            except websockets.exceptions.ConnectionClosedError as e:
                if e.code != 4503:
                    self.failures.append(f"Wrong close code during drain: {e.code}")
                    return False
            
            # End drain mode
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/admin/drain/complete",
                    headers={"Authorization": "Bearer test_admin_token"}
                ) as resp:
                    if resp.status != 200:
                        self.failures.append(f"Failed to end drain mode: {resp.status}")
                        return False
            
            logger.info("✓ Drain notifications test passed")
            return True
            
        except Exception as e:
            self.failures.append(f"Drain notifications test failed: {e}")
            return False
    
    async def test_sticky_routing(self) -> bool:
        """Test sticky routing consistency."""
        logger.info("Testing sticky routing...")
        
        try:
            device_id = f"sticky_test_{int(time.time())}"
            
            # Make multiple requests and check affinity consistency
            async with aiohttp.ClientSession() as session:
                affinity_keys = set()
                
                for i in range(5):
                    async with session.get(
                        f"{self.base_url}/api/v1/esp32/config",
                        params={"device_id": device_id}
                    ) as resp:
                        if resp.status != 200:
                            self.failures.append(f"Config request failed: {resp.status}")
                            return False
                        
                        affinity_key = resp.headers.get("X-Affinity-Key")
                        if affinity_key:
                            affinity_keys.add(affinity_key)
                
                # Should have consistent affinity
                if len(affinity_keys) > 1:
                    self.failures.append(f"Inconsistent affinity keys: {affinity_keys}")
                    return False
            
            logger.info("✓ Sticky routing test passed")
            return True
            
        except Exception as e:
            self.failures.append(f"Sticky routing test failed: {e}")
            return False
    
    async def test_metrics_collection(self) -> bool:
        """Test metrics collection for zero-drop monitoring."""
        logger.info("Testing metrics collection...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/v1/esp32/metrics") as resp:
                    if resp.status != 200:
                        self.failures.append(f"Metrics endpoint failed: {resp.status}")
                        return False
                    
                    data = await resp.json()
                    
                    # Check required metrics
                    required_metrics = [
                        "ws_active", "ws_reconnects", "ws_resumes", 
                        "resume_failures", "dropped_messages"
                    ]
                    
                    ws_metrics = data.get("ws_metrics", {})
                    for metric in required_metrics:
                        if metric not in ws_metrics:
                            self.failures.append(f"Missing metric: {metric}")
                            return False
                    
                    # Check for resume store metrics
                    resume_metrics = data.get("resume_store_metrics", {})
                    if not resume_metrics:
                        self.failures.append("Resume store metrics missing")
                        return False
            
            logger.info("✓ Metrics collection test passed")
            return True
            
        except Exception as e:
            self.failures.append(f"Metrics collection test failed: {e}")
            return False
    
    async def test_message_sequencing(self) -> bool:
        """Test message sequencing for resume support."""
        logger.info("Testing message sequencing...")
        
        try:
            device_id = f"seq_test_{int(time.time())}"
            uri = f"{self.ws_url}/ws/esp32/connect?device_id={device_id}&child_id=test&child_name=Test&child_age=7&token=test"
            
            async with websockets.connect(uri) as ws:
                # Send ping and check sequence numbers
                await ws.send(json.dumps({"type": "ping", "timestamp": time.time() * 1000}))
                
                response = await ws.recv()
                data = json.loads(response)
                
                # Should have sequence number
                if "_seq" not in data:
                    self.failures.append("Message missing sequence number")
                    return False
                
                seq1 = data["_seq"]
                
                # Send another ping
                await ws.send(json.dumps({"type": "ping", "timestamp": time.time() * 1000}))
                
                response2 = await ws.recv()
                data2 = json.loads(response2)
                
                if "_seq" not in data2:
                    self.failures.append("Second message missing sequence number")
                    return False
                
                seq2 = data2["_seq"]
                
                # Sequence should increment
                if seq2 <= seq1:
                    self.failures.append(f"Sequence not incrementing: {seq1} -> {seq2}")
                    return False
            
            logger.info("✓ Message sequencing test passed")
            return True
            
        except Exception as e:
            self.failures.append(f"Message sequencing test failed: {e}")
            return False


async def main():
    """Main CI gate function."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8000"
    
    validator = ZeroDropValidator(base_url)
    success = await validator.validate_all()
    
    if success:
        logger.info("🎉 All zero-drop validations passed!")
        sys.exit(0)
    else:
        logger.error("❌ Zero-drop validation failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())