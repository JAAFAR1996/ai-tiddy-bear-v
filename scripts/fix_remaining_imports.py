#!/usr/bin/env python3
"""
Fix remaining broken imports in test files
"""

import os
import re
from pathlib import Path


def fix_test_imports(root_path: Path):
    """Fix all broken imports in test files."""
    
    # Define import fixes
    import_fixes = {
        # Exception imports
        r'# BROKEN: from src\.core\.exceptions import AuthenticationError, InvalidTokenError':
            'from src.core.exceptions import AuthenticationError, InvalidTokenError',
        r'# BROKEN: from src\.core\.exceptions import SafetyViolationError':
            'from src.core.exceptions import SafetyViolationError',
        r'# BROKEN: from src\.core\.exceptions import ConversationNotFoundError':
            'from src.core.exceptions import ConversationNotFoundError',
        
        # Value object imports
        r'# BROKEN: from src\.core\.value_objects import AgeGroup':
            'from src.core.value_objects import AgeGroup',
        
        # Service imports
        r'# BROKEN: from src\.application\.services\.ai\.emotion_analyzer import EmotionAnalyzer, EmotionResult':
            'from src.application.services.ai.emotion_analyzer import EmotionAnalyzer, EmotionResult',
        r'# BROKEN: from src\.infrastructure\.external\.openai_adapter import OpenAIAdapter as ProductionAIService':
            'from src.infrastructure.external.openai_adapter import OpenAIAdapter as ProductionAIService',
            
        # Interface imports that need fixing
        r'from src\.interfaces\.services import IAuthService':
            'from src.interfaces.services import IAuthenticationService as IAuthService',
    }
    
    # Find all test files
    test_files = []
    for test_dir in ['tests', 'tests_consolidated']:
        test_path = root_path / test_dir
        if test_path.exists():
            test_files.extend(test_path.rglob('*.py'))
    
    fixed_count = 0
    
    for test_file in test_files:
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Apply fixes
            for pattern, replacement in import_fixes.items():
                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    fixed_count += 1
            
            # Save if changed
            if content != original_content:
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Fixed imports in {test_file}")
                
        except Exception as e:
            print(f"Error processing {test_file}: {e}")
    
    return fixed_count


def create_missing_exception_classes(root_path: Path):
    """Ensure all exception classes exist."""
    exceptions_file = root_path / "src" / "core" / "exceptions.py"
    
    exception_content = '''"""
Core exceptions for AI Teddy Bear application
"""


class AITeddyBearException(Exception):
    """Base exception for all application exceptions."""
    pass


class AuthenticationError(AITeddyBearException):
    """Raised when authentication fails."""
    pass


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid or expired."""
    pass


class AuthorizationError(AITeddyBearException):
    """Raised when user lacks required permissions."""
    pass


class SafetyViolationError(AITeddyBearException):
    """Raised when content violates child safety rules."""
    
    def __init__(self, message: str, violations: list = None):
        super().__init__(message)
        self.violations = violations or []


class ConversationNotFoundError(AITeddyBearException):
    """Raised when requested conversation does not exist."""
    pass


class ChildNotFoundError(AITeddyBearException):
    """Raised when requested child profile does not exist."""
    pass


class ValidationError(AITeddyBearException):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, errors: dict = None):
        super().__init__(message)
        self.errors = errors or {}


class ExternalServiceError(AITeddyBearException):
    """Raised when external service call fails."""
    pass


class RateLimitError(AITeddyBearException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after
'''
    
    # Create directory if needed
    exceptions_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write exceptions file
    with open(exceptions_file, 'w', encoding='utf-8') as f:
        f.write(exception_content)
    
    print(f"Created exceptions file at {exceptions_file}")


def create_missing_value_objects(root_path: Path):
    """Ensure value objects exist."""
    vo_file = root_path / "src" / "core" / "value_objects.py"
    
    vo_content = '''"""
Core value objects for AI Teddy Bear application
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class AgeGroup(Enum):
    """Age group classifications for content filtering."""
    TODDLER = "toddler"  # 0-3 years
    PRESCHOOL = "preschool"  # 3-5 years
    EARLY_SCHOOL = "early_school"  # 5-7 years
    MIDDLE_SCHOOL = "middle_school"  # 7-9 years
    LATE_SCHOOL = "late_school"  # 9-11 years
    PRETEEN = "preteen"  # 11-13 years
    
    # Broader categories
    UNDER_5 = "under_5"
    UNDER_8 = "under_8"
    UNDER_13 = "under_13"
    
    @classmethod
    def from_age(cls, age: int) -> 'AgeGroup':
        """Get age group from numeric age."""
        if age < 3:
            return cls.TODDLER
        elif age < 5:
            return cls.PRESCHOOL
        elif age < 7:
            return cls.EARLY_SCHOOL
        elif age < 9:
            return cls.MIDDLE_SCHOOL
        elif age < 11:
            return cls.LATE_SCHOOL
        else:
            return cls.PRETEEN


@dataclass(frozen=True)
class SafetyScore:
    """Safety score for content validation."""
    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    violations: list[str]
    
    @property
    def is_safe(self) -> bool:
        """Check if content is safe based on score."""
        return self.score >= 0.8 and len(self.violations) == 0
    
    @property
    def severity(self) -> str:
        """Get severity level."""
        if self.score >= 0.9:
            return "safe"
        elif self.score >= 0.7:
            return "low"
        elif self.score >= 0.5:
            return "medium"
        else:
            return "high"


@dataclass(frozen=True)
class EmotionResult:
    """Result of emotion analysis."""
    primary_emotion: str
    confidence: float
    secondary_emotions: list[str] = None
    
    def __post_init__(self):
        if self.secondary_emotions is None:
            object.__setattr__(self, 'secondary_emotions', [])


@dataclass(frozen=True)
class ContentComplexity:
    """Content complexity rating."""
    level: str  # "simple", "moderate", "complex"
    vocabulary_score: float
    sentence_complexity: float
    concept_difficulty: float
    
    @property
    def is_age_appropriate(self, age: int) -> bool:
        """Check if complexity is appropriate for age."""
        if age < 5 and self.level != "simple":
            return False
        elif age < 8 and self.level == "complex":
            return False
        return True
'''
    
    # Create directory if needed
    vo_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write value objects file
    with open(vo_file, 'w', encoding='utf-8') as f:
        f.write(vo_content)
    
    print(f"Created value objects file at {vo_file}")


def main():
    """Main function."""
    project_root = Path(__file__).parent.parent
    
    print("🔧 Fixing remaining test imports...")
    
    # Create missing core files
    create_missing_exception_classes(project_root)
    create_missing_value_objects(project_root)
    
    # Fix imports
    fixed_count = fix_test_imports(project_root)
    
    print(f"\n✅ Fixed {fixed_count} imports")
    print("✅ Created missing exception classes")
    print("✅ Created missing value objects")


if __name__ == "__main__":
    main()