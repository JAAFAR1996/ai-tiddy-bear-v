#!/usr/bin/env python3

import jwt
import time
import os

# Device ID from ESP32 logs
device_id = "teddy-esp32-ccdba795baa4"

# JWT secret from environment
secret = "mJx0NIMiJ14DyPRmpY7UD0EgTY77T3gvFa*%zTsIPqVu2e-IH_vrb=TTYQHNnWjAvyCd*FS7"

# Create fresh token
current_time = int(time.time())
token_payload = {
    "sub": f"device:{device_id}:child:child-unknown",
    "device_id": device_id,
    "child_id": "child-unknown",
    "session_id": f"fresh-{current_time}",
    "type": "device_access",
    "aud": "teddy-api", 
    "iss": "teddy-device-system",
    "iat": current_time,
    "exp": current_time + (24 * 60 * 60)  # 24 hours
}

# Generate token
fresh_token = jwt.encode(token_payload, secret, algorithm="HS256")

print(f"Fresh JWT Token for {device_id}:")
print(f"Token: {fresh_token}")
print(f"Expires: {token_payload['exp']} ({time.ctime(token_payload['exp'])})")
print(f"Valid for: 24 hours")

# Test WebSocket URL
ws_url = f"ws://192.168.0.133:80/ws/esp32/connect?device_id={device_id}&child_id=child-unknown&child_name=Friend&child_age=7&token={fresh_token}"
print(f"\nWebSocket URL:")
print(ws_url)