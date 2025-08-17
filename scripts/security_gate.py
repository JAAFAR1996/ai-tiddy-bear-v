#!/usr/bin/env python3
"""
Security Gate for AI Teddy Bear CI/CD Pipeline
Analyzes security scan results and makes deployment decisions
"""

import os
import sys
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SecurityIssue:
    """Security issue found in scans"""
    tool: str
    severity: str
    issue_type: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    cve_id: Optional[str] = None
    confidence: Optional[str] = None

@dataclass
class SecurityGateResult:
    """Result of security gate evaluation"""
    passed: bool
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    child_safety_issues: int
    coppa_violations: int
    block_deployment: bool
    message: str
    recommendations: List[str]

class SecurityGate:
    """
    Security gate for AI Teddy Bear deployment pipeline
    Analyzes security scan results and determines if deployment should proceed
    """
    
    def __init__(self):
        self.issues: List[SecurityIssue] = []
        
        # Security thresholds for deployment blocking
        self.thresholds = {
            "critical": 0,      # No critical issues allowed
            "high": 2,          # Max 2 high severity issues
            "medium": 10,       # Max 10 medium severity issues
            "child_safety": 0,  # No child safety issues allowed
            "coppa": 0          # No COPPA violations allowed
        }
        
        # Child safety related patterns
        self.child_safety_patterns = [
            "child",
            "kid", 
            "minor",
            "parental",
            "coppa",
            "privacy",
            "consent",
            "age verification",
            "content filter"
        ]
        
        # COPPA related patterns
        self.coppa_patterns = [
            "coppa",
            "children's online privacy",
            "parental consent",
            "child data",
            "under 13",
            "minor data"
        ]
        
        # Critical vulnerability patterns
        self.critical_patterns = [
            "sql injection",
            "remote code execution",
            "authentication bypass",
            "privilege escalation",
            "data exposure",
            "password storage",
            "encryption",
            "hardcoded secret",
            "hardcoded password"
        ]
    
    def analyze_security_reports(self, bandit_report: str, safety_report: str, semgrep_report: str) -> SecurityGateResult:
        """Analyze all security reports and make deployment decision"""
        logger.info("Analyzing security reports...")
        
        # Parse reports
        self._parse_bandit_report(bandit_report)
        self._parse_safety_report(safety_report)
        self._parse_semgrep_report(semgrep_report)
        
        # Categorize issues
        critical_issues = [issue for issue in self.issues if issue.severity.lower() == "critical"]
        high_issues = [issue for issue in self.issues if issue.severity.lower() == "high"]
        medium_issues = [issue for issue in self.issues if issue.severity.lower() == "medium"]
        low_issues = [issue for issue in self.issues if issue.severity.lower() == "low"]
        
        # Check for child safety and COPPA issues
        child_safety_issues = self._identify_child_safety_issues()
        coppa_violations = self._identify_coppa_violations()
        
        # Make deployment decision
        block_deployment, message, recommendations = self._evaluate_deployment_decision(
            len(critical_issues), len(high_issues), len(medium_issues),
            len(child_safety_issues), len(coppa_violations)
        )
        
        # Create result
        result = SecurityGateResult(
            passed=not block_deployment,
            total_issues=len(self.issues),
            critical_issues=len(critical_issues),
            high_issues=len(high_issues),
            medium_issues=len(medium_issues),
            low_issues=len(low_issues),
            child_safety_issues=len(child_safety_issues),
            coppa_violations=len(coppa_violations),
            block_deployment=block_deployment,
            message=message,
            recommendations=recommendations
        )
        
        # Generate detailed report
        self._generate_security_gate_report(result)
        
        return result
    
    def _parse_bandit_report(self, report_file: str) -> None:
        """Parse Bandit security scan report"""
        if not Path(report_file).exists():
            logger.warning(f"Bandit report not found: {report_file}")
            return
        
        try:
            with open(report_file, 'r') as f:
                data = json.load(f)
            
            for result in data.get('results', []):
                severity = result.get('issue_severity', 'medium').lower()
                confidence = result.get('issue_confidence', 'medium').lower()
                
                # Adjust severity based on confidence
                if confidence == 'low' and severity == 'high':
                    severity = 'medium'
                elif confidence == 'high' and severity == 'medium':
                    # Keep as medium but note high confidence
                    pass
                
                issue = SecurityIssue(
                    tool="bandit",
                    severity=severity,
                    issue_type=result.get('test_name', 'unknown'),
                    description=result.get('issue_text', ''),
                    file_path=result.get('filename'),
                    line_number=result.get('line_number'),
                    confidence=confidence
                )
                
                self.issues.append(issue)
                
            logger.info(f"Parsed {len(data.get('results', []))} issues from Bandit report")
            
        except Exception as e:
            logger.error(f"Failed to parse Bandit report: {str(e)}")
    
    def _parse_safety_report(self, report_file: str) -> None:
        """Parse Safety vulnerability report"""
        if not Path(report_file).exists():
            logger.warning(f"Safety report not found: {report_file}")
            return
        
        try:
            with open(report_file, 'r') as f:
                # Safety report is typically JSON with vulnerability data
                data = json.load(f)
            
            vulnerabilities = data.get('vulnerabilities', [])
            for vuln in vulnerabilities:
                # Determine severity based on CVE data
                severity = self._determine_cve_severity(vuln)
                
                issue = SecurityIssue(
                    tool="safety",
                    severity=severity,
                    issue_type="dependency_vulnerability",
                    description=f"Vulnerable dependency: {vuln.get('package_name', 'unknown')} - {vuln.get('advisory', '')}",
                    cve_id=vuln.get('id', ''),
                    confidence="high"
                )
                
                self.issues.append(issue)
            
            logger.info(f"Parsed {len(vulnerabilities)} vulnerabilities from Safety report")
            
        except Exception as e:
            logger.error(f"Failed to parse Safety report: {str(e)}")
    
    def _parse_semgrep_report(self, report_file: str) -> None:
        """Parse Semgrep SAST scan report"""
        if not Path(report_file).exists():
            logger.warning(f"Semgrep report not found: {report_file}")
            return
        
        try:
            with open(report_file, 'r') as f:
                data = json.load(f)
            
            results = data.get('results', [])
            for result in results:
                # Semgrep severity mapping
                severity_map = {
                    'ERROR': 'high',
                    'WARNING': 'medium', 
                    'INFO': 'low'
                }
                
                severity = severity_map.get(result.get('extra', {}).get('severity', 'INFO'), 'medium')
                
                issue = SecurityIssue(
                    tool="semgrep",
                    severity=severity,
                    issue_type=result.get('check_id', 'unknown'),
                    description=result.get('extra', {}).get('message', ''),
                    file_path=result.get('path'),
                    line_number=result.get('start', {}).get('line'),
                    confidence="high"
                )
                
                self.issues.append(issue)
            
            logger.info(f"Parsed {len(results)} issues from Semgrep report")
            
        except Exception as e:
            logger.error(f"Failed to parse Semgrep report: {str(e)}")
    
    def _determine_cve_severity(self, vulnerability: Dict[str, Any]) -> str:
        """Determine CVE severity based on vulnerability data"""
        # Check for CVSS score if available
        cvss_score = vulnerability.get('cvss_score')
        if cvss_score:
            try:
                score = float(cvss_score)
                if score >= 9.0:
                    return "critical"
                elif score >= 7.0:
                    return "high"
                elif score >= 4.0:
                    return "medium"
                else:
                    return "low"
            except ValueError:
                pass
        
        # Check severity from advisory
        advisory = vulnerability.get('advisory', '').lower()
        if any(word in advisory for word in ['critical', 'severe', 'remote code execution']):
            return "critical"
        elif any(word in advisory for word in ['high', 'important', 'privilege escalation']):
            return "high"
        elif any(word in advisory for word in ['medium', 'moderate']):
            return "medium"
        else:
            return "low"
    
    def _identify_child_safety_issues(self) -> List[SecurityIssue]:
        """Identify issues related to child safety"""
        child_safety_issues = []
        
        for issue in self.issues:
            description_lower = issue.description.lower()
            file_path_lower = (issue.file_path or "").lower()
            issue_type_lower = issue.issue_type.lower()
            
            # Check if issue is related to child safety
            if any(pattern in description_lower or pattern in file_path_lower or pattern in issue_type_lower 
                   for pattern in self.child_safety_patterns):
                child_safety_issues.append(issue)
                continue
            
            # Check for critical patterns that affect child safety
            if any(pattern in description_lower for pattern in self.critical_patterns):
                # Critical security issues are also child safety issues
                child_safety_issues.append(issue)
        
        return child_safety_issues
    
    def _identify_coppa_violations(self) -> List[SecurityIssue]:
        """Identify COPPA compliance violations"""
        coppa_violations = []
        
        for issue in self.issues:
            description_lower = issue.description.lower()
            file_path_lower = (issue.file_path or "").lower()
            issue_type_lower = issue.issue_type.lower()
            
            # Check if issue is related to COPPA compliance
            if any(pattern in description_lower or pattern in file_path_lower or pattern in issue_type_lower 
                   for pattern in self.coppa_patterns):
                coppa_violations.append(issue)
                continue
            
            # Data handling issues are potential COPPA violations
            data_patterns = [
                "data exposure",
                "information disclosure",
                "privacy",
                "personal data",
                "user data",
                "logging sensitive",
                "hardcoded secret"
            ]
            
            if any(pattern in description_lower for pattern in data_patterns):
                coppa_violations.append(issue)
        
        return coppa_violations
    
    def _evaluate_deployment_decision(self, critical: int, high: int, medium: int, 
                                    child_safety: int, coppa: int) -> Tuple[bool, str, List[str]]:
        """Evaluate whether deployment should be blocked"""
        block_reasons = []
        recommendations = []
        
        # Check critical issues
        if critical > self.thresholds["critical"]:
            block_reasons.append(f"{critical} critical security issues found (limit: {self.thresholds['critical']})")
            recommendations.append("Fix all critical security vulnerabilities before deployment")
        
        # Check high severity issues
        if high > self.thresholds["high"]:
            block_reasons.append(f"{high} high severity issues found (limit: {self.thresholds['high']})")
            recommendations.append(f"Reduce high severity issues to {self.thresholds['high']} or fewer")
        
        # Check medium severity issues
        if medium > self.thresholds["medium"]:
            block_reasons.append(f"{medium} medium severity issues found (limit: {self.thresholds['medium']})")
            recommendations.append(f"Reduce medium severity issues to {self.thresholds['medium']} or fewer")
        
        # Check child safety issues (ZERO TOLERANCE)
        if child_safety > self.thresholds["child_safety"]:
            block_reasons.append(f"{child_safety} child safety issues found (limit: {self.thresholds['child_safety']})")
            recommendations.append("Fix ALL child safety related security issues - this is critical for child protection")
        
        # Check COPPA violations (ZERO TOLERANCE)
        if coppa > self.thresholds["coppa"]:
            block_reasons.append(f"{coppa} COPPA compliance violations found (limit: {self.thresholds['coppa']})")
            recommendations.append("Fix ALL COPPA compliance violations - this is required by law")
        
        # Determine if deployment should be blocked
        block_deployment = len(block_reasons) > 0
        
        if block_deployment:
            message = f"🚫 DEPLOYMENT BLOCKED: {'; '.join(block_reasons)}"
            recommendations.extend([
                "Review security scan reports for detailed information",
                "Address security issues in order of severity: Critical → High → Medium → Low",
                "Run security scans again after fixes",
                "Ensure all child safety and COPPA requirements are met"
            ])
        else:
            message = "✅ SECURITY GATE PASSED: Deployment approved"
            if high > 0 or medium > 0:
                recommendations.append("Consider addressing remaining security issues in future releases")
        
        return block_deployment, message, recommendations
    
    def _generate_security_gate_report(self, result: SecurityGateResult) -> None:
        """Generate detailed security gate report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "gate_result": {
                "passed": result.passed,
                "block_deployment": result.block_deployment,
                "message": result.message
            },
            "issue_summary": {
                "total_issues": result.total_issues,
                "critical_issues": result.critical_issues,
                "high_issues": result.high_issues,
                "medium_issues": result.medium_issues,
                "low_issues": result.low_issues,
                "child_safety_issues": result.child_safety_issues,
                "coppa_violations": result.coppa_violations
            },
            "thresholds": self.thresholds,
            "recommendations": result.recommendations,
            "detailed_issues": [
                {
                    "tool": issue.tool,
                    "severity": issue.severity,
                    "issue_type": issue.issue_type,
                    "description": issue.description,
                    "file_path": issue.file_path,
                    "line_number": issue.line_number,
                    "cve_id": issue.cve_id,
                    "confidence": issue.confidence
                }
                for issue in self.issues
            ]
        }
        
        # Save report
        report_file = Path("security_gate_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*70}")
        print("SECURITY GATE EVALUATION")
        print(f"{'='*70}")
        print(f"Result: {result.message}")
        print(f"\nIssue Summary:")
        print(f"  Total Issues: {result.total_issues}")
        print(f"  Critical: {result.critical_issues} (limit: {self.thresholds['critical']})")
        print(f"  High: {result.high_issues} (limit: {self.thresholds['high']})")
        print(f"  Medium: {result.medium_issues} (limit: {self.thresholds['medium']})")
        print(f"  Low: {result.low_issues}")
        print(f"  Child Safety Issues: {result.child_safety_issues} (limit: {self.thresholds['child_safety']})")
        print(f"  COPPA Violations: {result.coppa_violations} (limit: {self.thresholds['coppa']})")
        
        if result.recommendations:
            print(f"\nRecommendations:")
            for i, rec in enumerate(result.recommendations, 1):
                print(f"  {i}. {rec}")
        
        if result.block_deployment:
            print(f"\n{'='*30}")
            print("CRITICAL ISSUES TO FIX:")
            print(f"{'='*30}")
            
            # Show critical and child safety issues
            critical_and_safety = [
                issue for issue in self.issues 
                if issue.severity.lower() == "critical" or 
                   any(pattern in issue.description.lower() for pattern in self.child_safety_patterns + self.coppa_patterns)
            ]
            
            for issue in critical_and_safety:
                print(f"🚨 [{issue.tool.upper()}] {issue.severity.upper()}: {issue.description}")
                if issue.file_path:
                    print(f"   File: {issue.file_path}" + (f":{issue.line_number}" if issue.line_number else ""))
        
        print(f"\nDetailed report saved to: {report_file.absolute()}")

def main():
    """Main function for security gate"""
    parser = argparse.ArgumentParser(description='Security Gate for AI Teddy Bear Deployment')
    parser.add_argument('bandit_report', help='Path to Bandit JSON report')
    parser.add_argument('safety_report', help='Path to Safety JSON report')
    parser.add_argument('semgrep_report', help='Path to Semgrep JSON report')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run security gate
    gate = SecurityGate()
    result = gate.analyze_security_reports(args.bandit_report, args.safety_report, args.semgrep_report)
    
    # Exit with appropriate code
    sys.exit(0 if result.passed else 1)

if __name__ == "__main__":
    main()