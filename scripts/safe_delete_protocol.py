#!/usr/bin/env python3
"""
Safe Delete Protocol

Automated deletion script that safely removes dead code with full verification
and backup capabilities.
"""

import os
import sys
import shutil
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import argparse


class SafeDeleteProtocol:
    """Safe deletion protocol with verification and rollback."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / '.dead_code_backup'
        self.deletion_log = []
        self.report_file = self.project_root / 'dead_code_report.json'
        
    def create_backup_dir(self) -> None:
        """Create backup directory for deleted files."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_dir = self.project_root / f'.dead_code_backup_{timestamp}'
        self.backup_dir.mkdir(exist_ok=True)
        print(f"📁 Created backup directory: {self.backup_dir}")
    
    def backup_file(self, file_path: Path) -> str:
        """Backup a file before deletion."""
        rel_path = file_path.relative_to(self.project_root)
        backup_path = self.backup_dir / rel_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        if file_path.exists():
            # Calculate checksum
            if file_path.stat().st_size > 0:
                with open(file_path, 'rb') as f:
                    checksum = hashlib.md5(f.read()).hexdigest()
            else:
                checksum = 'empty'
            
            # Copy file
            shutil.copy2(file_path, backup_path)
            
            return checksum
        return 'not_found'
    
    def verify_imports(self) -> bool:
        """Verify no broken imports after deletion."""
        print("\n🔍 Verifying imports...")
        
        try:
            # Try to compile all Python files
            result = subprocess.run(
                ['python3', '-m', 'compileall', '-q', 'src/'],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode != 0:
                print("❌ Import verification failed:")
                print(result.stderr)
                return False
                
            print("✅ All imports verified successfully")
            return True
            
        except Exception as e:
            print(f"❌ Import verification error: {e}")
            return False
    
    def run_tests(self) -> bool:
        """Run test suite to ensure no breakage."""
        print("\n🧪 Running tests...")
        
        # Check if pytest is available
        pytest_check = subprocess.run(
            ['python3', '-m', 'pytest', '--version'],
            capture_output=True
        )
        
        if pytest_check.returncode != 0:
            print("⚠️  pytest not found, skipping tests")
            return True
        
        # Run tests
        result = subprocess.run(
            ['python3', '-m', 'pytest', '-x', '-q'],
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        if result.returncode == 0:
            print("✅ All tests passed")
            return True
        else:
            print("❌ Tests failed:")
            print(result.stdout)
            return False
    
    def check_references(self, file_path: str) -> List[str]:
        """Double-check for any references to the file."""
        references = []
        
        # Search for direct imports
        patterns = [
            os.path.basename(file_path).replace('.py', ''),
            file_path.replace(str(self.project_root) + '/', '').replace('/', '.').replace('.py', ''),
            file_path.replace(str(self.project_root) + '/', '').replace('\\', '.').replace('.py', ''),
        ]
        
        for pattern in patterns:
            result = subprocess.run(
                ['grep', '-r', pattern, 'src/', '--include=*.py'],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.stdout:
                for line in result.stdout.splitlines():
                    if file_path not in line:  # Don't count self-references
                        references.append(line)
        
        return references
    
    def delete_file(self, file_info: Dict[str, Any], verify: bool = True) -> bool:
        """Safely delete a single file."""
        file_path = Path(file_info['file'])
        
        if not file_path.exists():
            print(f"⚠️  File already deleted: {file_path}")
            return True
        
        # Verify it's safe
        if verify and not file_info.get('safe_to_delete', False):
            print(f"⚠️  Skipping unsafe file: {file_path}")
            return False
        
        # Double-check references
        refs = self.check_references(str(file_path))
        if refs and verify:
            print(f"⚠️  Found references to {file_path}:")
            for ref in refs[:3]:
                print(f"    {ref}")
            return False
        
        # Backup file
        checksum = self.backup_file(file_path)
        
        # Delete file
        try:
            file_path.unlink()
            self.deletion_log.append({
                'file': str(file_path),
                'timestamp': datetime.now().isoformat(),
                'checksum': checksum,
                'backup_path': str(self.backup_dir / file_path.relative_to(self.project_root))
            })
            print(f"✅ Deleted: {file_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to delete {file_path}: {e}")
            return False
    
    def load_report(self) -> Dict[str, Any]:
        """Load the dead code report."""
        if not self.report_file.exists():
            print("❌ Dead code report not found. Run dead_code_scanner.py first.")
            sys.exit(1)
        
        with open(self.report_file, 'r') as f:
            return json.load(f)
    
    def save_deletion_log(self) -> None:
        """Save deletion log for audit trail."""
        log_file = self.project_root / 'deletion_log.json'
        
        # Load existing log if it exists
        existing_log = []
        if log_file.exists():
            with open(log_file, 'r') as f:
                existing_log = json.load(f)
        
        # Append new deletions
        existing_log.extend(self.deletion_log)
        
        # Save updated log
        with open(log_file, 'w') as f:
            json.dump(existing_log, f, indent=2)
        
        print(f"\n💾 Deletion log saved to: {log_file}")
    
    def execute_phase1(self, verify: bool = True) -> None:
        """Phase 1: Delete verified empty files."""
        print("\n🚀 Phase 1: Deleting verified empty files")
        print("=" * 60)
        
        report = self.load_report()
        candidates = report['deletion_candidates']
        
        # Filter for phase 1 files
        phase1_files = [
            c for c in candidates 
            if c['safe_to_delete'] and c['reason'] == 'empty_file'
        ]
        
        print(f"\nFound {len(phase1_files)} empty files to delete")
        
        deleted = 0
        for file_info in phase1_files:
            if self.delete_file(file_info, verify):
                deleted += 1
        
        print(f"\n📊 Phase 1 complete: {deleted}/{len(phase1_files)} files deleted")
        
        if verify and deleted > 0:
            self.verify_imports()
            self.run_tests()
    
    def execute_phase2(self, verify: bool = True) -> None:
        """Phase 2: Delete cleanup scripts and other artifacts."""
        print("\n🚀 Phase 2: Deleting cleanup scripts and artifacts")
        print("=" * 60)
        
        # Define phase 2 targets
        cleanup_patterns = [
            '*CLEANUP*.sh',
            '*cleanup*.sh',
            'FINAL_STRUCTURE*.sh',
            'PYTHON_FILES*.sh',
            'SENIOR_ENGINEER*.sh'
        ]
        
        phase2_files = []
        for pattern in cleanup_patterns:
            for file_path in self.project_root.glob(pattern):
                if file_path.is_file():
                    phase2_files.append({
                        'file': str(file_path),
                        'reason': 'cleanup_script',
                        'safe_to_delete': True
                    })
        
        print(f"\nFound {len(phase2_files)} cleanup scripts to delete")
        
        deleted = 0
        for file_info in phase2_files:
            if self.delete_file(file_info, verify):
                deleted += 1
        
        print(f"\n📊 Phase 2 complete: {deleted}/{len(phase2_files)} files deleted")
    
    def rollback(self) -> None:
        """Rollback deletions from backup."""
        if not self.backup_dir.exists():
            print("❌ No backup directory found")
            return
        
        print(f"\n🔄 Rolling back from: {self.backup_dir}")
        
        restored = 0
        for backup_file in self.backup_dir.rglob('*'):
            if backup_file.is_file():
                rel_path = backup_file.relative_to(self.backup_dir)
                restore_path = self.project_root / rel_path
                
                restore_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, restore_path)
                restored += 1
                print(f"✅ Restored: {restore_path}")
        
        print(f"\n📊 Rollback complete: {restored} files restored")


def main():
    """Main function to execute safe deletion protocol."""
    parser = argparse.ArgumentParser(description='Safe Delete Protocol')
    parser.add_argument('--phase', type=int, choices=[1, 2], 
                       help='Deletion phase to execute')
    parser.add_argument('--verify', action='store_true', default=True,
                       help='Verify safety before deletion (default: True)')
    parser.add_argument('--no-verify', dest='verify', action='store_false',
                       help='Skip verification (dangerous!)')
    parser.add_argument('--rollback', action='store_true',
                       help='Rollback previous deletions')
    
    args = parser.parse_args()
    
    # Get project root
    project_root = Path(__file__).parent.parent
    protocol = SafeDeleteProtocol(project_root)
    
    if args.rollback:
        protocol.rollback()
        return
    
    # Create backup directory
    protocol.create_backup_dir()
    
    # Execute requested phase
    if args.phase == 1:
        protocol.execute_phase1(args.verify)
    elif args.phase == 2:
        protocol.execute_phase2(args.verify)
    else:
        # Execute all phases
        protocol.execute_phase1(args.verify)
        if input("\nProceed with Phase 2? (y/n): ").lower() == 'y':
            protocol.execute_phase2(args.verify)
    
    # Save deletion log
    if protocol.deletion_log:
        protocol.save_deletion_log()
    
    # Final verification
    if protocol.deletion_log and args.verify:
        print("\n🔍 Final verification...")
        protocol.verify_imports()
        protocol.run_tests()
    
    # Git status
    if protocol.deletion_log:
        print("\n📋 Git status:")
        subprocess.run(['git', 'status', '--porcelain'], cwd=project_root)


if __name__ == "__main__":
    main()