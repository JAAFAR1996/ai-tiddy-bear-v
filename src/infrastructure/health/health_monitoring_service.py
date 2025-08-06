"""
🎯 HEALTH MONITORING & GRACEFUL SHUTDOWN SERVICE
==============================================
Production-grade health monitoring and graceful shutdown system:
- Comprehensive health checks for all services
- Real-time system monitoring and alerting
- Graceful shutdown with cleanup procedures
- Service dependency health validation
- Child session safety during shutdown
- Database connection health monitoring
- Redis health and performance checks
- Automatic recovery and self-healing

ZERO DOWNTIME - CHILD SAFETY FIRST DURING OPERATIONS
"""

import asyncio
import signal
import time
import logging
import os
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Set
from enum import Enum
from dataclasses import dataclass, asdict
import uuid

# Health check imports
import redis.asyncio as redis
import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

# Internal imports
from src.infrastructure.logging.structlog_logger import StructlogLogger

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class ServiceType(str, Enum):
    """Types of services to monitor."""
    USER_SERVICE = "user_service"
    CHILD_SAFETY_SERVICE = "child_safety_service"
    AI_SERVICE = "ai_service"
    AUDIO_SERVICE = "audio_service"
    DATABASE = "database"
    REDIS = "redis"
    SESSION_STORE = "session_store"
    RATE_LIMITER = "rate_limiter"
    ENCRYPTION_SERVICE = "encryption_service"


class ShutdownPhase(str, Enum):
    """Phases of graceful shutdown."""
    SIGNAL_RECEIVED = "signal_received"
    STOP_ACCEPTING_REQUESTS = "stop_accepting_requests"
    FINISH_ACTIVE_SESSIONS = "finish_active_sessions"
    CLEANUP_CHILD_SESSIONS = "cleanup_child_sessions"
    FLUSH_AUDIT_LOGS = "flush_audit_logs"
    CLOSE_CONNECTIONS = "close_connections"
    FINAL_CLEANUP = "final_cleanup"
    SHUTDOWN_COMPLETE = "shutdown_complete"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    service_name: str
    service_type: ServiceType
    status: HealthStatus
    timestamp: datetime
    response_time_ms: float
    details: Dict[str, Any]
    error_message: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class SystemMetrics:
    """System-level metrics."""
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_connections: int
    load_average: List[float]
    uptime_seconds: float
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class HealthMonitoringService:
    """
    Production-grade health monitoring and graceful shutdown service.
    
    Features:
    - Comprehensive health checks
    - Real-time system monitoring
    - Graceful shutdown procedures
    - Child session protection
    - Automatic recovery attempts
    - Dependency health validation
    """
    
    def __init__(
        self,
        check_interval_seconds: int = 30,
        unhealthy_threshold: int = 3,
        enable_auto_recovery: bool = True,
        shutdown_timeout_seconds: int = 300
    ):
        """
        Initialize health monitoring service.
        
        Args:
            check_interval_seconds: Interval between health checks
            unhealthy_threshold: Number of failures before marking unhealthy
            enable_auto_recovery: Enable automatic recovery attempts
            shutdown_timeout_seconds: Maximum time for graceful shutdown
        """
        self.logger = StructlogLogger("health_monitoring", component="health")
        
        # Configuration
        self.check_interval = check_interval_seconds
        self.unhealthy_threshold = unhealthy_threshold
        self.enable_auto_recovery = enable_auto_recovery
        self.shutdown_timeout = shutdown_timeout_seconds
        
        # Health check registry
        self.health_checks: Dict[str, Callable] = {}
        self.service_instances: Dict[ServiceType, Any] = {}
        
        # Health status tracking
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.failure_counts: Dict[str, int] = {}
        self.last_health_check: Optional[datetime] = None
        
        # System monitoring
        self.system_metrics_history: List[SystemMetrics] = []
        self.max_metrics_history = 1440  # 24 hours at 1-minute intervals
        
        # Shutdown management
        self.shutdown_initiated = False
        self.shutdown_phase = None
        self.active_child_sessions: Set[str] = set()
        self.cleanup_callbacks: List[Callable] = []
        
        # Monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Register signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        self.logger.info("Health monitoring service initialized")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            asyncio.create_task(self.initiate_graceful_shutdown())
        
        # Register handlers for common shutdown signals
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # On Unix systems, also handle SIGUSR1 for health check trigger
        if hasattr(signal, 'SIGUSR1'):
            def health_check_signal(signum, frame):
                asyncio.create_task(self.run_all_health_checks())
            signal.signal(signal.SIGUSR1, health_check_signal)
    
    # ========================================================================
    # SERVICE REGISTRATION
    # ========================================================================
    
    def register_service(self, service_type: ServiceType, service_instance: Any):
        """Register a service instance for health monitoring."""
        self.service_instances[service_type] = service_instance
        self.logger.info(f"Registered service: {service_type.value}")
    
    def register_health_check(self, service_name: str, health_check_func: Callable):
        """Register a custom health check function."""
        self.health_checks[service_name] = health_check_func
        self.health_history[service_name] = []
        self.failure_counts[service_name] = 0
        self.logger.info(f"Registered health check: {service_name}")
    
    def register_cleanup_callback(self, callback: Callable):
        """Register a cleanup callback for graceful shutdown."""
        self.cleanup_callbacks.append(callback)
        self.logger.info("Registered cleanup callback")
    
    # ========================================================================
    # HEALTH CHECK METHODS
    # ========================================================================
    
    async def run_all_health_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        self.logger.info("Running comprehensive health checks")
        
        results = {}
        
        # Run built-in health checks
        builtin_checks = [
            ("system_resources", self._check_system_resources),
            ("database_health", self._check_database_health), 
            ("redis_health", self._check_redis_health),
            ("user_service_health", self._check_user_service_health),
            ("child_safety_health", self._check_child_safety_health),
            ("session_health", self._check_session_health),
        ]
        
        for check_name, check_func in builtin_checks:
            try:
                result = await check_func()
                results[check_name] = result
                self._update_health_history(check_name, result)
            except Exception as e:
                error_result = HealthCheckResult(
                    service_name=check_name,
                    service_type=ServiceType.USER_SERVICE,  # Default
                    status=HealthStatus.CRITICAL,
                    timestamp=datetime.utcnow(),
                    response_time_ms=0,
                    details={},
                    error_message=str(e)
                )
                results[check_name] = error_result
                self._update_health_history(check_name, error_result)
        
        # Run custom health checks
        for check_name, check_func in self.health_checks.items():
            try:
                result = await check_func()
                if isinstance(result, HealthCheckResult):
                    results[check_name] = result
                    self._update_health_history(check_name, result)
            except Exception as e:
                self.logger.error(f"Health check {check_name} failed: {e}")
        
        self.last_health_check = datetime.utcnow()
        self.logger.info(f"Completed health checks: {len(results)} checks")
        
        return results
    
    async def _check_system_resources(self) -> HealthCheckResult:
        """Check system resource utilization."""
        start_time = time.time()
        
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            
            # Determine health status
            status = HealthStatus.HEALTHY
            warnings = []
            
            if cpu_percent > 80:
                status = HealthStatus.DEGRADED
                warnings.append(f"High CPU usage: {cpu_percent:.1f}%")
            
            if memory.percent > 85:
                status = HealthStatus.DEGRADED if status == HealthStatus.HEALTHY else HealthStatus.UNHEALTHY
                warnings.append(f"High memory usage: {memory.percent:.1f}%")
            
            if disk.percent > 90:
                status = HealthStatus.CRITICAL
                warnings.append(f"Low disk space: {disk.percent:.1f}% used")
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="system_resources",
                service_type=ServiceType.USER_SERVICE,
                status=status,
                timestamp=datetime.utcnow(),
                response_time_ms=response_time,
                details={
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_used_gb': memory.used / (1024**3),
                    'memory_total_gb': memory.total / (1024**3),
                    'disk_percent': disk.percent,
                    'disk_free_gb': disk.free / (1024**3),
                    'load_average': load_avg
                },
                warnings=warnings
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="system_resources",
                service_type=ServiceType.USER_SERVICE,
                status=HealthStatus.CRITICAL,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={},
                error_message=str(e)
            )
    
    async def _check_database_health(self) -> HealthCheckResult:
        """Check database connectivity and performance."""
        start_time = time.time()
        
        try:
            # Try to get database instance from service registry
            if ServiceType.DATABASE in self.service_instances:
                db_instance = self.service_instances[ServiceType.DATABASE]
                
                # Test database connectivity with ORM
                if hasattr(db_instance, 'execute'):
                    # Test with simple ORM query instead of raw SQL
                    from sqlalchemy import select, literal
                    test_query = select(literal(1).label('test'))
                    result = await db_instance.execute(test_query)
                    
                    response_time = (time.time() - start_time) * 1000
                    
                    return HealthCheckResult(
                        service_name="database",
                        service_type=ServiceType.DATABASE,
                        status=HealthStatus.HEALTHY,
                        timestamp=datetime.utcnow(),
                        response_time_ms=response_time,
                        details={
                            'connection_status': 'connected',
                            'query_result': 'success',
                            'response_time_ms': response_time
                        }
                    )
            
            # Fallback: No database instance registered
            return HealthCheckResult(
                service_name="database",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.DEGRADED,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={'connection_status': 'not_registered'},
                warnings=["Database instance not registered with health monitor"]
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="database",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={},
                error_message=str(e)
            )
    
    async def _check_redis_health(self) -> HealthCheckResult:
        """Check Redis connectivity and performance."""
        start_time = time.time()
        
        try:
            # Try to get Redis instance
            if ServiceType.REDIS in self.service_instances:
                redis_instance = self.service_instances[ServiceType.REDIS]
                
                # Test Redis connectivity
                pong = await redis_instance.ping()
                
                # Get Redis info
                info = await redis_instance.info()
                
                response_time = (time.time() - start_time) * 1000
                
                # Check Redis health indicators
                status = HealthStatus.HEALTHY
                warnings = []
                
                memory_usage = info.get('used_memory', 0)
                max_memory = info.get('maxmemory', 0)
                
                if max_memory > 0 and (memory_usage / max_memory) > 0.9:
                    status = HealthStatus.DEGRADED
                    warnings.append("High Redis memory usage")
                
                connected_clients = info.get('connected_clients', 0)
                if connected_clients > 1000:  # Threshold for too many connections
                    status = HealthStatus.DEGRADED
                    warnings.append(f"High client connections: {connected_clients}")
                
                return HealthCheckResult(
                    service_name="redis",
                    service_type=ServiceType.REDIS,
                    status=status,
                    timestamp=datetime.utcnow(),
                    response_time_ms=response_time,
                    details={
                        'ping_result': pong,
                        'connected_clients': connected_clients,
                        'used_memory_human': info.get('used_memory_human', 'unknown'),
                        'redis_version': info.get('redis_version', 'unknown'),
                        'uptime_in_seconds': info.get('uptime_in_seconds', 0)
                    },
                    warnings=warnings
                )
            
            # Fallback: Try to create a new Redis connection
            redis_instance = redis.Redis.from_url("redis://localhost:6379")
            await redis_instance.ping()
            await redis_instance.close()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="redis",
                service_type=ServiceType.REDIS,
                status=HealthStatus.HEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=response_time,
                details={'connection_status': 'connected'},
                warnings=["Redis not registered, used fallback connection"]
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="redis",
                service_type=ServiceType.REDIS,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={},
                error_message=str(e)
            )
    
    async def _check_user_service_health(self) -> HealthCheckResult:
        """Check User Service health."""
        start_time = time.time()
        
        try:
            if ServiceType.USER_SERVICE in self.service_instances:
                user_service = self.service_instances[ServiceType.USER_SERVICE]
                
                # Check if service has health check method
                if hasattr(user_service, 'health_check'):
                    health_result = await user_service.health_check()
                    
                    response_time = (time.time() - start_time) * 1000
                    
                    # Determine status based on service response
                    if isinstance(health_result, dict):
                        service_status = health_result.get('status', 'unknown')
                        if service_status == 'healthy':
                            status = HealthStatus.HEALTHY
                        elif service_status == 'degraded':
                            status = HealthStatus.DEGRADED
                        else:
                            status = HealthStatus.UNHEALTHY
                    else:
                        status = HealthStatus.HEALTHY
                    
                    return HealthCheckResult(
                        service_name="user_service",
                        service_type=ServiceType.USER_SERVICE,
                        status=status,
                        timestamp=datetime.utcnow(),
                        response_time_ms=response_time,
                        details=health_result if isinstance(health_result, dict) else {'status': 'ok'}
                    )
                
                # Fallback: Service exists but no health check method
                return HealthCheckResult(
                    service_name="user_service",
                    service_type=ServiceType.USER_SERVICE,
                    status=HealthStatus.DEGRADED,
                    timestamp=datetime.utcnow(),
                    response_time_ms=(time.time() - start_time) * 1000,
                    details={'service_registered': True},
                    warnings=["User service has no health_check method"]
                )
            
            # Service not registered
            return HealthCheckResult(
                service_name="user_service",
                service_type=ServiceType.USER_SERVICE,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={'service_registered': False},
                error_message="User service not registered"
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="user_service",
                service_type=ServiceType.USER_SERVICE,
                status=HealthStatus.CRITICAL,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={},
                error_message=str(e)
            )
    
    async def _check_child_safety_health(self) -> HealthCheckResult:
        """Check Child Safety Service health."""
        start_time = time.time()
        
        try:
            if ServiceType.CHILD_SAFETY_SERVICE in self.service_instances:
                safety_service = self.service_instances[ServiceType.CHILD_SAFETY_SERVICE]
                
                # Test basic safety validation
                test_content = "Hello, this is a test message for children."
                validation_result = await safety_service.validate_content(test_content, child_age=8)
                
                response_time = (time.time() - start_time) * 1000
                
                # Check if validation worked correctly
                if validation_result and 'is_safe' in validation_result:
                    status = HealthStatus.HEALTHY
                    details = {
                        'validation_working': True,
                        'test_result': validation_result.get('is_safe', False),
                        'response_time_ms': response_time
                    }
                else:
                    status = HealthStatus.DEGRADED
                    details = {'validation_working': False}
                
                return HealthCheckResult(
                    service_name="child_safety_service",
                    service_type=ServiceType.CHILD_SAFETY_SERVICE,
                    status=status,
                    timestamp=datetime.utcnow(),
                    response_time_ms=response_time,
                    details=details
                )
            
            # Service not registered
            return HealthCheckResult(
                service_name="child_safety_service",
                service_type=ServiceType.CHILD_SAFETY_SERVICE,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={'service_registered': False},
                error_message="Child safety service not registered"
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="child_safety_service",
                service_type=ServiceType.CHILD_SAFETY_SERVICE,
                status=HealthStatus.CRITICAL,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={},
                error_message=str(e)
            )
    
    async def _check_session_health(self) -> HealthCheckResult:
        """Check session store health."""
        start_time = time.time()
        
        try:
            if ServiceType.SESSION_STORE in self.service_instances:
                session_store = self.service_instances[ServiceType.SESSION_STORE]
                
                # Test session store health
                if hasattr(session_store, 'health_check'):
                    health_result = await session_store.health_check()
                    
                    response_time = (time.time() - start_time) * 1000
                    
                    status = HealthStatus.HEALTHY
                    if isinstance(health_result, dict):
                        if health_result.get('status') != 'healthy':
                            status = HealthStatus.DEGRADED
                    
                    return HealthCheckResult(
                        service_name="session_store",
                        service_type=ServiceType.SESSION_STORE,
                        status=status,
                        timestamp=datetime.utcnow(),
                        response_time_ms=response_time,
                        details=health_result if isinstance(health_result, dict) else {'status': 'ok'}
                    )
            
            # Session store not registered
            return HealthCheckResult(
                service_name="session_store",
                service_type=ServiceType.SESSION_STORE,
                status=HealthStatus.DEGRADED,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={'service_registered': False},
                warnings=["Session store not registered with health monitor"]
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="session_store",
                service_type=ServiceType.SESSION_STORE,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={},
                error_message=str(e)
            )
    
    def _update_health_history(self, service_name: str, result: HealthCheckResult):
        """Update health history for a service."""
        if service_name not in self.health_history:
            self.health_history[service_name] = []
        
        self.health_history[service_name].append(result)
        
        # Keep only recent history (last 100 checks)
        if len(self.health_history[service_name]) > 100:
            self.health_history[service_name] = self.health_history[service_name][-50:]
        
        # Update failure count
        if result.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
            self.failure_counts[service_name] = self.failure_counts.get(service_name, 0) + 1
        else:
            self.failure_counts[service_name] = 0  # Reset on success
    
    # ========================================================================
    # MONITORING AND ALERTING
    # ========================================================================
    
    async def start_monitoring(self):
        """Start continuous health monitoring."""
        if self._monitoring_task and not self._monitoring_task.done():
            return
        
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring."""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while not self.shutdown_initiated:
            try:
                # Run health checks
                health_results = await self.run_all_health_checks()
                
                # Check for critical issues
                await self._check_for_alerts(health_results)
                
                # Collect system metrics
                await self._collect_system_metrics()
                
                # Auto-recovery attempts
                if self.enable_auto_recovery:
                    await self._attempt_auto_recovery(health_results)
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_for_alerts(self, health_results: Dict[str, HealthCheckResult]):
        """Check health results and trigger alerts if needed."""
        critical_services = []
        unhealthy_services = []
        
        for service_name, result in health_results.items():
            if result.status == HealthStatus.CRITICAL:
                critical_services.append(service_name)
            elif result.status == HealthStatus.UNHEALTHY:
                unhealthy_services.append(service_name)
        
        # Alert on critical services
        if critical_services:
            await self._send_critical_alert(critical_services)
        
        # Alert on persistent unhealthy services
        for service_name in unhealthy_services:
            if self.failure_counts.get(service_name, 0) >= self.unhealthy_threshold:
                await self._send_unhealthy_alert(service_name)
    
    async def _send_critical_alert(self, critical_services: List[str]):
        """Send alert for critical service failures."""
        alert_message = f"CRITICAL: Services in critical state: {', '.join(critical_services)}"
        
        self.logger.critical(alert_message, extra={
            'alert_type': 'critical_service_failure',
            'critical_services': critical_services,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # In production, send to alerting system (PagerDuty, Slack, etc.)
    
    async def _send_unhealthy_alert(self, service_name: str):
        """Send alert for persistently unhealthy service."""
        failure_count = self.failure_counts.get(service_name, 0)
        alert_message = f"ALERT: Service {service_name} unhealthy for {failure_count} consecutive checks"
        
        self.logger.error(alert_message, extra={
            'alert_type': 'persistent_service_failure',
            'service_name': service_name,
            'failure_count': failure_count,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def _collect_system_metrics(self):
        """Collect and store system metrics."""
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net_connections = len(psutil.net_connections())
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            
            metrics = SystemMetrics(
                cpu_usage_percent=cpu_percent,
                memory_usage_percent=memory.percent,
                memory_used_gb=memory.used / (1024**3),
                memory_total_gb=memory.total / (1024**3),
                disk_usage_percent=disk.percent,
                disk_free_gb=disk.free / (1024**3),
                network_connections=net_connections,
                load_average=load_avg,
                uptime_seconds=uptime,
                timestamp=datetime.utcnow()
            )
            
            self.system_metrics_history.append(metrics)
            
            # Keep only recent metrics
            if len(self.system_metrics_history) > self.max_metrics_history:
                self.system_metrics_history = self.system_metrics_history[-self.max_metrics_history//2:]
                
        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
    
    async def _attempt_auto_recovery(self, health_results: Dict[str, HealthCheckResult]):
        """Attempt automatic recovery for failed services."""
        for service_name, result in health_results.items():
            if result.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
                failure_count = self.failure_counts.get(service_name, 0)
                
                # Attempt recovery after multiple failures
                if failure_count >= 3 and failure_count % 5 == 0:  # Every 5th failure after 3
                    await self._attempt_service_recovery(service_name, result)
    
    async def _attempt_service_recovery(self, service_name: str, result: HealthCheckResult):
        """Attempt to recover a specific service."""
        self.logger.info(f"Attempting auto-recovery for service: {service_name}")
        
        try:
            # Service-specific recovery logic
            if service_name == "redis" and ServiceType.REDIS in self.service_instances:
                # Try to reconnect Redis
                redis_instance = self.service_instances[ServiceType.REDIS]
                if hasattr(redis_instance, 'close'):
                    await redis_instance.close()
                
                # Create new connection
                new_redis = redis.Redis.from_url("redis://localhost:6379")
                await new_redis.ping()
                self.service_instances[ServiceType.REDIS] = new_redis
                
                self.logger.info(f"Successfully recovered Redis connection")
            
            # Add more recovery logic for other services
            
        except Exception as e:
            self.logger.error(f"Auto-recovery failed for {service_name}: {e}")
    
    # ========================================================================
    # GRACEFUL SHUTDOWN METHODS
    # ========================================================================
    
    async def initiate_graceful_shutdown(self):
        """Initiate graceful shutdown process."""
        if self.shutdown_initiated:
            self.logger.warning("Shutdown already initiated")
            return
        
        self.shutdown_initiated = True
        self.logger.info("Initiating graceful shutdown")
        
        try:
            # Phase 1: Signal received
            await self._shutdown_phase(ShutdownPhase.SIGNAL_RECEIVED)
            
            # Phase 2: Stop accepting new requests
            await self._shutdown_phase(ShutdownPhase.STOP_ACCEPTING_REQUESTS)
            
            # Phase 3: Finish active sessions (with timeout)
            await self._shutdown_phase(ShutdownPhase.FINISH_ACTIVE_SESSIONS)
            
            # Phase 4: Special handling for child sessions
            await self._shutdown_phase(ShutdownPhase.CLEANUP_CHILD_SESSIONS)
            
            # Phase 5: Flush audit logs and important data
            await self._shutdown_phase(ShutdownPhase.FLUSH_AUDIT_LOGS)
            
            # Phase 6: Close connections
            await self._shutdown_phase(ShutdownPhase.CLOSE_CONNECTIONS)
            
            # Phase 7: Final cleanup
            await self._shutdown_phase(ShutdownPhase.FINAL_CLEANUP)
            
            # Phase 8: Shutdown complete
            await self._shutdown_phase(ShutdownPhase.SHUTDOWN_COMPLETE)
            
            self.logger.info("Graceful shutdown completed successfully")
            
        except asyncio.TimeoutError:
            self.logger.error(f"Graceful shutdown timed out after {self.shutdown_timeout}s")
        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")
        finally:
            # Force exit if still running
            os._exit(0)
    
    async def _shutdown_phase(self, phase: ShutdownPhase):
        """Execute a specific shutdown phase."""
        self.shutdown_phase = phase
        self.logger.info(f"Shutdown phase: {phase.value}")
        
        try:
            if phase == ShutdownPhase.SIGNAL_RECEIVED:
                # Log shutdown initiation
                await self._log_shutdown_event("Graceful shutdown initiated")
            
            elif phase == ShutdownPhase.STOP_ACCEPTING_REQUESTS:
                # Stop accepting new requests (implementation depends on web framework)
                # This would typically involve stopping the HTTP server from accepting new connections
                await asyncio.sleep(1)  # Allow current requests to be accepted
            
            elif phase == ShutdownPhase.FINISH_ACTIVE_SESSIONS:
                # Wait for active sessions to complete (with timeout)
                await self._wait_for_active_sessions(timeout_seconds=60)
            
            elif phase == ShutdownPhase.CLEANUP_CHILD_SESSIONS:
                # Special handling for child sessions - ensure they're properly saved
                await self._cleanup_child_sessions()
            
            elif phase == ShutdownPhase.FLUSH_AUDIT_LOGS:
                # Flush any pending audit logs
                await self._flush_pending_data()
            
            elif phase == ShutdownPhase.CLOSE_CONNECTIONS:
                # Close database and Redis connections
                await self._close_service_connections()
            
            elif phase == ShutdownPhase.FINAL_CLEANUP:
                # Run cleanup callbacks
                await self._run_cleanup_callbacks()
            
            elif phase == ShutdownPhase.SHUTDOWN_COMPLETE:
                # Log successful shutdown
                await self._log_shutdown_event("Graceful shutdown completed")
                
        except Exception as e:
            self.logger.error(f"Error in shutdown phase {phase.value}: {e}")
    
    async def _wait_for_active_sessions(self, timeout_seconds: int):
        """Wait for active sessions to complete."""
        self.logger.info(f"Waiting for active sessions to complete (timeout: {timeout_seconds}s)")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            # Check if any services have active sessions
            active_sessions = 0
            
            if ServiceType.USER_SERVICE in self.service_instances:
                user_service = self.service_instances[ServiceType.USER_SERVICE]
                if hasattr(user_service, '_sessions'):
                    active_sessions += len(user_service._sessions)
            
            if active_sessions == 0:
                self.logger.info("All sessions completed")
                return
            
            self.logger.info(f"Waiting for {active_sessions} sessions to complete")
            await asyncio.sleep(1)
        
        self.logger.warning(f"Timeout waiting for sessions to complete, proceeding with shutdown")
    
    async def _cleanup_child_sessions(self):
        """Special cleanup for child sessions to ensure child safety."""
        self.logger.info("Performing child session cleanup")
        
        if ServiceType.USER_SERVICE in self.service_instances:
            user_service = self.service_instances[ServiceType.USER_SERVICE]
            
            # Get all active child sessions
            if hasattr(user_service, '_sessions'):
                child_sessions = [
                    session for session in user_service._sessions.values()
                    if hasattr(session, 'user_type') and session.user_type == 'child'
                ]
                
                # Gracefully end child sessions with proper logging
                for session in child_sessions:
                    try:
                        if hasattr(user_service, 'end_session'):
                            await user_service.end_session(session.session_id)
                        
                        # Log child session cleanup
                        self.logger.info(f"Child session {session.session_id} ended during shutdown")
                        
                    except Exception as e:
                        self.logger.error(f"Error ending child session {session.session_id}: {e}")
    
    async def _flush_pending_data(self):
        """Flush any pending audit logs or important data."""
        self.logger.info("Flushing pending data")
        
        # Flush audit logs if encryption service is available
        if ServiceType.ENCRYPTION_SERVICE in self.service_instances:
            encryption_service = self.service_instances[ServiceType.ENCRYPTION_SERVICE]
            if hasattr(encryption_service, '_flush_audit_buffer'):
                try:
                    await encryption_service._flush_audit_buffer()
                    self.logger.info("Audit logs flushed")
                except Exception as e:
                    self.logger.error(f"Error flushing audit logs: {e}")
    
    async def _close_service_connections(self):
        """Close all service connections."""
        self.logger.info("Closing service connections")
        
        for service_type, service_instance in self.service_instances.items():
            try:
                if hasattr(service_instance, 'close'):
                    await service_instance.close()
                    self.logger.info(f"Closed {service_type.value} connection")
            except Exception as e:
                self.logger.error(f"Error closing {service_type.value}: {e}")
    
    async def _run_cleanup_callbacks(self):
        """Run all registered cleanup callbacks."""
        self.logger.info(f"Running {len(self.cleanup_callbacks)} cleanup callbacks")
        
        for callback in self.cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                self.logger.error(f"Error in cleanup callback: {e}")
    
    async def _log_shutdown_event(self, message: str):
        """Log shutdown event."""
        self.logger.info(message, extra={
            'event_type': 'graceful_shutdown',
            'shutdown_phase': self.shutdown_phase.value if self.shutdown_phase else None,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_overall_health_status(self) -> Dict[str, Any]:
        """Get overall system health status."""
        if not self.health_history:
            return {
                'status': HealthStatus.UNKNOWN,
                'message': 'No health checks performed yet'
            }
        
        # Get latest results for all services
        latest_results = {}
        for service_name, history in self.health_history.items():
            if history:
                latest_results[service_name] = history[-1]
        
        # Determine overall status
        critical_count = sum(1 for result in latest_results.values() 
                           if result.status == HealthStatus.CRITICAL)
        unhealthy_count = sum(1 for result in latest_results.values() 
                            if result.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for result in latest_results.values() 
                           if result.status == HealthStatus.DEGRADED)
        
        if critical_count > 0:
            overall_status = HealthStatus.CRITICAL
        elif unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        return {
            'status': overall_status,
            'last_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'services_checked': len(latest_results),
            'critical_services': critical_count,
            'unhealthy_services': unhealthy_count,
            'degraded_services': degraded_count,
            'healthy_services': len(latest_results) - critical_count - unhealthy_count - degraded_count,
            'system_uptime_seconds': self.system_metrics_history[-1].uptime_seconds if self.system_metrics_history else 0,
            'monitoring_active': self._monitoring_task and not self._monitoring_task.done()
        }
    
    def get_service_health_history(self, service_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get health history for a specific service."""
        if service_name not in self.health_history:
            return []
        
        history = self.health_history[service_name][-limit:]
        return [result.to_dict() for result in history]
    
    def get_system_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent system metrics."""
        metrics = self.system_metrics_history[-limit:]
        return [metric.to_dict() for metric in metrics]


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_health_monitoring_service(
    check_interval_seconds: int = 30,
    child_protection_mode: bool = True
) -> HealthMonitoringService:
    """
    Factory function to create health monitoring service.
    
    Args:
        check_interval_seconds: Health check interval
        child_protection_mode: Enable child protection features
        
    Returns:
        Configured HealthMonitoringService instance
    """
    if child_protection_mode:
        # More frequent checks for child safety
        check_interval_seconds = min(check_interval_seconds, 15)
        shutdown_timeout = 600  # 10 minutes for child session cleanup
    else:
        shutdown_timeout = 300  # 5 minutes standard
    
    return HealthMonitoringService(
        check_interval_seconds=check_interval_seconds,
        unhealthy_threshold=3,
        enable_auto_recovery=True,
        shutdown_timeout_seconds=shutdown_timeout
    )


# Export for easy imports
__all__ = [
    "HealthMonitoringService",
    "HealthStatus",
    "ServiceType",
    "ShutdownPhase",
    "HealthCheckResult",
    "SystemMetrics",
    "create_health_monitoring_service"
]


if __name__ == "__main__":
    # Demo usage
    async def demo():
        print("🏥 Health Monitoring & Graceful Shutdown Service Demo")
        
        health_service = create_health_monitoring_service()
        
        # Run health checks
        results = await health_service.run_all_health_checks()
        print(f"Health check results: {len(results)} services checked")
        
        # Get overall health
        overall_health = health_service.get_overall_health_status()
        print(f"Overall health: {overall_health['status']}")
        
        # Start monitoring
        await health_service.start_monitoring()
        print("Health monitoring started")
        
        # Wait a bit then shutdown
        await asyncio.sleep(5)
        await health_service.stop_monitoring()
        print("Health monitoring stopped")
    
    asyncio.run(demo())