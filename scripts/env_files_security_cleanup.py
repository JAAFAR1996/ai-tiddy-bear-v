#!/usr/bin/env python3
"""
Environment Files Security Cleanup
==================================
Secure cleanup of environment files containing potential secrets.
Removes, encrypts, or sanitizes .env backup and example files.
"""

import os
import sys
import json
import shutil
import hashlib
import secrets
from datetime import datetime
from typing import List, Dict, Any, Tuple
from cryptography.fernet import Fernet
from pathlib import Path


class EnvironmentFilesSecurityCleaner:
    """Security cleaner for environment files."""
    
    def __init__(self, project_root: str = None):
        self.project_root = project_root or os.getcwd()
        self.cleanup_results = {
            "timestamp": datetime.now().isoformat(),
            "project_root": self.project_root,
            "files_processed": [],
            "files_removed": [],
            "files_encrypted": [],
            "security_issues": [],
            "cleanup_summary": {}
        }
        
        # Generate encryption key for sensitive data
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
    
    def find_environment_files(self) -> List[str]:
        """Find all environment-related files in the project."""
        env_patterns = [
            "*.env*",
            ".env.*",
            "env.*",
            "*environment*",
            "*config*.env"
        ]
        
        found_files = []
        
        for root, dirs, files in os.walk(self.project_root):
            # Skip node_modules, venv, and other build directories
            dirs[:] = [d for d in dirs if d not in [
                'node_modules', '.venv', '.venv311', '__pycache__', 
                '.git', 'build', 'dist', '.next', 'coverage'
            ]]
            
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, self.project_root)
                
                # Check if file matches env patterns
                if (file.startswith('.env') or 
                    'env' in file.lower() or 
                    file.endswith('.env') or
                    'environment' in file.lower()):
                    found_files.append(relative_path)
        
        return sorted(found_files)
    
    def analyze_env_file_content(self, file_path: str) -> Dict[str, Any]:
        """Analyze environment file content for secrets."""
        analysis = {
            "file_path": file_path,
            "exists": False,
            "size": 0,
            "contains_secrets": False,
            "secret_patterns": [],
            "risk_level": "low",
            "should_remove": False,
            "should_encrypt": False
        }
        
        try:
            full_path = os.path.join(self.project_root, file_path)
            
            if not os.path.exists(full_path):
                return analysis
            
            analysis["exists"] = True
            analysis["size"] = os.path.getsize(full_path)
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check for secret patterns
            secret_patterns = [
                (r'(?i)(password|pwd|pass)\s*=\s*[^\s#]+', "Password"),
                (r'(?i)(secret|key)\s*=\s*[^\s#]+', "Secret/Key"),
                (r'(?i)(token|auth)\s*=\s*[^\s#]+', "Token/Auth"),
                (r'(?i)(api[_-]?key)\s*=\s*[^\s#]+', "API Key"),
                (r'(?i)(database[_-]?url|db[_-]?url)\s*=\s*[^\s#]+', "Database URL"),
                (r'(?i)(redis[_-]?url)\s*=\s*[^\s#]+', "Redis URL"),
                (r'(?i)(smtp|mail)\s*=\s*[^\s#]+', "Email Config"),
                (r'sk-[A-Za-z0-9]{48,}', "OpenAI API Key"),
                (r'pk_live_[A-Za-z0-9]+', "Stripe Live Key"),
                (r'sk_live_[A-Za-z0-9]+', "Stripe Secret Key"),
                (r'-----BEGIN [A-Z ]+-----', "Private Key"),
                (r'[A-Za-z0-9+/]{40,}={0,2}', "Base64 Encoded Secret")
            ]
            
            found_patterns = []
            for pattern, description in secret_patterns:
                import re
                if re.search(pattern, content):
                    found_patterns.append(description)
                    analysis["contains_secrets"] = True
            
            analysis["secret_patterns"] = found_patterns
            
            # Determine risk level and action
            if analysis["contains_secrets"]:
                if any("live" in pattern.lower() or "production" in content.lower() 
                      for pattern in found_patterns):
                    analysis["risk_level"] = "critical"
                elif len(found_patterns) > 3:
                    analysis["risk_level"] = "high"
                else:
                    analysis["risk_level"] = "medium"
            
            # Determine cleanup action based on file type and content
            file_name = os.path.basename(file_path).lower()
            
            if analysis["contains_secrets"]:
                if any(keyword in file_name for keyword in [
                    "backup", "old", "copy", "tmp", "temp", "bak"
                ]):
                    analysis["should_remove"] = True
                elif file_name in [".env.example", ".env.template"]:
                    # Templates should not contain real secrets
                    analysis["should_encrypt"] = True
                elif analysis["risk_level"] == "critical":
                    analysis["should_encrypt"] = True
            
        except Exception as e:
            analysis["error"] = str(e)
        
        return analysis
    
    def sanitize_env_template(self, file_path: str) -> bool:
        """Sanitize environment template files by removing real secrets."""
        try:
            full_path = os.path.join(self.project_root, file_path)
            
            with open(full_path, 'r') as f:
                lines = f.readlines()
            
            sanitized_lines = []
            changes_made = False
            
            for line in lines:
                original_line = line
                
                # If line contains a secret pattern, replace value with placeholder
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Check if this looks like a real secret (not already a placeholder)
                    if (len(value) > 10 and 
                        value not in ['', 'your_value_here', 'CHANGE_ME', 'REPLACE_WITH_ACTUAL_VALUE'] and
                        not value.startswith('${') and
                        any(keyword in key.upper() for keyword in [
                            'PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'API'
                        ])):
                        
                        # Replace with secure placeholder
                        new_value = f"REPLACE_WITH_SECURE_{key.upper()}"
                        sanitized_line = f"{key}={new_value}\n"
                        sanitized_lines.append(sanitized_line)
                        changes_made = True
                    else:
                        sanitized_lines.append(original_line)
                else:
                    sanitized_lines.append(original_line)
            
            if changes_made:
                # Backup original file
                backup_path = f"{full_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(full_path, backup_path)
                
                # Write sanitized version
                with open(full_path, 'w') as f:
                    f.writelines(sanitized_lines)
                
                print(f"✅ Sanitized template: {file_path}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error sanitizing {file_path}: {e}")
            return False
    
    def encrypt_sensitive_file(self, file_path: str) -> bool:
        """Encrypt a sensitive environment file."""
        try:
            full_path = os.path.join(self.project_root, file_path)
            
            with open(full_path, 'rb') as f:
                file_data = f.read()
            
            # Encrypt the data
            encrypted_data = self.cipher.encrypt(file_data)
            
            # Save encrypted file
            encrypted_path = f"{full_path}.encrypted"
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Save encryption key separately (should be stored securely)
            key_path = f"{full_path}.key"
            with open(key_path, 'wb') as f:
                f.write(self.encryption_key)
            
            # Remove original file
            os.remove(full_path)
            
            print(f"🔒 Encrypted file: {file_path}")
            print(f"   Encrypted data: {encrypted_path}")
            print(f"   Encryption key: {key_path}")
            print(f"   ⚠️  Store the encryption key securely!")
            
            return True
            
        except Exception as e:
            print(f"❌ Error encrypting {file_path}: {e}")
            return False
    
    def remove_insecure_file(self, file_path: str) -> bool:
        """Securely remove an insecure environment file."""
        try:
            full_path = os.path.join(self.project_root, file_path)
            
            # Create secure deletion log entry
            file_hash = self.calculate_file_hash(full_path)
            
            # Overwrite file with random data before deletion (basic secure delete)
            file_size = os.path.getsize(full_path)
            with open(full_path, 'wb') as f:
                f.write(secrets.token_bytes(file_size))
            
            # Remove file
            os.remove(full_path)
            
            print(f"🗑️  Securely removed: {file_path}")
            
            # Log removal
            self.cleanup_results["files_removed"].append({
                "file_path": file_path,
                "file_hash": file_hash,
                "removal_time": datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Error removing {file_path}: {e}")
            return False
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            return file_hash
        except:
            return "unknown"
    
    def cleanup_environment_files(self) -> Dict[str, Any]:
        """Perform comprehensive cleanup of environment files."""
        print("🧹 Starting environment files security cleanup...")
        print("=" * 60)
        
        # Find all environment files
        env_files = self.find_environment_files()
        print(f"📄 Found {len(env_files)} environment files")
        
        if not env_files:
            print("✅ No environment files found")
            return self.cleanup_results
        
        # Analyze each file
        for file_path in env_files:
            print(f"\n🔍 Analyzing: {file_path}")
            analysis = self.analyze_env_file_content(file_path)
            
            self.cleanup_results["files_processed"].append(analysis)
            
            if not analysis["exists"]:
                continue
            
            print(f"   Size: {analysis['size']} bytes")
            print(f"   Contains secrets: {analysis['contains_secrets']}")
            print(f"   Risk level: {analysis['risk_level']}")
            
            if analysis["contains_secrets"]:  
                print(f"   Secret patterns: {', '.join(analysis['secret_patterns'])}")
                
                # Determine action
                if analysis["should_remove"]:
                    print(f"   🚨 Action: REMOVE (backup/temporary file with secrets)")
                    if self.remove_insecure_file(file_path):
                        self.cleanup_results["files_removed"].append(file_path)
                
                elif analysis["should_encrypt"]:
                    print(f"   🔒 Action: ENCRYPT (sensitive file)")
                    if self.encrypt_sensitive_file(file_path):
                        self.cleanup_results["files_encrypted"].append(file_path)
                
                elif file_path.endswith(('.example', '.template')):
                    print(f"   🧹 Action: SANITIZE (template with real secrets)")
                    self.sanitize_env_template(file_path)
                
                else:
                    print(f"   ⚠️  Action: MANUAL REVIEW REQUIRED")
                    self.cleanup_results["security_issues"].append({
                        "file": file_path,
                        "issue": "Contains secrets but needs manual review",
                        "risk_level": analysis["risk_level"]
                    })
            else:
                print(f"   ✅ Action: SAFE (no secrets detected)")
        
        # Generate summary
        total_files = len(env_files)
        files_with_secrets = len([f for f in self.cleanup_results["files_processed"] if f["contains_secrets"]])
        
        self.cleanup_results["cleanup_summary"] = {
            "total_files_found": total_files,
            "files_with_secrets": files_with_secrets,
            "files_removed": len(self.cleanup_results["files_removed"]),
            "files_encrypted": len(self.cleanup_results["files_encrypted"]),
            "security_issues": len(self.cleanup_results["security_issues"])
        }
        
        return self.cleanup_results
    
    def generate_cleanup_report(self) -> str:
        """Generate detailed cleanup report."""
        results = self.cleanup_results
        summary = results["cleanup_summary"]
        
        report = f"""
🧹 ENVIRONMENT FILES SECURITY CLEANUP REPORT
{'=' * 60}
Timestamp: {results['timestamp']}
Project Root: {results['project_root']}

CLEANUP SUMMARY:
- Total files found: {summary['total_files_found']}
- Files with secrets: {summary['files_with_secrets']}
- Files removed: {summary['files_removed']}
- Files encrypted: {summary['files_encrypted']}
- Issues requiring review: {summary['security_issues']}

"""
        
        if results["files_removed"]:
            report += "\n🗑️  REMOVED FILES:\n"
            for file_path in results["files_removed"]:
                report += f"   • {file_path}\n"
        
        if results["files_encrypted"]:
            report += "\n🔒 ENCRYPTED FILES:\n"
            for file_path in results["files_encrypted"]:
                report += f"   • {file_path}\n"
        
        if results["security_issues"]:
            report += "\n⚠️  MANUAL REVIEW REQUIRED:\n"
            for issue in results["security_issues"]:
                report += f"   • {issue['file']} - {issue['issue']} (Risk: {issue['risk_level']})\n"
        
        if summary["files_removed"] > 0 or summary["files_encrypted"] > 0:
            report += f"""
🎉 CLEANUP COMPLETED SUCCESSFULLY
{'=' * 40}
Environment files have been secured:
- {summary['files_removed']} potentially dangerous files removed
- {summary['files_encrypted']} sensitive files encrypted
- {summary['security_issues']} files need manual review

IMPORTANT SECURITY NOTES:
1. Encrypted file keys are stored locally - move to secure location
2. Review any files marked for manual review
3. Update .gitignore to prevent future secret commits
4. Consider using environment variable management service

"""
        else:
            report += "\n✅ NO CLEANUP ACTIONS REQUIRED\n"
            report += "All environment files are already secure.\n"
        
        return report


def main():
    """Main cleanup execution."""
    print("🔐 AI Teddy Bear - Environment Files Security Cleanup")
    print("=" * 60)
    
    # Get project root
    project_root = "/mnt/c/Users/jaafa/Desktop/ai teddy bear"
    
    # Create cleaner
    cleaner = EnvironmentFilesSecurityCleaner(project_root)
    
    # Run cleanup
    results = cleaner.cleanup_environment_files()
    
    # Generate and display report
    report = cleaner.generate_cleanup_report()
    print(report)
    
    # Save detailed results
    results_file = os.path.join(project_root, "environment_cleanup_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"📄 Detailed results saved to: {results_file}")
    
    # Return appropriate exit code
    if results["cleanup_summary"]["security_issues"] > 0:
        print("\n⚠️  Some files require manual review")
        return 1
    else:
        print("\n✅ Environment files cleanup completed successfully")
        return 0


if __name__ == "__main__":
    sys.exit(main())