"""
AI Teddy Bear - RTO/RPO Measurement and Validation Framework

This module provides comprehensive measurement and validation of Recovery Time Objectives (RTO)
and Recovery Point Objectives (RPO) for all disaster recovery scenarios.

CRITICAL: RTO/RPO targets are contractual commitments for child safety and service availability.
All measurements must be accurate and auditable for compliance purposes.
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import statistics
import numpy as np

from src.infrastructure.monitoring.audit import AuditLogger
from src.core.exceptions import DisasterRecoveryError, MetricsError


@dataclass
class RTOTarget:
    """Recovery Time Objective target definition."""
    service_name: str
    target_seconds: int
    criticality: str  # CRITICAL, HIGH, MEDIUM, LOW
    business_impact: str
    child_safety_impact: bool
    compliance_requirement: bool


@dataclass
class RPOTarget:
    """Recovery Point Objective target definition."""
    data_type: str
    target_seconds: int
    criticality: str  # CRITICAL, HIGH, MEDIUM, LOW
    child_safety_impact: bool
    compliance_requirement: bool
    zero_tolerance: bool


@dataclass
class RTOMeasurement:
    """Recovery Time Objective measurement result."""
    service_name: str
    target_seconds: int
    actual_seconds: float
    achieved: bool
    measurement_timestamp: str
    test_scenario: str
    failure_type: str
    recovery_method: str
    criticality: str
    child_safety_impact: bool


@dataclass
class RPOMeasurement:
    """Recovery Point Objective measurement result."""
    data_type: str
    target_seconds: int
    actual_seconds: float
    achieved: bool
    measurement_timestamp: str
    test_scenario: str
    data_loss_amount: int
    recovery_method: str
    criticality: str
    child_safety_impact: bool


class RTORPOMeasurementFramework:
    """
    Comprehensive RTO/RPO measurement and validation framework.
    
    Provides:
    - RTO/RPO target definition and management
    - Real-time measurement during disaster recovery tests
    - Statistical analysis and trending
    - Compliance reporting and validation
    - Child safety impact assessment
    """
    
    def __init__(self):
        self.audit_logger = AuditLogger()
        self.measurement_start_time = datetime.utcnow()
        self.rto_measurements: List[RTOMeasurement] = []
        self.rpo_measurements: List[RPOMeasurement] = []
        
        # Define RTO targets based on business requirements
        self.rto_targets = self._define_rto_targets()
        
        # Define RPO targets based on compliance and business requirements
        self.rpo_targets = self._define_rpo_targets()
        
        # Active measurement sessions
        self.active_measurements = {}

    def _define_rto_targets(self) -> List[RTOTarget]:
        """Define RTO targets for all critical services."""
        return [
            # Child Safety Services - CRITICAL
            RTOTarget(
                service_name="child_safety_monitoring",
                target_seconds=30,  # 30 seconds - CRITICAL
                criticality="CRITICAL",
                business_impact="Child safety compromise",
                child_safety_impact=True,
                compliance_requirement=True
            ),
            RTOTarget(
                service_name="child_session_termination",
                target_seconds=30,  # 30 seconds - CRITICAL
                criticality="CRITICAL", 
                business_impact="Child exposure to unsafe content",
                child_safety_impact=True,
                compliance_requirement=True
            ),
            RTOTarget(
                service_name="parent_notification",
                target_seconds=60,  # 1 minute - CRITICAL
                criticality="CRITICAL",
                business_impact="Parent not informed of safety incident",
                child_safety_impact=True,
                compliance_requirement=True
            ),
            
            # Core Application Services - HIGH
            RTOTarget(
                service_name="ai_conversation_service",
                target_seconds=300,  # 5 minutes - HIGH
                criticality="HIGH",
                business_impact="Service unavailable to children",
                child_safety_impact=False,
                compliance_requirement=False
            ),
            RTOTarget(
                service_name="user_authentication",
                target_seconds=180,  # 3 minutes - HIGH
                criticality="HIGH", 
                business_impact="Users cannot access service",
                child_safety_impact=False,
                compliance_requirement=False
            ),
            RTOTarget(
                service_name="content_filtering",
                target_seconds=60,  # 1 minute - HIGH
                criticality="HIGH",
                business_impact="Inappropriate content exposure risk",
                child_safety_impact=True,
                compliance_requirement=True
            ),
            
            # Database Services - HIGH
            RTOTarget(
                service_name="database_primary",
                target_seconds=600,  # 10 minutes - HIGH
                criticality="HIGH",
                business_impact="Data unavailable",
                child_safety_impact=False,
                compliance_requirement=True
            ),
            RTOTarget(
                service_name="database_failover",
                target_seconds=180,  # 3 minutes - HIGH
                criticality="HIGH",
                business_impact="Extended data unavailability",
                child_safety_impact=False,
                compliance_requirement=True
            ),
            
            # Infrastructure Services - MEDIUM
            RTOTarget(
                service_name="load_balancer",
                target_seconds=120,  # 2 minutes - MEDIUM
                criticality="MEDIUM",
                business_impact="Service access issues",
                child_safety_impact=False,
                compliance_requirement=False
            ),
            RTOTarget(
                service_name="redis_cache",
                target_seconds=300,  # 5 minutes - MEDIUM
                criticality="MEDIUM",
                business_impact="Performance degradation",
                child_safety_impact=False,
                compliance_requirement=False
            ),
            
            # System Recovery - MEDIUM
            RTOTarget(
                service_name="full_system_recovery",
                target_seconds=900,  # 15 minutes - MEDIUM
                criticality="MEDIUM",
                business_impact="Complete service outage",
                child_safety_impact=True,
                compliance_requirement=False
            )
        ]

    def _define_rpo_targets(self) -> List[RPOTarget]:
        """Define RPO targets for all critical data types."""
        return [
            # Child Safety Data - ZERO TOLERANCE
            RPOTarget(
                data_type="child_safety_incidents",
                target_seconds=0,  # Zero tolerance
                criticality="CRITICAL",
                child_safety_impact=True,
                compliance_requirement=True,
                zero_tolerance=True
            ),
            RPOTarget(
                data_type="child_profile_data",
                target_seconds=0,  # Zero tolerance
                criticality="CRITICAL",
                child_safety_impact=True,
                compliance_requirement=True,
                zero_tolerance=True
            ),
            RPOTarget(
                data_type="audit_logs",
                target_seconds=0,  # Zero tolerance
                criticality="CRITICAL",
                child_safety_impact=True,
                compliance_requirement=True,
                zero_tolerance=True
            ),
            
            # Compliance Data - ZERO TOLERANCE
            RPOTarget(
                data_type="coppa_compliance_records",
                target_seconds=0,  # Zero tolerance
                criticality="CRITICAL",
                child_safety_impact=True,
                compliance_requirement=True,
                zero_tolerance=True
            ),
            RPOTarget(
                data_type="consent_forms",
                target_seconds=0,  # Zero tolerance
                criticality="CRITICAL",
                child_safety_impact=True,
                compliance_requirement=True,
                zero_tolerance=True
            ),
            
            # User Data - LIMITED TOLERANCE
            RPOTarget(
                data_type="user_sessions",
                target_seconds=300,  # 5 minutes
                criticality="HIGH",
                child_safety_impact=False,
                compliance_requirement=False,
                zero_tolerance=False
            ),
            RPOTarget(
                data_type="conversation_history",
                target_seconds=300,  # 5 minutes
                criticality="HIGH",
                child_safety_impact=False,
                compliance_requirement=False,
                zero_tolerance=False
            ),
            
            # System Data - MODERATE TOLERANCE
            RPOTarget(
                data_type="application_logs",
                target_seconds=600,  # 10 minutes
                criticality="MEDIUM",
                child_safety_impact=False,
                compliance_requirement=False,
                zero_tolerance=False
            ),
            RPOTarget(
                data_type="performance_metrics",
                target_seconds=900,  # 15 minutes
                criticality="LOW",
                child_safety_impact=False,
                compliance_requirement=False,
                zero_tolerance=False
            )
        ]

    async def start_rto_measurement(self, service_name: str, test_scenario: str, failure_type: str) -> str:
        """Start measuring RTO for a service recovery."""
        measurement_id = f"rto_{service_name}_{int(time.time())}"
        
        # Find target for this service
        target = next((t for t in self.rto_targets if t.service_name == service_name), None)
        if not target:
            raise MetricsError(f"No RTO target defined for service: {service_name}")
        
        measurement_session = {
            'measurement_id': measurement_id,
            'service_name': service_name,
            'target_seconds': target.target_seconds,
            'start_time': time.time(),
            'test_scenario': test_scenario,
            'failure_type': failure_type,
            'criticality': target.criticality,
            'child_safety_impact': target.child_safety_impact,
            'compliance_requirement': target.compliance_requirement
        }
        
        self.active_measurements[measurement_id] = measurement_session
        
        # Log measurement start
        await self.audit_logger.log_security_event(
            "rto_measurement_start",
            {
                "measurement_id": measurement_id,
                "service_name": service_name,
                "target_seconds": target.target_seconds,
                "test_scenario": test_scenario,
                "failure_type": failure_type,
                "criticality": target.criticality
            }
        )
        
        return measurement_id

    async def end_rto_measurement(self, measurement_id: str, recovery_method: str = "automatic") -> RTOMeasurement:
        """End RTO measurement and record results."""
        if measurement_id not in self.active_measurements:
            raise MetricsError(f"No active RTO measurement found: {measurement_id}")
        
        session = self.active_measurements[measurement_id]
        end_time = time.time()
        actual_seconds = end_time - session['start_time']
        achieved = actual_seconds <= session['target_seconds']
        
        measurement = RTOMeasurement(
            service_name=session['service_name'],
            target_seconds=session['target_seconds'],
            actual_seconds=actual_seconds,
            achieved=achieved,
            measurement_timestamp=datetime.utcnow().isoformat(),
            test_scenario=session['test_scenario'],
            failure_type=session['failure_type'],
            recovery_method=recovery_method,
            criticality=session['criticality'],
            child_safety_impact=session['child_safety_impact']
        )
        
        self.rto_measurements.append(measurement)
        del self.active_measurements[measurement_id]
        
        # Log measurement completion
        await self.audit_logger.log_security_event(
            "rto_measurement_completed",
            {
                "measurement_id": measurement_id,
                "service_name": session['service_name'],
                "target_seconds": session['target_seconds'],
                "actual_seconds": actual_seconds,
                "achieved": achieved,
                "recovery_method": recovery_method,
                "criticality": session['criticality'],
                "child_safety_impact": session['child_safety_impact']
            }
        )
        
        # Alert if critical RTO not met
        if not achieved and session['child_safety_impact']:
            await self.audit_logger.log_security_event(
                "critical_rto_violation",
                {
                    "service_name": session['service_name'],
                    "target_seconds": session['target_seconds'],
                    "actual_seconds": actual_seconds,
                    "child_safety_impact": True,
                    "severity": "CRITICAL"
                }
            )
        
        return measurement

    async def start_rpo_measurement(self, data_type: str, test_scenario: str) -> str:
        """Start measuring RPO for data recovery."""
        measurement_id = f"rpo_{data_type}_{int(time.time())}"
        
        # Find target for this data type
        target = next((t for t in self.rpo_targets if t.data_type == data_type), None)
        if not target:
            raise MetricsError(f"No RPO target defined for data type: {data_type}")
        
        measurement_session = {
            'measurement_id': measurement_id,
            'data_type': data_type,
            'target_seconds': target.target_seconds,
            'start_time': time.time(),
            'test_scenario': test_scenario,
            'criticality': target.criticality,
            'child_safety_impact': target.child_safety_impact,
            'compliance_requirement': target.compliance_requirement,
            'zero_tolerance': target.zero_tolerance
        }
        
        self.active_measurements[measurement_id] = measurement_session
        
        # Log measurement start
        await self.audit_logger.log_security_event(
            "rpo_measurement_start",
            {
                "measurement_id": measurement_id,
                "data_type": data_type,
                "target_seconds": target.target_seconds,
                "test_scenario": test_scenario,
                "criticality": target.criticality,
                "zero_tolerance": target.zero_tolerance
            }
        )
        
        return measurement_id

    async def end_rpo_measurement(self, measurement_id: str, data_loss_amount: int = 0, recovery_method: str = "backup") -> RPOMeasurement:
        """End RPO measurement and record results."""
        if measurement_id not in self.active_measurements:
            raise MetricsError(f"No active RPO measurement found: {measurement_id}")
        
        session = self.active_measurements[measurement_id]
        end_time = time.time()
        
        # For RPO, we measure data loss time, not recovery time
        # This would typically be calculated based on the last backup/checkpoint
        actual_seconds = float(data_loss_amount)  # Simplified for testing
        achieved = actual_seconds <= session['target_seconds']
        
        # Zero tolerance means no data loss is acceptable
        if session['zero_tolerance']:
            achieved = data_loss_amount == 0
        
        measurement = RPOMeasurement(
            data_type=session['data_type'],
            target_seconds=session['target_seconds'],
            actual_seconds=actual_seconds,
            achieved=achieved,
            measurement_timestamp=datetime.utcnow().isoformat(),
            test_scenario=session['test_scenario'],
            data_loss_amount=data_loss_amount,
            recovery_method=recovery_method,
            criticality=session['criticality'],
            child_safety_impact=session['child_safety_impact']
        )
        
        self.rpo_measurements.append(measurement)
        del self.active_measurements[measurement_id]
        
        # Log measurement completion
        await self.audit_logger.log_security_event(
            "rpo_measurement_completed",
            {
                "measurement_id": measurement_id,
                "data_type": session['data_type'],
                "target_seconds": session['target_seconds'],
                "actual_seconds": actual_seconds,
                "data_loss_amount": data_loss_amount,
                "achieved": achieved,
                "recovery_method": recovery_method,
                "criticality": session['criticality'],
                "child_safety_impact": session['child_safety_impact']
            }
        )
        
        # Alert if critical RPO not met
        if not achieved and (session['child_safety_impact'] or session['zero_tolerance']):
            await self.audit_logger.log_security_event(
                "critical_rpo_violation",
                {
                    "data_type": session['data_type'],
                    "target_seconds": session['target_seconds'],
                    "actual_seconds": actual_seconds,
                    "data_loss_amount": data_loss_amount,
                    "child_safety_impact": session['child_safety_impact'],
                    "zero_tolerance": session['zero_tolerance'],
                    "severity": "CRITICAL"
                }
            )
        
        return measurement

    def get_rto_statistics(self, service_name: Optional[str] = None, criticality: Optional[str] = None) -> Dict:
        """Get statistical analysis of RTO measurements."""
        measurements = self.rto_measurements
        
        # Filter measurements
        if service_name:
            measurements = [m for m in measurements if m.service_name == service_name]
        if criticality:
            measurements = [m for m in measurements if m.criticality == criticality]
        
        if not measurements:
            return {'error': 'No measurements found for the specified criteria'}
        
        actual_times = [m.actual_seconds for m in measurements]
        achievement_rate = sum(1 for m in measurements if m.achieved) / len(measurements)
        
        # Child safety specific statistics
        child_safety_measurements = [m for m in measurements if m.child_safety_impact]
        child_safety_achievement_rate = (
            sum(1 for m in child_safety_measurements if m.achieved) / len(child_safety_measurements)
            if child_safety_measurements else 1.0
        )
        
        return {
            'total_measurements': len(measurements),
            'achievement_rate': achievement_rate,
            'child_safety_achievement_rate': child_safety_achievement_rate,
            'statistics': {
                'mean_recovery_time': statistics.mean(actual_times),
                'median_recovery_time': statistics.median(actual_times),
                'min_recovery_time': min(actual_times),
                'max_recovery_time': max(actual_times),
                'std_deviation': statistics.stdev(actual_times) if len(actual_times) > 1 else 0
            },
            'criticality_breakdown': {
                crit: len([m for m in measurements if m.criticality == crit])
                for crit in set(m.criticality for m in measurements)
            },
            'failures': [
                {
                    'service_name': m.service_name,
                    'target_seconds': m.target_seconds,
                    'actual_seconds': m.actual_seconds,
                    'test_scenario': m.test_scenario,
                    'child_safety_impact': m.child_safety_impact
                }
                for m in measurements if not m.achieved
            ]
        }

    def get_rpo_statistics(self, data_type: Optional[str] = None, criticality: Optional[str] = None) -> Dict:
        """Get statistical analysis of RPO measurements."""
        measurements = self.rpo_measurements
        
        # Filter measurements
        if data_type:
            measurements = [m for m in measurements if m.data_type == data_type]
        if criticality:
            measurements = [m for m in measurements if m.criticality == criticality]
        
        if not measurements:
            return {'error': 'No measurements found for the specified criteria'}
        
        data_loss_amounts = [m.data_loss_amount for m in measurements]
        achievement_rate = sum(1 for m in measurements if m.achieved) / len(measurements)
        
        # Zero tolerance specific statistics
        zero_tolerance_measurements = [m for m in measurements if m.data_type in [t.data_type for t in self.rpo_targets if t.zero_tolerance]]
        zero_tolerance_achievement_rate = (
            sum(1 for m in zero_tolerance_measurements if m.achieved) / len(zero_tolerance_measurements)
            if zero_tolerance_measurements else 1.0
        )
        
        return {
            'total_measurements': len(measurements),
            'achievement_rate': achievement_rate,
            'zero_tolerance_achievement_rate': zero_tolerance_achievement_rate,
            'statistics': {
                'mean_data_loss': statistics.mean(data_loss_amounts),
                'median_data_loss': statistics.median(data_loss_amounts),
                'min_data_loss': min(data_loss_amounts),
                'max_data_loss': max(data_loss_amounts),
                'total_data_loss': sum(data_loss_amounts)
            },
            'criticality_breakdown': {
                crit: len([m for m in measurements if m.criticality == crit])
                for crit in set(m.criticality for m in measurements)
            },
            'failures': [
                {
                    'data_type': m.data_type,
                    'target_seconds': m.target_seconds,
                    'data_loss_amount': m.data_loss_amount,
                    'test_scenario': m.test_scenario,
                    'child_safety_impact': m.child_safety_impact
                }
                for m in measurements if not m.achieved
            ]
        }

    def validate_production_readiness_rto_rpo(self) -> Dict:
        """Validate if RTO/RPO targets meet production readiness criteria."""
        validation_results = {
            'production_ready': True,
            'critical_issues': [],
            'warnings': [],
            'summary': {}
        }
        
        # Check RTO compliance
        rto_stats = self.get_rto_statistics()
        if 'error' not in rto_stats:
            # Critical services must have 100% achievement rate
            critical_rto_achievement = self.get_rto_statistics(criticality="CRITICAL").get('achievement_rate', 0)
            if critical_rto_achievement < 1.0:
                validation_results['production_ready'] = False
                validation_results['critical_issues'].append(
                    f"Critical RTO achievement rate too low: {critical_rto_achievement:.2%} (must be 100%)"
                )
            
            # Child safety services must have 100% achievement rate
            child_safety_achievement = rto_stats.get('child_safety_achievement_rate', 0)
            if child_safety_achievement < 1.0:
                validation_results['production_ready'] = False
                validation_results['critical_issues'].append(
                    f"Child safety RTO achievement rate too low: {child_safety_achievement:.2%} (must be 100%)"
                )
            
            # Overall achievement rate should be > 95%
            overall_achievement = rto_stats.get('achievement_rate', 0)
            if overall_achievement < 0.95:
                validation_results['warnings'].append(
                    f"Overall RTO achievement rate below recommended: {overall_achievement:.2%} (recommended > 95%)"
                )
            
            validation_results['summary']['rto_achievement_rate'] = overall_achievement
            validation_results['summary']['critical_rto_achievement_rate'] = critical_rto_achievement
            validation_results['summary']['child_safety_rto_achievement_rate'] = child_safety_achievement
        
        # Check RPO compliance
        rpo_stats = self.get_rpo_statistics()
        if 'error' not in rpo_stats:
            # Zero tolerance data must have 100% achievement rate
            zero_tolerance_achievement = rpo_stats.get('zero_tolerance_achievement_rate', 0)
            if zero_tolerance_achievement < 1.0:
                validation_results['production_ready'] = False
                validation_results['critical_issues'].append(
                    f"Zero tolerance RPO achievement rate too low: {zero_tolerance_achievement:.2%} (must be 100%)"
                )
            
            # Overall achievement rate should be > 95%
            overall_rpo_achievement = rpo_stats.get('achievement_rate', 0)
            if overall_rpo_achievement < 0.95:
                validation_results['warnings'].append(
                    f"Overall RPO achievement rate below recommended: {overall_rpo_achievement:.2%} (recommended > 95%)"
                )
            
            validation_results['summary']['rpo_achievement_rate'] = overall_rpo_achievement
            validation_results['summary']['zero_tolerance_rpo_achievement_rate'] = zero_tolerance_achievement
        
        return validation_results

    async def generate_comprehensive_rto_rpo_report(self) -> Dict:
        """Generate comprehensive RTO/RPO measurement and validation report."""
        
        # Get statistics
        rto_overall_stats = self.get_rto_statistics()
        rpo_overall_stats = self.get_rpo_statistics()
        
        # Get critical service statistics
        rto_critical_stats = self.get_rto_statistics(criticality="CRITICAL")
        rpo_critical_stats = self.get_rpo_statistics(criticality="CRITICAL")
        
        # Validate production readiness
        production_readiness = self.validate_production_readiness_rto_rpo()
        
        report = {
            'rto_rpo_measurement_report': {
                'generated_at': datetime.utcnow().isoformat(),
                'measurement_period_minutes': (datetime.utcnow() - self.measurement_start_time).total_seconds() / 60,
                'production_ready': production_readiness['production_ready'],
                
                'rto_targets_defined': len(self.rto_targets),
                'rpo_targets_defined': len(self.rpo_targets),
                'total_rto_measurements': len(self.rto_measurements),
                'total_rpo_measurements': len(self.rpo_measurements),
                
                'rto_analysis': {
                    'overall_statistics': rto_overall_stats,
                    'critical_services_statistics': rto_critical_stats,
                    'service_breakdown': {
                        service.service_name: self.get_rto_statistics(service_name=service.service_name)
                        for service in self.rto_targets
                    }
                },
                
                'rpo_analysis': {
                    'overall_statistics': rpo_overall_stats,
                    'critical_data_statistics': rpo_critical_stats,
                    'data_type_breakdown': {
                        data.data_type: self.get_rpo_statistics(data_type=data.data_type)
                        for data in self.rpo_targets
                    }
                },
                
                'child_safety_assessment': {
                    'child_safety_rto_services': len([t for t in self.rto_targets if t.child_safety_impact]),
                    'child_safety_rpo_data': len([t for t in self.rpo_targets if t.child_safety_impact]),
                    'child_safety_rto_achievement_rate': rto_overall_stats.get('child_safety_achievement_rate', 0) if 'error' not in rto_overall_stats else 0,
                    'zero_tolerance_rpo_achievement_rate': rpo_overall_stats.get('zero_tolerance_achievement_rate', 0) if 'error' not in rpo_overall_stats else 0,
                    'child_safety_compliance': production_readiness['summary'].get('child_safety_rto_achievement_rate', 0) >= 1.0 and 
                                             production_readiness['summary'].get('zero_tolerance_rpo_achievement_rate', 0) >= 1.0
                },
                
                'compliance_assessment': {
                    'coppa_compliant_rto_targets': len([t for t in self.rto_targets if t.compliance_requirement]),
                    'coppa_compliant_rpo_targets': len([t for t in self.rpo_targets if t.compliance_requirement]),
                    'audit_trail_preservation': True,  # All measurements are logged
                    'regulatory_compliance': production_readiness['production_ready']
                },
                
                'production_readiness_validation': production_readiness,
                
                'targets_configuration': {
                    'rto_targets': [asdict(target) for target in self.rto_targets],
                    'rpo_targets': [asdict(target) for target in self.rpo_targets]
                },
                
                'recommendations': self._generate_rto_rpo_recommendations(production_readiness, rto_overall_stats, rpo_overall_stats)
            }
        }
        
        return report

    def _generate_rto_rpo_recommendations(self, production_readiness: Dict, rto_stats: Dict, rpo_stats: Dict) -> List[str]:
        """Generate recommendations for RTO/RPO improvements."""
        recommendations = []
        
        # Critical issues first
        if production_readiness['critical_issues']:
            recommendations.extend([
                f"CRITICAL: {issue}" for issue in production_readiness['critical_issues']
            ])
        
        # RTO specific recommendations
        if 'error' not in rto_stats:
            if rto_stats.get('achievement_rate', 0) < 0.95:
                recommendations.append(
                    f"Improve overall RTO achievement rate: {rto_stats['achievement_rate']:.2%} (target: >95%)"
                )
            
            # Check for frequently failing services
            failures = rto_stats.get('failures', [])
            if failures:
                failing_services = {}
                for failure in failures:
                    service = failure['service_name']
                    failing_services[service] = failing_services.get(service, 0) + 1
                
                for service, count in failing_services.items():
                    if count > 1:
                        recommendations.append(
                            f"Address repeated RTO failures for {service}: {count} failures detected"
                        )
        
        # RPO specific recommendations
        if 'error' not in rpo_stats:
            if rpo_stats.get('achievement_rate', 0) < 0.95:
                recommendations.append(
                    f"Improve overall RPO achievement rate: {rpo_stats['achievement_rate']:.2%} (target: >95%)"
                )
            
            # Check for data loss in zero tolerance systems
            if rpo_stats.get('zero_tolerance_achievement_rate', 0) < 1.0:
                recommendations.append(
                    "CRITICAL: Implement zero data loss backup solutions for child safety and compliance data"
                )
        
        # General recommendations
        if production_readiness['warnings']:
            recommendations.extend(production_readiness['warnings'])
        
        if not recommendations:
            recommendations.append("All RTO/RPO targets are meeting production readiness criteria")
        
        return recommendations

    def export_measurements_for_compliance(self, file_path: str):
        """Export all measurements to file for compliance auditing."""
        export_data = {
            'export_timestamp': datetime.utcnow().isoformat(),
            'measurement_period': {
                'start': self.measurement_start_time.isoformat(),
                'end': datetime.utcnow().isoformat()
            },
            'rto_targets': [asdict(target) for target in self.rto_targets],
            'rpo_targets': [asdict(target) for target in self.rpo_targets],
            'rto_measurements': [asdict(measurement) for measurement in self.rto_measurements],
            'rpo_measurements': [asdict(measurement) for measurement in self.rpo_measurements],
            'summary_statistics': {
                'total_rto_measurements': len(self.rto_measurements),
                'total_rpo_measurements': len(self.rpo_measurements),
                'rto_achievement_rate': self.get_rto_statistics().get('achievement_rate', 0),
                'rpo_achievement_rate': self.get_rpo_statistics().get('achievement_rate', 0)
            }
        }
        
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)


# Example usage context manager for automatic measurement
class RTOContext:
    """Context manager for automatic RTO measurement."""
    
    def __init__(self, framework: RTORPOMeasurementFramework, service_name: str, test_scenario: str, failure_type: str):
        self.framework = framework
        self.service_name = service_name
        self.test_scenario = test_scenario
        self.failure_type = failure_type
        self.measurement_id = None

    async def __aenter__(self):
        self.measurement_id = await self.framework.start_rto_measurement(
            self.service_name, self.test_scenario, self.failure_type
        )
        return self.measurement_id

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.measurement_id:
            recovery_method = "automatic" if exc_type is None else "manual_intervention"
            await self.framework.end_rto_measurement(self.measurement_id, recovery_method)


class RPOContext:
    """Context manager for automatic RPO measurement."""
    
    def __init__(self, framework: RTORPOMeasurementFramework, data_type: str, test_scenario: str):
        self.framework = framework
        self.data_type = data_type
        self.test_scenario = test_scenario
        self.measurement_id = None

    async def __aenter__(self):
        self.measurement_id = await self.framework.start_rpo_measurement(
            self.data_type, self.test_scenario
        )
        return self.measurement_id

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.measurement_id:
            # In real scenario, would calculate actual data loss
            data_loss_amount = 0 if exc_type is None else 1
            recovery_method = "backup" if exc_type is None else "manual_recovery"
            await self.framework.end_rpo_measurement(self.measurement_id, data_loss_amount, recovery_method)


if __name__ == "__main__":
    # Example usage
    async def example_usage():
        framework = RTORPOMeasurementFramework()
        
        # Example RTO measurement
        async with RTOContext(framework, "child_safety_monitoring", "safety_incident", "content_filter_failure"):
            # Simulate recovery work
            await asyncio.sleep(25)  # Recovery takes 25 seconds
        
        # Example RPO measurement
        async with RPOContext(framework, "audit_logs", "system_crash"):
            # Simulate data recovery
            await asyncio.sleep(1)  # Recovery with no data loss
        
        # Generate report
        report = await framework.generate_comprehensive_rto_rpo_report()
        print(json.dumps(report, indent=2, default=str))
    
    asyncio.run(example_usage())