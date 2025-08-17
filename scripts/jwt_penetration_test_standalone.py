#!/usr/bin/env python3
"""
JWT Penetration Testing Suite - Standalone Version
=================================================
Comprehensive penetration testing for JWT security without external dependencies.
Tests various attack vectors to ensure production security.
"""

import os
import jwt
import json
import base64
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


class StandaloneJWTPenetrationTester:
    """Standalone JWT penetration testing suite."""
    
    def __init__(self):
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "test_suite": "JWT Penetration Testing (Standalone)",
            "tests": {},
            "security_score": 0,
            "vulnerabilities": [],
            "passed_tests": 0,
            "total_tests": 0
        }
        
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
        
        # Test HMAC secret
        self.hmac_secret = "test_secret_key_for_testing"
    
    def test_algorithm_substitution_attack(self):
        """Test algorithm substitution attacks (alg: none, HS256)."""
        test_name = "Algorithm Substitution Attack"
        
        try:
            attacks = []
            
            # Create legitimate RS256 token
            payload = {
                "sub": "test_user",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "role": "user"
            }
            
            legitimate_token = jwt.encode(payload, self.legitimate_private, algorithm="RS256")
            
            # Attack 1: Change algorithm to 'none'
            try:
                # Create token with alg=none
                none_token = jwt.encode(payload, "", algorithm="none")
                
                # Try to verify with RS256 public key (should fail)
                try:
                    decoded = jwt.decode(none_token, self.legitimate_public, algorithms=["RS256"])
                    attacks.append({
                        "attack": "Algorithm None (RS256 verify)",
                        "status": "VULNERABLE", 
                        "details": "System accepted token with alg=none when expecting RS256"
                    })
                except:
                    attacks.append({
                        "attack": "Algorithm None (RS256 verify)",
                        "status": "PROTECTED",
                        "details": "System rejected token with alg=none when expecting RS256"
                    })
                
                # Try to verify with none algorithm allowed (should be blocked)
                try:
                    decoded = jwt.decode(none_token, "", algorithms=["none"])
                    attacks.append({
                        "attack": "Algorithm None (none allowed)",
                        "status": "VULNERABLE",
                        "details": "System allowed verification with alg=none"
                    })
                except:
                    attacks.append({
                        "attack": "Algorithm None (none allowed)",
                        "status": "PROTECTED", 
                        "details": "System blocked verification with alg=none"
                    })
                    
            except Exception as e:
                attacks.append({
                    "attack": "Algorithm None",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Attack 2: Change RS256 to HS256 using public key as secret
            try:
                # Create HS256 token using public key as secret
                hs256_token = jwt.encode(payload, self.legitimate_public, algorithm="HS256")
                
                # Try to verify with public key as HMAC secret (common vulnerability)
                try:
                    decoded = jwt.decode(hs256_token, self.legitimate_public, algorithms=["HS256"])
                    attacks.append({
                        "attack": "RS256 to HS256 (public key as secret)",
                        "status": "VULNERABLE",
                        "details": "System accepted HS256 token using public key as HMAC secret"
                    })
                except:
                    attacks.append({
                        "attack": "RS256 to HS256 (public key as secret)",
                        "status": "PROTECTED", 
                        "details": "System rejected HS256 token using public key as HMAC secret"
                    })
                
                # Try to verify HS256 token when expecting RS256 (should fail)
                try:
                    decoded = jwt.decode(hs256_token, self.legitimate_public, algorithms=["RS256"])
                    attacks.append({
                        "attack": "HS256 bypass RS256 verification",
                        "status": "VULNERABLE",
                        "details": "HS256 token accepted when expecting RS256"
                    })
                except:
                    attacks.append({
                        "attack": "HS256 bypass RS256 verification",
                        "status": "PROTECTED",
                        "details": "HS256 token rejected when expecting RS256"
                    })
                    
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
            
            # Try to verify with legitimate public key (should fail)
            try:
                decoded = jwt.decode(fake_token, self.legitimate_public, algorithms=["RS256"])
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
            
            # Test with legitimate token verified with fake public key
            legitimate_payload = {
                "sub": "legitimate_user",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "role": "user"
            }
            
            legitimate_token = jwt.encode(legitimate_payload, self.legitimate_private, algorithm="RS256")
            
            try:
                decoded = jwt.decode(legitimate_token, self.fake_public, algorithms=["RS256"])
                attacks.append({
                    "attack": "Public Key Substitution",
                    "status": "VULNERABLE", 
                    "details": "System accepted legitimate token with fake public key"
                })
            except:
                attacks.append({
                    "attack": "Public Key Substitution",
                    "status": "PROTECTED",
                    "details": "System rejected legitimate token with fake public key"
                })
            
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
                
                # Try to verify (should fail due to signature mismatch)
                try:
                    decoded = jwt.decode(tampered_token, self.legitimate_public, algorithms=["RS256"])
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
                    decoded = jwt.decode(expired_token, self.legitimate_public, algorithms=["RS256"])
                    attacks.append({
                        "attack": "Expired Token Bypass",
                        "status": "VULNERABLE",
                        "details": "System accepted expired token"
                    })
                except jwt.ExpiredSignatureError:
                    attacks.append({
                        "attack": "Expired Token Bypass",
                        "status": "PROTECTED", 
                        "details": "System rejected expired token"
                    })
                except Exception as e:
                    attacks.append({
                        "attack": "Expired Token Bypass",
                        "status": "ERROR",
                        "details": f"Unexpected error: {str(e)}"
                    })
                    
            except Exception as e:
                attacks.append({
                    "attack": "Expired Token Bypass",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"  
                })
            
            # Attack 3: Future token (nbf manipulation)
            try:
                future_payload = legitimate_payload.copy()
                future_payload['nbf'] = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
                
                future_token = jwt.encode(future_payload, self.legitimate_private, algorithm="RS256")
                
                try:
                    decoded = jwt.decode(future_token, self.legitimate_public, algorithms=["RS256"])
                    attacks.append({
                        "attack": "Future Token Bypass",
                        "status": "VULNERABLE",
                        "details": "System accepted token with future nbf"
                    })
                except jwt.ImmatureSignatureError:
                    attacks.append({
                        "attack": "Future Token Bypass",
                        "status": "PROTECTED",
                        "details": "System rejected token with future nbf"
                    })
                except Exception as e:
                    attacks.append({
                        "attack": "Future Token Bypass", 
                        "status": "ERROR",
                        "details": f"Unexpected error: {str(e)}"
                    })
                    
            except Exception as e:
                attacks.append({
                    "attack": "Future Token Bypass",
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
    
    def test_weak_secret_attacks(self):
        """Test attacks against weak HMAC secrets."""
        test_name = "Weak Secret Attack"
        
        try:
            attacks = []
            
            # Create HS256 token with weak secret
            payload = {
                "sub": "test_user",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "role": "admin"
            }
            
            # Test common weak secrets
            weak_secrets = [
                "secret",
                "password", 
                "123456",
                "",
                "key",
                "jwt_secret"
            ]
            
            for weak_secret in weak_secrets:
                try:
                    # Create token with weak secret
                    weak_token = jwt.encode(payload, weak_secret, algorithm="HS256")
                    
                    # Try to crack by guessing the secret
                    try:
                        decoded = jwt.decode(weak_token, weak_secret, algorithms=["HS256"])
                        attacks.append({
                            "attack": f"Weak Secret: '{weak_secret}'",
                            "status": "VULNERABLE",
                            "details": f"Token cracked using weak secret: {weak_secret}"
                        })
                    except:
                        attacks.append({
                            "attack": f"Weak Secret: '{weak_secret}'",
                            "status": "PROTECTED",
                            "details": f"Token secure against weak secret: {weak_secret}"
                        })
                        
                except Exception as e:
                    attacks.append({
                        "attack": f"Weak Secret: '{weak_secret}'",
                        "status": "ERROR",
                        "details": f"Test error: {str(e)}"
                    })
            
            # Test brute force resistance (simulate dictionary attack)
            try:
                strong_secret = secrets.token_urlsafe(32)
                strong_token = jwt.encode(payload, strong_secret, algorithm="HS256")
                
                # Try to crack with common passwords
                crack_attempts = ["password", "admin", "secret", "123456", "qwerty"]
                cracked = False
                
                for attempt in crack_attempts:
                    try:
                        decoded = jwt.decode(strong_token, attempt, algorithms=["HS256"])
                        cracked = True
                        break
                    except:
                        continue
                
                if cracked:
                    attacks.append({
                        "attack": "Dictionary Attack Resistance",
                        "status": "VULNERABLE",
                        "details": "Strong token cracked with dictionary attack"
                    })
                else:
                    attacks.append({
                        "attack": "Dictionary Attack Resistance",
                        "status": "PROTECTED",
                        "details": "Strong token resisted dictionary attack"
                    })
                    
            except Exception as e:
                attacks.append({
                    "attack": "Dictionary Attack Resistance",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            vulnerable_attacks = [a for a in attacks if a["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_attacks else "PASS",
                "attacks": attacks,
                "vulnerabilities_found": len(vulnerable_attacks),
                "details": f"Tested {len(attacks)} weak secret attacks"
            }
            
            if vulnerable_attacks:
                self.test_results["vulnerabilities"].extend([
                    f"Weak secret vulnerability: {attack['attack']}" 
                    for attack in vulnerable_attacks
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute weak secret tests"
            }
        
        self.test_results["tests"]["weak_secret"] = test_result
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
            vulnerability_penalty = min(len(self.test_results["vulnerabilities"]) * 10, 80)
            
            self.test_results["security_score"] = max(0, base_score - vulnerability_penalty)
    
    def run_penetration_tests(self):
        """Run complete penetration testing suite."""
        print("🛡️ Starting JWT Penetration Testing Suite (Standalone)")
        print("=" * 60)
        
        # Run all tests
        tests = [
            self.test_algorithm_substitution_attack,
            self.test_key_substitution_attack, 
            self.test_token_manipulation_attacks,
            self.test_weak_secret_attacks
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
        print("🎯 PENETRATION TEST RESULTS")
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
        print(f"Vulnerabilities Found: {len(self.test_results['vulnerabilities'])}")
        
        # Show vulnerabilities
        if self.test_results["vulnerabilities"]:
            print("\n🚨 VULNERABILITIES DETECTED:")
            for vuln in self.test_results["vulnerabilities"]:
                print(f"  • {vuln}")
        else:
            print("\n✅ No vulnerabilities detected in JWT implementation")
        
        # Security recommendations
        print("\n💡 SECURITY RECOMMENDATIONS:")
        print("  • Always use RS256 with strong RSA keys (minimum 2048-bit)")
        print("  • Never accept 'alg': 'none' tokens in production")
        print("  • Validate all JWT claims (exp, nbf, iat)")
        print("  • Use strong, random secrets for HMAC algorithms")
        print("  • Implement proper key rotation policies")
        print("  • Monitor for algorithm downgrade attacks")
        
        return self.test_results


def main():
    """Main penetration testing execution."""
    tester = StandaloneJWTPenetrationTester()
    results = tester.run_penetration_tests()
    
    # Save results to file
    output_file = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/JWT_PENETRATION_TEST_RESULTS.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {output_file}")
    
    # Return exit code based on vulnerabilities
    vulnerability_count = len(results["vulnerabilities"])
    if vulnerability_count > 0:
        print(f"\n❌ Penetration testing identified {vulnerability_count} potential issues")
        return 1
    else:
        print("\n✅ Penetration testing completed successfully - JWT library secure")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())