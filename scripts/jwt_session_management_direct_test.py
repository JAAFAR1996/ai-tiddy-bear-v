#!/usr/bin/env python3
"""
JWT Session Management Direct Testing
====================================
Direct testing of JWT session management functionality without external dependencies.
Tests token revocation, blacklisting, session limits, and security features.
"""

import os
import jwt
import json
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List


class DirectJWTSessionTester:
    """Direct JWT session management testing without external dependencies."""
    
    def __init__(self):
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "test_suite": "JWT Session Management Direct Testing",
            "tests": {},
            "security_score": 0,
            "issues_found": [],
            "passed_tests": 0,
            "total_tests": 0
        }
        
        # Setup test environment
        self.jwt_secret = "test_jwt_secret_for_session_management_testing"
        self.algorithm = "HS256"  # Use HS256 for testing simplicity
        
        # Mock blacklist storage
        self.blacklisted_tokens = set()
        
        # Mock session storage
        self.active_sessions = {}  # user_id -> list of session_info
        self.max_sessions_per_user = 5
    
    def generate_test_token(self, user_id: str, role: str = "user", 
                           device_id: str = None, ip_address: str = None,
                           extra_claims: Dict[str, Any] = None) -> str:
        """Generate test JWT token."""
        now = datetime.now(timezone.utc)
        
        payload = {
            "sub": user_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "jti": f"test_{secrets.token_urlsafe(8)}",
            "role": role,
            "user_type": "parent" if role != "admin" else "admin",
            "device_id": device_id,
            "ip_address": ip_address
        }
        
        if extra_claims:
            payload.update(extra_claims)
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.algorithm)
    
    def verify_test_token(self, token: str, check_blacklist: bool = True) -> Dict[str, Any]:
        """Verify test JWT token."""
        try:
            # Decode token
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.algorithm])
            
            # Check blacklist
            if check_blacklist and payload.get("jti") in self.blacklisted_tokens:
                raise jwt.InvalidTokenError("Token is blacklisted")
            
            return payload
        except Exception as e:
            raise jwt.InvalidTokenError(f"Token verification failed: {str(e)}")
    
    def revoke_token(self, jti: str):
        """Add token to blacklist."""
        self.blacklisted_tokens.add(jti)
    
    def add_session(self, user_id: str, session_info: Dict[str, Any]):
        """Add session to active sessions."""
        if user_id not in self.active_sessions:
            self.active_sessions[user_id] = []
        
        # Add new session
        self.active_sessions[user_id].append(session_info)
        
        # Enforce session limit
        if len(self.active_sessions[user_id]) > self.max_sessions_per_user:
            # Remove oldest session
            oldest_session = self.active_sessions[user_id].pop(0)
            # Revoke oldest session token
            if "jti" in oldest_session:
                self.revoke_token(oldest_session["jti"])
    
    def test_token_revocation_functionality(self) -> bool:
        """Test token revocation functionality."""
        test_name = "Token Revocation Functionality"
        
        try:
            test_cases = []
            
            # Test Case 1: Basic token revocation
            try:
                # Create token
                user_token = self.generate_test_token("revoke_user", "user")
                
                # Verify token works initially
                claims = self.verify_test_token(user_token)
                initial_jti = claims["jti"]
                
                # Revoke token
                self.revoke_token(initial_jti)
                
                # Try to verify revoked token (should fail)
                try:
                    revoked_claims = self.verify_test_token(user_token)
                    test_cases.append({
                        "case": "Basic Token Revocation",
                        "status": "VULNERABLE",
                        "details": "Revoked token still accepted"
                    })
                except:
                    test_cases.append({
                        "case": "Basic Token Revocation", 
                        "status": "PROTECTED",
                        "details": "Revoked token properly rejected"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Basic Token Revocation",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 2: Multiple token revocation
            try:
                tokens = []
                jtis = []
                
                # Create multiple tokens
                for i in range(3):
                    token = self.generate_test_token(f"multi_user_{i}", "user")
                    claims = self.verify_test_token(token)
                    tokens.append(token)
                    jtis.append(claims["jti"])
                
                # Revoke all tokens
                for jti in jtis:
                    self.revoke_token(jti)
                
                # Try to verify all tokens (all should fail)
                all_revoked = True
                for token in tokens:
                    try:
                        self.verify_test_token(token)
                        all_revoked = False
                        break
                    except:
                        continue
                
                if all_revoked:
                    test_cases.append({
                        "case": "Multiple Token Revocation",
                        "status": "PROTECTED",
                        "details": "All tokens properly revoked"
                    })
                else:
                    test_cases.append({
                        "case": "Multiple Token Revocation",
                        "status": "VULNERABLE",
                        "details": "Some tokens still active after revocation"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Multiple Token Revocation",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 3: Blacklist persistence
            try:
                # Create token
                persistent_token = self.generate_test_token("persistent_user", "admin")
                persistent_claims = self.verify_test_token(persistent_token)
                persistent_jti = persistent_claims["jti"]
                
                # Revoke token
                self.revoke_token(persistent_jti)
                
                # Simulate time passing and multiple verification attempts
                attempts_blocked = 0
                for _ in range(5):
                    try:
                        self.verify_test_token(persistent_token)
                    except:
                        attempts_blocked += 1
                
                if attempts_blocked == 5:
                    test_cases.append({
                        "case": "Blacklist Persistence",
                        "status": "PROTECTED", 
                        "details": "Blacklist persistent across multiple attempts"
                    })
                else:
                    test_cases.append({
                        "case": "Blacklist Persistence",
                        "status": "VULNERABLE",
                        "details": f"Blacklist inconsistent: {attempts_blocked}/5 attempts blocked"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Blacklist Persistence",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} token revocation scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["issues_found"].extend([
                    f"Token revocation issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute token revocation tests"
            }
        
        self.test_results["tests"]["token_revocation"] = test_result
        return test_result["status"] == "PASS"
    
    def test_session_limit_enforcement(self) -> bool:
        """Test session limit enforcement."""
        test_name = "Session Limit Enforcement"
        
        try:
            test_cases = []
            user_id = "session_limit_user"
            
            # Test Case 1: Create maximum sessions
            try:
                sessions_created = []
                
                # Create maximum allowed sessions
                for i in range(self.max_sessions_per_user):
                    token = self.generate_test_token(user_id, "user", device_id=f"device_{i}")
                    claims = self.verify_test_token(token)
                    
                    session_info = {
                        "jti": claims["jti"],
                        "token": token,
                        "device_id": f"device_{i}",
                        "created_at": datetime.now().isoformat()
                    }
                    
                    self.add_session(user_id, session_info)
                    sessions_created.append(session_info)
                
                # Verify all sessions are active
                active_count = len(self.active_sessions.get(user_id, []))
                
                if active_count == self.max_sessions_per_user:
                    test_cases.append({
                        "case": "Maximum Sessions Creation",
                        "status": "PASS",
                        "details": f"Successfully created {self.max_sessions_per_user} sessions"
                    })
                else:
                    test_cases.append({
                        "case": "Maximum Sessions Creation",
                        "status": "FAIL",
                        "details": f"Expected {self.max_sessions_per_user}, got {active_count}"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Maximum Sessions Creation",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 2: Exceed session limit
            try:
                # Get first session info for later verification
                first_session = self.active_sessions[user_id][0] if user_id in self.active_sessions else None
                
                # Try to create one more session (should evict oldest)
                overflow_token = self.generate_test_token(user_id, "user", device_id="overflow_device")
                overflow_claims = self.verify_test_token(overflow_token)
                
                overflow_session = {
                    "jti": overflow_claims["jti"],
                    "token": overflow_token,
                    "device_id": "overflow_device",
                    "created_at": datetime.now().isoformat()
                }
                
                self.add_session(user_id, overflow_session)
                
                # Check session count (should still be max)
                current_count = len(self.active_sessions.get(user_id, []))
                
                if current_count <= self.max_sessions_per_user:
                    test_cases.append({
                        "case": "Session Limit Enforcement",
                        "status": "PROTECTED",
                        "details": f"Session limit enforced: {current_count} active sessions"
                    })
                    
                    # Verify oldest session was evicted
                    if first_session:
                        try:
                            self.verify_test_token(first_session["token"])
                            test_cases.append({
                                "case": "Oldest Session Eviction",
                                "status": "VULNERABLE",
                                "details": "Oldest session not evicted when limit exceeded"
                            })
                        except:
                            test_cases.append({
                                "case": "Oldest Session Eviction",
                                "status": "PROTECTED",
                                "details": "Oldest session properly evicted"
                            })
                else:
                    test_cases.append({
                        "case": "Session Limit Enforcement",
                        "status": "VULNERABLE",
                        "details": f"Session limit exceeded: {current_count} active sessions"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Session Limit Enforcement",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            failed_cases = [c for c in test_cases if c["status"] == "FAIL"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if (vulnerable_cases or failed_cases) else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} session management scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["issues_found"].extend([
                    f"Session management issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute session management tests"
            }
        
        self.test_results["tests"]["session_management"] = test_result
        return test_result["status"] == "PASS"
    
    def test_privilege_escalation_detection(self) -> bool:
        """Test privilege escalation detection."""
        test_name = "Privilege Escalation Detection"
        
        try:
            test_cases = []
            
            # Test Case 1: Role tampering detection
            try:
                # Create user token
                user_token = self.generate_test_token("privilege_user", "user")
                
                # Tamper with role in token
                try:
                    header, payload, signature = user_token.split('.')
                    decoded_payload = json.loads(base64.urlsafe_b64decode(payload + '=='))
                    
                    # Modify role to admin
                    decoded_payload['role'] = 'admin'
                    decoded_payload['user_type'] = 'admin'
                    
                    # Re-encode payload
                    tampered_payload = base64.urlsafe_b64encode(
                        json.dumps(decoded_payload).encode()
                    ).decode().rstrip('=')
                    
                    # Create tampered token
                    tampered_token = f"{header}.{tampered_payload}.{signature}"
                    
                    # Try to verify tampered token (should fail due to signature)
                    try:
                        tampered_claims = self.verify_test_token(tampered_token)
                        test_cases.append({
                            "case": "Role Tampering Detection",
                            "status": "VULNERABLE",
                            "details": f"Tampered token accepted with role: {tampered_claims.get('role')}"
                        })
                    except:
                        test_cases.append({
                            "case": "Role Tampering Detection",
                            "status": "PROTECTED",
                            "details": "Tampered token properly rejected"
                        })
                        
                except Exception as e:
                    test_cases.append({
                        "case": "Role Tampering Detection",
                        "status": "ERROR",
                        "details": f"Tampering test error: {str(e)}"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Role Tampering Detection",
                    "status": "ERROR",
                    "details": f"Test setup error: {str(e)}"
                })
            
            # Test Case 2: Expired admin token reuse
            try:
                # Create expired admin token
                now = datetime.now(timezone.utc)
                expired_payload = {
                    "sub": "expired_admin",
                    "iat": int((now - timedelta(hours=2)).timestamp()),
                    "exp": int((now - timedelta(hours=1)).timestamp()),  # Expired
                    "jti": f"expired_{secrets.token_urlsafe(8)}",
                    "role": "admin",
                    "user_type": "admin"
                }
                
                expired_token = jwt.encode(expired_payload, self.jwt_secret, algorithm=self.algorithm)
                
                # Try to verify expired admin token
                try:
                    expired_claims = self.verify_test_token(expired_token)
                    test_cases.append({
                        "case": "Expired Admin Token Reuse",
                        "status": "VULNERABLE",
                        "details": "Expired admin token still accepted"
                    })
                except jwt.ExpiredSignatureError:
                    test_cases.append({
                        "case": "Expired Admin Token Reuse",
                        "status": "PROTECTED",
                        "details": "Expired admin token properly rejected"
                    })
                except Exception as e:
                    test_cases.append({
                        "case": "Expired Admin Token Reuse",
                        "status": "PROTECTED",
                        "details": f"Expired token rejected: {str(e)}"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Expired Admin Token Reuse",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 3: Cross-user token impersonation
            try:
                # Create tokens for two different users
                user1_token = self.generate_test_token("user_1", "user")
                user2_token = self.generate_test_token("user_2", "admin")
                
                # Verify each token with correct user context
                user1_claims = self.verify_test_token(user1_token)
                user2_claims = self.verify_test_token(user2_token)
                
                # Check that user IDs are correctly bound
                if user1_claims["sub"] == "user_1" and user2_claims["sub"] == "user_2":
                    test_cases.append({
                        "case": "Cross-User Token Binding",
                        "status": "PROTECTED",
                        "details": "User tokens properly bound to correct users"
                    })
                else:
                    test_cases.append({
                        "case": "Cross-User Token Binding",
                        "status": "VULNERABLE",
                        "details": "User token binding issue detected"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Cross-User Token Binding",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} privilege escalation scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["issues_found"].extend([
                    f"Privilege escalation issue: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute privilege escalation tests"
            }
        
        self.test_results["tests"]["privilege_escalation"] = test_result
        return test_result["status"] == "PASS"
    
    def test_device_fingerprinting_simulation(self) -> bool:
        """Test device fingerprinting simulation."""
        test_name = "Device Fingerprinting Simulation"
        
        try:
            test_cases = []
            
            # Test Case 1: Device binding verification
            try:
                device_id = "trusted_device_123"
                
                # Create token with device binding
                device_token = self.generate_test_token(
                    "device_user", "user", 
                    device_id=device_id,
                    ip_address="192.168.1.100"
                )
                
                # Verify token contains device info
                claims = self.verify_test_token(device_token)
                
                if claims.get("device_id") == device_id:
                    test_cases.append({
                        "case": "Device ID Binding",
                        "status": "PASS",
                        "details": f"Token properly bound to device: {device_id}"
                    })
                else:
                    test_cases.append({
                        "case": "Device ID Binding",
                        "status": "FAIL",
                        "details": "Device ID not properly bound to token"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Device ID Binding",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 2: IP address tracking
            try:
                original_ip = "192.168.1.50"
                different_ip = "10.0.0.50"
                
                # Create token with IP tracking
                ip_token = self.generate_test_token(
                    "ip_user", "user",
                    ip_address=original_ip
                )
                
                claims = self.verify_test_token(ip_token)
                
                # Verify IP is recorded in token
                if claims.get("ip_address") == original_ip:
                    test_cases.append({
                        "case": "IP Address Tracking",
                        "status": "PASS",
                        "details": f"IP address properly tracked: {original_ip}"
                    })
                else:
                    test_cases.append({
                        "case": "IP Address Tracking",
                        "status": "FAIL",
                        "details": "IP address not properly tracked in token"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "IP Address Tracking",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 3: Device fingerprint generation consistency
            try:
                # Simulate device info
                device_info_1 = {
                    "user_agent": "Mozilla/5.0 (Test Browser)",
                    "platform": "TestOS",
                    "screen_resolution": "1920x1080"
                }
                
                device_info_2 = device_info_1.copy()  # Same device
                device_info_3 = device_info_1.copy()
                device_info_3["user_agent"] = "Different Browser"  # Different device
                
                # Generate fingerprints
                def generate_fingerprint(device_info):
                    fingerprint_data = ""
                    for key in sorted(device_info.keys()):
                        fingerprint_data += str(device_info[key])
                    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
                
                fp1 = generate_fingerprint(device_info_1)
                fp2 = generate_fingerprint(device_info_2)
                fp3 = generate_fingerprint(device_info_3)
                
                # Same device should produce same fingerprint
                if fp1 == fp2 and fp1 != fp3:
                    test_cases.append({
                        "case": "Device Fingerprint Consistency",
                        "status": "PASS",
                        "details": "Device fingerprints consistent and unique"
                    })
                else:
                    test_cases.append({
                        "case": "Device Fingerprint Consistency",
                        "status": "FAIL",
                        "details": f"Fingerprint inconsistency: {fp1} vs {fp2} vs {fp3}"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Device Fingerprint Consistency",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            failed_cases = [c for c in test_cases if c["status"] == "FAIL"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if failed_cases else "PASS",
                "test_cases": test_cases,
                "failed_tests": len(failed_cases),
                "details": f"Tested {len(test_cases)} device fingerprinting scenarios"
            }
            
            if failed_cases:
                self.test_results["issues_found"].extend([
                    f"Device fingerprinting issue: {case['case']}" 
                    for case in failed_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute device fingerprinting tests"
            }
        
        self.test_results["tests"]["device_fingerprinting"] = test_result
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
            
            # Deduct points for issues
            issue_penalty = min(len(self.test_results["issues_found"]) * 10, 80)
            
            self.test_results["security_score"] = max(0, base_score - issue_penalty)
    
    def run_all_tests(self):
        """Run complete JWT session management testing suite."""
        print("🔒 Starting JWT Session Management Direct Testing")
        print("=" * 60)
        
        # Run all tests
        tests = [
            self.test_token_revocation_functionality,
            self.test_session_limit_enforcement,
            self.test_privilege_escalation_detection,
            self.test_device_fingerprinting_simulation
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
        print("🎯 SESSION MANAGEMENT TEST RESULTS")
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
        print(f"Issues Found: {len(self.test_results['issues_found'])}")
        
        # Show issues
        if self.test_results["issues_found"]:
            print("\n🚨 ISSUES DETECTED:")
            for issue in self.test_results["issues_found"]:
                print(f"  • {issue}")
        else:
            print("\n✅ No security issues detected in session management")
        
        # Security recommendations
        print("\n💡 SESSION SECURITY RECOMMENDATIONS:")
        print("  • Implement server-side token blacklisting with Redis/database")
        print("  • Enforce maximum active sessions per user (recommended: 5)")
        print("  • Bind tokens to device fingerprints for enhanced security")
        print("  • Track IP addresses for suspicious activity detection")
        print("  • Implement automatic token revocation on role changes")
        print("  • Use short-lived access tokens with secure refresh mechanism")
        
        return self.test_results


def main():
    """Main testing execution."""
    tester = DirectJWTSessionTester()
    results = tester.run_all_tests()
    
    # Save results to file
    output_file = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/JWT_SESSION_DIRECT_TEST_RESULTS.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {output_file}")
    
    # Return exit code based on issues
    issue_count = len(results["issues_found"])
    if issue_count > 0:
        print(f"\n⚠️ Session management testing found {issue_count} implementation issues")
        return 1
    else:
        print("\n✅ Session management concepts validated successfully")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())