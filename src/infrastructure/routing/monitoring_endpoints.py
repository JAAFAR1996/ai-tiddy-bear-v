"""
🧸 AI TEDDY BEAR - ROUTE MONITORING ENDPOINTS
API endpoints for route monitoring and management
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from src.infrastructure.security.auth import get_current_user
from .route_monitor import RouteMonitor

logger = logging.getLogger(__name__)

# Create router for monitoring endpoints
monitoring_router = APIRouter(prefix="/api/v1/admin/routes", tags=["Route Monitoring"])


@monitoring_router.get("/status")
async def get_route_status(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Get current route status and health summary.
    Requires admin authentication.
    """
    # Check admin permissions
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Admin access required for route monitoring"
        )
    
    try:
        # Get route manager from app state
        if hasattr(request.app.state, "route_manager"):
            route_manager = request.app.state.route_manager
            summary = route_manager.get_registration_summary()
        else:
            # Fallback to direct monitoring
            monitor = RouteMonitor(request.app)
            summary = monitor.get_route_summary()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": summary,
                "message": "Route status retrieved successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get route status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve route status: {str(e)}"
        )


@monitoring_router.get("/scan")
async def scan_routes(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Perform comprehensive route scan and conflict detection.
    Requires admin authentication.
    """
    # Check admin permissions
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Admin access required for route scanning"
        )
    
    try:
        monitor = RouteMonitor(request.app)
        scan_results = monitor.scan_routes()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": scan_results,
                "message": f"Route scan completed. Found {scan_results['conflicts_detected']} conflicts."
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to scan routes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Route scan failed: {str(e)}"
        )


@monitoring_router.get("/validate")
async def validate_routes(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Validate route organization against best practices.
    Requires admin authentication.
    """
    # Check admin permissions
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Admin access required for route validation"
        )
    
    try:
        monitor = RouteMonitor(request.app)
        validation_results = monitor.validate_route_organization()
        
        # Determine HTTP status based on validation results
        status_code = 200
        if validation_results["overall_status"] == "CRITICAL":
            status_code = 500
        elif validation_results["overall_status"] in ["WARNING", "MINOR_ISSUES"]:
            status_code = 200  # Still successful, but with warnings
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "success" if status_code == 200 else "warning",
                "data": validation_results,
                "message": f"Route validation completed with status: {validation_results['overall_status']}"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to validate routes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Route validation failed: {str(e)}"
        )


@monitoring_router.get("/report")
async def generate_route_report(
    request: Request,
    format: str = "json",
    current_user: dict = Depends(get_current_user)
):
    """
    Generate comprehensive route report.
    Supports 'json' and 'markdown' formats.
    Requires admin authentication.
    """
    # Check admin permissions
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Admin access required for route reporting"
        )
    
    if format not in ["json", "markdown"]:
        raise HTTPException(
            status_code=400,
            detail="Format must be 'json' or 'markdown'"
        )
    
    try:
        monitor = RouteMonitor(request.app)
        
        if format == "markdown":
            report = monitor.generate_route_report()
            return PlainTextResponse(
                content=report,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": "attachment; filename=route_report.md"
                }
            )
        else:  # json format
            scan_results = monitor.scan_routes()
            validation_results = monitor.validate_route_organization()
            
            report_data = {
                "scan_results": scan_results,
                "validation_results": validation_results,
                "summary": {
                    "total_routes": scan_results["total_routes"],
                    "conflicts": scan_results["conflicts_detected"],
                    "overall_status": validation_results["overall_status"],
                    "recommendations_count": len(validation_results.get("recommendations", []))
                }
            }
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "data": report_data,
                    "message": "Route report generated successfully"
                }
            )
        
    except Exception as e:
        logger.error(f"Failed to generate route report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Route report generation failed: {str(e)}"
        )


@monitoring_router.get("/conflicts")
async def get_route_conflicts(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information about route conflicts.
    Requires admin authentication.
    """
    # Check admin permissions
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Admin access required for conflict monitoring"
        )
    
    try:
        monitor = RouteMonitor(request.app)
        scan_results = monitor.scan_routes()
        
        conflicts = scan_results.get("conflicts", [])
        
        # Categorize conflicts by severity
        critical_conflicts = [c for c in conflicts if c.get("severity") == "HIGH"]
        medium_conflicts = [c for c in conflicts if c.get("severity") == "MEDIUM"]
        low_conflicts = [c for c in conflicts if c.get("severity") == "LOW"]
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": {
                    "total_conflicts": len(conflicts),
                    "critical_conflicts": critical_conflicts,
                    "medium_conflicts": medium_conflicts,
                    "low_conflicts": low_conflicts,
                    "summary": {
                        "critical_count": len(critical_conflicts),
                        "medium_count": len(medium_conflicts),
                        "low_count": len(low_conflicts)
                    }
                },
                "message": f"Found {len(conflicts)} route conflicts"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get route conflicts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve route conflicts: {str(e)}"
        )


@monitoring_router.get("/health")
async def route_monitoring_health(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Health check for route monitoring system.
    Requires admin authentication.
    """
    # Check admin permissions
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Admin access required for monitoring health check"
        )
    
    try:
        monitor = RouteMonitor(request.app)
        
        # Quick health check
        summary = monitor.get_route_summary()
        
        # Determine health status
        is_healthy = summary.get("status") == "HEALTHY"
        conflicts_count = summary.get("conflicts", 0)
        
        health_status = {
            "monitoring_system": "operational",
            "route_health": summary.get("status", "UNKNOWN"),
            "total_routes": summary.get("total_routes", 0),
            "conflicts_detected": conflicts_count,
            "last_scan": summary.get("last_scan"),
            "overall_health": "healthy" if is_healthy else "degraded"
        }
        
        status_code = 200 if is_healthy else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if is_healthy else "degraded",
                "data": health_status,
                "message": f"Route monitoring system is {'healthy' if is_healthy else 'degraded'}"
            }
        )
        
    except Exception as e:
        logger.error(f"Route monitoring health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "message": "Route monitoring system is unhealthy"
            }
        )


# Public endpoint for basic route information (no auth required)
@monitoring_router.get("/info", dependencies=[])
async def get_basic_route_info(request: Request):
    """
    Get basic route information without sensitive details.
    No authentication required.
    """
    try:
        monitor = RouteMonitor(request.app)
        summary = monitor.get_route_summary()
        
        # Return only non-sensitive information
        basic_info = {
            "total_routes": summary.get("total_routes", 0),
            "system_status": summary.get("status", "UNKNOWN"),
            "last_health_check": summary.get("last_scan"),
            "api_version": "v1"
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": basic_info,
                "message": "Basic route information retrieved"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get basic route info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve route information"
        )
