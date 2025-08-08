#!/usr/bin/env python3
"""
Coverage Gap Analysis Script
Identifies untested code and generates test templates for achieving 80%+ coverage.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime
import importlib.util

class CoverageAnalyzer:
    """Comprehensive coverage gap analyzer and test generator."""
    
    CRITICAL_MODULES = {
        "core.entities": 100,  # Target coverage percentage
        "core.value_objects": 100,
        "core.exceptions": 100,
        "application.services.ai": 95,
        "application.services.child_safety": 100,
        "application.services.auth": 95,
        "infrastructure.security": 95,
        "api": 90,
        "adapters": 85
    }
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.tests_dir = project_root / "tests"
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "coverage_gaps": [],
            "missing_tests": [],
            "low_coverage_files": [],
            "test_templates_generated": [],
            "criticality_analysis": {}
        }
    
    def analyze(self):
        """Run comprehensive coverage analysis."""
        print("📊 Starting Coverage Gap Analysis...")
        
        # 1. Analyze source code structure
        self.analyze_source_structure()
        
        # 2. Identify missing test files
        self.identify_missing_tests()
        
        # 3. Analyze function-level coverage
        self.analyze_function_coverage()
        
        # 4. Generate test templates for critical gaps
        self.generate_test_templates()
        
        # 5. Create coverage improvement plan
        self.create_improvement_plan()
        
        # 6. Generate report
        self.generate_report()
    
    def analyze_source_structure(self):
        """Analyze source code to understand what needs testing."""
        print("\n🔍 Analyzing source code structure...")
        
        source_files = list(self.src_dir.rglob("*.py"))
        source_files = [f for f in source_files if "__pycache__" not in str(f)]
        
        for source_file in source_files:
            if source_file.name == "__init__.py":
                continue
            
            module_path = source_file.relative_to(self.src_dir)
            module_name = str(module_path.with_suffix("")).replace("/", ".")
            
            # Analyze the file
            analysis = self.analyze_source_file(source_file, module_name)
            
            if analysis["functions"] or analysis["classes"]:
                self.report["coverage_gaps"].append(analysis)
    
    def analyze_source_file(self, file_path: Path, module_name: str) -> Dict:
        """Analyze a single source file for testable components."""
        analysis = {
            "module": module_name,
            "file": str(file_path.relative_to(self.project_root)),
            "classes": [],
            "functions": [],
            "complexity": 0,
            "criticality": self.get_criticality(module_name)
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "methods": [],
                        "line": node.lineno
                    }
                    
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            if not item.name.startswith("_") or item.name in ["__init__", "__str__", "__repr__"]:
                                class_info["methods"].append({
                                    "name": item.name,
                                    "line": item.lineno,
                                    "has_docstring": ast.get_docstring(item) is not None,
                                    "is_async": isinstance(item, ast.AsyncFunctionDef),
                                    "complexity": self.calculate_complexity(item)
                                })
                    
                    if class_info["methods"]:
                        analysis["classes"].append(class_info)
                
                elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                    # Top-level function
                    if not node.name.startswith("_"):
                        analysis["functions"].append({
                            "name": node.name,
                            "line": node.lineno,
                            "has_docstring": ast.get_docstring(node) is not None,
                            "is_async": isinstance(node, ast.AsyncFunctionDef),
                            "complexity": self.calculate_complexity(node)
                        })
            
            # Calculate overall complexity
            analysis["complexity"] = sum(
                m["complexity"] 
                for c in analysis["classes"] 
                for m in c["methods"]
            ) + sum(f["complexity"] for f in analysis["functions"])
            
        except Exception as e:
            print(f"  ⚠️  Error analyzing {file_path}: {e}")
        
        return analysis
    
    def calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def get_criticality(self, module_name: str) -> str:
        """Determine criticality level of a module."""
        for critical_pattern, target_coverage in self.CRITICAL_MODULES.items():
            if critical_pattern in module_name:
                if target_coverage == 100:
                    return "CRITICAL"
                elif target_coverage >= 95:
                    return "HIGH"
                else:
                    return "MEDIUM"
        return "LOW"
    
    def identify_missing_tests(self):
        """Identify source files without corresponding test files."""
        print("\n🔎 Identifying missing test files...")
        
        for gap in self.report["coverage_gaps"]:
            module_name = gap["module"]
            
            # Expected test file names
            possible_test_names = [
                f"test_{module_name.split('.')[-1]}.py",
                f"{module_name.split('.')[-1]}_test.py"
            ]
            
            # Search for test files
            test_found = False
            for test_name in possible_test_names:
                test_files = list(self.tests_dir.rglob(test_name))
                if test_files:
                    test_found = True
                    break
            
            if not test_found and (gap["classes"] or gap["functions"]):
                self.report["missing_tests"].append({
                    "module": module_name,
                    "source_file": gap["file"],
                    "criticality": gap["criticality"],
                    "testable_items": len(gap["classes"]) + len(gap["functions"])
                })
                print(f"  ⚠️  No tests found for: {module_name}")
    
    def analyze_function_coverage(self):
        """Analyze which specific functions lack test coverage."""
        print("\n📈 Analyzing function-level coverage...")
        
        # Group by criticality
        by_criticality = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
        
        for gap in self.report["coverage_gaps"]:
            criticality = gap["criticality"]
            
            # Check each class and function
            for class_info in gap["classes"]:
                for method in class_info["methods"]:
                    if method["complexity"] > 3:  # Focus on complex methods
                        by_criticality[criticality].append({
                            "module": gap["module"],
                            "class": class_info["name"],
                            "method": method["name"],
                            "complexity": method["complexity"],
                            "is_async": method["is_async"]
                        })
            
            for func in gap["functions"]:
                if func["complexity"] > 3:
                    by_criticality[criticality].append({
                        "module": gap["module"],
                        "function": func["name"],
                        "complexity": func["complexity"],
                        "is_async": func["is_async"]
                    })
        
        self.report["criticality_analysis"] = by_criticality
    
    def generate_test_templates(self):
        """Generate test templates for critical missing tests."""
        print("\n📝 Generating test templates...")
        
        templates_dir = self.tests_dir / "generated_templates"
        templates_dir.mkdir(exist_ok=True)
        
        # Focus on CRITICAL and HIGH priority gaps
        for priority in ["CRITICAL", "HIGH"]:
            items = self.report["criticality_analysis"].get(priority, [])
            
            for item in items[:10]:  # Generate up to 10 templates per priority
                template = self.create_test_template(item)
                
                # Save template
                module_parts = item["module"].split(".")
                test_filename = f"test_{module_parts[-1]}_{item.get('method', item.get('function'))}.py"
                template_path = templates_dir / test_filename
                
                with open(template_path, 'w') as f:
                    f.write(template)
                
                self.report["test_templates_generated"].append({
                    "file": str(template_path.relative_to(self.project_root)),
                    "for": item
                })
                
                print(f"  ✓ Generated template: {test_filename}")
    
    def create_test_template(self, item: Dict) -> str:
        """Create a test template for a specific function/method."""
        module = item["module"]
        is_async = item.get("is_async", False)
        
        if "class" in item:
            # Method test template
            class_name = item["class"]
            method_name = item["method"]
            
            template = f'''"""
Test template for {class_name}.{method_name}
Generated by Coverage Gap Analysis
"""

import pytest
{"import asyncio" if is_async else ""}
from unittest.mock import Mock, patch{", AsyncMock" if is_async else ""}

from src.{module.replace(".", "/")} import {class_name}


@pytest.mark.unit
class Test{class_name}_{method_name.capitalize()}:
    """Comprehensive tests for {class_name}.{method_name}."""
    
    @pytest.fixture
    def instance(self):
        """Create {class_name} instance for testing."""
        # TODO: Initialize with proper test data
        return {class_name}()
    
    {"@pytest.mark.asyncio" if is_async else ""}
    {"async " if is_async else ""}def test_{method_name}_happy_path(self, instance):
        """Test {method_name} with valid inputs."""
        # Arrange
        # TODO: Set up test data
        
        # Act
        result = {"await " if is_async else ""}instance.{method_name}()
        
        # Assert
        # TODO: Add assertions
        assert result is not None
    
    {"@pytest.mark.asyncio" if is_async else ""}
    {"async " if is_async else ""}def test_{method_name}_edge_case_empty_input(self, instance):
        """Test {method_name} with empty/null input."""
        # TODO: Implement edge case test
        pass
    
    {"@pytest.mark.asyncio" if is_async else ""}
    {"async " if is_async else ""}def test_{method_name}_error_handling(self, instance):
        """Test {method_name} error handling."""
        # TODO: Test exception scenarios
        with pytest.raises(Exception):
            {"await " if is_async else ""}instance.{method_name}(invalid_input=True)
    
    @pytest.mark.parametrize("input_data,expected", [
        # TODO: Add test cases
        ({{"example": "data1"}}, "result1"),
        ({{"example": "data2"}}, "result2"),
    ])
    {"@pytest.mark.asyncio" if is_async else ""}
    {"async " if is_async else ""}def test_{method_name}_parametrized(self, instance, input_data, expected):
        """Test {method_name} with various inputs."""
        result = {"await " if is_async else ""}instance.{method_name}(**input_data)
        assert result == expected
'''
        else:
            # Function test template
            func_name = item["function"]
            
            template = f'''"""
Test template for {func_name}
Generated by Coverage Gap Analysis
"""

import pytest
{"import asyncio" if is_async else ""}
from unittest.mock import Mock, patch{", AsyncMock" if is_async else ""}

from src.{module.replace(".", "/")} import {func_name}


@pytest.mark.unit
class Test{func_name.capitalize()}:
    """Comprehensive tests for {func_name} function."""
    
    {"@pytest.mark.asyncio" if is_async else ""}
    {"async " if is_async else ""}def test_{func_name}_happy_path(self):
        """Test {func_name} with valid inputs."""
        # Arrange
        # TODO: Set up test data
        
        # Act
        result = {"await " if is_async else ""}{func_name}()
        
        # Assert
        # TODO: Add assertions
        assert result is not None
    
    {"@pytest.mark.asyncio" if is_async else ""}
    {"async " if is_async else ""}def test_{func_name}_edge_cases(self):
        """Test {func_name} edge cases."""
        # TODO: Implement edge case tests
        pass
    
    {"@pytest.mark.asyncio" if is_async else ""}
    {"async " if is_async else ""}def test_{func_name}_error_handling(self):
        """Test {func_name} error handling."""
        # TODO: Test exception scenarios
        with pytest.raises(Exception):
            {"await " if is_async else ""}{func_name}(invalid_input=True)
    
    @pytest.mark.parametrize("input_data,expected", [
        # TODO: Add test cases
        ("input1", "output1"),
        ("input2", "output2"),
    ])
    {"@pytest.mark.asyncio" if is_async else ""}
    {"async " if is_async else ""}def test_{func_name}_parametrized(self, input_data, expected):
        """Test {func_name} with various inputs."""
        result = {"await " if is_async else ""}{func_name}(input_data)
        assert result == expected
'''
        
        return template
    
    def create_improvement_plan(self):
        """Create a prioritized test improvement plan."""
        plan = {
            "immediate_actions": [],
            "short_term": [],
            "long_term": []
        }
        
        # Immediate: Critical modules with no tests
        for missing in self.report["missing_tests"]:
            if missing["criticality"] in ["CRITICAL", "HIGH"]:
                plan["immediate_actions"].append({
                    "action": "Create test file",
                    "module": missing["module"],
                    "priority": missing["criticality"],
                    "estimated_tests": missing["testable_items"] * 3  # 3 tests per item minimum
                })
        
        # Short term: Complex functions in critical modules
        for item in self.report["criticality_analysis"].get("CRITICAL", [])[:20]:
            plan["short_term"].append({
                "action": "Add comprehensive tests",
                "target": item,
                "tests_needed": ["happy_path", "edge_cases", "error_handling", "concurrency"]
            })
        
        # Long term: Achieve coverage targets
        for module_pattern, target in self.CRITICAL_MODULES.items():
            plan["long_term"].append({
                "module_pattern": module_pattern,
                "target_coverage": target,
                "strategy": "property-based testing" if target == 100 else "standard testing"
            })
        
        self.report["improvement_plan"] = plan
    
    def generate_report(self):
        """Generate comprehensive coverage gap report."""
        report_path = self.project_root / "coverage_gap_analysis.json"
        with open(report_path, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        # Print summary
        print("\n" + "="*60)
        print("COVERAGE GAP ANALYSIS COMPLETE")
        print("="*60)
        print(f"Total modules analyzed: {len(self.report['coverage_gaps'])}")
        print(f"Missing test files: {len(self.report['missing_tests'])}")
        print(f"Test templates generated: {len(self.report['test_templates_generated'])}")
        
        print("\n🎯 Priority Actions:")
        for action in self.report["improvement_plan"]["immediate_actions"][:5]:
            print(f"  - {action['action']} for {action['module']} ({action['priority']})")
        
        print(f"\nDetailed report saved to: {report_path}")
        
        # Create executable test generation script
        self.create_test_generation_script()
    
    def create_test_generation_script(self):
        """Create a script to help generate tests from templates."""
        script_content = '''#!/usr/bin/env python3
"""
Test Generation Helper
Converts templates to actual tests with proper implementation.
"""

import sys
from pathlib import Path

def main():
    templates_dir = Path(__file__).parent.parent / "tests" / "generated_templates"
    
    print("Available test templates:")
    templates = list(templates_dir.glob("*.py"))
    
    for i, template in enumerate(templates, 1):
        print(f"{i}. {template.name}")
    
    choice = input("\\nSelect template to implement (number): ")
    
    try:
        selected = templates[int(choice) - 1]
        print(f"\\nOpening {selected.name} for implementation...")
        print("Remember to:")
        print("  1. Replace TODO comments with actual implementation")
        print("  2. Add proper test data and fixtures")
        print("  3. Include edge cases and error scenarios")
        print("  4. Run mutation testing to verify test quality")
        
        # Copy to proper test directory
        target_dir = Path(__file__).parent.parent / "tests" / "unit"
        target_path = target_dir / selected.name
        
        if target_path.exists():
            print(f"\\n⚠️  {target_path} already exists!")
        else:
            import shutil
            shutil.copy(selected, target_path)
            print(f"\\n✓ Copied to: {target_path}")
            
    except (ValueError, IndexError):
        print("Invalid selection")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        
        script_path = self.project_root / "scripts" / "implement_test_template.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        import os
        os.chmod(script_path, 0o755)
        
        print(f"\n✓ Created test implementation helper: {script_path}")


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    analyzer = CoverageAnalyzer(project_root)
    analyzer.analyze()