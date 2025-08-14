#!/usr/bin/env python3
"""
Simple test script to verify claim endpoint is working
"""

import requests
import hmac
import hashlib

def test_claim_endpoint():
    """Test claim endpoint with simple request"""
    
    # Test data
    device_id = "Teddy-ESP32-001"
    child_id = "test-child-001" 
    nonce = "1234567890abcdef1234567890abcdef"  # 32 hex chars
    
    # Generate simple HMAC for testing
    # This mimics the server's OOB secret generation
    salt = "ai-teddy-bear-oob-secret-v1"
    hash_input = f"{device_id}:{salt}".encode('utf-8')
    device_hash = hashlib.sha256(hash_input).hexdigest()
    oob_secret = hashlib.sha256((device_hash + salt).encode('utf-8')).hexdigest().upper()
    
    # Calculate HMAC like server expects: device_id + child_id + bytes.fromhex(nonce)
    message = device_id.encode('utf-8') + child_id.encode('utf-8') + bytes.fromhex(nonce)
    hmac_hex = hmac.new(bytes.fromhex(oob_secret), message, hashlib.sha256).hexdigest()
    
    payload = {
        "device_id": device_id,
        "child_id": child_id, 
        "nonce": nonce,
        "hmac_hex": hmac_hex
    }
    
    headers = {"Content-Type": "application/json"}
    
    print("=== Claim Endpoint Test ===")
    print(f"URL: https://ai-tiddy-bear-v-xuqy.onrender.com/api/v1/pair/claim")
    print(f"Device: {device_id}")
    print(f"Child: {child_id}")
    print(f"Nonce: {nonce} (len={len(nonce)})")
    print(f"HMAC: {hmac_hex} (len={len(hmac_hex)})")
    print()
    
    try:
        # Test endpoint availability first
        print("Testing endpoint availability...")
        response = requests.post(
            "https://ai-tiddy-bear-v-xuqy.onrender.com/api/v1/pair/claim",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 404:
            print("\n❌ Endpoint not found - router registration failed")
        elif response.status_code == 422:
            print("\n⚠️ Validation error - check field formats")
            try:
                error = response.json()
                if 'detail' in error:
                    for err in error['detail']:
                        print(f"  - {err['loc']}: {err['msg']}")
            except:
                pass
        elif response.status_code == 200:
            print("\n✅ Success!")
        else:
            print(f"\n⚠️ Unexpected status: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_claim_endpoint()