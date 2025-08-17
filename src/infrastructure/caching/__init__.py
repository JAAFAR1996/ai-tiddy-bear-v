"""
Cache management utilities for AI Teddy Bear application.
Provides centralized cache management with lazy initialization.
"""

from typing import Optional
from .production_redis_cache import ProductionRedisCache

# Global cache manager instance
_cache_manager: Optional[ProductionRedisCache] = None


def get_cache_manager() -> ProductionRedisCache:
    """
    Get the global cache manager instance with lazy initialization.

    Returns:
        ProductionRedisCache: The initialized cache manager
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = ProductionRedisCache()
    return _cache_manager


# Export the main classes and functions
__all__ = [
    "get_cache_manager",
    "ProductionRedisCache",
]
