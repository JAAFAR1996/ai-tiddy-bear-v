"""
Provider Integration - FastAPI Integration Layer
==============================================
FastAPI integration for provider circuit breakers and health monitoring:
- Automatic provider registration and setup
- Health check endpoints with detailed reporting
- Circuit breaker management endpoints
- Real-time monitoring dashboard API
- Provider selection and routing middleware
- Automated failover and recovery workflows
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .provider_registry import ProviderRegistry, ProviderConfiguration, LoadBalancingStrategy, ProviderStatus
from .provider_circuit_breaker import ProviderType, CircuitBreakerConfig, CircuitState
from .provider_health_monitor import HealthCheckType, HealthStatus
from .fallback_logger import FallbackLogger
from ..messaging.event_bus_integration import EventPublisher


class ProviderRegistrationRequest(BaseModel):
    """Provider registration request model."""
    provider_id: str
    provider_type: str
    name: str
    description: str = ""
    endpoint_url: str = ""
    region: str = "unknown"
    weight: int = 100
    max_concurrent_requests: int = 100
    priority: int = 1
    cost_per_request: float = 0.0
    enabled: bool = True
    enable_health_monitoring: bool = True
    health_check_interval: int = 60
    circuit_breaker_config: Optional[Dict[str, Any]] = None
    tags: Dict[str, str] = {}


class ProviderSelectionRequest(BaseModel):
    """Provider selection request model."""
    provider_type: Optional[str] = None
    region: Optional[str] = None
    strategy: str = "health_weighted"
    count: int = 1
    exclude: List[str] = []
    max_cost: Optional[float] = None


class ProviderHealthCheckRequest(BaseModel):
    """Provider health check request model."""
    check_type: str = "basic"
    force_check: bool = False


class CircuitBreakerActionRequest(BaseModel):
    """Circuit breaker action request model."""
    action: str  # "open", "close", "reset"
    reason: str = "Manual intervention"


# Global provider registry
provider_registry = ProviderRegistry()


@asynccontextmanager
async def provider_lifespan(app: FastAPI):
    """Lifespan context manager for provider integration."""
    # Startup
    await provider_registry.start()
    
    try:
        yield
    finally:
        # Shutdown
        await provider_registry.stop()


def get_provider_registry() -> ProviderRegistry:
    """Dependency to get provider registry."""
    return provider_registry


def add_provider_routes(app: FastAPI):
    """Add provider management routes to FastAPI application."""
    
    @app.post("/api/providers/register")
    async def register_provider(
        request: ProviderRegistrationRequest,
        background_tasks: BackgroundTasks,
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Register a new provider."""
        try:
            # Convert request to configuration
            provider_type = ProviderType(request.provider_type)
            
            # Create circuit breaker config if provided
            cb_config = None
            if request.circuit_breaker_config:
                cb_config = CircuitBreakerConfig(
                    provider_id=request.provider_id,
                    provider_type=provider_type,
                    **request.circuit_breaker_config
                )
            
            config = ProviderConfiguration(
                provider_id=request.provider_id,
                provider_type=provider_type,
                name=request.name,
                description=request.description,
                endpoint_url=request.endpoint_url,
                region=request.region,
                weight=request.weight,
                max_concurrent_requests=request.max_concurrent_requests,
                priority=request.priority,
                cost_per_request=request.cost_per_request,
                enabled=request.enabled,
                enable_health_monitoring=request.enable_health_monitoring,
                health_check_interval=request.health_check_interval,
                circuit_breaker_config=cb_config,
                tags=request.tags
            )
            
            # Register provider
            provider_id = await registry.register_provider(config)
            
            return {
                "success": True,
                "provider_id": provider_id,
                "message": f"Provider {provider_id} registered successfully"
            }
            
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    
    @app.delete("/api/providers/{provider_id}")
    async def unregister_provider(
        provider_id: str = Path(...),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Unregister a provider."""
        try:
            await registry.unregister_provider(provider_id)
            return {
                "success": True,
                "message": f"Provider {provider_id} unregistered successfully"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unregistration failed: {str(e)}")
    
    @app.post("/api/providers/select")
    async def select_provider(
        request: ProviderSelectionRequest,
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Select best provider(s) based on criteria."""
        try:
            provider_type = ProviderType(request.provider_type) if request.provider_type else None
            strategy = LoadBalancingStrategy(request.strategy)
            
            if request.count == 1:
                selected = await registry.select_provider(
                    provider_type=provider_type,
                    region=request.region,
                    strategy=strategy,
                    exclude=request.exclude,
                    max_cost=request.max_cost
                )
                return {
                    "selected_provider": selected,
                    "count": 1 if selected else 0
                }
            else:
                selected = await registry.select_providers(
                    count=request.count,
                    provider_type=provider_type,
                    region=request.region,
                    strategy=strategy,
                    exclude=request.exclude,
                    max_cost=request.max_cost
                )
                return {
                    "selected_providers": selected,
                    "count": len(selected)
                }
                
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Selection failed: {str(e)}")
    
    @app.get("/api/providers/{provider_id}/status")
    async def get_provider_status(
        provider_id: str = Path(...),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Get detailed provider status."""
        status = registry.get_provider_status(provider_id)
        if not status:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        return status
    
    @app.get("/api/providers")
    async def list_providers(
        provider_type: Optional[str] = Query(None),
        region: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """List providers with optional filtering."""
        overview = registry.get_registry_overview()
        
        # Get all provider statuses
        providers = []
        for provider_id in registry.providers:
            provider_status = registry.get_provider_status(provider_id)
            
            # Apply filters
            if provider_type and provider_status["provider_type"] != provider_type:
                continue
            if region and provider_status["region"] != region:
                continue
            if status and provider_status["status"] != status:
                continue
            
            providers.append(provider_status)
        
        return {
            "providers": providers,
            "total_count": len(providers),
            "overview": overview
        }
    
    @app.get("/api/providers/overview")
    async def get_registry_overview(
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Get registry overview and statistics."""
        return registry.get_registry_overview()
    
    @app.post("/api/providers/{provider_id}/health-check")
    async def trigger_health_check(
        provider_id: str = Path(...),
        registry: ProviderRegistry = Depends(get_provider_registry),
        background_tasks: BackgroundTasks = None,
        request: ProviderHealthCheckRequest = ProviderHealthCheckRequest()
    ):
        """Trigger health check for a provider."""
        if provider_id not in registry.health_monitors:
            raise HTTPException(status_code=404, detail="Provider health monitor not found")
        
        try:
            check_type = HealthCheckType(request.check_type)
            health_monitor = registry.health_monitors[provider_id]
            
            if request.force_check:
                # Run health check in background
                background_tasks.add_task(
                    health_monitor.perform_health_check,
                    check_type
                )
                return {
                    "success": True,
                    "message": f"Health check scheduled for {provider_id}",
                    "check_type": check_type.value
                }
            else:
                # Get latest health check result
                if check_type in health_monitor.recent_checks:
                    result = health_monitor.recent_checks[check_type]
                    return {
                        "provider_id": provider_id,
                        "check_type": check_type.value,
                        "status": result.status.value,
                        "timestamp": result.timestamp.isoformat(),
                        "response_time": result.response_time,
                        "overall_score": result.get_overall_score(),
                        "errors": result.errors,
                        "warnings": result.warnings
                    }
                else:
                    raise HTTPException(status_code=404, detail="No recent health check results")
                    
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
    
    @app.get("/api/providers/{provider_id}/health-report")
    async def get_health_report(
        provider_id: str = Path(...),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Get comprehensive health report for a provider."""
        if provider_id not in registry.health_monitors:
            raise HTTPException(status_code=404, detail="Provider health monitor not found")
        
        health_monitor = registry.health_monitors[provider_id]
        return health_monitor.get_health_report()
    
    @app.post("/api/providers/{provider_id}/circuit-breaker")
    async def manage_circuit_breaker(
        provider_id: str = Path(...),
        registry: ProviderRegistry = Depends(get_provider_registry),
        request: CircuitBreakerActionRequest = None
    ):
        """Manage circuit breaker state."""
        if provider_id not in registry.circuit_breakers:
            raise HTTPException(status_code=404, detail="Provider circuit breaker not found")
        
        circuit_breaker = registry.circuit_breakers[provider_id]
        
        try:
            if request.action == "open":
                await circuit_breaker.force_open(request.reason)
            elif request.action == "close":
                await circuit_breaker.force_close(request.reason)
            elif request.action == "reset":
                await circuit_breaker.reset_metrics()
            else:
                raise HTTPException(status_code=400, detail="Invalid action. Use 'open', 'close', or 'reset'")
            
            return {
                "success": True,
                "action": request.action,
                "provider_id": provider_id,
                "current_state": circuit_breaker.state.value,
                "message": f"Circuit breaker {request.action} completed for {provider_id}"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Circuit breaker action failed: {str(e)}")
    
    @app.get("/api/providers/{provider_id}/circuit-breaker")
    async def get_circuit_breaker_status(
        provider_id: str = Path(...),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Get circuit breaker status."""
        if provider_id not in registry.circuit_breakers:
            raise HTTPException(status_code=404, detail="Provider circuit breaker not found")
        
        circuit_breaker = registry.circuit_breakers[provider_id]
        return circuit_breaker.get_status()
    
    @app.post("/api/providers/{provider_id}/enable")
    async def enable_provider(
        provider_id: str = Path(...),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Enable a provider."""
        try:
            await registry.enable_provider(provider_id)
            return {
                "success": True,
                "message": f"Provider {provider_id} enabled"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to enable provider: {str(e)}")
    
    @app.post("/api/providers/{provider_id}/disable")
    async def disable_provider(
        provider_id: str = Path(...),
        reason: str = Query("Manual disable"),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Disable a provider."""
        try:
            await registry.disable_provider(provider_id, reason)
            return {
                "success": True,
                "message": f"Provider {provider_id} disabled",
                "reason": reason
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to disable provider: {str(e)}")
    
    @app.post("/api/providers/{provider_id}/maintenance")
    async def set_maintenance_mode(
        provider_id: str = Path(...),
        maintenance: bool = Query(...),
        reason: str = Query(""),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Set provider maintenance mode."""
        try:
            await registry.set_maintenance_mode(provider_id, maintenance, reason)
            return {
                "success": True,
                "message": f"Provider {provider_id} maintenance mode {'enabled' if maintenance else 'disabled'}",
                "maintenance_mode": maintenance,
                "reason": reason
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to set maintenance mode: {str(e)}")
    
    # Dashboard endpoints
    @app.get("/api/dashboard/providers")
    async def dashboard_providers(
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Get provider dashboard data."""
        overview = registry.get_registry_overview()
        
        # Get detailed status for each provider
        providers = []
        for provider_id in registry.providers:
            status = registry.get_provider_status(provider_id)
            if status:
                # Simplify for dashboard
                dashboard_status = {
                    "provider_id": provider_id,
                    "name": status["name"],
                    "type": status["provider_type"],
                    "region": status["region"],
                    "status": status["status"],
                    "health_score": status["metrics"]["health_score"],
                    "success_rate": status["metrics"]["success_rate"],
                    "response_time": status["metrics"]["average_response_time"],
                    "circuit_breaker_state": status["metrics"]["circuit_breaker_state"],
                    "active_requests": status["metrics"]["active_requests"],
                    "enabled": status["enabled"]
                }
                providers.append(dashboard_status)
        
        return {
            "overview": overview,
            "providers": providers,
            "timestamp": datetime.now().isoformat()
        }
    
    @app.get("/api/dashboard/metrics")
    async def dashboard_metrics(
        hours: int = Query(1, ge=1, le=24),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Get aggregated metrics for dashboard."""
        # This would typically pull from a time-series database
        # For now, return current metrics
        overview = registry.get_registry_overview()
        
        # Simulate time-series data
        time_points = []
        current_time = datetime.now()
        
        for i in range(hours * 4):  # 15-minute intervals
            time_point = current_time - timedelta(minutes=15 * i)
            time_points.append({
                "timestamp": time_point.isoformat(),
                "total_requests": overview["aggregate_metrics"]["total_requests"],
                "success_rate": overview["aggregate_metrics"]["overall_success_rate"],
                "average_response_time": overview["aggregate_metrics"]["average_response_time"],
                "active_providers": overview["status_distribution"].get("active", 0)
            })
        
        return {
            "metrics": list(reversed(time_points)),
            "current_overview": overview
        }
    
    @app.get("/api/dashboard/alerts")
    async def dashboard_alerts(
        limit: int = Query(50, ge=1, le=100),
        severity: Optional[str] = Query(None),
        registry: ProviderRegistry = Depends(get_provider_registry)
    ):
        """Get recent alerts for dashboard."""
        # This would typically pull from an alert/event store
        # For now, return simulated alerts based on current provider states
        alerts = []
        
        for provider_id, metrics in registry.provider_metrics.items():
            if metrics.health_score < 50:
                alerts.append({
                    "id": f"health_{provider_id}_{int(datetime.now().timestamp())}",
                    "provider_id": provider_id,
                    "severity": "critical" if metrics.health_score < 20 else "warning",
                    "type": "health_score",
                    "message": f"Low health score for {provider_id}: {metrics.health_score:.1f}",
                    "timestamp": datetime.now().isoformat(),
                    "status": "active"
                })
            
            if metrics.circuit_breaker_state == "open":
                alerts.append({
                    "id": f"circuit_{provider_id}_{int(datetime.now().timestamp())}",
                    "provider_id": provider_id,
                    "severity": "critical",
                    "type": "circuit_breaker",
                    "message": f"Circuit breaker open for {provider_id}",
                    "timestamp": datetime.now().isoformat(),
                    "status": "active"
                })
        
        # Filter by severity if specified
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        
        return {
            "alerts": alerts[:limit],
            "total_count": len(alerts)
        }


def create_provider_app() -> FastAPI:
    """Create FastAPI application with provider integration."""
    app = FastAPI(
        title="AI Teddy Bear Provider Management API",
        version="1.0.0",
        lifespan=provider_lifespan
    )
    
    # Add provider routes
    add_provider_routes(app)
    
    return app


# Create the main application
provider_app = create_provider_app()


class ProviderMiddleware:
    """Middleware for automatic provider selection and routing."""
    
    def __init__(self, app: FastAPI, registry: ProviderRegistry):
        self.app = app
        self.registry = registry
        self.logger = FallbackLogger("provider_middleware")
    
    async def __call__(self, scope, receive, send):
        """ASGI middleware implementation."""
        if scope["type"] == "http":
            # Add provider selection logic here
            
            # Extract provider requirements from headers or path
            provider_type = None
            region = None
            
            # Check for provider hints in headers
            headers = dict(scope.get("headers", []))
            if b"x-provider-type" in headers:
                provider_type = headers[b"x-provider-type"].decode()
            if b"x-region" in headers:
                region = headers[b"x-region"].decode()
            
            # Select appropriate provider
            if provider_type:
                try:
                    ptype = ProviderType(provider_type)
                    selected_provider = await self.registry.select_provider(
                        provider_type=ptype,
                        region=region,
                        strategy=LoadBalancingStrategy.HEALTH_WEIGHTED
                    )
                    
                    if selected_provider:
                        # Add selected provider to request context
                        scope["selected_provider"] = selected_provider
                        self.logger.info(f"Selected provider {selected_provider} for request")
                    
                except Exception as e:
                    self.logger.warning(f"Provider selection failed: {str(e)}")
        
        # Call the next middleware/app
        await self.app(scope, receive, send)


def setup_provider_integration(app: FastAPI, registry: Optional[ProviderRegistry] = None) -> ProviderRegistry:
    """Setup provider integration with an existing FastAPI app."""
    if registry is None:
        registry = provider_registry
    
    # Add provider routes
    add_provider_routes(app)
    
    # Add middleware
    app.add_middleware(ProviderMiddleware, registry=registry)
    
    return registry