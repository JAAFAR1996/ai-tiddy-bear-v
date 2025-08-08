"""
Tests for ParentDashboard - real dashboard functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import uuid

from src.adapters.dashboard.parent_dashboard import (
    ProductionParentDashboard,
    DashboardServiceProvider,
    DashboardDataTransformer,
    DashboardCache,
    DashboardSection,
    CacheStatus,
    create_parent_dashboard,
    create_test_dashboard
)
from src.infrastructure.exceptions import ValidationError, ServiceError


class TestDashboardDataTransformer:
    @pytest.fixture
    def transformer(self):
        return DashboardDataTransformer()

    def test_transform_child_data_success(self, transformer):
        mock_child = Mock()
        mock_child.id = uuid.uuid4()
        mock_child.name = "Ahmed"
        mock_child.age = 8
        mock_child.is_active = True
        
        activity_data = {
            "last_activity": datetime.now(),
            "safety_status": "safe",
            "daily_usage_minutes": 45,
            "safety_violations": 0,
            "recent_emotions": ["happy", "curious"],
            "parental_controls_enabled": True
        }
        
        result = transformer.transform_child_data(mock_child, activity_data)
        
        assert result.child_id == str(mock_child.id)
        assert result.name == "Ahmed"
        assert result.age == 8
        assert result.age_group == "school_age"
        assert result.safety_status == "safe"
        assert result.daily_usage_minutes == 45
        assert result.recent_emotions == ["happy", "curious"]

    def test_transform_child_data_error_handling(self, transformer):
        # Test with invalid child object
        mock_child = Mock()
        mock_child.id = "invalid-id"  # This will cause error
        mock_child.name = "Ahmed"
        
        result = transformer.transform_child_data(mock_child, {})
        
        # Should return safe defaults
        assert result.name == "Ahmed"
        assert result.age == 0
        assert result.age_group == "unknown"
        assert result.safety_status == "unknown"
        assert result.is_active is False

    def test_transform_safety_data_success(self, transformer):
        safety_data = {
            "overall_status": "safe",
            "total_violations": 2,
            "recent_violations": [{"type": "mild", "timestamp": datetime.now()}],
            "content_filter_level": "strict",
            "active_restrictions": ["time_limit"],
            "requires_attention": False
        }
        
        result = transformer.transform_safety_data(safety_data)
        
        assert result.overall_status == "safe"
        assert result.total_violations == 2
        assert result.content_filter_level == "strict"
        assert result.requires_attention is False

    def test_transform_safety_data_error_handling(self, transformer):
        # Test with invalid data
        result = transformer.transform_safety_data({})
        
        # Should return safe defaults
        assert result.overall_status == "unknown"
        assert result.total_violations == 0
        assert result.content_filter_level == "strict"
        assert result.requires_attention is False

    def test_transform_usage_data_success(self, transformer):
        usage_data = {
            "total_sessions_today": 3,
            "total_time_today_minutes": 90,
            "average_session_duration": 30.0,
            "peak_usage_hours": [16, 17, 19],
            "weekly_trend": {"Mon": 30, "Tue": 45},
            "screen_time_limits": {"weekday": 60},
            "exceeded_limits": []
        }
        
        result = transformer.transform_usage_data(usage_data)
        
        assert result.total_sessions_today == 3
        assert result.total_time_today_minutes == 90
        assert result.average_session_duration == 30.0
        assert result.peak_usage_hours == [16, 17, 19]

    def test_transform_notification_data_success(self, transformer):
        notification_data = {
            "unread_count": 5,
            "priority_notifications": [{"message": "High priority"}],
            "recent_notifications": [{"message": "Recent"}],
            "notification_types": {"safety": 2, "usage": 3},
            "last_checked": datetime.now()
        }
        
        result = transformer.transform_notification_data(notification_data)
        
        assert result.unread_count == 5
        assert len(result.priority_notifications) == 1
        assert result.notification_types["safety"] == 2


class TestDashboardCache:
    @pytest.fixture
    def cache(self):
        return DashboardCache(default_ttl_minutes=5)

    def test_get_cache_key(self, cache):
        key1 = cache._get_cache_key("parent-123")
        key2 = cache._get_cache_key("parent-123", "children")
        
        assert key1 == "dashboard:parent-123:full"
        assert key2 == "dashboard:parent-123:children"

    def test_set_and_get_success(self, cache):
        parent_id = "parent-123"
        data = {"test": "data"}
        
        cache.set(parent_id, data)
        result = cache.get(parent_id)
        
        assert result == data

    def test_get_expired(self, cache):
        parent_id = "parent-123"
        data = {"test": "data"}
        
        # Set with very short TTL
        cache.set(parent_id, data, ttl=timedelta(microseconds=1))
        
        # Wait a bit and try to get
        import time
        time.sleep(0.001)
        
        result = cache.get(parent_id)
        assert result is None

    def test_get_nonexistent(self, cache):
        result = cache.get("nonexistent-parent")
        assert result is None

    def test_invalidate_specific_section(self, cache):
        parent_id = "parent-123"
        cache.set(parent_id, {"data": "full"})
        cache.set(parent_id, {"data": "children"}, section="children")
        
        cache.invalidate(parent_id, "children")
        
        assert cache.get(parent_id) is not None  # Full data still there
        assert cache.get(parent_id, "children") is None  # Section data removed

    def test_invalidate_all_sections(self, cache):
        parent_id = "parent-123"
        cache.set(parent_id, {"data": "full"})
        cache.set(parent_id, {"data": "children"}, section="children")
        
        cache.invalidate(parent_id)
        
        assert cache.get(parent_id) is None
        assert cache.get(parent_id, "children") is None

    def test_cleanup_expired(self, cache):
        # Add expired entries
        cache.set("parent-1", {"data": "1"}, ttl=timedelta(microseconds=1))
        cache.set("parent-2", {"data": "2"}, ttl=timedelta(microseconds=1))
        cache.set("parent-3", {"data": "3"})  # Not expired
        
        import time
        time.sleep(0.001)
        
        cleaned_count = cache.cleanup_expired()
        
        assert cleaned_count == 2
        assert cache.get("parent-3") is not None


class TestDashboardServiceProvider:
    def test_init_with_services(self):
        mock_user_service = Mock()
        mock_safety_service = Mock()
        
        provider = DashboardServiceProvider(
            user_service=mock_user_service,
            safety_service=mock_safety_service
        )
        
        assert provider._user_service == mock_user_service
        assert provider._safety_service == mock_safety_service

    @pytest.mark.asyncio
    async def test_get_user_service_with_override(self):
        mock_service = Mock()
        provider = DashboardServiceProvider(user_service=mock_service)
        
        result = await provider.get_user_service()
        
        assert result == mock_service

    @pytest.mark.asyncio
    async def test_get_user_service_from_registry(self):
        provider = DashboardServiceProvider()
        
        with patch('src.adapters.dashboard.parent_dashboard.get_user_service') as mock_get:
            mock_service = Mock()
            mock_get.return_value = mock_service
            
            result = await provider.get_user_service()
            
            assert result == mock_service


class TestProductionParentDashboard:
    @pytest.fixture
    def mock_service_provider(self):
        provider = Mock()
        provider.get_user_service = AsyncMock()
        provider.get_safety_service = AsyncMock()
        provider.get_ai_service = AsyncMock()
        provider.get_notification_service = AsyncMock()
        return provider

    @pytest.fixture
    def dashboard(self, mock_service_provider):
        return ProductionParentDashboard(
            service_provider=mock_service_provider,
            enable_caching=False
        )

    def test_init_default(self):
        dashboard = ProductionParentDashboard()
        
        assert dashboard.service_provider is not None
        assert dashboard.transformer is not None
        assert dashboard.request_count == 0

    def test_init_with_cache(self):
        cache = DashboardCache()
        dashboard = ProductionParentDashboard(cache=cache, enable_caching=True)
        
        assert dashboard.cache == cache
        assert dashboard.enable_caching is True

    def test_validate_parent_id_valid(self, dashboard):
        valid_uuid = str(uuid.uuid4())
        result = dashboard._validate_parent_id(valid_uuid)
        assert result == valid_uuid

    def test_validate_parent_id_invalid(self, dashboard):
        with pytest.raises(ValidationError) as exc:
            dashboard._validate_parent_id("invalid-uuid")
        assert "Invalid parent ID format" in str(exc.value)

    def test_validate_parent_id_empty(self, dashboard):
        with pytest.raises(ValidationError) as exc:
            dashboard._validate_parent_id("")
        assert "cannot be empty" in str(exc.value)

    def test_validate_child_id_valid(self, dashboard):
        valid_uuid = str(uuid.uuid4())
        result = dashboard._validate_child_id(valid_uuid)
        assert result == valid_uuid

    @pytest.mark.asyncio
    async def test_safe_service_call_success(self, dashboard):
        async def mock_operation():
            return "success"
        
        result = await dashboard._safe_service_call(
            mock_operation,
            "test_operation",
            "correlation-123"
        )
        
        assert result == "success"

    @pytest.mark.asyncio
    async def test_safe_service_call_with_fallback(self, dashboard):
        async def failing_operation():
            raise Exception("Service failed")
        
        result = await dashboard._safe_service_call(
            failing_operation,
            "test_operation",
            "correlation-123",
            fallback_result="fallback"
        )
        
        assert result == "fallback"
        assert dashboard.error_count == 1

    @pytest.mark.asyncio
    async def test_safe_service_call_without_fallback(self, dashboard):
        async def failing_operation():
            raise Exception("Service failed")
        
        with pytest.raises(ServiceError) as exc:
            await dashboard._safe_service_call(
                failing_operation,
                "test_operation",
                "correlation-123"
            )
        
        assert "Service operation failed" in str(exc.value)

    @pytest.mark.asyncio
    async def test_load_children_data_success(self, dashboard):
        parent_id = str(uuid.uuid4())
        
        # Mock children data
        mock_child = Mock()
        mock_child.id = uuid.uuid4()
        mock_child.name = "Ahmed"
        mock_child.age = 8
        
        mock_user_service = Mock()
        mock_user_service.get_children = AsyncMock(return_value=[mock_child])
        dashboard.service_provider.get_user_service.return_value = mock_user_service
        
        with patch.object(dashboard, '_get_child_activity') as mock_activity:
            mock_activity.return_value = {"safety_status": "safe"}
            
            result = await dashboard._load_children_data(parent_id, "correlation-123")
            
            assert len(result) == 1
            assert result[0].name == "Ahmed"
            assert result[0].age == 8

    @pytest.mark.asyncio
    async def test_load_children_data_service_error(self, dashboard):
        parent_id = str(uuid.uuid4())
        
        mock_user_service = Mock()
        mock_user_service.get_children = AsyncMock(side_effect=Exception("Service error"))
        dashboard.service_provider.get_user_service.return_value = mock_user_service
        
        result = await dashboard._load_children_data(parent_id, "correlation-123")
        
        # Should return empty list on error
        assert result == []

    @pytest.mark.asyncio
    async def test_get_child_activity(self, dashboard):
        child_id = str(uuid.uuid4())
        
        result = await dashboard._get_child_activity(child_id, "correlation-123")
        
        # Should return mock activity data
        assert "last_activity" in result
        assert "safety_status" in result
        assert result["safety_status"] == "safe"

    @pytest.mark.asyncio
    async def test_load_safety_data_success(self, dashboard):
        parent_id = str(uuid.uuid4())
        
        mock_safety_service = Mock()
        mock_safety_service.get_safety_overview = AsyncMock(return_value={
            "overall_status": "safe",
            "total_violations": 0
        })
        dashboard.service_provider.get_safety_service.return_value = mock_safety_service
        
        result = await dashboard._load_safety_data(parent_id, "correlation-123")
        
        assert result.overall_status == "safe"
        assert result.total_violations == 0

    @pytest.mark.asyncio
    async def test_get_dashboard_data_success(self, dashboard):
        parent_id = str(uuid.uuid4())
        
        # Mock all services
        mock_user_service = Mock()
        mock_user_service.get_children = AsyncMock(return_value=[])
        dashboard.service_provider.get_user_service.return_value = mock_user_service
        
        mock_safety_service = Mock()
        mock_safety_service.get_safety_overview = AsyncMock(return_value={})
        dashboard.service_provider.get_safety_service.return_value = mock_safety_service
        
        mock_notification_service = Mock()
        mock_notification_service.get_notifications = AsyncMock(return_value={})
        dashboard.service_provider.get_notification_service.return_value = mock_notification_service
        
        with patch.object(dashboard, '_get_usage_summary') as mock_usage:
            mock_usage.return_value = {}
            
            result = await dashboard.get_dashboard_data(str(parent_id))
            
            assert result is not None
            assert result.children == []
            assert result.metrics.child_count == 0
            assert result.metrics.cache_status == CacheStatus.MISS

    @pytest.mark.asyncio
    async def test_get_dashboard_data_with_cache(self):
        cache = DashboardCache()
        dashboard = ProductionParentDashboard(cache=cache, enable_caching=True)
        parent_id = str(uuid.uuid4())
        
        # Mock cached data
        from src.adapters.dashboard.parent_dashboard import DashboardData, DashboardMetrics
        cached_data = DashboardData(
            children=[],
            safety=dashboard.transformer.transform_safety_data({}),
            usage=dashboard.transformer.transform_usage_data({}),
            notifications=dashboard.transformer.transform_notification_data({}),
            metrics=DashboardMetrics(
                load_time_ms=100,
                cache_status=CacheStatus.HIT,
                sections_loaded=["all"],
                errors_encountered=[],
                child_count=0,
                data_freshness_minutes=0,
                correlation_id="test-123"
            ),
            generated_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        
        cache.set(parent_id, cached_data)
        
        result = await dashboard.get_dashboard_data(parent_id)
        
        assert result.metrics.cache_status == CacheStatus.HIT

    @pytest.mark.asyncio
    async def test_get_dashboard_data_invalid_parent_id(self, dashboard):
        with pytest.raises(ValidationError) as exc:
            await dashboard.get_dashboard_data("invalid-uuid")
        
        assert "Invalid parent ID format" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_child_details_success(self, dashboard):
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())
        
        # Mock child data
        mock_child = Mock()
        mock_child.id = uuid.UUID(child_id)
        mock_child.parent_id = uuid.UUID(parent_id)
        mock_child.name = "Ahmed"
        mock_child.age = 8
        
        mock_user_service = Mock()
        mock_user_service.get_child = AsyncMock(return_value=mock_child)
        dashboard.service_provider.get_user_service.return_value = mock_user_service
        
        mock_safety_service = Mock()
        mock_safety_service.get_child_safety_status = AsyncMock(return_value={})
        dashboard.service_provider.get_safety_service.return_value = mock_safety_service
        
        with patch.object(dashboard, '_get_child_activity') as mock_activity:
            mock_activity.return_value = {}
            
            result = await dashboard.get_child_details(parent_id, child_id)
            
            assert result["basic_info"].name == "Ahmed"
            assert result["basic_info"].age == 8
            assert "safety_details" in result
            assert "correlation_id" in result

    @pytest.mark.asyncio
    async def test_get_child_details_child_not_found(self, dashboard):
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())
        
        mock_user_service = Mock()
        mock_user_service.get_child = AsyncMock(return_value=None)
        dashboard.service_provider.get_user_service.return_value = mock_user_service
        
        with pytest.raises(ValidationError) as exc:
            await dashboard.get_child_details(parent_id, child_id)
        
        assert "not found" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_child_details_wrong_parent(self, dashboard):
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())
        different_parent_id = str(uuid.uuid4())
        
        mock_child = Mock()
        mock_child.id = uuid.UUID(child_id)
        mock_child.parent_id = uuid.UUID(different_parent_id)  # Different parent
        
        mock_user_service = Mock()
        mock_user_service.get_child = AsyncMock(return_value=mock_child)
        dashboard.service_provider.get_user_service.return_value = mock_user_service
        
        with pytest.raises(ValidationError) as exc:
            await dashboard.get_child_details(parent_id, child_id)
        
        assert "does not belong" in str(exc.value)

    def test_invalidate_cache(self):
        cache = DashboardCache()
        dashboard = ProductionParentDashboard(cache=cache, enable_caching=True)
        parent_id = str(uuid.uuid4())
        
        # Add some cached data
        cache.set(parent_id, {"data": "test"})
        cache.set(parent_id, {"data": "children"}, section="children")
        
        # Invalidate specific section
        dashboard.invalidate_cache(parent_id, DashboardSection.CHILDREN)
        
        assert cache.get(parent_id) is not None  # Full data still there
        assert cache.get(parent_id, "children") is None  # Section removed

    def test_get_performance_metrics(self, dashboard):
        dashboard.request_count = 100
        dashboard.error_count = 5
        dashboard.cache_hits = 30
        dashboard.cache_misses = 70
        
        metrics = dashboard.get_performance_metrics()
        
        assert metrics["total_requests"] == 100
        assert metrics["error_count"] == 5
        assert metrics["error_rate"] == 0.05
        assert metrics["cache_hit_rate"] == 0.3


class TestFactoryFunctions:
    def test_create_parent_dashboard_default(self):
        dashboard = create_parent_dashboard()
        
        assert isinstance(dashboard, ProductionParentDashboard)
        assert dashboard.enable_caching is True
        assert dashboard.cache is not None

    def test_create_parent_dashboard_no_cache(self):
        dashboard = create_parent_dashboard(enable_caching=False)
        
        assert dashboard.enable_caching is False
        assert dashboard.cache is None

    def test_create_test_dashboard(self):
        mock_user_service = Mock()
        mock_safety_service = Mock()
        
        dashboard = create_test_dashboard(
            mock_user_service=mock_user_service,
            mock_safety_service=mock_safety_service
        )
        
        assert isinstance(dashboard, ProductionParentDashboard)
        assert dashboard.enable_caching is False
        assert dashboard.service_provider._user_service == mock_user_service
        assert dashboard.service_provider._safety_service == mock_safety_service