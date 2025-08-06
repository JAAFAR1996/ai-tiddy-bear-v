# Test Implementation Guide - AI Teddy Bear

## Overview

This guide provides concrete examples and patterns for implementing high-quality tests that meet our strict coverage and mutation testing requirements.

## Test Patterns by Type

### 1. Entity Tests (100% Coverage Required)

```python
# tests/unit/test_entities.py

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.core.entities import Child, User, Conversation
from src.core.value_objects import AgeGroup


class TestChildEntity:
    """Comprehensive tests for Child entity."""
    
    def test_child_creation_valid(self):
        """Test creating a valid child entity."""
        child_id = str(uuid4())
        child = Child(
            id=child_id,
            name="Emma",
            age=7,
            parent_id="parent-123",
            created_at=datetime.utcnow()
        )
        
        assert child.id == child_id
        assert child.name == "Emma"
        assert child.age == 7
        assert child.parent_id == "parent-123"
        assert child.age_group == AgeGroup.EARLY_SCHOOL
    
    @pytest.mark.parametrize("age,expected_group", [
        (0, AgeGroup.INFANT),
        (1, AgeGroup.TODDLER),
        (2, AgeGroup.TODDLER),
        (3, AgeGroup.PRESCHOOL),
        (5, AgeGroup.PRESCHOOL),
        (6, AgeGroup.EARLY_SCHOOL),
        (8, AgeGroup.MIDDLE_SCHOOL),
        (10, AgeGroup.LATE_SCHOOL),
        (12, AgeGroup.PRETEEN),
        (13, AgeGroup.PRETEEN),
    ])
    def test_age_group_calculation(self, age, expected_group):
        """Test age group calculation for all ranges."""
        child = Child(
            id=str(uuid4()),
            name="Test",
            age=age,
            parent_id="parent-123"
        )
        assert child.age_group == expected_group
    
    @pytest.mark.parametrize("invalid_age", [-1, -10, 14, 18, 100])
    def test_child_invalid_age_rejected(self, invalid_age):
        """Test that invalid ages are rejected."""
        with pytest.raises(ValueError, match="Age must be between 0 and 13"):
            Child(
                id=str(uuid4()),
                name="Test",
                age=invalid_age,
                parent_id="parent-123"
            )
    
    @pytest.mark.parametrize("invalid_name", ["", "  ", None])
    def test_child_invalid_name_rejected(self, invalid_name):
        """Test that invalid names are rejected."""
        with pytest.raises(ValueError, match="Name cannot be empty"):
            Child(
                id=str(uuid4()),
                name=invalid_name,
                age=7,
                parent_id="parent-123"
            )
    
    def test_child_preferences_immutable(self):
        """Test that preferences cannot be modified after creation."""
        preferences = {"favorite_color": "blue"}
        child = Child(
            id=str(uuid4()),
            name="Test",
            age=7,
            parent_id="parent-123",
            preferences=preferences
        )
        
        # Attempt to modify
        with pytest.raises(AttributeError):
            child.preferences["favorite_color"] = "red"
        
        # Original dict modification doesn't affect entity
        preferences["favorite_color"] = "red"
        assert child.preferences["favorite_color"] == "blue"
```

### 2. Service Tests with Mocking

```python
# tests/unit/test_ai_service.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.application.services.ai.ai_service import AIService
from src.core.entities import Child
from src.core.exceptions import SafetyViolationError


class TestAIService:
    """Tests for AI service with proper mocking."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        client = Mock()
        client.chat.completions.create = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_safety_monitor(self):
        """Mock safety monitor."""
        monitor = Mock()
        monitor.check_content = AsyncMock(return_value={"safe": True, "score": 0.95})
        return monitor
    
    @pytest.fixture
    def ai_service(self, mock_openai_client, mock_safety_monitor):
        """Create AI service with mocked dependencies."""
        return AIService(
            openai_client=mock_openai_client,
            safety_monitor=mock_safety_monitor
        )
    
    @pytest.fixture
    def sample_child(self):
        """Sample child for testing."""
        return Child(
            id="child-123",
            name="Emma",
            age=7,
            parent_id="parent-123"
        )
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self, ai_service, sample_child, mock_openai_client):
        """Test successful AI response generation."""
        # Arrange
        mock_openai_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Hello Emma! How are you today?"))]
        )
        
        # Act
        response = await ai_service.generate_response(
            child=sample_child,
            message="Hi!"
        )
        
        # Assert
        assert response.content == "Hello Emma! How are you today?"
        assert response.is_safe is True
        assert response.safety_score == 0.95
        mock_openai_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_response_unsafe_content_blocked(
        self, ai_service, sample_child, mock_safety_monitor
    ):
        """Test that unsafe content is blocked."""
        # Arrange
        mock_safety_monitor.check_content.return_value = {
            "safe": False,
            "score": 0.3,
            "reason": "Inappropriate content detected"
        }
        
        # Act & Assert
        with pytest.raises(SafetyViolationError) as exc_info:
            await ai_service.generate_response(
                child=sample_child,
                message="Tell me something scary"
            )
        
        assert "Inappropriate content detected" in str(exc_info.value)
        assert exc_info.value.safety_score == 0.3
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("age,expected_model", [
        (2, "gpt-3.5-turbo"),  # Toddler - simple model
        (5, "gpt-4"),          # Preschool - standard model
        (10, "gpt-4"),         # Late school - standard model
    ])
    async def test_model_selection_by_age(
        self, ai_service, mock_openai_client, age, expected_model
    ):
        """Test that appropriate AI model is selected based on age."""
        # Arrange
        child = Child(id="1", name="Test", age=age, parent_id="p1")
        mock_openai_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Response"))]
        )
        
        # Act
        await ai_service.generate_response(child=child, message="Hi")
        
        # Assert
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == expected_model
```

### 3. Integration Tests with Real Dependencies

```python
# tests/integration/test_api_endpoints.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.core.entities import User, Child


@pytest.mark.integration
class TestChildProfileAPI:
    """Integration tests for child profile endpoints."""
    
    @pytest.fixture
    async def authenticated_client(self, client: AsyncClient, test_user: User):
        """Client with authentication headers."""
        token = create_test_jwt(test_user.id)
        client.headers["Authorization"] = f"Bearer {token}"
        return client
    
    @pytest.mark.asyncio
    async def test_create_child_profile_success(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        """Test creating a child profile with valid data."""
        # Arrange
        child_data = {
            "name": "Emma",
            "age": 7,
            "preferences": {
                "favorite_color": "purple",
                "interests": ["dinosaurs", "space"]
            }
        }
        
        # Act
        response = await authenticated_client.post(
            "/api/v1/children",
            json=child_data
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Emma"
        assert data["age"] == 7
        assert data["age_group"] == "early_school"
        assert "id" in data
        
        # Verify in database
        child = await db_session.get(Child, data["id"])
        assert child is not None
        assert child.name == "Emma"
    
    @pytest.mark.asyncio
    async def test_create_child_profile_duplicate_name_rejected(
        self, authenticated_client: AsyncClient, existing_child: Child
    ):
        """Test that duplicate child names for same parent are rejected."""
        # Arrange
        child_data = {
            "name": existing_child.name,  # Duplicate
            "age": 5
        }
        
        # Act
        response = await authenticated_client.post(
            "/api/v1/children",
            json=child_data
        )
        
        # Assert
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_data,expected_error", [
        ({"name": "", "age": 5}, "Name cannot be empty"),
        ({"name": "Test", "age": -1}, "Age must be between 0 and 13"),
        ({"name": "Test", "age": 15}, "Age must be between 0 and 13"),
        ({"name": "Test"}, "Age is required"),
        ({"age": 5}, "Name is required"),
    ])
    async def test_create_child_profile_validation(
        self, authenticated_client: AsyncClient, invalid_data, expected_error
    ):
        """Test validation of child profile data."""
        response = await authenticated_client.post(
            "/api/v1/children",
            json=invalid_data
        )
        
        assert response.status_code == 422
        assert expected_error in response.text
```

### 4. Performance Tests

```python
# tests/performance/test_response_times.py

import pytest
import asyncio
import time
from statistics import mean, stdev

from src.application.services.ai.ai_service import AIService


@pytest.mark.performance
class TestResponseTimePerformance:
    """Performance tests for response time requirements."""
    
    @pytest.fixture
    def performance_monitor(self):
        """Monitor for tracking performance metrics."""
        class Monitor:
            def __init__(self):
                self.times = []
            
            def record(self, duration):
                self.times.append(duration)
            
            @property
            def avg(self):
                return mean(self.times) if self.times else 0
            
            @property
            def p95(self):
                if not self.times:
                    return 0
                sorted_times = sorted(self.times)
                idx = int(len(sorted_times) * 0.95)
                return sorted_times[idx]
        
        return Monitor()
    
    @pytest.mark.asyncio
    async def test_ai_response_time_under_500ms(self, ai_service, sample_child, performance_monitor):
        """Test that AI responses are generated within 500ms."""
        # Warm up
        await ai_service.generate_response(sample_child, "Hi")
        
        # Test
        for _ in range(20):
            start = time.perf_counter()
            await ai_service.generate_response(sample_child, "Tell me a joke")
            duration = time.perf_counter() - start
            performance_monitor.record(duration)
        
        # Assert
        assert performance_monitor.avg < 0.5, f"Average response time {performance_monitor.avg:.3f}s exceeds 500ms"
        assert performance_monitor.p95 < 0.7, f"95th percentile {performance_monitor.p95:.3f}s exceeds 700ms"
    
    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, ai_service, performance_monitor):
        """Test handling multiple concurrent requests."""
        children = [
            Child(id=f"child-{i}", name=f"Child{i}", age=7, parent_id=f"parent-{i}")
            for i in range(10)
        ]
        
        async def make_request(child):
            start = time.perf_counter()
            await ai_service.generate_response(child, "Hi")
            return time.perf_counter() - start
        
        # Run 10 concurrent requests
        start = time.perf_counter()
        times = await asyncio.gather(*[make_request(child) for child in children])
        total_time = time.perf_counter() - start
        
        # Assert
        assert total_time < 2.0, f"10 concurrent requests took {total_time:.3f}s"
        assert max(times) < 1.0, f"Slowest request took {max(times):.3f}s"
```

### 5. Security Tests

```python
# tests/security/test_authentication.py

import pytest
import jwt
from datetime import datetime, timedelta

from src.infrastructure.security.auth import (
    create_access_token,
    verify_token,
    hash_password,
    verify_password
)


@pytest.mark.security
class TestAuthentication:
    """Security tests for authentication system."""
    
    def test_password_hashing_uses_argon2(self):
        """Test that passwords are hashed with Argon2."""
        password = "MySecurePassword123!"
        hashed = hash_password(password)
        
        assert hashed.startswith("$argon2")
        assert len(hashed) > 60
        assert password not in hashed
    
    def test_password_verification_timing_safe(self):
        """Test that password verification is timing-safe."""
        password = "MySecurePassword123!"
        hashed = hash_password(password)
        
        # Time correct password
        times_correct = []
        for _ in range(100):
            start = time.perf_counter_ns()
            verify_password(password, hashed)
            times_correct.append(time.perf_counter_ns() - start)
        
        # Time incorrect password
        times_incorrect = []
        for _ in range(100):
            start = time.perf_counter_ns()
            verify_password("WrongPassword", hashed)
            times_incorrect.append(time.perf_counter_ns() - start)
        
        # Check timing difference is minimal (< 10% difference in averages)
        avg_correct = mean(times_correct)
        avg_incorrect = mean(times_incorrect)
        difference = abs(avg_correct - avg_incorrect) / avg_correct
        
        assert difference < 0.1, f"Timing difference {difference:.2%} may be exploitable"
    
    def test_jwt_token_expiration_enforced(self):
        """Test that expired tokens are rejected."""
        # Create token that expires in 1 second
        token = create_access_token(
            data={"sub": "user-123"},
            expires_delta=timedelta(seconds=1)
        )
        
        # Verify immediately - should work
        payload = verify_token(token)
        assert payload["sub"] == "user-123"
        
        # Wait for expiration
        time.sleep(2)
        
        # Verify after expiration - should fail
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_token(token)
    
    @pytest.mark.parametrize("malicious_input", [
        "' OR '1'='1",  # SQL injection
        "<script>alert('xss')</script>",  # XSS
        "../../../etc/passwd",  # Path traversal
        "'; DROP TABLE users; --",  # SQL injection
    ])
    def test_malicious_input_sanitized(self, client, malicious_input):
        """Test that malicious inputs are properly sanitized."""
        response = client.post("/api/v1/login", json={
            "username": malicious_input,
            "password": "password"
        })
        
        # Should fail gracefully, not execute malicious code
        assert response.status_code in [400, 401, 422]
        assert "script" not in response.text.lower()
        assert "drop table" not in response.text.lower()
```

### 6. Mutation Testing Validators

```python
# tests/unit/test_mutation_validators.py

import pytest
from src.core.value_objects import SafetyScore


class TestMutationKillers:
    """Tests specifically designed to kill mutations."""
    
    def test_safety_score_boundary_exact(self):
        """Kill mutations that change comparison operators."""
        # Boundary value tests
        assert SafetyScore(0.79).is_safe() is False  # Just below threshold
        assert SafetyScore(0.80).is_safe() is True   # Exactly at threshold
        assert SafetyScore(0.81).is_safe() is True   # Just above threshold
        
        # This kills mutations like:
        # - score >= 0.8 → score > 0.8
        # - score >= 0.8 → score <= 0.8
    
    def test_arithmetic_operations_exact(self):
        """Kill arithmetic operator mutations."""
        from src.core.calculations import calculate_discount
        
        # Test exact calculations
        assert calculate_discount(100, 10) == 90  # 100 - 10
        assert calculate_discount(100, 0) == 100  # No discount
        assert calculate_discount(50, 50) == 0    # Full discount
        
        # This kills mutations like:
        # - price - discount → price + discount
        # - price - discount → price * discount
    
    def test_boolean_logic_all_paths(self):
        """Kill boolean operator mutations."""
        from src.core.validators import is_valid_age_and_consent
        
        # Test all combinations
        assert is_valid_age_and_consent(7, True) is True    # Both true
        assert is_valid_age_and_consent(7, False) is False  # Age OK, no consent
        assert is_valid_age_and_consent(15, True) is False  # Age bad, consent OK
        assert is_valid_age_and_consent(15, False) is False # Both false
        
        # This kills mutations like:
        # - age_valid AND consent → age_valid OR consent
```

## Testing Anti-Patterns to Avoid

### ❌ Don't Write Fake Tests

```python
# BAD - Fake test
def test_something():
    assert True  # Provides no value

# BAD - Test without assertions
def test_user_creation():
    user = User(name="Test")
    # No assertions!

# GOOD - Real test with meaningful assertions
def test_user_creation():
    user = User(name="Test", email="test@example.com")
    assert user.name == "Test"
    assert user.email == "test@example.com"
    assert user.id is not None
```

### ❌ Don't Over-Mock

```python
# BAD - Mocking everything
def test_service(mock_db, mock_cache, mock_logger, mock_validator, mock_auth):
    # Too many mocks - probably testing implementation, not behavior
    
# GOOD - Mock only external dependencies
def test_service(mock_external_api):
    # Use real validator, real business logic
    # Only mock what you don't control
```

### ❌ Don't Write Non-Deterministic Tests

```python
# BAD - Flaky test
def test_with_current_time():
    user = create_user()
    assert user.created_at.hour == datetime.now().hour  # May fail at hour boundary

# GOOD - Deterministic
def test_with_fixed_time(freezer):
    freezer.move_to("2024-01-15 10:30:00")
    user = create_user()
    assert user.created_at == datetime(2024, 1, 15, 10, 30, 0)
```

## Continuous Improvement

### Weekly Tasks
1. Run mutation testing: `make mutation`
2. Review coverage report: `make coverage`
3. Fix any new flaky tests
4. Update test templates

### Monthly Tasks
1. Performance baseline: `make performance`
2. Security audit: `make security`
3. Review and update test patterns
4. Analyze test execution times

### Metrics to Track
- Coverage percentage (target: 80%+)
- Mutation score (target: 70%+)
- Average test execution time
- Number of flaky tests (target: 0)
- Tests per source file ratio

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Mutation Testing Guide](https://github.com/mutpy/mutpy)
- [Property-Based Testing](https://hypothesis.works/)
- [Test Patterns](https://martinfowler.com/articles/mocksArentStubs.html)

Remember: **Every line of code must be protected by real, meaningful tests.**