#!/usr/bin/env python3

import json
import base64
import time
from datetime import datetime

# JWT token from ESP32 logs
jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZXZpY2U6dGVkZHktZXNwMzItY2NkYmE3OTViYWE0OmNoaWxkOmNoaWxkLXVua25vd24iLCJkZXZpY2VfaWQiOiJ0ZWRkeS1lc3AzMi1jY2RiYTc5NWJhYTQiLCJjaGlsZF9pZCI6ImNoaWxkLXVua25vd24iLCJzZXNzaW9uX2lkIjoiNzM1NTE5ZTgtNjc3NS00ZDlhLTgxMWItMDlkYjcwNTgyOGRhIiwidHlwZSI6ImRldmljZV9hY2Nlc3MiLCJhdWQiOiJ0ZWRkeS1hcGkiLCJpc3MiOiJ0ZWRkeS1kZXZpY2Utc3lzdGVtIiwiaWF0IjoxNzU4NzEyMzU1LCJleHAiOjE3NTg3MTU5NTV9.pGqcybVjLXM-kzuPW3o7OOuVVsq9Hw5UkWPW1hVQkrM"

# Decode the JWT payload (without verification)
try:
    # Split the JWT into parts
    header, payload, signature = jwt_token.split('.')
    
    # Add padding if needed
    payload += '=' * (4 - len(payload) % 4)
    
    # Decode the payload
    decoded_payload = base64.urlsafe_b64decode(payload)
    payload_json = json.loads(decoded_payload)
    
    print("JWT Payload:")
    print(json.dumps(payload_json, indent=2))
    
    # Check expiry
    exp_timestamp = payload_json.get('exp')
    iat_timestamp = payload_json.get('iat')
    current_timestamp = int(time.time())
    
    print(f"\nTimestamp Analysis:")
    print(f"Current time: {current_timestamp} ({datetime.fromtimestamp(current_timestamp)})")
    print(f"Token issued at (iat): {iat_timestamp} ({datetime.fromtimestamp(iat_timestamp)})")
    print(f"Token expires at (exp): {exp_timestamp} ({datetime.fromtimestamp(exp_timestamp)})")
    
    if current_timestamp > exp_timestamp:
        print(f"❌ Token is EXPIRED (expired {current_timestamp - exp_timestamp} seconds ago)")
    else:
        print(f"✅ Token is VALID (expires in {exp_timestamp - current_timestamp} seconds)")
        
except Exception as e:
    print(f"Error decoding JWT: {e}")