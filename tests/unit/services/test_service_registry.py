"""
Unit tests for ServiceRegistry.
Tests service registration, dependency injection, and lifecycle management.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from src.services.service_registry import ServiceRegistry


class TestServiceRegistry:
    """Test suite for service registry functionality."""

    @pytest.fixture
    def test_config(self) -> Dict[str, Any]:
        """Test configuration for service registry."""
        return {
            "OPENAI_API_KEY": "sk-test",
            "DATABASE_URL": "postgresql://test",
            "REDIS_URL": "redis://test",
            "COPPA_ENCRYPTION_KEY": "test-key-32-chars",
            "ENVIRONMENT": "test"
        }

    @pytest.fixture
    def registry(self, test_config):
        """Create service registry instance."""
        with patch("src.services.service_registry.logger"):
            return ServiceRegistry(config=test_config)

    def test_registry_initialization(self, test_config):
        """Test service registry initializes correctly."""
        registry = ServiceRegistry(config=test_config)
        
        assert registry.config == test_config
        assert isinstance(registry._services, dict)
        assert isinstance(registry._factories, dict)
        assert isinstance(registry._singletons, dict)
        assert hasattr(registry, "_lock")

    def test_registry_default_config(self):
        """Test service registry with no config."""
        registry = ServiceRegistry()
        
        assert registry.config == {}
        assert len(registry._services) == 0
        assert len(registry._factories) == 0
        assert len(registry._singletons) == 0

    @pytest.mark.asyncio
    async def test_register_singleton_service(self, registry):
        """Test registering a singleton service."""
        # Mock factory
        mock_service = Mock()
        mock_factory = AsyncMock(return_value=mock_service)
        
        # Register service
        registry.register_singleton(
            service_name="test_service",
            factory=mock_factory,
            dependencies=[]
        )
        
        # Verify registration
        assert "test_service" in registry._factories
        assert registry._factories["test_service"] == mock_factory

    @pytest.mark.asyncio
    async def test_get_singleton_service(self, registry):
        """Test getting a singleton service (created once)."""
        # Mock service and factory
        mock_service = Mock()
        mock_factory = AsyncMock(return_value=mock_service)
        
        # Register
        registry.register_singleton(
            service_name="singleton_test",
            factory=mock_factory,
            dependencies=[]
        )
        
        # Get service multiple times
        service1 = await registry.get_service("singleton_test")
        service2 = await registry.get_service("singleton_test")
        service3 = await registry.get_service("singleton_test")
        
        # Should be same instance
        assert service1 is service2
        assert service2 is service3
        
        # Factory called only once
        mock_factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_service_with_dependencies(self, registry):
        """Test getting service with dependencies."""
        # Mock dependencies
        dep1 = Mock()
        dep2 = Mock()
        dep1_factory = AsyncMock(return_value=dep1)
        dep2_factory = AsyncMock(return_value=dep2)
        
        # Register dependencies
        registry.register_singleton("dependency1", dep1_factory, [])
        registry.register_singleton("dependency2", dep2_factory, [])
        
        # Mock main service that needs dependencies
        main_service = Mock()
        async def main_factory(d1, d2):
            assert d1 is dep1
            assert d2 is dep2
            return main_service
        
        registry.register_singleton(
            "main_service",
            main_factory,
            ["dependency1", "dependency2"]
        )
        
        # Get main service
        service = await registry.get_service("main_service")
        
        assert service is main_service
        # Dependencies should be created
        dep1_factory.assert_called_once()
        dep2_factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, registry):
        """Test detection of circular dependencies."""
        # Create circular dependency
        async def factory_a(b):
            return Mock()
        
        async def factory_b(a):
            return Mock()
        
        registry.register_singleton("service_a", factory_a, ["service_b"])
        registry.register_singleton("service_b", factory_b, ["service_a"])
        
        # Should raise error or handle gracefully
        with pytest.raises(Exception):  # Specific exception type depends on implementation
            await registry.get_service("service_a")

    @pytest.mark.asyncio
    async def test_get_nonexistent_service(self, registry):
        """Test getting a service that doesn't exist."""
        with pytest.raises(KeyError):
            await registry.get_service("nonexistent_service")

    @pytest.mark.asyncio
    async def test_register_factory_service(self, registry):
        """Test registering a factory (non-singleton) service."""
        call_count = 0
        
        async def factory():
            nonlocal call_count
            call_count += 1
            return Mock(id=call_count)
        
        registry.register_factory("factory_service", factory)
        
        # Get service multiple times
        service1 = await registry.get_service("factory_service")
        service2 = await registry.get_service("factory_service")
        service3 = await registry.get_service("factory_service")
        
        # Should be different instances
        assert service1 is not service2
        assert service2 is not service3
        assert service1.id == 1
        assert service2.id == 2
        assert service3.id == 3

    @pytest.mark.asyncio
    async def test_concurrent_singleton_access(self, registry):
        """Test concurrent access to singleton doesn't create multiple instances."""
        creation_count = 0
        creation_lock = asyncio.Lock()
        
        async def slow_factory():
            nonlocal creation_count
            async with creation_lock:
                creation_count += 1
                await asyncio.sleep(0.1)  # Simulate slow initialization
                return Mock(instance_id=creation_count)
        
        registry.register_singleton("concurrent_test", slow_factory, [])
        
        # Access concurrently
        tasks = [
            registry.get_service("concurrent_test")
            for _ in range(10)
        ]
        services = await asyncio.gather(*tasks)
        
        # All should be same instance
        first_service = services[0]
        assert all(s is first_service for s in services)
        assert creation_count == 1

    @pytest.mark.asyncio
    async def test_service_initialization_error(self, registry):
        """Test handling of service initialization errors."""
        async def failing_factory():
            raise RuntimeError("Service initialization failed")
        
        registry.register_singleton("failing_service", failing_factory, [])
        
        with pytest.raises(RuntimeError) as exc_info:
            await registry.get_service("failing_service")
        
        assert "Service initialization failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_ai_service(self, registry):
        """Test getting AI service through registry."""
        with patch("src.services.service_registry.ConsolidatedAIService") as MockAI:
            mock_ai = Mock()
            MockAI.return_value = mock_ai
            
            # Override factory
            registry._factories["ai_service"] = AsyncMock(return_value=mock_ai)
            
            service = await registry.get_ai_service()
            assert service is mock_ai

    @pytest.mark.asyncio
    async def test_get_child_safety_service(self, registry):
        """Test getting child safety service."""
        with patch("src.services.service_registry.ChildSafetyService") as MockSafety:
            mock_safety = Mock()
            MockSafety.return_value = mock_safety
            
            registry._factories["child_safety_service"] = AsyncMock(return_value=mock_safety)
            
            service = await registry.get_child_safety_service()
            assert service is mock_safety

    @pytest.mark.asyncio
    async def test_get_conversation_service(self, registry):
        """Test getting conversation service."""
        with patch("src.services.service_registry.ConsolidatedConversationService") as MockConv:
            mock_conv = Mock()
            MockConv.return_value = mock_conv
            
            registry._factories["conversation_service"] = AsyncMock(return_value=mock_conv)
            
            service = await registry.get_conversation_service()
            assert service is mock_conv

    def test_service_lifecycle_methods(self, registry):
        """Test service lifecycle management methods."""
        # Test has_service method
        async def dummy_factory():
            return Mock()
        
        registry.register_singleton("lifecycle_test", dummy_factory, [])
        
        assert registry.has_service("lifecycle_test") is True
        assert registry.has_service("nonexistent") is False

    @pytest.mark.asyncio
    async def test_clear_singletons(self, registry):
        """Test clearing singleton instances."""
        # Create some singletons
        mock_service = Mock()
        registry._singletons["test1"] = mock_service
        registry._singletons["test2"] = Mock()
        
        assert len(registry._singletons) == 2
        
        # Clear singletons
        registry.clear_singletons()
        
        assert len(registry._singletons) == 0

    @pytest.mark.asyncio
    async def test_dependency_injection_with_config(self, registry):
        """Test services receive config during creation."""
        received_config = None
        
        async def factory_with_config(config):
            nonlocal received_config
            received_config = config
            return Mock()
        
        # Register with config dependency
        registry.register_singleton(
            "config_service",
            lambda: factory_with_config(registry.config),
            []
        )
        
        await registry.get_service("config_service")
        
        assert received_config == registry.config

    @pytest.mark.asyncio
    async def test_repository_creation(self, registry):
        """Test repository services are created correctly."""
        # Mock database session
        mock_session = Mock()
        
        with patch("src.adapters.database_production.get_db_session") as mock_get_session:
            mock_get_session.return_value = mock_session
            
            # Test user repository
            with patch("src.adapters.database_production.ProductionUserRepository") as MockUserRepo:
                mock_user_repo = Mock()
                MockUserRepo.return_value = mock_user_repo
                
                registry._factories["user_repository"] = AsyncMock(return_value=mock_user_repo)
                
                repo = await registry.get_service("user_repository")
                assert repo is mock_user_repo

    def test_service_registration_validation(self, registry):
        """Test service registration validates inputs."""
        # Test invalid service name
        with pytest.raises(ValueError):
            registry.register_singleton("", AsyncMock(), [])
        
        # Test invalid factory
        with pytest.raises(TypeError):
            registry.register_singleton("test", "not_a_callable", [])
        
        # Test invalid dependencies
        with pytest.raises(TypeError):
            registry.register_singleton("test", AsyncMock(), "not_a_list")