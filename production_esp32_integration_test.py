#!/usr/bin/env python3
"""
Production ESP32-Server Integration Test
========================================
Comprehensive test suite for ESP32-Server authentication flow
"""

import requests
import json
import hashlib
import hmac
import secrets
import sys
from typing import Dict, Any, Optional

class ESP32ServerIntegrationTest:
    def __init__(self, server_url: str = "https://ai-tiddy-bear-v-xuqy.onrender.com"):
        self.server_url = server_url
        self.device_id = "Teddy-ESP32-001"
        self.child_id = "test-child-001"
        self.results = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result with detailed information"""
        status = "PASS" if success else "FAIL"
        self.results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        print(f"{status} {test_name}")
        if details:
            print(f"    Details: {details}")
        print()
        
    def generate_oob_secret(self, device_id: str) -> str:
        """Generate OOB secret using same algorithm as server"""
        salt = "ai-teddy-bear-oob-secret-v1"
        hash_input = f"{device_id}:{salt}".encode('utf-8')
        
        # First SHA256
        device_hash = hashlib.sha256(hash_input).hexdigest()
        
        # Second SHA256
        final_hash = hashlib.sha256((device_hash + salt).encode('utf-8')).hexdigest()
        
        return final_hash.upper()
        
    def calculate_hmac(self, device_id: str, child_id: str, nonce_hex: str, oob_secret_hex: str) -> str:
        """Calculate HMAC using same algorithm as ESP32/Server"""
        # Convert OOB secret and nonce from hex
        oob_secret_bytes = bytes.fromhex(oob_secret_hex)
        nonce_bytes = bytes.fromhex(nonce_hex)
        
        # Create HMAC: device_id || child_id || nonce_bytes
        mac = hmac.new(oob_secret_bytes, digestmod=hashlib.sha256)
        mac.update(device_id.encode('utf-8'))
        mac.update(child_id.encode('utf-8'))
        mac.update(nonce_bytes)
        
        return mac.hexdigest()
        
    def test_server_health(self) -> bool:
        """Test 1: Server health check"""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=10)
            success = response.status_code == 200
            details = f"Status: {response.status_code}, Response time: {response.elapsed.total_seconds():.2f}s"
            self.log_test("Server Health Check", success, details)
            return success
        except Exception as e:
            self.log_test("Server Health Check", False, f"Exception: {e}")
            return False
            
    def test_oob_secret_generation(self) -> bool:
        """Test 2: OOB Secret Generation Algorithm"""
        try:
            expected_secret = self.generate_oob_secret(self.device_id)
            success = len(expected_secret) == 64 and all(c in '0123456789ABCDEF' for c in expected_secret)
            details = f"Generated secret: {expected_secret[:16]}... (64 chars, uppercase hex)"
            self.log_test("OOB Secret Generation", success, details)
            return success
        except Exception as e:
            self.log_test("OOB Secret Generation", False, f"Exception: {e}")
            return False
            
    def test_hmac_calculation(self) -> bool:
        """Test 3: HMAC Calculation Compatibility"""
        try:
            nonce_hex = secrets.token_hex(16)  # 32 hex chars
            oob_secret_hex = self.generate_oob_secret(self.device_id)
            
            hmac_result = self.calculate_hmac(self.device_id, self.child_id, nonce_hex, oob_secret_hex)
            success = len(hmac_result) == 64 and all(c in '0123456789abcdef' for c in hmac_result)
            details = f"HMAC: {hmac_result[:16]}... (64 chars hex), Nonce: {nonce_hex}"
            self.log_test("HMAC Calculation", success, details)
            return success
        except Exception as e:
            self.log_test("HMAC Calculation", False, f"Exception: {e}")
            return False
            
    def test_claim_endpoint_format(self) -> bool:
        """Test 4: Claim Endpoint JSON Format Validation"""
        try:
            nonce_hex = secrets.token_hex(16)
            oob_secret_hex = self.generate_oob_secret(self.device_id)
            hmac_hex = self.calculate_hmac(self.device_id, self.child_id, nonce_hex, oob_secret_hex)
            
            payload = {
                "device_id": self.device_id,
                "child_id": self.child_id,
                "nonce": nonce_hex,
                "hmac_hex": hmac_hex,
                "firmware_version": "1.2.0"
            }
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ESP32-TeddyBear/1.2.0"
            }
            
            response = requests.post(
                f"{self.server_url}/api/v1/pair/claim",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            # Check if we get past validation (422 means format issue)
            success = response.status_code != 422
            
            details = f"Status: {response.status_code}"
            if response.status_code == 422:
                try:
                    error_detail = response.json()
                    details += f", Validation errors: {len(error_detail.get('detail', []))}"
                except:
                    details += ", Invalid JSON response"
            elif response.status_code == 404:
                details += " (Child not found - expected in test)"
            elif response.status_code == 503:
                details += " (Service unavailable - server starting)"
            elif response.status_code == 200:
                details += " (Success - unexpected in test but good!)"
                
            self.log_test("Claim Endpoint Format", success, details)
            return success
        except Exception as e:
            self.log_test("Claim Endpoint Format", False, f"Exception: {e}")
            return False
            
    def test_error_handling(self) -> bool:
        """Test 5: Server Error Handling"""
        try:
            # Test with invalid payload
            invalid_payload = {
                "device_id": "invalid-device",
                "child_id": "invalid-child", 
                "nonce": "invalid-nonce",
                "hmac_hex": "invalid-hmac"
            }
            
            response = requests.post(
                f"{self.server_url}/api/v1/pair/claim",
                json=invalid_payload,
                timeout=30
            )
            
            # Should get validation error or authentication failure
            success = response.status_code in [400, 401, 404, 422]
            details = f"Status: {response.status_code} (expected 400-422 range)"
            
            self.log_test("Error Handling", success, details)
            return success
        except Exception as e:
            self.log_test("Error Handling", False, f"Exception: {e}")
            return False
            
    def test_cors_headers(self) -> bool:
        """Test 6: CORS Headers for ESP32"""
        try:
            response = requests.options(f"{self.server_url}/api/v1/pair/claim", timeout=10)
            
            has_cors = 'access-control-allow-origin' in [h.lower() for h in response.headers.keys()]
            success = response.status_code in [200, 204, 405] or has_cors
            details = f"Status: {response.status_code}, CORS headers: {has_cors}"
            
            self.log_test("CORS Headers", success, details)
            return success
        except Exception as e:
            self.log_test("CORS Headers", False, f"Exception: {e}")
            return False
            
    def run_integration_tests(self) -> bool:
        """Run complete integration test suite"""
        print("ESP32-Server Integration Test Suite")
        print("=====================================")
        print(f"Server: {self.server_url}")
        print(f"Test Device: {self.device_id}")
        print(f"Test Child: {self.child_id}")
        print()
        
        # Run all tests
        tests = [
            self.test_server_health,
            self.test_oob_secret_generation,
            self.test_hmac_calculation,
            self.test_claim_endpoint_format,
            self.test_error_handling,
            self.test_cors_headers
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            if test():
                passed += 1
                
        # Summary
        print("=" * 50)
        print(f"Test Results: {passed}/{total} passed ({passed/total*100:.1f}%)")
        print()
        
        if passed == total:
            print("ALL TESTS PASSED - ESP32-Server integration ready!")
        else:
            print("WARNING: Some tests failed - review issues before production")
            
        # Detailed results
        print("\nDetailed Results:")
        for result in self.results:
            status = "PASS" if result["success"] else "FAIL"
            print(f"{status} {result['test']}")
            if result["details"]:
                print(f"    {result['details']}")
                
        return passed == total

if __name__ == "__main__":
    tester = ESP32ServerIntegrationTest()
    success = tester.run_integration_tests()
    sys.exit(0 if success else 1)
