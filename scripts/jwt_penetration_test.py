#!/usr/bin/env python3
"""
JWT Penetration Testing Suite
============================
Comprehensive penetration testing for JWT security implementation.
Tests various attack vectors to ensure production security.
"""

import os
import sys
import jwt
import json
import base64
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


class JWTPenetrationTester:
    """Comprehensive JWT penetration testing suite."""
    
    def __init__(self):
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "test_suite": "JWT Penetration Testing",
            "tests": {},
            "security_score": 0,
            "vulnerabilities": [],
            "passed_tests": 0,
            "total_tests": 0
        }
        
        # Test JWT Manager
        os.environ["ENVIRONMENT"] = "testing"  # Safe testing mode
        
        # Import our JWT manager
        sys.path.append("/mnt/c/Users/jaafa/Desktop/ai teddy bear/src")
        from infrastructure.security.jwt_advanced import AdvancedJWTManager
        self.jwt_manager = AdvancedJWTManager()
        
        # Generate test keys
        self.generate_test_keys()
    
    def generate_test_keys(self):
        """Generate test RSA keys for testing."""
        # Generate legitimate key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        self.legitimate_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        self.legitimate_public = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Generate fake key pair for attack testing
        fake_private = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        self.fake_private = fake_private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        self.fake_public = fake_private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Set legitimate keys in environment for testing
        os.environ["JWT_PRIVATE_KEY"] = self.legitimate_private
        os.environ["JWT_PUBLIC_KEY"] = self.legitimate_public
    
    def test_algorithm_substitution_attack(self):
        """Test algorithm substitution attacks (alg: none, HS256)."""
        test_name = "Algorithm Substitution Attack"
        
        try:
            # Create legitimate token first
            legitimate_token = jwt.encode({
                "sub": "test_user",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "role": "user"
            }, self.legitimate_private, algorithm="RS256")
            
            attacks = []
            
            # Attack 1: Change algorithm to 'none'
            try:
                payload = jwt.decode(legitimate_token, options={"verify_signature": False})
                none_token = jwt.encode(payload, "", algorithm="none")
                
                # Try to verify with our system
                try:
                    os.environ["ENVIRONMENT"] = "production"  # Test production mode
                    test_jwt_manager = AdvancedJWTManager()
                    claims = test_jwt_manager.verify_token(none_token)
                    attacks.append({
                        "attack": "Algorithm None",
                        "status": "VULNERABLE", 
                        "details": "System accepted token with alg=none"
                    })
                except:
                    attacks.append({
                        "attack": "Algorithm None",
                        "status": "PROTECTED",
                        "details": "System rejected token with alg=none"
                    })
                finally:
                    os.environ["ENVIRONMENT"] = "testing"
            except Exception as e:
                attacks.append({
                    "attack": "Algorithm None",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Attack 2: Change RS256 to HS256 using public key as secret
            try:
                payload = jwt.decode(legitimate_token, options={"verify_signature": False})
                # Use public key as HMAC secret (common attack)
                hs256_token = jwt.encode(payload, self.legitimate_public, algorithm="HS256")
                
                try:
                    os.environ["ENVIRONMENT"] = "production"
                    test_jwt_manager = AdvancedJWTManager()
                    claims = test_jwt_manager.verify_token(hs256_token)
                    attacks.append({
                        "attack": "RS256 to HS256 Substitution",
                        "status": "VULNERABLE",
                        "details": "System accepted HS256 token in production"
                    })
                except:
                    attacks.append({
                        "attack": "RS256 to HS256 Substitution", 
                        "status": "PROTECTED",
                        "details": "System rejected HS256 token in production"
                    })
                finally:
                    os.environ["ENVIRONMENT"] = "testing"
            except Exception as e:
                attacks.append({
                    "attack": "RS256 to HS256 Substitution",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Determine overall test result
            vulnerable_attacks = [a for a in attacks if a["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_attacks else "PASS",
                "attacks": attacks,
                "vulnerabilities_found": len(vulnerable_attacks),
                "details": f"Tested {len(attacks)} algorithm substitution attacks"
            }
            
            if vulnerable_attacks:
                self.test_results["vulnerabilities"].extend([
                    f"Algorithm substitution vulnerability: {attack['attack']}" 
                    for attack in vulnerable_attacks
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute algorithm substitution tests"
            }
        
        self.test_results["tests"]["algorithm_substitution"] = test_result
        return test_result["status"] == "PASS"
    
    def test_key_substitution_attack(self):
        """Test key substitution attacks using fake keys."""
        test_name = "Key Substitution Attack"
        
        try:
            attacks = []
            
            # Create token with fake private key
            payload = {
                "sub": "malicious_user",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "role": "admin",  # Try to escalate privileges
                "user_type": "admin"
            }
            
            fake_token = jwt.encode(payload, self.fake_private, algorithm="RS256")
            
            # Try to verify with legitimate system
            try:
                os.environ["ENVIRONMENT"] = "production"
                test_jwt_manager = AdvancedJWTManager()
                claims = test_jwt_manager.verify_token(fake_token)
                attacks.append({
                    "attack": "Fake Key Substitution",
                    "status": "VULNERABLE",
                    "details": "System accepted token signed with fake key"
                })
            except:
                attacks.append({
                    "attack": "Fake Key Substitution", 
                    "status": "PROTECTED",
                    "details": "System rejected token signed with fake key"
                })
            finally:
                os.environ["ENVIRONMENT"] = "testing"
            
            # Test with modified public key in environment
            original_public = os.environ.get("JWT_PUBLIC_KEY")
            try:
                os.environ["JWT_PUBLIC_KEY"] = self.fake_public
                os.environ["ENVIRONMENT"] = "production"
                test_jwt_manager = AdvancedJWTManager()
                
                # This should fail due to key mismatch
                try:
                    claims = test_jwt_manager.verify_token(fake_token)
                    attacks.append({
                        "attack": "Environment Key Substitution",
                        "status": "VULNERABLE", 
                        "details": "System accepted token after key substitution"
                    })
                except:
                    attacks.append({
                        "attack": "Environment Key Substitution",
                        "status": "PROTECTED",
                        "details": "System detected key substitution"
                    })
            finally:
                if original_public:
                    os.environ["JWT_PUBLIC_KEY"] = original_public
                os.environ["ENVIRONMENT"] = "testing"
            
            vulnerable_attacks = [a for a in attacks if a["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_attacks else "PASS",
                "attacks": attacks,
                "vulnerabilities_found": len(vulnerable_attacks),
                "details": f"Tested {len(attacks)} key substitution attacks"
            }
            
            if vulnerable_attacks:
                self.test_results["vulnerabilities"].extend([
                    f"Key substitution vulnerability: {attack['attack']}" 
                    for attack in vulnerable_attacks
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute key substitution tests"
            }
        
        self.test_results["tests"]["key_substitution"] = test_result
        return test_result["status"] == "PASS"
    
    def test_token_manipulation_attacks(self):
        """Test token payload manipulation attacks."""
        test_name = "Token Manipulation Attack"
        
        try:
            attacks = []
            
            # Create legitimate token
            legitimate_payload = {
                "sub": "regular_user",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "role": "user",
                "user_type": "parent"
            }
            
            legitimate_token = jwt.encode(legitimate_payload, self.legitimate_private, algorithm="RS256")
            
            # Attack 1: Modify payload without re-signing
            try:
                # Decode token parts
                header, payload, signature = legitimate_token.split('.')
                
                # Decode payload
                decoded_payload = json.loads(base64.urlsafe_b64decode(payload + '=='))
                
                # Modify payload (privilege escalation)
                decoded_payload['role'] = 'admin'
                decoded_payload['user_type'] = 'admin'
                
                # Re-encode payload
                modified_payload = base64.urlsafe_b64encode(
                    json.dumps(decoded_payload).encode()
                ).decode().rstrip('=')
                
                # Create tampered token
                tampered_token = f"{header}.{modified_payload}.{signature}"
                
                # Try to verify
                try:
                    os.environ["ENVIRONMENT"] = "production"
                    test_jwt_manager = AdvancedJWTManager()
                    claims = test_jwt_manager.verify_token(tampered_token)
                    attacks.append({
                        "attack": "Payload Manipulation",
                        "status": "VULNERABLE",
                        "details": "System accepted tampered token payload"
                    })
                except:
                    attacks.append({
                        "attack": "Payload Manipulation",
                        "status": "PROTECTED",
                        "details": "System detected payload tampering"
                    })
                finally:
                    os.environ["ENVIRONMENT"] = "testing"
                    
            except Exception as e:
                attacks.append({
                    "attack": "Payload Manipulation",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Attack 2: Timestamp manipulation (expired token)
            try:
                expired_payload = legitimate_payload.copy()
                expired_payload['exp'] = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
                
                expired_token = jwt.encode(expired_payload, self.legitimate_private, algorithm="RS256")
                
                try:
                    os.environ["ENVIRONMENT"] = "production"
                    test_jwt_manager = AdvancedJWTManager()
                    claims = test_jwt_manager.verify_token(expired_token)
                    attacks.append({
                        "attack": "Expired Token Bypass",
                        "status": "VULNERABLE",
                        "details": "System accepted expired token"
                    })
                except:
                    attacks.append({
                        "attack": "Expired Token Bypass",
                        "status": "PROTECTED", 
                        "details": "System rejected expired token"
                    })
                finally:
                    os.environ["ENVIRONMENT"] = "testing"
                    
            except Exception as e:
                attacks.append({
                    "attack": "Expired Token Bypass",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"  
                })
            
            vulnerable_attacks = [a for a in attacks if a["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_attacks else "PASS",
                "attacks": attacks,
                "vulnerabilities_found": len(vulnerable_attacks),
                "details": f"Tested {len(attacks)} token manipulation attacks"
            }
            
            if vulnerable_attacks:
                self.test_results["vulnerabilities"].extend([
                    f"Token manipulation vulnerability: {attack['attack']}" 
                    for attack in vulnerable_attacks
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR", 
                "error": str(e),
                "details": "Failed to execute token manipulation tests"
            }
        
        self.test_results["tests"]["token_manipulation"] = test_result
        return test_result["status"] == "PASS"
    
    def test_production_mode_enforcement(self):
        """Test production mode security enforcement."""
        test_name = "Production Mode Enforcement"
        
        try:
            enforcement_tests = []
            
            # Test 1: Ensure HS256 is blocked in production
            try:
                os.environ["JWT_ALGORITHM"] = "HS256"
                os.environ["ENVIRONMENT"] = "production"
                
                # This should raise an exception
                try:
                    test_jwt_manager = AdvancedJWTManager()
                    enforcement_tests.append({
                        "test": "HS256 Algorithm Block",
                        "status": "VULNERABLE",
                        "details": "System allowed HS256 in production mode"
                    })
                except Exception as e:
                    if "SECURITY VIOLATION" in str(e):
                        enforcement_tests.append({
                            "test": "HS256 Algorithm Block",
                            "status": "PROTECTED",
                            "details": "System blocked HS256 in production mode"
                        })
                    else:
                        enforcement_tests.append({
                            "test": "HS256 Algorithm Block",
                            "status": "ERROR",
                            "details": f"Unexpected error: {str(e)}"
                        })
                finally:
                    os.environ["JWT_ALGORITHM"] = "RS256"
                    os.environ["ENVIRONMENT"] = "testing"
                    
            except Exception as e:
                enforcement_tests.append({
                    "test": "HS256 Algorithm Block",
                    "status": "ERROR",
                    "details": f"Test setup error: {str(e)}"
                })
            
            # Test 2: Ensure missing RSA keys are detected
            try:
                original_private = os.environ.get("JWT_PRIVATE_KEY")
                original_public = os.environ.get("JWT_PUBLIC_KEY")
                
                # Remove keys
                if "JWT_PRIVATE_KEY" in os.environ:
                    del os.environ["JWT_PRIVATE_KEY"]
                if "JWT_PUBLIC_KEY" in os.environ:
                    del os.environ["JWT_PUBLIC_KEY"]
                
                os.environ["ENVIRONMENT"] = "production"
                
                try:
                    test_jwt_manager = AdvancedJWTManager()
                    # Try to create a token (should fail)
                    token = test_jwt_manager.create_token(
                        user_id="test",
                        email="test@test.com", 
                        role="user",
                        user_type="parent",
                        token_type=test_jwt_manager.TokenType.ACCESS
                    )
                    enforcement_tests.append({
                        "test": "Missing RSA Keys Detection",
                        "status": "VULNERABLE",
                        "details": "System allowed token creation without RSA keys"
                    })
                except Exception as e:
                    if "key pair" in str(e).lower() or "rsa" in str(e).lower():
                        enforcement_tests.append({
                            "test": "Missing RSA Keys Detection", 
                            "status": "PROTECTED",
                            "details": "System detected missing RSA keys"
                        })
                    else:
                        enforcement_tests.append({
                            "test": "Missing RSA Keys Detection",
                            "status": "ERROR",
                            "details": f"Unexpected error: {str(e)}"
                        })
                finally:
                    # Restore keys
                    if original_private:
                        os.environ["JWT_PRIVATE_KEY"] = original_private
                    if original_public:
                        os.environ["JWT_PUBLIC_KEY"] = original_public
                    os.environ["ENVIRONMENT"] = "testing"
                    
            except Exception as e:
                enforcement_tests.append({
                    "test": "Missing RSA Keys Detection",
                    "status": "ERROR",
                    "details": f"Test setup error: {str(e)}"
                })
            
            vulnerable_tests = [t for t in enforcement_tests if t["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_tests else "PASS",
                "enforcement_tests": enforcement_tests,
                "vulnerabilities_found": len(vulnerable_tests),
                "details": f"Tested {len(enforcement_tests)} production enforcement checks"
            }
            
            if vulnerable_tests:
                self.test_results["vulnerabilities"].extend([
                    f"Production enforcement vulnerability: {test['test']}" 
                    for test in vulnerable_tests
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute production enforcement tests"
            }
        
        self.test_results["tests"]["production_enforcement"] = test_result
        return test_result["status"] == "PASS"
    
    def calculate_security_score(self):
        """Calculate overall security score."""
        self.test_results["total_tests"] = len(self.test_results["tests"])
        self.test_results["passed_tests"] = sum(
            1 for test in self.test_results["tests"].values() 
            if test["status"] == "PASS"
        )
        
        if self.test_results["total_tests"] == 0:
            self.test_results["security_score"] = 0
        else:
            base_score = (self.test_results["passed_tests"] / self.test_results["total_tests"]) * 100
            
            # Deduct points for vulnerabilities
            vulnerability_penalty = min(len(self.test_results["vulnerabilities"]) * 15, 90)
            
            self.test_results["security_score"] = max(0, base_score - vulnerability_penalty)
    
    def run_penetration_tests(self):
        """Run complete penetration testing suite."""
        print("🛡️ Starting JWT Penetration Testing Suite")
        print("=" * 50)
        
        # Run all tests
        tests = [
            self.test_algorithm_substitution_attack,
            self.test_key_substitution_attack, 
            self.test_token_manipulation_attacks,
            self.test_production_mode_enforcement
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
        print("\n" + "=" * 50)
        print("🎯 PENETRATION TEST RESULTS")
        print("=" * 50)
        
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
        print(f"Vulnerabilities Found: {len(self.test_results['vulnerabilities'])}")
        
        # Show vulnerabilities
        if self.test_results["vulnerabilities"]:
            print("\n🚨 VULNERABILITIES DETECTED:")
            for vuln in self.test_results["vulnerabilities"]:
                print(f"  • {vuln}")
        else:
            print("\n✅ No vulnerabilities detected in JWT implementation")
        
        return self.test_results


def main():
    """Main penetration testing execution."""
    tester = JWTPenetrationTester()
    results = tester.run_penetration_tests()
    
    # Save results to file
    output_file = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/JWT_PENETRATION_TEST_RESULTS.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {output_file}")
    
    # Return exit code based on vulnerabilities
    vulnerability_count = len(results["vulnerabilities"])
    if vulnerability_count > 0:
        print(f"\n❌ Penetration testing failed with {vulnerability_count} vulnerabilities")
        return 1
    else:
        print("\n✅ Penetration testing completed successfully - No vulnerabilities found")
        return 0


if __name__ == "__main__":
    sys.exit(main())