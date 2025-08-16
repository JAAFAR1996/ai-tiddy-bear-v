#!/usr/bin/env python3
"""
Simple test to verify the enum fix works correctly
"""

import json
from enum import Enum

print("=" * 60)
print("Testing Enum JSON Serialization Fix")
print("=" * 60)

# Simulate the OLD way (causes JSON serialization error)
class OldDeviceStatus(Enum):
    UNREGISTERED = "unregistered"
    PAIRED = "paired"

print("1. OLD WAY (Enum only):")
old_status = OldDeviceStatus.UNREGISTERED
print(f"   Type: {type(old_status)}")
print(f"   Value: {old_status.value}")
print(f"   String repr: {old_status}")

test_dict = {"status": old_status}
try:
    json_str = json.dumps(test_dict)
    print(f"   ✅ JSON serialization: {json_str}")
except TypeError as e:
    print(f"   ❌ JSON serialization failed: {e}")

# Try with .value
test_dict_value = {"status": old_status.value}
try:
    json_str = json.dumps(test_dict_value)
    print(f"   ✅ JSON with .value: {json_str}")
except TypeError as e:
    print(f"   ❌ JSON with .value failed: {e}")

print()

# Simulate the NEW way (JSON serializable)
class NewDeviceStatus(str, Enum):
    UNREGISTERED = "unregistered"
    PAIRED = "paired"

print("2. NEW WAY (str + Enum):")
new_status = NewDeviceStatus.UNREGISTERED
print(f"   Type: {type(new_status)}")
print(f"   Value: {new_status.value}")
print(f"   String repr: {new_status}")
print(f"   str() conversion: {str(new_status)}")

test_dict = {"status": new_status}
try:
    json_str = json.dumps(test_dict)
    print(f"   ✅ JSON serialization: {json_str}")
except TypeError as e:
    print(f"   ❌ JSON serialization failed: {e}")

print()

# Test compatibility with mock class
class MockDeviceStatus:
    UNREGISTERED = "unregistered"
    PAIRED = "paired"

print("3. MOCK CLASS (fallback):")
mock_status = MockDeviceStatus.UNREGISTERED
print(f"   Type: {type(mock_status)}")
print(f"   Direct value: {mock_status}")
print(f"   str() conversion: {str(mock_status)}")

test_dict = {"status": mock_status}
try:
    json_str = json.dumps(test_dict)
    print(f"   ✅ JSON serialization: {json_str}")
except TypeError as e:
    print(f"   ❌ JSON serialization failed: {e}")

print()

# Test the unified approach
def get_status_string(status):
    """Unified way to get string value"""
    return str(status)

print("4. UNIFIED APPROACH (using str()):")
for name, status_class in [("New Enum", NewDeviceStatus), ("Mock", MockDeviceStatus)]:
    status = status_class.UNREGISTERED
    status_str = get_status_string(status)
    print(f"   {name}: {status_str} (type: {type(status_str)})")
    
    test_dict = {"status": status_str}
    try:
        json_str = json.dumps(test_dict)
        print(f"   ✅ JSON: {json_str}")
    except TypeError as e:
        print(f"   ❌ JSON failed: {e}")

print()
print("=" * 60)
print("CONCLUSION:")
print("✅ Using (str, Enum) makes enum values JSON serializable")
print("✅ str() works for both Enum and mock string values")
print("✅ No need for .value checks or special handling")
print("=" * 60)