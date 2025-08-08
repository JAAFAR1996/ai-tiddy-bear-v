"""
🧸 AI TEDDY BEAR V5 - CONFIGURATION PROVIDER
===========================================
Lightweight configuration provider to avoid circular imports.
This module should ONLY contain the get_config function and minimal dependencies.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

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


__all__ = ["get_config", "reload_config"]
