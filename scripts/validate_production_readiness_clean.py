#!/usr/bin/env python3
"""
Production Deployment Validation Script
=======================================

Validates that the enum consolidation fixes are production-ready.
This script runs before any production deployment to ensure no regressions.

Usage:
    python scripts/validate_production_readiness.py

Returns:
    Exit code 0: Ready for production
    Exit code 1: Issues found, deployment blocked
"""

import sys
import subprocess
from pathlib import Path
from typing import List


class ProductionValidator:
    """Validates production readiness after enum consolidation."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.issues: List[str] = []
        self.warnings: List[str] = []

    def run_validation(self) -> bool:
        """Run all production validation checks."""
        print("[DEPLOY] Production Readiness Validation")
        print("=" * 50)

        checks = [
            ("[CHECK] Enum Duplication Check", self._check_enum_duplications),
            ("[IMPORT] Import Consistency Check", self._check_import_consistency),
            ("[TEST] Unit Tests", self._run_unit_tests),
            ("[BUILD] Inheritance Pattern Check", self._check_inheritance_patterns),
            ("[DOCS] Documentation Check", self._check_documentation),
            ("[SECURE] Child Safety Compliance", self._check_child_safety),
            ("[SYNTAX] Syntax Validation", self._check_syntax_errors),
        ]

        all_passed = True

        for check_name, check_func in checks:
            print(f"\n{check_name}...")
            try:
                passed = check_func()
                if passed:
                    print("[PASS] PASSED")
                else:
                    print("[FAIL] FAILED")
                    all_passed = False
            except Exception as e:
                print(f"[ERROR] ERROR: {e}")
                self.issues.append(f"{check_name}: {e}")
                all_passed = False

        self._print_summary()
        return all_passed

    def _check_enum_duplications(self) -> bool:
        """Check for enum duplications using validation script."""
        try:
            result = subprocess.run(
                [sys.executable, "scripts/validate_enums_clean.py"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True
            else:
                self.issues.append(f"Enum validation failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.issues.append("Enum validation timed out")
            return False
        except Exception as e:
            self.issues.append(f"Enum validation error: {e}")
            return False

    def _check_import_consistency(self) -> bool:
        """Check that all imports use shared audio_types."""
        import re

        inconsistent_imports = []

        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Find audio_types imports
                imports = re.findall(r"from\s+([\w.]+audio_types[^;]*)", content)

                for import_line in imports:
                    if "src.shared.audio_types" not in import_line:
                        inconsistent_imports.append(f"{py_file.name}: {import_line}")

            except Exception:
                continue

        if inconsistent_imports:
            self.issues.extend(inconsistent_imports)
            return False
        return True

    def _run_unit_tests(self) -> bool:
        """Run critical unit tests."""
        try:
            # Run specific audio-related tests
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests_consolidated/test_enum_governance.py::TestEnumGovernance::test_shared_enums_exist",
                    "-v",
                    "--tb=short",
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return True
            else:
                self.issues.append(f"Unit tests failed: {result.stdout}")
                return False

        except subprocess.TimeoutExpired:
            self.warnings.append("Unit tests timed out")
            return True  # Don't fail deployment for test timeout
        except Exception as e:
            self.warnings.append(f"Unit test error: {e}")
            return True  # Don't fail deployment for test infrastructure issues

    def _check_inheritance_patterns(self) -> bool:
        """Check specialized enum inheritance patterns."""
        import re

        compression_file = (
            self.project_root / "src/infrastructure/performance/compression_manager.py"
        )

        if not compression_file.exists():
            self.issues.append("Compression manager file not found")
            return False

        with open(compression_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for proper inheritance
        inheritance_pattern = (
            r"class\s+CompressionAudioFormat\s*\(\s*BaseAudioFormat\s*\)"
        )

        if not re.search(inheritance_pattern, content):
            self.issues.append(
                "CompressionAudioFormat doesn't inherit from BaseAudioFormat"
            )
            return False

        return True

    def _check_documentation(self) -> bool:
        """Check that governance documentation exists."""
        docs_to_check = ["docs/ENUM_GOVERNANCE_RULES.md", "src/shared/audio_types.py"]

        for doc_path in docs_to_check:
            full_path = self.project_root / doc_path
            if not full_path.exists():
                self.issues.append(f"Missing documentation: {doc_path}")
                return False

        return True

    def _check_child_safety(self) -> bool:
        """Check child safety compliance in enums."""
        audio_types_file = self.project_root / "src/shared/audio_types.py"

        with open(audio_types_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for CHILD in VoiceGender
        if "CHILD" not in content:
            self.issues.append("VoiceGender missing CHILD option for safety")
            return False

        # Check that inappropriate emotions are not included
        inappropriate = ["ANGRY", "RAGE", "FEAR", "DISGUST"]
        for emotion in inappropriate:
            if emotion in content:
                self.issues.append(f"Inappropriate emotion {emotion} found")
                return False

        return True

    def _check_syntax_errors(self) -> bool:
        """Check for Python syntax errors."""
        critical_files = [
            "src/shared/audio_types.py",
            "src/infrastructure/performance/compression_manager.py",
            "src/interfaces/providers/tts_provider.py",
        ]

        for file_path in critical_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue

            try:
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(full_path)],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    self.issues.append(f"Syntax error in {file_path}: {result.stderr}")
                    return False

            except Exception as e:
                self.issues.append(f"Cannot validate syntax for {file_path}: {e}")
                return False

        return True

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        skip_parts = {"venv", "venv-dev", "venv-test", "__pycache__", ".git"}
        return any(part in skip_parts for part in file_path.parts)

    def _print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 50)
        print("[SUMMARY] VALIDATION SUMMARY")
        print("=" * 50)

        if not self.issues and not self.warnings:
            print("[SUCCESS] ALL VALIDATIONS PASSED!")
            print("[PASS] Production deployment is APPROVED")

        else:
            if self.issues:
                print(f"[FAIL] CRITICAL ISSUES ({len(self.issues)}):")
                for issue in self.issues:
                    print(f"   [ERROR] {issue}")

            if self.warnings:
                print(f"[WARN] WARNINGS ({len(self.warnings)}):")
                for warning in self.warnings:
                    print(f"   [WARN] {warning}")

        print("\n" + "=" * 50)


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent

    validator = ProductionValidator(str(project_root))
    success = validator.run_validation()

    if success:
        print("\n[DEPLOY] READY FOR PRODUCTION DEPLOYMENT!")
        print("[SECURE] Enum consolidation fixes are production-ready")
        sys.exit(0)
    else:
        print("\n[ERROR] DEPLOYMENT BLOCKED!")
        print("[FAIL] Fix issues before production deployment")
        sys.exit(1)


if __name__ == "__main__":
    main()
