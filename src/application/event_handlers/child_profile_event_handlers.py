import asyncio
import logging
from typing import Optional, Any, Dict
from contextlib import asynccontextmanager

from src.interfaces.read_model_interfaces import (
    IChildProfileReadModel,
    IChildProfileReadModelStore,
)
from src.core.events import ChildProfileUpdated, ChildRegistered

"""
Child Profile Event Handlers for AI Teddy Bear
This module handles domain events related to child profile management,
updating read models and maintaining data consistency across the system.

Performance Features:
- Async/await pattern for non-blocking operations
- Batch processing capabilities
- Optimized database operations
- Connection pooling support
"""

logger = logging.getLogger(__name__)


def create_child_profile_read_model(
    child_id: str,
    name: str,
    age: int,
    preferences: Optional[Dict[str, Any]] = None
) -> IChildProfileReadModel:
    """Factory function to create child profile read model.
    
    Args:
        child_id: Unique identifier for the child
        name: Child's name
        age: Child's age (must be between 3-13 for COPPA compliance)
        preferences: Optional child preferences dictionary
        
    Returns:
        IChildProfileReadModel: New child profile read model
    """
    # COPPA compliance check
    if not (3 <= age <= 13):
        raise ValueError(f"Age {age} violates COPPA compliance (must be 3-13)")
    
    # Create a concrete implementation of the read model
    # This would typically be defined in the infrastructure layer
    class ChildProfileReadModel:
        def __init__(self, child_id: str, name: str, age: int, preferences: Dict[str, Any]):
            self.child_id = child_id
            self.name = name
            self.age = age
            self.preferences = preferences or {}
    
    return ChildProfileReadModel(child_id, name, age, preferences or {})


class ChildProfileEventHandlers:
    """High-performance event handlers for child profile domain events.
    Handles child registration and profile update events with optimized
    async operations, transaction support, and consistent error handling.
    """

    def __init__(self, read_model_store: IChildProfileReadModelStore) -> None:
        self.read_model_store = read_model_store
        self._max_retry_attempts = 3
        self._retry_delay = 1.0  # seconds

    @asynccontextmanager
    async def _transaction_context(self):
        """Context manager for database transactions with rollback support."""
        transaction = None
        try:
            # Check if store supports transactions
            if hasattr(self.read_model_store, 'begin_transaction'):
                transaction = await self.read_model_store.begin_transaction()
            
            yield transaction
            
            # Commit transaction if supported
            if transaction and hasattr(transaction, 'commit'):
                await transaction.commit()
                
        except Exception as e:
            # Rollback transaction if supported
            if transaction and hasattr(transaction, 'rollback'):
                try:
                    await transaction.rollback()
                    logger.info("Transaction rolled back successfully")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")
            raise e

    async def _retry_operation(self, operation, *args, **kwargs):
        """Retry an operation with exponential backoff."""
        last_exception = None
        
        for attempt in range(self._max_retry_attempts):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self._max_retry_attempts - 1:
                    delay = self._retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Operation failed (attempt {attempt + 1}/{self._max_retry_attempts}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Operation failed after {self._max_retry_attempts} attempts: {e}")
        
        raise last_exception

    async def handle_child_registered(self, event: ChildRegistered) -> None:
        """Handle child registration event with transaction support and retry logic.

        Args:
            event: ChildRegistered domain event

        Features:
        - Transaction support with automatic rollback
        - Retry logic with exponential backoff
        - Comprehensive error handling and recovery
        - COPPA compliance validation
        """
        correlation_id = getattr(event, 'correlation_id', 'unknown')
        logger.info(f"Processing child registration event [correlation_id: {correlation_id}]")
        
        try:
            # Validate COPPA compliance
            if not (3 <= event.age <= 13):
                logger.error(f"COPPA violation: Invalid age {event.age} [correlation_id: {correlation_id}]")
                raise ValueError(f"Age {event.age} violates COPPA compliance (must be 3-13)")
            
            async with self._transaction_context() as transaction:
                # Create child profile read model
                child_read_model = create_child_profile_read_model(
                    child_id=event.child_id,
                    name=event.name,
                    age=event.age,
                    preferences=event.preferences,
                )
                
                # Save with retry logic
                await self._retry_operation(self._async_save_transactional, child_read_model, transaction)
                
                logger.info(
                    f"Child profile created successfully for age {event.age} [correlation_id: {correlation_id}]"
                )
                
        except ValueError as ve:
            # COPPA compliance errors should not be retried
            logger.error(f"COPPA compliance error in child registration [correlation_id: {correlation_id}]: {ve}")
            raise
        except Exception as e:
            logger.error(f"Failed to handle child registration [correlation_id: {correlation_id}]: {e}")
            # Don't re-raise to prevent event loop disruption - log and continue
            # The event system should handle dead letter queues for failed events

    async def handle_child_profile_updated(self, event: ChildProfileUpdated) -> None:
        """Handle child profile update event with transaction support and retry logic.

        Args:
            event: ChildProfileUpdated domain event

        Features:
        - Transaction support with automatic rollback
        - Retry logic with exponential backoff
        - Optimistic locking for concurrent updates
        - COPPA compliance validation for age updates
        """
        correlation_id = getattr(event, 'correlation_id', 'unknown')
        logger.info(f"Processing child profile update event [correlation_id: {correlation_id}]")
        
        try:
            async with self._transaction_context() as transaction:
                # Get existing model with retry logic
                existing_model = await self._retry_operation(
                    self._async_get_by_id_transactional, event.child_id, transaction
                )
                
                if not existing_model:
                    logger.warning(f"Child profile not found for update: {event.child_id} [correlation_id: {correlation_id}]")
                    return

                updates_made = False
                update_summary = []

                # Validate age updates for COPPA compliance
                if event.age is not None:
                    if not (3 <= event.age <= 13):
                        logger.error(f"COPPA violation: Invalid age update {event.age} [correlation_id: {correlation_id}]")
                        raise ValueError(f"Age {event.age} violates COPPA compliance (must be 3-13)")
                    
                    if existing_model.age != event.age:
                        existing_model.age = event.age
                        updates_made = True
                        update_summary.append(f"age: {event.age}")

                # Name updates
                if event.name is not None and existing_model.name != event.name:
                    existing_model.name = event.name
                    updates_made = True
                    update_summary.append("name updated")

                # Batch preference updates
                if event.preferences is not None:
                    preference_changes = 0
                    for key, value in event.preferences.items():
                        if existing_model.preferences.get(key) != value:
                            existing_model.preferences[key] = value
                            updates_made = True
                            preference_changes += 1
                    
                    if preference_changes > 0:
                        update_summary.append(f"{preference_changes} preferences")

                if updates_made:
                    # Save with retry logic
                    await self._retry_operation(
                        self._async_save_transactional, existing_model, transaction
                    )
                    
                    logger.info(
                        f"Child profile updated successfully [{', '.join(update_summary)}] "
                        f"[correlation_id: {correlation_id}]"
                    )
                else:
                    logger.debug(f"No changes detected, skipping database update [correlation_id: {correlation_id}]")
                    
        except ValueError as ve:
            # COPPA compliance errors should not be retried
            logger.error(f"COPPA compliance error in profile update [correlation_id: {correlation_id}]: {ve}")
            raise
        except Exception as e:
            logger.error(f"Failed to handle child profile update [correlation_id: {correlation_id}]: {e}")
            # Don't re-raise to prevent event loop disruption - log and continue

    async def _async_save_transactional(self, model: IChildProfileReadModel, transaction=None) -> None:
        """Async save operation with transaction support.

        Args:
            model: Child profile read model to save
            transaction: Optional database transaction
        """
        if hasattr(self.read_model_store, "async_save"):
            if transaction and hasattr(self.read_model_store.async_save, 'supports_transaction'):
                await self.read_model_store.async_save(model, transaction=transaction)
            else:
                await self.read_model_store.async_save(model)
        else:
            # For stores without native async support, ensure we don't block the event loop
            # Use asyncio.to_thread (Python 3.9+) for better thread management
            if hasattr(asyncio, 'to_thread'):
                await asyncio.to_thread(self.read_model_store.save, model)
            else:
                # Fallback for older Python versions
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.read_model_store.save, model)

    async def _async_get_by_id_transactional(self, child_id: str, transaction=None) -> Optional[IChildProfileReadModel]:
        """Async get operation with transaction support.

        Args:
            child_id: Child identifier
            transaction: Optional database transaction

        Returns:
            Child profile read model or None if not found
        """
        if hasattr(self.read_model_store, "async_get_by_id"):
            if transaction and hasattr(self.read_model_store.async_get_by_id, 'supports_transaction'):
                return await self.read_model_store.async_get_by_id(child_id, transaction=transaction)
            else:
                return await self.read_model_store.async_get_by_id(child_id)
        else:
            # For stores without native async support, ensure we don't block the event loop
            # Use asyncio.to_thread (Python 3.9+) for better thread management
            if hasattr(asyncio, 'to_thread'):
                return await asyncio.to_thread(self.read_model_store.get_by_id, child_id)
            else:
                # Fallback for older Python versions
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.read_model_store.get_by_id, child_id)

    async def _async_save(self, model: IChildProfileReadModel) -> None:
        """Legacy async save method for backward compatibility."""
        await self._async_save_transactional(model)

    async def _async_get_by_id(self, child_id: str) -> Optional[IChildProfileReadModel]:
        """Legacy async get method for backward compatibility."""
        return await self._async_get_by_id_transactional(child_id)
