"""
Monitoring Integration - FastAPI Integration for Prometheus & Grafana
===================================================================
Complete monitoring integration for AI Teddy Bear system:
- FastAPI middleware for automatic metrics collection
- Prometheus metrics endpoint
- Grafana dashboard API endpoints
- Health check endpoints with detailed metrics
- Custom business metrics collection
- Alert manager integration
- Monitoring configuration management
"""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from prometheus_client import start_http_server, push_to_gateway, CollectorRegistry
import psutil

from .prometheus_metrics import PrometheusMetrics, PrometheusMiddleware, prometheus_metrics, metrics_decorator, MetricType
from .grafana_dashboards import GrafanaDashboardGenerator, DashboardType, grafana_dashboard_generator
from ..resilience.fallback_logger import FallbackLogger
from ..messaging.event_bus_integration import EventPublisher


class MonitoringIntegration:
    """
    Complete monitoring integration for AI Teddy Bear system.
    
    Features:
    - Automatic Prometheus metrics collection
    - Grafana dashboard management
    - Health checks with detailed metrics
    - Custom business metrics
    - System resource monitoring
    - Alert integration
    """
    
    def __init__(self, metrics: Optional[PrometheusMetrics] = None):
        self.metrics = metrics or prometheus_metrics
        self.dashboard_generator = grafana_dashboard_generator
        self.logger = FallbackLogger("monitoring_integration")
        
        # Monitoring configuration
        self.prometheus_port = int(os.getenv("PROMETHEUS_PORT", "8000"))
        self.pushgateway_url = os.getenv("PUSHGATEWAY_URL", "")
        self.grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
        self.grafana_api_key = os.getenv("GRAFANA_API_KEY", "")
        
        # Monitoring tasks
        self._system_metrics_task: Optional[asyncio.Task] = None
        self._business_metrics_task: Optional[asyncio.Task] = None
        self._alert_check_task: Optional[asyncio.Task] = None
        
        # System metrics collection
        self.system_metrics_interval = 30  # seconds
        self.business_metrics_interval = 60  # seconds
        self.alert_check_interval = 30  # seconds
        
        # Health thresholds
        self.health_thresholds = {
            "cpu_warning": 80.0,
            "cpu_critical": 90.0,
            "memory_warning": 80.0,
            "memory_critical": 90.0,
            "disk_warning": 85.0,
            "disk_critical": 95.0,
            "response_time_warning": 1.0,
            "response_time_critical": 5.0
        }
        
        self.logger.info("Monitoring integration initialized")
    
    async def start(self):
        """Start monitoring services."""
        try:
            # Start Prometheus HTTP server
            if self.prometheus_port:
                start_http_server(self.prometheus_port, registry=self.metrics.registry)
                self.logger.info(f"Prometheus metrics server started on port {self.prometheus_port}")
            
            # Start background monitoring tasks
            self._system_metrics_task = asyncio.create_task(self._collect_system_metrics())
            self._business_metrics_task = asyncio.create_task(self._collect_business_metrics())
            self._alert_check_task = asyncio.create_task(self._check_alerts())
            
            # Initialize application info
            self.metrics.application_info.info({
                "version": os.getenv("APP_VERSION", "1.0.0"),
                "environment": os.getenv("ENVIRONMENT", "development"),
                "build_date": os.getenv("BUILD_DATE", datetime.now().isoformat()),
                "git_commit": os.getenv("GIT_COMMIT", "unknown")
            })
            
            # Set initial uptime
            self.metrics.application_uptime_seconds.set_to_current_time()
            
            self.logger.info("Monitoring services started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring services: {str(e)}")
            raise
    
    async def stop(self):
        """Stop monitoring services."""
        try:
            # Cancel background tasks
            tasks = [self._system_metrics_task, self._business_metrics_task, self._alert_check_task]
            for task in tasks:
                if task:
                    task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)
            
            self.logger.info("Monitoring services stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping monitoring services: {str(e)}")
    
    async def _collect_system_metrics(self):
        """Collect system resource metrics."""
        while True:
            try:
                await asyncio.sleep(self.system_metrics_interval)
                
                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                self.metrics.cpu_usage_percent.labels(
                    instance_id=os.getenv("INSTANCE_ID", "local"),
                    cpu_type="total"
                ).set(cpu_percent)
                
                # Memory metrics
                memory = psutil.virtual_memory()
                self.metrics.memory_usage_bytes.labels(
                    instance_id=os.getenv("INSTANCE_ID", "local"),
                    memory_type="used"
                ).set(memory.used)
                
                self.metrics.memory_usage_bytes.labels(
                    instance_id=os.getenv("INSTANCE_ID", "local"),
                    memory_type="available"
                ).set(memory.available)
                
                # Disk metrics
                disk = psutil.disk_usage('/')
                disk_usage_percent = (disk.used / disk.total) * 100
                
                self.metrics.disk_io_operations_total.labels(
                    instance_id=os.getenv("INSTANCE_ID", "local"),
                    operation_type="read",
                    device="root"
                ).inc(0)  # Would increment with actual I/O stats
                
                # Network metrics
                network = psutil.net_io_counters()
                self.metrics.network_io_bytes_total.labels(
                    instance_id=os.getenv("INSTANCE_ID", "local"),
                    direction="sent",
                    interface="total"
                ).inc(network.bytes_sent - getattr(self, '_last_bytes_sent', 0))
                
                self.metrics.network_io_bytes_total.labels(
                    instance_id=os.getenv("INSTANCE_ID", "local"),
                    direction="received",
                    interface="total"
                ).inc(network.bytes_recv - getattr(self, '_last_bytes_recv', 0))
                
                self._last_bytes_sent = network.bytes_sent
                self._last_bytes_recv = network.bytes_recv
                
                # Update uptime
                self.metrics.application_uptime_seconds.set_to_current_time()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error collecting system metrics: {str(e)}")
    
    async def _collect_business_metrics(self):
        """Collect business-specific metrics."""
        while True:
            try:
                await asyncio.sleep(self.business_metrics_interval)
                
                # This would typically query your database or application state
                # For now, we'll simulate some business metrics
                
                # Update health check status for services
                services = ["ai_service", "storage_service", "auth_service", "cache_service"]
                for service in services:
                    # This would be actual health check logic
                    health_status = "healthy"  # or "warning", "critical", "unknown"
                    self.metrics.health_check_status.labels(service_name=service).state(health_status)
                
                # Publish business metrics event
                await EventPublisher.publish_system_event(
                    event_type="monitoring.business_metrics.collected",
                    payload={
                        "timestamp": datetime.now().isoformat(),
                        "metrics_collected": True
                    }
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error collecting business metrics: {str(e)}")
    
    async def _check_alerts(self):
        """Check for alert conditions."""
        while True:
            try:
                await asyncio.sleep(self.alert_check_interval)
                
                # Check system resource alerts
                await self._check_system_alerts()
                
                # Check application-specific alerts
                await self._check_application_alerts()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error checking alerts: {str(e)}")
    
    async def _check_system_alerts(self):
        """Check system resource alerts."""
        try:
            # CPU alert
            cpu_percent = psutil.cpu_percent()
            if cpu_percent > self.health_thresholds["cpu_critical"]:
                await self._send_alert("cpu_critical", f"CPU usage critical: {cpu_percent:.1f}%")
            elif cpu_percent > self.health_thresholds["cpu_warning"]:
                await self._send_alert("cpu_warning", f"CPU usage high: {cpu_percent:.1f}%")
            
            # Memory alert
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            if memory_percent > self.health_thresholds["memory_critical"]:
                await self._send_alert("memory_critical", f"Memory usage critical: {memory_percent:.1f}%")
            elif memory_percent > self.health_thresholds["memory_warning"]:
                await self._send_alert("memory_warning", f"Memory usage high: {memory_percent:.1f}%")
            
            # Disk alert
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > self.health_thresholds["disk_critical"]:
                await self._send_alert("disk_critical", f"Disk usage critical: {disk_percent:.1f}%")
            elif disk_percent > self.health_thresholds["disk_warning"]:
                await self._send_alert("disk_warning", f"Disk usage high: {disk_percent:.1f}%")
                
        except Exception as e:
            self.logger.error(f"Error checking system alerts: {str(e)}")
    
    async def _check_application_alerts(self):
        """Check application-specific alerts."""
        # This would check your application metrics for alert conditions
        # Examples: high error rates, slow response times, circuit breakers open, etc.
        pass
    
    async def _send_alert(self, alert_type: str, message: str, severity: str = "warning"):
        """Send alert notification."""
        alert_data = {
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "instance_id": os.getenv("INSTANCE_ID", "local"),
            "environment": os.getenv("ENVIRONMENT", "development")
        }
        
        self.logger.warning(f"Alert: {message}", extra=alert_data)
        
        # Publish alert event
        await EventPublisher.publish_system_event(
            event_type="monitoring.alert.triggered",
            payload=alert_data
        )
        
        # Send to external alert manager if configured
        if self.pushgateway_url:
            try:
                # Push alert metric to Pushgateway
                registry = CollectorRegistry()
                from prometheus_client import Gauge
                alert_gauge = Gauge('monitoring_alert', 'Monitoring alert', ['alert_type', 'severity'], registry=registry)
                alert_gauge.labels(alert_type=alert_type, severity=severity).set(1)
                
                push_to_gateway(self.pushgateway_url, job='ai_teddy_bear_alerts', registry=registry)
            except Exception as e:
                self.logger.error(f"Failed to send alert to Pushgateway: {str(e)}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        try:
            # System resources
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Determine overall health
            health_issues = []
            overall_status = "healthy"
            
            if cpu_percent > self.health_thresholds["cpu_critical"]:
                health_issues.append(f"CPU usage critical: {cpu_percent:.1f}%")
                overall_status = "critical"
            elif cpu_percent > self.health_thresholds["cpu_warning"]:
                health_issues.append(f"CPU usage high: {cpu_percent:.1f}%")
                if overall_status == "healthy":
                    overall_status = "warning"
            
            if memory.percent > self.health_thresholds["memory_critical"]:
                health_issues.append(f"Memory usage critical: {memory.percent:.1f}%")
                overall_status = "critical"
            elif memory.percent > self.health_thresholds["memory_warning"]:
                health_issues.append(f"Memory usage high: {memory.percent:.1f}%")
                if overall_status == "healthy":
                    overall_status = "warning"
            
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > self.health_thresholds["disk_critical"]:
                health_issues.append(f"Disk usage critical: {disk_percent:.1f}%")
                overall_status = "critical"
            elif disk_percent > self.health_thresholds["disk_warning"]:
                health_issues.append(f"Disk usage high: {disk_percent:.1f}%")
                if overall_status == "healthy":
                    overall_status = "warning"
            
            return {
                "status": overall_status,
                "timestamp": datetime.now().isoformat(),
                "version": os.getenv("APP_VERSION", "1.0.0"),
                "environment": os.getenv("ENVIRONMENT", "development"),
                "uptime_seconds": time.time() - psutil.boot_time(),
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "memory_total_gb": memory.total / (1024**3),
                    "disk_percent": disk_percent,
                    "disk_used_gb": disk.used / (1024**3),
                    "disk_total_gb": disk.total / (1024**3)
                },
                "issues": health_issues,
                "monitoring": {
                    "prometheus_enabled": True,
                    "prometheus_port": self.prometheus_port,
                    "grafana_url": self.grafana_url,
                    "system_metrics_running": self._system_metrics_task is not None and not self._system_metrics_task.done(),
                    "business_metrics_running": self._business_metrics_task is not None and not self._business_metrics_task.done(),
                    "alert_checking_running": self._alert_check_task is not None and not self._alert_check_task.done()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting health status: {str(e)}")
            return {
                "status": "unknown",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }


# Global monitoring integration instance
monitoring_integration = MonitoringIntegration()


@asynccontextmanager
async def monitoring_lifespan(app: FastAPI):
    """Lifespan context manager for monitoring integration."""
    # Startup
    await monitoring_integration.start()
    
    try:
        yield
    finally:
        # Shutdown
        await monitoring_integration.stop()


def add_monitoring_routes(app: FastAPI):
    """Add monitoring routes to FastAPI application."""
    
    @app.get("/metrics", response_class=PlainTextResponse)
    async def get_metrics():
        """Prometheus metrics endpoint."""
        return monitoring_integration.metrics.get_metrics()
    
    @app.get("/health")
    async def health_check():
        """Comprehensive health check endpoint."""
        return monitoring_integration.get_health_status()
    
    @app.get("/health/live")
    async def liveness_probe():
        """Kubernetes liveness probe."""
        return {"status": "alive", "timestamp": datetime.now().isoformat()}
    
    @app.get("/health/ready")
    async def readiness_probe():
        """Kubernetes readiness probe."""
        health = monitoring_integration.get_health_status()
        if health["status"] in ["healthy", "warning"]:
            return {"status": "ready", "timestamp": datetime.now().isoformat()}
        else:
            raise HTTPException(status_code=503, detail="Service not ready")
    
    @app.get("/monitoring/dashboards")
    async def list_dashboards():
        """List available Grafana dashboards."""
        dashboards = monitoring_integration.dashboard_generator.generate_all_dashboards()
        
        return {
            "dashboards": [
                {
                    "type": dashboard_type.value,
                    "title": dashboard.title,
                    "tags": dashboard.tags,
                    "panels": len(dashboard.panels)
                }
                for dashboard_type, dashboard in dashboards.items()
            ],
            "total_count": len(dashboards)
        }
    
    @app.get("/monitoring/dashboards/{dashboard_type}")
    async def get_dashboard(dashboard_type: str):
        """Get specific Grafana dashboard JSON."""
        try:
            dash_type = DashboardType(dashboard_type)
            
            if dash_type == DashboardType.OVERVIEW:
                dashboard = monitoring_integration.dashboard_generator.generate_overview_dashboard()
            elif dash_type == DashboardType.HTTP_PERFORMANCE:
                dashboard = monitoring_integration.dashboard_generator.generate_http_performance_dashboard()
            elif dash_type == DashboardType.BUSINESS_METRICS:
                dashboard = monitoring_integration.dashboard_generator.generate_business_metrics_dashboard()
            elif dash_type == DashboardType.PROVIDER_MONITORING:
                dashboard = monitoring_integration.dashboard_generator.generate_provider_monitoring_dashboard()
            elif dash_type == DashboardType.SECURITY_COMPLIANCE:
                dashboard = monitoring_integration.dashboard_generator.generate_security_compliance_dashboard()
            else:
                raise HTTPException(status_code=404, detail="Dashboard not found")
            
            return JSONResponse(content=json.loads(dashboard.to_json()))
            
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dashboard type")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating dashboard: {str(e)}")
    
    @app.post("/monitoring/dashboards/export")
    async def export_dashboards(
        background_tasks: BackgroundTasks,
        output_dir: str = Query("./grafana_dashboards")
    ):
        """Export all dashboards to JSON files."""
        background_tasks.add_task(
            monitoring_integration.dashboard_generator.export_all_dashboards,
            output_dir
        )
        
        return {
            "message": "Dashboard export started",
            "output_dir": output_dir,
            "status": "in_progress"
        }
    
    @app.get("/monitoring/metrics/summary")
    async def metrics_summary():
        """Get metrics summary for monitoring overview."""
        try:
            # This would typically query your metrics storage
            # For now, return current system state
            health = monitoring_integration.get_health_status()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "system_health": health["status"],
                "uptime_hours": health.get("uptime_seconds", 0) / 3600,
                "system_resources": health.get("system", {}),
                "monitoring_status": health.get("monitoring", {}),
                "metrics_endpoint": f"/metrics",
                "grafana_url": monitoring_integration.grafana_url,
                "alert_count": len(health.get("issues", []))
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting metrics summary: {str(e)}")
    
    @app.post("/monitoring/alerts/test")
    async def test_alert(
        alert_type: str = Query(...),
        message: str = Query(...),
        severity: str = Query("warning")
    ):
        """Test alert system."""
        await monitoring_integration._send_alert(alert_type, message, severity)
        
        return {
            "message": "Test alert sent",
            "alert_type": alert_type,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }


def create_monitoring_app() -> FastAPI:
    """Create FastAPI application with monitoring integration."""
    app = FastAPI(
        title="AI Teddy Bear Monitoring API",
        version="1.0.0",
        lifespan=monitoring_lifespan
    )
    
    # Add Prometheus middleware
    app.add_middleware(PrometheusMiddleware, metrics=monitoring_integration.metrics)
    
    # Add monitoring routes
    add_monitoring_routes(app)
    
    return app


def setup_monitoring_integration(app: FastAPI, metrics: Optional[PrometheusMetrics] = None) -> MonitoringIntegration:
    """Setup monitoring integration with an existing FastAPI app."""
    global monitoring_integration
    
    if metrics:
        monitoring_integration = MonitoringIntegration(metrics)
    
    # Add Prometheus middleware
    app.add_middleware(PrometheusMiddleware, metrics=monitoring_integration.metrics)
    
    # Add monitoring routes
    add_monitoring_routes(app)
    
    return monitoring_integration


# Create the main monitoring application
monitoring_app = create_monitoring_app()