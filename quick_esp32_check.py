#!/usr/bin/env python3
"""
فحص سريع لـ ESP32 - AI Teddy Bear
=================================
فحص سريع وبسيط لحالة ESP32 endpoints
"""

import requests
import time
import sys
from datetime import datetime

BASE_URL = "http://172.28.80.1:8000"

def quick_check():
    """فحص سريع لجميع ESP32 endpoints"""
    print("🤖 AI Teddy Bear - فحص سريع لـ ESP32")
    print("="*50)
    print(f"🌐 السيرفر: {BASE_URL}")
    print(f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    session = requests.Session()
    session.timeout = 10
    
    endpoints = [
        ("الصحة العامة", "/health"),
        ("إعدادات ESP32", "/api/v1/esp32/config"),
        ("الفيرموير", "/api/v1/esp32/firmware"),
        ("صحة الراوترات", "/routes-health"),
    ]
    
    results = []
    
    for name, path in endpoints:
        print(f"🔍 فحص {name}...")
        
        start_time = time.time()
        try:
            response = session.get(f"{BASE_URL}{path}")
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000  # ms
            
            if 200 <= response.status_code < 400:
                status = "✅ يعمل"
                success = True
            else:
                status = f"⚠️ مشكلة ({response.status_code})"
                success = False
            
            print(f"   {status} - {response_time:.0f}ms")
            
            results.append({
                "name": name,
                "success": success,
                "status_code": response.status_code,
                "response_time": response_time
            })
            
        except Exception as e:
            print(f"   ❌ خطأ - {str(e)[:50]}...")
            results.append({
                "name": name,
                "success": False,
                "status_code": None,
                "response_time": None
            })
    
    print()
    print("📊 ملخص النتائج:")
    print("-" * 30)
    
    working = sum(1 for r in results if r["success"])
    total = len(results)
    
    for result in results:
        status = "✅" if result["success"] else "❌"
        time_str = f"{result['response_time']:.0f}ms" if result["response_time"] else "N/A"
        print(f"   {status} {result['name']} - {time_str}")
    
    print()
    print(f"📈 النتيجة: {working}/{total} endpoints تعمل")
    
    if working == total:
        print("🎉 جميع ESP32 endpoints تعمل بشكل مثالي!")
        return 0
    elif working >= total * 0.8:
        print("⚠️ معظم ESP32 endpoints تعمل، لكن هناك بعض المشاكل")
        return 1
    else:
        print("❌ مشاكل كثيرة في ESP32 endpoints")
        return 2

if __name__ == "__main__":
    try:
        sys.exit(quick_check())
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف الفحص")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        sys.exit(2)