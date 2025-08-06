"""
Comprehensive tests for monitoring integration.
Tests flexible configuration, circular import avoidance, and error handling.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from src.infrastructure.monitoring.integration import (
    MonitoringConfig,
    MonitoringIntegration,
    get_monitoring_integration,
    setup_production_monitoring,
    monitoring_lifespan,
    log_application_startup,
    setup_error_monitoring
)


class TestMonitoringConfig:
    """Test MonitoringConfig class."""
    
    def test_config_default_values(self):
        """Test default configuration values."""
        config = MonitoringConfig()
        
        assert config.enable_metrics is True
        assert config.enable_request_logging is True
        assert config.enable_health_checks is True
        assert config.enable_audit_logging is True
        assert config.enable_error_handling is True
        assert config.metrics_endpoint == "/metrics"
        assert config.health_endpoint == "/health"
        assert config.monitoring_status_endpoint == "/monitoring/status"
        assert config.audit_endpoints_prefix == "/admin/audit"
        assert config.log_level == "INFO"
        assert config.request_timeout == 30.0
        assert config.max_request_body_size == 1024 * 1024
        assert config.custom_middleware == []
        assert config.custom_exception_handlers == {}
    
    def test_config_custom_values(self):
        """Test configuration with custom values."""
        custom_middleware = [Mock()]
        custom_handlers = {ValueError: Mock()}
        
        config = MonitoringConfig(
            enable_metrics=False,
            enable_request_logging=False,
            metrics_endpoint="/custom-metrics",
            health_endpoint="/custom-health",
            request_timeout=60.0,
            custom_middleware=custom_middleware,
            custom_exception_handlers=custom_handlers
        )
        
        assert config.enable_metrics is False
        assert config.enable_request_logging is False
        assert config.metrics_endpoint == "/custom-metrics"
        assert config.health_endpoint == "/custom-health"
        assert config.request_timeout == 60.0
        assert config.custom_middleware == custom_middleware
        assert config.custom_exception_handlers == custom_handlers


class TestMonitoringIntegration:
    """Test MonitoringIntegration class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = MonitoringConfig()
        self.integration = MonitoringIntegration(self.config)
    
    def test_integration_initialization(self):
        """Test monitoring integration initialization."""
        assert self.integration.config is self.config
        assert self.integration._components_loaded is False
        assert self.integration._startup_complete is False
        assert self.integration._shutdown_complete is False
        assert self.integration._logging_components is None
        assert self.integration._metrics_components is None
        assert self.integration._health_components is None
        assert self.integration._audit_components is None
        assert self.integration._startup_errors == []
        assert self.integration._runtime_errors == []
    
    def test_initialization_with_default_config(self):
        """Test initialization with default config."""
        integration = MonitoringIntegration()
        assert isinstance(integration.config, MonitoringConfig)
        assert integration.config.enable_metrics is True
    
    def test_load_logging_components_success(self):
        """Test successful loading of logging components."""
        with patch('src.infrastructure.monitoring.integration.logging') as mock_logging:
            # Mock the import success
            mock_logging.getLogger.return_value = Mock()
            
            # Mock successful import
            with patch.dict('sys.modules', {
                'src.infrastructure.monitoring.logging.production_logger': Mock(
                    setup_logging=Mock(),
                    get_logger=Mock(),
                    RequestLogger=Mock,
                    performance_logger=Mock(),
                    security_logger=Mock(),
                    audit_logger=Mock()
                )
            }):
                components = self.integration._load_logging_components()
                
                assert 'setup_logging' in components
                assert 'get_logger' in components
                assert 'RequestLogger' in components
                assert 'performance_logger' in components
                assert 'security_logger' in components
                assert 'audit_logger' in components
    
    def test_load_logging_components_failure(self):
        """Test loading logging components with import error."""
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            components = self.integration._load_logging_components()
            
            # Should provide fallback components
            assert 'setup_logging' in components
            assert 'get_logger' in components
            assert 'RequestLogger' in components
            assert len(self.integration._startup_errors) == 1
            assert "Logging components" in self.integration._startup_errors[0]
    
    def test_load_metrics_components_success(self):
        """Test successful loading of metrics components."""
        with patch.dict('sys.modules', {
            'src.infrastructure.monitoring.monitoring.metrics': Mock(
                MetricsMiddleware=Mock,
                get_metrics_response=Mock(),
                ai_metrics=Mock(),
                safety_metrics=Mock()
            )
        }):
            components = self.integration._load_metrics_components()
            
            assert 'MetricsMiddleware' in components
            assert 'get_metrics_response' in components
            assert 'ai_metrics' in components
            assert 'safety_metrics' in components
    
    def test_load_metrics_components_failure(self):
        """Test loading metrics components with import error."""
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            components = self.integration._load_metrics_components()
            
            # Should provide fallback components
            assert components['MetricsMiddleware'] is not None
            assert callable(components['get_metrics_response'])
            assert len(self.integration._startup_errors) == 1
    
    def test_load_health_components_success(self):
        """Test successful loading of health components."""
        with patch.dict('sys.modules', {
            'src.infrastructure.monitoring.monitoring.health': Mock(
                setup_health_endpoints=Mock(),
                health_manager=Mock()
            )
        }):
            components = self.integration._load_health_components()
            
            assert 'setup_health_endpoints' in components
            assert 'health_manager' in components
    
    def test_load_health_components_failure(self):
        """Test loading health components with import error."""
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            components = self.integration._load_health_components()
            
            # Should provide fallback components
            assert callable(components['setup_health_endpoints'])
            assert len(self.integration._startup_errors) == 1
    
    def test_load_audit_components_success(self):
        """Test successful loading of audit components."""
        with patch.dict('sys.modules', {
            'src.infrastructure.monitoring.monitoring.audit': Mock(
                coppa_audit=Mock(),
                get_user_context_from_request=Mock()
            )
        }):
            components = self.integration._load_audit_components()
            
            assert 'coppa_audit' in components
            assert 'get_user_context_from_request' in components
    
    def test_load_audit_components_failure(self):
        """Test loading audit components with import error."""
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            components = self.integration._load_audit_components()
            
            # Should provide fallback components
            assert hasattr(components['coppa_audit'], 'log_event')
            assert callable(components['get_user_context_from_request'])
            assert len(self.integration._startup_errors) == 1
    
    def test_ensure_components_loaded(self):
        """Test ensuring all components are loaded."""
        with patch.object(self.integration, '_load_logging_components') as mock_logging, \
             patch.object(self.integration, '_load_metrics_components') as mock_metrics, \
             patch.object(self.integration, '_load_health_components') as mock_health, \
             patch.object(self.integration, '_load_audit_components') as mock_audit:
            
            self.integration._ensure_components_loaded()
            
            mock_logging.assert_called_once()
            mock_metrics.assert_called_once()
            mock_health.assert_called_once()
            mock_audit.assert_called_once()
            assert self.integration._components_loaded is True
    
    def test_ensure_components_loaded_idempotent(self):
        """Test that ensuring components loaded is idempotent."""
        self.integration._components_loaded = True
        
        with patch.object(self.integration, '_load_logging_components') as mock_loading:
            self.integration._ensure_components_loaded()
            mock_loading.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_lifespan_manager_success(self):
        """Test successful lifespan management."""
        app = FastAPI()
        
        # Mock all component loading
        with patch.object(self.integration, '_ensure_components_loaded'), \
             patch.object(self.integration, '_load_logging_components') as mock_logging, \
             patch.object(self.integration, '_load_audit_components') as mock_audit:
            
            mock_logging.return_value = {'setup_logging': Mock()}
            mock_audit.return_value = {
                'coppa_audit': Mock(log_event=Mock())
            }
            
            async with self.integration.lifespan_manager(app):
                assert self.integration._startup_complete is True
            
            assert self.integration._shutdown_complete is True
    
    @pytest.mark.asyncio
    async def test_lifespan_manager_startup_failure(self):
        """Test lifespan management with startup failure."""
        app = FastAPI()
        
        with patch.object(self.integration, '_ensure_components_loaded', side_effect=Exception("Startup error")):
            async with self.integration.lifespan_manager(app):
                pass  # Should still yield despite error
            
            assert len(self.integration._startup_errors) == 1
            assert "Startup failure" in self.integration._startup_errors[0]
    
    def test_setup_monitoring_success(self):
        """Test successful monitoring setup."""
        app = FastAPI()
        
        with patch.object(self.integration, '_ensure_components_loaded'), \
             patch.object(self.integration, '_load_metrics_components') as mock_metrics, \
             patch.object(self.integration, '_setup_request_logging_middleware'), \
             patch.object(self.integration, '_setup_health_endpoints'), \
             patch.object(self.integration, '_setup_metrics_endpoint'), \
             patch.object(self.integration, '_setup_monitoring_status_endpoint'), \
             patch.object(self.integration, '_setup_audit_endpoints'), \
             patch.object(self.integration, '_setup_error_handlers'):
            
            mock_metrics.return_value = {'MetricsMiddleware': Mock}
            
            self.integration.setup_monitoring(app)
            
            # Should have no errors
            assert len(self.integration._startup_errors) == 0
    
    def test_setup_monitoring_with_custom_middleware(self):
        """Test monitoring setup with custom middleware."""
        app = FastAPI()
        custom_middleware = Mock(__name__="CustomMiddleware")
        config = MonitoringConfig(custom_middleware=[custom_middleware])
        integration = MonitoringIntegration(config)
        
        with patch.object(integration, '_ensure_components_loaded'), \
             patch.object(app, 'add_middleware') as mock_add_middleware:
            
            integration.setup_monitoring(app)
            
            mock_add_middleware.assert_called()
    
    def test_setup_monitoring_with_custom_exception_handlers(self):
        """Test monitoring setup with custom exception handlers."""
        app = FastAPI()
        custom_handler = Mock(__name__="custom_handler")
        config = MonitoringConfig(custom_exception_handlers={ValueError: custom_handler})
        integration = MonitoringIntegration(config)
        
        with patch.object(integration, '_ensure_components_loaded'), \
             patch.object(app, 'add_exception_handler') as mock_add_handler:
            
            integration.setup_monitoring(app)
            
            mock_add_handler.assert_called()
    
    def test_setup_request_logging_middleware(self):
        """Test request logging middleware setup."""
        app = FastAPI()
        
        with patch.object(self.integration, '_load_logging_components') as mock_logging, \
             patch.object(self.integration, '_load_audit_components') as mock_audit:
            
            mock_logging.return_value = {'RequestLogger': Mock}
            mock_audit.return_value = {'get_user_context_from_request': Mock()}
            
            self.integration._setup_request_logging_middleware(app)
            
            # Should have added middleware (can't easily test the actual middleware)
            assert len(self.integration._startup_errors) == 0
    
    def test_setup_health_endpoints_success(self):
        """Test successful health endpoints setup."""
        app = FastAPI()
        
        with patch.object(self.integration, '_load_health_components') as mock_health:
            mock_setup = Mock()
            mock_health.return_value = {'setup_health_endpoints': mock_setup}
            
            self.integration._setup_health_endpoints(app)
            
            mock_setup.assert_called_once_with(app)
    
    def test_setup_health_endpoints_failure(self):
        """Test health endpoints setup with failure."""
        app = FastAPI()
        
        with patch.object(self.integration, '_load_health_components', side_effect=Exception("Health error")):
            self.integration._setup_health_endpoints(app)
            
            # Should have created fallback endpoint
            assert len(app.routes) > 0
    
    def test_setup_metrics_endpoint(self):
        """Test metrics endpoint setup."""
        app = FastAPI()
        
        with patch.object(self.integration, '_load_metrics_components') as mock_metrics:
            mock_metrics.return_value = {'get_metrics_response': lambda: "# Test metrics"}
            
            self.integration._setup_metrics_endpoint(app)
            
            # Should have added metrics endpoint
            assert any(route.path == "/metrics" for route in app.routes)
    
    def test_setup_monitoring_status_endpoint(self):
        """Test monitoring status endpoint setup."""
        app = FastAPI()
        
        self.integration._setup_monitoring_status_endpoint(app)
        
        # Should have added status endpoint
        assert any(route.path == "/monitoring/status" for route in app.routes)
    
    def test_setup_audit_endpoints(self):
        """Test audit endpoints setup."""
        app = FastAPI()
        
        with patch.object(self.integration, '_load_audit_components') as mock_audit:
            mock_audit.return_value = {
                'coppa_audit': Mock(query_audit_logs=Mock(return_value=[]))
            }
            
            self.integration._setup_audit_endpoints(app)
            
            # Should have added audit endpoints
            audit_routes = [route for route in app.routes if "/admin/audit" in getattr(route, 'path', '')]
            assert len(audit_routes) > 0
    
    def test_setup_error_handlers(self):
        """Test error handlers setup."""
        app = FastAPI()
        
        with patch.object(self.integration, '_load_audit_components') as mock_audit:
            mock_audit.return_value = {
                'get_user_context_from_request': lambda req: {"user_id": "test"}
            }
            
            self.integration._setup_error_handlers(app)
            
            # Should have added exception handlers
            assert HTTPException in app.exception_handlers
            assert Exception in app.exception_handlers
    
    def test_get_monitoring_status(self):
        """Test getting monitoring status."""
        status = self.integration.get_monitoring_status()
        
        assert 'config' in status
        assert 'status' in status
        assert 'errors' in status
        assert 'components' in status
        
        assert status['config']['enable_metrics'] is True
        assert status['status']['startup_complete'] is False
        assert status['errors']['startup_errors'] == 0
        assert status['components']['logging'] is False


class TestMiddlewareAndHandlers:
    """Test middleware and exception handlers."""
    
    @pytest.mark.asyncio
    async def test_request_logging_middleware_success(self):
        """Test request logging middleware with successful request."""
        app = FastAPI()
        integration = MonitoringIntegration()
        
        # Mock components
        with patch.object(integration, '_load_logging_components') as mock_logging, \
             patch.object(integration, '_load_audit_components') as mock_audit:
            
            mock_request_logger = Mock()
            mock_request_logger.log_request_start = AsyncMock()
            mock_request_logger.log_request_end = AsyncMock()
            
            mock_logging.return_value = {'RequestLogger': lambda: mock_request_logger}
            mock_audit.return_value = {
                'get_user_context_from_request': lambda req: {"user_id": "test"}
            }
            
            integration._setup_request_logging_middleware(app)
            
            # Test that middleware was set up (actual testing would require more complex setup)
            assert len(integration._startup_errors) == 0
    
    @pytest.mark.asyncio
    async def test_request_timeout_handling(self):
        """Test request timeout handling in middleware."""
        config = MonitoringConfig(request_timeout=0.1)  # Very short timeout
        integration = MonitoringIntegration(config)
        
        # This would need more complex testing setup to fully test
        # For now, just verify the timeout value is used
        assert integration.config.request_timeout == 0.1
    
    @pytest.mark.asyncio
    async def test_http_exception_handler(self):
        """Test HTTP exception handler."""
        app = FastAPI()
        integration = MonitoringIntegration()
        
        with patch.object(integration, '_load_audit_components') as mock_audit:
            mock_audit.return_value = {
                'get_user_context_from_request': lambda req: {"user_id": "test"}
            }
            
            integration._setup_error_handlers(app)
            
            # Test that handlers were registered
            assert HTTPException in app.exception_handlers
    
    @pytest.mark.asyncio
    async def test_general_exception_handler(self):
        """Test general exception handler."""
        app = FastAPI()
        integration = MonitoringIntegration()
        
        with patch.object(integration, '_load_audit_components') as mock_audit:
            mock_audit.return_value = {
                'get_user_context_from_request': lambda req: {"user_id": "test"}
            }
            
            integration._setup_error_handlers(app)
            
            # Test that handlers were registered
            assert Exception in app.exception_handlers


class TestGlobalFunctions:
    """Test global utility functions."""
    
    def test_get_monitoring_integration_singleton(self):
        """Test monitoring integration singleton behavior."""
        # Clear any existing instance
        import src.infrastructure.monitoring.integration as integration_module
        integration_module._monitoring_integration = None
        
        integration1 = get_monitoring_integration()
        integration2 = get_monitoring_integration()
        
        assert integration1 is integration2
    
    def test_get_monitoring_integration_with_config(self):
        """Test monitoring integration with custom config."""
        config = MonitoringConfig(enable_metrics=False)
        
        # Clear any existing instance
        import src.infrastructure.monitoring.integration as integration_module
        integration_module._monitoring_integration = None
        
        integration = get_monitoring_integration(config)
        assert integration.config.enable_metrics is False
    
    def test_setup_production_monitoring(self):
        """Test production monitoring setup function."""
        app = FastAPI()
        
        with patch('src.infrastructure.monitoring.integration.MonitoringIntegration') as mock_integration_class:
            mock_integration = Mock()
            mock_integration_class.return_value = mock_integration
            
            result = setup_production_monitoring(app)
            
            mock_integration.setup_monitoring.assert_called_once_with(app)
            assert result is mock_integration
    
    @pytest.mark.asyncio
    async def test_monitoring_lifespan(self):
        """Test monitoring lifespan context manager."""
        app = FastAPI()
        
        with patch('src.infrastructure.monitoring.integration.MonitoringIntegration') as mock_integration_class:
            mock_integration = Mock()
            mock_integration.lifespan_manager = AsyncMock()
            mock_integration_class.return_value = mock_integration
            
            async with monitoring_lifespan(app):
                pass
            
            # Should have used the integration's lifespan manager
            mock_integration.lifespan_manager.assert_called_once()
    
    def test_log_application_startup(self):
        """Test application startup logging."""
        with patch('src.infrastructure.monitoring.integration.logger') as mock_logger:
            log_application_startup()
            
            # Should have logged startup information
            mock_logger.info.assert_called()
    
    def test_log_application_startup_with_components(self):
        """Test application startup logging with components."""
        mock_integration = Mock()
        mock_components = {
            'security_logger': Mock(),
            'performance_logger': Mock(),
            'audit_logger': Mock()
        }
        mock_integration._load_logging_components.return_value = mock_components
        
        with patch('src.infrastructure.monitoring.integration.get_monitoring_integration', return_value=mock_integration), \
             patch('src.infrastructure.monitoring.integration.logger'):
            
            log_application_startup()
            
            # Should have used specialized loggers
            mock_components['security_logger'].info.assert_called()
            mock_components['performance_logger'].info.assert_called()
            mock_components['audit_logger'].info.assert_called()
    
    def test_log_application_startup_error_handling(self):
        """Test startup logging error handling."""
        with patch('src.infrastructure.monitoring.integration.datetime', side_effect=Exception("Time error")), \
             patch('src.infrastructure.monitoring.integration.logger') as mock_logger:
            
            log_application_startup()
            
            # Should have logged error
            mock_logger.error.assert_called()
    
    def test_setup_error_monitoring_deprecated(self):
        """Test deprecated error monitoring function."""
        with patch('src.infrastructure.monitoring.integration.logger') as mock_logger:
            setup_error_monitoring()
            
            # Should have logged deprecation warning
            mock_logger.warning.assert_called()


class TestErrorHandling:
    """Test comprehensive error handling scenarios."""
    
    def test_startup_error_collection(self):
        """Test that startup errors are collected properly."""
        integration = MonitoringIntegration()
        
        # Simulate component loading failures
        with patch('builtins.__import__', side_effect=ImportError("All imports fail")):
            integration._ensure_components_loaded()
            
            # Should have collected multiple startup errors
            assert len(integration._startup_errors) >= 4  # One for each component type
    
    def test_runtime_error_collection(self):
        """Test that runtime errors are collected properly."""
        integration = MonitoringIntegration()
        
        # Simulate runtime error
        integration._runtime_errors.append("Test runtime error")
        
        status = integration.get_monitoring_status()
        assert status['errors']['runtime_errors'] == 1
    
    def test_fallback_components_functionality(self):
        """Test that fallback components work correctly."""
        integration = MonitoringIntegration()
        
        # Force fallback components by simulating import failures
        with patch('builtins.__import__', side_effect=ImportError("Import failed")):
            logging_components = integration._load_logging_components()
            
            # Fallback components should be functional
            logging_components['setup_logging']()  # Should not raise
            logger = logging_components['get_logger']('test')
            assert logger is not None
            
            request_logger = logging_components['RequestLogger']()
            # These should not raise exceptions
            asyncio.run(request_logger.log_request_start())
            asyncio.run(request_logger.log_request_end())
    
    def test_partial_component_failure(self):
        """Test handling of partial component loading failures."""
        integration = MonitoringIntegration()
        
        # Mock partial failure - some components load, others don't
        with patch.object(integration, '_load_logging_components', side_effect=Exception("Logging failed")), \
             patch.object(integration, '_load_metrics_components') as mock_metrics:
            
            mock_metrics.return_value = {'MetricsMiddleware': Mock}
            
            try:
                integration._ensure_components_loaded()
            except Exception:
                pass  # Expected
            
            # Should have recorded the error
            assert len(integration._startup_errors) > 0


class TestConfigurationFlexibility:
    """Test configuration flexibility and customization."""
    
    def test_selective_component_disabling(self):
        """Test disabling specific monitoring components."""
        config = MonitoringConfig(
            enable_metrics=False,
            enable_request_logging=False,
            enable_health_checks=True,
            enable_audit_logging=True
        )
        
        app = FastAPI()
        integration = MonitoringIntegration(config)
        
        with patch.object(integration, '_ensure_components_loaded'), \
             patch.object(integration, '_setup_health_endpoints') as mock_health, \
             patch.object(integration, '_setup_audit_endpoints') as mock_audit:
            
            integration.setup_monitoring(app)
            
            # Only enabled components should be set up
            mock_health.assert_called_once()
            mock_audit.assert_called_once()
    
    def test_custom_endpoint_paths(self):
        """Test custom endpoint path configuration."""
        config = MonitoringConfig(
            metrics_endpoint="/custom-metrics",
            health_endpoint="/custom-health",
            monitoring_status_endpoint="/custom-status"
        )
        
        app = FastAPI()
        integration = MonitoringIntegration(config)
        
        with patch.object(integration, '_ensure_components_loaded'), \
             patch.object(integration, '_load_metrics_components') as mock_metrics:
            
            mock_metrics.return_value = {'get_metrics_response': lambda: "metrics"}
            
            integration._setup_metrics_endpoint(app)
            integration._setup_monitoring_status_endpoint(app)
            
            # Should use custom paths
            assert any(route.path == "/custom-metrics" for route in app.routes)
            assert any(route.path == "/custom-status" for route in app.routes)
    
    def test_request_timeout_configuration(self):
        """Test request timeout configuration."""
        config = MonitoringConfig(request_timeout=60.0)
        integration = MonitoringIntegration(config)
        
        assert integration.config.request_timeout == 60.0
    
    def test_max_request_body_size_configuration(self):
        """Test max request body size configuration."""
        config = MonitoringConfig(max_request_body_size=2 * 1024 * 1024)  # 2MB
        integration = MonitoringIntegration(config)
        
        assert integration.config.max_request_body_size == 2 * 1024 * 1024


class TestCircularImportAvoidance:
    """Test that circular imports are properly avoided."""
    
    def test_lazy_component_loading(self):
        """Test that components are loaded lazily."""
        integration = MonitoringIntegration()
        
        # Initially, no components should be loaded
        assert integration._logging_components is None
        assert integration._metrics_components is None
        assert integration._health_components is None
        assert integration._audit_components is None
        
        # Loading one component shouldn't load others
        with patch('builtins.__import__'):
            integration._load_logging_components()
            
            assert integration._logging_components is not None
            assert integration._metrics_components is None
    
    def test_component_caching(self):
        """Test that loaded components are cached."""
        integration = MonitoringIntegration()
        
        with patch('builtins.__import__') as mock_import:
            # Load components twice
            integration._load_logging_components()
            integration._load_logging_components()
            
            # Import should only be called once due to caching
            assert mock_import.call_count <= 1  # May be 0 if fallback is used
    
    def test_standard_logger_usage(self):
        """Test that standard logger is used to avoid circular imports."""
        import src.infrastructure.monitoring.integration as integration_module
        
        # Module should use standard logger, not custom logger
        assert hasattr(integration_module, 'logger')
        assert integration_module.logger.name == integration_module.__name__


class TestIntegrationWithFastAPI:
    """Test integration with FastAPI application."""
    
    @pytest.mark.asyncio
    async def test_full_integration_setup(self):
        """Test full integration setup with FastAPI."""
        app = FastAPI()
        config = MonitoringConfig()
        
        # Mock all components to avoid import issues
        with patch('src.infrastructure.monitoring.integration.MonitoringIntegration._ensure_components_loaded'):
            integration = setup_production_monitoring(app, config)
            
            assert isinstance(integration, MonitoringIntegration)
            assert integration.config is config
    
    @pytest.mark.asyncio
    async def test_lifespan_integration(self):
        """Test lifespan integration with FastAPI."""
        app = FastAPI()
        
        async def test_lifespan():
            async with monitoring_lifespan(app) as lifespan:
                # Should be able to use the app normally
                assert app is not None
        
        # Should not raise any exceptions
        await test_lifespan()
    
    def test_endpoint_registration(self):
        """Test that monitoring endpoints are registered correctly."""
        app = FastAPI()
        integration = MonitoringIntegration()
        
        with patch.object(integration, '_ensure_components_loaded'), \
             patch.object(integration, '_load_metrics_components') as mock_metrics, \
             patch.object(integration, '_load_health_components') as mock_health, \
             patch.object(integration, '_load_audit_components') as mock_audit:
            
            mock_metrics.return_value = {'get_metrics_response': lambda: "metrics"}
            mock_health.return_value = {'setup_health_endpoints': Mock()}
            mock_audit.return_value = {'coppa_audit': Mock(query_audit_logs=Mock(return_value=[]))}
            
            integration.setup_monitoring(app)
            
            # Should have registered various endpoints
            paths = [route.path for route in app.routes if hasattr(route, 'path')]
            assert any("/metrics" in path for path in paths)
            assert any("/monitoring/status" in path for path in paths)