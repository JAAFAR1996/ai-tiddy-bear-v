#!/usr/bin/env python3
"""
Environment Variables Security Validator
========================================
Critical security validation for environment variables and secrets.
Ensures all secrets meet complexity requirements and validates configuration
before application startup. Prevents server startup if security requirements not met.
"""

import os
import re
import sys
import json
import hashlib
import secrets
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class SecurityLevel(Enum):
    """Security level classifications."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationResult(Enum):
    """Validation result types."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    CRITICAL_FAIL = "critical_fail"


@dataclass
class SecretRequirement:
    """Requirements for a secret/environment variable."""
    name: str
    required: bool
    min_length: int
    max_length: Optional[int]
    complexity_patterns: List[str]
    security_level: SecurityLevel
    description: str
    examples: List[str] = None
    forbidden_values: List[str] = None


@dataclass
class ValidationIssue:
    """Validation issue details."""
    variable: str
    issue_type: str
    severity: ValidationResult
    message: str
    recommendation: str


class EnvironmentSecurityValidator:
    """
    Comprehensive environment security validator for production deployment.
    
    Features:
    - Validates all critical environment variables
    - Enforces password complexity requirements
    - Checks for weak/default secrets
    - Validates database connection strings
    - Ensures JWT key security
    - Prevents startup with insecure configuration
    """
    
    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv("ENVIRONMENT", "development")
        self.validation_results = {
            "timestamp": datetime.now().isoformat(),
            "environment": self.environment,
            "validator_version": "1.0.0",
            "validation_issues": [],
            "security_score": 0,
            "is_production_ready": False,
            "critical_failures": 0,
            "warnings": 0
        }
        
        # Define security requirements for all environment variables
        self.secret_requirements = self._define_secret_requirements()
    
    def _define_secret_requirements(self) -> Dict[str, SecretRequirement]:
        """Define security requirements for all environment variables."""
        
        requirements = {}
        
        # JWT Security Requirements
        requirements["JWT_SECRET_KEY"] = SecretRequirement(
            name="JWT_SECRET_KEY",
            required=True,
            min_length=64,
            max_length=None,
            complexity_patterns=[
                r"[A-Z]",      # Uppercase letter
                r"[a-z]",      # Lowercase letter  
                r"[0-9]",      # Number
                r"[!@#$%^&*()_+\-=\[\]{}|;':\",./<>?]"  # Special character
            ],
            security_level=SecurityLevel.CRITICAL,
            description="JWT signing secret key",
            forbidden_values=[
                "secret", "password", "jwt_secret", "key", "test", "dev", "development",
                "production", "admin", "user", "default", "changeme", "12345", "abc123"
            ]
        )
        
        requirements["JWT_PRIVATE_KEY"] = SecretRequirement(
            name="JWT_PRIVATE_KEY",
            required=self.environment == "production",
            min_length=1000,  # RSA private key should be substantial
            max_length=None,
            complexity_patterns=[
                r"-----BEGIN PRIVATE KEY-----",
                r"-----END PRIVATE KEY-----",
                r"[A-Za-z0-9+/=]{100,}"  # Base64 content
            ],
            security_level=SecurityLevel.CRITICAL,
            description="RSA private key for JWT signing"
        )
        
        requirements["JWT_PUBLIC_KEY"] = SecretRequirement(
            name="JWT_PUBLIC_KEY", 
            required=self.environment == "production",
            min_length=200,
            max_length=None,
            complexity_patterns=[
                r"-----BEGIN PUBLIC KEY-----",
                r"-----END PUBLIC KEY-----"
            ],
            security_level=SecurityLevel.CRITICAL,
            description="RSA public key for JWT verification"
        )
        
        # Database Security Requirements
        requirements["DATABASE_URL"] = SecretRequirement(
            name="DATABASE_URL",
            required=True,
            min_length=20,
            max_length=None,
            complexity_patterns=[
                r"postgresql://",
                r"[a-zA-Z0-9_]{8,}",  # Username should be 8+ chars
                r"[:@]"  # Should contain auth separator
            ],
            security_level=SecurityLevel.CRITICAL,
            description="PostgreSQL database connection URL",
            forbidden_values=[
                "postgres://user:password@localhost:5432/db",
                "postgresql://user:pass@localhost/db"
            ]
        )
        
        requirements["DB_PASSWORD"] = SecretRequirement(
            name="DB_PASSWORD",
            required=True,
            min_length=16,
            max_length=None,
            complexity_patterns=[
                r"[A-Z]",
                r"[a-z]", 
                r"[0-9]",
                r"[!@#$%^&*()_+\-=\[\]{}|;':\",./<>?]"
            ],
            security_level=SecurityLevel.CRITICAL,
            description="Database password",
            forbidden_values=[
                "password", "123456", "admin", "root", "postgres", "db_password"
            ]
        )
        
        # Redis Security Requirements  
        requirements["REDIS_URL"] = SecretRequirement(
            name="REDIS_URL",
            required=True,
            min_length=15,
            max_length=None,
            complexity_patterns=[
                r"redis://",
                r"[:\d]+$"  # Should end with port number
            ],
            security_level=SecurityLevel.HIGH,
            description="Redis connection URL"
        )
        
        requirements["REDIS_PASSWORD"] = SecretRequirement(
            name="REDIS_PASSWORD",
            required=self.environment == "production", 
            min_length=32,
            max_length=None,
            complexity_patterns=[
                r"[A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;':\",./<>?]{32,}"
            ],
            security_level=SecurityLevel.HIGH,
            description="Redis authentication password"
        )
        
        # External API Keys
        requirements["OPENAI_API_KEY"] = SecretRequirement(
            name="OPENAI_API_KEY",
            required=True,
            min_length=40,
            max_length=None,
            complexity_patterns=[
                r"sk-[A-Za-z0-9]{48,}"
            ],
            security_level=SecurityLevel.HIGH,
            description="OpenAI API key"
        )
        
        requirements["STRIPE_SECRET_KEY"] = SecretRequirement(
            name="STRIPE_SECRET_KEY",
            required=self.environment == "production",
            min_length=30,
            max_length=None,
            complexity_patterns=[
                r"sk_(live|test)_[A-Za-z0-9]{24,}"
            ],
            security_level=SecurityLevel.HIGH,
            description="Stripe secret API key"
        )
        
        # Email/SMTP Security
        requirements["SMTP_PASSWORD"] = SecretRequirement(
            name="SMTP_PASSWORD",
            required=True,
            min_length=12,
            max_length=None,
            complexity_patterns=[
                r"[A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;':\",./<>?]{12,}"
            ],
            security_level=SecurityLevel.MEDIUM,
            description="SMTP authentication password"
        )
        
        # Application Security
        requirements["SECRET_KEY"] = SecretRequirement(
            name="SECRET_KEY",
            required=True,
            min_length=50,
            max_length=None,
            complexity_patterns=[
                r"[A-Z]",
                r"[a-z]",
                r"[0-9]",
                r"[!@#$%^&*()_+\-=\[\]{}|;':\",./<>?]"
            ],
            security_level=SecurityLevel.CRITICAL,
            description="Application secret key",
            forbidden_values=[
                "secret_key", "app_secret", "django_secret", "flask_secret"
            ]
        )
        
        requirements["ENCRYPTION_KEY"] = SecretRequirement(
            name="ENCRYPTION_KEY",
            required=True,
            min_length=32,
            max_length=32,  # Must be exactly 32 bytes for AES-256
            complexity_patterns=[
                r"[A-Za-z0-9+/=]{32}"  # Base64 encoded 32 bytes
            ],
            security_level=SecurityLevel.CRITICAL,
            description="AES-256 encryption key (32 bytes base64)"
        )
        
        # Monitoring & Security Services
        requirements["SENTRY_DSN"] = SecretRequirement(
            name="SENTRY_DSN",
            required=self.environment == "production",
            min_length=50,
            max_length=None,
            complexity_patterns=[
                r"https://[a-f0-9]{32}@[a-f0-9]+\.ingest\.sentry\.io/\d+"
            ],
            security_level=SecurityLevel.MEDIUM,
            description="Sentry error tracking DSN"
        )
        
        return requirements
    
    def validate_secret_complexity(self, name: str, value: str, requirement: SecretRequirement) -> List[ValidationIssue]:
        """Validate a single secret against its requirements."""
        issues = []
        
        # Check if required
        if requirement.required and not value:
            issues.append(ValidationIssue(
                variable=name,
                issue_type="missing_required",
                severity=ValidationResult.CRITICAL_FAIL,
                message=f"Required environment variable {name} is missing",
                recommendation=f"Set {name} with a secure value meeting complexity requirements"
            ))
            return issues
        
        if not value:  # Not required and empty
            return issues
        
        # Check minimum length
        if len(value) < requirement.min_length:
            issues.append(ValidationIssue(
                variable=name,
                issue_type="insufficient_length",
                severity=ValidationResult.FAIL,
                message=f"{name} is too short (minimum {requirement.min_length} characters)",
                recommendation=f"Increase {name} length to at least {requirement.min_length} characters"
            ))
        
        # Check maximum length
        if requirement.max_length and len(value) > requirement.max_length:
            issues.append(ValidationIssue(
                variable=name,
                issue_type="excessive_length",
                severity=ValidationResult.FAIL,
                message=f"{name} is too long (maximum {requirement.max_length} characters)",
                recommendation=f"Reduce {name} length to at most {requirement.max_length} characters"
            ))
        
        # Check complexity patterns
        missing_patterns = []
        for pattern in requirement.complexity_patterns:
            if not re.search(pattern, value):
                missing_patterns.append(pattern)
        
        if missing_patterns:
            issues.append(ValidationIssue(
                variable=name,
                issue_type="insufficient_complexity",
                severity=ValidationResult.FAIL,
                message=f"{name} does not meet complexity requirements",
                recommendation=f"Ensure {name} matches required patterns: {missing_patterns}"
            ))
        
        # Check forbidden values
        if requirement.forbidden_values:
            if value.lower() in [fv.lower() for fv in requirement.forbidden_values]:
                issues.append(ValidationIssue(
                    variable=name,
                    issue_type="forbidden_value",
                    severity=ValidationResult.CRITICAL_FAIL,
                    message=f"{name} uses a forbidden/weak value",
                    recommendation=f"Replace {name} with a strong, unique value"
                ))
        
        # Check for common weak patterns
        weak_patterns = [
            (r"^(test|dev|demo|example).*", "Contains weak prefix"),
            (r".*\b(123|abc|password|secret)\b.*", "Contains common weak words"),
            (r"^(.)\1{4,}", "Contains repeated characters"),
            (r"^(admin|root|user|guest)$", "Uses default account name")
        ]
        
        for pattern, description in weak_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                issues.append(ValidationIssue(
                    variable=name,
                    issue_type="weak_pattern",
                    severity=ValidationResult.WARN,
                    message=f"{name} {description}",
                    recommendation=f"Use a stronger value for {name}"
                ))
        
        return issues
    
    def validate_database_connection(self, db_url: str) -> List[ValidationIssue]:
        """Validate database connection string security."""
        issues = []
        
        if not db_url:
            return issues
        
        # Check for insecure database configurations
        insecure_patterns = [
            (r"://.*:.*@localhost", "Database on localhost may not be production-ready"),
            (r"://.*:.*@127\.0\.0\.1", "Database on loopback may not be production-ready"),
            (r"sslmode=disable", "SSL disabled for database connection"),
            (r"://postgres:postgres@", "Using default postgres credentials"),
            (r"://root:", "Using root database user"),
            (r"://.{1,3}:.{1,3}@", "Very short username/password combination")
        ]
        
        for pattern, message in insecure_patterns:
            if re.search(pattern, db_url, re.IGNORECASE):
                severity = ValidationResult.CRITICAL_FAIL if "ssl" in message.lower() or "default" in message.lower() else ValidationResult.WARN
                issues.append(ValidationIssue(
                    variable="DATABASE_URL",
                    issue_type="insecure_config",
                    severity=severity,
                    message=message,
                    recommendation="Use secure database configuration with strong credentials and SSL"
                ))
        
        return issues
    
    def validate_jwt_keys(self) -> List[ValidationIssue]:
        """Validate JWT key configuration."""
        issues = []
        
        private_key = os.getenv("JWT_PRIVATE_KEY", "")
        public_key = os.getenv("JWT_PUBLIC_KEY", "")
        algorithm = os.getenv("JWT_ALGORITHM", "RS256")
        
        if self.environment == "production":
            # Production requires RSA keys
            if algorithm != "RS256":
                issues.append(ValidationIssue(
                    variable="JWT_ALGORITHM",
                    issue_type="insecure_algorithm",
                    severity=ValidationResult.CRITICAL_FAIL,
                    message="Production environment must use RS256 algorithm",
                    recommendation="Set JWT_ALGORITHM=RS256 for production"
                ))
            
            if not private_key or not public_key:
                issues.append(ValidationIssue(
                    variable="JWT_KEYS",
                    issue_type="missing_rsa_keys",
                    severity=ValidationResult.CRITICAL_FAIL,
                    message="Production requires both JWT_PRIVATE_KEY and JWT_PUBLIC_KEY",
                    recommendation="Generate RSA key pair for JWT signing in production"
                ))
            
            # Validate RSA key format
            if private_key and not re.search(r"-----BEGIN PRIVATE KEY-----.*-----END PRIVATE KEY-----", private_key, re.DOTALL):
                issues.append(ValidationIssue(
                    variable="JWT_PRIVATE_KEY",
                    issue_type="invalid_key_format",
                    severity=ValidationResult.CRITICAL_FAIL,
                    message="JWT_PRIVATE_KEY is not in valid PEM format",
                    recommendation="Ensure JWT_PRIVATE_KEY is a valid RSA private key in PEM format"
                ))
            
            if public_key and not re.search(r"-----BEGIN PUBLIC KEY-----.*-----END PUBLIC KEY-----", public_key, re.DOTALL):
                issues.append(ValidationIssue(
                    variable="JWT_PUBLIC_KEY",
                    issue_type="invalid_key_format",
                    severity=ValidationResult.CRITICAL_FAIL,
                    message="JWT_PUBLIC_KEY is not in valid PEM format",
                    recommendation="Ensure JWT_PUBLIC_KEY is a valid RSA public key in PEM format"
                ))
        
        return issues
    
    def check_environment_leaks(self) -> List[ValidationIssue]:
        """Check for potential environment variable leaks."""
        issues = []
        
        # Check for environment variables that might leak in logs/errors
        dangerous_env_vars = []
        for key, value in os.environ.items():
            if any(keyword in key.upper() for keyword in ["SECRET", "KEY", "PASSWORD", "TOKEN", "API"]):
                if len(value) < 8:  # Very short secret
                    issues.append(ValidationIssue(
                        variable=key,
                        issue_type="short_secret",
                        severity=ValidationResult.WARN,
                        message=f"Secret {key} is very short and may be weak",
                        recommendation=f"Use a longer, more complex value for {key}"
                    ))
                
                # Check if secret appears to be encoded
                if re.match(r"^[A-Za-z0-9+/=]+$", value) and len(value) % 4 == 0:
                    # Looks like base64
                    continue
                elif re.match(r"^[a-f0-9]+$", value):
                    # Looks like hex
                    continue
                else:
                    # Plain text secret - warn if it contains common words
                    common_words = ["password", "secret", "key", "admin", "user", "test", "dev"]
                    if any(word in value.lower() for word in common_words):
                        issues.append(ValidationIssue(
                            variable=key,
                            issue_type="plaintext_secret",
                            severity=ValidationResult.WARN,
                            message=f"Secret {key} appears to contain common words",
                            recommendation=f"Use a randomly generated value for {key}"
                        ))
        
        return issues
    
    def validate_all_secrets(self) -> Dict[str, Any]:
        """Validate all environment secrets and configuration."""
        all_issues = []
        
        # Validate each defined secret requirement
        for name, requirement in self.secret_requirements.items():
            value = os.getenv(name, "")
            issues = self.validate_secret_complexity(name, value, requirement)
            all_issues.extend(issues)
        
        # Additional specific validations
        db_url = os.getenv("DATABASE_URL", "")
        all_issues.extend(self.validate_database_connection(db_url))
        all_issues.extend(self.validate_jwt_keys())
        all_issues.extend(self.check_environment_leaks())
        
        # Categorize issues
        critical_failures = [i for i in all_issues if i.severity == ValidationResult.CRITICAL_FAIL]
        failures = [i for i in all_issues if i.severity == ValidationResult.FAIL]
        warnings = [i for i in all_issues if i.severity == ValidationResult.WARN]
        
        # Calculate security score
        total_requirements = len(self.secret_requirements)
        critical_weight = 50
        failure_weight = 25
        warning_weight = 5
        
        penalty = (len(critical_failures) * critical_weight + 
                  len(failures) * failure_weight + 
                  len(warnings) * warning_weight)
        
        security_score = max(0, 100 - penalty)
        
        # Determine if production ready
        is_production_ready = (
            len(critical_failures) == 0 and 
            len(failures) == 0 and
            security_score >= 85
        )
        
        # Update validation results
        self.validation_results.update({
            "validation_issues": [
                {
                    "variable": issue.variable,
                    "type": issue.issue_type, 
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "recommendation": issue.recommendation
                }
                for issue in all_issues
            ],
            "security_score": security_score,
            "is_production_ready": is_production_ready,
            "critical_failures": len(critical_failures),
            "failures": len(failures),
            "warnings": len(warnings),
            "total_issues": len(all_issues)
        })
        
        return self.validation_results
    
    def generate_security_report(self) -> str:
        """Generate a detailed security validation report."""
        results = self.validation_results
        
        report = f"""
🔐 ENVIRONMENT SECURITY VALIDATION REPORT
{'=' * 60}
Timestamp: {results['timestamp']}
Environment: {results['environment']}
Validator Version: {results['validator_version']}

SECURITY SCORE: {results['security_score']}/100
Production Ready: {'✅ YES' if results['is_production_ready'] else '❌ NO'}

ISSUE SUMMARY:
- Critical Failures: {results['critical_failures']}
- Failures: {results['failures']} 
- Warnings: {results['warnings']}
- Total Issues: {results['total_issues']}

"""
        
        if results['validation_issues']:
            report += "\nISSUES DETECTED:\n"
            report += "-" * 40 + "\n"
            
            for issue in results['validation_issues']:
                severity_icon = {
                    'critical_fail': '💥',
                    'fail': '❌', 
                    'warn': '⚠️',
                    'pass': '✅'
                }.get(issue['severity'], '❓')
                
                report += f"{severity_icon} {issue['variable']}: {issue['message']}\n"
                report += f"   → {issue['recommendation']}\n\n"
        else:
            report += "\n✅ NO SECURITY ISSUES DETECTED\n"
        
        if not results['is_production_ready']:
            report += f"""
🚫 PRODUCTION DEPLOYMENT BLOCKED
{'=' * 40}
This configuration is NOT suitable for production deployment.
Critical security issues must be resolved before proceeding.

REQUIRED ACTIONS:
1. Fix all critical failures
2. Resolve security failures  
3. Achieve security score ≥ 85%
4. Re-run validation until production ready

"""
        else:
            report += f"""
🎉 PRODUCTION DEPLOYMENT APPROVED
{'=' * 40}
Environment configuration meets security requirements.
System is ready for production deployment.

"""
        
        return report
    
    def startup_security_check(self) -> bool:
        """
        Perform startup security check.
        Returns True if safe to proceed, False if startup should be blocked.
        """
        print("🔐 Performing environment security validation...")
        
        results = self.validate_all_secrets()
        report = self.generate_security_report()
        
        print(report)
        
        # Save detailed report
        report_file = f"environment_security_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📄 Detailed report saved to: {report_file}")
        
        if not results['is_production_ready']:
            print("\n💥 STARTUP BLOCKED: Critical security issues detected!")
            print("Server will NOT start until security requirements are met.")
            return False
        
        print("\n✅ Security validation passed - proceeding with startup")
        return True


def validate_environment_on_startup():
    """Entry point for startup environment validation."""
    validator = EnvironmentSecurityValidator()
    
    # Perform validation
    is_safe = validator.startup_security_check()
    
    if not is_safe:
        print("\n🚫 TERMINATING: Security validation failed")
        sys.exit(1)
    
    return validator


# Global validator instance
environment_validator = None


def get_environment_validator() -> EnvironmentSecurityValidator:
    """Get the global environment validator instance."""
    global environment_validator
    if environment_validator is None:
        environment_validator = EnvironmentSecurityValidator()
    return environment_validator


if __name__ == "__main__":
    # Run standalone validation
    validate_environment_on_startup()
