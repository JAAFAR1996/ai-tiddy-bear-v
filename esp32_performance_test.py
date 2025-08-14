#!/usr/bin/env python3
"""
فحص أداء ESP32 - AI Teddy Bear
==============================
فحص أداء واستجابة endpoints الخاصة بـ ESP32
"""

import requests
import time
import statistics
import concurrent.futures
import json
from typing import List, Dict, Any
import sys

BASE_URL = "http://127.0.0.1:8000"

class ESP32PerformanceTester:
    """فئة فحص أداء ESP32"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.timeout = 30
        
    def measure_response_time(self, url: str, method: str = "GET", data: Dict = None, headers: Dict = None) -> Dict[str, Any]:
        """قياس زمن الاستجابة لطلب واحد"""
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, headers=headers)
            else:
                raise ValueError(f"HTTP method غير مدعوم: {method}")
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # بالميلي ثانية
            
            return {
                "success": True,
                "status_code": response.status_code,
                "response_time_ms": response_time,
                "content_length": len(response.content),
                "error": None
            }
            
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            return {
                "success": False,
                "status_code": None,
                "response_time_ms": response_time,
                "content_length": 0,
                "error": str(e)
            }
    
    def load_test_endpoint(self, url: str, num_requests: int = 10, concurrent_requests: int = 3, 
                          method: str = "GET", data: Dict = None, headers: Dict = None) -> Dict[str, Any]:
        """اختبار تحميل endpoint معين"""
        print(f"🔄 اختبار تحميل: {url}")
        print(f"   📊 عدد الطلبات: {num_requests}")
        print(f"   🔀 الطلبات المتزامنة: {concurrent_requests}")
        
        results = []
        
        def make_request():
            return self.measure_response_time(url, method, data, headers)
        
        start_time = time.time()
        
        # تشغيل الطلبات بشكل متزامن
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # تحليل النتائج
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]
        
        if successful_requests:
            response_times = [r["response_time_ms"] for r in successful_requests]
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            median_response_time = statistics.median(response_times)
            
            if len(response_times) > 1:
                std_dev = statistics.stdev(response_times)
            else:
                std_dev = 0
        else:
            avg_response_time = min_response_time = max_response_time = median_response_time = std_dev = 0
        
        requests_per_second = num_requests / total_time if total_time > 0 else 0
        success_rate = len(successful_requests) / num_requests * 100
        
        # طباعة النتائج
        print(f"   ✅ الطلبات الناجحة: {len(successful_requests)}/{num_requests} ({success_rate:.1f}%)")
        print(f"   ❌ الطلبات الفاشلة: {len(failed_requests)}")
        print(f"   ⏱️ إجمالي الوقت: {total_time:.2f} ثانية")
        print(f"   🚀 الطلبات في الثانية: {requests_per_second:.2f}")
        
        if successful_requests:
            print(f"   📊 أزمنة الاستجابة (ms):")
            print(f"      📈 المتوسط: {avg_response_time:.2f}")
            print(f"      📉 الأدنى: {min_response_time:.2f}")
            print(f"      📈 الأعلى: {max_response_time:.2f}")
            print(f"      📊 الوسيط: {median_response_time:.2f}")
            print(f"      📏 الانحراف المعياري: {std_dev:.2f}")
        
        if failed_requests:
            print(f"   ❌ أخطاء:")
            error_counts = {}
            for req in failed_requests:
                error = req["error"]
                error_counts[error] = error_counts.get(error, 0) + 1
            
            for error, count in error_counts.items():
                print(f"      • {error}: {count} مرة")
        
        return {
            "url": url,
            "total_requests": num_requests,
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": success_rate,
            "total_time": total_time,
            "requests_per_second": requests_per_second,
            "avg_response_time": avg_response_time,
            "min_response_time": min_response_time,
            "max_response_time": max_response_time,
            "median_response_time": median_response_time,
            "std_dev": std_dev,
            "errors": error_counts if failed_requests else {}
        }
    
    def test_all_esp32_endpoints(self) -> Dict[str, Any]:
        """فحص أداء جميع ESP32 endpoints"""
        print("🚀 بدء فحص أداء جميع ESP32 endpoints")
        print("="*50)
        
        results = {}
        
        # 1. فحص endpoint الصحة
        print("\n1️⃣ فحص أداء endpoint الصحة")
        results["health"] = self.load_test_endpoint(
            f"{self.base_url}/health",
            num_requests=20,
            concurrent_requests=5
        )
        
        # 2. فحص endpoint إعدادات ESP32
        print("\n2️⃣ فحص أداء endpoint إعدادات ESP32")
        results["esp32_config"] = self.load_test_endpoint(
            f"{self.base_url}/api/v1/esp32/config",
            num_requests=15,
            concurrent_requests=3
        )
        
        # 3. فحص endpoint الفيرموير
        print("\n3️⃣ فحص أداء endpoint الفيرموير")
        results["esp32_firmware"] = self.load_test_endpoint(
            f"{self.base_url}/api/v1/esp32/firmware",
            num_requests=10,
            concurrent_requests=2
        )
        
        # 4. فحص endpoint صحة الراوترات
        print("\n4️⃣ فحص أداء endpoint صحة الراوترات")
        results["routes_health"] = self.load_test_endpoint(
            f"{self.base_url}/routes-health",
            num_requests=15,
            concurrent_requests=3
        )
        
        return results
    
    def print_performance_summary(self, results: Dict[str, Any]):
        """طباعة ملخص الأداء"""
        print("\n" + "="*60)
        print("📊 ملخص أداء ESP32 Endpoints")
        print("="*60)
        
        endpoint_names = {
            "health": "الصحة العامة",
            "esp32_config": "إعدادات ESP32",
            "esp32_firmware": "الفيرموير",
            "routes_health": "صحة الراوترات"
        }
        
        total_requests = 0
        total_successful = 0
        total_failed = 0
        avg_response_times = []
        
        for endpoint, result in results.items():
            name = endpoint_names.get(endpoint, endpoint)
            success_rate = result["success_rate"]
            avg_time = result["avg_response_time"]
            rps = result["requests_per_second"]
            
            total_requests += result["total_requests"]
            total_successful += result["successful_requests"]
            total_failed += result["failed_requests"]
            
            if result["successful_requests"] > 0:
                avg_response_times.append(avg_time)
            
            status = "✅" if success_rate >= 95 else "⚠️" if success_rate >= 80 else "❌"
            
            print(f"{status} {name}:")
            print(f"   📊 معدل النجاح: {success_rate:.1f}%")
            print(f"   ⏱️ متوسط الاستجابة: {avg_time:.2f} ms")
            print(f"   🚀 الطلبات/ثانية: {rps:.2f}")
            print()
        
        # الإحصائيات الإجمالية
        overall_success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0
        overall_avg_response = statistics.mean(avg_response_times) if avg_response_times else 0
        
        print("📈 الإحصائيات الإجمالية:")
        print(f"   📊 إجمالي الطلبات: {total_requests}")
        print(f"   ✅ الطلبات الناجحة: {total_successful}")
        print(f"   ❌ الطلبات الفاشلة: {total_failed}")
        print(f"   📊 معدل النجاح الإجمالي: {overall_success_rate:.1f}%")
        print(f"   ⏱️ متوسط الاستجابة الإجمالي: {overall_avg_response:.2f} ms")
        
        # تقييم الأداء
        print("\n🎯 تقييم الأداء:")
        if overall_success_rate >= 95 and overall_avg_response <= 500:
            print("   🟢 ممتاز: الأداء ممتاز والاستجابة سريعة")
            return 0
        elif overall_success_rate >= 90 and overall_avg_response <= 1000:
            print("   🟡 جيد: الأداء جيد مع بعض التحسينات المطلوبة")
            return 1
        elif overall_success_rate >= 80:
            print("   🟠 مقبول: الأداء مقبول لكن يحتاج تحسينات")
            return 2
        else:
            print("   🔴 ضعيف: الأداء ضعيف ويحتاج تحسينات جذرية")
            return 3

def main():
    """الدالة الرئيسية"""
    print("🤖 AI Teddy Bear - فحص أداء ESP32")
    print("="*50)
    print(f"🌐 السيرفر: {BASE_URL}")
    print()
    
    tester = ESP32PerformanceTester()
    
    try:
        # تشغيل اختبارات الأداء
        results = tester.test_all_esp32_endpoints()
        
        # طباعة الملخص
        exit_code = tester.print_performance_summary(results)
        
        return exit_code
        
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف اختبارات الأداء بواسطة المستخدم")
        return 1
    except Exception as e:
        print(f"\n❌ خطأ في اختبارات الأداء: {e}")
        return 2

if __name__ == "__main__":
    sys.exit(main())