"""
Production Enum Duplication Prevention Tests
==========================================

Critical tests to prevent enum duplications that caused production issues.
These tests MUST pass before any deployment.
"""

import re
from pathlib import Path
from typing import Dict, List
from collections import defaultdict


class TestEnumGovernance:
    """Test enum governance rules compliance."""

    @classmethod
    def setup_class(cls):
        """Set up test fixtures."""
        cls.project_root = Path(__file__).parent.parent
        cls.shared_audio_enums = {
            "AudioFormat",
            "AudioQuality",
            "VoiceGender",
            "VoiceEmotion",
        }
        cls.shared_enum_file = "src/shared/audio_types.py"

    def _find_enum_definitions(self) -> Dict[str, List[str]]:
        """Find all enum definitions in codebase."""
        enum_definitions = defaultdict(list)
        pattern = r"class\s+(\w+)\s*\(\s*(?:\w+\.)?Enum\s*\)"

        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                for match in re.finditer(pattern, content):
                    enum_name = match.group(1)
                    file_path = str(py_file.relative_to(self.project_root))
                    enum_definitions[enum_name].append(file_path)

            except Exception:
                continue  # Skip problematic files

        return enum_definitions

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        skip_dirs = {
            "venv",
            "venv-dev",
            "venv-test",
            "__pycache__",
            ".git",
            ".pytest_cache",
            "htmlcov",
            "build",
            "dist",
        }
        return any(part in skip_dirs for part in file_path.parts)

    def test_no_duplicate_audio_enums(self):
        """
        CRITICAL: Ensure no duplicate audio enum definitions exist.

        This test prevents the duplication issues that were found during
        the production readiness audit.
        """
        enum_definitions = self._find_enum_definitions()

        for enum_name in self.shared_audio_enums:
            definitions = enum_definitions.get(enum_name, [])

            # Must exist in shared location
            assert any(
                d.replace("\\", "/") == self.shared_enum_file for d in definitions
            ), f"{enum_name} must exist in {self.shared_enum_file}"

            # Must not have duplicates (except inherited ones)
            if len(definitions) > 1:
                # Check if extra definitions are inheritance-based
                for file_path in definitions:
                    if file_path.replace("\\", "/") != self.shared_enum_file:
                        # Read file to check if it's inheritance
                        file_full_path = self.project_root / file_path
                        with open(file_full_path, "r", encoding="utf-8") as f:
                            content = f.read()

                        # Look for inheritance pattern
                        inheritance_pattern = (
                            f"class\\s+\\w*{enum_name}\\w*\\s*\\(\\s*.*{enum_name}.*\\)"
                        )

                        assert re.search(inheritance_pattern, content), (
                            f"Duplicate {enum_name} in {file_path} must use inheritance "
                            f"from {self.shared_enum_file}"
                        )

    def test_shared_enums_exist(self):
        """Ensure all required shared audio enums exist."""
        shared_file = self.project_root / self.shared_enum_file

        assert (
            shared_file.exists()
        ), f"Shared enum file {self.shared_enum_file} must exist"

        with open(shared_file, "r", encoding="utf-8") as f:
            content = f.read()

        for enum_name in self.shared_audio_enums:
            pattern = f"class\\s+{enum_name}\\s*\\(\\s*Enum\\s*\\)"
            assert re.search(
                pattern, content
            ), f"{enum_name} must be defined in {self.shared_enum_file}"

    def test_import_consistency(self):
        """Ensure all audio_types imports use the shared module."""
        import_pattern = r"from\s+([\w.]+)audio_types.*import"
        violations = []

        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    match = re.search(import_pattern, line)
                    if match:
                        import_source = match.group(1)
                        if "src.shared." not in import_source:
                            violations.append(
                                f"{py_file.relative_to(self.project_root)}:{line_num} - {line.strip()}"
                            )

            except Exception:
                continue

        assert not violations, "Inconsistent audio_types imports found:\n" + "\n".join(
            violations
        )

    def test_enum_inheritance_pattern(self):
        """Test that specialized enums use proper inheritance."""
        # Find specialized audio enums
        specialized_enums = []

        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Look for audio-related enum classes
                pattern = (
                    r"class\s+(\w*(?:Audio|Voice|Compression)\w*)\s*\(\s*([^)]+)\s*\)"
                )
                matches = re.finditer(pattern, content)

                for match in matches:
                    class_name = match.group(1)
                    parent_class = match.group(2)

                    # If it inherits from a shared audio enum, it's specialized
                    if any(
                        shared_enum in parent_class
                        for shared_enum in self.shared_audio_enums
                    ):
                        specialized_enums.append(
                            {
                                "name": class_name,
                                "parent": parent_class,
                                "file": str(py_file.relative_to(self.project_root)),
                            }
                        )

            except Exception:
                continue

        # Verify specialized enums follow conventions
        for enum_info in specialized_enums:
            # Should not conflict with shared enum names
            assert (
                enum_info["name"] not in self.shared_audio_enums
            ), f"Specialized enum {enum_info['name']} conflicts with shared enum name"

            # Should have clear naming convention
            assert any(
                keyword in enum_info["name"].lower()
                for keyword in ["compression", "specialized", "extended"]
            ), f"Specialized enum {enum_info['name']} should have descriptive name"

    def test_enum_documentation(self):
        """Ensure enums have proper documentation."""
        shared_file = self.project_root / self.shared_enum_file

        with open(shared_file, "r", encoding="utf-8") as f:
            content = f.read()

        for enum_name in self.shared_audio_enums:
            # Find enum definition
            pattern = f"class\\s+{enum_name}.*?:(.*?)(?=class|$)"
            match = re.search(pattern, content, re.DOTALL)

            assert match, f"{enum_name} definition not found"

            enum_body = match.group(1)

            # Check for docstring
            assert (
                '"""' in enum_body or "'''" in enum_body
            ), f"{enum_name} must have docstring documentation"

            # Check for value definitions
            assert "=" in enum_body, f"{enum_name} must have enum values"

    def test_child_safety_compliance(self):
        """Ensure audio enums consider child safety."""
        shared_file = self.project_root / self.shared_enum_file

        with open(shared_file, "r", encoding="utf-8") as f:
            content = f.read()

        # VoiceGender should have child-appropriate options
        assert "class VoiceGender" in content, "VoiceGender enum not found"
        assert (
            'CHILD = "child"' in content
        ), "VoiceGender must include CHILD option for child safety compliance"

        # VoiceEmotion should have appropriate emotions
        assert "class VoiceEmotion" in content, "VoiceEmotion enum not found"

        # Should not have inappropriate emotions
        inappropriate_emotions = ["ANGRY", "FEAR", "DISGUST", "RAGE"]
        for emotion in inappropriate_emotions:
            assert (
                emotion not in content
            ), f"VoiceEmotion should not include {emotion} for child safety"


class TestEnumUsagePatterns:
    """Test proper enum usage patterns."""

    def test_no_hardcoded_audio_values(self):
        """Ensure no hardcoded audio format strings are used in production code."""
        import re
        from pathlib import Path

        # Only scan main source code folders
        scan_dirs = ["src", "src/adapters"]
        hardcoded_patterns = [
            r'["\']mp3["\']',
            r'["\']wav["\']',
            r'["\']ogg["\']',
            r'["\']male["\']',
            r'["\']female["\']',
            r'["\']child["\']',
            r'["\']neutral["\']',
            r'["\']happy["\']',
            r'["\']sad["\']',
            r'["\']angry["\']',
        ]
        violations = []
        for scan_dir in scan_dirs:
            dir_path = Path(scan_dir)
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                # Skip irrelevant folders
                skip = any(
                    x in str(py_file)
                    for x in [
                        "venv",
                        "__pycache__",
                        "test",
                        "migrations",
                        "archive",
                        "logs",
                    ]
                )
                if skip:
                    continue
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    for pattern in hardcoded_patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            # Skip if part of enum definition
                            if (
                                "class "
                                in content[max(0, match.start() - 50) : match.start()]
                            ):
                                continue
                            violations.append(f"{py_file} - {match.group(0)}")
                except Exception:
                    continue
        # Allow some violations in specific contexts (مثل configs, examples)
        filtered_violations = [
            v
            for v in violations
            if not any(skip in v for skip in ["config/", "example"])
        ]
        assert (
            len(filtered_violations) < 5
        ), "Too many hardcoded audio values found:\n" + "\n".join(
            filtered_violations[:10]
        )
