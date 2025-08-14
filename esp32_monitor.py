#!/usr/bin/env python3
"""
مراقب ESP32 المستمر - AI Teddy Bear
===================================
مراقبة مستمرة لحالة ESP32 endpoints مع تنبيهات
"""

import requests
import time
import json
import sys
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
from dataclasses import dataclass, asdict
import signal

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('esp32_monitor.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000"

@dataclass
class EndpointStatus:
    """حالة endpoint"""
    name: str
    url: str
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    is_healthy: bool = False
    last_check: Optional[datetime] = None
    error_message: Optional[str] = None
    consecutive_failures: int = 0
    total_checks: int = 0
    total_failures: int = 0

@dataclass
class MonitoringStats:
    """إحصائيات المراقبة"""
    start_time: datetime
    total_checks: int = 0
    total_failures: int = 0
    uptime_percentage: float = 100.0
    avg_response_time: float = 0.0
    alerts_sent: int = 0

class ESP32Monitor:
    """مراقب ESP32 المستمر"""
    
    def __init__(self, base_url: str = BASE_URL, check_interval: int = 30):
        self.base_url = base_url
        self.check_interval = check_interval  # بالثواني
        self.session = requests.Session()
        self.session.timeout = 10
        
        # حالة المراقبة
        self.is_running = False
        self.monitor_thread = None
        
        # إحصائيات
        self.stats = MonitoringStats(start_time=datetime.now())
        
        # endpoints للمراقبة
        self.endpoints = {
            "health": EndpointStatus("الصحة العامة", f"{base_url}/health"),
            "esp32_config": EndpointStatus("إعدادات ESP32", f"{base_url}/api/v1/esp32/config"),
            "esp32_firmware": EndpointStatus("الفيرموير", f"{base_url}/api/v1/esp32/firmware"),
            "routes_health": EndpointStatus("صحة الراوترات", f"{base_url}/routes-health"),
        }
        
        # إعدادات التنبيهات
        self.alert_thresholds = {
            "consecutive_failures": 3,  # عدد الفشل المتتالي قبل التنبيه
            "response_time_ms": 5000,   # زمن الاستجابة الأقصى (ms)
            "failure_rate": 20.0        # معدل الفشل الأقصى (%)
        }
        
        # سجل التنبيهات
        self.alerts_log = []
        
        # معالج إشارة الإيقاف
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """معالج إشارة الإيقاف"""
        print(f"\n🛑 تم استلام إشارة الإيقاف ({signum})")
        self.stop_monitoring()
        sys.exit(0)
    
    def check_endpoint(self, endpoint: EndpointStatus) -> EndpointStatus:
        """فحص endpoint واحد"""
        start_time = time.time()
        
        try:
            response = self.session.get(endpoint.url)
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000  # ms
            
            # تحديث حالة endpoint
            endpoint.status_code = response.status_code
            endpoint.response_time_ms = response_time
            endpoint.is_healthy = 200 <= response.status_code < 400
            endpoint.last_check = datetime.now()
            endpoint.error_message = None
            endpoint.total_checks += 1
            
            if endpoint.is_healthy:
                endpoint.consecutive_failures = 0
            else:
                endpoint.consecutive_failures += 1
                endpoint.total_failures += 1
                endpoint.error_message = f"HTTP {response.status_code}"
            
            return endpoint
            
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            # تحديث حالة endpoint عند الخطأ
            endpoint.status_code = None
            endpoint.response_time_ms = response_time
            endpoint.is_healthy = False
            endpoint.last_check = datetime.now()
            endpoint.error_message = str(e)
            endpoint.total_checks += 1
            endpoint.total_failures += 1
            endpoint.consecutive_failures += 1
            
            return endpoint
    
    def check_all_endpoints(self) -> Dict[str, EndpointStatus]:
        """فحص جميع endpoints"""
        results = {}
        
        for key, endpoint in self.endpoints.items():
            results[key] = self.check_endpoint(endpoint)
            self.endpoints[key] = results[key]
        
        # تحديث الإحصائيات العامة
        self.update_stats()
        
        return results
    
    def update_stats(self):
        """تحديث الإحصائيات العامة"""
        total_checks = sum(ep.total_checks for ep in self.endpoints.values())
        total_failures = sum(ep.total_failures for ep in self.endpoints.values())
        
        self.stats.total_checks = total_checks
        self.stats.total_failures = total_failures
        
        if total_checks > 0:
            self.stats.uptime_percentage = ((total_checks - total_failures) / total_checks) * 100
        
        # حساب متوسط زمن الاستجابة
        healthy_endpoints = [ep for ep in self.endpoints.values() if ep.is_healthy and ep.response_time_ms]
        if healthy_endpoints:
            self.stats.avg_response_time = sum(ep.response_time_ms for ep in healthy_endpoints) / len(healthy_endpoints)
    
    def check_alerts(self):
        """فحص التنبيهات"""
        current_time = datetime.now()
        
        for key, endpoint in self.endpoints.items():
            # تنبيه الفشل المتتالي
            if endpoint.consecutive_failures >= self.alert_thresholds["consecutive_failures"]:
                alert = {
                    "type": "consecutive_failures",
                    "endpoint": endpoint.name,
                    "message": f"{endpoint.name} فشل {endpoint.consecutive_failures} مرات متتالية",
                    "timestamp": current_time,
                    "severity": "high"
                }
                self.send_alert(alert)
            
            # تنبيه زمن الاستجابة البطيء
            if (endpoint.is_healthy and endpoint.response_time_ms and 
                endpoint.response_time_ms > self.alert_thresholds["response_time_ms"]):
                alert = {
                    "type": "slow_response",
                    "endpoint": endpoint.name,
                    "message": f"{endpoint.name} بطيء: {endpoint.response_time_ms:.0f}ms",
                    "timestamp": current_time,
                    "severity": "medium"
                }
                self.send_alert(alert)
            
            # تنبيه معدل الفشل العالي
            if endpoint.total_checks > 10:  # فقط بعد عدد كافي من الفحوصات
                failure_rate = (endpoint.total_failures / endpoint.total_checks) * 100
                if failure_rate > self.alert_thresholds["failure_rate"]:
                    alert = {
                        "type": "high_failure_rate",
                        "endpoint": endpoint.name,
                        "message": f"{endpoint.name} معدل فشل عالي: {failure_rate:.1f}%",
                        "timestamp": current_time,
                        "severity": "high"
                    }
                    self.send_alert(alert)
    
    def send_alert(self, alert: Dict[str, Any]):
        """إرسال تنبيه"""
        # تجنب التنبيهات المكررة
        recent_alerts = [a for a in self.alerts_log if 
                        (datetime.now() - a["timestamp"]).seconds < 300]  # آخر 5 دقائق
        
        similar_alert = any(
            a["type"] == alert["type"] and a["endpoint"] == alert["endpoint"]
            for a in recent_alerts
        )
        
        if not similar_alert:
            self.alerts_log.append(alert)
            self.stats.alerts_sent += 1
            
            # طباعة التنبيه
            severity_icon = {"high": "🚨", "medium": "⚠️", "low": "ℹ️"}.get(alert["severity"], "📢")
            print(f"{severity_icon} تنبيه: {alert['message']}")
            logger.warning(f"Alert: {alert['message']}")
    
    def print_status(self):
        """طباعة حالة المراقبة"""
        current_time = datetime.now()
        uptime = current_time - self.stats.start_time
        
        print(f"\n📊 حالة مراقبة ESP32 - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # الإحصائيات العامة
        print(f"⏰ مدة التشغيل: {uptime}")
        print(f"📈 معدل التوفر: {self.stats.uptime_percentage:.1f}%")
        print(f"⚡ متوسط الاستجابة: {self.stats.avg_response_time:.0f}ms")
        print(f"🚨 التنبيهات المرسلة: {self.stats.alerts_sent}")
        print()
        
        # حالة كل endpoint
        for key, endpoint in self.endpoints.items():
            status_icon = "✅" if endpoint.is_healthy else "❌"
            
            print(f"{status_icon} {endpoint.name}:")
            print(f"   🌐 URL: {endpoint.url}")
            
            if endpoint.last_check:
                print(f"   ⏰ آخر فحص: {endpoint.last_check.strftime('%H:%M:%S')}")
            
            if endpoint.status_code:
                print(f"   📊 كود الحالة: {endpoint.status_code}")
            
            if endpoint.response_time_ms:
                print(f"   ⚡ زمن الاستجابة: {endpoint.response_time_ms:.0f}ms")
            
            if endpoint.error_message:
                print(f"   ❌ الخطأ: {endpoint.error_message}")
            
            print(f"   📊 الفحوصات: {endpoint.total_checks} (فشل: {endpoint.total_failures})")
            
            if endpoint.total_checks > 0:
                success_rate = ((endpoint.total_checks - endpoint.total_failures) / endpoint.total_checks) * 100
                print(f"   📈 معدل النجاح: {success_rate:.1f}%")
            
            if endpoint.consecutive_failures > 0:
                print(f"   🔴 فشل متتالي: {endpoint.consecutive_failures}")
            
            print()
    
    def save_report(self, filename: str = None):
        """حفظ تقرير المراقبة"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"esp32_monitor_report_{timestamp}.json"
        
        report = {
            "monitoring_stats": asdict(self.stats),
            "endpoints": {key: asdict(ep) for key, ep in self.endpoints.items()},
            "alerts": self.alerts_log,
            "thresholds": self.alert_thresholds
        }
        
        # تحويل datetime إلى string للـ JSON
        def datetime_converter(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=datetime_converter)
            
            print(f"💾 تم حفظ التقرير: {filename}")
            logger.info(f"Report saved: {filename}")
            
        except Exception as e:
            print(f"❌ خطأ في حفظ التقرير: {e}")
            logger.error(f"Failed to save report: {e}")
    
    def monitoring_loop(self):
        """حلقة المراقبة الرئيسية"""
        logger.info("بدء مراقبة ESP32 endpoints")
        
        while self.is_running:
            try:
                # فحص جميع endpoints
                self.check_all_endpoints()
                
                # فحص التنبيهات
                self.check_alerts()
                
                # طباعة الحالة كل 5 دقائق
                if self.stats.total_checks % 10 == 0:  # كل 10 فحوصات
                    self.print_status()
                
                # انتظار الفترة التالية
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"خطأ في حلقة المراقبة: {e}")
                time.sleep(self.check_interval)
    
    def start_monitoring(self):
        """بدء المراقبة"""
        if self.is_running:
            print("⚠️ المراقبة تعمل بالفعل")
            return
        
        print(f"🚀 بدء مراقبة ESP32 endpoints")
        print(f"🔄 فترة الفحص: {self.check_interval} ثانية")
        print(f"🌐 السيرفر: {self.base_url}")
        print("اضغط Ctrl+C للإيقاف")
        print()
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        # طباعة الحالة الأولية
        self.print_status()
    
    def stop_monitoring(self):
        """إيقاف المراقبة"""
        if not self.is_running:
            return
        
        print("🛑 إيقاف المراقبة...")
        self.is_running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        # حفظ التقرير النهائي
        self.save_report()
        
        print("✅ تم إيقاف المراقبة")
        logger.info("تم إيقاف مراقبة ESP32")

def main():
    """الدالة الرئيسية"""
    print("🤖 AI Teddy Bear - مراقب ESP32 المستمر")
    print("="*50)
    
    # معاملات سطر الأوامر
    import argparse
    parser = argparse.ArgumentParser(description="مراقب ESP32 المستمر")
    parser.add_argument("--url", default=BASE_URL, help="رابط السيرفر")
    parser.add_argument("--interval", type=int, default=30, help="فترة الفحص بالثواني")
    parser.add_argument("--duration", type=int, help="مدة المراقبة بالدقائق (اختياري)")
    
    args = parser.parse_args()
    
    # إنشاء المراقب
    monitor = ESP32Monitor(base_url=args.url, check_interval=args.interval)
    
    try:
        # بدء المراقبة
        monitor.start_monitoring()
        
        # إذا تم تحديد مدة، انتظر ثم أوقف
        if args.duration:
            print(f"⏰ المراقبة ستتوقف بعد {args.duration} دقيقة")
            time.sleep(args.duration * 60)
            monitor.stop_monitoring()
        else:
            # مراقبة مستمرة حتى يتم الإيقاف يدوياً
            while monitor.is_running:
                time.sleep(1)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف المراقبة بواسطة المستخدم")
        monitor.stop_monitoring()
        return 0
    except Exception as e:
        print(f"\n❌ خطأ في المراقبة: {e}")
        logger.error(f"Monitoring error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())