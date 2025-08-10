"""
Database Interface - Abstract Layer
No dependencies on implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager


class IDatabaseManager(ABC):
    """Abstract database manager interface."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize database manager."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close database connections."""
        pass
    
    @abstractmethod
    @asynccontextmanager
    async def get_session(self):
        """Get database session."""
        pass
    
    @abstractmethod
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> Any:
        """Execute database query."""
        pass


class IMetricsCollector(ABC):
    """Abstract metrics collector interface."""
    
    @abstractmethod
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Record a metric."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        pass
