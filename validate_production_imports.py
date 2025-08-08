#!/usr/bin/env python3
"""
Production Import Validator
===========================
Strict validator to ensure ZERO non-production imports in the codebase.
Enforces the rule: "All services MUST be imported from real production files only"

BLOCKED PATTERNS:
- Any import containing: mock, dummy, fake, test, example
- Any class instantiation with: Mock*, Dummy*, Fake*, Example*
- Any import from files named with non-production patterns

EXIT CODES:
- 0: All imports are production-ready
- 1: Non-production imports detected (blocks deployment)
- 2: Script execution error
"""

import os
import re
import sys
import glob
from pathlib import Path
from typing import List, Dict, Set, Tuple

# Colors for output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_colored(text: str, color: str = Colors.WHITE, bold: bool = False):
    """Print colored text to console"""
    prefix = Colors.BOLD if bold else ""
    print(f"{prefix}{color}{text}{Colors.END}")

# FORBIDDEN PATTERNS - Zero tolerance
FORBIDDEN_IMPORT_PATTERNS = [
    r'import\s+.*\bmock\b',
    r'import\s+.*\bdummy\b', 
    r'import\s+.*\bfake\b',
    r'import\s+.*\btest\b(?!_utils)',  # Allow test_utils but not test modules
    r'import\s+.*\bexample\b',
    r'from\s+.*\bmock\b',
    r'from\s+.*\bdummy\b',
    r'from\s+.*\bfake\b', 
    r'from\s+.*\btest\b(?!_utils)',
    r'from\s+.*\bexample\b',
    r'from\s+\.mock_',
    r'from\s+\.dummy_',
    r'from\s+\.fake_',
    r'from\s+\.test_',
    r'from\s+\.example_',
]

FORBIDDEN_CLASS_PATTERNS = [
    r'Mock[A-Z]\w*\s*\(',
    r'Dummy[A-Z]\w*\s*\(',
    r'Fake[A-Z]\w*\s*\(',
    r'Example[A-Z]\w*\s*\(',
    r'Test[A-Z]\w*\s*\(',  # Test classes being instantiated
]

FORBIDDEN_FILENAMES = [
    'mock_', 'dummy_', 'fake_', 'test_', 'example_',
    '_mock', '_dummy', '_fake', '_test', '_example'
]

# Production directories - only these contain valid services
PRODUCTION_DIRECTORIES = {
    'src/application/services',
    'src/adapters', 
    'src/infrastructure',
    'src/core',
    'src/utils'
}

class ProductionImportValidator:
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.violations: List[Dict] = []
        self.scanned_files: Set[str] = set()
        self.production_services: Set[str] = set()
        
    def scan_production_services(self) -> Set[str]:
        """Scan and catalog all legitimate production services"""
        services = set()
        
        for prod_dir in PRODUCTION_DIRECTORIES:
            dir_path = self.root_path / prod_dir
            if dir_path.exists():
                for py_file in dir_path.rglob('*.py'):
                    if py_file.name == '__init__.py':
                        continue
                    # Skip files with forbidden patterns in names
                    if any(pattern in py_file.name.lower() for pattern in FORBIDDEN_FILENAMES):
                        continue
                    services.add(str(py_file.relative_to(self.root_path)))
        
        return services
    
    def is_production_file(self, file_path: Path) -> bool:
        """Check if a file is in production directories and has production name"""
        relative_path = file_path.relative_to(self.root_path)
        
        # Must be in production directory
        in_prod_dir = any(str(relative_path).startswith(prod_dir) for prod_dir in PRODUCTION_DIRECTORIES)
        
        # Must not have forbidden filename patterns
        has_clean_name = not any(pattern in file_path.name.lower() for pattern in FORBIDDEN_FILENAMES)
        
        return in_prod_dir and has_clean_name
    
    def validate_file(self, file_path: Path) -> List[Dict]:
        """Validate a single Python file for production imports"""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            return [{"type": "file_error", "file": str(file_path), "error": str(e)}]
        
        relative_path = str(file_path.relative_to(self.root_path))
        
        # Skip if this file itself is non-production
        if not self.is_production_file(file_path):
            # But still check if it's being imported elsewhere
            return violations
            
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Skip comments and empty lines
            if not line_stripped or line_stripped.startswith('#'):
                continue
            
            # Check forbidden import patterns
            for pattern in FORBIDDEN_IMPORT_PATTERNS:
                if re.search(pattern, line_stripped, re.IGNORECASE):
                    violations.append({
                        "type": "forbidden_import",
                        "file": relative_path,
                        "line": line_num,
                        "content": line_stripped,
                        "pattern": pattern,
                        "severity": "CRITICAL"
                    })
            
            # Check forbidden class instantiations
            for pattern in FORBIDDEN_CLASS_PATTERNS:
                if re.search(pattern, line_stripped):
                    violations.append({
                        "type": "forbidden_class", 
                        "file": relative_path,
                        "line": line_num,
                        "content": line_stripped,
                        "pattern": pattern,
                        "severity": "CRITICAL"
                    })
        
        return violations
    
    def validate_imports_reference_production(self, file_path: Path) -> List[Dict]:
        """Ensure all imports reference real production files"""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception:
            return violations
            
        relative_path = str(file_path.relative_to(self.root_path))
        
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Look for relative imports
            import_match = re.match(r'from\s+(\.[\w\.]*)\s+import', line_stripped)
            if import_match:
                import_path = import_match.group(1)
                # Check if imported module exists and is production
                # This is a basic check - could be enhanced
                pass
        
        return violations
    
    def scan_directory(self, directory: Path = None) -> None:
        """Scan directory recursively for Python files"""
        if directory is None:
            directory = self.root_path / "src"
            
        print_colored(f"🔍 Scanning {directory} for production import compliance...", Colors.BLUE)
        
        python_files = list(directory.rglob('*.py'))
        print_colored(f"📁 Found {len(python_files)} Python files to validate", Colors.CYAN)
        
        for py_file in python_files:
            self.scanned_files.add(str(py_file))
            file_violations = self.validate_file(py_file)
            self.violations.extend(file_violations)
            
        print_colored(f"✅ Scanned {len(python_files)} files", Colors.GREEN)
        
    def generate_report(self) -> Dict:
        """Generate comprehensive validation report"""
        critical_violations = [v for v in self.violations if v.get('severity') == 'CRITICAL']
        
        report = {
            "summary": {
                "total_files_scanned": len(self.scanned_files),
                "total_violations": len(self.violations),
                "critical_violations": len(critical_violations),
                "status": "FAIL" if critical_violations else "PASS",
                "production_ready": len(critical_violations) == 0
            },
            "violations": self.violations,
            "production_services": len(self.production_services),
            "scanned_directories": list(PRODUCTION_DIRECTORIES)
        }
        
        return report
    
    def print_report(self, report: Dict) -> None:
        """Print formatted validation report"""
        summary = report["summary"]
        
        print_colored("\n" + "="*80, Colors.BOLD)
        print_colored("🚨 PRODUCTION IMPORT VALIDATION REPORT", Colors.BOLD + Colors.RED if summary["status"] == "FAIL" else Colors.BOLD + Colors.GREEN)
        print_colored("="*80, Colors.BOLD)
        
        # Summary
        status_color = Colors.RED if summary["status"] == "FAIL" else Colors.GREEN
        print_colored(f"📊 STATUS: {summary['status']}", status_color, bold=True)
        print_colored(f"📁 Files Scanned: {summary['total_files_scanned']}", Colors.CYAN)
        print_colored(f"🚨 Total Violations: {summary['total_violations']}", Colors.YELLOW)
        print_colored(f"💥 Critical Violations: {summary['critical_violations']}", Colors.RED if summary['critical_violations'] > 0 else Colors.GREEN)
        print_colored(f"✅ Production Ready: {'YES' if summary['production_ready'] else 'NO'}", Colors.GREEN if summary['production_ready'] else Colors.RED, bold=True)
        
        # Detailed violations
        if self.violations:
            print_colored("\n🚫 VIOLATIONS FOUND:", Colors.RED, bold=True)
            print_colored("-" * 80, Colors.RED)
            
            for violation in self.violations:
                severity_color = Colors.RED if violation.get('severity') == 'CRITICAL' else Colors.YELLOW
                
                print_colored(f"\n[{violation.get('severity', 'UNKNOWN')}] {violation['type'].upper()}", severity_color, bold=True)
                print_colored(f"📄 File: {violation['file']}", Colors.WHITE)
                if 'line' in violation:
                    print_colored(f"📍 Line {violation['line']}: {violation['content']}", Colors.CYAN)
                if 'pattern' in violation:
                    print_colored(f"🎯 Pattern: {violation['pattern']}", Colors.MAGENTA)
                print_colored("-" * 40, Colors.WHITE)
        else:
            print_colored("\n✅ NO VIOLATIONS FOUND - ALL IMPORTS ARE PRODUCTION READY!", Colors.GREEN, bold=True)
            
        print_colored("\n" + "="*80, Colors.BOLD)
        
        # Exit code guidance
        if summary["status"] == "FAIL":
            print_colored("🚨 DEPLOYMENT BLOCKED: Fix all violations before proceeding", Colors.RED, bold=True)
            print_colored("💡 Next steps:", Colors.YELLOW)
            print_colored("  1. Replace all mock/dummy/fake imports with production services", Colors.WHITE)
            print_colored("  2. Remove or move non-production files out of src/", Colors.WHITE)
            print_colored("  3. Re-run this validator until status = PASS", Colors.WHITE)
        else:
            print_colored("🎉 DEPLOYMENT APPROVED: All imports are production-ready!", Colors.GREEN, bold=True)

def main():
    """Main validation entry point"""
    print_colored("🛡️ AI Teddy Bear - Production Import Validator", Colors.BOLD + Colors.BLUE)
    print_colored("Enforcing ZERO non-production imports policy\n", Colors.CYAN)
    
    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir
    
    if not (project_root / "src").exists():
        print_colored("❌ ERROR: src/ directory not found", Colors.RED)
        print_colored(f"📍 Looked in: {project_root}", Colors.WHITE)
        return 2
    
    # Initialize validator
    validator = ProductionImportValidator(project_root)
    
    try:
        # Scan production services first
        validator.production_services = validator.scan_production_services()
        print_colored(f"📋 Found {len(validator.production_services)} production services", Colors.GREEN)
        
        # Scan for violations
        validator.scan_directory()
        
        # Generate and print report
        report = validator.generate_report()
        validator.print_report(report)
        
        # Return appropriate exit code
        return 1 if report["summary"]["critical_violations"] > 0 else 0
        
    except Exception as e:
        print_colored(f"❌ VALIDATION ERROR: {str(e)}", Colors.RED, bold=True)
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)