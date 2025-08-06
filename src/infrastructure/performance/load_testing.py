"""
Load Testing and Benchmarking System
Comprehensive performance testing for child-safe AI applications
"""

import asyncio
import time
import logging
import statistics
import random
import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import concurrent.futures
from pathlib import Path

import httpx
import aiofiles
from faker import Faker

from src.core.exceptions import TestError, ValidationError
from src.utils.date_utils import get_current_timestamp
from src.core.utils.crypto_utils import hash_data

def generate_test_child_id(prefix: str = "test_child") -> str:
    """Generate a test child ID for testing purposes."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


logger = logging.getLogger(__name__)
fake = Faker()


class TestType(Enum):
    """Types of load tests."""

    SMOKE = "smoke"  # Basic functionality
    LOAD = "load"  # Normal expected load
    STRESS = "stress"  # Beyond normal capacity
    SPIKE = "spike"  # Sudden traffic increases
    VOLUME = "volume"  # Large amounts of data
    ENDURANCE = "endurance"  # Long-term stability


class LoadPattern(Enum):
    """Load generation patterns."""

    CONSTANT = "constant"  # Steady load
    RAMP_UP = "ramp_up"  # Gradually increasing
    RAMP_DOWN = "ramp_down"  # Gradually decreasing
    SPIKE = "spike"  # Sudden bursts
    WAVE = "wave"  # Sine wave pattern
    STEP = "step"  # Step increases


@dataclass
class TestScenario:
    """Load test scenario configuration."""

    name: str
    description: str
    test_type: TestType
    duration_seconds: int

    # Load configuration
    initial_users: int = 1
    max_users: int = 10
    load_pattern: LoadPattern = LoadPattern.RAMP_UP
    ramp_duration_seconds: int = 60

    # Request configuration
    base_url: str = "http://localhost:8000"
    endpoints: List[str] = field(default_factory=list)
    request_timeout: int = 30

    # Child safety specific
    child_safe_endpoints_only: bool = True
    simulate_coppa_compliance: bool = True
    child_data_volume: int = 100

    # Performance thresholds
    max_response_time_ms: int = 2000
    max_error_rate: float = 0.05  # 5%
    min_throughput_rps: float = 10.0


@dataclass
class TestResult:
    """Individual test result."""

    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    response_size_bytes: int
    error: Optional[str] = None
    child_safe_test: bool = False


@dataclass
class TestSummary:
    """Test run summary statistics."""

    scenario_name: str
    test_type: TestType
    start_time: datetime
    end_time: datetime
    duration_seconds: float

    # Request statistics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0

    # Response time statistics
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    p50_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0

    # Throughput statistics
    requests_per_second: float = 0.0
    bytes_per_second: float = 0.0

    # Child safety metrics
    child_safe_requests: int = 0
    coppa_violations: int = 0
    child_data_requests: int = 0

    # Performance assessment
    passed_response_time_threshold: bool = True
    passed_error_rate_threshold: bool = True
    passed_throughput_threshold: bool = True
    overall_passed: bool = True


class BaseLoadGenerator(ABC):
    """Base class for load generators."""

    @abstractmethod
    async def generate_load(
        self, scenario: TestScenario, result_collector: Callable[[TestResult], None]
    ) -> None:
        """Generate load according to scenario."""
        pass


class HTTPLoadGenerator(BaseLoadGenerator):
    """HTTP-based load generator."""

    def __init__(self):
        self.client_session = None
        self.child_test_data = {}

    async def generate_load(
        self, scenario: TestScenario, result_collector: Callable[[TestResult], None]
    ) -> None:
        """Generate HTTP load."""

        # Create HTTP client session
        timeout = httpx.Timeout(scenario.request_timeout)
        limits = httpx.Limits(max_connections=scenario.max_users * 2)

        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            self.client_session = client

            # Generate test data
            await self._generate_child_test_data(scenario)

            # Calculate load pattern
            load_schedule = self._calculate_load_schedule(scenario)

            # Execute load test
            tasks = []
            for timestamp, user_count in load_schedule:
                # Wait until scheduled time
                wait_time = timestamp - time.time()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

                # Launch user tasks
                for _ in range(user_count):
                    task = asyncio.create_task(
                        self._simulate_user_session(scenario, result_collector)
                    )
                    tasks.append(task)

            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

    def _calculate_load_schedule(
        self, scenario: TestScenario
    ) -> List[Tuple[float, int]]:
        """Calculate load generation schedule."""
        schedule = []
        start_time = time.time()
        current_time = start_time

        if scenario.load_pattern == LoadPattern.CONSTANT:
            # Constant load for entire duration
            schedule.append((current_time, scenario.max_users))

        elif scenario.load_pattern == LoadPattern.RAMP_UP:
            # Gradually increase users
            steps = min(scenario.ramp_duration_seconds // 5, scenario.max_users)
            step_duration = scenario.ramp_duration_seconds / steps
            users_per_step = scenario.max_users / steps

            for step in range(steps):
                users = int((step + 1) * users_per_step)
                schedule.append((current_time + step * step_duration, users))

        elif scenario.load_pattern == LoadPattern.SPIKE:
            # Sudden spike in users
            schedule.append((current_time, scenario.initial_users))
            schedule.append((current_time + 10, scenario.max_users))  # Spike after 10s
            schedule.append(
                (current_time + 60, scenario.initial_users)
            )  # Return to normal

        elif scenario.load_pattern == LoadPattern.WAVE:
            # Sine wave pattern
            duration = scenario.duration_seconds
            steps = duration // 10  # Every 10 seconds

            for step in range(steps):
                t = step / steps * 2 * 3.14159  # Full wave cycle
                users = int(
                    scenario.initial_users
                    + (scenario.max_users - scenario.initial_users)
                    * (1 + math.sin(t))
                    / 2
                )
                schedule.append((current_time + step * 10, users))

        return schedule

    async def _generate_child_test_data(self, scenario: TestScenario) -> None:
        """Generate test data for child-safe endpoints."""
        self.child_test_data = {
            "child_profiles": [],
            "conversation_prompts": [],
            "audio_samples": [],
        }

        # Generate child profiles (synthetic data only)
        for _ in range(scenario.child_data_volume):
            child_id = generate_test_child_id()
            profile = {
                "child_id": child_id,
                "age": random.randint(3, 12),
                "name": f"TestChild{random.randint(1000, 9999)}",
                "language": "en",
                "interests": random.sample(
                    ["stories", "games", "music", "learning"], 2
                ),
            }
            self.child_test_data["child_profiles"].append(profile)

        # Generate conversation prompts
        prompts = [
            "Tell me a bedtime story",
            "What's the weather like?",
            "Can you sing a song?",
            "Help me with math",
            "Tell me a joke",
        ]
        self.child_test_data["conversation_prompts"] = prompts

    async def _simulate_user_session(
        self, scenario: TestScenario, result_collector: Callable[[TestResult], None]
    ) -> None:
        """Simulate a user session with multiple requests."""

        session_duration = random.randint(30, 300)  # 30s to 5min
        session_start = time.time()

        while (time.time() - session_start) < session_duration:
            # Select random endpoint
            if scenario.endpoints:
                endpoint = random.choice(scenario.endpoints)
            else:
                endpoint = self._select_random_endpoint(
                    scenario.child_safe_endpoints_only
                )

            # Make request
            await self._make_request(scenario, endpoint, result_collector)

            # Random delay between requests (1-10 seconds)
            await asyncio.sleep(random.uniform(1, 10))

    def _select_random_endpoint(self, child_safe_only: bool) -> str:
        """Select a random endpoint for testing."""

        if child_safe_only:
            endpoints = [
                "/api/v1/children/profiles",
                "/api/v1/conversations/start",
                "/api/v1/stories/generate",
                "/api/v1/audio/tts",
                "/api/v1/safety/check",
                "/health",
            ]
        else:
            endpoints = [
                "/api/v1/admin/metrics",
                "/api/v1/system/status",
                "/api/v1/auth/login",
                "/health",
                "/metrics",
            ]

        return random.choice(endpoints)

    async def _make_request(
        self,
        scenario: TestScenario,
        endpoint: str,
        result_collector: Callable[[TestResult], None],
    ) -> None:
        """Make HTTP request and collect results."""

        start_time = time.time()
        url = f"{scenario.base_url}{endpoint}"

        # Determine request method and payload
        method, data = self._prepare_request(endpoint)

        try:
            # Make request
            if method == "GET":
                response = await self.client_session.get(url)
            elif method == "POST":
                response = await self.client_session.post(url, json=data)
            elif method == "PUT":
                response = await self.client_session.put(url, json=data)
            else:
                response = await self.client_session.get(url)

            # Calculate metrics
            response_time_ms = (time.time() - start_time) * 1000
            response_size = len(response.content) if response.content else 0

            # Create result
            result = TestResult(
                timestamp=datetime.now(),
                endpoint=endpoint,
                method=method,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                response_size_bytes=response_size,
                child_safe_test=self._is_child_safe_endpoint(endpoint),
            )

            # Validate child safety compliance
            if result.child_safe_test and scenario.simulate_coppa_compliance:
                self._validate_coppa_compliance(response, result)

            result_collector(result)

        except Exception as e:
            # Record error
            response_time_ms = (time.time() - start_time) * 1000

            result = TestResult(
                timestamp=datetime.now(),
                endpoint=endpoint,
                method=method,
                status_code=0,
                response_time_ms=response_time_ms,
                response_size_bytes=0,
                error=str(e),
                child_safe_test=self._is_child_safe_endpoint(endpoint),
            )

            result_collector(result)

    def _prepare_request(self, endpoint: str) -> Tuple[str, Optional[Dict]]:
        """Prepare request method and data based on endpoint."""

        if "/conversations/start" in endpoint:
            return "POST", {
                "child_id": random.choice(self.child_test_data["child_profiles"])[
                    "child_id"
                ],
                "prompt": random.choice(self.child_test_data["conversation_prompts"]),
            }

        elif "/stories/generate" in endpoint:
            return "POST", {
                "child_id": random.choice(self.child_test_data["child_profiles"])[
                    "child_id"
                ],
                "theme": random.choice(["adventure", "friendship", "learning"]),
                "length": "short",
            }

        elif "/children/profiles" in endpoint:
            if random.choice([True, False]):  # 50% chance of POST vs GET
                return "POST", random.choice(self.child_test_data["child_profiles"])
            else:
                return "GET", None

        elif "/audio/tts" in endpoint:
            return "POST", {
                "text": "Hello, this is a test message for text-to-speech",
                "voice": "child_friendly",
                "format": "mp3",
            }

        else:
            return "GET", None

    def _is_child_safe_endpoint(self, endpoint: str) -> bool:
        """Check if endpoint is child-safe."""
        child_safe_patterns = [
            "/children/",
            "/conversations/",
            "/stories/",
            "/audio/",
            "/safety/",
            "/coppa/",
        ]
        return any(pattern in endpoint for pattern in child_safe_patterns)

    def _validate_coppa_compliance(
        self, response: httpx.Response, result: TestResult
    ) -> None:
        """Validate COPPA compliance in response."""

        # Check for required headers
        required_headers = ["X-Child-Safe", "X-COPPA-Compliant", "X-Content-Safety"]
        missing_headers = [h for h in required_headers if h not in response.headers]

        if missing_headers:
            result.error = f"Missing COPPA compliance headers: {missing_headers}"

        # Check response doesn't contain sensitive data patterns
        if response.content:
            content = response.content.decode("utf-8", errors="ignore")

            # Simple checks for potential PII leakage
            sensitive_patterns = ["email", "phone", "address", "ssn"]
            found_patterns = [p for p in sensitive_patterns if p in content.lower()]

            if found_patterns:
                result.error = f"Potential PII leakage: {found_patterns}"


class LoadTestRunner:
    """Main load test runner."""

    def __init__(self):
        self.results: List[TestResult] = []
        self.scenarios: List[TestScenario] = []
        self.summary_reports: List[TestSummary] = []

    def add_scenario(self, scenario: TestScenario) -> None:
        """Add test scenario."""
        self.scenarios.append(scenario)

    async def run_all_scenarios(self) -> List[TestSummary]:
        """Run all configured test scenarios."""
        summaries = []

        for scenario in self.scenarios:
            logger.info(f"Starting load test scenario: {scenario.name}")
            summary = await self.run_scenario(scenario)
            summaries.append(summary)

            # Log results
            logger.info(
                f"Scenario '{scenario.name}' completed",
                extra={
                    "total_requests": summary.total_requests,
                    "error_rate": summary.error_rate,
                    "avg_response_time_ms": summary.avg_response_time_ms,
                    "requests_per_second": summary.requests_per_second,
                    "passed": summary.overall_passed,
                },
            )

        return summaries

    async def run_scenario(self, scenario: TestScenario) -> TestSummary:
        """Run a single test scenario."""

        # Clear previous results
        scenario_results = []

        def collect_result(result: TestResult) -> None:
            scenario_results.append(result)

        # Create load generator
        generator = HTTPLoadGenerator()

        # Run test
        start_time = datetime.now()

        try:
            await generator.generate_load(scenario, collect_result)
        except Exception as e:
            logger.error(f"Load test scenario '{scenario.name}' failed: {e}")
            raise TestError(f"Load test failed: {e}")

        end_time = datetime.now()

        # Generate summary
        summary = self._generate_summary(
            scenario, scenario_results, start_time, end_time
        )
        self.summary_reports.append(summary)

        return summary

    def _generate_summary(
        self,
        scenario: TestScenario,
        results: List[TestResult],
        start_time: datetime,
        end_time: datetime,
    ) -> TestSummary:
        """Generate test summary from results."""

        if not results:
            return TestSummary(
                scenario_name=scenario.name,
                test_type=scenario.test_type,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=0,
                overall_passed=False,
            )

        # Basic statistics
        total_requests = len(results)
        successful_requests = sum(
            1 for r in results if 200 <= r.status_code < 400 and not r.error
        )
        failed_requests = total_requests - successful_requests
        error_rate = failed_requests / total_requests if total_requests > 0 else 0

        # Response time statistics
        response_times = [r.response_time_ms for r in results if not r.error]

        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)

            sorted_times = sorted(response_times)
            p50_response_time = sorted_times[int(0.5 * len(sorted_times))]
            p95_response_time = sorted_times[int(0.95 * len(sorted_times))]
            p99_response_time = sorted_times[int(0.99 * len(sorted_times))]
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p50_response_time = p95_response_time = p99_response_time = 0

        # Throughput statistics
        duration_seconds = (end_time - start_time).total_seconds()
        requests_per_second = (
            total_requests / duration_seconds if duration_seconds > 0 else 0
        )

        total_bytes = sum(r.response_size_bytes for r in results)
        bytes_per_second = total_bytes / duration_seconds if duration_seconds > 0 else 0

        # Child safety metrics
        child_safe_requests = sum(1 for r in results if r.child_safe_test)
        coppa_violations = sum(
            1
            for r in results
            if r.child_safe_test and r.error and "coppa" in r.error.lower()
        )
        child_data_requests = sum(
            1 for r in results if "children" in r.endpoint or "child" in r.endpoint
        )

        # Performance assessment
        passed_response_time = avg_response_time <= scenario.max_response_time_ms
        passed_error_rate = error_rate <= scenario.max_error_rate
        passed_throughput = requests_per_second >= scenario.min_throughput_rps

        overall_passed = (
            passed_response_time and passed_error_rate and passed_throughput
        )

        return TestSummary(
            scenario_name=scenario.name,
            test_type=scenario.test_type,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            error_rate=error_rate,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            requests_per_second=requests_per_second,
            bytes_per_second=bytes_per_second,
            child_safe_requests=child_safe_requests,
            coppa_violations=coppa_violations,
            child_data_requests=child_data_requests,
            passed_response_time_threshold=passed_response_time,
            passed_error_rate_threshold=passed_error_rate,
            passed_throughput_threshold=passed_throughput,
            overall_passed=overall_passed,
        )

    async def export_results(self, output_dir: str, format: str = "json") -> str:
        """Export test results to files."""

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "json":
            # Export detailed results
            results_file = output_path / f"load_test_results_{timestamp}.json"

            export_data = {
                "metadata": {
                    "timestamp": timestamp,
                    "total_scenarios": len(self.summary_reports),
                    "export_format": format,
                },
                "summaries": [
                    {
                        "scenario_name": s.scenario_name,
                        "test_type": s.test_type.value,
                        "start_time": s.start_time.isoformat(),
                        "end_time": s.end_time.isoformat(),
                        "duration_seconds": s.duration_seconds,
                        "total_requests": s.total_requests,
                        "successful_requests": s.successful_requests,
                        "failed_requests": s.failed_requests,
                        "error_rate": s.error_rate,
                        "avg_response_time_ms": s.avg_response_time_ms,
                        "p95_response_time_ms": s.p95_response_time_ms,
                        "p99_response_time_ms": s.p99_response_time_ms,
                        "requests_per_second": s.requests_per_second,
                        "child_safe_requests": s.child_safe_requests,
                        "coppa_violations": s.coppa_violations,
                        "overall_passed": s.overall_passed,
                    }
                    for s in self.summary_reports
                ],
            }

            async with aiofiles.open(results_file, "w") as f:
                await f.write(json.dumps(export_data, indent=2))

            return str(results_file)

        elif format == "html":
            # Export HTML report
            html_file = output_path / f"load_test_report_{timestamp}.html"
            html_content = self._generate_html_report()

            async with aiofiles.open(html_file, "w") as f:
                await f.write(html_content)

            return str(html_file)

        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _generate_html_report(self) -> str:
        """Generate HTML report."""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Load Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .scenario {{ margin: 20px 0; border: 1px solid #ddd; border-radius: 5px; }}
                .scenario-header {{ background: #e7f3ff; padding: 15px; font-weight: bold; }}
                .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; padding: 15px; }}
                .metric {{ background: #f9f9f9; padding: 10px; border-radius: 3px; }}
                .passed {{ color: green; }}
                .failed {{ color: red; }}
                .child-safety {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Load Test Report</h1>
                <p>Generated: {datetime.now().isoformat()}</p>
                <p>Total Scenarios: {len(self.summary_reports)}</p>
            </div>
        """

        for summary in self.summary_reports:
            status_class = "passed" if summary.overall_passed else "failed"
            status_text = "PASSED" if summary.overall_passed else "FAILED"

            html += f"""
            <div class="scenario">
                <div class="scenario-header">
                    {summary.scenario_name} ({summary.test_type.value.upper()}) - 
                    <span class="{status_class}">{status_text}</span>
                </div>
                <div class="metrics">
                    <div class="metric">
                        <strong>Total Requests:</strong><br>
                        {summary.total_requests:,}
                    </div>
                    <div class="metric">
                        <strong>Success Rate:</strong><br>
                        {(1 - summary.error_rate) * 100:.1f}%
                    </div>
                    <div class="metric">
                        <strong>Avg Response Time:</strong><br>
                        {summary.avg_response_time_ms:.1f}ms
                    </div>
                    <div class="metric">
                        <strong>P95 Response Time:</strong><br>
                        {summary.p95_response_time_ms:.1f}ms
                    </div>
                    <div class="metric">
                        <strong>Throughput:</strong><br>
                        {summary.requests_per_second:.1f} req/s
                    </div>
                    <div class="metric">
                        <strong>Duration:</strong><br>
                        {summary.duration_seconds:.1f}s
                    </div>
                </div>
                
                <div class="child-safety">
                    <strong>Child Safety Metrics:</strong><br>
                    Child-safe requests: {summary.child_safe_requests:,}<br>
                    COPPA violations: {summary.coppa_violations}<br>
                    Child data requests: {summary.child_data_requests:,}
                </div>
            </div>
            """

        html += """
        </body>
        </html>
        """

        return html


# Predefined test scenarios
def get_default_scenarios(
    base_url: str = "http://localhost:8000",
) -> List[TestScenario]:
    """Get default test scenarios for AI Teddy Bear application."""

    scenarios = [
        # Smoke test - basic functionality
        TestScenario(
            name="smoke_test",
            description="Basic functionality test with minimal load",
            test_type=TestType.SMOKE,
            duration_seconds=60,
            initial_users=1,
            max_users=2,
            load_pattern=LoadPattern.CONSTANT,
            base_url=base_url,
            endpoints=["/health", "/api/v1/children/profiles"],
            max_response_time_ms=1000,
            max_error_rate=0.01,
            min_throughput_rps=1.0,
        ),
        # Load test - normal expected traffic
        TestScenario(
            name="normal_load_test",
            description="Normal expected load test",
            test_type=TestType.LOAD,
            duration_seconds=300,  # 5 minutes
            initial_users=5,
            max_users=50,
            load_pattern=LoadPattern.RAMP_UP,
            ramp_duration_seconds=120,
            base_url=base_url,
            child_safe_endpoints_only=True,
            max_response_time_ms=2000,
            max_error_rate=0.05,
            min_throughput_rps=25.0,
        ),
        # Stress test - beyond normal capacity
        TestScenario(
            name="stress_test",
            description="Stress test beyond normal capacity",
            test_type=TestType.STRESS,
            duration_seconds=600,  # 10 minutes
            initial_users=10,
            max_users=200,
            load_pattern=LoadPattern.RAMP_UP,
            ramp_duration_seconds=300,
            base_url=base_url,
            child_safe_endpoints_only=True,
            max_response_time_ms=5000,
            max_error_rate=0.10,
            min_throughput_rps=50.0,
        ),
        # Spike test - sudden traffic increase
        TestScenario(
            name="spike_test",
            description="Sudden spike in traffic",
            test_type=TestType.SPIKE,
            duration_seconds=180,  # 3 minutes
            initial_users=5,
            max_users=100,
            load_pattern=LoadPattern.SPIKE,
            base_url=base_url,
            child_safe_endpoints_only=True,
            max_response_time_ms=3000,
            max_error_rate=0.15,
            min_throughput_rps=20.0,
        ),
        # Child data volume test
        TestScenario(
            name="child_data_volume_test",
            description="High volume of child data requests",
            test_type=TestType.VOLUME,
            duration_seconds=300,
            initial_users=10,
            max_users=30,
            load_pattern=LoadPattern.CONSTANT,
            base_url=base_url,
            endpoints=[
                "/api/v1/children/profiles",
                "/api/v1/conversations/start",
                "/api/v1/stories/generate",
            ],
            child_data_volume=500,
            max_response_time_ms=3000,
            max_error_rate=0.05,
            min_throughput_rps=15.0,
        ),
    ]

    return scenarios


# Factory function for easy setup
def create_load_test_runner(base_url: str = "http://localhost:8000") -> LoadTestRunner:
    """Create load test runner with default scenarios."""

    runner = LoadTestRunner()

    # Add default scenarios
    scenarios = get_default_scenarios(base_url)
    for scenario in scenarios:
        runner.add_scenario(scenario)

    return runner
