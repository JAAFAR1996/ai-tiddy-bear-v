"""
Shared test fixtures and utilities for AI Teddy Bear tests.
This provides common test data, mocks, and fixtures used across all test modules.

⚠️  DEPRECATION NOTICE: This file contains mock-based testing fixtures.
    For production-ready integration tests, use tests/conftest_production.py instead.
    New tests should use real services and database operations, not mocks.
"""

import os
import sys
import asyncio
from datetime import datetime

print("[DEBUG] sys.path before modification:", sys.path)
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
print("[DEBUG] Resolved src path:", src_path)
sys.path.insert(0, src_path)
print("[DEBUG] sys.path after modification:", sys.path)
from typing import AsyncGenerator, Generator, Dict, Any
from unittest.mock import AsyncMock, MagicMock, Mock
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.entities import Child, Message, Conversation, User, SafetyResult, AIResponse
from infrastructure.config.production_config import ProductionConfig
from application.services.child_safety_service import ChildSafetyService
from services.service_registry import ServiceRegistry


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Provide test configuration."""
    return {
        "SECRET_KEY": "test-secret-key-32-chars-minimum-length",
        "JWT_SECRET_KEY": "test-jwt-secret-key-32-chars-minimum",
        "COPPA_ENCRYPTION_KEY": "test-coppa-key-32-chars-minimum-length",
        "DATABASE_URL": TEST_DATABASE_URL,
        "REDIS_URL": "redis://localhost:6379/1",
        "OPENAI_API_KEY": "sk-test-key",
        "ENVIRONMENT": "test",
        "DEBUG": True,
        "CORS_ALLOWED_ORIGINS": '["http://localhost:3000"]',
        "PARENT_NOTIFICATION_EMAIL": "parent@test.com",
        "RATE_LIMIT_PER_MINUTE": 100,
        "SESSION_TIMEOUT_MINUTES": 30,
    }


@pytest.fixture
def mock_production_config(test_config, monkeypatch):
    """Mock production configuration."""
    for key, value in test_config.items():
        monkeypatch.setenv(key, str(value))

    config = Mock(spec=ProductionConfig)
    for key, value in test_config.items():
        setattr(config, key, value)

    # Add additional config attributes
    config.get_database_url.return_value = test_config["DATABASE_URL"]
    config.get_redis_url.return_value = test_config["REDIS_URL"]
    config.is_production.return_value = False

    return config


@pytest.fixture
def valid_child() -> Child:
    """Create a valid child entity for testing."""
    return Child(
        id="child-123",
        name="Timmy",
        age=7,
        preferences={"favorite_color": "blue", "interests": ["dinosaurs", "space"]},
        safety_level="strict",
        created_at=datetime.now(),
    )


@pytest.fixture
def valid_child_profile() -> Child:
    """Create a valid child entity for testing (replaces ChildProfile)."""
    return Child.create(
        name="Sarah",
        age=8,
        preferences={"favorite_animal": "cat", "hobbies": ["reading", "drawing"]},
    )


@pytest.fixture
def invalid_child_age_too_young() -> Dict[str, Any]:
    """Create child data with age below COPPA limit."""
    return {"name": "Baby", "age": 2, "preferences": {}}  # Below 3


@pytest.fixture
def invalid_child_age_too_old() -> Dict[str, Any]:
    """Create child data with age above COPPA limit."""
    return {"name": "Teen", "age": 14, "preferences": {}}  # Above 13


@pytest.fixture
def valid_user() -> User:
    """Create a valid user entity for testing."""
    return User(
        id="user-456",
        email="parent@example.com",
        role="parent",
        children=["child-123"],
        created_at=datetime.now(),
        is_active=True,
    )


@pytest.fixture
def sample_message(valid_child) -> Message:
    """Create a sample message for testing."""
    return Message(
        id="msg-789",
        content="Tell me a story about dinosaurs!",
        role="user",
        timestamp=datetime.now(),
        child_id=valid_child.id,
        safety_checked=True,
        safety_score=1.0,
    )


@pytest.fixture
def unsafe_message(valid_child) -> Message:
    """Create an unsafe message for testing."""
    return Message(
        id="msg-unsafe",
        content="Tell me about violence and weapons",
        role="user",
        timestamp=datetime.now(),
        child_id=valid_child.id,
        safety_checked=True,
        safety_score=0.2,
    )


@pytest.fixture
def sample_conversation(valid_child) -> Conversation:
    """Create a sample conversation for testing."""
    return Conversation(
        id="conv-101",
        child_id=valid_child.id,
        started_at=datetime.now(),
        last_activity=datetime.now(),
        status="active",
        context={"session_type": "storytelling"},
    )


@pytest.fixture
def sample_ai_response() -> AIResponse:
    """Create a sample AI response for testing."""
    return AIResponse(
        content="Once upon a time, there was a friendly dinosaur named Rex...",
        emotion="happy",
        safety_score=1.0,
        age_appropriate=True,
        timestamp=datetime.now(),
    )


@pytest.fixture
def unsafe_ai_response() -> AIResponse:
    """Create an unsafe AI response for testing."""
    return AIResponse(
        content="The dinosaur fought violently with weapons...",
        emotion="aggressive",
        safety_score=0.1,
        age_appropriate=False,
        timestamp=datetime.now(),
    )


@pytest.fixture
def safety_result_safe() -> SafetyResult:
    """Create a safe safety result."""
    return SafetyResult(
        is_safe=True,
        safety_score=0.95,
        violations=[],
        filtered_content=None,
        age_appropriate=True,
    )


@pytest.fixture
def safety_result_unsafe() -> SafetyResult:
    """Create an unsafe safety result."""
    return SafetyResult(
        is_safe=False,
        safety_score=0.3,
        violations=["violence", "inappropriate_content"],
        filtered_content="The dinosaur [content filtered] with [content filtered]...",
        age_appropriate=False,
    )


@pytest.fixture
def mock_child_safety_service():
    """Create a mock child safety service."""
    service = Mock(spec=ChildSafetyService)
    service.validate_content = AsyncMock(
        return_value={
            "is_safe": True,
            "confidence": 0.95,
            "issues": [],
            "age_appropriate": True,
            "timestamp": datetime.now().isoformat(),
        }
    )
    service.filter_content = AsyncMock(side_effect=lambda x: x)
    service.log_safety_event = AsyncMock(return_value=True)
    service.get_safety_recommendations = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_ai_service():
    """Create a mock AI service."""
    service = Mock()
    service.generate_response = AsyncMock(
        return_value=AIResponse(
            content="Once upon a time...",
            emotion="happy",
            safety_score=1.0,
            age_appropriate=True,
        )
    )
    service.analyze_emotion = AsyncMock(return_value="happy")
    service.is_available = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_user_repository():
    """Create a mock user repository."""
    repo = Mock()
    repo.get_by_id = AsyncMock()
    repo.get_by_email = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_child_repository():
    """Create a mock child repository."""
    repo = Mock()
    repo.get_by_id = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.get_by_parent_id = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_conversation_repository():
    """Create a mock conversation repository."""
    repo = Mock()
    repo.get_by_id = AsyncMock()
    repo.get_by_child_id = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.add_message = AsyncMock()
    repo.get_messages = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_service_registry(
    mock_ai_service,
    mock_child_safety_service,
    mock_user_repository,
    mock_child_repository,
    mock_conversation_repository,
):
    """Create a mock service registry with all dependencies."""
    registry = Mock(spec=ServiceRegistry)
    registry.get_ai_service = AsyncMock(return_value=mock_ai_service)
    registry.get_child_safety_service = AsyncMock(
        return_value=mock_child_safety_service
    )
    registry.get_user_repository = AsyncMock(return_value=mock_user_repository)
    registry.get_child_repository = AsyncMock(return_value=mock_child_repository)
    registry.get_conversation_repository = AsyncMock(
        return_value=mock_conversation_repository
    )
    return registry


@pytest.fixture
async def async_db_session():
    """Create an async database session for testing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = Mock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=0)
    client.expire = AsyncMock(return_value=True)
    client.incr = AsyncMock(return_value=1)
    client.ping = AsyncMock(return_value=True)
    return client


@pytest.fixture
def auth_headers(valid_user) -> Dict[str, str]:
    """Create authentication headers for testing."""
    # In real tests, this would generate a valid JWT token
    return {"Authorization": "Bearer test-jwt-token", "X-User-ID": valid_user.id}


@pytest.fixture
def rate_limit_headers() -> Dict[str, str]:
    """Create rate limit headers for testing."""
    return {
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Remaining": "59",
        "X-RateLimit-Reset": str(int(datetime.now().timestamp()) + 3600),
    }


# Test data generators
def generate_test_children(count: int = 5) -> list[Child]:
    """Generate multiple test children."""
    return [
        Child(
            id=f"child-{i}",
            name=f"Child{i}",
            age=5 + (i % 9),  # Ages 5-13
            preferences={"test_id": i},
            safety_level="strict" if i % 2 == 0 else "moderate",
        )
        for i in range(count)
    ]


def generate_test_messages(child_id: str, count: int = 10) -> list[Message]:
    """Generate multiple test messages."""
    messages = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append(
            Message(
                id=f"msg-{i}",
                content=f"Test message {i}",
                role=role,
                timestamp=datetime.now(),
                child_id=child_id,
                safety_checked=True,
                safety_score=0.9 + (i % 10) / 100,
            )
        )
    return messages


# Pytest markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "asyncio: Async tests")
