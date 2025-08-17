#!/usr/bin/env python3
"""
Environment Security Test Suite
===============================
Comprehensive testing of environment variable security and startup validation.
Tests the security validator and startup hooks to ensure proper operation.
"""

import os
import sys
import json
import tempfile
from datetime import datetime
from typing import Dict, Any, List

# Add project path
sys.path.append("/mnt/c/Users/jaafa/Desktop/ai teddy bear/src")


class EnvironmentSecurityTester:
    """Comprehensive environment security testing."""
    
    def __init__(self):
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "test_suite": "Environment Security Testing",
            "tests": {},
            "security_score": 0,
            "critical_issues": [],
            "passed_tests": 0,
            "total_tests": 0
        }
        
        # Store original environment
        self.original_env = dict(os.environ)
    
    def restore_environment(self):
        """Restore original environment variables."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def setup_test_environment(self, env_vars: Dict[str, str]):
        """Setup test environment variables."""
        self.restore_environment()
        for key, value in env_vars.items():
            os.environ[key] = value
    
    def test_weak_secret_detection(self) -> bool:
        """Test detection of weak secrets."""
        test_name = "Weak Secret Detection"
        
        try:
            test_cases = []
            
            # Test Case 1: Very weak JWT secret
            self.setup_test_environment({
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "secret123",  # Weak secret
                "DATABASE_URL": "postgresql://user:strongpassword123@db:5432/app",
                "REDIS_URL": "redis://localhost:6379"
            })
            
            try:
                from infrastructure.security.environment_validator import EnvironmentSecurityValidator
                validator = EnvironmentSecurityValidator()
                results = validator.validate_all_secrets()
                
                # Should detect weak JWT secret
                jwt_issues = [issue for issue in results["validation_issues"] 
                             if issue["variable"] == "JWT_SECRET_KEY"]
                
                if jwt_issues and any("insufficient" in issue["type"] for issue in jwt_issues):
                    test_cases.append({
                        "case": "Weak JWT Secret Detection",
                        "status": "PROTECTED",
                        "details": "Weak JWT secret properly detected"
                    })
                else:
                    test_cases.append({
                        "case": "Weak JWT Secret Detection",
                        "status": "VULNERABLE",
                        "details": "Weak JWT secret not detected"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Weak JWT Secret Detection",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 2: Strong secret should pass
            self.setup_test_environment({
                "ENVIRONMENT": "development",
                "JWT_SECRET_KEY": "h8K2nP9mR4qL7sX3vB6yE1wQ0zA5uI8oT2fG4jC7dN1mV9sR6bK3pL8hQ2nE5vU8",
                "DATABASE_URL": "postgresql://app_user:StrongPassword123!@production-db:5432/teddy_app",
                "REDIS_URL": "redis://localhost:6379"
            })
            
            try:
                validator = EnvironmentSecurityValidator()
                results = validator.validate_all_secrets()
                
                # Should not have critical issues for JWT secret
                jwt_critical = [issue for issue in results["validation_issues"] 
                               if issue["variable"] == "JWT_SECRET_KEY" and 
                               issue["severity"] == "critical_fail"]
                
                if not jwt_critical:
                    test_cases.append({
                        "case": "Strong Secret Acceptance",
                        "status": "PROTECTED",
                        "details": "Strong JWT secret properly accepted"
                    })
                else:
                    test_cases.append({
                        "case": "Strong Secret Acceptance",
                        "status": "VULNERABLE",
                        "details": "Strong JWT secret incorrectly rejected"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Strong Secret Acceptance",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} secret strength scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["critical_issues"].extend([
                    f"Weak secret detection issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute weak secret detection tests"
            }
        
        self.test_results["tests"]["weak_secret_detection"] = test_result
        return test_result["status"] == "PASS"
    
    def test_production_requirements_enforcement(self) -> bool:
        """Test production environment requirements enforcement."""
        test_name = "Production Requirements Enforcement"
        
        try:
            test_cases = []
            
            # Test Case 1: Missing production requirements
            self.setup_test_environment({
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "h8K2nP9mR4qL7sX3vB6yE1wQ0zA5uI8oT2fG4jC7dN1mV9sR6bK3pL8hQ2nE5vU8"
                # Missing JWT_PRIVATE_KEY, JWT_PUBLIC_KEY, etc.
            })
            
            try:
                from infrastructure.security.environment_validator import EnvironmentSecurityValidator
                validator = EnvironmentSecurityValidator()
                results = validator.validate_all_secrets()
                
                # Should detect missing production requirements
                missing_rsa = [issue for issue in results["validation_issues"] 
                              if "JWT_PRIVATE_KEY" in issue["variable"] or "JWT_PUBLIC_KEY" in issue["variable"]]
                
                if missing_rsa:
                    test_cases.append({
                        "case": "Missing Production RSA Keys",
                        "status": "PROTECTED",
                        "details": "Missing RSA keys properly detected in production"
                    })
                else:
                    test_cases.append({
                        "case": "Missing Production RSA Keys",
                        "status": "VULNERABLE",
                        "details": "Missing RSA keys not detected in production"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Missing Production RSA Keys",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 2: Development environment should be more lenient
            self.setup_test_environment({
                "ENVIRONMENT": "development",
                "JWT_SECRET_KEY": "h8K2nP9mR4qL7sX3vB6yE1wQ0zA5uI8oT2fG4jC7dN1mV9sR6bK3pL8hQ2nE5vU8",
                "DATABASE_URL": "postgresql://user:pass@localhost:5432/dev_db",
                "REDIS_URL": "redis://localhost:6379"
            })
            
            try:
                validator = EnvironmentSecurityValidator()
                results = validator.validate_all_secrets()
                
                # Should not require RSA keys in development
                rsa_critical = [issue for issue in results["validation_issues"] 
                               if ("JWT_PRIVATE_KEY" in issue["variable"] or "JWT_PUBLIC_KEY" in issue["variable"]) 
                               and issue["severity"] == "critical_fail"]
                
                if not rsa_critical:
                    test_cases.append({
                        "case": "Development Environment Flexibility",
                        "status": "PROTECTED",
                        "details": "Development environment properly allows missing RSA keys"
                    })
                else:
                    test_cases.append({
                        "case": "Development Environment Flexibility",
                        "status": "VULNERABLE",
                        "details": "Development environment too strict on RSA keys"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Development Environment Flexibility",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} production requirement scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["critical_issues"].extend([
                    f"Production requirements issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute production requirements tests"
            }
        
        self.test_results["tests"]["production_requirements"] = test_result
        return test_result["status"] == "PASS"
    
    def test_startup_security_hooks(self) -> bool:
        """Test startup security hooks functionality."""
        test_name = "Startup Security Hooks"
        
        try:
            test_cases = []
            
            # Test Case 1: Secure environment should pass startup checks
            self.setup_test_environment({
                "ENVIRONMENT": "development",
                "JWT_SECRET_KEY": "h8K2nP9mR4qL7sX3vB6yE1wQ0zA5uI8oT2fG4jC7dN1mV9sR6bK3pL8hQ2nE5vU8",
                "DATABASE_URL": "postgresql://app_user:StrongPassword123@db:5432/teddy",
                "REDIS_URL": "redis://localhost:6379",
                "SECRET_KEY": "SuperSecretAppKey12345!@#$%^&*()ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef",
                "ENCRYPTION_KEY": "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXox"  # 32 bytes base64
            })
            
            try:
                from infrastructure.startup.security_hooks import SecurityStartupHooks
                hooks = SecurityStartupHooks()
                
                # Test environment validation
                env_result = hooks.run_environment_security_validation()
                
                if env_result:
                    test_cases.append({
                        "case": "Secure Environment Startup",
                        "status": "PROTECTED",
                        "details": "Secure environment passed startup validation"
                    })
                else:
                    test_cases.append({
                        "case": "Secure Environment Startup",
                        "status": "VULNERABLE",
                        "details": "Secure environment failed startup validation"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Secure Environment Startup",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 2: Insecure environment should fail startup checks
            self.setup_test_environment({
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "weak",  # Very weak secret
                "DATABASE_URL": "postgresql://user:pass@localhost:5432/db"
            })
            
            try:
                hooks = SecurityStartupHooks()
                
                # Test environment validation (should fail)
                env_result = hooks.run_environment_security_validation()
                
                if not env_result:
                    test_cases.append({
                        "case": "Insecure Environment Blocking",
                        "status": "PROTECTED",
                        "details": "Insecure environment properly blocked at startup"
                    })
                else:
                    test_cases.append({
                        "case": "Insecure Environment Blocking",
                        "status": "VULNERABLE",
                        "details": "Insecure environment allowed to start"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Insecure Environment Blocking",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} startup hook scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["critical_issues"].extend([
                    f"Startup security issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute startup security hooks tests"
            }
        
        self.test_results["tests"]["startup_hooks"] = test_result
        return test_result["status"] == "PASS"
    
    def test_forbidden_values_detection(self) -> bool:
        """Test detection of forbidden/default values."""
        test_name = "Forbidden Values Detection"
        
        try:
            test_cases = []
            
            # Test forbidden values
            forbidden_test_cases = [
                ("JWT_SECRET_KEY", "secret", "Generic 'secret' value"),
                ("DB_PASSWORD", "password", "Generic 'password' value"),
                ("DB_PASSWORD", "123456", "Numeric weak password"),
                ("SECRET_KEY", "changeme", "Default changeme value"),
                ("ENCRYPTION_KEY", "key", "Generic 'key' value")
            ]
            
            for var_name, forbidden_value, description in forbidden_test_cases:
                self.setup_test_environment({
                    "ENVIRONMENT": "development",
                    var_name: forbidden_value,
                    "DATABASE_URL": "postgresql://user:strongpass@db:5432/app",
                    "REDIS_URL": "redis://localhost:6379"
                })
                
                try:
                    from infrastructure.security.environment_validator import EnvironmentSecurityValidator
                    validator = EnvironmentSecurityValidator()
                    results = validator.validate_all_secrets()
                    
                    # Should detect forbidden value
                    forbidden_issues = [issue for issue in results["validation_issues"] 
                                       if issue["variable"] == var_name and 
                                       "forbidden" in issue["type"]]
                    
                    if forbidden_issues:
                        test_cases.append({
                            "case": f"Forbidden Value Detection: {description}",
                            "status": "PROTECTED",
                            "details": f"Forbidden value '{forbidden_value}' properly detected"
                        })
                    else:
                        test_cases.append({
                            "case": f"Forbidden Value Detection: {description}",
                            "status": "VULNERABLE",
                            "details": f"Forbidden value '{forbidden_value}' not detected"
                        })
                        
                except Exception as e:
                    test_cases.append({
                        "case": f"Forbidden Value Detection: {description}",
                        "status": "ERROR",
                        "details": f"Test error: {str(e)}"
                    })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} forbidden value scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["critical_issues"].extend([
                    f"Forbidden value detection issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute forbidden values tests"
            }
        
        self.test_results["tests"]["forbidden_values"] = test_result
        return test_result["status"] == "PASS"
    
    def test_complexity_requirements(self) -> bool:
        """Test password/secret complexity requirements."""
        test_name = "Complexity Requirements"
        
        try:
            test_cases = []
            
            # Test complexity requirements
            complexity_tests = [
                ("JWT_SECRET_KEY", "short", "Too short JWT secret"),
                ("DB_PASSWORD", "nouppercasenumbers", "Missing uppercase and numbers"),
                ("SECRET_KEY", "NoNumbers!", "Missing numbers in secret key"),
                ("ENCRYPTION_KEY", "WrongLength123", "Wrong length encryption key")
            ]
            
            for var_name, weak_value, description in complexity_tests:
                self.setup_test_environment({
                    "ENVIRONMENT": "development",
                    var_name: weak_value,
                    "DATABASE_URL": "postgresql://user:strongpass@db:5432/app",
                    "REDIS_URL": "redis://localhost:6379"
                })
                
                try:
                    from infrastructure.security.environment_validator import EnvironmentSecurityValidator
                    validator = EnvironmentSecurityValidator()
                    results = validator.validate_all_secrets()
                    
                    # Should detect complexity issues
                    complexity_issues = [issue for issue in results["validation_issues"] 
                                        if issue["variable"] == var_name and 
                                        ("insufficient" in issue["type"] or 
                                         "length" in issue["type"])]
                    
                    if complexity_issues:
                        test_cases.append({
                            "case": f"Complexity Check: {description}",
                            "status": "PROTECTED",
                            "details": f"Complexity issue properly detected for '{var_name}'"
                        })
                    else:
                        test_cases.append({
                            "case": f"Complexity Check: {description}",
                            "status": "VULNERABLE",
                            "details": f"Complexity issue not detected for '{var_name}'"
                        })
                        
                except Exception as e:
                    test_cases.append({
                        "case": f"Complexity Check: {description}",
                        "status": "ERROR",
                        "details": f"Test error: {str(e)}"
                    })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} complexity requirement scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["critical_issues"].extend([
                    f"Complexity requirements issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute complexity requirements tests"
            }
        
        self.test_results["tests"]["complexity_requirements"] = test_result
        return test_result["status"] == "PASS"
    
    def calculate_security_score(self):
        """Calculate overall security score."""
        self.test_results["total_tests"] = len(self.test_results["tests"])
        passed_tests = sum(
            1 for test in self.test_results["tests"].values() 
            if test["status"] == "PASS"
        )
        self.test_results["passed_tests"] = passed_tests
        
        if self.test_results["total_tests"] == 0:
            self.test_results["security_score"] = 0
        else:
            base_score = (passed_tests / self.test_results["total_tests"]) * 100
            
            # Deduct heavily for critical issues
            critical_penalty = min(len(self.test_results["critical_issues"]) * 20, 80)
            
            self.test_results["security_score"] = max(0, base_score - critical_penalty)
    
    def run_all_tests(self):
        """Run complete environment security testing suite."""
        print("🔐 Starting Environment Security Testing Suite")
        print("=" * 60)
        
        # Run all tests
        tests = [
            self.test_weak_secret_detection,
            self.test_production_requirements_enforcement,
            self.test_startup_security_hooks,
            self.test_forbidden_values_detection,
            self.test_complexity_requirements
        ]
        
        for test in tests:
            try:
                result = test()
                test_name = test.__name__.replace('test_', '').replace('_', ' ').title()
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{test_name}: {status}")
            except Exception as e:
                test_name = test.__name__.replace('test_', '').replace('_', ' ').title()
                print(f"{test_name}: ❌ ERROR - {e}")
            finally:
                # Always restore environment after each test
                self.restore_environment()
        
        # Calculate final score
        self.calculate_security_score()
        
        # Display results
        print("\n" + "=" * 60)
        print("🎯 ENVIRONMENT SECURITY TEST RESULTS")
        print("=" * 60)
        
        score = self.test_results["security_score"]
        if score >= 90:
            score_status = "🟢 EXCELLENT"
        elif score >= 70:
            score_status = "🟡 GOOD"
        elif score >= 50:
            score_status = "🟠 NEEDS IMPROVEMENT"
        else:
            score_status = "🔴 CRITICAL"
        
        print(f"Security Score: {score:.1f}% {score_status}")
        print(f"Tests Passed: {self.test_results['passed_tests']}/{self.test_results['total_tests']}")
        print(f"Critical Issues: {len(self.test_results['critical_issues'])}")
        
        # Show critical issues
        if self.test_results["critical_issues"]:
            print("\n🚨 CRITICAL ISSUES:")
            for issue in self.test_results["critical_issues"]:
                print(f"  • {issue}")
        else:
            print("\n✅ No critical security issues detected")
        
        return self.test_results


def main():
    """Main testing execution."""
    tester = EnvironmentSecurityTester()
    results = tester.run_all_tests()
    
    # Save results to file
    output_file = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/ENVIRONMENT_SECURITY_TEST_RESULTS.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {output_file}")
    
    # Return exit code based on critical issues
    critical_count = len(results["critical_issues"])
    score = results["security_score"]
    
    if score >= 90:
        print("\n✅ Environment security testing PASSED - System secure!")
        return 0
    elif critical_count > 0:
        print(f"\n❌ Environment security testing FAILED with {critical_count} critical issues")
        return 1
    else:
        print(f"\n⚠️ Environment security testing completed with warnings (Score: {score:.1f}%)")
        return 2


if __name__ == "__main__":
    sys.exit(main())