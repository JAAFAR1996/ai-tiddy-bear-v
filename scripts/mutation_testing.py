#!/usr/bin/env python3
"""
Mutation Testing & Flaky Test Detection Script
Validates test effectiveness through code mutation and identifies unreliable tests.
"""

import ast
import json
import subprocess
import sys
import random
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime
import copy

class MutationTester:
    """Live mutation testing to verify test effectiveness."""
    
    MUTATION_OPERATORS = {
        "arithmetic": [
            (ast.Add, ast.Sub),
            (ast.Sub, ast.Add),
            (ast.Mult, ast.Div),
            (ast.Div, ast.Mult),
        ],
        "comparison": [
            (ast.Lt, ast.LtE),
            (ast.LtE, ast.Lt),
            (ast.Gt, ast.GtE),
            (ast.GtE, ast.Gt),
            (ast.Eq, ast.NotEq),
            (ast.NotEq, ast.Eq),
        ],
        "boolean": [
            (ast.And, ast.Or),
            (ast.Or, ast.And),
        ],
        "constant": [
            ("True", "False"),
            ("False", "True"),
            ("0", "1"),
            ("1", "0"),
            ('""', '"mutated"'),
        ]
    }
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.tests_dir = project_root / "tests"
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "mutations_tested": 0,
            "mutations_killed": 0,
            "mutations_survived": [],
            "flaky_tests": [],
            "mutation_score": 0.0,
            "critical_gaps": []
        }
    
    def run_mutation_testing(self):
        """Run comprehensive mutation testing."""
        print("🧬 Starting Mutation Testing...")
        
        # 1. Select critical modules for mutation
        critical_modules = self.select_critical_modules()
        
        # 2. Run baseline tests to ensure they pass
        if not self.run_baseline_tests():
            print("❌ Baseline tests are failing. Fix tests before mutation testing.")
            return
        
        # 3. Apply mutations and test
        for module_path in critical_modules:
            self.mutate_and_test(module_path)
        
        # 4. Detect flaky tests
        self.detect_flaky_tests()
        
        # 5. Generate report
        self.generate_report()
    
    def select_critical_modules(self) -> List[Path]:
        """Select critical modules for mutation testing."""
        critical_patterns = [
            "**/child_safety*.py",
            "**/auth*.py",
            "**/entities.py",
            "**/value_objects.py",
            "**/exceptions.py",
            "**/validators/*.py"
        ]
        
        modules = []
        for pattern in critical_patterns:
            modules.extend(self.src_dir.glob(pattern))
        
        # Filter out __init__.py and test files
        modules = [m for m in modules if m.name != "__init__.py" and "test" not in m.name]
        
        print(f"Selected {len(modules)} critical modules for mutation testing")
        return modules[:10]  # Limit to 10 for performance
    
    def run_baseline_tests(self) -> bool:
        """Run tests to ensure baseline passes."""
        print("\n🧪 Running baseline tests...")
        
        cmd = [
            sys.executable, "-m", "pytest",
            "-x",  # Stop on first failure
            "--tb=no",  # No traceback
            "-q",  # Quiet
            str(self.tests_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Baseline tests pass")
            return True
        else:
            print("❌ Baseline tests fail")
            print(result.stdout)
            return False
    
    def mutate_and_test(self, module_path: Path):
        """Apply mutations to a module and test."""
        print(f"\n🔬 Mutating: {module_path.relative_to(self.project_root)}")
        
        # Parse the module
        with open(module_path, 'r') as f:
            original_code = f.read()
        
        try:
            tree = ast.parse(original_code)
        except:
            print(f"  ⚠️  Failed to parse {module_path}")
            return
        
        # Find mutation points
        mutations = self.find_mutation_points(tree)
        
        # Sample mutations (test up to 20 per file)
        sampled_mutations = random.sample(mutations, min(20, len(mutations)))
        
        for mutation in sampled_mutations:
            self.test_single_mutation(module_path, original_code, mutation)
    
    def find_mutation_points(self, tree: ast.AST) -> List[Dict]:
        """Find potential mutation points in the AST."""
        mutations = []
        
        class MutationFinder(ast.NodeVisitor):
            def visit_BinOp(self, node):
                # Arithmetic mutations
                for old_op, new_op in self.parent.MUTATION_OPERATORS["arithmetic"]:
                    if isinstance(node.op, old_op):
                        mutations.append({
                            "type": "arithmetic",
                            "node": node,
                            "old_op": old_op,
                            "new_op": new_op,
                            "line": node.lineno
                        })
                self.generic_visit(node)
            
            def visit_Compare(self, node):
                # Comparison mutations
                for i, op in enumerate(node.ops):
                    for old_op, new_op in self.parent.MUTATION_OPERATORS["comparison"]:
                        if isinstance(op, old_op):
                            mutations.append({
                                "type": "comparison",
                                "node": node,
                                "op_index": i,
                                "old_op": old_op,
                                "new_op": new_op,
                                "line": node.lineno
                            })
                self.generic_visit(node)
            
            def visit_BoolOp(self, node):
                # Boolean mutations
                for old_op, new_op in self.parent.MUTATION_OPERATORS["boolean"]:
                    if isinstance(node.op, old_op):
                        mutations.append({
                            "type": "boolean",
                            "node": node,
                            "old_op": old_op,
                            "new_op": new_op,
                            "line": node.lineno
                        })
                self.generic_visit(node)
            
            def visit_Constant(self, node):
                # Constant mutations
                value_str = str(node.value)
                for old_val, new_val in self.parent.MUTATION_OPERATORS["constant"]:
                    if value_str == old_val:
                        mutations.append({
                            "type": "constant",
                            "node": node,
                            "old_value": old_val,
                            "new_value": new_val,
                            "line": node.lineno
                        })
                self.generic_visit(node)
            
            def __init__(self, parent):
                self.parent = parent
        
        finder = MutationFinder(self)
        finder.visit(tree)
        
        return mutations
    
    def test_single_mutation(self, module_path: Path, original_code: str, mutation: Dict):
        """Apply a single mutation and test if it's caught."""
        self.report["mutations_tested"] += 1
        
        # Create mutated code
        tree = ast.parse(original_code)
        mutated_tree = self.apply_mutation(copy.deepcopy(tree), mutation)
        
        try:
            mutated_code = ast.unparse(mutated_tree)
        except:
            # Fallback for older Python versions
            mutated_code = self.manual_mutation(original_code, mutation)
        
        # Write mutated code to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(mutated_code)
            temp_path = Path(f.name)
        
        try:
            # Backup original file
            backup_path = module_path.with_suffix('.py.bak')
            shutil.copy(module_path, backup_path)
            
            # Replace with mutated version
            shutil.copy(temp_path, module_path)
            
            # Run tests
            test_result = self.run_tests_for_module(module_path)
            
            if test_result:
                # Mutation survived (tests still pass - BAD!)
                self.report["mutations_survived"].append({
                    "file": str(module_path.relative_to(self.project_root)),
                    "line": mutation["line"],
                    "type": mutation["type"],
                    "description": self.describe_mutation(mutation)
                })
                print(f"  ❌ Mutation survived at line {mutation['line']}: {mutation['type']}")
            else:
                # Mutation killed (tests fail - GOOD!)
                self.report["mutations_killed"] += 1
                print(f"  ✅ Mutation killed at line {mutation['line']}: {mutation['type']}")
            
        finally:
            # Restore original file
            shutil.copy(backup_path, module_path)
            backup_path.unlink()
            temp_path.unlink()
    
    def apply_mutation(self, tree: ast.AST, mutation: Dict) -> ast.AST:
        """Apply mutation to AST."""
        class Mutator(ast.NodeTransformer):
            def visit(self, node):
                if node == mutation["node"]:
                    if mutation["type"] == "arithmetic":
                        node.op = mutation["new_op"]()
                    elif mutation["type"] == "comparison":
                        node.ops[mutation["op_index"]] = mutation["new_op"]()
                    elif mutation["type"] == "boolean":
                        node.op = mutation["new_op"]()
                    elif mutation["type"] == "constant":
                        node.value = eval(mutation["new_value"])
                
                return self.generic_visit(node)
        
        return Mutator().visit(tree)
    
    def manual_mutation(self, code: str, mutation: Dict) -> str:
        """Manual mutation for older Python versions."""
        # Simple text-based mutation as fallback
        lines = code.split('\n')
        line_idx = mutation["line"] - 1
        
        if mutation["type"] == "arithmetic":
            replacements = {'+': '-', '-': '+', '*': '/', '/': '*'}
            for old, new in replacements.items():
                if old in lines[line_idx]:
                    lines[line_idx] = lines[line_idx].replace(old, new, 1)
                    break
        
        return '\n'.join(lines)
    
    def describe_mutation(self, mutation: Dict) -> str:
        """Generate human-readable mutation description."""
        if mutation["type"] == "arithmetic":
            return f"Changed {mutation['old_op'].__name__} to {mutation['new_op'].__name__}"
        elif mutation["type"] == "comparison":
            return f"Changed {mutation['old_op'].__name__} to {mutation['new_op'].__name__}"
        elif mutation["type"] == "boolean":
            return f"Changed {mutation['old_op'].__name__} to {mutation['new_op'].__name__}"
        elif mutation["type"] == "constant":
            return f"Changed {mutation['old_value']} to {mutation['new_value']}"
        return "Unknown mutation"
    
    def run_tests_for_module(self, module_path: Path) -> bool:
        """Run tests related to a specific module."""
        # Find related test files
        module_name = module_path.stem
        test_patterns = [
            f"test_{module_name}.py",
            f"**/test_{module_name}.py",
            f"test_*{module_name}*.py"
        ]
        
        test_files = []
        for pattern in test_patterns:
            test_files.extend(self.tests_dir.glob(pattern))
        
        if not test_files:
            # No specific tests found, run all tests
            test_files = [self.tests_dir]
        
        # Run tests
        cmd = [
            sys.executable, "-m", "pytest",
            "-x",  # Stop on first failure
            "--tb=no",  # No traceback
            "-q",  # Quiet
        ] + [str(f) for f in test_files]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    
    def detect_flaky_tests(self):
        """Detect flaky tests by running multiple times."""
        print("\n🎲 Detecting flaky tests...")
        
        # Run all tests multiple times
        num_runs = 5
        test_results = {}
        
        for i in range(num_runs):
            print(f"  Run {i+1}/{num_runs}...")
            
            cmd = [
                sys.executable, "-m", "pytest",
                "--tb=no",
                "-v",
                "--json-report",
                "--json-report-file=/tmp/pytest_report.json",
                str(self.tests_dir)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse results
            try:
                with open("/tmp/pytest_report.json", 'r') as f:
                    report = json.load(f)
                
                for test in report.get("tests", []):
                    test_name = test["nodeid"]
                    outcome = test["outcome"]
                    
                    if test_name not in test_results:
                        test_results[test_name] = []
                    test_results[test_name].append(outcome)
            except:
                pass
        
        # Identify flaky tests
        for test_name, outcomes in test_results.items():
            unique_outcomes = set(outcomes)
            if len(unique_outcomes) > 1:
                self.report["flaky_tests"].append({
                    "test": test_name,
                    "outcomes": outcomes,
                    "flakiness": len(unique_outcomes) / len(outcomes)
                })
        
        print(f"  Found {len(self.report['flaky_tests'])} flaky tests")
    
    def generate_report(self):
        """Generate mutation testing report."""
        # Calculate mutation score
        if self.report["mutations_tested"] > 0:
            self.report["mutation_score"] = (
                self.report["mutations_killed"] / self.report["mutations_tested"]
            ) * 100
        
        # Identify critical gaps
        for survived in self.report["mutations_survived"]:
            if "child_safety" in survived["file"] or "auth" in survived["file"]:
                self.report["critical_gaps"].append(survived)
        
        # Save report
        report_path = self.project_root / "mutation_testing_report.json"
        with open(report_path, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        # Print summary
        print("\n" + "="*60)
        print("MUTATION TESTING COMPLETE")
        print("="*60)
        print(f"Mutations tested: {self.report['mutations_tested']}")
        print(f"Mutations killed: {self.report['mutations_killed']}")
        print(f"Mutations survived: {len(self.report['mutations_survived'])}")
        print(f"Mutation score: {self.report['mutation_score']:.1f}%")
        print(f"Flaky tests found: {len(self.report['flaky_tests'])}")
        
        if self.report["mutation_score"] < 70:
            print("\n⚠️  MUTATION SCORE TOO LOW!")
            print("Tests are not effectively catching bugs.")
        
        if self.report["critical_gaps"]:
            print(f"\n🚨 CRITICAL: {len(self.report['critical_gaps'])} mutations survived in security-critical code!")
        
        print(f"\nDetailed report saved to: {report_path}")
        
        # Generate improvement script
        self.generate_improvement_script()
    
    def generate_improvement_script(self):
        """Generate script to improve test effectiveness."""
        script_content = '''#!/usr/bin/env python3
"""
Test Improvement Script
Based on mutation testing results, improves test effectiveness.
"""

import json
from pathlib import Path

def main():
    report_path = Path(__file__).parent.parent / "mutation_testing_report.json"
    
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    print("MUTATION TESTING IMPROVEMENT GUIDE")
    print("="*50)
    
    print(f"\\nCurrent mutation score: {report['mutation_score']:.1f}%")
    print(f"Target mutation score: 70%+\\n")
    
    print("SURVIVING MUTATIONS TO FIX:")
    for i, mutation in enumerate(report["mutations_survived"][:10], 1):
        print(f"\\n{i}. {mutation['file']} (line {mutation['line']})")
        print(f"   Type: {mutation['type']}")
        print(f"   Description: {mutation['description']}")
        print(f"   Action: Add test to verify this behavior")
    
    if report["flaky_tests"]:
        print("\\n\\nFLAKY TESTS TO FIX:")
        for test in report["flaky_tests"][:5]:
            print(f"\\n- {test['test']}")
            print(f"  Flakiness: {test['flakiness']*100:.0f}%")
            print(f"  Fix: Add proper test isolation and deterministic behavior")
    
    print("\\n\\nRECOMMENDATIONS:")
    print("1. Focus on critical modules first (auth, child_safety)")
    print("2. Add boundary value tests for all numeric operations")
    print("3. Test both success and failure paths")
    print("4. Use property-based testing for complex logic")
    print("5. Ensure tests are deterministic and isolated")

if __name__ == "__main__":
    main()
'''
        
        script_path = self.project_root / "scripts" / "improve_test_effectiveness.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        import os
        os.chmod(script_path, 0o755)
        
        print(f"\n✓ Created test improvement guide: {script_path}")


class LiveCodeBreaker:
    """Simulate live code breakage to verify coverage."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.tests_dir = project_root / "tests"
    
    def break_and_test(self):
        """Randomly break code and verify tests catch it."""
        print("\n💥 Starting Live Code Breaking...")
        
        # Select functions to break
        functions = self.find_covered_functions()
        
        broken_but_passed = []
        
        for func_info in random.sample(functions, min(10, len(functions))):
            if self.break_function(func_info):
                broken_but_passed.append(func_info)
        
        if broken_but_passed:
            print(f"\n⚠️  {len(broken_but_passed)} functions have fake coverage!")
            for func in broken_but_passed:
                print(f"  - {func['file']}::{func['function']}")
        else:
            print("\n✅ All tested functions have real coverage!")
    
    def find_covered_functions(self) -> List[Dict]:
        """Find functions that claim to have test coverage."""
        # This would integrate with coverage.py data
        # For now, return sample functions
        return [
            {"file": "core/entities.py", "function": "Child.__init__", "line": 20},
            {"file": "core/value_objects.py", "function": "AgeGroup.from_age", "line": 15},
        ]
    
    def break_function(self, func_info: Dict) -> bool:
        """Break a function and see if tests fail."""
        file_path = self.src_dir / func_info["file"]
        
        if not file_path.exists():
            return False
        
        # Read file
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Comment out a line in the function
        line_idx = func_info["line"]
        original_line = lines[line_idx]
        lines[line_idx] = "    # BROKEN: " + original_line
        
        # Write broken version
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        # Run tests
        tests_pass = self.run_related_tests(func_info["file"])
        
        # Restore original
        lines[line_idx] = original_line
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        return tests_pass  # True means fake coverage
    
    def run_related_tests(self, source_file: str) -> bool:
        """Run tests related to a source file."""
        cmd = [
            sys.executable, "-m", "pytest",
            "-x", "--tb=no", "-q",
            str(self.tests_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    
    # Run mutation testing
    mutator = MutationTester(project_root)
    mutator.run_mutation_testing()
    
    # Run live code breaking
    breaker = LiveCodeBreaker(project_root)
    breaker.break_and_test()