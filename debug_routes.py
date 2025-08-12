#!/usr/bin/env python3
"""
🔍 Debug Routes Registration
تشخيص مشكلة Route Registration في السيرفر
"""

import sys
import traceback
from pathlib import Path

# Add project root to Python path  
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_imports():
    """Test all critical imports."""
    print("🔍 Testing Route Imports...")
    
    imports = [
        ("src.adapters.auth_routes", "router"),
        ("src.adapters.dashboard_routes", "router"),
        ("src.adapters.api_routes", "router"),
        ("src.adapters.esp32_router", "esp32_public"),
        ("src.adapters.esp32_router", "esp32_private"),
        ("src.adapters.esp32_websocket_router", "esp32_router"),
        ("src.adapters.web", "router"),
    ]
    
    results = []
    
    for module_name, router_name in imports:
        try:
            module = __import__(module_name, fromlist=[router_name])
            router = getattr(module, router_name)
            print(f"✅ {module_name}.{router_name}")
            results.append((module_name, router_name, True, None))
        except Exception as e:
            print(f"❌ {module_name}.{router_name}: {e}")
            results.append((module_name, router_name, False, str(e)))
            
    return results

def test_database_connection():
    """Test database connection."""
    print("\n🔍 Testing Database Connection...")
    
    try:
        from src.infrastructure.database.database_manager import get_db
        print("✅ Database manager imports successfully")
        return True
    except Exception as e:
        print(f"❌ Database manager import failed: {e}")
        traceback.print_exc()
        return False

def test_config():
    """Test configuration."""
    print("\n🔍 Testing Configuration...")
    
    try:
        from src.infrastructure.config.production_config import load_config
        config = load_config()
        print("✅ Configuration loads successfully")
        return True
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        traceback.print_exc()
        return False

def test_route_manager():
    """Test route manager."""
    print("\n🔍 Testing Route Manager...")
    
    try:
        from src.infrastructure.routing.route_manager import RouteManager, register_all_routers
        print("✅ Route Manager imports successfully")
        return True
    except Exception as e:
        print(f"❌ Route Manager import failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Main diagnosis function."""
    print("🧸 AI Teddy Bear Route Debug Tool")
    print("=" * 40)
    
    all_good = True
    
    # Test imports
    import_results = test_imports()
    failed_imports = [r for r in import_results if not r[2]]
    if failed_imports:
        all_good = False
        
    # Test database
    if not test_database_connection():
        all_good = False
        
    # Test config
    if not test_config():
        all_good = False
        
    # Test route manager
    if not test_route_manager():
        all_good = False
        
    print("\n" + "=" * 40)
    if all_good:
        print("🎉 All tests passed! Routes should work.")
    else:
        print("🚨 Issues found that prevent route registration!")
        print("\nFailed imports:")
        for module_name, router_name, success, error in import_results:
            if not success:
                print(f"  ❌ {module_name}.{router_name}: {error}")
                
    print(f"\nThis explains why the server at https://ai-tiddy-bear-v-xuqy.onrender.com")
    print(f"returns 404 for all API endpoints!")

if __name__ == "__main__":
    main()