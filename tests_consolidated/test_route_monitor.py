import pytest
from fastapi import FastAPI, APIRouter
from src.infrastructure.routing.route_manager import RouteManager, RouteConflictError
from src.infrastructure.routing.route_monitor import RouteMonitor


@pytest.fixture
def app():
    return FastAPI()


@pytest.fixture
def route_manager(app):
    return RouteManager(app)


@pytest.fixture
def monitor(app):
    return RouteMonitor(app)


def make_router(prefix, tags, path="/test", name="test", require_auth=True):
    router = APIRouter(prefix=prefix, tags=tags)

    @router.get(path, name=name)
    def test_endpoint():
        return {"ok": True}

    return router


def test_register_and_monitor_routes(route_manager, monitor):
    # Register router
    router1 = make_router("/r1", ["r1"])
    route_manager.register_router(router1, "r1", prefix="/r1", tags=["r1"])
    # Monitor should see the route
    scan = monitor.scan_routes()
    assert any("/r1/test" in r for r in scan["routes"])
    # Validate organization
    result = monitor.validate_route_organization()
    assert result["overall_status"] in ("HEALTHY", "MINOR_ISSUES")


def test_conflict_detection(route_manager):
    router1 = make_router("/conflict", ["c"])
    router2 = make_router("/conflict", ["c2"])
    route_manager.register_router(router1, "c1", prefix="/conflict", tags=["c"])
    with pytest.raises(RouteConflictError):
        route_manager.register_router(router2, "c2", prefix="/conflict", tags=["c2"])


def test_prefix_overlap_warning(route_manager):
    router1 = make_router("/api", ["api"])
    router2 = make_router("/api/v1", ["apiv1"])
    route_manager.register_router(router1, "api", prefix="/api", tags=["api"])
    # Should not raise, but log a warning
    route_manager.register_router(router2, "apiv1", prefix="/api/v1", tags=["apiv1"])


def test_unregister_on_failure(app):
    rm = RouteManager(app)
    router1 = make_router("/fail", ["fail"])
    router2 = make_router("/fail", ["fail2"])
    rm.register_router(router1, "fail1", prefix="/fail", tags=["fail"])
    # Force conflict
    with pytest.raises(RouteConflictError):
        rm.register_router(router2, "fail2", prefix="/fail", tags=["fail2"])
    # After failure, no /fail routes should remain for fail2
    assert all(v != "fail2" for v in rm.registered_routes.values())


def test_no_routes_registered(monitor):
    scan = monitor.scan_routes()
    assert scan["overall_status"] in ("WARNING", "HEALTHY")
    # Should not crash if no routes
    doc = monitor.generate_route_report()
    assert isinstance(doc, str)
