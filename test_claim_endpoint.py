#!/usr/bin/env python3
"""
Test script for the claim API endpoint to verify the fix
"""

import requests
import json
import hmac
import hashlib
import secrets
from datetime import datetime

def generate_test_hmac(device_id: str, child_id: str, nonce: str) -> str:
    """Generate test HMAC for the given parameters"""
    # Use the same deterministic OOB secret generation as the server
    salt = "ai-teddy-bear-oob-secret-v1"
    hash_input = f"{device_id}:{salt}".encode('utf-8')
    device_hash = hashlib.sha256(hash_input).hexdigest()
    final_hash = hashlib.sha256((device_hash + salt).encode('utf-8')).hexdigest()
    oob_secret_hex = final_hash.upper()
    
    # Convert OOB secret from hex to bytes
    oob_secret_bytes = bytes.fromhex(oob_secret_hex)
    
    # Create HMAC instance
    mac = hmac.new(oob_secret_bytes, digestmod=hashlib.sha256)
    
    # Add data in specific order (device_id || child_id || nonce)
    mac.update(device_id.encode('utf-8'))
    mac.update(child_id.encode('utf-8'))
    mac.update(bytes.fromhex(nonce))
    
    return mac.hexdigest()

def test_claim_endpoint():
    """Test the claim API endpoint with the ESP32's exact request"""
    
    # Test data (same as ESP32 is sending)
    device_id = "Teddy-ESP32-A795BAA4"
    child_id = "test-child-001"
    nonce = "dee882e9ff7a341a"
    
    # Generate correct HMAC
    hmac_hex = generate_test_hmac(device_id, child_id, nonce)
    
    print(f"Testing claim endpoint with:")
    print(f"  Device ID: {device_id}")
    print(f"  Child ID: {child_id}")
    print(f"  Nonce: {nonce}")
    print(f"  HMAC: {hmac_hex}")
    print()
    
    # Prepare the request
    url = "https://ai-tiddy-bear-v-xuqy.onrender.com/api/v1/pair/claim"
    payload = {
        "device_id": device_id,
        "child_id": child_id,
        "nonce": nonce,
        "hmac_hex": hmac_hex,
        "firmware_version": "1.0.0"
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ESP32-Teddy-Bear/1.0"
    }
    
    try:
        print(f"Sending request to: {url}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ SUCCESS: Claim endpoint is working correctly!")
            data = response.json()
            if "access_token" in data:
                print(f"✅ Access token received: {data['access_token'][:50]}...")
            if "device_config" in data:
                print(f"✅ Device config received: {list(data['device_config'].keys())}")
        elif response.status_code == 500:
            print("\n❌ FAILURE: HTTP 500 error - server issue")
            try:
                error_data = response.json()
                print(f"Error details: {error_data}")
            except:
                print("Error response is not valid JSON")
        else:
            print(f"\n⚠️  UNEXPECTED: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"Response data: {error_data}")
            except:
                print("Response is not valid JSON")
                
    except requests.exceptions.Timeout:
        print("❌ FAILURE: Request timed out")
    except requests.exceptions.ConnectionError:
        print("❌ FAILURE: Could not connect to server")
    except Exception as e:
        print(f"❌ FAILURE: Unexpected error: {e}")

if __name__ == "__main__":
    print("=== AI Teddy Bear Claim API Test ===")
    print("Testing the fix for HTTP 500 errors")
    print("=" * 50)
    test_claim_endpoint()