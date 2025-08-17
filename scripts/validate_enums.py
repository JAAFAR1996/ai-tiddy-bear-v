#!/usr/bin/env python3
"""
Production Enum Validation Script
================================

Validates that no duplicate enum definitions exist in the codebase.
Part of production governance to prevent enum duplication issues.

Usage:
    python scripts/validate_enums.py
    
Returns:
    Exit code 0: No duplications found
    Exit code 1: Duplications detected
"""

import re
import sys
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class EnumDefinition:
    """Represents an enum definition found in code."""
    name: str
    file_path: str
    line_number: int
    context: str


class EnumValidator:
    """Validates enum definitions across the codebase."""
    
    # Audio enums that should only exist in shared location
    SHARED_AUDIO_ENUMS = {
        'AudioFormat',
        'AudioQuality', 
        'VoiceGender',
        'VoiceEmotion'
    }
    
    # Expected location for shared enums
    SHARED_ENUM_FILE = 'src/shared/audio_types.py'
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.violations: List[str] = []
        self.enum_definitions: Dict[str, List[EnumDefinition]] = defaultdict(list)
    
    def find_enum_definitions(self) -> None:
        """Find all enum definitions in the codebase."""
        print("Scanning for enum definitions...")
        
        # Search for class definitions that inherit from Enum
        pattern = r'class\s+(\w+)\s*\(\s*(?:\w+\.)?Enum\s*\)'
        
        for py_file in self.project_root.rglob('*.py'):
            if self._should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    match = re.search(pattern, line)
                    if match:
                        enum_name = match.group(1)
                        
                        # Get context (few lines around the definition)
                        context_start = max(0, line_num - 2)
                        context_end = min(len(lines), line_num + 3)
                        context = ''.join(lines[context_start:context_end])
                        
                        enum_def = EnumDefinition(
                            name=enum_name,
                            file_path=str(py_file.relative_to(self.project_root)),
                            line_number=line_num,
                            context=context.strip()
                        )
                        
                        self.enum_definitions[enum_name].append(enum_def)
                        
            except Exception as e:
                print(f"⚠️  Error reading {py_file}: {e}")
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped during scanning."""
        skip_dirs = {
            'venv', 'venv-dev', 'venv-test', '__pycache__', 
            '.git', '.pytest_cache', 'htmlcov', 'build', 'dist'
        }
        
        # Skip if any parent directory is in skip list
        return any(part in skip_dirs for part in file_path.parts)
    
    def validate_shared_audio_enums(self) -> None:
        """Validate that shared audio enums exist only in designated location."""
        print("🎵 Validating shared audio enum definitions...")
        
        for enum_name in self.SHARED_AUDIO_ENUMS:
            definitions = self.enum_definitions.get(enum_name, [])
            
            if not definitions:
                self.violations.append(
                    f"❌ MISSING: {enum_name} not found in any file"
                )
                continue
            
            # Check if exists in shared location
            shared_definitions = [
                d for d in definitions 
                if d.file_path.replace('\\', '/') == self.SHARED_ENUM_FILE
            ]
            
            if not shared_definitions:
                self.violations.append(
                    f"❌ MISSING SHARED: {enum_name} not found in {self.SHARED_ENUM_FILE}"
                )
            
            # Check for duplicates
            if len(definitions) > 1:
                self.violations.append(
                    f"❌ DUPLICATE: {enum_name} defined in {len(definitions)} files:"
                )
                
                for definition in definitions:
                    self.violations.append(
                        f"    📁 {definition.file_path}:{definition.line_number}"
                    )
    
    def validate_inheritance_pattern(self) -> None:
        """Validate that specialized enums use proper inheritance."""
        print("🧬 Validating enum inheritance patterns...")
        
        # Look for specialized audio enums that should inherit
        specialized_patterns = [
            r'class\s+\w*Audio\w*\s*\(\s*.*AudioFormat.*\)',
            r'class\s+Compression\w*\s*\(\s*.*AudioFormat.*\)'
        ]
        
        for py_file in self.project_root.rglob('*.py'):
            if self._should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern in specialized_patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        # This is good - specialized enum using inheritance
                        print(f"✅ GOOD INHERITANCE: {match.group(0)} in {py_file.name}")
                        
            except Exception as e:
                print(f"⚠️  Error reading {py_file}: {e}")
    
    def validate_import_consistency(self) -> None:
        """Validate that imports use the shared audio_types module."""
        print("📦 Validating import consistency...")
        
        # Pattern to find audio_types imports
        import_pattern = r'from\s+[\w.]+audio_types.*import'
        
        inconsistent_imports = []
        
        for py_file in self.project_root.rglob('*.py'):
            if self._should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    if re.search(import_pattern, line):
                        # Check if importing from correct location
                        if 'src.shared.audio_types' not in line:
                            inconsistent_imports.append(
                                f"📁 {py_file.relative_to(self.project_root)}:{line_num} - {line.strip()}"
                            )
                            
            except Exception as e:
                print(f"⚠️  Error reading {py_file}: {e}")
        
        if inconsistent_imports:
            self.violations.append("❌ INCONSISTENT IMPORTS:")
            self.violations.extend(inconsistent_imports)
    
    def run_validation(self) -> bool:
        """Run all validations and return success status."""
        print("Starting enum validation...")
        print(f"Project root: {self.project_root}")
        print("-" * 60)
        
        self.find_enum_definitions()
        self.validate_shared_audio_enums()
        self.validate_inheritance_pattern()
        self.validate_import_consistency()
        
        print("-" * 60)
        
        if self.violations:
            print("❌ VALIDATION FAILURES:")
            for violation in self.violations:
                print(violation)
            return False
        else:
            print("✅ ALL VALIDATIONS PASSED!")
            self._print_summary()
            return True
    
    def _print_summary(self) -> None:
        """Print summary of found enums."""
        print("\n📊 ENUM SUMMARY:")
        print(f"📁 Shared audio enums location: {self.SHARED_ENUM_FILE}")
        
        for enum_name in self.SHARED_AUDIO_ENUMS:
            definitions = self.enum_definitions.get(enum_name, [])
            if definitions:
                print(f"✅ {enum_name}: {len(definitions)} definition(s)")
            else:
                print(f"❌ {enum_name}: Not found")


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    
    validator = EnumValidator(str(project_root))
    success = validator.run_validation()
    
    if success:
        print("\n🎉 Enum validation completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Enum validation failed!")
        print("\n🔧 To fix these issues:")
        print("1. Review ENUM_GOVERNANCE_RULES.md")
        print("2. Consolidate duplicate enums")
        print("3. Use inheritance for specialized cases")
        print("4. Update imports to use src.shared.audio_types")
        sys.exit(1)


if __name__ == '__main__':
    main()