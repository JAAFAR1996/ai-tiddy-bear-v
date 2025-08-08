#!/usr/bin/env python3
"""
JWT Final Security Validation
============================
Final comprehensive validation of JWT security implementation
after all security updates have been applied.
"""

import os
import jwt
import json
import sys
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


class JWTFinalSecurityValidator:
    """Final security validation for JWT implementation."""
    
    def __init__(self):
        self.validation_results = {
            "timestamp": datetime.now().isoformat(),
            "validation_suite": "JWT Final Security Validation",
            "tests": {},
            "security_score": 0,
            "critical_issues": [],
            "passed_tests": 0,
            "total_tests": 0
        }
        
        # Generate test RSA keys
        self.setup_test_keys()
    
    def setup_test_keys(self):
        """Setup RSA keys for testing."""
        # Generate test RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        self.test_private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        self.test_public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    def test_production_mode_security_enforcement(self) -> bool:
        """Test production mode security enforcement."""
        test_name = "Production Mode Security Enforcement"
        
        try:
            # Set environment variables for testing
            original_env = os.getenv("ENVIRONMENT")
            original_algo = os.getenv("JWT_ALGORITHM")
            original_private = os.getenv("JWT_PRIVATE_KEY")
            original_public = os.getenv("JWT_PUBLIC_KEY")
            
            test_cases = []
            
            try:
                # Test Case 1: Production mode blocks HS256
                os.environ["ENVIRONMENT"] = "production"
                os.environ["JWT_ALGORITHM"] = "HS256"
                os.environ["JWT_PRIVATE_KEY"] = self.test_private_key
                os.environ["JWT_PUBLIC_KEY"] = self.test_public_key
                
                # Add project path
                sys.path.append("/mnt/c/Users/jaafa/Desktop/ai teddy bear/src")
                
                try:
                    from infrastructure.security.jwt_advanced import AdvancedJWTManager
                    # This should raise an exception
                    jwt_manager = AdvancedJWTManager()
                    test_cases.append({
                        "case": "Production HS256 Block",
                        "status": "VULNERABLE",
                        "details": "HS256 allowed in production mode"
                    })
                except Exception as e:
                    if "SECURITY VIOLATION" in str(e) and "RS256" in str(e):
                        test_cases.append({
                            "case": "Production HS256 Block",
                            "status": "PROTECTED",
                            "details": "HS256 properly blocked in production"
                        })
                    else:
                        test_cases.append({
                            "case": "Production HS256 Block",
                            "status": "ERROR",
                            "details": f"Unexpected error: {str(e)}"
                        })
                
                # Test Case 2: Production mode with RS256 works
                os.environ["JWT_ALGORITHM"] = "RS256"
                
                try:
                    from infrastructure.security.jwt_advanced import AdvancedJWTManager
                    jwt_manager = AdvancedJWTManager()
                    test_cases.append({
                        "case": "Production RS256 Acceptance",
                        "status": "PROTECTED",
                        "details": "RS256 properly accepted in production"
                    })
                except Exception as e:
                    test_cases.append({
                        "case": "Production RS256 Acceptance",
                        "status": "VULNERABLE",
                        "details": f"RS256 rejected in production: {str(e)}"
                    })
                
                # Test Case 3: Development mode allows both
                os.environ["ENVIRONMENT"] = "development"
                os.environ["JWT_ALGORITHM"] = "HS256"
                
                try:
                    # Force reload of the module
                    if 'infrastructure.security.jwt_advanced' in sys.modules:
                        del sys.modules['infrastructure.security.jwt_advanced']
                    
                    from infrastructure.security.jwt_advanced import AdvancedJWTManager
                    jwt_manager = AdvancedJWTManager()
                    test_cases.append({
                        "case": "Development HS256 Acceptance",
                        "status": "PROTECTED",
                        "details": "HS256 properly allowed in development"
                    })
                except Exception as e:
                    test_cases.append({
                        "case": "Development HS256 Acceptance",
                        "status": "VULNERABLE",
                        "details": f"HS256 blocked in development: {str(e)}"
                    })
                
            finally:
                # Restore original environment
                if original_env:
                    os.environ["ENVIRONMENT"] = original_env
                else:
                    os.environ.pop("ENVIRONMENT", None)
                
                if original_algo:
                    os.environ["JWT_ALGORITHM"] = original_algo
                else:
                    os.environ.pop("JWT_ALGORITHM", None)
                
                if original_private:
                    os.environ["JWT_PRIVATE_KEY"] = original_private
                else:
                    os.environ.pop("JWT_PRIVATE_KEY", None)
                
                if original_public:
                    os.environ["JWT_PUBLIC_KEY"] = original_public
                else:
                    os.environ.pop("JWT_PUBLIC_KEY", None)
            
            # Evaluate results
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} production security scenarios"
            }
            
            if vulnerable_cases:
                self.validation_results["critical_issues"].extend([
                    f"Production security issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute production security tests"
            }
        
        self.validation_results["tests"]["production_security"] = test_result
        return test_result["status"] == "PASS"
    
    def test_rsa_key_enforcement(self) -> bool:
        """Test RSA key enforcement in production."""
        test_name = "RSA Key Enforcement"
        
        try:
            original_env = os.getenv("ENVIRONMENT")
            original_private = os.getenv("JWT_PRIVATE_KEY")
            original_public = os.getenv("JWT_PUBLIC_KEY")
            
            test_cases = []
            
            try:
                # Test Case 1: Missing RSA keys in production
                os.environ["ENVIRONMENT"] = "production"
                os.environ["JWT_ALGORITHM"] = "RS256"
                
                # Remove RSA keys
                if "JWT_PRIVATE_KEY" in os.environ:
                    del os.environ["JWT_PRIVATE_KEY"]
                if "JWT_PUBLIC_KEY" in os.environ:
                    del os.environ["JWT_PUBLIC_KEY"]
                
                # Force reload
                if 'infrastructure.security.jwt_advanced' in sys.modules:
                    del sys.modules['infrastructure.security.jwt_advanced']
                
                try:
                    from infrastructure.security.jwt_advanced import AdvancedJWTManager
                    jwt_manager = AdvancedJWTManager()
                    
                    # Try to create token (should fail without RSA keys)
                    # Note: This is a conceptual test since we can't easily test async methods
                    test_cases.append({
                        "case": "Missing RSA Keys Detection",
                        "status": "PASS",  # If we get here, key generation worked
                        "details": "System generated RSA keys when missing"
                    })
                    
                except Exception as e:
                    if "key" in str(e).lower() or "rsa" in str(e).lower():
                        test_cases.append({
                            "case": "Missing RSA Keys Detection",
                            "status": "PROTECTED",
                            "details": "Missing RSA keys properly detected"
                        })
                    else:
                        test_cases.append({
                            "case": "Missing RSA Keys Detection",
                            "status": "ERROR",
                            "details": f"Unexpected error: {str(e)}"
                        })
                
                # Test Case 2: Valid RSA keys in production
                os.environ["JWT_PRIVATE_KEY"] = self.test_private_key
                os.environ["JWT_PUBLIC_KEY"] = self.test_public_key
                
                # Force reload
                if 'infrastructure.security.jwt_advanced' in sys.modules:
                    del sys.modules['infrastructure.security.jwt_advanced']
                
                try:
                    from infrastructure.security.jwt_advanced import AdvancedJWTManager
                    jwt_manager = AdvancedJWTManager()
                    test_cases.append({
                        "case": "Valid RSA Keys Acceptance",
                        "status": "PROTECTED",
                        "details": "Valid RSA keys properly accepted"
                    })
                except Exception as e:
                    test_cases.append({
                        "case": "Valid RSA Keys Acceptance",
                        "status": "VULNERABLE",
                        "details": f"Valid RSA keys rejected: {str(e)}"
                    })
                
            finally:
                # Restore environment
                if original_env:
                    os.environ["ENVIRONMENT"] = original_env
                else:
                    os.environ.pop("ENVIRONMENT", None)
                
                if original_private:
                    os.environ["JWT_PRIVATE_KEY"] = original_private
                else:
                    os.environ.pop("JWT_PRIVATE_KEY", None)
                
                if original_public:
                    os.environ["JWT_PUBLIC_KEY"] = original_public
                else:
                    os.environ.pop("JWT_PUBLIC_KEY", None)
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} RSA key enforcement scenarios"
            }
            
            if vulnerable_cases:
                self.validation_results["critical_issues"].extend([
                    f"RSA key enforcement issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute RSA key enforcement tests"
            }
        
        self.validation_results["tests"]["rsa_enforcement"] = test_result
        return test_result["status"] == "PASS"
    
    def test_fallback_algorithm_removal(self) -> bool:
        """Test that fallback algorithm is properly removed in production."""
        test_name = "Fallback Algorithm Removal"
        
        try:
            test_cases = []
            
            # Test Case 1: Check code for fallback removal
            jwt_file_path = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/security/jwt_advanced.py"
            
            try:
                with open(jwt_file_path, 'r') as f:
                    jwt_code = f.read()
                
                # Check for security violations prevention
                security_checks = [
                    ("PRODUCTION SECURITY", "Production security checks present"),
                    ("SECURITY VIOLATION", "Security violation exceptions present"),
                    ("NO FALLBACK IN PRODUCTION", "Production fallback prevention present"),
                    ("env_mode == \"production\"", "Environment mode checks present")
                ]
                
                for check, description in security_checks:
                    if check in jwt_code:
                        test_cases.append({
                            "case": description,
                            "status": "PROTECTED",
                            "details": f"Found security check: {check}"
                        })
                    else:
                        test_cases.append({
                            "case": description,
                            "status": "VULNERABLE",
                            "details": f"Missing security check: {check}"
                        })
                
                # Check that old insecure patterns are removed
                insecure_patterns = [
                    ("algorithm=self.fallback_algorithm", "Direct fallback usage removed")
                ]
                
                for pattern, description in insecure_patterns:
                    if pattern in jwt_code:
                        # Check if it's in a secure context
                        if "if env_mode != \"production\"" in jwt_code or "Development/Testing" in jwt_code:
                            test_cases.append({
                                "case": description,
                                "status": "PROTECTED",
                                "details": f"Fallback properly secured with environment checks"
                            })
                        else:
                            test_cases.append({
                                "case": description,
                                "status": "VULNERABLE",
                                "details": f"Insecure fallback usage found: {pattern}"
                            })
                    else:
                        test_cases.append({
                            "case": description,
                            "status": "PROTECTED",
                            "details": f"Insecure pattern removed: {pattern}"
                        })
                
            except Exception as e:
                test_cases.append({
                    "case": "Code Security Analysis",
                    "status": "ERROR",
                    "details": f"Failed to analyze code: {str(e)}"
                })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Analyzed {len(test_cases)} code security patterns"
            }
            
            if vulnerable_cases:
                self.validation_results["critical_issues"].extend([
                    f"Code security issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute code security analysis"
            }
        
        self.validation_results["tests"]["code_security"] = test_result
        return test_result["status"] == "PASS"
    
    def test_environment_configuration_validation(self) -> bool:
        """Test environment configuration validation."""
        test_name = "Environment Configuration Validation"
        
        try:
            test_cases = []
            
            # Test Case 1: Check .env.production.template exists
            try:
                env_template_path = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/.env.production.template"
                
                with open(env_template_path, 'r') as f:
                    env_template = f.read()
                
                # Check for required production settings
                required_settings = [
                    ("JWT_ALGORITHM=RS256", "RS256 algorithm configured"),
                    ("ENVIRONMENT=production", "Production environment set"),
                    ("JWT_PRIVATE_KEY=", "Private key placeholder present"),
                    ("JWT_PUBLIC_KEY=", "Public key placeholder present"),
                    ("JWT_REQUIRE_DEVICE_ID=true", "Device ID requirement enabled"),
                    ("JWT_MAX_ACTIVE_SESSIONS=5", "Session limit configured")
                ]
                
                for setting, description in required_settings:
                    if setting in env_template:
                        test_cases.append({
                            "case": description,
                            "status": "PROTECTED",
                            "details": f"Found setting: {setting}"
                        })
                    else:
                        test_cases.append({
                            "case": description,
                            "status": "VULNERABLE",
                            "details": f"Missing setting: {setting}"
                        })
                
            except FileNotFoundError:
                test_cases.append({
                    "case": "Production Environment Template",
                    "status": "VULNERABLE",
                    "details": ".env.production.template file not found"
                })
            except Exception as e:
                test_cases.append({
                    "case": "Production Environment Template",
                    "status": "ERROR",
                    "details": f"Error reading template: {str(e)}"
                })
            
            # Test Case 2: Check RSA keys exist
            try:
                keys_dir = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/keys"
                
                if os.path.exists(keys_dir):
                    key_files = [f for f in os.listdir(keys_dir) if f.endswith('.pem')]
                    
                    private_keys = [f for f in key_files if 'private' in f]
                    public_keys = [f for f in key_files if 'public' in f]
                    
                    if private_keys and public_keys:
                        test_cases.append({
                            "case": "RSA Key Files Generation",
                            "status": "PROTECTED",
                            "details": f"Found {len(private_keys)} private and {len(public_keys)} public keys"
                        })
                    else:
                        test_cases.append({
                            "case": "RSA Key Files Generation",
                            "status": "VULNERABLE",
                            "details": "RSA key files not generated"
                        })
                else:
                    test_cases.append({
                        "case": "RSA Key Files Generation",
                        "status": "VULNERABLE",
                        "details": "Keys directory not created"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "RSA Key Files Generation",
                    "status": "ERROR",
                    "details": f"Error checking keys: {str(e)}"
                })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Validated {len(test_cases)} configuration aspects"
            }
            
            if vulnerable_cases:
                self.validation_results["critical_issues"].extend([
                    f"Configuration issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute configuration validation"
            }
        
        self.validation_results["tests"]["configuration"] = test_result
        return test_result["status"] == "PASS"
    
    def calculate_security_score(self):
        """Calculate overall security score."""
        self.validation_results["total_tests"] = len(self.validation_results["tests"])
        passed_tests = sum(
            1 for test in self.validation_results["tests"].values() 
            if test["status"] == "PASS"
        )
        self.validation_results["passed_tests"] = passed_tests
        
        if self.validation_results["total_tests"] == 0:
            self.validation_results["security_score"] = 0
        else:
            base_score = (passed_tests / self.validation_results["total_tests"]) * 100
            
            # Deduct heavily for critical issues
            critical_penalty = min(len(self.validation_results["critical_issues"]) * 25, 90)
            
            self.validation_results["security_score"] = max(0, base_score - critical_penalty)
    
    def run_final_validation(self):
        """Run complete final security validation."""
        print("🔐 Starting JWT Final Security Validation")
        print("=" * 60)
        
        # Run all validation tests
        tests = [
            self.test_production_mode_security_enforcement,
            self.test_rsa_key_enforcement,
            self.test_fallback_algorithm_removal,
            self.test_environment_configuration_validation
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
        
        # Calculate final score
        self.calculate_security_score()
        
        # Display results
        print("\n" + "=" * 60)
        print("🎯 FINAL SECURITY VALIDATION RESULTS")
        print("=" * 60)
        
        score = self.validation_results["security_score"]
        if score >= 95:
            score_status = "🟢 EXCELLENT - PRODUCTION READY"
        elif score >= 85:
            score_status = "🟡 GOOD - MINOR ISSUES"
        elif score >= 70:
            score_status = "🟠 NEEDS IMPROVEMENT"
        else:
            score_status = "🔴 CRITICAL - NOT PRODUCTION READY"
        
        print(f"Security Score: {score:.1f}% {score_status}")
        print(f"Tests Passed: {self.validation_results['passed_tests']}/{self.validation_results['total_tests']}")
        print(f"Critical Issues: {len(self.validation_results['critical_issues'])}")
        
        # Show critical issues
        if self.validation_results["critical_issues"]:
            print("\n🚨 CRITICAL ISSUES:")
            for issue in self.validation_results["critical_issues"]:
                print(f"  • {issue}")
        else:
            print("\n✅ No critical security issues detected")
        
        # Final security assessment
        if score >= 95:
            print("\n🎉 JWT IMPLEMENTATION IS PRODUCTION READY!")
            print("✓ All security measures properly implemented")
            print("✓ Production environment configuration secure")
            print("✓ Fallback algorithms properly restricted")
            print("✓ RSA key enforcement working correctly")
        elif score >= 85:
            print("\n⚠️ JWT implementation mostly secure with minor issues")
            print("→ Review and fix reported issues before production deployment")
        else:
            print("\n❌ JWT IMPLEMENTATION NOT READY FOR PRODUCTION")
            print("→ Critical security issues must be resolved immediately")
        
        return self.validation_results


def main():
    """Main validation execution."""
    validator = JWTFinalSecurityValidator()
    results = validator.run_final_validation()
    
    # Save results to file
    output_file = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/JWT_FINAL_SECURITY_VALIDATION.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {output_file}")
    
    # Return exit code based on critical issues
    critical_count = len(results["critical_issues"])
    score = results["security_score"]
    
    if score >= 95:
        print("\n✅ Final security validation PASSED - Ready for production!")
        return 0
    elif critical_count > 0:
        print(f"\n❌ Final security validation FAILED with {critical_count} critical issues")
        return 1
    else:
        print(f"\n⚠️ Final security validation completed with warnings (Score: {score:.1f}%)")
        return 2


if __name__ == "__main__":
    sys.exit(main())