"""
Tests for Prometheus Metrics.
"""

import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, Response
from prometheus_client import CollectorRegistry

from src.infrastructure.monitoring.prometheus_metrics import (
from fastapi import Response
    PrometheusMetrics,
    PrometheusMiddleware,
    AIMetricsCollector,
    SafetyMetricsCollector,
    MetricType,
    metrics_decorator,
    get_metrics_response
)


class TestPrometheusMetrics:
    """Test Prometheus metrics functionality."""

    @pytest.fixture
    def metrics(self):
        """Create metrics instance with custom registry."""
        registry = CollectorRegistry()
        return PrometheusMetrics(registry=registry, service_name="test_service")

    def test_metrics_initialization(self, metrics):
        """Test metrics initialization."""
        assert metrics.service_name == "test_service"
        assert metrics.registry is not None
        
        # Check that key metrics are initialized
        assert hasattr(metrics, 'http_requests_total')
        assert hasattr(metrics, 'child_interactions_total')
        assert hasattr(metrics, 'provider_requests_total')
        assert hasattr(metrics, 'database_operations_total')

    def test_record_http_request(self, metrics):
        """Test HTTP request recording."""
        metrics.record_http_request(
            method="GET",
            endpoint="/api/v1/children",
            status_code=200,
            duration=0.5,
            request_size=1024,
            response_size=2048,
            user_type="parent",
            region="us-east-1"
        )
        
        # Verify metrics were recorded
        samples = list(metrics.http_requests_total.collect())[0].samples
        assert len(samples) > 0
        
        # Check labels
        sample = samples[0]
        assert sample.labels['method'] == 'GET'
        assert sample.labels['endpoint'] == '/api/v1/children'
        assert sample.labels['status_code'] == '200'
        assert sample.labels['user_type'] == 'parent'
        assert sample.value == 1.0

    def test_record_child_interaction(self, metrics):
        """Test child interaction recording."""
        metrics.record_child_interaction(
            interaction_type="story_request",
            age_group="middle_childhood",
            language="en",
            safety_status="safe"
        )
        
        samples = list(metrics.child_interactions_total.collect())[0].samples
        assert len(samples) > 0
        
        sample = samples[0]
        assert sample.labels['interaction_type'] == 'story_request'
        assert sample.labels['age_group'] == 'middle_childhood'
        assert sample.labels['language'] == 'en'
        assert sample.labels['safety_status'] == 'safe'
        assert sample.value == 1.0

    def test_record_provider_request(self, metrics):
        """Test provider request recording."""
        metrics.record_provider_request(
            provider_id="openai",
            provider_type="ai_model",
            operation="text_generation",
            status="success",
            duration=1.5,
            cost=0.05
        )
        
        # Check request counter
        request_samples = list(metrics.provider_requests_total.collect())[0].samples
        assert len(request_samples) > 0
        
        request_sample = request_samples[0]
        assert request_sample.labels['provider_id'] == 'openai'
        assert request_sample.labels['provider_type'] == 'ai_model'
        assert request_sample.labels['operation'] == 'text_generation'
        assert request_sample.labels['status'] == 'success'
        assert request_sample.value == 1.0
        
        # Check cost counter
        cost_samples = list(metrics.provider_cost_total.collect())[0].samples
        assert len(cost_samples) > 0
        
        cost_sample = cost_samples[0]
        assert cost_sample.value == 0.05

    def test_update_circuit_breaker_state(self, metrics):
        """Test circuit breaker state update."""
        metrics.update_circuit_breaker_state(
            provider_id="openai",
            provider_type="ai_model",
            state="open"
        )
        
        samples = list(metrics.circuit_breaker_state.collect())[0].samples
        assert len(samples) > 0
        
        sample = samples[0]
        assert sample.labels['provider_id'] == 'openai'
        assert sample.labels['provider_type'] == 'ai_model'
        assert sample.value == 1.0  # "open" state

    def test_update_provider_health(self, metrics):
        """Test provider health score update."""
        metrics.update_provider_health(
            provider_id="openai",
            provider_type="ai_model",
            region="us-east-1",
            health_score=85.5
        )
        
        samples = list(metrics.provider_health_score.collect())[0].samples
        assert len(samples) > 0
        
        sample = samples[0]
        assert sample.labels['provider_id'] == 'openai'
        assert sample.labels['provider_type'] == 'ai_model'
        assert sample.labels['region'] == 'us-east-1'
        assert sample.value == 85.5

    def test_record_database_query(self, metrics):
        """Test database query recording."""
        metrics.record_database_query(
            database_name="postgres",
            query_type="SELECT",
            table_name="children",
            duration=0.025,
            status="success"
        )
        
        # Check operations counter
        op_samples = list(metrics.database_operations_total.collect())[0].samples
        assert len(op_samples) > 0
        
        op_sample = op_samples[0]
        assert op_sample.labels['database_name'] == 'postgres'
        assert op_sample.labels['operation'] == 'SELECT'
        assert op_sample.labels['table_name'] == 'children'
        assert op_sample.labels['status'] == 'success'
        assert op_sample.value == 1.0

    def test_record_cache_operation(self, metrics):
        """Test cache operation recording."""
        metrics.record_cache_operation(
            cache_name="redis",
            operation="get",
            result="hit",
            duration=0.001
        )
        
        samples = list(metrics.cache_operations_total.collect())[0].samples
        assert len(samples) > 0
        
        sample = samples[0]
        assert sample.labels['cache_name'] == 'redis'
        assert sample.labels['operation'] == 'get'
        assert sample.labels['result'] == 'hit'
        assert sample.value == 1.0

    def test_record_security_event(self, metrics):
        """Test security event recording."""
        metrics.record_security_event(
            event_type="failed_login",
            severity="medium",
            action_taken="blocked",
            source_ip="192.168.1.100"
        )
        
        samples = list(metrics.security_violations_total.collect())[0].samples
        assert len(samples) > 0
        
        sample = samples[0]
        assert sample.labels['violation_type'] == 'failed_login'
        assert sample.labels['severity'] == 'medium'
        assert sample.labels['action_taken'] == 'blocked'
        assert sample.labels['source_ip'] == '192.168.1.100'
        assert sample.value == 1.0

    def test_record_ml_prediction(self, metrics):
        """Test ML prediction recording."""
        metrics.record_ml_prediction(
            model_name="gpt-4",
            model_version="1.0",
            prediction_type="text_generation",
            confidence_level="high",
            duration=2.5
        )
        
        # Check predictions counter
        pred_samples = list(metrics.ml_predictions_total.collect())[0].samples
        assert len(pred_samples) > 0
        
        pred_sample = pred_samples[0]
        assert pred_sample.labels['model_name'] == 'gpt-4'
        assert pred_sample.labels['model_version'] == '1.0'
        assert pred_sample.labels['prediction_type'] == 'text_generation'
        assert pred_sample.labels['confidence_level'] == 'high'
        assert pred_sample.value == 1.0

    def test_record_compliance_check(self, metrics):
        """Test compliance check recording."""
        metrics.record_compliance_check(
            check_type="coppa_age_verification",
            result="pass",
            data_type="child_data"
        )
        
        # Check COPPA compliance counter
        coppa_samples = list(metrics.coppa_compliance_checks_total.collect())[0].samples
        assert len(coppa_samples) > 0
        
        coppa_sample = coppa_samples[0]
        assert coppa_sample.labels['check_type'] == 'coppa_age_verification'
        assert coppa_sample.labels['result'] == 'pass'
        assert coppa_sample.labels['age_verification'] == 'true'
        assert coppa_sample.value == 1.0

    def test_get_metrics(self, metrics):
        """Test metrics export."""
        # Record some metrics first
        metrics.record_http_request("GET", "/test", 200, 0.1)
        
        metrics_output = metrics.get_metrics()
        
        assert isinstance(metrics_output, str)
        assert "http_requests_total" in metrics_output
        assert "# HELP" in metrics_output
        assert "# TYPE" in metrics_output

    def test_get_content_type(self, metrics):
        """Test content type for metrics."""
        content_type = metrics.get_content_type()
        assert content_type == "text/plain; version=0.0.4; charset=utf-8"


class TestPrometheusMiddleware:
    """Test Prometheus middleware functionality."""

    @pytest.fixture
    def metrics(self):
        """Create metrics instance."""
        registry = CollectorRegistry()
        return PrometheusMetrics(registry=registry)

    @pytest.fixture
    def middleware(self, metrics):
        """Create middleware instance."""
        app = Mock(spec=True)
        return PrometheusMiddleware(app, metrics)

    @pytest.mark.asyncio
    async def test_middleware_success_request(self, middleware):
        """Test middleware with successful request."""
        # Mock request
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/v1/children"
        request.headers = {"content-length": "100"}
        
        # Mock response
        response = Mock(spec=Response)
        response.status_code = 200
        response.headers = {"content-length": "500"}
        
        # Mock call_next
        async def mock_call_next(req):
            return response
        
        # Process request
        result = await middleware.dispatch(request, mock_call_next)
        
        assert result == response
        
        # Check that metrics were recorded
        samples = list(middleware.metrics.http_requests_total.collect())[0].samples
        assert len(samples) > 0

    @pytest.mark.asyncio
    async def test_middleware_error_request(self, middleware):
        """Test middleware with error request."""
        # Mock request
        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/error"
        request.headers = {"content-length": "200"}
        
        # Mock call_next that raises exception
        async def mock_call_next(req):
            raise ValueError("Test error")
        
        # Process request and expect exception
        with pytest.raises(ValueError, match="Test error"):
            await middleware.dispatch(request, mock_call_next)
        
        # Check that error metrics were recorded
        error_samples = list(middleware.metrics.http_errors_total.collect())[0].samples
        assert len(error_samples) > 0
        
        error_sample = error_samples[0]
        assert error_sample.labels['error_type'] == 'ValueError'

    def test_normalize_endpoint(self, middleware):
        """Test endpoint path normalization."""
        # Test UUID replacement
        path1 = "/api/v1/children/123e4567-e89b-12d3-a456-426614174000"
        normalized1 = middleware._normalize_endpoint(path1)
        assert normalized1 == "/api/v1/children/{id}"
        
        # Test numeric ID replacement
        path2 = "/api/v1/users/12345"
        normalized2 = middleware._normalize_endpoint(path2)
        assert normalized2 == "/api/v1/users/{id}"
        
        # Test long path truncation
        long_path = "/api/v1/" + "a" * 200
        normalized_long = middleware._normalize_endpoint(long_path)
        assert len(normalized_long) <= 103  # 100 + "..."

    def test_extract_user_type(self, middleware):
        """Test user type extraction."""
        # Test header-based extraction
        request1 = Mock(spec=Request)
        request1.headers = {"x-user-type": "parent"}
        user_type1 = middleware._extract_user_type(request1)
        assert user_type1 == "parent"
        
        # Test JWT-based extraction
        request2 = Mock(spec=Request)
        request2.headers = {
            "authorization": "Bearer parent_token_here",
            "x-user-type": "unknown"
        }
        user_type2 = middleware._extract_user_type(request2)
        assert user_type2 == "parent"
        
        # Test default
        request3 = Mock(spec=Request)
        request3.headers = {}
        user_type3 = middleware._extract_user_type(request3)
        assert user_type3 == "unknown"

    def test_extract_region(self, middleware):
        """Test region extraction."""
        # Test header-based extraction
        request1 = Mock(spec=Request)
        request1.headers = {"x-region": "us-west-2"}
        region1 = middleware._extract_region(request1)
        assert region1 == "us-west-2"
        
        # Test CloudFront header
        request2 = Mock(spec=Request)
        request2.headers = {"cloudfront-viewer-country": "US"}
        region2 = middleware._extract_region(request2)
        assert region2 == "us"
        
        # Test X-Forwarded-For
        request3 = Mock(spec=Request)
        request3.headers = {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}
        region3 = middleware._extract_region(request3)
        assert region3 == "local"


class TestAIMetricsCollector:
    """Test AI metrics collector."""

    @pytest.fixture
    def metrics(self):
        """Create metrics instance."""
        registry = CollectorRegistry()
        return PrometheusMetrics(registry=registry)

    @pytest.fixture
    def ai_metrics(self, metrics):
        """Create AI metrics collector."""
        return AIMetricsCollector(metrics)

    def test_record_ai_request(self, ai_metrics):
        """Test AI request recording."""
        ai_metrics.record_ai_request(
            model="gpt-4",
            provider="openai",
            status="success",
            duration=2.5,
            prompt_tokens=100,
            completion_tokens=50,
            cost_estimate=0.05,
            child_age_group="middle_childhood"
        )
        
        # Check provider requests
        provider_samples = list(ai_metrics.metrics.provider_requests_total.collect())[0].samples
        assert len(provider_samples) > 0
        
        provider_sample = provider_samples[0]
        assert provider_sample.labels['provider_id'] == 'openai'
        assert provider_sample.labels['provider_type'] == 'ai_model'
        assert provider_sample.labels['operation'] == 'generate_gpt-4'
        assert provider_sample.labels['status'] == 'success'
        assert provider_sample.value == 1.0

    def test_record_tts_request(self, ai_metrics):
        """Test TTS request recording."""
        ai_metrics.record_tts_request(
            provider="openai",
            voice_id="alloy",
            language="en",
            status="success",
            duration=1.2,
            character_count=150,
            cost_usd=0.03,
            cached=False,
            model="tts-1",
            content_type="story"
        )
        
        # Check TTS requests
        tts_samples = list(ai_metrics.metrics.tts_requests_total.collect())[0].samples
        assert len(tts_samples) > 0
        
        tts_sample = tts_samples[0]
        assert tts_sample.labels['provider'] == 'openai'
        assert tts_sample.labels['voice_id'] == 'alloy'
        assert tts_sample.labels['language'] == 'en'
        assert tts_sample.labels['status'] == 'success'
        assert tts_sample.labels['cached'] == 'fresh'
        assert tts_sample.value == 1.0

    def test_record_audio_validation(self, ai_metrics):
        """Test audio validation recording."""
        ai_metrics.record_audio_validation(
            audio_format="wav",
            result="valid",
            error_type="none",
            quality_score=0.85,
            age_group="early_childhood"
        )
        
        # Check validation metrics
        validation_samples = list(ai_metrics.metrics.audio_validation_checks_total.collect())[0].samples
        assert len(validation_samples) > 0
        
        validation_sample = validation_samples[0]
        assert validation_sample.labels['format'] == 'wav'
        assert validation_sample.labels['result'] == 'valid'
        assert validation_sample.labels['error_type'] == 'none'
        assert validation_sample.value == 1.0

    def test_record_audio_safety_check(self, ai_metrics):
        """Test audio safety check recording."""
        ai_metrics.record_audio_safety_check(
            check_type="content_filter",
            result="safe",
            child_age=8,
            violations=["inappropriate_language"],
            action_taken="filtered"
        )
        
        # Check safety checks
        safety_samples = list(ai_metrics.metrics.audio_safety_checks_total.collect())[0].samples
        assert len(safety_samples) > 0
        
        safety_sample = safety_samples[0]
        assert safety_sample.labels['check_type'] == 'content_filter'
        assert safety_sample.labels['result'] == 'safe'
        assert safety_sample.labels['child_age_group'] == 'middle_childhood'
        assert safety_sample.value == 1.0

    def test_record_stt_request(self, ai_metrics):
        """Test STT request recording."""
        ai_metrics.record_stt_request(
            provider="whisper",
            language="en",
            status="success",
            duration=0.8,
            confidence=0.95
        )
        
        # Check STT requests
        stt_samples = list(ai_metrics.metrics.stt_requests_total.collect())[0].samples
        assert len(stt_samples) > 0
        
        stt_sample = stt_samples[0]
        assert stt_sample.labels['provider'] == 'whisper'
        assert stt_sample.labels['language'] == 'en'
        assert stt_sample.labels['status'] == 'success'
        assert stt_sample.value == 1.0

    def test_record_child_audio_session(self, ai_metrics):
        """Test child audio session recording."""
        ai_metrics.record_child_audio_session(
            child_age=7,
            session_type="interactive_story",
            duration_seconds=180,
            content_type="educational"
        )
        
        # Check session metrics
        session_samples = list(ai_metrics.metrics.child_audio_sessions_total.collect())[0].samples
        assert len(session_samples) > 0
        
        session_sample = session_samples[0]
        assert session_sample.labels['age_group'] == 'middle_childhood'
        assert session_sample.labels['session_type'] == 'interactive_story'
        assert session_sample.labels['duration_bucket'] == 'medium'
        assert session_sample.value == 1.0

    def test_get_age_group(self, ai_metrics):
        """Test age group classification."""
        assert ai_metrics._get_age_group(0) == "unknown"
        assert ai_metrics._get_age_group(3) == "early_childhood"
        assert ai_metrics._get_age_group(7) == "middle_childhood"
        assert ai_metrics._get_age_group(10) == "late_childhood"
        assert ai_metrics._get_age_group(15) == "adolescent"


class TestSafetyMetricsCollector:
    """Test safety metrics collector."""

    @pytest.fixture
    def metrics(self):
        """Create metrics instance."""
        registry = CollectorRegistry()
        return PrometheusMetrics(registry=registry)

    @pytest.fixture
    def safety_metrics(self, metrics):
        """Create safety metrics collector."""
        return SafetyMetricsCollector(metrics)

    def test_record_safety_check(self, safety_metrics):
        """Test safety check recording."""
        safety_metrics.record_safety_check(
            check_type="inappropriate_content",
            result="violation",
            severity="high",
            age_group="early_childhood"
        )
        
        # Check safety violations
        violation_samples = list(safety_metrics.metrics.safety_violations_total.collect())[0].samples
        assert len(violation_samples) > 0
        
        violation_sample = violation_samples[0]
        assert violation_sample.labels['violation_type'] == 'inappropriate_content'
        assert violation_sample.labels['severity'] == 'high'
        assert violation_sample.labels['action_taken'] == 'blocked'
        assert violation_sample.labels['age_group'] == 'early_childhood'
        assert violation_sample.value == 1.0

    def test_record_coppa_check(self, safety_metrics):
        """Test COPPA check recording."""
        safety_metrics.record_coppa_check(
            check_type="age_verification",
            result="pass",
            action_taken="approved"
        )
        
        # Check COPPA compliance
        coppa_samples = list(safety_metrics.metrics.coppa_compliance_checks_total.collect())[0].samples
        assert len(coppa_samples) > 0
        
        coppa_sample = coppa_samples[0]
        assert coppa_sample.labels['check_type'] == 'coppa_age_verification'
        assert coppa_sample.labels['result'] == 'pass'
        assert coppa_sample.labels['age_verification'] == 'true'
        assert coppa_sample.value == 1.0

    def test_record_content_filter_action(self, safety_metrics):
        """Test content filter action recording."""
        safety_metrics.record_content_filter_action(
            action_type="blocked",
            content_type="text",
            severity="medium"
        )
        
        # Check security violations
        security_samples = list(safety_metrics.metrics.security_violations_total.collect())[0].samples
        assert len(security_samples) > 0
        
        security_sample = security_samples[0]
        assert security_sample.labels['violation_type'] == 'content_filter_blocked'
        assert security_sample.labels['severity'] == 'medium'
        assert security_sample.labels['action_taken'] == 'blocked'
        assert security_sample.value == 1.0

    def test_record_parental_consent(self, safety_metrics):
        """Test parental consent recording."""
        safety_metrics.record_parental_consent(
            event_type="granted",
            status="active"
        )
        
        # Check compliance metrics
        coppa_samples = list(safety_metrics.metrics.coppa_compliance_checks_total.collect())[0].samples
        assert len(coppa_samples) > 0
        
        # Check notifications
        notification_samples = list(safety_metrics.metrics.parent_notifications_total.collect())[0].samples
        assert len(notification_samples) > 0
        
        notification_sample = notification_samples[0]
        assert notification_sample.labels['notification_type'] == 'consent_update'
        assert notification_sample.labels['channel'] == 'system'
        assert notification_sample.value == 1.0


class TestMetricsDecorator:
    """Test metrics decorator functionality."""

    @pytest.fixture
    def metrics(self):
        """Create metrics instance."""
        registry = CollectorRegistry()
        return PrometheusMetrics(registry=registry)

    @pytest.mark.asyncio
    async def test_async_function_decorator(self, metrics):
        """Test decorator with async function."""
        @metrics_decorator(metrics, MetricType.BUSINESS)
        async def test_async_function():
            await asyncio.sleep(0.01)
            return "success"
        
        result = await test_async_function()
        assert result == "success"
        
        # Check that metrics were recorded
        samples = list(metrics.child_interactions_total.collect())[0].samples
        assert len(samples) > 0

    def test_sync_function_decorator(self, metrics):
        """Test decorator with sync function."""
        @metrics_decorator(metrics, MetricType.BUSINESS)
        def test_sync_function():
            time.sleep(0.01)
            return "success"
        
        result = test_sync_function()
        assert result == "success"
        
        # Check that metrics were recorded
        samples = list(metrics.child_interactions_total.collect())[0].samples
        assert len(samples) > 0

    @pytest.mark.asyncio
    async def test_decorator_with_exception(self, metrics):
        """Test decorator with function that raises exception."""
        @metrics_decorator(metrics, MetricType.BUSINESS)
        async def test_failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await test_failing_function()
        
        # Check that error metrics were recorded
        error_samples = list(metrics.http_errors_total.collect())[0].samples
        assert len(error_samples) > 0


class TestLegacyCompatibility:
    """Test legacy compatibility functions."""

    def test_get_metrics_response(self):
        """Test legacy metrics response function."""
        response = get_metrics_response()
        
        assert hasattr(response, 'body') or hasattr(response, 'content')
        assert response.media_type == "text/plain; version=0.0.4; charset=utf-8"

    def test_global_metrics_instances(self):
        """Test global metrics instances."""
        from src.infrastructure.monitoring.prometheus_metrics import (
            prometheus_metrics,
            ai_metrics,
            safety_metrics
        )
        
        assert prometheus_metrics is not None
        assert ai_metrics is not None
        assert safety_metrics is not None
        
        assert isinstance(ai_metrics, AIMetricsCollector)
        assert isinstance(safety_metrics, SafetyMetricsCollector)


class TestMetricsIntegration:
    """Test metrics integration scenarios."""

    @pytest.fixture
    def metrics(self):
        """Create metrics instance."""
        registry = CollectorRegistry()
        return PrometheusMetrics(registry=registry)

    def test_comprehensive_request_flow(self, metrics):
        """Test complete request flow with all metrics."""
        # Simulate HTTP request
        metrics.record_http_request(
            method="POST",
            endpoint="/api/v1/children/{id}/stories",
            status_code=200,
            duration=1.5,
            request_size=512,
            response_size=2048,
            user_type="parent",
            region="us-east-1"
        )
        
        # Simulate child interaction
        metrics.record_child_interaction(
            interaction_type="story_generation",
            age_group="middle_childhood",
            language="en",
            safety_status="safe"
        )
        
        # Simulate AI provider call
        metrics.record_provider_request(
            provider_id="openai",
            provider_type="ai_model",
            operation="text_generation",
            status="success",
            duration=1.2,
            cost=0.08
        )
        
        # Simulate database query
        metrics.record_database_query(
            database_name="postgres",
            query_type="INSERT",
            table_name="stories",
            duration=0.05,
            status="success"
        )
        
        # Simulate cache operation
        metrics.record_cache_operation(
            cache_name="redis",
            operation="set",
            result="success",
            duration=0.002
        )
        
        # Verify all metrics were recorded
        http_samples = list(metrics.http_requests_total.collect())[0].samples
        assert len(http_samples) > 0
        
        interaction_samples = list(metrics.child_interactions_total.collect())[0].samples
        assert len(interaction_samples) > 0
        
        provider_samples = list(metrics.provider_requests_total.collect())[0].samples
        assert len(provider_samples) > 0
        
        db_samples = list(metrics.database_operations_total.collect())[0].samples
        assert len(db_samples) > 0
        
        cache_samples = list(metrics.cache_operations_total.collect())[0].samples
        assert len(cache_samples) > 0

    def test_error_scenario_metrics(self, metrics):
        """Test error scenario metrics recording."""
        # Simulate failed request
        metrics.record_http_request(
            method="GET",
            endpoint="/api/v1/error",
            status_code=500,
            duration=0.1,
            user_type="parent"
        )
        
        # Simulate security violation
        metrics.record_security_event(
            event_type="rate_limit_exceeded",
            severity="high",
            action_taken="blocked",
            source_ip="192.168.1.100"
        )
        
        # Simulate provider failure
        metrics.record_provider_request(
            provider_id="openai",
            provider_type="ai_model",
            operation="text_generation",
            status="error",
            duration=30.0  # Timeout
        )
        
        # Verify error metrics
        http_samples = list(metrics.http_requests_total.collect())[0].samples
        error_sample = next(s for s in http_samples if s.labels['status_code'] == '500')
        assert error_sample.value == 1.0
        
        security_samples = list(metrics.security_violations_total.collect())[0].samples
        assert len(security_samples) > 0
        
        provider_samples = list(metrics.provider_requests_total.collect())[0].samples
        error_provider_sample = next(s for s in provider_samples if s.labels['status'] == 'error')
        assert error_provider_sample.value == 1.0