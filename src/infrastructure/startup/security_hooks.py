#!/usr/bin/env python3
"""
Security Startup Hooks
======================
Critical security hooks that run during application startup.
These hooks ensure the application meets security requirements before serving requests.
"""

import os
import sys
import logging
from typing import Any, Dict
from fastapi import FastAPI
from contextlib import asynccontextmanager

# Add project path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from infrastructure.security.environment_validator import (
    EnvironmentSecurityValidator,
    validate_environment_on_startup,
)


class SecurityStartupHooks:
    """Security hooks for application startup."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validator = None
        self.security_checks_passed = False

    def run_environment_security_validation(self) -> bool:
        """Run comprehensive environment security validation."""
        try:
            self.logger.info("🔐 Starting environment security validation...")

            self.validator = EnvironmentSecurityValidator()
            is_safe = self.validator.startup_security_check()

            if not is_safe:
                self.logger.critical(
                    "💥 SECURITY VALIDATION FAILED - Application startup blocked"
                )
                return False

            self.logger.info("✅ Environment security validation passed")
            self.security_checks_passed = True
            return True

        except Exception as e:
            self.logger.critical(f"❌ Security validation error: {str(e)}")
            return False

    def validate_critical_services(self) -> bool:
        """Validate that critical services are properly configured."""
        try:
            self.logger.info("🔍 Validating critical service configurations...")

            # Database validation
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                self.logger.critical("💥 DATABASE_URL not configured")
                return False

            # Redis validation
            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                self.logger.critical("💥 REDIS_URL not configured")
                return False

            # JWT validation
            jwt_secret = os.getenv("JWT_SECRET_KEY")
            environment = os.getenv("ENVIRONMENT", "development")

            if environment == "production":
                # Production requires RSA keys
                private_key = os.getenv("JWT_PRIVATE_KEY")
                public_key = os.getenv("JWT_PUBLIC_KEY")

                if not private_key or not public_key:
                    self.logger.critical(
                        "💥 Production requires JWT_PRIVATE_KEY and JWT_PUBLIC_KEY"
                    )
                    return False
            elif not jwt_secret:
                self.logger.critical("💥 JWT_SECRET_KEY not configured")
                return False

            self.logger.info("✅ Critical services validation passed")
            return True

        except Exception as e:
            self.logger.critical(f"❌ Critical services validation error: {str(e)}")
            return False

    def check_production_readiness(self) -> bool:
        """Check if application is ready for production deployment."""
        try:
            environment = os.getenv("ENVIRONMENT", "development")

            if environment != "production":
                self.logger.info(f"ℹ️ Running in {environment} mode")
                return True

            self.logger.info("🚀 Validating production readiness...")

            # Check production-specific requirements
            production_requirements = [
                "JWT_PRIVATE_KEY",
                "JWT_PUBLIC_KEY",
                "DATABASE_URL",
                "REDIS_URL",
                "REDIS_PASSWORD",
                "STRIPE_SECRET_KEY",
                "SENTRY_DSN",
                "SECRET_KEY",
                "ENCRYPTION_KEY",
            ]

            missing_vars = []
            for var in production_requirements:
                if not os.getenv(var):
                    missing_vars.append(var)

            if missing_vars:
                self.logger.critical(
                    f"💥 Missing production environment variables: {missing_vars}"
                )
                return False

            # Check that debug mode is disabled
            debug_mode = os.getenv("DEBUG", "false").lower()
            if debug_mode in ["true", "1", "yes", "on"]:
                self.logger.critical("💥 DEBUG mode must be disabled in production")
                return False

            self.logger.info("✅ Production readiness validation passed")
            return True

        except Exception as e:
            self.logger.critical(f"❌ Production readiness validation error: {str(e)}")
            return False

    def run_all_security_checks(self) -> bool:
        """Run all security checks in sequence."""
        checks = [
            ("Environment Security", self.run_environment_security_validation),
            ("Critical Services", self.validate_critical_services),
            ("Production Readiness", self.check_production_readiness),
        ]

        for check_name, check_func in checks:
            self.logger.info(f"🔍 Running {check_name} validation...")
            if not check_func():
                self.logger.critical(
                    f"💥 {check_name} validation FAILED - Startup blocked"
                )
                return False

        self.logger.info("🎉 All security checks PASSED - Application startup approved")
        return True


# Global security hooks instance
security_hooks = SecurityStartupHooks()


@asynccontextmanager
async def security_lifespan(app: FastAPI):
    """FastAPI lifespan context manager with security checks."""

    # Startup security checks
    logging.info("🚀 Starting application with security validation...")

    if not security_hooks.run_all_security_checks():
        logging.critical("💥 STARTUP BLOCKED: Security validation failed")
        sys.exit(1)

    logging.info("✅ Application startup security validation completed")

    yield  # Application runs here

    # Cleanup on shutdown
    logging.info("🔒 Application shutdown initiated")


def create_secure_app() -> FastAPI:
    """Create FastAPI application with security hooks."""

    # Create FastAPI app with security lifespan
    app = FastAPI(
        title="AI Teddy Bear - Secure Production API",
        description="Child-safe AI companion with enterprise security",
        version="1.0.0",
        lifespan=security_lifespan,
    )

    # Add security middleware and routes here
    # This will be imported by main.py

    return app


def validate_startup_security():
    """Standalone function to validate startup security."""
    print("🔐 AI Teddy Bear - Security Validation")
    print("=" * 50)

    if not security_hooks.run_all_security_checks():
        print("\n💥 SECURITY VALIDATION FAILED")
        print("Application cannot start due to security issues.")
        print("Please resolve all security issues and try again.")
        sys.exit(1)

    print("\n🎉 SECURITY VALIDATION PASSED")
    print("Application is secure and ready to start.")
    return True


if __name__ == "__main__":
    # Run standalone security validation
    validate_startup_security()
