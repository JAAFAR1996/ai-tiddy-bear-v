"""
Event Bus Usage Examples - Production Integration
===============================================
Comprehensive examples showing how to integrate the event bus
with the AI Teddy Bear application:
- FastAPI application setup
- Event publishing patterns
- Handler customization
- Testing strategies
- Monitoring integration
"""

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime
import uuid

from .event_bus_integration import (
    event_bus_lifespan,
    EventPublishingMiddleware,
    EventPublisher,
    add_event_bus_routes,
    get_event_bus,
    publish_background_event
)
from .event_config import config_manager
from .production_event_bus_advanced import EventPriority
from ..security.security_integration import security_integration


# Pydantic models for API requests
class ChildMessageRequest(BaseModel):
    content: str
    language: str = "en"
    emotion_context: Optional[Dict[str, Any]] = None


class VoiceRecordingRequest(BaseModel):
    audio_url: str
    duration_seconds: float
    quality_score: float = 0.0
    language: str = "en"


class StoryRequest(BaseModel):
    story_type: str
    theme: str = "general"
    age_group: str
    preferences: Dict[str, Any] = {}


class UserRegistrationEvent(BaseModel):
    email: str
    user_type: str
    registration_source: str = "web"
    metadata: Dict[str, Any] = {}


# FastAPI application with event bus integration
def create_app() -> FastAPI:
    """Create FastAPI application with event bus integration."""
    
    # Create app with event bus lifespan management
    app = FastAPI(
        title="AI Teddy Bear API",
        version="1.0.0",
        lifespan=event_bus_lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add event publishing middleware
    app.add_middleware(EventPublishingMiddleware)
    
    # Add event bus management routes
    add_event_bus_routes(app)
    
    return app


# Create app instance
app = create_app()


# Example API endpoints with event publishing
@app.post("/api/child/message")
async def send_child_message(
    request: ChildMessageRequest,
    background_tasks: BackgroundTasks,
    current_user_id: str = "child_123"  # Would come from authentication
):
    """Handle child message and publish event."""
    
    # Validate input for child safety
    validation_result = await security_integration.validate_input(
        {"content": request.content},
        child_safe=True
    )
    
    if not validation_result.is_valid:
        # Publish safety violation event
        await EventPublisher.publish_audit_event(
            event_type="audit.security.violation",
            payload={
                "violation_type": "child_safety",
                "content": request.content[:100],  # Truncated for logging
                "violations": validation_result.child_safety_violations,
                "user_id": current_user_id
            }
        )
        
        raise HTTPException(
            status_code=400,
            detail="Message content not appropriate for children"
        )
    
    # Process the message (AI response logic would go here)
    ai_response = "Thank you for your message! Let me think about that..."
    
    # Publish child interaction event
    correlation_id = str(uuid.uuid4())
    
    event_id = await EventPublisher.publish_child_interaction(
        event_type="child.message.sent",
        payload={
            "content": validation_result.sanitized_value["content"],
            "language": request.language,
            "emotion_context": request.emotion_context,
            "ai_response": ai_response,
            "processing_time": 0.5,
            "safety_checked": True
        },
        user_id=current_user_id,
        correlation_id=correlation_id
    )
    
    return {
        "response": ai_response,
        "event_id": event_id,
        "correlation_id": correlation_id,
        "safety_checked": True
    }


@app.post("/api/child/voice")
async def process_voice_recording(
    request: VoiceRecordingRequest,
    current_user_id: str = "child_123",
    background_tasks: BackgroundTasks = None
):
    """Process voice recording and publish event."""
    
    # Validate audio URL
    url_validation = await security_integration.validate_input(
        {"url": request.audio_url},
        validation_rules={"url": {"pattern": r"^https?://.+"}}
    )
    
    if not url_validation.is_valid:
        raise HTTPException(status_code=400, detail="Invalid audio URL")
    
    # Process voice recording (STT logic would go here)
    transcription = "Hello, I would like to hear a story about dragons!"
    
    # Publish voice interaction event
    event_id = await EventPublisher.publish_child_interaction(
        event_type="child.voice.recorded",
        payload={
            "audio_url": url_validation.sanitized_value["url"],
            "duration_seconds": request.duration_seconds,
            "quality_score": request.quality_score,
            "language": request.language,
            "transcription": transcription,
            "processing_method": "whisper_api"
        },
        user_id=current_user_id
    )
    
    return {
        "transcription": transcription,
        "event_id": event_id,
        "processing_status": "completed"
    }


@app.post("/api/child/story")
async def request_story(
    request: StoryRequest,
    current_user_id: str = "child_123",
    background_tasks: BackgroundTasks = None
):
    """Handle story request and publish event."""
    
    # Validate age group
    age_validation = await security_integration.validate_input(
        {"age_group": request.age_group},
        validation_rules={"age_group": {"pattern": r"^(3-5|6-8|9-12)$"}}
    )
    
    if not age_validation.is_valid:
        raise HTTPException(status_code=400, detail="Invalid age group")
    
    # Generate story (AI story generation would go here)
    story_content = f"Once upon a time, there was a brave little dragon who loved {request.theme}..."
    
    # Publish story request event
    event_id = await EventPublisher.publish_child_interaction(
        event_type="child.story.requested",
        payload={
            "story_type": request.story_type,
            "theme": request.theme,
            "age_group": age_validation.sanitized_value["age_group"],
            "preferences": request.preferences,
            "story_content": story_content,
            "generation_method": "gpt4_creative",
            "content_safety_checked": True
        },
        user_id=current_user_id
    )
    
    return {
        "story": story_content,
        "event_id": event_id,
        "story_type": request.story_type,
        "age_appropriate": True
    }


@app.post("/api/emotion/detected")
async def emotion_detected(
    emotion: str,
    confidence: float,
    context: Dict[str, Any] = {},
    current_user_id: str = "child_123"
):
    """Handle emotion detection and publish event."""
    
    # Validate emotion and confidence
    if emotion not in ["happy", "sad", "excited", "calm", "angry", "frustrated", "scared"]:
        raise HTTPException(status_code=400, detail="Invalid emotion type")
    
    if not 0 <= confidence <= 1:
        raise HTTPException(status_code=400, detail="Confidence must be between 0 and 1")
    
    # Determine priority based on emotion and confidence
    priority = EventPriority.NORMAL
    if confidence > 0.8 and emotion in ["angry", "frustrated", "scared", "sad"]:
        priority = EventPriority.HIGH
    
    # Publish emotion detection event
    event_id = await EventPublisher.publish_child_interaction(
        event_type="child.emotion.detected",
        payload={
            "emotion": emotion,
            "confidence": confidence,
            "context": context,
            "detection_method": "voice_analysis",
            "timestamp": datetime.now().isoformat(),
            "requires_attention": confidence > 0.8 and emotion in ["angry", "scared"]
        },
        user_id=current_user_id
    )
    
    return {
        "emotion_processed": True,
        "event_id": event_id,
        "requires_attention": confidence > 0.8 and emotion in ["angry", "scared"]
    }


@app.post("/api/users/register")
async def register_user(
    user_data: UserRegistrationEvent,
    background_tasks: BackgroundTasks
):
    """Handle user registration and publish event."""
    
    # Validate email
    email_validation = await security_integration.validate_input(
        {"email": user_data.email}
    )
    
    if not email_validation.is_valid:
        raise HTTPException(status_code=400, detail="Invalid email address")
    
    # Create user (database logic would go here)
    user_id = str(uuid.uuid4())
    
    # Publish user registration event
    event_id = await EventPublisher.publish_user_event(
        event_type="user.registered",
        payload={
            "email": email_validation.sanitized_value["email"],
            "user_type": user_data.user_type,
            "registration_source": user_data.registration_source,
            "metadata": user_data.metadata,
            "registration_ip": "1.2.3.4",  # Would get from request
            "email_verified": False
        },
        user_id=user_id
    )
    
    return {
        "user_id": user_id,
        "event_id": event_id,
        "registration_status": "pending_verification"
    }


@app.post("/api/users/{user_id}/login")
async def user_login(
    user_id: str,
    login_data: Dict[str, Any],
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle user login and publish event."""
    
    # Authenticate user (authentication logic would go here)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication failed")
    
    # Get client information
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "")
    
    # Publish login event
    event_id = await EventPublisher.publish_user_event(
        event_type="user.login",
        payload={
            "ip_address": client_ip,
            "user_agent": user_agent,
            "login_method": login_data.get("method", "password"),
            "device_info": {
                "type": "web",
                "platform": "unknown"
            },
            "session_id": str(uuid.uuid4())
        },
        user_id=user_id
    )
    
    return {
        "login_status": "success",
        "event_id": event_id,
        "session_token": "jwt_token_here"
    }


@app.post("/api/admin/system/alert")
async def trigger_system_alert(
    alert_type: str,
    severity: str,
    message: str,
    background_tasks: BackgroundTasks,
    details: Dict[str, Any] = {}
):
    """Trigger system alert (admin endpoint)."""
    
    # Validate severity
    if severity not in ["low", "medium", "high", "critical"]:
        raise HTTPException(status_code=400, detail="Invalid severity level")
    
    # Map severity to event priority
    priority_map = {
        "low": EventPriority.LOW,
        "medium": EventPriority.NORMAL,
        "high": EventPriority.HIGH,
        "critical": EventPriority.CRITICAL
    }
    
    # Publish system event
    event_id = await EventPublisher.publish_system_event(
        event_type=f"system.{alert_type}",
        payload={
            "severity": severity,
            "message": message,
            "details": details,
            "triggered_by": "admin",
            "timestamp": datetime.now().isoformat()
        },
        priority=priority_map[severity]
    )
    
    return {
        "alert_triggered": True,
        "event_id": event_id,
        "severity": severity
    }


# Background task examples
@app.post("/api/analytics/process")
async def process_analytics(background_tasks: BackgroundTasks):
    """Process analytics data in background."""
    
    def analytics_task():
        """Background analytics processing."""
        # Simulate analytics processing
        import time
        time.sleep(2)
        
        # Publish completion event
        asyncio.create_task(
            EventPublisher.publish_system_event(
                event_type="system.analytics.completed",
                payload={
                    "processing_time": 2.0,
                    "records_processed": 1000,
                    "insights_generated": 15
                }
            )
        )
    
    background_tasks.add_task(analytics_task)
    
    return {"analytics_processing": "started"}


# Health check endpoints
@app.get("/health")
async def health_check():
    """Application health check."""
    event_bus = get_event_bus()
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "event_bus": "healthy" if event_bus else "not_initialized"
        }
    }
    
    if event_bus:
        event_bus_health = await event_bus.health_check()
        health_status["components"]["event_bus_details"] = event_bus_health
    
    return health_status


@app.get("/config/validate")
async def validate_configuration():
    """Validate event bus configuration."""
    issues = config_manager.validate_config()
    
    return {
        "configuration_valid": len(issues) == 0,
        "issues": issues,
        "environment": config_manager._environment.value
    }


# Testing utilities
@app.post("/test/events/bulk")
async def bulk_test_events(
    background_tasks: BackgroundTasks,
    count: int = 10,
    event_type: str = "test.event"
):
    """Generate bulk test events for testing."""
    
    if count > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 events per request")
    
    event_ids = []
    
    for i in range(count):
        event_id = await EventPublisher.publish_system_event(
            event_type=event_type,
            payload={
                "test_index": i,
                "batch_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "test_data": {"message": f"Test event {i}"}
            },
            priority=EventPriority.LOW
        )
        
        if event_id:
            event_ids.append(event_id)
    
    return {
        "events_created": len(event_ids),
        "event_ids": event_ids[:10]  # Return first 10 IDs
    }


if __name__ == "__main__":
    import uvicorn
    
    # Development server
    uvicorn.run(
        "usage_examples:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )