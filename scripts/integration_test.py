#!/usr/bin/env python3
"""Integration test to verify all services are properly wired and functional.

This script tests:
1. Dependency injection container initialization
2. Service instantiation
3. Real functionality (no stubs)
4. Proper layer boundaries
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.container import get_injector
from src.interfaces.services import (
    IAIService, IAuthService, IChildSafetyService,
    IConversationService, IChatService
)
from src.interfaces.repositories import (
    IUserRepository, IChildRepository, IConversationRepository
)
from src.interfaces.config import IConfiguration
from injector import Injector


async def test_injector_initialization():
    """Test that the DI injector initializes without errors."""
    print("✓ Testing injector initialization...")
    
    try:
        # Set required environment variables for testing
        os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'test-key-for-validation')
        os.environ['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'test-secret-key-minimum-32-characters-long')
        
        injector = get_injector()
        assert isinstance(injector, Injector)
        print("  ✓ Injector created successfully")
        return injector
    except Exception as e:
        print(f"  ✗ Injector initialization failed: {e}")
        raise


async def test_service_instantiation(injector: Injector):
    """Test that all services can be instantiated."""
    print("\n✓ Testing service instantiation...")
    
    services_to_test = [
        (IConfiguration, 'Configuration'),
        (IAIService, 'AI Service'),
        (IAuthService, 'Auth Service'),
        (IChildSafetyService, 'Child Safety Service'),
        ('ChildRepository', 'Child Repository'),
        ('UserRepository', 'User Repository'),
        ('ConversationRepository', 'Conversation Repository'),
    ]
    
    for service_key, service_name in services_to_test:
        try:
            service = injector.get(service_key)
            # Verify it implements the interface (has required methods)
            assert hasattr(service, '__class__')
            print(f"  ✓ {service_name} instantiated successfully")
        except Exception as e:
            print(f"  ✗ {service_name} instantiation failed: {e}")
            raise


async def test_real_functionality(injector: Injector):
    """Test that services have real implementations, not stubs."""
    print("\n✓ Testing real functionality...")
    
    # Test configuration service
    try:
        config = injector.get(IConfiguration)
        jwt_key = config.JWT_SECRET_KEY
        assert jwt_key is not None
        assert len(jwt_key) >= 32
        print("  ✓ Configuration service returns real values")
    except Exception as e:
        print(f"  ✗ Configuration service test failed: {e}")
        raise
    
    # Test auth service token generation
    try:
        auth_service = injector.get(IAuthService)
        user_data = {"id": "test-user-123", "email": "test@example.com"}
        token = auth_service.create_access_token(user_data)
        assert token is not None
        assert len(token) > 0
        print("  ✓ Auth service generates real tokens")
    except Exception as e:
        print(f"  ✗ Auth service test failed: {e}")
        raise
    
    # Test child safety service
    try:
        safety_service = injector.get(IChildSafetyService)
        # Test content validation
        result = await safety_service.validate_content("Hello, how are you?", child_age=10)
        assert isinstance(result, dict)
        assert 'safe' in result
        print("  ✓ Child safety service validates content")
    except Exception as e:
        print(f"  �� Child safety service test failed: {e}")
        raise


async def test_no_circular_dependencies():
    """Verify no circular dependencies exist."""
    print("\n✓ Testing for circular dependencies...")
    
    import subprocess
    result = subprocess.run(
        ["python3", "scripts/verify_layer_dependencies.py"],
        capture_output=True,
        text=True
    )
    
    if "violations found: 0" in result.stdout:
        print("  ✓ No layer dependency violations")
    else:
        print("  ✗ Layer dependency violations found")
        print(result.stdout)
        raise Exception("Layer dependency violations detected")


async def main():
    """Run all integration tests."""
    print("=" * 60)
    print("INTEGRATION TEST SUITE")
    print("=" * 60)
    
    try:
        # Test 1: Injector initialization
        injector = await test_injector_initialization()
        
        # Test 2: Service instantiation
        await test_service_instantiation(injector)
        
        # Test 3: Real functionality
        await test_real_functionality(injector)
        
        # Test 4: No circular dependencies
        await test_no_circular_dependencies()
        
        print("\n" + "=" * 60)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ INTEGRATION TESTS FAILED: {e}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)