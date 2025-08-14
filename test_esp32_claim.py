#!/usr/bin/env python3
import requests
import hashlib
import hmac
import secrets
import json

BASE_URL = "http://127.0.0.1:8000"

def generate_device_oob_secret(device_id: str) -> str:
    salt = "ai-teddy-bear-oob-secret-v1"
    hash_input = f"{device_id}:{salt}".encode('utf-8')
    
    device_hash = hashlib.sha256(hash_input).hexdigest()
    final_hash = hashlib.sha256((device_hash + salt).encode('utf-8')).hexdigest()
    
    return final_hash.upper()

def generate_test_hmac(device_id: str, child_id: str, nonce: str, oob_secret: str) -> str:
    oob_secret_bytes = bytes.fromhex(oob_secret)
    mac = hmac.new(oob_secret_bytes, digestmod=hashlib.sha256)
    
    mac.update(device_id.encode('utf-8'))
    mac.update(child_id.encode('utf-8'))
    mac.update(bytes.fromhex(nonce))
    
    return mac.hexdigest()

def test_claim():
    print("Testing ESP32 Device Claim")
    print("=" * 40)
    
    device_id = "Teddy-ESP32-TEST001"
    child_id = "test-child-123"
    nonce = secrets.token_hex(16)
    
    oob_secret = generate_device_oob_secret(device_id)
    hmac_signature = generate_test_hmac(device_id, child_id, nonce, oob_secret)
    
    payload = {
        "device_id": device_id,
        "child_id": child_id,
        "nonce": nonce,
        "hmac_hex": hmac_signature,
        "firmware_version": "1.2.1"
    }
    
    print(f"Device ID: {device_id}")
    print(f"Child ID: {child_id}")
    print(f"Nonce: {nonce[:16]}...")
    print(f"HMAC: {hmac_signature[:16]}...")
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/pair/claim",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS: Device claimed!")
            print(f"Access Token: {data.get('access_token', '')[:20]}...")
            print(f"Session ID: {data.get('device_session_id', 'N/A')}")
            print(f"Expires In: {data.get('expires_in', 'N/A')} seconds")
        elif response.status_code == 404:
            print("EXPECTED: Child profile not found (normal in test environment)")
        elif response.status_code == 503:
            print("WARNING: Service still initializing")
        else:
            print(f"ERROR: {response.text}")
            
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_claim()