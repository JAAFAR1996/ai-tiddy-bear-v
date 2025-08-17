#!/usr/bin/env python3
"""
🎯 AI TEDDY BEAR - سكريبت تشغيل النظام الأمني الموحد
====================================================
سكريبت رئيسي للوصول لجميع وظائف النظام الأمني
"""

import sys
import subprocess
import argparse
from pathlib import Path
import json


def print_banner():
    """طباعة شعار النظام"""
    banner = """
🔒 AI TEDDY BEAR - نظام الأمان الموحد
=====================================
النظام الشامل لإدارة أمان التبعيات

📁 المكونات المتاحة:
├── 🔍 فحص شامل للتبعيات  
├── 📊 تحليل متقدم للأمان
├── 🤖 أتمتة ذكية للمراقبة
├── ⚡ تحديث سريع للحزم الحرجة
└── 📋 تقارير مفصلة

"""
    print(banner)


def run_audit():
    """تشغيل فحص شامل للتبعيات"""
    print("🔍 بدء الفحص الشامل للتبعيات...")
    script_path = Path(__file__).parent / "core" / "dependency_audit.py"
    subprocess.run([sys.executable, str(script_path)], check=False)


def run_analyzer():
    """تشغيل المحلل المتقدم"""
    print("📊 بدء التحليل المتقدم للأمان...")
    script_path = Path(__file__).parent / "core" / "dependency_analyzer.py"
    subprocess.run([sys.executable, str(script_path)], check=False)


def run_automation(mode="daily"):
    """تشغيل النظام المؤتمت"""
    print(f"🤖 بدء النظام المؤتمت في وضع: {mode}")
    script_path = Path(__file__).parent / "automation" / "security_automation.py"
    subprocess.run([sys.executable, str(script_path), "--mode", mode], check=False)


def run_quick_update():
    """تشغيل التحديث السريع"""
    print("⚡ بدء التحديث السريع للحزم الحرجة...")
    script_path = Path(__file__).parent / "tools" / "quick_security_update.py"
    subprocess.run([sys.executable, str(script_path)], check=False)


def show_status():
    """عرض حالة النظام"""
    print("📊 حالة النظام الأمني:")
    print("=" * 50)

    # فحص وجود التقارير
    reports_dir = Path(__file__).parent / "reports"
    if reports_dir.exists():
        audit_reports = list(reports_dir.glob("**/audit_*.json"))
        if audit_reports:
            latest_report = sorted(audit_reports)[-1]
            print(f"📄 آخر تقرير فحص: {latest_report.name}")

            try:
                with open(latest_report, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(
                        f"   📦 التبعيات المفحوصة: {data.get('total_dependencies', 'غير محدد')}"
                    )
                    print(
                        f"   🔒 الثغرات المكتشفة: {data.get('total_vulnerabilities', 'غير محدد')}"
                    )
                    print(
                        f"   ⚠️ التحديثات المطلوبة: {data.get('packages_needing_update', 'غير محدد')}"
                    )
            except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
                print(f"   ❌ خطأ في قراءة التقرير: {e}")

    # فحص السجلات
    logs_dir = Path(__file__).parent / "logs"
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.log"))
        print(f"📝 ملفات السجل المتاحة: {len(log_files)}")

    # فحص النسخ الاحتياطية
    backups_dir = Path(__file__).parent / "backups"
    if backups_dir.exists():
        backup_files = list(backups_dir.rglob("*"))
        print(f"💾 النسخ الاحتياطية: {len(backup_files)} ملف")

    print("✅ النظام جاهز للعمل!")


def main():
    """الدالة الرئيسية"""
    parser = argparse.ArgumentParser(
        description="نظام الأمان الموحد لـ AI Teddy Bear",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة للاستخدام:
  python run_security.py --audit           # فحص شامل
  python run_security.py --analyze         # تحليل متقدم  
  python run_security.py --automate daily  # أتمتة يومية
  python run_security.py --quick-update    # تحديث سريع
  python run_security.py --status          # عرض الحالة
        """,
    )

    parser.add_argument("--audit", action="store_true", help="تشغيل فحص شامل للتبعيات")
    parser.add_argument(
        "--analyze", action="store_true", help="تشغيل التحليل المتقدم للأمان"
    )
    parser.add_argument(
        "--automate",
        choices=["daily", "weekly", "monthly", "emergency"],
        help="تشغيل النظام المؤتمت",
    )
    parser.add_argument(
        "--quick-update", action="store_true", help="تحديث سريع للحزم الحرجة"
    )
    parser.add_argument("--status", action="store_true", help="عرض حالة النظام")

    args = parser.parse_args()

    print_banner()

    # إذا لم يتم تحديد أي خيار، عرض الحالة
    if not any(vars(args).values()):
        show_status()
        return

    # تنفيذ الإجراءات المطلوبة
    if args.audit:
        run_audit()

    if args.analyze:
        run_analyzer()

    if args.automate:
        run_automation(args.automate)

    if args.quick_update:
        run_quick_update()

    if args.status:
        show_status()


if __name__ == "__main__":
    main()
