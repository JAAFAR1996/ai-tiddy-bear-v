#!/usr/bin/env python3
"""
ESP32 Authentication Test with Real Secret
==========================================
"""

import hashlib
import hmac
import secrets
import requests
import json

# المفتاح المعرّف في Render
ESP32_SHARED_SECRET = "46a1d7e1d6719f4a74404a01a7a18bd5734c824b461708a5123a5f42618c6bc5"

# معلومات الجهاز
DEVICE_ID = "Teddy-ESP32-001"
CHILD_ID = "test-child-001"  # للاختبار
SERVER_URL = "https://ai-tiddy-bear-v-xuqy.onrender.com"

def generate_device_oob_secret(device_id: str) -> str:
    """Generate OOB secret for device (same algorithm as server)"""
    salt = "ai-teddy-bear-oob-secret-v1"
    hash_input = f"{device_id}:{salt}".encode('utf-8')
    
    # First SHA256
    device_hash = hashlib.sha256(hash_input).hexdigest()
    
    # Second SHA256
    final_hash = hashlib.sha256((device_hash + salt).encode('utf-8')).hexdigest()
    
    return final_hash.upper()

def calculate_hmac(device_id: str, child_id: str, nonce_hex: str, oob_secret_hex: str) -> str:
    """Calculate HMAC for authentication"""
    # Convert from hex
    oob_secret_bytes = bytes.fromhex(oob_secret_hex)
    nonce_bytes = bytes.fromhex(nonce_hex)
    
    # Create HMAC
    mac = hmac.new(oob_secret_bytes, digestmod=hashlib.sha256)
    mac.update(device_id.encode('utf-8'))
    mac.update(child_id.encode('utf-8'))
    mac.update(nonce_bytes)
    
    return mac.hexdigest()

def test_claim_device():
    """Test device claiming with real authentication"""
    
    print("=" * 60)
    print("ESP32 AUTHENTICATION TEST")
    print("=" * 60)
    print(f"Server: {SERVER_URL}")
    print(f"Device ID: {DEVICE_ID}")
    print(f"ESP32_SHARED_SECRET: {ESP32_SHARED_SECRET[:16]}...")
    print()
    
    # Step 1: Generate OOB Secret
    oob_secret = generate_device_oob_secret(DEVICE_ID)
    print(f"1. OOB Secret Generated:")
    print(f"   {oob_secret}")
    print(f"   Length: {len(oob_secret)} chars")
    print()
    
    # Step 2: Generate Nonce
    nonce_hex = secrets.token_hex(16)  # 32 hex chars
    print(f"2. Nonce Generated:")
    print(f"   {nonce_hex}")
    print()
    
    # Step 3: Calculate HMAC
    hmac_hex = calculate_hmac(DEVICE_ID, CHILD_ID, nonce_hex, oob_secret)
    print(f"3. HMAC Calculated:")
    print(f"   {hmac_hex}")
    print()
    
    # Step 4: Create Request Payload
    payload = {
        "device_id": DEVICE_ID,
        "child_id": CHILD_ID,
        "nonce": nonce_hex,
        "hmac_hex": hmac_hex,
        "firmware_version": "1.2.0"
    }
    
    print("4. Request Payload:")
    print(json.dumps(payload, indent=2))
    print()
    
    # Step 5: Send Request
    print("5. Sending Claim Request...")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ESP32-TeddyBear/1.2.0"
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/api/v1/pair/claim",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        print("   Response:")
        
        try:
            response_data = response.json()
            print(json.dumps(response_data, indent=2))
        except:
            print(response.text)
            
        print()
        
        # Interpret result
        if response.status_code == 200:
            print("✅ SUCCESS! Device authenticated and paired")
            if 'access_token' in response_data:
                print(f"   Access Token: {response_data['access_token'][:50]}...")
        elif response.status_code == 401:
            print("❌ AUTHENTICATION FAILED - Invalid HMAC")
        elif response.status_code == 404:
            print("⚠️ CHILD NOT FOUND - Device auth works but child not registered")
        elif response.status_code == 422:
            print("❌ VALIDATION ERROR - Check request format")
        else:
            print(f"❓ UNEXPECTED STATUS: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
    
    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    
    # Return OOB secret for ESP32 code
    return oob_secret

if __name__ == "__main__":
    oob_secret = test_claim_device()
    
    print("\n📝 ESP32 Arduino Code Configuration:")
    print("```c")
    print(f'const char* DEVICE_ID = "{DEVICE_ID}";')
    print(f'const char* OOB_SECRET = "{oob_secret}";')
    print(f'const char* SERVER_URL = "{SERVER_URL}";')
    print("```")