from fastapi import APIRouter, Depends, HTTPException, status, Request
from src.infrastructure.routing.route_manager import RouteManager, register_all_routers
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# Simple admin_guard fallback (JWT with 'role'=='admin')
def admin_guard(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    import jwt

    try:
        payload = jwt.decode(credentials.credentials, "secret", algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token"
        )


router = APIRouter(
    prefix="/web",
    tags=["Web Interface"],
)

# ...existing routes...


# Admin healthcheck endpoint
@router.get("/admin/routes/health", tags=["Admin"], dependencies=[Depends(admin_guard)])
async def admin_routes_health():
    summary = route_manager.get_registration_summary()
    return {
        "status": summary["route_health"],
        "total_routes": summary["total_routes"],
        "total_prefixes": summary["total_prefixes"],
        "conflicts_detected": summary["conflicts_detected"],
        "prefixes": summary["prefixes"],
        "routes_by_router": summary["routes_by_router"],
        "last_scan": summary["registration_timestamp"],
        "errors": summary["errors"],
    }


"""
🧸 AI TEDDY BEAR V5 - WEB INTERFACE
Secure dashboard web interface with authentication and error handling.
"""

import logging
import html
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from src.application.dependencies import AuthServiceDep
from src.adapters.database_production import get_database_adapter
from pathlib import Path
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/web", tags=["Web Interface"])

# Dynamic template path
TEMPLATE_DIR = Path(__file__).parent / "templates"

try:
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    templates.env.autoescape = True  # Enable auto-escaping
    # Check for required templates at startup
    required_templates = [
        "dashboard.html",
        "child_profile.html",
        "reports.html",
        "settings.html",
    ]
    missing = []
    for tpl in required_templates:
        if not (TEMPLATE_DIR / tpl).is_file():
            missing.append(tpl)
    if missing:
        logger.warning(f"Missing required template files: {missing} in {TEMPLATE_DIR}")
except Exception as e:
    logger.error(f"Failed to load templates: {e}")
    templates = None


def _sanitize_template_data(data):
    """Sanitize data before passing to templates to prevent XSS."""
    if isinstance(data, dict):
        return {key: _sanitize_template_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_sanitize_template_data(item) for item in data]
    elif isinstance(data, str):
        return html.escape(data)
    else:
        return data


async def get_current_user(auth_service=AuthServiceDep):
    """Get authenticated user from token."""
    # Production environment only
    # Must implement real JWT validation from auth service
    try:
        # Get real authenticated user from auth service
        user = await auth_service.get_current_authenticated_user()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        return user
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication",
        )


async def verify_child_access(child_id: str, user: dict):
    """Verify user has access to child."""
    try:
        adapter = await get_database_adapter()
        child_repo = adapter.get_child_repository()
        child = await child_repo.get_child_by_id(child_id)

        if not child or str(child.parent_id) != user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to child profile",
            )
        return child
    except Exception as e:
        logger.error(f"Child access verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to verify access",
        )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_home(request: Request, user: dict = Depends(get_current_user)):
    """Parent dashboard home page with authentication."""
    if not templates:
        raise HTTPException(status_code=500, detail="Templates not available")

    try:
        # Sanitize user data before passing to template
        safe_user = _sanitize_template_data(user)
        return templates.TemplateResponse(
            "dashboard.html", {"request": request, "user": safe_user}
        )
    except Exception as e:
        logger.error(f"Dashboard template error: {e}")
        raise HTTPException(status_code=500, detail="Dashboard unavailable")


@router.get("/dashboard/child/{child_id}", response_class=HTMLResponse)
async def child_profile(
    request: Request, child_id: str, user: dict = Depends(get_current_user)
):
    """Child profile page with access control."""
    if not templates:
        raise HTTPException(status_code=500, detail="Templates not available")

    child = await verify_child_access(child_id, user)

    try:
        # Sanitize data before passing to template
        safe_child = _sanitize_template_data(
            child.__dict__ if hasattr(child, "__dict__") else child
        )
        safe_user = _sanitize_template_data(user)
        return templates.TemplateResponse(
            "child_profile.html",
            {"request": request, "child": safe_child, "user": safe_user},
        )
    except Exception as e:
        logger.error(f"Child profile template error: {e}")
        raise HTTPException(status_code=500, detail="Profile unavailable")


@router.get("/dashboard/reports", response_class=HTMLResponse)
async def usage_reports(request: Request, user: dict = Depends(get_current_user)):
    """Usage reports page with authentication."""
    if not templates:
        raise HTTPException(status_code=500, detail="Templates not available")

    try:
        # Sanitize user data before passing to template
        safe_user = _sanitize_template_data(user)
        return templates.TemplateResponse(
            "reports.html", {"request": request, "user": safe_user}
        )
    except Exception as e:
        logger.error(f"Reports template error: {e}")
        raise HTTPException(status_code=500, detail="Reports unavailable")


@router.get("/dashboard/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: dict = Depends(get_current_user)):
    """Settings page with authentication."""
    if not templates:
        raise HTTPException(status_code=500, detail="Templates not available")

    try:
        # Sanitize user data before passing to template
        safe_user = _sanitize_template_data(user)
        return templates.TemplateResponse(
            "settings.html", {"request": request, "user": safe_user}
        )
    except Exception as e:
        logger.error(f"Settings template error: {e}")
        raise HTTPException(status_code=500, detail="Settings unavailable")
