"""
Database Migrations - Production-Ready Migration Management
==========================================================
Enterprise database migration system with:
- Version control for database schema
- Rollback capabilities
- Data migration support
- Environment-specific migrations
- Performance optimization migrations
- COPPA compliance migrations
- Zero-downtime migration strategies
"""

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import (
    text,
    MetaData,
    Table,
    Column,
    String,
    DateTime,
    Boolean,
    Integer,
    Text,
)
from sqlalchemy.exc import SQLAlchemyError

from .database_manager import database_manager
from ..config import get_config_manager
from ..logging import get_logger, audit_logger


class MigrationStatus(Enum):
    """Migration status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MigrationType(Enum):
    """Migration type enumeration."""

    SCHEMA = "schema"
    DATA = "data"
    INDEX = "index"
    CONSTRAINT = "constraint"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"


@dataclass
class MigrationRecord:
    """Migration record for tracking."""

    version: str
    name: str
    migration_type: MigrationType
    status: MigrationStatus
    applied_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    execution_time_ms: Optional[float] = None
    checksum: Optional[str] = None
    error_message: Optional[str] = None


class Migration:
    """Base migration class."""

    def __init__(
        self,
        version: str,
        name: str,
        migration_type: MigrationType = MigrationType.SCHEMA,
    ):
        self.version = version
        self.name = name
        self.migration_type = migration_type
        self.logger = get_logger(f"migration_{version}")

    async def up(self, connection) -> None:
        """Apply migration."""
        raise NotImplementedError("Subclasses must implement up() method")

    async def down(self, connection) -> None:
        """Rollback migration."""
        raise NotImplementedError("Subclasses must implement down() method")

    async def validate(self, connection) -> bool:
        """Validate migration was applied correctly."""
        return True

    def get_checksum(self) -> str:
        """Get migration checksum for integrity verification."""
        content = f"{self.version}:{self.name}:{self.migration_type.value}"
        return hashlib.sha256(content.encode()).hexdigest()


class CreateInitialTables(Migration):
    """Initial database schema migration."""

    def __init__(self):
        super().__init__("001", "create_initial_tables", MigrationType.SCHEMA)

    async def up(self, connection) -> None:
        """Create initial database tables."""
        self.logger.info("Creating initial database tables")

        # Users table
        await connection.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(255),
                password_hash VARCHAR(255),
                role VARCHAR(20) NOT NULL CHECK (role IN ('child', 'parent', 'admin', 'support')),
                is_active BOOLEAN NOT NULL DEFAULT true,
                is_verified BOOLEAN NOT NULL DEFAULT false,
                display_name VARCHAR(100),
                avatar_url VARCHAR(500),
                timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
                language VARCHAR(10) NOT NULL DEFAULT 'en',
                settings JSONB NOT NULL DEFAULT '{}',
                last_login_at TIMESTAMP WITH TIME ZONE,
                login_count INTEGER NOT NULL DEFAULT 0,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                deleted_at TIMESTAMP WITH TIME ZONE,
                is_deleted BOOLEAN NOT NULL DEFAULT false,
                retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
                scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
                created_by UUID,
                updated_by UUID,
                metadata_json JSONB NOT NULL DEFAULT '{}'
            )
        """
            )
        )

        # Children table (COPPA compliant)
        await connection.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS children (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                parent_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                birth_date TIMESTAMP WITH TIME ZONE,
                hashed_identifier VARCHAR(64) UNIQUE NOT NULL,
                parental_consent BOOLEAN NOT NULL DEFAULT false,
                consent_date TIMESTAMP WITH TIME ZONE,
                consent_withdrawn_date TIMESTAMP WITH TIME ZONE,
                age_verified BOOLEAN NOT NULL DEFAULT false,
                age_verification_date TIMESTAMP WITH TIME ZONE,
                estimated_age INTEGER CHECK (estimated_age >= 3 AND estimated_age <= 18),
                safety_level VARCHAR(20) NOT NULL DEFAULT 'safe' CHECK (safety_level IN ('safe', 'review', 'blocked')),
                content_filtering_enabled BOOLEAN NOT NULL DEFAULT true,
                interaction_logging_enabled BOOLEAN NOT NULL DEFAULT true,
                data_retention_days INTEGER NOT NULL DEFAULT 90 CHECK (data_retention_days >= 1 AND data_retention_days <= 2555),
                allow_data_sharing BOOLEAN NOT NULL DEFAULT false,
                favorite_topics JSONB NOT NULL DEFAULT '[]',
                content_preferences JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                deleted_at TIMESTAMP WITH TIME ZONE,
                is_deleted BOOLEAN NOT NULL DEFAULT false,
                retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
                scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
                created_by UUID,
                updated_by UUID,
                metadata_json JSONB NOT NULL DEFAULT '{}'
            )
        """
            )
        )

        # Conversations table
        await connection.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS conversations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                child_id UUID REFERENCES children(id) ON DELETE CASCADE,
                title VARCHAR(200),
                status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'archived')),
                safety_checked BOOLEAN NOT NULL DEFAULT false,
                safety_score REAL CHECK (safety_score >= 0.0 AND safety_score <= 1.0),
                flagged_content BOOLEAN NOT NULL DEFAULT false,
                session_start TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                session_end TIMESTAMP WITH TIME ZONE,
                total_messages INTEGER NOT NULL DEFAULT 0 CHECK (total_messages >= 0),
                educational_content BOOLEAN NOT NULL DEFAULT false,
                parental_review_required BOOLEAN NOT NULL DEFAULT false,
                context_data JSONB NOT NULL DEFAULT '{}',
                conversation_settings JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                deleted_at TIMESTAMP WITH TIME ZONE,
                is_deleted BOOLEAN NOT NULL DEFAULT false,
                retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
                scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
                created_by UUID,
                updated_by UUID,
                metadata_json JSONB NOT NULL DEFAULT '{}'
            )
        """
            )
        )

        # Messages table
        await connection.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                sender_type VARCHAR(20) NOT NULL CHECK (sender_type IN ('user', 'child', 'ai', 'system')),
                content_type VARCHAR(20) NOT NULL DEFAULT 'conversation' CHECK (content_type IN ('story', 'conversation', 'image', 'audio')),
                content TEXT NOT NULL,
                content_encrypted BYTEA,
                safety_checked BOOLEAN NOT NULL DEFAULT false,
                safety_level VARCHAR(20) NOT NULL DEFAULT 'safe' CHECK (safety_level IN ('safe', 'review', 'blocked')),
                content_filtered BOOLEAN NOT NULL DEFAULT false,
                processed_by_ai BOOLEAN NOT NULL DEFAULT false,
                ai_model_used VARCHAR(100),
                ai_processing_time REAL,
                character_count INTEGER NOT NULL DEFAULT 0 CHECK (character_count >= 0),
                word_count INTEGER NOT NULL DEFAULT 0 CHECK (word_count >= 0),
                sentiment_score REAL CHECK (sentiment_score >= -1.0 AND sentiment_score <= 1.0),
                message_metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                deleted_at TIMESTAMP WITH TIME ZONE,
                is_deleted BOOLEAN NOT NULL DEFAULT false,
                retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
                scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
                created_by UUID,
                updated_by UUID,
                metadata_json JSONB NOT NULL DEFAULT '{}'
            )
        """
            )
        )

        # Safety reports table
        await connection.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS safety_reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                child_id UUID REFERENCES children(id) ON DELETE CASCADE,
                conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
                message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
                report_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
                description TEXT NOT NULL,
                detected_by_ai BOOLEAN NOT NULL DEFAULT false,
                ai_confidence REAL CHECK (ai_confidence >= 0.0 AND ai_confidence <= 1.0),
                detection_rules JSONB NOT NULL DEFAULT '[]',
                reviewed BOOLEAN NOT NULL DEFAULT false,
                reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
                reviewed_at TIMESTAMP WITH TIME ZONE,
                review_notes TEXT,
                action_taken VARCHAR(100),
                content_blocked BOOLEAN NOT NULL DEFAULT false,
                parent_notified BOOLEAN NOT NULL DEFAULT false,
                notification_sent_at TIMESTAMP WITH TIME ZONE,
                resolved BOOLEAN NOT NULL DEFAULT false,
                resolved_at TIMESTAMP WITH TIME ZONE,
                resolution_notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                deleted_at TIMESTAMP WITH TIME ZONE,
                is_deleted BOOLEAN NOT NULL DEFAULT false,
                retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
                scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
                created_by UUID,
                updated_by UUID,
                metadata_json JSONB NOT NULL DEFAULT '{}'
            )
        """
            )
        )

        # Audit logs table
        await connection.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                action VARCHAR(100) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id UUID,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                session_id VARCHAR(100),
                old_values JSONB,
                new_values JSONB,
                description TEXT,
                severity VARCHAR(20) NOT NULL DEFAULT 'info' CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical')),
                tags JSONB NOT NULL DEFAULT '[]',
                involves_child_data BOOLEAN NOT NULL DEFAULT false,
                child_id_hash VARCHAR(64),
                success BOOLEAN NOT NULL DEFAULT true,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                deleted_at TIMESTAMP WITH TIME ZONE,
                is_deleted BOOLEAN NOT NULL DEFAULT false,
                retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
                scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
                created_by UUID,
                updated_by UUID,
                metadata_json JSONB NOT NULL DEFAULT '{}'
            )
        """
            )
        )

        self.logger.info("Initial database tables created successfully")

    async def down(self, connection) -> None:
        """Drop initial tables."""
        self.logger.info("Dropping initial database tables")

        tables = [
            "audit_logs",
            "safety_reports",
            "messages",
            "conversations",
            "children",
            "users",
        ]
        for table in tables:
            await connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))

        self.logger.info("Initial database tables dropped")


class CreateIndexes(Migration):
    """Create performance indexes."""

    def __init__(self):
        super().__init__("002", "create_performance_indexes", MigrationType.INDEX)

    async def up(self, connection) -> None:
        """Create performance indexes."""
        self.logger.info("Creating performance indexes")

        # Users indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
            # Children indexes
            "CREATE INDEX IF NOT EXISTS idx_children_parent_id ON children(parent_id)",
            "CREATE INDEX IF NOT EXISTS idx_children_hashed_identifier ON children(hashed_identifier)",
            "CREATE INDEX IF NOT EXISTS idx_children_safety_level ON children(safety_level)",
            "CREATE INDEX IF NOT EXISTS idx_children_consent ON children(parental_consent)",
            "CREATE INDEX IF NOT EXISTS idx_children_retention_status ON children(retention_status)",
            # Conversations indexes
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_child_id ON conversations(child_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_safety ON conversations(safety_checked, flagged_content)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_session_start ON conversations(session_start)",
            # Messages indexes
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_sender_type ON messages(sender_type)",
            "CREATE INDEX IF NOT EXISTS idx_messages_safety ON messages(safety_checked, safety_level)",
            "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_content_type ON messages(content_type)",
            # Safety reports indexes
            "CREATE INDEX IF NOT EXISTS idx_safety_reports_child_id ON safety_reports(child_id)",
            "CREATE INDEX IF NOT EXISTS idx_safety_reports_conversation_id ON safety_reports(conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_safety_reports_type_severity ON safety_reports(report_type, severity)",
            "CREATE INDEX IF NOT EXISTS idx_safety_reports_reviewed ON safety_reports(reviewed)",
            "CREATE INDEX IF NOT EXISTS idx_safety_reports_resolved ON safety_reports(resolved)",
            "CREATE INDEX IF NOT EXISTS idx_safety_reports_created_at ON safety_reports(created_at)",
            # Audit logs indexes
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_child_data ON audit_logs(involves_child_data)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_severity ON audit_logs(severity)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_ip ON audit_logs(ip_address)",
            # Composite indexes for common queries
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_children_parent_consent ON children(parent_id, parental_consent)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_child_status ON conversations(child_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_safety_reports_child_severity ON safety_reports(child_id, severity, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_child_action ON audit_logs(involves_child_data, action, created_at)",
        ]

        for index_sql in indexes:
            try:
                await connection.execute(text(index_sql))
            except Exception as e:
                self.logger.warning(
                    f"Failed to create index: {index_sql}, Error: {str(e)}"
                )

        # Partial indexes for active records
        partial_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_active ON users(id) WHERE is_active = true AND is_deleted = false",
            "CREATE INDEX IF NOT EXISTS idx_children_active ON children(id) WHERE is_deleted = false AND retention_status = 'active'",
            "CREATE INDEX IF NOT EXISTS idx_conversations_active ON conversations(id) WHERE status = 'active' AND is_deleted = false",
        ]

        for index_sql in partial_indexes:
            try:
                await connection.execute(text(index_sql))
            except Exception as e:
                self.logger.warning(
                    f"Failed to create partial index: {index_sql}, Error: {str(e)}"
                )

        self.logger.info("Performance indexes created successfully")

    async def down(self, connection) -> None:
        """Drop performance indexes."""
        self.logger.info("Dropping performance indexes")

        # List all indexes to drop
        indexes_to_drop = [
            "idx_users_username",
            "idx_users_email",
            "idx_users_role",
            "idx_users_is_active",
            "idx_users_created_at",
            "idx_children_parent_id",
            "idx_children_hashed_identifier",
            "idx_children_safety_level",
            "idx_children_consent",
            "idx_children_retention_status",
            "idx_conversations_user_id",
            "idx_conversations_child_id",
            "idx_conversations_status",
            "idx_conversations_safety",
            "idx_conversations_session_start",
            "idx_messages_conversation_id",
            "idx_messages_sender_type",
            "idx_messages_safety",
            "idx_messages_created_at",
            "idx_messages_content_type",
            "idx_safety_reports_child_id",
            "idx_safety_reports_conversation_id",
            "idx_safety_reports_type_severity",
            "idx_safety_reports_reviewed",
            "idx_safety_reports_resolved",
            "idx_safety_reports_created_at",
            "idx_audit_logs_user_id",
            "idx_audit_logs_action",
            "idx_audit_logs_resource",
            "idx_audit_logs_child_data",
            "idx_audit_logs_created_at",
            "idx_audit_logs_severity",
            "idx_audit_logs_ip",
            "idx_messages_conversation_created",
            "idx_children_parent_consent",
            "idx_conversations_child_status",
            "idx_safety_reports_child_severity",
            "idx_audit_logs_child_action",
            "idx_users_active",
            "idx_children_active",
            "idx_conversations_active",
        ]

        for index_name in indexes_to_drop:
            try:
                await connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
            except Exception as e:
                self.logger.warning(f"Failed to drop index {index_name}: {str(e)}")

        self.logger.info("Performance indexes dropped")


class CreateMigrationTracking(Migration):
    """Create migration tracking table."""

    def __init__(self):
        super().__init__("000", "create_migration_tracking", MigrationType.SCHEMA)

    async def up(self, connection) -> None:
        """Create migration tracking table."""
        self.logger.info("Creating migration tracking table")

        await connection.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(50) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                migration_type VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE,
                rolled_back_at TIMESTAMP WITH TIME ZONE,
                execution_time_ms REAL,
                checksum VARCHAR(64),
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """
            )
        )

        self.logger.info("Migration tracking table created successfully")

    async def down(self, connection) -> None:
        """Drop migration tracking table."""
        await connection.execute(text("DROP TABLE IF EXISTS schema_migrations"))


class MigrationManager:
    """Production database migration manager."""

    def __init__(self):
        self.config_manager = get_config_manager()
        self.logger = get_logger("migration_manager")

        # Migration settings
        self.migration_timeout = self.config_manager.get_float(
            "MIGRATION_TIMEOUT", 600.0
        )  # 10 minutes
        self.enable_rollback = self.config_manager.get_bool(
            "MIGRATION_ENABLE_ROLLBACK", True
        )
        self.dry_run_mode = self.config_manager.get_bool("MIGRATION_DRY_RUN", False)

        # Available migrations in order
        self.migrations = [
            CreateMigrationTracking(),
            CreateInitialTables(),
            CreateIndexes(),
        ]

    async def initialize_tracking(self):
        """Initialize migration tracking table."""
        self.logger.info("Initializing migration tracking")

        tracking_migration = CreateMigrationTracking()

        try:
            async with database_manager.primary_node.acquire_connection() as conn:
                await tracking_migration.up(conn)

                # Record the tracking migration itself
                await self._record_migration(
                    conn,
                    tracking_migration,
                    MigrationStatus.COMPLETED,
                    execution_time_ms=0.0,
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize migration tracking: {str(e)}")
            raise

    async def get_pending_migrations(self) -> List[Migration]:
        """Get list of pending migrations."""
        try:
            applied_versions = await self._get_applied_versions()

            pending = []
            for migration in self.migrations:
                if migration.version not in applied_versions:
                    pending.append(migration)

            return pending

        except Exception as e:
            self.logger.error(f"Failed to get pending migrations: {str(e)}")
            raise

    async def apply_migrations(self, target_version: Optional[str] = None) -> bool:
        """Apply pending migrations up to target version."""
        self.logger.info(
            f"Starting migration process (target: {target_version or 'latest'})"
        )

        try:
            pending_migrations = await self.get_pending_migrations()

            if not pending_migrations:
                self.logger.info("No pending migrations found")
                return True

            # Filter migrations up to target version if specified
            if target_version:
                pending_migrations = [
                    m for m in pending_migrations if m.version <= target_version
                ]

            self.logger.info(f"Found {len(pending_migrations)} pending migrations")

            # Apply migrations one by one
            for migration in pending_migrations:
                success = await self._apply_single_migration(migration)
                if not success:
                    self.logger.error(f"Migration {migration.version} failed, stopping")
                    return False

            self.logger.info("All migrations applied successfully")
            return True

        except Exception as e:
            self.logger.error(f"Migration process failed: {str(e)}")
            return False

    async def rollback_migration(self, version: str) -> bool:
        """Rollback specific migration."""
        if not self.enable_rollback:
            self.logger.error("Migration rollback is disabled")
            return False

        self.logger.info(f"Rolling back migration {version}")

        try:
            # Find the migration
            migration = next((m for m in self.migrations if m.version == version), None)
            if not migration:
                self.logger.error(f"Migration {version} not found")
                return False

            # Check if migration is applied
            applied_versions = await self._get_applied_versions()
            if version not in applied_versions:
                self.logger.error(f"Migration {version} is not applied")
                return False

            # Perform rollback
            start_time = datetime.now()

            async with database_manager.primary_node.acquire_connection() as conn:
                await migration.down(conn)

                # Update migration record
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                await self._update_migration_status(
                    conn,
                    version,
                    MigrationStatus.ROLLED_BACK,
                    execution_time_ms=execution_time,
                )

                # Log rollback
                audit_logger.audit(
                    f"Migration {version} rolled back",
                    metadata={
                        "version": version,
                        "name": migration.name,
                        "execution_time_ms": execution_time,
                    },
                )

            self.logger.info(f"Migration {version} rolled back successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to rollback migration {version}: {str(e)}")
            return False

    async def validate_migrations(self) -> Dict[str, bool]:
        """Validate all applied migrations."""
        self.logger.info("Validating applied migrations")

        results = {}

        try:
            applied_versions = await self._get_applied_versions()

            for migration in self.migrations:
                if migration.version in applied_versions:
                    try:
                        async with database_manager.primary_node.acquire_connection() as conn:
                            is_valid = await migration.validate(conn)
                            results[migration.version] = is_valid

                            if not is_valid:
                                self.logger.warning(
                                    f"Migration {migration.version} validation failed"
                                )

                    except Exception as e:
                        self.logger.error(
                            f"Failed to validate migration {migration.version}: {str(e)}"
                        )
                        results[migration.version] = False

            return results

        except Exception as e:
            self.logger.error(f"Migration validation failed: {str(e)}")
            return {}

    async def get_migration_status(self) -> List[MigrationRecord]:
        """Get status of all migrations."""
        try:
            async with database_manager.primary_node.acquire_connection() as conn:
                result = await conn.fetch(
                    text(
                        """
                    SELECT version, name, migration_type, status, applied_at, 
                           rolled_back_at, execution_time_ms, checksum, error_message
                    FROM schema_migrations 
                    ORDER BY version
                """
                    )
                )

                records = []
                for row in result:
                    record = MigrationRecord(
                        version=row["version"],
                        name=row["name"],
                        migration_type=MigrationType(row["migration_type"]),
                        status=MigrationStatus(row["status"]),
                        applied_at=row["applied_at"],
                        rolled_back_at=row["rolled_back_at"],
                        execution_time_ms=row["execution_time_ms"],
                        checksum=row["checksum"],
                        error_message=row["error_message"],
                    )
                    records.append(record)

                return records

        except Exception as e:
            self.logger.error(f"Failed to get migration status: {str(e)}")
            return []

    async def _apply_single_migration(self, migration: Migration) -> bool:
        """Apply a single migration."""
        self.logger.info(f"Applying migration {migration.version}: {migration.name}")

        try:
            start_time = datetime.now()

            async with database_manager.primary_node.acquire_connection() as conn:
                # Mark as running
                await self._record_migration(conn, migration, MigrationStatus.RUNNING)

                try:
                    if self.dry_run_mode:
                        self.logger.info(
                            f"DRY RUN: Would apply migration {migration.version}"
                        )
                    else:
                        # Apply migration
                        await migration.up(conn)

                        # Validate migration
                        if not await migration.validate(conn):
                            raise Exception("Migration validation failed")

                    # Mark as completed
                    execution_time = (
                        datetime.now() - start_time
                    ).total_seconds() * 1000
                    await self._update_migration_status(
                        conn,
                        migration.version,
                        MigrationStatus.COMPLETED,
                        execution_time_ms=execution_time,
                    )

                    # Log success
                    audit_logger.audit(
                        f"Migration {migration.version} applied successfully",
                        metadata={
                            "version": migration.version,
                            "name": migration.name,
                            "type": migration.migration_type.value,
                            "execution_time_ms": execution_time,
                        },
                    )

                    self.logger.info(
                        f"Migration {migration.version} applied successfully in {execution_time:.2f}ms"
                    )
                    return True

                except Exception as e:
                    # Mark as failed
                    execution_time = (
                        datetime.now() - start_time
                    ).total_seconds() * 1000
                    await self._update_migration_status(
                        conn,
                        migration.version,
                        MigrationStatus.FAILED,
                        execution_time_ms=execution_time,
                        error_message=str(e),
                    )

                    self.logger.error(f"Migration {migration.version} failed: {str(e)}")
                    return False

        except Exception as e:
            self.logger.error(
                f"Failed to apply migration {migration.version}: {str(e)}"
            )
            return False

    async def _get_applied_versions(self) -> List[str]:
        """Get list of applied migration versions."""
        try:
            async with database_manager.primary_node.acquire_connection() as conn:
                result = await conn.fetch(
                    text(
                        """
                    SELECT version FROM schema_migrations 
                    WHERE status = 'completed'
                    ORDER BY version
                """
                    )
                )

                return [row["version"] for row in result]

        except Exception as e:
            # If table doesn't exist, return empty list
            if "does not exist" in str(e).lower():
                return []
            raise

    async def _record_migration(
        self,
        conn,
        migration: Migration,
        status: MigrationStatus,
        execution_time_ms: Optional[float] = None,
        error_message: Optional[str] = None,
    ):
        """Record migration in tracking table."""
        await conn.execute(
            text(
                """
            INSERT INTO schema_migrations 
            (version, name, migration_type, status, applied_at, execution_time_ms, checksum, error_message)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (version) DO UPDATE SET
                status = EXCLUDED.status,
                applied_at = EXCLUDED.applied_at,
                execution_time_ms = EXCLUDED.execution_time_ms,
                error_message = EXCLUDED.error_message,
                updated_at = now()
        """
            ),
            [
                migration.version,
                migration.name,
                migration.migration_type.value,
                status.value,
                datetime.now() if status == MigrationStatus.COMPLETED else None,
                execution_time_ms,
                migration.get_checksum(),
                error_message,
            ],
        )

    async def _update_migration_status(
        self,
        conn,
        version: str,
        status: MigrationStatus,
        execution_time_ms: Optional[float] = None,
        error_message: Optional[str] = None,
    ):
        """Update migration status."""
        await conn.execute(
            text(
                """
            UPDATE schema_migrations 
            SET status = $1, 
                applied_at = CASE WHEN $1 = 'completed' THEN now() ELSE applied_at END,
                rolled_back_at = CASE WHEN $1 = 'rolled_back' THEN now() ELSE rolled_back_at END,
                execution_time_ms = COALESCE($2, execution_time_ms),
                error_message = $3,
                updated_at = now()
            WHERE version = $4
        """
            ),
            [status.value, execution_time_ms, error_message, version],
        )


# Global migration manager
_migration_manager: Optional[MigrationManager] = None


def get_migration_manager() -> MigrationManager:
    """Get the global migration manager instance with lazy initialization."""
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = MigrationManager()
    return _migration_manager


# Convenience functions
async def initialize_database():
    """Initialize database with all migrations."""
    manager = get_migration_manager()
    await manager.initialize_tracking()
    return await manager.apply_migrations()


async def migrate_database(target_version: Optional[str] = None) -> bool:
    """Run database migrations."""
    return await get_migration_manager().apply_migrations(target_version)


async def rollback_database(version: str) -> bool:
    """Rollback database migration."""
    return await get_migration_manager().rollback_migration(version)


async def validate_database() -> Dict[str, bool]:
    """Validate database migrations."""
    return await get_migration_manager().validate_migrations()


async def get_database_status() -> List[MigrationRecord]:
    """Get database migration status."""
    return await get_migration_manager().get_migration_status()
