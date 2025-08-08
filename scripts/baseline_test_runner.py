#!/usr/bin/env python3
"""
Baseline Test Runner
Runs a basic pytest execution to identify failing tests.
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

def run_baseline_tests():
    """Run baseline tests and capture results."""
    project_root = Path(__file__).parent.parent
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_results": {},
        "summary": {}
    }
    
    print("🧪 Running Baseline Tests...")
    print("=" * 50)
    
    # Try to run pytest with minimal configuration
    cmd = [
        sys.executable, "-m", "pytest",
        "--tb=short",
        "--no-header",
        "-v",
        "-x",  # Stop on first failure
        str(project_root / "tests")
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        results["exit_code"] = result.returncode
        results["stdout"] = result.stdout
        results["stderr"] = result.stderr
        
        # Parse results
        if result.returncode == 0:
            print("✅ All tests passed!")
        else:
            print("❌ Tests failed!")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
        
        # Save results
        results_file = project_root / "baseline_test_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: {results_file}")
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        results["error"] = str(e)
        
    return results

if __name__ == "__main__":
    run_baseline_tests()