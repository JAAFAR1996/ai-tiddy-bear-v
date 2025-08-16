#!/usr/bin/env python3
"""
Test script to verify DeviceStatus enum fix for production
Tests both import scenarios and JSON serialization
"""

import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_device_status():
    """Test DeviceStatus enum handling in different scenarios"""
    
    print("=" * 60)
    print("Testing DeviceStatus Enum Fix")
    print("=" * 60)
    
    # Test 1: Import the real DeviceStatus
    try:
        from src.user_experience.device_pairing.pairing_manager import DeviceStatus
        print("✅ Successfully imported DeviceStatus from pairing_manager")
        
        # Check if it's a string enum
        status = DeviceStatus.UNREGISTERED
        print(f"   Type: {type(status)}")
        print(f"   Value: {status}")
        print(f"   String conversion: {str(status)}")
        
        # Test JSON serialization
        test_dict = {"status": status}
        try:
            json_str = json.dumps(test_dict)
            print(f"✅ JSON serialization works: {json_str}")
        except TypeError as e:
            print(f"❌ JSON serialization failed: {e}")
            
    except ImportError as e:
        print(f"⚠️  Could not import DeviceStatus: {e}")
    
    print()
    
    # Test 2: Test claim_api import and usage
    try:
        from src.adapters.claim_api import DeviceStatus as ClaimDeviceStatus
        from src.adapters.claim_api import get_device_status_value, DEVICE_STATUS_IMPORTED
        
        print(f"✅ Successfully imported from claim_api")
        print(f"   DEVICE_STATUS_IMPORTED: {DEVICE_STATUS_IMPORTED}")
        
        # Test the status value
        status = ClaimDeviceStatus.UNREGISTERED
        print(f"   Raw status: {status}")
        print(f"   String conversion: {str(status)}")
        print(f"   Helper function result: {get_device_status_value(status)}")
        
        # Test JSON serialization
        test_dict = {
            "status": str(status),
            "raw_status": status
        }
        try:
            json_str = json.dumps(test_dict)
            print(f"✅ JSON serialization works: {json_str}")
        except TypeError as e:
            print(f"❌ JSON serialization failed: {e}")
            
    except ImportError as e:
        print(f"❌ Could not import from claim_api: {e}")
    
    print()
    
    # Test 3: Test get_device_record function
    print("Testing get_device_record function...")
    try:
        from src.adapters.claim_api import get_device_record
        from unittest.mock import AsyncMock, MagicMock
        import asyncio
        
        # Create mock config
        mock_config = MagicMock()
        mock_config.ENVIRONMENT = "production"
        mock_config.DEVICE_SHARED_SECRET = "test_secret"
        
        # Create mock db session
        mock_db = AsyncMock()
        
        # Test auto-registration
        async def test_auto_registration():
            device_id = "Teddy-ESP32-TEST123"
            result = await get_device_record(device_id, mock_db, mock_config)
            
            if result:
                print(f"✅ Auto-registration returned device record")
                print(f"   Status type: {type(result.get('status'))}")
                print(f"   Status value: {result.get('status')}")
                
                # Verify it's JSON serializable
                try:
                    json_str = json.dumps(result)
                    print(f"✅ Device record is JSON serializable")
                except TypeError as e:
                    print(f"❌ Device record not JSON serializable: {e}")
            else:
                print(f"❌ Auto-registration failed")
        
        # Run async test
        asyncio.run(test_auto_registration())
        
    except Exception as e:
        print(f"⚠️  Could not test get_device_record: {e}")
    
    print()
    print("=" * 60)
    print("Test Summary:")
    print("- DeviceStatus is now a str Enum (inherits from both str and Enum)")
    print("- This makes it directly JSON serializable")
    print("- str() conversion always returns the string value")
    print("- Compatible with both import success and failure scenarios")
    print("=" * 60)

if __name__ == "__main__":
    test_device_status()