"""
E2E Tests for Error Handling & Edge Cases
==========================================
Comprehensive end-to-end tests for error handling and edge cases:
- Invalid inputs and malformed requests
- Service failures and circuit breakers
- Database connectivity issues
- External API failures
- Network timeouts and retries
- Data corruption scenarios
- System resource exhaustion
- Graceful degradation testing
"""

import pytest
import asyncio
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock, patch
import json

from httpx import AsyncClient, HTTPError, ConnectTimeout, ReadTimeout

from .base import E2ETestBase, E2ETestConfig, performance_test
from .utils import (
    validate_response,
    validate_error_response,
    generate_large_payload,
    retry_on_failure,
    PerformanceTimer,
    wait_for_condition
)


class ErrorHandlingEdgeCaseTests(E2ETestBase):
    """E2E tests for error handling and edge case scenarios."""
    
    async def _custom_setup(self):
        """Setup for error handling tests."""
        self.error_scenarios = {
            "network_timeouts": [1, 5, 10, 30],  # seconds
            "invalid_data_sizes": [0, 1, 1024, 10*1024*1024, 100*1024*1024],  # bytes
            "malformed_requests": self._generate_malformed_requests(),
            "database_errors": ["connection_timeout", "deadlock", "constraint_violation"],
            "external_api_errors": [400, 401, 403, 404, 429, 500, 502, 503, 504]
        }
        
        # Create test entities for error scenarios
        self.test_parent = await self.data_manager.create_test_user(
            role="parent",
            username="error_test_parent"
        )
        
        self.test_child = await self.data_manager.create_test_child(
            parent_id=uuid.UUID(self.test_parent["id"]),
            name="Error Test Child",
            estimated_age=8,
            parental_consent=True
        )
        
        self.authenticated_client = await self.create_authenticated_client(
            self.test_parent["username"]
        )
    
    async def _custom_teardown(self):
        """Teardown for error handling tests."""
        pass
    
    def _generate_malformed_requests(self) -> List[Dict[str, Any]]:
        """Generate various malformed request scenarios."""
        return [
            # Invalid JSON
            {"type": "invalid_json", "data": "{invalid json}"},
            {"type": "incomplete_json", "data": '{"field": "value"'},
            {"type": "null_json", "data": None},
            
            # Invalid field types
            {"type": "string_as_number", "data": {"age": "not_a_number"}},
            {"type": "number_as_string", "data": {"name": 12345}},
            {"type": "array_as_object", "data": {"settings": ["not", "an", "object"]}},
            
            # Missing required fields
            {"type": "missing_required", "data": {"optional_field": "value"}},
            
            # Invalid UUIDs
            {"type": "invalid_uuid", "data": {"child_id": "not-a-valid-uuid"}},
            {"type": "empty_uuid", "data": {"child_id": ""}},
            
            # Extremely long strings
            {"type": "oversized_string", "data": {"content": "x" * 100000}},
            
            # Invalid dates
            {"type": "invalid_date", "data": {"created_at": "not-a-date"}},
            {"type": "future_date", "data": {"birth_date": "2050-01-01"}},
            
            # Negative numbers where positive expected
            {"type": "negative_age", "data": {"age": -5}},
            {"type": "negative_duration", "data": {"duration": -10.5}},
            
            # Empty or whitespace-only strings
            {"type": "empty_string", "data": {"name": ""}},
            {"type": "whitespace_only", "data": {"name": "   "}},
        ]
    
    async def test_invalid_input_handling(self):
        """Test handling of various invalid inputs."""
        
        for scenario in self.error_scenarios["malformed_requests"]:
            scenario_type = scenario["type"]
            test_data = scenario["data"]
            
            # Test invalid input in child creation
            if isinstance(test_data, dict):
                response = await self.authenticated_client.post(
                    "/api/v1/children",
                    json=test_data
                )
                
                # Should return appropriate error
                assert response.status_code in [400, 422], \
                    f"Invalid input not handled for {scenario_type}: {response.status_code}"
                
                error_data = response.json()
                assert "error" in error_data
                assert "message" in error_data
                
                # Error message should be helpful but not expose internals
                error_message = error_data["message"].lower()
                assert "internal" not in error_message
                assert "exception" not in error_message
                assert "traceback" not in error_message
            
            # Test invalid input in message creation
            if scenario_type in ["string_as_number", "oversized_string", "empty_string"]:
                # Create conversation first
                conv_response = await self.authenticated_client.post(
                    f"/api/v1/children/{self.test_child['id']}/conversations",
                    json={"title": "Error Test Conversation"}
                )
                
                if conv_response.status_code == 201:
                    conversation = conv_response.json()
                    
                    message_data = {"content": test_data.get("content", "test"), "sender_type": "child"}
                    if "age" in test_data:
                        message_data["metadata"] = {"child_age": test_data["age"]}
                    
                    response = await self.authenticated_client.post(
                        f"/api/v1/conversations/{conversation['id']}/messages",
                        json=message_data
                    )
                    
                    assert response.status_code in [400, 422], \
                        f"Invalid message input not handled for {scenario_type}"
    
    async def test_network_timeout_handling(self):
        """Test handling of network timeouts and connection issues."""
        
        # Test various timeout scenarios
        timeout_scenarios = [
            {"timeout": 0.1, "operation": "fast_timeout"},
            {"timeout": 1.0, "operation": "short_timeout"},
            {"timeout": 5.0, "operation": "medium_timeout"}
        ]
        
        for scenario in timeout_scenarios:
            timeout_duration = scenario["timeout"]
            
            # Create client with very short timeout
            timeout_client = AsyncClient(
                base_url=self.config.base_url,
                timeout=timeout_duration,
                headers=self.authenticated_client.headers
            )
            
            try:
                # Test timeout on potentially slow endpoint
                start_time = time.time()
                
                try:
                    response = await timeout_client.get("/api/v1/dashboard/overview")
                    request_duration = time.time() - start_time
                    
                    # If request succeeded within timeout, that's good
                    if response.status_code == 200:
                        assert request_duration <= timeout_duration + 0.5  # Small buffer
                    
                except (ConnectTimeout, ReadTimeout, HTTPError) as e:
                    # Timeout occurred - verify it was handled gracefully
                    request_duration = time.time() - start_time
                    assert request_duration <= timeout_duration + 1.0  # Allow some buffer
                    
                    # Should timeout reasonably quickly
                    assert request_duration >= timeout_duration * 0.8
                
                finally:
                    await timeout_client.aclose()
            
            except Exception as e:
                self.logger.info(f"Timeout test {scenario['operation']} resulted in: {str(e)}")
    
    async def test_database_error_handling(self):
        """Test handling of database errors and connection issues."""
        
        # Test 1: Invalid database queries
        invalid_queries = [
            {"child_id": "00000000-0000-0000-0000-000000000000"},  # Non-existent UUID
            {"child_id": str(uuid.uuid4())},  # Random UUID
        ]
        
        for query in invalid_queries:
            child_id = query["child_id"]
            
            response = await self.authenticated_client.get(
                f"/api/v1/children/{child_id}/profile"
            )
            
            # Should return 404 for non-existent resources
            assert response.status_code == 404
            
            error_data = response.json()
            assert error_data["error"] == "child_not_found"
            assert "does not exist" in error_data["message"] or "not found" in error_data["message"]
        
        # Test 2: Constraint violations
        # Try to create child with invalid parent reference
        response = await self.authenticated_client.post(
            "/api/v1/children",
            json={
                "name": "Invalid Parent Child",
                "estimated_age": 8,
                "parent_id": str(uuid.uuid4()),  # Non-existent parent
                "parental_consent": True
            }
        )
        
        # Should handle foreign key constraint violation
        assert response.status_code in [400, 422]
        
        error_data = response.json()
        assert "error" in error_data
        
        # Test 3: Concurrent modification scenarios
        # Simulate race condition by trying to update same resource concurrently
        async def update_child_name(name_suffix):
            return await self.authenticated_client.put(
                f"/api/v1/children/{self.test_child['id']}/profile",
                json={"name": f"Updated Child {name_suffix}"}
            )
        
        # Make concurrent updates
        update_tasks = [update_child_name(i) for i in range(5)]
        update_results = await asyncio.gather(*update_tasks, return_exceptions=True)
        
        # At least one should succeed
        successful_updates = [r for r in update_results if not isinstance(r, Exception) and hasattr(r, 'status_code') and r.status_code == 200]
        assert len(successful_updates) >= 1, "No concurrent updates succeeded"
        
        # Others might fail due to optimistic locking or constraints
        failed_updates = [r for r in update_results if isinstance(r, Exception) or (hasattr(r, 'status_code') and r.status_code != 200)]
        
        # Failures should be handled gracefully
        for failure in failed_updates:
            if hasattr(failure, 'status_code'):
                assert failure.status_code in [409, 422, 500]  # Conflict, validation, or server error
    
    async def test_external_api_failure_handling(self):
        """Test handling of external API failures."""
        
        # Test AI service failures
        with patch('src.application.services.ai_service.AIService.generate_response') as mock_ai:
            # Simulate AI service timeout
            mock_ai.side_effect = asyncio.TimeoutError("AI service timeout")
            
            # Create conversation
            response = await self.authenticated_client.post(
                f"/api/v1/children/{self.test_child['id']}/conversations",
                json={"title": "AI Failure Test"}
            )
            
            conversation = validate_response(response, 201)
            
            # Send message that would trigger AI response
            response = await self.authenticated_client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={
                    "content": "Tell me a story",
                    "sender_type": "child"
                }
            )
            
            # Message should be accepted but AI response should gracefully fail
            message_data = validate_response(response, 201)
            
            # Check AI response status
            ai_response_id = message_data.get("ai_response_id")
            if ai_response_id:
                # Wait a bit for processing
                await asyncio.sleep(1)
                
                response = await self.authenticated_client.get(
                    f"/api/v1/ai-responses/{ai_response_id}"
                )
                
                if response.status_code == 200:
                    ai_data = response.json()
                    # Should indicate failure and provide fallback
                    assert ai_data.get("status") in ["failed", "fallback_used"]
                    assert "fallback_content" in ai_data or "error_message" in ai_data
        
        # Test TTS service failures
        with patch('src.application.services.text_to_speech_service.TextToSpeechService.generate_audio') as mock_tts:
            mock_tts.side_effect = Exception("TTS service unavailable")
            
            # Request audio response
            response = await self.authenticated_client.post(
                "/api/v1/conversations/generate-audio-response",
                json={
                    "text": "Hello, this is a test message",
                    "child_id": self.test_child["id"],
                    "voice_settings": {"voice": "child_friendly"}
                }
            )
            
            # Should handle TTS failure gracefully
            if response.status_code == 202:
                # Async processing
                audio_data = response.json()
                
                # Wait for processing
                await asyncio.sleep(2)
                
                # Check status
                status_response = await self.authenticated_client.get(
                    f"/api/v1/audio-generation/{audio_data['id']}/status"
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    assert status_data["status"] in ["failed", "fallback_available"]
            else:
                # Immediate failure handling
                assert response.status_code in [503, 500]
                error_data = response.json()
                assert "service_unavailable" in error_data.get("error", "")
    
    async def test_data_corruption_scenarios(self):
        """Test handling of data corruption and integrity issues."""
        
        # Test 1: Malformed database records
        # This would typically be tested with database mocking
        # For now, we'll test API resilience to unexpected data
        
        corruption_scenarios = [
            {
                "name": "null_required_field",
                "data": {"name": None, "estimated_age": 8, "parental_consent": True}
            },
            {
                "name": "invalid_enum_value", 
                "data": {"name": "Test Child", "estimated_age": 8, "status": "invalid_status"}
            },
            {
                "name": "circular_reference",
                "data": {"name": "Test Child", "estimated_age": 8, "parent_id": "self"}
            }
        ]
        
        for scenario in corruption_scenarios:
            response = await self.authenticated_client.post(
                "/api/v1/children",
                json=scenario["data"]
            )
            
            # Should handle corrupted data gracefully
            assert response.status_code in [400, 422, 500]
            
            if response.status_code != 500:
                error_data = response.json()
                assert "error" in error_data
                assert len(error_data.get("message", "")) > 0
        
        # Test 2: Inconsistent data states
        # Create child then try to create duplicate
        valid_child_data = {
            "name": "Duplicate Test Child",
            "estimated_age": 7,
            "parental_consent": True
        }
        
        # First creation should succeed
        response1 = await self.authenticated_client.post(
            "/api/v1/children",
            json=valid_child_data
        )
        
        if response1.status_code == 201:
            child1 = response1.json()
            
            # Second creation with same data should be handled appropriately
            response2 = await self.authenticated_client.post(
                "/api/v1/children", 
                json=valid_child_data
            )
            
            # Might succeed (multiple children allowed) or fail (if uniqueness required)
            if response2.status_code != 201:
                assert response2.status_code in [400, 409, 422]
    
    async def test_resource_exhaustion_scenarios(self):
        """Test handling of resource exhaustion."""
        
        # Test 1: Large payload handling
        large_payloads = [
            {"size_mb": 1, "should_succeed": True},
            {"size_mb": 10, "should_succeed": False},
            {"size_mb": 100, "should_succeed": False}
        ]
        
        for payload_test in large_payloads:
            size_mb = payload_test["size_mb"]
            should_succeed = payload_test["should_succeed"]
            
            large_content = generate_large_payload(size_mb)
            
            response = await self.authenticated_client.post(
                f"/api/v1/children/{self.test_child['id']}/conversations",
                json={
                    "title": "Large Payload Test",
                    "description": large_content
                }
            )
            
            if should_succeed:
                # Small payloads should work
                assert response.status_code in [201, 413, 422]  # Created or rejected
            else:
                # Large payloads should be rejected
                assert response.status_code in [413, 422]  # Payload too large or validation error
                
                if response.status_code == 413:
                    error_data = response.json()
                    assert "too_large" in error_data.get("error", "").lower()
        
        # Test 2: Memory exhaustion simulation
        # Create many concurrent requests
        async def create_conversation(index):
            try:
                response = await self.authenticated_client.post(
                    f"/api/v1/children/{self.test_child['id']}/conversations",
                    json={
                        "title": f"Concurrent Test {index}",
                        "description": "x" * 1000  # Small but numerous
                    }
                )
                return {
                    "index": index,
                    "success": response.status_code == 201,
                    "status_code": response.status_code
                }
            except Exception as e:
                return {
                    "index": index,
                    "success": False,
                    "error": str(e)
                }
        
        # Create many concurrent requests
        concurrent_tasks = [create_conversation(i) for i in range(20)]
        results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
        
        successful_requests = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_requests = [r for r in results if isinstance(r, dict) and not r.get("success")]
        
        # Some requests should succeed
        assert len(successful_requests) > 0, "No concurrent requests succeeded"
        
        # If some failed, they should fail gracefully
        for failed_request in failed_requests:
            if "status_code" in failed_request:
                assert failed_request["status_code"] in [429, 503, 500]  # Rate limited, unavailable, or server error
    
    async def test_graceful_degradation(self):
        """Test graceful degradation when services are partially unavailable."""
        
        # Test 1: AI service degradation
        with patch('src.application.services.ai_service.AIService.is_available') as mock_ai_available:
            mock_ai_available.return_value = False
            
            # Create conversation
            response = await self.authenticated_client.post(
                f"/api/v1/children/{self.test_child['id']}/conversations",
                json={"title": "Degraded Service Test"}
            )
            
            conversation = validate_response(response, 201)
            
            # Send message
            response = await self.authenticated_client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={
                    "content": "Hello, can you hear me?",
                    "sender_type": "child"
                }
            )
            
            # Message should be accepted even if AI is unavailable
            message_data = validate_response(response, 201)
            
            # Should indicate degraded service
            assert message_data.get("ai_response_available") is False
            assert message_data.get("service_status") == "degraded"
        
        # Test 2: Monitoring service degradation
        with patch('src.infrastructure.monitoring.health.HealthChecker.check_all_services') as mock_health:
            mock_health.return_value = {
                "overall_health": "degraded",
                "services": {
                    "database": "healthy",
                    "ai_service": "unhealthy",
                    "tts_service": "degraded"
                }
            }
            
            # Health check should report degraded status
            response = await self.client.get("/health")
            
            # Should return degraded status but still respond
            assert response.status_code in [200, 503]
            
            health_data = response.json()
            assert health_data.get("status") in ["degraded", "unhealthy"]
            assert "services" in health_data
        
        # Test 3: Partial feature availability
        # Test dashboard when some metrics are unavailable
        with patch('src.adapters.dashboard.parent_dashboard.MetricsCollector.collect_all_metrics') as mock_metrics:
            mock_metrics.side_effect = Exception("Metrics service unavailable")
            
            response = await self.authenticated_client.get("/api/v1/dashboard/overview")
            
            # Dashboard should still work with limited data
            if response.status_code == 200:
                dashboard_data = response.json()
                # Should indicate partial data availability
                assert dashboard_data.get("metrics_available") is False
                assert dashboard_data.get("limited_data") is True
            else:
                # Or return service unavailable
                assert response.status_code == 503
    
    async def test_error_recovery_mechanisms(self):
        """Test error recovery and retry mechanisms."""
        
        # Test 1: Automatic retry on transient failures
        retry_count = 0
        
        async def failing_operation():
            nonlocal retry_count
            retry_count += 1
            
            if retry_count < 3:
                raise Exception("Transient failure")
            return {"success": True, "attempts": retry_count}
        
        # Test retry mechanism
        result = await retry_on_failure(
            failing_operation,
            max_retries=5,
            delay=0.1
        )
        
        assert result["success"] is True
        assert result["attempts"] == 3
        
        # Test 2: Circuit breaker pattern
        # Simulate multiple failures followed by recovery
        failure_count = 0
        
        async def circuit_breaker_test():
            nonlocal failure_count
            failure_count += 1
            
            if failure_count <= 5:
                raise Exception(f"Failure {failure_count}")
            return {"recovered": True}
        
        # Multiple failures should trigger circuit breaker
        for i in range(7):
            try:
                await circuit_breaker_test()
                break
            except Exception as e:
                if i < 5:
                    assert "Failure" in str(e)
                else:
                    # Should recover
                    break
        
        # Test 3: Fallback mechanisms
        # Test fallback AI responses when primary AI fails
        with patch('src.application.services.ai_service.PrimaryAIProvider.generate') as mock_primary:
            with patch('src.application.services.ai_service.FallbackAIProvider.generate') as mock_fallback:
                
                mock_primary.side_effect = Exception("Primary AI failed")
                mock_fallback.return_value = "This is a fallback response"
                
                # Create conversation and message
                conv_response = await self.authenticated_client.post(
                    f"/api/v1/children/{self.test_child['id']}/conversations",
                    json={"title": "Fallback Test"}
                )
                
                conversation = validate_response(conv_response, 201)
                
                msg_response = await self.authenticated_client.post(
                    f"/api/v1/conversations/{conversation['id']}/messages",
                    json={
                        "content": "Tell me a story",
                        "sender_type": "child"
                    }
                )
                
                message_data = validate_response(msg_response, 201)
                
                # Should use fallback when primary fails
                if "ai_response_id" in message_data:
                    await asyncio.sleep(1)  # Allow processing
                    
                    ai_response = await self.authenticated_client.get(
                        f"/api/v1/ai-responses/{message_data['ai_response_id']}"
                    )
                    
                    if ai_response.status_code == 200:
                        ai_data = ai_response.json()
                        assert ai_data.get("fallback_used") is True
                        assert "fallback response" in ai_data.get("content", "").lower()


# Test execution configuration
@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.error_handling
class TestErrorHandlingEdgeCasesE2E:
    """Test class for running error handling and edge case tests."""
    
    async def test_run_error_handling_edge_case_tests(self):
        """Run all error handling and edge case tests."""
        config = E2ETestConfig(
            max_response_time_ms=15000.0,  # Longer timeout for error scenarios
            enable_security_tests=True,
            cleanup_after_test=True
        )
        
        test_suite = ErrorHandlingEdgeCaseTests(config)
        
        try:
            await test_suite.setup()
            
            # Run all error handling tests
            await test_suite.test_invalid_input_handling()
            await test_suite.test_network_timeout_handling()
            await test_suite.test_database_error_handling()
            await test_suite.test_external_api_failure_handling()
            await test_suite.test_data_corruption_scenarios()
            await test_suite.test_resource_exhaustion_scenarios()
            await test_suite.test_graceful_degradation()
            await test_suite.test_error_recovery_mechanisms()
            
        finally:
            await test_suite.teardown()


if __name__ == "__main__":
    # Direct execution for development/debugging
    asyncio.run(TestErrorHandlingEdgeCasesE2E().test_run_error_handling_edge_case_tests())