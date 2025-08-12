#!/usr/bin/env python3
"""
🔍 Test Server Endpoints
اختبار شامل لجميع endpoints السيرفر
"""
import requests
from typing import List, Tuple

def test_endpoint(url: str, method: str = "GET") -> Tuple[int, str]:
    """Test a single endpoint."""
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        else:
            response = requests.post(url, timeout=10)
        return response.status_code, response.text[:100]
    except Exception as e:
        return 0, str(e)

def main():
    """Test all known endpoints."""
    BASE_URL = "https://ai-tiddy-bear-v-xuqy.onrender.com"
    
    endpoints = [
        # Basic
        ("GET", "/", "Home page"),
        ("GET", "/docs", "FastAPI docs"),
        ("GET", "/health", "Health check"),
        
        # ESP32 Public (should work)
        ("GET", "/api/v1/esp32/config", "ESP32 config"),
        ("GET", "/api/v1/esp32/firmware", "ESP32 firmware"),
        
        # Authentication
        ("GET", "/api/auth", "Auth root"),
        ("POST", "/api/auth/login", "Login"),
        ("GET", "/api/auth/validate", "Token validate"),
        
        # Dashboard
        ("GET", "/api/dashboard", "Dashboard root"),
        ("GET", "/api/dashboard/children", "Children list"),
        
        # Core API
        ("GET", "/api/v1/core", "Core API root"),
        ("POST", "/api/v1/core/chat", "Chat endpoint"),
        
        # ESP32 Private (needs auth)
        ("GET", "/api/v1/esp32/private/metrics", "ESP32 metrics"),
        
        # Web Interface
        ("GET", "/dashboard", "Web dashboard"),
        
        # Payments
        ("GET", "/api/v1/iraqi-payments", "Iraqi payments"),
    ]
    
    print(f"🔍 Testing {len(endpoints)} endpoints on: {BASE_URL}")
    print("=" * 60)
    
    working = 0
    total = 0
    
    for method, path, description in endpoints:
        url = BASE_URL + path
        status_code, response = test_endpoint(url, method)
        total += 1
        
        if status_code == 200:
            print(f"✅ {method} {path} - {description}")
            working += 1
        elif status_code == 401:
            print(f"🔐 {method} {path} - {description} (Auth required)")
            working += 1  # This is expected
        elif status_code == 404:
            print(f"❌ {method} {path} - {description} (Not Found)")
        elif status_code == 405:
            print(f"⚠️ {method} {path} - {description} (Method not allowed)")
        elif status_code == 503:
            print(f"🚫 {method} {path} - {description} (Service unavailable)")
        else:
            print(f"❓ {method} {path} - {description} ({status_code})")
    
    print("=" * 60)
    print(f"📊 Results: {working}/{total} endpoints working")
    
    if working == total:
        print("🎉 All endpoints working perfectly!")
    elif working > total * 0.7:
        print("😊 Most endpoints working - good!")
    elif working > total * 0.3:
        print("😐 Some endpoints working - needs investigation")
    else:
        print("😟 Many endpoints broken - major issues!")

if __name__ == "__main__":
    main()