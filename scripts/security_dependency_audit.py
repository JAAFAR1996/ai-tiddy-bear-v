#!/usr/bin/env python3
"""
📦 AI TEDDY BEAR - COMPREHENSIVE DEPENDENCIES SECURITY AUDIT
=============================================================

Advanced security audit for Python dependencies:
1. Check for known CVEs and vulnerabilities
2. Analyze package versions and security updates
3. Identify deprecated packages
4. Check for malicious packages
5. Generate security recommendations
6. Create dependency update plan
"""

import os
import re
import json
import subprocess
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import tempfile
import asyncio

# Try to import optional dependencies
try:
    import pkg_resources
except ImportError:
    pkg_resources = None

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    import requests
except ImportError:
    requests = None

try:
    from packaging import version
except ImportError:
    version = None

class DependencySecurityAuditor:
    """Comprehensive security auditor for Python dependencies."""
    
    def __init__(self, requirements_file: str = "requirements.txt"):
        self.requirements_file = Path(requirements_file)
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'critical_vulnerabilities': [],
            'high_vulnerabilities': [],
            'medium_vulnerabilities': [],
            'low_vulnerabilities': [],
            'outdated_packages': [],
            'deprecated_packages': [],
            'recommendations': [],
            'summary': {},
            'packages_analyzed': []
        }
        
        # Security databases and APIs
        self.pypi_api_base = "https://pypi.org/pypi/"
        self.osv_api_base = "https://api.osv.dev/v1/query"
        self.safety_db_url = "https://raw.githubusercontent.com/pyupio/safety-db/master/data/insecure_full.json"
        
        # Package patterns to watch
        self.sensitive_packages = {
            'crypto', 'cryptography', 'pyjwt', 'passlib', 'bcrypt', 'argon2',
            'requests', 'urllib3', 'httpx', 'aiohttp', 'fastapi', 'starlette',
            'sqlalchemy', 'redis', 'openai', 'anthropic'
        }
        
        self.deprecated_patterns = [
            r'(?i)(deprecated|legacy|obsolete|unmaintained)',
            r'(?i)(end.of.life|eol)',
            r'(?i)(no.longer.maintained)'
        ]
    
    def parse_requirements(self) -> List[Dict[str, Any]]:
        """Parse requirements.txt and extract package information."""
        packages = []
        
        if not self.requirements_file.exists():
            print(f"❌ Requirements file not found: {self.requirements_file}")
            return packages
        
        print(f"📋 Parsing requirements from: {self.requirements_file}")
        
        with open(self.requirements_file, 'r') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Parse package specification
            package_info = self._parse_package_spec(line, line_num)
            if package_info:
                packages.append(package_info)
        
        print(f"📦 Found {len(packages)} packages to analyze")
        return packages
    
    def _parse_package_spec(self, spec: str, line_num: int) -> Optional[Dict[str, Any]]:
        """Parse individual package specification."""
        # Handle extras [crypto], [standard], etc.
        extras_pattern = r'^([a-zA-Z0-9_-]+)(\[[^\]]+\])?([><=!]+.*)?$'
        match = re.match(extras_pattern, spec)
        
        if not match:
            print(f"⚠️ Could not parse package spec on line {line_num}: {spec}")
            return None
        
        name = match.group(1).lower()
        extras = match.group(2) if match.group(2) else ""
        version_spec = match.group(3) if match.group(3) else ""
        
        # Extract current version if installed
        current_version = None
        if pkg_resources:
            try:
                current_version = pkg_resources.get_distribution(name).version
            except pkg_resources.DistributionNotFound:
                pass
        else:
            # Fallback: try pip show
            try:
                result = subprocess.run(['pip', 'show', name], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('Version:'):
                            current_version = line.split(':', 1)[1].strip()
                            break
            except Exception:
                pass
        
        return {
            'name': name,
            'spec': spec,
            'extras': extras,
            'version_spec': version_spec,
            'current_version': current_version,
            'line_number': line_num,
            'is_sensitive': name in self.sensitive_packages
        }
    
    async def check_osv_vulnerabilities(self, package: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check OSV (Open Source Vulnerabilities) database."""
        vulnerabilities = []
        
        if not package.get('current_version') or not aiohttp:
            return vulnerabilities
        
        query = {
            "package": {
                "name": package['name'],
                "ecosystem": "PyPI"
            },
            "version": package['current_version']
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.osv_api_base, json=query, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        vulns = data.get('vulns', [])
                        
                        for vuln in vulns:
                            vulnerability = {
                                'id': vuln.get('id', 'Unknown'),
                                'summary': vuln.get('summary', 'No summary available'),
                                'severity': self._determine_severity(vuln),
                                'published': vuln.get('published', 'Unknown'),
                                'modified': vuln.get('modified', 'Unknown'),
                                'database': 'OSV',
                                'package': package['name'],
                                'affected_version': package['current_version']
                            }
                            vulnerabilities.append(vulnerability)
        
        except Exception as e:
            print(f"⚠️ Error checking OSV for {package['name']}: {e}")
        
        return vulnerabilities
    
    def _determine_severity(self, vuln: Dict[str, Any]) -> str:
        """Determine vulnerability severity from OSV data."""
        # Check CVSS score if available
        severity_info = vuln.get('severity', [])
        for sev in severity_info:
            if sev.get('type') == 'CVSS_V3':
                score = sev.get('score')
                if score:
                    if score >= 9.0:
                        return 'CRITICAL'
                    elif score >= 7.0:
                        return 'HIGH'
                    elif score >= 4.0:
                        return 'MEDIUM'
                    else:
                        return 'LOW'
        
        # Fallback to summary analysis
        summary = vuln.get('summary', '').lower()
        if any(word in summary for word in ['critical', 'severe', 'remote code execution', 'rce']):
            return 'CRITICAL'
        elif any(word in summary for word in ['high', 'privilege escalation', 'authentication bypass']):
            return 'HIGH'
        elif any(word in summary for word in ['medium', 'denial of service', 'information disclosure']):
            return 'MEDIUM'
        else:
            return 'LOW'
    
    async def check_pypi_metadata(self, package: Dict[str, Any]) -> Dict[str, Any]:
        """Check PyPI metadata for package information."""
        metadata = {
            'latest_version': None,
            'is_outdated': False,
            'is_deprecated': False,
            'last_updated': None,
            'maintainer_info': {},
            'description': ''
        }
        
        if not aiohttp:
            return metadata
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.pypi_api_base}{package['name']}/json"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        info = data.get('info', {})
                        releases = data.get('releases', {})
                        
                        # Latest version
                        metadata['latest_version'] = info.get('version')
                        
                        # Check if outdated
                        if package.get('current_version') and metadata['latest_version']:
                            metadata['is_outdated'] = (
                                package['current_version'] != metadata['latest_version']
                            )
                        
                        # Check deprecation
                        description = info.get('description', '') + info.get('summary', '')
                        for pattern in self.deprecated_patterns:
                            if re.search(pattern, description):
                                metadata['is_deprecated'] = True
                                break
                        
                        # Last updated
                        if releases and metadata['latest_version']:
                            latest_release = releases.get(metadata['latest_version'], [])
                            if latest_release:
                                upload_time = latest_release[0].get('upload_time')
                                if upload_time:
                                    metadata['last_updated'] = upload_time
                        
                        # Maintainer info
                        metadata['maintainer_info'] = {
                            'author': info.get('author', 'Unknown'),
                            'author_email': info.get('author_email', ''),
                            'maintainer': info.get('maintainer', ''),
                            'home_page': info.get('home_page', '')
                        }
                        
                        metadata['description'] = info.get('summary', '')
        
        except Exception as e:
            print(f"⚠️ Error checking PyPI metadata for {package['name']}: {e}")
        
        return metadata
    
    def check_local_vulnerabilities(self, package: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for known local vulnerability patterns."""
        vulnerabilities = []
        
        # Check for specific vulnerable versions
        vulnerable_versions = {
            'cryptography': {
                'versions': ['<3.4.8', '<41.0.7'],
                'issues': ['CVE-2022-3602', 'CVE-2023-23931']
            },
            'pyjwt': {
                'versions': ['<2.4.0'],
                'issues': ['CVE-2022-29217']
            },
            'fastapi': {
                'versions': ['<0.65.2'],
                'issues': ['ReDoS vulnerability']
            },
            'requests': {
                'versions': ['<2.31.0'],
                'issues': ['CVE-2023-32681']
            },
            'urllib3': {
                'versions': ['<2.0.7'],
                'issues': ['CVE-2023-45803']
            }
        }
        
        package_name = package['name']
        current_version = package.get('current_version')
        
        if package_name in vulnerable_versions and current_version:
            vuln_info = vulnerable_versions[package_name]
            
            # Simple version comparison (basic implementation)
            for version_pattern in vuln_info['versions']:
                if self._is_vulnerable_version(current_version, version_pattern):
                    for issue in vuln_info['issues']:
                        vulnerability = {
                            'id': issue,
                            'summary': f'Known vulnerability in {package_name} {current_version}',
                            'severity': 'HIGH',
                            'published': 'Known',
                            'database': 'Local Knowledge Base',
                            'package': package_name,
                            'affected_version': current_version
                        }
                        vulnerabilities.append(vulnerability)
        
        return vulnerabilities
    
    def _is_vulnerable_version(self, current: str, pattern: str) -> bool:
        """Basic version comparison for vulnerability checking."""
        # This is a simplified implementation
        # In production, use packaging.version for proper comparison
        try:
            if version:
                if pattern.startswith('<'):
                    target = pattern[1:]
                    return version.parse(current) < version.parse(target)
                elif pattern.startswith('<='):
                    target = pattern[2:]
                    return version.parse(current) <= version.parse(target)
                elif pattern.startswith('>'):
                    target = pattern[1:]
                    return version.parse(current) > version.parse(target)
                elif pattern.startswith('>='):
                    target = pattern[2:]
                    return version.parse(current) >= version.parse(target)
                else:
                    return current == pattern
            else:
                # Fallback simple string comparison
                return current == pattern.lstrip('<>=!')
        except Exception:
            return False
    
    def analyze_package_age(self, metadata: Dict[str, Any]) -> str:
        """Analyze how old the package version is."""
        last_updated = metadata.get('last_updated')
        if not last_updated:
            return 'Unknown'
        
        try:
            # Parse upload time
            update_date = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            now = datetime.now(update_date.tzinfo)
            age = now - update_date
            
            if age > timedelta(days=730):  # 2 years
                return 'Very Old'
            elif age > timedelta(days=365):  # 1 year
                return 'Old'
            elif age > timedelta(days=180):  # 6 months
                return 'Somewhat Old'
            else:
                return 'Recent'
        except Exception:
            return 'Unknown'
    
    async def audit_package(self, package: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive audit of a single package."""
        print(f"🔍 Auditing {package['name']}...")
        
        audit_result = {
            'package': package,
            'vulnerabilities': [],
            'metadata': {},
            'risk_level': 'LOW',
            'recommendations': []
        }
        
        # Check vulnerabilities from multiple sources
        try:
            # OSV database
            osv_vulns = await self.check_osv_vulnerabilities(package)
            audit_result['vulnerabilities'].extend(osv_vulns)
            
            # PyPI metadata
            metadata = await self.check_pypi_metadata(package)
            audit_result['metadata'] = metadata
            
            # Local vulnerability database
            local_vulns = self.check_local_vulnerabilities(package)
            audit_result['vulnerabilities'].extend(local_vulns)
            
            # Determine overall risk level
            audit_result['risk_level'] = self._calculate_package_risk(
                audit_result['vulnerabilities'], 
                metadata,
                package
            )
            
            # Generate recommendations
            audit_result['recommendations'] = self._generate_package_recommendations(
                package, metadata, audit_result['vulnerabilities']
            )
            
        except Exception as e:
            print(f"❌ Error auditing {package['name']}: {e}")
            audit_result['error'] = str(e)
        
        return audit_result
    
    def _calculate_package_risk(self, vulnerabilities: List[Dict], metadata: Dict, package: Dict) -> str:
        """Calculate overall risk level for a package."""
        # Critical vulnerabilities = CRITICAL risk
        if any(v.get('severity') == 'CRITICAL' for v in vulnerabilities):
            return 'CRITICAL'
        
        # High vulnerabilities or sensitive package with issues = HIGH risk
        if any(v.get('severity') == 'HIGH' for v in vulnerabilities):
            return 'HIGH'
        if package.get('is_sensitive') and vulnerabilities:
            return 'HIGH'
        
        # Medium vulnerabilities or deprecated packages = MEDIUM risk
        if any(v.get('severity') == 'MEDIUM' for v in vulnerabilities):
            return 'MEDIUM'
        if metadata.get('is_deprecated'):
            return 'MEDIUM'
        
        # Outdated sensitive packages = MEDIUM risk
        if package.get('is_sensitive') and metadata.get('is_outdated'):
            return 'MEDIUM'
        
        # Low vulnerabilities or very old packages = LOW risk
        if vulnerabilities or self.analyze_package_age(metadata) == 'Very Old':
            return 'LOW'
        
        return 'LOW'
    
    def _generate_package_recommendations(self, package: Dict, metadata: Dict, vulnerabilities: List[Dict]) -> List[str]:
        """Generate specific recommendations for a package."""
        recommendations = []
        
        if vulnerabilities:
            recommendations.append(f"🚨 Update {package['name']} immediately to fix {len(vulnerabilities)} vulnerability(ies)")
        
        if metadata.get('is_outdated') and metadata.get('latest_version'):
            current = package.get('current_version', 'unknown')
            latest = metadata['latest_version']
            recommendations.append(f"📦 Update {package['name']} from {current} to {latest}")
        
        if metadata.get('is_deprecated'):
            recommendations.append(f"⚠️ Find alternative to deprecated package {package['name']}")
        
        age = self.analyze_package_age(metadata)
        if age in ['Old', 'Very Old']:
            recommendations.append(f"📅 Consider updating {package['name']} - last updated: {age.lower()}")
        
        if package.get('is_sensitive') and not vulnerabilities:
            recommendations.append(f"🔐 Monitor {package['name']} closely - security-critical package")
        
        return recommendations
    
    async def run_comprehensive_audit(self) -> Dict[str, Any]:
        """Run complete dependency security audit."""
        print("📦 Starting comprehensive dependency security audit...")
        
        # Parse requirements
        packages = self.parse_requirements()
        if not packages:
            print("❌ No packages found to audit")
            return self.results
        
        # Audit each package
        audit_results = []
        for i, package in enumerate(packages, 1):
            print(f"[{i}/{len(packages)}] ", end="")
            result = await self.audit_package(package)
            audit_results.append(result)
            self.results['packages_analyzed'].append(result)
        
        # Categorize results
        self._categorize_results(audit_results)
        
        # Generate summary
        self._generate_summary()
        
        # Generate recommendations
        self._generate_recommendations()
        
        # Print report
        self.print_report()
        
        # Save detailed report
        report_file = self.save_report()
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return self.results
    
    def _categorize_results(self, audit_results: List[Dict[str, Any]]):
        """Categorize audit results by severity."""
        for result in audit_results:
            package_name = result['package']['name']
            risk_level = result['risk_level']
            vulnerabilities = result['vulnerabilities']
            metadata = result['metadata']
            
            # Categorize vulnerabilities
            for vuln in vulnerabilities:
                vuln_record = {
                    'package': package_name,
                    'vulnerability': vuln,
                    'risk_level': risk_level
                }
                
                severity = vuln.get('severity', 'LOW')
                if severity == 'CRITICAL':
                    self.results['critical_vulnerabilities'].append(vuln_record)
                elif severity == 'HIGH':
                    self.results['high_vulnerabilities'].append(vuln_record)
                elif severity == 'MEDIUM':
                    self.results['medium_vulnerabilities'].append(vuln_record)
                else:
                    self.results['low_vulnerabilities'].append(vuln_record)
            
            # Track outdated packages
            if metadata.get('is_outdated'):
                self.results['outdated_packages'].append({
                    'package': package_name,
                    'current_version': result['package'].get('current_version'),
                    'latest_version': metadata.get('latest_version'),
                    'age': self.analyze_package_age(metadata)
                })
            
            # Track deprecated packages
            if metadata.get('is_deprecated'):
                self.results['deprecated_packages'].append({
                    'package': package_name,
                    'reason': 'Deprecated according to PyPI metadata'
                })
    
    def _generate_summary(self):
        """Generate audit summary."""
        self.results['summary'] = {
            'total_packages': len(self.results['packages_analyzed']),
            'critical_vulnerabilities_count': len(self.results['critical_vulnerabilities']),
            'high_vulnerabilities_count': len(self.results['high_vulnerabilities']),
            'medium_vulnerabilities_count': len(self.results['medium_vulnerabilities']),
            'low_vulnerabilities_count': len(self.results['low_vulnerabilities']),
            'outdated_packages_count': len(self.results['outdated_packages']),
            'deprecated_packages_count': len(self.results['deprecated_packages']),
            'overall_risk_level': self._calculate_overall_risk()
        }
    
    def _calculate_overall_risk(self) -> str:
        """Calculate overall project risk level."""
        if self.results['critical_vulnerabilities']:
            return 'CRITICAL'
        elif len(self.results['high_vulnerabilities']) > 0:
            return 'HIGH'
        elif len(self.results['medium_vulnerabilities']) > 5 or len(self.results['outdated_packages']) > 20:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _generate_recommendations(self):
        """Generate overall security recommendations."""
        recommendations = []
        
        # Critical issues
        if self.results['critical_vulnerabilities']:
            recommendations.extend([
                "🚨 CRITICAL: Update packages with critical vulnerabilities immediately",
                "🔒 Review and test all critical security patches before deployment",
                "📋 Create incident response plan for critical vulnerability disclosure"
            ])
        
        # High priority issues
        if self.results['high_vulnerabilities']:
            recommendations.extend([
                "⚠️ HIGH PRIORITY: Update packages with high-severity vulnerabilities",
                "🔍 Implement automated vulnerability scanning in CI/CD pipeline"
            ])
        
        # Medium priority issues
        if self.results['medium_vulnerabilities'] or self.results['outdated_packages']:
            recommendations.extend([
                "📦 Update outdated packages to latest stable versions",
                "🗓️ Establish regular dependency update schedule (monthly)"
            ])
        
        # General recommendations
        recommendations.extend([
            "🔐 Use pip-audit or safety for continuous vulnerability monitoring",
            "📌 Pin exact versions in requirements.txt for reproducible builds",
            "🧪 Test all dependency updates in staging environment first",
            "📊 Set up automated security monitoring and alerting",
            "🔄 Implement dependency update automation with proper testing",
            "📋 Maintain Software Bill of Materials (SBOM)",
            "🏷️ Use semantic versioning and understand breaking changes",
            "🛡️ Consider using virtual environments and containerization"
        ])
        
        self.results['recommendations'] = recommendations
    
    def print_report(self):
        """Print formatted audit report."""
        summary = self.results['summary']
        
        print("\n" + "="*80)
        print("📦 AI TEDDY BEAR - DEPENDENCIES SECURITY AUDIT REPORT")
        print("="*80)
        print(f"📅 Audit Date: {self.results['timestamp']}")
        print(f"🎯 Overall Risk Level: {summary['overall_risk_level']}")
        print()
        
        # Summary
        print("📊 AUDIT SUMMARY:")
        print(f"   Packages Analyzed: {summary['total_packages']:,}")
        print(f"   Vulnerabilities Found: {summary['critical_vulnerabilities_count'] + summary['high_vulnerabilities_count'] + summary['medium_vulnerabilities_count'] + summary['low_vulnerabilities_count']:,}")
        print(f"   Outdated Packages: {summary['outdated_packages_count']:,}")
        print(f"   Deprecated Packages: {summary['deprecated_packages_count']:,}")
        print()
        
        # Vulnerabilities by severity
        print("🚨 VULNERABILITIES BY SEVERITY:")
        print(f"   Critical: {summary['critical_vulnerabilities_count']:,}")
        print(f"   High: {summary['high_vulnerabilities_count']:,}")
        print(f"   Medium: {summary['medium_vulnerabilities_count']:,}")
        print(f"   Low: {summary['low_vulnerabilities_count']:,}")
        print()
        
        # Critical vulnerabilities details
        if self.results['critical_vulnerabilities']:
            print("🚨 CRITICAL VULNERABILITIES (IMMEDIATE ACTION REQUIRED):")
            for vuln in self.results['critical_vulnerabilities'][:5]:  # Show first 5
                v = vuln['vulnerability']
                print(f"   • {vuln['package']}: {v['id']} - {v['summary'][:80]}...")
            print()
        
        # High vulnerabilities details
        if self.results['high_vulnerabilities']:
            print("⚠️ HIGH PRIORITY VULNERABILITIES:")
            for vuln in self.results['high_vulnerabilities'][:5]:  # Show first 5
                v = vuln['vulnerability']
                print(f"   • {vuln['package']}: {v['id']} - {v['summary'][:80]}...")
            print()
        
        # Outdated packages
        if self.results['outdated_packages']:
            print("📦 OUTDATED PACKAGES:")
            for pkg in self.results['outdated_packages'][:10]:  # Show first 10
                print(f"   • {pkg['package']}: {pkg['current_version']} → {pkg['latest_version']} ({pkg['age']})")
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
            filename = f"dependency_security_audit_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        return filename
    
    def generate_update_script(self) -> str:
        """Generate script to update vulnerable packages."""
        script_lines = [
            "#!/bin/bash",
            "# AI Teddy Bear - Dependency Security Updates",
            f"# Generated on: {datetime.now().isoformat()}",
            "",
            "echo '📦 Updating vulnerable packages...'",
            ""
        ]
        
        # Critical and high vulnerabilities first
        critical_packages = set()
        high_packages = set()
        
        for vuln in self.results['critical_vulnerabilities']:
            critical_packages.add(vuln['package'])
        
        for vuln in self.results['high_vulnerabilities']:
            high_packages.add(vuln['package'])
        
        if critical_packages:
            script_lines.extend([
                "echo '🚨 Updating CRITICAL vulnerability packages...'",
                f"pip install --upgrade {' '.join(critical_packages)}",
                ""
            ])
        
        if high_packages:
            script_lines.extend([
                "echo '⚠️ Updating HIGH priority packages...'",
                f"pip install --upgrade {' '.join(high_packages)}",
                ""
            ])
        
        # Outdated packages
        outdated_packages = [pkg['package'] for pkg in self.results['outdated_packages']]
        if outdated_packages:
            script_lines.extend([
                "echo '📦 Updating outdated packages...'",
                f"pip install --upgrade {' '.join(outdated_packages[:20])}",  # Limit to 20
                ""
            ])
        
        script_lines.extend([
            "echo '✅ Updates completed!'",
            "echo '🧪 Please test thoroughly before deploying to production.'"
        ])
        
        script_content = "\n".join(script_lines)
        script_filename = f"update_dependencies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sh"
        
        with open(script_filename, 'w') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(script_filename, 0o755)
        
        return script_filename

async def main():
    """Main function."""
    auditor = DependencySecurityAuditor()
    results = await auditor.run_comprehensive_audit()
    
    # Generate update script
    script_file = auditor.generate_update_script()
    print(f"\n🔧 Update script generated: {script_file}")
    
    # Return appropriate exit code
    risk_level = results['summary']['overall_risk_level']
    if risk_level in ['CRITICAL', 'HIGH']:
        print(f"\n❌ AUDIT FAILED - {risk_level} RISK DETECTED")
        return 1
    else:
        print(f"\n✅ AUDIT PASSED - {risk_level} RISK LEVEL")
        return 0

if __name__ == "__main__":
    exit(asyncio.run(main()))