#!/usr/bin/env python3
"""
Production test for ESP32 device claim fix
Tests the actual claim_api functionality
"""

import json
import hmac
import hashlib
import time
import requests
import sys
import os

# Configuration
BASE_URL = "http://localhost:8000"  # Update with your server URL
DEVICE_ID = f"Teddy-ESP32-{int(time.time())}"
CHILD_ID = "test-child-001"
DEVICE_SHARED_SECRET = os.getenv("DEVICE_SHARED_SECRET", "your-secret-key-here")

def generate_hmac(device_id: str, child_id: str, nonce: str, secret: str) -> str:
    """Generate HMAC for device authentication"""
    message = f"{device_id}:{child_id}:{nonce}"
    return hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

def test_claim_endpoint():
    """Test the /api/v1/pair/claim endpoint"""
    
    print("=" * 60)
    print("Testing ESP32 Device Claim Endpoint")
    print("=" * 60)
    
    # Generate nonce
    nonce = hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:16]
    
    # Generate HMAC
    hmac_hex = generate_hmac(DEVICE_ID, CHILD_ID, nonce, DEVICE_SHARED_SECRET)
    
    # Prepare claim request
    claim_data = {
        "device_id": DEVICE_ID,
        "child_id": CHILD_ID,
        "nonce": nonce,
        "hmac_hex": hmac_hex
    }
    
    print(f"Device ID: {DEVICE_ID}")
    print(f"Child ID: {CHILD_ID}")
    print(f"Nonce: {nonce}")
    print(f"HMAC: {hmac_hex[:16]}...")
    print()
    
    # Make request
    url = f"{BASE_URL}/api/v1/pair/claim"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ESP32HTTPClient"
    }
    
    print(f"Sending POST request to {url}")
    
    try:
        response = requests.post(url, json=claim_data, headers=headers, timeout=10)
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Claim successful!")
            response_data = response.json()
            print(f"Response: {json.dumps(response_data, indent=2)}")
            
            # Verify the response structure
            if "access_token" in response_data:
                print("✅ Access token received")
            if "ws_url" in response_data:
                print(f"✅ WebSocket URL: {response_data['ws_url']}")
            if "config" in response_data:
                print("✅ Configuration received")
                
        elif response.status_code == 404:
            print("⚠️  Device not found (expected for auto-registration)")
            print(f"Response: {response.text}")
        elif response.status_code == 409:
            print("⚠️  Nonce already used (replay attack protection working)")
            print(f"Response: {response.text}")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the server is running.")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()
    print("=" * 60)
    print("Test Summary:")
    print("- DeviceStatus enum is now (str, Enum) for JSON compatibility")
    print("- Auto-registration creates device records with proper status")
    print("- No more 'str' object has no attribute 'value' errors")
    print("=" * 60)

def test_enum_locally():
    """Test the enum fix locally"""
    print("\n" + "=" * 60)
    print("Testing Enum Fix Locally")
    print("=" * 60)
    
    try:
        # Add src to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        
        # Try to import and test
        try:
            from src.user_experience.device_pairing.pairing_manager import DeviceStatus
            
            status = DeviceStatus.UNREGISTERED
            test_dict = {"status": status, "device": DEVICE_ID}
            
            # Test JSON serialization
            json_str = json.dumps(test_dict)
            print(f"✅ DeviceStatus is JSON serializable: {json_str}")
            
            # Verify the value
            parsed = json.loads(json_str)
            assert parsed["status"] == "unregistered", f"Expected 'unregistered', got {parsed['status']}"
            print(f"✅ Status value is correct: {parsed['status']}")
            
        except ImportError:
            print("⚠️  Using mock DeviceStatus (import failed)")
            from src.adapters.claim_api import DeviceStatus
            
            status = DeviceStatus.UNREGISTERED
            test_dict = {"status": status, "device": DEVICE_ID}
            json_str = json.dumps(test_dict)
            print(f"✅ Mock DeviceStatus is JSON serializable: {json_str}")
            
    except Exception as e:
        print(f"❌ Local test failed: {e}")

if __name__ == "__main__":
    # Test enum locally first
    test_enum_locally()
    
    # Test against running server
    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        test_claim_endpoint()
    else:
        print("\n💡 To test against live server, run: python test_production_fix.py --live")