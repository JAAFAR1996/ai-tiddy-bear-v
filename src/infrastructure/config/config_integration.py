"""
Configuration Integration - FastAPI and Application Integration
============================================================
FastAPI integration for configuration management:
- Dependency injection for configuration
- Configuration validation middleware
- Hot reload configuration updates
- Configuration API endpoints
- Environment-specific configuration loading
- Health checks for configuration dependencies
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .production_config import ConfigurationManager, Environment, ConfigSource
from ..logging import get_logger, audit_logger, security_logger


# Additional configuration models
class ConfigItem(BaseModel):
    """Configuration item model."""

    key: str
    value: Any
    source: str = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConfigValidation(BaseModel):
    """Configuration validation model."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ConfigurationIntegration:
    """Main configuration integration for applications."""

    def __init__(self, config_manager: ConfigurationManager):
        self.config_manager = config_manager
        self.logger = get_logger("config_integration")
        self._health_checks: Dict[str, Callable] = {}
        self._dependency_callbacks: List[Callable] = []

    async def start(self):
        """Start configuration integration."""
        try:
            await self.config_manager.start()

            # Register health checks for critical dependencies
            await self._register_health_checks()

            self.logger.info("Configuration integration started")

        except Exception as e:
            self.logger.error(f"Failed to start configuration integration: {str(e)}")
            raise

    async def stop(self):
        """Stop configuration integration."""
        try:
            await self.config_manager.stop()
            self.logger.info("Configuration integration stopped")
        except Exception as e:
            self.logger.error(f"Error stopping configuration integration: {str(e)}")

    async def _register_health_checks(self):
        """Register health checks for configuration dependencies."""
        # Database health check
        if self.config_manager.get("DATABASE_URL"):
            self._health_checks["database"] = self._check_database_config

        # Redis health check
        if self.config_manager.get("REDIS_URL"):
            self._health_checks["redis"] = self._check_redis_config

        # AI Provider health check
        if self.config_manager.get("OPENAI_API_KEY"):
            self._health_checks["ai_providers"] = self._check_ai_provider_config

    async def _check_database_config(self) -> Dict[str, Any]:
        """Health check for database configuration."""
        try:
            database_url = self.config_manager.get("DATABASE_URL")
            pool_size = self.config_manager.get_int("DATABASE_POOL_SIZE", 10)
            timeout = self.config_manager.get_int("DATABASE_TIMEOUT", 30)

            return {
                "status": "healthy",
                "configured": True,
                "pool_size": pool_size,
                "timeout": timeout,
                "url_configured": bool(database_url),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def _check_redis_config(self) -> Dict[str, Any]:
        """Health check for Redis configuration."""
        try:
            redis_url = self.config_manager.get("REDIS_URL")
            max_connections = self.config_manager.get_int("REDIS_MAX_CONNECTIONS", 100)
            timeout = self.config_manager.get_int("REDIS_TIMEOUT", 5)

            return {
                "status": "healthy",
                "configured": True,
                "max_connections": max_connections,
                "timeout": timeout,
                "url_configured": bool(redis_url),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def _check_ai_provider_config(self) -> Dict[str, Any]:
        """Health check for AI provider configuration."""
        try:
            openai_key = self.config_manager.get("OPENAI_API_KEY")
            anthropic_key = self.config_manager.get("ANTHROPIC_API_KEY")
            timeout = self.config_manager.get_int("AI_PROVIDER_TIMEOUT", 30)

            return {
                "status": "healthy",
                "openai_configured": bool(openai_key),
                "anthropic_configured": bool(anthropic_key),
                "timeout": timeout,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall configuration health status."""
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "environment": self.config_manager.environment.value,
            "checks": {},
        }

        overall_healthy = True

        for check_name, check_func in self._health_checks.items():
            try:
                check_result = await check_func()
                health_status["checks"][check_name] = check_result

                if check_result.get("status") != "healthy":
                    overall_healthy = False

            except Exception as e:
                health_status["checks"][check_name] = {
                    "status": "error",
                    "error": str(e),
                }
                overall_healthy = False

        if not overall_healthy:
            health_status["overall_status"] = "unhealthy"

        return health_status

    def add_dependency_callback(self, callback: Callable):
        """Add callback for configuration dependency changes."""
        self._dependency_callbacks.append(callback)

        # Also add to config manager watchers
        self.config_manager.add_watcher(self._handle_config_change)

    async def _handle_config_change(self, key: str, value: Any):
        """Handle configuration changes."""
        self.logger.info(f"Configuration changed: {key}")

        # Notify dependency callbacks
        for callback in self._dependency_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(key, value)
                else:
                    callback(key, value)
            except Exception as e:
                self.logger.error(f"Error in dependency callback: {str(e)}")


# Global configuration integration instance
config_integration = ConfigurationIntegration(ConfigurationManager.get_instance())


@asynccontextmanager
async def config_lifespan(app: FastAPI):
    """Lifespan context manager for configuration integration."""
    # Startup
    await config_integration.start()

    try:
        yield
    finally:
        # Shutdown
        await config_integration.stop()


# Dependency injection functions
def get_config_manager() -> ConfigurationManager:
    """Dependency to get configuration manager."""
    from .config_manager_provider import get_config_manager as _get_config_manager

    return _get_config_manager()


def get_config_integration() -> ConfigurationIntegration:
    """Dependency to get configuration integration."""
    return config_integration


# Pydantic models for API
class ConfigUpdateRequest(BaseModel):
    """Configuration update request model."""

    key: str = Field(..., description="Configuration key")
    value: str = Field(..., description="Configuration value")
    source: str = Field(default="env", description="Configuration source")


class ConfigBulkUpdateRequest(BaseModel):
    """Bulk configuration update request."""

    updates: Dict[str, str] = Field(..., description="Configuration updates")
    source: str = Field(default="env", description="Configuration source")


class ConfigValidationRequest(BaseModel):
    """Configuration validation request."""

    config_data: Dict[str, Any] = Field(
        ..., description="Configuration data to validate"
    )


def add_config_routes(app: FastAPI):
    """Add configuration management routes to FastAPI application."""

    @app.get("/api/config/health")
    async def get_config_health(
        integration: ConfigurationIntegration = Depends(get_config_integration),
    ):
        """Get configuration health status."""
        return await integration.get_health_status()

    @app.get("/api/config")
    async def get_all_config(
        include_sensitive: bool = Query(False, description="Include sensitive values"),
        config_mgr: ConfigurationManager = Depends(get_config_manager),
    ):
        """Get all configuration items."""
        if include_sensitive:
            # Log security event for accessing sensitive config
            security_logger.warning(
                "Sensitive configuration accessed",
                metadata={
                    "endpoint": "/api/config",
                    "include_sensitive": True,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        config_data = config_mgr.get_all_config(include_sensitive=include_sensitive)
        metadata = config_mgr.get_config_metadata()

        return {
            "environment": config_mgr.environment.value,
            "config_count": len(config_data),
            "config": config_data,
            "metadata": metadata,
        }

    @app.get("/api/config/{key}")
    async def get_config_item(
        key: str = Path(..., description="Configuration key"),
        config_mgr: ConfigurationManager = Depends(get_config_manager),
    ):
        """Get specific configuration item."""
        value = config_mgr.get(key)
        if value is None:
            raise HTTPException(
                status_code=404, detail=f"Configuration key '{key}' not found"
            )

        # Get metadata
        metadata = config_mgr.get_config_metadata().get(key, {})

        # Don't return sensitive values in plain text
        if metadata.get("sensitive", False):
            value = "***SENSITIVE***"

        return {"key": key, "value": value, "metadata": metadata}

    @app.post("/api/config/{key}")
    async def update_config_item(
        key: str,
        request: ConfigUpdateRequest,
        background_tasks: BackgroundTasks,
        config_mgr: ConfigurationManager = Depends(get_config_manager),
    ):
        """Update specific configuration item."""
        try:
            source = ConfigSource(request.source)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid source: {request.source}"
            )

        try:
            await config_mgr.set(key, request.value, source)

            # Log the update
            audit_logger.audit(
                f"Configuration updated via API: {key}",
                metadata={
                    "key": key,
                    "source": source.value,
                    "timestamp": datetime.now().isoformat(),
                    "endpoint": "/api/config/{key}",
                },
            )

            return {
                "success": True,
                "message": f"Configuration '{key}' updated successfully",
                "key": key,
                "source": source.value,
            }

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to update configuration: {str(e)}"
            )

    @app.post("/api/config/bulk-update")
    async def bulk_update_config(
        request: ConfigBulkUpdateRequest,
        background_tasks: BackgroundTasks,
        config_mgr: ConfigurationManager = Depends(get_config_manager),
    ):
        """Bulk update configuration items."""
        try:
            source = ConfigSource(request.source)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid source: {request.source}"
            )

        success_count = 0
        errors = []

        for key, value in request.updates.items():
            try:
                await config_mgr.set(key, value, source)
                success_count += 1
            except Exception as e:
                errors.append(f"{key}: {str(e)}")

        # Log bulk update
        audit_logger.audit(
            f"Bulk configuration update via API",
            metadata={
                "updates_count": len(request.updates),
                "success_count": success_count,
                "error_count": len(errors),
                "source": source.value,
                "timestamp": datetime.now().isoformat(),
            },
        )

        return {
            "success": len(errors) == 0,
            "total_updates": len(request.updates),
            "successful_updates": success_count,
            "errors": errors,
        }

    @app.post("/api/config/validate")
    async def validate_config(
        request: ConfigValidationRequest,
        config_mgr: ConfigurationManager = Depends(get_config_manager),
    ):
        """Validate configuration data."""
        validation_errors = []

        for key, value in request.config_data.items():
            validation = config_mgr._get_validation_for_key(key)

            if validation:
                # Create temporary config item for validation
                temp_item = ConfigItem(
                    key=key,
                    value=value,
                    source=ConfigSource.DEFAULT,
                    environment=config_mgr.environment,
                    validation=validation,
                )

                errors = config_mgr._validate_config_item(temp_item)
                if errors:
                    validation_errors.extend([f"{key}: {error}" for error in errors])

        return {
            "valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "validated_keys": list(request.config_data.keys()),
        }

    @app.get("/api/config/schema")
    async def get_config_schema(
        config_mgr: ConfigurationManager = Depends(get_config_manager),
    ):
        """Get configuration schema."""
        schema_dict = {}

        # Convert schema to dictionary format
        for section_name in [
            "database",
            "redis",
            "ai_providers",
            "security",
            "logging",
            "monitoring",
            "storage",
            "communication",
            "child_safety",
            "application",
        ]:
            section = getattr(config_mgr._schema, section_name)
            section_dict = {}

            for key, validation in section.items():
                section_dict[key] = {
                    "required": validation.required,
                    "data_type": validation.data_type.__name__,
                    "sensitive": validation.sensitive,
                    "description": validation.description,
                    "min_value": validation.min_value,
                    "max_value": validation.max_value,
                    "min_length": validation.min_length,
                    "max_length": validation.max_length,
                    "pattern": validation.pattern,
                    "choices": validation.choices,
                }

            if section_dict:
                schema_dict[section_name] = section_dict

        return {"environment": config_mgr.environment.value, "schema": schema_dict}

    @app.post("/api/config/reload")
    async def reload_config(
        background_tasks: BackgroundTasks,
        config_mgr: ConfigurationManager = Depends(get_config_manager),
    ):
        """Reload configuration from all sources."""
        try:
            # Reload in background
            background_tasks.add_task(config_mgr.load_configuration)

            audit_logger.audit(
                "Configuration reload requested via API",
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "environment": config_mgr.environment.value,
                },
            )

            return {
                "success": True,
                "message": "Configuration reload initiated",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to reload configuration: {str(e)}"
            )

    @app.get("/api/config/environment/{env}")
    async def get_environment_config(
        env: str = Path(..., description="Environment name"),
        config_mgr: ConfigurationManager = Depends(get_config_manager),
    ):
        """Get configuration for specific environment."""
        try:
            environment = Environment(env.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid environment: {env}")

        # This would typically create a new config manager for the environment
        # For now, return current config if it matches
        if config_mgr.environment == environment:
            config_data = config_mgr.get_all_config(include_sensitive=False)
            return {"environment": environment.value, "config": config_data}
        else:
            return {
                "environment": environment.value,
                "message": f"Configuration for {environment.value} not loaded",
                "current_environment": config_mgr.environment.value,
            }


def create_config_app() -> FastAPI:
    """Create FastAPI application with configuration integration."""
    app = FastAPI(
        title="AI Teddy Bear Configuration API",
        version="1.0.0",
        lifespan=config_lifespan,
    )

    # Add configuration routes
    add_config_routes(app)

    return app


def setup_config_integration(app: FastAPI) -> ConfigurationIntegration:
    """Setup configuration integration with an existing FastAPI app."""
    # Add configuration routes
    add_config_routes(app)

    return config_integration


# Configuration dependency decorator
def with_config(config_key: str, default_value: Any = None):
    """Decorator to inject configuration values into functions."""

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # Inject configuration value
            config_value = ConfigurationManager.get_instance().get(
                config_key, default_value
            )
            kwargs[f"config_{config_key.lower()}"] = config_value
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Configuration validation decorator
def validate_config(*required_keys: str):
    """Decorator to validate required configuration keys."""

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            missing_keys = []
            for key in required_keys:
                if ConfigurationManager.get_instance().get(key) is None:
                    missing_keys.append(key)

            if missing_keys:
                raise ValueError(
                    f"Missing required configuration: {', '.join(missing_keys)}"
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


# Create the main configuration application
config_app = create_config_app()
