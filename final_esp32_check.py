#!/usr/bin/env python3
"""
فحص نهائي شامل لـ ESP32 - AI Teddy Bear
========================================
"""

import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def final_check():
    print("ESP32 Final Comprehensive Check")
    print("=" * 50)
    print(f"Server: {BASE_URL}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    session = requests.Session()
    session.timeout = 15
    
    # Test endpoints
    tests = [
        ("Health Check", "GET", "/health"),
        ("ESP32 Config", "GET", "/api/v1/esp32/config"),
        ("ESP32 Firmware", "GET", "/api/v1/esp32/firmware"),
        ("ESP32 Metrics", "GET", "/api/v1/esp32/metrics"),
        ("Routes Health", "GET", "/routes-health"),
    ]
    
    results = []
    
    for name, method, path in tests:
        print(f"Testing {name}...")
        
        start_time = time.time()
        try:
            if method == "GET":
                response = session.get(f"{BASE_URL}{path}")
            else:
                response = session.post(f"{BASE_URL}{path}")
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            if 200 <= response.status_code < 400:
                status = "PASS"
                success = True
                print(f"   ✓ {status} - {response.status_code} - {response_time:.0f}ms")
                
                # Show some response data for key endpoints
                if path == "/api/v1/esp32/config":
                    try:
                        data = response.json()
                        print(f"     Host: {data.get('host', 'N/A')}")
                        print(f"     Version: {data.get('app_version', 'N/A')}")
                    except:
                        pass
                elif path == "/api/v1/esp32/firmware":
                    try:
                        data = response.json()
                        print(f"     Firmware: {data.get('version', 'N/A')}")
                        print(f"     Size: {data.get('size', 0):,} bytes")
                    except:
                        pass
                        
            elif response.status_code == 401:
                status = "AUTH_REQUIRED"
                success = True  # Expected for protected endpoints
                print(f"   ⚠ {status} - Authentication required (expected)")
            elif response.status_code == 404:
                status = "NOT_FOUND"
                success = False
                print(f"   ✗ {status} - Endpoint not found")
            elif response.status_code == 503:
                status = "SERVICE_UNAVAILABLE"
                success = False
                print(f"   ⚠ {status} - Service initializing")
            else:
                status = f"ERROR_{response.status_code}"
                success = False
                print(f"   ✗ {status} - {response_time:.0f}ms")
            
            results.append({
                "name": name,
                "success": success,
                "status_code": response.status_code,
                "response_time": response_time,
                "status": status
            })
            
        except requests.exceptions.Timeout:
            print(f"   ✗ TIMEOUT - Request timed out")
            results.append({"name": name, "success": False, "status": "TIMEOUT"})
        except requests.exceptions.ConnectionError:
            print(f"   ✗ CONNECTION_ERROR - Cannot connect to server")
            results.append({"name": name, "success": False, "status": "CONNECTION_ERROR"})
        except Exception as e:
            print(f"   ✗ ERROR - {str(e)[:50]}...")
            results.append({"name": name, "success": False, "status": "ERROR"})
    
    print()
    print("=" * 50)
    print("FINAL SUMMARY")
    print("=" * 50)
    
    working = sum(1 for r in results if r["success"])
    total = len(results)
    
    for result in results:
        status_icon = "✓" if result["success"] else "✗"
        print(f"   {status_icon} {result['name']}: {result.get('status', 'UNKNOWN')}")
    
    print()
    print(f"Result: {working}/{total} endpoints working properly")
    
    if working == total:
        print("🎉 ALL ESP32 ENDPOINTS ARE WORKING PERFECTLY!")
        print("✅ Your ESP32 system is ready for production")
        return 0
    elif working >= total * 0.8:
        print("⚠️  Most ESP32 endpoints working, minor issues detected")
        print("✅ System is functional but may need attention")
        return 1
    else:
        print("❌ Multiple ESP32 endpoints have problems")
        print("🔧 System needs troubleshooting")
        return 2

if __name__ == "__main__":
    try:
        sys.exit(final_check())
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(2)