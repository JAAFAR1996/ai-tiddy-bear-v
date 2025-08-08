"""
Fallback System Integration Layer
================================
Integration layer that connects fallback management with existing services:
- Service registration and configuration
- Decorator-based fallback wrapping
- Container integration for dependency injection
- Health monitoring and metrics collection
- Environment-specific configuration loading
"""

import asyncio
import functools
import os
from typing import Dict, Any, Callable, Optional, Union, Type
from datetime import datetime

from src.infrastructure.resilience.fallback_manager import (
    ServiceFallbackManager, ServiceFallbackConfig, FailureReason
)
from src.infrastructure.resilience.service_fallback_configs import ServiceFallbackConfigs
from src.infrastructure.resilience.fallback_logger import (
    FallbackLogger, LogContext, EventType, fallback_logger
)


class FallbackIntegration:
    """
    Integration layer for fallback system with AI Teddy Bear services.
    
    Features:
    - Automatic service registration
    - Decorator-based fallback wrapping
    - Health monitoring integration
    - Metrics collection and reporting
    - Environment-specific configuration
    """
    
    def __init__(self):
        self.fallback_manager = ServiceFallbackManager()
        self.logger = fallback_logger
        self._registered_services: Dict[str, bool] = {}
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        
        # Initialize all service configurations
        self._initialize_service_configurations()
        
        self.logger.logger.info(
            "FallbackIntegration initialized",
            extra=self.logger._create_log_extra(
                LogContext(service_name="fallback_integration"),
                EventType.PROVIDER_SUCCESS,
                {"component": "integration", "action": "initialized"}
            )
        )
    
    def _initialize_service_configurations(self):
        """Initialize all service fallback configurations."""
        all_configs = ServiceFallbackConfigs.get_all_service_configs()
        environment_overrides = ServiceFallbackConfigs.get_environment_specific_overrides()
        
        for service_name, config in all_configs.items():
            # Apply environment-specific overrides
            if "all_services" in environment_overrides:
                self._apply_config_overrides(config, environment_overrides["all_services"])
            
            if service_name in environment_overrides:
                self._apply_config_overrides(config, environment_overrides[service_name])
            
            # Register service
            self.fallback_manager.register_service(config)
            self._registered_services[service_name] = True
            
            # Start health check monitoring
            self._start_health_monitoring(service_name, config)
    
    def _apply_config_overrides(self, config: ServiceFallbackConfig, overrides: Dict[str, Any]):
        """Apply environment-specific configuration overrides."""
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    def _start_health_monitoring(self, service_name: str, config: ServiceFallbackConfig):
        """Start background health monitoring for a service."""
        async def health_monitor():
            while True:
                try:
                    await self._perform_health_checks(service_name, config)
                    await asyncio.sleep(config.health_check_interval_seconds)
                except Exception as e:
                    self.logger.log_operation_error(
                        LogContext(service_name=service_name),
                        e
                    )
                    await asyncio.sleep(30)  # Retry after 30 seconds on error
        
        task = asyncio.create_task(health_monitor())
        self._health_check_tasks[service_name] = task
    
    async def _perform_health_checks(self, service_name: str, config: ServiceFallbackConfig):
        """Perform health checks for all providers of a service."""
        context = LogContext(
            service_name=service_name,
            operation_id=f"health_check_{datetime.now().isoformat()}"
        )
        
        for tier, providers in config.tier_providers.items():
            for provider in providers:
                try:
                    # This would call actual provider health check
                    # For now, we'll simulate based on circuit breaker state
                    is_healthy = self._simulate_provider_health_check(service_name, provider)
                    
                    self.logger.log_health_check(
                        context,
                        provider,
                        is_healthy,
                        additional_data={"tier": tier.value}
                    )
                    
                except Exception as e:
                    self.logger.log_health_check(
                        context,
                        provider,
                        False,
                        error=str(e),
                        additional_data={"tier": tier.value}
                    )
    
    def _simulate_provider_health_check(self, service_name: str, provider: str) -> bool:
        """Simulate provider health check based on circuit breaker state."""
        circuit_breakers = self.fallback_manager.circuit_breakers.get(service_name, {})
        circuit_breaker = circuit_breakers.get(provider, {})
        
        # Provider is healthy if circuit breaker is closed or half-open
        state = circuit_breaker.get("state", "closed")
        return state in ["closed", "half_open"]
    
    def with_fallback(
        self,
        service_name: str,
        failure_detector: Optional[Callable[[Exception], FailureReason]] = None,
        operation_name: str = None,
        user_id: str = None,
        session_id: str = None
    ):
        """
        Decorator to add fallback capabilities to service methods.
        
        Args:
            service_name: Name of the service for fallback configuration
            failure_detector: Function to categorize exceptions
            operation_name: Name of the operation for logging
            user_id: User ID for context
            session_id: Session ID for context
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Create operation context
                context = LogContext(
                    service_name=service_name,
                    operation_id=f"{service_name}_{operation_name or func.__name__}_{datetime.now().isoformat()}",
                    user_id=user_id,
                    session_id=session_id,
                    environment=os.getenv("ENVIRONMENT", "development")
                )
                
                # Execute with fallback using the context manager
                with self.logger.operation_context(context):
                    result, metadata = await self.fallback_manager.execute_with_fallback(
                        service_name=service_name,
                        operation=func,
                        *args,
                        failure_detector=failure_detector,
                        **kwargs
                    )
                    
                    # Log successful operation
                    self.logger.log_provider_success(
                        context,
                        metadata.get("final_provider", "unknown"),
                        metadata.get("response_time_ms", 0),
                        additional_data={
                            "final_tier": metadata.get("final_tier"),
                            "total_attempts": metadata.get("total_attempts"),
                            "success": metadata.get("success")
                        }
                    )
                    
                    return result
            
            return wrapper
        return decorator
    
    def register_custom_service(
        self,
        service_name: str,
        config: ServiceFallbackConfig
    ):
        """Register a custom service configuration."""
        self.fallback_manager.register_service(config)
        self._registered_services[service_name] = True
        self._start_health_monitoring(service_name, config)
        
        self.logger.logger.info(
            f"Custom service registered: {service_name}",
            extra=self.logger._create_log_extra(
                LogContext(service_name=service_name),
                EventType.PROVIDER_SUCCESS,
                {"action": "custom_service_registered"}
            )
        )
    
    def get_service_health(self, service_name: str = None) -> Dict[str, Any]:
        """Get health status for a service or all services."""
        if service_name:
            return self.fallback_manager.get_service_metrics(service_name)
        else:
            return self.fallback_manager.get_all_metrics()
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health including fallback status."""
        fallback_health = await self.fallback_manager.health_check()
        logger_metrics = self.logger.get_metrics_summary()
        
        return {
            "overall_status": fallback_health.get("status", "unknown"),
            "fallback_manager": fallback_health,
            "logging_metrics": logger_metrics,
            "registered_services": list(self._registered_services.keys()),
            "health_monitoring_active": len(self._health_check_tasks),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    def create_failure_detector(self, service_type: str) -> Callable[[Exception], FailureReason]:
        """Create a service-specific failure detector."""
        def detect_failure(exception: Exception) -> FailureReason:
            error_str = str(exception).lower()
            error_type = type(exception).__name__.lower()
            
            # Service-specific failure detection
            if service_type == "ai_service":
                if "rate_limit" in error_str or "429" in error_str:
                    return FailureReason.RATE_LIMIT_EXCEEDED
                elif "quota" in error_str or "billing" in error_str:
                    return FailureReason.QUOTA_EXCEEDED
                elif "timeout" in error_str or "asyncio.timeout" in error_type:
                    return FailureReason.TIMEOUT
                elif "connection" in error_str or "network" in error_str:
                    return FailureReason.CONNECTION_ERROR
                elif "unauthorized" in error_str or "401" in error_str:
                    return FailureReason.AUTHENTICATION_ERROR
                elif "unavailable" in error_str or "503" in error_str:
                    return FailureReason.SERVICE_UNAVAILABLE
            
            elif service_type == "tts_service":
                if "audio" in error_str and "invalid" in error_str:
                    return FailureReason.VALIDATION_ERROR
                elif "voice" in error_str and "not_found" in error_str:
                    return FailureReason.VALIDATION_ERROR
                elif "rate_limit" in error_str:
                    return FailureReason.RATE_LIMIT_EXCEEDED
                elif "timeout" in error_str or "slow" in error_str:
                    return FailureReason.TIMEOUT
            
            elif service_type == "stt_service":
                if "audio" in error_str and ("format" in error_str or "codec" in error_str):
                    return FailureReason.VALIDATION_ERROR
                elif "too_long" in error_str or "duration" in error_str:
                    return FailureReason.VALIDATION_ERROR
                elif "timeout" in error_str:
                    return FailureReason.TIMEOUT
            
            elif service_type == "safety_service":
                # Safety service failures are critical
                if "timeout" in error_str:
                    return FailureReason.TIMEOUT
                elif "connection" in error_str:
                    return FailureReason.CONNECTION_ERROR
                else:
                    return FailureReason.SERVICE_UNAVAILABLE  # Fail secure
            
            # Default failure detection
            if "timeout" in error_str:
                return FailureReason.TIMEOUT
            elif "connection" in error_str or "network" in error_str:
                return FailureReason.CONNECTION_ERROR
            elif "auth" in error_str or "unauthorized" in error_str:
                return FailureReason.AUTHENTICATION_ERROR
            elif "rate" in error_str or "429" in error_str:
                return FailureReason.RATE_LIMIT_EXCEEDED
            elif "quota" in error_str or "limit" in error_str:
                return FailureReason.QUOTA_EXCEEDED
            elif "unavailable" in error_str or "503" in error_str:
                return FailureReason.SERVICE_UNAVAILABLE
            elif "validation" in error_str or "invalid" in error_str:
                return FailureReason.VALIDATION_ERROR
            else:
                return FailureReason.UNKNOWN_ERROR
        
        return detect_failure
    
    async def shutdown(self):
        """Shutdown fallback integration and cleanup resources."""
        # Cancel health check tasks
        for task in self._health_check_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self._health_check_tasks:
            await asyncio.gather(*self._health_check_tasks.values(), return_exceptions=True)
        
        # Flush logs
        await self.logger.flush_logs()
        
        self.logger.logger.info(
            "FallbackIntegration shutdown complete",
            extra=self.logger._create_log_extra(
                LogContext(service_name="fallback_integration"),
                EventType.PROVIDER_SUCCESS,
                {"action": "shutdown_complete"}
            )
        )


# Global fallback integration instance
fallback_integration = FallbackIntegration()


# Convenience decorators for common services
def with_ai_fallback(
    operation_name: str = None,
    user_id: str = None,
    session_id: str = None
):
    """Decorator for AI service operations with fallback."""
    return fallback_integration.with_fallback(
        service_name="ai_service",
        failure_detector=fallback_integration.create_failure_detector("ai_service"),
        operation_name=operation_name,
        user_id=user_id,
        session_id=session_id
    )


def with_tts_fallback(
    operation_name: str = None,
    user_id: str = None,
    session_id: str = None
):
    """Decorator for TTS service operations with fallback."""
    return fallback_integration.with_fallback(
        service_name="tts_service",
        failure_detector=fallback_integration.create_failure_detector("tts_service"),
        operation_name=operation_name,
        user_id=user_id,
        session_id=session_id
    )


def with_stt_fallback(
    operation_name: str = None,
    user_id: str = None,
    session_id: str = None
):
    """Decorator for STT service operations with fallback."""
    return fallback_integration.with_fallback(
        service_name="stt_service",
        failure_detector=fallback_integration.create_failure_detector("stt_service"),
        operation_name=operation_name,
        user_id=user_id,
        session_id=session_id
    )


def with_safety_fallback(
    operation_name: str = None,
    user_id: str = None,
    session_id: str = None
):
    """Decorator for Safety service operations with fallback."""
    return fallback_integration.with_fallback(
        service_name="safety_service",
        failure_detector=fallback_integration.create_failure_detector("safety_service"),
        operation_name=operation_name,
        user_id=user_id,
        session_id=session_id
    )


def with_notification_fallback(
    operation_name: str = None,
    user_id: str = None,
    session_id: str = None
):
    """Decorator for Notification service operations with fallback."""
    return fallback_integration.with_fallback(
        service_name="notification_service",
        failure_detector=fallback_integration.create_failure_detector("notification_service"),
        operation_name=operation_name,
        user_id=user_id,
        session_id=session_id
    )


def with_storage_fallback(
    operation_name: str = None,
    user_id: str = None,
    session_id: str = None
):
    """Decorator for File Storage operations with fallback."""
    return fallback_integration.with_fallback(
        service_name="file_storage",
        failure_detector=fallback_integration.create_failure_detector("file_storage"),
        operation_name=operation_name,
        user_id=user_id,
        session_id=session_id
    )


def with_database_fallback(
    operation_name: str = None,
    user_id: str = None,
    session_id: str = None
):
    """Decorator for Database operations with fallback."""
    return fallback_integration.with_fallback(
        service_name="database_service",
        failure_detector=fallback_integration.create_failure_detector("database_service"),
        operation_name=operation_name,
        user_id=user_id,
        session_id=session_id
    )
