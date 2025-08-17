#!/usr/bin/env python3
"""
Check if test files exist for source files.
Used as a pre-commit hook.
"""

import sys
from pathlib import Path

def check_test_exists(source_files):
    """Check if test files exist for given source files."""
    missing_tests = []
    
    for source_file in source_files:
        source_path = Path(source_file)
        
        # Skip __init__.py files
        if source_path.name == "__init__.py":
            continue
        
        # Determine expected test file name
        module_name = source_path.stem
        expected_test_names = [
            f"test_{module_name}.py",
            f"{module_name}_test.py"
        ]
        
        # Look for test file
        tests_dir = Path("tests")
        test_found = False
        
        for test_name in expected_test_names:
            # Check in various test subdirectories
            possible_paths = [
                tests_dir / test_name,
                tests_dir / "unit" / test_name,
                tests_dir / "integration" / test_name,
                tests_dir / "e2e" / test_name,
            ]
            
            if any(p.exists() for p in possible_paths):
                test_found = True
                break
        
        if not test_found:
            missing_tests.append(source_file)
    
    if missing_tests:
        print("❌ Missing test files for:")
        for file in missing_tests:
            print(f"  - {file}")
        print("\nPlease create test files before committing.")
        return 1
    
    return 0

if __name__ == "__main__":
    # Get files from command line arguments
    files = sys.argv[1:] if len(sys.argv) > 1 else []
    sys.exit(check_test_exists(files))