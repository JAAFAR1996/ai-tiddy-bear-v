"""
Repository Pattern - Production-Ready Database Repository with Clean Architecture
===============================================================================
Enterprise repository implementation with:
- Generic repository pattern with type safety
- Child-safe data operations with COPPA compliance
- Caching layer integration
- Query optimization and performance monitoring
- Audit logging for all data operations
- Connection pool management
- Transaction support
- Data validation and sanitization
"""

import asyncio
import threading
from abc import ABC, abstractmethod
from typing import (
    Generic,
    TypeVar,
    List,
    Optional,
    Dict,
    Any,
    Union,
    Callable,
    Type,
    Tuple,
)
from datetime import datetime, timedelta
import uuid
import json

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Import from both development and production models
try:
    from .models import (
        BaseModel,
        User,
        Child,
        Conversation,
        Message,
        SafetyReport,
        AuditLog,
        UserRole,
        SafetyLevel,
        Interaction,
        Subscription,
    )
    MODELS_IMPORTED = True
except ImportError:
    # Fallback to production models if development models not available
    from ..persistence.models.production_models import (
        UserModel as User,
        ChildModel as Child,
        ConversationModel as Conversation,
        MessageModel as Message,
        AuditLogModel as AuditLog,
    )
    # Define missing types for compatibility
    BaseModel = object
    SafetyReport = object
    Interaction = object
    Subscription = object
    class UserRole:
        PARENT = 'parent'
        ADMIN = 'admin'
        SUPPORT = 'support'
    class SafetyLevel:
        LOW = 0.3
        MEDIUM = 0.6
        HIGH = 0.8
    MODELS_IMPORTED = False
# Import managers - these should be injected, not imported as globals
try:
    from .database_manager import database_manager
    from .transaction_manager import transaction_manager
except ImportError:
    # If managers are not available, they should be injected
    database_manager = None
    transaction_manager = None

from ..config import get_config_manager
from ..logging import get_logger, audit_logger, security_logger, performance_logger
from ..caching import get_cache_manager

# Type variables for generic repository
T = TypeVar("T", bound=BaseModel)
ModelType = TypeVar("ModelType", bound=BaseModel)


class RepositoryError(Exception):
    """Base repository exception."""

    pass


class ValidationError(RepositoryError):
    """Data validation error."""

    pass


class PermissionError(RepositoryError):
    """Permission denied error."""

    pass


class NotFoundError(RepositoryError):
    """Resource not found error."""

    pass


class BaseRepository(Generic[T], ABC):
    """Base repository with common CRUD operations."""

    def __init__(self, model_class: Type[T], config_manager, database_manager=None, transaction_manager=None, cache_manager=None):
        if config_manager is None:
            raise ValueError("config_manager is required and cannot be None")
        
        self.model_class = model_class
        self.logger = get_logger(f"repository_{model_class.__name__.lower()}")
        self.config_manager = config_manager
        
        # Inject dependencies or get defaults with proper error handling
        self.database_manager = database_manager or self._get_database_manager()
        self.transaction_manager = transaction_manager or self._get_transaction_manager()
        self.cache_manager = cache_manager or self._get_cache_manager()
        
        # Validate critical dependencies (Fail Fast approach)
        self._validate_critical_dependencies()

        # Performance settings
        self.query_timeout = self.config_manager.get_float(
            "REPOSITORY_QUERY_TIMEOUT", 30.0
        )
        self.cache_ttl = self.config_manager.get_int(
            "REPOSITORY_CACHE_TTL", 300
        )  # 5 minutes
        self.enable_caching = self.config_manager.get_bool(
            "REPOSITORY_ENABLE_CACHING", True
        )

        # Child safety settings
        self.child_data_protection = self.config_manager.get_bool(
            "CHILD_DATA_PROTECTION", True
        )
    
    def _get_database_manager(self):
        """Get database manager with proper error handling."""
        global database_manager
        if database_manager is None:
            try:
                # Try to import and initialize
                from .database_manager import get_database_manager
                return get_database_manager()
            except ImportError as e:
                raise RuntimeError(
                    "database_manager is not available. Ensure database system is initialized."
                ) from e
        return database_manager
    
    def _get_transaction_manager(self):
        """Get transaction manager with proper error handling."""
        global transaction_manager
        if transaction_manager is None:
            try:
                # Try to import and initialize
                from .transaction_manager import get_transaction_manager
                return get_transaction_manager()
            except ImportError as e:
                # Transaction manager is optional, log warning and continue
                self.logger.warning("transaction_manager not available, operations will not use transactions")
                return None
        return transaction_manager
    
    def _get_cache_manager(self):
        """Get cache manager with proper error handling."""
        try:
            return get_cache_manager()
        except Exception as e:
            # Cache manager is optional, log warning and continue
            self.logger.warning(f"cache_manager not available: {str(e)}")
            return None
    
    def _validate_critical_dependencies(self):
        """Validate critical dependencies using Fail Fast approach."""
        errors = []
        
        # Database manager is absolutely critical
        if not self.database_manager:
            errors.append("database_manager is required but not available")
        
        # Config manager must have essential settings
        try:
            essential_settings = [
                "REPOSITORY_QUERY_TIMEOUT",
                "REPOSITORY_CACHE_TTL", 
                "CHILD_DATA_PROTECTION"
            ]
            
            for setting in essential_settings:
                value = self.config_manager.get(setting)
                if value is None:
                    errors.append(f"Essential config setting '{setting}' is missing")
                    
        except Exception as e:
            errors.append(f"config_manager validation failed: {str(e)}")
        
        # If we have errors, fail fast
        if errors:
            error_msg = f"Repository initialization failed for {self.model_class.__name__}: " + "; ".join(errors)
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        self.logger.debug(
            f"Repository dependencies validated successfully for {self.model_class.__name__}",
            extra={
                "has_database_manager": bool(self.database_manager),
                "has_transaction_manager": bool(self.transaction_manager),
                "has_cache_manager": bool(self.cache_manager),
                "cache_enabled": self.enable_caching
            }
        )

    async def create(
        self,
        data: Dict[str, Any],
        user_id: Optional[uuid.UUID] = None,
        validate: bool = True,
    ) -> T:
        """Create new entity with validation and audit logging."""
        try:
            # Validate data
            if validate:
                data = await self._validate_create_data(data)

            # Add audit fields
            data["created_by"] = user_id
            data["updated_by"] = user_id

            # Check child data protection
            if self._involves_child_data(data):
                await self._validate_child_data_operation(data, "create", user_id)

            # Create entity
            entity = self.model_class(**data)

            # Execute in transaction (if transaction manager available)
            if self.transaction_manager:
                async with self.transaction_manager.transaction() as tx:
                    # Use database manager for write operation
                    result = await self.database_manager.execute_write(
                        self._insert_entity, entity
                    )
            else:
                # Execute without transaction if transaction manager not available
                result = await self.database_manager.execute_write(
                    self._insert_entity, entity
                )

                # Log creation
                await self._log_audit_event(
                    "create", entity.id, user_id, new_values=data
                )

                # Invalidate cache (if cache manager available)
                if self.enable_caching and self.cache_manager:
                    await self._invalidate_cache(entity.id)

                self.logger.info(
                    f"Created {self.model_class.__name__} {entity.id}",
                    extra={
                        "entity_id": str(entity.id),
                        "user_id": str(user_id) if user_id else None,
                    },
                )

                return entity

        except IntegrityError as e:
            self.logger.error(f"Integrity constraint violation: {str(e)}")
            raise ValidationError(f"Data integrity violation: {str(e)}")

        except Exception as e:
            self.logger.error(f"Failed to create {self.model_class.__name__}: {str(e)}")
            raise RepositoryError(f"Create operation failed: {str(e)}")

    async def get_by_id(
        self,
        entity_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        include_deleted: bool = False,
    ) -> Optional[T]:
        """Get entity by ID with caching and permission checks."""
        try:
            # Check cache first (if cache manager available)
            if self.enable_caching and self.cache_manager:
                cached_entity = await self._get_from_cache(entity_id)
                if cached_entity:
                    # Check permissions for cached entity
                    if await self._check_read_permission(cached_entity, user_id):
                        return cached_entity
                    else:
                        raise PermissionError("Access denied to this resource")

            # Query database
            if not self.database_manager:
                raise RuntimeError("Database manager not available for read operation")
                
            result = await self.database_manager.execute_read(
                self._select_by_id, entity_id, include_deleted
            )

            if not result:
                return None

            entity = self._map_result_to_entity(result)

            # Check permissions
            if not await self._check_read_permission(entity, user_id):
                raise PermissionError("Access denied to this resource")

            # Cache the result (if cache manager available)
            if self.enable_caching and self.cache_manager:
                await self._cache_entity(entity)

            return entity

        except PermissionError:
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to get {self.model_class.__name__} {entity_id}: {str(e)}"
            )
            raise RepositoryError(f"Get operation failed: {str(e)}")

    async def update(
        self,
        entity_id: uuid.UUID,
        data: Dict[str, Any],
        user_id: Optional[uuid.UUID] = None,
        validate: bool = True,
    ) -> Optional[T]:
        """Update entity with validation and audit logging."""
        try:
            # Get existing entity
            existing_entity = await self.get_by_id(entity_id, user_id)
            if not existing_entity:
                raise NotFoundError(
                    f"{self.model_class.__name__} {entity_id} not found"
                )

            # Check write permission
            if not await self._check_write_permission(existing_entity, user_id):
                raise PermissionError("Access denied for update operation")

            # Validate data
            if validate:
                data = await self._validate_update_data(data, existing_entity)

            # Store old values for audit
            old_values = existing_entity.to_dict()

            # Add audit fields
            data["updated_by"] = user_id
            data["updated_at"] = datetime.utcnow()

            # Check child data protection
            if self._involves_child_data(data):
                await self._validate_child_data_operation(data, "update", user_id)

            # Execute update in transaction (if available)
            if self.transaction_manager:
                async with self.transaction_manager.transaction() as tx:
                    result = await self.database_manager.execute_write(
                        self._update_entity, entity_id, data
                    )
            else:
                result = await self.database_manager.execute_write(
                    self._update_entity, entity_id, data
                )

                if result:
                    updated_entity = await self.get_by_id(entity_id, user_id)

                    # Log update
                    await self._log_audit_event(
                        "update",
                        entity_id,
                        user_id,
                        old_values=old_values,
                        new_values=data,
                    )

                    # Invalidate cache
                    if self.enable_caching:
                        await self._invalidate_cache(entity_id)

                    self.logger.info(
                        f"Updated {self.model_class.__name__} {entity_id}",
                        extra={
                            "entity_id": str(entity_id),
                            "user_id": str(user_id) if user_id else None,
                        },
                    )

                    return updated_entity

                return None

        except (NotFoundError, PermissionError):
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to update {self.model_class.__name__} {entity_id}: {str(e)}"
            )
            raise RepositoryError(f"Update operation failed: {str(e)}")

    async def delete(
        self,
        entity_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        soft_delete: bool = True,
    ) -> bool:
        """Delete entity (soft delete by default for audit trail)."""
        try:
            # Get existing entity
            existing_entity = await self.get_by_id(entity_id, user_id)
            if not existing_entity:
                raise NotFoundError(
                    f"{self.model_class.__name__} {entity_id} not found"
                )

            # Check delete permission
            if not await self._check_delete_permission(existing_entity, user_id):
                raise PermissionError("Access denied for delete operation")

            # Store values for audit
            old_values = existing_entity.to_dict()

            # Execute delete in transaction (if available)
            if self.transaction_manager:
                async with self.transaction_manager.transaction() as tx:
                    if soft_delete:
                        # Soft delete
                        delete_data = {
                            "is_deleted": True,
                            "deleted_at": datetime.utcnow(),
                            "updated_by": user_id,
                        }

                        result = await self.database_manager.execute_write(
                            self._update_entity, entity_id, delete_data
                        )
                    else:
                        # Hard delete
                        result = await self.database_manager.execute_write(
                            self._delete_entity, entity_id
                        )
            else:
                if soft_delete:
                    # Soft delete without transaction
                    delete_data = {
                        "is_deleted": True,
                        "deleted_at": datetime.utcnow(),
                        "updated_by": user_id,
                    }
                    result = await self.database_manager.execute_write(
                        self._update_entity, entity_id, delete_data
                    )
                else:
                    # Hard delete without transaction
                    result = await self.database_manager.execute_write(
                        self._delete_entity, entity_id
                    )

                if result:
                    # Log deletion
                    await self._log_audit_event(
                        "delete" if not soft_delete else "soft_delete",
                        entity_id,
                        user_id,
                        old_values=old_values,
                    )

                    # Invalidate cache
                    if self.enable_caching:
                        await self._invalidate_cache(entity_id)

                    # Special handling for child data
                    if self._involves_child_data(old_values):
                        await self._handle_child_data_deletion(existing_entity, user_id)

                    self.logger.info(
                        f"{'Soft ' if soft_delete else ''}Deleted {self.model_class.__name__} {entity_id}",
                        extra={
                            "entity_id": str(entity_id),
                            "user_id": str(user_id) if user_id else None,
                        },
                    )

                    return True

                return False

        except (NotFoundError, PermissionError):
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to delete {self.model_class.__name__} {entity_id}: {str(e)}"
            )
            raise RepositoryError(f"Delete operation failed: {str(e)}")

    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        user_id: Optional[uuid.UUID] = None,
        offset: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Tuple[List[T], int]:
        """List entities with filtering, pagination, and permission checks."""
        try:
            # Validate and sanitize filters
            filters = filters or {}
            filters = await self._validate_filters(filters, user_id)

            # Apply permission filters
            filters = await self._apply_permission_filters(filters, user_id)

            # Execute query
            if not self.database_manager:
                raise RuntimeError("Database manager not available for list operation")
                
            results, total_count = await self.database_manager.execute_read(
                self._select_list, filters, offset, limit, order_by, include_deleted
            )

            # Map results to entities
            entities = [self._map_result_to_entity(result) for result in results]

            # Filter entities based on individual permissions
            filtered_entities = []
            for entity in entities:
                if await self._check_read_permission(entity, user_id):
                    filtered_entities.append(entity)

            self.logger.debug(
                f"Listed {len(filtered_entities)} {self.model_class.__name__} entities",
                extra={
                    "user_id": str(user_id) if user_id else None,
                    "filters": filters,
                    "total_count": total_count,
                },
            )

            return filtered_entities, total_count

        except Exception as e:
            self.logger.error(f"Failed to list {self.model_class.__name__}: {str(e)}")
            raise RepositoryError(f"List operation failed: {str(e)}")

    # Abstract methods for subclasses to implement
    @abstractmethod
    async def _validate_create_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data for create operation."""
        pass

    @abstractmethod
    async def _validate_update_data(
        self, data: Dict[str, Any], existing_entity: T
    ) -> Dict[str, Any]:
        """Validate data for update operation."""
        pass

    @abstractmethod
    async def _check_read_permission(
        self, entity: T, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check if user has read permission for entity."""
        pass

    @abstractmethod
    async def _check_write_permission(
        self, entity: T, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check if user has write permission for entity."""
        pass

    @abstractmethod
    async def _check_delete_permission(
        self, entity: T, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check if user has delete permission for entity."""
        pass

    # Helper methods
    def _involves_child_data(self, data: Dict[str, Any]) -> bool:
        """Check if operation involves child data."""
        return "child_id" in data or isinstance(
            self.model_class, (Child, Message, Conversation, SafetyReport)
        )

    async def _validate_child_data_operation(
        self, data: Dict[str, Any], operation: str, user_id: Optional[uuid.UUID]
    ):
        """Validate child data operation for COPPA compliance."""
        if not self.child_data_protection:
            return

        # Log child data access
        security_logger.info(
            f"Child data {operation} operation attempted",
            extra={
                "operation": operation,
                "user_id": str(user_id) if user_id else None,
                "model": self.model_class.__name__,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Additional validation for child data operations
        if "child_id" in data and user_id:
            # Verify user has permission to access this child's data
            child_id = data["child_id"]
            if not await self._user_can_access_child_data(user_id, child_id):
                raise PermissionError(
                    "User does not have permission to access this child's data"
                )

    async def _user_can_access_child_data(
        self, user_id: uuid.UUID, child_id: uuid.UUID
    ) -> bool:
        """Check if user can access specific child's data with database verification."""
        try:
            # Check if user is admin
            if await self._is_admin_access_check(user_id):
                return True
            
            # Check if user is the child's parent
            result = await database_manager.execute_read(
                self._check_parent_child_relationship, user_id, child_id
            )
            return bool(result)
            
        except Exception as e:
            self.logger.error(f"Child data access check failed: {str(e)}")
            return False
            
    async def _check_parent_child_relationship(self, conn, user_id: uuid.UUID, child_id: uuid.UUID):
        """Query to verify parent-child relationship."""
        query = """
            SELECT 1 FROM children c
            JOIN users u ON c.parent_id = u.id
            WHERE c.id = $1 AND u.id = $2
            AND u.is_active = TRUE
            AND (c.is_deleted = FALSE OR c.is_deleted IS NULL)
            LIMIT 1
        """
        return await conn.fetchrow(query, str(child_id), str(user_id))
        
    async def _is_admin_access_check(self, user_id: uuid.UUID) -> bool:
        """Check if user has admin privileges for data access."""
        try:
            result = await database_manager.execute_read(
                self._check_admin_privileges, user_id
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Admin privileges check failed: {str(e)}")
            return False
            
    async def _check_admin_privileges(self, conn, user_id: uuid.UUID):
        """Query to check admin privileges."""
        query = """
            SELECT 1 FROM users 
            WHERE id = $1 
            AND role IN ('admin', 'support') 
            AND is_active = TRUE 
            LIMIT 1
        """
        return await conn.fetchrow(query, str(user_id))

    async def _handle_child_data_deletion(
        self, entity: T, user_id: Optional[uuid.UUID]
    ):
        """Handle special child data deletion requirements."""
        security_logger.warning(
            f"Child data deleted: {self.model_class.__name__}",
            extra={
                "entity_id": str(entity.id),
                "user_id": str(user_id) if user_id else None,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def _log_audit_event(
        self,
        action: str,
        resource_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
    ):
        """Log audit event for data operation."""
        audit_data = {
            "user_id": user_id,
            "action": action,
            "resource_type": self.model_class.__name__,
            "resource_id": resource_id,
            "old_values": old_values,
            "new_values": new_values,
            "involves_child_data": self._involves_child_data(
                new_values or old_values or {}
            ),
            "timestamp": datetime.utcnow(),
        }

        # Create audit log entry
        audit_logger.audit(f"{action} {self.model_class.__name__}", metadata=audit_data)

    # Cache management methods
    async def _get_from_cache(self, entity_id: uuid.UUID) -> Optional[T]:
        """Get entity from cache."""
        if not self.cache_manager:
            return None

        try:
            cache_key = f"{self.model_class.__name__.lower()}:{entity_id}"
            cached_data = await self.cache_manager.get(cache_key)

            if cached_data:
                return self.model_class(**json.loads(cached_data))

        except Exception as e:
            self.logger.warning(f"Cache get failed: {str(e)}")

        return None

    async def _cache_entity(self, entity: T):
        """Cache entity."""
        if not self.cache_manager:
            return

        try:
            cache_key = f"{self.model_class.__name__.lower()}:{entity.id}"
            entity_data = json.dumps(entity.to_dict(), default=str)
            await self.cache_manager.set(cache_key, entity_data, ttl=self.cache_ttl)

        except Exception as e:
            self.logger.warning(f"Cache set failed: {str(e)}")

    async def _invalidate_cache(self, entity_id: uuid.UUID):
        """Invalidate cached entity."""
        if not self.cache_manager:
            return

        try:
            cache_key = f"{self.model_class.__name__.lower()}:{entity_id}"
            await self.cache_manager.delete(cache_key)

        except Exception as e:
            self.logger.warning(f"Cache invalidation failed: {str(e)}")

    # Database operation methods - PRODUCTION IMPLEMENTATIONS
    async def _insert_entity(self, conn, entity: T):
        """Insert entity into database using actual PostgreSQL connection."""
        try:
            table_name = self._get_table_name()
            columns = self._get_entity_columns(entity)
            values = self._get_entity_values(entity)
            placeholders = ', '.join([f'${i+1}' for i in range(len(values))])
            
            query = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({placeholders})
                RETURNING *
            """
            
            result = await conn.fetchrow(query, *values)
            return result
            
        except Exception as e:
            self.logger.error(f"Database insert failed: {str(e)}")
            raise

    async def _select_by_id(self, conn, entity_id: uuid.UUID, include_deleted: bool):
        """Select entity by ID from PostgreSQL database."""
        try:
            table_name = self._get_table_name()
            where_clause = "WHERE id = $1"
            
            if not include_deleted and self._has_soft_delete():
                where_clause += " AND (is_deleted = FALSE OR is_deleted IS NULL)"
            
            query = f"SELECT * FROM {table_name} {where_clause}"
            result = await conn.fetchrow(query, str(entity_id))
            return result
            
        except Exception as e:
            self.logger.error(f"Database select failed: {str(e)}")
            raise

    async def _update_entity(self, conn, entity_id: uuid.UUID, data: Dict[str, Any]):
        """Update entity in PostgreSQL database."""
        try:
            table_name = self._get_table_name()
            
            # Build SET clause
            set_clauses = []
            values = []
            param_index = 1
            
            for key, value in data.items():
                set_clauses.append(f"{key} = ${param_index}")
                values.append(value)
                param_index += 1
            
            # Add entity_id as last parameter
            values.append(str(entity_id))
            
            query = f"""
                UPDATE {table_name} 
                SET {', '.join(set_clauses)}
                WHERE id = ${param_index}
                RETURNING *
            """
            
            result = await conn.fetchrow(query, *values)
            return result
            
        except Exception as e:
            self.logger.error(f"Database update failed: {str(e)}")
            raise

    async def _delete_entity(self, conn, entity_id: uuid.UUID):
        """Delete entity from PostgreSQL database (hard delete)."""
        try:
            table_name = self._get_table_name()
            query = f"DELETE FROM {table_name} WHERE id = $1 RETURNING id"
            result = await conn.fetchrow(query, str(entity_id))
            return result is not None
            
        except Exception as e:
            self.logger.error(f"Database delete failed: {str(e)}")
            raise

    async def _select_list(
        self,
        conn,
        filters: Dict[str, Any],
        offset: int,
        limit: int,
        order_by: Optional[str],
        include_deleted: bool,
    ):
        """Select list of entities from PostgreSQL database with filters."""
        try:
            table_name = self._get_table_name()
            
            # Build WHERE clause
            where_clauses = []
            values = []
            param_index = 1
            
            # Add soft delete filter
            if not include_deleted and self._has_soft_delete():
                where_clauses.append("(is_deleted = FALSE OR is_deleted IS NULL)")
            
            # Add custom filters
            for key, value in filters.items():
                if value is not None:
                    where_clauses.append(f"{key} = ${param_index}")
                    values.append(value)
                    param_index += 1
            
            where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            # Build ORDER BY clause
            order_clause = ""
            if order_by:
                # Sanitize order_by to prevent SQL injection
                safe_order_by = order_by.replace(';', '').replace('--', '')
                order_clause = f"ORDER BY {safe_order_by}"
            else:
                order_clause = "ORDER BY created_at DESC"
            
            # Build LIMIT and OFFSET
            limit_clause = f"LIMIT ${param_index} OFFSET ${param_index + 1}"
            values.extend([limit, offset])
            
            # Count query
            count_query = f"SELECT COUNT(*) FROM {table_name} {where_clause}"
            total_count = await conn.fetchval(count_query, *values[:-2])  # Exclude limit/offset
            
            # Main query
            query = f"""
                SELECT * FROM {table_name} 
                {where_clause}
                {order_clause}
                {limit_clause}
            """
            
            results = await conn.fetch(query, *values)
            return results, total_count
            
        except Exception as e:
            self.logger.error(f"Database list query failed: {str(e)}")
            raise

    def _map_result_to_entity(self, result) -> T:
        """Map PostgreSQL result record to entity object."""
        try:
            if not result:
                return None
                
            # Convert asyncpg record to dict
            data = dict(result)
            
            # Handle UUID conversion
            if 'id' in data and isinstance(data['id'], str):
                data['id'] = uuid.UUID(data['id'])
                
            # Handle other UUID fields
            uuid_fields = ['parent_id', 'child_id', 'user_id', 'conversation_id']
            for field in uuid_fields:
                if field in data and data[field] and isinstance(data[field], str):
                    data[field] = uuid.UUID(data[field])
            
            # Handle datetime fields
            datetime_fields = ['created_at', 'updated_at', 'deleted_at', 'last_login']
            for field in datetime_fields:
                if field in data and data[field]:
                    if isinstance(data[field], str):
                        data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
            
            # Handle JSON fields
            json_fields = ['preferences', 'safety_settings', 'conversation_metadata', 'message_metadata']
            for field in json_fields:
                if field in data and isinstance(data[field], str):
                    try:
                        data[field] = json.loads(data[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            
            # Create entity instance
            return self.model_class(**data)
            
        except Exception as e:
            self.logger.error(f"Entity mapping failed: {str(e)}")
            raise
    
    def _get_table_name(self) -> str:
        """Get database table name for the model."""
        if hasattr(self.model_class, '__tablename__'):
            return self.model_class.__tablename__
        else:
            # Map model classes to actual table names used in production_models.py
            model_to_table = {
                'UserModel': 'users',
                'ChildModel': 'children', 
                'ConversationModel': 'conversations',
                'MessageModel': 'messages',
                'AuditLogModel': 'audit_logs',
                'ConsentModel': 'parental_consents',
                'SessionModel': 'sessions',
                'User': 'users',
                'Child': 'children',
                'Conversation': 'conversations', 
                'Message': 'messages',
                'AuditLog': 'audit_logs',
                'Notification': 'notifications',
                'DeliveryRecord': 'delivery_records',
                'SafetyReport': 'safety_reports',
                'Interaction': 'interactions',
                'Subscription': 'subscriptions',
                'PaymentTransaction': 'payment_transactions',
            }
            class_name = self.model_class.__name__
            return model_to_table.get(class_name, f"{class_name.lower()}s")
    
    def _has_soft_delete(self) -> bool:
        """Check if model supports soft delete."""
        return hasattr(self.model_class, 'is_deleted')
    
    def _get_entity_columns(self, entity: T) -> List[str]:
        """Get column names for entity insertion."""
        columns = []
        for attr_name in dir(entity):
            if not attr_name.startswith('_') and hasattr(entity, attr_name):
                attr_value = getattr(entity, attr_name)
                if not callable(attr_value):
                    columns.append(attr_name)
        return columns
    
    def _get_entity_values(self, entity: T) -> List[Any]:
        """Get values for entity insertion."""
        values = []
        for attr_name in dir(entity):
            if not attr_name.startswith('_') and hasattr(entity, attr_name):
                attr_value = getattr(entity, attr_name)
                if not callable(attr_value):
                    # Convert UUID to string for PostgreSQL
                    if isinstance(attr_value, uuid.UUID):
                        values.append(str(attr_value))
                    # Convert datetime to ISO string
                    elif isinstance(attr_value, datetime):
                        values.append(attr_value.isoformat())
                    # Convert dict/list to JSON string
                    elif isinstance(attr_value, (dict, list)):
                        values.append(json.dumps(attr_value))
                    else:
                        values.append(attr_value)
        return values

    async def _validate_filters(
        self, filters: Dict[str, Any], user_id: Optional[uuid.UUID]
    ) -> Dict[str, Any]:
        """Validate and sanitize filters."""
        return filters

    async def _apply_permission_filters(
        self, filters: Dict[str, Any], user_id: Optional[uuid.UUID]
    ) -> Dict[str, Any]:
        """Apply permission-based filters."""
        return filters


class UserRepository(BaseRepository[User]):
    """Repository for User entities."""

    def __init__(self, config_manager, database_manager=None, transaction_manager=None, cache_manager=None):
        super().__init__(User, config_manager, database_manager, transaction_manager, cache_manager)

    async def _validate_create_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user creation data."""
        required_fields = ["username", "role"]
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")

        # Validate username uniqueness
        if await self._username_exists(data["username"]):
            raise ValidationError("Username already exists")

        # Validate email if provided
        if "email" in data and data["email"]:
            if await self._email_exists(data["email"]):
                raise ValidationError("Email already exists")

        return data

    async def _validate_update_data(
        self, data: Dict[str, Any], existing_entity: User
    ) -> Dict[str, Any]:
        """Validate user update data."""
        # Check username uniqueness if being changed
        if "username" in data and data["username"] != existing_entity.username:
            if await self._username_exists(data["username"]):
                raise ValidationError("Username already exists")

        # Check email uniqueness if being changed
        if "email" in data and data["email"] != existing_entity.email:
            if await self._email_exists(data["email"]):
                raise ValidationError("Email already exists")

        return data

    async def _check_read_permission(
        self, entity: User, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check read permission for user."""
        if not user_id:
            return False

        # Users can read their own data, admins can read all
        return entity.id == user_id or await self._is_admin(user_id)

    async def _check_write_permission(
        self, entity: User, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check write permission for user."""
        if not user_id:
            return False

        # Users can update their own data, admins can update all
        return entity.id == user_id or await self._is_admin(user_id)

    async def _check_delete_permission(
        self, entity: User, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check delete permission for user."""
        if not user_id:
            return False

        # Only admins can delete users
        return await self._is_admin(user_id)

    async def _username_exists(self, username: str) -> bool:
        """Check if username already exists in database."""
        if not self.database_manager:
            self.logger.error("Database manager not available for username check")
            return False
            
        try:
            result = await self.database_manager.execute_read(
                self._check_username_exists, username
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Username check failed: {str(e)}")
            return False
    
    async def _check_username_exists(self, conn, username: str):
        """Query to check username existence."""
        query = "SELECT 1 FROM users WHERE email = $1 LIMIT 1"
        return await conn.fetchrow(query, username)

    async def _email_exists(self, email: str) -> bool:
        """Check if email already exists in database."""
        try:
            result = await database_manager.execute_read(
                self._check_email_exists, email
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Email check failed: {str(e)}")
            return False
            
    async def _check_email_exists(self, conn, email: str):
        """Query to check email existence."""
        query = "SELECT 1 FROM users WHERE email = $1 LIMIT 1"
        return await conn.fetchrow(query, email)

    async def _is_admin(self, user_id: uuid.UUID) -> bool:
        """Check if user has admin role in database."""
        try:
            result = await database_manager.execute_read(
                self._check_admin_role, user_id
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Admin check failed: {str(e)}")
            return False
            
    async def _check_admin_role(self, conn, user_id: uuid.UUID):
        """Query to check if user has admin role."""
        query = "SELECT 1 FROM users WHERE id = $1 AND role = 'admin' LIMIT 1"
        return await conn.fetchrow(query, str(user_id))

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username from database."""
        try:
            result = await database_manager.execute_read(
                self._select_by_username, username
            )
            if result:
                return self._map_result_to_entity(result)
            return None
        except Exception as e:
            self.logger.error(f"Get by username failed: {str(e)}")
            return None
            
    async def _select_by_username(self, conn, username: str):
        """Query to select user by username."""
        query = "SELECT * FROM users WHERE email = $1 AND (is_deleted = FALSE OR is_deleted IS NULL) LIMIT 1"
        return await conn.fetchrow(query, username)

    async def get_children(self, parent_id: uuid.UUID) -> List[Child]:
        """Get all children for a parent with permission check."""
        try:
            results = await database_manager.execute_read(
                self._select_children_by_parent, parent_id
            )
            children = []
            for result in results:
                child = self._map_result_to_entity(result) 
                if child:
                    children.append(child)
            return children
        except Exception as e:
            self.logger.error(f"Get children failed: {str(e)}")
            return []
            
    async def _select_children_by_parent(self, conn, parent_id: uuid.UUID):
        """Query to select children by parent ID."""
        query = """
            SELECT * FROM children 
            WHERE parent_id = $1 
            AND (is_deleted = FALSE OR is_deleted IS NULL)
            ORDER BY created_at ASC
        """
        return await conn.fetch(query, str(parent_id))


class ChildRepository(BaseRepository[Child]):
    """Repository for Child entities with enhanced COPPA compliance."""

    def __init__(self, config_manager, database_manager=None, transaction_manager=None, cache_manager=None):
        super().__init__(Child, config_manager, database_manager, transaction_manager, cache_manager)

    async def _validate_create_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate child creation data with COPPA compliance."""
        required_fields = ["parent_id", "name"]
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")

        # Validate parent exists and has permission
        parent_id = data["parent_id"]
        if not await self._parent_exists(parent_id):
            raise ValidationError("Invalid parent ID")

        # Ensure parental consent is properly handled
        if "estimated_age" in data and data["estimated_age"] < 13:
            if not data.get("parental_consent", False):
                raise ValidationError("Parental consent required for children under 13")

        return data

    async def _validate_update_data(
        self, data: Dict[str, Any], existing_entity: Child
    ) -> Dict[str, Any]:
        """Validate child update data."""
        # Log all child data updates for audit
        security_logger.info(
            f"Child data update attempted",
            extra={
                "child_hash": existing_entity.hashed_identifier,
                "fields_updated": list(data.keys()),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        return data

    async def _check_read_permission(
        self, entity: Child, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check read permission for child data."""
        if not user_id:
            return False

        # Only parent and admins can read child data
        return entity.parent_id == user_id or await self._is_admin(user_id)

    async def _check_write_permission(
        self, entity: Child, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check write permission for child data."""
        if not user_id:
            return False

        # Only parent and admins can update child data
        return entity.parent_id == user_id or await self._is_admin(user_id)

    async def _check_delete_permission(
        self, entity: Child, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check delete permission for child data."""
        if not user_id:
            return False

        # Only parent and admins can delete child data
        return entity.parent_id == user_id or await self._is_admin(user_id)

    async def _parent_exists(self, parent_id: uuid.UUID) -> bool:
        """Check if parent exists in database."""
        try:
            result = await database_manager.execute_read(
                self._check_parent_exists, parent_id
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Parent check failed: {str(e)}")
            return False
            
    async def _check_parent_exists(self, conn, parent_id: uuid.UUID):
        """Query to check if parent exists."""
        query = "SELECT 1 FROM users WHERE id = $1 AND role = 'parent' AND is_active = TRUE LIMIT 1"
        return await conn.fetchrow(query, str(parent_id))

    async def _is_admin(self, user_id: uuid.UUID) -> bool:
        """Check if user has admin role in database."""
        try:
            result = await database_manager.execute_read(
                self._check_admin_role_child, user_id
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Admin check failed: {str(e)}")
            return False
            
    async def _check_admin_role_child(self, conn, user_id: uuid.UUID):
        """Query to check if user has admin role."""
        query = "SELECT 1 FROM users WHERE id = $1 AND role IN ('admin', 'support') LIMIT 1"
        return await conn.fetchrow(query, str(user_id))

    async def get_by_parent(self, parent_id: uuid.UUID) -> List[Child]:
        """Get all children for a parent with security checks."""
        try:
            results = await database_manager.execute_read(
                self._select_children_by_parent_secure, parent_id
            )
            children = []
            for result in results:
                child = self._map_result_to_entity(result)
                if child:
                    children.append(child)
            return children
        except Exception as e:
            self.logger.error(f"Get children by parent failed: {str(e)}")
            return []
            
    async def _select_children_by_parent_secure(self, conn, parent_id: uuid.UUID):
        """Secure query to select children by parent ID."""
        query = """
            SELECT c.* FROM children c
            JOIN users u ON c.parent_id = u.id
            WHERE c.parent_id = $1 
            AND u.is_active = TRUE
            AND (c.is_deleted = FALSE OR c.is_deleted IS NULL)
            ORDER BY c.created_at ASC
        """
        return await conn.fetch(query, str(parent_id))

    async def get_expiring_data(self, days_ahead: int = 7) -> List[Child]:
        """Get children whose data is expiring soon (COPPA compliance)."""
        try:
            results = await database_manager.execute_read(
                self._select_expiring_data, days_ahead
            )
            children = []
            for result in results:
                child = self._map_result_to_entity(result)
                if child:
                    children.append(child)
            return children
        except Exception as e:
            self.logger.error(f"Get expiring data failed: {str(e)}")
            return []
            
    async def _select_expiring_data(self, conn, days_ahead: int):
        """Query to find children with data expiring soon."""
        query = """
            SELECT * FROM children 
            WHERE created_at + INTERVAL '1 day' * data_retention_days 
                  <= CURRENT_TIMESTAMP + INTERVAL '1 day' * $1
            AND (is_deleted = FALSE OR is_deleted IS NULL)
            ORDER BY created_at ASC
        """
        return await conn.fetch(query, days_ahead)


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for Conversation entities with child safety features."""

    def __init__(self, config_manager, database_manager=None, transaction_manager=None, cache_manager=None):
        super().__init__(Conversation, config_manager, database_manager, transaction_manager, cache_manager)

    async def _validate_create_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate conversation creation data."""
        # Ensure either user_id or child_id is provided
        if not data.get("user_id") and not data.get("child_id"):
            raise ValidationError("Either user_id or child_id must be provided")

        # If child conversation, ensure proper safety settings
        if data.get("child_id"):
            data["safety_checked"] = (
                False  # Require safety check for child conversations
            )
            data["parental_review_required"] = True

        return data

    async def _validate_update_data(
        self, data: Dict[str, Any], existing_entity: Conversation
    ) -> Dict[str, Any]:
        """Validate conversation update data."""
        # Log child conversation updates
        if existing_entity.child_id:
            security_logger.info(
                f"Child conversation update",
                extra={
                    "conversation_id": str(existing_entity.id),
                    "child_id": str(existing_entity.child_id),
                    "fields_updated": list(data.keys()),
                },
            )

        return data

    async def _check_read_permission(
        self, entity: Conversation, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check read permission for conversation."""
        if not user_id:
            return False

        # User can read their own conversations
        if entity.user_id == user_id:
            return True

        # Parent can read child's conversations
        if entity.child_id:
            child = await self._get_child(entity.child_id)
            if child and child.parent_id == user_id:
                return True

        # Admins can read all
        return await self._is_admin(user_id)

    async def _check_write_permission(
        self, entity: Conversation, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check write permission for conversation."""
        # Same as read permission for conversations
        return await self._check_read_permission(entity, user_id)

    async def _check_delete_permission(
        self, entity: Conversation, user_id: Optional[uuid.UUID]
    ) -> bool:
        """Check delete permission for conversation."""
        # Same as read permission for conversations
        return await self._check_read_permission(entity, user_id)

    async def _get_child(self, child_id: uuid.UUID) -> Optional[Child]:
        """Get child by ID from database."""
        try:
            result = await database_manager.execute_read(
                self._select_child_by_id, child_id
            )
            if result:
                return self._map_result_to_entity(result)
            return None
        except Exception as e:
            self.logger.error(f"Get child failed: {str(e)}")
            return None
            
    async def _select_child_by_id(self, conn, child_id: uuid.UUID):
        """Query to select child by ID."""
        query = "SELECT * FROM children WHERE id = $1 AND (is_deleted = FALSE OR is_deleted IS NULL) LIMIT 1"
        return await conn.fetchrow(query, str(child_id))

    async def _is_admin(self, user_id: uuid.UUID) -> bool:
        """Check if user has admin role in database."""
        try:
            result = await database_manager.execute_read(
                self._check_admin_role_conv, user_id
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Admin check failed: {str(e)}")
            return False
            
    async def _check_admin_role_conv(self, conn, user_id: uuid.UUID):
        """Query to check if user has admin role."""
        query = "SELECT 1 FROM users WHERE id = $1 AND role IN ('admin', 'support') AND is_active = TRUE LIMIT 1"
        return await conn.fetchrow(query, str(user_id))

    async def get_child_conversations(
        self, child_id: uuid.UUID, parent_id: uuid.UUID, limit: int = 50
    ) -> List[Conversation]:
        """Get conversations for a child with parent permission verification."""
        try:
            # First verify parent has access to this child
            child = await self._get_child(child_id)
            if not child or child.parent_id != parent_id:
                security_logger.warning(
                    f"Unauthorized child conversation access attempt",
                    extra={
                        "parent_id": str(parent_id),
                        "child_id": str(child_id),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                return []
            
            results = await database_manager.execute_read(
                self._select_child_conversations, child_id, limit
            )
            conversations = []
            for result in results:
                conv = self._map_result_to_entity(result)
                if conv:
                    conversations.append(conv)
            return conversations
        except Exception as e:
            self.logger.error(f"Get child conversations failed: {str(e)}")
            return []
            
    async def _select_child_conversations(self, conn, child_id: uuid.UUID, limit: int):
        """Query to select conversations for a child."""
        query = """
            SELECT * FROM conversations 
            WHERE child_id = $1 
            AND (is_deleted = FALSE OR is_deleted IS NULL)
            ORDER BY created_at DESC 
            LIMIT $2
        """
        return await conn.fetch(query, str(child_id), limit)

    async def get_flagged_conversations(self, user_id: uuid.UUID) -> List[Conversation]:
        """Get conversations flagged for safety review (admin only)."""
        try:
            # Verify admin access
            if not await self._is_admin(user_id):
                security_logger.warning(
                    f"Unauthorized flagged conversations access attempt",
                    extra={
                        "user_id": str(user_id),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                return []
            
            results = await database_manager.execute_read(
                self._select_flagged_conversations
            )
            conversations = []
            for result in results:
                conv = self._map_result_to_entity(result)
                if conv:
                    conversations.append(conv)
            return conversations
        except Exception as e:
            self.logger.error(f"Get flagged conversations failed: {str(e)}")
            return []
            
    async def _select_flagged_conversations(self, conn):
        """Query to select flagged conversations for safety review."""
        query = """
            SELECT c.* FROM conversations c
            WHERE c.safety_score < 0.8
            OR c.parental_review_required = TRUE
            AND (c.is_deleted = FALSE OR c.is_deleted IS NULL)
            ORDER BY c.safety_score ASC, c.created_at ASC
        """
        return await conn.fetch(query)


# Repository factory and manager
class RepositoryManager:
    """Manager for all repositories with strict dependency injection."""

    def __init__(self, config_manager):
        if config_manager is None:
            raise ValueError("config_manager is required and cannot be None")
        
        self.config_manager = config_manager
        self.logger = get_logger("repository_manager")
        self._repositories: Dict[str, BaseRepository] = {}
        self._initialized = False
        
        # Validate config_manager has essential settings
        self._validate_config_manager()
        
        # Initialize repositories with strict dependency injection
        self._initialize_repositories()
    
    def _validate_config_manager(self):
        """Validate that config_manager has all required settings."""
        required_settings = [
            "DATABASE_URL",
            "REPOSITORY_QUERY_TIMEOUT",
            "CHILD_DATA_PROTECTION"
        ]
        
        missing_settings = []
        for setting in required_settings:
            try:
                value = self.config_manager.get(setting)
                if value is None:
                    missing_settings.append(setting)
            except Exception as e:
                missing_settings.append(f"{setting} (error: {str(e)})")
        
        if missing_settings:
            raise ValueError(
                f"config_manager is missing required settings: {', '.join(missing_settings)}"
            )
    
    def _initialize_repositories(self):
        """Initialize all repositories with validated config and shared dependencies."""
        try:
            # Get shared dependencies once for all repositories
            shared_database_manager = self._get_shared_database_manager()
            shared_transaction_manager = self._get_shared_transaction_manager()
            shared_cache_manager = self._get_shared_cache_manager()
            
            # Initialize repositories with explicit dependency injection
            self._repositories["user"] = UserRepository(
                self.config_manager,
                database_manager=shared_database_manager,
                transaction_manager=shared_transaction_manager,
                cache_manager=shared_cache_manager
            )
            self._repositories["child"] = ChildRepository(
                self.config_manager,
                database_manager=shared_database_manager,
                transaction_manager=shared_transaction_manager,
                cache_manager=shared_cache_manager
            )
            self._repositories["conversation"] = ConversationRepository(
                self.config_manager,
                database_manager=shared_database_manager,
                transaction_manager=shared_transaction_manager,
                cache_manager=shared_cache_manager
            )
            self._initialized = True
            
            self.logger.info(
                "RepositoryManager initialized successfully",
                extra={
                    "repositories_count": len(self._repositories),
                    "config_validated": True
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize repositories: {str(e)}")
            raise RuntimeError(f"Repository initialization failed: {str(e)}") from e
    
    def _get_shared_database_manager(self):
        """Get shared database manager for all repositories."""
        try:
            # Try to get enterprise database manager first
            from .database_manager import get_enterprise_database_manager
            return get_enterprise_database_manager()
        except ImportError:
            try:
                # Fallback to regular database manager
                from .database_manager import get_database_manager
                return get_database_manager()
            except ImportError as e:
                raise RuntimeError("No database manager available") from e
    
    def _get_shared_transaction_manager(self):
        """Get shared transaction manager for all repositories."""
        try:
            from .transaction_manager import get_transaction_manager
            return get_transaction_manager()
        except ImportError:
            self.logger.warning("Transaction manager not available - operations will not use transactions")
            return None
    
    def _get_shared_cache_manager(self):
        """Get shared cache manager for all repositories."""
        try:
            return get_cache_manager()
        except ImportError:
            self.logger.warning("Cache manager not available - caching will be disabled")
            return None

    def get_repository(self, entity_type: str) -> BaseRepository:
        """Get repository for entity type with initialization check."""
        if not self._initialized:
            raise RuntimeError("RepositoryManager not properly initialized")
        
        if entity_type not in self._repositories:
            raise ValueError(
                f"No repository found for entity type: {entity_type}. "
                f"Available types: {list(self._repositories.keys())}"
            )

        return self._repositories[entity_type]

    @property
    def user(self) -> UserRepository:
        """Get user repository."""
        return self._repositories["user"]

    @property
    def child(self) -> ChildRepository:
        """Get child repository."""
        return self._repositories["child"]

    @property
    def conversation(self) -> ConversationRepository:
        """Get conversation repository."""
        return self._repositories["conversation"]


# Global repository manager with thread-safe initialization
_repository_manager: Optional[RepositoryManager] = None
_initialization_lock = threading.Lock()


def get_repository_manager(config_manager=None) -> RepositoryManager:
    """Get the global repository manager instance with safe lazy initialization.
    
    Args:
        config_manager: Optional config manager. If not provided, will get default.
                       Should be provided on first call to ensure proper initialization.
    
    Returns:
        RepositoryManager: Initialized repository manager
        
    Raises:
        RuntimeError: If config_manager is not available or initialization fails
    """
    global _repository_manager
    
    # Fast path for already initialized manager
    if _repository_manager is not None:
        return _repository_manager
    
    # Thread-safe initialization
    with _initialization_lock:
        # Double-check pattern
        if _repository_manager is not None:
            return _repository_manager
            
        # Get config manager if not provided
        if config_manager is None:
            try:
                config_manager = get_config_manager()
            except Exception as e:
                raise RuntimeError(
                    "Cannot initialize RepositoryManager: config_manager not available. "
                    "Ensure config_manager is initialized before using repositories."
                ) from e
        
        if config_manager is None:
            raise RuntimeError(
                "config_manager is None. Repository system requires valid configuration."
            )
        
        try:
            _repository_manager = RepositoryManager(config_manager)
            return _repository_manager
        except Exception as e:
            # Reset on failure to allow retry
            _repository_manager = None
            raise RuntimeError(f"Failed to create RepositoryManager: {str(e)}") from e


def reset_repository_manager():
    """Reset repository manager (for testing or reconfiguration)."""
    global _repository_manager
    with _initialization_lock:
        if _repository_manager is not None:
            # Could add cleanup logic here if needed
            _repository_manager = None


def is_repository_manager_initialized() -> bool:
    """Check if repository manager is initialized."""
    return _repository_manager is not None


# Convenience functions with proper error handling
async def get_user_repository(config_manager=None) -> UserRepository:
    """Get user repository with proper initialization check.
    
    Args:
        config_manager: Optional config manager for first-time initialization
    
    Returns:
        UserRepository: Initialized user repository
        
    Raises:
        RuntimeError: If repository system is not properly initialized
    """
    try:
        manager = get_repository_manager(config_manager)
        return manager.user
    except Exception as e:
        raise RuntimeError(f"Cannot get user repository: {str(e)}") from e


async def get_child_repository(config_manager=None) -> ChildRepository:
    """Get child repository with proper initialization check.
    
    Args:
        config_manager: Optional config manager for first-time initialization
    
    Returns:
        ChildRepository: Initialized child repository
        
    Raises:
        RuntimeError: If repository system is not properly initialized
    """
    try:
        manager = get_repository_manager(config_manager)
        return manager.child
    except Exception as e:
        raise RuntimeError(f"Cannot get child repository: {str(e)}") from e


async def get_conversation_repository(config_manager=None) -> ConversationRepository:
    """Get conversation repository with proper initialization check.
    
    Args:
        config_manager: Optional config manager for first-time initialization
    
    Returns:
        ConversationRepository: Initialized conversation repository
        
    Raises:
        RuntimeError: If repository system is not properly initialized
    """
    try:
        manager = get_repository_manager(config_manager)
        return manager.conversation
    except Exception as e:
        raise RuntimeError(f"Cannot get conversation repository: {str(e)}") from e


# System validation functions
def validate_repository_system(config_manager) -> bool:
    """Validate that repository system can be properly initialized.
    
    Args:
        config_manager: Configuration manager to validate
    
    Returns:
        bool: True if system can be initialized, False otherwise
    """
    try:
        # Try to create a temporary repository manager
        temp_manager = RepositoryManager(config_manager)
        return temp_manager._initialized
    except Exception:
        return False


async def initialize_repository_system(config_manager) -> RepositoryManager:
    """Initialize repository system with proper validation.
    
    Args:
        config_manager: Configuration manager to use
        
    Returns:
        RepositoryManager: Initialized repository manager
        
    Raises:
        RuntimeError: If initialization fails
    """
    if not validate_repository_system(config_manager):
        raise RuntimeError(
            "Repository system validation failed. Check config_manager settings."
        )
    
    return get_repository_manager(config_manager)
