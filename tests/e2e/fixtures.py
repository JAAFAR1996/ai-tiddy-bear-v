"""
E2E Test Fixtures - Reusable Test Components
=============================================
Pytest fixtures for E2E testing:
- Test users and authentication
- Test children with COPPA compliance
- Test conversations and messages
- Database and client fixtures
- Mock services and data
"""

import pytest
import asyncio
import uuid
from typing import Dict, Any, AsyncGenerator, Optional
from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .base import E2ETestConfig, TestDataManager
from src.infrastructure.database import (
    initialize_database_infrastructure,
    shutdown_database_infrastructure,
    database_manager,
    get_user_repository,
    get_child_repository,
    get_conversation_repository
)
from src.infrastructure.config import get_config_manager
from src.core.security.auth_manager import AuthManager


# Configuration fixtures
@pytest.fixture(scope="session")
def e2e_config() -> E2ETestConfig:
    """E2E test configuration."""
    config_manager = get_config_manager()
    
    return E2ETestConfig(
        base_url=config_manager.get("TEST_BASE_URL", "http://localhost:8000"),
        test_database_url=config_manager.get("TEST_DATABASE_URL"),
        cleanup_after_test=config_manager.get_bool("TEST_CLEANUP", True),
        enable_security_tests=config_manager.get_bool("TEST_SECURITY", True),
        enable_child_safety_tests=config_manager.get_bool("TEST_CHILD_SAFETY", True)
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Database fixtures
@pytest.fixture(scope="session")
async def test_database(e2e_config: E2ETestConfig):
    """Initialize test database for entire test session."""
    # Set test database URL if provided
    if e2e_config.test_database_url:
        import os
        os.environ["DATABASE_URL"] = e2e_config.test_database_url
    
    # Initialize database
    await initialize_database_infrastructure()
    
    yield database_manager
    
    # Cleanup
    await shutdown_database_infrastructure()


@pytest.fixture
async def db_session(test_database) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for test."""
    async with database_manager.primary_node.acquire_connection() as conn:
        yield conn


@pytest.fixture
async def data_manager(e2e_config: E2ETestConfig) -> TestDataManager:
    """Test data manager for creating test entities."""
    manager = TestDataManager(e2e_config)
    yield manager
    await manager.cleanup()


# User fixtures
@pytest.fixture
async def test_user(data_manager: TestDataManager) -> Dict[str, Any]:
    """Create a test user."""
    return await data_manager.create_test_user(role="user")


@pytest.fixture
async def test_parent(data_manager: TestDataManager) -> Dict[str, Any]:
    """Create a test parent user."""
    return await data_manager.create_test_user(
        role="parent",
        display_name="Test Parent",
        settings={
            "notifications_enabled": True,
            "child_safety_level": "strict"
        }
    )


@pytest.fixture
async def test_admin(data_manager: TestDataManager) -> Dict[str, Any]:
    """Create a test admin user."""
    return await data_manager.create_test_user(
        role="admin",
        display_name="Test Admin",
        is_verified=True
    )


# Child fixtures
@pytest.fixture
async def test_child(test_parent: Dict[str, Any], data_manager: TestDataManager) -> Dict[str, Any]:
    """Create a test child with parental consent."""
    parent_id = uuid.UUID(test_parent["id"])
    
    return await data_manager.create_test_child(
        parent_id=parent_id,
        name="Test Child",
        estimated_age=8,
        parental_consent=True,
        content_filtering_enabled=True,
        safety_level="safe"
    )


@pytest.fixture
async def test_child_under_13(test_parent: Dict[str, Any], data_manager: TestDataManager) -> Dict[str, Any]:
    """Create a test child under 13 (COPPA protected)."""
    parent_id = uuid.UUID(test_parent["id"])
    
    return await data_manager.create_test_child(
        parent_id=parent_id,
        name="Young Test Child",
        estimated_age=6,
        parental_consent=True,
        data_retention_days=30,  # Shorter retention for younger children
        allow_data_sharing=False
    )


@pytest.fixture
async def test_child_no_consent(test_parent: Dict[str, Any], data_manager: TestDataManager) -> Dict[str, Any]:
    """Create a test child without parental consent (for testing restrictions)."""
    parent_id = uuid.UUID(test_parent["id"])
    
    return await data_manager.create_test_child(
        parent_id=parent_id,
        name="No Consent Child",
        estimated_age=10,
        parental_consent=False,
        interaction_logging_enabled=False
    )


# Conversation fixtures
@pytest.fixture
async def test_conversation(test_child: Dict[str, Any], db_session) -> Dict[str, Any]:
    """Create a test conversation."""
    conversation_repo = await get_conversation_repository()
    
    conversation_data = {
        "child_id": uuid.UUID(test_child["id"]),
        "title": "Test Conversation",
        "status": "active",
        "safety_checked": False,
        "parental_review_required": test_child["coppa_protected"],
        "educational_content": True
    }
    
    conversation = await conversation_repo.create(conversation_data)
    
    return {
        "id": str(conversation.id),
        "child_id": str(conversation.child_id),
        "title": conversation.title,
        "status": conversation.status.value,
        "created_at": conversation.created_at.isoformat()
    }


# HTTP client fixtures
@pytest.fixture
async def test_client(e2e_config: E2ETestConfig) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated test client."""
    async with AsyncClient(
        base_url=e2e_config.base_url,
        timeout=e2e_config.default_timeout
    ) as client:
        yield client


@pytest.fixture
async def authenticated_client(test_client: AsyncClient, test_user: Dict[str, Any]) -> AsyncClient:
    """Authenticated test client with regular user."""
    # Login to get token
    response = await test_client.post(
        "/api/v1/auth/login",
        json={
            "username": test_user["username"],
            "password": "test_password"
        }
    )
    
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    # Set authorization header
    test_client.headers["Authorization"] = f"Bearer {token}"
    
    return test_client


@pytest.fixture
async def parent_client(test_client: AsyncClient, test_parent: Dict[str, Any]) -> AsyncClient:
    """Authenticated test client with parent user."""
    # Create auth manager
    auth_manager = AuthManager()
    
    # Generate token for parent
    token = auth_manager.create_access_token(
        user_id=test_parent["id"],
        username=test_parent["username"],
        role=test_parent["role"]
    )
    
    # Set authorization header
    test_client.headers["Authorization"] = f"Bearer {token}"
    
    return test_client


@pytest.fixture
async def admin_client(test_client: AsyncClient, test_admin: Dict[str, Any]) -> AsyncClient:
    """Authenticated test client with admin user."""
    # Create auth manager
    auth_manager = AuthManager()
    
    # Generate token for admin
    token = auth_manager.create_access_token(
        user_id=test_admin["id"],
        username=test_admin["username"],
        role=test_admin["role"]
    )
    
    # Set authorization header
    test_client.headers["Authorization"] = f"Bearer {token}"
    
    return test_client


# Mock data fixtures
@pytest.fixture
def mock_ai_response() -> Dict[str, Any]:
    """Mock AI response for testing."""
    return {
        "text": "Hello! I'm your friendly AI teddy bear. How can I help you today?",
        "audio_url": "https://example.com/audio/response.mp3",
        "emotion": "happy",
        "safety_score": 0.95,
        "educational_value": 0.8
    }


@pytest.fixture
def mock_child_message() -> Dict[str, Any]:
    """Mock child message for testing."""
    return {
        "content": "Can you tell me a story about dinosaurs?",
        "audio_url": "https://example.com/audio/child_message.mp3",
        "duration": 3.5,
        "detected_emotion": "curious"
    }


@pytest.fixture
def mock_safety_report() -> Dict[str, Any]:
    """Mock safety report for testing."""
    return {
        "report_type": "inappropriate_content",
        "severity": "low",
        "description": "Mild inappropriate language detected",
        "detected_by_ai": True,
        "ai_confidence": 0.78,
        "action_taken": "content_filtered",
        "parent_notified": False
    }


# Helper fixtures
@pytest.fixture
def auth_headers(test_user: Dict[str, Any]) -> Dict[str, str]:
    """Get authentication headers for requests."""
    auth_manager = AuthManager()
    token = auth_manager.create_access_token(
        user_id=test_user["id"],
        username=test_user["username"],
        role=test_user["role"]
    )
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def coppa_headers() -> Dict[str, str]:
    """Headers for COPPA compliance testing."""
    return {
        "X-Child-Safety-Enabled": "true",
        "X-Parental-Consent": "verified",
        "X-Data-Retention-Days": "90"
    }


# Cleanup fixtures
@pytest.fixture(autouse=True)
async def cleanup_test_data(request, data_manager: TestDataManager):
    """Automatically cleanup test data after each test."""
    yield
    
    # Only cleanup if test passed or cleanup is forced
    if request.node.rep_call.passed or data_manager.config.cleanup_after_test:
        await data_manager.cleanup()


# Performance testing fixtures
@pytest.fixture
def performance_threshold() -> Dict[str, float]:
    """Performance thresholds for different operations."""
    return {
        "api_response": 200.0,  # 200ms for API responses
        "database_query": 50.0,  # 50ms for database queries
        "ai_processing": 1000.0,  # 1s for AI processing
        "audio_generation": 2000.0,  # 2s for audio generation
        "file_upload": 5000.0  # 5s for file uploads
    }


# Mock service fixtures
@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    class MockEmailService:
        async def send_email(self, to: str, subject: str, body: str) -> bool:
            return True
        
        async def send_parent_notification(self, parent_email: str, notification_type: str, data: Dict[str, Any]) -> bool:
            return True
    
    return MockEmailService()


@pytest.fixture
def mock_push_notification_service():
    """Mock push notification service for testing."""
    class MockPushNotificationService:
        async def send_notification(self, device_token: str, title: str, body: str, data: Optional[Dict[str, Any]] = None) -> bool:
            return True
        
        async def send_safety_alert(self, parent_device_token: str, alert_data: Dict[str, Any]) -> bool:
            return True
    
    return MockPushNotificationService()


# Test scenario fixtures
@pytest.fixture
async def complete_test_scenario(test_parent, test_child, test_conversation):
    """Complete test scenario with parent, child, and conversation."""
    return {
        "parent": test_parent,
        "child": test_child,
        "conversation": test_conversation
    }


@pytest.fixture
async def multi_child_family(test_parent, data_manager):
    """Test family with multiple children of different ages."""
    children = []
    
    # Create children of different ages
    ages = [5, 8, 12, 15]
    for age in ages:
        child = await data_manager.create_test_child(
            parent_id=uuid.UUID(test_parent["id"]),
            name=f"Child Age {age}",
            estimated_age=age,
            parental_consent=True
        )
        children.append(child)
    
    return {
        "parent": test_parent,
        "children": children
    }