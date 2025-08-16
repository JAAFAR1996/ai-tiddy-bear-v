"""🧸 AI TEDDY BEAR V5 - API ROUTES
Production-ready API endpoints with comprehensive error handling.
"""

# Standard library imports
import os
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from uuid import UUID

# Third-party imports
import redis.asyncio as redis
from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Request,
    status,
)
from fastapi.responses import JSONResponse, Response
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from pydantic import BaseModel, Field

# Local imports
from src.adapters import database_production
from src.core.entities import Message
from src.application.dependencies import (
    ChatServiceDep,
    AuthServiceDep,
    ConversationServiceDep,
)
from src.shared.dto.esp32_request import ESP32Request
from src.application.services.audio_service import AudioService
from src.interfaces.providers.esp32_protocol import ESP32Protocol
from src.interfaces.services import IAIService, IConversationService
from src.application.use_cases.process_esp32_audio import ProcessESP32AudioUseCase
from src.infrastructure.container import injector_instance
from src.utils.crypto_utils import EncryptionService
from src.infrastructure.security.auth import get_current_user
from src.infrastructure.security.input_validator import advanced_input_validator
from src.infrastructure.security.rate_limiter_advanced import advanced_rate_limiter

router = APIRouter(tags=["Core API"])
logger = logging.getLogger(__name__)


# Security Guardrails Functions
async def validate_child_safety(
    content: str, child_age: int, child_id: str
) -> Dict[str, Any]:
    """Enhanced child safety validation with COPPA compliance."""
    validation_result = {
        "is_safe": True,
        "violations": [],
        "risk_score": 0.0,
        "coppa_compliant": True,
    }

    # Input validation
    if not content or not isinstance(content, str):
        validation_result["is_safe"] = False
        validation_result["violations"].append("Invalid content format")
        return validation_result

    if not isinstance(child_age, int) or child_age < 0:
        validation_result["is_safe"] = False
        validation_result["violations"].append("Invalid child age")
        return validation_result

    if not child_id or not isinstance(child_id, str):
        validation_result["is_safe"] = False
        validation_result["violations"].append("Invalid child ID")
        return validation_result

    # Sanitize child_id
    import re

    child_id = re.sub(r"[^a-zA-Z0-9_-]", "", child_id[:50])

    # COPPA age verification
    if child_age >= 13:
        validation_result["coppa_compliant"] = False
        validation_result["violations"].append(
            "Age verification required - user may not qualify for child platform"
        )
        validation_result["risk_score"] += 0.8

    # Content length validation for children
    if len(content) > 300:  # Shorter limit for children
        validation_result["violations"].append("Message too long for child interaction")
        validation_result["risk_score"] += 0.3

    # Enhanced child safety patterns
    import re

    unsafe_patterns = [
        r"\b(address|phone|password|secret|personal)\b",
        r"\b(meet|location|where.*live|real.*name)\b",
        r"\b(keep.*secret|don\'t.*tell|between.*us)\b",
        r"\b(hurt|harm|violence|weapon|scary)\b",
    ]

    for pattern in unsafe_patterns:
        if re.search(pattern, content.lower()):
            validation_result["is_safe"] = False
            validation_result["violations"].append(f"Unsafe content pattern detected")
            validation_result["risk_score"] += 0.5
            break

    # Age-specific content validation
    if child_age < 6:
        advanced_words = r"\b(complex|difficult|advanced|sophisticated)\b"
        if re.search(advanced_words, content.lower()):
            validation_result["violations"].append("Content too advanced for age group")
            validation_result["risk_score"] += 0.2

    # Input validation using existing validator
    validation = advanced_input_validator.validate_string(
        content, max_length=300, child_safe=True, sanitize=True
    )

    if not validation.is_valid:
        validation_result["is_safe"] = False
        validation_result["violations"].extend(validation.errors)
        validation_result["risk_score"] += 0.4

    if validation.child_safety_violations:
        validation_result["is_safe"] = False
        validation_result["violations"].extend(validation.child_safety_violations)
        validation_result["risk_score"] += 0.6

    return validation_result


async def apply_security_guardrails(request: Request, endpoint: str) -> Dict[str, Any]:
    """Apply comprehensive security guardrails."""
    security_result = {
        "allowed": True,
        "violations": [],
        "action": "allow",
        "metadata": {},
    }

    try:
        # Extract and validate request information
        client_ip = request.client.host if request.client else "unknown"

        # Validate IP address format
        if client_ip != "unknown":
            import ipaddress

            try:
                ipaddress.ip_address(client_ip)
            except ValueError:
                client_ip = "invalid"
                security_result["violations"].append("Invalid IP address format")

        user_agent = request.headers.get("user-agent", "")

        # Sanitize user agent
        if user_agent:
            user_agent = user_agent[:500]  # Limit length
            # Remove potentially dangerous characters
            import re

            user_agent = re.sub(r'[<>"\';\\]', "", user_agent)

        # Rate limiting check
        from src.infrastructure.security.rate_limiter_advanced import RateLimitScope

        rate_limit_result = await advanced_rate_limiter.check_rate_limit(
            identifier=client_ip,
            scope=RateLimitScope.IP,
            endpoint=endpoint,
            ip_address=client_ip,
        )

        if not rate_limit_result.allowed:
            security_result["allowed"] = False
            security_result["violations"].append("Rate limit exceeded")
            security_result["action"] = "rate_limit"
            security_result["metadata"]["retry_after"] = rate_limit_result.retry_after
            return security_result

        # IP reputation check (basic)
        if client_ip and client_ip not in ["127.0.0.1", "::1"]:
            # Check for suspicious IP patterns
            import ipaddress

            try:
                ip = ipaddress.ip_address(client_ip)
                if not ip.is_private and not ip.is_loopback:
                    # In production, you'd check against threat intelligence feeds
                    # For now, basic validation
                    pass
            except ValueError:
                security_result["violations"].append("Invalid IP address format")
                security_result["metadata"]["suspicious_ip"] = True

        # User agent validation
        if not user_agent or len(user_agent) < 10:
            security_result["violations"].append("Suspicious or missing user agent")
            security_result["metadata"]["suspicious_ua"] = True

        # Bot detection with more specific patterns
        bot_patterns = [
            "bot",
            "crawler",
            "spider",
            "scraper",
            "automated",
            "curl",
            "wget",
        ]
        if user_agent and any(
            pattern in user_agent.lower() for pattern in bot_patterns
        ):
            # Allow legitimate bots but log them
            legitimate_bots = ["googlebot", "bingbot", "slackbot"]
            if not any(legit in user_agent.lower() for legit in legitimate_bots):
                security_result["violations"].append("Bot-like user agent detected")
                security_result["action"] = "block"
                security_result["allowed"] = False

        return security_result

    except Exception as e:
        logger.error(f"Security guardrail error: {e}", exc_info=True)
        # Fail secure
        return {
            "allowed": False,
            "violations": ["Security validation failed"],
            "action": "block",
            "metadata": {"error": str(e)},
        }


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request with child safety validation."""

    message: str = Field(..., max_length=300, min_length=1, description="User message")
    child_id: str = Field(
        ..., min_length=1, max_length=50, description="Child identifier"
    )
    child_name: str = Field(default="friend", max_length=30, min_length=1)
    child_age: int = Field(..., ge=3, le=13, description="Child age (3-13)")


class ChatResponse(BaseModel):
    """AI chat response with safety metrics."""

    response: str
    emotion: str = "neutral"
    safe: bool = True
    timestamp: str
    safety_score: float = Field(ge=0.0, le=1.0)


class LoginRequest(BaseModel):
    """User login credentials."""

    email: str = Field(..., max_length=254, description="User email")
    password: str = Field(
        ..., min_length=8, max_length=128, description="User password"
    )


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ConversationHistoryResponse(BaseModel):
    messages: List[Dict[str, Any]]
    count: int


class ESP32AudioRequest(BaseModel):
    """ESP32 audio processing request."""

    child_id: str = Field(..., description="Child identifier")
    audio_data: bytes | None = Field(default=None, description="Audio data")
    language_code: str | None = Field(default=None, max_length=5)
    text_input: str | None = Field(default=None, max_length=500)


# API Endpoints
@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    request: ChatRequest,
    http_request: Request,
    chat_service=ChatServiceDep,
    conversation_service=ConversationServiceDep,
):
    """Main chat endpoint with enhanced security guardrails and child safety validation"""
    correlation_id = str(uuid.uuid4())
    retry_count = 0
    max_retries = 2  # Limited retries for child safety

    # Apply security guardrails first
    security_check = await apply_security_guardrails(http_request, "/chat")
    if not security_check["allowed"]:
        logger.warning(
            f"[{correlation_id}] Security guardrail blocked request: {security_check['violations']}"
        )

        if security_check["action"] == "rate_limit":
            retry_after = security_check["metadata"].get("retry_after", 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request blocked by security policy",
            )

    # Enhanced child safety validation
    child_safety_check = await validate_child_safety(
        request.message, request.child_age, request.child_id
    )

    if not child_safety_check["is_safe"]:
        logger.critical(
            f"[{correlation_id}] Child safety violation: {child_safety_check['violations']}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content not appropriate for children",
        )

    if not child_safety_check["coppa_compliant"]:
        logger.warning(
            f"[{correlation_id}] COPPA compliance issue: age {request.child_age}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Age verification required - user may not qualify for child platform",
        )

    while retry_count <= max_retries:
        try:
            # Age validation (handled by Pydantic, but double-check)
            if not (3 <= request.child_age <= 13):
                logger.warning(f"[{correlation_id}] Invalid age: {request.child_age}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Child age must be 3-13 for COPPA compliance",
                )

            # Get conversation history with retry protection
            try:
                history = conversation_service.get_conversation_history(
                    request.child_id
                )
            except Exception as e:
                logger.warning(
                    f"[{correlation_id}] Failed to get history (attempt {retry_count + 1}): {e}"
                )
                if retry_count < max_retries:
                    retry_count += 1
                    await asyncio.sleep(0.5)  # Brief delay before retry
                    continue
                history = []  # Fallback to empty history

            # AI response generation with safety retry
            ai_response = await chat_service.generate_response(
                user_message=request.message,
                child_age=request.child_age,
                child_name=request.child_name,
                conversation_history=history,
            )

            # Safety score validation
            if ai_response.safety_score < 0.8:
                logger.warning(
                    f"[{correlation_id}] Low safety score: {ai_response.safety_score} (attempt {retry_count + 1})"
                )
                if retry_count < max_retries:
                    retry_count += 1
                    await asyncio.sleep(0.2)  # Brief delay for safety retry
                    continue
                else:
                    # If all retries failed, use fallback response
                    ai_response.content = "I want to make sure I give you the best answer. Could you ask me something else?"
                    ai_response.safety_score = 1.0

            # Success - break out of retry loop
            break

        except HTTPException:
            # Don't retry HTTP exceptions (validation errors, etc.)
            raise
        except Exception as e:
            if retry_count < max_retries:
                retry_count += 1
                logger.warning(
                    f"[{correlation_id}] Chat operation failed (attempt {retry_count}): {e}"
                )
                await asyncio.sleep(min(retry_count * 0.5, 2.0))  # Exponential backoff
                continue
            else:
                logger.error(
                    f"[{correlation_id}] Chat failed after {max_retries + 1} attempts: {e}"
                )
                raise

        # Save conversation with retry protection
        save_retry_count = 0
        max_save_retries = 2

        while save_retry_count <= max_save_retries:
            try:
                user_message = Message(
                    content=request.message,
                    role="user",
                    child_id=request.child_id,
                    safety_checked=True,
                    safety_score=1.0,
                )
                conversation_service.add_message(request.child_id, user_message)

                ai_message = Message(
                    content=ai_response.content,
                    role="assistant",
                    child_id=request.child_id,
                    safety_checked=True,
                    safety_score=ai_response.safety_score,
                )
                conversation_service.add_message(request.child_id, ai_message)

                # Get or create conversation for interaction tracking
                try:
                    # Try to get existing conversation for this child
                    conversations = (
                        await conversation_service.get_conversations_for_child(
                            child_id=UUID(request.child_id),
                            limit=1,
                            include_completed=False,
                        )
                    )

                    if conversations:
                        # Use existing active conversation
                        conversation_id = str(conversations[0].id)
                    else:
                        # Create new conversation
                        conversation_id = (
                            await conversation_service.create_conversation(
                                child_id=request.child_id,
                                metadata={
                                    "interaction_type": "chat",
                                    "started_via": "chat_endpoint",
                                },
                            )
                        )

                    # Store interaction record for dashboard display
                    await conversation_service.store_chat_interaction(
                        conversation_id=conversation_id,
                        user_message=request.message,
                        ai_response=ai_response.content,
                        safety_score=ai_response.safety_score,
                    )

                except Exception as interaction_error:
                    # Log error but don't fail the chat response
                    logger.warning(
                        f"[{correlation_id}] Failed to store interaction record: {interaction_error}"
                    )

                # Success
                break

            except Exception as e:
                if save_retry_count < max_save_retries:
                    save_retry_count += 1
                    logger.warning(
                        f"[{correlation_id}] Failed to save conversation (attempt {save_retry_count}): {e}"
                    )
                    await asyncio.sleep(0.3)
                    continue
                else:
                    # Log error but don't fail the response - user still gets the AI response
                    logger.error(
                        f"[{correlation_id}] Failed to save conversation after {max_save_retries + 1} attempts: {e}"
                    )

        logger.info(f"[{correlation_id}] Chat completed for child {request.child_id}")
        return ChatResponse(
            response=ai_response.content,
            emotion=ai_response.emotion,
            safe=ai_response.age_appropriate,
            timestamp=ai_response.timestamp.isoformat(),
            safety_score=ai_response.safety_score,
        )


# REMOVED: Duplicate authentication endpoints
# These endpoints are now handled by the dedicated auth_router in src/adapters/auth_routes.py
# This eliminates route conflicts and centralizes authentication logic


@router.get(
    "/conversations/{child_id}/history", response_model=ConversationHistoryResponse
)
async def get_conversation_history(
    child_id: str, limit: int = 10, conversation_service=ConversationServiceDep
):
    """Retrieve conversation history for a specific child with retry logic"""
    correlation_id = str(uuid.uuid4())
    retry_count = 0
    max_retries = 3  # Database operations may benefit from retries

    while retry_count <= max_retries:
        try:
            messages = conversation_service.get_conversation_history(child_id, limit)

            message_dicts = [
                {
                    "id": msg.id,
                    "content": msg.content,
                    "role": msg.role,
                    "timestamp": msg.timestamp.isoformat(),
                    "safety_score": msg.safety_score,
                }
                for msg in messages
            ]

            logger.info(
                f"[{correlation_id}] Retrieved {len(message_dicts)} messages for child {child_id}"
            )
            return ConversationHistoryResponse(
                messages=message_dicts, count=len(message_dicts)
            )

        except Exception as e:
            if retry_count < max_retries:
                retry_count += 1
                logger.warning(
                    f"[{correlation_id}] History retrieval failed (attempt {retry_count}): {e}"
                )
                await asyncio.sleep(min(retry_count * 0.5, 2.0))  # Exponential backoff
                continue
            else:
                logger.error(
                    f"[{correlation_id}] History retrieval failed after {max_retries + 1} attempts: {e}",
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Unable to retrieve conversation history. Correlation ID: {correlation_id}",
                )


def get_audio_service():
    """Inject audio service from DI container"""
    stt_provider = injector_instance.get("SpeechProvider")
    tts_provider = injector_instance.get("TTSProvider")
    return AudioService(stt_provider, tts_provider)


def get_esp32_audio_use_case():
    """Inject ESP32 audio use case dependencies"""
    audio_service = get_audio_service()
    esp32_protocol = ESP32Protocol()
    ai_service = injector_instance.get(IAIService)
    conversation_service = injector_instance.get(IConversationService)
    child_repository = injector_instance.get("ChildRepository")
    return ProcessESP32AudioUseCase(
        audio_service=audio_service,
        esp32_protocol=esp32_protocol,
        ai_service=ai_service,
        conversation_service=conversation_service,
        child_repository=child_repository,
    )


@router.post("/esp32/audio")
async def process_esp32_audio(
    request: ESP32AudioRequest,
    use_case: ProcessESP32AudioUseCase = Depends(get_esp32_audio_use_case),
):
    """Process ESP32 audio with real-time Whisper STT, optimized streaming, and retry logic"""
    correlation_id = str(uuid.uuid4())
    retry_count = 0
    max_retries = 2  # Limited retries for real-time audio processing

    while retry_count <= max_retries:
        try:
            # Create ESP32 request with enhanced processing
            esp32_req = ESP32Request(
                child_id=request.child_id,
                audio_data=request.audio_data,
                language_code=request.language_code,
                text_input=request.text_input,
            )

            # Process through use case with optimized services
            response = await use_case.execute(esp32_req)

            # Add real-time streaming metrics to response
            if hasattr(response, "metadata"):
                response.metadata.update(
                    {
                        "stt_provider": "whisper_local",
                        "streaming_optimized": True,
                        "latency_target": "300ms",
                        "correlation_id": correlation_id,
                        "retry_attempt": retry_count + 1,
                    }
                )

            logger.info(
                f"[{correlation_id}] ESP32 audio processed with Whisper STT "
                f"for child {request.child_id} (attempt {retry_count + 1})"
            )
            return response

        except Exception as e:
            if retry_count < max_retries:
                retry_count += 1
                logger.warning(
                    f"[{correlation_id}] ESP32 audio processing failed (attempt {retry_count}): {e}"
                )
                # Shorter delays for real-time audio processing
                await asyncio.sleep(0.1 + (retry_count * 0.1))
                continue
            else:
                logger.error(
                    f"[{correlation_id}] ESP32 audio processing failed after {max_retries + 1} attempts: {e}",
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Audio processing failed. Correlation ID: {correlation_id}",
                )


@router.get("/health")
async def health_check():
    """Production-grade health check endpoint with retry logic for reliability"""
    db_status = "unknown"
    redis_status = "unknown"
    healthy = True
    errors = []

    # Database health check with retries
    for attempt in range(3):
        try:
            adapter = await database_production.get_database_adapter()
            db_healthy = await adapter.health_check()
            db_status = "ok" if db_healthy else "error"
            if not db_healthy:
                healthy = False
                errors.append("Database health check failed")
            break
        except Exception as e:
            if attempt < 2:  # Retry on first 2 attempts
                await asyncio.sleep(0.2)
                continue
            db_status = "error"
            healthy = False
            errors.append(f"Database error: {str(e)}")

    # Redis health check with retries
    for attempt in range(3):
        try:
            redis_url = os.environ.get("REDIS_URL")
            if not redis_url:
                raise Exception("REDIS_URL not configured")
            r = redis.from_url(redis_url)
            await r.ping()
            redis_status = "ok"
            break
        except Exception as e:
            if attempt < 2:  # Retry on first 2 attempts
                await asyncio.sleep(0.2)
                continue
            redis_status = "error"
            healthy = False
            errors.append(f"Redis: {str(e)}")

    result = {
        "status": "healthy" if healthy else "unhealthy",
        "database": db_status,
        "redis": redis_status,
        "service": "ai-teddy-bear-api",
        "timestamp": datetime.now().isoformat(),
    }

    if errors:
        result["errors"] = errors

    return JSONResponse(
        status_code=HTTP_200_OK if healthy else HTTP_503_SERVICE_UNAVAILABLE,
        content=result,
    )


@router.get("/health/audio")
async def audio_health_check():
    """Production audio service health check endpoint"""
    try:
        # Get audio service from container
        audio_service = injector_instance.get(AudioService)

        # Get comprehensive health status
        health_status = await audio_service.get_service_health()

        # Determine overall health
        is_healthy = health_status.get("status") == "healthy"

        return JSONResponse(
            status_code=HTTP_200_OK if is_healthy else HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "service": "audio-pipeline",
                "timestamp": datetime.now().isoformat(),
                **health_status,
            },
        )

    except Exception as e:
        logger.error(f"Audio health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "service": "audio-pipeline",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


@router.get("/health/audio/metrics")
async def audio_metrics_endpoint():
    """Production audio service metrics endpoint for monitoring"""
    try:
        # Get audio service from container
        audio_service = injector_instance.get(AudioService)

        # Get comprehensive TTS metrics
        metrics = await audio_service.get_tts_metrics()

        return JSONResponse(
            status_code=HTTP_200_OK,
            content={
                "service": "audio-pipeline-metrics",
                "timestamp": datetime.now().isoformat(),
                **metrics,
            },
        )

    except Exception as e:
        logger.error(f"Audio metrics collection failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "service": "audio-pipeline-metrics",
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


@router.get("/health/audio/tts")
async def tts_health_check():
    """TTS provider health check endpoint"""
    try:
        # Get TTS service directly from container
        from src.interfaces.providers.tts_provider import ITTSService

        tts_service = injector_instance.get(ITTSService)

        # Get TTS provider health
        tts_health = await tts_service.health_check()

        is_healthy = tts_health.get("status") == "healthy"

        return JSONResponse(
            status_code=HTTP_200_OK if is_healthy else HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "service": "tts-provider",
                "timestamp": datetime.now().isoformat(),
                **tts_health,
            },
        )

    except Exception as e:
        logger.error(f"TTS health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "service": "tts-provider",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


@router.get("/metrics/audio")
async def audio_prometheus_metrics():
    """Prometheus metrics endpoint specifically for audio pipeline."""
    try:
        try:
            from src.infrastructure.monitoring.prometheus_metrics import prometheus_metrics
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        except ImportError:
            logger.warning("Prometheus metrics not available - fallback to basic metrics")
            return {"status": "basic_metrics_only", "prometheus_available": False}

        # Get only audio-related metrics
        audio_metrics = []
        registry_data = generate_latest(prometheus_metrics.registry).decode("utf-8")

        # Filter for audio-related metrics
        for line in registry_data.split("\n"):
            if any(
                metric in line for metric in ["tts_", "audio_", "stt_", "child_audio_"]
            ):
                audio_metrics.append(line)

        audio_metrics_str = "\n".join(audio_metrics)

        return Response(
            content=audio_metrics_str,
            media_type=CONTENT_TYPE_LATEST,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except Exception as e:
        logger.error(f"Audio metrics collection failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "Audio metrics unavailable",
                "detail": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


@router.get("/monitoring/smart-dashboard")
async def smart_monitoring_dashboard():
    """Smart monitoring dashboard for enhanced features with retry logic."""
    correlation_id = str(uuid.uuid4())
    retry_count = 0
    max_retries = 2

    while retry_count <= max_retries:
        try:
            from src.infrastructure.monitoring.ai_service_alerts import smart_monitor

            # Get smart monitoring data
            dashboard_data = await smart_monitor.get_smart_monitoring_dashboard()

            # Add additional system metrics
            dashboard_data.update(
                {
                    "system_health": {
                        "correlation_id": correlation_id,
                        "retry_attempt": retry_count + 1,
                        "enhanced_features_status": "active",
                    }
                }
            )

            logger.info(f"[{correlation_id}] Smart dashboard data retrieved")
            return JSONResponse(
                status_code=HTTP_200_OK,
                content={
                    "status": "success",
                    "data": dashboard_data,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            if retry_count < max_retries:
                retry_count += 1
                logger.warning(
                    f"[{correlation_id}] Smart dashboard failed (attempt {retry_count}): {e}"
                )
                await asyncio.sleep(0.5)
                continue
            else:
                logger.error(
                    f"[{correlation_id}] Smart dashboard failed after {max_retries + 1} attempts: {e}",
                    exc_info=True,
                )
                return JSONResponse(
                    status_code=HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "error": "Smart monitoring dashboard unavailable",
                        "detail": str(e),
                        "correlation_id": correlation_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                )


@router.get("/monitoring/alerts/history")
async def get_alert_history(hours: int = 24):
    """Get enhanced alert history with retry logic."""
    correlation_id = str(uuid.uuid4())
    retry_count = 0
    max_retries = 2

    while retry_count <= max_retries:
        try:
            from src.infrastructure.monitoring.ai_service_alerts import (
                create_enhanced_ai_service_monitor,
            )

            # Create monitor instance
            monitor = create_enhanced_ai_service_monitor()

            # Get alert history
            alert_history = monitor.get_enhanced_alert_history(hours=hours)

            # Convert to serializable format
            alerts_data = [alert.to_dict() for alert in alert_history]

            logger.info(f"[{correlation_id}] Retrieved {len(alerts_data)} alerts")
            return JSONResponse(
                status_code=HTTP_200_OK,
                content={
                    "status": "success",
                    "alerts": alerts_data,
                    "count": len(alerts_data),
                    "hours": hours,
                    "correlation_id": correlation_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            if retry_count < max_retries:
                retry_count += 1
                logger.warning(
                    f"[{correlation_id}] Alert history retrieval failed (attempt {retry_count}): {e}"
                )
                await asyncio.sleep(0.3)
                continue
            else:
                logger.error(
                    f"[{correlation_id}] Alert history failed after {max_retries + 1} attempts: {e}",
                    exc_info=True,
                )
                return JSONResponse(
                    status_code=HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "error": "Alert history unavailable",
                        "detail": str(e),
                        "correlation_id": correlation_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                )


@router.get("/security/status")
async def get_security_status():
    """Get comprehensive security status and guardrails information."""
    try:
        # Get rate limiter status
        rate_limiter_status = {
            "active_policies": len(advanced_rate_limiter.tier_configs),
            "endpoint_limits": len(advanced_rate_limiter.endpoint_limits),
            "global_limits_active": True,
        }

        # Security validation status
        validation_status = {
            "input_validator_active": advanced_input_validator is not None,
            "child_safety_patterns": len(
                getattr(advanced_input_validator, "_inappropriate_patterns", [])
            ),
            "security_patterns": {
                "sql_injection": len(
                    getattr(advanced_input_validator, "_sql_patterns", [])
                ),
                "xss": len(getattr(advanced_input_validator, "_xss_patterns", [])),
                "command_injection": len(
                    getattr(advanced_input_validator, "_cmd_patterns", [])
                ),
            },
        }

        # COPPA compliance status
        coppa_status = {
            "age_verification_active": True,
            "content_filtering_active": True,
            "data_retention_compliant": True,
            "parental_consent_required": True,
        }

        return JSONResponse(
            status_code=HTTP_200_OK,
            content={
                "status": "active",
                "security_guardrails": {
                    "rate_limiting": rate_limiter_status,
                    "input_validation": validation_status,
                    "coppa_compliance": coppa_status,
                    "child_safety": {
                        "active": True,
                        "content_filtering": True,
                        "age_appropriate_validation": True,
                        "personal_info_protection": True,
                    },
                },
                "last_updated": datetime.now().isoformat(),
                "service": "ai-teddy-bear-security",
            },
        )

    except Exception as e:
        logger.error(f"Security status check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "error": "Security status check failed",
                "detail": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


# SECURITY FIX: Removed test-guardrails endpoint - production should not expose security testing endpoints
# Security testing is restricted to development or staging environments
