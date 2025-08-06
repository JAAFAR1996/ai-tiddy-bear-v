"""
Comprehensive tests for configuration loader.
Tests thread safety, async operations, and error handling.
"""

import pytest
import asyncio
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

from src.infrastructure.config.loader import (
    ConfigurationManager,
    load_config,
    get_config,
    reload_config,
    reset_config_for_testing,
    validate_runtime_dependencies,
    validate_runtime_dependencies_async,
    get_security_summary,
)
from src.core.exceptions import ConfigurationError


class TestConfigurationManager:
    """Test the ConfigurationManager class."""

    def setup_method(self):
        """Reset configuration manager before each test."""
        reset_config_for_testing()
        self.manager = ConfigurationManager.get_instance()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config_for_testing()

    def test_singleton_pattern(self):
        """Test that ConfigurationManager follows singleton pattern."""
        manager1 = ConfigurationManager.get_instance()
        manager2 = ConfigurationManager.get_instance()
        assert manager1 is manager2

    def test_thread_safety_singleton(self):
        """Test singleton creation is thread-safe."""
        instances = []

        def create_instance():
            instances.append(ConfigurationManager.get_instance())

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_instance)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be the same
        assert len(set(id(instance) for instance in instances)) == 1

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_load_config_success(self, mock_config_class):
        """Test successful configuration loading."""
        mock_config = Mock()
        mock_config.ENVIRONMENT = "test"
        mock_config.DEBUG = True
        mock_config_class.return_value = mock_config

        config = self.manager.load_config()

        assert config is mock_config
        mock_config_class.assert_called_once()

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_load_config_with_env_file(self, mock_config_class):
        """Test configuration loading with env file."""
        mock_config = Mock()
        mock_config.ENVIRONMENT = "test"
        mock_config.DEBUG = True
        mock_config_class.return_value = mock_config

        config = self.manager.load_config(env_file=".env.test")

        mock_config_class.assert_called_once_with(_env_file=".env.test")

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_load_config_error_handling(self, mock_config_class):
        """Test configuration loading error handling."""
        mock_config_class.side_effect = ValueError("Invalid config")

        with pytest.raises(ConfigurationError) as exc_info:
            self.manager.load_config()

        assert "Configuration validation failed" in str(exc_info.value)

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_config_caching(self, mock_config_class):
        """Test that configuration is cached after first load."""
        mock_config = Mock()
        mock_config.ENVIRONMENT = "test"
        mock_config.DEBUG = True
        mock_config_class.return_value = mock_config

        config1 = self.manager.load_config()
        config2 = self.manager.load_config()

        assert config1 is config2
        mock_config_class.assert_called_once()  # Should only be called once

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_force_reload(self, mock_config_class):
        """Test force reloading configuration."""
        mock_config1 = Mock()
        mock_config1.ENVIRONMENT = "test1"
        mock_config1.DEBUG = True

        mock_config2 = Mock()
        mock_config2.ENVIRONMENT = "test2"
        mock_config2.DEBUG = False

        mock_config_class.side_effect = [mock_config1, mock_config2]

        config1 = self.manager.load_config()
        config2 = self.manager.load_config(force_reload=True)

        assert config1 is mock_config1
        assert config2 is mock_config2
        assert config1 is not config2
        assert mock_config_class.call_count == 2

    def test_get_config_without_loading(self):
        """Test getting config before loading raises error."""
        with pytest.raises(ConfigurationError) as exc_info:
            self.manager.get_config()

        assert "Configuration not loaded" in str(exc_info.value)

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_thread_safe_config_loading(self, mock_config_class):
        """Test that configuration loading is thread-safe."""
        mock_config = Mock()
        mock_config.ENVIRONMENT = "test"
        mock_config.DEBUG = True
        mock_config_class.return_value = mock_config

        configs = []
        errors = []

        def load_config_thread():
            try:
                configs.append(self.manager.load_config())
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=load_config_thread)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0
        # All configs should be the same instance
        assert len(set(id(config) for config in configs)) == 1
        # ProductionConfig should only be called once
        mock_config_class.assert_called_once()


class TestGlobalFunctions:
    """Test global configuration functions."""

    def setup_method(self):
        """Reset configuration before each test."""
        reset_config_for_testing()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config_for_testing()

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_load_config_function(self, mock_config_class):
        """Test global load_config function."""
        mock_config = Mock()
        mock_config.ENVIRONMENT = "test"
        mock_config.DEBUG = True
        mock_config_class.return_value = mock_config

        config = load_config()
        assert config is mock_config

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_get_config_function(self, mock_config_class):
        """Test global get_config function."""
        mock_config = Mock()
        mock_config.ENVIRONMENT = "test"
        mock_config.DEBUG = True
        mock_config_class.return_value = mock_config

        # Load config first
        load_config()

        # Then get it
        config = get_config()
        assert config is mock_config

    def test_get_config_without_loading_function(self):
        """Test get_config function raises error when not loaded."""
        with pytest.raises(ConfigurationError):
            get_config()

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_reload_config_function(self, mock_config_class):
        """Test global reload_config function."""
        mock_config1 = Mock()
        mock_config1.ENVIRONMENT = "test1"
        mock_config1.DEBUG = True

        mock_config2 = Mock()
        mock_config2.ENVIRONMENT = "test2"
        mock_config2.DEBUG = False

        mock_config_class.side_effect = [mock_config1, mock_config2]

        config1 = load_config()
        config2 = reload_config()

        assert config1 is mock_config1
        assert config2 is mock_config2
        assert config1 is not config2

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_load_config_system_exit_on_error(self, mock_config_class):
        """Test that load_config calls sys.exit on ConfigurationError."""
        mock_config_class.side_effect = ValueError("Invalid config")

        with pytest.raises(SystemExit):
            load_config()


class TestAsyncValidation:
    """Test async dependency validation functions."""

    @pytest.mark.asyncio
    async def test_validate_runtime_dependencies_async_success(self):
        """Test successful async dependency validation."""
        mock_config = Mock()
        mock_config.DATABASE_URL = "postgresql://test"
        mock_config.REDIS_URL = "redis://test"
        mock_config.OPENAI_API_KEY = "sk-test123456789012345678901234567890"

        with patch("asyncpg.connect") as mock_pg_connect, patch(
            "redis.asyncio.from_url"
        ) as mock_redis_from_url:

            # Mock PostgreSQL connection
            mock_pg_conn = Mock()
            mock_pg_connect.return_value = mock_pg_conn
            mock_pg_conn.close = Mock()

            # Mock Redis connection
            mock_redis = Mock()
            mock_redis_from_url.return_value = mock_redis
            mock_redis.ping = Mock()
            mock_redis.aclose = Mock()

            result = await validate_runtime_dependencies_async(mock_config)

            assert result is True
            mock_pg_connect.assert_called_once_with(mock_config.DATABASE_URL)
            mock_pg_conn.close.assert_called_once()
            mock_redis_from_url.assert_called_once_with(mock_config.REDIS_URL)
            await mock_redis.ping()
            await mock_redis.aclose()

    @pytest.mark.asyncio
    async def test_validate_runtime_dependencies_async_failures(self):
        """Test async dependency validation with failures."""
        mock_config = Mock()
        mock_config.DATABASE_URL = "postgresql://test"
        mock_config.REDIS_URL = "redis://test"
        mock_config.OPENAI_API_KEY = "invalid-key"

        with patch("asyncpg.connect", side_effect=Exception("DB Error")), patch(
            "redis.asyncio.from_url", side_effect=Exception("Redis Error")
        ):

            result = await validate_runtime_dependencies_async(mock_config)

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_runtime_dependencies_async_import_errors(self):
        """Test async validation with missing dependencies."""
        mock_config = Mock()
        mock_config.DATABASE_URL = "postgresql://test"
        mock_config.REDIS_URL = "redis://test"
        mock_config.OPENAI_API_KEY = "sk-test123456789012345678901234567890"

        with patch(
            "asyncpg.connect", side_effect=ImportError("asyncpg not found")
        ), patch(
            "redis.asyncio.from_url", side_effect=ImportError("aioredis not found")
        ):

            # Should handle import errors gracefully
            result = await validate_runtime_dependencies_async(mock_config)

            # Should still return True since import errors are handled
            assert result is True

    def test_validate_runtime_dependencies_sync_wrapper(self):
        """Test synchronous wrapper for dependency validation."""
        mock_config = Mock()
        mock_config.DATABASE_URL = "postgresql://test"
        mock_config.REDIS_URL = "redis://test"
        mock_config.OPENAI_API_KEY = "sk-test123456789012345678901234567890"

        with patch(
            "src.infrastructure.config.loader.validate_runtime_dependencies_async"
        ) as mock_async:
            mock_async.return_value = True

            result = validate_runtime_dependencies(mock_config)

            assert result is True

    def test_validate_runtime_dependencies_from_async_context(self):
        """Test validation from within async context."""
        mock_config = Mock()

        async def test_from_async():
            with patch("asyncio.get_running_loop", return_value=Mock()):
                with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
                    mock_future = Mock()
                    mock_future.result.return_value = True
                    mock_executor.return_value.__enter__.return_value.submit.return_value = (
                        mock_future
                    )

                    result = validate_runtime_dependencies(mock_config)
                    assert result is True

        asyncio.run(test_from_async())

    def test_validate_runtime_dependencies_error_handling(self):
        """Test error handling in sync wrapper."""
        mock_config = Mock()

        with patch("asyncio.run", side_effect=Exception("Test error")):
            result = validate_runtime_dependencies(mock_config)
            assert result is False


class TestSecuritySummary:
    """Test security summary function."""

    def test_get_security_summary(self):
        """Test security summary generation."""
        mock_config = Mock()
        mock_config.ENVIRONMENT = "production"
        mock_config.DEBUG = False
        mock_config.COPPA_COMPLIANCE_MODE = True
        mock_config.CONTENT_FILTER_STRICT = True
        mock_config.CORS_ALLOWED_ORIGINS = [
            "https://example.com",
            "https://app.example.com",
        ]
        mock_config.ALLOWED_HOSTS = ["example.com", "app.example.com"]
        mock_config.RATE_LIMIT_REQUESTS_PER_MINUTE = 60
        mock_config.SECRET_KEY = "a" * 32
        mock_config.JWT_SECRET_KEY = "b" * 32
        mock_config.COPPA_ENCRYPTION_KEY = "c" * 32
        mock_config.DATABASE_URL = "postgresql://user:pass@localhost/db"
        mock_config.REDIS_URL = "redis://localhost:6379"
        mock_config.OPENAI_API_KEY = "sk-test123456789012345678901234567890"

        summary = get_security_summary(mock_config)

        assert summary["environment"] == "production"
        assert summary["debug_mode"] is False
        assert summary["coppa_compliance"] is True
        assert summary["content_filter_strict"] is True
        assert summary["cors_origins_count"] == 2
        assert summary["allowed_hosts_count"] == 2
        assert summary["rate_limit_rpm"] == 60
        assert summary["security_keys_configured"] is True
        assert summary["database_type"] == "postgresql"
        assert summary["redis_configured"] is True
        assert summary["openai_configured"] is True


class TestConcurrency:
    """Test concurrent access patterns."""

    def setup_method(self):
        """Reset configuration before each test."""
        reset_config_for_testing()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config_for_testing()

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_concurrent_load_and_get(self, mock_config_class):
        """Test concurrent loading and getting of configuration."""
        mock_config = Mock()
        mock_config.ENVIRONMENT = "test"
        mock_config.DEBUG = True
        mock_config_class.return_value = mock_config

        results = []
        errors = []

        def load_worker():
            try:
                results.append(load_config())
            except Exception as e:
                errors.append(e)

        def get_worker():
            try:
                time.sleep(0.1)  # Give load workers a chance to start
                results.append(get_config())
            except Exception as e:
                errors.append(e)

        # Start multiple load and get workers
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []

            # Submit load workers
            for _ in range(10):
                futures.append(executor.submit(load_worker))

            # Submit get workers
            for _ in range(10):
                futures.append(executor.submit(get_worker))

            # Wait for all to complete
            for future in futures:
                future.result()

        # Should have no errors
        assert len(errors) == 0
        # Should have results from all workers
        assert len(results) == 20
        # All results should be the same instance
        assert len(set(id(config) for config in results)) == 1
        # Config should only be created once
        mock_config_class.assert_called_once()

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_concurrent_reload(self, mock_config_class):
        """Test concurrent reloading doesn't cause race conditions."""
        configs = [Mock() for _ in range(5)]
        for i, config in enumerate(configs):
            config.ENVIRONMENT = f"test{i}"
            config.DEBUG = True

        mock_config_class.side_effect = configs

        results = []
        errors = []

        def reload_worker():
            try:
                results.append(reload_config())
            except Exception as e:
                errors.append(e)

        # Start multiple reload workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(reload_worker) for _ in range(5)]

            for future in futures:
                future.result()

        # Should have no errors
        assert len(errors) == 0
        # Should have 5 results
        assert len(results) == 5
        # Each reload should get a valid config (one of the mocks)
        for result in results:
            assert result in configs


class TestErrorRecovery:
    """Test error recovery scenarios."""

    def setup_method(self):
        """Reset configuration before each test."""
        reset_config_for_testing()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config_for_testing()

    @patch("src.infrastructure.config.loader.ProductionConfig")
    def test_recovery_after_failed_load(self, mock_config_class):
        """Test that system can recover after a failed configuration load."""
        # First call fails
        mock_config_class.side_effect = [ValueError("Test error"), Mock()]
        mock_config_class.return_value.ENVIRONMENT = "test"
        mock_config_class.return_value.DEBUG = True

        # First load should fail
        with pytest.raises(ConfigurationError):
            ConfigurationManager.get_instance().load_config()

        # Reset the side effect for success
        mock_config = Mock()
        mock_config.ENVIRONMENT = "test"
        mock_config.DEBUG = True
        mock_config_class.side_effect = None
        mock_config_class.return_value = mock_config

        # Second load should succeed
        config = ConfigurationManager.get_instance().load_config(force_reload=True)
        assert config is mock_config

    def test_reset_functionality(self):
        """Test that reset_config_for_testing works properly."""
        # Get initial instance
        manager1 = ConfigurationManager.get_instance()

        # Reset
        reset_config_for_testing()

        # Get new instance
        manager2 = ConfigurationManager.get_instance()

        # Should be different instances
        assert manager1 is not manager2
