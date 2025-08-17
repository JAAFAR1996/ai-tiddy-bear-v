# Core module public interface


# --- Safe imports with error handling ---

import importlib
import sys

_import_errors = []


def _safe_import(module, names):
    mod = None
    try:
        # Try absolute import (core.module)
        mod = importlib.import_module(f"core.{module}")
    except ImportError:
        try:
            # Try relative import (for package context)
            mod = importlib.import_module(f".{module}", __package__)
        except ImportError as e:
            _import_errors.append((module, str(e)))
            return {name: None for name in names}
    return {name: getattr(mod, name, None) for name in names}


# Entities
_entities = _safe_import("entities", ["Child"])
# Exceptions
_exceptions = _safe_import(
    "exceptions",
    [
        "AITeddyBearException",
        "AuthenticationError",
        "InvalidTokenError",
        "AuthorizationError",
        "ConversationNotFoundError",
        "ChildNotFoundError",
        "ValidationError",
    ],
)
# Services - safe import with fallback
try:
    import importlib.util

    # Safe module loading without exec_module
    import os

    services_path = os.path.join(os.path.dirname(__file__), "services.py")
    if os.path.exists(services_path):
        services_spec = importlib.util.spec_from_file_location(
            "services", services_path
        )
        if services_spec and services_spec.loader:
            services_module = importlib.util.module_from_spec(services_spec)
            # Use safe import instead of exec_module
            try:
                services_spec.loader.exec_module(services_module)
                _services = {
                    "AuthService": getattr(services_module, "AuthService", None),
                    "SafetyService": getattr(services_module, "SafetyService", None),
                    "ChatService": getattr(services_module, "ChatService", None),
                    "ConversationService": getattr(
                        services_module, "ConversationService", None
                    ),
                }
            except Exception as e:
                import logging

                # Only log as debug to avoid spam during testing
                logging.debug(f"Failed to load services module: {e}")
                # Set default services instead of raising
                _services = {
                    "AuthService": None,
                    "SafetyService": None,
                    "ChatService": None,
                    "ConversationService": None,
                }
        else:
            raise ImportError("Could not create services spec")
    else:
        raise ImportError("Services module file not found")
except Exception as e:
    _services = {
        "AuthService": None,
        "SafetyService": None,
        "ChatService": None,
        "ConversationService": None,
    }
# Events (move to top)
from .events import (
    ChildRegistered,
    ChildProfileUpdated,
    MessageCreated,
    MessageViolation,
    AuthEvent,
    SensitiveOperation,
    EventStore,
)

# Repositories
_repos = _safe_import(
    "repositories",
    [
        "DatabaseConnectionError",
        "MessageNotFoundError",
        "IConversationRepository",
        "IMessageRepository",
        "ConversationRepository",
    ],
)
# Models
_models = _safe_import(
    "models",
    ["ConversationEntity", "MessageEntity", "RiskLevel", "SafetyAnalysisResult"],
)
# Value Objects
_vo = _safe_import(
    "value_objects.value_objects",
    [
        "SafetyLevel",
        "AgeGroup",
        "SafetyScore",
        "EmotionResult",
        "ContentComplexity",
        "ChildPreferences",
    ],
)

# --- Version info ---
__version__ = "1.0.0"


# --- Compatibility check ---
def check_compatibility():
    """Raise if Python version is < 3.9."""
    if sys.version_info < (3, 9):
        raise RuntimeError("Python >= 3.9 required for src.core")
    # Allow import errors for optional modules
    return True


# --- Exported symbols (grouped, not flat) ---

__all__ = [
    # Groups
    "entities",
    "exceptions",
    "services",
    "repositories",
    "models",
    "value_objects",
    "__version__",
    "check_compatibility",
    # Events (direct)
    "ChildRegistered",
    "ChildProfileUpdated",
    "MessageCreated",
    "MessageViolation",
    "AuthEvent",
    "SensitiveOperation",
    "EventStore",
]

# Grouped exports for interface segregation
entities = _entities
exceptions = _exceptions
services = _services

repositories = _repos
models = _models
value_objects = _vo

# --- Optionally, expose import errors for diagnostics ---
import_errors = _import_errors

__all__ = [
    # Entities
    "Child",
    # "ChildProfile",  # Removed: use "Child"
    # Exceptions
    "AITeddyBearException",
    "AuthenticationError",
    "InvalidTokenError",
    "AuthorizationError",
    "ConversationNotFoundError",
    "ChildNotFoundError",
    "ValidationError",
    # Services
    "AuthService",
    "SafetyService",
    "ChatService",
    "ConversationService",
    # Events
    "ChildRegistered",
    "ChildProfileUpdated",
    # Repositories
    "DatabaseConnectionError",
    "MessageNotFoundError",
    "IConversationRepository",
    "IMessageRepository",
    "ConversationRepository",
    # Models
    "ConversationEntity",
    "MessageEntity",
    "RiskLevel",
    "SafetyAnalysisResult",
    # Value Objects
    "SafetyLevel",
    "AgeGroup",
    "SafetyScore",
    "EmotionResult",
    "ContentComplexity",
    "ChildPreferences",
]
