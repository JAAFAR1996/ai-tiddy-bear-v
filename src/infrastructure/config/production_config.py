"""
🧸 AI TEDDY BEAR V5 - UNIFIED PRODUCTION CONFIGURATION
====================================================
SINGLE SOURCE OF TRUTH - Any config logic outside this file is a bug.

CRITICAL RULES:
- NO config files outside this module
- NO config validation outside this module
- NO config loading outside this module
- ANY violation = immediate code review rejection

Production-grade, type-safe, validated configuration system.
"""

import sys
import threading
import logging
import traceback
import secrets
import os
import re
from typing import List, Optional, Dict, Any, Set
from pathlib import Path
from datetime import datetime

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator

# Import ConfigurationError to avoid NameError
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ProductionConfig(BaseSettings):
    """
    SINGLE SOURCE OF TRUTH - Production Configuration
    All security-critical values MUST be provided via environment variables.
    """

    # ===========================================
    # ENVIRONMENT & DEPLOYMENT
    # ===========================================
    ENVIRONMENT: str = Field(..., pattern="^(production|staging|development|test)$")
    DEBUG: bool = False
    LOG_LEVEL: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # ===========================================
    # SECURITY KEYS - REQUIRED, NO DEFAULTS
    # ===========================================
    SECRET_KEY: str = Field(
        ..., min_length=32, description="Main application secret key"
    )
    JWT_SECRET_KEY: str = Field(..., min_length=32, description="JWT signing secret")
    COPPA_ENCRYPTION_KEY: str = Field(
        ..., min_length=32, description="Child data encryption key"
    )

    # ===========================================
    # SECURITY ENHANCEMENTS - KEY ROTATION
    # ===========================================
    ENABLE_KEY_ROTATION: bool = Field(True, description="Enable automatic key rotation")
    KEY_ROTATION_INTERVAL_HOURS: int = Field(
        24, ge=1, le=168, description="Key rotation interval in hours"
    )
    OLD_SECRET_KEY: Optional[str] = Field(
        None, min_length=32, description="Previous secret key for rotation"
    )
    OLD_JWT_SECRET_KEY: Optional[str] = Field(
        None, min_length=32, description="Previous JWT key for rotation"
    )
    KEY_ROTATION_GRACE_PERIOD_HOURS: int = Field(
        2, ge=1, le=24, description="Grace period for old keys in hours"
    )

    # Encryption at rest for sensitive keys
    MASTER_ENCRYPTION_KEY: Optional[str] = Field(
        None, min_length=32, description="Master key for encrypting other keys"
    )
    USE_EXTERNAL_KEY_MANAGER: bool = Field(
        False,
        description="Use external key management service (AWS KMS, Azure Key Vault)",
    )
    EXTERNAL_KEY_MANAGER_URL: Optional[str] = Field(
        None, description="External key manager service URL"
    )

    # ===========================================
    # DATABASE - SUPPORTS POSTGRESQL & SQLITE
    # ===========================================
    DATABASE_URL: str = Field(
        ...,
        pattern="^(postgresql(\\+asyncpg)?://|sqlite(\\+aiosqlite)?:///)",
        description="Database connection string (PostgreSQL or SQLite)",
    )
    DATABASE_POOL_SIZE: int = Field(10, ge=1, le=50)
    DATABASE_MAX_OVERFLOW: int = Field(20, ge=0, le=100)
    DATABASE_POOL_TIMEOUT: int = Field(30, ge=1, le=300)

    # ===========================================
    # REDIS - REQUIRED FOR CACHING & SESSIONS
    # ===========================================
    REDIS_URL: str = Field(
        ..., pattern="^redis(s)?://", description="Redis connection string"
    )
    REDIS_POOL_SIZE: int = Field(10, ge=1, le=50)
    REDIS_TIMEOUT: int = Field(5, ge=1, le=60)

    # ===========================================
    # AI SERVICES - OPENAI REQUIRED
    # ===========================================
    OPENAI_API_KEY: str = Field(..., pattern="^sk-", description="OpenAI API key")
    OPENAI_MODEL: str = Field("gpt-4", description="OpenAI model to use")
    OPENAI_MAX_TOKENS: int = Field(1000, ge=1, le=4000)
    OPENAI_TEMPERATURE: float = Field(0.7, ge=0.0, le=2.0)

    # ===========================================
    # CORS & SECURITY - NO WILDCARDS ALLOWED
    # ===========================================
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        ..., description="Exact CORS origins (no wildcards)"
    )
    ALLOWED_HOSTS: List[str] = Field(
        ..., description="Allowed host headers (production domains only)"
    )

    # ===========================================
    # METRICS SECURITY
    # ===========================================
    METRICS_USERNAME: str = Field(
        "metrics", description="Username for metrics endpoint basic auth"
    )
    METRICS_PASSWORD: Optional[str] = Field(
        None, description="Password for metrics endpoint (production only)"
    )
    METRICS_API_TOKEN: Optional[str] = Field(
        None, description="API token for metrics endpoint (alternative to basic auth)"
    )
    METRICS_INTERNAL_NETWORKS: List[str] = Field(
        default_factory=lambda: ["10.", "172.16.", "192.168.", "127.0.0.1"],
        description="Internal networks allowed to access metrics without auth"
    )

    # ===========================================
    # CHILD SAFETY & COPPA COMPLIANCE
    # ===========================================
    COPPA_COMPLIANCE_MODE: bool = Field(
        True, description="Enable COPPA compliance features"
    )
    CONTENT_FILTER_STRICT: bool = Field(
        True, description="Enable strict content filtering"
    )
    PARENT_NOTIFICATION_EMAIL: str = Field(
        ..., pattern=r"^[^@]+@[^@]+\.[^@]+$", description="Parent notification email"
    )

    # ===========================================
    # RATE LIMITING
    # ===========================================
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(60, ge=1, le=1000)
    RATE_LIMIT_BURST: int = Field(10, ge=1, le=100)

    # ===========================================
    # SERVER CONFIGURATION
    # ===========================================
    HOST: str = Field("0.0.0.0", description="Server host")
    PORT: int = Field(8000, ge=1, le=65535)
    WORKERS: int = Field(1, ge=1, le=16)

    # ===========================================
    # JWT CONFIGURATION
    # ===========================================
    JWT_ALGORITHM: str = Field("HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(7, ge=1, le=30)

    # ===========================================
    # API DOCUMENTATION
    # ===========================================
    API_BASE_URL: str = Field("https://api.aiteddybear.com", description="API base URL")
    API_TITLE: str = Field("AI Teddy Bear API", description="API title")
    API_VERSION: str = Field("1.0.0", description="API version")
    SUPPORT_EMAIL: str = Field("support@aiteddybear.com", description="Support email")

    # ===========================================
    # OPTIONAL AI SERVICES
    # ===========================================
    ELEVENLABS_API_KEY: Optional[str] = Field(None, description="ElevenLabs API key")
    TTS_PROVIDER: str = Field(
        "openai", pattern="^(openai|elevenlabs)$", description="TTS provider to use"
    )

    # ===========================================
    # FEATURE FLAGS
    # ===========================================
    ENABLE_DATABASE: bool = Field(True, description="Enable database features")
    ENABLE_REDIS: bool = Field(True, description="Enable Redis features")
    ENABLE_AI_SERVICES: bool = Field(True, description="Enable AI services")
    USE_MOCK_SERVICES: bool = Field(False, description="Use mock services for testing")

    # ===========================================
    # PREMIUM SUBSCRIPTION SYSTEM
    # ===========================================
    STRIPE_PUBLISHABLE_KEY: str = Field(..., description="Stripe publishable key")
    STRIPE_SECRET_KEY: str = Field(..., description="Stripe secret key")
    STRIPE_WEBHOOK_SECRET: str = Field(..., description="Stripe webhook secret")
    PREMIUM_TRIAL_DAYS: int = Field(7, ge=0, le=30, description="Premium trial period")
    PREMIUM_BILLING_CYCLE_DAYS: int = Field(
        30, ge=1, le=365, description="Billing cycle"
    )

    # Premium Feature Limits
    PREMIUM_MAX_CHILDREN_BASIC: int = Field(3, ge=1, le=10)
    PREMIUM_MAX_CHILDREN_PREMIUM: int = Field(-1, description="Unlimited (-1)")
    PREMIUM_HISTORY_DAYS_FREE: int = Field(7, ge=1, le=365)
    PREMIUM_HISTORY_DAYS_BASIC: int = Field(90, ge=1, le=365)
    PREMIUM_REPORTS_PER_MONTH_FREE: int = Field(1, ge=1, le=100)
    PREMIUM_REPORTS_PER_MONTH_BASIC: int = Field(5, ge=1, le=100)

    # ===========================================
    # WEBSOCKET & REAL-TIME NOTIFICATIONS
    # ===========================================
    WEBSOCKET_MAX_CONNECTIONS_PER_USER: int = Field(5, ge=1, le=20)
    WEBSOCKET_HEARTBEAT_INTERVAL: int = Field(30, ge=10, le=300)
    WEBSOCKET_CONNECTION_TIMEOUT: int = Field(300, ge=60, le=3600)
    WEBSOCKET_MESSAGE_RATE_LIMIT: int = Field(100, ge=10, le=1000)
    WEBSOCKET_MAX_MESSAGE_SIZE: int = Field(10240, ge=1024, le=65536)

    # Emergency Alert Configuration
    EMERGENCY_ESCALATION_DELAY: int = Field(300, ge=60, le=1800)
    EMERGENCY_CONTACT_AUTHORITIES: bool = Field(
        True, description="Auto-contact authorities"
    )
    EMERGENCY_BROADCAST_ALL_ADMINS: bool = Field(
        True, description="Broadcast to all admins"
    )

    # Real-time Alert Thresholds
    SAFETY_SCORE_CRITICAL_THRESHOLD: int = Field(30, ge=0, le=100)
    SAFETY_SCORE_HIGH_THRESHOLD: int = Field(50, ge=0, le=100)
    SAFETY_SCORE_MEDIUM_THRESHOLD: int = Field(70, ge=0, le=100)
    BEHAVIOR_PATTERN_CONFIDENCE_THRESHOLD: float = Field(0.8, ge=0.5, le=1.0)
    TRENDING_NEGATIVE_THRESHOLD: int = Field(3, ge=1, le=10)

    # ===========================================
    # PUSH NOTIFICATIONS
    # ===========================================
    FCM_SERVER_KEY: Optional[str] = Field(
        None, description="Firebase Cloud Messaging key"
    )
    APNS_CERTIFICATE: Optional[str] = Field(
        None, description="Apple Push Notification cert"
    )
    PUSH_BADGE_COUNT_ENABLED: bool = Field(True, description="Enable badge counts")
    PUSH_SOUND_ENABLED: bool = Field(True, description="Enable notification sounds")
    PUSH_VIBRATION_ENABLED: bool = Field(True, description="Enable vibration")

    # ===========================================
    # VALIDATORS - SECURITY CRITICAL
    # ===========================================

    @field_validator("OPENAI_API_KEY")
    @classmethod
    def validate_openai_key_format(cls, v: str) -> str:
        """Validate OpenAI API key format."""
        if not v.startswith("sk-"):
            raise ValueError(
                "OPENAI API ERROR: Invalid API key format. "
                "OpenAI API keys must start with 'sk-'. "
                "Get your API key from: https://platform.openai.com/api-keys"
            )
        if len(v) < 20:
            raise ValueError(
                "OPENAI API ERROR: API key appears to be too short. "
                "Valid OpenAI API keys are typically 51+ characters long."
            )
        return v

    @field_validator("SECRET_KEY", "JWT_SECRET_KEY", "COPPA_ENCRYPTION_KEY")
    @classmethod
    def validate_no_unsafe_defaults(cls, v: str) -> str:
        """Ensure no unsafe default values are used in production."""
        unsafe_patterns: Set[str] = {
            "fallback",
            "example",
            "change",
            "test",
            "default",
            "placeholder",
            "temp",
            "demo",
            "sample",
        }
        v_lower = v.lower()
        for pattern in unsafe_patterns:
            if pattern in v_lower:
                raise ValueError(
                    f"Security key contains unsafe pattern '{pattern}'. Use a secure random value in production."
                )
        return v

    @field_validator("SECRET_KEY", "JWT_SECRET_KEY", "COPPA_ENCRYPTION_KEY")
    @classmethod
    def validate_entropy(cls, v: str) -> str:
        """Ensure keys have sufficient entropy."""
        if len(set(v)) < 16:  # At least 16 unique characters
            raise ValueError(
                "Security key has insufficient entropy. Use a cryptographically secure random value."
            )
        return v

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def validate_no_wildcards(cls, v: List[str]) -> List[str]:
        """Ensure no wildcard CORS origins in production."""
        for origin in v:
            if "*" in origin:
                raise ValueError(
                    f"Wildcard CORS origin '{origin}' not allowed in production. Specify exact origins for security."
                )
            if not origin.startswith(("http://", "https://")):
                raise ValueError(
                    f"CORS origin '{origin}' must include protocol (http:// or https://)"
                )
        return v

    @model_validator(mode="after")
    def validate_security_consistency(self) -> "ProductionConfig":
        """Ensure all security keys are unique."""
        keys = [self.SECRET_KEY, self.JWT_SECRET_KEY, self.COPPA_ENCRYPTION_KEY]
        if len(set(keys)) != len(keys):
            raise ValueError(
                "All security keys (SECRET_KEY, JWT_SECRET_KEY, COPPA_ENCRYPTION_KEY) must be unique for maximum security."
            )
        return self

    @model_validator(mode="after")
    def validate_production_invariants(self) -> "ProductionConfig":
        """Production-specific validation rules."""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")
            if "*" in str(self.CORS_ALLOWED_ORIGINS):
                raise ValueError("Wildcard CORS not allowed in production")
            if self.HOST == "0.0.0.0":
                logger.warning(
                    "WARNING: Binding to 0.0.0.0 in production - ensure proper firewall rules"
                )
        return self

    # ===========================================
    # UTILITY PROPERTIES
    # ===========================================

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"

    def get_cors_origins_list(self) -> List[str]:
        """Get CORS origins as a proper list."""
        return self.CORS_ALLOWED_ORIGINS

    def get_validation_report(self) -> Dict[str, Any]:
        """Get comprehensive validation report."""
        return {
            "environment": self.ENVIRONMENT,
            "security_keys_configured": all(
                [
                    len(self.SECRET_KEY) >= 32,
                    len(self.JWT_SECRET_KEY) >= 32,
                    len(self.COPPA_ENCRYPTION_KEY) >= 32,
                ]
            ),
            "database_configured": self.DATABASE_URL.startswith("postgresql://"),
            "redis_configured": self.REDIS_URL.startswith("redis"),
            "openai_configured": self.OPENAI_API_KEY.startswith("sk-"),
            "cors_origins_count": len(self.CORS_ALLOWED_ORIGINS),
            "production_ready": self.is_production and not self.DEBUG,
            "coppa_compliant": self.COPPA_COMPLIANCE_MODE,
            "content_filtering": self.CONTENT_FILTER_STRICT,
        }

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "validate_assignment": True,
        "extra": "ignore",
    }


# ===========================================
# SINGLETON CONFIGURATION MANAGER
# ===========================================


class ConfigurationManager:
    """Thread-safe singleton configuration manager."""

    _instance: Optional["ConfigurationManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._config: Optional[ProductionConfig] = None
        self._config_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ConfigurationManager":
        """Get singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def load_config(
        self, env_file: Optional[str] = None, force_reload: bool = False
    ) -> ProductionConfig:
        """Thread-safe configuration loading with comprehensive error handling."""
        with self._config_lock:
            if self._config is not None and not force_reload:
                return self._config

            try:
                if env_file:
                    self._config = ProductionConfig(_env_file=env_file)
                else:
                    self._config = ProductionConfig()

                # Sanitize config values for logging to prevent log injection
                safe_env = re.sub(
                    r"[\r\n\x00-\x1f\x7f-\x9f]", "", str(self._config.ENVIRONMENT)
                )[:20]
                safe_debug = str(self._config.DEBUG)
                logger.info(
                    "Configuration loaded: Environment=%s, Debug=%s",
                    safe_env,
                    safe_debug,
                )
                return self._config

            except Exception as e:
                # CRITICAL: Full error logging with stack trace (sanitized)
                logger.critical("FATAL: Configuration validation failed")
                safe_error = re.sub(r"[\r\n\x00-\x1f\x7f-\x9f]", "", str(e))[:500]
                safe_type = re.sub(r"[\r\n\x00-\x1f\x7f-\x9f]", "", type(e).__name__)[
                    :50
                ]
                logger.critical("Error: %s", safe_error)
                logger.critical("Type: %s", safe_type)
                logger.critical("Stack trace:")
                logger.critical(traceback.format_exc())

                # Log specific missing variables
                missing_vars = []
                required_vars = [
                    "ENVIRONMENT",
                    "SECRET_KEY",
                    "JWT_SECRET_KEY",
                    "COPPA_ENCRYPTION_KEY",
                    "DATABASE_URL",
                    "REDIS_URL",
                    "OPENAI_API_KEY",
                    "CORS_ALLOWED_ORIGINS",
                    "PARENT_NOTIFICATION_EMAIL",
                ]

                for var in required_vars:
                    if not os.getenv(var):
                        missing_vars.append(var)

                if missing_vars:
                    logger.critical(
                        f"Missing required environment variables: {', '.join(missing_vars)}"
                    )

                # يجب تمرير الرسالة في الحقل message واسم المتغير في config_key فقط — أي استخدام غير ذلك = خطأ إنتاجي ويجب إصلاحه فوراً.
                raise ConfigurationError(
                    f"Configuration validation failed: {str(e)}",
                    context={"config_key": "CONFIG_VALIDATION"}
                ) from e

    def get_config(self) -> ProductionConfig:
        """Get current configuration with thread safety."""
        with self._config_lock:
            if self._config is None:
                # يجب تمرير الرسالة في الحقل message واسم المتغير في config_key فقط — أي استخدام غير ذلك = خطأ إنتاجي ويجب إصلاحه فوراً.
                raise ConfigurationError(
                    "Configuration not loaded. Call load_config() first.",
                    context={"config_key": "CONFIG_NOT_LOADED"}
                )
            return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        config = self.get_config()
        return getattr(config, key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        value = self.get(key, default)
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value."""
        value = self.get(key, default)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            true_values = {"true", "1", "yes", "on"}
            return value.lower() in true_values
        return bool(value)


# ===========================================
# GLOBAL CONFIGURATION INSTANCE
# ===========================================

_config_manager = ConfigurationManager()


# يجب تمرير الرسالة في الحقل message واسم المتغير في config_key فقط — أي استخدام غير ذلك = خطأ إنتاجي ويجب إصلاحه فوراً.
def load_config(env_file: Optional[str] = None) -> ProductionConfig:
    """Load and validate configuration using thread-safe manager."""
    try:
        return _config_manager.load_config(env_file)
    except Exception as e:
        logger.critical(
            "🚨 CRITICAL: Application cannot start due to configuration failure"
        )
        logger.critical("Full stack trace:")
        traceback.print_exc()
        # رفع الاستثناء برسالة واضحة واسم متغير محدد
        raise ConfigurationError(
            f"Application cannot start due to configuration failure: {str(e)}",
            context={"config_key": "CONFIG_STARTUP"}
        )


def get_config() -> ProductionConfig:
    """Get the current configuration instance."""
    return _config_manager.get_config()


# يجب تمرير الرسالة في الحقل message واسم المتغير في config_key فقط — أي استخدام غير ذلك = خطأ إنتاجي ويجب إصلاحه فوراً.
def reload_config(env_file: Optional[str] = None) -> ProductionConfig:
    """Reload configuration (useful for testing)."""
    try:
        return _config_manager.load_config(env_file, force_reload=True)
    except Exception as e:
        logger.critical("🚨 CRITICAL: Configuration reload failed")
        traceback.print_exc()
        # رفع الاستثناء برسالة واضحة واسم متغير محدد
        raise ConfigurationError(
            f"Configuration reload failed: {str(e)}",
            context={"config_key": "CONFIG_RELOAD"}
        )


def generate_secure_key() -> str:
    """Generate a cryptographically secure key.

    WARNING: This function is for development only.
    In production, use proper key management systems.
    """
    return secrets.token_urlsafe(32)


def create_env_template() -> str:
    """Create a template .env file with secure examples."""
    return f"""
# 🧸 AI TEDDY BEAR V5 - ENVIRONMENT CONFIGURATION
# ===============================================
# COPY THIS FILE TO .env AND UPDATE ALL VALUES
# NEVER COMMIT REAL SECRETS TO VERSION CONTROL

# Environment (production|staging|development|test)
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO

# Security Keys - GENERATE UNIQUE VALUES FOR EACH ENVIRONMENT
# Use: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY={generate_secure_key()}
JWT_SECRET_KEY={generate_secure_key()}
COPPA_ENCRYPTION_KEY={generate_secure_key()}

# Database - PostgreSQL Required (Production)
DATABASE_URL=postgresql://username:password@postgres:5432/ai_teddy_bear_prod
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Redis - Required for caching and sessions (Production)
REDIS_URL=redis://:password@redis:6379/0
REDIS_POOL_SIZE=20

# OpenAI - Required for AI responses (Production)
OPENAI_API_KEY=sk-REPLACE-WITH-PRODUCTION-OPENAI-KEY
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=1500

# CORS - Production domains only (no localhost)
CORS_ALLOWED_ORIGINS=["https://aiteddybear.com","https://www.aiteddybear.com","https://api.aiteddybear.com","https://ai-tiddy-bear-v-xuqy.onrender.com"]
ALLOWED_HOSTS=["aiteddybear.com","www.aiteddybear.com","api.aiteddybear.com","ai-tiddy-bear-v-xuqy.onrender.com"]

# Child Safety & COPPA
COPPA_COMPLIANCE_MODE=true
CONTENT_FILTER_STRICT=true
PARENT_NOTIFICATION_EMAIL=parent-notifications@yourdomain.com

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4
""".strip()


# ===========================================
# MISSING ENUMS FOR CONFIG INTEGRATION
# ===========================================

from enum import Enum


class Environment(str, Enum):
    """Environment enumeration for configuration."""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"


class ConfigSource(str, Enum):
    """Configuration source enumeration."""

    ENV = "env"
    FILE = "file"
    DATABASE = "database"
    API = "api"
    DEFAULT = "default"


# ===========================================
# EXPORTS
# ===========================================

__all__ = [
    "ProductionConfig",
    "ConfigurationManager",
    "load_config",
    "get_config",
    "reload_config",
    "generate_secure_key",
    "create_env_template",
    "Environment",
    "ConfigSource",
]
