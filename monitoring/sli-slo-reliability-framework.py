"""
SLI/SLO Reliability Framework - AI Teddy Bear Platform
====================================================
Production-grade Service Level Indicators (SLI) and Service Level Objectives (SLO)
framework with error budget tracking, burn rate alerting, and child safety prioritization.

Features:
- Child safety-focused SLI/SLO definitions
- Multi-window error budget tracking
- Burn rate alerting with intelligent escalation
- Business impact-based SLO prioritization
- Automated SLO reporting and compliance tracking
- Integration with monitoring and alerting systems

Author: Senior Engineering Team
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import json
import statistics
from collections import defaultdict, deque
import math

logger = logging.getLogger(__name__)


class SLIType(Enum):
    """Types of Service Level Indicators."""
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    CORRECTNESS = "correctness"
    FRESHNESS = "freshness"
    CHILD_SAFETY = "child_safety"


class SLOStatus(Enum):
    """SLO compliance status."""
    HEALTHY = "healthy"          # Within SLO target
    WARNING = "warning"          # Approaching SLO violation
    CRITICAL = "critical"        # SLO violation, immediate action required
    BREACH = "breach"           # SLO breached, error budget exhausted


class ErrorBudgetBurnRate(Enum):
    """Error budget burn rate levels."""
    SLOW = "slow"               # Normal consumption
    MODERATE = "moderate"       # Elevated consumption
    FAST = "fast"              # High consumption, attention needed
    CRITICAL = "critical"       # Extreme consumption, immediate action required


@dataclass
class SLIMetric:
    """Individual SLI measurement."""
    value: float
    timestamp: datetime
    good_events: int = 0
    total_events: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate for ratio-based SLIs."""
        if self.total_events == 0:
            return 1.0
        return self.good_events / self.total_events


@dataclass
class SLOTarget:
    """SLO target configuration."""
    name: str
    sli_type: SLIType
    target_value: float
    time_window_hours: int = 24
    
    # Child safety specific
    is_child_safety_critical: bool = False
    business_impact: str = "medium"
    priority: int = 5  # 1 = highest, 10 = lowest
    
    # Error budget configuration
    error_budget_percent: float = field(init=False)
    
    def __post_init__(self):
        """Calculate error budget based on target."""
        # Error budget = (1 - SLO target) * 100
        self.error_budget_percent = (1 - self.target_value) * 100


@dataclass
class ErrorBudget:
    """Error budget tracking for an SLO."""
    total_budget_percent: float
    consumed_percent: float = 0.0
    remaining_percent: float = field(init=False)
    burn_rate_per_hour: float = 0.0
    time_to_exhaustion_hours: Optional[float] = None
    
    def __post_init__(self):
        """Calculate derived values."""
        self.remaining_percent = self.total_budget_percent - self.consumed_percent
        
        if self.burn_rate_per_hour > 0:
            self.time_to_exhaustion_hours = self.remaining_percent / self.burn_rate_per_hour
            
    @property
    def status(self) -> ErrorBudgetBurnRate:
        """Determine burn rate status."""
        if self.burn_rate_per_hour == 0:
            return ErrorBudgetBurnRate.SLOW
            
        # Calculate how fast we're burning compared to sustainable rate
        # Sustainable rate = total_budget / time_window_hours
        sustainable_rate = self.total_budget_percent / 24  # Assuming 24h window
        burn_multiplier = self.burn_rate_per_hour / sustainable_rate
        
        if burn_multiplier >= 10:  # 10x faster than sustainable
            return ErrorBudgetBurnRate.CRITICAL
        elif burn_multiplier >= 5:  # 5x faster
            return ErrorBudgetBurnRate.FAST
        elif burn_multiplier >= 2:  # 2x faster
            return ErrorBudgetBurnRate.MODERATE
        else:
            return ErrorBudgetBurnRate.SLOW


@dataclass
class SLOResult:
    """Result of SLO evaluation."""
    slo_name: str
    sli_type: SLIType
    current_sli_value: float
    slo_target: float
    compliance_percent: float
    status: SLOStatus
    error_budget: ErrorBudget
    time_window_start: datetime
    time_window_end: datetime
    
    # Detailed metrics
    total_measurements: int = 0
    good_measurements: int = 0
    
    # Alerting context
    requires_immediate_attention: bool = False
    escalation_level: str = "none"


class ChildSafetySLICalculator:
    """Specialized SLI calculations for child safety services."""
    
    @staticmethod
    def calculate_content_filter_accuracy(
        filtered_correctly: int,
        total_content_items: int
    ) -> float:
        """Calculate content filtering accuracy SLI."""
        if total_content_items == 0:
            return 1.0
        return filtered_correctly / total_content_items
        
    @staticmethod
    def calculate_safety_response_time(response_times_ms: List[float]) -> float:
        """Calculate safety alert response time SLI (P95)."""
        if not response_times_ms:
            return 0.0
        return statistics.quantiles(response_times_ms, n=20)[18]  # P95
        
    @staticmethod
    def calculate_coppa_compliance_rate(
        compliant_interactions: int,
        total_child_interactions: int
    ) -> float:
        """Calculate COPPA compliance rate SLI."""
        if total_child_interactions == 0:
            return 1.0
        return compliant_interactions / total_child_interactions
        
    @staticmethod
    def calculate_parental_consent_coverage(
        children_with_valid_consent: int,
        total_children_under_13: int
    ) -> float:
        """Calculate parental consent coverage SLI."""
        if total_children_under_13 == 0:
            return 1.0
        return children_with_valid_consent / total_children_under_13


class SLOFramework:
    """
    Comprehensive SLI/SLO framework for AI Teddy Bear platform.
    
    Manages service reliability through:
    - Child safety-prioritized SLO definitions
    - Multi-window error budget tracking
    - Intelligent burn rate alerting
    - Automated compliance reporting
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        
        # SLO definitions
        self.slo_targets = self._initialize_slo_targets()
        
        # SLI measurement history
        self.sli_measurements: defaultdict = defaultdict(lambda: deque(maxlen=10000))
        
        # Error budget tracking
        self.error_budgets: Dict[str, ErrorBudget] = {}
        
        # Child safety calculator
        self.child_safety_calculator = ChildSafetySLICalculator()
        
        # Monitoring tasks
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        
        # Alert callbacks
        self.alert_callbacks: Dict[str, List[callable]] = defaultdict(list)
        
        # SLO compliance history
        self.compliance_history: defaultdict = defaultdict(lambda: deque(maxlen=1000))
        
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for SLO framework."""
        return {
            "evaluation_interval_seconds": 60,
            "error_budget_alerting": True,
            "automated_reporting": True,
            "child_safety_priority": True,
            "burn_rate_alert_thresholds": {
                "fast": 2.0,      # 2x normal burn rate
                "critical": 10.0  # 10x normal burn rate
            }
        }
        
    def _initialize_slo_targets(self) -> Dict[str, SLOTarget]:
        """Initialize production SLO targets."""
        return {
            # ========================================
            # CHILD SAFETY SLOS - HIGHEST PRIORITY
            # ========================================
            "content_filter_accuracy": SLOTarget(
                name="content_filter_accuracy",
                sli_type=SLIType.CHILD_SAFETY,
                target_value=0.995,  # 99.5% accuracy
                time_window_hours=24,
                is_child_safety_critical=True,
                business_impact="critical",
                priority=1
            ),
            
            "safety_alert_response_time": SLOTarget(
                name="safety_alert_response_time",
                sli_type=SLIType.LATENCY,
                target_value=30.0,   # 30 seconds P95
                time_window_hours=24,
                is_child_safety_critical=True,
                business_impact="critical",
                priority=1
            ),
            
            "coppa_compliance_rate": SLOTarget(
                name="coppa_compliance_rate", 
                sli_type=SLIType.CHILD_SAFETY,
                target_value=0.999,  # 99.9% compliance
                time_window_hours=24,
                is_child_safety_critical=True,
                business_impact="critical",
                priority=1
            ),
            
            "parental_consent_coverage": SLOTarget(
                name="parental_consent_coverage",
                sli_type=SLIType.CHILD_SAFETY,
                target_value=0.995,  # 99.5% coverage
                time_window_hours=24,
                is_child_safety_critical=True,
                business_impact="critical",
                priority=1
            ),
            
            # ========================================
            # APPLICATION AVAILABILITY & PERFORMANCE
            # ========================================
            "api_availability": SLOTarget(
                name="api_availability",
                sli_type=SLIType.AVAILABILITY,
                target_value=0.995,  # 99.5% uptime
                time_window_hours=24,
                business_impact="high",
                priority=2
            ),
            
            "api_latency_p95": SLOTarget(
                name="api_latency_p95",
                sli_type=SLIType.LATENCY,
                target_value=2000.0,  # 2s P95 (child attention span)
                time_window_hours=24,
                business_impact="high",
                priority=2
            ),
            
            "child_interaction_success_rate": SLOTarget(
                name="child_interaction_success_rate",
                sli_type=SLIType.CORRECTNESS,
                target_value=0.98,   # 98% successful interactions
                time_window_hours=24,
                business_impact="high",
                priority=2
            ),
            
            # ========================================
            # AI PROVIDER SLOS
            # ========================================
            "ai_provider_availability": SLOTarget(
                name="ai_provider_availability",
                sli_type=SLIType.AVAILABILITY,
                target_value=0.99,   # 99% availability
                time_window_hours=24,
                business_impact="high",
                priority=3
            ),
            
            "ai_response_latency_p95": SLOTarget(
                name="ai_response_latency_p95",
                sli_type=SLIType.LATENCY,
                target_value=5000.0,  # 5s P95 for AI responses
                time_window_hours=24,
                business_impact="medium",
                priority=3
            ),
            
            # ========================================
            # INFRASTRUCTURE SLOS
            # ========================================
            "database_availability": SLOTarget(
                name="database_availability",
                sli_type=SLIType.AVAILABILITY,
                target_value=0.999,  # 99.9% availability
                time_window_hours=24,
                business_impact="high",
                priority=2
            ),
            
            "database_query_latency_p95": SLOTarget(
                name="database_query_latency_p95", 
                sli_type=SLIType.LATENCY,
                target_value=500.0,  # 500ms P95
                time_window_hours=24,
                business_impact="medium",
                priority=4
            ),
            
            # ========================================
            # BUSINESS METRICS SLOS
            # ========================================
            "parent_satisfaction_score": SLOTarget(
                name="parent_satisfaction_score",
                sli_type=SLIType.CORRECTNESS,
                target_value=4.0,    # 4.0/5.0 average rating
                time_window_hours=168,  # 7 days for business metrics
                business_impact="medium",
                priority=5
            ),
            
            "story_generation_success_rate": SLOTarget(
                name="story_generation_success_rate",
                sli_type=SLIType.CORRECTNESS,
                target_value=0.95,   # 95% successful story generations
                time_window_hours=24,
                business_impact="medium",
                priority=4
            )
        }
        
    async def start_monitoring(self):
        """Start SLO monitoring and evaluation."""
        logger.info("Starting SLI/SLO monitoring framework")
        
        # Start evaluation task for each SLO
        for slo_name in self.slo_targets:
            self._monitoring_tasks[slo_name] = asyncio.create_task(
                self._continuous_slo_evaluation(slo_name)
            )
            
        # Start error budget monitoring
        self._monitoring_tasks["error_budget_monitor"] = asyncio.create_task(
            self._error_budget_monitoring()
        )
        
        # Start compliance reporting
        if self.config.get("automated_reporting", True):
            self._monitoring_tasks["compliance_reporting"] = asyncio.create_task(
                self._automated_compliance_reporting()
            )
            
        logger.info(f"Started {len(self._monitoring_tasks)} SLO monitoring tasks")
        
    async def _continuous_slo_evaluation(self, slo_name: str):
        """Continuously evaluate SLO compliance."""
        interval = self.config.get("evaluation_interval_seconds", 60)
        
        while True:
            try:
                slo_result = await self._evaluate_slo(slo_name)
                
                # Store compliance history
                self.compliance_history[slo_name].append(slo_result)
                
                # Update error budget
                await self._update_error_budget(slo_name, slo_result)
                
                # Check for alerting conditions
                await self._check_slo_alerting(slo_result)
                
                # Log significant changes
                if slo_result.status in [SLOStatus.CRITICAL, SLOStatus.BREACH]:
                    logger.critical(
                        f"SLO violation: {slo_name} at {slo_result.compliance_percent:.2f}% "
                        f"(target: {slo_result.slo_target:.2f}%)"
                    )
                elif slo_result.status == SLOStatus.WARNING:
                    logger.warning(
                        f"SLO warning: {slo_name} at {slo_result.compliance_percent:.2f}%"
                    )
                    
            except Exception as e:
                logger.error(f"SLO evaluation failed for {slo_name}: {e}")
                
            await asyncio.sleep(interval)
            
    async def _evaluate_slo(self, slo_name: str) -> SLOResult:
        """Evaluate SLO compliance for a specific service."""
        slo_target = self.slo_targets[slo_name]
        current_time = datetime.utcnow()
        time_window_start = current_time - timedelta(hours=slo_target.time_window_hours)
        
        try:
            # Get current SLI value based on SLO type
            current_sli_value = await self._calculate_current_sli(slo_name, time_window_start, current_time)
            
            # Calculate compliance
            if slo_target.sli_type in [SLIType.LATENCY]:
                # For latency SLOs, lower is better
                compliance_percent = min(100.0, (slo_target.target_value / max(current_sli_value, 1)) * 100)
                meets_target = current_sli_value <= slo_target.target_value
            else:
                # For availability, correctness, etc., higher is better
                compliance_percent = (current_sli_value * 100)
                meets_target = current_sli_value >= slo_target.target_value
                
            # Determine status
            if meets_target:
                status = SLOStatus.HEALTHY
            else:
                # Check error budget status
                error_budget = self.error_budgets.get(slo_name)
                if error_budget and error_budget.remaining_percent <= 0:
                    status = SLOStatus.BREACH
                elif error_budget and error_budget.remaining_percent <= 10:  # 10% remaining
                    status = SLOStatus.CRITICAL
                else:
                    status = SLOStatus.WARNING
                    
            # Get measurements count (simulated for now)
            total_measurements, good_measurements = await self._get_measurement_counts(
                slo_name, time_window_start, current_time
            )
            
            # Create error budget if not exists
            if slo_name not in self.error_budgets:
                self.error_budgets[slo_name] = ErrorBudget(
                    total_budget_percent=slo_target.error_budget_percent
                )
                
            return SLOResult(
                slo_name=slo_name,
                sli_type=slo_target.sli_type,
                current_sli_value=current_sli_value,
                slo_target=slo_target.target_value,
                compliance_percent=compliance_percent,
                status=status,
                error_budget=self.error_budgets[slo_name],
                time_window_start=time_window_start,
                time_window_end=current_time,
                total_measurements=total_measurements,
                good_measurements=good_measurements,
                requires_immediate_attention=(
                    slo_target.is_child_safety_critical and 
                    status in [SLOStatus.CRITICAL, SLOStatus.BREACH]
                ),
                escalation_level="immediate" if slo_target.is_child_safety_critical else "normal"
            )
            
        except Exception as e:
            logger.error(f"SLO evaluation failed for {slo_name}: {e}")
            return SLOResult(
                slo_name=slo_name,
                sli_type=slo_target.sli_type,
                current_sli_value=0.0,
                slo_target=slo_target.target_value,
                compliance_percent=0.0,
                status=SLOStatus.CRITICAL,
                error_budget=self.error_budgets.get(slo_name, ErrorBudget(0.0)),
                time_window_start=time_window_start,
                time_window_end=current_time,
                requires_immediate_attention=slo_target.is_child_safety_critical
            )
            
    async def _calculate_current_sli(
        self, 
        slo_name: str, 
        time_window_start: datetime, 
        time_window_end: datetime
    ) -> float:
        """Calculate current SLI value for the specified time window."""
        
        # This would normally query your metrics database (Prometheus, etc.)
        # For demonstration, we'll simulate SLI calculations
        
        if slo_name == "content_filter_accuracy":
            # Simulate content filter accuracy
            return self.child_safety_calculator.calculate_content_filter_accuracy(
                filtered_correctly=995,
                total_content_items=1000
            )
            
        elif slo_name == "safety_alert_response_time":
            # Simulate safety alert response times
            response_times = [15.0, 20.0, 25.0, 35.0, 45.0] * 20  # Sample data
            return self.child_safety_calculator.calculate_safety_response_time(response_times)
            
        elif slo_name == "coppa_compliance_rate":
            return self.child_safety_calculator.calculate_coppa_compliance_rate(
                compliant_interactions=999,
                total_child_interactions=1000
            )
            
        elif slo_name == "parental_consent_coverage":
            return self.child_safety_calculator.calculate_parental_consent_coverage(
                children_with_valid_consent=995,
                total_children_under_13=1000
            )
            
        elif slo_name == "api_availability":
            # Simulate API availability
            return 0.996  # 99.6%
            
        elif slo_name == "api_latency_p95":
            # Simulate API latency P95
            return 1800.0  # 1.8 seconds
            
        elif slo_name == "child_interaction_success_rate":
            # Simulate child interaction success rate
            return 0.982  # 98.2%
            
        elif slo_name == "ai_provider_availability":
            # Simulate AI provider availability
            return 0.992  # 99.2%
            
        elif slo_name == "ai_response_latency_p95":
            # Simulate AI response latency
            return 4200.0  # 4.2 seconds
            
        elif slo_name == "database_availability":
            return 0.9995  # 99.95%
            
        elif slo_name == "database_query_latency_p95":
            return 350.0  # 350ms
            
        elif slo_name == "parent_satisfaction_score":
            return 4.2  # 4.2/5.0
            
        elif slo_name == "story_generation_success_rate":
            return 0.96  # 96%
            
        else:
            # Default fallback
            return 0.95
            
    async def _get_measurement_counts(
        self,
        slo_name: str,
        time_window_start: datetime,
        time_window_end: datetime
    ) -> Tuple[int, int]:
        """Get total and good measurement counts for the time window."""
        # This would normally query your metrics database
        # For demonstration, return simulated counts
        
        time_window_hours = (time_window_end - time_window_start).total_seconds() / 3600
        
        # Estimate measurements based on typical traffic
        if "child_safety" in slo_name or "safety" in slo_name:
            total_measurements = int(time_window_hours * 100)  # 100 safety checks per hour
        elif "api" in slo_name:
            total_measurements = int(time_window_hours * 1000)  # 1000 API calls per hour
        else:
            total_measurements = int(time_window_hours * 500)   # 500 measurements per hour
            
        # Calculate good measurements based on current SLI
        current_sli = await self._calculate_current_sli(slo_name, time_window_start, time_window_end)
        good_measurements = int(total_measurements * current_sli)
        
        return total_measurements, good_measurements
        
    async def _update_error_budget(self, slo_name: str, slo_result: SLOResult):
        """Update error budget based on SLO result."""
        if slo_name not in self.error_budgets:
            return
            
        error_budget = self.error_budgets[slo_name]
        slo_target = self.slo_targets[slo_name]
        
        # Calculate error rate
        if slo_result.total_measurements > 0:
            error_events = slo_result.total_measurements - slo_result.good_measurements
            error_rate = error_events / slo_result.total_measurements
            
            # Update consumed budget
            # For a 24h window, each measurement represents (1/total_measurements) of the window
            window_fraction = 1.0 / max(slo_result.total_measurements, 1)
            error_budget.consumed_percent += (error_rate * 100 * window_fraction)
            
            # Calculate burn rate (errors per hour)
            time_window_hours = slo_target.time_window_hours
            error_budget.burn_rate_per_hour = (error_rate * 100) / time_window_hours
            
            # Update remaining budget
            error_budget.remaining_percent = max(0, error_budget.total_budget_percent - error_budget.consumed_percent)
            
            # Calculate time to exhaustion
            if error_budget.burn_rate_per_hour > 0:
                error_budget.time_to_exhaustion_hours = error_budget.remaining_percent / error_budget.burn_rate_per_hour
            else:
                error_budget.time_to_exhaustion_hours = None
                
    async def _check_slo_alerting(self, slo_result: SLOResult):
        """Check if SLO result requires alerting."""
        slo_target = self.slo_targets[slo_result.slo_name]
        
        # Always alert on child safety SLO violations
        if (slo_target.is_child_safety_critical and 
            slo_result.status in [SLOStatus.CRITICAL, SLOStatus.BREACH]):
            await self._trigger_slo_alert(slo_result, "child_safety_violation")
            
        # Alert on error budget burn rate
        if slo_result.slo_name in self.error_budgets:
            error_budget = self.error_budgets[slo_result.slo_name]
            burn_status = error_budget.status
            
            if burn_status == ErrorBudgetBurnRate.CRITICAL:
                await self._trigger_slo_alert(slo_result, "critical_burn_rate")
            elif burn_status == ErrorBudgetBurnRate.FAST:
                await self._trigger_slo_alert(slo_result, "fast_burn_rate")
                
        # Alert on SLO breach
        if slo_result.status == SLOStatus.BREACH:
            await self._trigger_slo_alert(slo_result, "slo_breach")
            
    async def _trigger_slo_alert(self, slo_result: SLOResult, alert_type: str):
        """Trigger SLO-related alert."""
        logger.warning(
            f"SLO Alert: {alert_type} for {slo_result.slo_name} - "
            f"Status: {slo_result.status.value}, "
            f"Compliance: {slo_result.compliance_percent:.2f}%"
        )
        
        # Execute registered alert callbacks
        for callback in self.alert_callbacks[alert_type]:
            try:
                await callback(slo_result)
            except Exception as e:
                logger.error(f"SLO alert callback failed: {e}")
                
    async def _error_budget_monitoring(self):
        """Monitor error budget burn rates."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                for slo_name, error_budget in self.error_budgets.items():
                    burn_status = error_budget.status
                    
                    # Log significant burn rate changes
                    if burn_status in [ErrorBudgetBurnRate.FAST, ErrorBudgetBurnRate.CRITICAL]:
                        logger.warning(
                            f"Error budget burn rate alert: {slo_name} - "
                            f"Status: {burn_status.value}, "
                            f"Remaining: {error_budget.remaining_percent:.2f}%, "
                            f"Time to exhaustion: {error_budget.time_to_exhaustion_hours:.1f}h"
                        )
                        
            except Exception as e:
                logger.error(f"Error budget monitoring failed: {e}")
                
    async def _automated_compliance_reporting(self):
        """Generate automated SLO compliance reports."""
        while True:
            try:
                # Generate report every hour
                await asyncio.sleep(3600)
                
                report = await self.generate_compliance_report()
                
                # Log summary
                logger.info(
                    f"SLO Compliance Report: "
                    f"Total SLOs: {report['total_slos']}, "
                    f"Healthy: {report['healthy_slos']}, "
                    f"Warning: {report['warning_slos']}, "
                    f"Critical: {report['critical_slos']}, "
                    f"Breached: {report['breached_slos']}"
                )
                
            except Exception as e:
                logger.error(f"Compliance reporting failed: {e}")
                
    async def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate comprehensive SLO compliance report."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_slos": len(self.slo_targets),
            "healthy_slos": 0,
            "warning_slos": 0,
            "critical_slos": 0,
            "breached_slos": 0,
            "slo_details": {},
            "child_safety_summary": {},
            "error_budget_summary": {}
        }
        
        child_safety_issues = []
        
        for slo_name in self.slo_targets:
            # Get latest compliance result
            if (slo_name in self.compliance_history and 
                self.compliance_history[slo_name]):
                latest_result = self.compliance_history[slo_name][-1]
                
                # Count by status
                if latest_result.status == SLOStatus.HEALTHY:
                    report["healthy_slos"] += 1
                elif latest_result.status == SLOStatus.WARNING:
                    report["warning_slos"] += 1
                elif latest_result.status == SLOStatus.CRITICAL:
                    report["critical_slos"] += 1
                elif latest_result.status == SLOStatus.BREACH:
                    report["breached_slos"] += 1
                    
                # Add detailed info
                report["slo_details"][slo_name] = {
                    "status": latest_result.status.value,
                    "compliance_percent": latest_result.compliance_percent,
                    "target": latest_result.slo_target,
                    "current_value": latest_result.current_sli_value,
                    "business_impact": self.slo_targets[slo_name].business_impact,
                    "is_child_safety_critical": self.slo_targets[slo_name].is_child_safety_critical
                }
                
                # Track child safety issues
                if (self.slo_targets[slo_name].is_child_safety_critical and
                    latest_result.status in [SLOStatus.CRITICAL, SLOStatus.BREACH]):
                    child_safety_issues.append({
                        "slo_name": slo_name,
                        "status": latest_result.status.value,
                        "compliance": latest_result.compliance_percent
                    })
                    
        # Child safety summary
        report["child_safety_summary"] = {
            "total_child_safety_slos": len([
                s for s in self.slo_targets.values() 
                if s.is_child_safety_critical
            ]),
            "issues_detected": len(child_safety_issues),
            "critical_issues": child_safety_issues
        }
        
        # Error budget summary
        total_budget_remaining = 0
        critical_burn_rates = 0
        
        for slo_name, error_budget in self.error_budgets.items():
            total_budget_remaining += error_budget.remaining_percent
            if error_budget.status == ErrorBudgetBurnRate.CRITICAL:
                critical_burn_rates += 1
                
        report["error_budget_summary"] = {
            "average_budget_remaining_percent": total_budget_remaining / max(len(self.error_budgets), 1),
            "services_with_critical_burn_rate": critical_burn_rates,
            "total_services_tracked": len(self.error_budgets)
        }
        
        return report
        
    def record_sli_measurement(
        self,
        slo_name: str,
        value: float,
        good_events: int = 0,
        total_events: int = 0
    ):
        """Record an SLI measurement."""
        measurement = SLIMetric(
            value=value,
            timestamp=datetime.utcnow(),
            good_events=good_events,
            total_events=total_events
        )
        
        self.sli_measurements[slo_name].append(measurement)
        
    def register_slo_alert_callback(self, alert_type: str, callback: callable):
        """Register callback for SLO alerts."""
        self.alert_callbacks[alert_type].append(callback)
        logger.info(f"Registered SLO alert callback for {alert_type}")
        
    async def get_slo_status_summary(self) -> Dict[str, Any]:
        """Get current SLO status summary."""
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": "healthy",
            "slo_statuses": {},
            "child_safety_status": "healthy",
            "requires_attention": []
        }
        
        critical_issues = 0
        child_safety_issues = 0
        
        for slo_name in self.slo_targets:
            if (slo_name in self.compliance_history and 
                self.compliance_history[slo_name]):
                latest_result = self.compliance_history[slo_name][-1]
                
                summary["slo_statuses"][slo_name] = {
                    "status": latest_result.status.value,
                    "compliance": latest_result.compliance_percent,
                    "error_budget_remaining": self.error_budgets.get(slo_name, ErrorBudget(0)).remaining_percent
                }
                
                if latest_result.status in [SLOStatus.CRITICAL, SLOStatus.BREACH]:
                    critical_issues += 1
                    summary["requires_attention"].append(slo_name)
                    
                    if self.slo_targets[slo_name].is_child_safety_critical:
                        child_safety_issues += 1
                        
        # Determine overall health
        if child_safety_issues > 0:
            summary["overall_health"] = "critical"
            summary["child_safety_status"] = "critical"
        elif critical_issues > 0:
            summary["overall_health"] = "degraded"
        
        return summary
        
    async def stop_monitoring(self):
        """Stop SLO monitoring."""
        logger.info("Stopping SLI/SLO monitoring")
        
        for task_name, task in self._monitoring_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        self._monitoring_tasks.clear()
        logger.info("SLI/SLO monitoring stopped")


# Factory function for production use
async def create_slo_framework(
    config: Optional[Dict[str, Any]] = None
) -> SLOFramework:
    """Create and start SLI/SLO framework."""
    
    framework = SLOFramework(config)
    await framework.start_monitoring()
    
    return framework


# Example usage for production deployment
if __name__ == "__main__":
    async def main():
        # Create SLO framework
        slo_framework = await create_slo_framework({
            "evaluation_interval_seconds": 30,  # More frequent for demo
            "child_safety_priority": True
        })
        
        # Register alert callbacks
        async def child_safety_alert(slo_result: SLOResult):
            print(f"🚨 CHILD SAFETY ALERT: {slo_result.slo_name} - {slo_result.status.value}")
            
        async def slo_breach_alert(slo_result: SLOResult):
            print(f"⚠️ SLO BREACH: {slo_result.slo_name} - {slo_result.compliance_percent:.2f}%")
            
        slo_framework.register_slo_alert_callback("child_safety_violation", child_safety_alert)
        slo_framework.register_slo_alert_callback("slo_breach", slo_breach_alert)
        
        # Record some sample measurements
        slo_framework.record_sli_measurement("content_filter_accuracy", 0.994, 994, 1000)
        slo_framework.record_sli_measurement("api_availability", 0.998, 998, 1000)
        
        # Run for demonstration
        await asyncio.sleep(120)  # 2 minutes
        
        # Generate compliance report
        report = await slo_framework.generate_compliance_report()
        print("\nSLO Compliance Report:")
        print(json.dumps(report, indent=2, default=str))
        
        # Get status summary
        status = await slo_framework.get_slo_status_summary()
        print("\nSLO Status Summary:")
        print(json.dumps(status, indent=2))
        
        # Stop monitoring
        await slo_framework.stop_monitoring()
    
    asyncio.run(main())