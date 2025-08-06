#!/usr/bin/env python3
"""
Test Coverage Report Generator

Generates comprehensive test coverage reports and identifies gaps.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
import ast


class CoverageAnalyzer:
    """Analyzes test coverage and identifies gaps."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.src_dir = self.project_root / "src"
        self.test_dir = self.project_root / "tests"
        self.source_files = []
        self.test_files = []
        self.coverage_data = {}
        
    def find_all_source_files(self) -> List[Path]:
        """Find all Python source files."""
        source_files = []
        for py_file in self.src_dir.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                source_files.append(py_file)
        return source_files
    
    def find_all_test_files(self) -> List[Path]:
        """Find all test files."""
        test_files = []
        
        # Check both test directories
        for test_dir in ["tests", "tests_consolidated"]:
            test_path = self.project_root / test_dir
            if test_path.exists():
                test_files.extend(test_path.rglob("test_*.py"))
                test_files.extend(test_path.rglob("*_test.py"))
        
        return test_files
    
    def map_source_to_tests(self) -> Dict[str, List[str]]:
        """Map source files to their test files."""
        mapping = {}
        
        for src_file in self.source_files:
            src_path = str(src_file.relative_to(self.project_root))
            mapping[src_path] = []
            
            # Look for corresponding test files
            src_name = src_file.stem
            for test_file in self.test_files:
                test_name = test_file.stem
                
                # Check if test file matches source file
                if src_name in test_name or test_name.endswith(f"_{src_name}"):
                    test_path = str(test_file.relative_to(self.project_root))
                    mapping[src_path].append(test_path)
        
        return mapping
    
    def analyze_test_coverage(self) -> Dict[str, any]:
        """Run coverage analysis and get results."""
        print("🔍 Running test coverage analysis...")
        
        # Run pytest with coverage
        cmd = [
            sys.executable, "-m", "pytest",
            "--cov=src",
            "--cov-report=json",
            "--cov-report=term-missing",
            "-q"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            # Load coverage data
            coverage_file = self.project_root / "coverage.json"
            if coverage_file.exists():
                with open(coverage_file, 'r') as f:
                    return json.load(f)
            else:
                print("⚠️  No coverage data generated")
                return {}
                
        except Exception as e:
            print(f"❌ Error running coverage: {e}")
            return {}
    
    def identify_untested_code(self, coverage_data: Dict) -> List[Dict]:
        """Identify specific untested code sections."""
        untested = []
        
        if "files" not in coverage_data:
            return untested
        
        for file_path, file_data in coverage_data["files"].items():
            if file_data["summary"]["percent_covered"] < 100:
                missing_lines = file_data.get("missing_lines", [])
                missing_branches = file_data.get("missing_branches", [])
                
                untested.append({
                    "file": file_path,
                    "coverage": file_data["summary"]["percent_covered"],
                    "missing_lines": missing_lines,
                    "missing_branches": missing_branches,
                    "priority": self._calculate_priority(file_path)
                })
        
        # Sort by priority and coverage
        untested.sort(key=lambda x: (x["priority"], x["coverage"]))
        
        return untested
    
    def _calculate_priority(self, file_path: str) -> int:
        """Calculate priority for testing based on file importance."""
        # High priority files
        if any(critical in file_path for critical in [
            "child_safety", "auth", "security", "coppa", "safety"
        ]):
            return 1
        
        # Medium priority - core business logic
        if any(core in file_path for core in [
            "services", "entities", "core", "ai_service", "conversation"
        ]):
            return 2
        
        # Lower priority - utilities and helpers
        return 3
    
    def generate_missing_tests(self, untested: List[Dict]) -> List[Dict]:
        """Generate test suggestions for untested code."""
        suggestions = []
        
        for item in untested[:10]:  # Top 10 untested files
            file_path = Path(item["file"])
            
            # Analyze what's missing
            suggestions.append({
                "file": item["file"],
                "current_coverage": item["coverage"],
                "test_file": self._suggest_test_file(file_path),
                "missing_tests": self._analyze_missing_tests(file_path, item["missing_lines"])
            })
        
        return suggestions
    
    def _suggest_test_file(self, source_file: Path) -> str:
        """Suggest test file name for source file."""
        relative_path = source_file.relative_to(self.src_dir)
        test_path = self.test_dir / "unit" / f"test_{relative_path}"
        return str(test_path)
    
    def _analyze_missing_tests(self, file_path: Path, missing_lines: List[int]) -> List[str]:
        """Analyze what tests are missing."""
        suggestions = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Find untested functions/methods
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if hasattr(node, 'lineno') and node.lineno in missing_lines:
                        suggestions.append(f"Test for {node.name}()")
                elif isinstance(node, ast.ClassDef):
                    if hasattr(node, 'lineno') and node.lineno in missing_lines:
                        suggestions.append(f"Test for {node.name} class")
            
        except Exception:
            suggestions.append("Add comprehensive tests for this module")
        
        return suggestions
    
    def generate_report(self) -> Dict[str, any]:
        """Generate comprehensive coverage report."""
        self.source_files = self.find_all_source_files()
        self.test_files = self.find_all_test_files()
        
        # Get file mapping
        file_mapping = self.map_source_to_tests()
        
        # Run coverage
        coverage_data = self.analyze_test_coverage()
        
        # Analyze gaps
        untested = self.identify_untested_code(coverage_data)
        test_suggestions = self.generate_missing_tests(untested)
        
        # Calculate metrics
        total_files = len(self.source_files)
        tested_files = len([f for f, tests in file_mapping.items() if tests])
        
        report = {
            "summary": {
                "total_source_files": total_files,
                "total_test_files": len(self.test_files),
                "files_with_tests": tested_files,
                "files_without_tests": total_files - tested_files,
                "overall_coverage": coverage_data.get("totals", {}).get("percent_covered", 0)
            },
            "untested_files": [f for f, tests in file_mapping.items() if not tests],
            "low_coverage_files": untested[:20],
            "test_suggestions": test_suggestions,
            "critical_gaps": self._identify_critical_gaps(untested)
        }
        
        return report
    
    def _identify_critical_gaps(self, untested: List[Dict]) -> List[Dict]:
        """Identify critical testing gaps."""
        critical = []
        
        for item in untested:
            if item["priority"] == 1 and item["coverage"] < 80:
                critical.append({
                    "file": item["file"],
                    "coverage": item["coverage"],
                    "risk": "HIGH - Safety critical component with low coverage",
                    "action": "Immediate test coverage required"
                })
        
        return critical
    
    def print_report(self, report: Dict) -> None:
        """Print formatted coverage report."""
        print("\n" + "=" * 80)
        print("📊 TEST COVERAGE REPORT")
        print("=" * 80)
        
        summary = report["summary"]
        print(f"\n📈 Overall Coverage: {summary['overall_coverage']:.1f}%")
        print(f"📁 Source Files: {summary['total_source_files']}")
        print(f"🧪 Test Files: {summary['total_test_files']}")
        print(f"✅ Files with Tests: {summary['files_with_tests']}")
        print(f"❌ Files without Tests: {summary['files_without_tests']}")
        
        if report["critical_gaps"]:
            print("\n🚨 CRITICAL GAPS (Safety-Critical Components)")
            print("-" * 60)
            for gap in report["critical_gaps"]:
                print(f"\n❗ {gap['file']}")
                print(f"   Coverage: {gap['coverage']:.1f}%")
                print(f"   Risk: {gap['risk']}")
                print(f"   Action: {gap['action']}")
        
        if report["untested_files"]:
            print("\n📝 Files Without Any Tests")
            print("-" * 60)
            for file in report["untested_files"][:10]:
                print(f"  - {file}")
            if len(report["untested_files"]) > 10:
                print(f"  ... and {len(report['untested_files']) - 10} more")
        
        print("\n💡 Test Creation Suggestions")
        print("-" * 60)
        for suggestion in report["test_suggestions"][:5]:
            print(f"\n📄 {suggestion['file']} ({suggestion['current_coverage']:.1f}% coverage)")
            print(f"   Create: {suggestion['test_file']}")
            for test in suggestion["missing_tests"][:3]:
                print(f"   - {test}")
        
        # Save detailed report
        report_path = self.project_root / "test_coverage_detailed.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n💾 Detailed report saved to: {report_path}")


def main():
    """Main function."""
    project_root = Path(__file__).parent.parent
    
    analyzer = CoverageAnalyzer(project_root)
    report = analyzer.generate_report()
    analyzer.print_report(report)
    
    # Return exit code based on coverage
    coverage = report["summary"]["overall_coverage"]
    if coverage >= 80:
        print(f"\n✅ Coverage target met: {coverage:.1f}% >= 80%")
        return 0
    else:
        print(f"\n❌ Coverage below target: {coverage:.1f}% < 80%")
        return 1


if __name__ == "__main__":
    sys.exit(main())