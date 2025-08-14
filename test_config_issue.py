#!/usr/bin/env python3
"""
Test configuration issue reproduction
"""

import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, '.')

async def reproduce_config_error():
    """Reproduce the exact configuration error from the claim endpoint."""
    
    try:
        print("=== Testing configuration issue reproduction ===")
        
        # Step 1: Load configuration the same way main.py does
        print("1. Loading config via load_config()...")
        from src.infrastructure.config.production_config import load_config
        config = load_config()
        print(f"   OK Config loaded successfully: {type(config)}")
        
        # Step 2: Test storing in mock app.state
        print("2. Storing config in mock app.state...")
        class MockState:
            def __init__(self):
                self.config = config
        
        class MockApp:
            def __init__(self):
                self.state = MockState()
        
        class MockRequest:
            def __init__(self):
                self.app = MockApp()
        
        mock_request = MockRequest()
        print(f"   OK Config stored in app.state: {type(mock_request.app.state.config)}")
        
        # Step 3: Test get_config_from_state dependency
        print("3. Testing get_config_from_state...")
        from src.application.dependencies import get_config_from_state
        retrieved_config = get_config_from_state(mock_request)
        print(f"   OK Config retrieved via dependency: {type(retrieved_config)}")
        
        # Step 4: Test JWT_SECRET_KEY access (the line that fails in claim endpoint)
        print("4. Testing JWT_SECRET_KEY access...")
        jwt_secret = retrieved_config.JWT_SECRET_KEY
        print(f"   OK JWT_SECRET_KEY access successful: {jwt_secret[:10]}...")
        
        # Step 5: Test SimpleTokenManager creation (exact code from claim_api.py:84)
        print("5. Testing SimpleTokenManager creation (exact claim_api.py line)...")
        class SimpleTokenManager:
            def __init__(self, secret: str, algorithm: str = "HS256"):
                self.secret = secret
                self.algorithm = algorithm
        
        token_manager = SimpleTokenManager(secret=retrieved_config.JWT_SECRET_KEY, algorithm="HS256")
        print(f"   OK SimpleTokenManager created successfully: {type(token_manager)}")
        
        # Step 6: Test if there are any property accessors or getters that might fail
        print("6. Testing all config attribute accesses...")
        test_attrs = ['JWT_SECRET_KEY', 'SECRET_KEY', 'ENVIRONMENT', 'DATABASE_URL', 'REDIS_URL']
        for attr in test_attrs:
            try:
                value = getattr(retrieved_config, attr)
                print(f"   OK {attr}: accessible")
            except Exception as e:
                print(f"   FAIL {attr}: FAILED - {e}")
                return False
        
        print("\nSUCCESS: All configuration access tests PASSED!")
        print("   The configuration system is working correctly.")
        print("   The error might be in a different part of the request flow.")
        return True
        
    except Exception as e:
        print(f"\nFAILED: Configuration error reproduced: {e}")
        print(f"   Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(reproduce_config_error())
    sys.exit(0 if result else 1)