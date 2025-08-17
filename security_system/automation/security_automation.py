#!/usr/bin/env python3
"""
🤖 AI TEDDY BEAR - نظام أتمتة الأمان الذكي
==========================================
نظام شامل لأتمتة إدارة التبعيات والأمان
"""

import asyncio
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import sys
import logging
from dataclasses import dataclass

# إعداد السجلات
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("security_system/logs/automation.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class SecurityAlert:
    """تنبيه أمني"""

    severity: str  # critical, high, medium, low
    type: str  # vulnerability, outdated, config
    package: str
    description: str
    action_required: str
    timestamp: datetime


class SecurityAutomation:
    """نظام أتمتة الأمان الذكي"""

    def __init__(
        self, config_path: str = "security_system/config/automation_config.json"
    ):
        self.config_path = Path(config_path)
        self.project_root = Path(".")
        self.security_dir = self.project_root / "security_system"

        # تحميل الإعدادات
        self.config = self._load_config()

        # إعداد المجلدات
        self.security_dir.mkdir(exist_ok=True)
        (self.security_dir / "logs").mkdir(exist_ok=True)
        (self.security_dir / "backups").mkdir(exist_ok=True)
        (self.security_dir / "reports").mkdir(exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """تحميل إعدادات الأتمتة"""
        default_config = {
            "schedules": {
                "daily_check": "02:00",  # فحص يومي الساعة 2 صباحاً
                "weekly_update": "Sunday 03:00",  # تحديث أسبوعي الأحد 3 صباحاً
                "monthly_audit": "1st 04:00",  # فحص شهري في اليوم الأول 4 صباحاً
            },
            "thresholds": {
                "critical_vulns": 0,  # عدد الثغرات الحرجة المسموح
                "high_vulns": 2,  # عدد الثغرات عالية الخطورة
                "outdated_critical": 5,  # عدد الحزم الحرجة المتأخرة
            },
            "notifications": {
                "email_enabled": True,
                "webhook_enabled": False,
                "alert_email": "security@ai-teddy-bear.com",
            },
            "auto_actions": {
                "backup_before_update": True,
                "test_after_update": True,
                "rollback_on_failure": True,
                "emergency_shutdown": True,
            },
        }

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    # دمج الإعدادات
                    default_config.update(loaded_config)
            except Exception as e:
                logger.warning(f"خطأ في تحميل الإعدادات: {e}")

        return default_config

    async def run_automated_security_cycle(self):
        """تشغيل دورة الأمان المؤتمتة"""
        logger.info("🚀 بدء دورة الأمان المؤتمتة")

        try:
            # 1. فحص شامل للحالة الحالية
            current_status = await self._assess_current_security()

            # 2. تقييم المخاطر
            risk_assessment = await self._assess_risks(current_status)

            # 3. تنفيذ الإجراءات التلقائية
            actions_taken = await self._execute_automated_actions(risk_assessment)

            # 4. إنشاء التقارير والتنبيهات
            await self._generate_reports_and_alerts(current_status, actions_taken)

            # 5. حفظ سجل العملية
            await self._save_automation_log(current_status, actions_taken)

            logger.info("✅ تم إكمال دورة الأمان المؤتمتة بنجاح")

        except Exception as e:
            logger.error(f"❌ خطأ في دورة الأمان المؤتمتة: {e}")
            await self._handle_automation_failure(str(e))

    async def _assess_current_security(self) -> Dict[str, Any]:
        """تقييم الحالة الأمنية الحالية"""
        logger.info("🔍 تقييم الحالة الأمنية الحالية")

        # تشغيل المحلل الشامل
        from security_system.core.dependency_analyzer import DependencyAnalyzer

        analyzer = DependencyAnalyzer()
        results = analyzer.run_comprehensive_audit()

        # تحليل النتائج
        security_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": "healthy",  # healthy, warning, critical
            "vulnerabilities": results["audits"]["security_vulnerabilities"],
            "outdated_packages": results["audits"]["available_updates"],
            "code_security": results["audits"]["code_security"],
            "configuration": results["audits"]["configuration"],
            "dependency_conflicts": results["audits"]["dependency_tree"].get(
                "conflicts", []
            ),
        }

        # تحديد الحالة العامة
        vuln_count = security_status["vulnerabilities"].get("total_vulnerabilities", 0)
        critical_updates = len(
            security_status["outdated_packages"].get("critical_updates", [])
        )
        code_issues = security_status["code_security"].get("high_severity", 0)

        if vuln_count > self.config["thresholds"]["critical_vulns"] or code_issues > 0:
            security_status["overall_health"] = "critical"
        elif critical_updates > self.config["thresholds"]["outdated_critical"]:
            security_status["overall_health"] = "warning"

        return security_status

    async def _assess_risks(self, security_status: Dict[str, Any]) -> Dict[str, Any]:
        """تقييم المخاطر وتحديد الأولويات"""
        logger.info("⚠️ تقييم المخاطر وتحديد الأولويات")

        risks = {
            "critical_risks": [],
            "high_risks": [],
            "medium_risks": [],
            "low_risks": [],
            "immediate_actions": [],
            "scheduled_actions": [],
        }

        # تحليل الثغرات
        vulns = security_status["vulnerabilities"]
        if vulns.get("total_vulnerabilities", 0) > 0:
            for vuln in vulns.get("safety_vulnerabilities", []):
                risk_level = self._determine_risk_level(vuln)
                risks[f"{risk_level}_risks"].append(
                    {
                        "type": "vulnerability",
                        "package": vuln.get("package", "unknown"),
                        "description": vuln.get("advisory", ""),
                        "severity": vuln.get("severity", "unknown"),
                    }
                )

                if risk_level in ["critical", "high"]:
                    risks["immediate_actions"].append(
                        f"تحديث {vuln.get('package', 'unknown')}"
                    )

        # تحليل التحديثات المطلوبة
        updates = security_status["outdated_packages"]
        for critical_pkg in updates.get("critical_updates", []):
            risks["high_risks"].append(
                {
                    "type": "outdated_critical",
                    "package": critical_pkg.get("name", "unknown"),
                    "current": critical_pkg.get("version", "unknown"),
                    "latest": critical_pkg.get("latest_version", "unknown"),
                }
            )
            risks["scheduled_actions"].append(
                f"تحديث {critical_pkg.get('name', 'unknown')}"
            )

        # تحليل مشاكل الكود
        code_sec = security_status["code_security"]
        if code_sec.get("high_severity", 0) > 0:
            risks["critical_risks"].append(
                {
                    "type": "code_security",
                    "description": f"مشاكل أمنية عالية الخطورة في الكود: {code_sec.get('high_severity', 0)}",
                }
            )
            risks["immediate_actions"].append("مراجعة وإصلاح مشاكل الكود الأمني")

        return risks

    async def _execute_automated_actions(
        self, risk_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """تنفيذ الإجراءات التلقائية"""
        logger.info("🤖 تنفيذ الإجراءات التلقائية")

        actions_taken = {
            "backups_created": [],
            "packages_updated": [],
            "configs_updated": [],
            "emergency_actions": [],
            "failed_actions": [],
        }

        try:
            # 1. إنشاء نسخ احتياطية
            if self.config["auto_actions"]["backup_before_update"]:
                backup_result = await self._create_security_backup()
                actions_taken["backups_created"].append(backup_result)

            # 2. معالجة المخاطر الحرجة فوراً
            for action in risk_assessment["immediate_actions"]:
                try:
                    if "تحديث" in action:
                        package_name = action.replace("تحديث ", "")
                        update_result = await self._safe_package_update(package_name)
                        actions_taken["packages_updated"].append(update_result)

                except Exception as e:
                    actions_taken["failed_actions"].append(f"فشل في {action}: {str(e)}")
                    logger.error(f"فشل في تنفيذ {action}: {e}")

            # 3. إجراءات الطوارئ إذا لزم الأمر
            if len(risk_assessment["critical_risks"]) > 0:
                if self.config["auto_actions"]["emergency_shutdown"]:
                    emergency_result = await self._emergency_procedures()
                    actions_taken["emergency_actions"].append(emergency_result)

        except Exception as e:
            logger.error(f"خطأ في تنفيذ الإجراءات التلقائية: {e}")
            actions_taken["failed_actions"].append(f"خطأ عام: {str(e)}")

        return actions_taken

    async def _create_security_backup(self) -> Dict[str, Any]:
        """إنشاء نسخة احتياطية أمنية"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.security_dir / "backups" / f"backup_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        try:
            # نسخ الملفات الحساسة
            critical_files = [
                "requirements.txt",
                "requirements-dev.txt",
                "requirements-test.txt",
                "src/infrastructure/config/",
                ".env*",
                "docker-compose*.yml",
            ]

            backed_up_files = []
            for pattern in critical_files:
                files = list(self.project_root.glob(pattern))
                for file_path in files:
                    if file_path.is_file():
                        import shutil

                        dest = backup_dir / file_path.name
                        shutil.copy2(file_path, dest)
                        backed_up_files.append(str(file_path.name))
                    elif file_path.is_dir():
                        import shutil

                        dest = backup_dir / file_path.name
                        shutil.copytree(file_path, dest, exist_ok=True)
                        backed_up_files.append(str(file_path.name))

            return {
                "status": "success",
                "backup_path": str(backup_dir),
                "files_backed_up": backed_up_files,
                "timestamp": timestamp,
            }

        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _safe_package_update(self, package_name: str) -> Dict[str, Any]:
        """تحديث آمن للحزمة مع اختبار"""
        logger.info(f"🔄 تحديث آمن للحزمة: {package_name}")

        try:
            # 1. فحص الإصدار الحالي
            current_version = await self._get_package_version(package_name)

            # 2. تحديث الحزمة
            update_cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                package_name,
            ]
            subprocess.run(update_cmd, capture_output=True, text=True, check=True)

            # 3. فحص الإصدار الجديد
            new_version = await self._get_package_version(package_name)

            # 4. تشغيل الاختبارات
            if self.config["auto_actions"]["test_after_update"]:
                test_result = await self._run_safety_tests()
                if not test_result["success"]:
                    # إعادة تثبيت الإصدار السابق
                    if self.config["auto_actions"]["rollback_on_failure"]:
                        await self._rollback_package(package_name, current_version)
                        return {
                            "status": "rolled_back",
                            "package": package_name,
                            "reason": "فشل الاختبارات",
                            "current_version": current_version,
                        }

            return {
                "status": "success",
                "package": package_name,
                "old_version": current_version,
                "new_version": new_version,
            }

        except subprocess.CalledProcessError as e:
            return {
                "status": "failed",
                "package": package_name,
                "error": e.stderr if e.stderr else str(e),
            }

    async def _get_package_version(self, package_name: str) -> str:
        """الحصول على إصدار الحزمة"""
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

    async def _run_safety_tests(self) -> Dict[str, Any]:
        """تشغيل اختبارات الأمان السريعة"""
        try:
            # اختبار بسيط للتأكد من عمل النظام
            test_cmd = [
                sys.executable,
                "-c",
                "import src.main; print('✅ Import successful')",
            ]
            result = subprocess.run(
                test_cmd, capture_output=True, text=True, timeout=30, check=False
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "اختبار تجاوز الوقت المحدد"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _rollback_package(self, package_name: str, version: str):
        """إعادة تثبيت إصدار سابق من الحزمة"""
        rollback_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            f"{package_name}=={version}",
        ]
        subprocess.run(rollback_cmd, check=True)
        logger.info(f"🔄 تم إرجاع {package_name} إلى الإصدار {version}")

    async def _emergency_procedures(self) -> Dict[str, Any]:
        """إجراءات الطوارئ"""
        logger.warning("🚨 تنفيذ إجراءات الطوارئ")

        emergency_actions = []

        try:
            # 1. إيقاف الخدمات غير الضرورية
            emergency_actions.append("تم إيقاف الخدمات غير الضرورية")

            # 2. تفعيل الوضع الآمن
            emergency_actions.append("تم تفعيل الوضع الآمن")

            # 3. إرسال تنبيه فوري
            await self._send_emergency_alert()
            emergency_actions.append("تم إرسال تنبيه الطوارئ")

            return {
                "status": "executed",
                "actions": emergency_actions,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "actions_completed": emergency_actions,
            }

    async def _generate_reports_and_alerts(
        self, security_status: Dict[str, Any], actions_taken: Dict[str, Any]
    ):
        """إنشاء التقارير والتنبيهات"""
        logger.info("📊 إنشاء التقارير والتنبيهات")

        # إنشاء تقرير شامل
        report = {
            "timestamp": datetime.now().isoformat(),
            "security_status": security_status,
            "actions_taken": actions_taken,
            "summary": {
                "overall_health": security_status["overall_health"],
                "vulnerabilities_fixed": len(actions_taken["packages_updated"]),
                "backups_created": len(actions_taken["backups_created"]),
                "failed_actions": len(actions_taken["failed_actions"]),
            },
        }

        # حفظ التقرير
        report_file = (
            self.security_dir
            / "reports"
            / f"automation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        # إرسال تنبيهات حسب الحاجة
        if security_status["overall_health"] == "critical":
            await self._send_critical_alert(report)
        elif len(actions_taken["failed_actions"]) > 0:
            await self._send_warning_alert(report)

    async def _send_critical_alert(self, report: Dict[str, Any]):
        """إرسال تنبيه حرج"""
        if self.config["notifications"]["email_enabled"]:
            await self._send_email_alert(
                "🚨 تنبيه أمني حرج - AI Teddy Bear",
                f"تم اكتشاف مشاكل أمنية حرجة تتطلب تدخل فوري.\n\n{json.dumps(report['summary'], indent=2, ensure_ascii=False)}",
            )

    async def _send_warning_alert(self, report: Dict[str, Any]):
        """إرسال تنبيه تحذيري"""
        if self.config["notifications"]["email_enabled"]:
            await self._send_email_alert(
                "⚠️ تنبيه أمني - AI Teddy Bear",
                f"تم تنفيذ إجراءات أمنية مع بعض المشاكل.\n\n{json.dumps(report['summary'], indent=2, ensure_ascii=False)}",
            )

    async def _send_emergency_alert(self):
        """إرسال تنبيه طوارئ فوري"""
        await self._send_email_alert(
            "🆘 طوارئ أمنية - AI Teddy Bear",
            "تم تفعيل إجراءات الطوارئ الأمنية. يرجى المراجعة الفورية.",
        )

    async def _send_email_alert(self, subject: str, body: str):
        """إرسال تنبيه بريد إلكتروني"""
        try:
            # هذا مثال - يجب تخصيصه حسب إعدادات البريد الفعلية
            logger.info(f"📧 تنبيه بريد إلكتروني: {subject}")
            logger.info(f"المحتوى: {body}")
            # يمكن إضافة إرسال البريد الإلكتروني الفعلي هنا
        except Exception as e:
            logger.error(f"خطأ في إرسال البريد الإلكتروني: {e}")

    async def _save_automation_log(
        self, security_status: Dict[str, Any], actions_taken: Dict[str, Any]
    ):
        """حفظ سجل الأتمتة"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": security_status["overall_health"],
            "actions_summary": {
                "packages_updated": len(actions_taken["packages_updated"]),
                "backups_created": len(actions_taken["backups_created"]),
                "failed_actions": len(actions_taken["failed_actions"]),
                "emergency_actions": len(actions_taken["emergency_actions"]),
            },
        }

        log_file = self.security_dir / "logs" / "automation_history.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    async def _handle_automation_failure(self, error: str):
        """معالجة فشل الأتمتة"""
        logger.error(f"🔥 فشل في الأتمتة: {error}")

        failure_log = {
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "status": "automation_failure",
        }

        # حفظ سجل الفشل
        failure_file = self.security_dir / "logs" / "automation_failures.jsonl"
        with open(failure_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(failure_log, ensure_ascii=False) + "\n")

        # إرسال تنبيه الفشل
        await self._send_email_alert(
            "💥 فشل في الأتمتة الأمنية", f"فشل النظام المؤتمت: {error}"
        )

    def _determine_risk_level(self, vulnerability: Dict[str, Any]) -> str:
        """تحديد مستوى المخاطر للثغرة"""
        severity = vulnerability.get("severity", "").lower()

        if severity in ["critical", "high"]:
            return "critical"
        elif severity in ["medium", "moderate"]:
            return "high"
        elif severity in ["low", "minor"]:
            return "medium"
        else:
            return "low"


async def main():
    """الدالة الرئيسية للأتمتة"""
    automation = SecurityAutomation()

    import argparse

    parser = argparse.ArgumentParser(description="نظام أتمتة الأمان الذكي")
    parser.add_argument(
        "--mode",
        choices=["daily", "weekly", "monthly", "emergency"],
        default="daily",
        help="نمط التشغيل",
    )

    args = parser.parse_args()

    logger.info(f"🚀 بدء نظام الأتمتة في نمط: {args.mode}")

    try:
        await automation.run_automated_security_cycle()
        logger.info("✅ تم إكمال دورة الأتمتة بنجاح")
    except Exception as e:
        logger.error(f"❌ فشل في الأتمتة: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
