"""Configuration interfaces for dependency inversion.

Core services should depend on configuration abstractions, not concrete implementations.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IConfiguration(ABC):
    """Interface for application configuration."""
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        pass
    
    @abstractmethod
    def get_required(self, key: str) -> Any:
        """Get required configuration value, raises error if not found."""
        pass
    
    @abstractmethod
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section."""
        pass
    
    # Specific configuration properties for type safety
    @property
    @abstractmethod
    def JWT_SECRET_KEY(self) -> str:
        """JWT secret key for authentication."""
        pass
    
    @property
    @abstractmethod
    def DATABASE_URL(self) -> str:
        """Database connection URL."""
        pass
    
    @property
    @abstractmethod
    def REDIS_URL(self) -> str:
        """Redis connection URL."""
        pass
    
    @property
    @abstractmethod
    def OPENAI_API_KEY(self) -> str:
        """OpenAI API key."""
        pass
    
    @property
    @abstractmethod
    def OPENAI_MODEL(self) -> str:
        """OpenAI model to use."""
        pass
    
    @property
    @abstractmethod
    def RATE_LIMIT_PER_MINUTE(self) -> int:
        """Rate limit per minute."""
        pass
    
    @property
    @abstractmethod
    def CHILD_SAFETY_ENABLED(self) -> bool:
        """Whether child safety features are enabled."""
        pass
    
    @property
    @abstractmethod
    def LOG_LEVEL(self) -> str:
        """Application log level."""
        pass
    
    @property
    @abstractmethod
    def ENVIRONMENT(self) -> str:
        """Current environment (dev/staging/production)."""
        pass
