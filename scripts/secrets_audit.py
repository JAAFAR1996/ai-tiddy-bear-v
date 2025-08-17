#!/usr/bin/env python3
"""
🔐 AI TEDDY BEAR - COMPREHENSIVE SECRETS AUDIT
==============================================

Comprehensive audit of all secrets, keys, and sensitive data:
1. Scans for hardcoded secrets in source code
2. Validates secret strength and entropy
3. Checks for exposed secrets in config files
4. Validates environment variable usage
5. Generates security recommendations
"""

import os
import re
import json
import secrets
import hashlib
import base64
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import subprocess

class SecretsAuditor:
    """Comprehensive secrets security auditor."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'critical_issues': [],
            'high_issues': [],
            'medium_issues': [],
            'low_issues': [],
            'recommendations': [],
            'summary': {},
            'file_scan_results': []
        }
        
        # Secret patterns to detect
        self.secret_patterns = {
            'api_key': r'(?i)(api[_-]?key|apikey)[\s]*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            'secret_key': r'(?i)(secret[_-]?key|secretkey)[\s]*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            'jwt_secret': r'(?i)(jwt[_-]?secret|jwtsecret)[\s]*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            'password': r'(?i)(password|pwd|pass)[\s]*[=:]\s*["\']?([a-zA-Z0-9_\-@#$%^&*()]{8,})["\']?',
            'private_key': r'-----BEGIN[\s\w]*PRIVATE KEY-----',
            'aws_access': r'(?i)(aws[_-]?access[_-]?key[_-]?id)[\s]*[=:]\s*["\']?([A-Z0-9]{20})["\']?',
            'aws_secret': r'(?i)(aws[_-]?secret[_-]?access[_-]?key)[\s]*[=:]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?',
            'stripe_key': r'(?i)(stripe[_-]?(?:secret|public)[_-]?key)[\s]*[=:]\s*["\']?(sk_live_[a-zA-Z0-9_]+|pk_live_[a-zA-Z0-9_]+)["\']?',
            'openai_key': r'(?i)(openai[_-]?api[_-]?key)[\s]*[=:]\s*["\']?(sk-[a-zA-Z0-9]{48})["\']?',
            'elevenlabs_key': r'(?i)(elevenlabs[_-]?api[_-]?key)[\s]*[=:]\s*["\']?([a-f0-9]{32})["\']?',
            'generic_token': r'(?i)(token|access_token|refresh_token)[\s]*[=:]\s*["\']?([a-zA-Z0-9_\-\.]{32,})["\']?',
            'database_url': r'(?i)(database[_-]?url|db[_-]?url)[\s]*[=:]\s*["\']?([a-zA-Z0-9+://][^\s"\']+)["\']?',
            'connection_string': r'(?i)(connection[_-]?string)[\s]*[=:]\s*["\']?([a-zA-Z0-9+://][^\s"\']+)["\']?'
        }
        
        # Weak/test secrets patterns
        self.weak_patterns = {
            'test_secrets': r'(?i)(test|demo|example|changeme|default|admin|root)',
            'simple_passwords': r'^(123456|password|admin|root|test|demo)$',
            'sequential': r'(?i)(abc|123|qwerty)',
            'dev_keys': r'(?i)(dev|development|staging|local)'
        }
        
        # Files to scan
        self.scan_extensions = {'.py', '.js', '.ts', '.json', '.yaml', '.yml', '.env', '.conf', '.config', '.ini'}
        self.exclude_dirs = {'.git', '__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv', '.pio', '.venv311'}
        
    def calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of text."""
        if not text:
            return 0.0
        
        # Count character frequencies
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # Calculate entropy
        entropy = 0.0
        text_len = len(text)
        for count in char_counts.values():
            probability = count / text_len
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)
        
        return entropy
    
    def assess_secret_strength(self, secret: str, secret_type: str) -> Dict[str, Any]:
        """Assess the strength of a secret."""
        assessment = {
            'length': len(secret),
            'entropy': self.calculate_entropy(secret),
            'strength': 'weak',
            'issues': [],
            'recommendations': []
        }
        
        # Length checks
        min_lengths = {
            'api_key': 32,
            'secret_key': 32,
            'jwt_secret': 32,
            'password': 12,
            'token': 32
        }
        
        min_length = min_lengths.get(secret_type, 16)
        if assessment['length'] < min_length:
            assessment['issues'].append(f"Too short (minimum {min_length} characters)")
        
        # Entropy checks
        if assessment['entropy'] < 3.5:
            assessment['issues'].append("Low entropy (predictable)")
            assessment['recommendations'].append("Use cryptographically secure random generation")
        
        # Pattern checks for weak secrets
        for pattern_name, pattern in self.weak_patterns.items():
            if re.search(pattern, secret):
                assessment['issues'].append(f"Contains weak pattern: {pattern_name}")
        
        # Character diversity
        has_upper = any(c.isupper() for c in secret)
        has_lower = any(c.islower() for c in secret)
        has_digit = any(c.isdigit() for c in secret)
        has_special = any(not c.isalnum() for c in secret)
        
        diversity_count = sum([has_upper, has_lower, has_digit, has_special])
        if diversity_count < 3 and secret_type == 'password':
            assessment['issues'].append("Insufficient character diversity")
        
        # Overall strength assessment
        if not assessment['issues'] and assessment['entropy'] > 4.0 and assessment['length'] >= min_length:
            assessment['strength'] = 'strong'
        elif len(assessment['issues']) <= 1 and assessment['entropy'] > 3.0:
            assessment['strength'] = 'medium'
        
        return assessment
    
    def check_git_history_exposure(self, file_path: Path) -> List[str]:
        """Check if secrets might be exposed in git history."""
        issues = []
        try:
            # Check if file is tracked by git
            result = subprocess.run(
                ['git', 'log', '--oneline', str(file_path)],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                issues.append("File is tracked in git history - secrets may be exposed")
                
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass  # Git not available or other issues
        
        return issues
    
    def scan_file(self, file_path: Path) -> Dict[str, Any]:
        """Scan a single file for secrets."""
        result = {
            'file': str(file_path),
            'secrets_found': [],
            'issues': [],
            'recommendations': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check each secret pattern
            for pattern_name, pattern in self.secret_patterns.items():
                matches = re.finditer(pattern, content, re.MULTILINE)
                
                for match in matches:
                    secret_value = match.group(2) if len(match.groups()) >= 2 else match.group(0)
                    line_num = content[:match.start()].count('\n') + 1
                    
                    # Assess secret strength
                    strength_assessment = self.assess_secret_strength(secret_value, pattern_name)
                    
                    secret_info = {
                        'type': pattern_name,
                        'line': line_num,
                        'value_hash': hashlib.sha256(secret_value.encode()).hexdigest()[:16],
                        'strength': strength_assessment['strength'],
                        'length': len(secret_value),
                        'entropy': strength_assessment['entropy'],
                        'issues': strength_assessment['issues'],
                        'context': match.group(0)[:100]  # First 100 chars for context
                    }
                    
                    result['secrets_found'].append(secret_info)
                    
                    # Categorize issues
                    if strength_assessment['strength'] == 'weak':
                        self.results['critical_issues'].append({
                            'file': str(file_path),
                            'line': line_num,
                            'type': pattern_name,
                            'issue': 'Weak secret detected',
                            'details': strength_assessment['issues']
                        })
                    elif any('test' in issue.lower() or 'demo' in issue.lower() for issue in strength_assessment['issues']):
                        self.results['high_issues'].append({
                            'file': str(file_path),
                            'line': line_num,
                            'type': pattern_name,
                            'issue': 'Test/demo secret detected',
                            'details': strength_assessment['issues']
                        })
            
            # Check for git exposure
            git_issues = self.check_git_history_exposure(file_path)
            result['issues'].extend(git_issues)
            
            # Special checks for .env files
            if file_path.name.startswith('.env') and not file_path.name.endswith('.template'):
                self.results['critical_issues'].append({
                    'file': str(file_path),
                    'issue': 'Environment file with secrets detected',
                    'details': 'Environment files should not be committed to version control'
                })
        
        except Exception as e:
            result['issues'].append(f"Error scanning file: {e}")
        
        return result
    
    def scan_directory(self) -> None:
        """Scan entire directory for secrets."""
        print("🔍 Scanning for secrets in source code...")
        
        # Prioritize critical directories first
        priority_dirs = ['src', 'scripts', 'deployment', '.']
        
        scanned_files = 0
        max_files = 500  # Limit total files scanned
        
        for priority_dir in priority_dirs:
            priority_path = self.project_root / priority_dir
            if not priority_path.exists():
                continue
                
            print(f"   Scanning {priority_dir}...")
            
            for file_path in priority_path.rglob('*'):
                if scanned_files >= max_files:
                    print(f"   Reached scan limit of {max_files} files")
                    return
                    
                # Skip directories
                if file_path.is_dir():
                    continue
                
                # Skip excluded directories
                if any(excluded in file_path.parts for excluded in self.exclude_dirs):
                    continue
                
                # Only scan relevant file types
                if file_path.suffix not in self.scan_extensions:
                    continue
                
                # Skip binary-looking files
                if file_path.stat().st_size > 1024 * 1024:  # Skip files > 1MB
                    continue
                
                try:
                    file_result = self.scan_file(file_path)
                    if file_result['secrets_found'] or file_result['issues']:
                        self.results['file_scan_results'].append(file_result)
                    scanned_files += 1
                    
                    if scanned_files % 25 == 0:
                        print(f"   Scanned {scanned_files} files...")
                        
                except Exception as e:
                    print(f"   Error scanning {file_path}: {e}")
    
    def check_environment_variables(self) -> None:
        """Check environment variables for secrets."""
        print("🌐 Checking environment variables...")
        
        env_secrets = []
        for key, value in os.environ.items():
            if any(pattern in key.upper() for pattern in ['SECRET', 'KEY', 'TOKEN', 'PASSWORD', 'API']):
                strength = self.assess_secret_strength(value, 'secret_key')
                
                env_secrets.append({
                    'variable': key,
                    'strength': strength['strength'],
                    'length': len(value),
                    'entropy': strength['entropy'],
                    'issues': strength['issues']
                })
                
                if strength['strength'] == 'weak':
                    self.results['critical_issues'].append({
                        'type': 'environment_variable',
                        'variable': key,
                        'issue': 'Weak environment variable secret',
                        'details': strength['issues']
                    })
        
        self.results['environment_secrets'] = env_secrets
    
    def generate_recommendations(self) -> None:
        """Generate security recommendations."""
        recommendations = []
        
        # Based on issues found
        if self.results['critical_issues']:
            recommendations.extend([
                "🚨 CRITICAL: Replace all weak secrets immediately",
                "🔑 Use cryptographically secure secret generation",
                "📝 Never commit .env files to version control",
                "🔄 Rotate all exposed secrets"
            ])
        
        if self.results['high_issues']:
            recommendations.extend([
                "⚠️ Remove all test/demo secrets from production code",
                "🧹 Clean up development secrets from codebase"
            ])
        
        # General recommendations
        recommendations.extend([
            "🔐 Use environment variables for all secrets",
            "🏗️ Implement secret management system (HashiCorp Vault, AWS Secrets Manager)",
            "🔄 Implement regular secret rotation policy",
            "📊 Set up secret scanning in CI/CD pipeline",
            "🕵️ Monitor for secret exposure in logs and errors",
            "📋 Create incident response plan for secret exposure",
            "🎯 Use principle of least privilege for secret access",
            "🔍 Regular security audits and penetration testing"
        ])
        
        self.results['recommendations'] = recommendations
    
    def generate_summary(self) -> None:
        """Generate audit summary."""
        total_secrets = sum(len(result['secrets_found']) for result in self.results['file_scan_results'])
        files_with_secrets = len([r for r in self.results['file_scan_results'] if r['secrets_found']])
        
        self.results['summary'] = {
            'total_files_scanned': len(self.results['file_scan_results']),
            'files_with_secrets': files_with_secrets,
            'total_secrets_found': total_secrets,
            'critical_issues_count': len(self.results['critical_issues']),
            'high_issues_count': len(self.results['high_issues']),
            'medium_issues_count': len(self.results['medium_issues']),
            'low_issues_count': len(self.results['low_issues']),
            'overall_risk_level': self.calculate_risk_level()
        }
    
    def calculate_risk_level(self) -> str:
        """Calculate overall risk level."""
        if self.results['critical_issues']:
            return 'CRITICAL'
        elif len(self.results['high_issues']) > 5:
            return 'HIGH'
        elif len(self.results['high_issues']) > 0 or len(self.results['medium_issues']) > 10:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def print_report(self) -> None:
        """Print formatted audit report."""
        summary = self.results['summary']
        
        print("\n" + "="*80)
        print("🔐 AI TEDDY BEAR - COMPREHENSIVE SECRETS AUDIT REPORT")
        print("="*80)
        print(f"📅 Audit Date: {self.results['timestamp']}")
        print(f"🎯 Overall Risk Level: {summary['overall_risk_level']}")
        print()
        
        # Summary
        print("📊 AUDIT SUMMARY:")
        print(f"   Files Scanned: {summary['total_files_scanned']:,}")
        print(f"   Files with Secrets: {summary['files_with_secrets']:,}")
        print(f"   Total Secrets Found: {summary['total_secrets_found']:,}")
        print()
        
        # Issues by severity
        print("🚨 ISSUES BY SEVERITY:")
        print(f"   Critical: {summary['critical_issues_count']:,}")
        print(f"   High: {summary['high_issues_count']:,}")
        print(f"   Medium: {summary['medium_issues_count']:,}")
        print(f"   Low: {summary['low_issues_count']:,}")
        print()
        
        # Critical issues details
        if self.results['critical_issues']:
            print("🚨 CRITICAL ISSUES (IMMEDIATE ACTION REQUIRED):")
            for issue in self.results['critical_issues'][:10]:  # Show first 10
                print(f"   • {issue.get('file', 'N/A')}:{issue.get('line', 'N/A')} - {issue['issue']}")
                if issue.get('details'):
                    for detail in issue['details'][:2]:  # Show first 2 details
                        print(f"     └─ {detail}")
            print()
        
        # High issues details
        if self.results['high_issues']:
            print("⚠️ HIGH PRIORITY ISSUES:")
            for issue in self.results['high_issues'][:5]:  # Show first 5
                print(f"   • {issue.get('file', 'N/A')}:{issue.get('line', 'N/A')} - {issue['issue']}")
            print()
        
        # Environment variables
        if 'environment_secrets' in self.results:
            env_secrets = self.results['environment_secrets']
            if env_secrets:
                print("🌐 ENVIRONMENT VARIABLES WITH SECRETS:")
                for env_secret in env_secrets[:5]:  # Show first 5
                    print(f"   • {env_secret['variable']}: {env_secret['strength'].upper()} "
                          f"(Length: {env_secret['length']}, Entropy: {env_secret['entropy']:.2f})")
                print()
        
        # Top recommendations
        print("💡 TOP RECOMMENDATIONS:")
        for rec in self.results['recommendations'][:8]:  # Show first 8
            print(f"   {rec}")
        print()
        
        print("="*80)
    
    def save_report(self, filename: Optional[str] = None) -> str:
        """Save detailed report to JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"secrets_audit_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        return filename
    
    def run_comprehensive_audit(self) -> Dict[str, Any]:
        """Run complete secrets audit."""
        print("🔐 Starting comprehensive secrets audit...")
        
        # Scan directory
        self.scan_directory()
        
        # Check environment variables
        self.check_environment_variables()
        
        # Generate analysis
        self.generate_recommendations()
        self.generate_summary()
        
        # Print report
        self.print_report()
        
        # Save detailed report
        report_file = self.save_report()
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return self.results

def main():
    """Main function."""
    auditor = SecretsAuditor()
    results = auditor.run_comprehensive_audit()
    
    # Return appropriate exit code
    if results['summary']['overall_risk_level'] in ['CRITICAL', 'HIGH']:
        print(f"\n❌ AUDIT FAILED - {results['summary']['overall_risk_level']} RISK DETECTED")
        return 1
    else:
        print(f"\n✅ AUDIT PASSED - {results['summary']['overall_risk_level']} RISK LEVEL")
        return 0

if __name__ == "__main__":
    exit(main())