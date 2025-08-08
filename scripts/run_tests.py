#!/usr/bin/env python3
"""
Test Runner Script

Runs tests with proper configuration and generates coverage reports.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(cmd: list, cwd: Path = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout, result.stderr


def main():
    """Run test suite with coverage."""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print("🧪 AI Teddy Bear Test Suite")
    print("=" * 60)
    
    # Check if pytest is available
    ret, _, _ = run_command([sys.executable, "-m", "pytest", "--version"])
    if ret != 0:
        print("❌ pytest not found. Please install test dependencies:")
        print("   pip install -r requirements.txt")
        return 1
    
    # Test commands to run
    test_suites = [
        {
            "name": "Unit Tests",
            "cmd": [sys.executable, "-m", "pytest", "tests/unit/", "-v", "--tb=short"],
            "required": True
        },
        {
            "name": "Integration Tests",
            "cmd": [sys.executable, "-m", "pytest", "tests/integration/", "-v", "--tb=short"],
            "required": False  # May not exist yet
        },
        {
            "name": "E2E Tests",
            "cmd": [sys.executable, "-m", "pytest", "tests/e2e/", "-v", "--tb=short"],
            "required": False
        },
        {
            "name": "All Tests with Coverage",
            "cmd": [
                sys.executable, "-m", "pytest",
                "tests/",
                "--cov=src",
                "--cov-report=term-missing",
                "--cov-report=html",
                "-v"
            ],
            "required": True
        }
    ]
    
    results = []
    
    for suite in test_suites:
        print(f"\n📋 Running {suite['name']}...")
        print("-" * 40)
        
        ret, stdout, stderr = run_command(suite["cmd"])
        
        if ret == 0:
            print(f"✅ {suite['name']} passed!")
            results.append((suite['name'], True))
        elif ret == 5:  # No tests collected
            if suite["required"]:
                print(f"⚠️  {suite['name']}: No tests found")
                results.append((suite['name'], False))
            else:
                print(f"ℹ️  {suite['name']}: No tests found (optional)")
                results.append((suite['name'], None))
        else:
            print(f"❌ {suite['name']} failed!")
            print("\nError output:")
            print(stderr if stderr else stdout)
            results.append((suite['name'], False))
            
            if suite["required"]:
                break
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    total = len([r for r in results if r[1] is not None])
    passed = len([r for r in results if r[1] is True])
    
    for name, status in results:
        if status is True:
            print(f"✅ {name}")
        elif status is False:
            print(f"❌ {name}")
        else:
            print(f"⏭️  {name} (skipped)")
    
    if total > 0:
        print(f"\nTotal: {passed}/{total} test suites passed")
        
        # Check coverage if available
        coverage_file = project_root / "htmlcov" / "index.html"
        if coverage_file.exists():
            print(f"\n📈 Coverage report generated: {coverage_file}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())