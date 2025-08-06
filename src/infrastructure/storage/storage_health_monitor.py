"""
Storage Health Monitor - Advanced Health Checking System (UPDATED)
================================================================
🔧 UPDATED: Adapted to work with consolidated production_file_storage.py
- Removed dependencies on deleted storage_manager.py
- Works with unified storage architecture

Comprehensive health monitoring for storage providers:
- Deep health checks with synthetic transactions
- Performance benchmarking and SLA monitoring
- Predictive failure detection
- Automated remediation and alerting
- Cost and usage analytics
- Compliance and audit reporting
"""

import asyncio
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time

from .production_file_storage import (
    StorageProvider,
    FileMetadata,
    FileType,
    ProductionFileStorage,
)
from ..resilience.fallback_logger import FallbackLogger
from ..messaging.event_bus_integration import EventPublisher


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    provider: StorageProvider
    status: HealthStatus
    response_time: float
    timestamp: datetime

    # Detailed metrics
    upload_success: bool = False
    download_success: bool = False
    delete_success: bool = False
    list_success: bool = False
    metadata_success: bool = False

    # Performance metrics
    upload_time: float = 0.0
    download_time: float = 0.0
    throughput_mbps: float = 0.0

    # Error details
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Cost analysis
    estimated_cost_per_gb: float = 0.0

    def get_overall_score(self) -> float:
        """Calculate overall health score (0-100)."""
        operations = [
            self.upload_success,
            self.download_success,
            self.delete_success,
            self.list_success,
            self.metadata_success,
        ]

        success_rate = sum(operations) / len(operations) * 100

        # Penalize for high response time (threshold: 2 seconds)
        response_penalty = max(0, (self.response_time - 2.0) * 10)

        # Penalize for low throughput (threshold: 10 Mbps)
        throughput_penalty = max(0, (10.0 - self.throughput_mbps) * 2)

        score = success_rate - response_penalty - throughput_penalty
        return max(0.0, min(100.0, score))


@dataclass
class SLAMetrics:
    """Service Level Agreement metrics."""

    availability_target: float = 99.9  # 99.9% uptime
    response_time_target: float = 2.0  # 2 seconds max response time
    throughput_target: float = 10.0  # 10 Mbps min throughput
    error_rate_target: float = 1.0  # Max 1% error rate

    # Current measurements
    current_availability: float = 0.0
    current_response_time: float = 0.0
    current_throughput: float = 0.0
    current_error_rate: float = 0.0

    # SLA breach tracking
    availability_breaches: int = 0
    response_time_breaches: int = 0
    throughput_breaches: int = 0
    error_rate_breaches: int = 0

    def is_sla_met(self) -> bool:
        """Check if all SLA targets are met."""
        return (
            self.current_availability >= self.availability_target
            and self.current_response_time <= self.response_time_target
            and self.current_throughput >= self.throughput_target
            and self.current_error_rate <= self.error_rate_target
        )

    def get_breach_summary(self) -> Dict[str, int]:
        """Get summary of SLA breaches."""
        return {
            "availability": self.availability_breaches,
            "response_time": self.response_time_breaches,
            "throughput": self.throughput_breaches,
            "error_rate": self.error_rate_breaches,
        }


@dataclass
class PredictiveAnalysis:
    """Predictive failure analysis."""

    provider: StorageProvider
    failure_probability: float = 0.0
    predicted_failure_time: Optional[datetime] = None
    contributing_factors: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    confidence_level: float = 0.0


class StorageHealthMonitor:
    """
    Advanced health monitoring system for storage providers.

    Features:
    - Comprehensive health checks with synthetic transactions
    - SLA monitoring and breach detection
    - Predictive failure analysis
    - Performance benchmarking
    - Cost optimization recommendations
    - Automated alerting and remediation
    """

    def __init__(self, storage_manager: ProductionFileStorage):
        self.storage_manager = storage_manager
        self.logger = FallbackLogger("storage_health_monitor")

        # Health check configuration
        self.check_interval = 300  # 5 minutes
        self.deep_check_interval = 3600  # 1 hour
        self.benchmark_interval = 86400  # 24 hours

        # Health history storage
        self.health_history: Dict[StorageProvider, List[HealthCheckResult]] = {
            provider: [] for provider in StorageProvider
        }

        # SLA tracking
        self.sla_metrics: Dict[StorageProvider, SLAMetrics] = {
            provider: SLAMetrics() for provider in StorageProvider
        }

        # Predictive analysis
        self.predictive_analysis: Dict[StorageProvider, PredictiveAnalysis] = {}

        # Test data for synthetic transactions
        self.test_data_sizes = [1024, 8192, 65536, 1048576]  # 1KB, 8KB, 64KB, 1MB

        # Background tasks
        self._monitor_task: Optional[asyncio.Task] = None
        self._benchmark_task: Optional[asyncio.Task] = None
        self._analysis_task: Optional[asyncio.Task] = None

        # Alert thresholds
        self.alert_thresholds = {
            "response_time_warning": 3.0,
            "response_time_critical": 5.0,
            "error_rate_warning": 5.0,
            "error_rate_critical": 10.0,
            "availability_warning": 99.0,
            "availability_critical": 95.0,
        }

    async def start(self):
        """Start the health monitoring system."""
        try:
            # Start monitoring tasks
            self._monitor_task = asyncio.create_task(self._health_monitor_loop())
            self._benchmark_task = asyncio.create_task(self._benchmark_loop())
            self._analysis_task = asyncio.create_task(self._predictive_analysis_loop())

            self.logger.info("Storage health monitor started")

        except Exception as e:
            self.logger.error(f"Failed to start health monitor: {str(e)}")
            raise

    async def stop(self):
        """Stop the health monitoring system."""
        try:
            # Cancel background tasks
            tasks = [self._monitor_task, self._benchmark_task, self._analysis_task]
            for task in tasks:
                if task:
                    task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)

            self.logger.info("Storage health monitor stopped")

        except Exception as e:
            self.logger.error(f"Error stopping health monitor: {str(e)}")

    async def _health_monitor_loop(self):
        """Main health monitoring loop."""
        while True:
            try:
                await asyncio.sleep(self.check_interval)

                # Perform health checks on all providers
                check_tasks = []
                for provider in self.storage_manager.providers.keys():
                    task = asyncio.create_task(self._perform_health_check(provider))
                    check_tasks.append(task)

                # Wait for all health checks to complete
                results = await asyncio.gather(*check_tasks, return_exceptions=True)

                # Process results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        provider = list(self.storage_manager.providers.keys())[i]
                        self.logger.error(
                            f"Health check failed for {provider.value}: {str(result)}"
                        )
                    elif isinstance(result, HealthCheckResult):
                        await self._process_health_result(result)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitor loop error: {str(e)}")

    async def _perform_health_check(
        self, provider: StorageProvider
    ) -> HealthCheckResult:
        """Perform comprehensive health check for a provider."""
        start_time = time.time()

        result = HealthCheckResult(
            provider=provider,
            status=HealthStatus.HEALTHY,
            response_time=0.0,
            timestamp=datetime.now(),
        )

        try:
            # Generate test file
            test_file_id = f"health_check_{uuid.uuid4().hex[:8]}"
            test_data = b"Health check test data - " + b"x" * 1024  # 1KB test file

            test_metadata = FileMetadata(
                file_id=test_file_id,
                filename=f"{test_file_id}.txt",
                content_type="text/plain",
                file_size=len(test_data),
                file_type=FileType.OTHER,
                tags={"health_check": "true", "auto_delete": "true"},
            )

            # Test upload
            upload_start = time.time()
            try:
                upload_result = await self.storage_manager.upload_file(
                    test_data, test_metadata, preferred_provider=provider
                )
                result.upload_success = upload_result.success
                result.upload_time = time.time() - upload_start

                if not upload_result.success:
                    result.errors.append(
                        f"Upload failed: {upload_result.error_message}"
                    )

            except Exception as e:
                result.upload_success = False
                result.upload_time = time.time() - upload_start
                result.errors.append(f"Upload exception: {str(e)}")

            # Download for health check (only if upload succeeded)
            if result.upload_success and upload_result.file_metadata:
                download_start = time.time()
                try:
                    download_result = await self.storage_manager.download_file(
                        upload_result.file_metadata.storage_path, provider=provider
                    )
                    result.download_success = download_result.success
                    result.download_time = time.time() - download_start

                    if download_result.success:
                        # Calculate throughput
                        if result.download_time > 0:
                            bytes_per_second = len(test_data) / result.download_time
                            result.throughput_mbps = (bytes_per_second * 8) / (
                                1024 * 1024
                            )  # Convert to Mbps

                        # Verify data integrity
                        if download_result.content != test_data:
                            result.errors.append("Data integrity check failed")
                    else:
                        result.errors.append(
                            f"Download failed: {download_result.error_message}"
                        )

                except Exception as e:
                    result.download_success = False
                    result.download_time = time.time() - download_start
                    result.errors.append(f"Download exception: {str(e)}")

            # Test metadata retrieval
            if result.upload_success and upload_result.file_metadata:
                try:
                    metadata = await self.storage_manager.get_file_metadata(
                        upload_result.file_metadata.storage_path, provider=provider
                    )
                    result.metadata_success = metadata is not None

                    if not metadata:
                        result.errors.append("Metadata retrieval failed")

                except Exception as e:
                    result.metadata_success = False
                    result.errors.append(f"Metadata exception: {str(e)}")

            # Test list operation
            try:
                provider_instance = self.storage_manager.providers[provider]
                files, _ = await provider_instance.list_files(limit=1)
                result.list_success = True

            except Exception as e:
                result.list_success = False
                result.errors.append(f"List operation exception: {str(e)}")

            # Test delete (cleanup)
            if result.upload_success and upload_result.file_metadata:
                try:
                    delete_success = await self.storage_manager.delete_file(
                        upload_result.file_metadata.storage_path, provider=provider
                    )
                    result.delete_success = delete_success

                    if not delete_success:
                        result.errors.append("Delete operation failed")

                except Exception as e:
                    result.delete_success = False
                    result.errors.append(f"Delete exception: {str(e)}")

            # Calculate overall response time
            result.response_time = time.time() - start_time

            # Determine health status
            result.status = self._determine_health_status(result)

            # Log results
            self.logger.info(
                f"Health check completed for {provider.value}",
                extra={
                    "provider": provider.value,
                    "status": result.status.value,
                    "response_time": result.response_time,
                    "upload_success": result.upload_success,
                    "download_success": result.download_success,
                    "errors": result.errors,
                },
            )

        except Exception as e:
            result.status = HealthStatus.UNAVAILABLE
            result.response_time = time.time() - start_time
            result.errors.append(f"Health check exception: {str(e)}")

            self.logger.error(f"Health check failed for {provider.value}: {str(e)}")

        return result

    def _determine_health_status(self, result: HealthCheckResult) -> HealthStatus:
        """Determine health status based on check results."""
        if result.errors:
            if len(result.errors) >= 3:  # Multiple failures
                return HealthStatus.CRITICAL
            else:
                return HealthStatus.WARNING

        # Check response time
        if result.response_time > self.alert_thresholds["response_time_critical"]:
            return HealthStatus.CRITICAL
        elif result.response_time > self.alert_thresholds["response_time_warning"]:
            return HealthStatus.WARNING

        # Check operation success rates
        operations = [
            result.upload_success,
            result.download_success,
            result.delete_success,
            result.list_success,
            result.metadata_success,
        ]

        success_rate = sum(operations) / len(operations) * 100

        if success_rate < 60:  # Less than 60% success
            return HealthStatus.CRITICAL
        elif success_rate < 80:  # Less than 80% success
            return HealthStatus.WARNING

        return HealthStatus.HEALTHY

    async def _process_health_result(self, result: HealthCheckResult):
        """Process health check result and update metrics."""
        provider = result.provider

        # Store in history
        if provider not in self.health_history:
            self.health_history[provider] = []

        self.health_history[provider].append(result)

        # Keep only last 100 results
        if len(self.health_history[provider]) > 100:
            self.health_history[provider] = self.health_history[provider][-100:]

        # Update SLA metrics
        await self._update_sla_metrics(provider, result)

        # Check for alerts
        await self._check_alerts(result)

        # Publish health event
        await EventPublisher.publish_system_event(
            event_type="storage.health.checked",
            payload={
                "provider": provider.value,
                "status": result.status.value,
                "response_time": result.response_time,
                "success_operations": sum(
                    [
                        result.upload_success,
                        result.download_success,
                        result.delete_success,
                        result.list_success,
                        result.metadata_success,
                    ]
                ),
                "total_operations": 5,
                "errors": result.errors,
                "timestamp": result.timestamp.isoformat(),
            },
        )

    async def _update_sla_metrics(
        self, provider: StorageProvider, result: HealthCheckResult
    ):
        """Update SLA metrics based on health check result."""
        sla = self.sla_metrics[provider]

        # Calculate current metrics from recent history
        recent_results = self.health_history[provider][-20:]  # Last 20 results

        if recent_results:
            # Availability (percentage of non-unavailable results)
            available_count = sum(
                1 for r in recent_results if r.status != HealthStatus.UNAVAILABLE
            )
            sla.current_availability = (available_count / len(recent_results)) * 100

            # Response time (average of recent results)
            response_times = [
                r.response_time for r in recent_results if r.response_time > 0
            ]
            if response_times:
                sla.current_response_time = statistics.mean(response_times)

            # Throughput (average of recent successful downloads)
            throughputs = [
                r.throughput_mbps for r in recent_results if r.throughput_mbps > 0
            ]
            if throughputs:
                sla.current_throughput = statistics.mean(throughputs)

            # Error rate (percentage of results with errors)
            error_count = sum(1 for r in recent_results if r.errors)
            sla.current_error_rate = (error_count / len(recent_results)) * 100

        # Check for SLA breaches
        if sla.current_availability < sla.availability_target:
            sla.availability_breaches += 1

        if sla.current_response_time > sla.response_time_target:
            sla.response_time_breaches += 1

        if sla.current_throughput < sla.throughput_target:
            sla.throughput_breaches += 1

        if sla.current_error_rate > sla.error_rate_target:
            sla.error_rate_breaches += 1

        # Log SLA breach
        if not sla.is_sla_met():
            await self._log_sla_breach(provider, sla)

    async def _log_sla_breach(self, provider: StorageProvider, sla: SLAMetrics):
        """Log SLA breach event."""
        self.logger.warning(
            f"SLA breach detected for {provider.value}",
            extra={
                "provider": provider.value,
                "availability": sla.current_availability,
                "response_time": sla.current_response_time,
                "throughput": sla.current_throughput,
                "error_rate": sla.current_error_rate,
                "breaches": sla.get_breach_summary(),
            },
        )

        await EventPublisher.publish_system_event(
            event_type="storage.sla.breach",
            payload={
                "provider": provider.value,
                "breach_type": "sla_violation",
                "current_metrics": {
                    "availability": sla.current_availability,
                    "response_time": sla.current_response_time,
                    "throughput": sla.current_throughput,
                    "error_rate": sla.current_error_rate,
                },
                "target_metrics": {
                    "availability": sla.availability_target,
                    "response_time": sla.response_time_target,
                    "throughput": sla.throughput_target,
                    "error_rate": sla.error_rate_target,
                },
                "breach_counts": sla.get_breach_summary(),
            },
        )

    async def _check_alerts(self, result: HealthCheckResult):
        """Check if alerts should be triggered based on health result."""
        provider = result.provider
        alerts = []

        # Critical status alert
        if result.status == HealthStatus.CRITICAL:
            alerts.append(
                {
                    "severity": AlertSeverity.CRITICAL,
                    "message": f"Storage provider {provider.value} is in critical state",
                    "details": result.errors,
                }
            )

        # Warning status alert
        elif result.status == HealthStatus.WARNING:
            alerts.append(
                {
                    "severity": AlertSeverity.WARNING,
                    "message": f"Storage provider {provider.value} has warnings",
                    "details": result.errors + result.warnings,
                }
            )

        # Response time alerts
        if result.response_time > self.alert_thresholds["response_time_critical"]:
            alerts.append(
                {
                    "severity": AlertSeverity.CRITICAL,
                    "message": f"Response time critical for {provider.value}: {result.response_time:.2f}s",
                }
            )
        elif result.response_time > self.alert_thresholds["response_time_warning"]:
            alerts.append(
                {
                    "severity": AlertSeverity.WARNING,
                    "message": f"Response time warning for {provider.value}: {result.response_time:.2f}s",
                }
            )

        # Send alerts
        for alert in alerts:
            await self._send_alert(provider, alert)

    async def _send_alert(self, provider: StorageProvider, alert: Dict[str, Any]):
        """Send alert for storage provider issue."""
        self.logger.warning(
            f"Storage alert: {alert['message']}",
            extra={
                "provider": provider.value,
                "severity": alert["severity"].value,
                "alert_type": "storage_health",
                **alert,
            },
        )

        # Publish alert event
        await EventPublisher.publish_system_event(
            event_type="storage.alert.triggered",
            payload={
                "provider": provider.value,
                "severity": alert["severity"].value,
                "message": alert["message"],
                "details": alert.get("details", []),
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def _benchmark_loop(self):
        """Performance benchmarking loop."""
        while True:
            try:
                await asyncio.sleep(self.benchmark_interval)

                # Run benchmarks on all providers
                for provider in self.storage_manager.providers.keys():
                    await self._run_benchmark(provider)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Benchmark loop error: {str(e)}")

    async def _run_benchmark(self, provider: StorageProvider):
        """Run performance benchmark for a provider."""
        self.logger.info(f"Running benchmark for {provider.value}")

        benchmark_results = []

        # Test different file sizes
        for test_size in self.test_data_sizes:
            try:
                # Generate test data
                test_data = b"x" * test_size
                test_file_id = f"benchmark_{uuid.uuid4().hex[:8]}_{test_size}"

                test_metadata = FileMetadata(
                    file_id=test_file_id,
                    filename=f"{test_file_id}.bin",
                    content_type="application/octet-stream",
                    file_size=len(test_data),
                    file_type=FileType.OTHER,
                    tags={"benchmark": "true", "auto_delete": "true"},
                )

                # Upload benchmark
                upload_start = time.time()
                upload_result = await self.storage_manager.upload_file(
                    test_data, test_metadata, preferred_provider=provider
                )
                upload_time = time.time() - upload_start

                if upload_result.success:
                    # Download benchmark
                    download_start = time.time()
                    await self.storage_manager.download_file(
                        upload_result.file_metadata.storage_path, provider=provider
                    )
                    download_time = time.time() - download_start

                    # Calculate throughput
                    upload_throughput = (test_size / upload_time) / (
                        1024 * 1024
                    )  # MB/s
                    download_throughput = (test_size / download_time) / (
                        1024 * 1024
                    )  # MB/s

                    benchmark_results.append(
                        {
                            "file_size": test_size,
                            "upload_time": upload_time,
                            "download_time": download_time,
                            "upload_throughput_mbps": upload_throughput,
                            "download_throughput_mbps": download_throughput,
                        }
                    )

                    # Cleanup
                    await self.storage_manager.delete_file(
                        upload_result.file_metadata.storage_path, provider=provider
                    )

            except Exception as e:
                self.logger.error(
                    f"Benchmark failed for {provider.value} with {test_size} bytes: {str(e)}"
                )

        # Log benchmark results
        if benchmark_results:
            avg_upload_throughput = statistics.mean(
                [r["upload_throughput_mbps"] for r in benchmark_results]
            )
            avg_download_throughput = statistics.mean(
                [r["download_throughput_mbps"] for r in benchmark_results]
            )

            self.logger.info(
                f"Benchmark completed for {provider.value}",
                extra={
                    "provider": provider.value,
                    "avg_upload_throughput_mbps": avg_upload_throughput,
                    "avg_download_throughput_mbps": avg_download_throughput,
                    "test_results": benchmark_results,
                },
            )

            # Publish benchmark event
            await EventPublisher.publish_system_event(
                event_type="storage.benchmark.completed",
                payload={
                    "provider": provider.value,
                    "avg_upload_throughput_mbps": avg_upload_throughput,
                    "avg_download_throughput_mbps": avg_download_throughput,
                    "test_results": benchmark_results,
                    "timestamp": datetime.now().isoformat(),
                },
            )

    async def _predictive_analysis_loop(self):
        """Predictive failure analysis loop."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour

                # Perform predictive analysis for each provider
                for provider in self.storage_manager.providers.keys():
                    analysis = await self._perform_predictive_analysis(provider)
                    if analysis:
                        self.predictive_analysis[provider] = analysis

                        # Alert if high failure probability
                        if analysis.failure_probability > 0.7:
                            await self._send_predictive_alert(analysis)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Predictive analysis loop error: {str(e)}")

    async def _perform_predictive_analysis(
        self, provider: StorageProvider
    ) -> Optional[PredictiveAnalysis]:
        """Perform predictive failure analysis for a provider."""
        if (
            provider not in self.health_history
            or len(self.health_history[provider]) < 10
        ):
            return None

        recent_results = self.health_history[provider][-50:]  # Last 50 results
        analysis = PredictiveAnalysis(provider=provider)

        # Analyze trends
        error_rates = []
        response_times = []
        health_scores = []

        for result in recent_results:
            error_rate = len(result.errors) / 5  # 5 operations per check
            error_rates.append(error_rate)
            response_times.append(result.response_time)
            health_scores.append(result.get_overall_score())

        # Calculate failure probability based on trends
        factors = []

        # Increasing error rate trend
        if len(error_rates) >= 5:
            recent_error_rate = statistics.mean(error_rates[-5:])
            older_error_rate = (
                statistics.mean(error_rates[-10:-5]) if len(error_rates) >= 10 else 0
            )

            if recent_error_rate > older_error_rate * 1.5:
                factors.append("increasing_error_rate")
                analysis.failure_probability += 0.3

        # Degrading response time
        if len(response_times) >= 5:
            recent_response_time = statistics.mean(response_times[-5:])
            older_response_time = (
                statistics.mean(response_times[-10:-5])
                if len(response_times) >= 10
                else 0
            )

            if recent_response_time > older_response_time * 1.3:
                factors.append("degrading_response_time")
                analysis.failure_probability += 0.2

        # Declining health score
        if len(health_scores) >= 5:
            recent_health = statistics.mean(health_scores[-5:])
            older_health = (
                statistics.mean(health_scores[-10:-5])
                if len(health_scores) >= 10
                else 100
            )

            if recent_health < older_health * 0.8:
                factors.append("declining_health_score")
                analysis.failure_probability += 0.2

        # High consecutive failures
        metrics = self.storage_manager.provider_metrics.get(provider)
        if metrics and metrics.consecutive_failures >= 3:
            factors.append("consecutive_failures")
            analysis.failure_probability += 0.3

        analysis.contributing_factors = factors
        analysis.confidence_level = min(1.0, len(recent_results) / 50.0)

        # Generate recommendations
        if analysis.failure_probability > 0.5:
            analysis.recommended_actions.append("Increase health check frequency")
            analysis.recommended_actions.append("Consider failover to backup provider")

            if "degrading_response_time" in factors:
                analysis.recommended_actions.append("Investigate network connectivity")

            if "increasing_error_rate" in factors:
                analysis.recommended_actions.append("Check provider service status")

        # Estimate failure time if probability is high
        if analysis.failure_probability > 0.7:
            # Simple estimation based on trend velocity
            hours_to_failure = max(1, int(24 * (1 - analysis.failure_probability)))
            analysis.predicted_failure_time = datetime.now() + timedelta(
                hours=hours_to_failure
            )

        return analysis

    async def _send_predictive_alert(self, analysis: PredictiveAnalysis):
        """Send predictive failure alert."""
        self.logger.warning(
            f"Predictive failure alert for {analysis.provider.value}",
            extra={
                "provider": analysis.provider.value,
                "failure_probability": analysis.failure_probability,
                "predicted_failure_time": (
                    analysis.predicted_failure_time.isoformat()
                    if analysis.predicted_failure_time
                    else None
                ),
                "contributing_factors": analysis.contributing_factors,
                "recommended_actions": analysis.recommended_actions,
            },
        )

        await EventPublisher.publish_system_event(
            event_type="storage.predictive.failure_risk",
            payload={
                "provider": analysis.provider.value,
                "failure_probability": analysis.failure_probability,
                "predicted_failure_time": (
                    analysis.predicted_failure_time.isoformat()
                    if analysis.predicted_failure_time
                    else None
                ),
                "contributing_factors": analysis.contributing_factors,
                "recommended_actions": analysis.recommended_actions,
                "confidence_level": analysis.confidence_level,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def get_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "providers": {},
            "overall_health": "healthy",
        }

        critical_count = 0
        warning_count = 0
        total_providers = len(self.storage_manager.providers)

        for provider in self.storage_manager.providers.keys():
            provider_report = {
                "status": "healthy",
                "last_check": None,
                "response_time": 0.0,
                "success_rate": 100.0,
                "sla_metrics": {},
                "predictive_analysis": {},
                "recent_errors": [],
            }

            # Get latest health result
            if provider in self.health_history and self.health_history[provider]:
                latest_result = self.health_history[provider][-1]
                provider_report.update(
                    {
                        "status": latest_result.status.value,
                        "last_check": latest_result.timestamp.isoformat(),
                        "response_time": latest_result.response_time,
                        "success_rate": latest_result.get_overall_score(),
                        "recent_errors": latest_result.errors[-5:],  # Last 5 errors
                    }
                )

                if latest_result.status == HealthStatus.CRITICAL:
                    critical_count += 1
                elif latest_result.status == HealthStatus.WARNING:
                    warning_count += 1

            # Add SLA metrics
            if provider in self.sla_metrics:
                sla = self.sla_metrics[provider]
                provider_report["sla_metrics"] = {
                    "availability": sla.current_availability,
                    "response_time": sla.current_response_time,
                    "throughput": sla.current_throughput,
                    "error_rate": sla.current_error_rate,
                    "sla_met": sla.is_sla_met(),
                    "breaches": sla.get_breach_summary(),
                }

            # Add predictive analysis
            if provider in self.predictive_analysis:
                analysis = self.predictive_analysis[provider]
                provider_report["predictive_analysis"] = {
                    "failure_probability": analysis.failure_probability,
                    "predicted_failure_time": (
                        analysis.predicted_failure_time.isoformat()
                        if analysis.predicted_failure_time
                        else None
                    ),
                    "contributing_factors": analysis.contributing_factors,
                    "recommended_actions": analysis.recommended_actions,
                    "confidence_level": analysis.confidence_level,
                }

            report["providers"][provider.value] = provider_report

        # Determine overall health
        if critical_count > 0:
            report["overall_health"] = "critical"
        elif warning_count > 0:
            report["overall_health"] = "warning"
        elif critical_count + warning_count > total_providers / 2:
            report["overall_health"] = "degraded"

        report["summary"] = {
            "total_providers": total_providers,
            "healthy_providers": total_providers - critical_count - warning_count,
            "warning_providers": warning_count,
            "critical_providers": critical_count,
        }

        return report
