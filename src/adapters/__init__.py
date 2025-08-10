"""
🧸 AI TEDDY BEAR V5 - ADAPTERS MODULE
===================================
Lightweight module exports - imports moved to prevent circular dependencies during startup.

To import components from this module, import them directly:
- from src.adapters.database_production import ProductionDatabaseAdapter
- from src.adapters.auth_routes import router as auth_router
- from src.adapters.web import router as web_router
"""

# Intentionally minimal to avoid circular imports during startup
__all__ = []
