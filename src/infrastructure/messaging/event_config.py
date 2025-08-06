"""
Event Bus Configuration - Production Settings
===========================================
Configuration management for the event bus system:
- Environment-specific settings
- Handler configuration
- Backend configuration
- Retry and circuit breaker settings
- Monitoring and metrics configuration
"""

import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from .production_event_bus_advanced import BackendType, EventPriority, CircuitBreakerConfig


class Environment(Enum):
    """Environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class RetryConfig:
    """Retry configuration for event processing."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 300.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class RedisConfig:
    """Redis configuration for event bus."""
    url: str = "redis://localhost:6379"
    max_connections: int = 100
    connection_timeout: int = 5
    socket_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    
    # Stream configuration
    max_stream_length: int = 10000
    consumer_group: str = "event_processors"
    consumer_name: str = "processor_1"
    block_time: int = 1000
    batch_size: int = 10


@dataclass
class RabbitMQConfig:
    """RabbitMQ configuration for event bus."""
    url: str = "amqp://guest:guest@localhost:5672/"
    max_connections: int = 20
    connection_timeout: int = 10
    heartbeat: int = 600
    prefetch_count: int = 10
    
    # Exchange configuration
    main_exchange: str = "events"
    dlq_exchange: str = "events_dlq"
    retry_exchange: str = "events_retry"
    
    # Queue configuration
    durable: bool = True
    auto_delete: bool = False
    exclusive: bool = False


@dataclass
class MonitoringConfig:
    """Monitoring and metrics configuration."""
    enable_metrics: bool = True
    metrics_interval: int = 60
    health_check_interval: int = 30
    
    # Performance thresholds
    slow_processing_threshold: float = 2.0
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60
    
    # Alerting
    enable_alerts: bool = True
    alert_channels: List[str] = field(default_factory=lambda: ["log", "webhook"])
    webhook_url: Optional[str] = None


@dataclass
class EventBusConfig:
    """Complete event bus configuration."""
    environment: Environment = Environment.DEVELOPMENT
    backend_type: BackendType = BackendType.HYBRID
    
    # Backend configurations
    redis: RedisConfig = field(default_factory=RedisConfig)
    rabbitmq: RabbitMQConfig = field(default_factory=RabbitMQConfig)
    
    # Processing configuration
    retry: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    
    # Monitoring
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Event sourcing
    enable_event_sourcing: bool = True
    event_store_retention_days: int = 90
    
    # Security
    enable_encryption: bool = False
    encryption_key: Optional[str] = None
    
    # Handler configuration
    handler_timeout: int = 30
    max_concurrent_handlers: int = 100
    
    # Dead letter queue
    dlq_max_retries: int = 3
    dlq_retention_days: int = 30


class EventConfigManager:
    """Manager for event bus configuration."""
    
    def __init__(self):
        self._config: Optional[EventBusConfig] = None
        self._environment = Environment(os.getenv("ENVIRONMENT", "development"))
    
    def get_config(self) -> EventBusConfig:
        """Get event bus configuration."""
        if self._config is None:
            self._config = self._load_config()
        return self._config
    
    def _load_config(self) -> EventBusConfig:
        """Load configuration based on environment."""
        if self._environment == Environment.PRODUCTION:
            return self._get_production_config()
        elif self._environment == Environment.STAGING:
            return self._get_staging_config()
        elif self._environment == Environment.TESTING:
            return self._get_testing_config()
        else:
            return self._get_development_config()
    
    def _get_production_config(self) -> EventBusConfig:
        """Production configuration."""
        return EventBusConfig(
            environment=Environment.PRODUCTION,
            backend_type=BackendType(os.getenv("EVENT_BUS_BACKEND", "hybrid")),
            
            redis=RedisConfig(
                url=os.getenv("REDIS_URL", "redis://redis-cluster:6379"),
                max_connections=200,
                connection_timeout=5,
                socket_timeout=5,
                health_check_interval=15,
                max_stream_length=50000,
                batch_size=20
            ),
            
            rabbitmq=RabbitMQConfig(
                url=os.getenv("RABBITMQ_URL", "amqp://events:password@rabbitmq-cluster:5672/"),
                max_connections=50,
                connection_timeout=10,
                heartbeat=300,
                prefetch_count=20
            ),
            
            retry=RetryConfig(
                max_attempts=5,
                initial_delay=2.0,
                max_delay=600.0,
                exponential_base=2.0,
                jitter=True
            ),
            
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=10,
                recovery_timeout=120,
                success_threshold=5,
                request_timeout=60
            ),
            
            monitoring=MonitoringConfig(
                enable_metrics=True,
                metrics_interval=30,
                health_check_interval=15,
                slow_processing_threshold=1.0,
                circuit_breaker_failure_threshold=10,
                enable_alerts=True,
                alert_channels=["log", "webhook", "slack"],
                webhook_url=os.getenv("ALERT_WEBHOOK_URL")
            ),
            
            enable_event_sourcing=True,
            event_store_retention_days=365,
            enable_encryption=True,
            encryption_key=os.getenv("EVENT_ENCRYPTION_KEY"),
            handler_timeout=60,
            max_concurrent_handlers=200,
            dlq_max_retries=5,
            dlq_retention_days=90
        )
    
    def _get_staging_config(self) -> EventBusConfig:
        """Staging configuration."""
        return EventBusConfig(
            environment=Environment.STAGING,
            backend_type=BackendType(os.getenv("EVENT_BUS_BACKEND", "hybrid")),
            
            redis=RedisConfig(
                url=os.getenv("REDIS_URL", "redis://staging-redis:6379"),
                max_connections=100,
                health_check_interval=30,
                max_stream_length=25000,
                batch_size=15
            ),
            
            rabbitmq=RabbitMQConfig(
                url=os.getenv("RABBITMQ_URL", "amqp://events:password@staging-rabbitmq:5672/"),
                max_connections=30,
                prefetch_count=15
            ),
            
            retry=RetryConfig(
                max_attempts=4,
                initial_delay=1.5,
                max_delay=300.0
            ),
            
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=7,
                recovery_timeout=90,
                success_threshold=3
            ),
            
            monitoring=MonitoringConfig(
                enable_metrics=True,
                metrics_interval=45,
                health_check_interval=20,
                enable_alerts=True,
                alert_channels=["log", "webhook"]
            ),
            
            enable_event_sourcing=True,
            event_store_retention_days=180,
            enable_encryption=False,
            handler_timeout=45,
            max_concurrent_handlers=150
        )
    
    def _get_development_config(self) -> EventBusConfig:
        """Development configuration."""
        return EventBusConfig(
            environment=Environment.DEVELOPMENT,
            backend_type=BackendType(os.getenv("EVENT_BUS_BACKEND", "redis_streams")),
            
            redis=RedisConfig(
                url=os.getenv("REDIS_URL", "redis://localhost:6379"),
                max_connections=20,
                health_check_interval=60,
                max_stream_length=5000,
                batch_size=5
            ),
            
            rabbitmq=RabbitMQConfig(
                url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
                max_connections=10,
                prefetch_count=5
            ),
            
            retry=RetryConfig(
                max_attempts=2,
                initial_delay=0.5,
                max_delay=60.0
            ),
            
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30,
                success_threshold=2,
                request_timeout=30
            ),
            
            monitoring=MonitoringConfig(
                enable_metrics=True,
                metrics_interval=120,
                health_check_interval=60,
                slow_processing_threshold=5.0,
                enable_alerts=False
            ),
            
            enable_event_sourcing=True,
            event_store_retention_days=30,
            enable_encryption=False,
            handler_timeout=30,
            max_concurrent_handlers=50
        )
    
    def _get_testing_config(self) -> EventBusConfig:
        """Testing configuration."""
        return EventBusConfig(
            environment=Environment.TESTING,
            backend_type=BackendType.REDIS_STREAMS,
            
            redis=RedisConfig(
                url="redis://localhost:6379/15",  # Use test database
                max_connections=5,
                health_check_interval=300,
                max_stream_length=1000,
                batch_size=1
            ),
            
            retry=RetryConfig(
                max_attempts=1,
                initial_delay=0.1,
                max_delay=1.0
            ),
            
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=2,
                recovery_timeout=5,
                success_threshold=1,
                request_timeout=10
            ),
            
            monitoring=MonitoringConfig(
                enable_metrics=False,
                enable_alerts=False
            ),
            
            enable_event_sourcing=False,
            enable_encryption=False,
            handler_timeout=10,
            max_concurrent_handlers=10
        )
    
    def get_handler_config(self, handler_name: str) -> Dict[str, Any]:
        """Get configuration for specific handler."""
        config = self.get_config()
        
        # Default handler configuration
        handler_config = {
            "timeout": config.handler_timeout,
            "max_retries": config.retry.max_attempts,
            "circuit_breaker": {
                "failure_threshold": config.circuit_breaker.failure_threshold,
                "recovery_timeout": config.circuit_breaker.recovery_timeout,
                "success_threshold": config.circuit_breaker.success_threshold
            }
        }
        
        # Handler-specific overrides
        handler_overrides = {
            "child_interaction_handler": {
                "timeout": 15,  # Quick response for child interactions
                "priority": "normal"
            },
            "audit_handler": {
                "timeout": 60,  # More time for audit logging
                "priority": "high",
                "max_retries": 5  # Critical for compliance
            },
            "system_monitoring_handler": {
                "timeout": 30,
                "priority": "high"
            },
            "user_management_handler": {
                "timeout": 30,
                "priority": "normal"
            }
        }
        
        if handler_name in handler_overrides:
            handler_config.update(handler_overrides[handler_name])
        
        return handler_config
    
    def get_event_priority(self, event_type: str) -> EventPriority:
        """Get priority for event type."""
        high_priority_events = {
            "system.error.critical",
            "system.health.degraded",
            "audit.security.violation",
            "child.safety.violation"
        }
        
        critical_priority_events = {
            "system.capacity.critical",
            "audit.data.breach",
            "child.emergency.detected"
        }
        
        if event_type in critical_priority_events:
            return EventPriority.CRITICAL
        elif event_type in high_priority_events:
            return EventPriority.HIGH
        else:
            return EventPriority.NORMAL
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return any issues."""
        config = self.get_config()
        issues = []
        
        # Check Redis URL
        if not config.redis.url:
            issues.append("Redis URL is required")
        
        # Check RabbitMQ URL for hybrid/rabbitmq backends
        if config.backend_type in [BackendType.HYBRID, BackendType.RABBITMQ]:
            if not config.rabbitmq.url:
                issues.append("RabbitMQ URL is required for hybrid/rabbitmq backend")
        
        # Check encryption key for production
        if config.environment == Environment.PRODUCTION and config.enable_encryption:
            if not config.encryption_key:
                issues.append("Encryption key is required for production with encryption enabled")
        
        # Check alert webhook URL
        if config.monitoring.enable_alerts and "webhook" in config.monitoring.alert_channels:
            if not config.monitoring.webhook_url:
                issues.append("Webhook URL is required when webhook alerts are enabled")
        
        return issues


# Global configuration manager
config_manager = EventConfigManager()