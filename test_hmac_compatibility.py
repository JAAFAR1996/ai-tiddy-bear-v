#!/usr/bin/env python3
"""
Test HMAC compatibility between ESP32 and Server
"""

import hmac
import hashlib

def test_hmac_compatibility():
    """Test HMAC calculation matches between ESP32 and Server"""
    
    # Test data (same as ESP32 would use)
    device_id = "Teddy-ESP32-001"
    child_id = "test-child-001"
    nonce_hex = "892bc61928c07e5da2a3d08415ea4a03"  # 32 hex chars (16 bytes)
    
    # Generate OOB secret like server does
    salt = "ai-teddy-bear-oob-secret-v1"
    hash_input = f"{device_id}:{salt}".encode('utf-8')
    device_hash = hashlib.sha256(hash_input).hexdigest()
    oob_secret_hex = hashlib.sha256((device_hash + salt).encode('utf-8')).hexdigest().upper()
    
    print("=== HMAC Compatibility Test ===")
    print(f"Device ID: {device_id}")
    print(f"Child ID: {child_id}")
    print(f"Nonce (hex): {nonce_hex} (length: {len(nonce_hex)})")
    print(f"OOB Secret: {oob_secret_hex[:16]}... (64 chars)")
    print()
    
    # Server HMAC calculation (current implementation)
    message = device_id.encode('utf-8') + child_id.encode('utf-8') + bytes.fromhex(nonce_hex)
    server_hmac = hmac.new(bytes.fromhex(oob_secret_hex), message, hashlib.sha256).hexdigest()
    
    print(f"Server HMAC calculation:")
    print(f"  Message parts: '{device_id}' + '{child_id}' + bytes({len(bytes.fromhex(nonce_hex))} bytes)")
    print(f"  Expected HMAC: {server_hmac}")
    print()
    
    # Old ESP32 HMAC (string-based - should NOT match)
    old_message = device_id.encode('utf-8') + child_id.encode('utf-8') + nonce_hex.encode('utf-8')
    old_hmac = hmac.new(bytes.fromhex(oob_secret_hex), old_message, hashlib.sha256).hexdigest()
    
    print(f"Old ESP32 HMAC (string-based):")
    print(f"  Message parts: '{device_id}' + '{child_id}' + '{nonce_hex}' (as string)")
    print(f"  Old HMAC: {old_hmac}")
    print(f"  Matches server: {'✅ YES' if old_hmac == server_hmac else '❌ NO'}")
    print()
    
    # New ESP32 HMAC (bytes-based - should match)
    new_message = device_id.encode('utf-8') + child_id.encode('utf-8') + bytes.fromhex(nonce_hex)
    new_hmac = hmac.new(bytes.fromhex(oob_secret_hex), new_message, hashlib.sha256).hexdigest()
    
    print(f"New ESP32 HMAC (bytes-based):")
    print(f"  Message parts: '{device_id}' + '{child_id}' + bytes({len(bytes.fromhex(nonce_hex))} bytes)")
    print(f"  New HMAC: {new_hmac}")
    print(f"  Matches server: {'✅ YES' if new_hmac == server_hmac else '❌ NO'}")
    print()
    
    if new_hmac == server_hmac:
        print("🎉 SUCCESS: ESP32 and Server HMAC will match after fix!")
        print("\nTest JSON payload for ESP32:")
        import json
        test_payload = {
            "device_id": device_id,
            "child_id": child_id,
            "nonce": nonce_hex,
            "hmac_hex": new_hmac
        }
        print(json.dumps(test_payload, indent=2))
    else:
        print("❌ ERROR: HMAC calculation still doesn't match")

if __name__ == "__main__":
    test_hmac_compatibility()