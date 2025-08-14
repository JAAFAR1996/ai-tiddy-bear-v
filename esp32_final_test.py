#!/usr/bin/env python3
import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def final_test():
    print("ESP32 Final Test")
    print("=" * 40)
    print(f"Server: {BASE_URL}")
    print()
    
    session = requests.Session()
    session.timeout = 15
    
    tests = [
        ("Health", "/health"),
        ("ESP32 Config", "/api/v1/esp32/config"),
        ("ESP32 Firmware", "/api/v1/esp32/firmware"),
        ("ESP32 Metrics", "/api/v1/esp32/metrics"),
        ("Routes Health", "/routes-health"),
    ]
    
    results = []
    
    for name, path in tests:
        print(f"Testing {name}...")
        
        try:
            response = session.get(f"{BASE_URL}{path}")
            
            if 200 <= response.status_code < 400:
                print(f"   PASS - {response.status_code}")
                success = True
            elif response.status_code == 401:
                print(f"   AUTH_REQUIRED - {response.status_code}")
                success = True  # Expected
            else:
                print(f"   FAIL - {response.status_code}")
                success = False
            
            results.append({"name": name, "success": success})
            
        except Exception as e:
            print(f"   ERROR - {str(e)[:30]}...")
            results.append({"name": name, "success": False})
    
    print()
    print("Summary:")
    print("-" * 20)
    
    working = sum(1 for r in results if r["success"])
    total = len(results)
    
    for result in results:
        status = "PASS" if result["success"] else "FAIL"
        print(f"   {status} - {result['name']}")
    
    print()
    print(f"Result: {working}/{total} endpoints working")
    
    if working == total:
        print("SUCCESS: All ESP32 endpoints working!")
        return 0
    elif working >= 3:
        print("PARTIAL: Most endpoints working")
        return 1
    else:
        print("FAILURE: Multiple endpoints failing")
        return 2

if __name__ == "__main__":
    sys.exit(final_test())