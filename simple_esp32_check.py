#!/usr/bin/env python3
import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def check_esp32():
    print("AI Teddy Bear - ESP32 Check")
    print("=" * 40)
    print(f"Server: {BASE_URL}")
    print()
    
    session = requests.Session()
    session.timeout = 10
    
    endpoints = [
        ("Health", "/health"),
        ("ESP32 Config", "/api/v1/esp32/config"),
        ("Firmware", "/api/v1/esp32/firmware"),
        ("Routes Health", "/routes-health"),
    ]
    
    results = []
    
    for name, path in endpoints:
        print(f"Checking {name}...")
        
        start_time = time.time()
        try:
            response = session.get(f"{BASE_URL}{path}")
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000
            
            if 200 <= response.status_code < 400:
                status = "OK"
                success = True
            else:
                status = f"ERROR ({response.status_code})"
                success = False
            
            print(f"   {status} - {response_time:.0f}ms")
            results.append({"name": name, "success": success})
            
        except Exception as e:
            print(f"   FAILED - {str(e)[:50]}...")
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
        print("All ESP32 endpoints are working!")
        return 0
    elif working >= total * 0.8:
        print("Most ESP32 endpoints working, some issues found")
        return 1
    else:
        print("Many ESP32 endpoints have problems")
        return 2

if __name__ == "__main__":
    try:
        sys.exit(check_esp32())
    except KeyboardInterrupt:
        print("\nTest stopped")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(2)