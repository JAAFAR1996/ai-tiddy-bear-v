"""
End-to-End Testing Framework - Production E2E Test Suite
========================================================
Comprehensive E2E testing framework for AI Teddy Bear with:
- Full API integration testing
- Child safety scenario testing
- Performance and load testing
- Security testing
- COPPA compliance validation
- Multi-environment support
- Test data management
- Automated reporting
"""

from .base import (
    E2ETestBase,
    E2ETestConfig,
    TestEnvironment,
    TestDataManager,
    TestReporter,
    performance_test,
    security_test,
    child_safety_test
)

from .fixtures import (
    test_user,
    test_parent,
    test_child,
    test_conversation,
    test_database,
    test_client,
    authenticated_client,
    admin_client
)

from .utils import (
    generate_test_data,
    cleanup_test_data,
    wait_for_condition,
    retry_on_failure,
    measure_performance,
    validate_response,
    validate_child_safety
)

__all__ = [
    # Base classes
    "E2ETestBase",
    "E2ETestConfig", 
    "TestEnvironment",
    "TestDataManager",
    "TestReporter",
    
    # Decorators
    "performance_test",
    "security_test",
    "child_safety_test",
    
    # Fixtures
    "test_user",
    "test_parent",
    "test_child",
    "test_conversation",
    "test_database",
    "test_client",
    "authenticated_client",
    "admin_client",
    
    # Utilities
    "generate_test_data",
    "cleanup_test_data",
    "wait_for_condition",
    "retry_on_failure",
    "measure_performance",
    "validate_response",
    "validate_child_safety"
]