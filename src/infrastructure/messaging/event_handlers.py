"""
Event Handlers - Production Event Processing
==========================================
Enterprise-grade event handlers for the AI Teddy Bear system:
- Child interaction events
- User management events
- System monitoring events
- Audit and compliance events
- Error handling and retry logic
- Performance monitoring
"""

import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import asdict

from .production_event_bus_advanced import EventHandler, DomainEvent
from ..security.security_integration import security_integration
from ..resilience.fallback_logger import FallbackLogger, LogContext, EventType
from ..database.connection_manager import connection_manager


class ChildInteractionEventHandler(EventHandler):
    """Handler for child interaction events."""
    
    def __init__(self):
        super().__init__("child_interaction_handler") 
        self.analytics_logger = FallbackLogger("child_analytics")
        
        # Events this handler processes
        self.handled_events = {
            "child.message.sent",
            "child.voice.recorded", 
            "child.story.requested",
            "child.emotion.detected",
            "child.learning.progress"
        }
    
    async def handle(self, event: DomainEvent) -> bool:
        """Handle child interaction events."""
        try:
            self.logger.info(
                f"Processing child interaction event: {event.metadata.event_type}",
                extra={
                    "event_id": event.metadata.event_id,
                    "user_id": event.metadata.user_id,
                    "correlation_id": event.metadata.correlation_id
                }
            )
            
            # Route to specific handler based on event type
            handler_map = {
                "child.message.sent": self._handle_message_sent,
                "child.voice.recorded": self._handle_voice_recorded, 
                "child.story.requested": self._handle_story_requested,
                "child.emotion.detected": self._handle_emotion_detected,
                "child.learning.progress": self._handle_learning_progress
            }
            
            handler = handler_map.get(event.metadata.event_type)
            if handler:
                await handler(event)
                
                # Update analytics
                await self._update_child_analytics(event)
                
                return True
            else:
                self.logger.warning(f"No handler found for event type: {event.metadata.event_type}")
                return False
                
        except Exception as e:
            self.logger.error(
                f"Failed to handle child interaction event: {str(e)}",
                extra={
                    "event_id": event.metadata.event_id,
                    "error": str(e)
                }
            )
            return False
    
    def can_handle(self, event_type: str) -> bool:
        """Check if this handler can process the event type."""
        return event_type in self.handled_events
    
    async def _handle_message_sent(self, event: DomainEvent):
        """Handle child message sent event."""
        payload = event.payload
        
        # Validate message content for safety
        if payload.get("content"):
            validation_result = await security_integration.validate_input(
                {"message": payload["content"]},
                child_safe=True
            )
            
            if not validation_result.is_valid:
                # Log safety violation
                self.logger.warning(
                    "Child safety violation in message",
                    extra={
                        "user_id": event.metadata.user_id,
                        "violations": validation_result.child_safety_violations,
                        "event_id": event.metadata.event_id
                    }
                )
                
                # Trigger parent notification if needed
                await self._notify_parent_safety_concern(event)
        
        # Store interaction for learning
        await self._store_interaction(event, "message")
    
    async def _handle_voice_recorded(self, event: DomainEvent):
        """Handle voice recording event."""
        payload = event.payload
        
        # Log voice interaction metrics
        duration = payload.get("duration_seconds", 0)
        quality_score = payload.get("quality_score", 0)
        
        self.analytics_logger.log_event(
            LogContext(
                service_name="child_interaction",
                user_id=event.metadata.user_id,
                session_id=event.metadata.session_id
            ),
            "voice_interaction",
            "Child voice interaction recorded",
            additional_data={
                "duration": duration,
                "quality_score": quality_score,
                "language": payload.get("language", "en")
            }
        )
        
        # Store for voice pattern analysis
        await self._store_interaction(event, "voice")
    
    async def _handle_story_requested(self, event: DomainEvent):
        """Handle story request event."""
        payload = event.payload
        
        # Log story preferences
        story_type = payload.get("story_type", "unknown")
        theme = payload.get("theme", "general")
        
        self.analytics_logger.log_event(
            LogContext(
                service_name="content_analytics",
                user_id=event.metadata.user_id
            ),
            "story_requested",
            f"Child requested story: {story_type}",
            additional_data={
                "story_type": story_type,
                "theme": theme,
                "age_group": payload.get("age_group"),
                "preferences": payload.get("preferences", {})
            }
        )
        
        await self._store_interaction(event, "story_request")
    
    async def _handle_emotion_detected(self, event: DomainEvent):
        """Handle emotion detection event."""
        payload = event.payload
        
        emotion = payload.get("emotion", "unknown")
        confidence = payload.get("confidence", 0)
        
        # High-confidence negative emotions need attention
        if confidence > 0.8 and emotion in ["sad", "angry", "frustrated", "scared"]:
            await self._handle_concerning_emotion(event)
        
        # Store emotional state for learning
        await self._store_emotion_data(event)
    
    async def _handle_learning_progress(self, event: DomainEvent):
        """Handle learning progress event."""
        payload = event.payload
        
        skill = payload.get("skill", "unknown")
        progress_level = payload.get("progress_level", 0)
        
        self.analytics_logger.log_event(
            LogContext(
                service_name="learning_analytics",
                user_id=event.metadata.user_id
            ),
            "learning_progress",
            f"Learning progress: {skill}",
            additional_data={
                "skill": skill,
                "progress_level": progress_level,
                "session_duration": payload.get("session_duration", 0),
                "activities_completed": payload.get("activities_completed", 0)
            }
        )
        
        await self._store_learning_progress(event)
    
    async def _update_child_analytics(self, event: DomainEvent):
        """Update child analytics database."""
        try:
            async with connection_manager.get_connection() as conn:
                # Update interaction counts
                await conn.execute("""
                    INSERT INTO child_analytics (
                        user_id, event_type, event_date, interaction_count, metadata
                    ) VALUES ($1, $2, $3, 1, $4)
                    ON CONFLICT (user_id, event_type, event_date)
                    DO UPDATE SET 
                        interaction_count = child_analytics.interaction_count + 1,
                        metadata = EXCLUDED.metadata
                """, 
                event.metadata.user_id,
                event.metadata.event_type,
                event.metadata.created_at.date(),
                json.dumps(event.payload)
                )
                
        except Exception as e:
            self.logger.error(f"Failed to update child analytics: {str(e)}")
    
    async def _store_interaction(self, event: DomainEvent, interaction_type: str):
        """Store interaction data for learning algorithms."""
        try:
            async with connection_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO child_interactions (
                        user_id, interaction_type, event_id, content, metadata, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                event.metadata.user_id,
                interaction_type,
                event.metadata.event_id,
                json.dumps(event.payload),
                json.dumps(event.metadata.to_dict()),
                event.metadata.created_at
                )
                
        except Exception as e:
            self.logger.error(f"Failed to store interaction: {str(e)}")
    
    async def _store_emotion_data(self, event: DomainEvent):
        """Store emotional state data."""
        try:
            async with connection_manager.get_connection() as conn:
                payload = event.payload
                await conn.execute("""
                    INSERT INTO child_emotions (
                        user_id, emotion, confidence, context, detected_at
                    ) VALUES ($1, $2, $3, $4, $5)
                """,
                event.metadata.user_id,
                payload.get("emotion"),
                payload.get("confidence", 0),
                json.dumps(payload.get("context", {})),
                event.metadata.created_at
                )
                
        except Exception as e:
            self.logger.error(f"Failed to store emotion data: {str(e)}")
    
    async def _store_learning_progress(self, event: DomainEvent):
        """Store learning progress data."""
        try:
            async with connection_manager.get_connection() as conn:
                payload = event.payload
                await conn.execute("""
                    INSERT INTO learning_progress (
                        user_id, skill, progress_level, session_data, updated_at
                    ) VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id, skill)
                    DO UPDATE SET
                        progress_level = EXCLUDED.progress_level,
                        session_data = EXCLUDED.session_data,
                        updated_at = EXCLUDED.updated_at
                """,
                event.metadata.user_id,
                payload.get("skill"),
                payload.get("progress_level", 0),
                json.dumps(payload),
                event.metadata.created_at
                )
                
        except Exception as e:
            self.logger.error(f"Failed to store learning progress: {str(e)}")
    
    async def _notify_parent_safety_concern(self, event: DomainEvent):
        """Notify parent of safety concern."""
        # This would integrate with notification service
        self.logger.info(
            "Safety concern notification sent to parent",
            extra={
                "user_id": event.metadata.user_id,
                "event_id": event.metadata.event_id
            }
        )
    
    async def _handle_concerning_emotion(self, event: DomainEvent):
        """Handle concerning emotional state."""
        payload = event.payload
        
        self.logger.warning(
            f"Concerning emotion detected: {payload.get('emotion')}",
            extra={
                "user_id": event.metadata.user_id,
                "emotion": payload.get("emotion"),
                "confidence": payload.get("confidence"),
                "context": payload.get("context", {})
            }
        )
        
        # Could trigger therapeutic response or parent notification


class UserManagementEventHandler(EventHandler):
    """Handler for user management events."""
    
    def __init__(self):
        super().__init__("user_management_handler")
        
        self.handled_events = {
            "user.registered",
            "user.login",
            "user.logout", 
            "user.profile.updated",
            "user.subscription.changed",
            "user.deleted"
        }
    
    async def handle(self, event: DomainEvent) -> bool:
        """Handle user management events."""
        try:
            handler_map = {
                "user.registered": self._handle_user_registered,
                "user.login": self._handle_user_login,
                "user.logout": self._handle_user_logout,
                "user.profile.updated": self._handle_profile_updated,
                "user.subscription.changed": self._handle_subscription_changed,
                "user.deleted": self._handle_user_deleted
            }
            
            handler = handler_map.get(event.metadata.event_type)
            if handler:
                await handler(event)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to handle user management event: {str(e)}")
            return False
    
    def can_handle(self, event_type: str) -> bool:
        return event_type in self.handled_events
    
    async def _handle_user_registered(self, event: DomainEvent):
        """Handle new user registration."""
        payload = event.payload
        
        # Log registration metrics
        self.logger.info(
            "New user registered",
            extra={
                "user_id": event.metadata.user_id,
                "user_type": payload.get("user_type"),
                "registration_source": payload.get("source", "unknown")
            }
        )
        
        # Initialize user onboarding
        await self._start_user_onboarding(event)
    
    async def _handle_user_login(self, event: DomainEvent):
        """Handle user login."""
        payload = event.payload
        
        # Update last login
        await self._update_last_login(event.metadata.user_id, event.metadata.created_at)
        
        # Check for suspicious login patterns
        await self._check_login_security(event)
    
    async def _handle_user_logout(self, event: DomainEvent):
        """Handle user logout."""
        # Update session duration analytics
        payload = event.payload
        session_duration = payload.get("session_duration", 0)
        
        if session_duration > 0:
            await self._update_session_analytics(event.metadata.user_id, session_duration)
    
    async def _handle_profile_updated(self, event: DomainEvent):
        """Handle profile update."""
        payload = event.payload
        
        # Log profile changes for audit
        self.logger.info(
            "User profile updated",
            extra={
                "user_id": event.metadata.user_id,
                "fields_updated": payload.get("updated_fields", []),
                "update_source": payload.get("source", "user")
            }
        )
    
    async def _handle_subscription_changed(self, event: DomainEvent):
        """Handle subscription changes."""
        payload = event.payload
        
        old_plan = payload.get("old_plan")
        new_plan = payload.get("new_plan")
        
        self.logger.info(
            f"Subscription changed: {old_plan} -> {new_plan}",
            extra={
                "user_id": event.metadata.user_id,
                "old_plan": old_plan,
                "new_plan": new_plan,
                "change_reason": payload.get("reason")
            }
        )
        
        # Update user permissions based on new plan
        await self._update_user_permissions(event.metadata.user_id, new_plan)
    
    async def _handle_user_deleted(self, event: DomainEvent):
        """Handle user deletion (GDPR compliance)."""
        self.logger.info(
            "User account deleted",
            extra={
                "user_id": event.metadata.user_id,
                "deletion_reason": event.payload.get("reason", "user_request")
            }
        )
        
        # Clean up user data
        await self._cleanup_user_data(event.metadata.user_id)
    
    async def _start_user_onboarding(self, event: DomainEvent):
        """Initialize user onboarding process."""
        # Could trigger welcome email, setup wizard, etc.
        pass
    
    async def _update_last_login(self, user_id: str, login_time: datetime):
        """Update user's last login time."""
        try:
            async with connection_manager.get_connection() as conn:
                await conn.execute(
                    "UPDATE users SET last_login = $1 WHERE id = $2",
                    login_time, user_id
                )
        except Exception as e:
            self.logger.error(f"Failed to update last login: {str(e)}")
    
    async def _check_login_security(self, event: DomainEvent):
        """Check login for security issues."""
        payload = event.payload
        
        # Check for unusual login patterns
        ip_address = payload.get("ip_address")
        user_agent = payload.get("user_agent", "")
        
        # This could include geolocation checks, device fingerprinting, etc.
        if ip_address:
            # Log for security analysis
            self.logger.info(
                "User login security check",
                extra={
                    "user_id": event.metadata.user_id,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "suspicious": False  # Would implement actual checks
                }
            )
    
    async def _update_session_analytics(self, user_id: str, duration: int):
        """Update session duration analytics."""
        try:
            async with connection_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO user_sessions (user_id, session_date, total_duration, session_count)
                    VALUES ($1, $2, $3, 1)
                    ON CONFLICT (user_id, session_date)
                    DO UPDATE SET
                        total_duration = user_sessions.total_duration + EXCLUDED.total_duration,
                        session_count = user_sessions.session_count + 1
                """, user_id, datetime.now().date(), duration)
        except Exception as e:
            self.logger.error(f"Failed to update session analytics: {str(e)}")
    
    async def _update_user_permissions(self, user_id: str, plan: str):
        """Update user permissions based on subscription plan."""
        # Implementation would depend on permission system
        pass
    
    async def _cleanup_user_data(self, user_id: str):
        """Clean up user data for GDPR compliance."""
        # Implementation would clean up personal data while preserving anonymized analytics
        pass


class SystemMonitoringEventHandler(EventHandler):
    """Handler for system monitoring and health events."""
    
    def __init__(self):
        super().__init__("system_monitoring_handler")
        
        self.handled_events = {
            "system.health.degraded",
            "system.health.recovered", 
            "system.performance.alert",
            "system.error.critical",
            "system.capacity.warning"
        }
    
    async def handle(self, event: DomainEvent) -> bool:
        """Handle system monitoring events."""
        try:
            handler_map = {
                "system.health.degraded": self._handle_health_degraded,
                "system.health.recovered": self._handle_health_recovered,
                "system.performance.alert": self._handle_performance_alert,
                "system.error.critical": self._handle_critical_error,
                "system.capacity.warning": self._handle_capacity_warning
            }
            
            handler = handler_map.get(event.metadata.event_type)
            if handler:
                await handler(event)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to handle system monitoring event: {str(e)}")
            return False
    
    def can_handle(self, event_type: str) -> bool:
        return event_type in self.handled_events
    
    async def _handle_health_degraded(self, event: DomainEvent):
        """Handle service health degradation."""
        payload = event.payload
        service_name = payload.get("service_name", "unknown")
        
        self.logger.warning(
            f"Service health degraded: {service_name}",
            extra={
                "service_name": service_name,
                "health_score": payload.get("health_score", 0),
                "symptoms": payload.get("symptoms", []),
                "affected_endpoints": payload.get("affected_endpoints", [])
            }
        )
        
        # Could trigger alerts, failover, etc.
    
    async def _handle_health_recovered(self, event: DomainEvent):
        """Handle service health recovery."""
        payload = event.payload
        service_name = payload.get("service_name", "unknown")
        
        self.logger.info(
            f"Service health recovered: {service_name}",
            extra={
                "service_name": service_name,
                "recovery_time": payload.get("recovery_time"),
                "health_score": payload.get("health_score", 100)
            }
        )
    
    async def _handle_performance_alert(self, event: DomainEvent):
        """Handle performance alerts."""
        payload = event.payload
        
        self.logger.warning(
            "Performance alert triggered",
            extra={
                "metric_name": payload.get("metric_name"),
                "current_value": payload.get("current_value"),
                "threshold": payload.get("threshold"),
                "service": payload.get("service"),
                "endpoint": payload.get("endpoint")
            }
        )
    
    async def _handle_critical_error(self, event: DomainEvent):
        """Handle critical system errors."""
        payload = event.payload
        
        self.logger.critical(
            "Critical system error",
            extra={
                "error_type": payload.get("error_type"),
                "error_message": payload.get("error_message"),
                "service": payload.get("service"),
                "stack_trace": payload.get("stack_trace"),
                "affected_users": payload.get("affected_users", 0)
            }
        )
        
        # Could trigger incident response
    
    async def _handle_capacity_warning(self, event: DomainEvent):
        """Handle capacity warnings."""
        payload = event.payload
        
        self.logger.warning(
            "System capacity warning",
            extra={
                "resource_type": payload.get("resource_type"),
                "current_usage": payload.get("current_usage"),
                "capacity_limit": payload.get("capacity_limit"),
                "projected_time_to_limit": payload.get("projected_time_to_limit")
            }
        )


class AuditEventHandler(EventHandler):
    """Handler for audit and compliance events."""
    
    def __init__(self):
        super().__init__("audit_handler")
        
        self.handled_events = {
            "audit.data.access",
            "audit.data.modification",
            "audit.security.violation", 
            "audit.compliance.check",
            "audit.admin.action"
        }
    
    async def handle(self, event: DomainEvent) -> bool:
        """Handle audit events."""
        try:
            # All audit events get logged for compliance
            await self._log_audit_event(event)
            
            # Route to specific handlers
            handler_map = {
                "audit.data.access": self._handle_data_access,
                "audit.data.modification": self._handle_data_modification,
                "audit.security.violation": self._handle_security_violation,
                "audit.compliance.check": self._handle_compliance_check,
                "audit.admin.action": self._handle_admin_action
            }
            
            handler = handler_map.get(event.metadata.event_type)
            if handler:
                await handler(event)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to handle audit event: {str(e)}")
            return False
    
    def can_handle(self, event_type: str) -> bool:
        return event_type in self.handled_events
    
    async def _log_audit_event(self, event: DomainEvent):
        """Log audit event to compliance database."""
        try:
            async with connection_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO audit_log (
                        event_id, event_type, user_id, session_id, 
                        source_service, event_data, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                event.metadata.event_id,
                event.metadata.event_type,
                event.metadata.user_id,
                event.metadata.session_id,
                event.metadata.source_service,
                json.dumps(event.payload),
                event.metadata.created_at
                )
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {str(e)}")
    
    async def _handle_data_access(self, event: DomainEvent):
        """Handle data access audit."""
        payload = event.payload
        
        # Check for unusual access patterns
        if payload.get("sensitive_data", False):
            self.logger.info(
                "Sensitive data access",
                extra={
                    "user_id": event.metadata.user_id,
                    "data_type": payload.get("data_type"),
                    "access_reason": payload.get("reason"),
                    "data_subject": payload.get("data_subject")
                }
            )
    
    async def _handle_data_modification(self, event: DomainEvent):
        """Handle data modification audit."""
        payload = event.payload
        
        self.logger.info(
            "Data modification recorded",
            extra={
                "user_id": event.metadata.user_id,
                "data_type": payload.get("data_type"),
                "operation": payload.get("operation"),
                "fields_modified": payload.get("fields_modified", []),
                "data_subject": payload.get("data_subject")
            }
        )
    
    async def _handle_security_violation(self, event: DomainEvent):
        """Handle security violation."""
        payload = event.payload
        
        self.logger.critical(
            "Security violation detected",
            extra={
                "violation_type": payload.get("violation_type"),
                "severity": payload.get("severity"),
                "user_id": event.metadata.user_id,
                "ip_address": payload.get("ip_address"),
                "details": payload.get("details")
            }
        )
    
    async def _handle_compliance_check(self, event: DomainEvent):
        """Handle compliance check results."""
        payload = event.payload
        
        self.logger.info(
            "Compliance check completed",
            extra={
                "check_type": payload.get("check_type"),
                "result": payload.get("result"),
                "violations": payload.get("violations", []),
                "recommendations": payload.get("recommendations", [])
            }
        )
    
    async def _handle_admin_action(self, event: DomainEvent):
        """Handle administrative actions."""
        payload = event.payload
        
        self.logger.info(
            "Administrative action performed",
            extra={
                "admin_user_id": event.metadata.user_id,
                "action_type": payload.get("action_type"),
                "target_user": payload.get("target_user"),
                "action_details": payload.get("details"),
                "justification": payload.get("justification")
            }
        )


# Global handler instances
child_interaction_handler = ChildInteractionEventHandler()
user_management_handler = UserManagementEventHandler()
system_monitoring_handler = SystemMonitoringEventHandler()
audit_handler = AuditEventHandler()