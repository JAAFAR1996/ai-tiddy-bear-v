#!/usr/bin/env python3
"""
🔍 AI Teddy Bear System Monitor
مراقب شامل لتشخيص مشاكل السيرفر والـ ESP32
"""

import os
import sys
import time
import json
import subprocess
import requests
from datetime import datetime
from pathlib import Path
import serial.tools.list_ports

class SystemMonitor:
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.issues = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def add_issue(self, issue, severity="MEDIUM"):
        self.issues.append({
            "issue": issue,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        })
        
    def check_environment_variables(self):
        """فحص متغيرات البيئة المطلوبة"""
        self.log("🔍 فحص متغيرات البيئة...")
        
        required_vars = [
            "OPENAI_API_KEY",
            "ESP32_SHARED_SECRET", 
            "DATABASE_URL",
            "REDIS_URL"
        ]
        
        env_file = self.base_path / ".env"
        if env_file.exists():
            self.log(f"✅ ملف البيئة موجود: {env_file}")
            with open(env_file, 'r') as f:
                content = f.read()
                
            for var in required_vars:
                if f"{var}=" in content:
                    if "__PROVIDE_" in content or "__SET_ME__" in content:
                        self.add_issue(f"❌ {var} لم يتم تعيينه بقيمة صحيحة", "HIGH")
                    else:
                        self.log(f"✅ {var} موجود")
                else:
                    self.add_issue(f"❌ {var} مفقود من ملف البيئة", "HIGH")
        else:
            self.add_issue("❌ ملف .env مفقود", "CRITICAL")
            
    def check_docker_containers(self):
        """فحص حالة حاويات Docker"""
        self.log("🐳 فحص حاويات Docker...")
        
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
                capture_output=True, text=True, check=True
            )
            
            containers = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for container in containers:
                if "ai-teddy" in container:
                    parts = container.split('\t')
                    name = parts[0]
                    status = parts[1]
                    
                    if "Up" in status and "healthy" in status:
                        self.log(f"✅ {name}: {status}")
                    else:
                        self.add_issue(f"❌ {name}: {status}", "HIGH")
                        
        except subprocess.CalledProcessError as e:
            self.add_issue(f"❌ خطأ في فحص Docker: {e}", "HIGH")
            
    def check_server_health(self):
        """فحص صحة السيرفر"""
        self.log("🏥 فحص صحة السيرفر...")
        
        endpoints = [
            "http://localhost:8000/health",
            "http://localhost/health",
            "https://localhost/health"
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    self.log(f"✅ السيرفر يعمل: {endpoint}")
                    return True
                else:
                    self.log(f"⚠️ السيرفر يرد بخطأ {response.status_code}: {endpoint}")
            except requests.exceptions.RequestException as e:
                self.log(f"❌ لا يمكن الوصول للسيرفر: {endpoint} - {e}")
                
        self.add_issue("❌ السيرفر لا يستجيب على أي منفذ", "CRITICAL")
        return False
        
    def check_esp32_ports(self):
        """فحص منافذ ESP32 المتاحة"""
        self.log("📡 فحص منافذ ESP32...")
        
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            self.add_issue("❌ لا توجد منافذ COM متاحة", "HIGH")
            return
            
        for port in ports:
            self.log(f"🔌 منفذ متاح: {port.device} - {port.description}")
            
            # محاولة فتح المنفذ للاختبار
            try:
                import serial
                ser = serial.Serial(port.device, 115200, timeout=1)
                ser.close()
                self.log(f"✅ يمكن الوصول للمنفذ: {port.device}")
            except serial.SerialException as e:
                self.add_issue(f"❌ لا يمكن الوصول للمنفذ {port.device}: {e}", "MEDIUM")
                
    def check_logs_for_errors(self):
        """فحص السجلات للأخطاء"""
        self.log("📋 فحص السجلات...")
        
        log_files = [
            self.base_path / "logs" / "application.log",
            self.base_path / "logs" / "errors.log",
            self.base_path / "logs" / "serial-COM5-115200.log"
        ]
        
        for log_file in log_files:
            if log_file.exists():
                self.log(f"📄 فحص {log_file.name}...")
                
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # البحث عن أخطاء شائعة
                    error_patterns = [
                        "CRITICAL",
                        "ERROR", 
                        "FATAL",
                        "ValidationError",
                        "PermissionError",
                        "ConnectionError"
                    ]
                    
                    for pattern in error_patterns:
                        if pattern in content:
                            count = content.count(pattern)
                            self.add_issue(f"⚠️ وجد {count} من أخطاء {pattern} في {log_file.name}", "MEDIUM")
                            
                except Exception as e:
                    self.log(f"❌ خطأ في قراءة {log_file}: {e}")
            else:
                self.log(f"⚠️ ملف السجل مفقود: {log_file}")
                
    def check_network_connectivity(self):
        """فحص الاتصال بالشبكة"""
        self.log("🌐 فحص الاتصال بالشبكة...")
        
        # فحص الاتصال بـ OpenAI
        try:
            response = requests.get("https://api.openai.com/v1/models", timeout=10)
            if response.status_code == 401:  # Unauthorized is expected without API key
                self.log("✅ الاتصال بـ OpenAI يعمل")
            else:
                self.log(f"⚠️ استجابة غير متوقعة من OpenAI: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.add_issue(f"❌ لا يمكن الوصول لـ OpenAI: {e}", "HIGH")
            
    def generate_report(self):
        """إنشاء تقرير شامل"""
        self.log("📊 إنشاء التقرير...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_issues": len(self.issues),
                "critical_issues": len([i for i in self.issues if i["severity"] == "CRITICAL"]),
                "high_issues": len([i for i in self.issues if i["severity"] == "HIGH"]),
                "medium_issues": len([i for i in self.issues if i["severity"] == "MEDIUM"])
            },
            "issues": self.issues
        }
        
        # حفظ التقرير
        report_file = self.base_path / f"system_diagnosis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        self.log(f"📄 تم حفظ التقرير: {report_file}")
        
        # طباعة ملخص
        print("\n" + "="*60)
        print("🔍 ملخص التشخيص")
        print("="*60)
        print(f"📊 إجمالي المشاكل: {report['summary']['total_issues']}")
        print(f"🚨 مشاكل حرجة: {report['summary']['critical_issues']}")
        print(f"⚠️ مشاكل عالية: {report['summary']['high_issues']}")
        print(f"ℹ️ مشاكل متوسطة: {report['summary']['medium_issues']}")
        
        if self.issues:
            print("\n🔧 المشاكل المكتشفة:")
            for issue in self.issues:
                severity_icon = {
                    "CRITICAL": "🚨",
                    "HIGH": "⚠️", 
                    "MEDIUM": "ℹ️"
                }.get(issue["severity"], "❓")
                print(f"{severity_icon} [{issue['severity']}] {issue['issue']}")
        else:
            print("\n✅ لم يتم العثور على مشاكل!")
            
        return report
        
    def suggest_fixes(self):
        """اقتراح حلول للمشاكل"""
        print("\n" + "="*60)
        print("💡 اقتراحات الإصلاح")
        print("="*60)
        
        fixes = []
        
        # فحص المشاكل واقتراح حلول
        for issue in self.issues:
            if "OPENAI_API_KEY" in issue["issue"]:
                fixes.append("🔑 قم بتعيين مفتاح OpenAI صحيح في ملف .env")
                
            if "COM" in issue["issue"] and "PermissionError" in issue["issue"]:
                fixes.append("🔌 أغلق أي برامج تستخدم منفذ COM وأعد تشغيل IDE كمدير")
                
            if "Docker" in issue["issue"]:
                fixes.append("🐳 أعد تشغيل حاويات Docker: docker-compose restart")
                
            if "السيرفر لا يستجيب" in issue["issue"]:
                fixes.append("🏥 تحقق من logs السيرفر وأعد تشغيله")
                
        # إزالة التكرارات
        fixes = list(set(fixes))
        
        if fixes:
            for i, fix in enumerate(fixes, 1):
                print(f"{i}. {fix}")
        else:
            print("✅ لا توجد إصلاحات مقترحة - النظام يعمل بشكل طبيعي!")
            
    def run_full_diagnosis(self):
        """تشغيل التشخيص الكامل"""
        print("🔍 بدء التشخيص الشامل لنظام AI Teddy Bear...")
        print("="*60)
        
        # تشغيل جميع الفحوصات
        self.check_environment_variables()
        self.check_docker_containers()
        self.check_server_health()
        self.check_esp32_ports()
        self.check_logs_for_errors()
        self.check_network_connectivity()
        
        # إنشاء التقرير
        report = self.generate_report()
        
        # اقتراح الحلول
        self.suggest_fixes()
        
        return report

def main():
    monitor = SystemMonitor()
    
    try:
        report = monitor.run_full_diagnosis()
        
        # إذا كانت هناك مشاكل حرجة، اخرج بكود خطأ
        if report['summary']['critical_issues'] > 0:
            sys.exit(1)
        elif report['summary']['high_issues'] > 0:
            sys.exit(2)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف التشخيص بواسطة المستخدم")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ خطأ في التشخيص: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()