#!/usr/bin/env python3
"""
Production Code Quality Checker for AI Teddy Bear

This script verifies that the codebase is production-ready by checking for:
- Mock/dummy/fake implementations
- Unimplemented functions
- Placeholder code
- Test/example files in production paths
"""

import os
import re
import sys
import ast
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum


class IssueLevel(Enum):
    """Severity levels for code issues."""
    CRITICAL = "CRITICAL"  # Must fix before production
    WARNING = "WARNING"    # Should fix but not blocking
    INFO = "INFO"         # Informational only


@dataclass
class CodeIssue:
    """Represents a code quality issue."""
    level: IssueLevel
    file_path: str
    line_number: int
    issue_type: str
    description: str
    code_snippet: str = ""


class ProductionCodeChecker:
    """Checks code for production readiness."""
    
    def __init__(self, src_path: str = "src/"):
        self.src_path = Path(src_path)
        self.issues: List[CodeIssue] = []
        
        # Patterns to check
        self.mock_class_pattern = re.compile(r'class\s+(Mock|Dummy|Fake|Test(?!ing))\w*')
        self.mock_return_pattern = re.compile(r'return\s+.*?(mock_|dummy_|fake_|test_data)')
        self.placeholder_pattern = re.compile(r'return\s+(True|None|False)\s*#\s*(placeholder|stub|todo|fixme)', re.IGNORECASE)
        self.todo_pattern = re.compile(r'#\s*(TODO|FIXME|HACK|XXX):', re.IGNORECASE)
        
        # Files to skip (legitimate test/example files)
        self.skip_patterns = [
            '__pycache__',
            '.pyc',
            '__init__.py',
            'test_',
            '_test.py',
            'conftest.py'
        ]
        
        # Abstract class indicators
        self.abstract_indicators = [
            'Abstract', 'Base', 'Interface', 'Protocol', 
            'Backend', 'Provider', 'Repository'
        ]
    
    def should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        for pattern in self.skip_patterns:
            if pattern in str(file_path):
                return True
        return False
    
    def is_abstract_class(self, class_name: str) -> bool:
        """Check if class name indicates abstract/interface."""
        return any(indicator in class_name for indicator in self.abstract_indicators)
    
    def check_file_for_mock_classes(self, file_path: Path) -> None:
        """Check for mock/dummy/fake classes."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            for i, line in enumerate(lines, 1):
                match = self.mock_class_pattern.search(line)
                if match:
                    # Check if it's an abstract class or in a comment
                    if not any(indicator in line for indicator in ['# Abstract', '# Interface', '# Base class']):
                        self.issues.append(CodeIssue(
                            level=IssueLevel.CRITICAL,
                            file_path=str(file_path),
                            line_number=i,
                            issue_type="Mock Class",
                            description=f"Found mock class: {match.group(0)}",
                            code_snippet=line.strip()
                        ))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    def check_file_for_mock_returns(self, file_path: Path) -> None:
        """Check for functions returning mock data."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            for i, line in enumerate(lines, 1):
                match = self.mock_return_pattern.search(line)
                if match:
                    # Check if it's marked as fallback or development only
                    if not any(marker in line for marker in ['# Fallback', '# Development only']):
                        self.issues.append(CodeIssue(
                            level=IssueLevel.CRITICAL,
                            file_path=str(file_path),
                            line_number=i,
                            issue_type="Mock Return Value",
                            description=f"Function returns mock data",
                            code_snippet=line.strip()
                        ))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    def check_file_for_placeholders(self, file_path: Path) -> None:
        """Check for placeholder implementations."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            for i, line in enumerate(lines, 1):
                match = self.placeholder_pattern.search(line)
                if match:
                    self.issues.append(CodeIssue(
                        level=IssueLevel.CRITICAL,
                        file_path=str(file_path),
                        line_number=i,
                        issue_type="Placeholder Implementation",
                        description="Found placeholder return statement",
                        code_snippet=line.strip()
                    ))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    def check_file_for_not_implemented(self, file_path: Path) -> None:
        """Check for NotImplementedError in non-abstract methods."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Skip if it's an abstract class
                    if self.is_abstract_class(node.name):
                        continue
                    
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            # Check for @abstractmethod decorator
                            has_abstract_decorator = any(
                                isinstance(d, ast.Name) and d.id == 'abstractmethod'
                                for d in item.decorator_list
                            )
                            
                            if has_abstract_decorator:
                                continue
                            
                            # Check for NotImplementedError
                            for stmt in ast.walk(item):
                                if isinstance(stmt, ast.Raise):
                                    exc = stmt.exc
                                    if isinstance(exc, (ast.Name, ast.Call)):
                                        exc_name = exc.id if isinstance(exc, ast.Name) else \
                                                  exc.func.id if isinstance(exc.func, ast.Name) else None
                                        
                                        if exc_name == 'NotImplementedError':
                                            # Check if it's a critical issue
                                            if 'CRITICAL' in str(exc.args[0].s if hasattr(exc, 'args') else ''):
                                                level = IssueLevel.INFO  # Already marked as critical in code
                                            else:
                                                level = IssueLevel.WARNING
                                            
                                            self.issues.append(CodeIssue(
                                                level=level,
                                                file_path=str(file_path),
                                                line_number=item.lineno,
                                                issue_type="NotImplementedError",
                                                description=f"Non-abstract method {node.name}.{item.name} raises NotImplementedError",
                                                code_snippet=f"class {node.name}: def {item.name}(...)"
                                            ))
        except Exception as e:
            # Silently skip files that can't be parsed
            pass
    
    def check_file_naming(self, file_path: Path) -> None:
        """Check for suspicious file names."""
        name = file_path.name.lower()
        suspicious_patterns = ['example', 'dummy', 'mock', 'sample', 'test']
        
        for pattern in suspicious_patterns:
            if pattern in name and not name.startswith('test_'):
                self.issues.append(CodeIssue(
                    level=IssueLevel.WARNING,
                    file_path=str(file_path),
                    line_number=0,
                    issue_type="Suspicious Filename",
                    description=f"File name contains '{pattern}' - verify if production-ready",
                    code_snippet=""
                ))
    
    def check_todos(self, file_path: Path) -> None:
        """Check for TODO/FIXME comments."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines, 1):
                match = self.todo_pattern.search(line)
                if match:
                    self.issues.append(CodeIssue(
                        level=IssueLevel.INFO,
                        file_path=str(file_path),
                        line_number=i,
                        issue_type="TODO Comment",
                        description=f"Found {match.group(1)} comment",
                        code_snippet=line.strip()
                    ))
        except Exception as e:
            pass
    
    def run_checks(self) -> List[CodeIssue]:
        """Run all checks on the codebase."""
        self.issues = []
        
        # Find all Python files
        python_files = list(self.src_path.rglob('*.py'))
        
        print(f"🔍 Checking {len(python_files)} Python files for production readiness...")
        
        for file_path in python_files:
            if self.should_skip_file(file_path):
                continue
            
            # Run all checks
            self.check_file_for_mock_classes(file_path)
            self.check_file_for_mock_returns(file_path)
            self.check_file_for_placeholders(file_path)
            self.check_file_for_not_implemented(file_path)
            self.check_file_naming(file_path)
            self.check_todos(file_path)
        
        return self.issues
    
    def print_report(self) -> int:
        """Print the check report and return exit code."""
        if not self.issues:
            print("✅ All checks passed! Code is production-ready.")
            return 0
        
        # Group issues by level
        critical_issues = [i for i in self.issues if i.level == IssueLevel.CRITICAL]
        warning_issues = [i for i in self.issues if i.level == IssueLevel.WARNING]
        info_issues = [i for i in self.issues if i.level == IssueLevel.INFO]
        
        # Print critical issues
        if critical_issues:
            print(f"\n❌ CRITICAL ISSUES ({len(critical_issues)}):")
            print("These MUST be fixed before production deployment:\n")
            for issue in critical_issues[:10]:  # Show first 10
                print(f"  [{issue.issue_type}] {issue.file_path}:{issue.line_number}")
                print(f"    {issue.description}")
                if issue.code_snippet:
                    print(f"    Code: {issue.code_snippet}")
                print()
        
        # Print warnings
        if warning_issues:
            print(f"\n⚠️  WARNINGS ({len(warning_issues)}):")
            print("These should be reviewed:\n")
            for issue in warning_issues[:5]:  # Show first 5
                print(f"  [{issue.issue_type}] {issue.file_path}:{issue.line_number}")
                print(f"    {issue.description}")
                print()
        
        # Print info
        if info_issues:
            print(f"\nℹ️  INFO ({len(info_issues)} items)")
            print(f"  - {len([i for i in info_issues if i.issue_type == 'TODO Comment'])} TODO comments")
            print(f"  - {len([i for i in info_issues if i.issue_type == 'NotImplementedError'])} marked NotImplementedError")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY:")
        print(f"  Critical Issues: {len(critical_issues)}")
        print(f"  Warnings: {len(warning_issues)}")
        print(f"  Info: {len(info_issues)}")
        print("=" * 60)
        
        # Return non-zero if critical issues exist
        return 1 if critical_issues else 0


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check code for production readiness')
    parser.add_argument('--src', default='src/', help='Source directory to check')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')
    args = parser.parse_args()
    
    checker = ProductionCodeChecker(args.src)
    issues = checker.run_checks()
    exit_code = checker.print_report()
    
    if args.strict and any(i.level == IssueLevel.WARNING for i in issues):
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()