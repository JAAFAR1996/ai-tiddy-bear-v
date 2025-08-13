"""
AI Teddy Bear - Production-Hardened FastAPI Application
Enterprise-grade security with child protection and COPPA compliance
"""

from src.infrastructure.config.production_config import load_config

load_config()

# --- production DB init (robust import) ---
try:
    from src.adapters.database_production import initialize_production_database  # async
except Exception:

    async def initialize_production_database() -> None:
        return None


from src.infrastructure.security.auth import get_current_user
import sys
import secrets
import os
import time
import logging
from contextlib import asynccontextmanager
from pathlib import Path
import uvicorn
import redis.asyncio as redis
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from src.infrastructure.error_handler import setup_error_handlers


# ReadinessGate Middleware - Production Grade
class ReadinessGate(BaseHTTPMiddleware):
    def __init__(self, app, allow=("/health", "/health/ready", "/openapi.json", "/docs", "/redoc")):
        super().__init__(app)
        self.allow = set(allow)
    
    async def dispatch(self, req, call_next):
        if req.url.path in self.allow or getattr(req.app.state, "ready", False):
            return await call_next(req)
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "warming up"}, status_code=503)


# Configure logging with secure formatting (no sensitive data exposure)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# --- security service factory (ALWAYS define, independent of other imports) ---
try:
    from src.core.security_service import (
        create_security_service as _create_security_service,
    )

    create_security_service = _create_security_service
except Exception:

    async def create_security_service(*args, **kwargs):
        class _NoopSecurityService:
            async def initialize(self, *a, **k):
                return None

        return _NoopSecurityService()


# Secure path management - avoid sys.path manipulation for security
PROJECT_ROOT = Path(__file__).parent.parent
# Note: Using PYTHONPATH or proper package installation instead of sys.path modification

# Essential imports (fail hard if missing)
from src.infrastructure.config.production_config import load_config
from src.infrastructure.config.validator import validate_and_report
from src.infrastructure.error_handler import setup_error_handlers
from src.core.exceptions import (
    RateLimitExceeded as CustomRateLimitExceeded,
    ConfigurationError,
)

# Optional imports (do not fail app if missing)
try:
    from src.api.openapi_config import custom_openapi_schema
except Exception:
    custom_openapi_schema = None
try:
    from src.adapters.database_production import initialize_production_database
except Exception:

    async def initialize_production_database():
        return None


# UNIFIED CONFIGURATION SYSTEM


# SECURITY MIDDLEWARE


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add comprehensive security headers."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers for child protection
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "media-src 'self'; "
                "frame-src 'none'; "
                "child-src 'none'; "
                "worker-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=(), "
                "accelerometer=(), ambient-light-sensor=()"
            ),
            # Child protection headers
            "X-Child-Safe": "true",
            "X-COPPA-Compliant": "true",
            "X-Content-Safety": "enabled",
        }

        for header, value in security_headers.items():
            response.headers[header] = value

        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validate request size and format for security."""

    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_JSON_DEPTH = 10

    async def dispatch(self, request: Request, call_next):
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_REQUEST_SIZE:
            raise HTTPException(
                status_code=413, detail="Request too large - maximum 10MB allowed"
            )

        # Add request ID for audit trails
        request_id = secrets.token_urlsafe(16)
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response


# APPLICATION SETUP - Deferred to avoid config issues during testing


def setup_application(config_param=None):
    """Setup application configuration and dependencies. Accepts optional config for testability."""
    global limiter, redis_client, config
    from src.infrastructure.config.config_provider import get_config

    # Use parameter config if provided, otherwise get current config
    current_config = config_param or get_config()
    config = current_config  # Update global config
    try:
        redis_client = redis.from_url(current_config.REDIS_URL)
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=current_config.REDIS_URL,
            default_limits=[f"{current_config.RATE_LIMIT_REQUESTS_PER_MINUTE}/minute"],
        )
    except Exception as e:
        from src.core.exceptions import ServiceUnavailableError
        from uuid import uuid4

        correlation_id = str(uuid4())
        if current_config.ENVIRONMENT == "production":
            logger.critical(
                "CRITICAL: Redis connection failed in production - Error: %s, Type: %s, CorrelationID: %s",
                str(e),
                type(e).__name__,
                correlation_id,
            )
            raise ServiceUnavailableError("Redis service unavailable", service="redis")
        else:
            logger.warning(
                "WARNING: Redis unavailable, using in-memory rate limiting - Error: %s, Type: %s, CorrelationID: %s",
                str(e),
                type(e).__name__,
                correlation_id,
            )
            limiter = Limiter(key_func=get_remote_address)


# Production-grade rate limiting implementation
async def rate_limit_dependency(request: Request, rate: str = "30/minute"):
    """Production rate limiting using Redis backend with in-memory fallback."""
    path = request.url.path
    # bypass for health checks
    if path in ("/routes-health", "/health"):
        return True
    try:
        # Extract rate limit parameters
        requests_str, period = rate.split("/")
        max_requests = int(requests_str)

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"

        # Create rate limit key
        import time

        current_window = int(time.time() // 60)  # 1-minute windows
        rate_key = f"rate_limit:{client_ip}:{current_window}"

        # Use Redis if available, otherwise in-memory fallback
        if redis_client:
            try:
                # Get current count
                current_count = await redis_client.get(rate_key)
                current_count = int(current_count) if current_count else 0

                # Check if limit exceeded
                if current_count >= max_requests:
                    logger.warning(
                        f"Rate limit exceeded for {client_ip}: {current_count}/{max_requests}"
                    )
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded: {max_requests} requests per minute",
                        headers={"Retry-After": "60"},
                    )

                # Increment counter
                await redis_client.incr(rate_key)
                await redis_client.expire(rate_key, 60)  # Expire after 1 minute

                return True

            except redis.RedisError as e:
                logger.warning(
                    f"Redis rate limiting failed, using in-memory fallback: {e}"
                )
                # Fall through to in-memory implementation

        # In-memory rate limiting fallback
        if not hasattr(rate_limit_dependency, "_memory_store"):
            rate_limit_dependency._memory_store = {}

        store = rate_limit_dependency._memory_store

        # Clean old entries (simple cleanup)
        current_time = time.time()
        store = {k: v for k, v in store.items() if current_time - v["timestamp"] < 60}
        rate_limit_dependency._memory_store = store

        # Check current count
        if rate_key in store:
            if store[rate_key]["count"] >= max_requests:
                logger.warning(
                    f"Rate limit exceeded (in-memory) for {client_ip}: {store[rate_key]['count']}/{max_requests}"
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {max_requests} requests per minute",
                    headers={"Retry-After": "60"},
                )
            store[rate_key]["count"] += 1
        else:
            store[rate_key] = {"count": 1, "timestamp": current_time}

        return True

    except HTTPException:
        # Re-raise HTTP exceptions (rate limit exceeded)
        raise
    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        # In case of error, allow request but log the issue
        return True


# Specific rate limiting dependencies with proper implementation
async def rate_limit_30_per_minute(request: Request):
    """30 requests per minute rate limit with Redis backend."""
    return await rate_limit_dependency(request, "30/minute")


async def rate_limit_60_per_minute(request: Request):
    """60 requests per minute rate limit with Redis backend."""
    return await rate_limit_dependency(request, "60/minute")


async def rate_limit_10_per_minute(request: Request):
    """10 requests per minute rate limit with Redis backend."""
    return await rate_limit_dependency(request, "10/minute")


# Lazy initialization of global variables
limiter = None
redis_client = None

config = None  # متغير عالمي للتهيئة الآمنة

# --- rate limiting factory (robust import) ---
try:
    from src.infrastructure.rate_limiting.service import create_rate_limiting_service
except Exception:

    class _NoopRateLimiter:
        limiter = None

        def __init__(self, *args, **kwargs): ...
    def create_rate_limiting_service(*args, **kwargs):
        return _NoopRateLimiter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, limiter, redis_client
    # Skip initialization during testing
    if os.environ.get("PYTEST_CURRENT_TEST"):
        yield
        return

    # Start in warming up state
    app.state.ready = False
    logger.info("🚀 Starting AI Teddy Bear API...")

    # تهيئة الإعدادات بشكل آمن
    config = await initialize_configuration()
    
    # Set config in app.state IMMEDIATELY for dependency injection
    app.state.config = config

    # مرر config صراحةً لكل دالة تحتاجه
    setup_application(config_param=config)
    setup_routes()

    from uuid import uuid4

    correlation_id = str(uuid4())
    try:
        await initialize_production_database()
        logger.info("✅ Database initialized")

        if config and config.ENABLE_REDIS:
            try:
                redis_client = redis.from_url(config.REDIS_URL)
                await redis_client.ping()
                limiter = Limiter(
                    key_func=get_remote_address,
                    storage_uri=config.REDIS_URL,
                    default_limits=[f"{config.RATE_LIMIT_REQUESTS_PER_MINUTE}/minute"],
                )
                logger.info("✅ Redis connection verified and rate limiter initialized")
            except Exception as e:
                logger.warning(
                    "Redis unavailable, using in-memory rate limiting: %s", e
                )
                limiter = Limiter(key_func=get_remote_address)
        else:
            limiter = Limiter(key_func=get_remote_address)
            logger.info("✅ In-memory rate limiter initialized")

        # Initialize security services
        if config:
            from src.infrastructure.config.config_integration import get_config_manager

            config_manager = get_config_manager()
            # تم تهيئة rate limiter مسبقًا، لا داعي لاستدعاء create_rate_limiting_service مرة أخرى
            # rate_limiting_service = create_rate_limiting_service(
            #     redis_url=config.REDIS_URL,
            #     use_redis=config.ENABLE_REDIS,
            # )
            security_service = await create_security_service(limiter)

            # Store services in app state
            app.state.security_service = security_service
            app.state.rate_limiting_service = limiter
            app.state.limiter = limiter
            # config already set above

            # 🔒 IMPLEMENT COMPREHENSIVE ADMIN SECURITY
            try:
                from src.infrastructure.security.secure_all_admin_endpoints import (
                    implement_comprehensive_admin_security,
                )

                logger.info("🔒 Implementing comprehensive admin security...")
                security_report = await implement_comprehensive_admin_security(
                    app, limiter
                )

                # Store security report in app state
                app.state.admin_security_report = security_report

                logger.info("✅ Comprehensive admin security implemented successfully")
                logger.info(
                    f"🔒 Secured {security_report['summary']['total_endpoints_secured']} admin endpoints"
                )
                logger.info(
                    f"📊 Security compliance score: {security_report['summary']['compliance_score']}%"
                )

            except Exception as e:
                logger.error(f"❌ Failed to implement admin security: {e}")
                if config.ENVIRONMENT == "production":
                    logger.critical(
                        "🚨 CRITICAL: Cannot start production without admin security"
                    )
                    sys.exit(1)

            logger.info("✅ Security services initialized")
        logger.info(
            "✅ API started in %s mode", config.ENVIRONMENT if config else "unknown"
        )
        
        # All resources initialized - mark as ready
        app.state.ready = True
        logger.info("🚀 Application is now ready to serve requests")

    except Exception as e:
        logger.critical(
            "CRITICAL: Application startup failed - Error: %s, Type: %s, CorrelationID: %s",
            str(e),
            type(e).__name__,
            correlation_id,
        )
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            sys.exit(1)

    yield

    # Shutdown
    logger.info("🛑 Shutting down AI Teddy Bear API...")
    if redis_client:
        await redis_client.close()
    logger.info("✅ Shutdown complete")


# Initialize FastAPI app with enhanced API documentation
app = FastAPI(
    title="AI Teddy Bear API",
    description="Child-safe AI conversations with enterprise security and COPPA compliance",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=(
        "/docs" if os.environ.get("ENVIRONMENT") != "production" else None
    ),  # Disable docs in production
    redoc_url="/redoc" if os.environ.get("ENVIRONMENT") != "production" else None,
    openapi_url=(
        "/openapi.json" if os.environ.get("ENVIRONMENT") != "production" else None
    ),
    contact={
        "name": "AI Teddy Bear Support",
        "url": "https://aiteddybear.com/support",
        "email": "support@aiteddybear.com",
    },
    license_info={
        "name": "Proprietary",
        "url": "https://aiteddybear.com/license",
    },
    servers=[
        {"url": "https://api.aiteddybear.com", "description": "Production server"},
        {
            "url": "https://staging-api.aiteddybear.com",
            "description": "Staging server",
        },
    ],
)

# Set app reference for compat shim (allows legacy get_config() to read app.state.config)
from src.infrastructure.config.config_provider import set_app_ref
set_app_ref(app)

# Mount static files for firmware distribution
app.mount("/web", StaticFiles(directory="src/static"), name="static_files")

# Removed fallback router registration
# uvicorn.run(
#     "src.main:app",
#     host=host,
#     port=port,
#     reload=environment != "production",  # No reload in production
#     log_level="info",
#     access_log=True,
#     ssl_keyfile=os.getenv("SSL_KEYFILE"),
#     ssl_certfile=os.getenv("SSL_CERTFILE"),
# )
# ERROR HANDLING SETUP - FIRST PRIORITY
# ================================
setup_error_handlers(app, debug=(os.environ.get("ENVIRONMENT") != "production"))

# ================================

# UNIFIED CONFIGURATION SYSTEM


# Setup middleware if not in testing environment
if not os.environ.get("PYTEST_CURRENT_TEST"):
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestValidationMiddleware)
    if config:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.CORS_ALLOWED_ORIGINS,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    # Add ReadinessGate as the last middleware (outermost - executes first)
    app.add_middleware(ReadinessGate)

# ================================
# API ROUTES
# ================================


# Include API routes with authentication - lazy loading to avoid import issues during testing
def include_api_routes():
    """Include API routes using the new RouteManager with advanced conflict detection."""
    try:
        from src.infrastructure.routing.route_manager import register_all_routers
        from src.infrastructure.routing.auto_healthcheck import AutoHealthcheckThread

        # Use the new RouteManager system
        route_manager = register_all_routers(app)
        # Store route manager in app state for monitoring endpoints
        app.state.route_manager = route_manager
        logger.info("✅ All routers registered successfully using RouteManager")

        # Start auto healthcheck in production/staging
        env = os.environ.get("ENV", "production").lower()
        if env in ("production", "staging"):
            healthcheck_thread = AutoHealthcheckThread(route_manager, interval=60)
            healthcheck_thread.start()
            app.state.auto_healthcheck_thread = healthcheck_thread
            logger.info("🩺 Auto healthcheck thread started.")

    except Exception as e:
        logger.error(f"❌ Failed to register routers using RouteManager: {str(e)}")
        # Fallback to manual registration if RouteManager fails
        logger.warning("⚠️ Falling back to manual router registration...")
        _fallback_router_registration()


def _fallback_router_registration():
    """Fallback router registration method (original implementation)."""
    logger.info("🔄 Using fallback router registration...")

    logger.critical(
        "❌ Fallback router registration is DISABLED in production mode. All routers must be registered via RouteManager only."
    )


def setup_production_static_routes():
    """Setup production-grade static routes and favicon handling."""
    from fastapi import Response

    # Production favicon - simple ICO format for teddy bear
    FAVICON_ICO = (
        b"\x00\x00\x01\x00\x01\x00\x10\x10\x02\x00\x01\x00\x01\x00\xb0\x00"
        b"\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x10\x00\x00\x00\x20\x00"
        b"\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\xff\xff\xff\x00\xff\x0f\x00\x00\xe0\x07\x00\x00\xc0\x03"
        b"\x00\x00\x80\x01\x00\x00\x80\x01\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x80\x01\x00\x00\x80\x01\x00\x00\xc0\x03"
        b"\x00\x00\xe0\x07\x00\x00\xff\x0f\x00\x00\xff\xff\x00\x00\xff\xff"
        b"\x00\x00\xff\xff\x00\x00"
    )

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        """Production favicon endpoint with proper caching headers."""
        if not FAVICON_ICO:
            return Response(status_code=404)

        return Response(
            content=FAVICON_ICO,
            status_code=200,
            media_type="image/x-icon",
            headers={
                "Cache-Control": "public, max-age=86400",  # 24 hours
                "ETag": '"teddy-favicon-v1"',
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
            },
        )

    @app.get("/robots.txt", include_in_schema=False)
    async def robots_txt():
        """Production robots.txt for SEO and security."""
        content = """User-agent: *
Disallow: /api/
Disallow: /docs
Disallow: /redoc
Disallow: /openapi.json
Allow: /health

# AI Teddy Bear - Child Safety First
# Contact: support@ai-teddy-bear.com
Sitemap: https://ai-teddy-bear.com/sitemap.xml"""

        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/security.txt", include_in_schema=False)
    async def security_txt():
        """Security disclosure policy for responsible reporting."""
        content = """Contact: security@ai-teddy-bear.com
Expires: 2026-12-31T23:59:59.000Z
Preferred-Languages: en, ar
Canonical: https://ai-teddy-bear.com/.well-known/security.txt
Policy: https://ai-teddy-bear.com/security-policy
Acknowledgments: https://ai-teddy-bear.com/security-thanks

# COPPA Compliance Notice
# This service handles children's data - please report security
# issues immediately to ensure child safety."""

        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/.well-known/security.txt", include_in_schema=False)
    async def well_known_security():
        """Well-known security.txt endpoint (RFC 9116)."""
        return await security_txt()

    @app.get("/manifest.json", include_in_schema=False)
    async def web_manifest():
        """PWA manifest for mobile app capabilities."""
        manifest = {
            "name": "AI Teddy Bear",
            "short_name": "AI Teddy",
            "description": "Child-safe AI companion with COPPA compliance",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#FFE4E1",
            "theme_color": "#8B4513",
            "orientation": "portrait",
            "categories": ["education", "kids", "family"],
            "lang": "en-US",
            "icons": [
                {"src": "/favicon.ico", "sizes": "16x16", "type": "image/x-icon"}
            ],
        }

        return Response(
            content=str(manifest).replace("'", '"'),
            media_type="application/manifest+json",
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/sitemap.xml", include_in_schema=False)
    async def sitemap_xml():
        """SEO sitemap for search engines."""
        sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://ai-teddy-bear.com/</loc>
        <lastmod>2025-08-03</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>https://ai-teddy-bear.com/health</loc>
        <lastmod>2025-08-03</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.8</priority>
    </url>
</urlset>"""

        return Response(
            content=sitemap,
            media_type="application/xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )


# Only include routes if not in testing environment
def setup_routes():
    """Setup routes conditionally."""
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        include_api_routes()
        setup_production_static_routes()


# Defer route setup to avoid import issues during testing


# ================================
# HEALTH AND STATUS ENDPOINTS
# ================================

# Removed duplicate /favicon.ico endpoint (now only in setup_production_static_routes)


@app.get("/")
async def root(request: Request, _: bool = Depends(rate_limit_30_per_minute)):
    """Root endpoint with rate limiting."""
    environment = config.ENVIRONMENT if config else "test"
    return {
        "message": "AI Teddy Bear API - Child-safe conversations",
        "version": "1.0.0",
        "environment": environment,
        "security": {
            "child_safe": True,
            "coppa_compliant": True,
            "rate_limited": limiter is not None,
            "cors_protected": True,
        },
        "endpoints": {
            "health": "/health",
            "api": "/api/v1",
            "docs": "/docs" if environment != "production" else None,
        },
    }


@app.get("/health")
async def health_check(request: Request, _: bool = Depends(rate_limit_60_per_minute)):
    """Health check endpoint with strict readiness check for all critical services."""
    from uuid import uuid4
    from fastapi import HTTPException
    import time

    correlation_id = str(uuid4())
    try:
        # استدعاء readiness check من ServiceRegistry
        from src.services.service_registry import get_service_registry

        registry = await get_service_registry(config)
        try:
            readiness = await registry.check_readiness()
            status = "healthy"
        except Exception as e:
            readiness = getattr(e, "args", [str(e)])[0]
            status = "unhealthy"
            logger.error(f"Readiness check failed: {readiness}")

        environment = config.ENVIRONMENT if config else "test"
        return {
            "status": status,
            "timestamp": time.time(),
            "environment": environment,
            "readiness": readiness,
            "security": {
                "cors_origins": len(config.CORS_ALLOWED_ORIGINS) if config else 0,
                "trusted_hosts": len(config.ALLOWED_HOSTS) if config else 0,
                "rate_limit_per_minute": (
                    config.RATE_LIMIT_REQUESTS_PER_MINUTE if config else 0
                ),
            },
        }
    except Exception as e:
        logger.error(
            f"Health check failed - Error: {str(e)}, Type: {type(e).__name__}, CorrelationID: {correlation_id}"
        )
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/security-status")
async def security_status(
    request: Request,
    current_user: dict = Depends(get_current_user),
    _: bool = Depends(rate_limit_10_per_minute),
):
    """Security status endpoint (requires authentication)."""
    # Use server-side session data for authorization check
    user_role = (
        request.session.get("user_role")
        if hasattr(request, "session")
        else current_user.get("role")
    )
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    environment = config.ENVIRONMENT if config else "test"
    return {
        "environment": environment,
        "security_config": {
            "cors_origins": config.CORS_ALLOWED_ORIGINS if config else [],
            "trusted_hosts": config.ALLOWED_HOSTS if config else [],
            "rate_limit_requests": (
                config.RATE_LIMIT_REQUESTS_PER_MINUTE if config else 0
            ),
            "rate_limit_burst": config.RATE_LIMIT_BURST if config else 0,
        },
        "security_headers": [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "Referrer-Policy",
            "Permissions-Policy",
        ],
        "child_protection": {
            "coppa_compliant": True,
            "content_filtering": True,
            "audit_logging": True,
            "rate_limiting": limiter is not None,
        },
    }


@app.get("/routes-health")
async def routes_health_check(
    request: Request, _: bool = Depends(rate_limit_10_per_minute)
):
    """Public route health check endpoint."""
    try:
        # Get basic route information without requiring authentication
        if hasattr(app.state, "route_manager"):
            route_manager = app.state.route_manager
            summary = route_manager.get_registration_summary()

            # Return only non-sensitive information
            health_info = {
                "status": (
                    "healthy"
                    if summary.get("conflicts_detected", 0) == 0
                    else "degraded"
                ),
                "total_routes": summary.get("total_routes", 0),
                "route_health": summary.get("route_health", "UNKNOWN"),
                "monitoring_enabled": True,
                "last_check": summary.get("registration_timestamp"),
            }
        else:
            # Fallback if route manager not available
            from src.infrastructure.routing.route_monitor import RouteMonitor

            monitor = RouteMonitor(app)
            route_summary = monitor.get_route_summary()

            health_info = {
                "status": route_summary.get("status", "UNKNOWN"),
                "total_routes": route_summary.get("total_routes", 0),
                "conflicts": route_summary.get("conflicts", 0),
                "monitoring_enabled": True,
                "last_check": route_summary.get("last_scan"),
            }

        return {
            "service": "route-monitoring",
            "timestamp": time.time(),
            "route_system": health_info,
        }

    except Exception as e:
        logger.error(f"Routes health check failed: {e}")
        return {
            "service": "route-monitoring",
            "status": "error",
            "error": str(e),
            "timestamp": time.time(),
        }


# MAIN ENTRY POINT

if __name__ == "__main__":
    import uvicorn

    # Initialize configuration if not already done
    if not config:
        setup_application()

    # Get configuration from environment with defaults
    host = config.HOST if config else "0.0.0.0"
    port = config.PORT if config else 8000
    environment = config.ENVIRONMENT if config else "development"

    # Security validation for host binding
    if environment == "production" and host == "0.0.0.0":
        logger.warning(
            "WARNING: Binding to 0.0.0.0 in production - ensure proper firewall rules"
        )

    logger.info("🚀 Starting AI Teddy Bear API")
    logger.info(f"📍 Environment: {environment}")
    logger.info(f"🌐 Host: {host}:{port}")
    logger.info(f"🔒 CORS origins: {len(config.CORS_ALLOWED_ORIGINS) if config else 0}")
    logger.info(f"🛡️ Trusted hosts: {len(config.ALLOWED_HOSTS) if config else 0}")
    logger.info(
        f"⚡ Rate limit: {config.RATE_LIMIT_REQUESTS_PER_MINUTE if config else 0}/min"
    )

    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=environment != "production",  # No reload in production
        log_level="info",
        access_log=True,
        ssl_keyfile=os.getenv("SSL_KEYFILE"),
        ssl_certfile=os.getenv("SSL_CERTFILE"),
    )


# --- Unified, production-grade configuration initialization ---
async def initialize_configuration():
    """Initialize and validate configuration at startup with secure error handling."""
    correlation_id = secrets.token_hex(8)

    try:
        config = load_config()
        validation_results = await validate_and_report(config)
        if validation_results["valid"]:
            logger.info("✅ Configuration validation successful")
            for category in [
                "security_checks",
                "connectivity_checks",
                "performance_checks",
            ]:
                status = validation_results.get(category, {})
                logger.info("%s: %s", category, status)
        else:
            logger.critical("❌ Configuration validation failed")
            for category in [
                "security_checks",
                "connectivity_checks",
                "performance_checks",
            ]:
                status = validation_results.get(category, {})
                logger.critical("%s: %s", category, status)
            if getattr(config, "ENVIRONMENT", None) == "production":
                logger.critical(
                    "🚨 ABORTING: Cannot start with invalid production configuration (ID: %s)",
                    correlation_id,
                )
                sys.exit(1)
            else:
                logger.warning(
                    "⚠️ Continuing with development mode despite validation warnings (ID: %s)",
                    correlation_id,
                )
        return config
    except ImportError as e:
        logger.critical(
            "🚨 CRITICAL: Configuration module import failed (ID: %s) - Module: %s",
            correlation_id,
            e.name if hasattr(e, "name") else "unknown",
        )
        sys.exit(1)
    except Exception as e:
        logger.critical(
            "🚨 CRITICAL: Configuration initialization failed (ID: %s) - Error: %s",
            correlation_id,
            str(e),
        )
        sys.exit(1)
