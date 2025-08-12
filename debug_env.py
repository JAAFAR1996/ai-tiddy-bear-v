#!/usr/bin/env python3
"""
Debug Environment Variables on Production Server
"""
import os
import sys

def check_env_vars():
    """Check critical environment variables."""
    critical_vars = [
        "DATABASE_URL",
        "REDIS_URL", 
        "OPENAI_API_KEY",
        "ENVIRONMENT",
        "ELEVENLABS_API_KEY",
        "ESP32_SHARED_SECRET"
    ]
    
    print("🔍 Environment Variables Check:")
    print("=" * 50)
    
    for var in critical_vars:
        value = os.environ.get(var)
        if value:
            # Mask sensitive data
            if "API_KEY" in var or "SECRET" in var:
                masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
                print(f"✅ {var}: {masked}")
            elif "URL" in var:
                print(f"✅ {var}: {value[:20]}...")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT SET")
    
    print("\n🐍 Python Environment:")
    print(f"  Python Version: {sys.version}")
    print(f"  Working Directory: {os.getcwd()}")
    print(f"  PYTHONPATH: {os.environ.get('PYTHONPATH', 'NOT SET')}")

if __name__ == "__main__":
    check_env_vars()