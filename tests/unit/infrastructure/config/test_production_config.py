"""
Tests for production configuration management.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from src.infrastructure.config.production_config import (
    ProductionConfig,
    ConfigurationManager,
    load_config,
    get_config,
    generate_secure_key,
    Environment,
    ConfigSource
)
from src.core.exceptions import ConfigurationError


class TestProductionConfig:
    """Test production configuration validation."""

    def test_valid_production_config(self):
        """Test valid production configuration."""
        config_data = {
            "ENVIRONMENT": "production",
            "DEBUG": False,
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "COPPA_ENCRYPTION_KEY": "c" * 32,
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test123456789012345678901234567890",
            "CORS_ALLOWED_ORIGINS": ["https://example.com"],
            "PARENT_NOTIFICATION_EMAIL": "parent@example.com"
        }
        
        with patch.dict(os.environ, config_data):
            config = ProductionConfig()
            assert config.ENVIRONMENT == "production"
            assert not config.DEBUG
            assert config.is_production
            assert not config.is_development

    def test_security_keys_uniqueness(self):
        """Test that security keys must be unique."""
        config_data = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "same_key_12345678901234567890123456789012",
            "JWT_SECRET_KEY": "same_key_12345678901234567890123456789012",
            "COPPA_ENCRYPTION_KEY": "different_key_1234567890123456789012345678",
            "DATABASE_URL": "postgresql://localhost/test",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test123456789012345678901234567890",
            "CORS_ALLOWED_ORIGINS": ["http://localhost:3000"],
            "PARENT_NOTIFICATION_EMAIL": "test@example.com"
        }
        
        with patch.dict(os.environ, config_data):
            with pytest.raises(ValidationError, match="must be unique"):
                ProductionConfig()

    def test_cors_wildcard_validation(self):
        """Test CORS wildcard validation in production."""
        config_data = {
            "ENVIRONMENT": "production",
            "DEBUG": False,
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "COPPA_ENCRYPTION_KEY": "c" * 32,
            "DATABASE_URL": "postgresql://localhost/db",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test123456789012345678901234567890",
            "CORS_ALLOWED_ORIGINS": ["https://example.com", "*"],
            "PARENT_NOTIFICATION_EMAIL": "parent@example.com"
        }
        
        with patch.dict(os.environ, config_data):
            with pytest.raises(ValidationError, match="Wildcard CORS origin"):
                ProductionConfig()

    def test_debug_false_in_production(self):
        """Test DEBUG must be False in production."""
        config_data = {
            "ENVIRONMENT": "production",
            "DEBUG": True,
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "COPPA_ENCRYPTION_KEY": "c" * 32,
            "DATABASE_URL": "postgresql://localhost/db",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test123456789012345678901234567890",
            "CORS_ALLOWED_ORIGINS": ["https://example.com"],
            "PARENT_NOTIFICATION_EMAIL": "parent@example.com"
        }
        
        with patch.dict(os.environ, config_data):
            with pytest.raises(ValidationError, match="DEBUG must be False"):
                ProductionConfig()

    def test_openai_key_validation(self):
        """Test OpenAI API key format validation."""
        config_data = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "COPPA_ENCRYPTION_KEY": "c" * 32,
            "DATABASE_URL": "postgresql://localhost/test",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "invalid-key",
            "CORS_ALLOWED_ORIGINS": ["http://localhost:3000"],
            "PARENT_NOTIFICATION_EMAIL": "test@example.com"
        }
        
        with patch.dict(os.environ, config_data):
            with pytest.raises(ValidationError, match="Invalid API key format"):
                ProductionConfig()

    def test_validation_report(self):
        """Test configuration validation report."""
        config_data = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "COPPA_ENCRYPTION_KEY": "c" * 32,
            "DATABASE_URL": "postgresql://localhost/test",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test123456789012345678901234567890",
            "CORS_ALLOWED_ORIGINS": ["http://localhost:3000"],
            "PARENT_NOTIFICATION_EMAIL": "test@example.com"
        }
        
        with patch.dict(os.environ, config_data):
            config = ProductionConfig()
            report = config.get_validation_report()
            
            assert report["environment"] == "development"
            assert report["security_keys_configured"] is True
            assert report["database_configured"] is True
            assert report["redis_configured"] is True
            assert report["openai_configured"] is True


class TestConfigurationManager:
    """Test configuration manager singleton."""

    def test_singleton_pattern(self):
        """Test singleton pattern implementation."""
        manager1 = ConfigurationManager.get_instance()
        manager2 = ConfigurationManager.get_instance()
        assert manager1 is manager2

    def test_load_config_success(self):
        """Test successful configuration loading."""
        config_data = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "COPPA_ENCRYPTION_KEY": "c" * 32,
            "DATABASE_URL": "postgresql://localhost/test",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test123456789012345678901234567890",
            "CORS_ALLOWED_ORIGINS": ["http://localhost:3000"],
            "PARENT_NOTIFICATION_EMAIL": "test@example.com"
        }
        
        with patch.dict(os.environ, config_data):
            manager = ConfigurationManager()
            config = manager.load_config()
            assert config.ENVIRONMENT == "development"

    def test_get_config_before_load(self):
        """Test getting config before loading raises error."""
        manager = ConfigurationManager()
        manager._config = None
        with pytest.raises(ConfigurationError, match="Configuration not loaded"):
            manager.get_config()

    def test_get_methods(self):
        """Test configuration getter methods."""
        config_data = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "COPPA_ENCRYPTION_KEY": "c" * 32,
            "DATABASE_URL": "postgresql://localhost/test",
            "REDIS_URL": "redis://localhost:6379",
            "OPENAI_API_KEY": "sk-test123456789012345678901234567890",
            "CORS_ALLOWED_ORIGINS": ["http://localhost:3000"],
            "PARENT_NOTIFICATION_EMAIL": "test@example.com",
            "PORT": "8000",
            "OPENAI_TEMPERATURE": "0.7",
            "DEBUG": "true"
        }
        
        with patch.dict(os.environ, config_data):
            manager = ConfigurationManager()
            manager.load_config()
            
            assert manager.get("ENVIRONMENT") == "development"
            assert manager.get_int("PORT") == 8000
            assert manager.get_float("OPENAI_TEMPERATURE") == 0.7
            assert manager.get_bool("DEBUG") is True


class TestConfigurationUtilities:
    """Test configuration utility functions."""

    def test_generate_secure_key(self):
        """Test secure key generation."""
        key = generate_secure_key()
        assert len(key) >= 32
        assert isinstance(key, str)
        
        # Keys should be different
        key2 = generate_secure_key()
        assert key != key2

    def test_environment_enum(self):
        """Test Environment enum values."""
        assert Environment.PRODUCTION == "production"
        assert Environment.STAGING == "staging"
        assert Environment.DEVELOPMENT == "development"
        assert Environment.TEST == "test"

    def test_config_source_enum(self):
        """Test ConfigSource enum values."""
        assert ConfigSource.ENV == "env"
        assert ConfigSource.FILE == "file"
        assert ConfigSource.DATABASE == "database"