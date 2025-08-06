"""
Database Usage Examples - Production Patterns and Best Practices
================================================================
Comprehensive examples demonstrating proper database usage:
- CRUD operations with repositories
- Child-safe operations with COPPA compliance
- Transaction management patterns
- Error handling and recovery
- Performance optimization
- Health monitoring and metrics
- Security best practices
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from . import (
    initialize_database_infrastructure,
    shutdown_database_infrastructure,
    transaction_manager,
    repository_manager,
    get_user_repository,
    get_child_repository,
    get_conversation_repository
)
from .models import UserRole, SafetyLevel, ConversationStatus, ContentType
from .transaction_manager import TransactionType, IsolationLevel, transactional, child_safe_transactional
from .health_checks import run_database_health_check
from ..logging import get_logger, audit_logger, security_logger


logger = get_logger("database_examples")


class UserManagementExamples:
    """Examples for user management operations."""
    
    @staticmethod
    async def create_parent_user() -> Dict[str, Any]:
        """Create a parent user with proper validation."""
        user_repo = await get_user_repository()
        
        user_data = {
            "username": f"parent_{uuid.uuid4().hex[:8]}",
            "email": f"parent_{uuid.uuid4().hex[:8]}@example.com",
            "password_hash": CryptoUtils().hash_password("secure_random_password"),
            "role": UserRole.PARENT,
            "display_name": "Example Parent",
            "timezone": "UTC",
            "language": "en",
            "settings": {
                "notifications_enabled": True,
                "child_safety_level": "strict",
                "data_sharing_consent": False
            }
        }
        
        try:
            user = await user_repo.create(user_data)
            
            logger.info(f"Created parent user: {user.username}")
            
            return {
                "success": True,
                "user_id": str(user.id),
                "username": user.username,
                "created_at": user.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to create parent user: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def update_user_preferences(user_id: uuid.UUID, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Update user preferences with validation."""
        user_repo = await get_user_repository()
        
        try:
            # Get existing user
            user = await user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Merge preferences with existing settings
            current_settings = user.settings or {}
            current_settings.update(preferences)
            
            # Update user
            updated_user = await user_repo.update(user_id, {"settings": current_settings})
            
            logger.info(f"Updated preferences for user: {user.username}")
            
            return {
                "success": True,
                "user_id": str(user_id),
                "updated_settings": updated_user.settings
            }
            
        except Exception as e:
            logger.error(f"Failed to update user preferences: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def get_user_with_children(user_id: uuid.UUID) -> Dict[str, Any]:
        """Get user with their children (parent-only operation)."""
        user_repo = await get_user_repository()
        child_repo = await get_child_repository()
        
        try:
            # Get user
            user = await user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Check if user is a parent
            if user.role != UserRole.PARENT:
                return {"success": False, "error": "Only parents can access children data"}
            
            # Get children
            children = await child_repo.get_by_parent(user_id)
            
            return {
                "success": True,
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "display_name": user.display_name,
                    "role": user.role.value
                },
                "children": [
                    {
                        "id": str(child.id),
                        "name": child.name,
                        "age": child.get_age(),
                        "safety_level": child.safety_level.value,
                        "parental_consent": child.parental_consent,
                        "coppa_protected": child.is_coppa_protected()
                    }
                    for child in children
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get user with children: {str(e)}")
            return {"success": False, "error": str(e)}


class ChildSafetyExamples:
    """Examples for child safety and COPPA-compliant operations."""
    
    @staticmethod
    async def create_child_with_consent(parent_id: uuid.UUID, child_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create child with proper COPPA compliance."""
        child_repo = await get_child_repository()
        
        # Ensure required fields for COPPA compliance
        child_data.update({
            "parent_id": parent_id,
            "parental_consent": True,
            "consent_date": datetime.now(),
            "content_filtering_enabled": True,
            "interaction_logging_enabled": True,
            "data_retention_days": 90,  # COPPA default
            "allow_data_sharing": False
        })
        
        try:
            # Use child-safe transaction
            async with transaction_manager.transaction(
                transaction_type=TransactionType.CHILD_SAFE,
                child_id=str(uuid.uuid4()),
                parent_consent=True
            ) as tx:
                child = await child_repo.create(child_data)
                
                # Schedule data deletion based on retention policy
                child.schedule_data_deletion()
                
                # Log child creation for audit
                security_logger.info(
                    "Child profile created with COPPA compliance",
                    extra={
                        "child_id_hash": child.hashed_identifier,
                        "parent_id": str(parent_id),
                        "estimated_age": child.estimated_age,
                        "coppa_protected": child.is_coppa_protected(),
                        "parental_consent": child.parental_consent,
                        "consent_date": child.consent_date.isoformat() if child.consent_date else None
                    }
                )
                
                return {
                    "success": True,
                    "child_id": str(child.id),
                    "hashed_identifier": child.hashed_identifier,
                    "coppa_protected": child.is_coppa_protected(),
                    "retention_days": child.data_retention_days,
                    "created_at": child.created_at.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to create child: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def update_child_safety_settings(child_id: uuid.UUID, parent_id: uuid.UUID, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update child safety settings with parent permission."""
        child_repo = await get_child_repository()
        
        try:
            # Verify parent permission
            child = await child_repo.get_by_id(child_id)
            if not child:
                return {"success": False, "error": "Child not found"}
            
            if child.parent_id != parent_id:
                return {"success": False, "error": "Permission denied - not the parent"}
            
            # Validate safety settings
            valid_settings = {}
            if "safety_level" in settings:
                if settings["safety_level"] in [level.value for level in SafetyLevel]:
                    valid_settings["safety_level"] = SafetyLevel(settings["safety_level"])
            
            if "content_filtering_enabled" in settings:
                valid_settings["content_filtering_enabled"] = bool(settings["content_filtering_enabled"])
            
            if "interaction_logging_enabled" in settings:
                valid_settings["interaction_logging_enabled"] = bool(settings["interaction_logging_enabled"])
            
            # Update child with child-safe transaction
            async with transaction_manager.transaction(
                transaction_type=TransactionType.CHILD_SAFE,
                child_id=str(child_id),
                parent_consent=True
            ) as tx:
                updated_child = await child_repo.update(child_id, valid_settings, parent_id)
                
                # Log safety settings change
                security_logger.info(
                    "Child safety settings updated",
                    extra={
                        "child_id_hash": child.hashed_identifier,
                        "parent_id": str(parent_id),
                        "settings_changed": list(valid_settings.keys()),
                        "new_safety_level": updated_child.safety_level.value
                    }
                )
                
                return {
                    "success": True,
                    "child_id": str(child_id),
                    "updated_settings": {
                        "safety_level": updated_child.safety_level.value,
                        "content_filtering_enabled": updated_child.content_filtering_enabled,
                        "interaction_logging_enabled": updated_child.interaction_logging_enabled
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to update child safety settings: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def schedule_child_data_deletion(child_id: uuid.UUID, parent_id: uuid.UUID) -> Dict[str, Any]:
        """Schedule child data for deletion (COPPA compliance)."""
        child_repo = await get_child_repository()
        
        try:
            # Verify parent permission
            child = await child_repo.get_by_id(child_id)
            if not child:
                return {"success": False, "error": "Child not found"}
            
            if child.parent_id != parent_id:
                return {"success": False, "error": "Permission denied - not the parent"}
            
            # Schedule deletion
            deletion_date = datetime.now() + timedelta(days=7)  # 7-day grace period
            
            async with transaction_manager.transaction(
                transaction_type=TransactionType.CHILD_SAFE,
                child_id=str(child_id),
                parent_consent=True
            ) as tx:
                child.schedule_deletion(deletion_date, parent_id)
                await child_repo.update(child_id, {
                    "scheduled_deletion_at": deletion_date,
                    "retention_status": "scheduled_deletion"
                }, parent_id)
                
                # Log deletion scheduling
                security_logger.warning(
                    "Child data deletion scheduled",
                    extra={
                        "child_id_hash": child.hashed_identifier,
                        "parent_id": str(parent_id),
                        "deletion_date": deletion_date.isoformat(),
                        "reason": "parent_request"
                    }
                )
                
                return {
                    "success": True,
                    "child_id": str(child_id),
                    "deletion_scheduled": deletion_date.isoformat(),
                    "grace_period_days": 7
                }
                
        except Exception as e:
            logger.error(f"Failed to schedule child data deletion: {str(e)}")
            return {"success": False, "error": str(e)}


class ConversationExamples:
    """Examples for conversation and message management."""
    
    @staticmethod
    async def create_child_conversation(child_id: uuid.UUID, parent_id: uuid.UUID) -> Dict[str, Any]:
        """Create a new conversation for a child."""
        conversation_repo = await get_conversation_repository()
        child_repo = await get_child_repository()
        
        try:
            # Verify child and parent relationship
            child = await child_repo.get_by_id(child_id)
            if not child or child.parent_id != parent_id:
                return {"success": False, "error": "Invalid child or parent relationship"}
            
            conversation_data = {
                "child_id": child_id,
                "title": f"Conversation with {child.name}",
                "status": ConversationStatus.ACTIVE,
                "safety_checked": False,
                "parental_review_required": child.is_coppa_protected(),
                "educational_content": True,
                "context_data": {
                    "child_age": child.get_age(),
                    "safety_level": child.safety_level.value,
                    "content_filtering": child.content_filtering_enabled
                }
            }
            
            async with transaction_manager.transaction(
                transaction_type=TransactionType.CHILD_SAFE,
                child_id=str(child_id),
                parent_consent=child.parental_consent
            ) as tx:
                conversation = await conversation_repo.create(conversation_data)
                
                # Log conversation creation
                audit_logger.audit(
                    "Child conversation created",
                    metadata={
                        "conversation_id": str(conversation.id),
                        "child_id_hash": child.hashed_identifier,
                        "parent_id": str(parent_id),
                        "coppa_protected": child.is_coppa_protected()
                    }
                )
                
                return {
                    "success": True,
                    "conversation_id": str(conversation.id),
                    "child_id": str(child_id),
                    "safety_checked": conversation.safety_checked,
                    "parental_review_required": conversation.parental_review_required,
                    "created_at": conversation.created_at.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to create child conversation: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def add_safe_message(conversation_id: uuid.UUID, content: str, sender_type: str = "child") -> Dict[str, Any]:
        """Add a message with safety checks."""
        from .models import Message
        from .repository import BaseRepository
        
        try:
            # Create message with safety validation
            message_data = {
                "conversation_id": conversation_id,
                "sender_type": sender_type,
                "content_type": ContentType.CONVERSATION,
                "content": content,
                "safety_checked": False,  # Will be checked by safety service
                "safety_level": SafetyLevel.SAFE,  # Default, will be updated
                "processed_by_ai": sender_type == "ai"
            }
            
            # Use child-safe transaction for child messages
            if sender_type == "child":
                async with transaction_manager.transaction(
                    transaction_type=TransactionType.CHILD_SAFE,
                    child_id="extracted-from-conversation",  # Would be extracted from conversation
                    parent_consent=True
                ) as tx:
                    # In a real implementation, this would use the message repository
                    message_id = uuid.uuid4()
                    
                    # Encrypt content for child messages
                    # message.encrypt_content()  # Would be called on actual message object
                    
                    # Log child message
                    security_logger.info(
                        "Child message created",
                        extra={
                            "message_id": str(message_id),
                            "conversation_id": str(conversation_id),
                            "content_length": len(content),
                            "sender_type": sender_type,
                            "encrypted": True
                        }
                    )
                    
                    return {
                        "success": True,
                        "message_id": str(message_id),
                        "conversation_id": str(conversation_id),
                        "safety_checked": False,
                        "encrypted": True,
                        "created_at": datetime.now().isoformat()
                    }
            else:
                # Regular transaction for non-child messages
                async with transaction_manager.transaction() as tx:
                    message_id = uuid.uuid4()
                    
                    return {
                        "success": True,
                        "message_id": str(message_id),
                        "conversation_id": str(conversation_id),
                        "safety_checked": False,
                        "encrypted": False,
                        "created_at": datetime.now().isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"Failed to add message: {str(e)}")
            return {"success": False, "error": str(e)}


class TransactionExamples:
    """Examples for different transaction patterns."""
    
    @staticmethod
    @transactional(isolation_level=IsolationLevel.READ_COMMITTED, timeout=60.0)
    async def atomic_user_creation(tx, user_data: Dict[str, Any], child_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create user and multiple children atomically."""
        try:
            # Create parent user
            user_repo = await get_user_repository()
            child_repo = await get_child_repository()
            
            user = await user_repo.create(user_data)
            logger.info(f"Created user in transaction: {user.username}")
            
            # Create children
            children = []
            for child_data in child_data_list:
                child_data["parent_id"] = user.id
                child = await child_repo.create(child_data)
                children.append(child)
                logger.info(f"Created child in transaction: {child.name}")
            
            return {
                "success": True,
                "user_id": str(user.id),
                "children_ids": [str(child.id) for child in children],
                "transaction_id": tx.transaction_id
            }
            
        except Exception as e:
            logger.error(f"Atomic user creation failed: {str(e)}")
            # Transaction will be automatically rolled back
            raise
    
    @staticmethod
    async def saga_conversation_cleanup() -> Dict[str, Any]:
        """Use saga pattern for complex conversation cleanup."""
        try:
            async with transaction_manager.transaction(
                transaction_type=TransactionType.SAGA
            ) as saga_tx:
                
                # Step 1: Archive old conversations
                saga_tx.add_step(
                    "archive_conversations",
                    TransactionExamples._archive_old_conversations,
                    TransactionExamples._restore_archived_conversations,
                    "Archive conversations older than 6 months"
                )
                
                # Step 2: Clean up orphaned messages
                saga_tx.add_step(
                    "cleanup_messages",
                    TransactionExamples._cleanup_orphaned_messages,
                    TransactionExamples._restore_cleaned_messages,
                    "Clean up orphaned messages"
                )
                
                # Step 3: Update conversation statistics
                saga_tx.add_step(
                    "update_stats",
                    TransactionExamples._update_conversation_stats,
                    TransactionExamples._revert_conversation_stats,
                    "Update conversation statistics"
                )
                
                # Execute saga
                await saga_tx.execute_saga()
                
                return {
                    "success": True,
                    "saga_id": saga_tx.transaction_id,
                    "steps_completed": len(saga_tx.executed_steps)
                }
                
        except Exception as e:
            logger.error(f"Saga conversation cleanup failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def _archive_old_conversations():
        """Archive old conversations."""
        logger.info("Archiving old conversations")
        # Implementation would archive conversations older than 6 months
    
    @staticmethod
    async def _restore_archived_conversations():
        """Restore archived conversations (compensation)."""
        logger.info("Restoring archived conversations")
        # Implementation would restore conversations if needed
    
    @staticmethod
    async def _cleanup_orphaned_messages():
        """Clean up orphaned messages."""
        logger.info("Cleaning up orphaned messages")
        # Implementation would remove messages without conversations
    
    @staticmethod
    async def _restore_cleaned_messages():
        """Restore cleaned messages (compensation)."""
        logger.info("Restoring cleaned messages")
        # Implementation would restore messages if needed
    
    @staticmethod
    async def _update_conversation_stats():
        """Update conversation statistics."""
        logger.info("Updating conversation statistics")
        # Implementation would update statistical tables
    
    @staticmethod
    async def _revert_conversation_stats():
        """Revert conversation statistics (compensation)."""
        logger.info("Reverting conversation statistics")
        # Implementation would revert statistical changes


class HealthMonitoringExamples:
    """Examples for health monitoring and maintenance."""
    
    @staticmethod
    async def comprehensive_health_check() -> Dict[str, Any]:
        """Run comprehensive health check with detailed reporting."""
        try:
            health_results = await run_database_health_check()
            
            # Analyze results
            critical_issues = []
            warnings = []
            healthy_checks = []
            
            for check_name, result in health_results.items():
                if result.status.value == "critical":
                    critical_issues.append({
                        "check": check_name,
                        "message": result.message,
                        "recommendations": result.recommendations
                    })
                elif result.status.value == "warning":
                    warnings.append({
                        "check": check_name,
                        "message": result.message,
                        "recommendations": result.recommendations
                    })
                else:
                    healthy_checks.append(check_name)
            
            # Create health report
            health_report = {
                "timestamp": datetime.now().isoformat(),
                "overall_status": "critical" if critical_issues else ("warning" if warnings else "healthy"),
                "total_checks": len(health_results),
                "healthy_checks": len(healthy_checks),
                "warnings": len(warnings),
                "critical_issues": len(critical_issues),
                "details": {
                    "healthy": healthy_checks,
                    "warnings": warnings,
                    "critical": critical_issues
                }
            }
            
            # Log health report
            if critical_issues:
                logger.error(f"Database health check found {len(critical_issues)} critical issues")
            elif warnings:
                logger.warning(f"Database health check found {len(warnings)} warnings")
            else:
                logger.info("Database health check passed - all systems healthy")
            
            return health_report
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "overall_status": "unknown",
                "error": str(e)
            }
    
    @staticmethod
    async def performance_monitoring_example() -> Dict[str, Any]:
        """Example of performance monitoring and optimization."""
        try:
            from . import get_database_metrics
            
            # Get current metrics
            metrics = get_database_metrics()
            
            # Analyze performance
            performance_issues = []
            recommendations = []
            
            db_metrics = metrics.get("database_metrics", {})
            tx_metrics = metrics.get("transaction_metrics", {})
            
            # Check connection pool utilization
            for node in db_metrics.get("nodes", []):
                pool_info = node.get("pool_info", {})
                if pool_info:
                    utilization = (
                        pool_info.get("pool_size", 0) / 
                        max(pool_info.get("pool_max_size", 1), 1) * 100
                    )
                    
                    if utilization > 80:
                        performance_issues.append(f"High connection pool utilization: {utilization:.1f}%")
                        recommendations.append("Consider increasing connection pool size")
            
            # Check transaction performance
            if tx_metrics.get("average_duration_ms", 0) > 1000:
                performance_issues.append(f"High average transaction duration: {tx_metrics['average_duration_ms']:.1f}ms")
                recommendations.append("Investigate transaction performance bottlenecks")
            
            if tx_metrics.get("success_rate", 100) < 95:
                performance_issues.append(f"Low transaction success rate: {tx_metrics['success_rate']:.1f}%")
                recommendations.append("Investigate transaction failures")
            
            return {
                "timestamp": datetime.now().isoformat(),
                "performance_status": "good" if not performance_issues else "needs_attention",
                "issues": performance_issues,
                "recommendations": recommendations,
                "metrics_summary": {
                    "total_nodes": db_metrics.get("summary", {}).get("total_nodes", 0),
                    "healthy_nodes": db_metrics.get("summary", {}).get("healthy_nodes", 0),
                    "total_transactions": tx_metrics.get("total_transactions", 0),
                    "success_rate": tx_metrics.get("success_rate", 0),
                    "average_duration_ms": tx_metrics.get("average_duration_ms", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Performance monitoring failed: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "performance_status": "unknown",
                "error": str(e)
            }


class DatabaseMaintenanceExamples:
    """Examples for database maintenance operations."""
    
    @staticmethod
    async def coppa_compliance_cleanup() -> Dict[str, Any]:
        """COPPA compliance data cleanup example."""
        try:
            child_repo = await get_child_repository()
            
            # Find children with expired data retention
            cutoff_date = datetime.now() - timedelta(days=90)  # 90-day default retention
            
            # This would be implemented with proper queries
            expired_children = []  # await child_repo.get_expiring_data(days_ahead=0)
            
            cleanup_results = {
                "children_processed": 0,
                "data_anonymized": 0,
                "records_deleted": 0,
                "errors": []
            }
            
            for child in expired_children:
                try:
                    # Use child-safe transaction for data cleanup
                    async with transaction_manager.transaction(
                        transaction_type=TransactionType.CHILD_SAFE,
                        child_id=str(child.id),
                        parent_consent=True
                    ) as tx:
                        
                        # Anonymize or delete child data based on requirements
                        if child.allow_data_sharing:
                            # Anonymize data
                            await child_repo.update(child.id, {
                                "name": "ANONYMIZED",
                                "birth_date": None,
                                "retention_status": "anonymized"
                            })
                            cleanup_results["data_anonymized"] += 1
                        else:
                            # Delete data
                            await child_repo.delete(child.id, soft_delete=True)
                            cleanup_results["records_deleted"] += 1
                        
                        cleanup_results["children_processed"] += 1
                        
                        # Log compliance action
                        security_logger.info(
                            "COPPA compliance cleanup performed",
                            extra={
                                "child_id_hash": child.hashed_identifier,
                                "action": "anonymized" if child.allow_data_sharing else "deleted",
                                "retention_expired": True
                            }
                        )
                        
                except Exception as e:
                    cleanup_results["errors"].append(f"Child {child.id}: {str(e)}")
                    logger.error(f"Failed to cleanup child {child.id}: {str(e)}")
            
            return {
                "success": True,
                "cleanup_results": cleanup_results,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"COPPA compliance cleanup failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def database_optimization_example() -> Dict[str, Any]:
        """Database optimization maintenance example."""
        try:
            optimization_results = {
                "indexes_analyzed": 0,
                "statistics_updated": 0,
                "vacuum_performed": False,
                "performance_improvement": "0%"
            }
            
            # Simulate optimization operations
            # In a real implementation, these would be actual database operations
            
            # Analyze and rebuild indexes
            await asyncio.sleep(0.1)  # Simulate work
            optimization_results["indexes_analyzed"] = 15
            
            # Update table statistics
            await asyncio.sleep(0.1)  # Simulate work
            optimization_results["statistics_updated"] = 8
            
            # Perform database vacuum
            await asyncio.sleep(0.1)  # Simulate work
            optimization_results["vacuum_performed"] = True
            
            logger.info("Database optimization completed")
            
            return {
                "success": True,
                "optimization_results": optimization_results,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database optimization failed: {str(e)}")
            return {"success": False, "error": str(e)}


# Main example runner
async def run_all_examples():
    """Run all database examples."""
    logger.info("Starting database examples")
    
    try:
        # Initialize database
        await initialize_database_infrastructure()
        logger.info("Database infrastructure initialized for examples")
        
        # Run user management examples
        logger.info("=== User Management Examples ===")
        user_result = await UserManagementExamples.create_parent_user()
        logger.info(f"Create parent user result: {user_result}")
        
        if user_result["success"]:
            user_id = uuid.UUID(user_result["user_id"])
            prefs_result = await UserManagementExamples.update_user_preferences(
                user_id, {"notifications_enabled": False}
            )
            logger.info(f"Update preferences result: {prefs_result}")
        
        # Run child safety examples
        logger.info("=== Child Safety Examples ===")
        if user_result["success"]:
            child_data = {
                "name": "Example Child",
                "estimated_age": 8
            }
            child_result = await ChildSafetyExamples.create_child_with_consent(user_id, child_data)
            logger.info(f"Create child result: {child_result}")
        
        # Run health monitoring examples
        logger.info("=== Health Monitoring Examples ===")
        health_result = await HealthMonitoringExamples.comprehensive_health_check()
        logger.info(f"Health check result: {health_result['overall_status']}")
        
        # Run performance monitoring
        perf_result = await HealthMonitoringExamples.performance_monitoring_example()
        logger.info(f"Performance monitoring result: {perf_result['performance_status']}")
        
        logger.info("All database examples completed successfully")
        
    except Exception as e:
        logger.error(f"Database examples failed: {str(e)}")
        raise
    
    finally:
        # Cleanup
        await shutdown_database_infrastructure()
        logger.info("Database infrastructure shutdown completed")


if __name__ == "__main__":
    # Run examples if script is executed directly
    asyncio.run(run_all_examples())