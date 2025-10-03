#!/usr/bin/env python3
"""
WebSocket Test Script for AI Teddy Bear ESP32 Communication
Tests the WebSocket endpoint with proper authentication
"""

import asyncio
import websockets
import json
import hmac
import hashlib
import os

# ESP32 Configuration
DEVICE_ID = "test_device_001"
CHILD_ID = "test_child_001"
CHILD_NAME = "TestChild"
CHILD_AGE = 7

# Generate HMAC token for ESP32 authentication
def generate_esp32_token(device_id: str, secret: str) -> str:
    """Generate HMAC-SHA256 token for ESP32 authentication"""
    return hmac.new(
        secret.encode(),
        device_id.encode(),
        hashlib.sha256
    ).hexdigest()

async def test_websocket_connection():
    """Test WebSocket connection to ESP32 endpoint"""
    
    # Get ESP32 shared secret from environment
    secret = os.getenv("ESP32_SHARED_SECRET", "dev-esp32-shared-secret-64-chars-long-12345678901234567890123456789012345678901234567890")
    
    # Generate authentication token
    token = generate_esp32_token(DEVICE_ID, secret)
    
    # WebSocket URL with query parameters - try without token first for dev bypass
    ws_url = f"ws://localhost:8000/ws/esp32/connect?device_id={DEVICE_ID}&child_id={CHILD_ID}&child_name={CHILD_NAME}&child_age={CHILD_AGE}"
    
    print(f"🔌 Connecting to WebSocket: {ws_url}")
    print(f"🔑 Device ID: {DEVICE_ID}")
    print(f"🔑 Token: {token[:16]}...")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connection established!")
            
            # Send a test message
            test_message = {
                "type": "audio_start",
                "audio_session_id": "test_session_001"
            }
            
            print(f"📤 Sending test message: {test_message}")
            await websocket.send(json.dumps(test_message))
            
            # Wait for response
            print("⏳ Waiting for response...")
            response = await websocket.recv()
            print(f"📥 Received response: {response}")
            
            # Send audio chunk message
            audio_chunk_message = {
                "type": "audio_chunk",
                "audio_data": "dGVzdF9hdWRpb19kYXRh",  # base64 encoded "test_audio_data"
                "chunk_id": "chunk_001",
                "audio_session_id": "test_session_001",
                "is_final": True
            }
            
            print(f"📤 Sending audio chunk: {audio_chunk_message}")
            await websocket.send(json.dumps(audio_chunk_message))
            
            # Wait for AI response
            print("⏳ Waiting for AI response...")
            ai_response = await websocket.recv()
            print(f"🤖 AI Response: {ai_response}")
            
            # Send audio end message
            audio_end_message = {
                "type": "audio_end",
                "audio_session_id": "test_session_001"
            }
            
            print(f"📤 Sending audio end: {audio_end_message}")
            await websocket.send(json.dumps(audio_end_message))
            
            print("✅ WebSocket test completed successfully!")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket connection closed: {e}")
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_websocket_ping():
    """Test the ping WebSocket endpoint"""
    print("\n🏓 Testing WebSocket ping endpoint...")
    
    try:
        async with websockets.connect("ws://localhost:8000/ws/ping") as websocket:
            print("✅ Ping WebSocket connected!")
            
            # Send ping
            await websocket.send("ping")
            response = await websocket.recv()
            print(f"📥 Ping response: {response}")
            
    except Exception as e:
        print(f"❌ Ping test failed: {e}")

if __name__ == "__main__":
    print("🧸 AI Teddy Bear WebSocket Test")
    print("=" * 50)
    
    # Test ping endpoint first
    asyncio.run(test_websocket_ping())
    
    # Test main ESP32 endpoint
    asyncio.run(test_websocket_connection())
