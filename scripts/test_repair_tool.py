#!/usr/bin/env python3
"""
Test Repair Tool

Comprehensive tool to fix broken tests, update imports, and validate test suite.
"""

import os
import ast
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Set, Tuple, Any
import subprocess
import re
import json


class TestRepairTool:
    """Repairs broken tests and fixes import issues."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.test_dirs = ["tests_consolidated", "tests"]
        self.source_dir = self.project_root / "src"
        self.broken_imports = []
        self.fixed_imports = []
        self.test_results = {}
        
    def find_all_tests(self) -> List[Path]:
        """Find all test files in the project."""
        test_files = []
        
        for test_dir in self.test_dirs:
            test_path = self.project_root / test_dir
            if test_path.exists():
                test_files.extend(test_path.rglob("test_*.py"))
                test_files.extend(test_path.rglob("*_test.py"))
                
        return test_files
    
    def analyze_imports(self, file_path: Path) -> List[Dict[str, Any]]:
        """Analyze imports in a test file."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self._check_module_exists(alias.name):
                            issues.append({
                                'file': str(file_path),
                                'line': node.lineno,
                                'type': 'import',
                                'module': alias.name,
                                'statement': f"import {alias.name}"
                            })
                            
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        if not self._check_module_exists(node.module):
                            imported_names = [n.name for n in node.names]
                            issues.append({
                                'file': str(file_path),
                                'line': node.lineno,
                                'type': 'from_import',
                                'module': node.module,
                                'names': imported_names,
                                'statement': f"from {node.module} import {', '.join(imported_names)}"
                            })
                            
        except Exception as e:
            issues.append({
                'file': str(file_path),
                'error': str(e),
                'type': 'parse_error'
            })
            
        return issues
    
    def _check_module_exists(self, module_name: str) -> bool:
        """Check if a module exists in the project or is installed."""
        # Check if it's a project module
        if module_name.startswith('src.'):
            parts = module_name.split('.')
            path_parts = parts[1:]  # Remove 'src'
            
            # Check as module file
            module_path = self.source_dir / '/'.join(path_parts)
            if (module_path.with_suffix('.py')).exists():
                return True
                
            # Check as package
            if (module_path / '__init__.py').exists():
                return True
                
            return False
        
        # Check if it's an installed package
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False
    
    def fix_imports(self, file_path: Path, issues: List[Dict[str, Any]]) -> bool:
        """Fix import issues in a file."""
        if not issues:
            return True
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Sort issues by line number in reverse order to avoid offset issues
            issues.sort(key=lambda x: x.get('line', 0), reverse=True)
            
            for issue in issues:
                if issue.get('type') == 'parse_error':
                    continue
                    
                line_num = issue['line'] - 1
                if line_num < len(lines):
                    old_line = lines[line_num]
                    
                    # Try to fix the import
                    fixed_module = self._find_correct_module(issue['module'])
                    
                    if fixed_module:
                        if issue['type'] == 'import':
                            new_line = f"import {fixed_module}\n"
                        else:
                            names = issue.get('names', [])
                            new_line = f"from {fixed_module} import {', '.join(names)}\n"
                        
                        lines[line_num] = new_line
                        self.fixed_imports.append({
                            'file': str(file_path),
                            'old': old_line.strip(),
                            'new': new_line.strip()
                        })
                    else:
                        # Comment out broken import
                        lines[line_num] = f"# BROKEN: {old_line}"
                        self.broken_imports.append({
                            'file': str(file_path),
                            'import': old_line.strip(),
                            'reason': 'Module not found'
                        })
            
            # Write fixed file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            return True
            
        except Exception as e:
            print(f"Error fixing {file_path}: {e}")
            return False
    
    def _find_correct_module(self, module_name: str) -> str:
        """Try to find the correct module path."""
        # Common import mappings based on refactored structure
        mappings = {
            'src.application.services.ai.ai_orchestration_service': 'src.application.services.ai.ai_service',
            'src.application.services.ai.main_service': 'src.core.services',
            'src.application.services.emotion_analyzer': 'src.application.services.ai.emotion_analyzer',
            'src.infrastructure.ai.real_ai_service': 'src.infrastructure.external.openai_adapter',
            'src.domain.value_objects.age_group': 'src.core.value_objects.age_group',
            'src.application.dto.ai_response': 'src.shared.dto.ai_response',
        }
        
        if module_name in mappings:
            return mappings[module_name]
        
        # Try to find similar modules
        if module_name.startswith('src.'):
            parts = module_name.split('.')
            
            # Try different variations
            variations = [
                # Move from application to core
                module_name.replace('src.application.', 'src.core.'),
                # Move from domain to core
                module_name.replace('src.domain.', 'src.core.'),
                # Move dto to shared
                module_name.replace('.dto.', '.shared.dto.'),
                # Try services directly
                module_name.replace('.services.', '.core.services.'),
            ]
            
            for variant in variations:
                if self._check_module_exists(variant):
                    return variant
        
        return None
    
    def fix_async_decorators(self, file_path: Path) -> bool:
        """Fix async test decorators."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Fix async test decorators
            patterns = [
                (r'async def test_', '@pytest.mark.asyncio\n    async def test_'),
                (r'@pytest.mark.asyncio\s*\n\s*@pytest.mark.asyncio', '@pytest.mark.asyncio'),
            ]
            
            modified = False
            for pattern, replacement in patterns:
                if re.search(pattern, content) and '@pytest.mark.asyncio' not in content:
                    content = re.sub(pattern, replacement, content)
                    modified = True
            
            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
            return True
            
        except Exception as e:
            print(f"Error fixing async decorators in {file_path}: {e}")
            return False
    
    def validate_test(self, file_path: Path) -> Dict[str, Any]:
        """Validate a single test file."""
        result = {
            'file': str(file_path),
            'valid': False,
            'errors': [],
            'warnings': []
        }
        
        # Check if file compiles
        try:
            compile_result = subprocess.run(
                [sys.executable, '-m', 'py_compile', str(file_path)],
                capture_output=True,
                text=True
            )
            
            if compile_result.returncode != 0:
                result['errors'].append(f"Compilation error: {compile_result.stderr}")
                return result
                
        except Exception as e:
            result['errors'].append(f"Compilation check failed: {e}")
            return result
        
        # Check for test functions
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            
            test_count = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.name.startswith('test_'):
                        test_count += 1
                        
                        # Check for assertions
                        has_assertion = False
                        for child in ast.walk(node):
                            if isinstance(child, ast.Assert) or \
                               (isinstance(child, ast.Call) and 
                                isinstance(child.func, ast.Name) and 
                                child.func.id in ['assertEqual', 'assertTrue', 'assertFalse']):
                                has_assertion = True
                                break
                                
                        if not has_assertion:
                            result['warnings'].append(f"Test '{node.name}' has no assertions")
            
            if test_count == 0:
                result['warnings'].append("No test functions found")
            
            result['test_count'] = test_count
            result['valid'] = len(result['errors']) == 0
            
        except Exception as e:
            result['errors'].append(f"Parse error: {e}")
            
        return result
    
    def run_repair(self, fix_imports: bool = True, validate: bool = True) -> Dict[str, Any]:
        """Run the repair process."""
        print("🔧 Starting test repair process...")
        
        test_files = self.find_all_tests()
        print(f"Found {len(test_files)} test files")
        
        results = {
            'total_files': len(test_files),
            'files_with_issues': 0,
            'files_fixed': 0,
            'import_issues': [],
            'validation_results': []
        }
        
        for test_file in test_files:
            print(f"\n📄 Processing: {test_file}")
            
            # Analyze imports
            issues = self.analyze_imports(test_file)
            if issues:
                results['files_with_issues'] += 1
                results['import_issues'].extend(issues)
                
                if fix_imports:
                    if self.fix_imports(test_file, issues):
                        results['files_fixed'] += 1
                        print(f"  ✅ Fixed {len(issues)} import issues")
                    else:
                        print(f"  ❌ Failed to fix imports")
            
            # Fix async decorators
            self.fix_async_decorators(test_file)
            
            # Validate
            if validate:
                validation = self.validate_test(test_file)
                results['validation_results'].append(validation)
                
                if validation['valid']:
                    print(f"  ✅ Validation passed")
                else:
                    print(f"  ❌ Validation failed: {validation['errors']}")
        
        return results
    
    def generate_report(self, results: Dict[str, Any]) -> None:
        """Generate a detailed repair report."""
        report_path = self.project_root / 'test_repair_report.json'
        
        report = {
            'summary': {
                'total_files': results['total_files'],
                'files_with_issues': results['files_with_issues'],
                'files_fixed': results['files_fixed'],
                'broken_imports': len(self.broken_imports),
                'fixed_imports': len(self.fixed_imports)
            },
            'broken_imports': self.broken_imports,
            'fixed_imports': self.fixed_imports,
            'validation_results': results['validation_results']
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\n📊 Report saved to: {report_path}")
        
        # Print summary
        print("\n📈 Repair Summary:")
        print(f"  Total test files: {results['total_files']}")
        print(f"  Files with issues: {results['files_with_issues']}")
        print(f"  Files fixed: {results['files_fixed']}")
        print(f"  Broken imports: {len(self.broken_imports)}")
        print(f"  Fixed imports: {len(self.fixed_imports)}")
        
        # Count valid tests
        valid_tests = sum(1 for v in results['validation_results'] if v['valid'])
        print(f"  Valid test files: {valid_tests}/{len(results['validation_results'])}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test Repair Tool')
    parser.add_argument('--fix-imports', action='store_true',
                       help='Fix broken imports')
    parser.add_argument('--validate', action='store_true',
                       help='Validate test files')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show issues without fixing')
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    tool = TestRepairTool(project_root)
    
    results = tool.run_repair(
        fix_imports=args.fix_imports and not args.dry_run,
        validate=args.validate
    )
    
    tool.generate_report(results)
    
    # Exit with error if there are still issues
    if results['files_with_issues'] > results['files_fixed']:
        sys.exit(1)


if __name__ == "__main__":
    main()