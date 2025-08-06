#!/usr/bin/env python3
"""
AI Teddy Bear - Complete Load and Stability Test Suite Runner
============================================================

Comprehensive test execution orchestrator that runs all load and stability tests:
- Load testing with realistic child interactions
- Stress testing to find breaking points
- Database performance testing
- Failover and recovery testing
- 24-hour stability testing
- Child safety performance validation
- Real-time monitoring and reporting

This is the master script for production readiness validation.
"""

import asyncio
import time
import logging
import json
import argparse
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import signal
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from comprehensive_load_test import LoadTestOrchestrator
from database_stress_test import DatabaseStressTester, run_database_stress_tests
from failover_recovery_test import FailoverRecoveryOrchestrator, run_failover_recovery_tests
from performance_monitor import LoadTestMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('complete_load_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TestSuiteOrchestrator:
    """Orchestrates the complete load and stability test suite."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        self.interrupted = False
        
        # Test components
        self.load_orchestrator = None
        self.db_tester = None
        self.failover_orchestrator = None
        self.performance_monitor = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.interrupted = True
    
    async def initialize(self):
        """Initialize all test components."""
        logger.info("Initializing test suite components...")
        
        try:
            # Initialize load test orchestrator
            self.load_orchestrator = LoadTestOrchestrator(
                base_url=self.config.get("service_url", "http://localhost:8000")
            )
            await self.load_orchestrator.initialize()
            
            # Initialize database tester
            self.db_tester = DatabaseStressTester(
                database_url=self.config.get("database_url", "sqlite:///./ai_teddy_bear.db")
            )
            await self.db_tester.initialize()
            
            # Initialize failover orchestrator
            self.failover_orchestrator = FailoverRecoveryOrchestrator(
                service_url=self.config.get("service_url", "http://localhost:8000"),
                redis_url=self.config.get("redis_url", "redis://localhost:6379")
            )
            await self.failover_orchestrator.initialize()
            
            # Initialize performance monitor
            self.performance_monitor = LoadTestMonitor()
            
            logger.info("✅ All test components initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize test components: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup all test components."""
        logger.info("Cleaning up test components...")
        
        cleanup_tasks = []
        
        if self.load_orchestrator:
            cleanup_tasks.append(self.load_orchestrator.cleanup())
        
        if self.db_tester:
            cleanup_tasks.append(self.db_tester.cleanup())
        
        if self.failover_orchestrator:
            cleanup_tasks.append(self.failover_orchestrator.cleanup())
        
        if self.performance_monitor:
            cleanup_tasks.append(self.performance_monitor.stop_monitoring())
        
        # Execute cleanup in parallel
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        logger.info("✅ Cleanup completed")
    
    async def run_complete_test_suite(self) -> Dict[str, Any]:
        """Run the complete load and stability test suite."""
        self.start_time = time.time()
        logger.info("🚀 Starting Complete Load and Stability Test Suite")
        logger.info("="*80)
        
        try:
            # Start performance monitoring
            await self.performance_monitor.start_monitoring(show_dashboard=False)
            
            # Phase 1: Baseline Performance Tests
            if not self.interrupted:
                logger.info("📊 Phase 1: Baseline Performance Testing")
                await self._run_baseline_tests()
            
            # Phase 2: Load Testing
            if not self.interrupted and self.config.get("run_load_tests", True):
                logger.info("⚡ Phase 2: Load Testing")
                await self._run_load_tests()
            
            # Phase 3: Database Stress Testing
            if not self.interrupted and self.config.get("run_database_tests", True):
                logger.info("🗄️ Phase 3: Database Stress Testing")
                await self._run_database_tests()
            
            # Phase 4: Failover and Recovery Testing
            if not self.interrupted and self.config.get("run_failover_tests", True):
                logger.info("🔄 Phase 4: Failover and Recovery Testing")
                await self._run_failover_tests()
            
            # Phase 5: Stress Testing (Find Breaking Points)
            if not self.interrupted and self.config.get("run_stress_tests", True):
                logger.info("💥 Phase 5: Stress Testing")
                await self._run_stress_tests()
            
            # Phase 6: Child Safety Performance Testing
            if not self.interrupted and self.config.get("run_safety_tests", True):
                logger.info("🛡️ Phase 6: Child Safety Performance Testing")
                await self._run_child_safety_tests()
            
            # Phase 7: Stability Testing (if enabled)
            if not self.interrupted and self.config.get("run_stability_test", False):
                logger.info("⏰ Phase 7: Long-term Stability Testing")
                await self._run_stability_tests()
            
            self.end_time = time.time()
            
            # Generate comprehensive report
            final_report = await self._generate_final_report()
            
            return final_report
            
        except Exception as e:
            logger.error(f"❌ Test suite failed: {e}")
            raise
        finally:
            await self.performance_monitor.stop_monitoring()
    
    async def _run_baseline_tests(self):
        """Run baseline performance tests."""
        logger.info("Running baseline performance tests...")
        
        try:
            # Light load test to establish baseline
            baseline_metrics = await self.load_orchestrator.run_load_test(
                concurrent_users=50, 
                duration_minutes=2
            )
            
            self.test_results["baseline"] = {
                "status": "completed",
                "metrics": baseline_metrics,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Baseline test completed - {baseline_metrics.successful_requests}/{baseline_metrics.total_requests} successful")
            
        except Exception as e:
            logger.error(f"❌ Baseline tests failed: {e}")
            self.test_results["baseline"] = {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _run_load_tests(self):
        """Run comprehensive load tests."""
        logger.info("Running load tests with increasing load...")
        
        load_scenarios = [
            {"users": 100, "duration": 3, "name": "Light Load"},
            {"users": 250, "duration": 3, "name": "Medium Load"},
            {"users": 500, "duration": 3, "name": "Heavy Load"},
            {"users": 1000, "duration": 2, "name": "Peak Load"}
        ]
        
        load_results = []
        
        for scenario in load_scenarios:
            if self.interrupted:
                break
                
            logger.info(f"Running {scenario['name']}: {scenario['users']} users for {scenario['duration']} minutes")
            
            try:
                metrics = await self.load_orchestrator.run_load_test(
                    concurrent_users=scenario["users"],
                    duration_minutes=scenario["duration"]
                )
                
                scenario_result = {
                    "scenario": scenario,
                    "metrics": metrics,
                    "status": "completed",
                    "timestamp": datetime.now().isoformat()
                }
                
                load_results.append(scenario_result)
                
                # Brief cooldown between tests
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"❌ Load test {scenario['name']} failed: {e}")
                scenario_result = {
                    "scenario": scenario,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                load_results.append(scenario_result)
        
        self.test_results["load_tests"] = load_results
        logger.info(f"✅ Load tests completed - {len(load_results)} scenarios executed")
    
    async def _run_database_tests(self):
        """Run database stress tests."""
        logger.info("Running database stress tests...")
        
        try:
            # Connection pool test
            pool_metrics = await self.db_tester.test_connection_pool_efficiency(300)
            
            # Query performance test
            query_metrics = await self.db_tester.test_query_performance_under_load(500)
            
            # Transaction isolation test
            isolation_results = await self.db_tester.test_transaction_isolation(100)
            
            # Connection recovery test
            recovery_results = await self.db_tester.test_connection_recovery(25)
            
            self.test_results["database_tests"] = {
                "connection_pool": pool_metrics,
                "query_performance": query_metrics,
                "transaction_isolation": isolation_results,
                "connection_recovery": recovery_results,
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("✅ Database stress tests completed")
            
        except Exception as e:
            logger.error(f"❌ Database tests failed: {e}")
            self.test_results["database_tests"] = {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _run_failover_tests(self):
        """Run failover and recovery tests."""
        logger.info("Running failover and recovery tests...")
        
        try:
            failover_results = await self.failover_orchestrator.run_comprehensive_failover_tests()
            
            self.test_results["failover_tests"] = {
                **failover_results,
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("✅ Failover and recovery tests completed")
            
        except Exception as e:
            logger.error(f"❌ Failover tests failed: {e}")
            self.test_results["failover_tests"] = {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _run_stress_tests(self):
        """Run stress tests to find breaking points."""
        logger.info("Running stress tests to find system breaking points...")
        
        try:
            stress_results = await self.load_orchestrator.run_stress_test()
            
            self.test_results["stress_tests"] = {
                **stress_results,
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Stress tests completed - Breaking point: {stress_results.get('max_concurrent_users', 'Not reached')} users")
            
        except Exception as e:
            logger.error(f"❌ Stress tests failed: {e}")
            self.test_results["stress_tests"] = {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _run_child_safety_tests(self):
        """Run child safety performance tests."""
        logger.info("Running child safety performance tests...")
        
        try:
            safety_results = await self.load_orchestrator.run_child_safety_tests()
            
            self.test_results["child_safety_tests"] = {
                **safety_results,
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("✅ Child safety performance tests completed")
            
        except Exception as e:
            logger.error(f"❌ Child safety tests failed: {e}")
            self.test_results["child_safety_tests"] = {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _run_stability_tests(self):
        """Run long-term stability tests."""
        stability_hours = self.config.get("stability_test_hours", 24)
        logger.info(f"Running {stability_hours}-hour stability test...")
        
        try:
            stability_results = await self.load_orchestrator.run_stability_test(stability_hours)
            
            self.test_results["stability_tests"] = {
                **stability_results,
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Stability test completed after {stability_results.get('actual_duration_hours', 0):.2f} hours")
            
        except Exception as e:
            logger.error(f"❌ Stability tests failed: {e}")
            self.test_results["stability_tests"] = {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive final report."""
        logger.info("Generating comprehensive test report...")
        
        # Get performance monitoring report
        monitoring_report = self.performance_monitor.get_monitoring_report()
        
        # Calculate test suite statistics
        total_duration = (self.end_time - self.start_time) if self.end_time and self.start_time else 0
        
        completed_tests = sum(1 for result in self.test_results.values() 
                            if isinstance(result, dict) and result.get("status") == "completed")
        failed_tests = sum(1 for result in self.test_results.values() 
                         if isinstance(result, dict) and result.get("status") == "failed")
        
        # Production readiness assessment
        production_assessment = self._assess_production_readiness()
        
        final_report = {
            "test_suite_summary": {
                "start_time": datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
                "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
                "total_duration_minutes": total_duration / 60,
                "completed_tests": completed_tests,
                "failed_tests": failed_tests,
                "interrupted": self.interrupted,
                "success_rate": (completed_tests / (completed_tests + failed_tests) * 100) if (completed_tests + failed_tests) > 0 else 0
            },
            "test_results": self.test_results,
            "performance_monitoring": monitoring_report,
            "production_readiness": production_assessment,
            "detailed_analysis": self._analyze_test_results(),
            "recommendations": self._generate_recommendations()
        }
        
        # Save report
        report_filename = f"complete_load_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(final_report, f, indent=2, default=str)
        
        logger.info(f"📄 Comprehensive report saved to: {report_filename}")
        
        # Print summary
        self._print_final_summary(final_report)
        
        return final_report
    
    def _assess_production_readiness(self) -> Dict[str, Any]:
        """Assess production readiness based on test results."""
        assessment = {
            "overall_ready": False,
            "readiness_score": 0,
            "critical_issues": [],
            "warnings": [],
            "passed_criteria": [],
            "criteria_analysis": {}
        }
        
        score = 0
        max_score = 0
        
        # Load test criteria
        if "load_tests" in self.test_results:
            max_score += 20
            load_tests = self.test_results["load_tests"]
            
            if isinstance(load_tests, list):
                peak_load_test = None
                for test in load_tests:
                    if (isinstance(test, dict) and 
                        test.get("scenario", {}).get("name") == "Peak Load" and 
                        test.get("status") == "completed"):
                        peak_load_test = test
                        break
                
                if peak_load_test:
                    metrics = peak_load_test.get("metrics")
                    if hasattr(metrics, 'avg_response_time') and hasattr(metrics, 'error_rate'):
                        if metrics.avg_response_time < 0.5 and metrics.error_rate < 5:
                            score += 20
                            assessment["passed_criteria"].append("Peak load performance meets requirements")
                        else:
                            assessment["critical_issues"].append(f"Peak load performance issues: {metrics.avg_response_time:.3f}s response, {metrics.error_rate:.2f}% errors")
                    else:
                        assessment["warnings"].append("Peak load test metrics unavailable")
                else:
                    assessment["critical_issues"].append("Peak load test not completed successfully")
        
        # Database performance criteria
        if "database_tests" in self.test_results:
            max_score += 15
            db_tests = self.test_results["database_tests"]
            
            if isinstance(db_tests, dict) and db_tests.get("status") == "completed":
                query_perf = db_tests.get("query_performance")
                if hasattr(query_perf, 'avg_query_time') and query_perf.avg_query_time < 0.05:
                    score += 15
                    assessment["passed_criteria"].append("Database query performance meets requirements")
                else:
                    assessment["critical_issues"].append("Database query performance too slow")
            else:
                assessment["critical_issues"].append("Database tests not completed successfully")
        
        # Failover criteria
        if "failover_tests" in self.test_results:
            max_score += 15
            failover_tests = self.test_results["failover_tests"]
            
            if isinstance(failover_tests, dict) and failover_tests.get("status") == "completed":
                summary = failover_tests.get("summary", {})
                if summary.get("successful_recoveries", 0) == summary.get("total_tests", 1):
                    score += 15
                    assessment["passed_criteria"].append("All failover scenarios recovered successfully")
                else:
                    assessment["critical_issues"].append("Failover recovery issues detected")
            else:
                assessment["warnings"].append("Failover tests not completed")
        
        # Child safety criteria
        if "child_safety_tests" in self.test_results:
            max_score += 25
            safety_tests = self.test_results["child_safety_tests"]
            
            if isinstance(safety_tests, dict) and safety_tests.get("status") == "completed":
                content_filtering = safety_tests.get("content_filtering", {})
                if content_filtering.get("requests_per_second", 0) > 100:
                    score += 25
                    assessment["passed_criteria"].append("Child safety systems perform well under load")
                else:
                    assessment["critical_issues"].append("Child safety system performance inadequate")
            else:
                assessment["critical_issues"].append("Child safety tests not completed")
        
        # Stress test criteria
        if "stress_tests" in self.test_results:
            max_score += 15
            stress_tests = self.test_results["stress_tests"]
            
            if isinstance(stress_tests, dict) and stress_tests.get("status") == "completed":
                max_users = stress_tests.get("max_concurrent_users", 0)
                if max_users >= 500:
                    score += 15
                    assessment["passed_criteria"].append(f"System handles {max_users} concurrent users")
                else:
                    assessment["warnings"].append(f"System capacity limited to {max_users} concurrent users")
            else:
                assessment["warnings"].append("Stress tests not completed")
        
        # Stability criteria
        if "stability_tests" in self.test_results:
            max_score += 10
            stability_tests = self.test_results["stability_tests"]
            
            if isinstance(stability_tests, dict) and stability_tests.get("status") == "completed":
                if not stability_tests.get("memory_leak_detected") and not stability_tests.get("performance_degradation"):
                    score += 10
                    assessment["passed_criteria"].append("System stable during extended operation")
                else:
                    assessment["critical_issues"].append("Stability issues detected during long-term testing")
        
        # Calculate final score
        assessment["readiness_score"] = (score / max_score * 100) if max_score > 0 else 0
        assessment["overall_ready"] = (
            assessment["readiness_score"] >= 80 and 
            len(assessment["critical_issues"]) == 0
        )
        
        return assessment
    
    def _analyze_test_results(self) -> Dict[str, Any]:
        """Analyze test results for patterns and insights."""
        analysis = {
            "performance_trends": {},
            "bottlenecks_identified": [],
            "scalability_analysis": {},
            "reliability_metrics": {}
        }
        
        # Analyze load test progression
        if "load_tests" in self.test_results and isinstance(self.test_results["load_tests"], list):
            response_times = []
            error_rates = []
            user_counts = []
            
            for test in self.test_results["load_tests"]:
                if test.get("status") == "completed" and hasattr(test.get("metrics"), "avg_response_time"):
                    metrics = test["metrics"]
                    response_times.append(metrics.avg_response_time)
                    error_rates.append(metrics.error_rate)
                    user_counts.append(test["scenario"]["users"])
            
            if len(response_times) > 1:
                # Check if response time increases with load
                if response_times[-1] > response_times[0] * 2:
                    analysis["bottlenecks_identified"].append("Response time degrades significantly under high load")
                
                # Check scalability
                if len(user_counts) >= 2:
                    throughput_efficiency = (user_counts[-1] / user_counts[0]) / (response_times[-1] / response_times[0])
                    analysis["scalability_analysis"]["throughput_efficiency"] = throughput_efficiency
                    
                    if throughput_efficiency < 0.5:
                        analysis["bottlenecks_identified"].append("Poor scalability - throughput doesn't scale with load")
        
        return analysis
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Performance recommendations
        if "load_tests" in self.test_results:
            for test in self.test_results["load_tests"]:
                if (test.get("status") == "completed" and 
                    hasattr(test.get("metrics"), "avg_response_time")):
                    metrics = test["metrics"]
                    
                    if metrics.avg_response_time > 0.5:
                        recommendations.append("Optimize API endpoints - response times exceed 500ms under load")
                    
                    if metrics.error_rate > 5:
                        recommendations.append("Address error handling - error rate exceeds 5% under load")
        
        # Database recommendations
        if "database_tests" in self.test_results:
            db_tests = self.test_results["database_tests"]
            if isinstance(db_tests, dict) and db_tests.get("status") == "completed":
                query_perf = db_tests.get("query_performance")
                if hasattr(query_perf, 'avg_query_time') and query_perf.avg_query_time > 0.05:
                    recommendations.append("Database query optimization needed - average query time > 50ms")
        
        # Child safety recommendations
        if "child_safety_tests" in self.test_results:
            safety_tests = self.test_results["child_safety_tests"]
            if isinstance(safety_tests, dict) and safety_tests.get("status") == "completed":
                session_isolation = safety_tests.get("session_isolation", {})
                if session_isolation.get("isolation_violations", 0) > 0:
                    recommendations.append("CRITICAL: Fix session isolation violations for COPPA compliance")
        
        # Capacity recommendations
        if "stress_tests" in self.test_results:
            stress_tests = self.test_results["stress_tests"]
            if isinstance(stress_tests, dict):
                max_users = stress_tests.get("max_concurrent_users", 0)
                if max_users < 1000:
                    recommendations.append(f"Consider scaling infrastructure - current capacity: {max_users} concurrent users")
        
        # General recommendations
        recommendations.extend([
            "Implement comprehensive monitoring and alerting for production",
            "Set up automated performance regression testing in CI/CD",
            "Plan for gradual capacity scaling based on user growth",
            "Establish performance SLAs and monitoring dashboards",
            "Regular load testing should be part of deployment process"
        ])
        
        return recommendations
    
    def _print_final_summary(self, report: Dict[str, Any]):
        """Print comprehensive test summary."""
        print("\n" + "="*80)
        print("🎯 AI TEDDY BEAR - COMPLETE LOAD AND STABILITY TEST SUMMARY")
        print("="*80)
        
        summary = report["test_suite_summary"]
        assessment = report["production_readiness"]
        
        print(f"📅 Test Duration: {summary['total_duration_minutes']:.1f} minutes")
        print(f"✅ Completed Tests: {summary['completed_tests']}")
        print(f"❌ Failed Tests: {summary['failed_tests']}")
        print(f"📊 Success Rate: {summary['success_rate']:.1f}%")
        
        if summary.get("interrupted"):
            print("⚠️ Test suite was interrupted")
        
        print(f"\n🎯 PRODUCTION READINESS SCORE: {assessment['readiness_score']:.1f}/100")
        
        if assessment["overall_ready"]:
            print("✅ SYSTEM IS PRODUCTION READY!")
        else:
            print("❌ SYSTEM NEEDS OPTIMIZATION BEFORE PRODUCTION")
        
        print(f"\n✅ Passed Criteria ({len(assessment['passed_criteria'])}):")
        for criteria in assessment["passed_criteria"]:
            print(f"  • {criteria}")
        
        if assessment["critical_issues"]:
            print(f"\n❌ Critical Issues ({len(assessment['critical_issues'])}):")
            for issue in assessment["critical_issues"]:
                print(f"  • {issue}")
        
        if assessment["warnings"]:
            print(f"\n⚠️ Warnings ({len(assessment['warnings'])}):")
            for warning in assessment["warnings"]:
                print(f"  • {warning}")
        
        print(f"\n🔧 Top Recommendations:")
        for i, rec in enumerate(report["recommendations"][:5], 1):
            print(f"  {i}. {rec}")
        
        print("\n" + "="*80)

def create_test_config(args) -> Dict[str, Any]:
    """Create test configuration from command line arguments."""
    return {
        "service_url": args.service_url,
        "database_url": args.database_url,
        "redis_url": args.redis_url,
        "run_load_tests": not args.skip_load_tests,
        "run_database_tests": not args.skip_database_tests,
        "run_failover_tests": not args.skip_failover_tests,
        "run_stress_tests": not args.skip_stress_tests,
        "run_safety_tests": not args.skip_safety_tests,
        "run_stability_test": args.run_stability_test,
        "stability_test_hours": args.stability_hours
    }

async def main():
    """Main entry point for the complete test suite."""
    parser = argparse.ArgumentParser(
        description="AI Teddy Bear - Complete Load and Stability Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full test suite (except 24h stability)
  python run_complete_load_tests.py
  
  # Run with custom service URL
  python run_complete_load_tests.py --service-url http://staging.example.com
  
  # Run only load and database tests
  python run_complete_load_tests.py --skip-failover-tests --skip-stress-tests --skip-safety-tests
  
  # Run with 1-hour stability test
  python run_complete_load_tests.py --run-stability-test --stability-hours 1
        """
    )
    
    parser.add_argument(
        "--service-url",
        default="http://localhost:8000",
        help="Base URL of the service to test (default: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--database-url",
        default="sqlite:///./ai_teddy_bear.db",
        help="Database URL for testing (default: sqlite:///./ai_teddy_bear.db)"
    )
    
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379",
        help="Redis URL for testing (default: redis://localhost:6379)"
    )
    
    parser.add_argument(
        "--skip-load-tests",
        action="store_true",
        help="Skip load testing phase"
    )
    
    parser.add_argument(
        "--skip-database-tests",
        action="store_true",
        help="Skip database stress testing phase"
    )
    
    parser.add_argument(
        "--skip-failover-tests",
        action="store_true",
        help="Skip failover and recovery testing phase"
    )
    
    parser.add_argument(
        "--skip-stress-tests",
        action="store_true",
        help="Skip stress testing phase"
    )
    
    parser.add_argument(
        "--skip-safety-tests",
        action="store_true",
        help="Skip child safety performance testing phase"
    )
    
    parser.add_argument(
        "--run-stability-test",
        action="store_true",
        help="Run long-term stability test (WARNING: Takes many hours)"
    )
    
    parser.add_argument(
        "--stability-hours",
        type=float,
        default=24.0,
        help="Duration of stability test in hours (default: 24)"
    )
    
    args = parser.parse_args()
    
    # Create test configuration
    config = create_test_config(args)
    
    print("🚀 AI Teddy Bear - Complete Load and Stability Test Suite")
    print("="*60)
    print("This comprehensive test suite will validate production readiness by testing:")
    print("• Load handling with realistic child interactions")
    print("• Database performance under concurrent access")
    print("• System resilience and recovery capabilities")
    print("• Child safety system performance (COPPA compliance)")
    print("• System breaking points and capacity limits")
    
    if config["run_stability_test"]:
        print(f"• Long-term stability ({config['stability_test_hours']} hours)")
        print("\n⚠️  WARNING: Stability test will run for a VERY LONG TIME!")
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() != "yes":
            print("Test suite cancelled.")
            return
    
    print(f"\nTarget System: {config['service_url']}")
    print(f"Database: {config['database_url']}")
    print(f"Redis: {config['redis_url']}")
    print("\nStarting in 5 seconds... (Ctrl+C to cancel)")
    
    try:
        await asyncio.sleep(5)
    except KeyboardInterrupt:
        print("\nTest suite cancelled.")
        return
    
    # Initialize and run test suite
    orchestrator = TestSuiteOrchestrator(config)
    
    try:
        await orchestrator.initialize()
        final_report = await orchestrator.run_complete_test_suite()
        
        # Return appropriate exit code
        if final_report["production_readiness"]["overall_ready"]:
            print("\n🎉 All tests passed - System is PRODUCTION READY!")
            sys.exit(0)
        else:
            print("\n⚠️ System needs optimization before production deployment")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Test suite interrupted by user")
        print("\n⚠️ Test suite interrupted. Partial results may be available in log files.")
        sys.exit(2)
    except Exception as e:
        logger.error(f"Test suite failed with error: {e}")
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(3)
    finally:
        await orchestrator.cleanup()

if __name__ == "__main__":
    asyncio.run(main())