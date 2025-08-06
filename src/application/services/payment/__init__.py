"""
Iraqi Payment System Module
===========================
Complete payment processing system for the Iraqi market.

This module provides:
- Support for major Iraqi payment providers (ZainCash, FastPay, Switch, etc.)
- Mock implementations for testing without real money movement
- RESTful API endpoints for payment operations
- Comprehensive configuration system
- Production-ready examples and test cases

Usage:
    from src.application.services.payment import IraqiPaymentService, PaymentMethod

    service = IraqiPaymentService()
    result = await service.initiate_payment(payment_request)

Key Components:
- interfaces.py: Payment interfaces and data models
- mock_provider.py: Mock Iraqi payment provider implementations
- payment_service.py: Main payment coordination service
- api_endpoints.py: FastAPI REST endpoints
- config.py: Configuration and provider settings
- examples.py: Complete usage examples and testing utilities
"""

from .interfaces import (
    # Core enums
    PaymentStatus,
    PaymentMethod,
    Currency,
    ErrorCode,
    # Request/Response models
    PaymentRequest,
    PaymentResponse,
    PaymentStatusResponse,
    RefundRequest,
    RefundResponse,
    SubscriptionRequest,
    SubscriptionResponse,
    # Interfaces
    IPaymentProvider,
    # Exceptions
    PaymentProviderError,
)

from .payment_service import IraqiPaymentService, get_payment_service

from .mock_provider import MockIraqiPaymentProvider

from .config import (
    PaymentSystemConfig,
    ProviderConfig,
    Environment,
    get_payment_config,
    configure_for_environment,
    validate_config,
)

from .api_endpoints import router as payment_router

from .examples import PaymentExamples, PaymentSystemTester

# Version information
__version__ = "1.0.0"
__author__ = "AI Teddy Bear Team"
__description__ = "Iraqi Payment System for AI Teddy Bear Application"

# Public API
__all__ = [
    # Core enums
    "PaymentStatus",
    "PaymentMethod",
    "Currency",
    "ErrorCode",
    # Request/Response models
    "PaymentRequest",
    "PaymentResponse",
    "PaymentStatusResponse",
    "RefundRequest",
    "RefundResponse",
    "SubscriptionRequest",
    "SubscriptionResponse",
    # Interfaces
    "IPaymentProvider",
    # Main services
    "IraqiPaymentService",
    "get_payment_service",
    "MockIraqiPaymentProvider",
    # Configuration
    "PaymentSystemConfig",
    "ProviderConfig",
    "Environment",
    "get_payment_config",
    "configure_for_environment",
    "validate_config",
    # API
    "payment_router",
    # Testing and examples
    "PaymentExamples",
    "PaymentSystemTester",
    # Exceptions
    "PaymentProviderError",
    # Metadata
    "__version__",
    "__author__",
    "__description__",
]


def get_supported_providers() -> list[str]:
    """Get list of supported Iraqi payment providers."""
    return [method.value for method in PaymentMethod]


def get_system_info() -> dict:
    """Get system information and status."""
    config = get_payment_config()

    return {
        "version": __version__,
        "description": __description__,
        "environment": config.environment.value,
        "debug_mode": config.debug_mode,
        "supported_providers": get_supported_providers(),
        "enabled_providers": list(config.get_enabled_providers().keys()),
        "default_currency": config.default_currency,
        "max_refund_days": config.max_refund_days,
    }


async def health_check() -> dict:
    """Perform health check on payment system."""
    try:
        service = get_payment_service()
        config = get_payment_config()

        # Check configuration
        config_status = validate_config(config)

        # Check provider status
        provider_status = await service.get_provider_status()

        # Calculate overall health
        healthy_providers = sum(
            1 for status in provider_status.values() if status.get("available", False)
        )
        total_providers = len(provider_status)

        overall_health = (
            "healthy"
            if config_status["valid"] and healthy_providers > 0
            else "unhealthy"
        )

        return {
            "status": overall_health,
            "timestamp": import_datetime_now().isoformat(),
            "configuration": {
                "valid": config_status["valid"],
                "issues": config_status.get("issues", []),
                "warnings": config_status.get("warnings", []),
            },
            "providers": {
                "total": total_providers,
                "healthy": healthy_providers,
                "unhealthy": total_providers - healthy_providers,
                "details": provider_status,
            },
            "system_info": get_system_info(),
        }

    except Exception as e:
        return {
            "status": "error",
            "timestamp": import_datetime_now().isoformat(),
            "error": str(e),
            "system_info": get_system_info(),
        }


def import_datetime_now():
    """Import datetime.now to avoid circular import issues."""
    from datetime import datetime

    return datetime.utcnow()


# Quick start example
QUICK_START_EXAMPLE = """
# Quick Start Example - Iraqi Payment System

from src.application.services.payment import (
    IraqiPaymentService, 
    PaymentRequest, 
    PaymentMethod
)
from decimal import Decimal

# Initialize service
service = IraqiPaymentService()

# Create payment request
request = PaymentRequest(
    amount=Decimal("50000"),  # 50,000 IQD
    currency="IQD",
    payment_method=PaymentMethod.ZAIN_CASH,
    customer_phone="07901234567",
    customer_name="أحمد محمد",
    description="اشتراك شهري"
)

# Process payment
response = await service.initiate_payment(request)
print(f"Payment ID: {response.payment_id}")
print(f"Status: {response.status}")
print(f"USSD Code: {response.payment_code}")

# Check status
status = await service.get_payment_status(response.payment_id)
print(f"Final Status: {status.status}")
"""

# Configuration example
CONFIG_EXAMPLE = """
# Configuration Example

from src.application.services.payment import (
    get_payment_config, 
    configure_for_environment,
    Environment
)

# Get current config
config = get_payment_config()
print(f"Environment: {config.environment}")
print(f"Enabled providers: {list(config.get_enabled_providers().keys())}")

# Configure for production
production_config = configure_for_environment(Environment.PRODUCTION)
print(f"Production mode: {not production_config.debug_mode}")

# Check specific provider
if config.is_provider_enabled("zain_cash"):
    provider_config = config.get_provider_config("zain_cash")
    print(f"ZainCash max amount: {provider_config.max_amount} IQD")
"""
