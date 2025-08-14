#!/usr/bin/env python3
"""
Test script for claim endpoint - debug 422 error
"""

import requests
import json
import sys

def test_claim_endpoint():
    """Test claim endpoint with proper ESP32 payload"""
    
    # Use the HMAC from our compatibility test
    test_payload = {
        "device_id": "Teddy-ESP32-001",
        "child_id": "test-child-001",
        "nonce": "892bc61928c07e5da2a3d08415ea4a03",
        "hmac_hex": "a43a89eb532e3a369acef720823f61c3a5fe2c3a53d4480941fb90a02a18b53b",
        "firmware_version": "1.2.0"
    }
    
    url = "https://ai-tiddy-bear-v-xuqy.onrender.com/api/v1/pair/claim"
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ESP32-TeddyBear/1.2.0"
    }
    
    print("=== Testing Claim Endpoint ===")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")
    print()
    
    try:
        response = requests.post(
            url, 
            json=test_payload, 
            headers=headers,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print()
        
        if response.headers.get('content-type', '').startswith('application/json'):
            try:
                response_data = response.json()
                print(f"Response JSON:")
                print(json.dumps(response_data, indent=2))
            except:
                print(f"Response Text: {response.text}")
        else:
            print(f"Response Text: {response.text}")
            
        print()
        
        if response.status_code == 200:
            print("✅ SUCCESS: Claim endpoint working correctly")
        elif response.status_code == 422:
            print("❌ VALIDATION ERROR: Check request format")
        elif response.status_code == 401:
            print("❌ AUTHENTICATION ERROR: JWT required unexpectedly")
        elif response.status_code == 404:
            print("❌ NOT FOUND: Endpoint not registered")
        elif response.status_code == 503:
            print("❌ SERVICE UNAVAILABLE: Server not ready")
        else:
            print(f"❌ UNEXPECTED STATUS: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST FAILED: {e}")
        return False
        
    return response.status_code == 200

if __name__ == "__main__":
    success = test_claim_endpoint()
    sys.exit(0 if success else 1)
