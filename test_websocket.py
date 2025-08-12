#!/usr/bin/env python3
"""
Test WebSocket connection to AI Teddy Bear server
"""
import asyncio
import websockets
import json
import sys
import urllib.parse

async def test_websocket():
    """Test WebSocket connection with proper parameters."""
    
    # Connection parameters
    host = "ai-tiddy-bear-v-xuqy.onrender.com"
    path = "/ws/esp32/connect"
    
    # Device parameters
    params = {
        "device_id": "dev12345678",
        "token": "6d38672526b1cdd9d71c945eac00c895dd767a42fc0be5b4fbb0f0446ce03f86",
        "child_id": "c1",
        "child_name": "سارة",
        "child_age": "7"
    }
    
    # Build URL
    query_string = urllib.parse.urlencode(params)
    url = f"wss://{host}{path}?{query_string}"
    
    print(f"🔗 Connecting to: {url}")
    
    try:
        # Connect with timeout
        async with websockets.connect(url, timeout=10) as websocket:
            print("✅ WebSocket connection established!")
            
            # Send a test message
            test_message = {
                "type": "audio_chunk",
                "data": "test_audio_data",
                "sequence": 1
            }
            
            await websocket.send(json.dumps(test_message))
            print("📤 Sent test message")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"📥 Received: {response}")
            except asyncio.TimeoutError:
                print("⏰ No response received within 5 seconds")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ Connection closed: {e}")
    except websockets.exceptions.InvalidURI as e:
        print(f"❌ Invalid URI: {e}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())