"""
🧸 AI TEDDY BEAR V5 - CONFIGURATION PROVIDER
===========================================
Lightweight configuration provider to avoid circular imports.
This module should ONLY contain the get_config function and minimal dependencies.
"""

from functools import lru_cache
from typing import TYPE_CHECKING, Optional
import weakref
from fastapi import Request, HTTPException

if TYPE_CHECKING:
    from .production_config import ProductionConfig

try:
    from fastapi import FastAPI  # type: ignore
except Exception:
    FastAPI = object  # typing only

# Global configuration instance
_config_instance = None
_app_ref: Optional[weakref.ReferenceType] = None


def set_app_ref(app: "FastAPI") -> None:
    """Store a weak ref to the app so legacy get_config() can read app.state.config at runtime."""
    global _app_ref
    _app_ref = weakref.ref(app)


def _try_state_config():
    """Try to get config from app.state if available."""
    if _app_ref:
        app = _app_ref()
        if app is not None:
            return getattr(app.state, "config", None)
    return None


@lru_cache(maxsize=1)
def get_config() -> "ProductionConfig":
    """
    Get the current configuration instance.
    
    Compat: prefer app.state.config if available (runtime-safe)
    This prevents ConfigurationError during request processing.
    """
    # Try app.state.config first (runtime-safe)
    cfg = _try_state_config()
    if cfg is not None:
        return cfg
    
    # Fallback: manager (CLI/tools). If not loaded, return 503 (not 500).
    global _config_instance
    if _config_instance is None:
        try:
            # Import here to avoid circular imports
            from .production_config import _config_manager
            _config_instance = _config_manager.get_config()
        except Exception:
            # Return 503 instead of ConfigurationError to prevent 500
            raise HTTPException(status_code=503, detail="Configuration not loaded")

    return _config_instance


def reload_config() -> "ProductionConfig":
    """Reload configuration (clears cache and reloads)."""
    global _config_instance

    # Clear the cache
    get_config.cache_clear()
    _config_instance = None

    # Import and reload
    from .production_config import _config_manager

    _config_instance = _config_manager.load_config(force_reload=True)

    return _config_instance


def get_config_from_state(request: Request) -> "ProductionConfig":
    """
    Get configuration from FastAPI app state (production-grade dependency)
    
    Args:
        request: FastAPI Request object
        
    Returns:
        ProductionConfig: Configuration from app.state
        
    Raises:
        HTTPException: 503 if config not available in app.state
    """
    config = getattr(request.app.state, "config", None)
    if config is None:
        raise HTTPException(status_code=503, detail="Configuration not loaded")
    return config


__all__ = ["get_config", "reload_config", "get_config_from_state", "set_app_ref"]
