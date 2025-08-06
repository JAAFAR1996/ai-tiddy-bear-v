#!/usr/bin/env python3
"""
Test Reality Check Script
Identifies fake tests, dead code, and import errors in the test suite.
"""

import ast
import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
import importlib.util
import re
from datetime import datetime

class TestRealityChecker:
    """Comprehensive test suite analyzer."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.tests_dir = project_root / "tests"
        self.src_dir = project_root / "src"
        self.report = {
            "scan_date": datetime.now().isoformat(),
            "fake_tests": [],
            "import_errors": [],
            "dead_tests": [],
            "empty_assertions": [],
            "skipped_tests": [],
            "todo_tests": [],
            "pass_only_tests": [],
            "missing_source_files": [],
            "test_stats": {}
        }
    
    def scan_all_tests(self):
        """Run comprehensive test scan."""
        print("🔍 Starting Test Reality Check...")
        
        # Collect all test files
        test_files = list(self.tests_dir.rglob("test_*.py"))
        print(f"Found {len(test_files)} test files")
        
        for test_file in test_files:
            self.analyze_test_file(test_file)
        
        # Check for orphaned tests
        self.check_orphaned_tests()
        
        # Generate report
        self.generate_report()
    
    def analyze_test_file(self, test_file: Path):
        """Analyze a single test file."""
        relative_path = test_file.relative_to(self.project_root)
        print(f"  Analyzing: {relative_path}")
        
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
            
            # Check imports
            self.check_imports(test_file, tree)
            
            # Analyze test functions
            self.analyze_test_functions(test_file, tree, content)
            
        except Exception as e:
            self.report["import_errors"].append({
                "file": str(relative_path),
                "error": str(e),
                "type": "parse_error"
            })
    
    def check_imports(self, test_file: Path, tree: ast.AST):
        """Check for import errors."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.verify_import(test_file, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.verify_import(test_file, node.module, is_from=True)
    
    def verify_import(self, test_file: Path, module_name: str, is_from: bool = False):
        """Verify that an import is valid."""
        try:
            # Handle relative imports and project imports
            if module_name.startswith('src.'):
                module_path = self.project_root / module_name.replace('.', '/')
                if is_from:
                    # Check if it's a module directory or file
                    if not (module_path.exists() or (module_path.with_suffix('.py')).exists()):
                        self.report["import_errors"].append({
                            "file": str(test_file.relative_to(self.project_root)),
                            "module": module_name,
                            "error": "Module not found in project"
                        })
            else:
                # Try to import external module
                spec = importlib.util.find_spec(module_name)
                if spec is None:
                    self.report["import_errors"].append({
                        "file": str(test_file.relative_to(self.project_root)),
                        "module": module_name,
                        "error": "External module not found"
                    })
        except Exception as e:
            self.report["import_errors"].append({
                "file": str(test_file.relative_to(self.project_root)),
                "module": module_name,
                "error": str(e)
            })
    
    def analyze_test_functions(self, test_file: Path, tree: ast.AST, content: str):
        """Analyze test functions for quality issues."""
        relative_path = test_file.relative_to(self.project_root)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                # Check for various test quality issues
                self.check_fake_test(test_file, node, content)
                self.check_skipped_test(test_file, node, content)
                self.check_empty_assertions(test_file, node)
    
    def check_fake_test(self, test_file: Path, func_node: ast.FunctionDef, content: str):
        """Check if test is fake (only pass, NotImplementedError, etc)."""
        relative_path = test_file.relative_to(self.project_root)
        
        # Check for pass-only tests
        if len(func_node.body) == 1 and isinstance(func_node.body[0], ast.Pass):
            self.report["pass_only_tests"].append({
                "file": str(relative_path),
                "function": func_node.name,
                "line": func_node.lineno
            })
            return
        
        # Check for NotImplementedError
        for node in ast.walk(func_node):
            if isinstance(node, ast.Raise):
                if isinstance(node.exc, ast.Call):
                    if hasattr(node.exc.func, 'id') and node.exc.func.id == 'NotImplementedError':
                        self.report["todo_tests"].append({
                            "file": str(relative_path),
                            "function": func_node.name,
                            "line": func_node.lineno
                        })
                        return
        
        # Check for assert True only
        has_real_assertion = False
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                # Check if it's not just assert True
                if not (isinstance(node.test, ast.Constant) and node.test.value is True):
                    has_real_assertion = True
                    break
        
        if not has_real_assertion:
            # Check if there are any assertions at all
            has_any_assertion = any(isinstance(node, ast.Assert) for node in ast.walk(func_node))
            if has_any_assertion:
                self.report["fake_tests"].append({
                    "file": str(relative_path),
                    "function": func_node.name,
                    "line": func_node.lineno,
                    "reason": "Only contains 'assert True' statements"
                })
    
    def check_skipped_test(self, test_file: Path, func_node: ast.FunctionDef, content: str):
        """Check if test is skipped."""
        relative_path = test_file.relative_to(self.project_root)
        
        # Check for decorators
        for decorator in func_node.decorator_list:
            decorator_str = ast.unparse(decorator)
            if 'skip' in decorator_str.lower() or 'xfail' in decorator_str.lower():
                self.report["skipped_tests"].append({
                    "file": str(relative_path),
                    "function": func_node.name,
                    "line": func_node.lineno,
                    "decorator": decorator_str
                })
    
    def check_empty_assertions(self, test_file: Path, func_node: ast.FunctionDef):
        """Check if test has no assertions."""
        relative_path = test_file.relative_to(self.project_root)
        
        has_assertion = False
        has_pytest_raises = False
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                has_assertion = True
                break
            elif isinstance(node, ast.With):
                # Check for pytest.raises
                if any('raises' in ast.unparse(item.context_expr) for item in node.items):
                    has_pytest_raises = True
                    break
        
        if not has_assertion and not has_pytest_raises:
            self.report["empty_assertions"].append({
                "file": str(relative_path),
                "function": func_node.name,
                "line": func_node.lineno
            })
    
    def check_orphaned_tests(self):
        """Check for tests that test non-existent source files."""
        for test_file in self.tests_dir.rglob("test_*.py"):
            # Extract the module name being tested
            test_name = test_file.stem
            if test_name.startswith("test_"):
                module_name = test_name[5:]  # Remove 'test_' prefix
                
                # Try to find corresponding source file
                possible_sources = [
                    self.src_dir / f"{module_name}.py",
                    self.src_dir / module_name,
                    *list(self.src_dir.rglob(f"{module_name}.py")),
                    *list(self.src_dir.rglob(module_name))
                ]
                
                # Filter out __pycache__ directories
                possible_sources = [p for p in possible_sources if '__pycache__' not in str(p)]
                
                if not any(p.exists() for p in possible_sources):
                    self.report["dead_tests"].append({
                        "test_file": str(test_file.relative_to(self.project_root)),
                        "expected_source": module_name,
                        "reason": "No corresponding source file found"
                    })
    
    def generate_report(self):
        """Generate and save the report."""
        # Calculate statistics
        total_issues = (
            len(self.report["fake_tests"]) +
            len(self.report["import_errors"]) +
            len(self.report["dead_tests"]) +
            len(self.report["empty_assertions"]) +
            len(self.report["skipped_tests"]) +
            len(self.report["todo_tests"]) +
            len(self.report["pass_only_tests"])
        )
        
        self.report["test_stats"] = {
            "total_test_files": len(list(self.tests_dir.rglob("test_*.py"))),
            "total_issues": total_issues,
            "fake_tests": len(self.report["fake_tests"]),
            "import_errors": len(self.report["import_errors"]),
            "dead_tests": len(self.report["dead_tests"]),
            "empty_assertions": len(self.report["empty_assertions"]),
            "skipped_tests": len(self.report["skipped_tests"]),
            "todo_tests": len(self.report["todo_tests"]),
            "pass_only_tests": len(self.report["pass_only_tests"])
        }
        
        # Save report
        report_path = self.project_root / "test_reality_check_report.json"
        with open(report_path, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        # Print summary
        print("\n" + "="*50)
        print("TEST REALITY CHECK REPORT")
        print("="*50)
        print(f"Total test files: {self.report['test_stats']['total_test_files']}")
        print(f"Total issues found: {total_issues}")
        print(f"  - Fake tests (assert True only): {len(self.report['fake_tests'])}")
        print(f"  - Import errors: {len(self.report['import_errors'])}")
        print(f"  - Dead tests (no source): {len(self.report['dead_tests'])}")
        print(f"  - Empty assertions: {len(self.report['empty_assertions'])}")
        print(f"  - Skipped tests: {len(self.report['skipped_tests'])}")
        print(f"  - TODO tests: {len(self.report['todo_tests'])}")
        print(f"  - Pass-only tests: {len(self.report['pass_only_tests'])}")
        print(f"\nDetailed report saved to: {report_path}")
        
        # Print critical issues
        if self.report["import_errors"]:
            print("\n⚠️  CRITICAL: Import errors found!")
            for error in self.report["import_errors"][:5]:
                print(f"  - {error['file']}: {error['module']} ({error['error']})")
            if len(self.report["import_errors"]) > 5:
                print(f"  ... and {len(self.report['import_errors']) - 5} more")
        
        if self.report["fake_tests"]:
            print("\n⚠️  Fake tests detected!")
            for fake in self.report["fake_tests"][:5]:
                print(f"  - {fake['file']}::{fake['function']} (line {fake['line']})")
        
        return total_issues == 0


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    checker = TestRealityChecker(project_root)
    success = checker.scan_all_tests()
    sys.exit(0 if success else 1)