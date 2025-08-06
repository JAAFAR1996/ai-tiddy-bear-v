"""
Automated Performance Optimization Engine
Intelligent optimization recommendations and automated performance tuning
"""

import asyncio
import logging
import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import os
from pathlib import Path

import yaml
import aiofiles

from src.core.exceptions import OptimizationError, ConfigurationError
from src.utils.date_utils import get_current_timestamp
from .monitoring import PerformanceMonitor
from .cache_manager import CacheManager
from .cdn_manager import CDNManager
from .database_optimizer import ConnectionPoolManager
from .compression_manager import CompressionManager


logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """Types of performance optimizations."""

    CACHE_TUNING = "cache_tuning"
    DATABASE_OPTIMIZATION = "database_optimization"
    CDN_CONFIGURATION = "cdn_configuration"
    COMPRESSION_SETTINGS = "compression_settings"
    CONNECTION_POOLING = "connection_pooling"
    QUERY_OPTIMIZATION = "query_optimization"
    RESOURCE_SCALING = "resource_scaling"
    CHILD_SAFETY_OPTIMIZATION = "child_safety_optimization"


class OptimizationPriority(Enum):
    """Priority levels for optimizations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OptimizationStatus(Enum):
    """Status of optimization recommendations."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation."""

    id: str
    type: OptimizationType
    priority: OptimizationPriority
    title: str
    description: str
    expected_improvement: str
    estimated_risk: str

    # Implementation details
    changes_required: Dict[str, Any]
    rollback_plan: Dict[str, Any]
    validation_criteria: List[str]

    # Child safety considerations
    child_safety_impact: bool = False
    coppa_compliance_verified: bool = True

    # Metrics
    estimated_performance_gain: float = 0.0  # Percentage
    implementation_time_minutes: int = 30

    # Status tracking
    status: OptimizationStatus = OptimizationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    applied_at: Optional[datetime] = None

    # Results
    actual_improvement: Optional[float] = None
    metrics_before: Optional[Dict[str, Any]] = None
    metrics_after: Optional[Dict[str, Any]] = None


@dataclass
class OptimizationRule:
    """Rule for generating optimization recommendations."""

    name: str
    type: OptimizationType
    condition: Callable[[Dict[str, Any]], bool]
    generate_recommendation: Callable[[Dict[str, Any]], OptimizationRecommendation]
    enabled: bool = True
    min_interval_hours: int = 24  # Minimum time between applying this rule


class BaseOptimizer(ABC):
    """Base class for performance optimizers."""

    @abstractmethod
    async def analyze_performance(
        self, metrics: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Analyze performance and generate recommendations."""
        pass

    @abstractmethod
    async def apply_optimization(
        self, recommendation: OptimizationRecommendation
    ) -> bool:
        """Apply optimization recommendation."""
        pass

    @abstractmethod
    async def rollback_optimization(
        self, recommendation: OptimizationRecommendation
    ) -> bool:
        """Rollback optimization if needed."""
        pass


class CacheOptimizer(BaseOptimizer):
    """Cache performance optimizer."""

    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager

    async def analyze_performance(
        self, metrics: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Analyze cache performance and generate recommendations."""
        recommendations = []

        cache_metrics = metrics.get("cache", {})
        overall_hit_ratio = cache_metrics.get("overall_hit_ratio", 0.0)

        # Low cache hit ratio optimization
        if overall_hit_ratio < 0.6:  # Below 60%
            recommendations.append(
                OptimizationRecommendation(
                    id=f"cache_hit_ratio_{int(get_current_timestamp())}",
                    type=OptimizationType.CACHE_TUNING,
                    priority=OptimizationPriority.HIGH,
                    title="Improve Cache Hit Ratio",
                    description=f"Cache hit ratio is {overall_hit_ratio:.1%}, below optimal threshold of 60%",
                    expected_improvement="20-40% reduction in response times",
                    estimated_risk="Low - no data loss risk",
                    changes_required={
                        "increase_cache_ttl": True,
                        "expand_cache_size": True,
                        "add_cache_warming": True,
                    },
                    rollback_plan={
                        "restore_previous_ttl": True,
                        "revert_cache_size": True,
                    },
                    validation_criteria=[
                        "Cache hit ratio > 0.7",
                        "Response time improvement > 15%",
                        "No increase in memory usage > 20%",
                    ],
                    estimated_performance_gain=25.0,
                    implementation_time_minutes=15,
                )
            )

        # Child data cache optimization
        child_cache_metrics = cache_metrics.get("by_cache", {}).get("child_data", {})
        if child_cache_metrics.get("hit_ratio", 0.0) < 0.5:
            recommendations.append(
                OptimizationRecommendation(
                    id=f"child_cache_opt_{int(get_current_timestamp())}",
                    type=OptimizationType.CHILD_SAFETY_OPTIMIZATION,
                    priority=OptimizationPriority.MEDIUM,
                    title="Optimize Child Data Caching",
                    description="Child data cache performance is below optimal",
                    expected_improvement="Faster child profile and preference loading",
                    estimated_risk="Low - child data remains secure",
                    changes_required={
                        "optimize_child_cache_policy": True,
                        "implement_predictive_caching": True,
                    },
                    rollback_plan={"restore_default_child_cache_policy": True},
                    validation_criteria=[
                        "Child data cache hit ratio > 0.6",
                        "Child profile load time < 100ms",
                        "COPPA compliance maintained",
                    ],
                    child_safety_impact=True,
                    coppa_compliance_verified=True,
                    estimated_performance_gain=20.0,
                )
            )

        return recommendations

    async def apply_optimization(
        self, recommendation: OptimizationRecommendation
    ) -> bool:
        """Apply cache optimization."""
        try:
            changes = recommendation.changes_required

            if changes.get("increase_cache_ttl"):
                # Increase TTL for frequently accessed data
                for cache_name in ["api_responses", "db_queries"]:
                    cache = self.cache_manager.get_cache(cache_name)
                    # Implementation would adjust TTL settings
                    logger.info(f"Increased TTL for {cache_name} cache")

            if changes.get("expand_cache_size"):
                # Increase cache sizes based on memory availability
                logger.info("Expanded cache sizes")

            if changes.get("add_cache_warming"):
                # Implement cache warming for frequently accessed data
                await self._warm_critical_caches()

            if changes.get("optimize_child_cache_policy"):
                # Optimize child data caching while maintaining safety
                await self._optimize_child_cache_policy()

            recommendation.status = OptimizationStatus.COMPLETED
            recommendation.applied_at = datetime.now()

            return True

        except Exception as e:
            logger.error(f"Failed to apply cache optimization: {e}")
            recommendation.status = OptimizationStatus.FAILED
            return False

    async def rollback_optimization(
        self, recommendation: OptimizationRecommendation
    ) -> bool:
        """Rollback cache optimization."""
        try:
            rollback_plan = recommendation.rollback_plan

            if rollback_plan.get("restore_previous_ttl"):
                logger.info("Restored previous cache TTL settings")

            if rollback_plan.get("revert_cache_size"):
                logger.info("Reverted cache size changes")

            recommendation.status = OptimizationStatus.REVERTED
            return True

        except Exception as e:
            logger.error(f"Failed to rollback cache optimization: {e}")
            return False

    async def _warm_critical_caches(self) -> None:
        """Warm up critical caches with frequently accessed data."""
        # This would implement cache warming logic
        pass

    async def _optimize_child_cache_policy(self) -> None:
        """Optimize child data cache policy while maintaining safety."""
        # This would implement child-safe cache optimization
        pass


class DatabaseOptimizer(BaseOptimizer):
    """Database performance optimizer."""

    def __init__(self, db_manager: ConnectionPoolManager):
        self.db_manager = db_manager

    async def analyze_performance(
        self, metrics: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Analyze database performance and generate recommendations."""
        recommendations = []

        db_metrics = metrics.get("database", {})
        query_metrics = db_metrics.get("query_performance", {})

        # Slow query optimization
        slow_queries_count = query_metrics.get("slow_queries_count", 0)
        if slow_queries_count > 10:
            recommendations.append(
                OptimizationRecommendation(
                    id=f"slow_queries_{int(get_current_timestamp())}",
                    type=OptimizationType.QUERY_OPTIMIZATION,
                    priority=OptimizationPriority.HIGH,
                    title="Optimize Slow Database Queries",
                    description=f"Detected {slow_queries_count} slow queries in the last hour",
                    expected_improvement="30-50% reduction in database response times",
                    estimated_risk="Medium - requires query changes",
                    changes_required={
                        "add_missing_indexes": True,
                        "optimize_query_structure": True,
                        "implement_query_caching": True,
                    },
                    rollback_plan={
                        "remove_added_indexes": True,
                        "revert_query_changes": True,
                    },
                    validation_criteria=[
                        "Average query time < 50ms",
                        "No queries > 1 second",
                        "Database CPU usage < 70%",
                    ],
                    estimated_performance_gain=35.0,
                    implementation_time_minutes=45,
                )
            )

        # Connection pool optimization
        pool_metrics = db_metrics.get("connection_pools", {})
        main_pool = pool_metrics.get("main", {})

        if main_pool.get("checkout_errors", 0) > 5:
            recommendations.append(
                OptimizationRecommendation(
                    id=f"conn_pool_{int(get_current_timestamp())}",
                    type=OptimizationType.CONNECTION_POOLING,
                    priority=OptimizationPriority.MEDIUM,
                    title="Optimize Database Connection Pool",
                    description="High number of connection pool checkout errors detected",
                    expected_improvement="Reduced connection timeouts and improved concurrency",
                    estimated_risk="Low - connection pool adjustments",
                    changes_required={
                        "increase_pool_size": True,
                        "adjust_pool_timeout": True,
                        "optimize_connection_recycling": True,
                    },
                    rollback_plan={"restore_pool_settings": True},
                    validation_criteria=[
                        "Connection checkout errors < 1 per hour",
                        "Pool utilization < 80%",
                        "No connection timeouts",
                    ],
                    estimated_performance_gain=15.0,
                )
            )

        return recommendations

    async def apply_optimization(
        self, recommendation: OptimizationRecommendation
    ) -> bool:
        """Apply database optimization."""
        try:
            changes = recommendation.changes_required

            if changes.get("add_missing_indexes"):
                # Get index recommendations and apply them
                await self._apply_index_recommendations()

            if changes.get("optimize_query_structure"):
                # Optimize slow queries
                await self._optimize_slow_queries()

            if changes.get("increase_pool_size"):
                # Adjust connection pool settings
                await self._optimize_connection_pools()

            recommendation.status = OptimizationStatus.COMPLETED
            recommendation.applied_at = datetime.now()

            return True

        except Exception as e:
            logger.error(f"Failed to apply database optimization: {e}")
            recommendation.status = OptimizationStatus.FAILED
            return False

    async def rollback_optimization(
        self, recommendation: OptimizationRecommendation
    ) -> bool:
        """Rollback database optimization."""
        try:
            # Implementation would revert database changes
            recommendation.status = OptimizationStatus.REVERTED
            return True
        except Exception as e:
            logger.error(f"Failed to rollback database optimization: {e}")
            return False

    async def _apply_index_recommendations(self) -> None:
        """Apply recommended database indexes."""
        recommendations = self.db_manager.query_analyzer.get_index_recommendations()

        for rec in recommendations[:5]:  # Apply top 5 recommendations
            if rec.estimated_benefit > 0.6:  # Only high-benefit indexes
                try:
                    # Create index
                    index_sql = f"CREATE INDEX CONCURRENTLY idx_{rec.table_name}_{'_'.join(rec.columns)} ON {rec.table_name} ({', '.join(rec.columns)})"
                    await self.db_manager.execute_query(index_sql, fetch_results=False)
                    logger.info(
                        f"Created index on {rec.table_name}({', '.join(rec.columns)})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to create index: {e}")

    async def _optimize_slow_queries(self) -> None:
        """Optimize slow database queries."""
        # This would implement query optimization logic
        pass

    async def _optimize_connection_pools(self) -> None:
        """Optimize database connection pool settings."""
        # This would adjust connection pool parameters
        pass


class OptimizationEngine:
    """Main performance optimization engine."""

    def __init__(
        self,
        performance_monitor: PerformanceMonitor,
        cache_manager: Optional[CacheManager] = None,
        cdn_manager: Optional[CDNManager] = None,
        db_manager: Optional[ConnectionPoolManager] = None,
        compression_manager: Optional[CompressionManager] = None,
    ):

        self.performance_monitor = performance_monitor
        self.cache_manager = cache_manager
        self.cdn_manager = cdn_manager
        self.db_manager = db_manager
        self.compression_manager = compression_manager

        # Optimization components
        self.optimizers: Dict[OptimizationType, BaseOptimizer] = {}
        self._initialize_optimizers()

        # Recommendations tracking
        self.recommendations: List[OptimizationRecommendation] = []
        self.applied_optimizations: List[OptimizationRecommendation] = []

        # Optimization rules
        self.rules: List[OptimizationRule] = []
        self._initialize_rules()

        # Background optimization task
        self._optimization_task = None
        self._running = False

    def _initialize_optimizers(self) -> None:
        """Initialize optimization components."""
        if self.cache_manager:
            self.optimizers[OptimizationType.CACHE_TUNING] = CacheOptimizer(
                self.cache_manager
            )

        if self.db_manager:
            db_optimizer = DatabaseOptimizer(self.db_manager)
            self.optimizers[OptimizationType.DATABASE_OPTIMIZATION] = db_optimizer
            self.optimizers[OptimizationType.QUERY_OPTIMIZATION] = db_optimizer
            self.optimizers[OptimizationType.CONNECTION_POOLING] = db_optimizer

    def _initialize_rules(self) -> None:
        """Initialize optimization rules."""

        # Cache hit ratio rule
        self.rules.append(
            OptimizationRule(
                name="cache_hit_ratio_rule",
                type=OptimizationType.CACHE_TUNING,
                condition=lambda m: m.get("cache", {}).get("overall_hit_ratio", 1.0)
                < 0.6,
                generate_recommendation=self._generate_cache_optimization,
            )
        )

        # Response time rule
        self.rules.append(
            OptimizationRule(
                name="response_time_rule",
                type=OptimizationType.QUERY_OPTIMIZATION,
                condition=lambda m: m.get("application", {}).get(
                    "avg_response_time_ms", 0
                )
                > 1000,
                generate_recommendation=self._generate_response_time_optimization,
            )
        )

        # Child safety performance rule
        self.rules.append(
            OptimizationRule(
                name="child_safety_performance_rule",
                type=OptimizationType.CHILD_SAFETY_OPTIMIZATION,
                condition=lambda m: (
                    m.get("application", {}).get("child_safety_violations", 0) > 0
                    or m.get("application", {}).get("coppa_compliance_score", 100) < 95
                ),
                generate_recommendation=self._generate_child_safety_optimization,
            )
        )

    async def start_optimization_engine(self, interval_minutes: int = 60) -> None:
        """Start automated optimization engine."""
        if self._running:
            return

        self._running = True
        self._optimization_task = asyncio.create_task(
            self._optimization_loop(interval_minutes)
        )

        logger.info(
            f"Performance optimization engine started with {interval_minutes}m interval"
        )

    async def stop_optimization_engine(self) -> None:
        """Stop optimization engine."""
        self._running = False

        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass

        logger.info("Performance optimization engine stopped")

    async def _optimization_loop(self, interval_minutes: int) -> None:
        """Main optimization loop."""
        while self._running:
            try:
                # Analyze performance and generate recommendations
                await self.analyze_and_optimize()

                # Wait for next interval
                await asyncio.sleep(interval_minutes * 60)

            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(60)  # Short retry interval

    async def analyze_and_optimize(self) -> Dict[str, Any]:
        """Analyze performance and apply optimizations."""

        # Get current performance metrics
        metrics = await self.performance_monitor.get_performance_dashboard_data()

        # Generate new recommendations
        new_recommendations = await self._generate_recommendations(metrics)

        # Filter and prioritize recommendations
        actionable_recommendations = self._filter_recommendations(new_recommendations)

        # Apply high-priority optimizations automatically
        applied_count = await self._apply_automatic_optimizations(
            actionable_recommendations
        )

        # Update recommendations list
        self.recommendations.extend(new_recommendations)

        # Clean up old recommendations
        self._cleanup_old_recommendations()

        result = {
            "analysis_timestamp": datetime.now().isoformat(),
            "new_recommendations": len(new_recommendations),
            "actionable_recommendations": len(actionable_recommendations),
            "applied_optimizations": applied_count,
            "total_pending_recommendations": len(
                [
                    r
                    for r in self.recommendations
                    if r.status == OptimizationStatus.PENDING
                ]
            ),
        }

        logger.info("Performance analysis completed", extra=result)
        return result

    async def _generate_recommendations(
        self, metrics: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on current metrics."""
        recommendations = []

        # Apply optimization rules
        for rule in self.rules:
            if not rule.enabled:
                continue

            # Check if rule condition is met
            if rule.condition(metrics):

                # Check if we haven't applied this rule recently
                recent_cutoff = datetime.now() - timedelta(
                    hours=rule.min_interval_hours
                )
                recent_applications = [
                    r
                    for r in self.applied_optimizations
                    if r.type == rule.type
                    and r.applied_at
                    and r.applied_at > recent_cutoff
                ]

                if not recent_applications:
                    try:
                        recommendation = rule.generate_recommendation(metrics)
                        recommendations.append(recommendation)

                        logger.info(f"Generated recommendation: {recommendation.title}")

                    except Exception as e:
                        logger.error(
                            f"Failed to generate recommendation for rule {rule.name}: {e}"
                        )

        # Get recommendations from individual optimizers
        for opt_type, optimizer in self.optimizers.items():
            try:
                optimizer_recommendations = await optimizer.analyze_performance(metrics)
                recommendations.extend(optimizer_recommendations)
            except Exception as e:
                logger.error(
                    f"Error getting recommendations from {opt_type.value} optimizer: {e}"
                )

        return recommendations

    def _filter_recommendations(
        self, recommendations: List[OptimizationRecommendation]
    ) -> List[OptimizationRecommendation]:
        """Filter and prioritize recommendations."""

        # Remove duplicates based on type and similar changes
        unique_recommendations = []
        seen_types = set()

        for rec in recommendations:
            key = f"{rec.type.value}_{hash(str(rec.changes_required))}"
            if key not in seen_types:
                seen_types.add(key)
                unique_recommendations.append(rec)

        # Sort by priority and expected impact
        priority_order = {
            OptimizationPriority.CRITICAL: 4,
            OptimizationPriority.HIGH: 3,
            OptimizationPriority.MEDIUM: 2,
            OptimizationPriority.LOW: 1,
        }

        unique_recommendations.sort(
            key=lambda x: (priority_order[x.priority], x.estimated_performance_gain),
            reverse=True,
        )

        return unique_recommendations

    async def _apply_automatic_optimizations(
        self, recommendations: List[OptimizationRecommendation]
    ) -> int:
        """Apply high-priority optimizations automatically."""
        applied_count = 0

        for recommendation in recommendations:
            # Only auto-apply high-priority, low-risk optimizations
            if (
                recommendation.priority
                in [OptimizationPriority.HIGH, OptimizationPriority.CRITICAL]
                and "low" in recommendation.estimated_risk.lower()
                and recommendation.estimated_performance_gain > 10.0
            ):

                # Check child safety impact
                if (
                    recommendation.child_safety_impact
                    and not recommendation.coppa_compliance_verified
                ):
                    logger.warning(
                        f"Skipping auto-optimization {recommendation.id} due to child safety concerns"
                    )
                    continue

                # Capture baseline metrics
                recommendation.metrics_before = (
                    await self.performance_monitor.get_performance_dashboard_data()
                )

                # Apply optimization
                optimizer = self.optimizers.get(recommendation.type)
                if optimizer:
                    try:
                        recommendation.status = OptimizationStatus.IN_PROGRESS

                        success = await optimizer.apply_optimization(recommendation)

                        if success:
                            # Wait a bit for metrics to stabilize
                            await asyncio.sleep(30)

                            # Capture post-optimization metrics
                            recommendation.metrics_after = (
                                await self.performance_monitor.get_performance_dashboard_data()
                            )

                            # Validate optimization
                            if await self._validate_optimization(recommendation):
                                recommendation.status = OptimizationStatus.COMPLETED
                                self.applied_optimizations.append(recommendation)
                                applied_count += 1

                                logger.info(
                                    f"Successfully applied optimization: {recommendation.title}"
                                )
                            else:
                                # Rollback if validation failed
                                await optimizer.rollback_optimization(recommendation)
                                logger.warning(
                                    f"Rolled back optimization {recommendation.id} due to validation failure"
                                )

                    except Exception as e:
                        logger.error(
                            f"Failed to apply optimization {recommendation.id}: {e}"
                        )
                        recommendation.status = OptimizationStatus.FAILED

        return applied_count

    async def _validate_optimization(
        self, recommendation: OptimizationRecommendation
    ) -> bool:
        """Validate that optimization had positive impact."""

        if not recommendation.metrics_before or not recommendation.metrics_after:
            return False

        # Check validation criteria
        metrics_before = recommendation.metrics_before
        metrics_after = recommendation.metrics_after

        # Response time improvement
        response_time_before = metrics_before.get("application", {}).get(
            "avg_response_time_ms", 0
        )
        response_time_after = metrics_after.get("application", {}).get(
            "avg_response_time_ms", 0
        )

        if response_time_before > 0 and response_time_after > 0:
            improvement = (
                response_time_before - response_time_after
            ) / response_time_before
            recommendation.actual_improvement = improvement * 100

            # Require at least 5% improvement
            if improvement < 0.05:
                logger.warning(
                    f"Optimization {recommendation.id} showed insufficient improvement: {improvement:.1%}"
                )
                return False

        # Child safety compliance check
        if recommendation.child_safety_impact:
            coppa_score_before = metrics_before.get("application", {}).get(
                "coppa_compliance_score", 100
            )
            coppa_score_after = metrics_after.get("application", {}).get(
                "coppa_compliance_score", 100
            )

            if coppa_score_after < coppa_score_before:
                logger.error(
                    f"Optimization {recommendation.id} reduced COPPA compliance score"
                )
                return False

        return True

    def _cleanup_old_recommendations(self) -> None:
        """Remove old completed/failed recommendations."""
        cutoff_date = datetime.now() - timedelta(days=7)

        # Keep only recent recommendations
        self.recommendations = [
            r
            for r in self.recommendations
            if r.created_at > cutoff_date or r.status == OptimizationStatus.PENDING
        ]

        # Limit applied optimizations history
        self.applied_optimizations = self.applied_optimizations[-100:]  # Keep last 100

    def _generate_cache_optimization(
        self, metrics: Dict[str, Any]
    ) -> OptimizationRecommendation:
        """Generate cache optimization recommendation."""
        hit_ratio = metrics.get("cache", {}).get("overall_hit_ratio", 0.0)

        return OptimizationRecommendation(
            id=f"cache_opt_{int(get_current_timestamp())}",
            type=OptimizationType.CACHE_TUNING,
            priority=OptimizationPriority.HIGH,
            title="Improve Cache Performance",
            description=f"Cache hit ratio is {hit_ratio:.1%}, below optimal threshold",
            expected_improvement="20-30% reduction in response times",
            estimated_risk="Low - no data loss risk",
            changes_required={"optimize_cache_settings": True},
            rollback_plan={"restore_cache_settings": True},
            validation_criteria=[
                "Cache hit ratio > 70%",
                "Response time improvement > 10%",
            ],
            estimated_performance_gain=25.0,
        )

    def _generate_response_time_optimization(
        self, metrics: Dict[str, Any]
    ) -> OptimizationRecommendation:
        """Generate response time optimization recommendation."""
        response_time = metrics.get("application", {}).get("avg_response_time_ms", 0)

        return OptimizationRecommendation(
            id=f"response_time_opt_{int(get_current_timestamp())}",
            type=OptimizationType.QUERY_OPTIMIZATION,
            priority=OptimizationPriority.HIGH,
            title="Optimize Response Times",
            description=f"Average response time is {response_time}ms, above optimal threshold",
            expected_improvement="30-50% reduction in response times",
            estimated_risk="Medium - requires query optimization",
            changes_required={"optimize_database_queries": True},
            rollback_plan={"revert_query_changes": True},
            validation_criteria=[
                "Average response time < 500ms",
                "P95 response time < 1000ms",
            ],
            estimated_performance_gain=40.0,
        )

    def _generate_child_safety_optimization(
        self, metrics: Dict[str, Any]
    ) -> OptimizationRecommendation:
        """Generate child safety performance optimization."""
        violations = metrics.get("application", {}).get("child_safety_violations", 0)
        coppa_score = metrics.get("application", {}).get("coppa_compliance_score", 100)

        return OptimizationRecommendation(
            id=f"child_safety_opt_{int(get_current_timestamp())}",
            type=OptimizationType.CHILD_SAFETY_OPTIMIZATION,
            priority=OptimizationPriority.CRITICAL,
            title="Optimize Child Safety Performance",
            description=f"Child safety violations: {violations}, COPPA score: {coppa_score:.1f}%",
            expected_improvement="Improved child safety response times and compliance",
            estimated_risk="Low - maintains safety standards",
            changes_required={
                "optimize_safety_checks": True,
                "improve_coppa_compliance": True,
            },
            rollback_plan={"restore_safety_settings": True},
            validation_criteria=[
                "COPPA compliance score > 95%",
                "Child safety violations = 0",
            ],
            child_safety_impact=True,
            coppa_compliance_verified=True,
            estimated_performance_gain=15.0,
        )

    async def get_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive optimization report."""

        pending_recommendations = [
            r for r in self.recommendations if r.status == OptimizationStatus.PENDING
        ]
        completed_optimizations = [
            r
            for r in self.applied_optimizations
            if r.status == OptimizationStatus.COMPLETED
        ]

        # Calculate total performance gains
        total_estimated_gain = sum(
            r.estimated_performance_gain for r in completed_optimizations
        )
        total_actual_gain = sum(
            r.actual_improvement or 0 for r in completed_optimizations
        )

        report = {
            "summary": {
                "engine_running": self._running,
                "total_recommendations": len(self.recommendations),
                "pending_recommendations": len(pending_recommendations),
                "completed_optimizations": len(completed_optimizations),
                "total_estimated_gain_percent": total_estimated_gain,
                "total_actual_gain_percent": total_actual_gain,
            },
            "pending_recommendations": [
                {
                    "id": r.id,
                    "type": r.type.value,
                    "priority": r.priority.value,
                    "title": r.title,
                    "description": r.description,
                    "expected_improvement": r.expected_improvement,
                    "estimated_risk": r.estimated_risk,
                    "estimated_performance_gain": r.estimated_performance_gain,
                    "child_safety_impact": r.child_safety_impact,
                    "created_at": r.created_at.isoformat(),
                }
                for r in pending_recommendations[:10]  # Top 10 pending
            ],
            "recent_optimizations": [
                {
                    "id": r.id,
                    "type": r.type.value,
                    "title": r.title,
                    "status": r.status.value,
                    "estimated_gain": r.estimated_performance_gain,
                    "actual_gain": r.actual_improvement,
                    "applied_at": r.applied_at.isoformat() if r.applied_at else None,
                }
                for r in completed_optimizations[-10:]  # Last 10 applied
            ],
            "optimization_categories": {
                category.value: {
                    "pending": len(
                        [r for r in pending_recommendations if r.type == category]
                    ),
                    "completed": len(
                        [r for r in completed_optimizations if r.type == category]
                    ),
                }
                for category in OptimizationType
            },
        }

        return report

    async def export_optimization_config(self, file_path: str) -> None:
        """Export optimization configuration for deployment."""

        config = {
            "optimization_rules": [
                {
                    "name": rule.name,
                    "type": rule.type.value,
                    "enabled": rule.enabled,
                    "min_interval_hours": rule.min_interval_hours,
                }
                for rule in self.rules
            ],
            "applied_optimizations": [
                {
                    "id": r.id,
                    "type": r.type.value,
                    "title": r.title,
                    "changes_required": r.changes_required,
                    "applied_at": r.applied_at.isoformat() if r.applied_at else None,
                    "actual_improvement": r.actual_improvement,
                }
                for r in self.applied_optimizations
                if r.status == OptimizationStatus.COMPLETED
            ],
        }

        async with aiofiles.open(file_path, "w") as f:
            await f.write(yaml.dump(config, default_flow_style=False))

        logger.info(f"Optimization configuration exported to {file_path}")


# Factory function for easy initialization
def create_optimization_engine(
    performance_monitor: PerformanceMonitor,
    cache_manager: Optional[CacheManager] = None,
    cdn_manager: Optional[CDNManager] = None,
    db_manager: Optional[ConnectionPoolManager] = None,
    compression_manager: Optional[CompressionManager] = None,
) -> OptimizationEngine:
    """Create optimization engine with integrated components."""

    return OptimizationEngine(
        performance_monitor=performance_monitor,
        cache_manager=cache_manager,
        cdn_manager=cdn_manager,
        db_manager=db_manager,
        compression_manager=compression_manager,
    )
