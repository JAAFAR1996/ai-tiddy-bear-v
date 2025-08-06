#!/usr/bin/env python3
"""
🔒 AI TEDDY BEAR - نظام فحص التبعيات الشامل
===========================================
سكريبت شامل لفحص وإدارة أمان التبعيات للنظام
"""

import subprocess
import json
import datetime
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, NamedTuple
import argparse


class SecurityIssue(NamedTuple):
    """هيكل بيانات لمشكلة أمنية"""

    package: str
    current_version: str
    affected_versions: str
    vulnerability_id: str
    severity: str
    description: str
    fix_available: bool
    recommended_version: Optional[str] = None


class DependencyAnalyzer:
    """محلل شامل للتبعيات والأمان"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.security_dir = self.project_root / "security"
        self.security_dir.mkdir(exist_ok=True)

        # إنشاء مجلدات التقارير
        self.reports_dir = self.security_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)

        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    def run_comprehensive_audit(self) -> Dict[str, Any]:
        """تشغيل فحص شامل لجميع جوانب الأمان"""
        print("🔍 بدء الفحص الأمني الشامل...")

        results = {
            "timestamp": self.timestamp,
            "project_path": str(self.project_root),
            "python_version": sys.version,
            "audits": {},
        }

        # 1. فحص التبعيات المثبتة
        print("📦 فحص التبعيات المثبتة...")
        results["audits"]["installed_packages"] = self._audit_installed_packages()

        # 2. فحص الثغرات الأمنية
        print("🚨 فحص الثغرات الأمنية...")
        results["audits"][
            "security_vulnerabilities"
        ] = self._audit_security_vulnerabilities()

        # 3. فحص كود المصدر
        print("🔍 فحص أمان الكود...")
        results["audits"]["code_security"] = self._audit_code_security()

        # 4. فحص ملفات التكوين
        print("⚙️ فحص ملفات التكوين...")
        results["audits"]["configuration"] = self._audit_configuration()

        # 5. فحص التحديثات المتاحة
        print("🔄 فحص التحديثات المتاحة...")
        results["audits"]["available_updates"] = self._audit_available_updates()

        # 6. تحليل شجرة التبعيات
        print("🌳 تحليل شجرة التبعيات...")
        results["audits"]["dependency_tree"] = self._audit_dependency_tree()

        # حفظ التقرير
        self._save_comprehensive_report(results)

        return results

    def _audit_installed_packages(self) -> Dict[str, Any]:
        """فحص الحزم المثبتة وحالتها"""
        try:
            # قائمة الحزم المثبتة
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
            )
            installed_packages = json.loads(result.stdout)

            # معلومات إضافية عن كل حزمة
            package_info = {}
            critical_packages = [
                "fastapi",
                "sqlalchemy",
                "redis",
                "cryptography",
                "pyjwt",
                "passlib",
                "slowapi",
                "openai",
            ]

            for pkg in installed_packages:
                name = pkg["name"].lower()
                package_info[name] = {
                    "version": pkg["version"],
                    "is_critical": name in critical_packages,
                    "location": self._get_package_location(name),
                }

            return {
                "total_packages": len(installed_packages),
                "critical_packages": len(
                    [p for p in package_info.values() if p["is_critical"]]
                ),
                "packages": package_info,
                "status": "success",
            }

        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": str(e)}

    def _audit_security_vulnerabilities(self) -> Dict[str, Any]:
        """فحص الثغرات الأمنية باستخدام safety"""
        try:
            # تثبيت safety إذا لم يكن مثبت
            self._ensure_package_installed("safety")

            # فحص بـ safety
            result = subprocess.run(
                [sys.executable, "-m", "safety", "check", "--json"],
                capture_output=True,
                text=True,
            )

            vulnerabilities = []
            if result.stdout.strip():
                safety_data = json.loads(result.stdout)
                vulnerabilities = safety_data

            # فحص إضافي بـ pip-audit
            pip_audit_result = self._run_pip_audit()

            return {
                "safety_vulnerabilities": vulnerabilities,
                "pip_audit_result": pip_audit_result,
                "total_vulnerabilities": len(vulnerabilities),
                "status": (
                    "success" if len(vulnerabilities) == 0 else "vulnerabilities_found"
                ),
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _audit_code_security(self) -> Dict[str, Any]:
        """فحص أمان الكود باستخدام bandit"""
        try:
            self._ensure_package_installed("bandit[toml]")

            # فحص مجلد src
            src_path = self.project_root / "src"
            if not src_path.exists():
                return {"status": "skipped", "reason": "src directory not found"}

            result = subprocess.run(
                [sys.executable, "-m", "bandit", "-r", str(src_path), "-f", "json"],
                capture_output=True,
                text=True,
            )

            bandit_results = {"issues": [], "skipped": []}
            if result.stdout.strip():
                bandit_data = json.loads(result.stdout)
                bandit_results = {
                    "issues": bandit_data.get("results", []),
                    "skipped": bandit_data.get("skipped", []),
                    "metrics": bandit_data.get("metrics", {}),
                }

            return {
                "bandit_results": bandit_results,
                "total_issues": len(bandit_results["issues"]),
                "high_severity": len(
                    [
                        i
                        for i in bandit_results["issues"]
                        if i.get("issue_severity") == "HIGH"
                    ]
                ),
                "status": "success",
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _audit_configuration(self) -> Dict[str, Any]:
        """فحص ملفات التكوين والإعدادات الأمنية"""
        config_checks = {
            "requirements_files": self._check_requirements_files(),
            "docker_security": self._check_docker_security(),
            "environment_variables": self._check_environment_security(),
            "secrets_in_code": self._check_secrets_in_code(),
        }

        return {"checks": config_checks, "status": "success"}

    def _audit_available_updates(self) -> Dict[str, Any]:
        """فحص التحديثات المتاحة للحزم"""
        try:
            # فحص التحديثات المتاحة
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
            )

            outdated_packages = []
            if result.stdout.strip():
                outdated_packages = json.loads(result.stdout)

            # تصنيف التحديثات حسب الأهمية
            critical_updates = []
            security_updates = []
            regular_updates = []

            critical_package_names = [
                "fastapi",
                "sqlalchemy",
                "redis",
                "cryptography",
                "pyjwt",
                "passlib",
                "slowapi",
            ]

            for pkg in outdated_packages:
                if pkg["name"].lower() in critical_package_names:
                    critical_updates.append(pkg)
                elif any(
                    keyword in pkg["name"].lower()
                    for keyword in ["security", "crypto", "auth"]
                ):
                    security_updates.append(pkg)
                else:
                    regular_updates.append(pkg)

            return {
                "total_outdated": len(outdated_packages),
                "critical_updates": critical_updates,
                "security_updates": security_updates,
                "regular_updates": regular_updates,
                "status": "success",
            }

        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": str(e)}

    def _audit_dependency_tree(self) -> Dict[str, Any]:
        """تحليل شجرة التبعيات للتحقق من التضارب"""
        try:
            self._ensure_package_installed("pipdeptree")

            # شجرة التبعيات
            result = subprocess.run(
                [sys.executable, "-m", "pipdeptree", "--json"],
                capture_output=True,
                text=True,
                check=True,
            )

            dependency_tree = json.loads(result.stdout)

            # تحليل التضارب
            conflicts = self._analyze_dependency_conflicts()

            return {
                "dependency_tree": dependency_tree,
                "conflicts": conflicts,
                "total_packages": len(dependency_tree),
                "status": "success",
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_pip_audit(self) -> Dict[str, Any]:
        """تشغيل pip-audit للفحص الإضافي"""
        try:
            self._ensure_package_installed("pip-audit")

            result = subprocess.run(
                [sys.executable, "-m", "pip_audit", "--format=json"],
                capture_output=True,
                text=True,
            )

            if result.stdout.strip():
                return json.loads(result.stdout)
            return {"vulnerabilities": []}

        except Exception:
            return {"status": "error", "message": "pip-audit not available"}

    def _ensure_package_installed(self, package: str):
        """التأكد من تثبيت حزمة معينة"""
        try:
            __import__(package.split("[")[0].replace("-", "_"))
        except ImportError:
            print(f"🔧 تثبيت {package}...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                check=True,
                capture_output=True,
            )

    def _get_package_location(self, package_name: str) -> str:
        """الحصول على مسار تثبيت الحزمة"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", package_name],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.split("\n"):
                if line.startswith("Location:"):
                    return line.split("Location:")[1].strip()
        except Exception:
            pass
        return "unknown"

    def _check_requirements_files(self) -> Dict[str, Any]:
        """فحص ملفات requirements"""
        req_files = list(self.project_root.glob("requirements*.txt"))

        analysis = {
            "files_found": [str(f.name) for f in req_files],
            "pinned_versions": 0,
            "unpinned_versions": 0,
            "issues": [],
        }

        for req_file in req_files:
            try:
                content = req_file.read_text(encoding="utf-8")
                lines = [
                    line.strip()
                    for line in content.split("\n")
                    if line.strip() and not line.startswith("#")
                ]

                for line in lines:
                    if "==" in line:
                        analysis["pinned_versions"] += 1
                    else:
                        analysis["unpinned_versions"] += 1
                        analysis["issues"].append(f"غير مثبت الإصدار: {line}")

            except Exception as e:
                analysis["issues"].append(f"خطأ في قراءة {req_file.name}: {str(e)}")

        return analysis

    def _check_docker_security(self) -> Dict[str, Any]:
        """فحص إعدادات Docker الأمنية"""
        docker_files = list(self.project_root.glob("*Dockerfile*")) + list(
            self.project_root.glob("docker-compose*.yml")
        )

        analysis = {
            "files_found": [str(f.name) for f in docker_files],
            "security_issues": [],
            "recommendations": [],
        }

        for docker_file in docker_files:
            try:
                content = docker_file.read_text(encoding="utf-8").lower()

                # فحص المشاكل الأمنية الشائعة
                if "user root" in content or "user 0" in content:
                    analysis["security_issues"].append(
                        f"{docker_file.name}: استخدام root user"
                    )

                if "password" in content and "=" in content:
                    analysis["security_issues"].append(
                        f"{docker_file.name}: كلمة مرور محتملة في النص"
                    )

                if "--privileged" in content:
                    analysis["security_issues"].append(
                        f"{docker_file.name}: استخدام privileged mode"
                    )

            except Exception as e:
                analysis["security_issues"].append(
                    f"خطأ في فحص {docker_file.name}: {str(e)}"
                )

        return analysis

    def _check_environment_security(self) -> Dict[str, Any]:
        """فحص متغيرات البيئة والأسرار"""
        env_files = list(self.project_root.glob(".env*"))

        analysis = {
            "env_files_found": [str(f.name) for f in env_files],
            "potential_secrets": [],
            "recommendations": [],
        }

        # كلمات مفتاحية للأسرار
        secret_keywords = [
            "password",
            "secret",
            "key",
            "token",
            "api_key",
            "private_key",
            "auth",
            "credential",
        ]

        for env_file in env_files:
            try:
                content = env_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    line_lower = line.lower()
                    for keyword in secret_keywords:
                        if keyword in line_lower and "=" in line:
                            analysis["potential_secrets"].append(
                                f"{env_file.name}:{i} - محتمل سر: {line.split('=')[0]}"
                            )

            except Exception as e:
                analysis["potential_secrets"].append(
                    f"خطأ في فحص {env_file.name}: {str(e)}"
                )

        return analysis

    def _check_secrets_in_code(self) -> Dict[str, Any]:
        """فحص الأسرار المحتملة في الكود"""
        analysis = {"potential_secrets": [], "files_scanned": 0}

        # فحص الملفات مباشرة بدون regex معقدة
        src_path = self.project_root / "src"
        if src_path.exists():
            for py_file in src_path.rglob("*.py"):
                try:
                    content = py_file.read_text(encoding="utf-8")
                    analysis["files_scanned"] += 1

                    # فحص بسيط للكلمات الحساسة
                    if any(
                        word in content.lower()
                        for word in ["password =", "secret =", "api_key ="]
                    ):
                        analysis["potential_secrets"].append(
                            f"{py_file.relative_to(self.project_root)}: محتمل سر في الكود"
                        )

                except Exception:
                    continue

        return analysis

    def _analyze_dependency_conflicts(self) -> List[str]:
        """تحليل تضارب التبعيات"""
        conflicts = []
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "check"], capture_output=True, text=True
            )

            if result.returncode != 0:
                conflicts = (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )

        except Exception:
            conflicts = ["فشل في فحص التضارب"]

        return conflicts

    def _save_comprehensive_report(self, results: Dict[str, Any]):
        """حفظ التقرير الشامل"""
        report_file = self.reports_dir / f"security_audit_{self.timestamp}.json"

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        # تقرير مبسط بالعربية
        summary_file = self.reports_dir / f"security_summary_{self.timestamp}.md"
        self._generate_arabic_summary(results, summary_file)

        print(f"📊 تم حفظ التقرير في: {report_file}")
        print(f"📋 تم حفظ الملخص في: {summary_file}")

    def _generate_arabic_summary(self, results: Dict[str, Any], output_file: Path):
        """إنشاء ملخص بالعربية للتقرير"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(
                f"""# 🔒 تقرير الأمان الشامل - AI Teddy Bear
## {results['timestamp']}

### 📊 الملخص التنفيذي:

"""
            )

            # ملخص التبعيات
            packages = results["audits"]["installed_packages"]
            f.write(
                f"""#### 📦 التبعيات:
- إجمالي الحزم: {packages.get('total_packages', 0)}
- الحزم الحرجة: {packages.get('critical_packages', 0)}
- الحالة: {"✅ سليم" if packages.get('status') == 'success' else "❌ مشكلة"}

"""
            )

            # ملخص الثغرات
            vulns = results["audits"]["security_vulnerabilities"]
            f.write(
                f"""#### 🚨 الثغرات الأمنية:
- إجمالي الثغرات: {vulns.get('total_vulnerabilities', 0)}
- الحالة: {"✅ آمن" if vulns.get('total_vulnerabilities', 0) == 0 else "⚠️ يحتاج إصلاح"}

"""
            )

            # ملخص أمان الكود
            code_sec = results["audits"]["code_security"]
            f.write(
                f"""#### 🔍 أمان الكود:
- المشاكل المكتشفة: {code_sec.get('total_issues', 0)}
- المشاكل عالية الخطورة: {code_sec.get('high_severity', 0)}
- الحالة: {"✅ آمن" if code_sec.get('total_issues', 0) == 0 else "⚠️ يحتاج مراجعة"}

"""
            )

            # التحديثات المتاحة
            updates = results["audits"]["available_updates"]
            f.write(
                f"""#### 🔄 التحديثات:
- حزم تحتاج تحديث: {updates.get('total_outdated', 0)}
- تحديثات حرجة: {len(updates.get('critical_updates', []))}
- الحالة: {"✅ محدث" if updates.get('total_outdated', 0) == 0 else "⚠️ يحتاج تحديث"}

"""
            )

            f.write(
                """
### 🎯 التوصيات:

1. **فوري**: إصلاح الثغرات الأمنية عالية الخطورة
2. **أسبوعي**: تحديث الحزم الحرجة
3. **شهري**: مراجعة شاملة للتبعيات
4. **مستمر**: مراقبة تلقائية للثغرات الجديدة

### 📞 في حالة الطوارئ:
- تشغيل: `python security/dependency_analyzer.py --emergency`
- مراجعة: `security/DEPENDENCY_SECURITY_GUIDE.md`

---
تم إنشاء هذا التقرير تلقائياً بواسطة نظام AI Teddy Bear الأمني
"""
            )


def main():
    """الدالة الرئيسية"""
    parser = argparse.ArgumentParser(description="نظام فحص التبعيات الشامل")
    parser.add_argument(
        "--emergency", action="store_true", help="وضع الطوارئ - فحص سريع"
    )
    parser.add_argument("--daily-check", action="store_true", help="فحص يومي مجدول")
    parser.add_argument("--project-root", default=".", help="مسار المشروع")

    args = parser.parse_args()

    analyzer = DependencyAnalyzer(args.project_root)

    if args.emergency:
        print("🚨 وضع الطوارئ - فحص سريع للثغرات الحرجة")
        # فحص مبسط للطوارئ
        results = analyzer._audit_security_vulnerabilities()
        if results.get("total_vulnerabilities", 0) > 0:
            print("❌ تم اكتشاف ثغرات أمنية حرجة!")
            sys.exit(1)
        else:
            print("✅ لم يتم اكتشاف ثغرات حرجة")

    elif args.daily_check:
        print("📅 فحص يومي مجدول")
        # فحص أساسي يومي
        vulns = analyzer._audit_security_vulnerabilities()
        updates = analyzer._audit_available_updates()

        if (
            vulns.get("total_vulnerabilities", 0) > 0
            or len(updates.get("critical_updates", [])) > 0
        ):
            print("⚠️ تحديثات أمنية مطلوبة")
            # إرسال تنبيه (يمكن إضافة webhook هنا)

    else:
        # فحص شامل كامل
        results = analyzer.run_comprehensive_audit()

        # عرض الملخص
        print("\n" + "=" * 50)
        print("🎯 ملخص النتائج:")
        print("=" * 50)

        total_packages = results["audits"]["installed_packages"].get(
            "total_packages", 0
        )
        total_vulns = results["audits"]["security_vulnerabilities"].get(
            "total_vulnerabilities", 0
        )
        total_outdated = results["audits"]["available_updates"].get("total_outdated", 0)

        print(f"📦 إجمالي التبعيات: {total_packages}")
        print(f"🚨 الثغرات الأمنية: {total_vulns}")
        print(f"🔄 التحديثات المطلوبة: {total_outdated}")

        if total_vulns == 0 and total_outdated == 0:
            print("\n✅ النظام آمن ومحدث!")
        else:
            print("\n⚠️ يحتاج النظام إلى صيانة أمنية")

        print("\n📊 راجع التقرير الكامل في: security/reports/")


if __name__ == "__main__":
    main()
