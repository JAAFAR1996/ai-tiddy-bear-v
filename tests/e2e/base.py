"""
E2E Test Base Classes - Foundation for End-to-End Testing
=========================================================
Base classes and utilities for comprehensive E2E testing:
- Test environment management
- Test data lifecycle
- Performance monitoring
- Security validation
- Child safety compliance
- Test reporting
"""

import asyncio
import time
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Union, Type
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config import get_config_manager
from src.infrastructure.logging import get_logger
from src.infrastructure.database import (
    initialize_database_infrastructure,
    shutdown_database_infrastructure,
    get_user_repository,
    get_child_repository
)


logger = get_logger("e2e_tests")
config_manager = get_config_manager()


class TestEnvironment(Enum):
    """Test environment types."""
    LOCAL = "local"
    CI = "ci"
    STAGING = "staging"
    PRODUCTION = "production"  # Read-only tests


@dataclass
class E2ETestConfig:
    """Configuration for E2E tests."""
    environment: TestEnvironment = TestEnvironment.LOCAL
    base_url: str = "http://localhost:8000"
    api_version: str = "v1"
    
    # Database configuration
    test_database_url: Optional[str] = None
    use_test_database: bool = True
    cleanup_after_test: bool = True
    
    # Performance thresholds
    max_response_time_ms: float = 1000.0
    max_database_query_time_ms: float = 100.0
    
    # Security settings
    enable_security_tests: bool = True
    test_authentication: bool = True
    test_authorization: bool = True
    
    # Child safety
    enable_child_safety_tests: bool = True
    coppa_compliance_checks: bool = True
    
    # Test data
    test_data_seed: int = 12345
    generate_random_data: bool = True
    
    # Reporting
    generate_html_report: bool = True
    generate_json_report: bool = True
    report_directory: str = "test_reports"
    
    # Timeouts
    default_timeout: float = 30.0
    long_operation_timeout: float = 300.0
    
    # Retry configuration
    max_retries: int = 3
    retry_delay: float = 1.0


class TestDataManager:
    """Manages test data lifecycle."""
    
    def __init__(self, config: E2ETestConfig):
        self.config = config
        self.created_entities: Dict[str, List[uuid.UUID]] = {
            "users": [],
            "children": [],
            "conversations": [],
            "messages": []
        }
        self.logger = get_logger("test_data_manager")
    
    async def create_test_user(self, **kwargs) -> Dict[str, Any]:
        """Create a test user."""
        user_repo = await get_user_repository()
        
        user_data = {
            "username": f"test_user_{uuid.uuid4().hex[:8]}",
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "role": kwargs.get("role", "parent"),
            "password_hash": "$2b$12$test_password_hash",
            **kwargs
        }
        
        user = await user_repo.create(user_data)
        self.created_entities["users"].append(user.id)
        
        self.logger.debug(f"Created test user: {user.username}")
        
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role.value
        }
    
    async def create_test_child(self, parent_id: uuid.UUID, **kwargs) -> Dict[str, Any]:
        """Create a test child with COPPA compliance."""
        child_repo = await get_child_repository()
        
        child_data = {
            "parent_id": parent_id,
            "name": f"Test Child {uuid.uuid4().hex[:4]}",
            "estimated_age": kwargs.get("age", 8),
            "parental_consent": kwargs.get("parental_consent", True),
            "consent_date": datetime.now() if kwargs.get("parental_consent", True) else None,
            **kwargs
        }
        
        child = await child_repo.create(child_data)
        self.created_entities["children"].append(child.id)
        
        self.logger.debug(f"Created test child: {child.name}")
        
        return {
            "id": str(child.id),
            "name": child.name,
            "parent_id": str(parent_id),
            "estimated_age": child.estimated_age,
            "parental_consent": child.parental_consent,
            "coppa_protected": child.is_coppa_protected()
        }
    
    async def cleanup(self):
        """Clean up all created test data."""
        if not self.config.cleanup_after_test:
            self.logger.info("Skipping test data cleanup (configured to keep data)")
            return
        
        self.logger.info("Cleaning up test data")
        
        # Clean up in reverse order of dependencies
        cleanup_order = ["messages", "conversations", "children", "users"]
        
        for entity_type in cleanup_order:
            entity_ids = self.created_entities.get(entity_type, [])
            if entity_ids:
                self.logger.debug(f"Cleaning up {len(entity_ids)} {entity_type}")
                # Actual cleanup would be implemented here
                # For now, we'll just clear the tracking
                self.created_entities[entity_type].clear()
        
        self.logger.info("Test data cleanup completed")


class TestReporter:
    """Handles test reporting and metrics."""
    
    def __init__(self, config: E2ETestConfig):
        self.config = config
        self.test_results: List[Dict[str, Any]] = []
        self.performance_metrics: List[Dict[str, Any]] = []
        self.security_findings: List[Dict[str, Any]] = []
        self.child_safety_validations: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
        self.logger = get_logger("test_reporter")
    
    def add_test_result(self, test_name: str, passed: bool, duration_ms: float, details: Optional[Dict[str, Any]] = None):
        """Add a test result."""
        result = {
            "test_name": test_name,
            "passed": passed,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.test_results.append(result)
        
        if not passed:
            self.logger.error(f"Test failed: {test_name}")
    
    def add_performance_metric(self, operation: str, duration_ms: float, success: bool, details: Optional[Dict[str, Any]] = None):
        """Add a performance metric."""
        metric = {
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.performance_metrics.append(metric)
        
        if duration_ms > self.config.max_response_time_ms:
            self.logger.warning(f"Slow operation detected: {operation} took {duration_ms}ms")
    
    def add_security_finding(self, severity: str, category: str, description: str, details: Optional[Dict[str, Any]] = None):
        """Add a security finding."""
        finding = {
            "severity": severity,
            "category": category,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.security_findings.append(finding)
        
        if severity in ["high", "critical"]:
            self.logger.error(f"Security issue found: {description}")
    
    def add_child_safety_validation(self, check_type: str, passed: bool, details: Optional[Dict[str, Any]] = None):
        """Add a child safety validation result."""
        validation = {
            "check_type": check_type,
            "passed": passed,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.child_safety_validations.append(validation)
        
        if not passed:
            self.logger.error(f"Child safety check failed: {check_type}")
    
    def generate_report(self):
        """Generate test report."""
        total_duration = (datetime.now() - self.start_time).total_seconds()
        
        # Calculate statistics
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["passed"]])
        failed_tests = total_tests - passed_tests
        
        avg_response_time = sum(m["duration_ms"] for m in self.performance_metrics) / len(self.performance_metrics) if self.performance_metrics else 0
        
        security_issues = len([f for f in self.security_findings if f["severity"] in ["high", "critical"]])
        
        child_safety_failures = len([v for v in self.child_safety_validations if not v["passed"]])
        
        report = {
            "summary": {
                "environment": self.config.environment.value,
                "start_time": self.start_time.isoformat(),
                "total_duration_seconds": total_duration,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "pass_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "average_response_time_ms": avg_response_time,
                "security_issues": security_issues,
                "child_safety_failures": child_safety_failures
            },
            "test_results": self.test_results,
            "performance_metrics": self.performance_metrics,
            "security_findings": self.security_findings,
            "child_safety_validations": self.child_safety_validations
        }
        
        # Save reports
        if self.config.generate_json_report:
            self._save_json_report(report)
        
        if self.config.generate_html_report:
            self._save_html_report(report)
        
        return report
    
    def _save_json_report(self, report: Dict[str, Any]):
        """Save JSON report."""
        os.makedirs(self.config.report_directory, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"e2e_test_report_{timestamp}.json"
        filepath = os.path.join(self.config.report_directory, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"JSON report saved to: {filepath}")
    
    def _save_html_report(self, report: Dict[str, Any]):
        """Save HTML report."""
        os.makedirs(self.config.report_directory, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"e2e_test_report_{timestamp}.html"
        filepath = os.path.join(self.config.report_directory, filename)
        
        html_content = self._generate_html_content(report)
        
        with open(filepath, 'w') as f:
            f.write(html_content)
        
        self.logger.info(f"HTML report saved to: {filepath}")
    
    def _generate_html_content(self, report: Dict[str, Any]) -> str:
        """Generate HTML report content."""
        summary = report["summary"]
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>E2E Test Report - {summary['start_time']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .summary {{ margin: 20px 0; }}
                .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
                .passed {{ color: green; }}
                .failed {{ color: red; }}
                .warning {{ color: orange; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f0f0f0; }}
                .section {{ margin: 30px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>AI Teddy Bear - E2E Test Report</h1>
                <p>Environment: <strong>{summary['environment']}</strong></p>
                <p>Start Time: {summary['start_time']}</p>
                <p>Duration: {summary['total_duration_seconds']:.2f} seconds</p>
            </div>
            
            <div class="summary">
                <h2>Test Summary</h2>
                <div class="metric">
                    Total Tests: <strong>{summary['total_tests']}</strong>
                </div>
                <div class="metric passed">
                    Passed: <strong>{summary['passed_tests']}</strong>
                </div>
                <div class="metric failed">
                    Failed: <strong>{summary['failed_tests']}</strong>
                </div>
                <div class="metric">
                    Pass Rate: <strong>{summary['pass_rate']:.1f}%</strong>
                </div>
            </div>
            
            <div class="section">
                <h2>Performance Metrics</h2>
                <p>Average Response Time: <strong>{summary['average_response_time_ms']:.2f}ms</strong></p>
            </div>
            
            <div class="section">
                <h2>Security & Compliance</h2>
                <p>Security Issues: <strong class="{'failed' if summary['security_issues'] > 0 else 'passed'}">{summary['security_issues']}</strong></p>
                <p>Child Safety Failures: <strong class="{'failed' if summary['child_safety_failures'] > 0 else 'passed'}">{summary['child_safety_failures']}</strong></p>
            </div>
            
            <div class="section">
                <h2>Test Results</h2>
                <table>
                    <tr>
                        <th>Test Name</th>
                        <th>Status</th>
                        <th>Duration (ms)</th>
                        <th>Timestamp</th>
                    </tr>
                    {''.join(f'''
                    <tr>
                        <td>{result['test_name']}</td>
                        <td class="{'passed' if result['passed'] else 'failed'}">{'PASSED' if result['passed'] else 'FAILED'}</td>
                        <td>{result['duration_ms']:.2f}</td>
                        <td>{result['timestamp']}</td>
                    </tr>
                    ''' for result in report['test_results'][:50])}
                </table>
            </div>
        </body>
        </html>
        """
        
        return html


class E2ETestBase(ABC):
    """Base class for E2E tests."""
    
    def __init__(self, config: Optional[E2ETestConfig] = None):
        self.config = config or E2ETestConfig()
        self.data_manager = TestDataManager(self.config)
        self.reporter = TestReporter(self.config)
        self.client: Optional[AsyncClient] = None
        self.authenticated_clients: Dict[str, AsyncClient] = {}
        self.logger = logger
    
    async def setup(self):
        """Set up test environment."""
        self.logger.info(f"Setting up E2E test environment: {self.config.environment.value}")
        
        # Initialize database if needed
        if self.config.use_test_database:
            await self._setup_test_database()
        
        # Create base HTTP client
        self.client = AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.default_timeout
        )
        
        # Run custom setup
        await self._custom_setup()
    
    async def teardown(self):
        """Tear down test environment."""
        self.logger.info("Tearing down E2E test environment")
        
        # Run custom teardown
        await self._custom_teardown()
        
        # Clean up test data
        await self.data_manager.cleanup()
        
        # Close HTTP clients
        if self.client:
            await self.client.aclose()
        
        for client in self.authenticated_clients.values():
            await client.aclose()
        
        # Generate report
        report = self.reporter.generate_report()
        
        # Log summary
        summary = report["summary"]
        self.logger.info(
            f"Test run completed: {summary['passed_tests']}/{summary['total_tests']} passed "
            f"({summary['pass_rate']:.1f}% pass rate)"
        )
    
    async def _setup_test_database(self):
        """Set up test database."""
        if self.config.test_database_url:
            # Override database URL for testing
            os.environ["DATABASE_URL"] = self.config.test_database_url
        
        await initialize_database_infrastructure()
        self.logger.info("Test database initialized")
    
    @abstractmethod
    async def _custom_setup(self):
        """Custom setup for specific test class."""
        pass
    
    @abstractmethod
    async def _custom_teardown(self):
        """Custom teardown for specific test class."""
        pass
    
    async def create_authenticated_client(self, username: str, password: str = "test_password") -> AsyncClient:
        """Create an authenticated HTTP client."""
        # Get auth token
        response = await self.client.post(
            f"/api/{self.config.api_version}/auth/login",
            json={"username": username, "password": password}
        )
        
        if response.status_code != 200:
            raise ValueError(f"Authentication failed for {username}")
        
        token = response.json()["access_token"]
        
        # Create authenticated client
        auth_client = AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.default_timeout,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        self.authenticated_clients[username] = auth_client
        return auth_client
    
    @asynccontextmanager
    async def measure_time(self, operation_name: str):
        """Context manager to measure operation time."""
        start_time = time.time()
        success = True
        
        try:
            yield
        except Exception as e:
            success = False
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.reporter.add_performance_metric(operation_name, duration_ms, success)
    
    def validate_response(self, response, expected_status: int = 200, schema: Optional[Dict[str, Any]] = None):
        """Validate API response."""
        assert response.status_code == expected_status, f"Expected status {expected_status}, got {response.status_code}"
        
        if schema:
            # Basic schema validation
            response_data = response.json()
            for key, expected_type in schema.items():
                assert key in response_data, f"Missing required field: {key}"
                assert isinstance(response_data[key], expected_type), f"Invalid type for {key}"
    
    def validate_child_safety(self, data: Dict[str, Any], check_type: str):
        """Validate child safety compliance."""
        passed = True
        details = {}
        
        # Check for required child safety fields
        if check_type == "parental_consent":
            passed = data.get("parental_consent", False) is True
            details["has_consent"] = data.get("parental_consent", False)
        
        elif check_type == "age_appropriate":
            age = data.get("estimated_age", 0)
            passed = age >= 3  # Minimum age requirement
            details["age"] = age
        
        elif check_type == "data_retention":
            retention_days = data.get("data_retention_days", 0)
            passed = 0 < retention_days <= 90  # COPPA compliance
            details["retention_days"] = retention_days
        
        self.reporter.add_child_safety_validation(check_type, passed, details)
        
        return passed


# Decorators for test methods
def performance_test(threshold_ms: float = 1000.0):
    """Decorator for performance tests."""
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(self, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                passed = duration_ms <= threshold_ms
                self.reporter.add_test_result(
                    func.__name__,
                    passed,
                    duration_ms,
                    {"threshold_ms": threshold_ms}
                )
                
                if not passed:
                    self.logger.warning(f"Performance test {func.__name__} exceeded threshold: {duration_ms}ms > {threshold_ms}ms")
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self.reporter.add_test_result(func.__name__, False, duration_ms, {"error": str(e)})
                raise
        
        return wrapper
    return decorator


def security_test(category: str = "general"):
    """Decorator for security tests."""
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(self, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                self.reporter.add_test_result(func.__name__, True, duration_ms, {"category": category})
                return result
                
            except AssertionError as e:
                duration_ms = (time.time() - start_time) * 1000
                self.reporter.add_security_finding(
                    "high",
                    category,
                    str(e),
                    {"test": func.__name__}
                )
                self.reporter.add_test_result(func.__name__, False, duration_ms, {"error": str(e)})
                raise
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self.reporter.add_test_result(func.__name__, False, duration_ms, {"error": str(e)})
                raise
        
        return wrapper
    return decorator


def child_safety_test(check_type: str = "general"):
    """Decorator for child safety tests."""
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(self, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                self.reporter.add_test_result(func.__name__, True, duration_ms, {"check_type": check_type})
                return result
                
            except AssertionError as e:
                duration_ms = (time.time() - start_time) * 1000
                self.reporter.add_child_safety_validation(check_type, False, {"error": str(e), "test": func.__name__})
                self.reporter.add_test_result(func.__name__, False, duration_ms, {"error": str(e)})
                raise
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self.reporter.add_test_result(func.__name__, False, duration_ms, {"error": str(e)})
                raise
        
        return wrapper
    return decorator