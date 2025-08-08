#!/usr/bin/env python3
"""
RSA Environment Validation Script
================================
Critical security validation for JWT RSA keys in production environment.
This script ensures that RSA keys are properly configured and secure.
"""

import os
import sys
import json
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


class RSAEnvironmentValidator:
    """Validates RSA key configuration for production security."""
    
    def __init__(self):
        self.validation_results = {
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "tests": {},
            "security_score": 0,
            "critical_issues": [],
            "recommendations": []
        }
    
    def validate_environment_mode(self):
        """Validate environment mode is properly set."""
        env_mode = os.getenv("ENVIRONMENT", "development")
        
        test_result = {
            "test_name": "Environment Mode Validation",
            "status": "PASS" if env_mode in ["production", "development", "testing"] else "FAIL",
            "details": f"Environment mode: {env_mode}",
            "critical": True if env_mode not in ["production", "development", "testing"] else False
        }
        
        if env_mode == "production":
            test_result["production_mode"] = True
            test_result["details"] += " - Production security enforced"
        else:
            test_result["production_mode"] = False
            test_result["details"] += " - Development fallbacks available"
        
        self.validation_results["tests"]["environment_mode"] = test_result
        
        if test_result["status"] == "FAIL":
            self.validation_results["critical_issues"].append(
                "Invalid environment mode detected"
            )
        
        return test_result["status"] == "PASS"
    
    def validate_jwt_algorithm(self):
        """Validate JWT algorithm configuration."""
        jwt_algorithm = os.getenv("JWT_ALGORITHM", "RS256")
        env_mode = os.getenv("ENVIRONMENT", "development")
        
        test_result = {
            "test_name": "JWT Algorithm Validation",
            "algorithm": jwt_algorithm,
            "environment": env_mode
        }
        
        if env_mode == "production":
            if jwt_algorithm == "RS256":
                test_result["status"] = "PASS"
                test_result["details"] = "RS256 correctly configured for production"
                test_result["critical"] = False
            else:
                test_result["status"] = "FAIL"
                test_result["details"] = f"Invalid algorithm {jwt_algorithm} for production"
                test_result["critical"] = True
                self.validation_results["critical_issues"].append(
                    f"Production environment using insecure algorithm: {jwt_algorithm}"
                )
        else:
            test_result["status"] = "PASS"
            test_result["details"] = f"Algorithm {jwt_algorithm} acceptable for {env_mode}"
            test_result["critical"] = False
        
        self.validation_results["tests"]["jwt_algorithm"] = test_result
        return test_result["status"] == "PASS"
    
    def validate_rsa_private_key(self):
        """Validate RSA private key configuration."""
        private_key_env = os.getenv("JWT_PRIVATE_KEY")
        
        test_result = {
            "test_name": "RSA Private Key Validation",
            "key_present": bool(private_key_env),
            "key_length_valid": False,
            "key_format_valid": False,
            "security_level": "UNKNOWN"
        }
        
        if not private_key_env:
            test_result["status"] = "FAIL"
            test_result["details"] = "JWT_PRIVATE_KEY environment variable not set"
            test_result["critical"] = True
            self.validation_results["critical_issues"].append(
                "Missing RSA private key in environment"
            )
        else:
            try:
                # Parse private key
                private_key = serialization.load_pem_private_key(
                    private_key_env.encode(), 
                    password=None, 
                    backend=default_backend()
                )
                
                if isinstance(private_key, rsa.RSAPrivateKey):
                    key_size = private_key.key_size
                    test_result["key_size"] = key_size
                    test_result["key_format_valid"] = True
                    
                    if key_size >= 2048:
                        test_result["key_length_valid"] = True
                        if key_size >= 4096:
                            test_result["security_level"] = "EXCELLENT"
                        elif key_size >= 2048:
                            test_result["security_level"] = "GOOD"
                    else:
                        test_result["security_level"] = "WEAK"
                        self.validation_results["critical_issues"].append(
                            f"RSA key size {key_size} is too weak (minimum 2048 bits)"
                        )
                    
                    # Check key age (if possible)
                    test_result["key_type"] = "RSA"
                    test_result["status"] = "PASS" if test_result["key_length_valid"] else "FAIL"
                    test_result["details"] = f"Valid RSA-{key_size} private key found"
                    test_result["critical"] = not test_result["key_length_valid"]
                else:
                    test_result["status"] = "FAIL"
                    test_result["details"] = "Private key is not RSA format"
                    test_result["critical"] = True
                    self.validation_results["critical_issues"].append(
                        "Private key is not in RSA format"
                    )
                    
            except Exception as e:
                test_result["status"] = "FAIL"
                test_result["details"] = f"Invalid private key format: {str(e)}"
                test_result["critical"] = True
                test_result["error"] = str(e)
                self.validation_results["critical_issues"].append(
                    f"Cannot parse RSA private key: {str(e)}"
                )
        
        self.validation_results["tests"]["rsa_private_key"] = test_result
        return test_result["status"] == "PASS"
    
    def validate_rsa_public_key(self):
        """Validate RSA public key configuration."""
        public_key_env = os.getenv("JWT_PUBLIC_KEY")
        
        test_result = {
            "test_name": "RSA Public Key Validation",
            "key_present": bool(public_key_env),
            "key_format_valid": False,
            "matches_private": False
        }
        
        if not public_key_env:
            test_result["status"] = "FAIL"
            test_result["details"] = "JWT_PUBLIC_KEY environment variable not set"
            test_result["critical"] = True
            self.validation_results["critical_issues"].append(
                "Missing RSA public key in environment"
            )
        else:
            try:
                # Parse public key
                public_key = serialization.load_pem_public_key(
                    public_key_env.encode(), 
                    backend=default_backend()
                )
                
                if isinstance(public_key, rsa.RSAPublicKey):
                    key_size = public_key.key_size
                    test_result["key_size"] = key_size
                    test_result["key_format_valid"] = True
                    test_result["key_type"] = "RSA"
                    
                    # Try to match with private key
                    private_key_env = os.getenv("JWT_PRIVATE_KEY")
                    if private_key_env:
                        try:
                            private_key = serialization.load_pem_private_key(
                                private_key_env.encode(), 
                                password=None, 
                                backend=default_backend()
                            )
                            
                            # Compare public keys
                            private_public = private_key.public_key()
                            private_public_pem = private_public.public_bytes(
                                encoding=serialization.Encoding.PEM,
                                format=serialization.PublicFormat.SubjectPublicKeyInfo
                            )
                            current_public_pem = public_key.public_bytes(
                                encoding=serialization.Encoding.PEM,
                                format=serialization.PublicFormat.SubjectPublicKeyInfo
                            )
                            
                            test_result["matches_private"] = private_public_pem == current_public_pem
                            
                        except Exception as e:
                            test_result["key_match_error"] = str(e)
                    
                    test_result["status"] = "PASS"
                    test_result["details"] = f"Valid RSA-{key_size} public key found"
                    test_result["critical"] = False
                    
                    if not test_result["matches_private"]:
                        test_result["details"] += " (Warning: May not match private key)"
                        self.validation_results["recommendations"].append(
                            "Verify that public and private keys are a matching pair"
                        )
                else:
                    test_result["status"] = "FAIL"
                    test_result["details"] = "Public key is not RSA format"
                    test_result["critical"] = True
                    self.validation_results["critical_issues"].append(
                        "Public key is not in RSA format"
                    )
                    
            except Exception as e:
                test_result["status"] = "FAIL"
                test_result["details"] = f"Invalid public key format: {str(e)}"
                test_result["critical"] = True
                test_result["error"] = str(e)
                self.validation_results["critical_issues"].append(
                    f"Cannot parse RSA public key: {str(e)}"
                )
        
        self.validation_results["tests"]["rsa_public_key"] = test_result
        return test_result["status"] == "PASS"
    
    def validate_key_security_requirements(self):
        """Validate security requirements for RSA keys."""
        env_mode = os.getenv("ENVIRONMENT", "development")
        
        test_result = {
            "test_name": "Key Security Requirements",
            "environment": env_mode,
            "requirements_met": True,
            "security_checks": []
        }
        
        # Check if keys are required based on environment
        if env_mode == "production":
            # Production requires both keys
            private_key = os.getenv("JWT_PRIVATE_KEY")
            public_key = os.getenv("JWT_PUBLIC_KEY")
            
            if not private_key:
                test_result["requirements_met"] = False
                test_result["security_checks"].append({
                    "check": "Production Private Key Required",
                    "status": "FAIL",
                    "details": "JWT_PRIVATE_KEY must be set in production"
                })
            
            if not public_key:
                test_result["requirements_met"] = False
                test_result["security_checks"].append({
                    "check": "Production Public Key Required", 
                    "status": "FAIL",
                    "details": "JWT_PUBLIC_KEY must be set in production"
                })
            
            # Check key strength
            if private_key:
                try:
                    private_key_obj = serialization.load_pem_private_key(
                        private_key.encode(), password=None, backend=default_backend()
                    )
                    if isinstance(private_key_obj, rsa.RSAPrivateKey):
                        key_size = private_key_obj.key_size
                        if key_size < 2048:
                            test_result["requirements_met"] = False
                            test_result["security_checks"].append({
                                "check": "Key Strength Validation",
                                "status": "FAIL",
                                "details": f"RSA key size {key_size} too weak for production"
                            })
                        else:
                            test_result["security_checks"].append({
                                "check": "Key Strength Validation",
                                "status": "PASS",
                                "details": f"RSA-{key_size} meets security requirements"
                            })
                except:
                    test_result["requirements_met"] = False
                    test_result["security_checks"].append({
                        "check": "Key Parsing Validation",
                        "status": "FAIL",
                        "details": "Cannot parse private key for validation"
                    })
        else:
            # Development/Testing - keys are optional
            test_result["security_checks"].append({
                "check": "Development Environment",
                "status": "PASS",
                "details": "RSA keys optional in development mode"
            })
        
        test_result["status"] = "PASS" if test_result["requirements_met"] else "FAIL"
        test_result["critical"] = not test_result["requirements_met"]
        test_result["details"] = f"Security requirements {'met' if test_result['requirements_met'] else 'NOT MET'}"
        
        if not test_result["requirements_met"]:
            self.validation_results["critical_issues"].append(
                "RSA key security requirements not met for current environment"
            )
        
        self.validation_results["tests"]["security_requirements"] = test_result
        return test_result["status"] == "PASS"
    
    def calculate_security_score(self):
        """Calculate overall security score."""
        total_tests = len(self.validation_results["tests"])
        passed_tests = sum(1 for test in self.validation_results["tests"].values() 
                          if test["status"] == "PASS")
        
        if total_tests == 0:
            self.validation_results["security_score"] = 0
        else:
            base_score = (passed_tests / total_tests) * 100
            
            # Deduct points for critical issues
            critical_issues = len(self.validation_results["critical_issues"])
            penalty = min(critical_issues * 20, 80)  # Max 80% penalty
            
            self.validation_results["security_score"] = max(0, base_score - penalty)
    
    def generate_recommendations(self):
        """Generate security recommendations."""
        env_mode = os.getenv("ENVIRONMENT", "development")
        
        if env_mode == "production":
            if not os.getenv("JWT_PRIVATE_KEY"):
                self.validation_results["recommendations"].append(
                    "Generate and set JWT_PRIVATE_KEY environment variable for production"
                )
            
            if not os.getenv("JWT_PUBLIC_KEY"):
                self.validation_results["recommendations"].append(
                    "Generate and set JWT_PUBLIC_KEY environment variable for production"
                )
        
        # Key rotation recommendation
        self.validation_results["recommendations"].append(
            "Implement regular RSA key rotation (recommended: every 30 days)"
        )
        
        # Security monitoring
        self.validation_results["recommendations"].append(
            "Monitor JWT signing operations for anomalies"
        )
        
        # Backup recommendations
        self.validation_results["recommendations"].append(
            "Maintain secure backup of RSA key pairs"
        )
    
    def run_validation(self):
        """Run complete RSA environment validation."""
        print("🔐 Starting RSA Environment Validation...")
        print("=" * 50)
        
        # Run all validation tests
        tests = [
            self.validate_environment_mode,
            self.validate_jwt_algorithm,
            self.validate_rsa_private_key,
            self.validate_rsa_public_key,
            self.validate_key_security_requirements
        ]
        
        for test in tests:
            try:
                result = test()
                test_name = test.__name__.replace('validate_', '').replace('_', ' ').title()
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{test_name}: {status}")
            except Exception as e:
                print(f"{test_name}: ❌ ERROR - {e}")
        
        # Calculate final score and recommendations
        self.calculate_security_score()
        self.generate_recommendations()
        
        # Display results
        print("\n" + "=" * 50)
        print("🎯 VALIDATION RESULTS")
        print("=" * 50)
        
        score = self.validation_results["security_score"]
        if score >= 90:
            score_status = "🟢 EXCELLENT"
        elif score >= 70:
            score_status = "🟡 GOOD"
        elif score >= 50:
            score_status = "🟠 NEEDS IMPROVEMENT"
        else:
            score_status = "🔴 CRITICAL"
        
        print(f"Security Score: {score:.1f}% {score_status}")
        print(f"Environment: {self.validation_results['environment']}")
        print(f"Critical Issues: {len(self.validation_results['critical_issues'])}")
        
        # Show critical issues
        if self.validation_results["critical_issues"]:
            print("\n🚨 CRITICAL ISSUES:")
            for issue in self.validation_results["critical_issues"]:
                print(f"  • {issue}")
        
        # Show recommendations
        if self.validation_results["recommendations"]:
            print("\n💡 RECOMMENDATIONS:")
            for rec in self.validation_results["recommendations"]:
                print(f"  • {rec}")
        
        return self.validation_results


def main():
    """Main validation execution."""
    validator = RSAEnvironmentValidator()
    results = validator.run_validation()
    
    # Save results to file
    output_file = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/RSA_ENVIRONMENT_VALIDATION.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {output_file}")
    
    # Return exit code based on critical issues
    critical_issues = len(results["critical_issues"])
    if critical_issues > 0:
        print(f"\n❌ Validation failed with {critical_issues} critical issues")
        return 1
    else:
        print("\n✅ Validation completed successfully")
        return 0


if __name__ == "__main__":
    sys.exit(main())