"""
🧸 AI TEDDY BEAR V5 - CONFIGURATION VALIDATOR
=============================================
Production-grade configuration validation with runtime checks.
"""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass
from src.infrastructure.config.production_config import ProductionConfig

logger = logging.getLogger(__name__)


@dataclass
class COPPAValidationResult:
    """Result of COPPA validation checks."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]


@dataclass
class ValidationResult:
    """General validation result with details."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]

    def add_error(self, message: str, category: str = "general") -> None:
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False
        if category not in self.details:
            self.details[category] = []
        self.details[category].append({"type": "error", "message": message})

    def add_warning(self, message: str, category: str = "general") -> None:
        """Add a warning message."""
        self.warnings.append(message)
        if category not in self.details:
            self.details[category] = []
        self.details[category].append({"type": "warning", "message": message})


class ConfigurationValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


async def validate_production_config(config: ProductionConfig) -> Dict[str, Any]:
    """
    Comprehensive validation of production configuration.

    Args:
        config: Configuration to validate

    Returns:
        Validation results with details

    Raises:
        ConfigurationValidationError: If critical validations fail
    """
    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "security_checks": {},
        "connectivity_checks": {},
        "performance_checks": {},
    }

    # Security Validation
    await _validate_security_configuration(config, results)

    # Connectivity Validation
    await _validate_connectivity(config, results)

    # Performance Validation
    _validate_performance_settings(config, results)

    # COPPA Compliance Validation
    _validate_coppa_compliance(config, results)

    # Production Readiness Validation
    _validate_production_readiness(config, results)

    # Determine overall validity
    results["valid"] = len(results["errors"]) == 0

    if not results["valid"]:
        error_summary = "; ".join(results["errors"])
        raise ConfigurationValidationError(
            f"Configuration validation failed: {error_summary}"
        )

    return results


async def _validate_security_configuration(
    config: ProductionConfig, results: Dict[str, Any]
) -> None:
    """Validate security-related configuration."""
    security_checks = results["security_checks"]

    # Check secret keys uniqueness
    keys = [config.SECRET_KEY, config.JWT_SECRET_KEY, config.COPPA_ENCRYPTION_KEY]
    if len(set(keys)) != len(keys):
        results["errors"].append("Security keys must be unique")
        security_checks["unique_keys"] = False
    else:
        security_checks["unique_keys"] = True

    # Check key entropy
    for key_name, key_value in [
        ("SECRET_KEY", config.SECRET_KEY),
        ("JWT_SECRET_KEY", config.JWT_SECRET_KEY),
        ("COPPA_ENCRYPTION_KEY", config.COPPA_ENCRYPTION_KEY),
    ]:
        entropy = len(set(key_value))
        if entropy < 16:
            results["errors"].append(
                f"{key_name} has insufficient entropy ({entropy} unique chars)"
            )
            security_checks[f"{key_name}_entropy"] = False
        else:
            security_checks[f"{key_name}_entropy"] = True

    # Validate CORS origins
    for origin in config.CORS_ALLOWED_ORIGINS:
        if "*" in origin:
            results["errors"].append(f"Wildcard CORS origin not allowed: {origin}")
            security_checks["cors_secure"] = False
        elif not origin.startswith(("http://", "https://")):
            results["errors"].append(f"CORS origin missing protocol: {origin}")
            security_checks["cors_secure"] = False
        else:
            security_checks["cors_secure"] = True

    # Validate production security settings
    if config.ENVIRONMENT == "production":
        if config.DEBUG:
            results["errors"].append("DEBUG must be False in production")
            security_checks["production_debug"] = False
        else:
            security_checks["production_debug"] = True

    # Check for unsafe patterns in keys
    unsafe_patterns = ["test", "example", "demo", "fallback", "change"]
    for key_name, key_value in [
        ("SECRET_KEY", config.SECRET_KEY),
        ("JWT_SECRET_KEY", config.JWT_SECRET_KEY),
        ("COPPA_ENCRYPTION_KEY", config.COPPA_ENCRYPTION_KEY),
    ]:
        key_lower = key_value.lower()
        unsafe_found = [pattern for pattern in unsafe_patterns if pattern in key_lower]
        if unsafe_found:
            results["errors"].append(
                f"{key_name} contains unsafe patterns: {unsafe_found}"
            )
            security_checks[f"{key_name}_safe"] = False
        else:
            security_checks[f"{key_name}_safe"] = True


async def _validate_connectivity(
    config: ProductionConfig, results: Dict[str, Any]
) -> None:
    """Validate connectivity to external services."""
    connectivity_checks = results["connectivity_checks"]

    # PostgreSQL validation
    try:
        import asyncpg

        # asyncpg only accepts postgresql:// or postgres://
        db_url = config.DATABASE_URL
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = "postgresql://" + db_url[len("postgresql+asyncpg://") :]

        conn = await asyncpg.connect(db_url)

        # Test basic query
        version = await conn.fetchval("SELECT version()")
        await conn.close()

        connectivity_checks["postgresql"] = True
        connectivity_checks["postgresql_version"] = version[:50]  # Truncate for safety
        logger.info("✅ PostgreSQL connection validated")

    except ImportError:
        results["warnings"].append("asyncpg not installed - cannot validate PostgreSQL")
        connectivity_checks["postgresql"] = "not_tested"
    except Exception as e:
        results["errors"].append(f"PostgreSQL connection failed: {str(e)}")
        connectivity_checks["postgresql"] = False

    # Redis validation
    try:
        import redis.asyncio as aioredis

        redis = aioredis.from_url(config.REDIS_URL)

        # Test ping
        await redis.ping()

        # Test basic operations
        await redis.set("config_test", "ok", ex=1)
        test_value = await redis.get("config_test")
        await redis.delete("config_test")

        await redis.aclose()  # Changed from close() to aclose() for redis.asyncio

        if test_value == b"ok":
            connectivity_checks["redis"] = True
            logger.info("✅ Redis connection validated")
        else:
            results["errors"].append("Redis basic operations failed")
            connectivity_checks["redis"] = False

    except ImportError:
        results["warnings"].append("aioredis not installed - cannot validate Redis")
        connectivity_checks["redis"] = "not_tested"
    except Exception as e:
        results["errors"].append(f"Redis connection failed: {str(e)}")
        connectivity_checks["redis"] = False

    # OpenAI API key validation (format only)
    if config.OPENAI_API_KEY.startswith("sk-") and len(config.OPENAI_API_KEY) > 20:
        connectivity_checks["openai_format"] = True
        logger.info("✅ OpenAI API key format validated")
    else:
        results["errors"].append("OpenAI API key format invalid")
        connectivity_checks["openai_format"] = False


def _validate_performance_settings(
    config: ProductionConfig, results: Dict[str, Any]
) -> None:
    """Validate performance-related settings."""
    performance_checks = results["performance_checks"]

    # Database pool settings
    if config.DATABASE_POOL_SIZE < 5:
        results["warnings"].append("Database pool size is very low (< 5)")
        performance_checks["db_pool_adequate"] = False
    else:
        performance_checks["db_pool_adequate"] = True

    if config.DATABASE_POOL_SIZE > config.DATABASE_MAX_OVERFLOW:
        results["warnings"].append("Database max_overflow should be >= pool_size")
        performance_checks["db_overflow_adequate"] = False
    else:
        performance_checks["db_overflow_adequate"] = True

    # Redis pool settings
    if config.REDIS_POOL_SIZE < 5:
        results["warnings"].append("Redis pool size is very low (< 5)")
        performance_checks["redis_pool_adequate"] = False
    else:
        performance_checks["redis_pool_adequate"] = True

    # Rate limiting settings
    if config.RATE_LIMIT_REQUESTS_PER_MINUTE > 300:
        results["warnings"].append("Very high rate limit may impact performance")
        performance_checks["rate_limit_reasonable"] = False
    else:
        performance_checks["rate_limit_reasonable"] = True

    # OpenAI settings
    if config.OPENAI_MAX_TOKENS > 2000:
        results["warnings"].append("High token limit may increase costs and latency")
        performance_checks["openai_tokens_reasonable"] = False
    else:
        performance_checks["openai_tokens_reasonable"] = True


def _validate_coppa_compliance(
    config: ProductionConfig, results: Dict[str, Any]
) -> None:
    """Validate COPPA compliance settings."""
    if not config.COPPA_COMPLIANCE_MODE:
        results["errors"].append(
            "COPPA compliance mode must be enabled for child-facing application"
        )

    if not config.CONTENT_FILTER_STRICT:
        results["errors"].append(
            "Strict content filtering must be enabled for child safety"
        )

    # Validate parent notification email
    import re

    email_pattern = r"^[^@]+@[^@]+\.[^@]+$"
    if not re.match(email_pattern, config.PARENT_NOTIFICATION_EMAIL):
        results["errors"].append("Invalid parent notification email format")


def _validate_production_readiness(
    config: ProductionConfig, results: Dict[str, Any]
) -> None:
    """Validate production readiness."""
    if config.ENVIRONMENT == "production":
        # Production-specific checks - CRITICAL ERRORS
        if any("localhost" in origin for origin in config.CORS_ALLOWED_ORIGINS):
            results["errors"].append(
                "❌ CRITICAL: localhost found in CORS origins for production environment"
            )

        if any("127.0.0.1" in origin for origin in config.CORS_ALLOWED_ORIGINS):
            results["errors"].append(
                "❌ CRITICAL: 127.0.0.1 found in CORS origins for production environment"
            )

        if any("localhost" in host for host in config.ALLOWED_HOSTS):
            results["errors"].append(
                "❌ CRITICAL: localhost found in ALLOWED_HOSTS for production environment"
            )

        if any("127.0.0.1" in host for host in config.ALLOWED_HOSTS):
            results["errors"].append(
                "❌ CRITICAL: 127.0.0.1 found in ALLOWED_HOSTS for production environment"
            )

        if config.HOST == "127.0.0.1":
            results["warnings"].append(
                "⚠️  Binding to 127.0.0.1 in production - consider 0.0.0.0"
            )

        # Check for development/test patterns
        import re

        database_url = config.DATABASE_URL.lower()
        allowed_schemes = ("postgresql://", "postgres://", "postgresql+asyncpg://")
        if not database_url.startswith(allowed_schemes):
            results["errors"].append(
                "Database URL must use a supported PostgreSQL schema (postgresql://, postgres://, or postgresql+asyncpg://)"
            )
        if "localhost" in database_url or "127.0.0.1" in database_url:
            results["errors"].append(
                "❌ CRITICAL: Database URL contains localhost/127.0.0.1 in production"
            )
        if "test" in database_url and config.ENVIRONMENT == "production":
            results["errors"].append(
                "❌ CRITICAL: Database URL contains 'test' in production environment"
            )

        # Check Redis URL
        redis_url = config.REDIS_URL.lower()
        if "localhost" in redis_url or "127.0.0.1" in redis_url:
            results["errors"].append(
                "❌ CRITICAL: Redis URL contains localhost/127.0.0.1 in production"
            )

        # Stripe configuration checks
        if hasattr(config, "STRIPE_SECRET_KEY"):
            if config.STRIPE_SECRET_KEY.startswith("sk_test_"):
                results["errors"].append(
                    "❌ CRITICAL: Using Stripe test key in production environment"
                )
            elif not config.STRIPE_SECRET_KEY.startswith("sk_live_"):
                results["warnings"].append(
                    "⚠️  Stripe secret key format unexpected (should start with sk_live_)"
                )

        if hasattr(config, "STRIPE_PUBLISHABLE_KEY"):
            if config.STRIPE_PUBLISHABLE_KEY.startswith("pk_test_"):
                results["errors"].append(
                    "❌ CRITICAL: Using Stripe test publishable key in production environment"
                )
            elif not config.STRIPE_PUBLISHABLE_KEY.startswith("pk_live_"):
                results["warnings"].append(
                    "⚠️  Stripe publishable key format unexpected (should start with pk_live_)"
                )

        # Optional but recommended settings
        if hasattr(config, "SENTRY_DSN") and not config.SENTRY_DSN:
            results["warnings"].append(
                "⚠️  No Sentry DSN configured for production error tracking"
            )

        # Domain validation for production
        production_patterns = ["aiteddybear.com", "teddy-bear.com"]
        if not any(
            pattern in str(config.CORS_ALLOWED_ORIGINS)
            for pattern in production_patterns
        ):
            results["warnings"].append(
                "⚠️  No production domain patterns found in CORS origins"
            )

        # Check for proper SSL enforcement
        if hasattr(config, "FORCE_HTTPS") and not config.FORCE_HTTPS:
            results["warnings"].append("⚠️  HTTPS enforcement is disabled in production")


async def validate_and_report(config: ProductionConfig) -> bool:
    """
    Validate configuration and print detailed report.

    Args:
        config: Configuration to validate

    Returns:
        True if validation passed, False otherwise
    """
    try:
        results = await validate_production_config(config)

        logger.info("Configuration validation report generated")
        logger.info(f"Security checks completed: {results['security_checks']}")
        logger.info(f"Connectivity checks completed: {results['connectivity_checks']}")
        logger.info(f"Performance checks completed: {results['performance_checks']}")

        if results["warnings"]:
            logger.warning(f"Configuration warnings detected: {results['warnings']}")

        if results["valid"]:
            logger.info("✅ Configuration validation PASSED")
        else:
            logger.error("❌ Configuration validation FAILED")

        return results

    except ConfigurationValidationError as e:
        logger.error(
            f"Configuration validation failed: {str(e)} (type={type(e).__name__})"
        )
        return {
            "valid": False,
            "errors": [str(e)],
            "warnings": [],
            "security_checks": {},
            "connectivity_checks": {},
            "performance_checks": {},
        }


class COPPAValidator:
    """COPPA compliance validator for child safety."""

    def validate_age(self, age: int) -> bool:
        """Validate that age is within COPPA compliance range (3-13)."""
        return 3 <= age <= 13

    def validate_child_data(self, data: dict) -> bool:
        """Validate child data meets COPPA requirements."""
        required_fields = ["age", "name"]
        for field in required_fields:
            if field not in data:
                return False

        if not self.validate_age(data["age"]):
            return False

        return True

    def validate_parent_consent(self, consent_data: dict) -> ValidationResult:
        """Validate parent consent."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[], details={})

        required = ["parent_email", "consent_timestamp", "ip_address"]
        missing = [f for f in required if f not in consent_data]
        if missing:
            result.add_error(f"Missing consent fields: {missing}", "coppa")

        return result
