"""
Production Iraqi Payment System Configuration
===========================================
Production-grade configuration for Iraqi payment providers with enterprise security,
monitoring, and compliance features.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from decimal import Decimal
import os
from enum import Enum
import logging
from src.infrastructure.config.config_provider import get_config


class Environment(Enum):
    """Application environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class PaymentProvider(Enum):
    """Supported Iraqi payment providers."""

    ZAINCASH = "zaincash"
    FASTPAY = "fastpay"
    SWITCH = "switch"
    ASIACELL_CASH = "asiacell_cash"
    KOREK_PAY = "korek_pay"


class PaymentStatus(Enum):
    """Payment processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


@dataclass
class SecurityConfig:
    """Security configuration for payment processing."""

    # JWT Configuration
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # Encryption
    encryption_key: str = ""
    encryption_algorithm: str = "AES-256-GCM"

    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 1000
    rate_limit_per_day: int = 10000

    # Fraud Detection
    fraud_detection_enabled: bool = True
    max_failed_attempts: int = 5
    suspicious_amount_threshold: Decimal = Decimal("10000000")  # 10M IQD
    velocity_check_enabled: bool = True
    max_transactions_per_hour: int = 50

    # IP Security
    allowed_ip_ranges: List[str] = field(default_factory=list)
    blocked_countries: List[str] = field(default_factory=lambda: ["US", "IL"])

    # Audit
    audit_logging_enabled: bool = True
    audit_retention_days: int = 365


@dataclass
class ProviderConfig:
    """Enhanced configuration for Iraqi payment providers."""

    # Basic Configuration
    name: str
    provider_type: PaymentProvider
    enabled: bool = True
    sandbox_mode: bool = True

    # API Configuration
    api_url: str = ""
    sandbox_api_url: str = ""
    api_key: str = ""
    secret_key: str = ""
    merchant_id: str = ""

    # Connection Settings
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 2
    connection_pool_size: int = 10

    # Transaction Limits
    min_amount: Decimal = Decimal("1000")  # 1000 IQD
    max_amount: Decimal = Decimal("50000000")  # 50M IQD
    daily_limit: Decimal = Decimal("500000000")  # 500M IQD
    supported_currencies: List[str] = field(default_factory=lambda: ["IQD"])

    # Webhook Configuration
    webhook_url: str = ""
    webhook_secret: str = ""
    webhook_timeout: int = 10
    webhook_retries: int = 3

    # Provider-Specific Settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)

    # Monitoring
    health_check_url: str = ""
    health_check_interval: int = 300  # 5 minutes

    # Commission and Fees
    commission_rate: Decimal = Decimal("0.025")  # 2.5%
    fixed_fee: Decimal = Decimal("500")  # 500 IQD
    currency_conversion_fee: Decimal = Decimal("0.01")  # 1%


@dataclass
class DatabaseConfig:
    """Database configuration for payment system."""

    # Connection Settings
    host: str = "localhost"
    port: int = 5432
    database: str = "aiteddy_payments"
    username: str = ""  # Must be set from environment
    password: str = ""  # Must be set from environment

    # Pool Settings
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600

    # SSL Settings
    ssl_mode: str = "require"
    ssl_cert: str = ""
    ssl_key: str = ""
    ssl_ca: str = ""

    # Performance
    echo_queries: bool = False
    query_timeout: int = 30

    # Backup
    backup_enabled: bool = True
    backup_schedule: str = "0 2 * * *"  # Daily at 2 AM
    backup_retention_days: int = 30


@dataclass
class RedisConfig:
    """Redis configuration for caching and sessions."""

    # Connection
    host: str = "localhost"
    port: int = 6379
    database: int = 0
    password: str = ""  # Optional for Redis

    # Pool Settings
    max_connections: int = 50
    socket_timeout: int = 5
    socket_connect_timeout: int = 5

    # Cache Settings
    default_ttl: int = 3600  # 1 hour
    session_ttl: int = 1800  # 30 minutes
    rate_limit_ttl: int = 60  # 1 minute

    # SSL
    ssl_enabled: bool = False
    ssl_cert_reqs: str = "required"


@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration."""

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str = "payment_system.log"
    log_max_size: str = "100MB"
    log_backup_count: int = 5

    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"

    # Health Checks
    health_check_enabled: bool = True
    health_check_port: int = 8080
    health_check_path: str = "/health"

    # Alerting
    alert_email: str = ""
    alert_webhook: str = ""
    alert_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "error_rate": 0.05,  # 5%
            "response_time_p95": 2.0,  # 2 seconds
            "failed_payments": 0.1,  # 10%
        }
    )


class ProductionPaymentConfig:
    """Production configuration for Iraqi payment system."""

    def __init__(self, environment: Environment = Environment.PRODUCTION, config=None):
        """Initialize with explicit config injection (production-grade)"""
        self.environment = environment
        self.debug_mode = environment != Environment.PRODUCTION
        self.config = config  # Store injected config

        # Initialize configurations
        self.security = self._init_security_config()
        self.database = self._init_database_config()
        self.redis = self._init_redis_config()
        self.monitoring = self._init_monitoring_config()
        self.providers = self._init_provider_configs()

    def _init_security_config(self) -> SecurityConfig:
        """Initialize security configuration."""
        if self.config is None:
            raise RuntimeError("ProductionPaymentConfig requires config injection - no fallback allowed")
        config = self.config
        if not config.JWT_SECRET_KEY:
            raise Exception(
                "JWT_SECRET_KEY missing in config. COPPA compliance violation."
            )
        if not config.COPPA_ENCRYPTION_KEY:
            raise Exception(
                "COPPA_ENCRYPTION_KEY missing in config. COPPA compliance violation."
            )
        return SecurityConfig(
            jwt_secret_key=config.JWT_SECRET_KEY,
            encryption_key=config.COPPA_ENCRYPTION_KEY,
            rate_limit_per_minute=int(getattr(config, "RATE_LIMIT_PER_MINUTE", 100)),
            fraud_detection_enabled=str(
                getattr(config, "FRAUD_DETECTION_ENABLED", True)
            ).lower()
            == "true",
            audit_logging_enabled=True,
            allowed_ip_ranges=getattr(config, "ALLOWED_IP_RANGES", []),
        )

    def _raise_config_error(self, key: str) -> None:
        """Raise error for missing critical configuration."""
        raise ValueError(
            f"CRITICAL: {key} environment variable is required for production. "
            f"Cannot start payment service without proper database credentials."
        )

    def _init_database_config(self) -> DatabaseConfig:
        """Initialize database configuration."""
        return DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "aiteddy_payments"),
            username=os.getenv("DB_USER") or self._raise_config_error("DB_USER"),
            password=os.getenv("DB_PASSWORD")
            or self._raise_config_error("DB_PASSWORD"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            ssl_mode=os.getenv("DB_SSL_MODE", "require"),
        )

    def _init_redis_config(self) -> RedisConfig:
        """Initialize Redis configuration."""
        return RedisConfig(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD", ""),  # Optional for Redis
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
        )

    def _init_monitoring_config(self) -> MonitoringConfig:
        """Initialize monitoring configuration."""
        return MonitoringConfig(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            metrics_enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
            alert_email=os.getenv("ALERT_EMAIL", ""),
        )

    def _init_provider_configs(self) -> Dict[PaymentProvider, ProviderConfig]:
        """Initialize Iraqi payment provider configurations."""
        providers = {}

        # ZainCash Configuration
        providers[PaymentProvider.ZAINCASH] = ProviderConfig(
            name="ZainCash",
            provider_type=PaymentProvider.ZAINCASH,
            enabled=os.getenv("ZAINCASH_ENABLED", "true").lower() == "true",
            sandbox_mode=os.getenv("ZAINCASH_SANDBOX", "false").lower() == "true",
            api_url="https://api.zaincash.iq/v1",
            sandbox_api_url="https://test.zaincash.iq/v1",
            api_key=os.getenv("ZAINCASH_API_KEY", ""),
            secret_key=os.getenv("ZAINCASH_SECRET_KEY", ""),
            merchant_id=os.getenv("ZAINCASH_MERCHANT_ID", ""),
            min_amount=Decimal("1000"),
            max_amount=Decimal("25000000"),  # 25M IQD
            daily_limit=Decimal("250000000"),  # 250M IQD
            webhook_url=os.getenv("ZAINCASH_WEBHOOK_URL", ""),
            webhook_secret=os.getenv("ZAINCASH_WEBHOOK_SECRET", ""),
            commission_rate=Decimal("0.025"),
            custom_settings={
                "lang": "ar",
                "currency": "IQD",
                "payment_methods": ["wallet", "card"],
                "redirect_url": os.getenv("ZAINCASH_REDIRECT_URL", ""),
            },
        )

        # FastPay Configuration
        providers[PaymentProvider.FASTPAY] = ProviderConfig(
            name="FastPay",
            provider_type=PaymentProvider.FASTPAY,
            enabled=os.getenv("FASTPAY_ENABLED", "true").lower() == "true",
            sandbox_mode=os.getenv("FASTPAY_SANDBOX", "false").lower() == "true",
            api_url="https://api.fast-pay.iq/v2",
            sandbox_api_url="https://sandbox.fast-pay.iq/v2",
            api_key=os.getenv("FASTPAY_API_KEY", ""),
            secret_key=os.getenv("FASTPAY_SECRET_KEY", ""),
            merchant_id=os.getenv("FASTPAY_MERCHANT_ID", ""),
            min_amount=Decimal("1000"),
            max_amount=Decimal("50000000"),  # 50M IQD
            daily_limit=Decimal("500000000"),  # 500M IQD
            webhook_url=os.getenv("FASTPAY_WEBHOOK_URL", ""),
            webhook_secret=os.getenv("FASTPAY_WEBHOOK_SECRET", ""),
            commission_rate=Decimal("0.02"),  # 2%
            custom_settings={
                "payment_types": ["mobile", "card", "bank"],
                "auto_capture": True,
                "currency": "IQD",
            },
        )

        # Switch Payment Configuration
        providers[PaymentProvider.SWITCH] = ProviderConfig(
            name="Switch Payment",
            provider_type=PaymentProvider.SWITCH,
            enabled=os.getenv("SWITCH_ENABLED", "true").lower() == "true",
            sandbox_mode=os.getenv("SWITCH_SANDBOX", "false").lower() == "true",
            api_url="https://switch.iq/api/v1",
            sandbox_api_url="https://test.switch.iq/api/v1",
            api_key=os.getenv("SWITCH_API_KEY", ""),
            secret_key=os.getenv("SWITCH_SECRET_KEY", ""),
            merchant_id=os.getenv("SWITCH_MERCHANT_ID", ""),
            min_amount=Decimal("500"),
            max_amount=Decimal("100000000"),  # 100M IQD
            daily_limit=Decimal("1000000000"),  # 1B IQD
            webhook_url=os.getenv("SWITCH_WEBHOOK_URL", ""),
            webhook_secret=os.getenv("SWITCH_WEBHOOK_SECRET", ""),
            commission_rate=Decimal("0.03"),  # 3%
            custom_settings={
                "supported_banks": ["BOB", "TBI", "RBI", "CBI"],
                "instant_transfer": True,
                "currency": "IQD",
            },
        )

        # AsiaCell Cash Configuration
        providers[PaymentProvider.ASIACELL_CASH] = ProviderConfig(
            name="AsiaCell Cash",
            provider_type=PaymentProvider.ASIACELL_CASH,
            enabled=os.getenv("ASIACELL_ENABLED", "false").lower() == "true",
            sandbox_mode=os.getenv("ASIACELL_SANDBOX", "true").lower() == "true",
            api_url="https://api.asiacell.com/cash/v1",
            sandbox_api_url="https://test.asiacell.com/cash/v1",
            api_key=os.getenv("ASIACELL_API_KEY", ""),
            secret_key=os.getenv("ASIACELL_SECRET_KEY", ""),
            merchant_id=os.getenv("ASIACELL_MERCHANT_ID", ""),
            min_amount=Decimal("1000"),
            max_amount=Decimal("20000000"),  # 20M IQD
            daily_limit=Decimal("200000000"),  # 200M IQD
            commission_rate=Decimal("0.028"),  # 2.8%
        )

        # Korek Pay Configuration
        providers[PaymentProvider.KOREK_PAY] = ProviderConfig(
            name="Korek Pay",
            provider_type=PaymentProvider.KOREK_PAY,
            enabled=os.getenv("KOREK_ENABLED", "false").lower() == "true",
            sandbox_mode=os.getenv("KOREK_SANDBOX", "true").lower() == "true",
            api_url="https://api.korek.com/pay/v1",
            sandbox_api_url="https://sandbox.korek.com/pay/v1",
            api_key=os.getenv("KOREK_API_KEY", ""),
            secret_key=os.getenv("KOREK_SECRET_KEY", ""),
            merchant_id=os.getenv("KOREK_MERCHANT_ID", ""),
            min_amount=Decimal("1000"),
            max_amount=Decimal("15000000"),  # 15M IQD
            daily_limit=Decimal("150000000"),  # 150M IQD
            commission_rate=Decimal("0.03"),  # 3%
        )

        return providers

    def get_provider_config(self, provider: PaymentProvider) -> ProviderConfig:
        """Get configuration for a specific provider."""
        return self.providers.get(provider)

    def get_enabled_providers(self) -> List[ProviderConfig]:
        """Get all enabled payment providers."""
        return [config for config in self.providers.values() if config.enabled]

    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Validate security settings
        if not self.security.jwt_secret_key:
            errors.append("JWT_SECRET_KEY is required")

        if not self.security.encryption_key:
            errors.append("ENCRYPTION_KEY is required")

        # Validate database settings
        if not self.database.username:
            errors.append("DB_USER is required")

        if not self.database.password:
            errors.append("DB_PASSWORD is required")

        # Validate enabled providers
        enabled_providers = self.get_enabled_providers()
        if not enabled_providers:
            errors.append("At least one payment provider must be enabled")

        for provider in enabled_providers:
            if not provider.api_key:
                errors.append(f"{provider.name} API key is required")

            if not provider.secret_key:
                errors.append(f"{provider.name} secret key is required")

        return errors

    def is_production_ready(self) -> bool:
        """Check if configuration is ready for production."""
        errors = self.validate_configuration()
        return len(errors) == 0 and self.environment == Environment.PRODUCTION


# Global configuration instance
_config_instance: Optional[ProductionPaymentConfig] = None


def get_payment_config() -> ProductionPaymentConfig:
    """Get the global payment configuration instance."""
    global _config_instance

    if _config_instance is None:
        env = Environment(os.getenv("ENVIRONMENT", "development"))
        _config_instance = ProductionPaymentConfig(env)

    return _config_instance


def reload_config() -> ProductionPaymentConfig:
    """Reload configuration from environment variables."""
    global _config_instance
    _config_instance = None
    return get_payment_config()


# Configuration validation at module import
if __name__ == "__main__":
    config = get_payment_config()
    errors = config.validate_configuration()

    if errors:
        logging.error("Configuration validation failed:")
        for error in errors:
            logging.error(f"  - {error}")
    else:
        logging.info("Configuration validation passed")
        logging.info(f"Environment: {config.environment.value}")
        logging.info(f"Enabled providers: {len(config.get_enabled_providers())}")
