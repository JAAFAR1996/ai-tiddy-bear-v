#!/usr/bin/env python3
"""
Test script for ESP32 claim flow integration
"""

import requests
import hmac
import hashlib
import time
import json
import os
from typing import Dict, Any

# Test configuration
DEVICE_ID = "Teddy-ESP32-0001"
CHILD_ID = "child_123"
OOB_SECRET_HEX = "A1B2C3D4E5F6789012345678901234567890ABCDEF1234567890ABCDEF123456"
API_BASE_URL = "http://localhost:8000"

def generate_nonce() -> str:
    """Generate a unique nonce"""
    return str(int(time.time() * 1000000))

def compute_hmac_signature(device_id: str, child_id: str, nonce: str, oob_secret_hex: str) -> str:
    """Compute HMAC signature like ESP32 does"""
    oob_secret = bytes.fromhex(oob_secret_hex)
    
    mac = hmac.new(oob_secret, digestmod=hashlib.sha256)
    mac.update(device_id.encode('utf-8'))
    mac.update(child_id.encode('utf-8'))
    mac.update(nonce.encode('utf-8'))
    
    return mac.hexdigest()

def test_claim_endpoint():
    """Test the claim endpoint"""
    print("Testing claim endpoint...")
    
    # Generate nonce and signature
    nonce = generate_nonce()
    hmac_hex = compute_hmac_signature(DEVICE_ID, CHILD_ID, nonce, OOB_SECRET_HEX)
    
    # Prepare request
    claim_data = {
        "device_id": DEVICE_ID,
        "child_id": CHILD_ID,
        "nonce": nonce,
        "hmac_hex": hmac_hex
    }
    
    print(f"Claim request: {json.dumps(claim_data, indent=2)}")
    
    # Send request
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/pair/claim",
            json=claim_data,
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            tokens = response.json()
            print("✅ Claim successful!")
            print(f"Access token: {tokens['access'][:50]}...")
            print(f"Refresh token: {tokens['refresh'][:50]}...")
            return tokens
        else:
            print("❌ Claim failed!")
            return None
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def test_refresh_endpoint(refresh_token: str):
    """Test the refresh endpoint"""
    print("\nTesting refresh endpoint...")
    
    refresh_data = {
        "refresh_token": refresh_token
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/token/refresh",
            json=refresh_data,
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Refresh successful!")
            print(f"New access token: {result['access'][:50]}...")
            return result
        else:
            print("❌ Refresh failed!")
            return None
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def test_nonce_replay():
    """Test nonce replay protection"""
    print("\nTesting nonce replay protection...")
    
    # Use same nonce twice
    nonce = generate_nonce()
    hmac_hex = compute_hmac_signature(DEVICE_ID, CHILD_ID, nonce, OOB_SECRET_HEX)
    
    claim_data = {
        "device_id": DEVICE_ID,
        "child_id": CHILD_ID,
        "nonce": nonce,
        "hmac_hex": hmac_hex
    }
    
    # First request should succeed
    response1 = requests.post(f"{API_BASE_URL}/api/v1/pair/claim", json=claim_data)
    print(f"First request: {response1.status_code}")
    
    # Second request should fail
    response2 = requests.post(f"{API_BASE_URL}/api/v1/pair/claim", json=claim_data)
    print(f"Second request: {response2.status_code}")
    
    if response1.status_code == 200 and response2.status_code == 409:
        print("✅ Nonce replay protection working!")
    else:
        print("❌ Nonce replay protection failed!")

def test_invalid_hmac():
    """Test invalid HMAC rejection"""
    print("\nTesting invalid HMAC rejection...")
    
    nonce = generate_nonce()
    
    claim_data = {
        "device_id": DEVICE_ID,
        "child_id": CHILD_ID,
        "nonce": nonce,
        "hmac_hex": "invalid_hmac_signature"
    }
    
    response = requests.post(f"{API_BASE_URL}/api/v1/pair/claim", json=claim_data)
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 401:
        print("✅ Invalid HMAC properly rejected!")
    else:
        print("❌ Invalid HMAC not properly rejected!")

def main():
    """Run all tests"""
    print("🧪 Testing ESP32 Claim Flow Integration")
    print("=" * 50)
    
    # Set environment variables for testing
    os.environ["JWT_ACCESS_SECRET"] = "test_access_secret_key_123"
    os.environ["JWT_REFRESH_SECRET"] = "test_refresh_secret_key_456"
    
    # Test claim endpoint
    tokens = test_claim_endpoint()
    
    if tokens:
        # Test refresh endpoint
        test_refresh_endpoint(tokens["refresh"])
    
    # Test security features
    test_nonce_replay()
    test_invalid_hmac()
    
    print("\n🏁 Testing completed!")

if __name__ == "__main__":
    main()