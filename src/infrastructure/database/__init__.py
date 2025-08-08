"""
Database Infrastructure - Production-Ready Database Module
=========================================================
Enterprise database infrastructure with:
- Advanced connection pooling and failover
- Transaction management with ACID compliance
- COPPA-compliant models and repositories
- Database migrations and versioning
- Health monitoring and performance metrics
- Child safety and data protection features
"""

from .database_manager import (
    database_manager,
    initialize_database,
    close_database,
    get_connection,
    execute_query,
    fetch_one,
    fetch_all,
    execute_command,
    DatabaseConnectionState,
    DatabaseRole,
)

from .transaction_manager import (
    TransactionManager,
    get_transaction_manager,
    create_transaction_manager,
    TransactionType,
    IsolationLevel,
    TransactionConfig,
)

from .models import (
    Base,
    BaseModel,
    User,
    Child,
    Conversation,
    Message,
    SafetyReport,
    AuditLog,
    UserRole,
    SafetyLevel,
    ConversationStatus,
    ContentType,
    DataRetentionStatus,
    create_audit_log,
    get_child_by_hash,
    schedule_child_data_cleanup,
)

from .repository import (
    BaseRepository,
    UserRepository,
    ChildRepository,
    ConversationRepository,
    RepositoryError,
    ValidationError,
    PermissionError,
    NotFoundError,
)

from .migrations import (
    get_migration_manager,
    initialize_database as run_migrations,
    migrate_database,
    rollback_database,
    validate_database,
    get_database_status,
    MigrationStatus,
    MigrationType,
    MigrationRecord,
)

# Version information
__version__ = "1.0.0"
__author__ = "AI Teddy Bear Development Team"

# Export all components
__all__ = [
    # Database Manager
    "database_manager",
    "initialize_database",
    "close_database",
    "get_connection",
    "execute_query",
    "fetch_one",
    "fetch_all",
    "execute_command",
    "DatabaseConnectionState",
    "DatabaseRole",
    # Transaction Manager
    "TransactionType",
    "IsolationLevel",
    "TransactionConfig",
    # Models
    "Base",
    "BaseModel",
    "User",
    "Child",
    "Conversation",
    "Message",
    "SafetyReport",
    "AuditLog",
    "UserRole",
    "SafetyLevel",
    "ConversationStatus",
    "ContentType",
    "DataRetentionStatus",
    "create_audit_log",
    "get_child_by_hash",
    "schedule_child_data_cleanup",
    # Repository
    "repository_manager",
    "BaseRepository",
    "UserRepository",
    "ChildRepository",
    "ConversationRepository",
    "RepositoryError",
    "ValidationError",
    "PermissionError",
    "NotFoundError",
    # Migrations
    "migration_manager",
    "run_migrations",
    "migrate_database",
    "rollback_database",
    "validate_database",
    "get_database_status",
    "MigrationStatus",
    "MigrationType",
    "MigrationRecord",
]


# Module initialization
async def initialize_database_infrastructure():
    """Initialize complete database infrastructure."""
    from ..logging import get_logger

    logger = get_logger("database_init")
    logger.info("Initializing database infrastructure")

    try:

        # Initialize database connections
        await initialize_database()
        logger.info("Database manager initialized")

        # Run migrations
        migration_success = await run_migrations()
        if migration_success:
            logger.info("Database migrations completed successfully")
        else:
            logger.error("Database migrations failed")
            raise RuntimeError("Database migration failure")

        logger.info("Database infrastructure initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize database infrastructure: {str(e)}")
        raise


async def shutdown_database_infrastructure():
    """Shutdown database infrastructure gracefully."""
    from ..logging import get_logger

    logger = get_logger("database_shutdown")
    logger.info("Shutting down database infrastructure")

    try:

        # Close database connections
        await close_database()
        logger.info("Database manager closed")

        logger.info("Database infrastructure shutdown completed")

    except Exception as e:
        logger.error(f"Error during database shutdown: {str(e)}")
        raise


def get_database_health():
    """Get database health status."""
    return database_manager.get_health_status()


def get_database_metrics():
    """Get database performance metrics."""
    return {
        "database_metrics": database_manager.get_all_metrics(),
        # "transaction_metrics": ...  # Transaction metrics DI only, not global
    }
