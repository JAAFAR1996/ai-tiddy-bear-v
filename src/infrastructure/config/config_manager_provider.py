"""
🧸 AI TEDDY BEAR V5 - CONFIGURATION MANAGER PROVIDER
===================================================
Lightweight configuration manager provider to avoid circular imports.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .production_config import ConfigurationManager

_config_manager_instance = None


def get_config_manager() -> "ConfigurationManager":
    """
    Get the configuration manager instance.

    This function is separated to prevent circular import issues.
    """
    global _config_manager_instance

    if _config_manager_instance is None:
        # Import here to avoid circular imports
        from .production_config import ConfigurationManager

        _config_manager_instance = ConfigurationManager.get_instance()

    return _config_manager_instance


__all__ = ["get_config_manager"]
