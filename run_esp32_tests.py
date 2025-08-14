#!/usr/bin/env python3
"""
تشغيل شامل لاختبارات ESP32 - AI Teddy Bear
==========================================
سكريبت موحد لتشغيل جميع اختبارات ESP32
"""

import subprocess
import sys
import os
import time
import argparse
from datetime import datetime
import json

class ESP32TestRunner:
    """مشغل اختبارات ESP32 الشامل"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.results = {}
        self.start_time = datetime.now()
        
    def run_command(self, command: list, test_name: str, timeout: int = 300) -> dict:
        """تشغيل أمر واختبار النتيجة"""
        print(f"🚀 تشغيل {test_name}...")
        print(f"📝 الأمر: {' '.join(command)}")
        print("-" * 50)
        
        start_time = time.time()
        
        try:
            # تشغيل الأمر
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8'
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # طباعة النتيجة
            if result.stdout:
                print(result.stdout)
            
            if result.stderr:
                print("❌ أخطاء:")
                print(result.stderr)
            
            success = result.returncode == 0
            status = "✅ نجح" if success else "❌ فشل"
            
            print(f"\n{status} {test_name} - المدة: {duration:.2f} ثانية")
            print("=" * 60)
            
            return {
                "success": success,
                "return_code": result.returncode,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.TimeoutExpired:
            print(f"⏰ انتهت مهلة {test_name} ({timeout} ثانية)")
            return {
                "success": False,
                "return_code": -1,
                "duration": timeout,
                "stdout": "",
                "stderr": f"Timeout after {timeout} seconds"
            }
        except Exception as e:
            print(f"❌ خطأ في تشغيل {test_name}: {e}")
            return {
                "success": False,
                "return_code": -2,
                "duration": 0,
                "stdout": "",
                "stderr": str(e)
            }
    
    def check_server_health(self) -> bool:
        """فحص صحة السيرفر قبل الاختبارات"""
        print("🔍 فحص صحة السيرفر...")
        
        try:
            import requests
            response = requests.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ السيرفر يعمل - الحالة: {data.get('status', 'unknown')}")
                return True
            else:
                print(f"❌ السيرفر لا يستجيب - كود الحالة: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ خطأ في الاتصال بالسيرفر: {e}")
            return False
    
    def run_comprehensive_test(self) -> dict:
        """تشغيل الاختبار الشامل"""
        command = [sys.executable, "esp32_comprehensive_test.py"]
        return self.run_command(command, "الاختبار الشامل", timeout=180)
    
    def run_performance_test(self) -> dict:
        """تشغيل اختبار الأداء"""
        command = [sys.executable, "esp32_performance_test.py"]
        return self.run_command(command, "اختبار الأداء", timeout=300)
    
    def run_original_test(self) -> dict:
        """تشغيل الاختبار الأصلي"""
        command = [sys.executable, "test_esp32_endpoints.py"]
        return self.run_command(command, "الاختبار الأصلي", timeout=120)
    
    def start_monitoring(self, duration_minutes: int = 5) -> dict:
        """بدء المراقبة لفترة محددة"""
        command = [
            sys.executable, "esp32_monitor.py",
            "--duration", str(duration_minutes),
            "--interval", "10"
        ]
        return self.run_command(command, f"المراقبة ({duration_minutes} دقائق)", timeout=duration_minutes*60+30)
    
    def generate_report(self):
        """توليد تقرير شامل"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        # حساب الإحصائيات
        total_tests = len(self.results)
        successful_tests = sum(1 for result in self.results.values() if result["success"])
        failed_tests = total_tests - successful_tests
        
        report = {
            "test_session": {
                "start_time": self.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "total_duration": total_duration,
                "base_url": self.base_url
            },
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": (successful_tests / total_tests * 100) if total_tests > 0 else 0
            },
            "test_results": self.results
        }
        
        # حفظ التقرير
        timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
        report_filename = f"esp32_test_report_{timestamp}.json"
        
        try:
            with open(report_filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"💾 تم حفظ التقرير: {report_filename}")
            
        except Exception as e:
            print(f"❌ خطأ في حفظ التقرير: {e}")
        
        return report
    
    def print_final_summary(self, report: dict):
        """طباعة الملخص النهائي"""
        print("\n" + "="*80)
        print("📋 ملخص نهائي لاختبارات ESP32")
        print("="*80)
        
        session = report["test_session"]
        summary = report["summary"]
        
        print(f"⏰ بدء الاختبارات: {session['start_time']}")
        print(f"⏰ انتهاء الاختبارات: {session['end_time']}")
        print(f"⏱️ إجمالي المدة: {session['total_duration']:.2f} ثانية")
        print(f"🌐 السيرفر: {session['base_url']}")
        print()
        
        print("📊 الإحصائيات:")
        print(f"   📝 إجمالي الاختبارات: {summary['total_tests']}")
        print(f"   ✅ الاختبارات الناجحة: {summary['successful_tests']}")
        print(f"   ❌ الاختبارات الفاشلة: {summary['failed_tests']}")
        print(f"   📈 معدل النجاح: {summary['success_rate']:.1f}%")
        print()
        
        print("🔍 تفاصيل الاختبارات:")
        for test_name, result in self.results.items():
            status = "✅ نجح" if result["success"] else "❌ فشل"
            duration = result["duration"]
            
            print(f"   {status} {test_name} - {duration:.2f}s")
            
            if not result["success"] and result["stderr"]:
                print(f"      ❌ الخطأ: {result['stderr'][:100]}...")
        
        print()
        
        # تقييم عام
        if summary["success_rate"] >= 90:
            print("🎉 تقييم عام: ممتاز - ESP32 يعمل بشكل مثالي!")
            return 0
        elif summary["success_rate"] >= 70:
            print("⚠️ تقييم عام: جيد - ESP32 يعمل مع بعض المشاكل البسيطة")
            return 1
        elif summary["success_rate"] >= 50:
            print("🟠 تقييم عام: مقبول - ESP32 يحتاج تحسينات")
            return 2
        else:
            print("🔴 تقييم عام: ضعيف - ESP32 يحتاج إصلاحات جذرية")
            return 3
    
    def run_all_tests(self, include_monitoring: bool = True, monitoring_duration: int = 5):
        """تشغيل جميع الاختبارات"""
        print("🤖 AI Teddy Bear - تشغيل شامل لاختبارات ESP32")
        print("="*80)
        print(f"🌐 السيرفر: {self.base_url}")
        print(f"⏰ بدء الاختبارات: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. فحص صحة السيرفر
        if not self.check_server_health():
            print("❌ السيرفر لا يعمل. توقف الاختبارات.")
            return 3
        
        print()
        
        # 2. الاختبار الشامل
        self.results["comprehensive"] = self.run_comprehensive_test()
        
        # 3. اختبار الأداء
        self.results["performance"] = self.run_performance_test()
        
        # 4. الاختبار الأصلي
        self.results["original"] = self.run_original_test()
        
        # 5. المراقبة (اختياري)
        if include_monitoring:
            self.results["monitoring"] = self.start_monitoring(monitoring_duration)
        
        # 6. توليد التقرير
        report = self.generate_report()
        
        # 7. طباعة الملخص النهائي
        return self.print_final_summary(report)

def main():
    """الدالة الرئيسية"""
    parser = argparse.ArgumentParser(description="تشغيل شامل لاختبارات ESP32")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="رابط السيرفر")
    parser.add_argument("--no-monitoring", action="store_true", help="تخطي المراقبة")
    parser.add_argument("--monitoring-duration", type=int, default=5, help="مدة المراقبة بالدقائق")
    parser.add_argument("--test", choices=["comprehensive", "performance", "original", "monitoring"], 
                       help="تشغيل اختبار واحد فقط")
    
    args = parser.parse_args()
    
    runner = ESP32TestRunner(base_url=args.url)
    
    try:
        if args.test:
            # تشغيل اختبار واحد فقط
            print(f"🎯 تشغيل اختبار واحد: {args.test}")
            
            if args.test == "comprehensive":
                result = runner.run_comprehensive_test()
            elif args.test == "performance":
                result = runner.run_performance_test()
            elif args.test == "original":
                result = runner.run_original_test()
            elif args.test == "monitoring":
                result = runner.start_monitoring(args.monitoring_duration)
            
            runner.results[args.test] = result
            report = runner.generate_report()
            return runner.print_final_summary(report)
        else:
            # تشغيل جميع الاختبارات
            include_monitoring = not args.no_monitoring
            return runner.run_all_tests(include_monitoring, args.monitoring_duration)
    
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف الاختبارات بواسطة المستخدم")
        return 1
    except Exception as e:
        print(f"\n❌ خطأ في تشغيل الاختبارات: {e}")
        return 2

if __name__ == "__main__":
    sys.exit(main())