"""
Database Integration - FastAPI Integration and Example Usage
============================================================
Production database integration with FastAPI including:
- Database startup and shutdown lifecycle
- Health check endpoints
- Database dependency injection
- Error handling and middleware
- Performance monitoring integration
- Child safety middleware
- Transaction management
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Generator, AsyncGenerator
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from . import (
    initialize_database_infrastructure,
    shutdown_database_infrastructure,
    get_database_health,
    get_database_metrics,
    database_manager,
    transaction_manager,
    repository_manager,
)
from .health_checks import run_database_health_check, get_database_health_summary
from .models import User, Child, Conversation, Message
from .repository import get_child_repository, get_conversation_repository
from ..config import get_config_manager
from ..logging import get_logger, audit_logger, performance_logger, security_logger


logger = get_logger("database_integration")
config_manager = get_config_manager()


# Database lifespan manager
@asynccontextmanager
async def database_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Database lifespan manager for FastAPI application."""
    logger.info("Starting database infrastructure")

    try:
        # Initialize database infrastructure
        await initialize_database_infrastructure()
        logger.info("Database infrastructure started successfully")

        # Store database info in app state
        app.state.database_initialized = True
        app.state.database_start_time = datetime.now()

        yield

    except Exception as e:
        logger.error(f"Failed to start database infrastructure: {str(e)}")
        raise RuntimeError(f"Database initialization failed: {str(e)}")

    finally:
        logger.info("Shutting down database infrastructure")
        try:
            await shutdown_database_infrastructure()
            logger.info("Database infrastructure shutdown completed")
        except Exception as e:
            logger.error(f"Error during database shutdown: {str(e)}")


# Database middleware for request tracking and performance monitoring
class DatabaseMiddleware(BaseHTTPMiddleware):
    """Middleware for database request monitoring and child safety."""

    def __init__(self, app):
        super().__init__(app)
        self.enable_child_protection = config_manager.get_bool(
            "CHILD_DATA_PROTECTION", True
        )
        self.log_all_queries = config_manager.get_bool(
            "LOG_ALL_DATABASE_QUERIES", False
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with database monitoring."""
        start_time = time.time()
        request_id = getattr(request.state, "request_id", "unknown")

        # Child safety checks
        if self.enable_child_protection:
            await self._check_child_data_access(request)

        # Add database context to request
        request.state.database_start_time = start_time
        request.state.database_queries = []

        try:
            response = await call_next(request)

            # Log successful database operations
            duration = time.time() - start_time

            if (
                hasattr(request.state, "database_queries")
                and request.state.database_queries
            ):
                performance_logger.info(
                    "Database operation completed",
                    extra={
                        "request_id": request_id,
                        "path": str(request.url.path),
                        "method": request.method,
                        "duration_ms": duration * 1000,
                        "query_count": len(request.state.database_queries),
                        "queries": (
                            request.state.database_queries
                            if self.log_all_queries
                            else []
                        ),
                    },
                )

            return response

        except Exception as e:
            duration = time.time() - start_time

            # Log database errors
            logger.error(
                f"Database operation failed during request processing",
                extra={
                    "request_id": request_id,
                    "path": str(request.url.path),
                    "method": request.method,
                    "duration_ms": duration * 1000,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

            raise

    async def _check_child_data_access(self, request: Request):
        """Check if request involves child data access."""
        path = str(request.url.path)

        # Check for child-related endpoints
        child_endpoints = ["/children/", "/child/", "/conversations/", "/messages/"]

        if any(endpoint in path for endpoint in child_endpoints):
            # Log child data access attempt
            security_logger.info(
                "Child data endpoint accessed",
                extra={
                    "path": path,
                    "method": request.method,
                    "client_ip": request.client.host if request.client else "unknown",
                    "user_agent": request.headers.get("user-agent", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                },
            )


# Database dependency injection
async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    try:
        async with database_manager.primary_node.acquire_connection() as conn:
            # Create a session-like wrapper around the connection
            yield DatabaseSessionWrapper(conn)
    except Exception as e:
        logger.error(f"Failed to acquire database session: {str(e)}")
        raise HTTPException(status_code=503, detail="Database unavailable")


class DatabaseSessionWrapper:
    """Wrapper to make database connection work like a session."""

    def __init__(self, connection):
        self.connection = connection

    async def execute(self, query, *args):
        """Execute query on the connection."""
        return await self.connection.execute(query, *args)

    async def fetch(self, query, *args):
        """Fetch results from query."""
        return await self.connection.fetch(query, *args)

    async def fetchrow(self, query, *args):
        """Fetch single row from query."""
        return await self.connection.fetchrow(query, *args)

    async def fetchval(self, query, *args):
        """Fetch single value from query."""
        return await self.connection.fetchval(query, *args)


# Repository dependencies
async def get_user_repo():
    """Get user repository dependency."""
    # get_user_repository removed: not implemented or needed


async def get_child_repo():
    """Get child repository dependency."""
    return await get_child_repository()


async def get_conversation_repo():
    """Get conversation repository dependency."""
    return await get_conversation_repository()


# Database health endpoints
def add_database_health_endpoints(app: FastAPI):
    """Add database health check endpoints to FastAPI app."""

    @app.get("/health/database")
    async def database_health():
        """Get database health status."""
        try:
            health_status = await get_database_health()
            return health_status
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            raise HTTPException(status_code=503, detail="Database health check failed")

    @app.get("/health/database/detailed")
    async def database_health_detailed():
        """Get detailed database health check results."""
        try:
            health_results = await run_database_health_check()

            # Convert results to JSON-serializable format
            serialized_results = {}
            for check_name, result in health_results.items():
                serialized_results[check_name] = {
                    "status": result.status.value,
                    "message": result.message,
                    "details": result.details,
                    "duration_ms": result.duration_ms,
                    "timestamp": result.timestamp.isoformat(),
                    "recommendations": result.recommendations,
                }

            return {
                "timestamp": datetime.now().isoformat(),
                "checks": serialized_results,
            }

        except Exception as e:
            logger.error(f"Detailed database health check failed: {str(e)}")
            raise HTTPException(status_code=503, detail="Database health check failed")

    @app.get("/health/database/summary")
    async def database_health_summary():
        """Get database health summary."""
        try:
            return await get_database_health_summary()
        except Exception as e:
            logger.error(f"Database health summary failed: {str(e)}")
            raise HTTPException(
                status_code=503, detail="Database health summary failed"
            )

    @app.get("/metrics/database")
    async def database_metrics():
        """Get database performance metrics."""
        try:
            return get_database_metrics()
        except Exception as e:
            logger.error(f"Database metrics collection failed: {str(e)}")
            raise HTTPException(status_code=503, detail="Database metrics unavailable")


# Example database endpoints


# Database initialization function for FastAPI
def setup_database_integration(app: FastAPI):
    """Setup complete database integration for FastAPI application."""

    # Add database middleware
    app.add_middleware(DatabaseMiddleware)

    # Add health check endpoints
    add_database_health_endpoints(app)

    # Production: No example endpoints

    # Add database lifespan events
    @app.on_event("startup")
    async def startup_database():
        """Initialize database on application startup."""
        logger.info("FastAPI database integration startup")
        # Database initialization is handled by lifespan manager

    @app.on_event("shutdown")
    async def shutdown_database():
        """Shutdown database on application shutdown."""
        logger.info("FastAPI database integration shutdown")
        # Database shutdown is handled by lifespan manager

    logger.info("Database integration setup completed")


# Example usage and best practices
class DatabaseUsageExamples:
    """Examples of proper database usage patterns."""

    @staticmethod
    async def example_user_operations():
        """Example user CRUD operations."""
        # Removed unused import UserRepository
        from .repository import create_user_repository

        # Use the async factory pattern for repository instantiation
        user_repo = create_user_repository(
            config_manager,
            database_manager=database_manager,
            transaction_manager=transaction_manager,
            cache_manager=None,
        )
        # Create user
        user_data = {
            "username": "example_user",
            "email": "user@example.com",
            "role": "parent",
        }
        user = await user_repo.create(user_data)
        logger.info(f"Created user: {user.id}")
        # Get user
        retrieved_user = await user_repo.get_by_id(user.id)
        logger.info(f"Retrieved user: {retrieved_user.username}")
        # Update user
        update_data = {"display_name": "Example User"}
        updated_user = await user_repo.update(user.id, update_data)
        logger.info(f"Updated user: {updated_user.display_name}")
        # List users
        users, total = await user_repo.list(limit=10)
        logger.info(f"Found {total} users")

    @staticmethod
    async def example_child_safe_operations():
        """Example child-safe operations with COPPA compliance."""
        child_repo = await get_child_repository()

        # Create child with parental consent
        child_data = {
            "parent_id": "parent-uuid-here",
            "name": "Child Name",
            "estimated_age": 8,
            "parental_consent": True,
        }

        # Use child-safe transaction
        from .transaction_manager import child_safe_transactional

        @child_safe_transactional("child-id-here", parent_consent=True)
        async def create_child_safely(tx):
            child = await child_repo.create(child_data)

            # Log child data operation
            security_logger.info(
                "Child data operation",
                extra={
                    "operation": "create",
                    "child_hash": child.hashed_identifier,
                    "coppa_protected": child.is_coppa_protected(),
                },
            )

            return child

        child = await create_child_safely()
        logger.info(f"Created child safely: {child.id}")

    @staticmethod
    async def example_transaction_usage():
        """Example transaction patterns."""

        # Simple transaction
        async with transaction_manager.transaction() as tx:
            result = await tx.execute("SELECT COUNT(*) FROM users")
            logger.info(f"User count: {result}")

        # Child-safe transaction
        async with transaction_manager.transaction(
            transaction_type=transaction_manager.TransactionType.CHILD_SAFE,
            child_id="child-id-here",
            parent_consent=True,
        ) as tx:
            # Child data operations
            await tx.execute_child_operation(
                "create",
                "messages",
                {"content": "Hello", "child_id": "child-id-here"},
                "INSERT INTO messages (content, child_id) VALUES ($1, $2)",
                "Hello",
                "child-id-here",
            )

        # Saga transaction for complex operations
        async with transaction_manager.transaction(
            transaction_type=transaction_manager.TransactionType.SAGA
        ) as saga_tx:
            # Add saga steps
            saga_tx.add_step(
                "create_user",
                lambda: logger.info("Creating user"),
                lambda: logger.info("Compensating user creation"),
                "Create user step",
            )

            await saga_tx.execute_saga()

    @staticmethod
    async def example_health_monitoring():
        """Example health monitoring usage."""

        # Get overall database health
        health = await get_database_health()
        logger.info(f"Database health: {health['status']}")

        # Get detailed health check
        detailed_health = await run_database_health_check()

        for check_name, result in detailed_health.items():
            logger.info(
                f"Health check {check_name}: {result.status.value} - {result.message}"
            )

        # Get performance metrics
        metrics = get_database_metrics()
        logger.info(f"Database metrics: {metrics}")


# Export main integration function
__all__ = [
    "database_lifespan",
    "DatabaseMiddleware",
    "setup_database_integration",
    "get_database_session",
    "get_user_repo",
    "get_child_repo",
    "get_conversation_repo",
    "add_database_health_endpoints",
    "DatabaseUsageExamples",
]  # Production: No example endpoints - removed for security
