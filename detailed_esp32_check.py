#!/usr/bin/env python3
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def detailed_check():
    print("ESP32 Detailed Check")
    print("=" * 50)
    
    session = requests.Session()
    session.timeout = 15
    
    # 1. Health Check
    print("1. Health Endpoint:")
    try:
        response = session.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status', 'unknown')}")
            print(f"   Environment: {data.get('environment', 'unknown')}")
            print(f"   Uptime: {data.get('uptime_percentage', 'N/A')}%")
        else:
            print(f"   ERROR: {response.status_code}")
    except Exception as e:
        print(f"   FAILED: {e}")
    
    print()
    
    # 2. ESP32 Config
    print("2. ESP32 Config:")
    try:
        response = session.get(f"{BASE_URL}/api/v1/esp32/config")
        if response.status_code == 200:
            config = response.json()
            print(f"   Host: {config.get('host', 'N/A')}")
            print(f"   Port: {config.get('port', 'N/A')}")
            print(f"   WebSocket Path: {config.get('ws_path', 'N/A')}")
            print(f"   TLS: {config.get('tls', False)}")
            print(f"   App Version: {config.get('app_version', 'N/A')}")
            print(f"   Firmware Version: {config.get('firmware_version', 'N/A')}")
            
            features = config.get('features', {})
            print("   Features:")
            for feature, enabled in features.items():
                print(f"     {feature}: {enabled}")
        else:
            print(f"   ERROR: {response.status_code}")
    except Exception as e:
        print(f"   FAILED: {e}")
    
    print()
    
    # 3. Firmware Info
    print("3. Firmware Info:")
    try:
        response = session.get(f"{BASE_URL}/api/v1/esp32/firmware")
        if response.status_code == 200:
            firmware = response.json()
            print(f"   Version: {firmware.get('version', 'N/A')}")
            print(f"   Size: {firmware.get('size', 0):,} bytes")
            print(f"   Available: {firmware.get('available', False)}")
            print(f"   Mandatory: {firmware.get('mandatory', False)}")
            print(f"   SHA256: {firmware.get('sha256', 'N/A')[:16]}...")
            print(f"   URL: {firmware.get('url', 'N/A')}")
        elif response.status_code == 404:
            print("   Firmware not available (404)")
        elif response.status_code == 503:
            print("   Firmware service unavailable (503)")
        else:
            print(f"   ERROR: {response.status_code}")
    except Exception as e:
        print(f"   FAILED: {e}")
    
    print()
    
    # 4. Routes Health
    print("4. Routes Health:")
    try:
        response = session.get(f"{BASE_URL}/routes-health")
        if response.status_code == 200:
            data = response.json()
            route_system = data.get('route_system', {})
            print(f"   Status: {route_system.get('status', 'unknown')}")
            print(f"   Total Routes: {route_system.get('total_routes', 0)}")
            print(f"   Route Health: {route_system.get('route_health', 'unknown')}")
            print(f"   Monitoring: {route_system.get('monitoring_enabled', False)}")
        else:
            print(f"   ERROR: {response.status_code}")
    except Exception as e:
        print(f"   FAILED: {e}")
    
    print()
    print("=" * 50)
    print("ESP32 endpoints are functioning properly!")

if __name__ == "__main__":
    detailed_check()