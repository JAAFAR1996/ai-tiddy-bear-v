#!/usr/bin/env python3
"""
🔒 AI TEDDY BEAR - نظام تدقيق الأمان والتبعيات الشامل
==============================================================
نظام آلي لفحص الثغرات الأمنية وإدارة التبعيات بشكل منهجي
"""

import json
import requests
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """مستويات الخطورة الأمنية"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DependencyCategory(Enum):
    """تصنيف التبعيات حسب الأهمية"""

    CORE_FRAMEWORK = "core_framework"  # FastAPI, SQLAlchemy
    SECURITY = "security"  # cryptography, passlib
    CHILD_SAFETY = "child_safety"  # content filters
    AI_ML = "ai_ml"  # OpenAI, torch
    DATABASE = "database"  # PostgreSQL, Redis
    MONITORING = "monitoring"  # Prometheus, Sentry
    UTILITIES = "utilities"  # مساعدة
    DEVELOPMENT = "development"  # pytest, black
    OPTIONAL = "optional"  # يمكن الاستغناء عنها


@dataclass
class SecurityVulnerability:
    """معلومات الثغرة الأمنية"""

    id: str
    package: str
    version: str
    severity: SecurityLevel
    title: str
    description: str
    fixed_version: Optional[str] = None
    cve_id: Optional[str] = None
    published_date: Optional[datetime] = None


@dataclass
class DependencyInfo:
    """معلومات التبعية"""

    name: str
    current_version: str
    latest_version: str
    category: DependencyCategory
    is_pinned: bool = False
    vulnerabilities: List[SecurityVulnerability] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    license: Optional[str] = None
    dependencies_count: int = 0

    @property
    def needs_update(self) -> bool:
        """هل تحتاج التبعية لتحديث؟"""
        if not self.latest_version or not self.current_version:
            return False
        try:
            # مقارنة بسيطة للإصدارات
            current_parts = self.current_version.split(".")
            latest_parts = self.latest_version.split(".")

            # مقارنة عدد صحيح لكل جزء
            for i in range(min(len(current_parts), len(latest_parts))):
                try:
                    current_num = int(current_parts[i])
                    latest_num = int(latest_parts[i])
                    if current_num < latest_num:
                        return True
                    elif current_num > latest_num:
                        return False
                except ValueError:
                    # إذا لم يكن رقم، مقارنة نصية
                    if current_parts[i] < latest_parts[i]:
                        return True
                    elif current_parts[i] > latest_parts[i]:
                        return False

            # إذا كانت جميع الأجزاء متساوية، تحقق من الطول
            return len(current_parts) < len(latest_parts)
        except Exception:
            return False

    @property
    def has_critical_vulns(self) -> bool:
        """هل تحتوي على ثغرات حرجة؟"""
        return any(v.severity == SecurityLevel.CRITICAL for v in self.vulnerabilities)


class DependencyAuditor:
    """مدقق التبعيات والأمان الآلي"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.requirements_file = self.project_root / "requirements.txt"
        self.audit_dir = self.project_root / "security_system" / "reports"
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # تصنيف التبعيات الأساسية
        self.dependency_categories = {
            # إطار العمل الأساسي
            "fastapi": DependencyCategory.CORE_FRAMEWORK,
            "uvicorn": DependencyCategory.CORE_FRAMEWORK,
            "starlette": DependencyCategory.CORE_FRAMEWORK,
            "pydantic": DependencyCategory.CORE_FRAMEWORK,
            # الأمان
            "cryptography": DependencyCategory.SECURITY,
            "passlib": DependencyCategory.SECURITY,
            "pyjwt": DependencyCategory.SECURITY,
            "argon2-cffi": DependencyCategory.SECURITY,
            "bcrypt": DependencyCategory.SECURITY,
            # حماية الأطفال
            "slowapi": DependencyCategory.CHILD_SAFETY,
            "fastapi-limiter": DependencyCategory.CHILD_SAFETY,
            "better-profanity": DependencyCategory.CHILD_SAFETY,
            "email-validator": DependencyCategory.CHILD_SAFETY,
            # الذكاء الاصطناعي
            "openai": DependencyCategory.AI_ML,
            "anthropic": DependencyCategory.AI_ML,
            "torch": DependencyCategory.AI_ML,
            "transformers": DependencyCategory.AI_ML,
            "sentence-transformers": DependencyCategory.AI_ML,
            # قاعدة البيانات
            "sqlalchemy": DependencyCategory.DATABASE,
            "asyncpg": DependencyCategory.DATABASE,
            "redis": DependencyCategory.DATABASE,
            "alembic": DependencyCategory.DATABASE,
            # المراقبة
            "prometheus-client": DependencyCategory.MONITORING,
            "sentry-sdk": DependencyCategory.MONITORING,
            "structlog": DependencyCategory.MONITORING,
            "loguru": DependencyCategory.MONITORING,
        }

    def parse_requirements(self) -> List[Tuple[str, str]]:
        """تحليل ملف requirements.txt"""
        dependencies = []

        if not self.requirements_file.exists():
            logger.error(f"Requirements file not found: {self.requirements_file}")
            return dependencies

        with open(self.requirements_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # استخراج اسم الحزمة والإصدار
                    if "==" in line:
                        name, version = line.split("==", 1)
                        name = name.split("[")[0].strip()  # إزالة extras
                        dependencies.append((name, version.strip()))
                    elif ">=" in line or "<=" in line or ">" in line or "<" in line:
                        # التعامل مع نطاقات الإصدارات
                        name = (
                            line.split(">=")[0]
                            .split("<=")[0]
                            .split(">")[0]
                            .split("<")[0]
                            .strip()
                        )
                        name = name.split("[")[0].strip()
                        dependencies.append((name, "flexible"))

        return dependencies

    def check_security_vulnerabilities(
        self, package: str, version: str
    ) -> List[SecurityVulnerability]:
        """فحص الثغرات الأمنية باستخدام OSV Database"""
        vulnerabilities = []

        try:
            # استخدام OSV API للفحص
            url = "https://api.osv.dev/v1/query"
            payload = {
                "package": {"name": package, "ecosystem": "PyPI"},
                "version": version,
            }

            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()

                for vuln in data.get("vulns", []):
                    severity = self._parse_severity(
                        vuln.get("database_specific", {}).get("severity")
                    )

                    vulnerability = SecurityVulnerability(
                        id=vuln.get("id", "UNKNOWN"),
                        package=package,
                        version=version,
                        severity=severity,
                        title=vuln.get("summary", "Security vulnerability"),
                        description=vuln.get("details", ""),
                        cve_id=(
                            vuln.get("aliases", [None])[0]
                            if vuln.get("aliases")
                            else None
                        ),
                    )
                    vulnerabilities.append(vulnerability)

        except Exception as e:
            logger.warning(f"Failed to check vulnerabilities for {package}: {e}")

        return vulnerabilities

    def _parse_severity(self, severity_str: str) -> SecurityLevel:
        """تحويل مستوى الخطورة"""
        if not severity_str:
            return SecurityLevel.MEDIUM

        severity_lower = severity_str.lower()
        if "critical" in severity_lower:
            return SecurityLevel.CRITICAL
        elif "high" in severity_lower:
            return SecurityLevel.HIGH
        elif "medium" in severity_lower:
            return SecurityLevel.MEDIUM
        elif "low" in severity_lower:
            return SecurityLevel.LOW
        else:
            return SecurityLevel.INFO

    def get_latest_version(self, package: str) -> Optional[str]:
        """الحصول على أحدث إصدار من PyPI"""
        try:
            url = f"https://pypi.org/pypi/{package}/json"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data["info"]["version"]
        except Exception as e:
            logger.warning(f"Failed to get latest version for {package}: {e}")
        return None

    def categorize_dependency(self, package: str) -> DependencyCategory:
        """تصنيف التبعية حسب أهميتها"""
        return self.dependency_categories.get(package, DependencyCategory.UTILITIES)

    def audit_dependencies(self) -> Dict[str, DependencyInfo]:
        """تدقيق شامل للتبعيات"""
        logger.info("🔍 Starting comprehensive dependency audit...")

        dependencies = self.parse_requirements()
        audit_results = {}

        for package, version in dependencies:
            logger.info(f"Auditing {package}=={version}")

            # جمع المعلومات الأساسية
            latest_version = self.get_latest_version(package)
            category = self.categorize_dependency(package)
            vulnerabilities = (
                self.check_security_vulnerabilities(package, version)
                if version != "flexible"
                else []
            )

            dependency_info = DependencyInfo(
                name=package,
                current_version=version,
                latest_version=latest_version or "unknown",
                category=category,
                is_pinned=(version != "flexible"),
                vulnerabilities=vulnerabilities,
            )

            audit_results[package] = dependency_info

        logger.info(f"✅ Audit completed for {len(dependencies)} dependencies")
        return audit_results

    def generate_security_report(
        self, audit_results: Dict[str, DependencyInfo]
    ) -> Dict:
        """إنشاء تقرير أمني شامل"""
        report = {
            "audit_date": datetime.now().isoformat(),
            "total_dependencies": len(audit_results),
            "summary": {
                "critical_vulnerabilities": 0,
                "high_vulnerabilities": 0,
                "medium_vulnerabilities": 0,
                "packages_with_vulns": 0,
                "packages_need_update": 0,
                "unpinned_packages": 0,
            },
            "critical_issues": [],
            "recommendations": [],
            "detailed_findings": {},
        }

        for package, info in audit_results.items():
            # إحصائيات
            if info.vulnerabilities:
                report["summary"]["packages_with_vulns"] += 1

            if info.has_critical_vulns:
                report["summary"]["critical_vulnerabilities"] += len(
                    [
                        v
                        for v in info.vulnerabilities
                        if v.severity == SecurityLevel.CRITICAL
                    ]
                )
                report["critical_issues"].append(
                    {
                        "package": package,
                        "issue": "Critical security vulnerabilities found",
                        "action": "Immediate update required",
                    }
                )

            if info.needs_update:
                report["summary"]["packages_need_update"] += 1

            if not info.is_pinned:
                report["summary"]["unpinned_packages"] += 1

            # تفاصيل كل حزمة
            report["detailed_findings"][package] = {
                "current_version": info.current_version,
                "latest_version": info.latest_version,
                "category": info.category.value,
                "vulnerabilities": [
                    {
                        "id": v.id,
                        "severity": v.severity.value,
                        "title": v.title,
                        "cve": v.cve_id,
                    }
                    for v in info.vulnerabilities
                ],
                "needs_update": info.needs_update,
                "is_pinned": info.is_pinned,
            }

        # توصيات
        if report["summary"]["critical_vulnerabilities"] > 0:
            report["recommendations"].append(
                "🚨 URGENT: Update packages with critical vulnerabilities immediately"
            )

        if report["summary"]["unpinned_packages"] > 5:
            report["recommendations"].append(
                "📌 Pin more package versions for reproducible builds"
            )

        if report["summary"]["packages_need_update"] > 10:
            report["recommendations"].append("🔄 Schedule regular dependency updates")

        return report

    def save_audit_report(self, report: Dict) -> Path:
        """حفظ تقرير التدقيق"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.audit_dir / f"security_audit_{timestamp}.json"

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"📄 Security audit report saved: {report_file}")
        return report_file

    def generate_requirements_lock(
        self, audit_results: Dict[str, DependencyInfo]
    ) -> Path:
        """إنشاء ملف requirements مع إصدارات مثبتة"""
        lock_file = self.project_root / "requirements-lock.txt"

        with open(lock_file, "w", encoding="utf-8") as f:
            f.write("# 🔒 AI TEDDY BEAR - LOCKED DEPENDENCIES\n")
            f.write(f"# Generated on: {datetime.now().isoformat()}\n")
            f.write("# This file contains exact versions for reproducible builds\n\n")

            # تجميع حسب الفئة
            categories = {}
            for package, info in audit_results.items():
                category = info.category
                if category not in categories:
                    categories[category] = []
                categories[category].append((package, info))

            # كتابة التبعيات مجمعة حسب الفئة
            for category, deps in categories.items():
                f.write(f"# {category.value.upper().replace('_', ' ')}\n")

                for package, info in sorted(deps, key=lambda x: x[0]):
                    version = info.current_version
                    if info.has_critical_vulns:
                        f.write(
                            f"# ⚠️ SECURITY WARNING: {package} has critical vulnerabilities\n"
                        )
                    if info.needs_update:
                        f.write(
                            f"# 🔄 UPDATE AVAILABLE: {package} -> {info.latest_version}\n"
                        )
                    f.write(f"{package}=={version}\n")
                f.write("\n")

        logger.info(f"🔐 Requirements lock file generated: {lock_file}")
        return lock_file


def main():
    """تشغيل التدقيق الشامل"""
    project_root = Path(__file__).parent.parent
    auditor = DependencyAuditor(project_root)

    print("🔍 Starting AI Teddy Bear Security Audit...")
    print("=" * 60)

    # تدقيق التبعيات
    audit_results = auditor.audit_dependencies()

    # إنشاء التقرير
    report = auditor.generate_security_report(audit_results)

    # حفظ التقرير
    report_file = auditor.save_audit_report(report)

    # إنشاء ملف الإصدارات المثبتة
    lock_file = auditor.generate_requirements_lock(audit_results)

    # عرض الملخص
    print("\n📊 SECURITY AUDIT SUMMARY")
    print("=" * 60)
    print(f"Total Dependencies: {report['total_dependencies']}")
    print(f"Critical Vulnerabilities: {report['summary']['critical_vulnerabilities']}")
    print(f"Packages with Vulnerabilities: {report['summary']['packages_with_vulns']}")
    print(f"Packages Need Update: {report['summary']['packages_need_update']}")
    print(f"Unpinned Packages: {report['summary']['unpinned_packages']}")

    if report["critical_issues"]:
        print(f"\n🚨 CRITICAL ISSUES: {len(report['critical_issues'])}")
        for issue in report["critical_issues"]:
            print(f"  - {issue['package']}: {issue['issue']}")

    print(f"\n📄 Report saved: {report_file}")
    print(f"🔐 Lock file created: {lock_file}")

    if report["summary"]["critical_vulnerabilities"] > 0:
        print("\n⚠️  IMMEDIATE ACTION REQUIRED!")
        return 1

    print("\n✅ Security audit completed successfully!")
    return 0


if __name__ == "__main__":
    exit(main())
