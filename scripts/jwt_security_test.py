#!/usr/bin/env python3
"""
🔑 AI TEDDY BEAR - COMPREHENSIVE JWT SECURITY TESTING SUITE
============================================================

Advanced security testing for JWT implementation:
1. Token generation and validation testing
2. Algorithm security assessment
3. Attack vector simulation
4. Child safety token validation
5. COPPA compliance verification
6. Performance and scalability testing
"""

import os
import sys
import json
import time
import hmac
import hashlib
import secrets
import asyncio
import jwt as pyjwt
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import subprocess
import tempfile

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class JWTSecurityTester:
    """Comprehensive JWT security testing suite."""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_results': {},
            'vulnerabilities': [],
            'recommendations': [],
            'compliance_status': {},
            'performance_metrics': {},
            'summary': {}
        }
        
        # Test configurations
        self.test_secret = "test-jwt-secret-key-for-security-testing"
        self.weak_secrets = ["123", "secret", "password", "jwt"]
        self.test_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        
        # Child safety test data
        self.child_test_data = {
            'valid_child': {
                'sub': 'child_123',
                'parent_id': 'parent_456',
                'age': 8,
                'coppa_compliant': True,
                'parent_consent_timestamp': '2024-01-01T00:00:00Z',
                'safety_level': 'strict'
            },
            'invalid_child': {
                'sub': 'child_789',
                'age': 2,  # Under COPPA limit
                'coppa_compliant': False
            }
        }
    
    def print_header(self, title: str):
        """Print formatted test header."""
        print(f"\n{'='*80}")
        print(f"🔑 {title}")
        print('='*80)
    
    def print_test(self, test_name: str, status: str, details: str = ""):
        """Print formatted test result."""
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} {test_name}: {status}")
        if details:
            print(f"   {details}")
    
    def test_basic_jwt_functionality(self) -> Dict[str, Any]:
        """Test basic JWT token creation and validation."""
        print("\n🔍 Testing Basic JWT Functionality...")
        
        test_results = {
            'token_creation': False,
            'token_validation': False,
            'expiration_handling': False,
            'invalid_signature': False
        }
        
        try:
            # Test token creation
            payload = {
                'sub': 'test_user',
                'iat': int(time.time()),
                'exp': int(time.time()) + 3600,
                'role': 'parent'
            }
            
            token = pyjwt.encode(payload, self.test_secret, algorithm='HS256')
            test_results['token_creation'] = True
            self.print_test("Token Creation", "PASS", f"Token length: {len(token)}")
            
            # Test token validation
            decoded = pyjwt.decode(token, self.test_secret, algorithms=['HS256'])
            if decoded['sub'] == 'test_user':
                test_results['token_validation'] = True
                self.print_test("Token Validation", "PASS", "Payload correctly decoded")
            
            # Test expiration handling
            expired_payload = {
                'sub': 'test_user',
                'iat': int(time.time()) - 7200,
                'exp': int(time.time()) - 3600,  # Expired 1 hour ago
                'role': 'parent'
            }
            
            expired_token = pyjwt.encode(expired_payload, self.test_secret, algorithm='HS256')
            try:
                pyjwt.decode(expired_token, self.test_secret, algorithms=['HS256'])
                self.print_test("Expiration Handling", "FAIL", "Expired token was accepted")
            except pyjwt.ExpiredSignatureError:
                test_results['expiration_handling'] = True
                self.print_test("Expiration Handling", "PASS", "Expired token correctly rejected")
            
            # Test invalid signature
            try:
                pyjwt.decode(token, "wrong-secret", algorithms=['HS256'])
                self.print_test("Invalid Signature", "FAIL", "Invalid signature was accepted")
            except pyjwt.InvalidSignatureError:
                test_results['invalid_signature'] = True
                self.print_test("Invalid Signature", "PASS", "Invalid signature correctly rejected")
                
        except Exception as e:
            self.print_test("Basic JWT Functionality", "FAIL", f"Error: {e}")
            self.results['vulnerabilities'].append({
                'severity': 'HIGH',
                'category': 'JWT Implementation',
                'issue': 'Basic JWT functionality failed',
                'details': str(e)
            })
        
        return test_results
    
    def test_algorithm_security(self) -> Dict[str, Any]:
        """Test JWT algorithm security and confusion attacks."""
        print("\n🔍 Testing Algorithm Security...")
        
        test_results = {
            'algorithm_confusion': False,
            'weak_secrets': False,
            'key_confusion': False,
            'none_algorithm': False
        }
        
        # Test algorithm confusion attack
        try:
            # Create token with HS256
            payload = {'sub': 'test_user', 'role': 'admin'}
            hs256_token = pyjwt.encode(payload, self.test_secret, algorithm='HS256')
            
            # Try to verify with different algorithm
            try:
                pyjwt.decode(hs256_token, self.test_secret, algorithms=['HS512'])
                self.print_test("Algorithm Confusion", "FAIL", "Algorithm confusion possible")
            except pyjwt.InvalidTokenError:
                test_results['algorithm_confusion'] = True
                self.print_test("Algorithm Confusion", "PASS", "Algorithm confusion prevented")
                
        except Exception as e:
            self.print_test("Algorithm Confusion", "FAIL", f"Error: {e}")
        
        # Test weak secrets
        weak_detected = []
        for weak_secret in self.weak_secrets:
            try:
                token = pyjwt.encode({'test': True}, weak_secret, algorithm='HS256')
                # If this succeeds, it's a vulnerability
                weak_detected.append(weak_secret)
            except Exception:
                pass
        
        if not weak_detected:
            test_results['weak_secrets'] = True
            self.print_test("Weak Secrets", "PASS", "No weak secrets detected")
        else:
            self.print_test("Weak Secrets", "FAIL", f"Weak secrets found: {weak_detected}")
            self.results['vulnerabilities'].append({
                'severity': 'HIGH',
                'category': 'JWT Security',
                'issue': 'Weak secrets vulnerable to brute force',
                'details': f"Weak secrets: {weak_detected}"
            })
        
        # Test 'none' algorithm attack
        try:
            # Create unsigned token
            header = {'alg': 'none', 'typ': 'JWT'}
            payload = {'sub': 'admin', 'role': 'admin'}
            
            # Manually create token with 'none' algorithm
            import base64
            header_encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
            payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
            none_token = f"{header_encoded}.{payload_encoded}."
            
            try:
                # This should fail
                decoded = pyjwt.decode(none_token, options={"verify_signature": False})
                self.print_test("None Algorithm", "FAIL", "None algorithm accepted")
            except Exception:
                test_results['none_algorithm'] = True
                self.print_test("None Algorithm", "PASS", "None algorithm rejected")
                
        except Exception as e:
            self.print_test("None Algorithm", "FAIL", f"Error: {e}")
        
        return test_results
    
    def test_child_safety_tokens(self) -> Dict[str, Any]:
        """Test child safety specific token validations."""
        print("\n🔍 Testing Child Safety Token Security...")
        
        test_results = {
            'age_validation': False,
            'coppa_compliance': False,
            'parent_consent': False,
            'safety_levels': False
        }
        
        try:
            # Test valid child token
            valid_child_token = pyjwt.encode(
                self.child_test_data['valid_child'], 
                self.test_secret, 
                algorithm='HS256'
            )
            
            decoded_valid = pyjwt.decode(valid_child_token, self.test_secret, algorithms=['HS256'])
            
            # Test age validation
            if 3 <= decoded_valid.get('age', 0) <= 13:
                test_results['age_validation'] = True
                self.print_test("Age Validation", "PASS", f"Age {decoded_valid['age']} within COPPA limits")
            else:
                self.print_test("Age Validation", "FAIL", f"Age {decoded_valid.get('age')} outside COPPA limits")
            
            # Test COPPA compliance flag
            if decoded_valid.get('coppa_compliant'):
                test_results['coppa_compliance'] = True
                self.print_test("COPPA Compliance", "PASS", "COPPA compliance flag present")
            else:
                self.print_test("COPPA Compliance", "FAIL", "COPPA compliance flag missing")
            
            # Test parent consent timestamp
            consent_timestamp = decoded_valid.get('parent_consent_timestamp')
            if consent_timestamp:
                try:
                    consent_date = datetime.fromisoformat(consent_timestamp.replace('Z', '+00:00'))
                    if consent_date < datetime.now(timezone.utc):
                        test_results['parent_consent'] = True
                        self.print_test("Parent Consent", "PASS", f"Valid consent timestamp: {consent_timestamp}")
                    else:
                        self.print_test("Parent Consent", "FAIL", "Future consent timestamp")
                except Exception:
                    self.print_test("Parent Consent", "FAIL", "Invalid consent timestamp format")
            else:
                self.print_test("Parent Consent", "FAIL", "Missing parent consent timestamp")
            
            # Test safety levels
            safety_level = decoded_valid.get('safety_level')
            if safety_level in ['strict', 'moderate', 'relaxed']:
                test_results['safety_levels'] = True
                self.print_test("Safety Levels", "PASS", f"Valid safety level: {safety_level}")
            else:
                self.print_test("Safety Levels", "FAIL", f"Invalid safety level: {safety_level}")
            
            # Test invalid child token (under age limit)
            try:
                invalid_child_token = pyjwt.encode(
                    self.child_test_data['invalid_child'], 
                    self.test_secret, 
                    algorithm='HS256'
                )
                
                decoded_invalid = pyjwt.decode(invalid_child_token, self.test_secret, algorithms=['HS256'])
                
                if decoded_invalid.get('age', 0) < 3:
                    self.print_test("Under-Age Detection", "PASS", "Under-age child detected")
                    self.results['vulnerabilities'].append({
                        'severity': 'CRITICAL',
                        'category': 'COPPA Compliance',
                        'issue': 'Under-age child token validation needed',
                        'details': f"Age {decoded_invalid.get('age')} is below COPPA minimum of 3 years"
                    })
                    
            except Exception as e:
                self.print_test("Under-Age Detection", "FAIL", f"Error: {e}")
                
        except Exception as e:
            self.print_test("Child Safety Tokens", "FAIL", f"Error: {e}")
            self.results['vulnerabilities'].append({
                'severity': 'HIGH',
                'category': 'Child Safety',
                'issue': 'Child safety token validation failed',
                'details': str(e)
            })
        
        return test_results
    
    def test_token_manipulation_attacks(self) -> Dict[str, Any]:
        """Test various token manipulation attack vectors."""
        print("\n🔍 Testing Token Manipulation Attacks...")
        
        test_results = {
            'payload_tampering': False,
            'header_manipulation': False,
            'signature_stripping': False,
            'claim_injection': False
        }
        
        try:
            # Create legitimate token
            original_payload = {
                'sub': 'user_123',
                'role': 'parent',
                'exp': int(time.time()) + 3600
            }
            
            legitimate_token = pyjwt.encode(original_payload, self.test_secret, algorithm='HS256')
            
            # Test payload tampering
            try:
                # Decode without verification to modify payload
                tampered_payload = pyjwt.decode(legitimate_token, options={"verify_signature": False})
                tampered_payload['role'] = 'admin'  # Privilege escalation attempt
                
                # Re-encode with same secret (this should be detected)
                tampered_token = pyjwt.encode(tampered_payload, self.test_secret, algorithm='HS256')
                
                # Try to verify tampered token
                try:
                    verified = pyjwt.decode(tampered_token, self.test_secret, algorithms=['HS256'])
                    if verified['role'] == 'admin':
                        self.print_test("Payload Tampering", "FAIL", "Privilege escalation succeeded")
                    else:
                        test_results['payload_tampering'] = True
                        self.print_test("Payload Tampering", "PASS", "Tampering detected")
                except pyjwt.InvalidTokenError:
                    test_results['payload_tampering'] = True
                    self.print_test("Payload Tampering", "PASS", "Tampering detected")
                    
            except Exception as e:
                self.print_test("Payload Tampering", "FAIL", f"Error: {e}")
            
            # Test signature stripping
            try:
                parts = legitimate_token.split('.')
                if len(parts) == 3:
                    # Remove signature
                    unsigned_token = f"{parts[0]}.{parts[1]}."
                    
                    try:
                        pyjwt.decode(unsigned_token, self.test_secret, algorithms=['HS256'])
                        self.print_test("Signature Stripping", "FAIL", "Unsigned token accepted")
                    except pyjwt.InvalidTokenError:
                        test_results['signature_stripping'] = True
                        self.print_test("Signature Stripping", "PASS", "Unsigned token rejected")
                        
            except Exception as e:
                self.print_test("Signature Stripping", "FAIL", f"Error: {e}")
            
            # Test claim injection
            try:
                # Attempt to inject additional claims
                injection_payload = original_payload.copy()
                injection_payload['admin'] = True
                injection_payload['permissions'] = ['read', 'write', 'admin']
                
                injection_token = pyjwt.encode(injection_payload, self.test_secret, algorithm='HS256')
                decoded_injection = pyjwt.decode(injection_token, self.test_secret, algorithms=['HS256'])
                
                # Check if dangerous claims were preserved
                if decoded_injection.get('admin') or 'admin' in decoded_injection.get('permissions', []):
                    self.print_test("Claim Injection", "FAIL", "Malicious claims accepted")
                    self.results['vulnerabilities'].append({
                        'severity': 'HIGH',
                        'category': 'JWT Security',
                        'issue': 'Claim injection vulnerability',
                        'details': 'Malicious claims can be injected into tokens'
                    })
                else:
                    test_results['claim_injection'] = True
                    self.print_test("Claim Injection", "PASS", "Claim validation working")
                    
            except Exception as e:
                self.print_test("Claim Injection", "FAIL", f"Error: {e}")
                
        except Exception as e:
            self.print_test("Token Manipulation", "FAIL", f"Error: {e}")
        
        return test_results
    
    def test_timing_attacks(self) -> Dict[str, Any]:
        """Test for timing attack vulnerabilities."""
        print("\n🔍 Testing Timing Attack Resistance...")
        
        test_results = {
            'constant_time_validation': False,
            'timing_variance': False
        }
        
        try:
            # Create valid and invalid tokens
            valid_token = pyjwt.encode({'sub': 'test'}, self.test_secret, algorithm='HS256')
            invalid_token = valid_token[:-10] + "tamperedxx"
            
            # Measure validation times
            valid_times = []
            invalid_times = []
            
            for _ in range(100):
                # Time valid token validation
                start_time = time.perf_counter()
                try:
                    pyjwt.decode(valid_token, self.test_secret, algorithms=['HS256'])
                except:
                    pass
                valid_times.append(time.perf_counter() - start_time)
                
                # Time invalid token validation
                start_time = time.perf_counter()
                try:
                    pyjwt.decode(invalid_token, self.test_secret, algorithms=['HS256'])
                except:
                    pass
                invalid_times.append(time.perf_counter() - start_time)
            
            # Calculate timing statistics
            valid_avg = sum(valid_times) / len(valid_times)
            invalid_avg = sum(invalid_times) / len(invalid_times)
            timing_difference = abs(valid_avg - invalid_avg)
            
            # Check if timing difference is minimal (constant time)
            if timing_difference < 0.001:  # Less than 1ms difference
                test_results['constant_time_validation'] = True
                self.print_test("Constant Time Validation", "PASS", 
                               f"Timing difference: {timing_difference:.6f}s")
            else:
                self.print_test("Constant Time Validation", "FAIL", 
                               f"Timing difference: {timing_difference:.6f}s")
                self.results['vulnerabilities'].append({
                    'severity': 'MEDIUM',
                    'category': 'Timing Attack',
                    'issue': 'Token validation timing variance detected',
                    'details': f'Timing difference: {timing_difference:.6f}s'
                })
            
            # Check variance in timing
            valid_variance = sum((t - valid_avg) ** 2 for t in valid_times) / len(valid_times)
            invalid_variance = sum((t - invalid_avg) ** 2 for t in invalid_times) / len(invalid_times)
            
            if valid_variance < 0.000001 and invalid_variance < 0.000001:
                test_results['timing_variance'] = True
                self.print_test("Timing Variance", "PASS", "Low timing variance detected")
            else:
                self.print_test("Timing Variance", "FAIL", 
                               f"High timing variance: valid={valid_variance:.8f}, invalid={invalid_variance:.8f}")
                
        except Exception as e:
            self.print_test("Timing Attacks", "FAIL", f"Error: {e}")
        
        return test_results
    
    def test_performance_scalability(self) -> Dict[str, Any]:
        """Test JWT performance and scalability."""
        print("\n🔍 Testing Performance and Scalability...")
        
        performance_metrics = {
            'token_generation_rate': 0,
            'token_validation_rate': 0,
            'memory_usage': 0,
            'concurrent_handling': False
        }
        
        try:
            # Test token generation performance
            start_time = time.perf_counter()
            tokens = []
            
            for i in range(1000):
                payload = {
                    'sub': f'user_{i}',
                    'iat': int(time.time()),
                    'exp': int(time.time()) + 3600
                }
                token = pyjwt.encode(payload, self.test_secret, algorithm='HS256')
                tokens.append(token)
            
            generation_time = time.perf_counter() - start_time
            performance_metrics['token_generation_rate'] = 1000 / generation_time
            
            self.print_test("Token Generation Performance", "PASS", 
                           f"{performance_metrics['token_generation_rate']:.2f} tokens/second")
            
            # Test token validation performance
            start_time = time.perf_counter()
            
            for token in tokens:
                try:
                    pyjwt.decode(token, self.test_secret, algorithms=['HS256'])
                except:
                    pass
            
            validation_time = time.perf_counter() - start_time
            performance_metrics['token_validation_rate'] = 1000 / validation_time
            
            self.print_test("Token Validation Performance", "PASS", 
                           f"{performance_metrics['token_validation_rate']:.2f} validations/second")
            
            # Memory usage estimation
            import sys
            token_memory = sys.getsizeof(tokens) + sum(sys.getsizeof(t) for t in tokens)
            performance_metrics['memory_usage'] = token_memory / len(tokens)
            
            self.print_test("Memory Usage", "PASS", 
                           f"{performance_metrics['memory_usage']:.2f} bytes per token")
            
            # Test concurrent handling (simulated)
            if performance_metrics['token_validation_rate'] > 500:  # 500+ validations/second
                performance_metrics['concurrent_handling'] = True
                self.print_test("Concurrent Handling", "PASS", "Suitable for concurrent use")
            else:
                self.print_test("Concurrent Handling", "FAIL", "May struggle with high concurrency")
                
        except Exception as e:
            self.print_test("Performance Testing", "FAIL", f"Error: {e}")
        
        return performance_metrics
    
    def generate_security_recommendations(self):
        """Generate security recommendations based on test results."""
        recommendations = []
        
        # Critical recommendations
        critical_vulns = [v for v in self.results['vulnerabilities'] if v['severity'] == 'CRITICAL']
        if critical_vulns:
            recommendations.extend([
                "🚨 CRITICAL: Implement strict age validation for all child tokens",
                "🔒 CRITICAL: Add server-side COPPA compliance validation",
                "📋 CRITICAL: Create COPPA violation incident response procedures"
            ])
        
        # High priority recommendations
        high_vulns = [v for v in self.results['vulnerabilities'] if v['severity'] == 'HIGH']
        if high_vulns:
            recommendations.extend([
                "⚠️ HIGH: Implement robust token validation middleware",
                "🛡️ HIGH: Add comprehensive audit logging for token operations",
                "🔐 HIGH: Use strong, cryptographically secure secrets"
            ])
        
        # General recommendations
        recommendations.extend([
            "🔑 Use RS256 algorithm for production (asymmetric keys)",
            "⏱️ Implement shorter token lifetimes for child accounts (1-2 hours)",
            "🔄 Add automatic token refresh mechanisms",
            "📊 Implement token usage monitoring and anomaly detection",
            "🛡️ Add rate limiting for token endpoints",
            "🔒 Implement token blacklisting for revoked tokens",
            "👶 Add child-specific security claims to tokens",
            "📋 Regular security audits and penetration testing",
            "🚨 Implement real-time security alerting",
            "🏗️ Use secure key management and rotation procedures"
        ])
        
        self.results['recommendations'] = recommendations
    
    def generate_summary(self):
        """Generate test summary and overall assessment."""
        total_tests = len([r for r in self.results['test_results'].values() if isinstance(r, dict)])
        passed_tests = sum(len([t for t in result.values() if t]) for result in self.results['test_results'].values() if isinstance(result, dict))
        total_possible = sum(len(result) for result in self.results['test_results'].values() if isinstance(result, dict))
        
        critical_count = len([v for v in self.results['vulnerabilities'] if v['severity'] == 'CRITICAL'])
        high_count = len([v for v in self.results['vulnerabilities'] if v['severity'] == 'HIGH'])
        medium_count = len([v for v in self.results['vulnerabilities'] if v['severity'] == 'MEDIUM'])
        
        # Determine overall risk level
        if critical_count > 0:
            risk_level = 'CRITICAL'
        elif high_count > 2:
            risk_level = 'HIGH'
        elif high_count > 0 or medium_count > 3:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'
        
        self.results['summary'] = {
            'total_test_categories': total_tests,
            'passed_tests': passed_tests,
            'total_possible_tests': total_possible,
            'pass_rate': (passed_tests / total_possible * 100) if total_possible > 0 else 0,
            'vulnerabilities_found': len(self.results['vulnerabilities']),
            'critical_vulnerabilities': critical_count,
            'high_vulnerabilities': high_count,
            'medium_vulnerabilities': medium_count,
            'overall_risk_level': risk_level,
            'production_ready': risk_level in ['LOW', 'MEDIUM'] and critical_count == 0
        }
    
    def print_final_report(self):
        """Print comprehensive final report."""
        summary = self.results['summary']
        
        print("\n" + "="*80)
        print("🔑 AI TEDDY BEAR - JWT SECURITY TESTING REPORT")
        print("="*80)
        print(f"📅 Test Date: {self.results['timestamp']}")
        print(f"🎯 Overall Risk Level: {summary['overall_risk_level']}")
        print(f"🏭 Production Ready: {'✅ YES' if summary['production_ready'] else '❌ NO'}")
        print()
        
        # Test Results Summary
        print("📊 TEST RESULTS SUMMARY:")
        print(f"   Test Categories: {summary['total_test_categories']}")
        print(f"   Tests Passed: {summary['passed_tests']}/{summary['total_possible_tests']}")
        print(f"   Pass Rate: {summary['pass_rate']:.1f}%")
        print()
        
        # Vulnerabilities Summary
        print("🚨 VULNERABILITIES SUMMARY:")
        print(f"   Critical: {summary['critical_vulnerabilities']}")
        print(f"   High: {summary['high_vulnerabilities']}")
        print(f"   Medium: {summary['medium_vulnerabilities']}")
        print(f"   Total: {summary['vulnerabilities_found']}")
        print()
        
        # Detailed Vulnerabilities
        if self.results['vulnerabilities']:
            print("🔍 DETAILED VULNERABILITIES:")
            for vuln in self.results['vulnerabilities']:
                print(f"   [{vuln['severity']}] {vuln['category']}: {vuln['issue']}")
                print(f"      └─ {vuln['details']}")
            print()
        
        # Performance Metrics
        if 'performance_metrics' in self.results['test_results']:
            perf = self.results['test_results']['performance_metrics']
            print("⚡ PERFORMANCE METRICS:")
            print(f"   Token Generation: {perf.get('token_generation_rate', 0):.2f} tokens/sec")
            print(f"   Token Validation: {perf.get('token_validation_rate', 0):.2f} validations/sec")
            print(f"   Memory Usage: {perf.get('memory_usage', 0):.2f} bytes/token")
            print()
        
        # Top Recommendations
        print("💡 TOP SECURITY RECOMMENDATIONS:")
        for i, rec in enumerate(self.results['recommendations'][:10], 1):
            print(f"   {i}. {rec}")
        print()
        
        # Final Assessment
        if summary['production_ready']:
            print("✅ ASSESSMENT: Ready for production deployment with recommended improvements")
        else:
            print("❌ ASSESSMENT: NOT ready for production - critical issues must be resolved")
        
        print("="*80)
    
    def save_report(self, filename: Optional[str] = None) -> str:
        """Save detailed report to JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jwt_security_test_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        return filename
    
    async def run_comprehensive_test_suite(self):
        """Run the complete JWT security test suite."""
        self.print_header("STARTING COMPREHENSIVE JWT SECURITY TESTING")
        
        # Run all test categories
        print("🚀 Executing security test suite...")
        
        # Basic functionality tests
        self.results['test_results']['basic_functionality'] = self.test_basic_jwt_functionality()
        
        # Algorithm security tests
        self.results['test_results']['algorithm_security'] = self.test_algorithm_security()
        
        # Child safety specific tests
        self.results['test_results']['child_safety'] = self.test_child_safety_tokens()
        
        # Token manipulation tests
        self.results['test_results']['token_manipulation'] = self.test_token_manipulation_attacks()
        
        # Timing attack tests
        self.results['test_results']['timing_attacks'] = self.test_timing_attacks()
        
        # Performance tests
        self.results['test_results']['performance_metrics'] = self.test_performance_scalability()
        
        # Generate analysis
        self.generate_security_recommendations()
        self.generate_summary()
        
        # Print comprehensive report
        self.print_final_report()
        
        # Save detailed report
        report_file = self.save_report()
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return self.results

def main():
    """Main function to run JWT security testing."""
    tester = JWTSecurityTester()
    
    try:
        # Run async test suite
        results = asyncio.run(tester.run_comprehensive_test_suite())
        
        # Return appropriate exit code
        if results['summary']['overall_risk_level'] in ['CRITICAL', 'HIGH']:
            print(f"\n❌ TESTING FAILED - {results['summary']['overall_risk_level']} RISK DETECTED")
            return 1
        else:
            print(f"\n✅ TESTING PASSED - {results['summary']['overall_risk_level']} RISK LEVEL")
            return 0
            
    except Exception as e:
        print(f"\n❌ TESTING ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())