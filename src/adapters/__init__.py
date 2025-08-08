"""
🧸 AI TEDDY BEAR V5 - ADAPTERS MODULE
===================================
Organized exports for all adapter interfaces and implementations.
"""

# Database Adapters
from .database_production import (
    ProductionDatabaseAdapter,
    ProductionUserRepository,
    ProductionChildRepository,
    ProductionConversationRepository,
    ProductionMessageRepository,
    ProductionEventRepository,
    get_database_adapter,
    initialize_production_database
)

# AI Provider
from .providers.openai_provider import (
    ProductionOpenAIProvider,
    OpenAIProvider,
    create_openai_provider,
    create_child_safe_provider
)

# Web & API
from .web import router as web_router
from .api_routes import router as api_router

# Dashboard Components
from .dashboard import (
    ParentDashboard,
    ChildMonitor,
    SafetyControls,
    UsageReports,
    NotificationCenter
)

__all__ = [
    # Database
    "ProductionDatabaseAdapter",
    "ProductionUserRepository", 
    "ProductionChildRepository",
    "ProductionConversationRepository",
    "ProductionMessageRepository",
    "ProductionEventRepository",
    "get_database_adapter",
    "initialize_production_database",
    
    # AI Provider
    "ProductionOpenAIProvider",
    "OpenAIProvider",
    "create_openai_provider",
    "create_child_safe_provider",
    
    # Web & API
    "web_router",
    "api_router",
    
    # Dashboard
    "ParentDashboard",
    "ChildMonitor", 
    "SafetyControls",
    "UsageReports",
    "NotificationCenter"
]
