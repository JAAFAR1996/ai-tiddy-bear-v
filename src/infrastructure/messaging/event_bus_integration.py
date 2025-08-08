"""
Event Bus Integration - FastAPI Integration Layer
===============================================
Production integration layer for event bus with FastAPI:
- Startup/Shutdown lifecycle management
- Middleware integration
- Event publishing utilities
- Health check endpoints
- Metrics collection
- Configuration management
"""

import asyncio
import os
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from .production_event_bus_advanced import ProductionEventBus, BackendType, EventPriority
from .event_handlers import (
    child_interaction_handler,
    user_management_handler,
    system_monitoring_handler,
    audit_handler
)
from ..resilience.fallback_logger import FallbackLogger, LogContext, EventType


class EventBusLifecycleManager:
    """Manages Event Bus lifecycle for FastAPI application."""
    
    def __init__(self):
        self.event_bus: Optional[ProductionEventBus] = None
        self.logger = FallbackLogger("event_bus_lifecycle")
        self._processing_tasks: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
    
    async def startup(self):
        """Initialize and start the event bus."""
        try:
            # Configuration from environment
            backend_type = BackendType(os.getenv("EVENT_BUS_BACKEND", "hybrid"))
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
            
            # Create event bus instance
            self.event_bus = ProductionEventBus(
                backend_type=backend_type,
                redis_url=redis_url,
                rabbitmq_url=rabbitmq_url
            )
            
            # Register event handlers
            await self._register_handlers()
            
            # Start event processing
            processing_task = asyncio.create_task(self._start_processing())
            self._processing_tasks.append(processing_task)
            
            self.logger.info(
                "Event bus startup completed",
                extra={
                    "backend_type": backend_type.value,
                    "handlers_registered": len(self.event_bus._handlers)
                }
            )
            
        except Exception as e:
            self.logger.error(f"Event bus startup failed: {str(e)}")
            raise
    
    async def shutdown(self):
        """Gracefully shutdown the event bus."""
        try:
            self.logger.info("Starting event bus shutdown...")
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Cancel processing tasks
            for task in self._processing_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            if self._processing_tasks:
                await asyncio.gather(*self._processing_tasks, return_exceptions=True)
            
            # Shutdown event bus
            if self.event_bus:
                await self.event_bus.shutdown()
            
            self.logger.info("Event bus shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Event bus shutdown error: {str(e)}")
    
    async def _register_handlers(self):
        """Register all event handlers with the event bus."""
        if not self.event_bus:
            return
        
        # Child interaction events
        self.event_bus.register_handler("child.message.sent", child_interaction_handler)
        self.event_bus.register_handler("child.voice.recorded", child_interaction_handler)
        self.event_bus.register_handler("child.story.requested", child_interaction_handler)
        self.event_bus.register_handler("child.emotion.detected", child_interaction_handler)
        self.event_bus.register_handler("child.learning.progress", child_interaction_handler)
        
        # User management events
        self.event_bus.register_handler("user.registered", user_management_handler)
        self.event_bus.register_handler("user.login", user_management_handler)
        self.event_bus.register_handler("user.logout", user_management_handler)
        self.event_bus.register_handler("user.profile.updated", user_management_handler)
        self.event_bus.register_handler("user.subscription.changed", user_management_handler)
        self.event_bus.register_handler("user.deleted", user_management_handler)
        
        # System monitoring events
        self.event_bus.register_handler("system.health.degraded", system_monitoring_handler)
        self.event_bus.register_handler("system.health.recovered", system_monitoring_handler)
        self.event_bus.register_handler("system.performance.alert", system_monitoring_handler)
        self.event_bus.register_handler("system.error.critical", system_monitoring_handler)
        self.event_bus.register_handler("system.capacity.warning", system_monitoring_handler)
        
        # Audit events
        self.event_bus.register_handler("audit.data.access", audit_handler)
        self.event_bus.register_handler("audit.data.modification", audit_handler)
        self.event_bus.register_handler("audit.security.violation", audit_handler)
        self.event_bus.register_handler("audit.compliance.check", audit_handler)
        self.event_bus.register_handler("audit.admin.action", audit_handler)
        
        self.logger.info(f"Registered {len(self.event_bus._handlers)} event handler mappings")
    
    async def _start_processing(self):
        """Start event processing loop."""
        if not self.event_bus:
            return
        
        try:
            # Wait for shutdown signal or processing completion
            processing_task = asyncio.create_task(self.event_bus.start_processing())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())
            
            done, pending = await asyncio.wait(
                [processing_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                
        except asyncio.CancelledError:
            self.logger.info("Event processing cancelled")
        except Exception as e:
            self.logger.error(f"Event processing error: {str(e)}")


# Global lifecycle manager
lifecycle_manager = EventBusLifecycleManager()


@asynccontextmanager
async def event_bus_lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI event bus integration."""
    # Startup
    await lifecycle_manager.startup()
    
    try:
        yield
    finally:
        # Shutdown
        await lifecycle_manager.shutdown()


class EventPublishingMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically publish events for requests."""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = FallbackLogger("event_middleware")
    
    async def dispatch(self, request: Request, call_next):
        """Process request and publish relevant events."""
        start_time = asyncio.get_event_loop().time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = asyncio.get_event_loop().time() - start_time
        
        # Publish system events asynchronously
        asyncio.create_task(self._publish_request_events(request, response, process_time))
        
        return response
    
    async def _publish_request_events(self, request: Request, response: Response, process_time: float):
        """Publish events related to the request."""
        try:
            if not lifecycle_manager.event_bus:
                return
            
            # Performance monitoring event
            if process_time > 2.0:  # Slow request threshold
                await lifecycle_manager.event_bus.publish_event(
                    event_type="system.performance.alert",
                    payload={
                        "metric_name": "request_duration",
                        "current_value": process_time,
                        "threshold": 2.0,
                        "endpoint": str(request.url.path),
                        "method": request.method,
                        "status_code": response.status_code
                    },
                    source_service="api_gateway",
                    priority=EventPriority.HIGH
                )
            
            # Error event for 5xx responses
            if 500 <= response.status_code < 600:
                await lifecycle_manager.event_bus.publish_event(
                    event_type="system.error.critical",
                    payload={
                        "error_type": "http_5xx",
                        "status_code": response.status_code,
                        "endpoint": str(request.url.path),
                        "method": request.method,
                        "user_agent": request.headers.get("User-Agent", ""),
                        "ip_address": self._get_client_ip(request)
                    },
                    source_service="api_gateway",
                    priority=EventPriority.CRITICAL
                )
        
        except Exception as e:
            self.logger.error(f"Failed to publish request events: {str(e)}")
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"


class EventPublisher:
    """Utility class for publishing events from API endpoints."""
    
    @staticmethod
    async def publish_child_interaction(
        event_type: str,
        payload: Dict[str, Any],
        user_id: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Optional[str]:
        """Publish child interaction event."""
        if not lifecycle_manager.event_bus:
            return None
        
        try:
            return await lifecycle_manager.event_bus.publish_event(
                event_type=event_type,
                payload=payload,
                source_service="api_child_interaction",
                user_id=user_id,
                correlation_id=correlation_id,
                priority=EventPriority.NORMAL
            )
        except Exception as e:
            FallbackLogger("event_publisher").error(f"Failed to publish child interaction event: {str(e)}")
            return None
    
    @staticmethod
    async def publish_user_event(
        event_type: str,
        payload: Dict[str, Any],
        user_id: str,
        correlation_id: Optional[str] = None
    ) -> Optional[str]:
        """Publish user management event."""
        if not lifecycle_manager.event_bus:
            return None
        
        try:
            return await lifecycle_manager.event_bus.publish_event(
                event_type=event_type,
                payload=payload,
                source_service="api_user_management",
                user_id=user_id,
                correlation_id=correlation_id,
                priority=EventPriority.NORMAL
            )
        except Exception as e:
            FallbackLogger("event_publisher").error(f"Failed to publish user event: {str(e)}")
            return None
    
    @staticmethod
    async def publish_audit_event(
        event_type: str,
        payload: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """Publish audit event."""
        if not lifecycle_manager.event_bus:
            return None
        
        try:
            return await lifecycle_manager.event_bus.publish_event(
                event_type=event_type,
                payload=payload,
                source_service="api_audit",
                user_id=user_id,
                priority=EventPriority.HIGH
            )
        except Exception as e:
            FallbackLogger("event_publisher").error(f"Failed to publish audit event: {str(e)}")
            return None
    
    @staticmethod
    async def publish_system_event(
        event_type: str,  
        payload: Dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL
    ) -> Optional[str]:
        """Publish system monitoring event."""
        if not lifecycle_manager.event_bus:
            return None
        
        try:
            return await lifecycle_manager.event_bus.publish_event(
                event_type=event_type,
                payload=payload,
                source_service="system_monitor",
                priority=priority
            )
        except Exception as e:
            FallbackLogger("event_publisher").error(f"Failed to publish system event: {str(e)}")
            return None


def add_event_bus_routes(app: FastAPI):
    """Add event bus management routes to FastAPI app."""
    
    @app.get("/admin/eventbus/health")
    async def event_bus_health():
        """Get event bus health status."""
        if not lifecycle_manager.event_bus:
            return {"status": "not_initialized"}
        
        return await lifecycle_manager.event_bus.health_check()
    
    @app.get("/admin/eventbus/metrics")
    async def event_bus_metrics():
        """Get event bus metrics."""
        if not lifecycle_manager.event_bus:
            return {"error": "Event bus not initialized"}
        
        return lifecycle_manager.event_bus.get_metrics()
    
    @app.post("/admin/eventbus/replay")
    async def replay_events(
        correlation_id: str,
        from_timestamp: Optional[str] = None,
        to_timestamp: Optional[str] = None
    ):
        """Replay events for event sourcing."""
        if not lifecycle_manager.event_bus:
            return {"error": "Event bus not initialized"}
        
        from datetime import datetime
        
        from_dt = datetime.fromisoformat(from_timestamp) if from_timestamp else None
        to_dt = datetime.fromisoformat(to_timestamp) if to_timestamp else None
        
        events = await lifecycle_manager.event_bus.replay_events(
            correlation_id=correlation_id,
            from_timestamp=from_dt,
            to_timestamp=to_dt
        )
        
        return {
            "correlation_id": correlation_id,
            "events_count": len(events),
            "events": [event.to_message() for event in events]
        }
    
    @app.post("/admin/eventbus/test")
    async def test_event_publishing(background_tasks: BackgroundTasks):
        """Test event publishing (for development/testing)."""
        if not lifecycle_manager.event_bus:
            return {"error": "Event bus not initialized"}
        
        # Publish a test event
        event_id = await EventPublisher.publish_system_event(
            event_type="system.test.event",
            payload={
                "test": True,
                "timestamp": datetime.now().isoformat(),
                "message": "Test event from admin endpoint"
            },
            priority=EventPriority.LOW
        )
        
        return {
            "status": "test_event_published",
            "event_id": event_id
        }


# Utility functions for FastAPI integration
def get_event_bus() -> Optional[ProductionEventBus]:
    """Get the global event bus instance."""
    return lifecycle_manager.event_bus


def publish_background_event(
    background_tasks: BackgroundTasks,
    event_type: str,
    payload: Dict[str, Any],
    source_service: str,
    user_id: Optional[str] = None,
    priority: EventPriority = EventPriority.NORMAL
):
    """Publish event as a background task."""
    async def _publish():
        if lifecycle_manager.event_bus:
            await lifecycle_manager.event_bus.publish_event(
                event_type=event_type,
                payload=payload,
                source_service=source_service,
                user_id=user_id,
                priority=priority
            )
    
    background_tasks.add_task(_publish)
