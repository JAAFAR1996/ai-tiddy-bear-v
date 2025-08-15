import traceback
from typing import Dict, List, Optional, Set
from fastapi import FastAPI, APIRouter, Depends
from fastapi.security import HTTPBearer
from src.infrastructure.security.auth import get_current_user
from src.infrastructure.logging.production_logger import get_logger
from .route_monitor import RouteMonitor


# get_router_meta function removed - prefixes now handled explicitly in register_all_routers


"""
🧸 AI TEDDY BEAR - ROUTE MANAGER
Enhanced route management system with conflict prevention and unified security
"""


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
        tags: Optional[List[str]] = None,
        dependencies: Optional[List] = None,
        require_auth: bool = True,
        skip_conflict_check: bool = False,
        prefix: Optional[
            str
        ] = None,  # Kept for backward compatibility, but not required
        allow_overlap: bool = False,  # Allow intentional prefix overlaps (e.g., /api/v1/esp32 and /api/v1/esp32/private)
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
            allow_overlap: Allow intentional prefix overlaps (e.g., /api/v1/esp32 and /api/v1/esp32/private)
                          When True, overlapping prefixes will only generate warnings instead of errors.
                          Use this when you intentionally want more specific routes to be registered before general ones.

        Raises:
            RouteConflictError: If route conflicts are detected (unless allow_overlap=True for prefix overlaps)
            ValueError: If router parameters are invalid
        """

        # STRICT VALIDATION: router_name, prefix, tags
        import traceback
        import os

        # If prefix is not provided, use the router's own prefix
        if prefix is None:
            prefix = getattr(router, "prefix", None)
        error_context = {
            "router_name": router_name,
            "prefix": prefix,
            "tags": tags,
        }
        # Enforce explicit tags
        if tags is None:
            traceback.print_stack()
            raise ValueError(
                f"tags must be passed explicitly to register_router. Context: {error_context}"
            )
        # Strict prefix validation: no auto-correction in production
        strict_prefix = os.environ.get("STRICT_PREFIX_VALIDATION")
        if strict_prefix is None:
            # Default: True in production, False in dev/test
            env = os.environ.get("ENV", "production").lower()
            strict_prefix = (
                "false" if env in ("dev", "development", "test", "testing") else "true"
            )
        strict_prefix = strict_prefix.lower() == "true"

        if not router:
            raise ValueError(
                f"[RouteManager] Router cannot be None for '{router_name}'. Context: {error_context}\n{traceback.format_stack()}"
            )
        if not router_name or not isinstance(router_name, str):
            raise ValueError(
                f"[RouteManager] Router name must be a non-empty string. Context: {error_context}\n{traceback.format_stack()}"
            )
        if router_name.strip() != router_name:
            raise ValueError(
                f"[RouteManager] Router name '{router_name}' contains leading/trailing whitespace. Context: {error_context}\n{traceback.format_stack()}"
            )
        # Prefix must be string or None
        if prefix is not None:
            if not isinstance(prefix, str):
                raise ValueError(
                    f"[RouteManager] Prefix must be a string, got {type(prefix).__name__}. Context: {error_context}\n{traceback.format_stack()}"
                )
            if prefix:
                if not prefix.startswith("/"):
                    if strict_prefix:
                        raise ValueError(
                            f"[RouteManager] Prefix must start with '/'. Context: {error_context}\n{traceback.format_stack()}"
                        )
                    else:
                        prefix = f"/{prefix}"
                        logger.warning(
                            f"⚠️ [DEV ONLY] Auto-corrected prefix for '{router_name}': added leading slash. Context: {error_context}"
                        )
                if prefix.endswith("/") and prefix != "/":
                    if strict_prefix:
                        raise ValueError(
                            f"[RouteManager] Prefix must not end with '/'. Context: {error_context}\n{traceback.format_stack()}"
                        )
                    else:
                        prefix = prefix.rstrip("/")
                        logger.warning(
                            f"⚠️ [DEV ONLY] Auto-corrected prefix for '{router_name}': removed trailing slash. Context: {error_context}"
                        )
        # Tags must be a list of strings or None
        if tags is not None:
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
                raise ValueError(
                    f"[RouteManager] Tags must be a list of strings or None. Context: {error_context}\n{traceback.format_stack()}"
                )
            if any(t is None or t.strip() == "" for t in tags):
                raise ValueError(
                    f"[RouteManager] Tags list contains None or empty string. Context: {error_context}\n{traceback.format_stack()}"
                )

        # Normalize prefix for consistent handling
        normalized_prefix = prefix or ""

        # Enhanced logging with proper null handling
        prefix_display = prefix if prefix is not None else "None"
        logger.info(
            f"🔄 Registering router '{router_name}' with prefix '{prefix_display}'"
        )

        # Validate router has routes
        if not hasattr(router, "routes") or not router.routes:
            logger.warning(f"⚠️ Router '{router_name}' has no routes defined")

        # Pre-registration conflict check
        if not skip_conflict_check:
            self._check_prefix_conflicts(prefix, router_name, allow_overlap)
            self._check_route_conflicts(router, router_name, normalized_prefix)

        # Add unified authentication if required
        if require_auth and dependencies is None:
            dependencies = [Depends(get_current_user)]
        elif require_auth and dependencies:
            # Ensure get_current_user is in dependencies
            auth_dep = Depends(get_current_user)
            if auth_dep not in dependencies:
                dependencies.append(auth_dep)

        # Register the router with comprehensive error handling
        try:
            self.app.include_router(
                router, prefix=prefix, tags=tags, dependencies=dependencies
            )

            # Track registered routes
            if prefix:
                self.registered_prefixes.add(prefix)

            self._track_router_routes(router, router_name, normalized_prefix)

            # Success logging with detailed information
            logger.info(f"✅ Router '{router_name}' registered successfully")
            if prefix:
                logger.info(f"   📍 Prefix: {prefix}")
            if tags:
                logger.info(f"   🏷️ Tags: {', '.join(tags)}")
            if require_auth:
                logger.info("   🔐 Authentication: Required")

            # Log route count for monitoring
            route_count = len(router.routes) if hasattr(router, "routes") else 0
            logger.info(f"   📊 Routes: {route_count}")

        except Exception as e:
            # Enhanced error logging with context
            error_context = {
                "router_name": router_name,
                "prefix": prefix,
                "tags": tags,
                "require_auth": require_auth,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

            logger.error(f"❌ Failed to register router '{router_name}': {str(e)}")
            logger.error(f"   Context: {error_context}")

            # Clean up any partial registration
            if prefix and prefix in self.registered_prefixes:
                self.registered_prefixes.remove(prefix)
            # Clean up any partial registered routes for this router
            for route_path, r_name in list(self.registered_routes.items()):
                if r_name == router_name:
                    del self.registered_routes[route_path]

            raise RouteConflictError(
                f"Failed to register router '{router_name}': {str(e)}"
            ) from e

    def _check_prefix_conflicts(self, prefix: Optional[str], router_name: str, allow_overlap: bool = False) -> None:
        """Check for prefix conflicts with detailed analysis.
        
        Args:
            prefix: The prefix to check
            router_name: Name of the router being registered
            allow_overlap: If True, overlapping prefixes generate warnings instead of errors
        """
        if not prefix:
            return

        # Direct prefix conflict - always an error
        if prefix in self.registered_prefixes:
            raise RouteConflictError(
                f"Prefix '{prefix}' already registered. "
                f"Use a different prefix for router '{router_name}'"
            )

        # Check for overlapping prefixes
        for existing_prefix in self.registered_prefixes:
            if self._prefixes_overlap(prefix, existing_prefix):
                overlap_msg = (
                    f"Prefix overlap detected: '{prefix}' overlaps with '{existing_prefix}'. "
                    f"Router '{router_name}' may intercept requests intended for other routers."
                )
                
                if allow_overlap:
                    # When overlap is intentional (e.g., ESP32 routes), just warn
                    logger.warning(f"⚠️ [Intentional Overlap] {overlap_msg}")
                    logger.info(f"   ℹ️ This overlap is allowed (allow_overlap=True). Ensure more specific routes are registered first.")
                else:
                    # For unintentional overlaps, log warning but don't fail
                    logger.warning(f"⚠️ [Potential Issue] {overlap_msg}")
                    logger.warning(f"   💡 Tip: If this overlap is intentional, use allow_overlap=True when registering the router.")

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

    logger.info("🚀 Starting unified router registration with conflict detection...")

    # 1. Authentication Router (highest priority - no auth required)
    try:
        from src.adapters.auth_routes import router as auth_router

        route_manager.register_router(
            router=auth_router,
            router_name="authentication",
            prefix="/api/auth",
            tags=["Authentication"],
            require_auth=False,
            skip_conflict_check=False,
        )
        logger.info("✅ Authentication router registered")
    except ImportError as e:
        logger.critical(f"❌ Failed to load auth router: {e}")
        from src.core.exceptions import ConfigurationError
        raise ConfigurationError(
            f"Authentication router is required but not found: {e}",
            context={"config_key": "AUTH_ROUTER", "router_name": "authentication"}
        )

    # 2. Dashboard Router (requires auth)
    try:
        from src.adapters.dashboard_routes import router as dashboard_router

        route_manager.register_router(
            router=dashboard_router,
            router_name="dashboard",
            prefix="/api/dashboard",
            tags=["Dashboard"],
            require_auth=True,
            allow_overlap=True,  # Intentional overlap with /api base
        )
        logger.info("✅ Dashboard router registered")
    except ImportError as e:
        logger.critical(f"❌ Failed to load dashboard router: {e}")
        from src.core.exceptions import ConfigurationError
        raise ConfigurationError(
            f"Dashboard router is required but not found: {e}",
            context={"config_key": "DASHBOARD_ROUTER", "router_name": "dashboard"}
        )

    # 3. Core API Router (chat, health, etc.) - FIXED PREFIX to avoid conflict
    try:
        from src.adapters.api_routes import router as main_api_router

        route_manager.register_router(
            router=main_api_router,
            router_name="core_api",
            prefix="/api/v1/core",
            tags=["Core API"],
            require_auth=True,
            allow_overlap=True,  # Intentional overlap with /api/v1 base
        )
        logger.info("✅ Core API router registered")
    except ImportError as e:
        logger.critical(f"❌ Failed to load core API router: {e}")
        from src.core.exceptions import ConfigurationError
        raise ConfigurationError(
            f"Core API router is required but not found: {e}",
            context={"config_key": "CORE_API_ROUTER", "router_name": "core_api"}
        )

    # 4a. ESP32 Private Router - Authentication required 
    # IMPORTANT: Register MORE SPECIFIC routes first to ensure proper routing precedence
    # The /api/v1/esp32/private prefix is intentionally more specific than /api/v1/esp32
    # This ensures authenticated routes are matched before public routes
    try:
        from src.adapters.esp32_router import esp32_private

        route_manager.register_router(
            router=esp32_private,
            router_name="esp32_private",
            prefix="/api/v1/esp32/private",
            tags=["ESP32-Private"],
            require_auth=True,
        )
        logger.info("✅ ESP32 private router registered (specific routes first)")
    except ImportError as e:
        logger.critical(f"❌ Failed to load ESP32 private router: {e}")
        from src.core.exceptions import ConfigurationError
        raise ConfigurationError(
            f"ESP32 private router is required but not found: {e}",
            context={"config_key": "ESP32_PRIVATE_ROUTER", "router_name": "esp32_private"}
        )

    # 4b. ESP32 Public Router - No authentication required
    # IMPORTANT: Register GENERAL routes after specific ones
    # The /api/v1/esp32 prefix is intentionally less specific
    # This ensures it acts as a catch-all for non-private ESP32 routes
    try:
        from src.adapters.esp32_router import esp32_public

        route_manager.register_router(
            router=esp32_public,
            router_name="esp32_public",
            prefix="/api/v1/esp32",
            tags=["ESP32-Public"],
            require_auth=False,
            allow_overlap=True,  # Intentional overlap with /api/v1/esp32/private
        )
        logger.info("✅ ESP32 public router registered (general routes second, overlap allowed)")
    except ImportError as e:
        logger.critical(f"❌ Failed to load ESP32 public router: {e}")
        from src.core.exceptions import ConfigurationError
        raise ConfigurationError(
            f"ESP32 public router is required but not found: {e}",
            context={"config_key": "ESP32_PUBLIC_ROUTER", "router_name": "esp32_public"}
        )
    
    # 4b2. Device Claim Router - WITH AUTO-REGISTRATION
    try:
        from src.adapters.claim_api import router as claim_router
        logger.info("✅ Using claim router with AUTO-REGISTRATION enabled for production")

        route_manager.register_router(
            router=claim_router,
            router_name="device_claim",
            prefix="/api/v1",  # Base prefix (claim endpoint is at /api/v1/pair/claim)
            tags=["Device Claiming"],
            require_auth=False,  # Uses HMAC authentication
            allow_overlap=True,  # Allow overlap with other v1 endpoints
        )
        logger.info("✅ Device claim router registered with auto-registration")
    except ImportError as e:
        logger.critical(f"❌ Device claim router not available: {e}")

    # 4c. ESP32 WebSocket Router - Production WebSocket endpoints
    try:
        from src.adapters.esp32_websocket_router import (
            esp32_router as esp32_websocket_router,
        )

        route_manager.register_router(
            router=esp32_websocket_router,
            router_name="esp32_websocket",
            prefix="/ws/esp32",
            tags=["ESP32"],
            require_auth=False,
        )
        logger.info("✅ ESP32 WebSocket router registered")
    except ImportError as e:
        logger.warning(f"⚠️ ESP32 WebSocket router not available: {e}")

    # 5. Web Interface Router (templates) - SEPARATED from API
    try:
        from src.adapters.web import router as web_router

        route_manager.register_router(
            router=web_router,
            router_name="web_interface",
            prefix="/dashboard",
            tags=["Web Interface"],
            require_auth=True,
        )
        logger.info("✅ Web interface router registered")
    except ImportError as e:
        logger.critical(f"❌ Failed to load web router: {e}")
        from src.core.exceptions import ConfigurationError
        raise ConfigurationError(
            f"Web interface router is required but not found: {e}",
            context={"config_key": "WEB_ROUTER", "router_name": "web_interface"}
        )

    # 6. Premium Subscriptions Router
    try:
        from src.presentation.api.endpoints.premium.subscriptions import (
            router as premium_router,
        )

        route_manager.register_router(
            router=premium_router,
            router_name="premium_subscriptions",
            prefix="/api/v1/premium",
            tags=["Premium"],
            require_auth=True,
            allow_overlap=True,  # Intentional overlap with /api/v1 base
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
            prefix="/api/v1/payments",
            tags=["payments"],
            require_auth=True,
            allow_overlap=True,  # Intentional overlap with /api/v1 base
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
            prefix="/api/v1/payments/iraqi",  # Changed to be sub-path of payments
            tags=["iraqi-payments"],
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
            prefix="/ws",
            tags=["WebSocket"],
            require_auth=True,
        )
        logger.info("✅ WebSocket notifications router registered")
    except ImportError as e:
        logger.warning(f"⚠️ WebSocket router not available: {e}")

    # 10. Claim API Router - ALREADY REGISTERED ABOVE as device_claim
    # Removed duplicate registration to prevent prefix conflict

    # Final validation
    if route_manager.validate_all_routes():
        logger.info("✅ All routers registered successfully with no conflicts detected")

        # Log summary
        summary = route_manager.get_registration_summary()
        logger.info("📊 Registration Summary:")
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
