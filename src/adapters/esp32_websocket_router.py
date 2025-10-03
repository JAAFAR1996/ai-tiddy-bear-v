"""
ESP32 WebSocket Router - FastAPI Integration
===========================================
FastAPI router for ESP32 WebSocket connections with complete audio processing.
"""

import logging
import os
import json
import time
import secrets
from typing import Optional, Dict, Any, Deque
from datetime import datetime, timezone
from collections import defaultdict, deque

from sqlalchemy import select

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Query,
    Depends,
    Request,
)
from fastapi.responses import JSONResponse

from src.application.dependencies import ConfigDep
from src.services.esp32_production_runner import esp32_production_runner
from src.infrastructure.security.admin_security import (
    require_admin_permission,
    AdminPermission,
    SecurityLevel,
    AdminSession,
)
from src.adapters.esp32_router import ws_auth_dependency
from src.infrastructure.database.models import Device
from src.services.redis_resume_store import RedisSessionResumeStore


# Create router
esp32_router = APIRouter(tags=["ESP32"])
logger = logging.getLogger(__name__)

# In-memory trace buffer per device
_TRACE_MAX = 200
_traces: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=_TRACE_MAX))

_WS_METRICS: Dict[str, Any] = {
    "handshake_attempts": 0,
    "handshake_rejections": 0,
    "connections_total": 0,
    "connections_closed": 0,
    "active_connections": 0,
    "messages_received": 0,
    "errors_total": 0,
    "bytes_received": 0,
    "ws_reconnects": 0,
    "ws_resumes": 0,
    "resume_failures": 0,
    "ws_upgrades_blocked_during_drain": 0,
    "dropped_messages": 0,
    "last_failure_reason": None,
    "last_error_reason": None,
    "last_handshake_attempt_at": None,
    "last_failure_at": None,
    "last_error_at": None,
}

# Resume store instance
_resume_store: Optional[RedisSessionResumeStore] = None

async def get_resume_store() -> RedisSessionResumeStore:
    global _resume_store
    if _resume_store is None:
        from src.infrastructure.config.production_config import get_config
        config = get_config()
        redis_url = getattr(config, 'REDIS_URL', 'redis://localhost:6379/0')
        
        def on_messages_dropped(count: int):
            _WS_METRICS["dropped_messages"] += count
        
        _resume_store = RedisSessionResumeStore(
            redis_url=redis_url,
            ttl_seconds=900,
            max_messages_per_session=200,
            on_messages_dropped=on_messages_dropped
        )
    return _resume_store
_WS_ERROR_WINDOW_SECONDS = 300
_WS_ERROR_EVENTS: Deque[float] = deque(maxlen=2048)


def _record_handshake_attempt() -> None:
    now = time.time()
    _WS_METRICS["handshake_attempts"] += 1
    _WS_METRICS["last_handshake_attempt_at"] = now

def _record_error_event(reason: str) -> None:
    now = time.time()
    _WS_METRICS["errors_total"] += 1
    _WS_METRICS["last_error_reason"] = reason
    _WS_METRICS["last_error_at"] = now
    _WS_ERROR_EVENTS.append(now)

def _record_ws_error(reason: str) -> None:
    _record_error_event(reason)

def _record_handshake_rejection(reason: str) -> None:
    now = time.time()
    _WS_METRICS["handshake_rejections"] += 1
    _WS_METRICS["last_failure_reason"] = reason
    _WS_METRICS["last_failure_at"] = now
    _record_error_event(reason)

def _record_connection_open() -> None:
    now = time.time()
    _WS_METRICS["connections_total"] += 1
    _WS_METRICS["active_connections"] += 1
    _WS_METRICS["last_connection_opened_at"] = now

def _record_connection_closed() -> None:
    if _WS_METRICS["active_connections"] > 0:
        _WS_METRICS["active_connections"] -= 1
    _WS_METRICS["connections_closed"] += 1
    _WS_METRICS["last_connection_closed_at"] = time.time()

def _record_message_received(byte_count: int) -> None:
    _WS_METRICS["messages_received"] += 1
    if byte_count > 0:
        _WS_METRICS["bytes_received"] += byte_count

def _prune_error_events(now: float | None = None) -> None:
    current = now or time.time()
    cutoff = current - _WS_ERROR_WINDOW_SECONDS
    while _WS_ERROR_EVENTS and _WS_ERROR_EVENTS[0] < cutoff:
        _WS_ERROR_EVENTS.popleft()

def _ws_metrics_snapshot() -> Dict[str, Any]:
    snapshot = dict(_WS_METRICS)
    _prune_error_events()
    errors_last_window = len(_WS_ERROR_EVENTS)
    snapshot["errors_last_window"] = errors_last_window
    snapshot["error_window_seconds"] = _WS_ERROR_WINDOW_SECONDS
    total_connections = snapshot.get("connections_total", 0) or 0
    snapshot["ws_error_rate"] = (
        round(errors_last_window / total_connections, 4) if total_connections else 0.0
    )
    return snapshot


def _trace(device_id: str, event: str, **data: Any) -> None:
    try:
        _traces[device_id].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **data,
        })
    except Exception:
        pass


async def ensure_esp32_ready(websocket: WebSocket) -> None:
    """Guard WebSocket entry until ESP32 services finish bootstrapping."""
    _record_handshake_attempt()
    app = getattr(websocket, "app", None) or websocket.scope.get("app")
    if app is None:
        return
    ready_flag = bool(getattr(app.state, "esp32_services_ready", False))
    _WS_METRICS["last_readiness_state"] = ready_flag
    _WS_METRICS["last_readiness_checked_at"] = time.time()
    if not ready_flag:
        _record_handshake_rejection("esp32_not_ready")
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "esp32_warming_up",
                "message": "ESP32 services warming up",
            },
            headers={"Retry-After": "5"},
        )


@esp32_router.on_event("startup")
async def startup_esp32_services():
    """Initialize ESP32 services on startup (non-fatal on failure)."""
    try:
        if esp32_production_runner.get_chat_server():
            logger.info("ESP32 services already initialized; skipping router startup init")
            return
        # Inject production config explicitly to satisfy strict DI
        from src.infrastructure.config.production_config import get_config as _get_loaded_config
        _cfg = _get_loaded_config()
        await esp32_production_runner.initialize_services(config=_cfg)
        logger.info("ESP32 services initialized successfully")
    except Exception as e:
        # Do not abort app startup; WS endpoint has lazy init fallback
        logger.error(f"Failed to initialize ESP32 services at router startup: {e}", exc_info=True)
        return


@esp32_router.websocket("/connect")
async def esp32_websocket_endpoint(
    websocket: WebSocket,
    device_id: str = Query(..., description="ESP32 device identifier"),
    child_id: Optional[str] = Query(None, description="Child profile identifier"),
    child_name: Optional[str] = Query(None, description="Child's name"),
    child_age: Optional[int] = Query(None, description="Child's age (3-13)"),
    _ready: None = Depends(ensure_esp32_ready),
    auth_info: Dict[str, str] = Depends(ws_auth_dependency),
):
    drain_manager = await get_drain_manager()
    if drain_manager.is_draining():
        _WS_METRICS["ws_upgrades_blocked_during_drain"] += 1
        await websocket.close(code=4503, reason="draining")
        return
    
    resume_store = await get_resume_store()
    
    # Check for resumable session
    resume_offer = await resume_store.offer_resume(device_id)
    if resume_offer and resume_offer.get("can_resume", False):
        # Send resume offer
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "resume_offer",
            "session_id": resume_offer["session_id"],
            "missed_count": resume_offer["missed_count"],
            "timeout_ms": 5000
        }))
        
        # Wait for resume response
        try:
            response = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            data = json.loads(response)
            if data.get("type") == "resume_ack" and data.get("accepted", False):
                # Resume session
                _WS_METRICS["ws_resumes"] += 1
                await _handle_session_resume(websocket, device_id, resume_offer, resume_store)
                return
            else:
                _WS_METRICS["resume_failures"] += 1
        except (asyncio.TimeoutError, json.JSONDecodeError):
            _WS_METRICS["resume_failures"] += 1
    
    # Check for reconnection
    existing_session_id = device_sessions.get(device_id)
    if existing_session_id:
        _WS_METRICS["ws_reconnects"] += 1
    """
    WebSocket endpoint for ESP32 device connections.

    Complete audio processing pipeline:

    1. Device authentication and session creation
    2. Real-time audio streaming
    3. Speech-to-Text conversion (Whisper)
    4. AI response generation
    5. Text-to-Speech conversion
    6. Audio response streaming back to device

    Query Parameters:
    - device_id: Unique ESP32 device identifier (8-32 chars, alphanumeric)
    - child_id: Child profile UUID
    - child_name: Child's display name
    - child_age: Child's age (must be 3-13 for COPPA compliance)

    WebSocket Message Format:

    Audio Messages (ESP32 -> Server):
    {
        "type": "audio_start",
        "audio_session_id": "uuid"
    }
    {
        "type": "audio_chunk",
        "audio_data": "base64_encoded_audio",
        "chunk_id": "uuid",
        "audio_session_id": "uuid",
        "is_final": false
    }
    {
        "type": "audio_end",
        "audio_session_id": "uuid"
    }

    Response Messages (Server -> ESP32):
    {
        "type": "audio_response",
        "audio_data": "base64_encoded_audio",
        "text": "AI response text",
        "format": "mp3",
        "sample_rate": 22050
    }

    System Messages:
    {
        "type": "system",
        "data": {
            "type": "connection_established",
            "session_id": "uuid",
            "message": "Hello! I'm ready to chat!"
        }
    }

    Error Messages:
    {
        "type": "error",
        "error_code": "error_type",
        "error_message": "Human readable error"
    }
    """
    connection_registered = False

    # Diagnostic: log early query/headers and allow dev bypass before any checks
    try:
        headers = {k.decode(): v.decode() for k, v in websocket.headers.raw}
    except Exception:
        headers = {}
    try:
        q = dict(websocket.query_params)
    except Exception:
        q = {"error": "no_query"}
    logger.warning(
        "WS_ENTER /ws/esp32/connect",
        extra={
            "query": q,
            "headers": {
                "host": headers.get("host"),
                "origin": headers.get("origin"),
                "upgrade": headers.get("upgrade"),
            },
        },
    )
    _trace(device_id, "ws_enter", query=q)
    try:
        dbg = {
            "env": os.getenv("ENVIRONMENT", "development"),
            "query": q,
            "headers": headers,
            "client": str(getattr(websocket, "client", None)),
        }
        print("WS_ENTER", json.dumps(dbg))
    except Exception:
        pass

    env = (os.getenv("ENVIRONMENT", "development") or "development").lower()
    ws_dev_bypass = os.getenv("WS_DEV_BYPASS", "0").strip().lower() in ("1", "true", "yes")
    if env != "production" and ws_dev_bypass:
        await websocket.accept()
        await websocket.send_text("dev-ok")
        _trace(device_id, "ws_dev_bypass_accept")
        return

    chat_server = esp32_production_runner.get_chat_server()

    # Development convenience: allow missing child_* query params by providing sane defaults
    try:
        env = (os.getenv("ENVIRONMENT", "development") or "development").lower()
    except Exception:
        env = "development"
    if env != "production":
        if not child_id:
            child_id = "dev"
        if not child_name:
            child_name = "Dev"
        if not child_age:
            child_age = 7

    # Robustness: attempt lazy initialization if chat server is not ready yet
    if not chat_server:
        try:
            logger.info("ESP32 chat server not initialized; attempting lazy init...")
            # Load production config explicitly to satisfy strict DI
            from src.infrastructure.config.production_config import get_config as _get_loaded_config
            _cfg = _get_loaded_config()
            await esp32_production_runner.initialize_services(config=_cfg)
            chat_server = esp32_production_runner.get_chat_server()
        except Exception as _e:
            logger.error(f"Lazy init failed: {_e}", exc_info=True)
            chat_server = None

    if not chat_server:
        await websocket.close(code=1011, reason="Server not initialized")
        _trace(device_id, "ws_close", reason="Server not initialized")
        return

    session_id = None

    try:
        # --- Auto register device on first connect (dev by default, opt-in for prod) ---
        try:
            _env = (os.getenv("ENVIRONMENT", "development") or "development").lower()
            _allow_auto = os.getenv("ALLOW_AUTO_DEVICE_REG", "0").strip().lower() in ("1", "true", "yes")
            if _env != "production" or _allow_auto:
                # Prefer app-provided async sessionmaker (set in main.py)
                _app = getattr(websocket, "app", None) or websocket.scope.get("app")
                db_sessionmaker = getattr(_app.state, "db_sessionmaker", None) if _app else None
                if db_sessionmaker is not None:
                    async with db_sessionmaker() as db:
                        try:
                            res = await db.execute(select(Device).where(Device.device_id == device_id))
                            dev = res.scalar_one_or_none()
                            now = datetime.now(timezone.utc)
                            if not dev:
                                dev = Device(
                                    device_id=device_id,
                                    status="ACTIVE",
                                    is_active=True,
                                    registration_source="auto",
                                    firmware_version=None,
                                    hardware_version=None,
                                    last_seen_at=now,
                                    configuration={},
                                    capabilities=[],
                                    compliance_flags={},
                                )
                                db.add(dev)
                                await db.commit()
                                logger.info("Device auto-registered", extra={"device_id": device_id})
                            else:
                                # Update last_seen and un-pend if necessary
                                dev.last_seen_at = now
                                try:
                                    if getattr(dev, "status", "").upper() == "PENDING":
                                        dev.status = "ACTIVE"
                                except Exception:
                                    pass
                                await db.commit()
                        except Exception:
                            # Ensure the session is clean on failure
                            try:
                                await db.rollback()
                            except Exception:
                                pass
                            raise
                else:
                    logger.debug("DB sessionmaker not available; skipping auto device register")
        except Exception as _auto_e:
            logger.warning(f"Auto device registration failed: {_auto_e}")
        # --- end auto register ---

        # Connect device and create session
        session_id = await chat_server.connect_device(
            websocket=websocket,
            device_id=device_id,
            child_id=child_id,
            child_name=child_name,
            child_age=child_age,
        )
        
        # Register with resume store
        await resume_store.register_session(session_id, device_id)
        
        connection_registered = True
        _record_connection_open()
        _trace(device_id, "ws_connected", session_id=session_id, child_id=child_id, child_age=child_age)

        logger.info(
            f"ESP32 device connected via WebSocket",
            extra={
                "session_id": session_id,
                "device_id": device_id,
                "child_id": child_id,
                "child_age": child_age,
            },
        )

        # Handle messages
        while True:
            try:
                # Receive message from ESP32
                raw_message = await websocket.receive_text()
                # Trace inbound message size and JSON type if applicable
                msg_len = len(raw_message) if isinstance(raw_message, str) else 0
                _record_message_received(msg_len)
                msg_type = None
                try:
                    obj = json.loads(raw_message)
                    msg_type = obj.get("type")
                except Exception:
                    pass
                _trace(device_id, "ws_rx", session_id=session_id, bytes=msg_len, msg_type=msg_type)

                # Handle special resume messages
                try:
                    obj = json.loads(raw_message)
                    msg_type = obj.get("type")
                    
                    if msg_type == "message_ack":
                        ack_seq = obj.get("ack_seq")
                        if ack_seq:
                            await resume_store.acknowledge(session_id, ack_seq)
                        continue
                    elif msg_type == "ping":
                        # RTT measurement
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": time.time() * 1000
                        }))
                        continue
                except Exception:
                    pass
                
                # Process message through chat server
                await chat_server.handle_message(session_id, raw_message)

            except WebSocketDisconnect:
                logger.info(f"ESP32 device disconnected: {session_id}")
                _trace(device_id, "ws_disconnect", session_id=session_id)
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)
                _trace(device_id, "ws_error", error=str(e))
                _record_ws_error("message_processing_error")
                # Continue processing other messages

    except HTTPException as e:
        logger.warning(f"ESP32 connection rejected: {e.detail}")
        if not (
            e.status_code == 503
            and isinstance(e.detail, dict)
            and e.detail.get("error_code") == "esp32_warming_up"
        ):
            reason = e.detail if isinstance(e.detail, str) else e.detail.get("error_code", "http_exception")
            _record_handshake_rejection(str(reason))
        # Dev: do not return 403 silently; accept and send dev-error for diagnostics
        if env != "production":
            try:
                print("WS_FAIL", repr(e))
                await websocket.accept()
                await websocket.send_text(f"dev-error: {e.detail}")
                _trace(device_id, "ws_fail_dev", error=str(e))
                return
            except Exception:
                return
        else:
            try:
                await websocket.close(code=e.status_code, reason=e.detail)
            except Exception as close_e:
                logger.error(
                    f"Exception closing WebSocket connection after HTTP rejection: {close_e}",
                    exc_info=True,
                )
                # Continue - connection may already be closed by client
    except Exception as e:
        logger.error(f"ESP32 WebSocket error: {e}", exc_info=True)
        _record_ws_error("websocket_endpoint_error")
        if env != "production":
            try:
                print("WS_FAIL", repr(e))
                await websocket.accept()
                await websocket.send_text(f"dev-error: {e}")
                _trace(device_id, "ws_fail_dev", error=str(e))
                return
            except Exception:
                return
        else:
            try:
                await websocket.close(code=1011, reason="Internal server error")
            except Exception as close_e:
                logger.error(
                    f"Exception closing WebSocket connection after internal error: {close_e}",
                    exc_info=True,
                )
                # Continue - connection may already be closed or in invalid state
    finally:
        # Cleanup session
        if session_id:
            try:
                if chat_server:
                    await chat_server.disconnect_device(session_id, "websocket_closed")
                # Keep session in resume store for potential reconnection
            except Exception as e:
                logger.error(f"Error cleaning up session: {e}")
        if connection_registered:
            _record_connection_closed()
        _trace(device_id, "ws_cleanup", session_id=session_id)

async def _handle_session_resume(
    websocket: WebSocket,
    device_id: str,
    resume_offer: Dict[str, Any],
    resume_store: RedisSessionResumeStore
) -> None:
    """Handle session resume process."""
    try:
        old_session_id = resume_offer["session_id"]
        ack_seq = resume_offer["ack_seq"]
        
        # Get missed messages
        missed_messages = await resume_store.get_backlog(
            old_session_id,
            after_seq=ack_seq,
            limit=200
        )
        
        # Send missed messages
        for msg in missed_messages:
            await websocket.send_text(json.dumps({
                "type": "resume_message",
                "seq": msg.seq,
                "payload": msg.payload
            }))
        
        # Send resume complete
        await websocket.send_text(json.dumps({
            "type": "resume_complete",
            "delivered_count": len(missed_messages)
        }))
        
        logger.info(f"Session resumed: {old_session_id}, delivered {len(missed_messages)} messages")
        
    except Exception as e:
        logger.error(f"Session resume failed: {e}", exc_info=True)
        await websocket.send_text(json.dumps({
            "type": "resume_failed",
            "reason": "internal_error"
        }))


@esp32_router.get("/metrics")
async def esp32_metrics(request: Request, config = ConfigDep):
    """
    Get ESP32 Chat Server metrics.

    Returns:
        JSON with session metrics, service status, and performance data
    """
    try:
        environment = getattr(config, "ENVIRONMENT", "development")
        if environment == "production":
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            real_ip = request.headers.get("X-Real-IP", "")
            client_host = request.client.host if request.client else ""
            candidate_ip = (forwarded_for.split(",")[0].strip() if forwarded_for else "") or real_ip or client_host
            internal_networks = getattr(
                config,
                "METRICS_INTERNAL_NETWORKS",
                ["10.", "172.16.", "192.168.", "127.0.0.1"],
            )
            metrics_token = getattr(config, "METRICS_API_TOKEN", None)
            provided_token = request.headers.get("X-Metrics-Token")
            allow_by_token = bool(
                metrics_token
                and provided_token
                and secrets.compare_digest(str(provided_token), str(metrics_token))
            )
            allow_by_ip = any(
                candidate_ip.startswith(prefix) for prefix in internal_networks if prefix
            )
            if not (allow_by_token or allow_by_ip):
                raise HTTPException(
                    status_code=403, detail="ESP32 metrics restricted to internal network"
                )

        app_state = getattr(request, "app", None)
        state = getattr(app_state, "state", None) if app_state else None
        esp32_ready_flag = bool(getattr(state, "esp32_services_ready", False)) if state else False
        app_ready_flag = bool(getattr(state, "ready", False)) if state else False

        chat_server = esp32_production_runner.get_chat_server()

        if not chat_server:
            response_body = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "esp32_ready": esp32_ready_flag,
                "app_ready": app_ready_flag,
                "ws_metrics": _ws_metrics_snapshot(),
                "chat_server_metrics": None,
                "error": "Server not initialized",
            }
            return JSONResponse(status_code=503, content=response_body)

        metrics = chat_server.get_session_metrics()
        # Get resume store metrics
        resume_metrics = await resume_store.get_metrics() if resume_store else {}
        
        response_body = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "esp32_ready": esp32_ready_flag,
            "app_ready": app_ready_flag,
            "ws_metrics": _ws_metrics_snapshot(),
            "chat_server_metrics": metrics,
            "resume_store_metrics": resume_metrics,
        }
        return JSONResponse(status_code=200, content=response_body)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}", exc_info=True)
        _record_ws_error("metrics_error")
        return JSONResponse(status_code=500, content={"error": str(e)})


@esp32_router.post("/admin/shutdown")
async def esp32_admin_shutdown(
    session: AdminSession = Depends(
        require_admin_permission(AdminPermission.SYSTEM_ADMIN, SecurityLevel.CRITICAL)
    )
):
    """
    🔒 SECURED: Administrative endpoint to gracefully shutdown ESP32 Chat Server.

    CRITICAL SECURITY: Requires SYSTEM_ADMIN permission + MFA + Certificate auth.
    """
    try:
        await esp32_production_runner.shutdown()

        return JSONResponse(
            status_code=200,
            content={
                "message": "ESP32 Chat Server shutdown initiated",
                "initiated_by": session.user_id,
                "timestamp": "2025-01-27T12:00:00Z",
            },
        )

    except Exception as e:
        logger.error(f"Shutdown failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


# Export router for inclusion in main FastAPI app
__all__ = ["esp32_router"]


@esp32_router.get("/trace/{device_id}")
async def get_device_trace(device_id: str, limit: int = 100):
    """Return recent WebSocket trace events for a device (in-memory)."""
    try:
        buf = _traces.get(device_id)
        if not buf:
            return JSONResponse(status_code=200, content={"device_id": device_id, "events": []})
        events = list(buf)[-max(1, min(limit, _TRACE_MAX)) :]
        return JSONResponse(status_code=200, content={"device_id": device_id, "events": events})
    except Exception as e:
        logger.error(f"Failed to get trace for {device_id}: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

