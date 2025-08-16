"""
Feature Flags Configuration for AI Teddy Bear
==============================================
Centralized feature flag management for safe production rollouts
"""

import os
from typing import Dict, Any

def get_feature_flags() -> Dict[str, Any]:
    """
    Get feature flags from environment with production-safe defaults
    
    Production defaults are conservative:
    - Idempotency: false (enable after testing)
    - Auto-register: false (security risk if enabled)
    - ID normalization in HMAC: false (requires firmware update)
    """
    return {
        # Idempotency - safe to enable after testing
        "ENABLE_IDEMPOTENCY": os.getenv("ENABLE_IDEMPOTENCY", "false").lower() == "true",
        
        # Graceful degradation if Redis is down
        "DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE": os.getenv(
            "DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE", "true"
        ).lower() == "true",
        
        # Auto-registration - MUST be false in prod by default
        "ENABLE_AUTO_REGISTER": os.getenv("ENABLE_AUTO_REGISTER", "false").lower() == "true",
        
        # Fail closed on Redis errors in prod
        "FAIL_OPEN_ON_REDIS_ERROR": os.getenv(
            "FAIL_OPEN_ON_REDIS_ERROR", "false"
        ).lower() == "true",
        
        # Normalize IDs in HMAC calculation - requires firmware update
        "NORMALIZE_IDS_IN_HMAC": os.getenv(
            "NORMALIZE_IDS_IN_HMAC", "false"
        ).lower() == "true",
    }


def apply_feature_flags_to_config(config: Any) -> Any:
    """
    Apply feature flags to config object at startup
    
    This should be called once during application initialization
    """
    flags = get_feature_flags()
    
    for key, value in flags.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            # Skip attributes that don't exist in the config model
            # This prevents AttributeError on Pydantic models
            pass
    
    # Log configuration (without exposing sensitive data)
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(
        "Feature flags configured",
        extra={
            "ENABLE_IDEMPOTENCY": getattr(config, "ENABLE_IDEMPOTENCY", False),
            "DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE": getattr(config, "DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE", True),
            "ENABLE_AUTO_REGISTER": getattr(config, "ENABLE_AUTO_REGISTER", False),
            "FAIL_OPEN_ON_REDIS_ERROR": getattr(config, "FAIL_OPEN_ON_REDIS_ERROR", False),
            "NORMALIZE_IDS_IN_HMAC": getattr(config, "NORMALIZE_IDS_IN_HMAC", False),
            "environment": getattr(config, "ENVIRONMENT", "unknown")
        }
    )
    
    return config


# Environment-specific presets
FEATURE_PRESETS = {
    "production": {
        "ENABLE_IDEMPOTENCY": False,  # Enable after testing
        "DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE": True,
        "ENABLE_AUTO_REGISTER": False,  # Security risk
        "FAIL_OPEN_ON_REDIS_ERROR": False,  # Fail closed
        "NORMALIZE_IDS_IN_HMAC": False,  # Requires firmware update
    },
    "staging": {
        "ENABLE_IDEMPOTENCY": True,  # Test here first
        "DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE": True,
        "ENABLE_AUTO_REGISTER": True,  # Allow for testing
        "FAIL_OPEN_ON_REDIS_ERROR": False,
        "NORMALIZE_IDS_IN_HMAC": False,  # Test separately
    },
    "development": {
        "ENABLE_IDEMPOTENCY": True,
        "DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE": True,
        "ENABLE_AUTO_REGISTER": True,
        "FAIL_OPEN_ON_REDIS_ERROR": True,
        "NORMALIZE_IDS_IN_HMAC": True,  # Test all features
    }
}


def get_preset_for_environment(environment: str) -> Dict[str, Any]:
    """Get recommended feature flag preset for environment"""
    return FEATURE_PRESETS.get(environment, FEATURE_PRESETS["production"])