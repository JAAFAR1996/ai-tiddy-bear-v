#!/usr/bin/env python3

import jwt
import time
import os
from datetime import datetime, timedelta

def generate_permanent_jwt_token():
    """Generate a permanent JWT token for ESP32 without expiry"""
    
    # Device info
    device_id = "teddy-esp32-ccdba795baa4"
    child_id = "child-unknown"
    
    # JWT secret from environment
    secret = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-here-make-it-long-and-random-for-production")
    
    # Current timestamp
    current_time = int(time.time())
    
    # JWT payload WITHOUT expiry
    payload = {
        "sub": f"device:{device_id}:child:{child_id}",
        "device_id": device_id,
        "child_id": child_id,
        "session_id": f"permanent-{current_time}",
        "type": "device_access",
        "aud": "teddy-api",
        "iss": "teddy-device-system",
        "iat": current_time,
        # NO "exp" field = permanent token
    }
    
    # Generate JWT token
    token = jwt.encode(payload, secret, algorithm="HS256")
    
    print("=== PERMANENT JWT TOKEN GENERATED ===")
    print(f"Device ID: {device_id}")
    print(f"Child ID: {child_id}")
    print(f"Generated at: {datetime.fromtimestamp(current_time)}")
    print(f"Expires: NEVER (permanent)")
    print()
    print("JWT Token:")
    print(token)
    print()
    print("WebSocket URL:")
    print(f"ws://192.168.0.133:80/ws/esp32/connect?device_id={device_id}&child_id={child_id}&child_name=Friend&child_age=7&token={token}")
    print()
    
    # Verify token
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_exp": False, "verify_aud": False})
        print("Token verification: SUCCESS")
        print(f"Decoded payload: {decoded}")
    except Exception as e:
        print(f"Token verification failed: {e}")
    
    return token

if __name__ == "__main__":
    generate_permanent_jwt_token()