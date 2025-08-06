#!/usr/bin/env python3
"""
🚀 AI TEDDY BEAR - تحديث سريع للتبعيات الحرجة
===============================================
سكريبت سريع لتحديث التبعيات الحرجة بأمان
"""

import subprocess
import sys
import json
from pathlib import Path
import logging

# إعداد السجلات
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class QuickSecurityUpdater:
    """محدث سريع للتبعيات الأمنية"""

    def __init__(self):
        self.project_root = Path(".")
        self.critical_packages = [
            "cryptography",
            "pyjwt",
            "passlib",
            "fastapi",
            "sqlalchemy",
        ]

    def run_quick_update(self):
        """تشغيل تحديث سريع للتبعيات الحرجة"""
        logger.info("🚀 بدء التحديث السريع للتبعيات الحرجة")

        # 1. فحص سريع للثغرات
        vulnerabilities = self._quick_vulnerability_check()

        if vulnerabilities:
            logger.warning(f"⚠️ تم اكتشاف {len(vulnerabilities)} ثغرة أمنية")

            # 2. تحديث الحزم المتأثرة
            updated_packages = []
            for vuln in vulnerabilities:
                package = vuln.get("package", "")
                if package in self.critical_packages:
                    success = self._update_package_safely(package)
                    if success:
                        updated_packages.append(package)

            logger.info(
                f"✅ تم تحديث {len(updated_packages)} حزمة: {', '.join(updated_packages)}"
            )

        else:
            logger.info("✅ لم يتم اكتشاف ثغرات حرجة")

        # 3. فحص التحديثات المتاحة للحزم الحرجة
        outdated_critical = self._check_outdated_critical()

        if outdated_critical:
            logger.info(f"📦 حزم حرجة تحتاج تحديث: {len(outdated_critical)}")

            for package in outdated_critical[:3]:  # تحديث أول 3 حزم فقط
                success = self._update_package_safely(package["name"])
                if success:
                    logger.info(
                        f"✅ تم تحديث {package['name']} من {package['version']} إلى {package['latest_version']}"
                    )

        logger.info("🎯 تم إكمال التحديث السريع")

    def _quick_vulnerability_check(self):
        """فحص سريع للثغرات باستخدام safety"""
        try:
            # تثبيت safety إذا لم يكن موجود
            self._ensure_package_installed("safety")

            result = subprocess.run(
                [sys.executable, "-m", "safety", "check", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.stdout.strip():
                return json.loads(result.stdout)
            return []

        except Exception as e:
            logger.error(f"خطأ في فحص الثغرات: {e}")
            return []

    def _check_outdated_critical(self):
        """فحص التحديثات المتاحة للحزم الحرجة"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
            )

            if result.stdout.strip():
                all_outdated = json.loads(result.stdout)
                # فلترة الحزم الحرجة فقط
                critical_outdated = [
                    pkg
                    for pkg in all_outdated
                    if pkg["name"].lower()
                    in [p.lower() for p in self.critical_packages]
                ]
                return critical_outdated

            return []

        except subprocess.CalledProcessError as e:
            logger.error(f"خطأ في فحص التحديثات: {e}")
            return []

    def _update_package_safely(self, package_name: str) -> bool:
        """تحديث حزمة بأمان مع اختبار"""
        try:
            logger.info(f"🔄 تحديث {package_name}...")

            # الحصول على الإصدار الحالي
            current_version = self._get_current_version(package_name)

            # تحديث الحزمة
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", package_name],
                capture_output=True,
                text=True,
                check=True,
            )

            # اختبار سريع
            if self._quick_import_test():
                logger.info(f"✅ نجح تحديث {package_name}")
                return True
            else:
                # إرجاع إلى الإصدار السابق
                logger.warning(f"⚠️ فشل اختبار {package_name}، إرجاع إلى الإصدار السابق")
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        f"{package_name}=={current_version}",
                    ],
                    check=True,
                )
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ فشل تحديث {package_name}: {e}")
            return False

    def _get_current_version(self, package_name: str) -> str:
        """الحصول على الإصدار الحالي للحزمة"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", package_name],
                capture_output=True,
                text=True,
                check=True,
            )

            for line in result.stdout.split("\n"):
                if line.startswith("Version:"):
                    return line.split(":")[1].strip()
        except subprocess.CalledProcessError:
            pass
        return "unknown"

    def _quick_import_test(self) -> bool:
        """اختبار سريع لاستيراد الوحدات الأساسية"""
        try:
            test_imports = [
                "import fastapi",
                "import sqlalchemy",
                "import cryptography",
                "import jwt",
                "import passlib",
            ]

            for import_stmt in test_imports:
                result = subprocess.run(
                    [sys.executable, "-c", import_stmt],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if result.returncode != 0:
                    return False

            return True

        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    def _ensure_package_installed(self, package_name: str):
        """التأكد من تثبيت حزمة"""
        try:
            __import__(package_name.replace("-", "_"))
        except ImportError:
            logger.info(f"🔧 تثبيت {package_name}...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                check=True,
                capture_output=True,
            )


def main():
    """الدالة الرئيسية"""
    updater = QuickSecurityUpdater()

    print("🔒 AI TEDDY BEAR - تحديث سريع للأمان")
    print("=" * 50)

    try:
        updater.run_quick_update()
        print("\n✅ تم إكمال التحديث السريع بنجاح!")
        print(
            "💡 لفحص شامل، استخدم: python security_system/core/dependency_analyzer.py"
        )

    except KeyboardInterrupt:
        print("\n⚠️ تم إيقاف التحديث بواسطة المستخدم")

    except Exception as e:
        print(f"\n❌ خطأ في التحديث السريع: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
