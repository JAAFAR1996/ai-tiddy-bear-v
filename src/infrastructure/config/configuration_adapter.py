"""
Configuration Adapter - IConfiguration Implementation
====================================================
Adapter class that implements IConfiguration interface using ProductionConfigurationManager.
"""

import os
import logging
from typing import Any, Dict, Optional

from src.interfaces.config import IConfiguration
from .production_configuration_manager import ProductionConfigurationManager, ConfigEnvironment

logger = logging.getLogger(__name__)


class ConfigurationAdapter(IConfiguration):
    """Configuration adapter that implements IConfiguration interface."""
    
    def __init__(self):
        """Initialize configuration adapter."""
        # Determine environment
        env_name = os.getenv("ENVIRONMENT", "development").lower()
        if env_name == "production":
            environment = ConfigEnvironment.PRODUCTION
        elif env_name == "staging":
            environment = ConfigEnvironment.STAGING
        elif env_name == "testing":
            environment = ConfigEnvironment.TESTING
        else:
            environment = ConfigEnvironment.DEVELOPMENT
        
        self.config_manager = ProductionConfigurationManager(environment=environment)
        logger.info(f"ConfigurationAdapter initialized with environment: {environment.value}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        try:
            return self.config_manager.get(key, default)
        except Exception as e:
            logger.warning(f"Failed to get config key '{key}': {e}")
            return default
    
    def get_required(self, key: str) -> Any:
        """Get required configuration value, raises error if not found."""
        value = self.get(key)
        if value is None:
            raise ValueError(f"Required configuration key '{key}' not found")
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section."""
        try:
            return self.config_manager.get_section(section)
        except Exception as e:
            logger.warning(f"Failed to get config section '{section}': {e}")
            return {}
    
    # Required properties implementation
    @property
    def JWT_SECRET_KEY(self) -> str:
        """JWT secret key for authentication."""
        return self.get_required("JWT_SECRET_KEY")
    
    @property
    def DATABASE_URL(self) -> str:
        """Database connection URL."""
        return self.get_required("DATABASE_URL")
    
    @property
    def REDIS_URL(self) -> str:
        """Redis connection URL."""
        return self.get("REDIS_URL", "redis://localhost:6379/0")
    
    @property
    def OPENAI_API_KEY(self) -> str:
        """OpenAI API key."""
        return self.get_required("OPENAI_API_KEY")
    
    @property
    def OPENAI_MODEL(self) -> str:
        """OpenAI model to use."""
        return self.get("OPENAI_MODEL", "gpt-4")
    
    @property
    def RATE_LIMIT_PER_MINUTE(self) -> int:
        """Rate limit per minute."""
        return int(self.get("RATE_LIMIT_PER_MINUTE", 60))
    
    @property
    def CHILD_SAFETY_ENABLED(self) -> bool:
        """Whether child safety features are enabled."""
        return bool(self.get("CHILD_SAFETY_ENABLED", True))
    
    @property
    def LOG_LEVEL(self) -> str:
        """Application log level."""
        return self.get("LOG_LEVEL", "INFO")
    
    @property
    def ENVIRONMENT(self) -> str:
        """Current environment (dev/staging/production)."""
        return self.config_manager.environment.value


# Global instance for backward compatibility
configuration_adapter = ConfigurationAdapter()