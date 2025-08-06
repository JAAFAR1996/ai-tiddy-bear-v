"""
E2E Test Runner - Comprehensive Test Execution Manager
======================================================
Centralized test runner for all E2E test scenarios:
- Test suite orchestration
- Environment setup and teardown
- Parallel test execution
- Comprehensive reporting
- CI/CD integration
- Performance benchmarking
- Test data management
"""

import asyncio
import argparse
import sys
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Type
from pathlib import Path
import json
import importlib

from .base import E2ETestBase, E2ETestConfig, TestEnvironment
from .test_child_safety_coppa import ChildSafetyCOPPATests
from .test_production_api_flows import ProductionAPIFlowTests
from .test_security_performance import SecurityPerformanceTests
from .test_error_handling_edge_cases import ErrorHandlingEdgeCaseTests


class E2ETestRunner:
    """Comprehensive E2E test runner."""
    
    def __init__(self, config: E2ETestConfig):
        self.config = config
        self.test_suites: Dict[str, Type[E2ETestBase]] = {
            "child_safety": ChildSafetyCOPPATests,
            "production_flows": ProductionAPIFlowTests,
            "security_performance": SecurityPerformanceTests,
            "error_handling": ErrorHandlingEdgeCaseTests
        }
        
        self.results: Dict[str, Any] = {
            "start_time": None,
            "end_time": None,
            "total_duration": 0,
            "suite_results": {},
            "overall_summary": {}
        }
    
    async def run_all_tests(self, selected_suites: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run all or selected test suites."""
        self.results["start_time"] = datetime.now()
        
        suites_to_run = selected_suites or list(self.test_suites.keys())
        
        print(f"🚀 Starting E2E Test Runner")
        print(f"📊 Environment: {self.config.environment.value}")
        print(f"🎯 Test Suites: {', '.join(suites_to_run)}")
        print(f"🏁 Starting at: {self.results['start_time']}")
        print("=" * 80)
        
        # Run test suites
        for suite_name in suites_to_run:
            if suite_name in self.test_suites:
                print(f"\n🧪 Running {suite_name.replace('_', ' ').title()} Tests...")
                suite_result = await self._run_test_suite(suite_name)
                self.results["suite_results"][suite_name] = suite_result
            else:
                print(f"❌ Unknown test suite: {suite_name}")
        
        # Calculate overall results
        self.results["end_time"] = datetime.now()
        self.results["total_duration"] = (
            self.results["end_time"] - self.results["start_time"]
        ).total_seconds()
        
        self._calculate_overall_summary()
        
        # Generate reports
        await self._generate_comprehensive_report()
        
        return self.results
    
    async def _run_test_suite(self, suite_name: str) -> Dict[str, Any]:
        """Run a specific test suite."""
        suite_class = self.test_suites[suite_name]
        suite_instance = suite_class(self.config)
        
        suite_start_time = time.time()
        suite_result = {
            "name": suite_name,
            "start_time": datetime.now(),
            "end_time": None,
            "duration": 0,
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": [],
            "performance_metrics": [],
            "security_findings": [],
            "child_safety_validations": []
        }
        
        try:
            # Setup test suite
            await suite_instance.setup()
            
            # Get all test methods
            test_methods = [
                method for method in dir(suite_instance)
                if method.startswith('test_') and callable(getattr(suite_instance, method))
            ]
            
            suite_result["tests_run"] = len(test_methods)
            
            # Run each test method
            for test_method_name in test_methods:
                print(f"  🔍 Running {test_method_name}...")
                
                try:
                    test_method = getattr(suite_instance, test_method_name)
                    await test_method()
                    suite_result["tests_passed"] += 1
                    print(f"    ✅ {test_method_name} passed")
                    
                except Exception as e:
                    suite_result["tests_failed"] += 1
                    suite_result["errors"].append({
                        "test": test_method_name,
                        "error": str(e),
                        "type": type(e).__name__
                    })
                    print(f"    ❌ {test_method_name} failed: {str(e)}")
            
            # Collect suite metrics
            suite_result["performance_metrics"] = suite_instance.reporter.performance_metrics
            suite_result["security_findings"] = suite_instance.reporter.security_findings
            suite_result["child_safety_validations"] = suite_instance.reporter.child_safety_validations
            
        except Exception as e:
            suite_result["errors"].append({
                "test": "suite_setup",
                "error": str(e),
                "type": type(e).__name__
            })
            print(f"  ❌ Suite setup failed: {str(e)}")
            
        finally:
            # Teardown test suite
            try:
                await suite_instance.teardown()
            except Exception as e:
                print(f"  ⚠️  Suite teardown error: {str(e)}")
        
        suite_result["end_time"] = datetime.now()
        suite_result["duration"] = time.time() - suite_start_time
        
        # Print suite summary
        pass_rate = (suite_result["tests_passed"] / suite_result["tests_run"] * 100) if suite_result["tests_run"] > 0 else 0
        print(f"  📈 Suite Summary: {suite_result['tests_passed']}/{suite_result['tests_run']} passed ({pass_rate:.1f}%)")
        print(f"  ⏱️  Duration: {suite_result['duration']:.2f}s")
        
        return suite_result
    
    def _calculate_overall_summary(self):
        """Calculate overall test summary."""
        total_tests = sum(result["tests_run"] for result in self.results["suite_results"].values())
        total_passed = sum(result["tests_passed"] for result in self.results["suite_results"].values())
        total_failed = sum(result["tests_failed"] for result in self.results["suite_results"].values())
        
        total_errors = sum(len(result["errors"]) for result in self.results["suite_results"].values())
        total_security_findings = sum(len(result["security_findings"]) for result in self.results["suite_results"].values())
        total_safety_violations = sum(
            len([v for v in result["child_safety_validations"] if not v.get("passed", True)])
            for result in self.results["suite_results"].values()
        )
        
        # Performance summary
        all_performance_metrics = []
        for result in self.results["suite_results"].values():
            all_performance_metrics.extend(result["performance_metrics"])
        
        avg_response_time = (
            sum(m["duration_ms"] for m in all_performance_metrics) / len(all_performance_metrics)
            if all_performance_metrics else 0
        )
        
        self.results["overall_summary"] = {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "pass_rate": (total_passed / total_tests * 100) if total_tests > 0 else 0,
            "total_errors": total_errors,
            "total_security_findings": total_security_findings,
            "total_safety_violations": total_safety_violations,
            "avg_response_time_ms": avg_response_time,
            "total_duration_seconds": self.results["total_duration"]
        }
    
    async def _generate_comprehensive_report(self):
        """Generate comprehensive test reports."""
        # Ensure report directory exists
        report_dir = Path(self.config.report_directory)
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate JSON report
        json_report_path = report_dir / f"e2e_comprehensive_report_{timestamp}.json"
        with open(json_report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Generate HTML report
        html_report_path = report_dir / f"e2e_comprehensive_report_{timestamp}.html"
        html_content = self._generate_html_report()
        with open(html_report_path, 'w') as f:
            f.write(html_content)
        
        # Generate CI/CD report
        cicd_report_path = report_dir / f"e2e_cicd_report_{timestamp}.json"
        cicd_report = self._generate_cicd_report()
        with open(cicd_report_path, 'w') as f:
            json.dump(cicd_report, f, indent=2)
        
        print("\n📊 Test Reports Generated:")
        print(f"  📄 JSON Report: {json_report_path}")
        print(f"  🌐 HTML Report: {html_report_path}")
        print(f"  🔧 CI/CD Report: {cicd_report_path}")
    
    def _generate_html_report(self) -> str:
        """Generate comprehensive HTML report."""
        summary = self.results["overall_summary"]
        
        # Status indicators
        status_class = "success" if summary["pass_rate"] >= 95 else "warning" if summary["pass_rate"] >= 80 else "danger"
        security_class = "success" if summary["total_security_findings"] == 0 else "danger"
        safety_class = "success" if summary["total_safety_violations"] == 0 else "danger"
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AI Teddy Bear - E2E Test Report</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
                .header h1 {{ margin: 0; font-size: 2.5em; }}
                .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
                .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                .metric-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .metric-card h3 {{ margin: 0 0 10px 0; color: #333; }}
                .metric-value {{ font-size: 2em; font-weight: bold; margin: 10px 0; }}
                .success {{ color: #28a745; }}
                .warning {{ color: #ffc107; }}
                .danger {{ color: #dc3545; }}
                .section {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .test-suite {{ border-left: 4px solid #667eea; padding-left: 15px; margin-bottom: 20px; }}
                .test-item {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }}
                .test-item:last-child {{ border-bottom: none; }}
                .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }}
                .badge-success {{ background-color: #d4edda; color: #155724; }}
                .badge-danger {{ background-color: #f8d7da; color: #721c24; }}
                .progress-bar {{ width: 100%; height: 20px; background-color: #e9ecef; border-radius: 10px; overflow: hidden; }}
                .progress-fill {{ height: 100%; background: linear-gradient(90deg, #28a745, #20c997); transition: width 0.3s ease; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🧸 AI Teddy Bear - E2E Test Report</h1>
                    <p>Environment: {self.config.environment.value} | Generated: {self.results['start_time']}</p>
                </div>
                
                <div class="summary-grid">
                    <div class="metric-card">
                        <h3>Overall Test Results</h3>
                        <div class="metric-value {status_class}">{summary['pass_rate']:.1f}%</div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {summary['pass_rate']}%"></div>
                        </div>
                        <p>{summary['total_passed']}/{summary['total_tests']} tests passed</p>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Security Status</h3>
                        <div class="metric-value {security_class}">
                            {'✅ SECURE' if summary['total_security_findings'] == 0 else f"⚠️ {summary['total_security_findings']} ISSUES"}
                        </div>
                        <p>Security findings detected</p>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Child Safety Status</h3>
                        <div class="metric-value {safety_class}">
                            {'✅ SAFE' if summary['total_safety_violations'] == 0 else f"⚠️ {summary['total_safety_violations']} VIOLATIONS"}
                        </div>
                        <p>COPPA compliance violations</p>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Performance</h3>
                        <div class="metric-value {'success' if summary['avg_response_time_ms'] < 1000 else 'warning'}">{summary['avg_response_time_ms']:.0f}ms</div>
                        <p>Average response time</p>
                    </div>
                </div>
                
                <div class="section">
                    <h2>📋 Test Suite Results</h2>
                    {self._generate_suite_results_html()}
                </div>
                
                <div class="section">
                    <h2>🔒 Security Findings</h2>
                    {self._generate_security_findings_html()}
                </div>
                
                <div class="section">
                    <h2>👶 Child Safety Validations</h2>
                    {self._generate_safety_validations_html()}
                </div>
                
                <div class="section">
                    <h2>⚠️ Errors and Issues</h2>
                    {self._generate_errors_html()}
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _generate_suite_results_html(self) -> str:
        """Generate HTML for test suite results."""
        html_parts = []
        
        for suite_name, result in self.results["suite_results"].items():
            pass_rate = (result["tests_passed"] / result["tests_run"] * 100) if result["tests_run"] > 0 else 0
            status_class = "success" if pass_rate >= 95 else "warning" if pass_rate >= 80 else "danger"
            
            html_parts.append(f"""
            <div class="test-suite">
                <h3>{suite_name.replace('_', ' ').title()}</h3>
                <div class="test-item">
                    <span>Tests Run</span>
                    <span>{result['tests_run']}</span>
                </div>
                <div class="test-item">
                    <span>Tests Passed</span>
                    <span class="{status_class}">{result['tests_passed']}</span>
                </div>
                <div class="test-item">
                    <span>Tests Failed</span>
                    <span class="{'danger' if result['tests_failed'] > 0 else 'success'}">{result['tests_failed']}</span>
                </div>
                <div class="test-item">
                    <span>Pass Rate</span>
                    <span class="{status_class}">{pass_rate:.1f}%</span>
                </div>
                <div class="test-item">
                    <span>Duration</span>
                    <span>{result['duration']:.2f}s</span>
                </div>
            </div>
            """)
        
        return "".join(html_parts)
    
    def _generate_security_findings_html(self) -> str:
        """Generate HTML for security findings."""
        all_findings = []
        for result in self.results["suite_results"].values():
            all_findings.extend(result["security_findings"])
        
        if not all_findings:
            return "<p class='success'>✅ No security issues found!</p>"
        
        html_parts = []
        for finding in all_findings:
            severity_class = "danger" if finding["severity"] in ["high", "critical"] else "warning"
            html_parts.append(f"""
            <div class="test-item">
                <span>{finding['description']}</span>
                <span class="badge badge-{severity_class}">{finding['severity'].upper()}</span>
            </div>
            """)
        
        return "".join(html_parts)
    
    def _generate_safety_validations_html(self) -> str:
        """Generate HTML for child safety validations."""
        all_validations = []
        for result in self.results["suite_results"].values():
            all_validations.extend(result["child_safety_validations"])
        
        if not all_validations:
            return "<p>No child safety validations performed.</p>"
        
        passed_validations = [v for v in all_validations if v.get("passed", True)]
        failed_validations = [v for v in all_validations if not v.get("passed", True)]
        
        html_parts = [f"""
        <p class="{'success' if not failed_validations else 'danger'}">
            {len(passed_validations)}/{len(all_validations)} validations passed
        </p>
        """]
        
        for validation in failed_validations:
            html_parts.append(f"""
            <div class="test-item">
                <span>❌ {validation['check_type']}</span>
                <span class="badge badge-danger">FAILED</span>
            </div>
            """)
        
        return "".join(html_parts)
    
    def _generate_errors_html(self) -> str:
        """Generate HTML for errors."""
        all_errors = []
        for result in self.results["suite_results"].values():
            for error in result["errors"]:
                error["suite"] = result["name"]
                all_errors.append(error)
        
        if not all_errors:
            return "<p class='success'>✅ No errors encountered!</p>"
        
        html_parts = []
        for error in all_errors:
            html_parts.append(f"""
            <div class="test-item">
                <span><strong>{error['suite']}</strong> - {error['test']}</span>
                <span class="badge badge-danger">{error['type']}</span>
            </div>
            <div style="margin-left: 20px; color: #666; font-size: 0.9em;">
                {error['error']}
            </div>
            """)
        
        return "".join(html_parts)
    
    def _generate_cicd_report(self) -> Dict[str, Any]:
        """Generate CI/CD-friendly report."""
        summary = self.results["overall_summary"]
        
        return {
            "test_run_id": f"e2e_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "environment": self.config.environment.value,
            "timestamp": self.results["start_time"].isoformat(),
            "duration_seconds": summary["total_duration_seconds"],
            "results": {
                "total_tests": summary["total_tests"],
                "passed": summary["total_passed"],
                "failed": summary["total_failed"],
                "pass_rate": summary["pass_rate"],
                "success": summary["pass_rate"] >= 80 and summary["total_security_findings"] == 0 and summary["total_safety_violations"] == 0
            },
            "quality_gates": {
                "pass_rate_threshold": 80.0,
                "pass_rate_actual": summary["pass_rate"],
                "pass_rate_passed": summary["pass_rate"] >= 80.0,
                "security_findings_threshold": 0,
                "security_findings_actual": summary["total_security_findings"],
                "security_passed": summary["total_security_findings"] == 0,
                "safety_violations_threshold": 0,
                "safety_violations_actual": summary["total_safety_violations"],
                "safety_passed": summary["total_safety_violations"] == 0,
                "performance_threshold_ms": 2000.0,
                "performance_actual_ms": summary["avg_response_time_ms"],
                "performance_passed": summary["avg_response_time_ms"] <= 2000.0
            },
            "suite_breakdown": {
                name: {
                    "tests": result["tests_run"],
                    "passed": result["tests_passed"],
                    "failed": result["tests_failed"],
                    "duration": result["duration"]
                }
                for name, result in self.results["suite_results"].items()
            }
        }
    
    def print_summary(self):
        """Print test run summary to console."""
        summary = self.results["overall_summary"]
        
        print("\n" + "=" * 80)
        print("🏁 E2E Test Run Complete!")
        print("=" * 80)
        print(f"📊 Overall Results: {summary['total_passed']}/{summary['total_tests']} tests passed ({summary['pass_rate']:.1f}%)")
        print(f"⏱️  Total Duration: {summary['total_duration_seconds']:.2f} seconds")
        print(f"🔒 Security Findings: {summary['total_security_findings']}")
        print(f"👶 Safety Violations: {summary['total_safety_violations']}")
        print(f"⚡ Avg Response Time: {summary['avg_response_time_ms']:.0f}ms")
        
        # Quality gates status
        quality_passed = (
            summary['pass_rate'] >= 80 and 
            summary['total_security_findings'] == 0 and 
            summary['total_safety_violations'] == 0
        )
        
        status_emoji = "✅" if quality_passed else "❌"
        status_text = "PASSED" if quality_passed else "FAILED"
        
        print(f"\n{status_emoji} Quality Gates: {status_text}")
        print("=" * 80)


async def main():
    """Main entry point for E2E test runner."""
    parser = argparse.ArgumentParser(description="AI Teddy Bear E2E Test Runner")
    parser.add_argument(
        "--environment", 
        choices=["local", "ci", "staging", "production"], 
        default="local",
        help="Test environment"
    )
    parser.add_argument(
        "--suites",
        nargs="+",
        choices=["child_safety", "production_flows", "security_performance", "error_handling"],
        help="Test suites to run (default: all)"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for API testing"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Default request timeout in seconds"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run test suites in parallel (experimental)"
    )
    parser.add_argument(
        "--report-dir",
        default="test_reports",
        help="Directory for test reports"
    )
    
    args = parser.parse_args()
    
    # Create test configuration
    config = E2ETestConfig(
        environment=TestEnvironment(args.environment),
        base_url=args.base_url,
        default_timeout=args.timeout,
        report_directory=args.report_dir,
        generate_html_report=True,
        generate_json_report=True
    )
    
    # Create and run test runner
    runner = E2ETestRunner(config)
    
    try:
        results = await runner.run_all_tests(selected_suites=args.suites)
        runner.print_summary()
        
        # Exit with appropriate code for CI/CD
        quality_passed = (
            results["overall_summary"]["pass_rate"] >= 80 and
            results["overall_summary"]["total_security_findings"] == 0 and
            results["overall_summary"]["total_safety_violations"] == 0
        )
        
        sys.exit(0 if quality_passed else 1)
        
    except Exception as e:
        print(f"❌ Test runner failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())