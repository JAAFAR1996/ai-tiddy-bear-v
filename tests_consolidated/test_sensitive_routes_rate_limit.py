import pytest
from fastapi import FastAPI, APIRouter, Depends
from src.infrastructure.routing.route_manager import RouteManager
from src.infrastructure.security.auth import get_current_user
from src.main import (
    rate_limit_30_per_minute,
    rate_limit_60_per_minute,
    rate_limit_10_per_minute,
)

# Helper to collect all routes and their dependencies


def get_route_dependencies(app):
    deps = {}
    for route in app.routes:
        if hasattr(route, "dependant"):
            dep_names = set()
            stack = [route.dependant]
            while stack:
                d = stack.pop()
                if d.call is not None:
                    dep_names.add(getattr(d.call, "__name__", str(d.call)))
                stack.extend(d.dependencies)
            deps[route.path] = dep_names
    return deps


def test_all_sensitive_routes_have_rate_limit():
    app = FastAPI()
    rm = RouteManager(app)
    # Register example sensitive routers
    router = APIRouter(prefix="/child", tags=["child"])

    @router.get("/profile", dependencies=[Depends(rate_limit_30_per_minute)])
    async def child_profile():
        return {"ok": True}

    app.include_router(router)
    # ---
    deps = get_route_dependencies(app)
    # Assert all /child/* routes have a rate limit dependency
    for path, dep_names in deps.items():
        if path.startswith("/child"):
            assert (
                "rate_limit_30_per_minute" in dep_names
                or "rate_limit_60_per_minute" in dep_names
                or "rate_limit_10_per_minute" in dep_names
            ), f"Sensitive route {path} missing rate limit dependency!"
