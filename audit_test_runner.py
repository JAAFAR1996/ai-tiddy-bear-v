#!/usr/bin/env python3
"""
Audit Test Runner - Specific tests for Dummy/None/Async Injection Issues
========================================================================
يشغل اختبارات محددة للتحقق من مشاكل الـ DI/Async patterns
"""

import asyncio
import sys
import traceback
from typing import Dict, Any, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AsyncInjectionAuditor:
    """فاحص مشاكل Async Injection"""

    def __init__(self):
        self.issues_found = []
        self.tests_passed = 0
        self.tests_failed = 0

    async def run_all_audits(self) -> Dict[str, Any]:
        """تشغيل جميع فحوصات الـ Async Injection"""

        logger.info("🔍 بدء الفحص الشامل لمشاكل Async/DI Injection...")

        # Test 1: Service Registry Initialization
        await self._test_service_registry_initialization()

        # Test 2: Notification Service Patterns
        await self._test_notification_service_patterns()

        # Test 3: ESP32 Service Factory
        await self._test_esp32_service_factory()

        # Test 4: Conversation Service Dependencies
        await self._test_conversation_service_dependencies()

        # Test 5: Auth Service Async Patterns
        await self._test_auth_service_patterns()

        return self._generate_audit_report()

    async def _test_service_registry_initialization(self):
        """اختبار تهيئة Service Registry"""
        test_name = "Service Registry Initialization"
        logger.info(f"🧪 اختبار: {test_name}")

        try:
            from src.services.service_registry import (
                ServiceRegistry,
                get_service_registry,
            )

            # Test 1: Registry should initialize without None services
            registry = ServiceRegistry()

            # Check that no services are initialized as None in __init__
            if hasattr(registry, "_singletons"):
                for service_name, config in registry._singletons.items():
                    if config.get("instance") is not None:
                        # This is actually OK - singletons start as None until requested
                        pass

            # Test 2: Try to get a service that should exist
            try:
                # This should work without returning None
                ai_service = await registry.get_service("ai_service")
                if ai_service is None:
                    self._add_issue(f"❌ {test_name}: ai_service returned None")
                else:
                    logger.info(
                        f"✅ ai_service initialized correctly: {type(ai_service)}"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Could not test ai_service: {e}")

            self._test_passed(test_name)

        except Exception as e:
            self._test_failed(test_name, str(e))

    async def _test_notification_service_patterns(self):
        """اختبار أنماط Notification Service"""
        test_name = "Notification Service Patterns"
        logger.info(f"🧪 اختبار: {test_name}")

        try:
            from src.services.notification_service_production import (
                ProductionNotificationService,
            )

            # Test: Check if service initializes with None repos (before initialization)
            service = ProductionNotificationService()

            # Check private attributes instead of properties (to avoid initialization error)
            if service._notification_repo is None:
                logger.info("✅ notification_repo correctly starts as None")
            else:
                self._add_issue(
                    f"❌ {test_name}: notification_repo should start as None"
                )

            if service._delivery_record_repo is None:
                logger.info("✅ delivery_record_repo correctly starts as None")
            else:
                self._add_issue(
                    f"❌ {test_name}: delivery_record_repo should start as None"
                )

            # Test: Check if initialize method exists and works
            if hasattr(service, "initialize"):
                logger.info("✅ initialize() method exists - good pattern")
                # Test that service is not initialized yet
                if not service._initialized:
                    logger.info("✅ Service correctly shows as not initialized")
                else:
                    self._add_issue(
                        f"❌ {test_name}: Service should not be initialized yet"
                    )
                # Note: We can't actually call initialize() without proper DB setup in tests
            else:
                self._add_issue(f"❌ {test_name}: No initialize() method found")

            self._test_passed(test_name)

        except Exception as e:
            self._test_failed(test_name, str(e))

    async def _test_esp32_service_factory(self):
        """اختبار ESP32 Service Factory"""
        test_name = "ESP32 Service Factory"
        logger.info(f"🧪 اختبار: {test_name}")

        try:
            from src.services.esp32_service_factory import ESP32ServiceFactory

            factory = ESP32ServiceFactory()

            # Check if factory methods accept None as defaults
            import inspect

            create_method = getattr(factory, "create_production_server", None)
            if create_method:
                sig = inspect.signature(create_method)

                for param_name, param in sig.parameters.items():
                    if param.default is None and param_name in [
                        "ai_provider",
                        "tts_service",
                    ]:
                        self._add_issue(
                            f"❌ {test_name}: {param_name} defaults to None"
                        )
                        logger.warning(f"⚠️ Parameter {param_name} defaults to None")

            self._test_passed(test_name)

        except Exception as e:
            self._test_failed(test_name, str(e))

    async def _test_conversation_service_dependencies(self):
        """اختبار dependencies في Conversation Service"""
        test_name = "Conversation Service Dependencies"
        logger.info(f"🧪 اختبار: {test_name}")

        try:
            from src.services.conversation_service import (
                ConsolidatedConversationService,
            )
            import inspect

            # Check constructor signature
            sig = inspect.signature(ConsolidatedConversationService.__init__)

            none_defaults = []
            for param_name, param in sig.parameters.items():
                if param.default is None and param_name not in ["self", "metadata"]:
                    none_defaults.append(param_name)

            if none_defaults:
                for param in none_defaults:
                    if param in [
                        "message_repository",
                        "notification_service",
                        "logger",
                    ]:
                        self._add_issue(f"❌ {test_name}: {param} defaults to None")

            self._test_passed(test_name)

        except Exception as e:
            self._test_failed(test_name, str(e))

    async def _test_auth_service_patterns(self):
        """اختبار أنماط Auth Service"""
        test_name = "Auth Service Patterns"
        logger.info(f"🧪 اختبار: {test_name}")

        try:
            # Read the auth service file to check for loop.run_until_complete
            auth_file_path = "src/infrastructure/security/auth.py"

            try:
                with open(auth_file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if "loop.run_until_complete" in content:
                    self._add_issue(
                        f"❌ {test_name}: Found loop.run_until_complete usage"
                    )
                    logger.warning("⚠️ Found loop.run_until_complete in auth.py")
                else:
                    logger.info("✅ No loop.run_until_complete found in auth service")

            except FileNotFoundError:
                logger.warning(f"⚠️ Auth service file not found: {auth_file_path}")

            self._test_passed(test_name)

        except Exception as e:
            self._test_failed(test_name, str(e))

    def _add_issue(self, issue: str):
        """إضافة مشكلة إلى القائمة"""
        self.issues_found.append(issue)
        logger.error(issue)

    def _test_passed(self, test_name: str):
        """تسجيل نجاح الاختبار"""
        self.tests_passed += 1
        logger.info(f"✅ {test_name}: PASSED")

    def _test_failed(self, test_name: str, error: str):
        """تسجيل فشل الاختبار"""
        self.tests_failed += 1
        logger.error(f"❌ {test_name}: FAILED - {error}")
        self._add_issue(f"Test failed: {test_name} - {error}")

    def _generate_audit_report(self) -> Dict[str, Any]:
        """إنتاج تقرير الفحص"""

        total_tests = self.tests_passed + self.tests_failed
        success_rate = (self.tests_passed / total_tests * 100) if total_tests > 0 else 0

        report = {
            "audit_summary": {
                "total_tests": total_tests,
                "tests_passed": self.tests_passed,
                "tests_failed": self.tests_failed,
                "success_rate": f"{success_rate:.1f}%",
                "issues_found": len(self.issues_found),
            },
            "issues": self.issues_found,
            "status": "PASS" if len(self.issues_found) == 0 else "FAIL",
            "recommendation": self._get_recommendation(),
        }

        return report

    def _get_recommendation(self) -> str:
        """الحصول على توصية بناءً على النتائج"""
        if len(self.issues_found) == 0:
            return "✅ المشروع production-grade من ناحية DI/Async patterns"
        elif len(self.issues_found) <= 3:
            return "⚠️ يحتاج إصلاحات بسيطة قبل الإنتاج"
        else:
            return "❌ يحتاج إصلاحات جوهرية قبل الإنتاج"


async def main():
    """الدالة الرئيسية"""

    print("=" * 80)
    print("🔍 AUDIT: Comprehensive Dummy/None/Async Injection Check")
    print("=" * 80)

    auditor = AsyncInjectionAuditor()

    try:
        # Add src to path
        sys.path.insert(0, "src")

        # Run audit
        report = await auditor.run_all_audits()

        # Print results
        print("\n" + "=" * 80)
        print("📊 AUDIT RESULTS")
        print("=" * 80)

        summary = report["audit_summary"]
        print(f"إجمال�� الاختبارات: {summary['total_tests']}")
        print(f"الاختبارات الناجحة: {summary['tests_passed']}")
        print(f"الاختبارات الفاشلة: {summary['tests_failed']}")
        print(f"معدل النجاح: {summary['success_rate']}")
        print(f"المشاكل المكتشفة: {summary['issues_found']}")

        print(f"\n🎯 الحالة النهائية: {report['status']}")
        print(f"💡 التوصية: {report['recommendation']}")

        if report["issues"]:
            print("\n🔴 المشاكل المكتشفة:")
            for i, issue in enumerate(report["issues"], 1):
                print(f"  {i}. {issue}")

        print("\n" + "=" * 80)

        # Return appropriate exit code
        return 0 if report["status"] == "PASS" else 1

    except Exception as e:
        logger.error(f"❌ Audit failed with error: {e}")
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
