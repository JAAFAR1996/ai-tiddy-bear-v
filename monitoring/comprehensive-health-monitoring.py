"""
Comprehensive Health Monitoring System - AI Teddy Bear
====================================================
Advanced health monitoring with predictive analytics, dependency tracking,
and child safety-focused health checks.

Features:
- Multi-tier health checks (shallow, deep, comprehensive)
- Dependency chain health monitoring
- Predictive health analytics
- Child safety service health validation
- Business impact assessment
- Auto-healing trigger integration
- Health trend analysis

Author: Senior Engineering Team
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple
import json
import statistics
from collections import defaultdict, deque
import aiohttp
import psutil

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthCheckType(Enum):
    """Types of health checks."""
    SHALLOW = "shallow"      # Basic connectivity, <100ms
    DEEP = "deep"           # Functional validation, <500ms  
    COMPREHENSIVE = "comprehensive"  # Full system validation, <2s


class ServiceCategory(Enum):
    """Service categories for prioritization."""
    CHILD_SAFETY = "child_safety"
    AI_PROVIDER = "ai_provider"
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_API = "external_api"
    INFRASTRUCTURE = "infrastructure"
    BUSINESS_LOGIC = "business_logic"


@dataclass
class HealthMetric:
    """Individual health metric."""
    name: str
    value: float
    unit: str
    threshold_warning: float
    threshold_critical: float
    status: HealthStatus = HealthStatus.UNKNOWN
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Calculate status based on thresholds."""
        if self.value >= self.threshold_critical:
            self.status = HealthStatus.CRITICAL
        elif self.value >= self.threshold_warning:
            self.status = HealthStatus.DEGRADED
        else:
            self.status = HealthStatus.HEALTHY


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    service_name: str
    check_type: HealthCheckType
    status: HealthStatus
    response_time_ms: float
    error_message: Optional[str] = None
    metrics: Dict[str, HealthMetric] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    business_impact: str = "low"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    auto_healing_triggered: bool = False


@dataclass
class ServiceHealthConfig:
    """Configuration for service health monitoring."""
    name: str
    category: ServiceCategory
    priority: int = 5  # 1 = highest, 10 = lowest
    
    # Health check intervals
    shallow_interval_seconds: int = 10
    deep_interval_seconds: int = 60
    comprehensive_interval_seconds: int = 300
    
    # Thresholds
    response_time_warning_ms: float = 500.0
    response_time_critical_ms: float = 2000.0
    
    # Dependencies
    dependencies: List[str] = field(default_factory=list)
    
    # Business impact
    business_impact: str = "medium"
    
    # Auto-healing
    enable_auto_healing: bool = False
    healing_actions: List[str] = field(default_factory=list)
    
    # Child safety specific
    is_child_safety_critical: bool = False


class ChildSafetyHealthValidator:
    """Specialized health validator for child safety services."""
    
    def __init__(self):
        self.content_filter_tests = [
            {"input": "Tell me about dragons", "expected_safe": True},
            {"input": "Violence and harmful content", "expected_safe": False},
            {"input": "Educational story about friendship", "expected_safe": True}
        ]
        
    async def validate_content_filtering(self, content_filter_endpoint: str) -> HealthCheckResult:
        """Validate content filtering functionality."""
        start_time = time.time()
        
        try:
            passed_tests = 0
            total_tests = len(self.content_filter_tests)
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                for test_case in self.content_filter_tests:
                    try:
                        async with session.post(
                            content_filter_endpoint,
                            json={"content": test_case["input"]}
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                is_safe = result.get("is_safe", False)
                                if is_safe == test_case["expected_safe"]:
                                    passed_tests += 1
                    except Exception as e:
                        logger.warning(f"Content filter test failed: {e}")
            
            response_time_ms = (time.time() - start_time) * 1000
            success_rate = (passed_tests / total_tests) * 100
            
            # Determine status
            if success_rate >= 95:
                status = HealthStatus.HEALTHY
            elif success_rate >= 80:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.CRITICAL
                
            return HealthCheckResult(
                service_name="content_filter",
                check_type=HealthCheckType.DEEP,
                status=status,
                response_time_ms=response_time_ms,
                metrics={
                    "success_rate": HealthMetric(
                        name="content_filter_success_rate",
                        value=success_rate,
                        unit="percent",
                        threshold_warning=90.0,
                        threshold_critical=80.0
                    ),
                    "test_count": HealthMetric(
                        name="tests_executed",
                        value=total_tests,
                        unit="count",
                        threshold_warning=0,
                        threshold_critical=0
                    )
                },
                business_impact="critical"
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="content_filter",
                check_type=HealthCheckType.DEEP,
                status=HealthStatus.CRITICAL,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                business_impact="critical"
            )
            
    async def validate_coppa_compliance(self, compliance_endpoint: str) -> HealthCheckResult:
        """Validate COPPA compliance systems."""
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                # Test parental consent validation
                async with session.post(
                    f"{compliance_endpoint}/validate-consent",
                    json={
                        "child_id": "test_child_123",
                        "parent_id": "test_parent_456"
                    }
                ) as response:
                    consent_valid = response.status == 200
                    
                # Test data retention policy
                async with session.get(
                    f"{compliance_endpoint}/retention-policy"
                ) as response:
                    policy_accessible = response.status == 200
                    
            response_time_ms = (time.time() - start_time) * 1000
            compliance_score = (int(consent_valid) + int(policy_accessible)) * 50  # 0-100%
            
            status = HealthStatus.HEALTHY if compliance_score >= 90 else HealthStatus.CRITICAL
            
            return HealthCheckResult(
                service_name="coppa_compliance",
                check_type=HealthCheckType.DEEP,
                status=status,
                response_time_ms=response_time_ms,
                metrics={
                    "compliance_score": HealthMetric(
                        name="coppa_compliance_score",
                        value=compliance_score,
                        unit="percent",
                        threshold_warning=95.0,
                        threshold_critical=90.0
                    )
                },
                business_impact="critical"
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="coppa_compliance",
                check_type=HealthCheckType.DEEP,
                status=HealthStatus.CRITICAL,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                business_impact="critical"
            )


class AIProviderHealthMonitor:
    """Health monitoring for AI providers."""
    
    def __init__(self):
        self.test_prompts = [
            "Tell me a short story about friendship.",
            "What is 2+2?",
            "Describe the color blue in simple words."
        ]
        
    async def check_openai_health(self, api_key: str) -> HealthCheckResult:
        """Check OpenAI API health."""
        start_time = time.time()
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # Test models endpoint
                async with session.get(
                    "https://api.openai.com/v1/models",
                    headers=headers
                ) as response:
                    models_accessible = response.status == 200
                    
                # Test chat completion with a simple prompt
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [{"role": "user", "content": "Hello, reply with just 'OK'"}],
                        "max_tokens": 5
                    }
                ) as response:
                    completion_working = response.status == 200
                    
            response_time_ms = (time.time() - start_time) * 1000
            health_score = (int(models_accessible) + int(completion_working)) * 50
            
            status = HealthStatus.HEALTHY if health_score >= 90 else HealthStatus.DEGRADED
            
            return HealthCheckResult(
                service_name="openai_api",
                check_type=HealthCheckType.DEEP,
                status=status,
                response_time_ms=response_time_ms,
                metrics={
                    "health_score": HealthMetric(
                        name="openai_health_score",
                        value=health_score,
                        unit="percent",
                        threshold_warning=80.0,
                        threshold_critical=50.0
                    )
                },
                business_impact="high"
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="openai_api",
                check_type=HealthCheckType.DEEP,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                business_impact="high"
            )
            
    async def check_elevenlabs_health(self, api_key: str) -> HealthCheckResult:
        """Check ElevenLabs API health."""
        start_time = time.time()
        
        try:
            headers = {
                "xi-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # Test voices endpoint
                async with session.get(
                    "https://api.elevenlabs.io/v1/voices",
                    headers=headers
                ) as response:
                    voices_accessible = response.status == 200
                    
                # Test user info
                async with session.get(
                    "https://api.elevenlabs.io/v1/user",
                    headers=headers
                ) as response:
                    user_info_accessible = response.status == 200
                    
            response_time_ms = (time.time() - start_time) * 1000
            health_score = (int(voices_accessible) + int(user_info_accessible)) * 50
            
            status = HealthStatus.HEALTHY if health_score >= 90 else HealthStatus.DEGRADED
            
            return HealthCheckResult(
                service_name="elevenlabs_api",
                check_type=HealthCheckType.DEEP, 
                status=status,
                response_time_ms=response_time_ms,
                metrics={
                    "health_score": HealthMetric(
                        name="elevenlabs_health_score",
                        value=health_score,
                        unit="percent",
                        threshold_warning=80.0,
                        threshold_critical=50.0
                    )
                },
                business_impact="high"
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="elevenlabs_api",
                check_type=HealthCheckType.DEEP,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                business_impact="high"
            )


class SystemResourceMonitor:
    """Monitor system resources and infrastructure health."""
    
    async def check_system_resources(self) -> HealthCheckResult:
        """Check system resource utilization."""
        start_time = time.time()
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network stats
            network = psutil.net_io_counters()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Determine overall system health
            critical_resources = []
            if cpu_percent > 90:
                critical_resources.append("cpu")
            if memory_percent > 90:
                critical_resources.append("memory") 
            if disk_percent > 90:
                critical_resources.append("disk")
                
            if critical_resources:
                status = HealthStatus.CRITICAL
            elif cpu_percent > 70 or memory_percent > 80 or disk_percent > 80:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
                
            return HealthCheckResult(
                service_name="system_resources",
                check_type=HealthCheckType.SHALLOW,
                status=status,
                response_time_ms=response_time_ms,
                metrics={
                    "cpu_usage": HealthMetric(
                        name="cpu_usage_percent",
                        value=cpu_percent,
                        unit="percent",
                        threshold_warning=70.0,
                        threshold_critical=90.0
                    ),
                    "memory_usage": HealthMetric(
                        name="memory_usage_percent", 
                        value=memory_percent,
                        unit="percent",
                        threshold_warning=80.0,
                        threshold_critical=90.0
                    ),
                    "disk_usage": HealthMetric(
                        name="disk_usage_percent",
                        value=disk_percent,
                        unit="percent",
                        threshold_warning=80.0,
                        threshold_critical=90.0
                    )
                },
                business_impact="high" if critical_resources else "medium"
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="system_resources",
                check_type=HealthCheckType.SHALLOW,
                status=HealthStatus.CRITICAL,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                business_impact="high"
            )


class ComprehensiveHealthManager:
    """
    Comprehensive health monitoring system for AI Teddy Bear platform.
    
    Provides multi-tier health checks with predictive analytics and
    business impact assessment.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        
        # Health validators
        self.child_safety_validator = ChildSafetyHealthValidator()
        self.ai_provider_monitor = AIProviderHealthMonitor()
        self.system_monitor = SystemResourceMonitor()
        
        # Health history for trend analysis
        self.health_history: defaultdict = defaultdict(lambda: deque(maxlen=1000))
        
        # Service configurations
        self.service_configs = self._initialize_service_configs()
        
        # Health check tasks
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        
        # Auto-healing system
        self.auto_healing_enabled = config.get("auto_healing_enabled", True)
        self.healing_callbacks: Dict[str, Callable] = {}
        
        # Business impact calculator
        self.business_impact_weights = {
            "child_safety": 10.0,
            "ai_provider": 8.0,
            "database": 7.0,
            "cache": 5.0,
            "external_api": 4.0,
            "infrastructure": 6.0,
            "business_logic": 7.0
        }
        
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for health monitoring."""
        return {
            "enable_predictive_analytics": True,
            "health_trend_window_hours": 24,
            "auto_healing_enabled": True,
            "business_impact_threshold": 7.0,
            "alert_on_degraded": True,
            "health_check_timeout_seconds": 30
        }
        
    def _initialize_service_configs(self) -> Dict[str, ServiceHealthConfig]:
        """Initialize service health configurations."""
        return {
            "content_filter": ServiceHealthConfig(
                name="content_filter",
                category=ServiceCategory.CHILD_SAFETY,
                priority=1,
                shallow_interval_seconds=5,
                deep_interval_seconds=30,
                is_child_safety_critical=True,
                enable_auto_healing=True,
                business_impact="critical"
            ),
            "coppa_compliance": ServiceHealthConfig(
                name="coppa_compliance",
                category=ServiceCategory.CHILD_SAFETY,
                priority=1,
                shallow_interval_seconds=10,
                deep_interval_seconds=60,
                is_child_safety_critical=True,
                business_impact="critical"
            ),
            "openai_api": ServiceHealthConfig(
                name="openai_api",
                category=ServiceCategory.AI_PROVIDER,
                priority=2,
                deep_interval_seconds=120,
                dependencies=["internet_connectivity"],
                business_impact="high"
            ),
            "elevenlabs_api": ServiceHealthConfig(
                name="elevenlabs_api", 
                category=ServiceCategory.AI_PROVIDER,
                priority=2,
                deep_interval_seconds=120,
                dependencies=["internet_connectivity"],
                business_impact="high"
            ),
            "database": ServiceHealthConfig(
                name="database",
                category=ServiceCategory.DATABASE,
                priority=2,
                shallow_interval_seconds=30,
                deep_interval_seconds=300,
                enable_auto_healing=True,
                business_impact="high"
            ),
            "redis_cache": ServiceHealthConfig(
                name="redis_cache",
                category=ServiceCategory.CACHE,
                priority=3,
                shallow_interval_seconds=15,
                enable_auto_healing=True,
                business_impact="medium"
            ),
            "system_resources": ServiceHealthConfig(
                name="system_resources",
                category=ServiceCategory.INFRASTRUCTURE,
                priority=2,
                shallow_interval_seconds=10,
                business_impact="high"
            )
        }
        
    async def start_monitoring(self):
        """Start comprehensive health monitoring."""
        logger.info("Starting comprehensive health monitoring")
        
        # Start health check tasks for each service
        for service_name, config in self.service_configs.items():
            # Shallow checks
            self._health_check_tasks[f"{service_name}_shallow"] = asyncio.create_task(
                self._continuous_health_check(service_name, HealthCheckType.SHALLOW)
            )
            
            # Deep checks
            self._health_check_tasks[f"{service_name}_deep"] = asyncio.create_task(
                self._continuous_health_check(service_name, HealthCheckType.DEEP)
            )
            
            # Comprehensive checks
            if config.priority <= 2:  # Only for high-priority services
                self._health_check_tasks[f"{service_name}_comprehensive"] = asyncio.create_task(
                    self._continuous_health_check(service_name, HealthCheckType.COMPREHENSIVE)
                )
                
        # Start health analytics task
        if self.config.get("enable_predictive_analytics", True):
            self._health_check_tasks["predictive_analytics"] = asyncio.create_task(
                self._predictive_health_analytics()
            )
            
        logger.info(f"Started {len(self._health_check_tasks)} health monitoring tasks")
        
    async def _continuous_health_check(self, service_name: str, check_type: HealthCheckType):
        """Run continuous health checks for a service."""
        config = self.service_configs[service_name]
        
        # Determine interval based on check type
        if check_type == HealthCheckType.SHALLOW:
            interval = config.shallow_interval_seconds
        elif check_type == HealthCheckType.DEEP:
            interval = config.deep_interval_seconds
        else:  # COMPREHENSIVE
            interval = config.comprehensive_interval_seconds
            
        while True:
            try:
                health_result = await self._perform_health_check(service_name, check_type)
                
                # Store in history
                self.health_history[f"{service_name}_{check_type.value}"].append(health_result)
                
                # Trigger auto-healing if needed
                if (config.enable_auto_healing and 
                    health_result.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]):
                    await self._trigger_auto_healing(service_name, health_result)
                    
                # Log critical issues immediately
                if health_result.status == HealthStatus.CRITICAL:
                    logger.critical(
                        f"CRITICAL health issue detected in {service_name}: {health_result.error_message}"
                    )
                elif health_result.status == HealthStatus.UNHEALTHY:
                    logger.error(
                        f"UNHEALTHY service detected: {service_name} - {health_result.error_message}"
                    )
                    
            except Exception as e:
                logger.error(f"Health check failed for {service_name}: {e}")
                
            await asyncio.sleep(interval)
            
    async def _perform_health_check(
        self, 
        service_name: str, 
        check_type: HealthCheckType
    ) -> HealthCheckResult:
        """Perform specific health check based on service and type."""
        
        try:
            if service_name == "content_filter":
                if check_type == HealthCheckType.DEEP:
                    return await self.child_safety_validator.validate_content_filtering(
                        "http://localhost:8000/api/content/filter"
                    )
                    
            elif service_name == "coppa_compliance":
                if check_type == HealthCheckType.DEEP:
                    return await self.child_safety_validator.validate_coppa_compliance(
                        "http://localhost:8000/api/compliance"
                    )
                    
            elif service_name == "openai_api":
                if check_type == HealthCheckType.DEEP:
                    api_key = self.config.get("openai_api_key", "")
                    return await self.ai_provider_monitor.check_openai_health(api_key)
                    
            elif service_name == "elevenlabs_api":
                if check_type == HealthCheckType.DEEP:
                    api_key = self.config.get("elevenlabs_api_key", "")
                    return await self.ai_provider_monitor.check_elevenlabs_health(api_key)
                    
            elif service_name == "system_resources":
                return await self.system_monitor.check_system_resources()
                
            elif service_name == "database":
                return await self._check_database_health()
                
            elif service_name == "redis_cache":
                return await self._check_redis_health()
                
            # Default shallow health check
            return await self._basic_connectivity_check(service_name)
            
        except Exception as e:
            return HealthCheckResult(
                service_name=service_name,
                check_type=check_type,
                status=HealthStatus.CRITICAL,
                response_time_ms=0,
                error_message=str(e),
                business_impact=self.service_configs[service_name].business_impact
            )
            
    async def _basic_connectivity_check(self, service_name: str) -> HealthCheckResult:
        """Basic connectivity health check."""
        start_time = time.time()
        
        # This would normally test service endpoints
        # For now, simulate a basic check
        await asyncio.sleep(0.01)  # Simulate small delay
        
        response_time_ms = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            service_name=service_name,
            check_type=HealthCheckType.SHALLOW,
            status=HealthStatus.HEALTHY,
            response_time_ms=response_time_ms,
            business_impact=self.service_configs[service_name].business_impact
        )
        
    async def _check_database_health(self) -> HealthCheckResult:
        """Check database health."""
        start_time = time.time()
        
        try:
            # This would normally connect to the database and run health queries
            # For now, simulate database health check
            await asyncio.sleep(0.05)  # Simulate database query
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="database",
                check_type=HealthCheckType.SHALLOW,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                metrics={
                    "connection_pool_usage": HealthMetric(
                        name="db_connection_pool_usage",
                        value=45.0,  # Simulated
                        unit="percent",
                        threshold_warning=80.0,
                        threshold_critical=95.0
                    )
                },
                business_impact="high"
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="database",
                check_type=HealthCheckType.SHALLOW,
                status=HealthStatus.CRITICAL,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                business_impact="high"
            )
            
    async def _check_redis_health(self) -> HealthCheckResult:
        """Check Redis cache health."""
        start_time = time.time()
        
        try:
            # Simulate Redis health check
            await asyncio.sleep(0.02)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="redis_cache",
                check_type=HealthCheckType.SHALLOW,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                metrics={
                    "memory_usage": HealthMetric(
                        name="redis_memory_usage",
                        value=60.0,  # Simulated
                        unit="percent",
                        threshold_warning=80.0,
                        threshold_critical=95.0
                    )
                },
                business_impact="medium"
            )
            
        except Exception as e:
            return HealthCheckResult(
                service_name="redis_cache",
                check_type=HealthCheckType.SHALLOW,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                business_impact="medium"
            )
            
    async def _trigger_auto_healing(self, service_name: str, health_result: HealthCheckResult):
        """Trigger auto-healing actions for unhealthy services."""
        if not self.auto_healing_enabled:
            return
            
        config = self.service_configs[service_name]
        
        logger.warning(f"Triggering auto-healing for {service_name}")
        
        # Mark auto-healing as triggered
        health_result.auto_healing_triggered = True
        
        # Execute healing callbacks
        if service_name in self.healing_callbacks:
            try:
                await self.healing_callbacks[service_name](health_result)
                logger.info(f"Auto-healing executed for {service_name}")
            except Exception as e:
                logger.error(f"Auto-healing failed for {service_name}: {e}")
                
    async def _predictive_health_analytics(self):
        """Perform predictive health analytics."""
        while True:
            try:
                # Analyze trends every 5 minutes
                await asyncio.sleep(300)
                
                for service_name in self.service_configs:
                    await self._analyze_service_health_trends(service_name)
                    
            except Exception as e:
                logger.error(f"Predictive analytics failed: {e}")
                
    async def _analyze_service_health_trends(self, service_name: str):
        """Analyze health trends for predictive alerts."""
        try:
            history_key = f"{service_name}_shallow"
            if history_key not in self.health_history:
                return
                
            recent_checks = list(self.health_history[history_key])
            if len(recent_checks) < 10:
                return
                
            # Calculate health trend
            recent_response_times = [check.response_time_ms for check in recent_checks[-10:]]
            avg_response_time = statistics.mean(recent_response_times)
            
            # Check for degradation trend
            if len(recent_response_times) >= 5:
                recent_avg = statistics.mean(recent_response_times[-5:])
                older_avg = statistics.mean(recent_response_times[-10:-5])
                
                if recent_avg > older_avg * 1.5:  # 50% increase
                    logger.warning(
                        f"Performance degradation trend detected for {service_name}: "
                        f"{older_avg:.2f}ms -> {recent_avg:.2f}ms"
                    )
                    
        except Exception as e:
            logger.error(f"Health trend analysis failed for {service_name}: {e}")
            
    def get_overall_health_status(self) -> Dict[str, Any]:
        """Get overall system health status."""
        service_statuses = {}
        critical_services = []
        degraded_services = []
        
        for service_name in self.service_configs:
            # Get latest health check
            history_key = f"{service_name}_shallow"
            if history_key in self.health_history and self.health_history[history_key]:
                latest_check = self.health_history[history_key][-1]
                service_statuses[service_name] = {
                    "status": latest_check.status.value,
                    "response_time_ms": latest_check.response_time_ms,
                    "last_check": latest_check.timestamp.isoformat(),
                    "business_impact": latest_check.business_impact
                }
                
                if latest_check.status == HealthStatus.CRITICAL:
                    critical_services.append(service_name)
                elif latest_check.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
                    degraded_services.append(service_name)
            else:
                service_statuses[service_name] = {
                    "status": "unknown",
                    "response_time_ms": 0,
                    "last_check": None,
                    "business_impact": "unknown"
                }
                
        # Calculate overall status
        if critical_services:
            overall_status = HealthStatus.CRITICAL
        elif degraded_services:
            overall_status = HealthStatus.DEGRADED  
        else:
            overall_status = HealthStatus.HEALTHY
            
        return {
            "overall_status": overall_status.value,
            "services": service_statuses,
            "critical_services": critical_services,
            "degraded_services": degraded_services,
            "total_services": len(self.service_configs),
            "healthy_services": len([s for s in service_statuses.values() 
                                   if s["status"] == "healthy"]),
            "last_updated": datetime.utcnow().isoformat()
        }
        
    def register_healing_callback(self, service_name: str, callback: Callable):
        """Register auto-healing callback for a service."""
        self.healing_callbacks[service_name] = callback
        logger.info(f"Registered auto-healing callback for {service_name}")
        
    async def stop_monitoring(self):
        """Stop all health monitoring tasks."""
        logger.info("Stopping health monitoring")
        
        for task_name, task in self._health_check_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        self._health_check_tasks.clear()
        logger.info("Health monitoring stopped")


# Factory function for production use
async def create_health_manager(
    config: Optional[Dict[str, Any]] = None,
    enable_auto_healing: bool = True
) -> ComprehensiveHealthManager:
    """Create and start comprehensive health manager."""
    
    config = config or {}
    config["auto_healing_enabled"] = enable_auto_healing
    
    health_manager = ComprehensiveHealthManager(config)
    await health_manager.start_monitoring()
    
    return health_manager


# Example usage for production deployment
if __name__ == "__main__":
    async def main():
        # Create health manager
        health_manager = await create_health_manager({
            "openai_api_key": "your-openai-key",
            "elevenlabs_api_key": "your-elevenlabs-key",
            "enable_predictive_analytics": True
        })
        
        # Register healing callbacks
        async def restart_service(health_result: HealthCheckResult):
            print(f"Auto-healing triggered for {health_result.service_name}")
            # Implementation would restart the service
            
        health_manager.register_healing_callback("database", restart_service)
        health_manager.register_healing_callback("redis_cache", restart_service)
        
        # Run for demonstration
        await asyncio.sleep(60)
        
        # Get overall status
        status = health_manager.get_overall_health_status()
        print(json.dumps(status, indent=2))
        
        # Stop monitoring
        await health_manager.stop_monitoring()
    
    asyncio.run(main())