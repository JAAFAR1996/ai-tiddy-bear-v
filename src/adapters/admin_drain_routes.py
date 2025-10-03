from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from src.adapters.web import admin_guard
from src.services.service_registry import get_drain_manager


class DrainStartRequest(BaseModel):
    reason: Optional[str] = Field(
        None,
        max_length=200,
        description="Operational reason for initiating drain (stored in audit logs)"
    )
    max_session_age_seconds: Optional[int] = Field(
        None,
        ge=60,
        le=3600,
        description="Grace period for existing sessions before force termination"
    )


class DrainStatusResponse(BaseModel):
    is_draining: bool
    started_at: Optional[str] = None
    initiated_by: Optional[str] = None
    reason: Optional[str] = None
    max_session_age_seconds: Optional[int] = None
    notes: Optional[dict] = None


router = APIRouter(
    prefix="/admin/drain",
    tags=["Admin"],
)


@router.get("/status", response_model=DrainStatusResponse)
async def get_drain_status(_admin=Depends(admin_guard)):
    """Return the current drain status for this instance."""
    drain_manager = await get_drain_manager()
    status = drain_manager.get_status()
    payload = status.as_dict()
    payload.setdefault("is_draining", False)
    return payload


@router.post("/start", response_model=DrainStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_drain(request: DrainStartRequest, admin=Depends(admin_guard)):
    """Initiate drain mode for this instance."""
    drain_manager = await get_drain_manager()
    status = await drain_manager.start_drain(
        initiated_by=admin.get("sub") or admin.get("email") or "admin",
        reason=request.reason,
        max_session_age_seconds=request.max_session_age_seconds,
    )
    payload = status.as_dict()
    payload.setdefault("is_draining", True)
    return payload


@router.post("/complete", response_model=DrainStatusResponse)
async def complete_drain(admin=Depends(admin_guard)):
    """End drain mode and re-enable new session upgrades."""
    drain_manager = await get_drain_manager()
    status = await drain_manager.end_drain(
        initiated_by=admin.get("sub") or admin.get("email") or "admin",
        notes={"action": "manual_complete"},
    )
    payload = status.as_dict()
    payload.setdefault("is_draining", False)
    return payload
