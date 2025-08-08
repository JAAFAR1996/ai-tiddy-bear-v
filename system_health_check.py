#!/usr/bin/env python3
"""
🧸 AI TEDDY BEAR V5 - SYSTEM HEALTH CHECK
========================================
Script to verify system health and detect potential issues.
"""

import sys
import os
import importlib
from pathlib import Path

def check_circular_imports():
    """Check for circular import issues."""
    print("🔍 Checking for circular import issues...")
    
    try:
        # Test main configuration imports (without loading actual config)
        from src.infrastructure.config.config_provider import get_config
        print("✅ Config provider import: OK")
        
        from src.infrastructure.config.config_manager_provider import get_config_manager
        print("✅ Config manager provider import: OK")
        
        # Test basic module imports 
        import src.api.config
        print("✅ API config import: OK")
        
        import src.core.models
        print("✅ Core models import: OK")
        
        print("✅ All critical imports successful - No circular import issues detected")
        return True
        
    except Exception as e:
        print(f"❌ Import error detected: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_required_files():
    """Check for required __init__.py files."""
    print("\n🔍 Checking required __init__.py files...")
    
    required_dirs = [
        "src",
        "src/api", 
        "src/core",
        "src/infrastructure",
        "src/infrastructure/config",
        "src/infrastructure/database",
        "src/infrastructure/security",
        "src/application",
        "src/adapters"
    ]
    
    missing_files = []
    for dir_path in required_dirs:
        init_file = Path(dir_path) / "__init__.py"
        if not init_file.exists():
            missing_files.append(str(init_file))
            print(f"❌ Missing: {init_file}")
        else:
            print(f"✅ Found: {init_file}")
    
    if missing_files:
        print(f"❌ Missing {len(missing_files)} __init__.py files")
        return False
    else:
        print("✅ All required __init__.py files present")
        return True

def check_config_structure():
    """Check configuration file structure."""
    print("\n🔍 Checking configuration structure...")
    
    config_files = [
        "src/infrastructure/config/production_config.py",
        "src/infrastructure/config/config_provider.py", 
        "src/infrastructure/config/config_manager_provider.py",
        "src/infrastructure/config/__init__.py"
    ]
    
    for config_file in config_files:
        if Path(config_file).exists():
            print(f"✅ Found: {config_file}")
        else:
            print(f"❌ Missing: {config_file}")
            return False
    
    print("✅ Configuration structure is correct")
    return True

def check_docker_config():
    """Check Docker configuration."""
    print("\n🔍 Checking Docker configuration...")
    
    # Check Dockerfile
    dockerfile = Path("Dockerfile")
    if dockerfile.exists():
        content = dockerfile.read_text()
        if "PYTHONPATH=" in content and "/app/src" in content:
            print("✅ Dockerfile has correct PYTHONPATH")
        else:
            print("❌ Dockerfile missing PYTHONPATH setting")
            return False
            
        if "${PORT:-8000}" in content:
            print("✅ Dockerfile uses PORT environment variable correctly")
        else:
            print("❌ Dockerfile not configured for Render PORT variable")
            return False
    else:
        print("❌ Dockerfile not found")
        return False
    
    # Check docker-entrypoint.sh
    entrypoint = Path("docker-entrypoint.sh")
    if entrypoint.exists():
        print("✅ Docker entrypoint script found")
    else:
        print("❌ Docker entrypoint script missing")
        return False
    
    print("✅ Docker configuration is correct")
    return True

def main():
    """Run all health checks."""
    print("🧸 AI TEDDY BEAR V5 - SYSTEM HEALTH CHECK")
    print("=" * 50)
    
    checks = [
        check_required_files,
        check_config_structure,
        check_circular_imports,
        check_docker_config
    ]
    
    passed = 0
    total = len(checks)
    
    for check in checks:
        if check():
            passed += 1
        print()  # Add spacing between checks
    
    print("=" * 50)
    print(f"RESULTS: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 ALL CHECKS PASSED! System is healthy.")
        return 0
    else:
        print("⚠️  Some checks failed. Review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
