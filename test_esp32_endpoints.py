#!/usr/bin/env python3
"""
 AI TEDDY BEAR - ESP32 ENDPOINTS TEST SCRIPT
===============================================
Production-grade testing of ESP32 endpoints after implementation refinements
"""

import requests
import json
import hashlib
import hmac
import secrets
from datetime import datetime
import sys

# Server configuration
BASE_URL = "http://127.0.0.1:8080"

def generate_test_hmac(device_id: str, child_id: str, nonce: str, oob_secret: str) -> str:
    """Generate HMAC for device authentication."""
    # Convert OOB secret from hex to bytes
    oob_secret_bytes = bytes.fromhex(oob_secret)
    
    # Create HMAC instance
    mac = hmac.new(oob_secret_bytes, digestmod=hashlib.sha256)
    
    # Add data in specific order (device_id || child_id || nonce)
    mac.update(device_id.encode('utf-8'))
    mac.update(child_id.encode('utf-8'))
    mac.update(bytes.fromhex(nonce))
    
    return mac.hexdigest()

def generate_device_oob_secret(device_id: str) -> str:
    """Generate deterministic OOB secret for testing (matches server logic)."""
    salt = "ai-teddy-bear-oob-secret-v1"
    hash_input = f"{device_id}:{salt}".encode('utf-8')
    
    device_hash = hashlib.sha256(hash_input).hexdigest()
    final_hash = hashlib.sha256((device_hash + salt).encode('utf-8')).hexdigest()
    
    return final_hash.upper()

def test_health_endpoint():
    """Test health endpoint."""
    print("[TEST] Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   [PASS] Health endpoint working!")
            return True
        else:
            print(f"   [FAIL] Health endpoint failed: {response.text}")
            return False
    except Exception as e:
        print(f"   [FAIL] Health endpoint error: {e}")
        return False

def test_esp32_claim_endpoint():
    """Test ESP32 device claim endpoint."""
    print("[ESP32] Testing ESP32 claim endpoint...")
    
    # Test device data
    device_id = "Teddy-ESP32-DEV001"
    child_id = "test-child-123"
    nonce = secrets.token_hex(16)  # 32 hex chars = 16 bytes
    
    # Generate OOB secret and HMAC
    oob_secret = generate_device_oob_secret(device_id)
    hmac_signature = generate_test_hmac(device_id, child_id, nonce, oob_secret)
    
    payload = {
        "device_id": device_id,
        "child_id": child_id,
        "nonce": nonce,
        "hmac_hex": hmac_signature,
        "firmware_version": "1.0.0"
    }
    
    print(f"   Device: {device_id}")
    print(f"   Child: {child_id}")
    print(f"   Nonce: {nonce[:16]}...")
    print(f"   HMAC: {hmac_signature[:16]}...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/pair/claim",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("   [PASS] ESP32 claim successful!")
            print(f"   Token: {data['access_token'][:20]}...")
            print(f"   Session: {data['device_session_id']}")
            return data
        elif response.status_code == 404:
            print("   [WARN]  Child profile not found (expected in test environment)")
            return None
        elif response.status_code == 503:
            print("   [WARN]  Service still initializing")
            return None
        else:
            print(f"   [FAIL] ESP32 claim failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"   [FAIL] ESP32 claim error: {e}")
        return None

def test_esp32_status_endpoint():
    """Test ESP32 device status endpoint."""
    print("[STATUS] Testing ESP32 status endpoint...")
    
    device_id = "Teddy-ESP32-DEV001"
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/device/status/{device_id}",
            headers={"Authorization": "Bearer dummy-token"},
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 401:
            print("   [PASS] Authentication required (expected)")
            return True
        elif response.status_code == 200:
            print("   [PASS] Status endpoint working!")
            return True
        else:
            print(f"   [FAIL] Status endpoint failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"   [FAIL] Status endpoint error: {e}")
        return False

def main():
    """Run all ESP32 endpoint tests."""
    print("AI TEDDY BEAR - ESP32 ENDPOINTS TEST")
    print("=" * 50)
    print(f"Testing server at: {BASE_URL}")
    print("")
    
    # Test results
    results = {
        "health": False,
        "esp32_claim": False,
        "esp32_status": False
    }
    
    # Run tests
    results["health"] = test_health_endpoint()
    print("")
    
    if results["health"]:
        claim_result = test_esp32_claim_endpoint()
        results["esp32_claim"] = claim_result is not None
        print("")
        
        results["esp32_status"] = test_esp32_status_endpoint()
        print("")
    
    # Summary
    print("[SUMMARY] TEST SUMMARY")
    print("-" * 30)
    for test, passed in results.items():
        status = "[PASS] PASS" if passed else "[FAIL] FAIL"
        print(f"   {test.upper()}: {status}")
    
    print("")
    total_tests = len(results)
    passed_tests = sum(results.values())
    print(f"[RESULT] Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("[SUCCESS] All tests passed! ESP32 endpoints are working.")
        return 0
    else:
        print("[WARN]  Some tests failed. Check server logs.")
        return 1

if __name__ == "__main__":
    sys.exit(main())