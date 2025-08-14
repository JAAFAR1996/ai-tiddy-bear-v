#!/usr/bin/env python3
"""
Debug 422 Error for ESP32 Claim Endpoint
"""

import requests
import json
import hashlib
import hmac
import secrets

def generate_oob_secret(device_id: str) -> str:
    """Generate OOB secret using same algorithm as server"""
    salt = "ai-teddy-bear-oob-secret-v1"
    hash_input = f"{device_id}:{salt}".encode('utf-8')
    
    # First SHA256
    device_hash = hashlib.sha256(hash_input).hexdigest()
    
    # Second SHA256
    final_hash = hashlib.sha256((device_hash + salt).encode('utf-8')).hexdigest()
    
    return final_hash.upper()

def calculate_hmac(device_id: str, child_id: str, nonce_hex: str, oob_secret_hex: str) -> str:
    """Calculate HMAC using same algorithm as ESP32/Server"""
    oob_secret_bytes = bytes.fromhex(oob_secret_hex)
    nonce_bytes = bytes.fromhex(nonce_hex)
    
    mac = hmac.new(oob_secret_bytes, digestmod=hashlib.sha256)
    mac.update(device_id.encode('utf-8'))
    mac.update(child_id.encode('utf-8'))
    mac.update(nonce_bytes)
    
    return mac.hexdigest()

def test_claim_endpoint():
    server_url = "https://ai-tiddy-bear-v-xuqy.onrender.com"
    device_id = "Teddy-ESP32-001"
    child_id = "test-child-001"
    
    # Generate valid request
    nonce_hex = secrets.token_hex(16)
    oob_secret_hex = generate_oob_secret(device_id)
    hmac_hex = calculate_hmac(device_id, child_id, nonce_hex, oob_secret_hex)
    
    payload = {
        "device_id": device_id,
        "child_id": child_id,
        "nonce": nonce_hex,
        "hmac_hex": hmac_hex,
        "firmware_version": "1.2.0"
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ESP32-TeddyBear/1.2.0"
    }
    
    print("🔍 Sending request to:", f"{server_url}/api/v1/pair/claim")
    print("📦 Payload:")
    print(json.dumps(payload, indent=2))
    print("\n📡 Headers:")
    print(json.dumps(headers, indent=2))
    
    try:
        response = requests.post(
            f"{server_url}/api/v1/pair/claim",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"\n📊 Response Status: {response.status_code}")
        print("📄 Response Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print("\n📄 Response Body:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
            
            if response.status_code == 422:
                print("\n🔍 Detailed Validation Errors:")
                for error in response_json.get('detail', []):
                    print(f"  - Field: {error.get('loc', [])}")
                    print(f"    Type: {error.get('type', 'unknown')}")
                    print(f"    Message: {error.get('msg', 'No message')}")
                    print(f"    Input: {error.get('input', 'No input shown')}")
                    print()
        except:
            print(response.text)
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_claim_endpoint()