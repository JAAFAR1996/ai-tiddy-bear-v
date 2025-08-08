"""
System Health Monitor Tests
===========================
Tests for comprehensive system health monitoring and alerting.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"


class ComponentType(Enum):
    """System component types."""
    DATABASE = "database"
    REDIS = "redis"
    API = "api"
    WEBSOCKET = "websocket"
    ESP32 = "esp32"
    AI_SERVICE = "ai_service"
    AUDIO_SERVICE = "audio_service"
    FILE_STORAGE = "file_storage"


@dataclass
class HealthCheck:
    """Health check configuration."""
    name: str
    component_type: ComponentType
    check_function: callable
    interval_seconds: int = 30
    timeout_seconds: int = 5
    failure_threshold: int = 3
    recovery_threshold: int = 2


@dataclass
class HealthMetric:
    """Health metric data point."""
    component: str
    metric_name: str
    value: float
    unit: str
    timestamp: datetime
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    
    def get_status(self) -> HealthStatus:
        """Determine status based on thresholds."""
        if self.threshold_critical and self.value >= self.threshold_critical:
            return HealthStatus.CRITICAL
        elif self.threshold_warning and self.value >= self.threshold_warning:
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY


@dataclass
class HealthReport:
    """System health report."""
    overall_status: HealthStatus
    components: Dict[str, HealthStatus]
    metrics: List[HealthMetric]
    alerts: List[str]
    timestamp: datetime
    uptime_seconds: float


class SystemHealthMonitor:
    """Production system health monitoring service."""
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.component_status: Dict[str, HealthStatus] = {}
        self.failure_counts: Dict[str, int] = {}
        self.recovery_counts: Dict[str, int] = {}
        self.metrics_history: Dict[str, List[HealthMetric]] = {}
        self.alerts: List[str] = []
        self.start_time = time.time()
        self._monitoring_tasks: List[asyncio.Task] = []
        self._running = False
        
        # Alert callbacks
        self.alert_callbacks: List[callable] = []
    
    def register_health_check(self, health_check: HealthCheck):
        """Register a health check."""
        self.health_checks[health_check.name] = health_check
        self.component_status[health_check.name] = HealthStatus.HEALTHY
        self.failure_counts[health_check.name] = 0
        self.recovery_counts[health_check.name] = 0
    
    def add_alert_callback(self, callback: callable):
        """Add alert notification callback."""
        self.alert_callbacks.append(callback)
    
    async def start_monitoring(self):
        """Start health monitoring tasks."""
        self._running = True
        
        for name, health_check in self.health_checks.items():
            task = asyncio.create_task(
                self._monitor_component(name, health_check)
            )
            self._monitoring_tasks.append(task)
    
    async def stop_monitoring(self):
        """Stop all monitoring tasks."""
        self._running = False
        
        for task in self._monitoring_tasks:
            task.cancel()
        
        await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)
        self._monitoring_tasks.clear()
    
    async def _monitor_component(self, name: str, health_check: HealthCheck):
        """Monitor a specific component."""
        while self._running:
            try:
                # Perform health check
                start_time = time.time()
                
                try:
                    result = await asyncio.wait_for(
                        health_check.check_function(),
                        timeout=health_check.timeout_seconds
                    )
                    
                    # Health check passed
                    await self._handle_success(name, health_check, result)
                    
                except asyncio.TimeoutError:
                    await self._handle_failure(name, health_check, "Timeout")
                except Exception as e:
                    await self._handle_failure(name, health_check, str(e))
                
                # Wait for next check
                await asyncio.sleep(health_check.interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Monitor error for {name}: {e}")
                await asyncio.sleep(health_check.interval_seconds)
    
    async def _handle_success(self, name: str, health_check: HealthCheck, result: Dict[str, Any]):
        """Handle successful health check."""
        self.failure_counts[name] = 0
        
        # Check if component is recovering
        if self.component_status[name] != HealthStatus.HEALTHY:
            self.recovery_counts[name] += 1
            
            if self.recovery_counts[name] >= health_check.recovery_threshold:
                old_status = self.component_status[name]
                self.component_status[name] = HealthStatus.HEALTHY
                self.recovery_counts[name] = 0
                
                alert = f"Component {name} recovered from {old_status.value} to healthy"
                await self._send_alert(alert)
        
        # Store metrics if provided
        if "metrics" in result:
            await self._store_metrics(name, result["metrics"])
    
    async def _handle_failure(self, name: str, health_check: HealthCheck, error: str):
        """Handle failed health check."""
        self.failure_counts[name] += 1
        self.recovery_counts[name] = 0
        
        # Determine new status based on failure count
        if self.failure_counts[name] >= health_check.failure_threshold:
            old_status = self.component_status[name]
            
            if self.failure_counts[name] == health_check.failure_threshold:
                self.component_status[name] = HealthStatus.CRITICAL
            elif self.failure_counts[name] >= health_check.failure_threshold * 2:
                self.component_status[name] = HealthStatus.DOWN
            
            # Send alert if status changed
            if self.component_status[name] != old_status:
                alert = f"Component {name} status changed from {old_status.value} to {self.component_status[name].value}: {error}"
                await self._send_alert(alert)
    
    async def _store_metrics(self, component: str, metrics: Dict[str, Any]):
        """Store component metrics."""
        if component not in self.metrics_history:
            self.metrics_history[component] = []
        
        timestamp = datetime.now()
        
        for metric_name, metric_data in metrics.items():
            if isinstance(metric_data, dict):
                value = metric_data.get("value", 0)
                unit = metric_data.get("unit", "")
                warning_threshold = metric_data.get("warning_threshold")
                critical_threshold = metric_data.get("critical_threshold")
            else:
                value = float(metric_data)
                unit = ""
                warning_threshold = None
                critical_threshold = None
            
            metric = HealthMetric(
                component=component,
                metric_name=metric_name,
                value=value,
                unit=unit,
                timestamp=timestamp,
                threshold_warning=warning_threshold,
                threshold_critical=critical_threshold
            )
            
            self.metrics_history[component].append(metric)
            
            # Keep only recent metrics (last 100 per component)
            if len(self.metrics_history[component]) > 100:
                self.metrics_history[component] = self.metrics_history[component][-100:]
            
            # Check metric thresholds
            metric_status = metric.get_status()
            if metric_status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                alert = f"Metric {metric_name} for {component} is {metric_status.value}: {value} {unit}"
                await self._send_alert(alert)
    
    async def _send_alert(self, message: str):
        """Send alert notification."""
        self.alerts.append(message)
        
        # Keep only recent alerts (last 50)
        if len(self.alerts) > 50:
            self.alerts = self.alerts[-50:]
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(message)
            except Exception as e:
                print(f"Alert callback error: {e}")
    
    async def get_health_report(self) -> HealthReport:
        """Generate comprehensive health report."""
        # Determine overall status
        overall_status = HealthStatus.HEALTHY
        
        for status in self.component_status.values():
            if status == HealthStatus.DOWN:
                overall_status = HealthStatus.DOWN
                break
            elif status == HealthStatus.CRITICAL and overall_status != HealthStatus.DOWN:
                overall_status = HealthStatus.CRITICAL
            elif status == HealthStatus.WARNING and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.WARNING
        
        # Collect recent metrics
        recent_metrics = []
        for component_metrics in self.metrics_history.values():
            if component_metrics:
                recent_metrics.extend(component_metrics[-5:])  # Last 5 per component
        
        return HealthReport(
            overall_status=overall_status,
            components=self.component_status.copy(),
            metrics=recent_metrics,
            alerts=self.alerts[-10:],  # Last 10 alerts
            timestamp=datetime.now(),
            uptime_seconds=time.time() - self.start_time
        )
    
    async def perform_manual_check(self, component_name: str) -> Dict[str, Any]:
        """Perform manual health check for specific component."""
        if component_name not in self.health_checks:
            raise ValueError(f"Unknown component: {component_name}")
        
        health_check = self.health_checks[component_name]
        
        try:
            result = await asyncio.wait_for(
                health_check.check_function(),
                timeout=health_check.timeout_seconds
            )
            
            return {
                "component": component_name,
                "status": "healthy",
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "component": component_name,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


@pytest.fixture
def health_monitor():
    """Create health monitor for testing."""
    return SystemHealthMonitor()


@pytest.fixture
def mock_database_check():
    """Mock database health check."""
    async def check():
        return {
            "status": "connected",
            "metrics": {
                "connection_count": {"value": 15, "unit": "connections", "warning_threshold": 80, "critical_threshold": 100},
                "query_time": {"value": 25.5, "unit": "ms", "warning_threshold": 100, "critical_threshold": 500}
            }
        }
    return check


@pytest.fixture
def mock_failing_check():
    """Mock failing health check."""
    async def check():
        raise Exception("Service unavailable")
    return check


@pytest.mark.asyncio
class TestSystemHealthMonitor:
    """Test system health monitoring functionality."""
    
    async def test_health_check_registration(self, health_monitor, mock_database_check):
        """Test registering health checks."""
        health_check = HealthCheck(
            name="database",
            component_type=ComponentType.DATABASE,
            check_function=mock_database_check,
            interval_seconds=10,
            failure_threshold=2
        )
        
        # Register health check
        health_monitor.register_health_check(health_check)
        
        # Verify registration
        assert "database" in health_monitor.health_checks
        assert health_monitor.health_checks["database"] == health_check
        assert health_monitor.component_status["database"] == HealthStatus.HEALTHY
        assert health_monitor.failure_counts["database"] == 0
    
    async def test_successful_health_monitoring(self, health_monitor, mock_database_check):
        """Test successful health check monitoring."""
        health_check = HealthCheck(
            name="database",
            component_type=ComponentType.DATABASE,
            check_function=mock_database_check,
            interval_seconds=0.1  # Fast for testing
        )
        
        health_monitor.register_health_check(health_check)
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for a few checks
        await asyncio.sleep(0.3)
        
        # Stop monitoring
        await health_monitor.stop_monitoring()
        
        # Verify component remains healthy
        assert health_monitor.component_status["database"] == HealthStatus.HEALTHY
        assert health_monitor.failure_counts["database"] == 0
        
        # Verify metrics were stored
        assert "database" in health_monitor.metrics_history
        assert len(health_monitor.metrics_history["database"]) > 0
    
    async def test_health_check_failure_handling(self, health_monitor, mock_failing_check):
        """Test handling of health check failures."""
        health_check = HealthCheck(
            name="failing_service",
            component_type=ComponentType.API,
            check_function=mock_failing_check,
            interval_seconds=0.1,
            failure_threshold=2
        )
        
        health_monitor.register_health_check(health_check)
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for failures to accumulate
        await asyncio.sleep(0.5)
        
        # Stop monitoring
        await health_monitor.stop_monitoring()
        
        # Verify component marked as critical
        assert health_monitor.component_status["failing_service"] == HealthStatus.CRITICAL
        assert health_monitor.failure_counts["failing_service"] >= 2
        
        # Verify alert was generated
        assert len(health_monitor.alerts) > 0
        assert any("failing_service" in alert for alert in health_monitor.alerts)
    
    async def test_component_recovery(self, health_monitor):
        """Test component recovery after failures."""
        failure_count = 0
        
        async def intermittent_check():
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 3:  # Fail first 3 times
                raise Exception("Temporary failure")
            return {"status": "recovered"}
        
        health_check = HealthCheck(
            name="intermittent_service",
            component_type=ComponentType.API,
            check_function=intermittent_check,
            interval_seconds=0.1,
            failure_threshold=2,
            recovery_threshold=2
        )
        
        health_monitor.register_health_check(health_check)
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for failure and recovery
        await asyncio.sleep(1.0)
        
        # Stop monitoring
        await health_monitor.stop_monitoring()
        
        # Verify component recovered
        assert health_monitor.component_status["intermittent_service"] == HealthStatus.HEALTHY
        
        # Verify recovery alert was sent
        recovery_alerts = [alert for alert in health_monitor.alerts if "recovered" in alert]
        assert len(recovery_alerts) > 0
    
    async def test_metric_threshold_alerts(self, health_monitor):
        """Test metric threshold-based alerts."""
        async def high_metric_check():
            return {
                "status": "ok",
                "metrics": {
                    "cpu_usage": {
                        "value": 95.0,
                        "unit": "%",
                        "warning_threshold": 80.0,
                        "critical_threshold": 90.0
                    },
                    "memory_usage": {
                        "value": 75.0,
                        "unit": "%",
                        "warning_threshold": 80.0,
                        "critical_threshold": 90.0
                    }
                }
            }
        
        health_check = HealthCheck(
            name="resource_monitor",
            component_type=ComponentType.API,
            check_function=high_metric_check,
            interval_seconds=0.1
        )
        
        health_monitor.register_health_check(health_check)
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for metric collection
        await asyncio.sleep(0.3)
        
        # Stop monitoring
        await health_monitor.stop_monitoring()
        
        # Verify critical metric alert
        cpu_alerts = [alert for alert in health_monitor.alerts if "cpu_usage" in alert and "critical" in alert]
        assert len(cpu_alerts) > 0
        
        # Verify memory metric is healthy (no alert)
        memory_alerts = [alert for alert in health_monitor.alerts if "memory_usage" in alert]
        assert len(memory_alerts) == 0
    
    async def test_health_report_generation(self, health_monitor, mock_database_check):
        """Test comprehensive health report generation."""
        # Register multiple components
        db_check = HealthCheck("database", ComponentType.DATABASE, mock_database_check)
        
        async def api_check():
            return {
                "status": "ok",
                "metrics": {
                    "response_time": {"value": 150, "unit": "ms"},
                    "requests_per_second": {"value": 45, "unit": "req/s"}
                }
            }
        
        api_health_check = HealthCheck("api", ComponentType.API, api_check)
        
        health_monitor.register_health_check(db_check)
        health_monitor.register_health_check(api_health_check)
        
        # Start monitoring briefly
        await health_monitor.start_monitoring()
        await asyncio.sleep(0.2)
        await health_monitor.stop_monitoring()
        
        # Generate health report
        report = await health_monitor.get_health_report()
        
        # Verify report structure
        assert isinstance(report, HealthReport)
        assert report.overall_status == HealthStatus.HEALTHY
        assert "database" in report.components
        assert "api" in report.components
        assert len(report.metrics) > 0
        assert report.uptime_seconds > 0
        assert isinstance(report.timestamp, datetime)
    
    async def test_manual_health_check(self, health_monitor, mock_database_check):
        """Test manual health check execution."""
        health_check = HealthCheck(
            name="database",
            component_type=ComponentType.DATABASE,
            check_function=mock_database_check
        )
        
        health_monitor.register_health_check(health_check)
        
        # Perform manual check
        result = await health_monitor.perform_manual_check("database")
        
        # Verify result
        assert result["component"] == "database"
        assert result["status"] == "healthy"
        assert "result" in result
        assert "timestamp" in result
    
    async def test_manual_check_unknown_component(self, health_monitor):
        """Test manual check for unknown component."""
        with pytest.raises(ValueError, match="Unknown component"):
            await health_monitor.perform_manual_check("unknown_component")
    
    async def test_alert_callback_system(self, health_monitor, mock_failing_check):
        """Test alert callback notification system."""
        received_alerts = []
        
        async def alert_callback(message: str):
            received_alerts.append(message)
        
        # Add alert callback
        health_monitor.add_alert_callback(alert_callback)
        
        # Register failing component
        health_check = HealthCheck(
            name="failing_component",
            component_type=ComponentType.API,
            check_function=mock_failing_check,
            interval_seconds=0.1,
            failure_threshold=1
        )
        
        health_monitor.register_health_check(health_check)
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for failure
        await asyncio.sleep(0.3)
        
        # Stop monitoring
        await health_monitor.stop_monitoring()
        
        # Verify callback was called
        assert len(received_alerts) > 0
        assert any("failing_component" in alert for alert in received_alerts)
    
    async def test_multiple_component_monitoring(self, health_monitor):
        """Test monitoring multiple components simultaneously."""
        components = []
        
        for i in range(5):
            async def component_check():
                return {
                    "status": "ok",
                    "metrics": {
                        "uptime": {"value": time.time(), "unit": "seconds"}
                    }
                }
            
            health_check = HealthCheck(
                name=f"component_{i}",
                component_type=ComponentType.API,
                check_function=component_check,
                interval_seconds=0.1
            )
            
            health_monitor.register_health_check(health_check)
            components.append(f"component_{i}")
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for checks
        await asyncio.sleep(0.5)
        
        # Stop monitoring
        await health_monitor.stop_monitoring()
        
        # Verify all components monitored
        for component in components:
            assert component in health_monitor.component_status
            assert health_monitor.component_status[component] == HealthStatus.HEALTHY
            assert component in health_monitor.metrics_history
    
    async def test_coppa_compliance_monitoring(self, health_monitor):
        """Test COPPA compliance monitoring for child safety."""
        async def coppa_compliance_check():
            return {
                "status": "compliant",
                "metrics": {
                    "data_retention_days": {
                        "value": 30,
                        "unit": "days",
                        "critical_threshold": 90  # COPPA limit
                    },
                    "parent_consent_rate": {
                        "value": 98.5,
                        "unit": "%",
                        "warning_threshold": 95.0
                    },
                    "content_filter_accuracy": {
                        "value": 99.8,
                        "unit": "%",
                        "warning_threshold": 98.0,
                        "critical_threshold": 95.0
                    }
                }
            }
        
        health_check = HealthCheck(
            name="coppa_compliance",
            component_type=ComponentType.API,
            check_function=coppa_compliance_check,
            interval_seconds=0.1
        )
        
        health_monitor.register_health_check(health_check)
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for checks
        await asyncio.sleep(0.3)
        
        # Stop monitoring
        await health_monitor.stop_monitoring()
        
        # Verify COPPA compliance metrics collected
        assert "coppa_compliance" in health_monitor.metrics_history
        metrics = health_monitor.metrics_history["coppa_compliance"]
        
        metric_names = [m.metric_name for m in metrics]
        assert "data_retention_days" in metric_names
        assert "parent_consent_rate" in metric_names
        assert "content_filter_accuracy" in metric_names
        
        # Verify no compliance alerts (all metrics healthy)
        compliance_alerts = [alert for alert in health_monitor.alerts if "coppa_compliance" in alert]
        assert len(compliance_alerts) == 0
    
    async def test_esp32_device_monitoring(self, health_monitor):
        """Test ESP32 device health monitoring."""
        device_count = 0
        
        async def esp32_health_check():
            nonlocal device_count
            device_count += 1
            
            # Simulate occasional device disconnection
            if device_count % 10 == 0:
                raise Exception("Device disconnected")
            
            return {
                "status": "connected",
                "metrics": {
                    "battery_level": {
                        "value": 75,
                        "unit": "%",
                        "warning_threshold": 20,
                        "critical_threshold": 10
                    },
                    "wifi_signal": {
                        "value": -45,
                        "unit": "dBm",
                        "warning_threshold": -70,
                        "critical_threshold": -80
                    },
                    "temperature": {
                        "value": 42.5,
                        "unit": "°C",
                        "warning_threshold": 60,
                        "critical_threshold": 70
                    }
                }
            }
        
        health_check = HealthCheck(
            name="esp32_teddy_001",
            component_type=ComponentType.ESP32,
            check_function=esp32_health_check,
            interval_seconds=0.1,
            failure_threshold=2
        )
        
        health_monitor.register_health_check(health_check)
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for multiple checks
        await asyncio.sleep(1.2)
        
        # Stop monitoring
        await health_monitor.stop_monitoring()
        
        # Verify ESP32 metrics collected
        assert "esp32_teddy_001" in health_monitor.metrics_history
        esp32_metrics = health_monitor.metrics_history["esp32_teddy_001"]
        
        metric_names = [m.metric_name for m in esp32_metrics]
        assert "battery_level" in metric_names
        assert "wifi_signal" in metric_names
        assert "temperature" in metric_names