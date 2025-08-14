#!/usr/bin/env python3
"""
Debug script for 422 Unprocessable Content errors on /api/v1/pair/claim endpoint

This script analyzes the ClaimRequest model validation requirements and shows
common validation failures that cause 422 errors.
"""

import re
from pydantic import BaseModel, Field, validator, ValidationError

# Reproduce the ClaimRequest model from claim_api.py
class ClaimRequest(BaseModel):
    """Device claim request with HMAC authentication"""
    device_id: str = Field(
        ..., 
        min_length=8, 
        max_length=64, 
        pattern=r'^[a-zA-Z0-9_-]+$',
        description="Unique ESP32 device identifier"
    )
    child_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r'^[a-zA-Z0-9_-]+$',
        description="Child profile identifier"
    )
    nonce: str = Field(
        ...,
        min_length=16,
        max_length=64,
        pattern=r'^[a-fA-F0-9]+$',
        description="Cryptographic nonce (hex)"
    )
    hmac_hex: str = Field(
        ...,
        pattern=r'^[0-9a-fA-F]{64}$',
        description="HMAC-SHA256 signature (64 hex chars)"
    )
    firmware_version: str = Field(
        None,
        max_length=32,
        pattern=r'^[a-zA-Z0-9._-]+$',
        description="Device firmware version"
    )

    @validator('nonce')
    def validate_nonce_format(cls, v):
        """Validate nonce is proper hex format"""
        if len(v) % 2 != 0:
            raise ValueError("Nonce must be even-length hex string")
        try:
            bytes.fromhex(v)
        except ValueError:
            raise ValueError("Nonce must be valid hex")
        return v.lower()

def test_validation_scenarios():
    """Test various validation scenarios that cause 422 errors"""
    
    print("🔍 Testing ClaimRequest validation scenarios...")
    print("=" * 60)
    
    # Test cases that would cause 422 errors
    test_cases = [
        {
            "name": "Missing required fields",
            "data": {"device_id": "test-device"},
            "expected_error": "field required"
        },
        {
            "name": "device_id too short",
            "data": {
                "device_id": "short",  # < 8 chars
                "child_id": "child123",
                "nonce": "1234567890abcdef",
                "hmac_hex": "a" * 64
            },
            "expected_error": "at least 8 characters"
        },
        {
            "name": "device_id invalid characters",
            "data": {
                "device_id": "device@123",  # Contains @
                "child_id": "child123", 
                "nonce": "1234567890abcdef",
                "hmac_hex": "a" * 64
            },
            "expected_error": "string does not match expected pattern"
        },
        {
            "name": "nonce invalid hex",
            "data": {
                "device_id": "valid-device-id",
                "child_id": "child123",
                "nonce": "GGGG567890abcdef",  # Contains invalid hex chars
                "hmac_hex": "a" * 64
            },
            "expected_error": "string does not match expected pattern"
        },
        {
            "name": "nonce odd length",
            "data": {
                "device_id": "valid-device-id",
                "child_id": "child123", 
                "nonce": "123456789abcdef",  # Odd length (15 chars)
                "hmac_hex": "a" * 64
            },
            "expected_error": "even-length hex string"
        },
        {
            "name": "hmac_hex wrong length",
            "data": {
                "device_id": "valid-device-id",
                "child_id": "child123",
                "nonce": "1234567890abcdef",
                "hmac_hex": "a" * 32  # Should be 64 chars
            },
            "expected_error": "string does not match expected pattern"
        },
        {
            "name": "Valid request",
            "data": {
                "device_id": "Teddy-ESP32-001",
                "child_id": "child123",
                "nonce": "1234567890abcdef",
                "hmac_hex": "a" * 64,
                "firmware_version": "1.0.0"
            },
            "expected_error": None
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   Data: {test_case['data']}")
        
        try:
            request = ClaimRequest(**test_case['data'])
            if test_case['expected_error']:
                print(f"   ❌ Expected error but validation passed")
            else:
                print(f"   ✅ Validation passed as expected")
                print(f"   Result: device_id={request.device_id}, nonce={request.nonce}")
        except ValidationError as e:
            if test_case['expected_error']:
                print(f"   ✅ Expected validation error:")
                for error in e.errors():
                    print(f"      - {error['msg']} (field: {error['loc']})")
            else:
                print(f"   ❌ Unexpected validation error: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")

def show_common_422_causes():
    """Show the most common causes of 422 errors"""
    print("\n🚨 COMMON 422 ERROR CAUSES:")
    print("=" * 60)
    
    causes = [
        "1. device_id less than 8 characters or contains invalid chars (only a-z, A-Z, 0-9, _, - allowed)",
        "2. child_id empty or contains invalid characters", 
        "3. nonce not valid hex string or odd length (must be even-length hex)",
        "4. hmac_hex not exactly 64 hex characters",
        "5. firmware_version contains invalid characters or too long (>32 chars)",
        "6. Missing required fields (device_id, child_id, nonce, hmac_hex)",
        "7. Extra fields not defined in the model",
        "8. Incorrect Content-Type header (must be application/json)"
    ]
    
    for cause in causes:
        print(f"   {cause}")

def generate_valid_request():
    """Generate a valid request example"""
    import secrets
    
    print("\n✅ VALID REQUEST EXAMPLE:")
    print("=" * 60)
    
    # Generate a proper nonce and HMAC
    nonce = secrets.token_hex(16)  # 32 hex chars (16 bytes)
    hmac_hex = secrets.token_hex(32)  # 64 hex chars (32 bytes)
    
    valid_request = {
        "device_id": "Teddy-ESP32-001",
        "child_id": "child_profile_123",
        "nonce": nonce,
        "hmac_hex": hmac_hex,
        "firmware_version": "1.2.3"
    }
    
    print("Valid JSON payload:")
    import json
    print(json.dumps(valid_request, indent=2))
    
    # Test it validates
    try:
        request = ClaimRequest(**valid_request)
        print(f"\n✅ Validation successful!")
        print(f"   Device ID: {request.device_id}")
        print(f"   Child ID: {request.child_id}")
        print(f"   Nonce: {request.nonce}")
        print(f"   HMAC: {request.hmac_hex[:16]}...")
    except ValidationError as e:
        print(f"\n❌ Validation failed: {e}")

if __name__ == "__main__":
    test_validation_scenarios()
    show_common_422_causes()
    generate_valid_request()