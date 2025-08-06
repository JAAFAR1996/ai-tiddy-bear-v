"""
🧸 AI TEDDY BEAR - ROUTE MANAGER
Enhanced route management system with conflict prevention and unified security
"""

import logging
from typing import Dict, List, Optional, Set
from fastapi import FastAPI, APIRouter, Depends
from fastapi.security import HTTPBearer

from src.infrastructure.security.auth import get_current_user
from src.infrastructure.logging.production_logger import get_logger
from .route_monitor import RouteMonitor

logger = get_logger(__name__, "route_manager")


class RouteConflictError(Exception):
    """Raised when route conflicts are detected."""

    pass


class RouteManager:
    """
    Advanced route management system that prevents conflicts and ensures proper organization.
    Integrates with RouteMonitor for real-time conflict detection.
    """

    def __init__(self, app: FastAPI):
        self.app = app
        self.registered_routes: Dict[str, str] = {}  # path -> router_name
        self.registered_prefixes: Set[str] = set()
        self.security = HTTPBearer()
        self.monitor = RouteMonitor(app)

    def register_router(
        self,
        router: APIRouter,
        router_name: str,
        prefix: Optional[str] = None,
        tags: Optional[List[str]] = None,
        dependencies: Optional[List] = None,
        require_auth: bool = True,
        skip_conflict_check: bool = False,
    ) -> None:
        """
        Register a router with comprehensive conflict detection and unified security.

        Args:
            router: The APIRouter to register
            router_name: Unique name for the router
            prefix: URL prefix for the router
            tags: OpenAPI tags
            dependencies: FastAPI dependencies
            require_auth: Whether to require authentication for all routes
            skip_conflict_check: Skip conflict checking (use with caution)
        """

        logger.info(f"🔄 Registering router '{router_name}' with prefix '{prefix}'")

        # Pre-registration conflict check
        if not skip_conflict_check:
            self._check_prefix_conflicts(prefix, router_name)
            self._check_route_conflicts(router, router_name, prefix or "")

        # Add unified authentication if required
        if require_auth and dependencies is None:
            dependencies = [Depends(get_current_user)]
        elif require_auth and dependencies:
            # Ensure get_current_user is in dependencies
            auth_dep = Depends(get_current_user)
            if auth_dep not in dependencies:
                dependencies.append(auth_dep)

        # Register the router
        try:
            self.app.include_router(
                router, prefix=prefix, tags=tags, dependencies=dependencies
            )

            # Track registered routes
            if prefix:
                self.registered_prefixes.add(prefix)

            self._track_router_routes(router, router_name, prefix or "")

            logger.info(f"✅ Router '{router_name}' registered successfully")
            if prefix:
                logger.info(f"   📍 Prefix: {prefix}")
            if tags:
                logger.info(f"   🏷️ Tags: {tags}")
            if require_auth:
                logger.info(f"   🔐 Authentication: Required")

        except Exception as e:
            logger.error(f"❌ Failed to register router '{router_name}': {str(e)}")
            raise

    def _check_prefix_conflicts(self, prefix: Optional[str], router_name: str) -> None:
        """Check for prefix conflicts with detailed analysis."""
        if not prefix:
            return

        # Direct prefix conflict
        if prefix in self.registered_prefixes:
            raise RouteConflictError(
                f"Prefix '{prefix}' already registered. "
                f"Use a different prefix for router '{router_name}'"
            )

        # Check for overlapping prefixes
        for existing_prefix in self.registered_prefixes:
            if self._prefixes_overlap(prefix, existing_prefix):
                logger.warning(
                    f"⚠️ Potential prefix overlap detected: '{prefix}' vs '{existing_prefix}'"
                )

    def _prefixes_overlap(self, prefix1: str, prefix2: str) -> bool:
        """Check if two prefixes have problematic overlap."""
        # Remove leading/trailing slashes for comparison
        p1 = prefix1.strip("/")
        p2 = prefix2.strip("/")

        # Check if one is a subset of another
        return p1.startswith(p2) or p2.startswith(p1)

    def _check_route_conflicts(
        self, router: APIRouter, router_name: str, prefix: str
    ) -> None:
        """Check for route path conflicts with existing routes."""
        conflicts = []

        for route in router.routes:
            if hasattr(route, "path"):
                full_path = f"{prefix}{route.path}"

                if full_path in self.registered_routes:
                    conflicts.append(
                        f"Path '{full_path}' conflicts with router '{self.registered_routes[full_path]}'"
                    )

        if conflicts:
            raise RouteConflictError(
                f"Router '{router_name}' has conflicts:\n" + "\n".join(conflicts)
            )

    def _track_router_routes(
        self, router: APIRouter, router_name: str, prefix: str
    ) -> None:
        """Track all routes from a router for conflict detection."""
        for route in router.routes:
            if hasattr(route, "path"):
                full_path = f"{prefix}{route.path}"
                self.registered_routes[full_path] = router_name

    def get_registration_summary(self) -> Dict[str, any]:
        """Get a summary of all registered routes and routers."""
        # Run monitor scan to get current state
        scan_results = self.monitor.scan_routes()

        summary = {
            "registration_timestamp": scan_results["scan_timestamp"],
            "total_routes": len(self.registered_routes),
            "total_prefixes": len(self.registered_prefixes),
            "conflicts_detected": scan_results["conflicts_detected"],
            "prefixes": list(self.registered_prefixes),
            "routes_by_router": {},
            "route_health": scan_results.get("overall_status", "UNKNOWN"),
        }

        # Group routes by router
        for path, router_name in self.registered_routes.items():
            if router_name not in summary["routes_by_router"]:
                summary["routes_by_router"][router_name] = []
            summary["routes_by_router"][router_name].append(path)

        return summary

    def validate_all_routes(self) -> bool:
        """Validate all registered routes using the monitor."""
        validation_results = self.monitor.validate_route_organization()

        status = validation_results["overall_status"]
        if status in ["HEALTHY", "MINOR_ISSUES"]:
            logger.info("✅ All routes validated successfully")
            return True
        else:
            logger.error(f"❌ Route validation failed with status: {status}")
            return False

    def generate_route_documentation(self, output_file: Optional[str] = None) -> str:
        """Generate comprehensive route documentation."""
        return self.monitor.generate_route_report()


def register_all_routers(app: FastAPI) -> RouteManager:
    """
    Register all application routers with proper conflict resolution and monitoring.
    This replaces the existing include_api_routes() function with enhanced capabilities.

    Args:
        app: FastAPI application instance

    Returns:
        RouteManager instance for further monitoring
    """
    route_manager = RouteManager(app)

    try:
        logger.info(
            "🚀 Starting unified router registration with conflict detection..."
        )

        # 1. Authentication Router (highest priority - no auth required)
        try:
            from src.adapters.auth_routes import router as auth_router

            route_manager.register_router(
                router=auth_router,
                router_name="authentication",
                # Note: auth_router already has prefix="/api/auth"
                require_auth=False,  # Auth routes don't need auth
                skip_conflict_check=False,
            )
            logger.info("✅ Authentication router registered")
        except ImportError as e:
            logger.error(f"❌ Failed to load auth router: {e}")

        # 2. Dashboard Router (requires auth)
        try:
            from src.adapters.dashboard_routes import router as dashboard_router

            route_manager.register_router(
                router=dashboard_router,
                router_name="dashboard",
                # Note: dashboard_router already has prefix="/api/dashboard"
                require_auth=True,
            )
            logger.info("✅ Dashboard router registered")
        except ImportError as e:
            logger.error(f"❌ Failed to load dashboard router: {e}")

        # 3. Core API Router (chat, health, etc.) - FIXED PREFIX to avoid conflict
        try:
            from src.adapters.api_routes import router as main_api_router

            route_manager.register_router(
                router=main_api_router,
                router_name="core_api",
                prefix="/api/v1/core",  # Changed to avoid conflict
                tags=["Core API"],
                require_auth=True,
            )
            logger.info("✅ Core API router registered")
        except ImportError as e:
            logger.error(f"❌ Failed to load core API router: {e}")

        # 4. ESP32 Router - FIXED PREFIX to avoid conflict
        try:
            from src.adapters.esp32_router import router as esp32_router

            route_manager.register_router(
                router=esp32_router,
                router_name="esp32",
                prefix="/api/v1/esp32",  # Changed from "/api/v1"
                tags=["ESP32"],
                require_auth=True,
            )
            logger.info("✅ ESP32 router registered")
        except ImportError as e:
            logger.error(f"❌ Failed to load ESP32 router: {e}")

        # 5. Web Interface Router (templates) - SEPARATED from API
        try:
            from src.adapters.web import router as web_router

            route_manager.register_router(
                router=web_router,
                router_name="web_interface",
                prefix="/web",  # Separate from API
                tags=["Web Interface"],
                require_auth=True,
            )
            logger.info("✅ Web interface router registered")
        except ImportError as e:
            logger.error(f"❌ Failed to load web router: {e}")

        # 6. Premium Subscriptions Router
        try:
            from src.presentation.api.endpoints.premium.subscriptions import (
                router as premium_router,
            )

            route_manager.register_router(
                router=premium_router,
                router_name="premium_subscriptions",
                # Note: premium_router already has prefix="/api/v1/premium"
                require_auth=True,
            )
            logger.info("✅ Premium subscriptions router registered")
        except ImportError as e:
            logger.warning(f"⚠️ Premium subscriptions router not available: {e}")

        # 7. Payment System Router
        try:
            from src.application.services.payment.api.production_endpoints import (
                router as payment_router,
            )

            route_manager.register_router(
                router=payment_router,
                router_name="payment_system",
                # Note: payment_router already has prefix="/api/v1/payments"
                require_auth=True,
            )
            logger.info("✅ Payment system router registered")
        except ImportError as e:
            logger.warning(f"⚠️ Payment system router not available: {e}")

        # 8. Iraqi Payment Integration Router
        try:
            from src.presentation.api.endpoints.iraqi_payments import (
                router as iraqi_payment_router,
            )

            route_manager.register_router(
                router=iraqi_payment_router,
                router_name="iraqi_payment_integration",
                prefix="/api/v1/iraqi-payments",  # Explicit prefix to avoid conflicts
                tags=["Iraqi Payment Integration"],
                require_auth=True,
            )
            logger.info("✅ Iraqi payment integration router registered")
        except ImportError as e:
            logger.warning(f"⚠️ Iraqi payment integration router not available: {e}")

        # 9. WebSocket Router
        try:
            from src.presentation.api.websocket.parent_notifications import (
                router as websocket_router,
            )

            route_manager.register_router(
                router=websocket_router,
                router_name="websocket_notifications",
                # Note: websocket_router already has prefix="/ws"
                require_auth=True,
            )
            logger.info("✅ WebSocket notifications router registered")
        except ImportError as e:
            logger.warning(f"⚠️ WebSocket router not available: {e}")

        # Final validation
        if route_manager.validate_all_routes():
            logger.info(
                "✅ All routers registered successfully with no conflicts detected"
            )

            # Log summary
            summary = route_manager.get_registration_summary()
            logger.info(f"📊 Registration Summary:")
            logger.info(f"   Total Routes: {summary['total_routes']}")
            logger.info(f"   Total Prefixes: {summary['total_prefixes']}")
            logger.info(f"   Route Health: {summary['route_health']}")

            for router_name, routes in summary["routes_by_router"].items():
                logger.info(f"   {router_name}: {len(routes)} routes")
        else:
            logger.error("❌ Route validation failed after registration")
            # Generate detailed report for debugging
            report = route_manager.generate_route_documentation()
            logger.error("📄 Detailed route analysis:")
            for line in report.split("\n")[:20]:  # Log first 20 lines
                logger.error(f"   {line}")

            raise RouteConflictError("Route validation failed after registration")

    except Exception as e:
        logger.error(f"❌ Router registration failed: {str(e)}")
        raise

    return route_manager


def setup_unified_authentication() -> None:
    """
    Setup unified authentication middleware.
    This ensures all protected routes use the same auth mechanism.
    """
    logger.info("🔐 Setting up unified authentication...")

    # This is handled by the RouteManager.register_router() method
    # which automatically adds get_current_user dependency to protected routes

    logger.info("✅ Unified authentication configured")


def get_route_documentation(app: FastAPI) -> Dict[str, any]:
    """Get comprehensive route documentation for debugging and monitoring."""
    monitor = RouteMonitor(app)

    return {
        "route_summary": monitor.get_route_summary(),
        "validation_results": monitor.validate_route_organization(),
        "detailed_report": monitor.generate_route_report(),
    }
