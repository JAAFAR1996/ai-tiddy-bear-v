"""Factory functions for creating service instances using the DI container.

These factories provide a clean way to instantiate services without
exposing the container directly to other layers.
"""
import logging
from typing import Any, Dict, Optional, Type
from .container import get_injector
from ..core.exceptions import ConfigurationError, ServiceUnavailableError
from ..interfaces.read_model_interfaces import (
    IChildProfileReadModel,
    IChildProfileReadModelStore,
    IExternalAPIClient
)

logger = logging.getLogger(__name__)


def _safe_get_service(service_name: str, service_type: Optional[Type] = None):
    """Safely get service from container with proper error handling."""
    try:
        injector = get_injector()
        service = injector.get(service_name)
        if service is None:
            raise ServiceUnavailableError(
                f"Service '{service_name}' not available",
                service=service_name
            )
        return service
    except KeyError:
        raise ConfigurationError(
            f"Service '{service_name}' not configured",
            config_key=service_name
        )
    except Exception as e:
        logger.error(f"Failed to get service '{service_name}': {e}")
        raise ServiceUnavailableError(
            f"Service '{service_name}' unavailable: {str(e)}",
            service=service_name
        ) from e


def create_child_profile_read_model(
    child_id: str, name: str, age: int, preferences: dict[str, Any]
) -> IChildProfileReadModel:
    """Create a child profile read model instance."""
    if not child_id or not name or age < 0:
        raise ValueError("Invalid child profile parameters")
    
    class ChildProfileReadModel(IChildProfileReadModel):
        """Concrete implementation of child profile read model."""
        
        def __init__(self, child_id: str, name: str, age: int, preferences: dict[str, Any]):
            self._id = child_id
            self._name = name
            self._age = age
            self._preferences = preferences or {}
        
        @property
        def id(self) -> str:
            return self._id
        
        @property
        def name(self) -> str:
            return self._name
        
        @property
        def age(self) -> int:
            return self._age
        
        @property
        def preferences(self) -> dict[str, Any]:
            return self._preferences.copy()
    
    return ChildProfileReadModel(child_id, name, age, preferences)


def get_read_model_store() -> IChildProfileReadModelStore:
    """Get the child profile read model store service."""
    return _safe_get_service('ChildRepository')


def get_event_bus():
    """Get the event bus service."""
    return _safe_get_service('EventBusService')


def get_conversation_service():
    """Get the conversation service."""
    return _safe_get_service('ConversationService')


def get_child_service():
    """Get the child service."""
    return _safe_get_service('ChildService')


def get_safety_service():
    """Get the safety service."""
    return _safe_get_service('SafetyService')


def get_auth_service():
    """Get the authentication service."""
    return _safe_get_service('AuthService')


def get_database_service():
    """Get the database service."""
    return _safe_get_service('DatabaseService')


def get_cache_service():
    """Get the cache service."""
    return _safe_get_service('CacheService')


def get_notification_service():
    """Get the notification service."""
    return _safe_get_service('NotificationService')


def get_external_api_client(service_name: str) -> IExternalAPIClient:
    """Get an external API client service."""
    service_mapping = {
        "openai": "AIAPIAdapter",
        "anthropic": "AnthropicAPIAdapter", 
        "google": "GoogleAPIAdapter",
        "default": "ExternalAPIAdapter"
    }
    
    adapter_name = service_mapping.get(service_name, service_mapping["default"])
    return _safe_get_service(adapter_name)


def get_settings_provider():
    """Get the settings provider service."""
    return _safe_get_service('ConfigurationService')


def create_service_factory(service_name: str):
    """Create a factory function for any service."""
    def factory():
        return _safe_get_service(service_name)
    factory.__name__ = f"get_{service_name.lower()}"
    factory.__doc__ = f"Get the {service_name} service."
    return factory


def get_all_services() -> Dict[str, Any]:
    """Get all available services from container."""
    try:
        injector = get_injector()
        services = {}
        
        # Common service names
        service_names = [
            'ChildRepository', 'EventBusService', 'ConversationService',
            'ChildService', 'SafetyService', 'AuthService', 'DatabaseService',
            'CacheService', 'NotificationService', 'ConfigurationService',
            'AIAPIAdapter', 'ExternalAPIAdapter'
        ]
        
        for name in service_names:
            try:
                services[name] = injector.get(name)
            except (KeyError, Exception):
                logger.debug(f"Service '{name}' not available")
                
        return services
    except Exception as e:
        logger.error(f"Failed to get all services: {e}")
        raise ServiceUnavailableError("Container services unavailable") from e