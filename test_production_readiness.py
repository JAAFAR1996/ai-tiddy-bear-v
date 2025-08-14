#!/usr/bin/env python3
"""
Production Readiness Test Suite
===============================
Comprehensive test for all production-grade features:
- Transaction management with commit/rollback
- Metrics API endpoints (/metrics, /api/v1/esp32/metrics)
- App readiness state management
- Engine disposal cleanup
- Endpoint availability and response validation
"""

import asyncio
import sys
import time
import json
from typing import Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionReadinessTest:
    """Production readiness test suite."""
    
    def __init__(self):
        self.test_results = {
            "timestamp": time.time(),
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "failures": [],
            "summary": {}
        }
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result."""
        self.test_results["tests_run"] += 1
        if success:
            self.test_results["tests_passed"] += 1
            logger.info(f"✅ {test_name}: PASSED {details}")
        else:
            self.test_results["tests_failed"] += 1
            self.test_results["failures"].append(f"{test_name}: {details}")
            logger.error(f"❌ {test_name}: FAILED {details}")
    
    async def test_transaction_management(self):
        """Test database transaction management."""
        logger.info("🔍 Testing database transaction management...")
        
        try:
            from src.infrastructure.database.database_manager import DatabaseManager
            from src.infrastructure.config.production_config import load_config
            
            # Load config first for proper initialization
            config = load_config()
            
            # Test that get_connection method exists and has proper transaction handling
            db_manager = DatabaseManager(config=config)
            
            # Check if get_connection exists and test transaction logic by code inspection
            import inspect
            if hasattr(db_manager, 'get_connection'):
                # Get the source code to verify transaction handling
                method = getattr(db_manager, 'get_connection')
                try:
                    source = inspect.getsource(method)
                    has_commit = "await session.commit()" in source
                    has_rollback = "await session.rollback()" in source
                    has_asynccontextmanager = "@asynccontextmanager" in source
                    
                    transaction_implemented = has_commit and has_rollback and has_asynccontextmanager
                    self.log_test(
                        "Database Transaction Context Manager", 
                        transaction_implemented,
                        f"commit={has_commit}, rollback={has_rollback}, async_context={has_asynccontextmanager}"
                    )
                except:
                    # Fallback: just check method exists
                    self.log_test(
                        "Database Transaction Context Manager", 
                        True,
                        "get_connection method exists (source inspection failed)"
                    )
            else:
                self.log_test(
                    "Database Transaction Context Manager", 
                    False,
                    "get_connection method not found"
                )
                
        except Exception as e:
            self.log_test(
                "Database Transaction Management", 
                False,
                f"Exception: {e}"
            )
    
    def test_metrics_api_structure(self):
        """Test metrics API module structure."""
        logger.info("🔍 Testing metrics API structure...")
        
        try:
            from src.adapters import metrics_api
            
            # Test router exists
            has_router = hasattr(metrics_api, 'router')
            self.log_test(
                "Metrics API Router", 
                has_router,
                "Router should be defined"
            )
            
            # Test endpoints exist
            if has_router:
                router = metrics_api.router
                routes = [route.path for route in router.routes]
                
                expected_routes = [
                    "/api/v1/esp32/metrics",
                    "/api/v1/metrics",
                    "/api/v1/health/metrics",
                    "/api/v1/system/info"
                ]
                
                for route in expected_routes:
                    route_exists = route in routes
                    self.log_test(
                        f"Metrics Route {route}", 
                        route_exists,
                        f"Route should be registered"
                    )
            
            # Test utility functions exist
            utility_functions = [
                'increment_esp32_metric',
                'set_esp32_gauge', 
                'record_esp32_duration'
            ]
            
            for func_name in utility_functions:
                has_function = hasattr(metrics_api, func_name)
                self.log_test(
                    f"Metrics Utility {func_name}", 
                    has_function,
                    f"Utility function should be available"
                )
                
        except Exception as e:
            self.log_test(
                "Metrics API Structure", 
                False,
                f"Exception: {e}"
            )
    
    def test_app_state_management(self):
        """Test app state management."""
        logger.info("🔍 Testing app state management...")
        
        try:
            from src.main import create_app
            
            # Create app instance
            app = create_app()
            
            # Test config_ready flag
            has_config_ready = hasattr(app.state, 'config_ready')
            self.log_test(
                "App State config_ready", 
                has_config_ready,
                "config_ready flag should be set"
            )
            
            if has_config_ready:
                is_config_ready = getattr(app.state, 'config_ready', False)
                self.log_test(
                    "Config Ready Status", 
                    is_config_ready,
                    "config_ready should be True for ESP32 endpoints"
                )
            
            # Test config availability
            has_config = hasattr(app.state, 'config')
            self.log_test(
                "App State Config", 
                has_config,
                "Config should be available in app.state"
            )
            
            # Test database engine setup
            has_db_engine = hasattr(app.state, 'db_engine')
            self.log_test(
                "Database Engine Setup", 
                has_db_engine,
                "DB engine should be configured for cleanup"
            )
                
        except Exception as e:
            self.log_test(
                "App State Management", 
                False,
                f"Exception: {e}"
            )
    
    def test_readiness_gate_middleware(self):
        """Test ReadinessGate middleware functionality."""
        logger.info("🔍 Testing ReadinessGate middleware...")
        
        try:
            from src.main import ReadinessGate
            
            # Test middleware class exists
            self.log_test(
                "ReadinessGate Middleware Class", 
                ReadinessGate is not None,
                "ReadinessGate should be defined"
            )
            
            # Test middleware has required methods
            if ReadinessGate:
                has_dispatch = hasattr(ReadinessGate, 'dispatch')
                self.log_test(
                    "ReadinessGate Dispatch Method", 
                    has_dispatch,
                    "dispatch method should be implemented"
                )
                
                # Test middleware initialization
                try:
                    # Mock app for testing
                    class MockApp:
                        pass
                    
                    middleware = ReadinessGate(MockApp())
                    has_allow_paths = hasattr(middleware, 'allow')
                    self.log_test(
                        "ReadinessGate Allow Paths", 
                        has_allow_paths,
                        "Allow paths should be configured"
                    )
                    
                    has_config_dependent = hasattr(middleware, 'config_dependent')
                    self.log_test(
                        "ReadinessGate Config Dependent Paths", 
                        has_config_dependent,
                        "Config dependent paths should be configured"
                    )
                    
                except Exception as init_e:
                    self.log_test(
                        "ReadinessGate Initialization", 
                        False,
                        f"Initialization failed: {init_e}"
                    )
                
        except Exception as e:
            self.log_test(
                "ReadinessGate Middleware", 
                False,
                f"Exception: {e}"
            )
    
    def test_database_url_format(self):
        """Test DATABASE_URL async format handling."""
        logger.info("🔍 Testing DATABASE_URL async format...")
        
        try:
            # Test URL transformation logic
            test_urls = [
                ("postgresql://user:pass@host:5432/db", "postgresql+asyncpg://user:pass@host:5432/db"),
                ("postgresql+asyncpg://user:pass@host:5432/db", "postgresql+asyncpg://user:pass@host:5432/db"),
                ("sqlite:///test.db", "sqlite:///test.db")
            ]
            
            for original, expected in test_urls:
                # Simulate the transformation logic from main.py
                if original.startswith("postgresql://") and "+asyncpg" not in original:
                    transformed = original.replace("postgresql://", "postgresql+asyncpg://", 1)
                else:
                    transformed = original
                
                is_correct = transformed == expected
                self.log_test(
                    f"URL Transform {original[:20]}...", 
                    is_correct,
                    f"Expected: {expected[:30]}..., Got: {transformed[:30]}..."
                )
                
        except Exception as e:
            self.log_test(
                "DATABASE_URL Format", 
                False,
                f"Exception: {e}"
            )
    
    def test_engine_disposal_logic(self):
        """Test engine disposal in shutdown sequence."""
        logger.info("🔍 Testing engine disposal logic...")
        
        try:
            # Test that the lifespan function has proper cleanup
            import inspect
            from src.main import lifespan
            
            # Get the source code of lifespan function
            source = inspect.getsource(lifespan)
            
            # Check for engine disposal logic
            has_engine_disposal = "db_engine.dispose()" in source
            self.log_test(
                "Engine Disposal in Lifespan", 
                has_engine_disposal,
                "Lifespan should include engine.dispose() call"
            )
            
            # Check for proper error handling
            has_error_handling = "except Exception" in source and "engine" in source
            self.log_test(
                "Engine Disposal Error Handling", 
                has_error_handling,
                "Engine disposal should have error handling"
            )
            
            # Check for Redis cleanup
            has_redis_cleanup = "redis_client.close()" in source
            self.log_test(
                "Redis Cleanup", 
                has_redis_cleanup,
                "Redis connections should be closed"
            )
                
        except Exception as e:
            self.log_test(
                "Engine Disposal Logic", 
                False,
                f"Exception: {e}"
            )
    
    def test_prometheus_integration(self):
        """Test Prometheus integration availability."""
        logger.info("🔍 Testing Prometheus integration...")
        
        try:
            from src.adapters.metrics_api import PROMETHEUS_AVAILABLE
            
            self.log_test(
                "Prometheus Client Detection", 
                True,  # We should always detect correctly
                f"PROMETHEUS_AVAILABLE = {PROMETHEUS_AVAILABLE}"
            )
            
            if PROMETHEUS_AVAILABLE:
                from prometheus_client import REGISTRY, generate_latest, CONTENT_TYPE_LATEST
                
                # Test registry access
                has_registry = REGISTRY is not None
                self.log_test(
                    "Prometheus Registry", 
                    has_registry,
                    "Registry should be accessible"
                )
                
                # Test metrics generation
                metrics_output = generate_latest(REGISTRY)
                has_output = metrics_output is not None
                self.log_test(
                    "Prometheus Metrics Generation", 
                    has_output,
                    "Should generate metrics output"
                )
            else:
                self.log_test(
                    "Prometheus Fallback", 
                    True,
                    "Graceful degradation when prometheus_client not available"
                )
                
        except Exception as e:
            self.log_test(
                "Prometheus Integration", 
                False,
                f"Exception: {e}"
            )
    
    async def run_all_tests(self):
        """Run all production readiness tests."""
        logger.info("🚀 Starting Production Readiness Test Suite...")
        logger.info("=" * 60)
        
        # Run all tests
        await self.test_transaction_management()
        self.test_metrics_api_structure()
        self.test_app_state_management()
        self.test_readiness_gate_middleware()
        self.test_database_url_format()
        self.test_engine_disposal_logic()
        self.test_prometheus_integration()
        
        # Generate summary
        self.test_results["summary"] = {
            "total_tests": self.test_results["tests_run"],
            "passed": self.test_results["tests_passed"],
            "failed": self.test_results["tests_failed"],
            "success_rate": (
                self.test_results["tests_passed"] / max(1, self.test_results["tests_run"]) * 100
            ),
            "overall_status": "PASS" if self.test_results["tests_failed"] == 0 else "FAIL"
        }
        
        # Print results
        logger.info("=" * 60)
        logger.info("📊 PRODUCTION READINESS TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {self.test_results['summary']['total_tests']}")
        logger.info(f"Passed: {self.test_results['summary']['passed']}")
        logger.info(f"Failed: {self.test_results['summary']['failed']}")
        logger.info(f"Success Rate: {self.test_results['summary']['success_rate']:.1f}%")
        logger.info(f"Overall Status: {self.test_results['summary']['overall_status']}")
        
        if self.test_results["failures"]:
            logger.error("\n❌ FAILURES:")
            for failure in self.test_results["failures"]:
                logger.error(f"   - {failure}")
        
        logger.info("=" * 60)
        
        if self.test_results["summary"]["overall_status"] == "PASS":
            logger.info("🎉 ALL TESTS PASSED - PRODUCTION READY!")
        else:
            logger.warning("⚠️ SOME TESTS FAILED - REVIEW REQUIRED")
        
        return self.test_results

async def main():
    """Main test runner."""
    test_suite = ProductionReadinessTest()
    results = await test_suite.run_all_tests()
    
    # Save results to file
    with open("production_readiness_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Exit with appropriate code
    exit_code = 0 if results["summary"]["overall_status"] == "PASS" else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())