"""
🧸 AI TEDDY BEAR V5 - CONFIGURATION PROVIDER
===========================================
Lightweight configuration provider to avoid circular imports.
This module should ONLY contain the get_config function and minimal dependencies.
"""

from functools import lru_cache
from typing import TYPE_CHECKING
from fastapi import Request, HTTPException

if TYPE_CHECKING:
    from .production_config import ProductionConfig

# Global configuration instance
_config_instance = None


@lru_cache(maxsize=1)
def get_config() -> "ProductionConfig":
    """
    Get the current configuration instance.

    This function is cached and separated from production_config.py
    to prevent circular import issues.
    """
    global _config_instance

    if _config_instance is None:
        # Import here to avoid circular imports
        from .production_config import _config_manager

        _config_instance = _config_manager.get_config()

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


__all__ = ["get_config", "reload_config", "get_config_from_state"]
