#!/usr/bin/env python3
"""
Local Server Test - Check if fixes work correctly
"""
import os
import sys
import asyncio
import traceback

# Set environment variables for local testing
os.environ['ENVIRONMENT'] = 'development'  # Use development mode to avoid production checks
os.environ['DEBUG'] = 'true'
os.environ['HOST'] = '127.0.0.1'
os.environ['PORT'] = '8000'

# Mock database URL for testing (won't actually connect)
os.environ['DATABASE_URL'] = 'postgresql://localhost_dev:localpass@localhost:5432/localdb'
os.environ['REDIS_URL'] = 'redis://localhost:6379'
# Generate secure random keys for local testing
os.environ['SECRET_KEY'] = 'development_secure_key_12345678901234567890123456789012'
os.environ['JWT_SECRET_KEY'] = 'jwt_development_secure_key_12345678901234567890123456789012'
os.environ['OPENAI_API_KEY'] = 'sk-development_key_for_local_usage_only'
os.environ['COPPA_ENCRYPTION_KEY'] = 'coppa_dev_key_12345678901234567890123456789012'
os.environ['CORS_ALLOWED_ORIGINS'] = '["http://localhost:3000", "http://127.0.0.1:3000"]'
os.environ['PARENT_NOTIFICATION_EMAIL'] = 'dev@localhost.com'

# Skip tests during import
os.environ['PYTEST_CURRENT_TEST'] = 'test_local_server.py'

def test_imports():
    """Test that all critical imports work"""
    print("=== Testing Imports ===")
    
    try:
        print("1. Testing dependencies import...")
        from src.application.dependencies import AdminSecurityDep, TokenManagerDep
        print("   SUCCESS: Dependencies imported")
        
        print("2. Testing admin_security import...")
        from src.infrastructure.security.admin_security import AdminSecurityManager
        print("   SUCCESS: AdminSecurityManager imported")
        
        print("3. Testing auth import...")
        from src.infrastructure.security.auth import TokenManager
        print("   SUCCESS: TokenManager imported")
        
        print("4. Testing main import...")
        from src.main import app  # This should work without starting the server
        print("   SUCCESS: FastAPI app imported")
        
        return True
        
    except Exception as e:
        print(f"   ERROR: {e}")
        traceback.print_exc()
        return False

def test_dependency_creation():
    """Test that dependencies can be created properly"""
    print("\n=== Testing Dependency Creation ===")
    
    try:
        print("1. Testing get_admin_security_manager function...")
        from src.application.dependencies import get_admin_security_manager
        
        # Create a mock TokenManager for testing
        class MockTokenManager:
            def __init__(self):
                self.config = None
                pass
        
        mock_tm = MockTokenManager()
        admin_mgr = get_admin_security_manager(mock_tm)
        print(f"   SUCCESS: AdminSecurityManager created: {type(admin_mgr)}")
        
        return True
        
    except Exception as e:
        print(f"   ERROR: {e}")
        traceback.print_exc()
        return False

async def test_app_creation():
    """Test that the app can be created without errors"""
    print("\n=== Testing App Creation ===")
    
    try:
        # Import the app
        from src.main import app
        print("   SUCCESS: FastAPI app instance created")
        
        # Check that the app has the expected attributes
        if hasattr(app, 'routes'):
            print(f"   SUCCESS: App has routes ({len(app.routes)} routes)")
        else:
            print("   WARNING: App has no routes attribute")
            
        return True
        
    except Exception as e:
        print(f"   ERROR: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all local tests"""
    print("AI Teddy Bear - Local Server Test")
    print("=" * 50)
    
    results = []
    
    # Test imports
    results.append(test_imports())
    
    # Test dependency creation
    results.append(test_dependency_creation())
    
    # Test app creation
    results.append(asyncio.run(test_app_creation()))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Results:")
    
    passed = sum(results)
    total = len(results)
    
    print(f"   Passed: {passed}/{total}")
    
    if passed == total:
        print("   STATUS: ALL TESTS PASSED!")
        print("   The fixes are working correctly.")
        return 0
    else:
        print("   STATUS: SOME TESTS FAILED!")
        print("   There are still issues to resolve.")
        return 1

if __name__ == '__main__':
    sys.exit(main())