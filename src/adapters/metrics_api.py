# -*- coding: utf-8 -*-
"""
🧸 AI TEDDY BEAR - METRICS API
===============================
Production-grade metrics endpoints for monitoring and observability
Features:
- Prometheus-compatible /metrics endpoint for scraping
- ESP32-specific JSON metrics at /api/v1/esp32/metrics
- Performance and health metrics collection
- Child-safe operational monitoring
- COPPA-compliant metrics (no PII exposure)
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Response, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# Prometheus metrics
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST, 
        generate_latest, 
        REGISTRY,
        CollectorRegistry,
        Gauge,
        Counter,
        Histogram,
        Info
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock prometheus_client for development
    class MockRegistry:
        def collect(self):
            return []
    
    REGISTRY = MockRegistry()
    CONTENT_TYPE_LATEST = "text/plain"
    
    def generate_latest(registry):
        return "# Prometheus client not available\n"

from src.application.dependencies import get_config_from_state, ConfigDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["metrics"])

# Security setup for metrics
security = HTTPBasic()

def verify_metrics_access(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
    config = ConfigDep
):
    """
    Verify access to metrics endpoint in production.
    
    Production security options:
    1. HTTP Basic Auth with configurable credentials
    2. API key via X-Metrics-Token header  
    3. Internal network restriction (via X-Forwarded-For)
    """
    # Skip authentication in development/test
    environment = getattr(config, 'ENVIRONMENT', 'development')
    if environment in ('development', 'test'):
        return True
    
    # Production protection
    if environment == 'production':
        # Method 1: HTTP Basic Auth
        metrics_username = getattr(config, 'METRICS_USERNAME', 'metrics')
        metrics_password = getattr(config, 'METRICS_PASSWORD', None)
        
        if metrics_password:
            import secrets
            is_username_correct = secrets.compare_digest(credentials.username, metrics_username)
            is_password_correct = secrets.compare_digest(credentials.password, metrics_password)
            
            if is_username_correct and is_password_correct:
                return True
        
        # Method 2: API Key via header
        metrics_token = getattr(config, 'METRICS_API_TOKEN', None)
        if metrics_token:
            provided_token = request.headers.get('X-Metrics-Token')
            if provided_token:
                import secrets
                if secrets.compare_digest(provided_token, metrics_token):
                    return True
        
        # Method 3: Internal network check (via reverse proxy headers)
        forwarded_for = request.headers.get('X-Forwarded-For', '')
        real_ip = request.headers.get('X-Real-IP', '')
        
        # Allow internal networks (configurable)
        internal_networks = getattr(config, 'METRICS_INTERNAL_NETWORKS', ['10.', '172.16.', '192.168.', '127.0.0.1'])
        
        client_ip = real_ip or forwarded_for.split(',')[0].strip() or str(request.client.host)
        
        for network in internal_networks:
            if client_ip.startswith(network):
                logger.info(f"Metrics access granted for internal IP: {client_ip}")
                return True
        
        # Log unauthorized access attempt
        logger.warning(
            f"Unauthorized metrics access attempt from {client_ip}. "
            f"Headers: X-Forwarded-For={forwarded_for}, X-Real-IP={real_ip}"
        )
        
        raise HTTPException(
            status_code=401,
            detail="Unauthorized access to metrics endpoint",
            headers={"WWW-Authenticate": "Basic realm='Metrics Access'"}
        )
    
    return True

# System metrics collectors (initialized on first use)
_system_metrics = {}

def get_system_metrics():
    """Get or create system metrics collectors."""
    global _system_metrics
    
    if not _system_metrics and PROMETHEUS_AVAILABLE:
        try:
            # ESP32-specific metrics
            _system_metrics.update({
                'esp32_devices_connected': Gauge('esp32_devices_connected_total', 'Number of connected ESP32 devices'),
                'esp32_messages_total': Counter('esp32_messages_total', 'Total ESP32 messages processed', ['device_type', 'status']),
                'esp32_connection_duration': Histogram('esp32_connection_duration_seconds', 'ESP32 connection duration'),
                'esp32_audio_latency': Histogram('esp32_audio_latency_seconds', 'ESP32 audio processing latency'),
                'esp32_battery_level': Gauge('esp32_battery_level_percent', 'ESP32 device battery level', ['device_id']),
                'esp32_wifi_signal': Gauge('esp32_wifi_signal_strength', 'ESP32 WiFi signal strength', ['device_id']),
                
                # API metrics
                'api_requests_total': Counter('api_requests_total', 'Total API requests', ['endpoint', 'method', 'status']),
                'api_request_duration': Histogram('api_request_duration_seconds', 'API request duration'),
                'api_active_connections': Gauge('api_active_connections', 'Active API connections'),
                
                # Database metrics
                'db_connections_active': Gauge('db_connections_active', 'Active database connections'),
                'db_queries_total': Counter('db_queries_total', 'Total database queries', ['operation', 'status']),
                'db_query_duration': Histogram('db_query_duration_seconds', 'Database query duration'),
                
                # Child safety metrics
                'safety_checks_total': Counter('safety_checks_total', 'Total child safety checks', ['type', 'result']),
                'safety_violations_total': Counter('safety_violations_total', 'Safety violations detected', ['severity']),
                
                # Business metrics (COPPA-compliant)
                'active_sessions': Gauge('active_sessions_total', 'Active user sessions'),
                'conversations_total': Counter('conversations_total', 'Total conversations', ['language']),
                'content_generation_duration': Histogram('content_generation_duration_seconds', 'Content generation time'),
            })
            
            # System info
            _system_metrics['system_info'] = Info('ai_teddy_system', 'AI Teddy Bear system information')
            _system_metrics['system_info'].info({
                'version': '1.0.0',
                'environment': 'production',
                'component': 'ai_teddy_bear'
            })
            
            logger.info("✅ System metrics collectors initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize metrics collectors: {e}")
            _system_metrics = {}
    
    return _system_metrics


@router.get("/esp32/metrics", response_class=JSONResponse)
async def esp32_metrics(config = ConfigDep, _access: bool = Depends(verify_metrics_access)):
    """
    ESP32-specific metrics endpoint (JSON format)
    
    Returns filtered metrics for ESP32 devices and related operations.
    Designed for programmatic consumption by monitoring tools.
    
    Returns:
        Dict: JSON object containing ESP32 metrics
    """
    try:
        logger.debug("Generating ESP32 metrics")
        
        metrics_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "esp32_metrics": {},
            "system_health": {},
            "performance": {}
        }
        
        if PROMETHEUS_AVAILABLE:
            # Collect ESP32-specific metrics from Prometheus registry
            for metric in REGISTRY.collect():
                if metric.name.startswith("esp32_"):
                    metric_samples = []
                    for sample in metric.samples:
                        metric_samples.append({
                            "name": sample.name,
                            "labels": dict(sample.labels) if sample.labels else {},
                            "value": sample.value,
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        })
                    
                    metrics_data["esp32_metrics"][metric.name] = {
                        "type": metric.type,
                        "help": getattr(metric, 'documentation', ''),
                        "samples": metric_samples
                    }
        
        # Add system health indicators
        metrics_data["system_health"] = {
            "database_connected": True,  # Will be updated from actual health check
            "redis_connected": True,     # Will be updated from actual health check
            "openai_available": True,    # Will be updated from actual health check
            "esp32_endpoint_healthy": True,
            "last_health_check": datetime.utcnow().isoformat() + "Z"
        }
        
        # Add performance indicators
        metrics_data["performance"] = {
            "avg_response_time_ms": 0.0,  # Will be populated from actual metrics
            "throughput_requests_per_second": 0.0,
            "error_rate_percent": 0.0,
            "uptime_seconds": 0.0
        }
        
        # Try to get actual system metrics if available
        try:
            from src.infrastructure.monitoring import get_metrics_collector
            metrics_collector = get_metrics_collector()
            if hasattr(metrics_collector, 'get_current_metrics'):
                current_metrics = metrics_collector.get_current_metrics()
                metrics_data["performance"].update(current_metrics.get("performance", {}))
                metrics_data["system_health"].update(current_metrics.get("health", {}))
        except Exception as e:
            logger.warning(f"Could not retrieve detailed system metrics: {e}")
        
        logger.debug(f"ESP32 metrics generated: {len(metrics_data['esp32_metrics'])} metrics")
        return metrics_data
        
    except Exception as e:
        logger.error(f"Error generating ESP32 metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Metrics generation failed"
        )


@router.head("/esp32/metrics", include_in_schema=False)
async def esp32_metrics_head(
    request: Request,
    _access: bool = Depends(verify_metrics_access),
):
    """Lightweight HEAD handler ensuring access control for ESP32 metrics."""
    return Response(status_code=200)

@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def prometheus_metrics(
    request: Request,
    _: bool = Depends(verify_metrics_access)
):
    """
    Prometheus-compatible metrics endpoint (text/plain format)
    
    Standard Prometheus scraping endpoint that exposes all system metrics
    in the expected text format for Prometheus server consumption.
    
    Returns:
        PlainTextResponse: Prometheus-formatted metrics
    """
    try:
        logger.debug("Generating Prometheus metrics")
        
        if not PROMETHEUS_AVAILABLE:
            return PlainTextResponse(
                "# Prometheus client not available\n# Install prometheus_client package\n",
                media_type=CONTENT_TYPE_LATEST
            )
        
        # Initialize metrics collectors if not already done
        get_system_metrics()
        
        # Generate Prometheus format
        metrics_output = generate_latest(REGISTRY)
        
        # Add custom header for identification
        custom_header = f"# AI Teddy Bear Metrics - Generated at {datetime.utcnow().isoformat()}Z\n"
        
        if isinstance(metrics_output, bytes):
            full_output = custom_header.encode('utf-8') + metrics_output
        else:
            full_output = custom_header + metrics_output
        
        logger.debug("Prometheus metrics generated successfully")
        
        return Response(
            content=full_output,
            media_type=CONTENT_TYPE_LATEST,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating Prometheus metrics: {e}")
        error_response = f"# Error generating metrics: {str(e)}\n"
        return PlainTextResponse(
            error_response,
            status_code=500,
            media_type=CONTENT_TYPE_LATEST
        )


@router.get("/health/metrics", response_class=JSONResponse)
async def health_metrics(config = ConfigDep):
    """
    Health-focused metrics endpoint
    
    Provides health status and performance indicators for monitoring systems.
    Complements the main health check endpoint with detailed metrics.
    
    Returns:
        Dict: Health and performance metrics
    """
    try:
        logger.debug("Generating health metrics")
        
        health_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "health_status": "healthy",
            "services": {
                "database": {"status": "healthy", "response_time_ms": 0.0},
                "redis": {"status": "healthy", "response_time_ms": 0.0},
                "openai": {"status": "healthy", "response_time_ms": 0.0},
                "esp32_endpoint": {"status": "healthy", "response_time_ms": 0.0}
            },
            "performance": {
                "cpu_usage_percent": 0.0,
                "memory_usage_percent": 0.0,
                "disk_usage_percent": 0.0,
                "network_connections": 0
            },
            "application": {
                "active_sessions": 0,
                "requests_per_minute": 0.0,
                "error_rate_percent": 0.0,
                "average_response_time_ms": 0.0
            }
        }
        
        # Try to get real health data from monitoring services
        try:
            # Database health check
            from src.infrastructure.database.database_manager import get_database_manager
            db_manager = get_database_manager()
            if hasattr(db_manager, 'get_health_status'):
                db_health = await db_manager.get_health_status()
                if db_health.get("status") == "healthy":
                    health_data["services"]["database"]["status"] = "healthy"
                else:
                    health_data["services"]["database"]["status"] = "unhealthy"
                    health_data["health_status"] = "degraded"
        except Exception as e:
            logger.warning(f"Could not check database health: {e}")
            health_data["services"]["database"]["status"] = "unknown"
        
        # Try to get system performance metrics
        try:
            import psutil
            health_data["performance"]["cpu_usage_percent"] = psutil.cpu_percent(interval=0.1)
            health_data["performance"]["memory_usage_percent"] = psutil.virtual_memory().percent
            health_data["performance"]["disk_usage_percent"] = psutil.disk_usage('/').percent
            health_data["performance"]["network_connections"] = len(psutil.net_connections())
        except ImportError:
            logger.debug("psutil not available for system metrics")
        except Exception as e:
            logger.warning(f"Could not get system performance metrics: {e}")
        
        logger.debug("Health metrics generated successfully")
        return health_data
        
    except Exception as e:
        logger.error(f"Error generating health metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Health metrics generation failed"
        )


@router.get("/system/info", response_class=JSONResponse)
async def system_info(config = ConfigDep):
    """
    System information endpoint
    
    Provides system configuration and version information.
    Useful for deployment verification and debugging.
    
    Returns:
        Dict: System information
    """
    try:
        import platform
        import sys
        from datetime import datetime
        
        # Get application version and environment
        app_version = getattr(config, 'VERSION', '1.0.0')
        environment = getattr(config, 'ENVIRONMENT', 'unknown')
        
        system_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "application": {
                "name": "AI Teddy Bear",
                "version": app_version,
                "environment": environment,
                "python_version": sys.version,
                "platform": platform.platform(),
                "architecture": platform.architecture()[0]
            },
            "runtime": {
                "uptime_seconds": 0.0,  # Will be calculated from app start time
                "pid": None,
                "threads": 0,
                "memory_usage_bytes": 0
            },
            "configuration": {
                "debug_mode": getattr(config, 'DEBUG', False),
                "log_level": getattr(config, 'LOG_LEVEL', 'INFO'),
                "host": getattr(config, 'HOST', 'localhost'),
                "port": getattr(config, 'PORT', 8000),
                "database_type": "postgresql",
                "redis_enabled": hasattr(config, 'REDIS_URL'),
                "openai_enabled": hasattr(config, 'OPENAI_API_KEY'),
                "prometheus_enabled": PROMETHEUS_AVAILABLE
            }
        }
        
        # Try to get runtime information
        try:
            import os
            import psutil
            process = psutil.Process(os.getpid())
            system_data["runtime"].update({
                "pid": os.getpid(),
                "threads": process.num_threads(),
                "memory_usage_bytes": process.memory_info().rss
            })
        except ImportError:
            logger.debug("psutil not available for runtime metrics")
        except Exception as e:
            logger.warning(f"Could not get runtime information: {e}")
        
        logger.debug("System info generated successfully")
        return system_data
        
    except Exception as e:
        logger.error(f"Error generating system info: {e}")
        raise HTTPException(
            status_code=500,
            detail="System info generation failed"
        )


# Utility functions for metrics management

def increment_esp32_metric(metric_name: str, labels: Dict[str, str] = None, value: float = 1.0):
    """Increment ESP32-related counter metric."""
    try:
        metrics = get_system_metrics()
        if metric_name in metrics and hasattr(metrics[metric_name], 'labels'):
            if labels:
                metrics[metric_name].labels(**labels).inc(value)
            else:
                metrics[metric_name].inc(value)
    except Exception as e:
        logger.debug(f"Could not increment metric {metric_name}: {e}")


def set_esp32_gauge(metric_name: str, value: float, labels: Dict[str, str] = None):
    """Set ESP32-related gauge metric value."""
    try:
        metrics = get_system_metrics()
        if metric_name in metrics and hasattr(metrics[metric_name], 'labels'):
            if labels:
                metrics[metric_name].labels(**labels).set(value)
            else:
                metrics[metric_name].set(value)
    except Exception as e:
        logger.debug(f"Could not set gauge {metric_name}: {e}")


def record_esp32_duration(metric_name: str, duration: float, labels: Dict[str, str] = None):
    """Record ESP32-related duration metric."""
    try:
        metrics = get_system_metrics()
        if metric_name in metrics and hasattr(metrics[metric_name], 'labels'):
            if labels:
                metrics[metric_name].labels(**labels).observe(duration)
            else:
                metrics[metric_name].observe(duration)
    except Exception as e:
        logger.debug(f"Could not record duration {metric_name}: {e}")


# Initialize metrics collectors on module import
if PROMETHEUS_AVAILABLE:
    try:
        get_system_metrics()
        logger.info("✅ Metrics API initialized with Prometheus support")
    except Exception as e:
        logger.warning(f"Metrics API initialized with limited functionality: {e}")
else:
    logger.warning("⚠️ Metrics API initialized without Prometheus (install prometheus_client for full functionality)")
