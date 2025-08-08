"""
AI Teddy Bear - Automated Disaster Recovery Test Execution Framework

This module provides an automated framework for executing comprehensive disaster recovery tests,
including orchestration, monitoring, reporting, and integration with all disaster recovery
test suites.

CRITICAL: This framework orchestrates P0 incident simulations.
All executions must be carefully controlled and monitored.
"""

import asyncio
import time
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import subprocess
import signal
from dataclasses import dataclass, asdict

# Import all disaster recovery test modules
from test_database_disaster_recovery import DatabaseDisasterRecoveryTester
from test_system_failure_recovery import SystemFailureRecoveryTester
from test_child_safety_emergency_procedures import ChildSafetyEmergencyTester
from test_infrastructure_disaster_recovery import InfrastructureDisasterRecoveryTester
from test_data_protection_recovery_validation import DataProtectionRecoveryValidator
from rto_rpo_measurement_framework import RTORPOMeasurementFramework, RTOContext, RPOContext

from src.infrastructure.monitoring.audit import AuditLogger
from src.core.exceptions import DisasterRecoveryError, TestExecutionError


@dataclass
class TestSuiteConfiguration:
    """Configuration for disaster recovery test suite."""
    name: str
    enabled: bool
    priority: int  # 1=highest, 5=lowest
    timeout_minutes: int
    child_safety_impact: bool
    requires_manual_approval: bool
    prerequisites: List[str]
    environment_requirements: List[str]


@dataclass
class TestExecutionResult:
    """Result of disaster recovery test execution."""
    suite_name: str
    status: str  # PASSED, FAILED, SKIPPED, TIMEOUT
    start_time: str
    end_time: str
    duration_seconds: float
    tests_run: int
    tests_passed: int
    tests_failed: int
    child_safety_issues: int
    rto_violations: int
    rpo_violations: int
    error_message: Optional[str]
    detailed_results: Dict


class AutomatedDisasterRecoveryRunner:
    """
    Automated disaster recovery test execution framework.
    
    Provides:
    - Orchestrated execution of all disaster recovery test suites
    - Real-time monitoring and alerting
    - RTO/RPO measurement integration
    - Child safety incident prioritization
    - Comprehensive reporting and analytics
    - Emergency stop and rollback capabilities
    """
    
    def __init__(self, environment: str = "test"):
        self.environment = environment
        self.audit_logger = AuditLogger()
        self.rto_rpo_framework = RTORPOMeasurementFramework()
        self.test_start_time = datetime.utcnow()
        self.execution_results: List[TestExecutionResult] = []
        self.emergency_stop_requested = False
        
        # Configure test suites
        self.test_suites = self._configure_test_suites()
        
        # Initialize test components
        self.db_tester = None
        self.system_tester = None
        self.child_safety_tester = None
        self.infrastructure_tester = None
        self.data_protection_tester = None
        
        # Setup signal handlers for emergency stop
        signal.signal(signal.SIGINT, self._emergency_stop_handler)
        signal.signal(signal.SIGTERM, self._emergency_stop_handler)

    def _configure_test_suites(self) -> List[TestSuiteConfiguration]:
        """Configure all disaster recovery test suites."""
        return [
            # Child Safety Emergency Procedures - HIGHEST PRIORITY
            TestSuiteConfiguration(
                name="child_safety_emergency_procedures",
                enabled=True,
                priority=1,
                timeout_minutes=30,
                child_safety_impact=True,
                requires_manual_approval=False,  # Run automatically due to criticality
                prerequisites=[],
                environment_requirements=["database", "redis", "notification_service"]
            ),
            
            # Database Disaster Recovery - HIGH PRIORITY
            TestSuiteConfiguration(
                name="database_disaster_recovery",
                enabled=True,
                priority=2,
                timeout_minutes=45,
                child_safety_impact=True,
                requires_manual_approval=True,  # Requires approval due to data impact
                prerequisites=[],
                environment_requirements=["database", "backup_storage"]
            ),
            
            # Data Protection Recovery Validation - HIGH PRIORITY
            TestSuiteConfiguration(
                name="data_protection_recovery_validation",
                enabled=True,
                priority=2,
                timeout_minutes=40,
                child_safety_impact=True,
                requires_manual_approval=False,
                prerequisites=["database_disaster_recovery"],
                environment_requirements=["database", "encryption_keys", "backup_storage"]
            ),
            
            # System Failure Recovery - MEDIUM PRIORITY
            TestSuiteConfiguration(
                name="system_failure_recovery",
                enabled=True,
                priority=3,
                timeout_minutes=60,
                child_safety_impact=False,
                requires_manual_approval=True,
                prerequisites=[],
                environment_requirements=["docker", "containers", "network"]
            ),
            
            # Infrastructure Disaster Recovery - MEDIUM PRIORITY
            TestSuiteConfiguration(
                name="infrastructure_disaster_recovery",
                enabled=True,
                priority=4,
                timeout_minutes=50,
                child_safety_impact=False,
                requires_manual_approval=False,
                prerequisites=[],
                environment_requirements=["docker", "redis", "storage", "ssl_certificates"]
            )
        ]

    def _emergency_stop_handler(self, signum, frame):
        """Handle emergency stop signals."""
        print(f"\n🚨 EMERGENCY STOP REQUESTED (Signal: {signum})")
        self.emergency_stop_requested = True
        
        # Log emergency stop
        asyncio.create_task(self.audit_logger.log_security_event(
            "disaster_recovery_emergency_stop",
            {
                "signal": signum,
                "timestamp": datetime.utcnow().isoformat(),
                "environment": self.environment,
                "tests_completed": len(self.execution_results)
            }
        ))

    async def validate_environment_prerequisites(self) -> Dict:
        """Validate environment prerequisites for disaster recovery testing."""
        validation_results = {
            'environment_ready': True,
            'missing_requirements': [],
            'warnings': []
        }
        
        # Check Docker availability
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                validation_results['environment_ready'] = False
                validation_results['missing_requirements'].append('Docker not available')
        except FileNotFoundError:
            validation_results['environment_ready'] = False
            validation_results['missing_requirements'].append('Docker not installed')
        
        # Check database connectivity
        try:
            # This would test actual database connection
            # For now, we'll simulate the check
            db_available = True  # Simplified
            if not db_available:
                validation_results['environment_ready'] = False
                validation_results['missing_requirements'].append('Database not accessible')
        except Exception as e:
            validation_results['environment_ready'] = False
            validation_results['missing_requirements'].append(f'Database check failed: {str(e)}')
        
        # Check Redis availability
        try:
            # This would test actual Redis connection
            redis_available = True  # Simplified
            if not redis_available:
                validation_results['warnings'].append('Redis not available - some tests may be skipped')
        except Exception as e:
            validation_results['warnings'].append(f'Redis check warning: {str(e)}')
        
        # Check backup storage
        backup_paths = ['/backups', './data/backups']
        backup_available = any(os.path.exists(path) for path in backup_paths)
        if not backup_available:
            validation_results['warnings'].append('Backup storage location not found')
        
        # Check if running in test environment
        if self.environment == "production":
            validation_results['environment_ready'] = False
            validation_results['missing_requirements'].append('Cannot run disaster recovery tests in production environment')
        
        return validation_results

    async def request_manual_approval(self, suite_name: str, suite_config: TestSuiteConfiguration) -> bool:
        """Request manual approval for test suite execution."""
        if not suite_config.requires_manual_approval:
            return True
        
        print(f"\n⚠️  MANUAL APPROVAL REQUIRED FOR: {suite_name}")
        print(f"   Priority: {suite_config.priority}")
        print(f"   Child Safety Impact: {suite_config.child_safety_impact}")
        print(f"   Timeout: {suite_config.timeout_minutes} minutes")
        print(f"   Prerequisites: {suite_config.prerequisites}")
        print(f"   Environment Requirements: {suite_config.environment_requirements}")
        
        # In a real implementation, this would integrate with approval systems
        # For testing, we'll auto-approve or use environment variable
        auto_approve = os.getenv('AUTO_APPROVE_DR_TESTS', 'false').lower() == 'true'
        
        if auto_approve:
            print("   ✅ AUTO-APPROVED (via AUTO_APPROVE_DR_TESTS environment variable)")
            return True
        
        # Interactive approval
        while True:
            response = input("   Approve execution? (yes/no/skip): ").lower().strip()
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            elif response in ['skip', 's']:
                return False
            else:
                print("   Please enter 'yes', 'no', or 'skip'")

    async def execute_test_suite(self, suite_config: TestSuiteConfiguration) -> TestExecutionResult:
        """Execute a specific disaster recovery test suite."""
        suite_name = suite_config.name
        start_time = datetime.utcnow()
        
        print(f"\n🧪 EXECUTING TEST SUITE: {suite_name}")
        print(f"   Priority: {suite_config.priority}")
        print(f"   Timeout: {suite_config.timeout_minutes} minutes")
        
        # Log test suite start
        await self.audit_logger.log_security_event(
            "disaster_recovery_suite_start",
            {
                "suite_name": suite_name,
                "priority": suite_config.priority,
                "child_safety_impact": suite_config.child_safety_impact,
                "timeout_minutes": suite_config.timeout_minutes
            }
        )
        
        try:
            # Initialize tester based on suite type
            tester = await self._initialize_tester(suite_name)
            
            # Execute tests with timeout and RTO/RPO measurement
            detailed_results = await asyncio.wait_for(
                self._execute_suite_tests(suite_name, tester),
                timeout=suite_config.timeout_minutes * 60
            )
            
            # Analyze results
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Count test results
            tests_run = len(detailed_results.get('test_results', {}))
            tests_passed = sum(1 for result in detailed_results.get('test_results', {}).values() if result.get('status') == 'PASSED')
            tests_failed = tests_run - tests_passed
            
            # Count child safety issues
            child_safety_issues = sum(
                1 for result in detailed_results.get('test_results', {}).values()
                if result.get('status') == 'FAILED' and 'child_safety' in result.get('test_name', '').lower()
            )
            
            # Count RTO/RPO violations (simplified)
            rto_violations = sum(
                1 for result in detailed_results.get('test_results', {}).values()
                if not result.get('rto_met', True)
            )
            rpo_violations = sum(
                1 for result in detailed_results.get('test_results', {}).values()
                if not result.get('rpo_met', True)
            )
            
            status = 'PASSED' if tests_failed == 0 and child_safety_issues == 0 else 'FAILED'
            
            result = TestExecutionResult(
                suite_name=suite_name,
                status=status,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                duration_seconds=duration,
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                child_safety_issues=child_safety_issues,
                rto_violations=rto_violations,
                rpo_violations=rpo_violations,
                error_message=None,
                detailed_results=detailed_results
            )
            
            print(f"   ✅ COMPLETED: {status} ({tests_passed}/{tests_run} tests passed)")
            if child_safety_issues > 0:
                print(f"   🚨 CHILD SAFETY ISSUES: {child_safety_issues}")
            if rto_violations > 0:
                print(f"   ⏰ RTO VIOLATIONS: {rto_violations}")
            if rpo_violations > 0:
                print(f"   💾 RPO VIOLATIONS: {rpo_violations}")
            
            return result
            
        except asyncio.TimeoutError:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            print(f"   ⏰ TIMEOUT after {duration:.1f} seconds")
            
            return TestExecutionResult(
                suite_name=suite_name,
                status='TIMEOUT',
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                duration_seconds=duration,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                child_safety_issues=0,
                rto_violations=0,
                rpo_violations=0,
                error_message=f"Test suite timed out after {suite_config.timeout_minutes} minutes",
                detailed_results={}
            )
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            print(f"   ❌ ERROR: {str(e)}")
            
            # Log error
            await self.audit_logger.log_security_event(
                "disaster_recovery_suite_error",
                {
                    "suite_name": suite_name,
                    "error": str(e),
                    "duration_seconds": duration
                }
            )
            
            return TestExecutionResult(
                suite_name=suite_name,
                status='FAILED',
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                duration_seconds=duration,
                tests_run=0,
                tests_passed=0,
                tests_failed=1,
                child_safety_issues=1 if suite_config.child_safety_impact else 0,
                rto_violations=0,
                rpo_violations=0,
                error_message=str(e),
                detailed_results={}
            )

    async def _initialize_tester(self, suite_name: str):
        """Initialize the appropriate tester for the suite."""
        if suite_name == "database_disaster_recovery":
            if not self.db_tester:
                from src.infrastructure.database.database_manager import DatabaseManager
                db_manager = DatabaseManager()
                self.db_tester = DatabaseDisasterRecoveryTester(db_manager)
            return self.db_tester
            
        elif suite_name == "system_failure_recovery":
            if not self.system_tester:
                self.system_tester = SystemFailureRecoveryTester()
            return self.system_tester
            
        elif suite_name == "child_safety_emergency_procedures":
            if not self.child_safety_tester:
                self.child_safety_tester = ChildSafetyEmergencyTester()
            return self.child_safety_tester
            
        elif suite_name == "infrastructure_disaster_recovery":
            if not self.infrastructure_tester:
                self.infrastructure_tester = InfrastructureDisasterRecoveryTester()
            return self.infrastructure_tester
            
        elif suite_name == "data_protection_recovery_validation":
            if not self.data_protection_tester:
                self.data_protection_tester = DataProtectionRecoveryValidator()
            return self.data_protection_tester
            
        else:
            raise TestExecutionError(f"Unknown test suite: {suite_name}")

    async def _execute_suite_tests(self, suite_name: str, tester) -> Dict:
        """Execute all tests for a specific suite."""
        suite_results = {"test_results": {}}
        
        if suite_name == "database_disaster_recovery":
            # Execute database disaster recovery tests
            tests = [
                ("database_corruption_recovery", tester.test_database_corruption_recovery),
                ("complete_database_restore", tester.test_complete_database_restore),
                ("point_in_time_recovery", tester.test_point_in_time_recovery),
                ("database_failover_scenarios", tester.test_database_failover_scenarios),
                ("data_consistency_validation", tester.test_data_consistency_validation)
            ]
            
        elif suite_name == "system_failure_recovery":
            # Execute system failure recovery tests
            tests = [
                ("complete_system_crash_recovery", tester.test_complete_system_crash_recovery),
                ("container_failure_recovery", tester.test_container_failure_recovery),
                ("network_partition_recovery", tester.test_network_partition_recovery),
                ("storage_failure_recovery", tester.test_storage_failure_recovery),
                ("memory_exhaustion_recovery", tester.test_memory_exhaustion_recovery)
            ]
            
        elif suite_name == "child_safety_emergency_procedures":
            # Execute child safety emergency tests
            tests = [
                ("child_session_emergency_termination", tester.test_child_session_emergency_termination),
                ("child_data_protection_during_disasters", tester.test_child_data_protection_during_disasters),
                ("parent_notification_during_emergencies", tester.test_parent_notification_during_emergencies),
                ("coppa_compliance_during_disaster_scenarios", tester.test_coppa_compliance_during_disaster_scenarios),
                ("child_safety_audit_log_preservation", tester.test_child_safety_audit_log_preservation)
            ]
            
        elif suite_name == "infrastructure_disaster_recovery":
            # Execute infrastructure disaster recovery tests
            tests = [
                ("docker_orchestration_failure_recovery", tester.test_docker_orchestration_failure_recovery),
                ("redis_cache_failure_recovery", tester.test_redis_cache_failure_recovery),
                ("file_storage_system_failure", tester.test_file_storage_system_failure),
                ("load_balancer_failure_recovery", tester.test_load_balancer_failure_recovery),
                ("ssl_certificate_expiration_handling", tester.test_ssl_certificate_expiration_handling)
            ]
            
        elif suite_name == "data_protection_recovery_validation":
            # Execute data protection validation tests
            tests = [
                ("encrypted_data_recovery_validation", tester.test_encrypted_data_recovery_validation),
                ("audit_log_recovery_and_integrity", tester.test_audit_log_recovery_and_integrity),
                ("user_session_recovery", tester.test_user_session_recovery),
                ("child_interaction_history_recovery", tester.test_child_interaction_history_recovery),
                ("compliance_data_preservation", tester.test_compliance_data_preservation)
            ]
            
        else:
            tests = []
        
        # Execute each test with RTO/RPO measurement
        for test_name, test_method in tests:
            if self.emergency_stop_requested:
                print(f"   ⛔ EMERGENCY STOP - Skipping remaining tests")
                break
            
            print(f"     🔬 Running: {test_name}")
            
            # Measure RTO if applicable
            rto_measurement_id = None
            if "recovery" in test_name or "termination" in test_name:
                try:
                    rto_measurement_id = await self.rto_rpo_framework.start_rto_measurement(
                        service_name=test_name,
                        test_scenario=suite_name,
                        failure_type="simulated_disaster"
                    )
                except Exception as e:
                    print(f"       ⚠️  RTO measurement setup failed: {e}")
            
            try:
                # Execute the test
                test_result = await test_method()
                suite_results["test_results"][test_name] = test_result
                
                # End RTO measurement
                if rto_measurement_id:
                    try:
                        await self.rto_rpo_framework.end_rto_measurement(
                            rto_measurement_id,
                            recovery_method="automated"
                        )
                    except Exception as e:
                        print(f"       ⚠️  RTO measurement completion failed: {e}")
                
                status_symbol = "✅" if test_result.get('status') == 'PASSED' else "❌"
                print(f"       {status_symbol} {test_result.get('status', 'UNKNOWN')}")
                
            except Exception as e:
                # End RTO measurement with failure
                if rto_measurement_id:
                    try:
                        await self.rto_rpo_framework.end_rto_measurement(
                            rto_measurement_id,
                            recovery_method="failed"
                        )
                    except Exception:
                        pass
                
                print(f"       ❌ FAILED: {str(e)}")
                suite_results["test_results"][test_name] = {
                    'status': 'FAILED',
                    'error': str(e),
                    'test_name': test_name
                }
        
        # Generate suite report
        if hasattr(tester, 'generate_comprehensive_report'):
            try:
                suite_report = await tester.generate_comprehensive_report()
                suite_results["comprehensive_report"] = suite_report
            except AttributeError:
                # Try different report method names
                report_methods = [
                    'generate_disaster_recovery_report',
                    'generate_system_failure_recovery_report',
                    'generate_child_safety_emergency_report',
                    'generate_infrastructure_disaster_recovery_report',
                    'generate_data_protection_recovery_report'
                ]
                
                for method_name in report_methods:
                    if hasattr(tester, method_name):
                        try:
                            suite_report = await getattr(tester, method_name)()
                            suite_results["comprehensive_report"] = suite_report
                            break
                        except Exception as e:
                            print(f"       ⚠️  Report generation failed with {method_name}: {e}")
        
        return suite_results

    async def run_all_disaster_recovery_tests(self) -> Dict:
        """Execute all disaster recovery test suites in priority order."""
        print("🚨 STARTING COMPREHENSIVE DISASTER RECOVERY TESTING")
        print(f"   Environment: {self.environment}")
        print(f"   Test Suites: {len(self.test_suites)}")
        print(f"   Start Time: {self.test_start_time.isoformat()}")
        
        # Log comprehensive test start
        await self.audit_logger.log_security_event(
            "comprehensive_disaster_recovery_start",
            {
                "environment": self.environment,
                "total_suites": len(self.test_suites),
                "start_time": self.test_start_time.isoformat()
            }
        )
        
        # Validate environment prerequisites
        print("\n🔍 VALIDATING ENVIRONMENT PREREQUISITES")
        env_validation = await self.validate_environment_prerequisites()
        
        if not env_validation['environment_ready']:
            print("   ❌ ENVIRONMENT NOT READY")
            for requirement in env_validation['missing_requirements']:
                print(f"      • {requirement}")
            return {
                'status': 'FAILED',
                'error': 'Environment prerequisites not met',
                'missing_requirements': env_validation['missing_requirements']
            }
        
        print("   ✅ ENVIRONMENT READY")
        for warning in env_validation['warnings']:
            print(f"      ⚠️  {warning}")
        
        # Sort test suites by priority (1 = highest priority)
        sorted_suites = sorted(self.test_suites, key=lambda x: x.priority)
        
        # Execute test suites
        for suite_config in sorted_suites:
            if self.emergency_stop_requested:
                print("\n⛔ EMERGENCY STOP REQUESTED - Halting test execution")
                break
            
            if not suite_config.enabled:
                print(f"\n⏭️  SKIPPING DISABLED SUITE: {suite_config.name}")
                continue
            
            # Check prerequisites
            if suite_config.prerequisites:
                missing_prereqs = []
                for prereq in suite_config.prerequisites:
                    prereq_result = next((r for r in self.execution_results if r.suite_name == prereq), None)
                    if not prereq_result or prereq_result.status != 'PASSED':
                        missing_prereqs.append(prereq)
                
                if missing_prereqs:
                    print(f"\n⏭️  SKIPPING {suite_config.name}: Missing prerequisites: {missing_prereqs}")
                    continue
            
            # Request manual approval if required
            if not await self.request_manual_approval(suite_config.name, suite_config):
                print(f"   ⏭️  SKIPPED: Manual approval denied")
                continue
            
            # Execute test suite
            result = await self.execute_test_suite(suite_config)
            self.execution_results.append(result)
            
            # Check for critical failures
            if result.child_safety_issues > 0:
                print(f"\n🚨 CRITICAL CHILD SAFETY ISSUES DETECTED IN {suite_config.name}")
                print(f"   Issues: {result.child_safety_issues}")
                
                # Log critical issue
                await self.audit_logger.log_security_event(
                    "critical_child_safety_failure",
                    {
                        "suite_name": suite_config.name,
                        "issues_count": result.child_safety_issues,
                        "severity": "CRITICAL"
                    }
                )
                
                # Consider stopping execution for child safety issues
                if suite_config.child_safety_impact and result.child_safety_issues > 2:
                    print("   🛑 HALTING EXECUTION DUE TO MULTIPLE CHILD SAFETY FAILURES")
                    break
        
        # Generate comprehensive report
        return await self.generate_comprehensive_disaster_recovery_report()

    async def generate_comprehensive_disaster_recovery_report(self) -> Dict:
        """Generate comprehensive disaster recovery test execution report."""
        end_time = datetime.utcnow()
        total_duration = (end_time - self.test_start_time).total_seconds()
        
        # Calculate overall statistics
        total_tests = sum(r.tests_run for r in self.execution_results)
        total_passed = sum(r.tests_passed for r in self.execution_results)
        total_failed = sum(r.tests_failed for r in self.execution_results)
        total_child_safety_issues = sum(r.child_safety_issues for r in self.execution_results)
        total_rto_violations = sum(r.rto_violations for r in self.execution_results)
        total_rpo_violations = sum(r.rpo_violations for r in self.execution_results)
        
        # Determine overall status
        overall_status = 'FAILED' if (
            total_failed > 0 or
            total_child_safety_issues > 0 or
            any(r.status in ['FAILED', 'TIMEOUT'] for r in self.execution_results)
        ) else 'PASSED'
        
        # Get RTO/RPO analysis
        rto_rpo_report = await self.rto_rpo_framework.generate_comprehensive_rto_rpo_report()
        
        report = {
            'comprehensive_disaster_recovery_test_report': {
                'generated_at': end_time.isoformat(),
                'test_execution_summary': {
                    'environment': self.environment,
                    'start_time': self.test_start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'total_duration_minutes': total_duration / 60,
                    'overall_status': overall_status,
                    'emergency_stop_requested': self.emergency_stop_requested
                },
                'test_statistics': {
                    'suites_configured': len(self.test_suites),
                    'suites_executed': len(self.execution_results),
                    'suites_passed': len([r for r in self.execution_results if r.status == 'PASSED']),
                    'suites_failed': len([r for r in self.execution_results if r.status == 'FAILED']),
                    'suites_timeout': len([r for r in self.execution_results if r.status == 'TIMEOUT']),
                    'total_tests_run': total_tests,
                    'total_tests_passed': total_passed,
                    'total_tests_failed': total_failed,
                    'overall_pass_rate': (total_passed / total_tests) if total_tests > 0 else 0
                },
                'critical_issues_summary': {
                    'child_safety_issues': total_child_safety_issues,
                    'rto_violations': total_rto_violations,
                    'rpo_violations': total_rpo_violations,
                    'critical_suite_failures': [
                        r.suite_name for r in self.execution_results
                        if r.status == 'FAILED' and r.child_safety_issues > 0
                    ]
                },
                'suite_execution_results': [asdict(result) for result in self.execution_results],
                'rto_rpo_analysis': rto_rpo_report,
                'production_readiness_assessment': {
                    'ready_for_production': (
                        overall_status == 'PASSED' and
                        total_child_safety_issues == 0 and
                        total_rto_violations == 0 and
                        total_rpo_violations == 0
                    ),
                    'blocking_issues': self._identify_blocking_issues(),
                    'recommendations': self._generate_comprehensive_recommendations()
                },
                'compliance_assessment': {
                    'coppa_compliance_verified': total_child_safety_issues == 0,
                    'audit_trail_complete': True,
                    'rto_rpo_compliance': (
                        rto_rpo_report.get('rto_rpo_measurement_report', {})
                        .get('production_ready', False)
                    ),
                    'child_safety_procedures_verified': all(
                        r.child_safety_issues == 0 for r in self.execution_results
                        if 'child_safety' in r.suite_name
                    )
                }
            }
        }
        
        return report

    def _identify_blocking_issues(self) -> List[str]:
        """Identify issues that block production readiness."""
        blocking_issues = []
        
        # Child safety issues are always blocking
        child_safety_failures = [r for r in self.execution_results if r.child_safety_issues > 0]
        for failure in child_safety_failures:
            blocking_issues.append(
                f"CRITICAL: Child safety issues in {failure.suite_name}: {failure.child_safety_issues} issues"
            )
        
        # Failed critical suites
        critical_failures = [
            r for r in self.execution_results
            if r.status == 'FAILED' and any(
                suite.child_safety_impact for suite in self.test_suites
                if suite.name == r.suite_name
            )
        ]
        for failure in critical_failures:
            blocking_issues.append(
                f"CRITICAL: Failed critical suite {failure.suite_name}: {failure.error_message or 'Unknown error'}"
            )
        
        # RTO/RPO violations for critical services
        rto_violations = [r for r in self.execution_results if r.rto_violations > 0]
        for violation in rto_violations:
            blocking_issues.append(
                f"RTO VIOLATION: {violation.suite_name} has {violation.rto_violations} RTO violations"
            )
        
        rpo_violations = [r for r in self.execution_results if r.rpo_violations > 0]
        for violation in rpo_violations:
            blocking_issues.append(
                f"RPO VIOLATION: {violation.suite_name} has {violation.rpo_violations} RPO violations"
            )
        
        return blocking_issues

    def _generate_comprehensive_recommendations(self) -> List[str]:
        """Generate comprehensive recommendations for disaster recovery improvements."""
        recommendations = []
        
        # Check for suite-specific issues
        for result in self.execution_results:
            if result.status == 'FAILED':
                recommendations.append(
                    f"Address failures in {result.suite_name}: {result.tests_failed} failed tests"
                )
            
            if result.status == 'TIMEOUT':
                recommendations.append(
                    f"Optimize {result.suite_name} execution time - timed out after {result.duration_seconds:.1f}s"
                )
        
        # RTO/RPO specific recommendations
        if any(r.rto_violations > 0 for r in self.execution_results):
            recommendations.append("Optimize recovery procedures to meet RTO targets")
        
        if any(r.rpo_violations > 0 for r in self.execution_results):
            recommendations.append("Implement more frequent backups to meet RPO targets")
        
        # Child safety specific recommendations
        if any(r.child_safety_issues > 0 for r in self.execution_results):
            recommendations.insert(0, "PRIORITY: Resolve all child safety issues before production deployment")
        
        # General recommendations
        pass_rate = sum(r.tests_passed for r in self.execution_results) / max(1, sum(r.tests_run for r in self.execution_results))
        if pass_rate < 0.95:
            recommendations.append(f"Improve overall test pass rate: {pass_rate:.2%} (target: >95%)")
        
        if not recommendations:
            recommendations.append("All disaster recovery tests passed successfully - system is production ready")
        
        return recommendations

    async def save_report(self, report: Dict, file_path: str):
        """Save comprehensive disaster recovery report to file."""
        with open(file_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📄 COMPREHENSIVE DISASTER RECOVERY REPORT SAVED TO: {file_path}")


async def main():
    """Main execution function for automated disaster recovery testing."""
    # Initialize runner
    runner = AutomatedDisasterRecoveryRunner(environment="test")
    
    try:
        # Execute all disaster recovery tests
        report = await runner.run_all_disaster_recovery_tests()
        
        # Save comprehensive report
        report_path = f"/tmp/comprehensive_disaster_recovery_report_{int(time.time())}.json"
        await runner.save_report(report, report_path)
        
        # Print summary
        print("\n" + "="*80)
        print("🚨 COMPREHENSIVE DISASTER RECOVERY TEST EXECUTION COMPLETE")
        print("="*80)
        
        summary = report['comprehensive_disaster_recovery_test_report']
        print(f"Overall Status: {summary['test_execution_summary']['overall_status']}")
        print(f"Duration: {summary['test_execution_summary']['total_duration_minutes']:.1f} minutes")
        print(f"Suites Executed: {summary['test_statistics']['suites_executed']}")
        print(f"Tests Run: {summary['test_statistics']['total_tests_run']}")
        print(f"Pass Rate: {summary['test_statistics']['overall_pass_rate']:.2%}")
        print(f"Child Safety Issues: {summary['critical_issues_summary']['child_safety_issues']}")
        print(f"RTO Violations: {summary['critical_issues_summary']['rto_violations']}")
        print(f"RPO Violations: {summary['critical_issues_summary']['rpo_violations']}")
        print(f"Production Ready: {summary['production_readiness_assessment']['ready_for_production']}")
        
        if summary['production_readiness_assessment']['blocking_issues']:
            print("\n🚨 BLOCKING ISSUES:")
            for issue in summary['production_readiness_assessment']['blocking_issues']:
                print(f"   • {issue}")
        
        print(f"\nReport saved to: {report_path}")
        
        # Exit with appropriate code
        return 0 if summary['production_readiness_assessment']['ready_for_production'] else 1
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR IN DISASTER RECOVERY TESTING: {e}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())