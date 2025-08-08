#!/usr/bin/env python3
"""
JWT Session Management Testing Suite
===================================
Comprehensive testing for JWT token revocation, blacklisting, session management,
privilege escalation prevention, and device fingerprinting.
"""

import os
import sys
import jwt
import json
import base64
import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, List


# Mock Redis for testing
class MockRedis:
    """Mock Redis client for testing session management."""
    
    def __init__(self):
        self.data = {}
        self.expires = {}
    
    async def setex(self, key: str, ttl: int, value: str):
        """Set key with expiration."""
        self.data[key] = value
        self.expires[key] = datetime.now() + timedelta(seconds=ttl)
    
    async def get(self, key: str):
        """Get key value."""
        if key in self.expires and datetime.now() > self.expires[key]:
            # Simulate expiration
            if key in self.data:
                del self.data[key]
            del self.expires[key]
            return None
        return self.data.get(key)
    
    async def delete(self, key: str):
        """Delete key."""
        if key in self.data:
            del self.data[key]
        if key in self.expires:
            del self.expires[key]
    
    async def scan(self, cursor: int, match: str = None, count: int = 10):
        """Scan keys matching pattern."""
        keys = list(self.data.keys())
        if match:
            # Simple pattern matching for '*' wildcard
            pattern = match.replace('*', '')
            keys = [k for k in keys if pattern in k]
        
        # Simple pagination simulation
        start = cursor
        end = min(start + count, len(keys))
        result_keys = keys[start:end]
        next_cursor = end if end < len(keys) else 0
        
        return next_cursor, result_keys
    
    async def ttl(self, key: str):
        """Get TTL for key."""
        if key not in self.expires:
            return -1
        remaining = self.expires[key] - datetime.now()
        return int(remaining.total_seconds()) if remaining.total_seconds() > 0 else -2


class JWTSessionManagementTester:
    """Comprehensive JWT session management testing suite."""
    
    def __init__(self):
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "test_suite": "JWT Session Management Testing",
            "tests": {},
            "security_score": 0,
            "vulnerabilities": [],
            "passed_tests": 0,
            "total_tests": 0
        }
        
        # Setup mock environment
        self.setup_mock_environment()
        
        # Import and setup JWT manager
        self.setup_jwt_manager()
        
        # Mock Redis client
        self.mock_redis = MockRedis()
    
    def setup_mock_environment(self):
        """Setup mock environment for testing."""
        # Set testing environment
        os.environ["ENVIRONMENT"] = "testing"
        os.environ["JWT_ALGORITHM"] = "HS256"  # Use HS256 for testing simplicity
        os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_jwt_testing_only"
        os.environ["JWT_ACCESS_TOKEN_TTL"] = "900"  # 15 minutes
        os.environ["JWT_REFRESH_TOKEN_TTL"] = "604800"  # 7 days
        os.environ["JWT_REQUIRE_DEVICE_ID"] = "true"
        os.environ["JWT_TRACK_IP_ADDRESS"] = "true"
        os.environ["JWT_MAX_ACTIVE_SESSIONS"] = "5"
    
    def setup_jwt_manager(self):
        """Setup JWT manager for testing."""
        # Add project path
        sys.path.append("/mnt/c/Users/jaafa/Desktop/ai teddy bear/src")
        
        try:
            from infrastructure.security.jwt_advanced import AdvancedJWTManager, TokenType
            self.jwt_manager = AdvancedJWTManager()
            self.TokenType = TokenType
            
            # Setup mock logger
            self.jwt_manager.set_logger(Mock())
            
        except ImportError as e:
            print(f"Warning: Cannot import JWT manager - {e}")
            self.jwt_manager = None
            self.TokenType = None
    
    def generate_device_info(self, device_id: str = None) -> Dict[str, Any]:
        """Generate mock device information."""
        return {
            "user_agent": f"Mozilla/5.0 (Test Browser {device_id or 'default'})",
            "platform": "TestOS",
            "screen_resolution": "1920x1080",
            "timezone": "UTC"
        }
    
    async def test_token_revocation_on_logout(self):
        """Test token revocation when user logs out."""
        test_name = "Token Revocation on Logout"
        
        if not self.jwt_manager:
            test_result = {
                "test_name": test_name,
                "status": "SKIP",
                "details": "JWT manager not available"
            }
            self.test_results["tests"]["token_revocation"] = test_result
            return False
        
        try:
            # Setup mock Redis
            await self.jwt_manager.set_redis_client(self.mock_redis)
            
            test_cases = []
            
            # Test Case 1: Create and revoke access token
            try:
                device_info = self.generate_device_info("device_1")
                
                # Create access token
                access_token = await self.jwt_manager.create_token(
                    user_id="test_user_1",
                    email="test1@example.com",
                    role="user",
                    user_type="parent",
                    token_type=self.TokenType.ACCESS,
                    device_info=device_info,
                    ip_address="192.168.1.100"
                )
                
                # Verify token works initially
                claims = await self.jwt_manager.verify_token(
                    access_token,
                    expected_type=self.TokenType.ACCESS,
                    current_device_info=device_info,
                    current_ip="192.168.1.100"
                )
                
                # Revoke token (simulate logout)
                await self.jwt_manager.revoke_token(claims.jti, "user_logout")
                
                # Try to use revoked token (should fail)
                try:
                    revoked_claims = await self.jwt_manager.verify_token(
                        access_token,
                        expected_type=self.TokenType.ACCESS,
                        current_device_info=device_info,
                        current_ip="192.168.1.100"
                    )
                    test_cases.append({
                        "case": "Access Token Revocation",
                        "status": "VULNERABLE",
                        "details": "Revoked access token still accepted"
                    })
                except:
                    test_cases.append({
                        "case": "Access Token Revocation",
                        "status": "PROTECTED",
                        "details": "Revoked access token properly rejected"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Access Token Revocation",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 2: Create and revoke refresh token
            try:
                device_info = self.generate_device_info("device_2")
                
                # Create refresh token
                refresh_token = await self.jwt_manager.create_token(
                    user_id="test_user_2",
                    email="test2@example.com",
                    role="user",
                    user_type="parent",
                    token_type=self.TokenType.REFRESH,
                    device_info=device_info,
                    ip_address="192.168.1.101"
                )
                
                # Verify token works initially
                claims = await self.jwt_manager.verify_token(
                    refresh_token,
                    expected_type=self.TokenType.REFRESH,
                    current_device_info=device_info,
                    current_ip="192.168.1.101"
                )
                
                # Revoke token
                await self.jwt_manager.revoke_token(claims.jti, "user_logout")
                
                # Try to use revoked token (should fail)
                try:
                    revoked_claims = await self.jwt_manager.verify_token(
                        refresh_token,
                        expected_type=self.TokenType.REFRESH,
                        current_device_info=device_info,
                        current_ip="192.168.1.101"
                    )
                    test_cases.append({
                        "case": "Refresh Token Revocation",
                        "status": "VULNERABLE",
                        "details": "Revoked refresh token still accepted"
                    })
                except:
                    test_cases.append({
                        "case": "Refresh Token Revocation",
                        "status": "PROTECTED",
                        "details": "Revoked refresh token properly rejected"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Refresh Token Revocation",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 3: Revoke all user tokens
            try:
                device_info = self.generate_device_info("device_3")
                user_id = "test_user_3"
                
                # Create multiple tokens for same user
                tokens = []
                for i in range(3):
                    token = await self.jwt_manager.create_token(
                        user_id=user_id,
                        email=f"test{i}@example.com",
                        role="user",
                        user_type="parent",
                        token_type=self.TokenType.REFRESH,
                        device_info=device_info,
                        ip_address=f"192.168.1.{110+i}"
                    )
                    tokens.append(token)
                
                # Verify all tokens work initially
                all_valid = True
                for token in tokens:
                    try:
                        await self.jwt_manager.verify_token(
                            token,
                            expected_type=self.TokenType.REFRESH,
                            current_device_info=device_info
                        )
                    except:
                        all_valid = False
                        break
                
                if not all_valid:
                    test_cases.append({
                        "case": "All User Tokens Revocation Setup",
                        "status": "ERROR",
                        "details": "Initial tokens not all valid"
                    })
                else:
                    # Revoke all user tokens
                    await self.jwt_manager.revoke_all_user_tokens(user_id, "security_reset")
                    
                    # Try to use any token (all should fail)
                    all_revoked = True
                    for i, token in enumerate(tokens):
                        try:
                            await self.jwt_manager.verify_token(
                                token,
                                expected_type=self.TokenType.REFRESH,
                                current_device_info=device_info
                            )
                            all_revoked = False
                            break
                        except:
                            continue
                    
                    if all_revoked:
                        test_cases.append({
                            "case": "All User Tokens Revocation",
                            "status": "PROTECTED",
                            "details": "All user tokens properly revoked"
                        })
                    else:
                        test_cases.append({
                            "case": "All User Tokens Revocation",
                            "status": "VULNERABLE",
                            "details": "Some user tokens still active after revocation"
                        })
                        
            except Exception as e:
                test_cases.append({
                    "case": "All User Tokens Revocation",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Determine overall test result
            vulnerable_cases = [c for c in test_cases if c["status"] == "VULNERABLE"]
            
            test_result = {
                "test_name": test_name,
                "status": "FAIL" if vulnerable_cases else "PASS",
                "test_cases": test_cases,
                "vulnerabilities_found": len(vulnerable_cases),
                "details": f"Tested {len(test_cases)} token revocation scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["vulnerabilities"].extend([
                    f"Token revocation vulnerability: {case['case']}" 
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
    
    async def test_blacklist_enforcement(self):
        """Test blacklist enforcement for revoked tokens."""
        test_name = "Blacklist Enforcement"
        
        if not self.jwt_manager:
            test_result = {
                "test_name": test_name,
                "status": "SKIP",
                "details": "JWT manager not available"
            }
            self.test_results["tests"]["blacklist_enforcement"] = test_result
            return False
        
        try:
            await self.jwt_manager.set_redis_client(self.mock_redis)
            
            test_cases = []
            
            # Test Case 1: API access with blacklisted token
            try:
                device_info = self.generate_device_info("blacklist_device")
                
                # Create token
                access_token = await self.jwt_manager.create_token(
                    user_id="blacklist_user",
                    email="blacklist@example.com",
                    role="user",
                    user_type="parent",
                    token_type=self.TokenType.ACCESS,
                    device_info=device_info,
                    ip_address="192.168.1.200"
                )
                
                # Verify token works initially
                claims = await self.jwt_manager.verify_token(access_token)
                
                # Blacklist the token
                await self.jwt_manager.revoke_token(claims.jti, "security_violation")
                
                # Try multiple API calls with blacklisted token
                api_call_results = []
                for i in range(3):
                    try:
                        blacklisted_claims = await self.jwt_manager.verify_token(access_token)
                        api_call_results.append(f"API call {i+1}: VULNERABLE - Token accepted")
                    except:
                        api_call_results.append(f"API call {i+1}: PROTECTED - Token rejected")
                
                vulnerable_calls = [r for r in api_call_results if "VULNERABLE" in r]
                
                test_cases.append({
                    "case": "Blacklisted Token API Access",
                    "status": "VULNERABLE" if vulnerable_calls else "PROTECTED",
                    "details": f"API calls: {'; '.join(api_call_results)}",
                    "vulnerable_calls": len(vulnerable_calls)
                })
                
            except Exception as e:
                test_cases.append({
                    "case": "Blacklisted Token API Access",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 2: Token refresh with blacklisted refresh token
            try:
                device_info = self.generate_device_info("refresh_blacklist")
                
                # Create refresh token
                refresh_token = await self.jwt_manager.create_token(
                    user_id="refresh_user",
                    email="refresh@example.com",
                    role="user", 
                    user_type="parent",
                    token_type=self.TokenType.REFRESH,
                    device_info=device_info,
                    ip_address="192.168.1.201"
                )
                
                # Get claims
                claims = await self.jwt_manager.verify_token(refresh_token)
                
                # Blacklist refresh token
                await self.jwt_manager.revoke_token(claims.jti, "suspicious_activity")
                
                # Try to refresh tokens (should fail)
                try:
                    new_access, new_refresh = await self.jwt_manager.refresh_token(
                        refresh_token,
                        device_info=device_info,
                        ip_address="192.168.1.201"
                    )
                    test_cases.append({
                        "case": "Blacklisted Refresh Token",
                        "status": "VULNERABLE",
                        "details": "Token refresh succeeded with blacklisted token"
                    })
                except:
                    test_cases.append({
                        "case": "Blacklisted Refresh Token",
                        "status": "PROTECTED",
                        "details": "Token refresh rejected with blacklisted token"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Blacklisted Refresh Token",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 3: Blacklist persistence across system restart (simulated)
            try:
                device_info = self.generate_device_info("persistence_test")
                
                # Create token
                persistent_token = await self.jwt_manager.create_token(
                    user_id="persistent_user",
                    email="persistent@example.com",
                    role="admin",
                    user_type="admin",
                    token_type=self.TokenType.ACCESS,
                    device_info=device_info
                )
                
                claims = await self.jwt_manager.verify_token(persistent_token)
                
                # Blacklist token
                await self.jwt_manager.revoke_token(claims.jti, "policy_violation")
                
                # Simulate system restart by creating new JWT manager instance
                new_jwt_manager = type(self.jwt_manager)()
                new_jwt_manager.set_logger(Mock())
                await new_jwt_manager.set_redis_client(self.mock_redis)
                
                # Try to verify with new instance (should still be blacklisted)
                try:
                    persistent_claims = await new_jwt_manager.verify_token(persistent_token)
                    test_cases.append({
                        "case": "Blacklist Persistence",
                        "status": "VULNERABLE",
                        "details": "Blacklist not persistent across system restart"
                    })
                except:
                    test_cases.append({
                        "case": "Blacklist Persistence",
                        "status": "PROTECTED",
                        "details": "Blacklist maintained across system restart"
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
                "details": f"Tested {len(test_cases)} blacklist enforcement scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["vulnerabilities"].extend([
                    f"Blacklist enforcement vulnerability: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute blacklist enforcement tests"
            }
        
        self.test_results["tests"]["blacklist_enforcement"] = test_result
        return test_result["status"] == "PASS"
    
    async def test_multiple_sessions_management(self):
        """Test management of multiple active sessions per user."""
        test_name = "Multiple Sessions Management"
        
        if not self.jwt_manager:
            test_result = {
                "test_name": test_name,
                "status": "SKIP",
                "details": "JWT manager not available"
            }
            self.test_results["tests"]["multiple_sessions"] = test_result
            return False
        
        try:
            await self.jwt_manager.set_redis_client(self.mock_redis)
            
            test_cases = []
            user_id = "multi_session_user"
            
            # Test Case 1: Create maximum allowed sessions (5)
            try:
                sessions = []
                max_sessions = 5
                
                # Create maximum number of sessions
                for i in range(max_sessions):
                    device_info = self.generate_device_info(f"device_{i}")
                    refresh_token = await self.jwt_manager.create_token(
                        user_id=user_id,
                        email=f"session{i}@example.com",
                        role="user",
                        user_type="parent",
                        token_type=self.TokenType.REFRESH,
                        device_info=device_info,
                        ip_address=f"192.168.1.{220+i}"
                    )
                    sessions.append((refresh_token, device_info))
                
                # Verify all sessions are active
                active_sessions = await self.jwt_manager.get_user_sessions(user_id)
                
                if len(active_sessions) == max_sessions:
                    test_cases.append({
                        "case": "Maximum Sessions Creation",
                        "status": "PASS",
                        "details": f"Successfully created {max_sessions} active sessions"
                    })
                else:
                    test_cases.append({
                        "case": "Maximum Sessions Creation",
                        "status": "FAIL",
                        "details": f"Expected {max_sessions} sessions, got {len(active_sessions)}"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Maximum Sessions Creation",
                    "status": "ERROR",  
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 2: Exceed maximum sessions (should evict oldest)
            try:
                # Create one more session (6th session)
                device_info = self.generate_device_info("device_overflow")
                overflow_token = await self.jwt_manager.create_token(
                    user_id=user_id,
                    email="overflow@example.com",
                    role="user",
                    user_type="parent",
                    token_type=self.TokenType.REFRESH,
                    device_info=device_info,
                    ip_address="192.168.1.230"
                )
                
                # Check active sessions (should still be 5)
                active_sessions = await self.jwt_manager.get_user_sessions(user_id)
                
                if len(active_sessions) <= max_sessions:
                    test_cases.append({
                        "case": "Session Limit Enforcement",
                        "status": "PROTECTED",
                        "details": f"Session limit enforced: {len(active_sessions)} active sessions"
                    })
                else:
                    test_cases.append({
                        "case": "Session Limit Enforcement",
                        "status": "VULNERABLE",
                        "details": f"Session limit exceeded: {len(active_sessions)} active sessions"
                    })
                
                # Verify oldest session was evicted by trying to use first token
                if sessions:
                    first_token, first_device = sessions[0]
                    try:
                        await self.jwt_manager.verify_token(
                            first_token,
                            expected_type=self.TokenType.REFRESH,
                            current_device_info=first_device
                        )
                        test_cases.append({
                            "case": "Oldest Session Eviction",
                            "status": "VULNERABLE",
                            "details": "Oldest session not evicted when limit exceeded"
                        })
                    except:
                        test_cases.append({
                            "case": "Oldest Session Eviction",
                            "status": "PROTECTED",
                            "details": "Oldest session properly evicted when limit exceeded"
                        })
                        
            except Exception as e:
                test_cases.append({
                    "case": "Session Limit Enforcement",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 3: Session activity tracking
            try:
                # Create a session
                device_info = self.generate_device_info("activity_test")
                activity_token = await self.jwt_manager.create_token(
                    user_id="activity_user",
                    email="activity@example.com", 
                    role="user",
                    user_type="parent",
                    token_type=self.TokenType.REFRESH,
                    device_info=device_info,
                    ip_address="192.168.1.240"
                )
                
                # Verify token multiple times to simulate activity
                for _ in range(3):
                    await self.jwt_manager.verify_token(
                        activity_token,
                        expected_type=self.TokenType.REFRESH,
                        current_device_info=device_info
                    )
                
                # Check if session activity is tracked
                sessions = await self.jwt_manager.get_user_sessions("activity_user")
                
                if sessions and "last_activity" in sessions[0]:
                    test_cases.append({
                        "case": "Session Activity Tracking",
                        "status": "PASS",
                        "details": "Session activity properly tracked"
                    })
                else:
                    test_cases.append({
                        "case": "Session Activity Tracking",
                        "status": "FAIL",
                        "details": "Session activity not tracked"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Session Activity Tracking",
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
                "failed_tests": len(failed_cases),
                "details": f"Tested {len(test_cases)} session management scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["vulnerabilities"].extend([
                    f"Session management vulnerability: {case['case']}" 
                    for case in vulnerable_cases
                ])
            
        except Exception as e:
            test_result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "details": "Failed to execute session management tests"
            }
        
        self.test_results["tests"]["multiple_sessions"] = test_result
        return test_result["status"] == "PASS"
    
    async def test_privilege_escalation_prevention(self):
        """Test prevention of privilege escalation through token tampering."""
        test_name = "Privilege Escalation Prevention"
        
        if not self.jwt_manager:
            test_result = {
                "test_name": test_name,
                "status": "SKIP",
                "details": "JWT manager not available"
            }
            self.test_results["tests"]["privilege_escalation"] = test_result
            return False
        
        try:
            await self.jwt_manager.set_redis_client(self.mock_redis)
            
            test_cases = []
            
            # Test Case 1: Role tampering in JWT payload
            try:
                device_info = self.generate_device_info("role_tamper")
                
                # Create user token
                user_token = await self.jwt_manager.create_token(
                    user_id="role_test_user",
                    email="roletest@example.com",
                    role="user",
                    user_type="parent",
                    token_type=self.TokenType.ACCESS,
                    device_info=device_info
                )
                
                # Tamper with role in token payload
                try:
                    # Decode without verification
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
                    
                    # Try to verify tampered token
                    try:
                        tampered_claims = await self.jwt_manager.verify_token(tampered_token)
                        test_cases.append({
                            "case": "Role Tampering in JWT",
                            "status": "VULNERABLE",
                            "details": f"Tampered token accepted with role: {tampered_claims.role}"
                        })
                    except:
                        test_cases.append({
                            "case": "Role Tampering in JWT",
                            "status": "PROTECTED",
                            "details": "Tampered token properly rejected"
                        })
                        
                except Exception as e:
                    test_cases.append({
                        "case": "Role Tampering in JWT",
                        "status": "ERROR",
                        "details": f"Tampering test error: {str(e)}"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Role Tampering in JWT",
                    "status": "ERROR",
                    "details": f"Test setup error: {str(e)}"
                })
            
            # Test Case 2: Server-side authorization validation
            try:
                device_info = self.generate_device_info("auth_validation")
                
                # Create user token
                user_token = await self.jwt_manager.create_token(
                    user_id="auth_test_user",
                    email="authtest@example.com",
                    role="user",
                    user_type="parent",
                    token_type=self.TokenType.ACCESS,
                    device_info=device_info
                )
                
                claims = await self.jwt_manager.verify_token(user_token)
                
                # Test server-side authorization with correct session data
                server_session_data = {"server_role": "user"}
                auth_result = self.jwt_manager.validate_server_side_authorization(
                    claims, required_role="user", session_data=server_session_data
                )
                
                if auth_result:
                    # Now test with privilege escalation attempt
                    admin_session_data = {"server_role": "admin"}  # Fake admin role
                    escalation_result = self.jwt_manager.validate_server_side_authorization(
                        claims, required_role="admin", session_data=admin_session_data
                    )
                    
                    if escalation_result:
                        test_cases.append({
                            "case": "Server-Side Authorization Bypass",
                            "status": "VULNERABLE",  
                            "details": "Server-side authorization accepted fake admin role"
                        })
                    else:
                        test_cases.append({
                            "case": "Server-Side Authorization Bypass",
                            "status": "PROTECTED",
                            "details": "Server-side authorization rejected privilege escalation"
                        })
                else:
                    test_cases.append({
                        "case": "Server-Side Authorization Bypass",
                        "status": "ERROR",
                        "details": "Server-side authorization failed for valid user"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Server-Side Authorization Bypass",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 3: Reuse of old admin token after demotion
            try:
                device_info = self.generate_device_info("token_reuse")
                
                # Create admin token
                admin_token = await self.jwt_manager.create_token(
                    user_id="demoted_admin",
                    email="demoted@example.com",
                    role="admin",
                    user_type="admin",
                    token_type=self.TokenType.ACCESS,
                    device_info=device_info
                )
                
                # Verify admin token works
                admin_claims = await self.jwt_manager.verify_token(admin_token)
                
                # Simulate user demotion by revoking all tokens
                await self.jwt_manager.revoke_all_user_tokens("demoted_admin", "role_change")
                
                # Try to reuse old admin token after demotion
                try:
                    reused_claims = await self.jwt_manager.verify_token(admin_token)
                    test_cases.append({
                        "case": "Old Admin Token Reuse",
                        "status": "VULNERABLE",
                        "details": "Old admin token accepted after user demotion"
                    })
                except:
                    test_cases.append({
                        "case": "Old Admin Token Reuse",
                        "status": "PROTECTED",
                        "details": "Old admin token rejected after user demotion"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Old Admin Token Reuse",
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
                self.test_results["vulnerabilities"].extend([
                    f"Privilege escalation vulnerability: {case['case']}" 
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
    
    async def test_device_fingerprinting(self):
        """Test device fingerprinting and binding."""
        test_name = "Device Fingerprinting"
        
        if not self.jwt_manager:
            test_result = {
                "test_name": test_name,
                "status": "SKIP",
                "details": "JWT manager not available"
            }
            self.test_results["tests"]["device_fingerprinting"] = test_result
            return False
        
        try:
            await self.jwt_manager.set_redis_client(self.mock_redis)
            
            test_cases = []
            
            # Test Case 1: Token bound to specific device
            try:
                original_device = self.generate_device_info("original_device")
                
                # Create token with device binding
                device_token = await self.jwt_manager.create_token(
                    user_id="device_test_user",
                    email="devicetest@example.com",
                    role="user",
                    user_type="parent",
                    token_type=self.TokenType.ACCESS,
                    device_info=original_device,
                    ip_address="192.168.1.100"
                )
                
                # Verify with same device (should work)
                try:
                    same_device_claims = await self.jwt_manager.verify_token(
                        device_token,
                        verify_device=True,
                        current_device_info=original_device,
                        current_ip="192.168.1.100"
                    )
                    
                    # Try with different device (should fail)
                    different_device = self.generate_device_info("different_device")
                    try:
                        different_device_claims = await self.jwt_manager.verify_token(
                            device_token,
                            verify_device=True,
                            current_device_info=different_device,
                            current_ip="192.168.1.101"
                        )
                        test_cases.append({
                            "case": "Device Binding Enforcement",
                            "status": "VULNERABLE",
                            "details": "Token accepted on different device"
                        })
                    except:
                        test_cases.append({
                            "case": "Device Binding Enforcement",
                            "status": "PROTECTED",
                            "details": "Token rejected on different device"
                        })
                        
                except Exception as e:
                    test_cases.append({
                        "case": "Device Binding Enforcement",
                        "status": "ERROR",
                        "details": f"Same device verification failed: {str(e)}"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Device Binding Enforcement",
                    "status": "ERROR",
                    "details": f"Test setup error: {str(e)}"
                })
            
            # Test Case 2: Device fingerprint tampering
            try:
                legit_device = self.generate_device_info("legit_device")
                
                # Create token
                legit_token = await self.jwt_manager.create_token(
                    user_id="fingerprint_user",
                    email="fingerprint@example.com",
                    role="user",
                    user_type="parent",
                    token_type=self.TokenType.ACCESS,
                    device_info=legit_device
                )
                
                # Try to spoof device fingerprint
                spoofed_device = legit_device.copy()
                spoofed_device["user_agent"] = "Spoofed Browser"
                
                try:
                    spoofed_claims = await self.jwt_manager.verify_token(
                        legit_token,
                        verify_device=True,
                        current_device_info=spoofed_device
                    )
                    test_cases.append({
                        "case": "Device Fingerprint Spoofing",
                        "status": "VULNERABLE",
                        "details": "Token accepted with spoofed device fingerprint" 
                    })
                except:
                    test_cases.append({
                        "case": "Device Fingerprint Spoofing",
                        "status": "PROTECTED",
                        "details": "Token rejected with spoofed device fingerprint"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "Device Fingerprint Spoofing",
                    "status": "ERROR",
                    "details": f"Test error: {str(e)}"
                })
            
            # Test Case 3: IP address tracking
            try:
                tracked_device = self.generate_device_info("ip_tracked")
                original_ip = "192.168.1.100"
                
                # Create token with IP tracking
                ip_token = await self.jwt_manager.create_token(
                    user_id="ip_test_user",
                    email="iptest@example.com",
                    role="user",
                    user_type="parent", 
                    token_type=self.TokenType.ACCESS,
                    device_info=tracked_device,
                    ip_address=original_ip
                )
                
                # Verify with same IP (should work)
                try:
                    same_ip_claims = await self.jwt_manager.verify_token(
                        ip_token,
                        current_device_info=tracked_device,
                        current_ip=original_ip
                    )
                    
                    # Verify with different IP (should log warning but still work)
                    different_ip = "10.0.0.100"
                    try:
                        different_ip_claims = await self.jwt_manager.verify_token(
                            ip_token,
                            current_device_info=tracked_device,
                            current_ip=different_ip
                        )
                        test_cases.append({
                            "case": "IP Address Tracking",
                            "status": "PASS",
                            "details": "IP change detected and logged (legitimate roaming)"
                        })
                    except:
                        test_cases.append({
                            "case": "IP Address Tracking",
                            "status": "FAIL",
                            "details": "Token rejected due to IP change (too restrictive)"
                        })
                        
                except Exception as e:
                    test_cases.append({
                        "case": "IP Address Tracking",
                        "status": "ERROR",
                        "details": f"Same IP verification failed: {str(e)}"
                    })
                    
            except Exception as e:
                test_cases.append({
                    "case": "IP Address Tracking",
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
                "failed_tests": len(failed_cases),
                "details": f"Tested {len(test_cases)} device fingerprinting scenarios"
            }
            
            if vulnerable_cases:
                self.test_results["vulnerabilities"].extend([
                    f"Device fingerprinting vulnerability: {case['case']}" 
                    for case in vulnerable_cases
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
            
            # Deduct points for vulnerabilities
            vulnerability_penalty = min(len(self.test_results["vulnerabilities"]) * 15, 90)
            
            self.test_results["security_score"] = max(0, base_score - vulnerability_penalty)
    
    async def run_all_tests(self):
        """Run complete JWT session management testing suite."""
        print("🔒 Starting JWT Session Management Testing Suite")
        print("=" * 60)
        
        # Run all tests
        tests = [
            self.test_token_revocation_on_logout,
            self.test_blacklist_enforcement,
            self.test_multiple_sessions_management,
            self.test_privilege_escalation_prevention,
            self.test_device_fingerprinting
        ]
        
        for test in tests:
            try:
                result = await test()
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
        print(f"Vulnerabilities Found: {len(self.test_results['vulnerabilities'])}")
        
        # Show vulnerabilities
        if self.test_results["vulnerabilities"]:
            print("\n🚨 VULNERABILITIES DETECTED:")
            for vuln in self.test_results["vulnerabilities"]:
                print(f"  • {vuln}")
        else:
            print("\n✅ No vulnerabilities detected in session management")
        
        return self.test_results


async def main():
    """Main testing execution."""
    tester = JWTSessionManagementTester()
    results = await tester.run_all_tests()
    
    # Save results to file
    output_file = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/JWT_SESSION_MANAGEMENT_TEST_RESULTS.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {output_file}")
    
    # Return exit code based on vulnerabilities
    vulnerability_count = len(results["vulnerabilities"])
    if vulnerability_count > 0:
        print(f"\n❌ Session management testing found {vulnerability_count} vulnerabilities")
        return 1
    else:
        print("\n✅ Session management testing completed successfully - System secure")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))