#!/usr/bin/env python3
"""
Fix test imports after repair tool broke some imports
"""

import os
import re
from pathlib import Path


def fix_test_file(file_path: Path) -> int:
    """Fix broken imports in a test file."""
    fixes_made = 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix patterns
    replacements = [
        # Fix broken pytest import
        (r'# BROKEN: import pytest', 'import pytest'),
        # Fix broken imports that actually exist
        (r'# BROKEN: from src\.application\.services\.ai\.emotion_analyzer import EmotionAnalyzer, EmotionResult',
         'from src.application.services.ai.emotion_analyzer import EmotionAnalyzer, EmotionResult'),
        (r'# BROKEN: from src\.core\.value_objects\.age_group import AgeGroup',
         'from src.core.value_objects import AgeGroup'),
        (r'# BROKEN: from src\.infrastructure\.external\.openai_adapter import ProductionAIService',
         'from src.infrastructure.external.openai_adapter import OpenAIAdapter as ProductionAIService'),
        # Fix ResponseGenerator import
        (r'# BROKEN: from src\.application\.services\.ai\.modules\.response_generator import ResponseGenerator',
         '# ResponseGenerator moved to ai_service\nfrom src.application.services.ai.ai_service import AIService as ResponseGenerator'),
    ]
    
    for pattern, replacement in replacements:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            fixes_made += 1
    
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return fixes_made


def main():
    """Fix all test files."""
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "tests_consolidated"
    
    total_fixes = 0
    
    for test_file in test_dir.rglob("*.py"):
        if test_file.name.startswith("test_"):
            fixes = fix_test_file(test_file)
            if fixes > 0:
                print(f"Fixed {fixes} imports in {test_file}")
                total_fixes += fixes
    
    print(f"\nTotal fixes: {total_fixes}")


if __name__ == "__main__":
    main()