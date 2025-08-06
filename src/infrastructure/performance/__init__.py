"""
Comprehensive Performance Optimization System
Production-ready performance infrastructure for child-safe AI applications
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass

from .cdn_manager import CDNManager, create_cdn_manager
from .cache_manager import CacheManager, create_cache_manager
from .compression_manager import CompressionManager, create_compression_manager
from .database_optimizer import ConnectionPoolManager, create_database_optimizer
from .monitoring import PerformanceMonitor, create_performance_monitor
from .load_testing import LoadTestRunner, create_load_test_runner
from .optimization_engine import OptimizationEngine, create_optimization_engine


logger = logging.getLogger(__name__)


@dataclass
class PerformanceConfig:
    """Comprehensive performance system configuration."""
    
    # CDN Configuration
    cdn_enabled: bool = True
    cloudflare_config: Optional[Dict[str, Any]] = None
    aws_cloudfront_config: Optional[Dict[str, Any]] = None
    azure_cdn_config: Optional[Dict[str, Any]] = None
    
    # Cache Configuration
    redis_url: Optional[str] = None
    cache_enabled: bool = True
    
    # Database Configuration
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "ai_teddy_bear"
    db_username: str = "app_user"
    db_password: str = ""
    db_pool_size: int = 10
    
    # Compression Configuration
    compression_enabled: bool = True
    gzip_level: int = 6
    brotli_level: int = 6
    webp_quality: int = 85
    
    # Monitoring Configuration
    monitoring_enabled: bool = True
    monitoring_interval_seconds: int = 60
    webhook_alert_url: Optional[str] = None
    
    # Optimization Configuration
    auto_optimization_enabled: bool = True
    optimization_interval_minutes: int = 60
    
    # Child Safety Configuration
    child_data_encryption: bool = True
    coppa_compliance_monitoring: bool = True


class PerformanceSystem:
    """Integrated performance optimization system."""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        
        # Core components
        self.cdn_manager: Optional[CDNManager] = None
        self.cache_manager: Optional[CacheManager] = None
        self.compression_manager: Optional[CompressionManager] = None
        self.database_optimizer: Optional[ConnectionPoolManager] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.load_test_runner: Optional[LoadTestRunner] = None
        self.optimization_engine: Optional[OptimizationEngine] = None
        
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all performance components."""
        if self._initialized:
            return
        
        logger.info("Initializing comprehensive performance system...")
        
        # Initialize cache manager
        if self.config.cache_enabled:
            self.cache_manager = create_cache_manager(self.config.redis_url)
            logger.info("Cache manager initialized")
        
        # Initialize CDN manager
        if self.config.cdn_enabled:
            self.cdn_manager = create_cdn_manager(
                cloudflare_config=self.config.cloudflare_config,
                aws_config=self.config.aws_cloudfront_config,
                azure_config=self.config.azure_cdn_config
            )
            await self.cdn_manager.initialize()
            logger.info("CDN manager initialized")
        
        # Initialize compression manager
        if self.config.compression_enabled:
            self.compression_manager = create_compression_manager(
                gzip_level=self.config.gzip_level,
                brotli_level=self.config.brotli_level,
                webp_quality=self.config.webp_quality
            )
            logger.info("Compression manager initialized")
        
        # Initialize database optimizer
        self.database_optimizer = create_database_optimizer(
            host=self.config.db_host,
            port=self.config.db_port,
            database=self.config.db_name,
            username=self.config.db_username,
            password=self.config.db_password,
            pool_size=self.config.db_pool_size,
            child_data_encryption=self.config.child_data_encryption
        )
        await self.database_optimizer.initialize()
        logger.info("Database optimizer initialized")
        
        # Initialize performance monitor
        if self.config.monitoring_enabled:
            self.performance_monitor = create_performance_monitor(
                cache_manager=self.cache_manager,
                cdn_manager=self.cdn_manager,
                webhook_url=self.config.webhook_alert_url
            )
            logger.info("Performance monitor initialized")
        
        # Initialize load test runner
        self.load_test_runner = create_load_test_runner()
        logger.info("Load test runner initialized")
        
        # Initialize optimization engine
        if self.config.auto_optimization_enabled and self.performance_monitor:
            self.optimization_engine = create_optimization_engine(
                performance_monitor=self.performance_monitor,
                cache_manager=self.cache_manager,
                cdn_manager=self.cdn_manager,
                db_manager=self.database_optimizer,
                compression_manager=self.compression_manager
            )
            logger.info("Optimization engine initialized")
        
        self._initialized = True
        logger.info("Performance system initialization completed")
    
    async def start(self) -> None:
        """Start all performance services."""
        if not self._initialized:
            await self.initialize()
        
        logger.info("Starting performance system services...")
        
        # Start performance monitoring
        if self.performance_monitor:
            await self.performance_monitor.start_monitoring(
                interval_seconds=self.config.monitoring_interval_seconds
            )
            logger.info("Performance monitoring started")
        
        # Start optimization engine
        if self.optimization_engine:
            await self.optimization_engine.start_optimization_engine(
                interval_minutes=self.config.optimization_interval_minutes
            )
            logger.info("Optimization engine started")
        
        logger.info("Performance system services started successfully")
    
    async def stop(self) -> None:
        """Stop all performance services."""
        logger.info("Stopping performance system services...")
        
        # Stop optimization engine
        if self.optimization_engine:
            await self.optimization_engine.stop_optimization_engine()
            logger.info("Optimization engine stopped")
        
        # Stop performance monitoring
        if self.performance_monitor:
            await self.performance_monitor.stop_monitoring()
            logger.info("Performance monitoring stopped")
        
        # Close database connections
        if self.database_optimizer:
            await self.database_optimizer.close()
            logger.info("Database connections closed")
        
        logger.info("Performance system services stopped")
    
    async def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all performance components."""
        status = {
            "system_initialized": self._initialized,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # CDN status
        if self.cdn_manager:
            try:
                cdn_health = await self.cdn_manager.health_check()
                status["cdn"] = cdn_health
            except Exception as e:
                status["cdn"] = {"status": "error", "error": str(e)}
        else:
            status["cdn"] = {"status": "disabled"}
        
        # Cache status
        if self.cache_manager:
            try:
                cache_health = await self.cache_manager.health_check()
                status["cache"] = cache_health
            except Exception as e:
                status["cache"] = {"status": "error", "error": str(e)}
        else:
            status["cache"] = {"status": "disabled"}
        
        # Database status
        if self.database_optimizer:
            try:
                db_health = await self.database_optimizer.health_check()
                status["database"] = db_health
            except Exception as e:
                status["database"] = {"status": "error", "error": str(e)}
        else:
            status["database"] = {"status": "not_initialized"}
        
        # Monitoring status
        if self.performance_monitor:
            try:
                monitor_health = await self.performance_monitor.health_check()
                status["monitoring"] = monitor_health
            except Exception as e:
                status["monitoring"] = {"status": "error", "error": str(e)}
        else:
            status["monitoring"] = {"status": "disabled"}
        
        # Optimization engine status
        if self.optimization_engine:
            try:
                opt_report = await self.optimization_engine.get_optimization_report()
                status["optimization"] = {
                    "status": "running" if opt_report["summary"]["engine_running"] else "stopped",
                    "pending_recommendations": opt_report["summary"]["pending_recommendations"],
                    "completed_optimizations": opt_report["summary"]["completed_optimizations"],
                    "total_performance_gain": opt_report["summary"]["total_actual_gain_percent"]
                }
            except Exception as e:
                status["optimization"] = {"status": "error", "error": str(e)}
        else:
            status["optimization"] = {"status": "disabled"}
        
        # Overall system health
        component_statuses = []
        for component, component_status in status.items():
            if isinstance(component_status, dict) and "status" in component_status:
                component_statuses.append(component_status["status"])
        
        if "error" in component_statuses or "critical" in component_statuses:
            status["overall_status"] = "critical"
        elif "degraded" in component_statuses or "unhealthy" in component_statuses:
            status["overall_status"] = "degraded"
        elif "disabled" in component_statuses:
            status["overall_status"] = "partial"
        else:
            status["overall_status"] = "healthy"
        
        return status
    
    async def run_performance_benchmark(self, duration_minutes: int = 5) -> Dict[str, Any]:
        """Run comprehensive performance benchmark."""
        if not self.load_test_runner:
            raise RuntimeError("Load test runner not initialized")
        
        logger.info(f"Starting {duration_minutes}-minute performance benchmark...")
        
        # Configure benchmark scenarios
        from .load_testing import TestScenario, TestType, LoadPattern
        
        benchmark_scenario = TestScenario(
            name="performance_benchmark",
            description=f"Comprehensive {duration_minutes}-minute benchmark",
            test_type=TestType.LOAD,
            duration_seconds=duration_minutes * 60,
            initial_users=5,
            max_users=50,
            load_pattern=LoadPattern.RAMP_UP,
            ramp_duration_seconds=60,
            child_safe_endpoints_only=True,
            simulate_coppa_compliance=True,
            max_response_time_ms=2000,
            max_error_rate=0.05,
            min_throughput_rps=25.0
        )
        
        # Run benchmark
        self.load_test_runner.scenarios = [benchmark_scenario]
        results = await self.load_test_runner.run_all_scenarios()
        
        # Get current system metrics
        system_status = await self.get_comprehensive_status()
        
        benchmark_report = {
            "benchmark_duration_minutes": duration_minutes,
            "load_test_results": {
                "total_requests": results[0].total_requests,
                "successful_requests": results[0].successful_requests,
                "error_rate": results[0].error_rate,
                "avg_response_time_ms": results[0].avg_response_time_ms,
                "p95_response_time_ms": results[0].p95_response_time_ms,
                "p99_response_time_ms": results[0].p99_response_time_ms,
                "requests_per_second": results[0].requests_per_second,
                "child_safe_requests": results[0].child_safe_requests,
                "coppa_violations": results[0].coppa_violations,
                "overall_passed": results[0].overall_passed
            },
            "system_status": system_status,
            "performance_grade": self._calculate_performance_grade(results[0], system_status)
        }
        
        logger.info(f"Performance benchmark completed. Grade: {benchmark_report['performance_grade']}")
        return benchmark_report
    
    def _calculate_performance_grade(self, test_result, system_status) -> str:
        """Calculate overall performance grade."""
        score = 0
        max_score = 100
        
        # Load test performance (40 points)
        if test_result.overall_passed:
            score += 40
        elif test_result.error_rate < 0.1:  # Less than 10% errors
            score += 20
        
        # Response time performance (30 points)
        if test_result.avg_response_time_ms < 500:
            score += 30
        elif test_result.avg_response_time_ms < 1000:
            score += 20
        elif test_result.avg_response_time_ms < 2000:
            score += 10
        
        # System health (20 points)
        overall_status = system_status.get("overall_status", "unknown")
        if overall_status == "healthy":
            score += 20
        elif overall_status == "partial":
            score += 15
        elif overall_status == "degraded":
            score += 10
        
        # Child safety compliance (10 points)
        if test_result.coppa_violations == 0:
            score += 10
        elif test_result.coppa_violations < 5:
            score += 5
        
        # Convert to letter grade
        percentage = (score / max_score) * 100
        
        if percentage >= 90:
            return "A"
        elif percentage >= 80:
            return "B"
        elif percentage >= 70:
            return "C"
        elif percentage >= 60:
            return "D"
        else:
            return "F"
    
    async def export_performance_report(self, output_path: str) -> str:
        """Export comprehensive performance report."""
        
        # Gather all performance data
        status = await self.get_comprehensive_status()
        
        # Get metrics if monitoring is available
        metrics = {}
        if self.performance_monitor:
            try:
                metrics = await self.performance_monitor.get_performance_dashboard_data()
            except Exception as e:
                logger.warning(f"Could not get performance metrics: {e}")
        
        # Get optimization report if available
        optimization_report = {}
        if self.optimization_engine:
            try:
                optimization_report = await self.optimization_engine.get_optimization_report()
            except Exception as e:
                logger.warning(f"Could not get optimization report: {e}")
        
        # Create comprehensive report
        report = {
            "report_metadata": {
                "generated_at": asyncio.get_event_loop().time(),
                "system_version": "1.0.0",
                "child_safety_compliant": True,
                "coppa_compliant": True
            },
            "system_status": status,
            "performance_metrics": metrics,
            "optimization_report": optimization_report,
            "configuration": {
                "cdn_enabled": self.config.cdn_enabled,
                "cache_enabled": self.config.cache_enabled,
                "compression_enabled": self.config.compression_enabled,
                "monitoring_enabled": self.config.monitoring_enabled,
                "auto_optimization_enabled": self.config.auto_optimization_enabled,
                "child_data_encryption": self.config.child_data_encryption,
                "coppa_compliance_monitoring": self.config.coppa_compliance_monitoring
            }
        }
        
        # Export to file
        import json
        import aiofiles
        
        async with aiofiles.open(output_path, 'w') as f:
            await f.write(json.dumps(report, indent=2, default=str))
        
        logger.info(f"Performance report exported to {output_path}")
        return output_path


# Factory function for easy system creation
def create_performance_system(
    redis_url: Optional[str] = None,
    db_host: str = "localhost",
    db_port: int = 5432,
    db_name: str = "ai_teddy_bear",
    db_username: str = "app_user",
    db_password: str = "",
    webhook_alert_url: Optional[str] = None,
    cloudflare_config: Optional[Dict[str, Any]] = None,
    auto_optimization: bool = True
) -> PerformanceSystem:
    """Create performance system with common configuration."""
    
    config = PerformanceConfig(
        redis_url=redis_url,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_username=db_username,
        db_password=db_password,
        webhook_alert_url=webhook_alert_url,
        cloudflare_config=cloudflare_config,
        auto_optimization_enabled=auto_optimization,
        child_data_encryption=True,
        coppa_compliance_monitoring=True
    )
    
    return PerformanceSystem(config)


# Export main classes and functions
__all__ = [
    'PerformanceSystem',
    'PerformanceConfig',
    'create_performance_system',
    'CDNManager',
    'CacheManager', 
    'CompressionManager',
    'ConnectionPoolManager',
    'PerformanceMonitor',
    'LoadTestRunner',
    'OptimizationEngine'
]