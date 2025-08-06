import pytest
from fastapi import FastAPI, APIRouter
from src.infrastructure.routing.route_manager import RouteManager, RouteConflictError


def make_router(prefix, tags, path="/test", name="test", require_auth=True):
    router = APIRouter(prefix=prefix, tags=tags)

    @router.get(path, name=name)
    def test_endpoint():
        return {"ok": True}

    return router


def test_integration_register_all():
    app = FastAPI()
    rm = RouteManager(app)
    # Register main routers
    r1 = make_router("/auth", ["auth"])
    r2 = make_router("/dashboard", ["dashboard"])
    r3 = make_router("/core", ["core"])
    rm.register_router(r1, "auth", prefix="/auth", tags=["auth"])
    rm.register_router(r2, "dashboard", prefix="/dashboard", tags=["dashboard"])
    rm.register_router(r3, "core", prefix="/core", tags=["core"])
    # All should be present
    summary = rm.get_registration_summary()
    assert summary["total_routes"] == 3
    assert summary["total_prefixes"] == 3
    assert summary["route_health"] in ("HEALTHY", "MINOR_ISSUES")


def test_integration_conflict_crash():
    app = FastAPI()
    rm = RouteManager(app)
    r1 = make_router("/same", ["same"])
    r2 = make_router("/same", ["same2"])
    rm.register_router(r1, "same1", prefix="/same", tags=["same"])
    with pytest.raises(RouteConflictError):
        rm.register_router(r2, "same2", prefix="/same", tags=["same2"])
    # After crash, no routes for same2
    assert all(v != "same2" for v in rm.registered_routes.values())


def test_integration_prefix_overlap():
    app = FastAPI()
    rm = RouteManager(app)
    r1 = make_router("/api", ["api"])
    r2 = make_router("/api/v1", ["apiv1"])
    rm.register_router(r1, "api", prefix="/api", tags=["api"])
    rm.register_router(r2, "apiv1", prefix="/api/v1", tags=["apiv1"])
    summary = rm.get_registration_summary()
    assert "/api" in summary["prefixes"]
    assert "/api/v1" in summary["prefixes"]


def test_integration_no_routes():
    app = FastAPI()
    rm = RouteManager(app)
    summary = rm.get_registration_summary()
    assert summary["total_routes"] == 0
    assert summary["route_health"] in ("WARNING", "HEALTHY")
