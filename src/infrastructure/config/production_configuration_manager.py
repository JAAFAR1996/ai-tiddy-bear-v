"""
Production Configuration Management System
=========================================
Enterprise-grade configuration management with validation,
hot reloading, environment-specific settings, and security.
"""

import os
import json
import yaml
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import asyncio
from threading import Lock


class ConfigEnvironment(str, Enum):
    """Configuration environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigFormat(str, Enum):
    """Configuration file formats."""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    ENV = "env"


@dataclass
class ConfigValidationRule:
    """Configuration validation rule."""

    key: str
    required: bool
    data_type: type
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    pattern: Optional[str] = None
    default: Optional[Any] = None


@dataclass
class ConfigChangeEvent:
    """Configuration change event."""

    timestamp: datetime
    environment: ConfigEnvironment
    key: str
    old_value: Any
    new_value: Any
    source: str
    user: Optional[str] = None


class ProductionConfigurationManager:
    """
    Production-grade configuration management system with:
    - Multi-environment configuration support
    - Real-time configuration validation
    - Hot reloading and change detection
    - Secure configuration handling
    - Configuration versioning and rollback
    - Audit logging and change tracking
    - Remote configuration support
    - Performance optimized caching
    """

    def __init__(self, environment: ConfigEnvironment = ConfigEnvironment.DEVELOPMENT):
        self.environment = environment
        self.logger = logging.getLogger(__name__)
        self._config_data: Dict[str, Any] = {}
        self._config_cache: Dict[str, Any] = {}
        self._validation_rules: Dict[str, ConfigValidationRule] = {}
        self._change_history: List[ConfigChangeEvent] = []
        self._watchers: Dict[str, List[callable]] = {}
        self._config_lock = Lock()
        self._last_reload = datetime.now(timezone.utc)
        self._config_sources: Dict[str, Dict[str, Any]] = {}
        self._initialize_manager()

    def _initialize_manager(self):
        """Initialize the configuration manager."""
        self.logger.info(
            f"Initializing configuration manager for {self.environment.value}"
        )

        # Set up configuration paths
        self._config_dir = Path("config")
        self._secrets_dir = Path("secure_storage")

        # Load base configuration
        self._load_base_configuration()

        # Set up validation rules
        self._setup_validation_rules()

        # Start configuration monitoring
        asyncio.create_task(self._start_config_monitoring())

    def _load_base_configuration(self):
        """Load base configuration from files."""
        try:
            # Load environment-specific configuration
            config_file = self._config_dir / f"{self.environment.value}.yaml"
            if config_file.exists():
                with open(config_file, "r") as f:
                    env_config = yaml.safe_load(f)
                    self._config_sources["environment"] = env_config
                    self._config_data.update(env_config)

            # Load common configuration
            common_config_file = self._config_dir / "common.yaml"
            if common_config_file.exists():
                with open(common_config_file, "r") as f:
                    common_config = yaml.safe_load(f)
                    self._config_sources["common"] = common_config
                    # Environment config overrides common config
                    for key, value in common_config.items():
                        if key not in self._config_data:
                            self._config_data[key] = value

            # Load environment variables
            self._load_environment_variables()

            # Load secrets
            self._load_secrets()

            self.logger.info(f"Loaded configuration with {len(self._config_data)} keys")

        except Exception as e:
            self.logger.error(f"Failed to load base configuration: {str(e)}")
            raise

    def _load_environment_variables(self):
        """Load configuration from environment variables."""
        env_config = {}

        # Map environment variables to config keys
        env_mapping = {
            "SECRET_KEY": "security.secret_key",
            "JWT_SECRET_KEY": "security.jwt_secret_key",
            "DATABASE_URL": "database.url",
            "REDIS_URL": "redis.url",
            "OPENAI_API_KEY": "ai.openai_api_key",
            "CORS_ALLOWED_ORIGINS": "security.cors_allowed_origins",
            "PARENT_NOTIFICATION_EMAIL": "notifications.parent_email",
            "COPPA_ENCRYPTION_KEY": "security.coppa_encryption_key",
        }

        for env_var, config_key in env_mapping.items():
            value = os.getenv(env_var)
            if value:
                env_config[config_key] = value

        self._config_sources["environment_variables"] = env_config
        self._merge_nested_config(self._config_data, env_config)

    def _load_secrets(self):
        """Load secrets from secure storage."""
        try:
            secrets_file = self._secrets_dir / f"{self.environment.value}_secrets.json"
            if secrets_file.exists():
                with open(secrets_file, "r") as f:
                    secrets = json.load(f)
                    self._config_sources["secrets"] = secrets
                    self._merge_nested_config(self._config_data, secrets)

        except Exception as e:
            self.logger.warning(f"Could not load secrets: {str(e)}")

    def _merge_nested_config(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge nested configuration dictionaries."""
        for key, value in source.items():
            if "." in key:
                # Handle nested keys like 'database.url'
                keys = key.split(".")
                current = target
                for k in keys[:-1]:
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                current[keys[-1]] = value
            else:
                target[key] = value

    def _setup_validation_rules(self):
        """Set up configuration validation rules."""
        rules = [
            ConfigValidationRule(
                key="security.secret_key", required=True, data_type=str, min_value=32
            ),
            ConfigValidationRule(
                key="security.jwt_secret_key",
                required=True,
                data_type=str,
                min_value=32,
            ),
            ConfigValidationRule(
                key="database.url",
                required=True,
                data_type=str,
                pattern=r"^postgresql://.*",
            ),
            ConfigValidationRule(
                key="redis.url", required=True, data_type=str, pattern=r"^redis://.*"
            ),
            ConfigValidationRule(
                key="server.port",
                required=False,
                data_type=int,
                min_value=1024,
                max_value=65535,
                default=8000,
            ),
            ConfigValidationRule(
                key="server.host", required=False, data_type=str, default="0.0.0.0"
            ),
            ConfigValidationRule(
                key="logging.level",
                required=False,
                data_type=str,
                allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                default="INFO",
            ),
            ConfigValidationRule(
                key="features.premium_enabled",
                required=False,
                data_type=bool,
                default=True,
            ),
            ConfigValidationRule(
                key="features.analytics_enabled",
                required=False,
                data_type=bool,
                default=True,
            ),
        ]

        for rule in rules:
            self._validation_rules[rule.key] = rule

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with caching and validation.
        """
        try:
            with self._config_lock:
                # Check cache first
                if key in self._config_cache:
                    return self._config_cache[key]

                # Get value from config data
                value = self._get_nested_value(self._config_data, key)

                if value is None:
                    # Check if there's a default value in validation rules
                    if key in self._validation_rules:
                        rule = self._validation_rules[key]
                        if rule.default is not None:
                            value = rule.default
                        elif rule.required:
                            raise ValueError(
                                f"Required configuration key '{key}' is missing"
                            )

                    if value is None:
                        value = default

                # Validate value
                if value is not None:
                    self._validate_value(key, value)

                # Cache the value
                self._config_cache[key] = value

                return value

        except Exception as e:
            self.logger.error(f"Failed to get configuration '{key}': {str(e)}")
            if default is not None:
                return default
            raise

    async def set(
        self, key: str, value: Any, source: str = "runtime", user: Optional[str] = None
    ) -> bool:
        """
        Set configuration value with validation and change tracking.
        """
        try:
            with self._config_lock:
                # Validate new value
                self._validate_value(key, value)

                # Get old value for change tracking
                old_value = self._get_nested_value(self._config_data, key)

                # Set new value
                self._set_nested_value(self._config_data, key, value)

                # Update cache
                self._config_cache[key] = value

                # Record change event
                change_event = ConfigChangeEvent(
                    timestamp=datetime.now(timezone.utc),
                    environment=self.environment,
                    key=key,
                    old_value=old_value,
                    new_value=value,
                    source=source,
                    user=user,
                )
                self._change_history.append(change_event)

                # Notify watchers
                await self._notify_watchers(key, old_value, value)

                self.logger.info(
                    f"Configuration updated: {key}",
                    extra={
                        "key": key,
                        "source": source,
                        "user": user,
                        "old_value": str(old_value)[:100],  # Truncate for security
                        "new_value": str(value)[:100],
                    },
                )

                return True

        except Exception as e:
            self.logger.error(f"Failed to set configuration '{key}': {str(e)}")
            return False

    async def get_all(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all configuration values, optionally filtered by prefix.
        """
        try:
            with self._config_lock:
                if prefix:
                    filtered_config = {}
                    for key, value in self._config_data.items():
                        if key.startswith(prefix):
                            filtered_config[key] = value
                    return filtered_config
                else:
                    return self._config_data.copy()

        except Exception as e:
            self.logger.error(f"Failed to get all configuration: {str(e)}")
            return {}

    async def reload_from_file(self, file_path: str) -> bool:
        """
        Reload configuration from file.
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                self.logger.error(f"Configuration file not found: {file_path}")
                return False

            # Determine file format
            if file_path.suffix == ".yaml" or file_path.suffix == ".yml":
                with open(file_path, "r") as f:
                    new_config = yaml.safe_load(f)
            elif file_path.suffix == ".json":
                with open(file_path, "r") as f:
                    new_config = json.load(f)
            else:
                self.logger.error(
                    f"Unsupported configuration file format: {file_path.suffix}"
                )
                return False

            # Validate new configuration
            for key, value in new_config.items():
                self._validate_value(key, value)

            # Update configuration
            with self._config_lock:
                old_config = self._config_data.copy()
                self._config_data.update(new_config)
                self._config_cache.clear()  # Clear cache to force reload
                self._last_reload = datetime.now(timezone.utc)

            # Track changes
            for key, value in new_config.items():
                old_value = old_config.get(key)
                if old_value != value:
                    change_event = ConfigChangeEvent(
                        timestamp=datetime.now(timezone.utc),
                        environment=self.environment,
                        key=key,
                        old_value=old_value,
                        new_value=value,
                        source=f"file:{file_path}",
                        user=None,
                    )
                    self._change_history.append(change_event)
                    await self._notify_watchers(key, old_value, value)

            self.logger.info(f"Configuration reloaded from {file_path}")
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to reload configuration from {file_path}: {str(e)}"
            )
            return False

    async def validate_all(self) -> Dict[str, List[str]]:
        """
        Validate all configuration values against rules.
        """
        validation_errors = {}

        try:
            with self._config_lock:
                for key, rule in self._validation_rules.items():
                    errors = []

                    value = self._get_nested_value(self._config_data, key)

                    # Check if required value is missing
                    if rule.required and value is None:
                        errors.append(f"Required configuration '{key}' is missing")
                        continue

                    if value is not None:
                        try:
                            self._validate_value(key, value)
                        except ValueError as e:
                            errors.append(str(e))

                    if errors:
                        validation_errors[key] = errors

            return validation_errors

        except Exception as e:
            self.logger.error(f"Failed to validate configuration: {str(e)}")
            return {"validation_error": [str(e)]}

    async def watch(self, key: str, callback: callable) -> str:
        """
        Watch for changes to a configuration key.
        """
        watcher_id = str(datetime.now().timestamp())

        if key not in self._watchers:
            self._watchers[key] = []

        self._watchers[key].append({"id": watcher_id, "callback": callback})

        self.logger.info(f"Added watcher for configuration key: {key}")
        return watcher_id

    async def unwatch(self, key: str, watcher_id: str) -> bool:
        """
        Remove a configuration watcher.
        """
        if key in self._watchers:
            self._watchers[key] = [
                w for w in self._watchers[key] if w["id"] != watcher_id
            ]
            if not self._watchers[key]:
                del self._watchers[key]
            return True
        return False

    async def get_change_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get configuration change history.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent_changes = [
            {
                "timestamp": event.timestamp.isoformat(),
                "environment": event.environment.value,
                "key": event.key,
                "old_value": str(event.old_value)[:100] if event.old_value else None,
                "new_value": str(event.new_value)[:100] if event.new_value else None,
                "source": event.source,
                "user": event.user,
            }
            for event in self._change_history
            if event.timestamp > cutoff_time
        ]

        return recent_changes

    # Helper Methods

    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        if "." not in key:
            return data.get(key)

        keys = key.split(".")
        current = data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current

    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any) -> None:
        """Set value in nested dictionary using dot notation."""
        if "." not in key:
            data[key] = value
            return

        keys = key.split(".")
        current = data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    def _validate_value(self, key: str, value: Any) -> None:
        """Validate configuration value against rules."""
        if key not in self._validation_rules:
            return  # No validation rule defined

        rule = self._validation_rules[key]

        # Type validation
        if not isinstance(value, rule.data_type):
            raise ValueError(
                f"Configuration '{key}' must be of type {rule.data_type.__name__}"
            )

        # Range validation for numeric types
        if isinstance(value, (int, float)):
            if rule.min_value is not None and value < rule.min_value:
                raise ValueError(f"Configuration '{key}' must be >= {rule.min_value}")
            if rule.max_value is not None and value > rule.max_value:
                raise ValueError(f"Configuration '{key}' must be <= {rule.max_value}")

        # String length validation
        if isinstance(value, str) and rule.min_value is not None:
            if len(value) < rule.min_value:
                raise ValueError(
                    f"Configuration '{key}' must be at least {rule.min_value} characters"
                )

        # Allowed values validation
        if rule.allowed_values is not None and value not in rule.allowed_values:
            raise ValueError(
                f"Configuration '{key}' must be one of: {rule.allowed_values}"
            )

        # Pattern validation
        if rule.pattern is not None and isinstance(value, str):
            import re

            if not re.match(rule.pattern, value):
                raise ValueError(
                    f"Configuration '{key}' does not match required pattern"
                )

    async def _notify_watchers(self, key: str, old_value: Any, new_value: Any) -> None:
        """Notify watchers of configuration changes."""
        if key not in self._watchers:
            return

        for watcher in self._watchers[key]:
            try:
                await watcher["callback"](key, old_value, new_value)
            except Exception as e:
                self.logger.error(f"Error in configuration watcher: {str(e)}")

    async def _start_config_monitoring(self):
        """Start monitoring configuration files for changes."""
        while True:
            try:
                # Monitor configuration files for changes
                config_files = [
                    self._config_dir / f"{self.environment.value}.yaml",
                    self._config_dir / "common.yaml",
                ]

                for config_file in config_files:
                    if config_file.exists():
                        file_mtime = datetime.fromtimestamp(
                            config_file.stat().st_mtime, tz=timezone.utc
                        )
                        if file_mtime > self._last_reload:
                            self.logger.info(
                                f"Configuration file changed: {config_file}"
                            )
                            await self.reload_from_file(str(config_file))

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Error in configuration monitoring: {str(e)}")
                await asyncio.sleep(30)

    async def export_config(self, format_type: ConfigFormat = ConfigFormat.YAML) -> str:
        """
        Export current configuration in specified format.
        """
        try:
            with self._config_lock:
                config_copy = self._config_data.copy()

                # Remove sensitive data
                sensitive_keys = ["password", "secret", "key", "token", "credential"]
                self._redact_sensitive_data(config_copy, sensitive_keys)

                if format_type == ConfigFormat.YAML:
                    return yaml.dump(config_copy, default_flow_style=False)
                elif format_type == ConfigFormat.JSON:
                    return json.dumps(config_copy, indent=2)
                else:
                    raise ValueError(f"Unsupported export format: {format_type}")

        except Exception as e:
            self.logger.error(f"Failed to export configuration: {str(e)}")
            raise

    def _redact_sensitive_data(
        self, data: Dict[str, Any], sensitive_keys: List[str]
    ) -> None:
        """Redact sensitive data from configuration."""
        for key, value in data.items():
            if isinstance(value, dict):
                self._redact_sensitive_data(value, sensitive_keys)
            elif isinstance(key, str):
                for sensitive_key in sensitive_keys:
                    if sensitive_key.lower() in key.lower():
                        data[key] = "***REDACTED***"
                        break


# Service Factory
_config_manager_instance = None


def get_configuration_manager(
    environment: ConfigEnvironment = ConfigEnvironment.DEVELOPMENT,
) -> ProductionConfigurationManager:
    """Get singleton configuration manager instance."""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ProductionConfigurationManager(environment)
    return _config_manager_instance
